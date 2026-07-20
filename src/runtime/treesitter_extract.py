"""Tree-sitter extraction backend — a generic engine driven by declarative per-grammar DATA.

The roadmap asked for the shape engine to generalize beyond hand-written per-stack parsers. The
state-of-the-art way to do that — and the only one that is both **deterministic (no heuristics)**
and **architecturally stack-agnostic** — is the shape ast-grep and semgrep use: one generic engine
plus a **declarative spec per grammar**. Field extraction inherently needs *some* per-grammar
knowledge (you cannot read typed fields from source without knowing the syntax); this module keeps
that knowledge as **data** (`STACKS` below — a tree-sitter query + type maps + structural node-type
names), never as per-stack code, and never as a guess:

- no name-matching, no singular/plural folding, no comment-sniffing — the type comes only from the
  grammar's own type system (the AST + the equivalence `type_map`);
- adding a stack = adding one entry to `STACKS` (a query + maps), not writing a parser.

`extract_with_spec` is the ONE code path. It parses, runs the spec's query, unwraps the type node
with generic tree operations parameterized by the spec's node-type names (peel a nullable wrapper,
flatten a union, drop a collection/relation), then resolves the canonical type from the spec's
enum table / node-type map / type map. Nullability is read structurally (a nullable-default plus a
non-null wrapper, or a union member that is the grammar's null, or an optional-token child) — a
fact, not an inference.

This is the **primary** extraction path (`shapes.py` defaults to `backend="auto"`): a real grammar
parses the whole language, so real-world TS/GraphQL/SQL just works with no per-repo patches — the
fragility that made the regex extractors need a targeted fix per codebase. It is not a *hard*
dependency, though: `available()` probes for `tree_sitter` + a grammar source, and everything
degrades to `runtime/shapes.py`'s stdlib parsers when it is absent (so a stdlib-only environment
still runs). `bootstrap.sh` installs it. The ledger/core stay stdlib-only; only extraction prefers
tree-sitter. Grammars load from `tree_sitter_language_pack` (100+ languages) or an individual
`tree_sitter_<lang>` module. Targets current py-tree-sitter (Language(caps) → Parser → Query +
QueryCursor.matches) with a fallback to the pre-QueryCursor `query.matches`.
"""
from __future__ import annotations

from typing import Optional

_LANG_CACHE: dict = {}
_PARSER_CACHE: dict = {}


def available(lang: Optional[str] = None) -> bool:
    """Is the backend usable — for `lang` specifically, or at all?

    **Those two stopped being the same question, and the difference is the whole point of this
    signature.** `tree-sitter-language-pack` used to compile every grammar into the wheel, so "the
    library imports" really did imply "all ~165 grammars are here" — one probe answered both. It now
    ships a ~2 MB wheel and **downloads each grammar from GitHub releases on first use**, cached
    under `~/.cache/tree-sitter-language-pack/`. So the import proves nothing about any individual
    grammar: offline, air-gapped, behind a proxy, mid-outage, or on a checksum mismatch, the import
    succeeds and the grammar never arrives.

    The gap is not hypothetical and it is not new. The no-arg probe below returns True on the mere
    presence of `tree_sitter_typescript` — after which extracting **Go** raises. The bundled pack
    hid that for as long as it was bundled.

    Passing `lang` answers the question that decides anything, and the only honest way to answer it
    is to load the grammar — which is what this does. `_language` caches both outcomes, so a probe
    costs one attempt per grammar per process, not one per file.

    The no-arg form is kept for `backend="treesitter"`'s error message, which is genuinely asking
    the process-level question: is this environment set up at all?
    """
    try:
        import tree_sitter  # noqa: F401
    except Exception:
        return False
    if lang is not None:
        try:
            _language(_grammar_for(lang))
            return True
        except Exception:
            return False
    try:
        import tree_sitter_language_pack  # noqa: F401
        return True
    except Exception:
        pass
    for mod in ("tree_sitter_typescript", "tree_sitter_python", "tree_sitter_graphql"):
        try:
            __import__(mod)
            return True
        except Exception:
            continue
    return False


