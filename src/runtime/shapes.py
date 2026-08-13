"""Field-shape engine runtime — extractors + diff over the shared descriptor.

Implements `core/shape-engine.md` for the live stacks the step-0 experiments validated
(rescue: WEAK → standalone extractors are Plan A; greenfield: STRONG → generated layers,
guarded by this very diff as the CI drift-check):

- extract_contract    : the carrier (contract.json descriptor set) — greenfield's source
- extract_sqlalchemy  : SQLAlchemy declarative models, BOTH idioms — 2.0 `Mapped`/`mapped_column`
                        and 1.x `x = Column(...)` — with mixin columns and an inherited
                        `__tablename__` resolved statically (Python `ast`, no imports)
- extract_pydantic    : Pydantic-v2 DTOs (`<Entity>Read` = full projection, `<Entity>Create`
                        = partial: present fields must match, missing ones are not drift), with a
                        project-local base chain resolved across a bounded parse batch
- extract_typescript  : `export interface` / `export type` unions (tree-sitter primary; line parser fallback)
- extract_ddl         : Postgres `CREATE TABLE` / `CREATE TYPE ... AS ENUM` (tree-sitter primary; regex fallback)

Every representation reduces to `{name, type, nullable, enum?, constraints?}` with a canonical
type (string|int|float|bool|enum|uuid|json|datetime), then `diff_shapes` compares any two
projections. The three honesty rules are enforced:
  1. uncertain equivalence → `confidence: ambiguous`, downgraded to a note, never asserted;
  2. a field absent on one side IS the finding (missing_field) — never papered over;
  3. a side that extracted NOTHING is a refusal (`EmptyExtraction`), never an empty finding list —
     "I parsed neither layer" and "these layers agree" must not be the same value. Enforced at
     every entry point that extracts: `drift_check` (carrier AND each layer it was handed),
     `reconcile_layers`, `propose_correspondence`. `diff_shapes` takes two dicts somebody else
     extracted and cannot tell an empty one from an empty file, so it is not one of them.
Structural noise is classified rather than filtered: a finding may carry `structural_tier`,
`relation_pair`/`relation_role` or `entity_key_source`, and carries its own kind and count either
way, so a clustering pass can fold it and a measurement can still count it.

Extraction is **tree-sitter-primary** (`runtime/treesitter_extract.py`): a real grammar parses the
whole language, so real-world TS/GraphQL/SQL just works — no per-repo regex patches. The stdlib
line/`ast`/regex parsers here are the always-available fallback (used when tree-sitter is absent);
the Python `ast` extractors (SQLAlchemy/Pydantic/Django) are already full parsers and stay as-is.
Findings are dicts shaped to feed `runtime/ledger.py` contract_mismatch pins.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
from typing import Optional

CANONICAL = ("string", "int", "float", "bool", "enum", "uuid", "json", "datetime")

# Layers with no native uuid/datetime: both travel as `string`, so string ⟷ uuid/datetime is not
# drift across such a boundary (see diff_shapes). Never inferred — the type system's own fact.
# `graphql` is here because an SDL has neither scalar: a timestamp is a String or a custom scalar
# the schema itself declares, exactly the JS/TS situation.
_STRINGLY_LAYERS = ("client", "typescript", "ts", "graphql", "api:graphql")

# …of those, the layers whose language also has ONE number type, so int ⟷ float is not drift
# either. GraphQL is deliberately NOT here: it has `Int` and `Float` and can get the distinction
# wrong, which is a finding. The two equivalences were one tuple until this split; a single tuple
# would have bought GraphQL's `ID` fix by silently granting it a numeric equivalence it does not
# have, and a table entry that carries an unstated second rule is the drift this engine exists to
# find, sitting in the engine.
_ONE_NUMBER_LAYERS = ("client", "typescript", "ts")

# GraphQL layer labels, for the `ID` rule in diff_shapes. `reconcile_layers` passes the stack name
# (`graphql`); `drift_check` labels it `api:graphql` — both are the same boundary.
_GRAPHQL_LAYERS = ("graphql", "api:graphql")

# ---------------------------------------------------------------------------
# descriptor helpers
# ---------------------------------------------------------------------------


def descriptor(name: str, type_: str, nullable: bool, enum: Optional[list] = None,
               constraints: Optional[dict] = None, confidence: str = "extracted") -> dict:
    d = {"name": name, "type": type_, "nullable": nullable, "confidence": confidence}
    if enum:
        d["enum"] = list(enum)
    if constraints:
        d["constraints"] = constraints
    return d


class Extraction(dict):
    """`{entity: {field: descriptor}}` — a dict everywhere it is read, plus `entity_meta`.

    The descriptor has a slot for everything a FIELD can be uncertain about (`confidence`) and none
    for the one thing an ENTITY KEY can be uncertain about: whether the key is the name the source
    declared (a `__tablename__`, a `model User {`, a `CREATE TABLE`) or one the extractor derived
    because the source declares it somewhere the extractor cannot read without executing an import.
    A diff keyed on a derived name is a weaker claim than one keyed on a declared name, and saying
    so is this class's whole job.

    Read with `getattr(shapes, "entity_meta", {})`: every other extractor returns a plain dict and
    must keep working, so nothing may depend on the attribute existing.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: entity key → {"key_source": "class_name", "why": "…"}. Absent key ⇒ declared.
        self.entity_meta: dict[str, dict] = {}


class EmptyExtraction(RuntimeError):
    """A side of a diff read ZERO entities. Raised instead of returning an empty finding list.

    `reconcile_layers` used to answer `[]` for two different states — *these layers agree* and
    *I parsed neither* — and the second is the more common one on a real repository. Measured on
    `Netflix/dispatch` (`docs/measurements.md`): 65 `models.py` files, 0 entities from the ORM side,
    0 findings, and nothing in the output said the extractor had not read a thing. An empty diff
    over an empty extraction is the failure mode most easily mistaken for a clean bill of health,
    so this is the same refusal `_treesitter_only` makes rather than returning `{}`.

    `sides` carries the machine-readable half: one entry per empty side with its layer, its path,
    and the preconditions that extractor needs met before it can report anything.
    """

    def __init__(self, sides: list[dict]):
        self.sides = sides
        detail = "; ".join(
            f"{s['layer']} read 0 entities from {s['path']} (expected: {s['expects']})"
            for s in sides)
        super().__init__(
            "refusing to report a diff over nothing — " + detail
            + ". An empty finding list would be indistinguishable from two layers that agree.")


#: What each extractor must SEE before it can report an entity — the preconditions a null result
#: means were not met. Stated per stack because "0 entities" is never the answer to the operator's
#: question; "your models use an idiom this extractor does not read" is.
_EXTRACTOR_EXPECTS = {
    "contract": "a carrier declaring at least one entity under `entities`",
    "ddl": "`CREATE TABLE <name> ( … );` statements",
    "sqlalchemy": "declarative classes with a `__tablename__`, or with at least one "
                  "`x = Column(…)` / `x: Mapped[…] = mapped_column(…)` assignment",
    "pydantic": "classes whose base chain reaches a `BaseModel` inside this file or within "
                "`_MAX_IMPORT_HOPS` static import hops of it",
    "typescript": "`export interface X { … }` / `export type X = …` declarations",
    "drizzle": "`export const x = pgTable('name', { … })` declarations",
    "prisma": "`model X { … }` blocks",
    "django": "`class X(models.Model):` classes with `models.*Field(…)` attributes",
    "graphql": "`type X { … }` object type definitions (an SDL of only `input`/`scalar` "
               "definitions extracts nothing)",
    "go": "exported structs with typed fields",
    "java": "classes with typed fields",
    "rust": "structs with typed fields",
    "csharp": "classes with typed properties",
}


def _refuse_if_empty(*sides: tuple[str, str, dict]) -> None:
    """Raise `EmptyExtraction` if any (layer, path, shapes) side extracted no entities."""
    empty = [{"layer": layer, "path": str(path),
              "expects": _EXTRACTOR_EXPECTS.get(layer, "entities this extractor can read")}
             for layer, path, extracted in sides if not extracted]
    if empty:
        raise EmptyExtraction(empty)


def _try_treesitter(lang: str, text: str, backend: str):
    """Tree-sitter backend selector for an extractor. `backend`:
      - "auto"       (default) — the tree-sitter parse when installed (a real grammar, robust on
                     real-world code with no per-repo patches), else transparently fall back to the
                     stdlib parser. Tree-sitter is the primary path; bootstrap installs it.
      - "regex"      — force the stdlib line/regex parser (the always-available fallback; used in a
                     stdlib-only environment, or to compare paths).
      - "treesitter" — force tree-sitter; raise if it is not installed.
    Returns the extracted `{entity: {field: descriptor}}`, or None to fall through to stdlib."""
    if backend == "regex":
        return None
    if backend not in ("auto", "treesitter"):
        raise ValueError(f"backend must be regex|auto|treesitter, got {backend!r}")
    try:
        import treesitter_extract as _ts
    except Exception:
        _ts = None
    # Probe THIS grammar, not the library. `available()` with no argument answers "is tree-sitter
    # installed", which stopped implying "can it parse Go" the day the language pack started
    # downloading grammars on first use — and never implied it for someone carrying individual
    # `tree_sitter_<lang>` modules. See treesitter_extract.available().
    if _ts is None or not _ts.available(lang):
        if backend == "treesitter":
            raise RuntimeError(f"backend='treesitter' requested but no usable {lang!r} grammar "
                               "(pip install tree-sitter tree-sitter-language-pack; grammars are "
                               "fetched on first use, so this also fails with no network)")
        return None
    try:
        return _ts.extract(text, lang)
    except _ts.TreeSitterUnavailable:
        # `auto` promises to "transparently fall back", and a promise the code does not keep is the
        # bug this package exists to find. The probe above makes this nearly unreachable — nearly is
        # not never: the grammar can load and the download can still fail on a second grammar, and
        # `available()` is a probe, not a lock. An explicit backend='treesitter' still fails loudly,
        # because that caller asked for tree-sitter and silence would be the wrong answer.
        if backend == "treesitter":
            raise
        return None


