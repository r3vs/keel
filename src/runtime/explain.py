"""Explain-a-node drill-down — the `understand` mode's deep-dive on one file or symbol.

The pattern the study lifts from Understand-Anything's `explain`: assemble the node's *graph
neighborhood* — what it contains, what it depends on, what depends on it, which layer it lives in —
**and then read the real source** at its location for ground truth, against a fixed checklist. The
graph gives the map; the source gives the detail. The runtime assembles this context deterministically;
an agent narrates the five points. No fabrication: a target that does not resolve says so.

Stdlib-only; reuses `graph.Graph` for node access, adjacency, and blast-radius.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

import graph as graphmod

_CHECKLIST = [
    "Purpose — what this exists to do, in one or two sentences.",
    "Data flow — what goes in, what comes out, what it reads/writes.",
    "Interactions — who calls it and what it calls (see the neighborhood below).",
    "Patterns — the idioms/abstractions it uses (and why).",
    "Gotchas — the non-obvious constraints, edge cases, or foot-guns.",
]
_MAX_SOURCE_LINES = 80


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def resolve_target(g: graphmod.Graph, target: str) -> Optional[str]:
    """Resolve `target` to a node id, or None (never a guess). Accepts, in order:
    an exact node id · `path:symbol` · a bare `path` (its file node). A `path:symbol` matches a
    symbol whose file is `path` (exact, else a unique path-suffix) and whose name is/ends with
    `symbol`; ties break to the earliest line so the result is stable."""
    if "://" in target:  # a URL is never a node
        return None
    if target in g.nodes:
        return target

    path, _, symbol = target.partition(":")
    path = _norm(path)

    def _file_matches(node: dict) -> bool:
        sf = _norm(str(node.get("source_file") or ""))
        return bool(sf) and (sf == path or sf.endswith("/" + path) or sf == path.lstrip("/"))

    if symbol:
        cands = []
        for nid, node in g.nodes.items():
            if node.get("type") in ("file",):
                continue
            if not _file_matches(node):
                continue
            name = str(node.get("name") or "")
            if name == symbol or name.endswith("." + symbol) or name.split(".")[-1] == symbol:
                cands.append((node.get("start_line") or 0, nid))
        if cands:
            return sorted(cands)[0][1]
        return None

    # bare path → the file node (exact source_file, else unique suffix)
    file_hits = [nid for nid, node in g.nodes.items()
                 if node.get("type") == "file" and _file_matches(node)]
    return sorted(file_hits)[0] if file_hits else None


def _read_source(root: Optional[str], node: dict) -> Optional[dict]:
    if not root:
        return None
    sf = node.get("source_file")
    start = node.get("start_line")
    if not sf or not isinstance(start, int):
        return None
    fp = pathlib.Path(root) / sf
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    end = node.get("end_line")
    end = end if isinstance(end, int) and end >= start else min(len(lines), start + 40)
    end = min(end, start + _MAX_SOURCE_LINES - 1, len(lines))
    excerpt = lines[start - 1:end]
    return {"file": sf, "start_line": start, "end_line": end,
            "truncated": (node.get("end_line") or end) > end,
            "text": "\n".join(excerpt)}


def explain(data: dict, target: str, *, root: Optional[str] = None) -> dict:
    """Assemble the explain context for `target` → a dict the agent narrates against the checklist.
    `{found, target, node, neighborhood{contains, depends_on, depended_on_by}, source?, checklist}`."""
    g = graphmod.Graph(data)
    nid = resolve_target(g, target)
    if nid is None:
        return {"found": False, "target": target,
                "message": f"no node resolved for {target!r} — try an exact path, path:symbol, "
                           f"or a node id from the query surface.",
                "checklist": _CHECKLIST}
    node = g.nodes[nid]
    contains = g.dependencies(nid, max_depth=1, edge_types=["contains"])
    depends = g.dependencies(nid, max_depth=1, edge_types=["imports", "calls", "references"])
    dependents = g.blast_radius(nid, max_depth=1)

    def _label(x: str) -> str:
        return g.node_name(x) or g.node_loc(x) or x

    return {
        "found": True,
        "target": target,
        "node": {
            "id": nid, "name": node.get("name"), "type": node.get("type"),
            "loc": g.node_loc(nid), "layer": node.get("layer"),
            "language": node.get("language"),
        },
        "neighborhood": {
            "contains": [_label(x) for x in contains[:20]],
            "depends_on": [g.node_loc(x) or _label(x) for x in depends[:15]],
            "depended_on_by": [g.node_loc(x) or _label(x) for x in dependents[:15]],
        },
        "source": _read_source(root, node),
        "checklist": _CHECKLIST,
    }


def load(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _render_text(ctx: dict) -> str:
    if not ctx.get("found"):
        return ctx.get("message", "not found") + "\n"
    n = ctx["node"]
    nb = ctx["neighborhood"]
    out = [f"Explain: {n['name']}  ({n['type']}, layer={n['layer']})"
           + (f"  [{n['loc']}]" if n.get("loc") else ""), ""]
    if nb["contains"]:
        out.append("Contains: " + ", ".join(nb["contains"]))
    if nb["depends_on"]:
        out.append("Depends on: " + ", ".join(nb["depends_on"]))
    if nb["depended_on_by"]:
        out.append("Depended on by: " + ", ".join(nb["depended_on_by"]))
    src = ctx.get("source")
    if src:
        out += ["", f"Source {src['file']}:{src['start_line']}-{src['end_line']}"
                + (" (truncated)" if src["truncated"] else ""), "```", src["text"], "```"]
    out += ["", "Explain against this checklist:"]
    out += [f"  {i + 1}. {c}" for i, c in enumerate(ctx["checklist"])]
    return "\n".join(out) + "\n"
