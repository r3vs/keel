"""Diff/impact overlay — what a change touches, before you commit (study item C2).

Maps a set of changed files onto the structural graph and computes: the **changed** nodes, the
**affected** nodes (what depends on them, by reverse reachability over the EXTRACTED spine), the
**affected layers**, and the **unmapped** files — files in the diff that the graph has no node for,
i.e. new/renamed code that needs re-analysis before anyone trusts an "impact = 0" answer.

Two uses, both from the study: Phase-3 sequences and risk-rates the roadmap by blast radius, and
Phase-5 confirms a fix reached only its intended nodes (an unexpected node in the affected set is a
regression signal; an unmapped file is un-audited surface). The output is a `diff-overlay.json`
sidecar the map renders (`{changed_node_ids, affected_node_ids}`), so affected pins highlight.

Deterministic; reuses `graph.Graph` for reverse reachability. Stdlib-only.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
from typing import Iterable, Optional

import graph as graphmod


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def changed_files_from_git(root: str | pathlib.Path, base: str) -> list[str]:
    """`git diff --name-only <base> -- .` scoped to the project (the `-- .` keeps a monorepo's
    sibling commits from falsely invalidating), or [] outside git. Deterministic given the repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", base, "--", "."],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0:
            return []
        return sorted(_norm(line) for line in out.stdout.splitlines() if line.strip())
    except (OSError, subprocess.SubprocessError):
        return []


def overlay(data: dict, changed_files: Iterable[str], *, depth: int = 1) -> dict:
    """Compute the impact overlay for `changed_files` over the graph `data`.

    Returns `{changed_files, changed_node_ids, affected_node_ids, affected_layers, unmapped_files,
    risk}`. `affected` is the reverse-reachable set (dependents) at `depth`, minus the changed set.
    """
    g = graphmod.Graph(data)
    changed = {_norm(f) for f in changed_files}

    # file → its node ids (file node + every symbol declared in it)
    files_with_nodes: set[str] = set()
    changed_ids: set[str] = set()
    for nid, node in g.nodes.items():
        sf = node.get("source_file")
        if not sf:
            continue
        sf = _norm(str(sf))
        files_with_nodes.add(sf)
        if sf in changed:
            changed_ids.add(nid)

    affected: set[str] = set()
    for nid in changed_ids:
        for dep in g.blast_radius(nid, max_depth=depth):
            if dep not in changed_ids:
                affected.add(dep)

    def _layer(nid: str) -> Optional[str]:
        return (g.nodes.get(nid) or {}).get("layer")

    affected_layers = sorted({l for nid in (changed_ids | affected) if (l := _layer(nid))})
    unmapped = sorted(f for f in changed if f not in files_with_nodes)

    reasons = []
    if len(affected_layers) > 1:
        reasons.append(f"cross-layer: touches {len(affected_layers)} layers")
    if len(affected) > 5:
        reasons.append(f"wide blast radius: {len(affected)} affected nodes")
    if unmapped:
        reasons.append(f"{len(unmapped)} unmapped file(s) — new/renamed, need re-analysis")
    level = "high" if (unmapped or len(affected_layers) > 1) else ("medium" if affected else "low")

    return {
        "changed_files": sorted(changed),
        "changed_node_ids": sorted(changed_ids),
        "affected_node_ids": sorted(affected),
        "affected_layers": affected_layers,
        "unmapped_files": unmapped,
        "risk": {"level": level, "reasons": reasons},
    }


def load(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