# ---------------------------------------------------------------------------
# carrier (contract.json)
# ---------------------------------------------------------------------------


def extract_contract(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict]] = {}
    for entity, spec in data.get("entities", {}).items():
        fields = {}
        for f in spec.get("fields", []):
            fields[f["name"]] = descriptor(
                f["name"], f["type"], bool(f.get("nullable", False)),
                f.get("enum"), f.get("constraints"),
            )
        out[entity] = fields
    return out


def contract_tables(path: str | pathlib.Path) -> dict[str, str]:
    """table name → entity name (for the DDL layer). The contract must declare `table` per entity:
    a table name is a decision, never guessed by pluralizing the entity name (English-specific)."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for entity, spec in data.get("entities", {}).items():
        table = spec.get("table")
        if not table:
            raise ValueError(
                f"contract entity {entity!r} has no `table`: declare it explicitly "
                f"(the table name is a decision, never guessed from the entity name)")
        out[table] = entity
    return out


# ---------------------------------------------------------------------------
# the static base-chain resolver (shared by the two Python extractors)
# ---------------------------------------------------------------------------

# HYPOTHESIS, tunable — how many `from x.y import Base` hops the base-chain resolver follows out of
# the file it was handed. It is not a performance knob, it is the honesty bound on the phrase "the
# parse batch": a base that resolves within it is a class this extractor READ, and one that does not
# is left unresolved rather than guessed at by name. 2 is the depth the observed shape needs — a DTO
# inheriting a project base (`IncidentBase(DispatchBase)`) that inherits `BaseModel` in a shared
# module one hop away (Netflix/dispatch, `dispatch/models.py`) — plus one, so a base re-exported
# through a package `__init__` still resolves. Deeper chains extract as nothing, which is the
# refusal above rather than a silent miss.
_MAX_IMPORT_HOPS = 2


def _base_names(node: ast.ClassDef) -> list[str]:
    """Base class names as bare identifiers: `pydantic.BaseModel` → `BaseModel`, `Generic[T]` →
    `Generic`. Text off the AST — nothing is imported, so nothing is executed."""
    out: list[str] = []
    for b in node.bases:
        expr = b
        while isinstance(expr, ast.Subscript):
            expr = expr.value
        if isinstance(expr, ast.Attribute):
            out.append(expr.attr)
        elif isinstance(expr, ast.Name):
            out.append(expr.id)
        else:
            out.append(ast.unparse(expr))
    return out


class _ModuleBatch:
    """Resolve a class NAME to the `ast.ClassDef` that defines it, across a bounded parse batch.

    Both Python extractors used to stop at the file they were given, and both preconditions that
    cost were measured rather than imagined (`docs/measurements.md`, `Netflix/dispatch`): 131 DTOs
    inherit a project-local `DispatchBase` and were invisible because the base is not literally
    named `BaseModel`, and every ORM class inherits its `__tablename__` from a base in another
    module. The batch is the fix and its limit is stated: **at most `_MAX_IMPORT_HOPS` files, all
    parsed, none imported.** A module path is matched against directories on disk (the source file's
    ancestors, so `from dispatch.models import X` inside `<root>/src/dispatch/incident/models.py`
    finds `<root>/src/dispatch/models.py`); a name that does not resolve stays unresolved.

    Degrades rather than fails: an unreadable or unparsable NEIGHBOUR yields no classes, never an
    exception, because an extractor that dies on somebody else's syntax error reads nothing at all.
    The file the caller HANDED IN is not a neighbour — see `module(primary=True)`.
    """

    def __init__(self, hops: int = _MAX_IMPORT_HOPS):
        self.hops = hops
        self._cache: dict[pathlib.Path, tuple] = {}

    def module(self, path: str | pathlib.Path,
               primary: bool = False) -> tuple[Optional[ast.Module], dict]:
        """`(tree, {class name: ClassDef})` for a file, parsed at most once per batch.

        `primary=True` for the file the CALLER named: its own failure to read or parse is re-raised
        instead of degrading to no classes. The two answers are different findings and the operator
        acts on them differently — *this file does not parse* versus *this file uses an idiom the
        extractor does not read* — and the degradation flattened the first onto the second, because
        an empty extraction now surfaces as `EmptyExtraction`, whose message states the idiom it
        expected and says nothing about syntax. Same flattening as an empty diff read as agreement,
        one level down. A realistic trigger, not a hypothetical: a PEP 695 `type` statement read by
        an older interpreter on a matrix leg.
        """
        path = pathlib.Path(path)
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key not in self._cache:
            failure = None
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, SyntaxError, UnicodeDecodeError) as exc:
                tree, failure = None, exc
            classes = ({n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
                       if tree is not None else {})
            self._cache[key] = (tree, classes, failure)
        tree, classes, failure = self._cache[key]
        if primary and failure is not None:
            raise failure
        return tree, classes

    def _import_target(self, path: pathlib.Path, tree: ast.Module,
                       name: str) -> Optional[pathlib.Path]:
        """The FILE a `from … import <name>` in this module points at, or None. Purely static: the
        dotted module is matched against the source file's ancestor directories."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not any((alias.asname or alias.name) == name for alias in node.names):
                continue
            parts = [p for p in (node.module or "").split(".") if p]
            if not parts:
                continue                       # `from . import x` — no module path to follow
            if node.level:                     # relative: `from .models import X`
                root = pathlib.Path(path).parent
                for _ in range(node.level - 1):
                    root = root.parent
                roots = [root]
            else:                              # absolute: `from dispatch.models import X`
                roots = list(pathlib.Path(path).resolve().parents)
            for root in roots:
                for tail in (parts[:-1] + [parts[-1] + ".py"], parts + ["__init__.py"]):
                    candidate = root.joinpath(*tail)
                    if candidate.is_file():
                        return candidate
        return None

    def resolve(self, path: str | pathlib.Path, tree: Optional[ast.Module], name: str,
                _depth: int = 0, _seen: Optional[set] = None
                ) -> Optional[tuple[pathlib.Path, ast.Module, ast.ClassDef]]:
        """`(file, tree, ClassDef)` for `name` as seen from `path`, or None if it does not resolve
        inside the batch. Same file first; then one import hop at a time, up to `hops`."""
        if tree is None:
            return None
        path = pathlib.Path(path)
        _seen = set() if _seen is None else _seen
        local = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        if name in local:
            return (path, tree, local[name])
        if _depth >= self.hops:
            return None
        target = self._import_target(path, tree, name)
        if target is None or (target, name) in _seen:
            return None
        _seen.add((target, name))
        t_tree, t_classes = self.module(target)
        if name in t_classes:
            return (target, t_tree, t_classes[name])
        return self.resolve(target, t_tree, name, _depth + 1, _seen)


# ---------------------------------------------------------------------------
# SQLAlchemy models (python ast — parses source, imports nothing).
# Both idioms: 2.0 `x: Mapped[int] = mapped_column(...)` and 1.x `x = Column(Integer, ...)`.
# ---------------------------------------------------------------------------

_PY_TYPE_MAP = {
    "str": "string", "int": "int", "float": "float", "bool": "bool",
    "datetime": "datetime", "date": "datetime",
    "UUID": "uuid", "uuid.UUID": "uuid",
    "dict": "json", "Any": "json",
}


def _ann_to_canonical(node: ast.expr, enums: dict[str, list]) -> tuple[str, bool, Optional[list]]:
    """annotation → (canonical type, nullable, enum values). Unknown → ('unknown', …)."""
    if isinstance(node, ast.Subscript):
        base = ast.unparse(node.value)
        if base in ("Optional",):
            t, _, ev = _ann_to_canonical(node.slice, enums)
            return t, True, ev
        if base in ("Mapped",):
            return _ann_to_canonical(node.slice, enums)
        if base in ("dict", "Dict"):
            return "json", False, None
        if base in ("list", "List"):
            return "relationship", False, None      # collection → relationship, not a column
        if base == "Literal":
            elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            values = [e.value for e in elts if isinstance(e, ast.Constant)]
            return "enum", False, values
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):  # X | None
        left, _, ev = _ann_to_canonical(node.left, enums)
        right = ast.unparse(node.right)
        if right == "None":
            return left, True, ev
    name = ast.unparse(node).strip("'\"")
    if name in enums:
        return "enum", False, enums[name]
    if name in _PY_TYPE_MAP:
        return _PY_TYPE_MAP[name], False, None
    short = name.split(".")[-1]
    if short in _PY_TYPE_MAP:
        return _PY_TYPE_MAP[short], False, None
    return "unknown", False, None


def _collect_py_enums(tree: ast.Module) -> dict[str, list]:
    enums: dict[str, list] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = {ast.unparse(b) for b in node.bases}
            if any("Enum" in b for b in base_names):
                values = [s.value.value for s in node.body
                          if isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)]
                if values:
                    enums[node.name] = values
    return enums


