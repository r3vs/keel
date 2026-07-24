"""Co-change from git history — a second, independent carrier for this package's own thesis.

The field-shape engine finds cross-layer drift by comparing **declared structure**: the DB column,
the ORM field, the API schema, the client type. This module finds the same class of problem from a
completely different carrier — **recorded behaviour**, i.e. what this team has actually had to edit
together, commit after commit. Nobody wrote the coupling down; the history recorded it anyway.

Why bother when the shapes already work: because the two disagree in the interesting cases. Shapes
catch what is *declared* and miss coupling that lives in prose, config, fixtures, docs and
convention. History catches exactly that, and misses anything the team has not touched yet. So:

    two carriers agreeing is a strong finding;
    two carriers DISAGREEING is itself the finding.

That is why nothing here is ever merged into the shape signal or blended into a score.

**What it refuses to do.** It reports the frequencies and states no verdict. `min_commits` is a
declared, tunable **hypothesis** — not a discovered constant — and it is the only cutoff; the
ratio is reported, never thresholded. Ubiquity travels with every row so a lockfile that changes in
every commit can be discounted by the reader instead of being silently filtered by a rule nobody
can see. Renames are not followed (`git log --name-only` does not), so a renamed file reads as a
new one: a limitation, stated, not papered over.

Stdlib-only; the carrier is `git log`.
"""
from __future__ import annotations

import collections
import subprocess
from typing import Iterable

#: HYPOTHESIS, tunable — how many shared commits make a co-change worth reporting. Chosen because
#: two files land together once by coincidence routinely and three times rarely; it has no carrier
#: behind it and is labeled so rather than hidden as a constant (`core/trust-axes.md`).
DEFAULT_MIN_COMMITS = 3

#: HYPOTHESIS, tunable — how far back to read. A window, not a truth: coupling that ended two years
#: ago is history, not a signal about this change.
DEFAULT_WINDOW = 500


def _run_git(args: list[str], repo: str) -> str:
    """git, or an empty string. A repo without history is a fact, never an exception."""
    try:
        out = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True,
                             timeout=30, check=False)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def commits(repo: str, limit: int = DEFAULT_WINDOW) -> list[list[str]]:
    """The window as a list of file-sets, one per commit.

    `--no-merges` because a merge commit's file list is either empty or the union of both sides —
    in neither case is it evidence that a human edited those files together.
    """
    log = _run_git(["log", "--no-merges", f"-{limit}", "--format=%H", "--name-only"], repo)
    if not log:
        return []
    out: list[list[str]] = []
    current: list[str] = []
    for line in log.splitlines() + [""]:
        line = line.strip()
        if not line:
            if current:
                out.append(current)
            current = []
        elif "/" in line or "." in line:
            current.append(line.replace("\\", "/"))
    return out


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def outside(repo: str, files: Iterable[str], min_commits: int = DEFAULT_MIN_COMMITS,
            limit: int = DEFAULT_WINDOW) -> list[dict]:
    """Files that historically change WITH `files` but sit outside the set.

    The primitive both consumers share: the landing-zone gate asks it about a blast radius, the
    omission check asks it about a diff. One implementation, because two would drift.
    """
    window = commits(repo, limit)
    if not window:
        return []
    zone = {_norm(f) for f in files}
    pair: dict[str, int] = collections.Counter()
    own: dict[str, int] = collections.Counter()
    zone_commits = 0
    for touched in window:
        tset = {_norm(t) for t in touched}
        for f in tset:
            own[f] += 1
        if not (tset & zone):
            continue
        zone_commits += 1
        for f in tset - zone:
            pair[f] += 1
    rows = []
    for f, n in pair.items():
        if n < min_commits:
            continue
        rows.append({
            "file": f,
            "co_commits": n,
            # P(this file changed | the set changed). A conditional frequency read straight off the
            # carrier — not a weight, not a tuned score.
            "confidence": round(n / zone_commits, 3) if zone_commits else 0.0,
            # how often this file changes at all: a lockfile near 1.0 co-changes with everything and
            # means nothing. Reported so the reader discounts it; never filtered here.
            "ubiquity": round(own[f] / len(window), 3),
        })
    return sorted(rows, key=lambda r: (-r["confidence"], -r["co_commits"], r["file"]))


def omissions(repo: str, changed_files: Iterable[str],
              min_commits: int = DEFAULT_MIN_COMMITS,
              limit: int = DEFAULT_WINDOW) -> dict:
    """Files this diff *historically* would have touched and did not — the cross-layer omission.

    The archetype: an API handler changes and the client type that has moved with it fourteen times
    does not. The shape engine catches that only when both sides declare the shape; history catches
    it whenever the team has felt the coupling, declared or not.

    Candidates, never assertions. A deliberate omission is a perfectly good reason for a file to be
    absent, and this module cannot tell the two apart — which is exactly why the output is shaped as
    `contract_drift` *candidates* with `confidence: inferred`, in the same posture `docs_claims`
    already uses for dangling doc references.
    """
    changed = {_norm(f) for f in changed_files}
    rows = [r for r in outside(repo, changed, min_commits=min_commits, limit=limit)]
    return {
        "changed_files": sorted(changed),
        "candidates": [{
            "kind": "contract_mismatch",
            "failure_class": "contract_drift",
            "confidence": "inferred",
            "provenance": "cochange",
            "file": r["file"],
            "as_is": f"{r['file']} is absent from this diff",
            "evidence": (f"changed with this set in {r['co_commits']} of the last {limit} commits "
                         f"(P={r['confidence']}, this file's own change rate {r['ubiquity']})"),
            "question": f"`{r['file']}` has moved with these files {r['co_commits']} times and is "
                        "not in this change. Deliberate, or the other half of the edit?",
            **r,
        } for r in rows],
        "window": limit,
        "min_commits": min_commits,
        "determinism": "D0",
        "note": ("Frequencies only — no verdict. A deliberate omission looks identical to a "
                 "forgotten one from here, so these are candidates the agent judges and the human "
                 "elects. Renames are not followed; a renamed file reads as new."),
    }
