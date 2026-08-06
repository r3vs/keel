"""Agent-Ready Gate — is this item actually handable to an executor, or only unblocked?

`buildloop.ready()` answers one question: are this pin's dependencies closed? That is dependency
scheduling, and it is correct — but it lets a *vague* item through with no friction at all. An item
with no elected check, no idea where it lands, and no assessment of the ground it lands on is
"ready" only in the sense that nothing is holding it back.

The gate is **two layers, and they never merge into a single verdict** (`core/trust-axes.md`):

    PRECONDITIONS   is the thing PRESENT?   D0 presence   this module
    QUALITY         is the thing GOOD?      D2 judgment   the challenger

Fusing them is the failure this whole plan is written against: a `ready: true` computed partly from
"the verify field is non-empty" and partly from "the criterion looks falsifiable" would carry a
deterministic badge over a judgment. So the card reports both, side by side, labeled — and a reader
can always see which half is computed and which half was thought.

Nothing here invents a field for someone to fill. Each precondition reads a carrier that already
exists, and — the one worth naming — the *rollback and stop conditions* the gate wants are exactly
the `guardrails` and `abort_criteria` a premortem produces, so the premortem IS the preflight rather
than a second form beside it.

**Routing back beats blocking.** A failed precondition names who can fix it, because "not ready" with
no addressee is how an item sits still. One route is not in the original plan: `needs_challenge`.
The plan named four routes and then introduced a quality layer owned by the challenger with nowhere
to send it — that was a gap, and forcing it into `needs_research` (a different role entirely) would
have hidden the gap rather than closed it.

Stdlib-only. Reads the ledger and `buildloop` / `challenger`; writes nothing.
"""
from __future__ import annotations

import buildloop
import challenger
from ledger import pin_read

_DONE_STATES = ("resolved", "accepted")

#: route -> who is being handed the item back
OWNERS = {
    "ready": "executor",
    "needs_interview": "human (the interview elects)",
    "needs_research": "researcher",
    "needs_hardening": "executor, but on the prerequisite pins first",
    "needs_challenge": "challenger",
    "human_only": "human — the terrain says reshape the change, which is not an executor's call",
}


def _has_oracle(pin: dict) -> bool:
    """An elected, named check. Presence only — whether it is *falsifiable* is the quality layer's
    question, and answering it here with a keyword list is the trap this package documents."""
    to_be = pin.get("to_be")
    if isinstance(to_be, dict) and str(to_be.get("verify") or "").strip():
        return True
    # a defect's oracle is its reproduction: the as_is IS the failing observation
    return pin.get("kind") == "defect" and bool(pin.get("as_is"))


def _has_scope(pin: dict) -> bool:
    """Where the work lands: an anchor in existing code, or a declared target for new code.

    Both are carriers, and the two together are what makes the check work in *both* skills — rescue
    pins anchor into a tree that exists, forge's build items name a `canonical_target` for a tree
    that does not yet.
    """
    if pin.get("anchors"):
        return True
    return any(i.get("canonical_target") for i in pin.get("remediation", []))


def _terrain(ledger, pin: dict) -> dict:
    """Landing-zone state for this pin: `not_applicable` / `unassessed` / the recorded verdict.

    Not applicable when the pin has no anchors — there is no existing ground to bear anything, which
    is the ordinary case for a greenfield item on an empty tree. Reporting `unassessed` there would
    manufacture a gap out of a project's own emptiness.
    """
    if not pin.get("anchors"):
        return {"state": "not_applicable", "why": "no anchors — nothing existing is being landed on"}
    readiness = pin.get("readiness")
    if not readiness:
        return {"state": "unassessed", "why": "this change lands on existing code and no landing "
                                              "zone was assessed (`readiness_assess`)"}
    verdict = readiness.get("verdict")
    # The guarded read (v0.22): `mcp:agent_ready` is served read-only and takes nothing but a
    # ledger path, so a pin missing a field must not make the gate the call that fails.
    by_id = {pin_read(p)["id"]: p for p in ledger.readable_pins()}
    open_prereqs = [h for h in readiness.get("hardens", [])
                    if h in by_id and pin_read(by_id[h])["state"] not in _DONE_STATES]
    return {"state": verdict, "why": readiness.get("rationale", ""),
            "open_prerequisites": open_prereqs,
            "determinism": readiness.get("determinism", "D2")}