# SQLAlchemy's own column types → canonical. The 1.x idiom carries the type as the first positional
# argument of `Column(...)` (`Column(Integer)`, `Column(String(80))`), where the 2.0 idiom carries it
# in the `Mapped[...]` annotation — different place, same equivalence table (`core/shape-engine.md`).
_SQLA_COLUMN_TYPES = {
    "Integer": "int", "BigInteger": "int", "SmallInteger": "int", "INTEGER": "int",
    "BIGINT": "int", "SMALLINT": "int",
    "String": "string", "Text": "string", "Unicode": "string", "UnicodeText": "string",
    "VARCHAR": "string", "CHAR": "string", "NVARCHAR": "string", "TEXT": "string",
    "LargeBinary": "string", "BLOB": "string",
    "Boolean": "bool", "BOOLEAN": "bool",
    "DateTime": "datetime", "Date": "datetime", "Time": "datetime", "TIMESTAMP": "datetime",
    "DATETIME": "datetime", "DATE": "datetime",
    "Float": "float", "Numeric": "float", "DECIMAL": "float", "NUMERIC": "float",
    "Double": "float", "REAL": "float",
    "JSON": "json", "JSONB": "json",
    "UUID": "uuid", "Uuid": "uuid", "GUID": "uuid",
    "Enum": "enum",
}
_SQLA_SIZED = ("String", "VARCHAR", "CHAR", "NVARCHAR", "Unicode")


def _kw_true(node: ast.expr) -> bool:
    """`primary_key=True` is True; `primary_key=flag` is not asserted (a name is not a value)."""
    return isinstance(node, ast.Constant) and node.value is True


def _literal(node: ast.expr):
    """The constant an argument spells, or None when it does not spell one.

    `ast.literal_eval` raises `ValueError` on every node that is not a literal — a `Name`, an
    `Attribute`, a `Call`, even a `"a" + "b"` (verified on 3.11) — and idiomatic code spells all of
    them at exactly the keywords this module reads: `Field(max_length=MAX_LEN)`,
    `Field(validation_alias=AliasChoices("email", "emailAddress"))`, `Column(String(SIZE))`. A
    constraint this extractor cannot read is a constraint it does not report — the same degradation
    every other unresolved value here takes — and never a reason for the whole file to fail, which
    would take the module's other classes down with it (`_ModuleBatch`'s stated guarantee, which
    covered the parse and not the class-body walk that follows it).

    The exception list is the documented one rather than the one observed once: *"Raises ValueError,
    TypeError, SyntaxError, MemoryError and RecursionError depending on the malformed input"*
    (`ast.literal_eval`). Catching only the `ValueError` this repo happened to reproduce is how the
    SQLAlchemy side got its guard and how the Pydantic side got none.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def _sqla_arg_type(arg: ast.expr, enums: dict[str, list]) -> tuple[Optional[str], Optional[list],
                                                                   dict]:
    """One positional argument of a `Column(...)`/`mapped_column(...)` call →
    (canonical type or None, enum values or None, constraints it declares)."""
    cons: dict = {}
    if isinstance(arg, ast.Name):
        return _SQLA_COLUMN_TYPES.get(arg.id), None, cons
    if isinstance(arg, ast.Attribute):
        return _SQLA_COLUMN_TYPES.get(arg.attr), None, cons
    if not isinstance(arg, ast.Call):
        return None, None, cons
    fn = ast.unparse(arg.func).split(".")[-1]
    if fn == "ForeignKey" and arg.args:
        target = _literal(arg.args[0])
        if target is not None:
            cons["foreign_key"] = target
        return None, None, cons
    if fn in _SQLA_SIZED and arg.args:
        size = _literal(arg.args[0])
        if size is not None:
            cons["max_length"] = size
    if fn == "Enum":
        values = [a.value for a in arg.args
                  if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        for a in arg.args:                      # Enum(UserRole) — a python Enum declared in-file
            if isinstance(a, ast.Name) and a.id in enums:
                values = enums[a.id]
        return "enum", values or None, cons
    return _SQLA_COLUMN_TYPES.get(fn), None, cons


def _sqla_call_meta(call: Optional[ast.Call], enums: dict[str, list]) -> dict:
    """Everything a `Column(...)` / `mapped_column(...)` call declares about its column."""
    meta: dict = {"col_name": None, "constraints": {}, "type": None, "enum": None,
                  "nullable": None}
    if not isinstance(call, ast.Call):
        return meta
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                and meta["col_name"] is None:
            meta["col_name"] = arg.value       # Column("colname", …) — the reserved-word escape
            continue
        found, values, cons = _sqla_arg_type(arg, enums)
        meta["constraints"].update(cons)
        if found and meta["type"] is None:
            meta["type"], meta["enum"] = found, values
    for kw in call.keywords:
        if kw.arg == "primary_key" and _kw_true(kw.value):
            meta["constraints"]["primary_key"] = True
        if kw.arg == "unique" and _kw_true(kw.value):
            meta["constraints"]["unique"] = True
        if kw.arg in ("default", "server_default"):
            meta["constraints"].setdefault("default", ast.unparse(kw.value))
        if kw.arg == "nullable" and isinstance(kw.value, ast.Constant):
            meta["nullable"] = bool(kw.value.value)
        if kw.arg == "type_":
            found, values, cons = _sqla_arg_type(kw.value, enums)
            meta["constraints"].update(cons)
            if found and meta["type"] is None:
                meta["type"], meta["enum"] = found, values
    return meta


def _sqla_column_call(stmt: ast.Assign) -> Optional[ast.Call]:
    """The `Column(...)`/`mapped_column(...)` on the right of a 1.x-style assignment, or None.
    `relationship(...)` is deliberately not one — a relationship is not a column."""
    if not isinstance(stmt.value, ast.Call):
        return None
    fn = ast.unparse(stmt.value.func).split(".")[-1]
    return stmt.value if fn in ("Column", "mapped_column") else None


def _class_flag_true(node: ast.ClassDef, name: str) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and any(getattr(t, "id", "") == name for t in stmt.targets):
            return isinstance(stmt.value, ast.Constant) and stmt.value.value is True
    return False


def _assigns_tablename(node: ast.ClassDef) -> Optional[ast.expr]:
    """The right-hand side of this class's own `__tablename__ = …`, or None if it has none."""
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) \
                and any(getattr(t, "id", "") == "__tablename__" for t in stmt.targets):
            return stmt.value
    return None


def _declares_tablename(node: ast.ClassDef) -> Optional[str]:
    """The **string literal** `__tablename__ = "x"`, or None. A `@declared_attr` FUNCTION named
    `__tablename__` is not a literal: it computes the name at class-definition time, which this
    extractor does not execute — see `_base_computes_tablename`.

    Neither is `__tablename__ = PREFIX + "users"`, `f"{PREFIX}orders"` or `TABLES["thing"]`, and
    that case used to reach the caller as `ast.unparse(...).strip("'\\"")` — the *expression text*,
    mangled by the strip (`PREFIX + 'users`), keyed as an entity and carrying no `entity_meta`, i.e.
    indistinguishable from a table name this extractor actually read. It also made the extraction
    non-empty, so a models file whose classes all compute their table name defeated the
    `EmptyExtraction` refusal with one fabricated zero-field entity. Returning None sends such a
    class down the honest path: keyed by CLASS NAME, with `key_source` saying so.
    """
    value = _assigns_tablename(node)
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _base_computes_tablename(node: ast.ClassDef, tree: ast.Module, path: pathlib.Path,
                             batch: _ModuleBatch) -> bool:
    """Does a resolvable base declare `__tablename__` at all (literal or `@declared_attr`)?
    Positive evidence that the table name exists and is simply computed out of reach."""
    for base in _base_names(node):
        found = batch.resolve(path, tree, base)
        if not found:
            continue
        b_path, b_tree, b_node = found
        for stmt in b_node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and stmt.name == "__tablename__":
                return True
            if isinstance(stmt, ast.Assign) \
                    and any(getattr(t, "id", "") == "__tablename__" for t in stmt.targets):
                return True
        if _base_computes_tablename(b_node, b_tree, b_path, batch):
            return True
    return False


def _is_mapped_class(node: ast.ClassDef, tree: ast.Module, path: pathlib.Path,
                     batch: _ModuleBatch, _seen: Optional[set] = None) -> bool:
    """Positive evidence that a class is ORM-MAPPED, not merely a class with annotated attributes:
    a `Column(...)` / `mapped_column(...)` call, or a `Mapped[...]` annotation, on it or on a base.

    Required only by the no-`__tablename__` fallback, and required by measurement: in
    `Netflix/dispatch` the ORM model and its five Pydantic DTOs live in ONE file
    (`incident/models.py`), so a fallback keyed on "has annotated fields" turns every DTO into a
    table. The declared-`__tablename__` path needs none of this — the source already said it.
    """
    _seen = set() if _seen is None else _seen
    ident = (str(path), node.name)
    if ident in _seen:
        return False
    _seen.add(ident)
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and "Mapped[" in ast.unparse(stmt.annotation):
            return True
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and isinstance(stmt.value, ast.Call) \
                and ast.unparse(stmt.value.func).split(".")[-1] in ("Column", "mapped_column"):
            return True
    for base in _base_names(node):
        found = batch.resolve(path, tree, base)
        if found and _is_mapped_class(found[2], found[1], found[0], batch, _seen):
            return True
    return False