class TreeSitterUnavailable(RuntimeError):
    """Raised when the tree-sitter backend is explicitly requested but not installed."""


# ---------------------------------------------------------------------------
# Declarative per-grammar specs — DATA. A new stack is a new entry here, not code.
#
#   grammar          : language-pack key.
#   entity_query     : one match per (entity, field). Bind @entity, @field, @type; optionally @sig.
#   type_node_wrap   : the query captures `type: (annotation (_) @type)` — @type is already the
#                      inner type node (not the annotation wrapper).
#   nullable_default : is a field nullable unless a marker says otherwise? (GraphQL: True; TS: False)
#   non_null_node    : the wrapper node that marks NON-null (GraphQL `non_null_type`); optional.
#   union_node       : the union node (TS `union_type`); a member equal to `null_literal` ⇒ nullable.
#   null_literal     : the text of the grammar's null in a union (TS: "null").
#   optional_token   : a child token on @sig that marks optional (TS "?"); read structurally.
#   named_type_node  : a node whose identifying text is its first named child (GraphQL `named_type`).
#   enum_query       : one match per enum: bind @name, @body. Optional.
#   enum_value_node  : within @body, the node whose text is one enum value (TS `string_fragment`,
#                      GraphQL `enum_value`).
#   enum_member_node : if set, register the alias as an enum only when EVERY flattened @body member
#                      is this node (TS `literal_type` — so a non-string union is not a false enum).
#   type_map         : leaf type text → canonical (the equivalence table, per core/shape-engine.md).
#   node_type_map    : AST node type → canonical (e.g. TS `generic_type` Record<…> → json).
#   skip_node_types  : node types that are collections/relations, not scalar columns.
# ---------------------------------------------------------------------------

