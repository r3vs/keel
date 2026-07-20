"""Structural knowledge-graph builder — the tree-sitter-native backbone the study recommends.

The step-0 verdict (`references/contract-reconciliation.md`) settled that the graph is worth exactly
its **structural spine** — files/symbols as EXTRACTED nodes, `contains`/`imports`/`calls` as EXTRACTED
edges — and nothing more. Graphify produced that spine as an external pip dependency whose cross-layer
output we already refuse to ride; this module produces the *same* spine ourselves, deterministically,
from the parser the runtime already ships, so there is no dependency whose output we then discard.

What it emits is exactly what `graph.py` consumes: a plain NetworkX node-link `graph.json`
(`{"graph": {...}, "nodes": [...], "links": [...]}`) — so anchoring, blast-radius, the visual map,
and the `understand`-mode tools all read the builder's output with no adapter.

Determinism is the contract (the whole point of the EXTRACTED tier):
- **structure is read by code, never guessed.** Python is parsed with the stdlib `ast`; other
  languages use tree-sitter *when present* and degrade to file-only nodes when absent — never a
  regex that invents an edge.
- **no fabrication.** An `imports` edge is emitted only when the target resolves to exactly one
  internal file; an ambiguous or external import is dropped, not guessed. `calls` stay intra-file
  (a call to a name defined in the same file / a method on the enclosing class), because cross-file
  call resolution is not deterministic without a full type environment.
- every run of the same tree yields byte-identical output (sorted nodes/edges, stable ids).

Stdlib-only floor. `built_at_commit` is read from git so the staleness gate in `graph.py` works.
"""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
from typing import Iterable, Optional

# Directories that never carry authored source worth graphing. Kept deliberately small and explicit
# (no per-repo tuning): the point is a fast, deterministic default, not a perfect ignore file.
_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".venv", "venv", "env", "dist", "build", ".next", ".nuxt", "out",
    "target", "coverage", ".idea", ".vscode", "vendor", ".cache", ".tox", "site-packages",
})
# Generic container segments stripped when deriving a node's architectural layer, so a repo laid out
# as `src/api/...` reports layer "api", not the uninformative "src".
_LAYER_CONTAINERS = frozenset({"src", "app", "lib", "libs", "packages", "pkg", "source"})

_LANG_BY_EXT = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby", ".php": "php",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".kt": "kotlin", ".scala": "scala", ".swift": "swift", ".dart": "dart",
    ".sql": "sql", ".graphql": "graphql", ".gql": "graphql",
}


def _posix(p: str) -> str:
    return p.replace("\\", "/")


def layer_of(relpath: str) -> str:
    """The architectural layer of a file = its first meaningful path segment (a generic container
    like `src/` is stripped first). A top-level file is layer `root`. Deterministic, no LLM."""
    parts = [p for p in _posix(relpath).split("/") if p]
    parts = parts[:-1]  # drop the filename
    while parts and parts[0] in _LAYER_CONTAINERS:
        parts = parts[1:]
    return parts[0] if parts else "root"