def _sqla_columns(node: ast.ClassDef, tree: ast.Module, path: pathlib.Path,
                  enums: dict[str, list], batch: _ModuleBatch,
                  _seen: Optional[set] = None) -> dict[str, dict]:
    """The columns a declarative class contributes, its bases and declarative MIXINS included.

    Mixin columns are the table's columns — that is SQLAlchemy's own semantics, not an inference —
    so `Incident(Base, TimeStampMixin)` carries `created_at`. Resolution is the batch's: same file,
    then bounded static import hops. What stays out of reach and is NOT guessed at: a
    `@declared_attr` method returning a `Column` (the column exists only after the function runs).

    Bases are merged **rightmost first** so that the LEFTMOST one wins a name both declare, which is
    the same semantics: Python resolves `Thing(TimestampMixin, SoftDeleteMixin)` by MRO, and MRO
    puts the leftmost base first. Merging left-to-right — the obvious loop, and what this did — let
    the LAST base win, so a column the ORM actually resolves to `TimestampMixin` was extracted with
    `SoftDeleteMixin`'s type and the diff was keyed on the wrong side of the conflict. If the
    justification for merging at all is "that is SQLAlchemy's own semantics", the order is part of
    the semantics rather than a free choice. Own body last, so a class's own column beats any base.
    """
    _seen = set() if _seen is None else _seen
    ident = (str(path), node.name)
    if ident in _seen:
        return {}
    _seen.add(ident)
    fields: dict[str, dict] = {}
    for base in reversed(_base_names(node)):
        found = batch.resolve(path, tree, base)
        if not found:
            continue
        b_path, b_tree, b_node = found
        fields.update(_sqla_columns(b_node, b_tree, b_path, _collect_py_enums(b_tree), batch,
                                    _seen))                     # own columns override, below
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            call = stmt.value
            if isinstance(call, ast.Call) and ast.unparse(call.func).endswith("relationship"):
                continue
            t, nullable, ev = _ann_to_canonical(stmt.annotation, enums)   # 2.0: annotation is truth
            if t == "relationship":
                continue
            meta = _sqla_call_meta(call, enums)
            if meta["nullable"] is not None:
                nullable = meta["nullable"]     # an explicit nullable= beats the annotation
            if t == "unknown" and meta["type"]:
                t, ev = meta["type"], meta["enum"]   # annotation out of reach, the column says it
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            call = _sqla_column_call(stmt)
            if call is None:
                continue                        # not a column: a relationship, a constant, a flag
            meta = _sqla_call_meta(call, enums)
            t, ev = meta["type"] or "unknown", meta["enum"]
            # 1.x nullability is the ORM's own default: nullable unless said otherwise, and never
            # for a primary key.
            nullable = True if meta["nullable"] is None else meta["nullable"]
        else:
            continue
        constraints = meta["constraints"]
        if constraints.get("primary_key"):
            nullable = False
        col_name = meta["col_name"] or (stmt.target.id if isinstance(stmt, ast.AnnAssign)
                                        else stmt.targets[0].id)
        conf = "extracted" if t != "unknown" else "ambiguous"
        fields[col_name] = descriptor(col_name, t, nullable, ev, constraints or None, conf)
    return fields


def extract_sqlalchemy(path: str | pathlib.Path) -> Extraction:
    """SQLAlchemy declarative models → shapes, keyed by table name where the source declares one.

    Where it does not, the key is the CLASS NAME and `entity_meta` says so. That fallback is not a
    guess at the table name — deriving `incident` from `Incident` is the pluralization guess this
    engine refuses elsewhere, and the rule differs per project (`resolve_table_name` in
    `Netflix/dispatch` snake-cases; another base pluralizes). What IS deterministic is that the
    class is mapped at all: SQLAlchemy raises at class-definition time for a declarative class with
    columns and no table name, so **columns present + no `__tablename__` here ⇒ a base supplies
    it**. The diff then rests on a name this extractor read rather than one it invented, and a
    caller can see which by reading `entity_meta`.
    """
    path = pathlib.Path(path)
    batch = _ModuleBatch()
    tree, _ = batch.module(path, primary=True)   # this file's own syntax error is not a null result
    enums = _collect_py_enums(tree)
    out = Extraction()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if _class_flag_true(node, "__abstract__"):
            continue                       # the source says it is not a table; believe the source
        tablename = _declares_tablename(node)
        fields = _sqla_columns(node, tree, path, enums, batch)
        if tablename is not None:
            out[tablename] = fields        # a declared name is a fact; keep it even with no columns
            continue
        if not fields or not _is_mapped_class(node, tree, path, batch):
            continue                       # no table name and no columns: not a mapped class
        out[node.name] = fields
        if _assigns_tablename(node) is not None:
            why = ("`__tablename__` here is an EXPRESSION, not a literal (`PREFIX + \"users\"`, an "
                   "f-string, a table registry lookup); the real name exists only once that "
                   "expression runs, which this extractor does not do")
        elif _base_computes_tablename(node, tree, path, batch):
            why = ("no `__tablename__` here; a base class declares it and SQLAlchemy computes the "
                   "real table name at class-definition time, which this extractor does not "
                   "execute")
        else:
            why = ("no `__tablename__` anywhere inside the parse batch; a declarative class with "
                   "columns and no table name either inherits one or is a mixin")
        out.entity_meta[node.name] = {"key_source": "class_name", "why": why}
    return out


# ---------------------------------------------------------------------------
# Pydantic v2 DTOs
# ---------------------------------------------------------------------------


def _literal_aliases(tree: ast.Module) -> dict[str, list]:
    """module-level Literal aliases: `UserRole = Literal["admin", "member"]`."""
    enums: dict[str, list] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Subscript) \
                and ast.unparse(node.value.value) == "Literal":
            elts = node.value.slice.elts if isinstance(node.value.slice, ast.Tuple) \
                else [node.value.slice]
            values = [e.value for e in elts if isinstance(e, ast.Constant)]
            for target in node.targets:
                if isinstance(target, ast.Name):
                    enums[target.id] = values
    return enums


def _is_pydantic_model(node: ast.ClassDef, tree: ast.Module, path: pathlib.Path,
                       batch: _ModuleBatch, _seen: Optional[set] = None) -> bool:
    """Does this class's base CHAIN reach `BaseModel`, inside the parse batch?

    The old rule was one level and literal — a base whose name contains `BaseModel` — and it made
    every project that declares its own base invisible. Measured, not supposed: in
    `Netflix/dispatch` 131 classes inherit `DispatchBase` (which is `DispatchBase(BaseModel)`, one
    import hop away in `dispatch/models.py`) against 4 that inherit `BaseModel` directly, so the
    check saw 3% of the DTOs and reported zero drift over the rest.

    Resolution limit, stated because it is the difference between reading and guessing: **the file
    itself, plus at most `_MAX_IMPORT_HOPS` static import hops** (`_ModuleBatch`). Nothing is
    imported and no name is accepted for looking like a base — a chain that leaves the batch is
    unresolved, and an unresolved class is simply not extracted.
    """
    _seen = set() if _seen is None else _seen
    ident = (str(path), node.name)
    if ident in _seen:
        return False
    _seen.add(ident)
    names = _base_names(node)
    if any("BaseModel" in base for base in names):
        return True
    for base in names:
        found = batch.resolve(path, tree, base)
        if found and _is_pydantic_model(found[2], found[1], found[0], batch, _seen):
            return True
    return False


def _pydantic_fields(node: ast.ClassDef, tree: ast.Module, path: pathlib.Path,
                     enums: dict[str, list], batch: _ModuleBatch,
                     _seen: Optional[set] = None) -> dict[str, dict]:
    """A DTO's fields, its inherited ones included — bases resolved across the same parse batch,
    each base read with ITS OWN module's `Literal` aliases (an enum is defined where it is written).

    Bases are merged **rightmost first**, so the leftmost wins a field two of them declare — what
    `typing.get_type_hints` answers for the same classes, because pydantic builds its fields off the
    MRO and the MRO is leftmost-first. See `_sqla_columns` for the same rule and the same reason.
    """
    _seen = set() if _seen is None else _seen
    ident = (str(path), node.name)
    if ident in _seen:
        return {}
    _seen.add(ident)
    fields: dict[str, dict] = {}
    for base in reversed(_base_names(node)):
        found = batch.resolve(path, tree, base)
        if not found:
            continue
        b_path, b_tree, b_node = found
        fields.update(_pydantic_fields(b_node, b_tree, b_path, _literal_aliases(b_tree), batch,
                                       _seen))
    for stmt in node.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        if name == "model_config" or "ClassVar" in ast.unparse(stmt.annotation):
            continue                       # pydantic's own rule: a ClassVar is not a model field
        t, nullable, ev = _ann_to_canonical(stmt.annotation, enums)
        if t == "relationship":
            # `List[TagRead]` on a DTO. `relationship` is this module's internal sentinel for a
            # collection — not one of CANONICAL — and the ORM extractor uses it to SKIP the field.
            # Reaching the diff, it produced `sqlalchemy=json vs pydantic=relationship`: a sentinel
            # printed to an operator as if it were a type. A collection at a boundary is genuinely
            # undecided (a JSON column, a join table, or nothing), which is honesty rule 1's own
            # case: mark it unresolved and let the diff downgrade it to an ambiguous note.
            t = "unknown"
        constraints = {}
        if isinstance(stmt.value, ast.Call) and ast.unparse(stmt.value.func) == "Field":
            for kw in stmt.value.keywords:
                # `_literal`, not a bare `literal_eval`: `validation_alias=AliasChoices(…)` is what
                # pydantic v2's own docs write, and `max_length=MAX_LEN` is what a project with a
                # constants module writes. Both are non-literal nodes, and reading them as one used
                # to raise out of here — naming no file, from a neighbour the caller never passed.
                if kw.arg in ("max_length", "validation_alias"):
                    value = _literal(kw.value)
                    if value is not None:
                        constraints[kw.arg] = value
        conf = "extracted" if t != "unknown" else "ambiguous"
        fields[name] = descriptor(name, t, nullable, ev, constraints or None, conf)
    return fields


