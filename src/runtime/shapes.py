"""Field-shape engine runtime — extractors + diff over the shared descriptor.

Implements `core/shape-engine.md` for the live stacks the step-0 experiments validated
(rescue: WEAK → standalone extractors are Plan A; greenfield: STRONG → generated layers,
guarded by this very diff as the CI drift-check):

- extract_contract    : the carrier (contract.json descriptor set) — greenfield's source
- extract_sqlalchemy  : SQLAlchemy 2.0 `Mapped`/`mapped_column` models (Python `ast`, no imports)
- extract_pydantic    : Pydantic-v2 DTOs (`<Entity>Read` = full projection, `<Entity>Create`
                        = partial: present fields must match, missing ones are not drift)
- extract_typescript  : `export interface` / `export type` unions (tree-sitter primary; line parser fallback)
- extract_ddl         : Postgres `CREATE TABLE` / `CREATE TYPE ... AS ENUM` (tree-sitter primary; regex fallback)

Every representation reduces to `{name, type, nullable, enum?, constraints?}` with a canonical
type (string|int|float|bool|enum|uuid|json|datetime), then `diff_shapes` compares any two
projections. The two honesty rules are enforced:
  1. uncertain equivalence → `confidence: ambiguous`, downgraded to a note, never asserted;
  2. a field absent on one side IS the finding (missing_field) — never papered over.

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

# The JS/TS-family layers. Their language has no native uuid/datetime (both carried as `string`)
# AND no int/float distinction (both are `number`). Two deterministic diff-time equivalences follow
# from that (see diff_shapes): string ⟷ uuid/datetime, and int ⟷ float — never inferred, just the
# type system's own facts. A client cannot express, nor get wrong, either distinction.
_STRINGLY_LAYERS = ("client", "typescript", "ts")

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
# SQLAlchemy 2.0 models (python ast — parses source, imports nothing)
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


def extract_sqlalchemy(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    enums = _collect_py_enums(tree)
    out: dict[str, dict[str, dict]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        tablename = next((ast.unparse(s.value).strip("'\"") for s in node.body
                          if isinstance(s, ast.Assign)
                          and any(getattr(t, "id", "") == "__tablename__" for t in s.targets)),
                         None)
        if tablename is None:
            continue
        fields: dict[str, dict] = {}
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            attr = stmt.target.id
            call = stmt.value
            if isinstance(call, ast.Call) and ast.unparse(call.func).endswith("relationship"):
                continue
            t, nullable, ev = _ann_to_canonical(stmt.annotation, enums)
            if t == "relationship":
                continue
            col_name, constraints = attr, {}
            if isinstance(call, ast.Call):
                # mapped_column("colname", ...) — explicit column name (reserved-word escape)
                for arg in call.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        col_name = arg.value
                    if isinstance(arg, ast.Call):
                        fn = ast.unparse(arg.func).split(".")[-1]
                        if fn == "String" and arg.args:
                            constraints["max_length"] = ast.literal_eval(arg.args[0])
                        if fn == "ForeignKey" and arg.args:
                            constraints["foreign_key"] = ast.literal_eval(arg.args[0])
                for kw in call.keywords:
                    if kw.arg == "primary_key":
                        constraints["primary_key"] = True
                    if kw.arg == "unique":
                        constraints["unique"] = True
                    if kw.arg in ("default", "server_default"):
                        constraints.setdefault("default", ast.unparse(kw.value))
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[col_name] = descriptor(col_name, t, nullable, ev, constraints or None, conf)
        out[tablename] = fields
    return out


# ---------------------------------------------------------------------------
# Pydantic v2 DTOs
# ---------------------------------------------------------------------------


def extract_pydantic(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    """Returns per-CLASS shapes (UserRead, UserCreate, …); mapping to entities is diff's job."""
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    # module-level Literal aliases: UserRole = Literal["admin", "member"]
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
    out: dict[str, dict[str, dict]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {ast.unparse(b) for b in node.bases}
        if not any("BaseModel" in b or b in out for b in bases):
            continue
        fields: dict[str, dict] = {}
        for base in bases:            # single-level inheritance of already-seen DTO bases
            fields.update(out.get(base, {}))
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            name = stmt.target.id
            if name == "model_config":
                continue
            t, nullable, ev = _ann_to_canonical(stmt.annotation, enums)
            constraints = {}
            if isinstance(stmt.value, ast.Call) and ast.unparse(stmt.value.func) == "Field":
                for kw in stmt.value.keywords:
                    if kw.arg == "max_length":
                        constraints["max_length"] = ast.literal_eval(kw.value)
                    if kw.arg == "validation_alias":
                        constraints["validation_alias"] = ast.literal_eval(kw.value)
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[name] = descriptor(name, t, nullable, ev, constraints or None, conf)
        out[node.name] = fields
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
        # equivalence-table projection (core/shape-engine.md): across a JS/TS-family boundary two
        # of the client's type-system facts hold deterministically, so neither is drift —
        #  1. string ⟷ uuid/datetime (the client has no native uuid/datetime), and
        #  2. int ⟷ float (the client has one `number`; it cannot express the difference).
        # Applied symmetrically at diff time — never inferred from a comment during extraction.
        js = cand_layer.startswith(_STRINGLY_LAYERS) or ref_layer.startswith(_STRINGLY_LAYERS)
        projection = (
            (cand_layer.startswith(_STRINGLY_LAYERS) and cand["type"] == "string"
             and ref["type"] in ("uuid", "datetime"))
            or (ref_layer.startswith(_STRINGLY_LAYERS) and ref["type"] == "string"
                and cand["type"] in ("uuid", "datetime"))
            or (js and ref["type"] in ("int", "float") and cand["type"] in ("int", "float")))
        if ref["type"] != cand["type"] and not projection:
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
    return findings


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


def reconcile_layers(layer_a: str, path_a: str, layer_b: str, path_b: str) -> list[dict]:
    """Carrier-less reconciliation: diff two extracted layers **directly** against each other,
    matching entities by table/model/type name and fields by name. This is rescue's path when a
    repo has no shared-types carrier to anchor against (the Phase-0 verdict found the carrier is
    the strongest anchor *when present* — this covers when it is not). Neither side is 'truth': the
    diff is symmetric, so a field present only on one side surfaces as missing_field/extra_field
    (`core/shape-engine.md` honesty rule 2). Entity-name matching is case-insensitive EXACT — no
    pluralization guessing (that is English-specific and unreliable). When two layers use different
    naming conventions (a `users` table vs a `User` model), their correspondence is a fact the
    carrier declares: use `drift_check` (carrier-anchored), which the Phase-0 verdict names the
    strongest anchor. Here, absent an exact name match, a side is honestly missing/extra."""
    a = EXTRACTORS[layer_a](path_a)
    b = EXTRACTORS[layer_b](path_b)

    def key(name: str) -> str:
        return name.lower()   # case-insensitive exact; no singular/plural fold (a guess)

    b_by_key = {key(k): k for k in b}
    findings: list[dict] = []
    matched_b = set()
    for ea, fields_a in a.items():
        bk = b_by_key.get(key(ea))
        if bk is None:
            findings.append({"entity": ea, "field": "*", "kind": "missing_entity",
                             "detail": f"{ea} in {layer_a} has no counterpart in {layer_b}",
                             "layers": [layer_a, layer_b], "confidence": "inferred"})
            continue
        matched_b.add(bk)
        findings += diff_shapes(fields_a, b[bk], layer_a, layer_b, ea)
    for eb in b:
        if eb not in matched_b:
            findings.append({"entity": eb, "field": "*", "kind": "extra_entity",
                             "detail": f"{eb} in {layer_b} has no counterpart in {layer_a}",
                             "layers": [layer_a, layer_b], "confidence": "inferred"})
    return findings


def drift_check(contract_path: str, sqlalchemy: Optional[str] = None,
                pydantic: Optional[str] = None, typescript: Optional[str] = None,
                ddl: Optional[str] = None, drizzle: Optional[str] = None,
                prisma: Optional[str] = None, django: Optional[str] = None,
                graphql: Optional[str] = None, backend: str = "auto") -> list[dict]:
    """Diff every provided layer against the carrier. This IS greenfield's CI drift-check
    and rescue's contract-reconciliation core, pointed at a shared-types-style carrier.

    `backend` routes the TS/GraphQL layers to the tree-sitter parse when "auto"/"treesitter"
    (the other layers already use `ast`/robust parsers); default "regex" keeps it stdlib-only."""
    contract = extract_contract(contract_path)
    tables = contract_tables(contract_path)
    findings: list[dict] = []

    if ddl:
        shapes = extract_ddl(ddl)
        for table, entity in tables.items():
            if table not in shapes:
                findings.append({"entity": entity, "field": "*", "kind": "missing_entity",
                                 "detail": f"table {table} absent from DDL",
                                 "layers": ["contract", "db"], "confidence": "extracted"})
                continue
            findings += diff_shapes(contract[entity], shapes[table], "contract", "db", entity)
    if drizzle:            # table-keyed, like DDL (an ORM layer)
        shapes = extract_drizzle(drizzle)
        for table, entity in tables.items():
            if table in shapes:
                findings += diff_shapes(contract[entity], shapes[table],
                                        "contract", "orm:drizzle", entity)
    for label, path, fn in (("orm:prisma", prisma, extract_prisma),
                            ("orm:django", django, extract_django),
                            ("api:graphql", graphql, extract_graphql)):
        if not path:
            continue
        shapes = fn(path, backend=backend) if fn is extract_graphql else fn(path)
        for entity in contract:
            if entity in shapes:
                findings += diff_shapes(contract[entity], shapes[entity],
                                        "contract", label, entity)
    if sqlalchemy:
        shapes = extract_sqlalchemy(sqlalchemy)
        for table, entity in tables.items():
            if table in shapes:
                findings += diff_shapes(contract[entity], shapes[table],
                                        "contract", "orm", entity)
    if pydantic:
        classes = extract_pydantic(pydantic)
        for entity in contract:
            if f"{entity}Read" in classes:
                findings += diff_shapes(contract[entity], classes[f"{entity}Read"],
                                        "contract", "api:read", entity)
            if f"{entity}Create" in classes:
                findings += diff_shapes(contract[entity], classes[f"{entity}Create"],
                                        "contract", "api:create", entity, partial=True)
    if typescript:
        interfaces = extract_typescript(typescript, backend=backend)
        for entity in contract:
            if entity in interfaces:
                findings += diff_shapes(contract[entity], interfaces[entity],
                                        "contract", "client", entity)
            if f"{entity}Create" in interfaces:
                findings += diff_shapes(contract[entity], interfaces[f"{entity}Create"],
                                        "contract", "client:create", entity, partial=True)
    return findings


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Shape drift-check: diff generated/hand-written layers against the carrier")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--sqlalchemy")
    parser.add_argument("--pydantic")
    parser.add_argument("--typescript")
    parser.add_argument("--ddl")
    parser.add_argument("--drizzle")
    parser.add_argument("--prisma")
    parser.add_argument("--django")
    parser.add_argument("--graphql")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--treesitter", action="store_true",
                        help="use the tree-sitter backend for TS/GraphQL when installed "
                             "(more robust on multi-line/nested decls); falls back to regex")
    args = parser.parse_args(argv)

    findings = drift_check(args.contract, args.sqlalchemy, args.pydantic,
                           args.typescript, args.ddl, args.drizzle, args.prisma,
                           args.django, args.graphql,
                           backend="auto" if args.treesitter else "regex")
    hard = [f for f in findings if f["confidence"] != "ambiguous"]
    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            tag = "DRIFT " if f["confidence"] != "ambiguous" else "NOTE  "
            print(f"{tag} {f['entity']}.{f['field']}  [{f['kind']}]  {f['detail']}")
        print(f"\nshape drift-check: {len(hard)} drift(s), "
              f"{len(findings) - len(hard)} ambiguous note(s)")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