STACKS: dict[str, dict] = {
    "typescript": {
        "grammar": "typescript",
        "entity_query": """
            (interface_declaration
              name: (type_identifier) @entity
              body: (interface_body
                (property_signature
                  name: (property_identifier) @field
                  type: (type_annotation (_) @type)) @sig))
        """,
        "nullable_default": False,
        "union_node": "union_type",
        "null_literal": "null",
        "optional_token": "?",
        "enum_query": """
            (type_alias_declaration name: (type_identifier) @name value: (union_type) @body)
        """,
        "enum_value_node": "string_fragment",
        "enum_member_node": "literal_type",
        "type_map": {"string": "string", "number": "int", "boolean": "bool",
                     "unknown": "json", "any": "json", "object": "json"},
        "node_type_map": {"generic_type": "json", "object_type": "json"},
        "skip_node_types": ["array_type", "tuple_type"],
    },
    "graphql": {
        "grammar": "graphql",
        "entity_query": """
            (object_type_definition
              (name) @entity
              (fields_definition
                (field_definition (name) @field (type (_) @type))))
        """,
        "nullable_default": True,
        "non_null_node": "non_null_type",
        "named_type_node": "named_type",
        "enum_query": """
            (enum_type_definition (name) @name (enum_values_definition) @body)
        """,
        "enum_value_node": "enum_value",
        "type_map": {"ID": "uuid", "String": "string", "Int": "int", "Float": "float",
                     "Boolean": "bool", "DateTime": "datetime", "Date": "datetime",
                     "Timestamp": "datetime"},
        "skip_node_types": ["list_type"],
    },
    # ---- backend struct/class stacks: "container with typed fields" — same engine, different
    # nullability convention (Go `*T`, Rust `Option<T>`, C# `T?`, Java primitives), all DATA ----
    "go": {
        "grammar": "go",
        "entity_query": """
            (type_spec name: (type_identifier) @entity type: (struct_type (field_declaration_list
              (field_declaration name: (field_identifier) @field type: (_) @type))))
        """,
        "nullable_default": False,
        "nullable_wrapper_nodes": ["pointer_type"],     # *T is nullable
        "strip_package": True,                          # uuid.UUID → uuid, time.Time → time
        "skip_node_types": ["slice_type", "map_type", "array_type"],
        "type_map": {"string": "string", "bool": "bool", "byte": "int", "rune": "int",
                     "int": "int", "int8": "int", "int16": "int", "int32": "int", "int64": "int",
                     "uint": "int", "uint8": "int", "uint16": "int", "uint32": "int", "uint64": "int",
                     "float32": "float", "float64": "float",
                     "uuid": "uuid", "time": "datetime", "rawmessage": "json"},
    },
    "java": {
        "grammar": "java",
        "entity_query": """
            (class_declaration name: (identifier) @entity body: (class_body
              (field_declaration type: (_) @type declarator: (variable_declarator
                name: (identifier) @field))))
        """,
        "nullable_default": True,                       # object references are nullable
        "non_null_node_types": ["integral_type", "floating_point_type", "boolean_type"],  # primitives
        "type_map": {"string": "string", "uuid": "uuid", "char": "string",
                     "int": "int", "integer": "int", "long": "int", "short": "int", "byte": "int",
                     "biginteger": "int", "double": "float", "float": "float", "bigdecimal": "float",
                     "boolean": "bool", "instant": "datetime", "localdate": "datetime",
                     "localdatetime": "datetime", "offsetdatetime": "datetime",
                     "zoneddatetime": "datetime", "date": "datetime", "timestamp": "datetime"},
    },
    "rust": {
        "grammar": "rust",
        "entity_query": """
            (struct_item name: (type_identifier) @entity body: (field_declaration_list
              (field_declaration name: (field_identifier) @field type: (_) @type)))
        """,
        "nullable_default": False,
        "generic_node": "generic_type",
        "nullable_generic_names": ["Option"],           # Option<T> is nullable
        "type_map": {"string": "string", "str": "string", "bool": "bool",
                     "i8": "int", "i16": "int", "i32": "int", "i64": "int", "i128": "int",
                     "isize": "int", "u8": "int", "u16": "int", "u32": "int", "u64": "int",
                     "u128": "int", "usize": "int", "f32": "float", "f64": "float",
                     "uuid": "uuid", "datetime": "datetime", "naivedatetime": "datetime",
                     "naivedate": "datetime", "value": "json"},
    },
    "csharp": {
        "grammar": "csharp",
        "entity_query": """
            (class_declaration name: (identifier) @entity body: (declaration_list
              (property_declaration type: (_) @type name: (identifier) @field)))
        """,
        "nullable_default": False,
        "nullable_wrapper_nodes": ["nullable_type"],    # T? is nullable
        "type_map": {"string": "string", "guid": "uuid", "char": "string",
                     "int": "int", "long": "int", "short": "int", "byte": "int", "uint": "int",
                     "ulong": "int", "ushort": "int", "sbyte": "int", "double": "float",
                     "float": "float", "decimal": "float", "bool": "bool",
                     "datetime": "datetime", "datetimeoffset": "datetime", "dateonly": "datetime",
                     "timeonly": "datetime"},
    },
}


# ---------------------------------------------------------------------------
# grammar loading + query plumbing (the reusable, stack-agnostic tree-sitter glue)
# ---------------------------------------------------------------------------


def _grammar_for(lang: str) -> str:
    """The grammar a stack parses. Data for the spec-driven stacks; for the custom walks it is the
    stack's own name, which `_extract_sql`'s `parse(source, "sql")` states outright."""
    if lang in STACKS:
        return STACKS[lang]["grammar"]
    if lang in _CUSTOM:
        return lang
    raise KeyError(f"no stack spec for {lang!r}; known: {sorted(set(STACKS) | set(_CUSTOM))}")