def extract_pydantic(path: str | pathlib.Path) -> Extraction:
    """Returns per-CLASS shapes (UserRead, UserCreate, …); mapping to entities is diff's job."""
    path = pathlib.Path(path)
    batch = _ModuleBatch()
    tree, _ = batch.module(path, primary=True)   # this file's own syntax error is not a null result
    enums = _literal_aliases(tree)
    out = Extraction()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_pydantic_model(node, tree, path, batch):
            continue
        out[node.name] = _pydantic_fields(node, tree, path, enums, batch)
    return out


# ---------------------------------------------------------------------------
# TypeScript interfaces / type unions
# ---------------------------------------------------------------------------

_TS_TYPE_MAP = {"string": "string", "number": "int", "boolean": "bool",
                "Record<string, unknown>": "json", "unknown": "json"}
_TS_FIELD = re.compile(r"^\s*(\w+)(\?)?:\s*(.+?);\s*(?://\s*(.*))?$")
_TS_UNION = re.compile(r'^export type (\w+) = (.+);', re.M)


def extract_typescript(path: str | pathlib.Path, backend: str = "auto"
                       ) -> dict[str, dict[str, dict]]:
    """Returns per-INTERFACE shapes, read only from the TS type system (no comment sniffing):
    a `string` stays `string`. The uuid/datetime↔string equivalence is applied deterministically
    at diff time for stringly-typed layers (see `diff_shapes` / `_STRINGLY_LAYERS`), per
    `core/shape-engine.md`'s equivalence table.

    `backend="auto"|"treesitter"` routes to the tree-sitter parse (`runtime/treesitter_extract.py`),
    which recovers multi-line / nested-generic fields this line parser drops; default stays the
    stdlib line parser (see `_try_treesitter`)."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    ts = _try_treesitter("typescript", text, backend)
    if ts is not None:
        return ts
    unions: dict[str, list] = {}
    for m in _TS_UNION.finditer(text):
        parts = [p.strip() for p in m.group(2).split("|")]
        if all(p.startswith('"') and p.endswith('"') for p in parts):
            unions[m.group(1)] = [p.strip('"') for p in parts]
    out: dict[str, dict[str, dict]] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        header = re.match(r"^export interface (\w+)\s*{", line)
        if header:
            current = header.group(1)
            out[current] = {}
            continue
        if current and line.strip().startswith("}"):
            current = None
            continue
        if current:
            m = _TS_FIELD.match(line)
            if not m:
                continue
            name, optional, ts_type, _comment = m.groups()
            nullable = False
            base = ts_type.strip()
            if base.endswith("| null"):
                nullable = True
                base = base[: -len("| null")].strip()
            if optional:
                nullable = True      # partial DTOs: optional ≈ may be absent; diff treats
                                     # Create-interfaces as partial anyway
            enum_vals = unions.get(base)
            if enum_vals:
                t = "enum"
            elif base in _TS_TYPE_MAP:
                t = _TS_TYPE_MAP[base]
            else:
                t = "unknown"        # TS has no uuid/datetime type: a `string` stays `string`.
                                     # The uuid/datetime↔string equivalence is a deterministic
                                     # diff-time rule (see diff_shapes), never sniffed from a comment.
            conf = "extracted" if t != "unknown" else "ambiguous"
            out[current][name] = descriptor(name, t, nullable, enum_vals, None, conf)
    return out


# ---------------------------------------------------------------------------
# Postgres DDL
# ---------------------------------------------------------------------------

# Postgres type → canonical (the equivalence table). Multi-word types are matched as-is; a
# language without a distinct uuid/datetime carries them as `string`, handled at diff time.
_DDL_TYPE_MAP = {
    "uuid": "uuid",
    "text": "string", "varchar": "string", "character varying": "string",
    "char": "string", "character": "string", "bpchar": "string", "citext": "string", "name": "string",
    "boolean": "bool", "bool": "bool",
    "integer": "int", "int": "int", "int2": "int", "int4": "int", "int8": "int",
    "smallint": "int", "bigint": "int", "serial": "int", "bigserial": "int", "smallserial": "int",
    "numeric": "float", "decimal": "float", "real": "float", "float": "float",
    "float4": "float", "float8": "float", "double precision": "float", "money": "float",
    "timestamptz": "datetime", "timestamp": "datetime", "date": "datetime", "time": "datetime",
    "timetz": "datetime", "timestamp with time zone": "datetime",
    "timestamp without time zone": "datetime", "time with time zone": "datetime",
    "time without time zone": "datetime",
    "jsonb": "json", "json": "json", "bytea": "string",
}
_STRING_SIZED = ("varchar", "character varying", "char", "character", "bpchar")
# name  <multi-word type>  optional (size[,scale])  rest. Multi-word alternatives come first so
# `timestamp with time zone` is not truncated to `timestamp`; a schema prefix/quotes are tolerated.
_PG_COL = re.compile(
    r'^"?(?P<name>\w+)"?\s+'
    r'(?P<type>timestamp with time zone|timestamp without time zone|time with time zone|'
    r'time without time zone|double precision|character varying|character|\w+)'
    r'\s*(?P<size>\(\s*\d+(?:\s*,\s*\d+)?\s*\))?'
    r'(?P<rest>.*)$', re.I | re.S)
_TABLE_NAME = r'(?:IF NOT EXISTS\s+)?(?:"?\w+"?\.)?"?(\w+)"?'   # opt IF NOT EXISTS / schema / quotes


def extract_ddl(path: str | pathlib.Path, backend: str = "auto"
                ) -> dict[str, dict[str, dict]]:
    """Postgres DDL → shapes. Default `backend="auto"` uses the tree-sitter SQL grammar when
    installed (parses real Postgres — IF NOT EXISTS, `public.` prefixes, multi-word types — with no
    per-repo patches) and degrades to the stdlib regex parser below when it is not."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    ts = _try_treesitter("sql", text, backend)
    if ts is not None:
        return ts
    text = re.sub(r"--[^\n]*", "", text)   # strip SQL line comments (real DDL has them)
    enums: dict[str, list] = {}
    for m in re.finditer(rf"CREATE TYPE {_TABLE_NAME}\s+AS ENUM\s*\(([^)]*)\)", text, re.I):
        enums[m.group(1)] = [v.strip().strip("'") for v in m.group(2).split(",")]
    out: dict[str, dict[str, dict]] = {}
    for m in re.finditer(rf"CREATE TABLE {_TABLE_NAME}\s*\((.*?)\);", text, re.S | re.I):
        table, body = m.group(1), m.group(2)
        fields: dict[str, dict] = {}
        for raw in re.split(r",\s*\n", body):
            line = raw.strip()
            if line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT",
                                        "EXCLUDE", "LIKE")):
                continue
            col = _PG_COL.match(line)
            if not col:
                continue
            name = col.group("name")
            sql_type = re.sub(r"\s+", " ", col.group("type").strip().lower())
            size, rest = col.group("size"), col.group("rest")
            constraints: dict = {}
            if sql_type in _STRING_SIZED:
                t = "string"
                if size and (num := re.search(r"\d+", size)):
                    constraints["max_length"] = int(num.group())
            elif sql_type in _DDL_TYPE_MAP:
                t = _DDL_TYPE_MAP[sql_type]
            elif sql_type in enums:
                t = "enum"
            else:
                t = "unknown"
            rest_u = rest.upper()
            nullable = "NOT NULL" not in rest_u and "PRIMARY KEY" not in rest_u
            if "PRIMARY KEY" in rest_u:
                constraints["primary_key"] = True
            if "UNIQUE" in rest_u:
                constraints["unique"] = True
            fk = re.search(r'REFERENCES\s+(?:"?\w+"?\.)?"?(\w+)"?\s*\((\w+)\)', rest, re.I)
            if fk:
                constraints["foreign_key"] = f"{fk.group(1)}.{fk.group(2)}"
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[name] = descriptor(name, t, nullable, enums.get(sql_type),
                                      constraints or None, conf)
        out[table] = fields
    return out


# ---------------------------------------------------------------------------
# additional stacks (additive — new stacks add an extractor, they don't rewrite).
# These are line/regex parsers for the common shapes; full generalization is the
# tree-sitter query pass on the TODO. Each still normalizes to the one descriptor.
# ---------------------------------------------------------------------------

_DRIZZLE_TYPES = {"uuid": "uuid", "text": "string", "varchar": "string", "boolean": "bool",
                  "integer": "int", "bigint": "int", "serial": "int", "real": "float",
                  "doublePrecision": "float", "decimal": "float", "numeric": "float",
                  "timestamp": "datetime", "jsonb": "json", "json": "json", "date": "datetime"}


def _balanced_braces(text: str, open_idx: int) -> str:
    """Return the substring inside the braces starting at text[open_idx] == '{', matching nesting.
    Regex cannot count braces; a nested `{ length: 255 }` would otherwise truncate the body."""
    depth, i = 0, open_idx
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
        i += 1
    return text[open_idx + 1:]


