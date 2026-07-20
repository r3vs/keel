# GENERATED FILE - do not edit. Source: src/runtime/tours.py at the repo root;
# regenerate with: python scripts/build.py
"""Guided-tour generator — "learn this codebase in the right order", deterministically.

The `understand` mode's teaching surface. Given a structural `graph.json` (from `graph_build.py` or
any compatible producer), it computes a short, dependency-ordered walkthrough: start at the entry
points, follow imports outward, and group the reading order by architectural layer. Heuristic and
**LLM-free** — the same tree always yields the same tour; a semantic pass can later rename/narrate
the steps, but the order and membership are facts.

Why entry-point-first: a newcomer wants the top-level flow before the leaves. Entry points are files
nothing else imports (`in_degree == 0`) — CLIs, mains, servers — ranked by reach (`out_degree`) and
filename signal. A breadth-first walk from them assigns every file a depth = its distance from the
nearest entry, which is exactly "how deep into the machine you are". Steps are then grouped by layer
in first-reached order, so the tour reads outside-in.

Stdlib-only. Reads the node-link graph `graph.py` consumes; reuses `graph.Graph` for node access.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

import graph as graphmod

# Filename stems that signal a program entry point — a small, explicit, language-agnostic set.
_ENTRY_SIGNALS = frozenset({
    "main", "__main__", "index", "app", "server", "cli", "run", "start", "bootstrap",
    "manage", "wsgi", "asgi", "program", "entrypoint", "mod",
})


def _stem(path: str) -> str:
    name = path.replace("\\", "/").split("/")[-1]
    return name.rsplit(".", 1)[0].lower()


def _file_import_graph(data: dict) -> tuple[list[str], dict[str, set[str]], dict[str, set[str]]]:
    """(file ids, forward imports adjacency, reverse) over the `imports` edges only. File-level —
    a tour is an onboarding artifact, so it reads at file granularity, not symbol granularity."""
    files = sorted(n["id"] for n in data.get("nodes", []) if n.get("type") == "file")
    fileset = set(files)
    fwd: dict[str, set[str]] = {f: set() for f in files}
    rev: dict[str, set[str]] = {f: set() for f in files}
    edges = data.get("links")
    if edges is None:
        edges = data.get("edges") or []
    for e in edges:
        if str(e.get("type") or "").lower() != "imports":
            continue
        s, t = str(e.get("source")), str(e.get("target"))
        if s in fileset and t in fileset and s != t:
            fwd[s].add(t)
            rev[t].add(s)
    return files, fwd, rev


def _layer_of(node: dict) -> str:
    return str(node.get("layer") or "root")


def build_tour(data: dict, *, max_steps: int = 14, max_files_per_step: int = 12) -> dict:
    """A dependency-ordered tour of the graph → `{steps: [...], entry_points, stats}`.

    Each step is one architectural layer, in the order the layers are first reached from the entry
    points; its files are ranked most-depended-upon first (the things worth understanding first
    within a layer). Deterministic: every ordering has an explicit tie-break.
    """
    g = graphmod.Graph(data)
    files, fwd, rev = _file_import_graph(data)
    if not files:
        return {"steps": [], "entry_points": [], "stats": {"files": 0, "layers": 0}}

    in_deg = {f: len(rev[f]) for f in files}
    out_deg = {f: len(fwd[f]) for f in files}

    # entry points: nothing imports them; rank by (filename signal, reach, path). If the import graph
    # is empty or fully cyclic, fall back to the highest-reach files so the tour still has a start.
    roots = [f for f in files if in_deg[f] == 0]
    if not roots:
        roots = files[:]

    def _entry_key(f: str):
        node = g.nodes.get(f, {})
        signal = 1 if _stem(node.get("source_file") or f) in _ENTRY_SIGNALS else 0
        return (-signal, -out_deg[f], f)

    entry_points = sorted(roots, key=_entry_key)

    # multi-source BFS over imports → depth from the nearest entry point
    depth: dict[str, int] = {}
    frontier = list(entry_points)
    for f in frontier:
        depth[f] = 0
    d = 0
    while frontier:
        d += 1
        nxt = []
        for cur in frontier:
            for tgt in sorted(fwd.get(cur, ())):
                if tgt not in depth:
                    depth[tgt] = d
                    nxt.append(tgt)
        frontier = nxt
    # files unreachable from any entry point (disconnected) sort after, by layer/path
    unreached_depth = (max(depth.values()) + 1) if depth else 0
    for f in files:
        depth.setdefault(f, unreached_depth)

    # order files: depth, then layer, then most-depended-upon, then path
    ordered = sorted(files, key=lambda f: (depth[f], _layer_of(g.nodes.get(f, {})),
                                           -in_deg[f], f))

    # group into steps by layer, preserving first-appearance order
    steps: list[dict] = []
    layer_order: list[str] = []
    by_layer: dict[str, list[str]] = {}
    for f in ordered:
        lyr = _layer_of(g.nodes.get(f, {}))
        if lyr not in by_layer:
            by_layer[lyr] = []
            layer_order.append(lyr)
        by_layer[lyr].append(f)

    for i, lyr in enumerate(layer_order[:max_steps]):
        members = by_layer[lyr]
        ranked = sorted(members, key=lambda f: (-in_deg[f], depth[f], f))
        shown, extra = ranked[:max_files_per_step], max(0, len(ranked) - max_files_per_step)
        min_depth = min(depth[f] for f in members)
        why = (f"Reached at depth {min_depth} from the entry points; "
               f"{len(members)} file(s), most-depended-upon first"
               + (f" ({extra} more not shown)" if extra else "") + ".")
        steps.append({
            "order": i,
            "title": f"Layer: {lyr}",
            "layer": lyr,
            "node_ids": shown,
            "files": [g.nodes[f].get("source_file", f) for f in shown],
            "kind": "layer",
            "why": why,
        })

    return {
        "steps": steps,
        "entry_points": [g.nodes[f].get("source_file", f) for f in entry_points[:8]],
        "stats": {
            "files": len(files),
            "layers": len(layer_order),
            "steps": len(steps),
            "truncated_layers": max(0, len(layer_order) - max_steps),
        },
    }


def load(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _render_text(tour: dict) -> str:
    lines = [f"Guided tour — {tour['stats']['files']} files across "
             f"{tour['stats']['layers']} layers, {tour['stats']['steps']} steps.",
             f"Entry points: {', '.join(tour['entry_points']) or '(none detected)'}", ""]
    for s in tour["steps"]:
        lines.append(f"{s['order'] + 1}. {s['title']}  — {s['why']}")
        for fpath in s["files"]:
            lines.append(f"     - {fpath}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a dependency-ordered guided tour from a structural graph.json "
                    "(the understand-mode teaching surface). Heuristic, LLM-free, deterministic.")
    parser.add_argument("graph", help="path to graph.json (from scripts/runtime/graph_build.py)")
    parser.add_argument("--json", action="store_true", help="emit the tour as JSON (default: text)")
    parser.add_argument("--max-steps", type=int, default=14)
    args = parser.parse_args(argv)

    tour = build_tour(load(args.graph), max_steps=args.max_steps)
    if args.json:
        print(json.dumps(tour, ensure_ascii=False, indent=2))
    else:
        print(_render_text(tour), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