def _language(grammar: str):
    """Load a grammar, caching **both** outcomes.

    The negative cache is not an optimization — it is what keeps a failure cheap. A rescue walks
    thousands of files, and `tree-sitter-language-pack` now fetches grammars over the network on
    first use. Without a negative cache an undownloadable grammar is retried, network timeout and
    all, **once per file** — turning a clean fall-back-to-stdlib into a run that looks like a hang.
    Fail once, remember it, move on.
    """
    cached = _LANG_CACHE.get(grammar)
    if isinstance(cached, TreeSitterUnavailable):
        raise cached
    if cached is not None:
        return cached
    from tree_sitter import Language
    obj = None
    try:
        from tree_sitter_language_pack import get_language
        obj = get_language(grammar)
    except Exception as pack_exc:
        modname = "tree_sitter_" + grammar.replace("-", "_")
        try:
            mod = __import__(modname)
            if grammar in ("typescript", "tsx") and hasattr(mod, "language_" + grammar):
                obj = Language(getattr(mod, "language_" + grammar)())
            else:
                obj = Language(mod.language())
        except Exception as exc:  # pragma: no cover - depends on installed grammars
            # Report BOTH causes. Collapsing to the second one prints "No module named
            # tree_sitter_go" when the truth was "download failed: connection refused" — a
            # misleading diagnosis on precisely the failure mode this path exists to survive.
            err = TreeSitterUnavailable(
                f"no grammar for {grammar!r}: language-pack: {pack_exc}; module {modname}: {exc}")
            _LANG_CACHE[grammar] = err
            raise err from exc
    _LANG_CACHE[grammar] = obj
    return obj


def _parser(grammar: str):
    if grammar not in _PARSER_CACHE:
        from tree_sitter import Parser
        _PARSER_CACHE[grammar] = Parser(_language(grammar))
    return _PARSER_CACHE[grammar]


def _matches(grammar: str, query_str: str, root) -> list:
    """Run a query → [(pattern_index, {capture_name: [Node, ...]}), ...]. Version-robust."""
    from tree_sitter import Query
    query = Query(_language(grammar), query_str)
    try:
        from tree_sitter import QueryCursor
        return QueryCursor(query).matches(root)
    except Exception:
        return query.matches(root)  # pragma: no cover - older tree-sitter only


def _txt(node) -> str:
    return node.text.decode("utf-8", "replace")


def _cap1(caps: dict, name: str):
    seq = caps.get(name)
    return seq[0] if seq else None


def parse(source: str, grammar: str):
    return _parser(grammar).parse(bytes(source, "utf-8")).root_node


def _descriptor(name, type_, nullable, enum=None, confidence="extracted"):
    d = {"name": name, "type": type_, "nullable": nullable, "confidence": confidence}
    if enum:
        d["enum"] = list(enum)
    return d


# ---------------------------------------------------------------------------
# generic type resolution — one code path, parameterized only by spec DATA
# ---------------------------------------------------------------------------


def _flatten(node, union_node) -> list:
    """Flatten a (possibly left-nested) union into its members."""
    out = []
    for m in node.named_children:
        if m.type == union_node:
            out.extend(_flatten(m, union_node))
        else:
            out.append(m)
    return out


def _collect_leaves(node, leaf_type: str) -> list:
    out = []
    if node.type == leaf_type:
        out.append(node)
        return out
    for c in node.named_children:
        out.extend(_collect_leaves(c, leaf_type))
    return out


def _collect_enums(spec: dict, root) -> dict[str, list]:
    enums: dict[str, list] = {}
    eq = spec.get("enum_query")
    if not eq:
        return enums
    leaf = spec["enum_value_node"]
    member_node = spec.get("enum_member_node")
    union_node = spec.get("union_node")
    for _, caps in _matches(spec["grammar"], eq, root):
        name_node, body = _cap1(caps, "name"), _cap1(caps, "body")
        if name_node is None or body is None:
            continue
        if member_node:      # require every member to be the enum-member node (all string literals)
            members = _flatten(body, union_node) if union_node else list(body.named_children)
            if not members or any(m.type != member_node for m in members):
                continue
        values = [_txt(v).strip("'\"") for v in _collect_leaves(body, leaf)]
        if values:
            enums[_txt(name_node)] = values
    return enums


def _generic_arg(node):
    """The first type argument of a generic type node (Rust `Option<String>` → `String`)."""
    for c in node.named_children:
        if c.type == "type_arguments" and c.named_child_count:
            return c.named_children[0]
    return None


def _type_name_raw(node, spec: dict) -> str:
    """The identifying text of a type node (case preserved): a named_type's inner name, else the
    node's own text with any generic arguments stripped for the base lookup."""
    import re
    if node.type == spec.get("named_type_node") and node.named_child_count:
        return _txt(node.named_children[0])
    return re.sub(r"\s*<.*", "", _txt(node).strip())


