"""Learning with a carrier — you do not store the belief, you store the check the belief implies.

Every "continuous learning" design this package has looked at fails the same way, and it is worth
naming precisely because the failure is seductive: it stores a **belief** with a **confidence
number**, raises the number when nobody objects, and starts auto-applying above a threshold. Three
things are wrong at once. The confidence has no carrier. Absence of correction is treated as
evidence of correctness. And the loop certifies itself, because the sessions that validate an
instinct are running *under* that instinct.

The alternative here is smaller and survives contact:

    capture      divergence events already in the ledger              D0 — read, not inferred
    propose      a rule from a cluster of them                        D2 — an agent, labeled
    GRADUATE     express it as something CHECKABLE, or it stays inert D0 — this module
    elect        the human, in the interview                          the only authority

**Graduation is the piece nobody else does.** A candidate rule is promoted only if it can be written
as an ast-grep matcher, a shape rule, a lint rule, a `flip_criteria` predicate, or a test. A rule
that cannot be expressed that way is not thereby wrong — it stays a *proposal*: visible on the map,
attached to its evidence, and **never applied**. That is the whole trade:

    you do not memorize the belief, you memorize the check the belief implies.

And demotion becomes honest for free. A graduated rule *is* a generator, so it lives or dies by the
measured false-positive rate in `generators.py` — not by a confidence counter drifting downward.

**The signals are rare, human and adversarially verified**, which is exactly why they are worth more
than "five observed instances": the gap between what the brainstorm recommended and what the human
elected, challenges that were upheld, failures that were labeled, decisions production reopened.
Each one is a moment where a considered judgment was overruled by something. Nothing here observes
the operator's keystrokes, and nothing counts silence.

Honest cost, stated up front: **this learns far less.** The alternative learns more, and learns
wrong things confidently.

Stdlib-only. Reads the ledger; writes nothing.
"""
from __future__ import annotations

from typing import Optional

#: The forms a candidate rule may graduate INTO. Each is something a machine can run and a human can
#: read; nothing here is a stored opinion. The list is closed on purpose — an open one would quietly
#: grow a "note" member, and a note is a belief with extra steps.
CARRIER_KINDS = ("ast_grep", "shape_rule", "lint_rule", "flip_predicate", "test")


def divergences(ledger) -> dict:
    """Every recorded moment where a considered judgment was overruled. Pure D0 — a read.

    Four sources, all already persisted, none of them new instrumentation:

    - **brainstorm vs election** — the single best signal in the ledger and nobody was reading it.
      An agent proposed, marked one option `recommended`, and the human elected a different one.
      That gap is the model's blind spot, recorded by the one authority that can see it.
    - **upheld challenges** — an oracle that survived the interview and did not survive refutation.
    - **labeled failures** — what actually went wrong, in the shared vocabulary.
    - **reopens** — production falsifying a decision that looked sound.
    """
    out = {"brainstorm_vs_election": [], "upheld_challenges": [], "failures": [], "reopens": [],
           "unmatched_elections": [], "determinism": "D0"}
    events = ledger.data["decision_log"]
    for pin in ledger.data["pins"]:
        proposals = ((pin.get("brainstorm") or {}).get("proposals")) or []
        recommended = next((p for p in proposals if p.get("recommended")), None)
        decision = pin.get("decision")
        if recommended and decision:
            outcome = str(decision.get("outcome", ""))
            ids = {str(p.get("id")) for p in proposals}
            if outcome not in ids:
                # The election did not name a proposal, so agreement cannot be decided. Reporting
                # this as "no divergence" would silently inflate the model's apparent hit rate.
                out["unmatched_elections"].append({"pin": pin["id"], "outcome": outcome})
            elif outcome != str(recommended.get("id")):
                out["brainstorm_vs_election"].append({
                    "pin": pin["id"], "title": pin.get("title"),
                    "recommended": recommended.get("id"),
                    "recommended_summary": recommended.get("summary"),
                    "elected": outcome,
                    "elected_summary": next((p.get("summary") for p in proposals
                                             if str(p.get("id")) == outcome), None),
                })
    for e in events:
        if e["id"].startswith("chl_") and e.get("upheld"):
            out["upheld_challenges"].append({"pin": e["pin_id"], "class": e["class"],
                                             "argument": e.get("argument")})
        elif e["id"].startswith("fal_"):
            out["failures"].append({"pin": e["pin_id"], "class": e["class"],
                                    "phase": e.get("phase"), "detail": e.get("detail")})
        elif e["id"].startswith("rev_"):
            out["reopens"].append({"pin": e["pin_id"], "fired": e.get("fired"),
                                   "reason": e.get("reason")})
    out["total"] = sum(len(out[k]) for k in
                       ("brainstorm_vs_election", "upheld_challenges", "failures", "reopens"))
    return out


