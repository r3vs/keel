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


def declared_vs_actual(pin: dict, changed_files: Iterable[str]) -> dict:
    """Did the change stay inside the boundary it declared? A set difference, post-execution.

    The declared boundary is not invented for this check: it is the landing zone the pin already
    recorded (`readiness.zone.files`, v0.8), falling back to the files its anchors name. So the
    executor is measured against a boundary a human saw and accepted, never against one this
    function made up afterwards.

    Two directions, and only one of them is a finding:

    - `outside_declared` — files edited that the boundary did not cover. Candidate `scope_creep`,
      in the shared failure vocabulary (`ledger.FAILURE_CLASSES`).
    - `declared_untouched` — boundary files never edited. **Not** a finding. A blast radius is what
      *could* be affected; touching less than all of it is the ladder working.

    Deterministic, and it states no verdict for the same reason the readiness evidence does not:
    a widened scope can be discipline failing or the zone having been wrong, and only a reader can
    tell those apart. When no boundary was ever declared it says so — an unchecked scope must never
    read as a clean one (`core/static-analysis.md`, the degrade rule).
    """
    actual = {_norm(f) for f in changed_files}
    zone = ((pin.get("readiness") or {}).get("zone") or {}).get("files") or []
    source = "readiness.zone"
    if not zone:
        zone = [(a.get("loc") or "").split(":")[0] for a in pin.get("anchors", [])]
        zone = [z for z in zone if z]
        source = "anchors"
    declared = {_norm(f) for f in zone}
    if not declared:
        return {
            "pin": pin.get("id"), "checked": False, "determinism": "D0",
            "why": "no landing zone and no anchors — this change declared no boundary, so there is "
                   "nothing to compare against. Unchecked is not clean.",
            "changed_files": sorted(actual),
        }
    outside_declared = sorted(actual - declared)
    return {
        "pin": pin.get("id"),
        "checked": True,
        "determinism": "D0",
        "declared_from": source,
        "declared": sorted(declared),
        "changed_files": sorted(actual),
        "outside_declared": outside_declared,
        "declared_untouched": sorted(declared - actual),
        "candidates": [{
            "failure_class": "scope_creep",
            "confidence": "extracted",
            "provenance": "blast_radius_declared_vs_actual",
            "files": outside_declared,
            "as_is": f"{len(outside_declared)} file(s) edited outside the declared boundary",
            "question": "Did the scope legitimately widen (re-declare the zone), or did the work "
                        "spread past what was approved?",
        }] if outside_declared else [],
        "note": "Touching less than the declared zone is not a finding — a blast radius is what "
                "COULD be affected, and the minimum-change ladder aims below it by design.",
    }


def load(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