def extract_drizzle(path: str | pathlib.Path,
                    imported_enums: Optional[dict[str, list]] = None
                    ) -> dict[str, dict[str, dict]]:
    """Drizzle ORM (TS): `export const users = pgTable('users', { ... })` + `pgEnum(...)`.
    Handles single or double quotes and multi-line column method chains (real Drizzle spreads
    `.notNull().references(...)` across lines). Enum types are often imported from a sibling
    `enums.ts`; pass `imported_enums` ({constName: [values]}) to resolve them. A column whose
    constructor is a locally-declared `pgEnum` resolves to `enum` (+ values); one whose enum const
    is unresolved (imported, not supplied) extracts as `unknown`/ambiguous — honestly undecided,
    never guessed from the const's name."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    q = r'["\']'
    enums: dict[str, list] = {}
    for m in re.finditer(rf'pgEnum\(\s*{q}(\w+){q}\s*,\s*\[([^\]]*)\]', text):
        enums[m.group(1)] = [v.strip().strip('"\'') for v in m.group(2).split(",") if v.strip()]
    # enum-typed columns use the exported const name of the pgEnum; map const->enum-name
    enum_consts = {m.group(1): m.group(2) for m in
                   re.finditer(rf'(?:export\s+)?const\s+(\w+)\s*=\s*pgEnum\(\s*{q}(\w+){q}', text)}
    # a const known to be a pgEnum in a sibling file: caller supplies its values (or none)
    imported = imported_enums or {}
    out: dict[str, dict[str, dict]] = {}
    for opening in re.finditer(rf'pgTable\(\s*{q}(\w+){q}\s*,\s*\{{', text):
        table = opening.group(1)
        body = _balanced_braces(text, opening.end() - 1)  # nested { precision: 12 } etc.
        # join method-chain continuation lines (a line starting with `.`) onto the previous line
        body = re.sub(r"\n\s*\.", ".", body)
        fields: dict[str, dict] = {}
        for col in re.finditer(rf'(\w+)\s*:\s*(\w+)\(\s*{q}(\w+){q}([^,)]*(?:,\s*\{{[^}}]*\}})?)?\)(.*)',
                               body):
            js_attr, ctor, col_name, ctor_rest, chain = col.groups()
            chain = (ctor_rest or "") + (chain or "")
            cons: dict = {}
            if ctor in enum_consts:
                t, evals = "enum", enums.get(enum_consts[ctor])
            elif ctor in imported:
                t, evals = "enum", imported[ctor] or None       # cross-file enum (caller-resolved)
            elif ctor in _DRIZZLE_TYPES:
                t, evals = _DRIZZLE_TYPES[ctor], None
                ml = re.search(r"length:\s*(\d+)", ctor_rest or "")
                if ml:
                    cons["max_length"] = int(ml.group(1))
            else:
                t, evals = "unknown", None
            nullable = ".notNull()" not in chain and ".primaryKey()" not in chain
            if ".primaryKey()" in chain:
                cons["primary_key"] = True
            if ".unique()" in chain:
                cons["unique"] = True
            fk = re.search(r"\.references\(\(\)\s*=>\s*(\w+)\.(\w+)", chain)
            if fk:
                cons["foreign_key"] = f"{fk.group(1)}.{fk.group(2)}"
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[col_name] = descriptor(col_name, t, nullable, evals, cons or None, conf)
        out[table] = fields
    return out


_PRISMA_TYPES = {"String": "string", "Int": "int", "BigInt": "int", "Float": "float",
                 "Boolean": "bool", "DateTime": "datetime", "Json": "json", "Bytes": "string"}


def extract_prisma(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    """Prisma schema: `model User { id String @id ... }` + `enum Role { admin member }`.
    Keyed by model name (the entity), not table name."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    enums: dict[str, list] = {}
    for m in re.finditer(r"enum\s+(\w+)\s*\{([^}]*)\}", text):
        enums[m.group(1)] = [v.strip() for v in m.group(2).split() if v.strip()]
    out: dict[str, dict[str, dict]] = {}
    for model in re.finditer(r"model\s+(\w+)\s*\{([^}]*)\}", text):
        name, body = model.group(1), model.group(2)
        fields: dict[str, dict] = {}
        for line in body.splitlines():
            line = line.strip()
            m = re.match(r"^(\w+)\s+(\w+)(\?)?(\[\])?\s*(.*)$", line)
            if not m or line.startswith("//") or line.startswith("@@"):
                continue
            fname, ftype, optional, is_list, attrs = m.groups()
            if is_list or ftype in out or (ftype not in _PRISMA_TYPES and ftype not in enums
                                           and "@relation" in attrs):
                continue   # relation field, not a scalar column
            cons: dict = {}
            if ftype in enums:
                t, evals = "enum", enums[ftype]
            elif ftype in _PRISMA_TYPES:
                t, evals = _PRISMA_TYPES[ftype], None
            else:
                continue
            # Prisma has no uuid scalar: String @default(uuid()) / @db.Uuid IS a uuid
            if t == "string" and ("uuid(" in attrs or "@db.Uuid" in attrs):
                t = "uuid"
            nullable = bool(optional)
            if "@id" in attrs:
                cons["primary_key"] = True
                nullable = False
            if "@unique" in attrs:
                cons["unique"] = True
            fields[fname] = descriptor(fname, t, nullable, evals, cons or None)
        out[name] = fields
    return out


_DJANGO_FIELD = {"CharField": "string", "TextField": "string", "EmailField": "string",
                 "SlugField": "string", "UUIDField": "uuid", "IntegerField": "int",
                 "BigIntegerField": "int", "SmallIntegerField": "int", "FloatField": "float",
                 "BooleanField": "bool", "DateTimeField": "datetime", "DateField": "datetime",
                 "JSONField": "json", "ForeignKey": "uuid", "OneToOneField": "uuid"}