def _resolve(type_node, sig_node, spec: dict, enums: dict) -> Optional[tuple]:
    """(canonical_type, nullable, enum_values) or None to skip. One code path; every language's
    nullability convention is spec DATA, not code: a non-null wrapper (GraphQL), a union-with-null
    (TS), a nullable wrapper node (Go `*T`, C# `T?`), a nullable generic (Rust `Option<T>`), an
    optional token (TS `?`), or non-null node types that override a nullable default (Java primitives)."""
    node = type_node
    nullable = bool(spec.get("nullable_default", False))

    non_null = spec.get("non_null_node")
    if non_null and node.type == non_null and node.named_child_count:
        nullable = False
        node = node.named_children[0]

    union_node = spec.get("union_node")
    if union_node and node.type == union_node:
        members = _flatten(node, union_node)
        null_lit = spec.get("null_literal", "null")
        non_null_members = [m for m in members if _txt(m).strip() != null_lit]
        if len(non_null_members) < len(members):
            nullable = True
        node = non_null_members[0] if non_null_members else members[0]
        if non_null and node.type == non_null and node.named_child_count:
            node = node.named_children[0]

    # wrapper-nullable (Go `pointer_type`, C# `nullable_type`) and generic-nullable (Rust
    # `Option<T>`): the wrapper marks the field nullable; unwrap to the inner type. Peel defensively.
    wrappers = tuple(spec.get("nullable_wrapper_nodes", ()))
    generic_node = spec.get("generic_node")
    generic_names = set(spec.get("nullable_generic_names", ()))
    for _ in range(4):
        if wrappers and node.type in wrappers and node.named_child_count:
            nullable = True
            node = node.named_children[0]
        elif generic_node and node.type == generic_node and generic_names \
                and node.named_child_count and _txt(node.named_children[0]) in generic_names:
            nullable = True
            arg = _generic_arg(node)
            if arg is None:
                break
            node = arg
        else:
            break

    optional_token = spec.get("optional_token")
    if optional_token and sig_node is not None and \
            any(c.type == optional_token for c in sig_node.children):
        nullable = True

    if node.type in spec.get("non_null_node_types", ()):
        nullable = False        # a primitive (Java int/boolean) overrides a nullable default

    if node.type in spec.get("skip_node_types", ()):
        return None

    raw = _type_name_raw(node, spec)
    if raw in enums:
        return "enum", nullable, enums[raw]
    ntm = spec.get("node_type_map", {})
    if node.type in ntm:
        return ntm[node.type], nullable, None
    tm = spec.get("type_map", {})
    # try the name case-sensitively (GraphQL `ID`/`String`), then folded (Java `Integer`, C# `Guid`),
    # then the last path component (Go `uuid.UUID` → `uuid`) — all deterministic.
    for key in (raw, raw.lower(), raw.lower().split(".")[-1] if spec.get("strip_package") else None):
        if key and key in tm:
            return tm[key], nullable, None
    return "unknown", nullable, None


def extract_with_spec(source: str, spec: dict) -> dict[str, dict[str, dict]]:
    grammar = spec["grammar"]
    root = parse(source, grammar)
    enums = _collect_enums(spec, root)
    out: dict[str, dict[str, dict]] = {}
    for _, caps in _matches(grammar, spec["entity_query"], root):
        entity_node = _cap1(caps, "entity")
        field_node = _cap1(caps, "field")
        type_node = _cap1(caps, "type")
        if entity_node is None:
            continue
        entity = _txt(entity_node)
        out.setdefault(entity, {})
        if field_node is None or type_node is None:
            continue
        resolved = _resolve(type_node, _cap1(caps, "sig"), spec, enums)
        if resolved is None:
            continue
        canonical, nullable, enum_vals = resolved
        fname = _txt(field_node)
        conf = "extracted" if canonical != "unknown" else "ambiguous"
        out[entity][fname] = _descriptor(fname, canonical, nullable, enum_vals, conf)
    return out


