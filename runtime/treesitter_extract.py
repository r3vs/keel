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

Optional, never a hard dependency: the core runtime stays stdlib-only; `available()` probes for
`tree_sitter` + a grammar source and everything degrades to `runtime/shapes.py`'s stdlib parsers
when it is absent. Grammars load from `tree_sitter_language_pack` (100+ languages) or an individual
`tree_sitter_<lang>` module. Targets current py-tree-sitter (Language(caps) → Parser → Query +
QueryCursor.matches) with a fallback to the pre-QueryCursor `query.matches`.
"""
from __future__ import annotations

from typing import Optional

_LANG_CACHE: dict = {}
_PARSER_CACHE: dict = {}


def available() -> bool:
    """True if tree-sitter and at least one grammar source are importable."""
    try:
        import tree_sitter  # noqa: F401
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
}


# ---------------------------------------------------------------------------
# grammar loading + query plumbing (the reusable, stack-agnostic tree-sitter glue)
# ---------------------------------------------------------------------------


def _language(grammar: str):
    if grammar in _LANG_CACHE:
        return _LANG_CACHE[grammar]
    from tree_sitter import Language
    obj = None
    try:
        from tree_sitter_language_pack import get_language
        obj = get_language(grammar)
    except Exception:
        modname = "tree_sitter_" + grammar.replace("-", "_")
        try:
            mod = __import__(modname)
            if grammar in ("typescript", "tsx") and hasattr(mod, "language_" + grammar):
                obj = Language(getattr(mod, "language_" + grammar)())
            else:
                obj = Language(mod.language())
        except Exception as exc:  # pragma: no cover - depends on installed grammars
            raise TreeSitterUnavailable(f"no grammar for {grammar!r}: {exc}") from exc
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


def _type_name(node, spec: dict) -> str:
    """The identifying text of a type node: a named_type's inner name, else the node's own text."""
    if node.type == spec.get("named_type_node") and node.named_child_count:
        return _txt(node.named_children[0])
    return _txt(node).strip()


def _resolve(type_node, sig_node, spec: dict, enums: dict) -> Optional[tuple]:
    """(canonical_type, nullable, enum_values) or None to skip (a relation/collection)."""
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

    optional_token = spec.get("optional_token")
    if optional_token and sig_node is not None and \
            any(c.type == optional_token for c in sig_node.children):
        nullable = True

    if node.type in spec.get("skip_node_types", ()):
        return None

    name = _type_name(node, spec)
    if name in enums:
        return "enum", nullable, enums[name]
    ntm = spec.get("node_type_map", {})
    if node.type in ntm:
        return ntm[node.type], nullable, None
    tm = spec.get("type_map", {})
    if name in tm:
        return tm[name], nullable, None
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
# public surface
# ---------------------------------------------------------------------------

REGISTRY = STACKS  # back-compat alias


def extract(source: str, lang: str) -> dict[str, dict[str, dict]]:
    """Extract `{entity: {field: descriptor}}` from source in `lang` via its declarative spec."""
    if not available():
        raise TreeSitterUnavailable("tree-sitter backend not installed")
    if lang not in STACKS:
        raise KeyError(f"no stack spec for {lang!r}; known: {sorted(STACKS)}")
    return extract_with_spec(source, STACKS[lang])


def extract_typescript(source: str) -> dict[str, dict[str, dict]]:
    return extract(source, "typescript")


def extract_graphql(source: str) -> dict[str, dict[str, dict]]:
    return extract(source, "graphql")