def clusters(div: dict, min_size: int = 2) -> list[dict]:
    """Group divergences by the only key that is already a closed vocabulary — the failure class.

    Deliberately crude. Clustering prose by similarity is the judgment half of this pipeline and
    belongs to the agent; grouping by an enum somebody already assigned is the deterministic half.
    A cluster is *material for* a proposal, never a proposal.
    """
    by_class: dict[str, list] = {}
    for f in div.get("failures", []):
        by_class.setdefault(f["class"], []).append(f)
    for c in div.get("upheld_challenges", []):
        by_class.setdefault(c["class"], []).append(c)
    return [{"class": k, "size": len(v), "members": v}
            for k, v in sorted(by_class.items(), key=lambda kv: (-len(kv[1]), kv[0]))
            if len(v) >= min_size]


def graduate(candidate: dict) -> dict:
    """Can this candidate rule become a check? `{graduated, carrier|reason}` — the gate itself.

    A candidate needs a `carrier` of a known kind and a non-empty `expression` a machine can run.
    Failing that it is **not rejected as wrong** — it is returned as a standing proposal, which is
    the honest destination for a belief nobody can check. The distinction matters: rejecting it
    would throw away a real observation, while promoting it would give an opinion the authority of
    a rule.
    """
    carrier = (candidate or {}).get("carrier") or {}
    kind = carrier.get("kind")
    expression = str(carrier.get("expression", "")).strip()
    evidence = candidate.get("evidence") or []
    if not evidence:
        return {"graduated": False, "state": "rejected",
                "reason": "a candidate rule with no divergence events behind it is an opinion, "
                          "not a lesson — cite the pins it came from"}
    if kind not in CARRIER_KINDS:
        return {"graduated": False, "state": "proposal",
                "reason": f"no carrier: a rule must be expressible as one of {CARRIER_KINDS} to be "
                          "applied. It stays visible and attached to its evidence, and is never "
                          "enforced — you memorize the check a belief implies, not the belief"}
    if not expression:
        return {"graduated": False, "state": "proposal",
                "reason": f"carrier kind {kind!r} named with no expression to run — a carrier that "
                          "cannot execute is a label"}
    return {
        "graduated": True,
        "state": "check",
        "carrier": {"kind": kind, "expression": expression},
        "generator": candidate.get("generator") or f"learned:{kind}:{candidate.get('id', 'rule')}",
        "determinism": "D0",
        "note": ("Graduated rules are generators, so they are governed by the measured "
                 "false-positive rate in generators.py — demotion happens on evidence, not on a "
                 "confidence counter drifting down."),
    }


def report(ledger, min_cluster: int = 2, candidates: Optional[list] = None) -> dict:
    """The whole pipeline's read-only view: what diverged, what clustered, what could graduate."""
    div = divergences(ledger)
    graded = [{"candidate": c, **graduate(c)} for c in (candidates or [])]
    return {
        "divergences": div,
        "clusters": clusters(div, min_size=min_cluster),
        "candidates": graded,
        "checks": [g for g in graded if g["graduated"]],
        "standing_proposals": [g for g in graded if g.get("state") == "proposal"],
        "note": ("Nothing here is applied. Graduation makes a rule ELIGIBLE to be elected; only the "
                 "human's interview answer ever elects one, exactly as with every other decision. "
                 "With no cycles run yet this is correctly empty — an observer built before there "
                 "are outcomes observes nothing, which is why this was built last."),
    }