# ---------------------------------------------------------------------------
# SQL DDL — a custom extractor (SQL columns are positional `name type ...`, not the
# type-node model TS/GraphQL share). Still declarative: tree-sitter parses ALL of Postgres
# natively (IF NOT EXISTS, `public.` schema prefixes, quoted idents, multi-word types) — no
# per-repo patches — and the type meaning comes from the same finite map `shapes` uses.
# ---------------------------------------------------------------------------

_SQL_COLS_QUERY = """
(create_table
  (object_reference) @table
  (column_definitions (column_definition) @def))
"""
_SQL_ENUM_QUERY = """
(create_type (object_reference (identifier) @name) (enum_elements) @elements)
"""


def _extract_sql(source: str) -> dict[str, dict[str, dict]]:
    import re
    from shapes import _DDL_TYPE_MAP, _STRING_SIZED, descriptor   # single-source the type map
    root = parse(source, "sql")

    enums: dict[str, list] = {}
    for _, caps in _matches("sql", _SQL_ENUM_QUERY, root):
        name, elems = _cap1(caps, "name"), _cap1(caps, "elements")
        if name is None or elems is None:
            continue
        vals = [_txt(lit).strip("'\"") for lit in elems.named_children if lit.type == "literal"]
        if vals:
            enums[_txt(name).split(".")[-1].strip('"')] = vals

    out: dict[str, dict[str, dict]] = {}
    for _, caps in _matches("sql", _SQL_COLS_QUERY, root):
        tref, defnode = _cap1(caps, "table"), _cap1(caps, "def")
        if tref is None or defnode is None:
            continue
        table = _txt(tref).split(".")[-1].strip('"')
        out.setdefault(table, {})
        kids = defnode.named_children
        if len(kids) < 2 or kids[0].type != "identifier":
            continue
        col = _txt(kids[0]).strip('"')
        raw = re.sub(r"\s+", " ", _txt(kids[1]).strip().lower())      # 2nd child is the type
        base = re.sub(r"\s*\(.*", "", raw)                            # strip (size)
        cons: dict = {}
        evals = None
        if base in _STRING_SIZED:
            t = "string"
            if (m := re.search(r"\((\d+)", raw)):
                cons["max_length"] = int(m.group(1))
        elif base in _DDL_TYPE_MAP:
            t = _DDL_TYPE_MAP[base]
        elif base in enums:
            t, evals = "enum", enums[base]
        else:
            t = "unknown"
        dtext = _txt(defnode)
        du = dtext.upper()
        nullable = "NOT NULL" not in du and "PRIMARY KEY" not in du
        if "PRIMARY KEY" in du:
            cons["primary_key"] = True
        if "UNIQUE" in du:
            cons["unique"] = True
        fk = re.search(r'REFERENCES\s+(?:"?\w+"?\.)?"?(\w+)"?\s*\((\w+)\)', dtext, re.I)
        if fk:
            cons["foreign_key"] = f"{fk.group(1)}.{fk.group(2)}"
        conf = "extracted" if t != "unknown" else "ambiguous"
        out[table][col] = descriptor(col, t, nullable, evals, cons or None, conf)
    return out


# ---------------------------------------------------------------------------
# public surface
# ---------------------------------------------------------------------------

REGISTRY = STACKS  # back-compat alias
_CUSTOM = {"sql": _extract_sql}   # grammars whose shape needs a small custom walk, not the engine


def extract(source: str, lang: str) -> dict[str, dict[str, dict]]:
    """Extract `{entity: {field: descriptor}}` from source in `lang` via its spec / custom walk."""
    if not available():
        raise TreeSitterUnavailable("tree-sitter backend not installed")
    if lang in _CUSTOM:
        return _CUSTOM[lang](source)
    if lang not in STACKS:
        raise KeyError(f"no stack spec for {lang!r}; known: {sorted(set(STACKS) | set(_CUSTOM))}")
    return extract_with_spec(source, STACKS[lang])


def extract_typescript(source: str) -> dict[str, dict[str, dict]]:
    return extract(source, "typescript")


def extract_graphql(source: str) -> dict[str, dict[str, dict]]:
    return extract(source, "graphql")