def extract_django(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    """Django models: `class User(models.Model): role = models.CharField(...)`.
    Keyed by model class name (the entity)."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    out: dict[str, dict[str, dict]] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        cls = re.match(r"class\s+(\w+)\s*\(.*models\.Model.*\)\s*:", line)
        if cls:
            current = cls.group(1)
            out[current] = {}
            continue
        if current is None:
            continue
        m = re.match(r"\s+(\w+)\s*=\s*models\.(\w+)\((.*)\)\s*$", line)
        if not m:
            continue
        fname, ftype, args = m.groups()
        if ftype not in _DJANGO_FIELD:
            continue
        cons: dict = {}
        t = _DJANGO_FIELD[ftype]
        evals = None
        ml = re.search(r"max_length\s*=\s*(\d+)", args)
        if ml:
            cons["max_length"] = int(ml.group(1))
        if re.search(r"choices\s*=", args):
            t = "enum"    # values not resolvable without the choices tuple — shape only
        nullable = "null=True" in args
        if "primary_key=True" in args:
            cons["primary_key"] = True
        if "unique=True" in args:
            cons["unique"] = True
        conf = "extracted" if not (t == "enum" and evals is None) else "ambiguous"
        out[current][fname] = descriptor(fname, t, nullable, evals, cons or None, conf)
    return out


_GQL_TYPES = {"ID": "uuid", "String": "string", "Int": "int", "Float": "float",
              "Boolean": "bool"}


def extract_graphql(path: str | pathlib.Path, backend: str = "auto"
                    ) -> dict[str, dict[str, dict]]:
    """GraphQL SDL: `type User { id: ID! role: Role! }` + `enum Role { admin member }`.
    An API-layer contract; keyed by type name (the entity).

    `backend="auto"|"treesitter"` routes to the tree-sitter SDL parse (a different grammar from TS,
    proving the engine generalizes); default stays the stdlib regex parser."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    ts = _try_treesitter("graphql", text, backend)
    if ts is not None:
        return ts
    enums: dict[str, list] = {}
    for m in re.finditer(r"enum\s+(\w+)\s*\{([^}]*)\}", text):
        enums[m.group(1)] = [v.strip() for v in m.group(2).split() if v.strip()]
    scalar_datetime = {"DateTime", "Date", "Timestamp"}
    out: dict[str, dict[str, dict]] = {}
    for typ in re.finditer(r"type\s+(\w+)\s*\{([^}]*)\}", text):
        name, body = typ.group(1), typ.group(2)
        fields: dict[str, dict] = {}
        for line in body.splitlines():
            m = re.match(r"\s*(\w+)\s*:\s*(\[?\w+\]?)(!)?", line)
            if not m:
                continue
            fname, ftype, bang = m.groups()
            if ftype.startswith("["):
                continue    # list field / relation — not a scalar column
            nullable = not bool(bang)
            if ftype in enums:
                t, evals = "enum", enums[ftype]
            elif ftype in scalar_datetime:
                t, evals = "datetime", None
            elif ftype in _GQL_TYPES:
                t, evals = _GQL_TYPES[ftype], None
            else:
                continue    # object type — a relation, not a scalar field
            fields[fname] = descriptor(fname, t, nullable, evals)
        out[name] = fields
    return out


# ---------------------------------------------------------------------------
# the diff (rescue: find drift · greenfield: fail the build on drift)
# ---------------------------------------------------------------------------


def diff_shapes(reference: dict[str, dict], candidate: dict[str, dict],
                ref_layer: str, cand_layer: str, entity: str,
                partial: bool = False) -> list[dict]:
    """Compare one entity's fields across two layers. `partial=True` (Create DTOs):
    fields absent from the candidate are not drift; present ones must still agree."""
    findings: list[dict] = []

    def finding(kind: str, field: str, detail: str, confidence: str = "extracted") -> dict:
        return {"entity": entity, "field": field, "kind": kind, "detail": detail,
                "layers": [ref_layer, cand_layer], "confidence": confidence}

    for name, ref in reference.items():
        cand = candidate.get(name)
        if cand is None:
            if not partial:
                findings.append(finding("missing_field", name,
                                        f"{name} exists in {ref_layer} but not in {cand_layer}"))
            continue
        # honesty rule 1: an unresolved side is a note, never an asserted mismatch
        if ref["type"] == "unknown" or cand["type"] == "unknown":
            findings.append(finding(
                "unresolved", name,
                f"could not resolve type on one side ({ref['type']} vs {cand['type']})",
                confidence="ambiguous"))
            continue
        # equivalence-table projection (core/shape-engine.md): two of the receiving type system's
        # own facts hold deterministically, so neither is drift —
        #  1. string ⟷ uuid/datetime, on a layer with neither type (JS/TS AND GraphQL), and
        #  2. int ⟷ float, on a layer with ONE number type (JS/TS only — GraphQL has Int and Float
        #     and can get that wrong, which is why these are two lists and not one).
        # Applied symmetrically at diff time — never inferred from a comment during extraction.
        one_number = (cand_layer.startswith(_ONE_NUMBER_LAYERS)
                      or ref_layer.startswith(_ONE_NUMBER_LAYERS))
        projection = (
            (cand_layer.startswith(_STRINGLY_LAYERS) and cand["type"] == "string"
             and ref["type"] in ("uuid", "datetime"))
            or (ref_layer.startswith(_STRINGLY_LAYERS) and ref["type"] == "string"
                and cand["type"] in ("uuid", "datetime"))
            or (one_number and ref["type"] in ("int", "float")
                and cand["type"] in ("int", "float")))
        # …and one more, which is GraphQL's `ID` and nothing else. `ID` is the only GraphQL type
        # either backend canonicalizes to `uuid` (`_GQL_TYPES` here, `STACKS["graphql"]["type_map"]`
        # in treesitter_extract — `test_shapes` fails if a second one is ever added), so `uuid` on a
        # GraphQL side IS an `ID` field. The spec makes it opaque: "serialized as a String … input
        # coercion accepts both String and Int", and an SDL cannot say what the store holds. So
        # against string/int/uuid it is not drift; against bool/enum/json/datetime it still is.
        # Measured: 117 of keystone's 130 type_mismatch findings were this, 90% of the class, and
        # every one of them a Prisma `String @id`/`Int @id` under a GraphQL `ID!`.
        graphql_id = ((ref_layer.startswith(_GRAPHQL_LAYERS) and ref["type"] == "uuid")
                      or (cand_layer.startswith(_GRAPHQL_LAYERS) and cand["type"] == "uuid"))
        opaque_id = graphql_id and {ref["type"], cand["type"]} <= {"string", "int", "uuid"}
        if ref["type"] != cand["type"] and not projection and not opaque_id:
            findings.append(finding(
                "type_mismatch", name,
                f"{ref_layer}={ref['type']} vs {cand_layer}={cand['type']}"))
        elif ref["type"] == "enum" and ref.get("enum") and cand.get("enum") \
                and set(ref["enum"]) != set(cand["enum"]):
            findings.append(finding(
                "enum_mismatch", name,
                f"{ref_layer}={ref['enum']} vs {cand_layer}={cand['enum']}"))
        if not partial and bool(ref["nullable"]) != bool(cand["nullable"]):
            findings.append(finding(
                "nullability_mismatch", name,
                f"{ref_layer} nullable={ref['nullable']} vs {cand_layer} nullable={cand['nullable']}"))
    for name in candidate:
        if name not in reference:
            findings.append(finding("extra_field", name,
                                    f"{name} exists in {cand_layer} but not in {ref_layer}"))
    _tag_relation_pairs(findings)
    return findings


#: The two ways a foreign key is spelled on the far side of a relation. Suffixes, not a semantic
#: read: `authorId`/`author` and `banner_id`/`banner` are the camel and snake spellings of one
#: convention, and a name that ends in neither is left alone.
_RELATION_ID_SUFFIXES = ("_id", "Id")


def _tag_relation_pairs(findings: list[dict]) -> None:
    """Mark the `X_id` / `X` pair that is ONE disagreement reported in two kinds.

    A DB keeps the foreign key as a scalar column (`author_id`); an API exposes the related object
    (`author`). The diff is right about both — the scalar is on one side only and so is the object —
    but a reader counting findings counts the same fact twice. Measured on keystone, and the count
    is `docs/measurements.md`'s to state: this docstring carried a bare figure that the same page's
    postscript had already replaced with a smaller and better-founded one, because the old figure
    was the whole of `missing_field` + `extra_field` while the virtual counters (`postsCount`) are
    not relation pairs at all. A measured number restated away from its provenance stamp goes stale
    exactly like that, which is why that page forbids it.

    This CLASSIFIES; it does not suppress. Both findings survive with their kinds and details
    intact, each carrying `relation_pair` (the shared stem) and `relation_role`, so a clustering or
    fp-check pass downstream can fold them into one item and the raw counts stay derivable by
    ignoring the marker. Folding is a decision for the layer that presents findings to a human, not
    for the layer that finds them.
    """
    by_kind: dict[str, dict[str, list]] = {"missing_field": {}, "extra_field": {}}
    for f in findings:
        if f["kind"] in by_kind:
            by_kind[f["kind"]].setdefault(f["field"], []).append(f)
    for scalar_kind, object_kind in (("missing_field", "extra_field"),
                                     ("extra_field", "missing_field")):
        for name, scalars in by_kind[scalar_kind].items():
            for suffix in _RELATION_ID_SUFFIXES:
                stem = name[: -len(suffix)]
                if not name.endswith(suffix) or not stem:
                    continue
                objects = by_kind[object_kind].get(stem)
                if not objects:
                    continue
                for f in scalars:
                    f["relation_pair"], f["relation_role"] = stem, "fk_scalar"
                for f in objects:
                    f["relation_pair"], f["relation_role"] = stem, "relation_object"
                break


# Registry so a carrier-less reconcile can pick the extractor by stack name.
def _treesitter_only(lang: str):
    """A path→shapes extractor for a tree-sitter-only stack (Go/Java/Rust/C#): there is no stdlib
    fallback — you cannot read those languages without a real parser — so it raises if tree-sitter
    is absent. The per-stack knowledge is the declarative spec in `treesitter_extract.STACKS`."""
    def extractor(path: str | pathlib.Path, backend: str = "auto") -> dict[str, dict[str, dict]]:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        result = _try_treesitter(lang, text, "auto" if backend == "regex" else backend)
        if result is None:
            raise RuntimeError(f"{lang!r} extraction requires the tree-sitter backend "
                               f"(pip install tree-sitter tree-sitter-language-pack)")
        return result
    extractor.__name__ = f"extract_{lang}"
    return extractor


# Backend struct/class stacks read only via tree-sitter (a real parser per language).
extract_go = _treesitter_only("go")
extract_java = _treesitter_only("java")
extract_rust = _treesitter_only("rust")
extract_csharp = _treesitter_only("csharp")


EXTRACTORS = {
    "ddl": extract_ddl, "sqlalchemy": extract_sqlalchemy, "pydantic": extract_pydantic,
    "typescript": extract_typescript, "drizzle": extract_drizzle, "prisma": extract_prisma,
    "django": extract_django, "graphql": extract_graphql,
    "go": extract_go, "java": extract_java, "rust": extract_rust, "csharp": extract_csharp,
}


def propose_correspondence(layer_a: str, path_a: str, layer_b: str, path_b: str,
                           min_overlap: float = 0.5) -> list[dict]:
    """Candidate entity pairings between two layers, ranked by FIELD OVERLAP — never by name.

    `reconcile_layers` matches on the name and refuses to guess past it, which is right and, on a
    real repo, can leave you with nothing: a schema whose tables are `cert_lotti_registrati` and
    whose models are `LottoRegistrato` reports every entity missing and every entity extra. That is
    an honest answer and a useless one, and it pushes the operator into doing this comparison by
    hand outside the tool.

    So the comparison comes inside — as a PROPOSAL, which is the only form a similarity score may
    take here. Overlap of field names is a measure of shape, not of naming, and it is evidence for a
    human to accept or reject, never a correspondence. Feed what the human elects back in as
    `reconcile_layers(correspondence=...)`, and from that point the diff is deterministic again: the
    pairing is a declared fact, exactly as a contract carrier declares it.

    Jaccard over field names, one pair per entity (the best available, greedily), and every
    candidate carries its evidence so the human is electing on the fields, not on the number.
    """
    a = EXTRACTORS[layer_a](path_a)
    b = EXTRACTORS[layer_b](path_b)
    _refuse_if_empty((layer_a, path_a, a), (layer_b, path_b, b))   # no entities, no candidates
    scored = []
    for ea, fa in a.items():
        names_a = {f.lower() for f in fa}
        for eb, fb in b.items():
            names_b = {f.lower() for f in fb}
            union = names_a | names_b
            if not union:
                continue
            shared = names_a & names_b
            overlap = len(shared) / len(union)
            if overlap >= min_overlap:
                scored.append({
                    "a": ea, "b": eb, "overlap": round(overlap, 3),
                    "shared_fields": sorted(shared),
                    "only_in_a": sorted(names_a - names_b),
                    "only_in_b": sorted(names_b - names_a),
                    "name_match": ea.lower() == eb.lower(),
                    "status": "proposed",   # never a finding: nothing here has been elected
                })
    scored.sort(key=lambda c: (-c["overlap"], c["a"], c["b"]))
    taken_a, taken_b, out = set(), set(), []
    for cand in scored:
        if cand["a"] in taken_a or cand["b"] in taken_b:
            continue                      # one pairing per entity; the rest are worse by construction
        taken_a.add(cand["a"])
        taken_b.add(cand["b"])
        out.append(cand)
    return out


#: Entities a layer has BY CONSTRUCTION, which no other layer can have a counterpart for. Only the
#: GraphQL spec's three root operation types are listed, and only because the spec lists them
#: (§3.3: "query", "mutation", "subscription", defaulting to types of those names) — a schema has
#: them whether or not anything is persisted, so `Query in graphql has no counterpart in prisma` is
#: a structural fact restated per app, not a finding about the app. Everything else stays untagged:
#: keystone's 1,098 `Keystone*Meta` admin-UI types are equally structural and equally noisy, and
#: naming them here would be this engine encoding one vendor's prefix as a rule. That residual is
#: recorded in `docs/measurements.md` rather than guessed at.
_STRUCTURAL_TIERS = {
    "graphql": {"Query": "operation_root", "Mutation": "operation_root",
                "Subscription": "operation_root"},
}


def _structural_tier(layer: str, entity: str) -> Optional[str]:
    """The structural tier `entity` belongs to on `layer`, or None. `layer` may be a bare stack
    name (`graphql`, from reconcile) or a labelled one (`api:graphql`, from drift_check)."""
    for stack, tiers in _STRUCTURAL_TIERS.items():
        if stack in layer.split(":"):
            return tiers.get(entity)
    return None


def _key_sources(*sides: tuple[str, dict, str]) -> dict:
    """`{layer: "class_name"}` for each side whose entity KEY the extractor derived rather than
    read. Empty when both sides' names are declared in their sources — which is the usual case, so
    the marker's presence is the signal."""
    return {layer: meta[entity]["key_source"]
            for layer, meta, entity in sides
            if meta.get(entity, {}).get("key_source")}


def _entity_finding(kind: str, entity: str, layer_a: str, layer_b: str, own_layer: str,
                    detail: str, sources: dict) -> dict:
    f = {"entity": entity, "field": "*", "kind": kind, "detail": detail,
         "layers": [layer_a, layer_b], "confidence": "inferred"}
    tier = _structural_tier(own_layer, entity)
    if tier:
        f["structural_tier"] = tier
    if sources:
        f["entity_key_source"] = dict(sources)
    return f


def reconcile_layers(layer_a: str, path_a: str, layer_b: str, path_b: str,
                     correspondence: Optional[dict] = None) -> list[dict]:
    """Carrier-less reconciliation: diff two extracted layers **directly** against each other,
    matching entities by table/model/type name and fields by name. This is rescue's path when a
    repo has no shared-types carrier to anchor against (the Phase-0 verdict found the carrier is
    the strongest anchor *when present* — this covers when it is not). Neither side is 'truth': the
    diff is symmetric, so a field present only on one side surfaces as missing_field/extra_field
    (`core/shape-engine.md` honesty rule 2). Entity-name matching is case-insensitive EXACT — no
    pluralization guessing (that is English-specific and unreliable). When two layers use different
    naming conventions (a `users` table vs a `User` model), their correspondence is a fact the
    carrier declares: use `drift_check` (carrier-anchored), which the Phase-0 verdict names the
    strongest anchor. Here, absent an exact name match, a side is honestly missing/extra.

    `correspondence` is the third way, for a repo with no carrier AND no shared naming: a
    `{entity_in_a: entity_in_b}` map the HUMAN elected, which overrides the name match for those
    pairs and leaves every other pair alone. Propose the candidates with
    `propose_correspondence` — that is where field-overlap similarity is allowed to speak, because
    there it only proposes. Once declared here, the pairing is a fact and the diff is deterministic
    again."""
    a = EXTRACTORS[layer_a](path_a)
    b = EXTRACTORS[layer_b](path_b)
    _refuse_if_empty((layer_a, path_a, a), (layer_b, path_b, b))
    a_meta = getattr(a, "entity_meta", {})
    b_meta = getattr(b, "entity_meta", {})
    declared = {str(k).lower(): str(v) for k, v in (correspondence or {}).items()}

    def key(name: str) -> str:
        return name.lower()   # case-insensitive exact; no singular/plural fold (a guess)

    b_by_key = {key(k): k for k in b}
    for a_name, b_name in declared.items():
        if key(b_name) in b_by_key:
            b_by_key[a_name] = b_by_key[key(b_name)]   # a declared pair beats the name match
    findings: list[dict] = []
    matched_b = set()
    for ea, fields_a in a.items():
        bk = b_by_key.get(key(ea))
        sources = _key_sources((layer_a, a_meta, ea))
        if bk is None:
            findings.append(_entity_finding("missing_entity", ea, layer_a, layer_b, layer_a,
                                            f"{ea} in {layer_a} has no counterpart in {layer_b}",
                                            sources))
            continue
        matched_b.add(bk)
        sources.update(_key_sources((layer_b, b_meta, bk)))
        for f in diff_shapes(fields_a, b[bk], layer_a, layer_b, ea):
            if sources:
                f["entity_key_source"] = dict(sources)
            findings.append(f)
    for eb in b:
        if eb not in matched_b:
            findings.append(_entity_finding("extra_entity", eb, layer_a, layer_b, layer_b,
                                            f"{eb} in {layer_b} has no counterpart in {layer_a}",
                                            _key_sources((layer_b, b_meta, eb))))
    return findings


def drift_check(contract_path: str, sqlalchemy: Optional[str] = None,
                pydantic: Optional[str] = None, typescript: Optional[str] = None,
                ddl: Optional[str] = None, drizzle: Optional[str] = None,
                prisma: Optional[str] = None, django: Optional[str] = None,
                graphql: Optional[str] = None, backend: str = "auto") -> list[dict]:
    """Diff every provided layer against the carrier. This IS greenfield's CI drift-check
    and rescue's contract-reconciliation core, pointed at a shared-types-style carrier.

    `backend` routes the TS/GraphQL layers to the tree-sitter parse when "auto"/"treesitter"
    (the other layers already use `ast`/robust parsers); default "regex" keeps it stdlib-only.

    **Honesty rule 3 applies to every side, not only to the carrier**, and that is the whole reason
    the extraction happens up front here instead of inside each branch. Each layer below is matched
    against the carrier by a membership test — `if table in shapes`, `if entity in shapes` — which
    fails closed and *silently* over an extractor that returned `{}`, so this function answered
    `[]`, and `mcp:contract_diff` answered `{"findings": []}` with "an empty findings is zero drift,
    and IS the evidence" written on the tool, over a layer nothing had read. That is the measured
    `Netflix/dispatch` failure (`docs/measurements.md`) arriving through the carrier door — the door
    the playbooks reach for FIRST — while `reconcile_layers` and `propose_correspondence` refused it.
    Every side is extracted before any is diffed so one `EmptyExtraction` can name them all: an
    operator fixing extraction wants the whole list, not the first one."""
    contract = extract_contract(contract_path)
    sides: list[tuple[str, str, dict]] = [("contract", contract_path, contract)]
    read: dict[str, dict] = {}
    for layer, path, extract in (
            ("ddl", ddl, extract_ddl),
            ("drizzle", drizzle, extract_drizzle),
            ("prisma", prisma, extract_prisma),
            ("django", django, extract_django),
            ("graphql", graphql, lambda p: extract_graphql(p, backend=backend)),
            ("sqlalchemy", sqlalchemy, extract_sqlalchemy),
            ("pydantic", pydantic, extract_pydantic),
            ("typescript", typescript, lambda p: extract_typescript(p, backend=backend))):
        if not path:
            continue
        read[layer] = extract(path)
        sides.append((layer, path, read[layer]))
    _refuse_if_empty(*sides)          # an empty carrier proves nothing; nor does an empty layer
    tables = contract_tables(contract_path)
    findings: list[dict] = []

    if ddl:
        shapes = read["ddl"]
        for table, entity in tables.items():
            if table not in shapes:
                findings.append({"entity": entity, "field": "*", "kind": "missing_entity",
                                 "detail": f"table {table} absent from DDL",
                                 "layers": ["contract", "db"], "confidence": "extracted"})
                continue
            findings += diff_shapes(contract[entity], shapes[table], "contract", "db", entity)
    if drizzle:            # table-keyed, like DDL (an ORM layer)
        shapes = read["drizzle"]
        for table, entity in tables.items():
            if table in shapes:
                findings += diff_shapes(contract[entity], shapes[table],
                                        "contract", "orm:drizzle", entity)
    for label, layer in (("orm:prisma", "prisma"), ("orm:django", "django"),
                         ("api:graphql", "graphql")):
        if layer not in read:
            continue
        shapes = read[layer]
        for entity in contract:
            if entity in shapes:
                findings += diff_shapes(contract[entity], shapes[entity],
                                        "contract", label, entity)
    if sqlalchemy:
        shapes = read["sqlalchemy"]
        for table, entity in tables.items():
            if table in shapes:
                findings += diff_shapes(contract[entity], shapes[table],
                                        "contract", "orm", entity)
    if pydantic:
        classes = read["pydantic"]
        for entity in contract:
            if f"{entity}Read" in classes:
                findings += diff_shapes(contract[entity], classes[f"{entity}Read"],
                                        "contract", "api:read", entity)
            if f"{entity}Create" in classes:
                findings += diff_shapes(contract[entity], classes[f"{entity}Create"],
                                        "contract", "api:create", entity, partial=True)
    if typescript:
        interfaces = read["typescript"]
        for entity in contract:
            if entity in interfaces:
                findings += diff_shapes(contract[entity], interfaces[entity],
                                        "contract", "client", entity)
            if f"{entity}Create" in interfaces:
                findings += diff_shapes(contract[entity], interfaces[f"{entity}Create"],
                                        "contract", "client:create", entity, partial=True)
    return findings
