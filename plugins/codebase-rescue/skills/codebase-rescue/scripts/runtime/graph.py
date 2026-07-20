# GENERATED FILE - do not edit. Source: src/runtime/graph.py at the repo root;
# regenerate with: python scripts/build.py
"""Graph anchoring + blast-radius over a graphify knowledge graph — deterministic, no heuristics.

The Phase-0 re-run (2026-07-14, `references/contract-reconciliation.md`) settled what the graph is
good for: the codebase's **structural spine** (files, symbols, tables as EXTRACTED nodes;
`imports`/`calls`/`references` as EXTRACTED edges), but **no field-level correspondence**. So this
module does exactly two things, both **deterministic facts read from the graph — never a guess**:

1. **Anchoring** — resolve a pin anchor to a stable `node_id` **only by its `file:line`**: an exact
   `(file, line)` match, or the node whose declared line-range contains that line. No name-matching,
   no singular/plural folding, no basename fuzzing, no nearest-line approximation. `node_id: null`
   stays always legitimate — a pin never blocks on graph coverage (the standalone-first verdict).
2. **Blast-radius** — "what depends on this node", by **reverse reachability over the graph's own
   EXTRACTED edges** (its deterministic confidence tag). It never rides an INFERRED/semantic edge
   (the Phase-0 lesson), and it applies **no editorial edge-type filter** — the caller may scope by
   type explicitly, but the default counts every EXTRACTED dependency the graph records.

Anti-staleness is enforced: `anchor_ledger` refuses to write when `built_at_commit` ≠ HEAD unless
forced (a graph behind HEAD is worse than none — the stale run's wrong verdict was the tuition).

Stdlib-only. Reads a plain NetworkX node-link `graph.json` (`nodes` + `links`, also tolerating an
`edges` key and assorted attribute spellings). Enrichment is written back onto the ledger's own
`anchors[]`, so the visual map stays a pure, self-contained projection — it needs the graph at
*anchor* time, never at *view* time.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterable, Optional

_CONF_RANK = {"extracted": 2, "inferred": 1, "ambiguous": 0}
_FILE_KEYS = ("source_file", "file", "file_path", "path", "filepath", "filename")
_LINE_KEYS = ("line", "start_line", "lineno", "start_row", "row")
_END_KEYS = ("end_line", "end_row", "endline")
_NAME_KEYS = ("name", "qualified_name", "qualname", "label", "symbol", "identifier")


def _norm_conf(v: object) -> str:
    return str(v if v is not None else "extracted").strip().lower() or "extracted"


def _norm_path(p: object) -> Optional[str]:
    return str(p).replace("\\", "/") if p not in (None, "") else None


def _parse_loc(loc: object) -> tuple[Optional[str], Optional[int]]:
    """`"path/to/f.ts:12"` / `"path:12:5"` / `{file,line}` / int → (file, line). Deterministic."""
    if loc is None:
        return None, None
    if isinstance(loc, dict):
        f = next((loc[k] for k in _FILE_KEYS if loc.get(k)), None)
        ln = next((loc[k] for k in _LINE_KEYS if isinstance(loc.get(k), int)), None)
        return _norm_path(f), ln
    if isinstance(loc, int):
        return None, loc
    # peel up to two trailing numeric segments (":line" or ":line:col"), keeping a Windows drive
    # letter's colon intact. With two, the FIRST is the line (the second is the column).
    segs = str(loc).split(":")
    trailing: list[int] = []
    while segs and segs[-1].isdigit() and len(trailing) < 2:
        trailing.insert(0, int(segs.pop()))
    file_part = ":".join(segs) or None
    return _norm_path(file_part), (trailing[0] if trailing else None)


def _same_commit(a: object, b: object) -> bool:
    """Git shas match if one is a prefix of the other (short vs full), min 7 chars."""
    if not a or not b:
        return False
    a, b = str(a).strip().lower(), str(b).strip().lower()
    n = min(len(a), len(b))
    return n >= 7 and a[:n] == b[:n]


class Graph:
    """A loaded graphify graph.json: nodes + edges, indexed for loc anchoring and blast-radius."""

    def __init__(self, data: dict):
        self.raw = data
        self.nodes: dict[str, dict] = {}
        for n in data.get("nodes", []):
            nid = n.get("id")
            if nid is not None:
                self.nodes[str(nid)] = n

        raw_edges = data.get("links")
        if raw_edges is None:
            raw_edges = data.get("edges") or []
        self.edges: list[tuple[str, str, str, str]] = []
        self._rev: dict[str, list[tuple[str, str, str]]] = {}
        self._fwd: dict[str, list[tuple[str, str, str]]] = {}
        for e in raw_edges:
            s, t = e.get("source"), e.get("target")
            if s is None or t is None:
                continue
            s, t = str(s), str(t)
            et = str(e.get("type") or e.get("label") or e.get("relation") or "").lower()
            conf = _norm_conf(e.get("confidence"))
            self.edges.append((s, t, et, conf))
            self._rev.setdefault(t, []).append((s, et, conf))
            self._fwd.setdefault(s, []).append((t, et, conf))

        # file → [node_id]  and  (file, line) → node_id, for deterministic loc anchoring
        self._by_file: dict[str, list[str]] = {}
        self._by_file_line: dict[tuple[str, int], str] = {}
        for nid, n in self.nodes.items():
            f = self._node_file(n)
            if not f:
                continue
            self._by_file.setdefault(f, []).append(nid)
            ln = self._node_line(n)
            if ln is not None:
                self._by_file_line.setdefault((f, ln), nid)

    # -- graph-level metadata ------------------------------------------------

    @property
    def built_at_commit(self) -> Optional[str]:
        g = self.raw.get("graph") or {}
        return g.get("built_at_commit") or self.raw.get("built_at_commit")

    def is_current(self, head: str) -> bool:
        return _same_commit(self.built_at_commit, head)

    # -- node attribute access (defensive: graphify's exact spelling varies) --

    @staticmethod
    def _first(n: dict, keys: Iterable[str]):
        for k in keys:
            v = n.get(k)
            if v not in (None, ""):
                return v
        return None

    def _node_file(self, n: dict) -> Optional[str]:
        f = self._first(n, _FILE_KEYS)
        if f:
            return _norm_path(f)
        f, _ = _parse_loc(n.get("source_location") or n.get("location"))
        return f

    def _node_line(self, n: dict) -> Optional[int]:
        v = self._first(n, _LINE_KEYS)
        if isinstance(v, int):
            return v
        _, ln = _parse_loc(n.get("source_location") or n.get("location"))
        return ln

    def _node_end_line(self, n: dict) -> Optional[int]:
        v = self._first(n, _END_KEYS)
        return v if isinstance(v, int) else None

    def _node_name(self, n: dict) -> Optional[str]:
        v = self._first(n, _NAME_KEYS)
        return str(v) if v is not None else None

    def node_loc(self, node_id: str) -> Optional[str]:
        n = self.nodes.get(str(node_id))
        if not n:
            return None
        f, ln = self._node_file(n), self._node_line(n)
        if f and ln is not None:
            return f"{f}:{ln}"
        return f or None

    def node_name(self, node_id: str) -> Optional[str]:
        n = self.nodes.get(str(node_id))
        return self._node_name(n) if n else None

    # -- resolution: anchor → node_id (deterministic, by file:line only) ------

    def resolve(self, anchor: dict) -> Optional[str]:
        """The node_id at the anchor's `file:line`, or None — never fabricated, never guessed.
        Exact `(file, line)` first; else the node whose declared line-range contains the line."""
        file_, line = _parse_loc(anchor.get("loc"))
        if not file_ or line is None:
            return None
        if (file_, line) in self._by_file_line:
            return self._by_file_line[(file_, line)]
        # containment: the (unique) node whose [start, end] range encloses the line. Deterministic
        # only when the graph carries end lines; no nearest-line approximation otherwise.
        for nid in self._by_file.get(file_, []):
            n = self.nodes[nid]
            start, end = self._node_line(n), self._node_end_line(n)
            if start is not None and end is not None and start <= line <= end:
                return nid
        return None

    # -- blast-radius: reverse reachability over EXTRACTED edges --------------

    def blast_radius(self, node_id: str, max_depth: int = 2,
                     edge_types: Optional[Iterable[str]] = None,
                     min_conf: str = "extracted") -> list[str]:
        """Node ids that (transitively) depend on `node_id` — "what breaks if I change this".

        Walks REVERSE edges (a `imports` b ⇒ changing b impacts a) up to `max_depth`, counting only
        edges at ≥ `min_conf`. Default: the graph's EXTRACTED edges, ALL types (no editorial
        edge-type filter — pass `edge_types` to scope). Breadth-first; each node reported once.
        """
        return self._reach(self._rev, node_id, max_depth, edge_types, min_conf)

    def dependencies(self, node_id: str, max_depth: int = 1,
                     edge_types: Optional[Iterable[str]] = None,
                     min_conf: str = "extracted") -> list[str]:
        """Forward twin of blast_radius: what `node_id` depends on."""
        return self._reach(self._fwd, node_id, max_depth, edge_types, min_conf)

    @staticmethod
    def _reach(adj, node_id, max_depth, edge_types, min_conf) -> list[str]:
        node_id = str(node_id)
        allow = set(edge_types) if edge_types is not None else None
        floor = _CONF_RANK.get(min_conf, 2)
        seen = {node_id}
        order: list[str] = []
        frontier = [node_id]
        for _ in range(max(0, max_depth)):
            nxt: list[str] = []
            for cur in frontier:
                for other, et, conf in adj.get(cur, []):
                    if allow is not None and et not in allow:
                        continue
                    if _CONF_RANK.get(conf, 0) < floor:
                        continue
                    if other in seen:
                        continue
                    seen.add(other)
                    order.append(other)
                    nxt.append(other)
            frontier = nxt
            if not frontier:
                break
        return order


def load(path: str | pathlib.Path) -> Graph:
    return Graph(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))


def anchor_ledger(ledger_data: dict, graph: Graph, head: Optional[str] = None,
                  max_depth: int = 2, sample: int = 5, force: bool = False) -> dict:
    """Enrich a ledger's pin anchors from the graph, in place. For each anchor: fill `node_id`
    (only when currently null — never overwrite; only from an exact/containment `file:line` match),
    fill `loc` if the node knows it, and attach a compact `blast_radius` summary so the map stays
    self-contained. Returns a report.

    Staleness gate (consequence #3 of the Phase-0 verdict): if `head` is given and the graph's
    `built_at_commit` ≠ HEAD, refuse to write anything (a stale graph is worse than none) unless
    `force=True`. The report's `stale`/`skipped_stale` say what happened.
    """
    report = {
        "anchors_total": 0, "resolved": 0, "already": 0, "unresolved": 0,
        "with_blast_radius": 0, "built_at_commit": graph.built_at_commit,
        "head": head, "stale": None, "skipped_stale": False,
    }
    if head is not None:
        report["stale"] = not graph.is_current(head)
        if report["stale"] and not force:
            report["skipped_stale"] = True
            return report

    for pin in ledger_data.get("pins", []):
        for a in pin.get("anchors", []):
            report["anchors_total"] += 1
            nid = str(a["node_id"]) if a.get("node_id") else None
            if nid:
                report["already"] += 1
            else:
                nid = graph.resolve(a)
                if not nid:
                    report["unresolved"] += 1
                    continue
                a["node_id"] = nid
                report["resolved"] += 1
            if not a.get("loc"):
                loc = graph.node_loc(nid)
                if loc:
                    a["loc"] = loc
            radius = graph.blast_radius(nid, max_depth=max_depth)
            if radius:
                a["blast_radius"] = {
                    "count": len(radius),
                    "sample": [graph.node_loc(x) or graph.node_name(x) or x
                               for x in radius[:sample]],
                    "depth": max_depth,
                    "edges": "extracted",
                }
                report["with_blast_radius"] += 1
    return report


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Anchor a ledger's pins to graphify graph nodes (by file:line) + blast-radius")
    parser.add_argument("--graph", required=True, help="path to graphify graph.json")
    parser.add_argument("--ledger", required=True, help="path to ledger.json (enriched in place)")
    parser.add_argument("--head", help="HEAD sha to enforce built_at_commit==HEAD (anti-staleness)")
    parser.add_argument("--depth", type=int, default=2, help="blast-radius BFS depth")
    parser.add_argument("--force", action="store_true",
                        help="anchor even if the graph is stale (NOT recommended)")
    parser.add_argument("--dry-run", action="store_true", help="report only; do not write")
    args = parser.parse_args(argv)

    graph = load(args.graph)
    ledger_path = pathlib.Path(args.ledger)
    ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
    report = anchor_ledger(ledger_data, graph, head=args.head,
                           max_depth=args.depth, force=args.force)

    if report["skipped_stale"]:
        print(f"REFUSED: graph built_at_commit={report['built_at_commit']!r} != HEAD "
              f"{args.head!r} — rebuild it (`graphify update <path>`) or pass --force. "
              f"A stale graph is worse than none.")
        return 2
    if not args.dry_run and (report["resolved"] or report["with_blast_radius"]):
        ledger_path.write_text(json.dumps(ledger_data, ensure_ascii=False, indent=2),
                               encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
