"""Landing-zone readiness — is the ground solid enough to build the change on it?

This is a **premortem of the terrain**, and it is deliberately distinct from the challenger's
premortem of the *plan*: the challenger asks whether the elected oracle is sound, this asks whether
the code the change will land on can bear it at all. It runs when work *adds to* or *changes* a
living system — rescue's `align`, forge's `slice` on an existing tree, any add-feature intent.

The split this module holds to, per `core/trust-axes.md`:

    the ZONE and its EVIDENCE are D0 — graph reachability, git history, ledger state, all carriers;
    the VERDICT (ready / harden_first / redesign) is D2 — judgment over that evidence.

So this module computes facts and refuses to conclude. It returns the evidence bundle an agent reads
to form a verdict, and the ledger records the verdict as judgment, labeled as such. Manufacturing a
threshold here ("coupling > 0.6 means harden") would be the exact fake-determinism the trust-axes
doc exists to forbid — a number with no carrier wearing a green badge.

Two disciplines keep the gate from becoming an open-ended rewrite, and both are mechanical:

    blast-radius-scoped — evidence counts only what lies INSIDE the zone. A hotspot elsewhere is
                          not this change's problem and never enters the bundle.
    change-justified    — a pin may become a hardening prerequisite only if its own anchors land in
                          the zone. Enforced by the ledger, not by good intentions.

Stdlib-only. Reads the graph (`graph.Graph`), the ledger, and `git log`.
"""
from __future__ import annotations

import collections
import subprocess
from typing import Iterable, Optional

import cochange
import graph as graphmod

_DONE_STATES = ("resolved", "accepted")


def _run_git(args: list[str], repo: str) -> str:
    """git, or an empty string. A repo without history is a fact, never an exception."""
    try:
        out = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True,
                             timeout=30, check=False)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def zone_of(g: graphmod.Graph, anchors: Iterable[dict], max_depth: int = 2) -> dict:
    """The landing zone: the anchors' nodes plus what transitively depends on them.

    Reverse reachability, because "what breaks if this changes" is what the change must bear. An
    anchor whose `loc` the graph cannot resolve is reported as unresolved rather than dropped — a
    zone computed from half the anchors is not a smaller zone, it is an unknown one.
    """
    seeds, unresolved = [], []
    for a in anchors:
        nid = g.resolve(a) if not a.get("node_id") else str(a["node_id"])
        if nid and nid in g.nodes:
            seeds.append(nid)
        else:
            unresolved.append(a.get("loc") or a.get("node_id"))
    nodes = set(seeds)
    for nid in seeds:
        nodes.update(g.blast_radius(nid, max_depth=max_depth))
    files = sorted({f for nid in nodes if (f := g._node_file(g.nodes[nid]))})
    return {"seeds": sorted(seeds), "nodes": sorted(nodes), "files": files,
            "unresolved_anchors": unresolved}


def _open_pins_in_zone(ledger_data: dict, zone_files: set) -> list[dict]:
    """Unresolved pins whose anchors land inside the zone — the cheapest carrier there is.

    You are about to build on ground that the ledger already says is broken. No new signal needed:
    this is the package's own state read back at the moment it matters most.
    """
    # Through the guarded read, and ordered by the schema's own table (v0.23): this function kept a
    # third copy of the four severity pairs, and a copy is how the projection one module over came
    # to sort a pin with no severity ahead of a pin with an unrecognised one.
    from ledger import pin_read, read_collection, severity_rank
    out = []
    for p in read_collection(ledger_data, "pins"):
        if p.get("state") in _DONE_STATES:
            continue
        anchors = p.get("anchors")
        hits = [a for a in (anchors if isinstance(anchors, list) else [])
                if isinstance(a, dict) and (a.get("loc") or "").split(":")[0] in zone_files]
        if hits:
            read = pin_read(p)
            out.append({"pin": read["id"], "severity": p.get("severity"),
                        "kind": p.get("kind"), "state": read["state"],
                        "title": read["title"],
                        "anchors_in_zone": [a.get("loc") for a in hits]})
    return sorted(out, key=lambda x: (severity_rank(str(x["severity"] or "")), x["pin"]))


