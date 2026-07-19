# GENERATED FILE - do not edit. Source: src/runtime/query.py at the repo root;
# regenerate with: python scripts/build.py
"""Query surface over the structural graph — "which parts handle auth?", answered from the graph.

The `understand` mode's ask-anything surface, and equally a way to pull the neighborhood of a pin.
Instead of dumping files into context, it retrieves a small, relevant subgraph: rank nodes by a
weighted token match over their name / tags / summary / path / layer, then expand one hop over the
edges so the answer carries the matched node *and what it connects to*.

Deterministic and LLM-free (an agent reasons over the returned subgraph; the retrieval itself is a
pure function of the graph). Stdlib-only; reuses `graph.Graph` for node + edge access.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

import graph as graphmod

# Field weights, in the spirit of a weighted fuzzy index: a name hit outranks a summary hit, which
# outranks a path hit. Tuned to be legible, not magical.
_WEIGHTS = {"name": 4.0, "tags": 3.0, "summary": 2.0, "source_file": 2.0, "layer": 1.0}
_TYPE_RANK = {"file": 0, "class": 1, "function": 2, "method": 3}


def _tokens(q: str) -> list[str]:
    return [t for t in "".join(c.lower() if (c.isalnum() or c == "_") else " " for c in q).split() if t]


def _field_text(node: dict, field: str) -> str:
    v = node.get(field)
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v).lower()
    return str(v).lower()


def _score(node: dict, tokens: list[str]) -> float:
    """Sum of field weights for each query token that appears in that field. A token counts once
    per field (no runaway from repetition), so the score is bounded and comparable across nodes."""
    total = 0.0
    for field, weight in _WEIGHTS.items():
        text = _field_text(node, field)
        if not text:
            continue
        for tok in tokens:
            if tok in text:
                total += weight
    return total


def search(data: dict, query: str, *, limit: int = 10, expand: bool = True) -> dict:
    """Rank nodes against `query`; optionally attach each hit's 1-hop neighborhood.

    Returns `{query, results: [{id, name, type, loc, layer, score, neighbors?}], total_matched}`.
    Results are sorted by score desc, then a stable (type, id) tie-break — so equal-score hits do
    not reorder run to run.
    """
    tokens = _tokens(query)
    g = graphmod.Graph(data)
    if not tokens:
        return {"query": query, "results": [], "total_matched": 0}

    scored = []
    for nid, node in g.nodes.items():
        s = _score(node, tokens)
        if s > 0:
            scored.append((s, nid, node))
    scored.sort(key=lambda r: (-r[0], _TYPE_RANK.get(r[2].get("type"), 9), r[1]))

    results = []
    for s, nid, node in scored[:limit]:
        entry = {
            "id": nid,
            "name": node.get("name") or nid,
            "type": node.get("type"),
            "loc": g.node_loc(nid),
            "layer": node.get("layer"),
            "score": round(s, 2),
        }
        if expand:
            deps = g.dependencies(nid, max_depth=1)
            dependents = g.blast_radius(nid, max_depth=1)
            entry["neighbors"] = {
                "depends_on": [g.node_loc(x) or g.node_name(x) or x for x in deps[:8]],
                "depended_on_by": [g.node_loc(x) or g.node_name(x) or x for x in dependents[:8]],
            }
        results.append(entry)

    return {"query": query, "results": results, "total_matched": len(scored)}


def load(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _render_text(res: dict) -> str:
    lines = [f"Query: {res['query']!r} — {res['total_matched']} match(es)", ""]
    if not res["results"]:
        lines.append("  (no nodes matched)")
    for i, r in enumerate(res["results"], 1):
        loc = f"  [{r['loc']}]" if r.get("loc") else ""
        lines.append(f"{i}. ({r['type']}) {r['name']}  score={r['score']}{loc}")
        nb = r.get("neighbors")
        if nb:
            if nb["depends_on"]:
                lines.append(f"     depends on: {', '.join(nb['depends_on'])}")
            if nb["depended_on_by"]:
                lines.append(f"     used by:    {', '.join(nb['depended_on_by'])}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Query a structural graph.json by meaning-ish keywords → a ranked, 1-hop-"
                    "expanded subgraph (the understand-mode query surface). Deterministic.")
    parser.add_argument("graph", help="path to graph.json")
    parser.add_argument("query", help="what to look for, e.g. \"auth login\"")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--no-expand", action="store_true", help="do not attach neighborhoods")
    parser.add_argument("--json", action="store_true", help="emit JSON (default: text)")
    args = parser.parse_args(argv)

    res = search(load(args.graph), args.query, limit=args.limit, expand=not args.no_expand)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(_render_text(res), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