def head_commit(root: pathlib.Path) -> Optional[str]:
    """The repo's current HEAD sha (short), or None outside a git tree. Feeds the staleness gate."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------------------
# Python extraction (stdlib `ast`) — the always-on, fully-deterministic path.
# ---------------------------------------------------------------------------

def _py_module_index(files: list[str]) -> dict[str, list[str]]:
    """Map a dotted-module *suffix* → the internal files it could name, for import resolution.
    `a/b/c.py` is indexed under `c`, `b.c`, and `a.b.c` (and the `__init__` package forms), so a
    `from a.b import c` or a flat `import c` can be matched by the longest unambiguous suffix."""
    index: dict[str, list[str]] = {}
    for rel in files:
        if not rel.endswith(".py"):
            continue
        parts = rel[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        for i in range(len(parts)):
            key = ".".join(parts[i:])
            index.setdefault(key, []).append(rel)
    return index


def _resolve_py_import(module: str, level: int, importer_rel: str,
                       index: dict[str, list[str]]) -> Optional[str]:
    """Resolve a Python import to exactly one internal file, or None. Relative imports resolve
    against the importer's package; absolute imports match the longest unambiguous module suffix.
    Never returns a guess — zero or multiple candidates ⇒ None (the no-fabrication rule)."""
    if level and level > 0:
        base = importer_rel.split("/")[:-1]  # the importer's package dir
        up = level - 1
        if up:
            base = base[:-up] if up <= len(base) else []
        target = base + (module.split(".") if module else [])
        if not target:
            return None
        hits = index.get(".".join(target), [])
        return hits[0] if len(hits) == 1 else None
    if not module:
        return None
    hits = index.get(module, [])
    return hits[0] if len(hits) == 1 else None


def _extract_python(rel: str, src: str, index: dict[str, list[str]]) -> tuple[list[dict], list[dict]]:
    """Nodes (function/class/method) + edges (contains/imports/calls) for one Python file.
    Best-effort but never fabricating: unresolved imports and unresolved calls are simply omitted."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], []  # a file we cannot parse contributes only its file node (added by the caller)

    file_id = f"file:{rel}"
    nodes: list[dict] = []
    edges: list[dict] = []
    # symbol name (in this file) → its node id, for intra-file call resolution
    local: dict[str, str] = {}

    def _node(kind: str, qual: str, lineno: int, end: Optional[int]) -> str:
        nid = f"sym:{rel}:{qual}:{lineno}"
        nodes.append({
            "id": nid, "type": kind, "name": qual, "source_file": rel,
            "start_line": lineno, "end_line": end, "confidence": "extracted",
            "language": "python", "layer": layer_of(rel),
        })
        return nid

    def _walk(body: Iterable[ast.stmt], parent_id: str, prefix: str) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if prefix else "function"
                qual = f"{prefix}{stmt.name}"
                sid = _node(kind, qual, stmt.lineno, getattr(stmt, "end_lineno", None))
                local.setdefault(stmt.name, sid)
                local.setdefault(qual, sid)
                edges.append({"source": parent_id, "target": sid, "type": "contains",
                              "confidence": "extracted"})
                _walk(stmt.body, sid, "")  # nested defs are contained by this function
            elif isinstance(stmt, ast.ClassDef):
                qual = f"{prefix}{stmt.name}"
                cid = _node("class", qual, stmt.lineno, getattr(stmt, "end_lineno", None))
                local.setdefault(stmt.name, cid)
                edges.append({"source": parent_id, "target": cid, "type": "contains",
                              "confidence": "extracted"})
                _walk(stmt.body, cid, f"{qual}.")

    _walk(tree.body, file_id, "")

    # imports: file → internal file, only when unambiguously resolved
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.ImportFrom):
            tgt = _resolve_py_import(stmt.module or "", stmt.level or 0, rel, index)
            if tgt and tgt != rel:
                edges.append({"source": file_id, "target": f"file:{tgt}", "type": "imports",
                              "confidence": "extracted"})
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                tgt = _resolve_py_import(alias.name, 0, rel, index)
                if tgt and tgt != rel:
                    edges.append({"source": file_id, "target": f"file:{tgt}", "type": "imports",
                                  "confidence": "extracted"})

    # calls: intra-file only, resolved by the callee's plain name being defined in this file
    def _calls_in(node: ast.AST, owner_id: str) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                fn = child.func
                name = fn.id if isinstance(fn, ast.Name) else (
                    fn.attr if isinstance(fn, ast.Attribute) else None)
                if name and name in local and local[name] != owner_id:
                    edges.append({"source": owner_id, "target": local[name], "type": "calls",
                                  "confidence": "extracted"})

    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _calls_in(stmt, local.get(stmt.name, file_id))
        elif isinstance(stmt, ast.ClassDef):
            for m in stmt.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _calls_in(m, local.get(f"{stmt.name}.{m.name}", file_id))

    # dedupe edges (an intra-file call can appear many times) — deterministic order preserved later
    seen = set()
    uniq = []
    for e in edges:
        k = (e["source"], e["target"], e["type"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return nodes, uniq


# ---------------------------------------------------------------------------
# Tree-sitter extraction (other languages) — declarative per-grammar queries.
# Reuses treesitter_extract's grammar loader + query runner (py-tree-sitter version handling lives in
# one place). Guarded: absent tree-sitter, or a language with no query set, degrades to a file node —
# never a regex that invents a symbol. Extends additively: a new language is a new query set here.
# ---------------------------------------------------------------------------

_TS_GRAMMAR_BY_EXT = {
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
}
_JS_EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
_IMPORT_QUERY = "(import_statement source: (string) @src)"
_TS_QUERIES = {
    "typescript": {
        "function": ["(function_declaration name: (identifier) @name) @node",
                     "(variable_declarator name: (identifier) @name value: (arrow_function)) @node"],
        "class": ["(class_declaration name: (type_identifier) @name) @node"],
        "method": ["(method_definition name: (property_identifier) @name) @node"],
    },
    "javascript": {
        "function": ["(function_declaration name: (identifier) @name) @node",
                     "(variable_declarator name: (identifier) @name value: (arrow_function)) @node"],
        "class": ["(class_declaration name: (identifier) @name) @node"],
        "method": ["(method_definition name: (property_identifier) @name) @node"],
    },
}
_TS_QUERIES["tsx"] = _TS_QUERIES["typescript"]  # tsx reuses the TS queries, on the tsx grammar


def _treesitter_available() -> bool:
    try:
        import treesitter_extract as tse
        return tse.available()
    except Exception:
        return False


def _resolve_js_import(spec: str, importer_rel: str, fileset: set) -> Optional[str]:
    """Resolve a **relative** JS/TS import specifier to exactly one internal file, or None. A bare
    (package) specifier is dropped; a relative one resolves against the importer's dir, trying the
    known extensions and an `/index` file. No fabrication — unresolved ⇒ None."""
    spec = spec.strip().strip("\"'")
    if not spec.startswith("."):
        return None
    base = "/".join(importer_rel.split("/")[:-1])
    combined = f"{base}/{spec}" if base else spec
    parts: list[str] = []
    for seg in combined.split("/"):
        if seg in ("", "."):
            continue
        parts = parts[:-1] if seg == ".." and parts else (parts if seg == ".." else parts + [seg])
    stem = "/".join(parts)
    candidates = []
    if pathlib.PurePosixPath(stem).suffix.lower() in _JS_EXTS:
        candidates.append(stem)
    candidates += [stem + ext for ext in _JS_EXTS] + [stem + "/index" + ext for ext in _JS_EXTS]
    return next((c for c in candidates if c in fileset), None)


def _extract_treesitter(rel: str, src: str, ext: str, fileset: set) -> tuple[list[dict], list[dict]]:
    """Symbol nodes (function/class/method) + contains/imports edges for one non-Python file via
    tree-sitter. Methods are qualified with their enclosing class (tightest containing class range)
    and linked to it; imports resolve only when the relative specifier lands on an internal file."""
    grammar = _TS_GRAMMAR_BY_EXT.get(ext)
    queries = _TS_QUERIES.get(grammar)
    if grammar is None or queries is None:
        return [], []
    try:
        import treesitter_extract as tse
        root_node = tse.parse(src, grammar)
    except Exception:
        return [], []  # unloadable grammar / parse error → file-only, never a guess

    lang = _LANG_BY_EXT.get(ext, "text")
    file_id = f"file:{rel}"
    nodes: list[dict] = []
    edges: list[dict] = []
    classes: list[tuple[int, int, str, str]] = []  # (start, end, class_node_id, class_name)

    def _add(kind: str, name: str, node, parent_id: str) -> tuple[str, int, int]:
        start, end = node.start_point[0] + 1, node.end_point[0] + 1
        nid = f"sym:{rel}:{name}:{start}"
        nodes.append({"id": nid, "type": kind, "name": name, "source_file": rel,
                      "start_line": start, "end_line": end, "confidence": "extracted",
                      "language": lang, "layer": layer_of(rel)})
        edges.append({"source": parent_id, "target": nid, "type": "contains",
                      "confidence": "extracted"})
        return nid, start, end

    def _cap(caps):
        return tse._cap1(caps, "node"), tse._cap1(caps, "name")

    try:
        for q in queries.get("class", []):
            for _i, caps in tse._matches(grammar, q, root_node):
                nnode, nm = _cap(caps)
                if nnode is not None and nm is not None:
                    cname = tse._txt(nm)
                    cid, s, e = _add("class", cname, nnode, file_id)
                    classes.append((s, e, cid, cname))
        for q in queries.get("function", []):
            for _i, caps in tse._matches(grammar, q, root_node):
                nnode, nm = _cap(caps)
                if nnode is not None and nm is not None:
                    _add("function", tse._txt(nm), nnode, file_id)
        for q in queries.get("method", []):
            for _i, caps in tse._matches(grammar, q, root_node):
                nnode, nm = _cap(caps)
                if nnode is None or nm is None:
                    continue
                mstart = nnode.start_point[0] + 1
                owner_id, owner_name, best = file_id, None, None
                for s, e, cid, cname in classes:
                    if s <= mstart <= e and (best is None or (e - s) < best):
                        best, owner_id, owner_name = (e - s), cid, cname
                mname = f"{owner_name}.{tse._txt(nm)}" if owner_name else tse._txt(nm)
                _add("method", mname, nnode, owner_id)
        seen_imp = set()
        for _i, caps in tse._matches(grammar, _IMPORT_QUERY, root_node):
            snode = tse._cap1(caps, "src")
            if snode is None:
                continue
            tgt = _resolve_js_import(tse._txt(snode), rel, fileset)
            if tgt and tgt != rel and tgt not in seen_imp:
                seen_imp.add(tgt)
                edges.append({"source": file_id, "target": f"file:{tgt}", "type": "imports",
                              "confidence": "extracted"})
    except Exception:
        return [], []  # any grammar/query mismatch degrades to file-only rather than half-data

    # dedupe overlapping captures (arrow vs declaration) deterministically
    seen, uniq_nodes = set(), []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            uniq_nodes.append(n)
    eseen, uniq_edges = set(), []
    for e in edges:
        k = (e["source"], e["target"], e["type"])
        # keep every edge except a `contains` whose symbol target was deduped away; import edges
        # (file -> file) must survive — their target is another file node, not in this file's symbols
        if k in eseen or (e["type"] == "contains" and e["target"] not in seen):
            continue
        eseen.add(k)
        uniq_edges.append(e)
    return uniq_nodes, uniq_edges


# ---------------------------------------------------------------------------
# Repo walk + assembly
# ---------------------------------------------------------------------------

def _iter_source_files(root: pathlib.Path) -> list[str]:
    """Relative posix paths of source files under `root`, skipping the ignore set. Sorted."""
    out: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        if p.suffix.lower() in _LANG_BY_EXT:
            out.append(_posix(str(p.relative_to(root))))
    return sorted(out)


def build_graph(root: str | pathlib.Path, *, commit: Optional[str] = None) -> dict:
    """Build the structural graph of `root` → a node-link dict ready for `graph.py`/the map.

    One `file` node per source file (always), plus symbol nodes + contains/imports/calls edges for
    every Python file (stdlib `ast`) and for other languages when tree-sitter is present. Output is
    deterministic: nodes and links are sorted by id and validated (referential integrity) before
    return, so a re-run on the same tree is byte-identical.
    """
    root = pathlib.Path(root).resolve()
    files = _iter_source_files(root)
    fileset = set(files)
    py_index = _py_module_index(files)
    ts_ok = _treesitter_available()

    nodes: list[dict] = []
    links: list[dict] = []
    for rel in files:
        ext = pathlib.Path(rel).suffix.lower()
        lang = _LANG_BY_EXT.get(ext, "text")
        nodes.append({
            "id": f"file:{rel}", "type": "file", "name": _posix(rel).split("/")[-1],
            "source_file": rel, "start_line": 1, "end_line": None,
            "confidence": "extracted", "language": lang, "layer": layer_of(rel),
        })
        if lang == "python":
            try:
                src = (root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            sn, se = _extract_python(rel, src, py_index)
            nodes.extend(sn)
            links.extend(se)
        elif ts_ok and ext in _TS_GRAMMAR_BY_EXT:
            # JS/TS/… via tree-sitter when it is installed. Absent it (e.g. a stdlib-only CI),
            # these files fall through to their file node only — honest degradation, never a
            # regex that invents a symbol.
            try:
                src = (root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            sn, se = _extract_treesitter(rel, src, ext, fileset)
            nodes.extend(sn)
            links.extend(se)

    data = {
        "graph": {
            "built_at_commit": commit if commit is not None else head_commit(root),
            "root": str(root),
            "generated_by": "runtime/graph_build.py",
            "directed": True,
            "multigraph": False,
        },
        "nodes": nodes,
        "links": links,
    }
    clean, _issues = validate_repair(data)
    return clean


# ---------------------------------------------------------------------------
# Validate / repair — the guardrail for any (LLM- or tool-authored) graph.
# ---------------------------------------------------------------------------

_CONF = {"extracted", "inferred", "ambiguous"}


def validate_repair(data: dict) -> tuple[dict, list[dict]]:
    """Return a cleaned copy of `data` + a showable list of `GraphIssue`s.

    The guardrail sibling of the findings gate, for graphs: drop nodes without an id, drop duplicate
    ids (keep first), **drop edges whose endpoints do not resolve** (referential integrity), coerce
    confidence to the canonical set, and lowercase edge types. Every repair is recorded as an issue
    `{level, category, message}` so the fix is auditable rather than silent.
    """
    issues: list[dict] = []
    nodes_in = data.get("nodes") or []
    raw_edges = data.get("links")
    if raw_edges is None:
        raw_edges = data.get("edges") or []

    node_ids: set[str] = set()
    nodes_out: list[dict] = []
    for n in nodes_in:
        nid = n.get("id")
        if nid is None or nid == "":
            issues.append({"level": "warn", "category": "node.no_id",
                           "message": f"dropped a node with no id: {n.get('name') or n!r:.80}"})
            continue
        nid = str(nid)
        if nid in node_ids:
            issues.append({"level": "warn", "category": "node.duplicate_id",
                           "message": f"dropped a duplicate node id: {nid}"})
            continue
        conf = str(n.get("confidence") or "extracted").strip().lower()
        if conf not in _CONF:
            issues.append({"level": "info", "category": "node.confidence",
                           "message": f"node {nid}: confidence {n.get('confidence')!r} → extracted"})
            conf = "extracted"
        n = dict(n)
        n["id"], n["confidence"] = nid, conf
        node_ids.add(nid)
        nodes_out.append(n)

    edges_out: list[dict] = []
    seen_edges: set[tuple] = set()
    for e in raw_edges:
        s, t = e.get("source"), e.get("target")
        if s is None or t is None:
            issues.append({"level": "warn", "category": "edge.no_endpoint",
                           "message": f"dropped an edge with a missing endpoint: {e!r:.80}"})
            continue
        s, t = str(s), str(t)
        if s not in node_ids or t not in node_ids:
            issues.append({"level": "warn", "category": "edge.dangling",
                           "message": f"dropped a dangling edge {s} -> {t} "
                                      f"({'source' if s not in node_ids else 'target'} missing)"})
            continue
        et = str(e.get("type") or e.get("label") or e.get("relation") or "related").strip().lower()
        conf = str(e.get("confidence") or "extracted").strip().lower()
        if conf not in _CONF:
            conf = "extracted"
        key = (s, t, et)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges_out.append({"source": s, "target": t, "type": et, "confidence": conf})

    nodes_out.sort(key=lambda n: n["id"])
    edges_out.sort(key=lambda e: (e["source"], e["target"], e["type"]))
    clean = dict(data)
    clean["nodes"] = nodes_out
    clean["links"] = edges_out
    clean.pop("edges", None)  # canonicalize on the node-link `links` key
    return clean, issues


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a deterministic structural graph.json from a repo (tree-sitter-native "
                    "backbone; stdlib Python floor). Emits the node-link shape graph.py consumes.")
    parser.add_argument("root", nargs="?", default=".", help="repo root to graph (default: .)")
    parser.add_argument("-o", "--out", help="write graph.json here (default: stdout)")
    parser.add_argument("--commit", help="override built_at_commit (default: git HEAD of root)")
    parser.add_argument("--stats", action="store_true", help="print a node/edge summary to stderr")
    args = parser.parse_args(argv)

    data = build_graph(args.root, commit=args.commit)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text)
    if args.stats:
        import sys
        types: dict[str, int] = {}
        for n in data["nodes"]:
            types[n["type"]] = types.get(n["type"], 0) + 1
        etypes: dict[str, int] = {}
        for e in data["links"]:
            etypes[e["type"]] = etypes.get(e["type"], 0) + 1
        print(f"nodes={len(data['nodes'])} {types}  edges={len(data['links'])} {etypes}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