def _churn(repo: str, files: Iterable[str], since: str = "") -> dict:
    """Commits touching each zone file. `git log` is the carrier; no weighting, no score."""
    args = ["log", "--format=%H", "--name-only"]
    if since:
        args += [f"--since={since}"]
    log = _run_git(args, repo)
    if not log:
        return {}
    wanted = set(files)
    counts: dict[str, int] = collections.Counter()
    for line in log.splitlines():
        line = line.strip()
        if line and "/" in line or line in wanted:
            if line in wanted:
                counts[line] += 1
    return dict(counts)


def cochanged_outside(repo: str, files: Iterable[str],
                      min_commits: int = cochange.DEFAULT_MIN_COMMITS,
                      limit: int = cochange.DEFAULT_WINDOW) -> list[dict]:
    """Files that historically change WITH the zone but sit outside it.

    Delegates to `cochange.outside` — the same primitive the standalone omission check uses, because
    two implementations of "what moves together" would eventually disagree, and a package that hunts
    divergence cannot ship its own. This wrapper exists only to name the landing-zone reading of it.
    """
    return cochange.outside(repo, files, min_commits=min_commits, limit=limit)


def _test_files(g: graphmod.Graph) -> set:
    marks = ("test_", "_test.", ".test.", ".spec.", "/tests/", "/test/", "/spec/", "__tests__")
    return {f for nid in g.nodes if (f := g._node_file(g.nodes[nid]))
            and any(m in f.replace("\\", "/") for m in marks)}


def untested_in_zone(g: graphmod.Graph, zone_nodes: Iterable[str]) -> list[str]:
    """Zone files no test file depends on *directly*.

    Deterministic and deliberately coarse: it answers "does something under a test path import this
    file", not "is this well tested". Coverage percentages need a coverage run; this needs only the
    graph, so it is available at planning time — which is when the question is asked.

    Depth 1 on purpose. Transitive reach would call a file tested because a spec imports something
    that imports something that reaches it — in any connected graph that is nearly everything, so
    the signal would always read green and mean nothing. A direct edge is the claim that can be
    defended; anything looser is a comfortable number with no carrier behind it.
    """
    tests = _test_files(g)
    if not tests:
        return sorted({f for nid in zone_nodes if (f := g._node_file(g.nodes[nid]))})
    reached = set()
    for nid, node in g.nodes.items():
        f = g._node_file(node)
        if f in tests:
            for dep in g.dependencies(nid, max_depth=1):
                if (df := g._node_file(g.nodes[dep])):
                    reached.add(df)
    zone_files = {f for nid in zone_nodes if (f := g._node_file(g.nodes[nid]))}
    return sorted(zone_files - reached - tests)


class StaleGraph(RuntimeError):
    """The graph was built at another commit, so the zone it describes is not the zone you touch."""


def assess(graph_path: str, ledger_data: dict, anchors: list, repo: str = ".",
           max_depth: int = 2, head: Optional[str] = None) -> dict:
    """The D0 evidence bundle for one landing zone. Computes facts; states NO verdict.

    The caller (an agent) forms `ready` / `harden_first` / `redesign` from this and records it via
    the ledger, where it is stored as the D2 judgment it is.

    Refuses on a stale graph rather than degrading, for the same reason `blast_radius` does: the zone
    IS a blast radius, and one computed at another commit describes ground that has since moved. A
    readiness verdict is exactly the kind of answer that would be trusted, so a wrong one is worse
    than none.
    """
    g = graphmod.load(graph_path)
    if head and not g.is_current(head):
        raise StaleGraph(
            f"graph was built at {g.built_at_commit!r}, HEAD is {head!r} — rebuild it before "
            "assessing readiness; a zone from a stale graph is not the zone this change lands on"
        )
    zone = zone_of(g, anchors, max_depth=max_depth)
    zone_files = set(zone["files"])
    evidence = {
        "open_pins_in_zone": _open_pins_in_zone(ledger_data, zone_files),
        "untested_files": untested_in_zone(g, zone["nodes"]),
        "churn": _churn(repo, zone_files),
        "coupled_outside_zone": cochanged_outside(repo, zone_files),
    }
    return {
        "zone": zone,
        "evidence": evidence,
        "determinism": "D0",
        "built_at_commit": g.built_at_commit,
        "note": ("Evidence only — the verdict is judgment (D2) and belongs to the agent, then to "
                 "the human who elects what to do about it. A hotspot outside `zone.files` is "
                 "deliberately absent: this gate is scoped to what THIS change must bear."),
    }