def card(ledger, pin_id: str) -> dict:
    """The two-layer readiness card for one pin. Computes presence; delegates judgment; routes."""
    pin = ledger.pin(pin_id)
    terrain = _terrain(ledger, pin)
    premortem_req = challenger.premortem_required(ledger, pin)

    preconditions = {
        "oracle": {"present": _has_oracle(pin),
                   "carrier": "to_be.verify (or a defect's reproduction)"},
        "scope": {"present": _has_scope(pin),
                  "carrier": "pin.anchors or an item's canonical_target"},
        "terrain": {"present": terrain["state"] in ("not_applicable", "ready", "harden_first",
                                                    "redesign"),
                    "carrier": "pin.readiness (readiness_assess -> ledger_set_readiness)",
                    **terrain},
        "premortem": {"present": bool(pin.get("premortem")) or not premortem_req["required"],
                      "required": premortem_req["required"],
                      "because": premortem_req["because"],
                      "carrier": "pin.premortem — its guardrails and abort_criteria ARE the "
                                 "rollback and stop conditions this gate asks for"},
    }
    missing = [k for k, v in preconditions.items() if not v["present"]]

    # Route: first hit wins, hardest constraint first. Deterministic mapping from WHICH carrier is
    # absent to WHO can supply it — no scoring, no threshold.
    if terrain["state"] == "redesign":
        route = "human_only"
    elif terrain["state"] == "harden_first" and terrain.get("open_prerequisites"):
        route = "needs_hardening"
    elif not preconditions["oracle"]["present"]:
        route = "needs_interview"
    elif not preconditions["scope"]["present"] or terrain["state"] == "unassessed":
        route = "needs_research"
    elif not preconditions["premortem"]["present"]:
        route = "needs_challenge"
    else:
        route = "ready"

    return {
        "pin": pin_id,
        "title": pin.get("title"),
        "state": pin.get("state"),
        "preconditions": {"determinism": "D0", "checks": preconditions, "missing": missing},
        "quality": {
            "determinism": "D2",
            "owner": "challenger",
            "verdict": "not_run" if not pin.get("premortem")
                       and not _challenges_for(ledger, pin_id) else "see challenges/premortem",
            "open_challenges": _challenges_for(ledger, pin_id),
            "note": "falsifiability of a PRESENT verify and closedness of the scope are judgments; "
                    "this layer is never folded into the D0 result above",
        },
        "route": route,
        "hand_to": OWNERS[route],
    }


def _challenges_for(ledger, pin_id: str) -> list[dict]:
    return [{"id": e["id"], "class": e["class"], "upheld": e["upheld"], "argument": e["argument"]}
            for e in ledger.data["decision_log"]
            if e.get("pin_id") == pin_id and e["id"].startswith("chl_")]


def gate(ledger) -> dict:
    """Cards for everything `buildloop.ready()` currently offers, grouped by route.

    Advisory by construction: this does **not** remove pins from `ready()`. A gate that silently
    shrank the queue would make an item disappear with no addressee — the same black hole a state
    that appears on no surface creates. It reports, loudly, and names who is owed the work.
    """
    cards = [card(ledger, pin_read(p)["id"]) for p in buildloop.ready(ledger)]
    by_route: dict[str, list] = {}
    for c in cards:
        by_route.setdefault(c["route"], []).append(c["pin"])
    return {
        "cards": cards,
        "by_route": by_route,
        "handable_now": by_route.get("ready", []),
        # The challenger's whole queue, not only the part that is ready to build. It rides along
        # here rather than in a tool of its own: an MCP description is rent paid every session, and
        # a second tool for a list this one already had to compute is rent for nothing.
        "premortems_owed": challenger.premortem_gaps(ledger),
        "note": "Advisory: `buildloop.ready()` is unchanged. This says which of those items an "
                "executor can actually take, and hands the rest back to a named owner.",
    }
