#!/usr/bin/env python3
"""Point this repo's runtime at a real public codebase and record what it actually finds.

`docs/measurements.md` is the output of this script, and this script exists so that document can
be re-derived rather than believed. Every number there names the command that produced it; this
is that command.

What it runs is the runtime itself — the same functions the MCP tools call, imported directly:

  * comprehension — `graph_build.build_graph` → `understand.overview` → `tours.build_tour`
    (rescue's `understand` mode; `mcp:understand_repo`), timed.
  * cross-layer   — `shapes.reconcile_layers` (rescue's contract-reconciliation, carrier-less
    path; `mcp:reconcile_layers`), plus `shapes.propose_correspondence` when the two layers do
    not share a naming convention.

Two rules it follows, because a measurement that breaks either is advertising:

  **Nothing is filtered.** Every finding the runtime emits is counted, including the ones that
  turn out to be the runtime's own false-positive classes. A tool's error rate is a measurement
  of the tool; removing it from the tool's own report is the one edit that makes the number
  meaningless.

  **A null result is a result.** A layer that extracts zero entities is recorded as zero, with
  the reason found by reading the extractor rather than guessed — `reconcile` reports the entity
  counts of both sides precisely so an empty diff cannot be mistaken for a clean one.

Usage (paths are relative to --repo):

    python scripts/measure_public.py --repo /tmp/keystone --label keystonejs/keystone \\
        --comprehension \\
        --pair-dirs 'examples/*' --a prisma=schema.prisma --b graphql=schema.graphql \\
        --out /tmp/keystone.json

Stdlib-only apart from the runtime it measures.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "runtime"))

import graph_build          # noqa: E402
import shapes               # noqa: E402
import tours                # noqa: E402
import understand           # noqa: E402


def head(repo: pathlib.Path) -> str | None:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo),
                         capture_output=True, text=True)
    return out.stdout.strip() or None if out.returncode == 0 else None


def comprehension(repo: pathlib.Path) -> dict:
    """`understand` mode, split into its three timed stages so the cost is attributable. Reported
    separately because the graph build dominates and a single total would hide that."""
    t0 = time.monotonic()
    graph = graph_build.build_graph(repo)
    t1 = time.monotonic()
    view = understand.overview(graph)
    t2 = time.monotonic()
    tour = tours.build_tour(graph)
    t3 = time.monotonic()
    return {
        "seconds": {"build_graph": round(t1 - t0, 2), "overview": round(t2 - t1, 2),
                    "tour": round(t3 - t2, 2), "total": round(t3 - t0, 2)},
        "files": view["files"], "symbols": view["symbols"], "edges": view["edges"],
        "languages": view["languages"],
        "layers": dict(list(view["layers"].items())[:12]),
        "hotspots": [{"name": h["name"], "dependents": h["dependents"]}
                     for h in view["hotspots"][:5]],
        "tour_steps": tour["stats"]["steps"], "entry_points": tour["entry_points"][:5],
    }


def reconcile_one(a_layer: str, a_path: pathlib.Path, b_layer: str, b_path: pathlib.Path,
                  propose: bool, examples: int) -> dict:
    """One layer pair. Entity counts are reported for BOTH sides whatever the finding count is:
    an empty diff over two empty extractions is the failure mode most easily read as a success."""
    t0 = time.monotonic()
    try:
        a = shapes.EXTRACTORS[a_layer](str(a_path))
        b = shapes.EXTRACTORS[b_layer](str(b_path))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    correspondence = None
    proposals = []
    if propose:
        proposals = shapes.propose_correspondence(a_layer, str(a_path), b_layer, str(b_path))
        # Electing the proposals is normally the HUMAN's move (`core/shape-engine.md`); doing it
        # here is a stated condition of the measurement, not a claim that the tool decided.
        correspondence = {p["a"]: p["b"] for p in proposals if not p["name_match"]}
    findings = shapes.reconcile_layers(a_layer, str(a_path), b_layer, str(b_path),
                                       correspondence=correspondence)
    seconds = time.monotonic() - t0
    by_kind = collections.Counter(f["kind"] for f in findings)
    return {
        "seconds": round(seconds, 2),
        "entities": {a_layer: len(a), b_layer: len(b)},
        "fields": {a_layer: sum(len(v) for v in a.values()),
                   b_layer: sum(len(v) for v in b.values())},
        "findings": len(findings),
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: (-kv[1], kv[0]))),
        "elected_correspondence": correspondence or None,
        "proposals": len(proposals),
        "examples": [{"entity": f["entity"], "field": f["field"], "kind": f["kind"],
                      "detail": f["detail"]} for f in findings[:examples]],
    }


def parse_layer(spec: str) -> tuple[str, str]:
    layer, _, path = spec.partition("=")
    if layer not in shapes.EXTRACTORS:
        raise SystemExit(f"unknown layer {layer!r}; known: {sorted(shapes.EXTRACTORS)}")
    return layer, path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="path to a checkout of the target repo")
    ap.add_argument("--label", default="", help="owner/repo, for the report header")
    ap.add_argument("--comprehension", action="store_true", help="run graph_build + overview + tour")
    ap.add_argument("--a", default="", help="layer=relpath for side A (e.g. prisma=schema.prisma)")
    ap.add_argument("--b", default="", help="layer=relpath for side B")
    ap.add_argument("--pair-dirs", default="",
                    help="glob of directories, each expected to hold BOTH --a and --b relpaths; "
                         "one reconcile per directory")
    ap.add_argument("--propose", action="store_true",
                    help="elect propose_correspondence's top pairing per entity before diffing. "
                         "Normally the human's move — recorded in the output as a condition")
    ap.add_argument("--examples", type=int, default=6, help="concrete findings to carry per pair")
    ap.add_argument("--out", default="", help="write the JSON report here (default: stdout)")
    args = ap.parse_args()

    repo = pathlib.Path(args.repo).resolve()
    if not repo.is_dir():
        raise SystemExit(f"--repo {repo} is not a directory")

    report: dict = {"label": args.label or repo.name, "repo_path": str(repo),
                    "commit": head(repo), "measured_at": time.strftime("%Y-%m-%d"),
                    "runtime_commit": head(ROOT)}
    if args.comprehension:
        report["comprehension"] = comprehension(repo)

    if args.a and args.b:
        a_layer, a_rel = parse_layer(args.a)
        b_layer, b_rel = parse_layer(args.b)
        pairs = []
        if args.pair_dirs:
            for directory in sorted(repo.glob(args.pair_dirs)):
                if (directory / a_rel).is_file() and (directory / b_rel).is_file():
                    pairs.append((directory / a_rel, directory / b_rel))
        else:
            pairs.append((repo / a_rel, repo / b_rel))
        report["reconcile"] = []
        for a_path, b_path in pairs:
            entry = reconcile_one(a_layer, a_path, b_layer, b_path, args.propose, args.examples)
            entry["a"] = str(a_path.relative_to(repo))
            entry["b"] = str(b_path.relative_to(repo))
            report["reconcile"].append(entry)
        ok = [e for e in report["reconcile"] if "error" not in e]
        totals = collections.Counter()
        for entry in ok:
            totals.update(entry["by_kind"])
        report["reconcile_totals"] = {
            "pairs": len(report["reconcile"]), "pairs_ok": len(ok),
            "findings": sum(e["findings"] for e in ok),
            "seconds": round(sum(e["seconds"] for e in ok), 2),
            "by_kind": dict(sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))),
        }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"measure_public: wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
