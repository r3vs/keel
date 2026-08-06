"""Challenger pass — the mechanizable slice of the upstream oracle red-team (ledger v0.6).

`core/agents.md` + the ledger spec define the read-only `challenger`: after the interview commits
and at each wave checkpoint it tries to **refute** each elected oracle (an `acceptance_criterion`,
a `to_be`, a `Policy`) and, on a sustained challenge, reopens the pin via a `ChallengeEvent`.
It challenges, never decides.

Some challenge classes are **deterministic** and belong in code (a check that always fires on the
same shape); others need **judgment** and stay agent-driven. This module implements the
deterministic ones so they run every time, cheaply and without a model call:

- `unfalsifiable` (deterministic slice) — an elected `to_be`/`acceptance_criterion` with **no**
  `verify` at all (nothing a test could even name) → it is a slogan, not an oracle. Whether a
  *present* verify is genuinely testable or merely vague is a judgment call, left to the agent.
- `ignored_fanout` — a high-fan-out pin (many inbound `depends_on`) that was resolved as a silent
  `proposed_default` instead of `asked` → a decision that deserved a real question got a default.

The judgment classes (`inconsistent`, `unsatisfiable`, `unstated_assumption`) are left to the
agent, which calls `ledger.challenge(...)` with its argument — the same sink this module uses.

**Not here, and why:** "a decision recorded as `transcribed` with no `human_answer`" looks like a
deterministic class and is not one. `mcp/tools.py::record_decision` already *refuses* that write, so
no shipped path can produce it. What remained were the library's own callers, and the only one that
produced unquoted `transcribed` events was the policy cascade — running with the default rung for
something nobody transcribed. Since v0.11 it writes `cascaded` and points at the `Policy`, so that
population is empty by construction in anything this runtime wrote — and in a ledger written before
it, `ledger.decision_rung` reads those events as the cascades they are, so the class would not fire
there either, on a population that only ever existed as a recording defect. (The policy's own
election is quoted where it belongs, on the policy, and `record_policy` refuses a relayed one with no
quote — the same rule, one level up, where the claim is actually made.) The rung is
surfaced instead where a human weighs it (the map's decision card, `ledger_summary`), and an agent
that reads an unquoted relay can still challenge it as `unstated_assumption` on target `decision`.
Everything here only proposes challenges; `ledger.challenge(upheld=True)` is what reopens, and only
the interview ever commits.

**Second mode — premortem (v0.9).** Refutation asks whether the oracle is sound; the premortem
grants it and asks how the work dies anyway. Same role, same read-only posture, so the roster stays
at six: `premortem_required()` answers *is one owed here* from carriers the ledger already holds
(D0), and `ledger.premortem()` is where the imagined failures land (D2, labeled). The imagining
itself is the agent's — a script cannot invent a way for a plan to die, and pretending otherwise
would be the fake determinism `core/trust-axes.md` forbids.
"""
from __future__ import annotations

from typing import Optional

from ledger import pin_read

# HYPOTHESIS, tunable — a pin at or above this inbound fan-out, defaulted rather than asked, is an
# ignored_fanout smell. Nothing measured 2; it is the smallest count where "several decisions rest
# on this" is literally true. Declared here rather than hidden, and reused by premortem_required so
# the package has one fan-out notion instead of two.
_FANOUT_THRESHOLD = 2


def _inbound_fanout(ledger, pin_id: str) -> int:
    return sum(1 for p in ledger.readable_pins() if pin_id in pin_read(p)["depends_on"])


def _has_testable_verify(pin: dict) -> bool:
    """Deterministic slice only: a `verify` is present and non-empty.

    Whether a *present* verify is genuinely testable or just a slogan ("feels fast") is a
    judgment call and stays agent-driven — grepping a vibe-word blocklist here would be the
    keyword-guessing this package forbids, and it mis-fires both ways ("fast" is inside
    "breakfast", "solid" inside "consolidate").
    """
    to_be = pin.get("to_be") or {}
    verify = to_be.get("verify") if isinstance(to_be, dict) else None
    return bool(verify and str(verify).strip())


def scan(ledger) -> list[dict]:
    """Return proposed challenges (not yet applied) over the decided oracle pins.

    Each item: {pin_id, target, class, argument, severity}. The caller (or an agent that adds its
    own judgment-class challenges) decides which to apply via ledger.challenge(upheld=True)."""
    proposals: list[dict] = []
    # Through the guarded read (v0.22): `mcp:challenge_oracle` takes nothing but a ledger path and
    # is served read-only, so it is under the same rule the summary is — reading a ledger is never
    # the operation that fails on it. `kind` is not one of `pin_read`'s five and is asked with
    # `.get`, which is what a membership test wanted anyway.
    for pin in ledger.readable_pins():
        read = pin_read(pin)
        if read["state"] not in ("decided", "accepted"):
            continue

        # unfalsifiable: an elected outcome/to_be with no testable verify
        if pin.get("kind") in ("acceptance_criterion", "open_decision", "contract_mismatch",
                               "internal_contradiction", "ambiguity"):
            to_be = pin.get("to_be")
            if isinstance(to_be, dict) and ("verify" in to_be
                                            or pin.get("kind") == "acceptance_criterion"):
                if not _has_testable_verify(pin):
                    proposals.append({
                        "pin_id": read["id"], "target": "acceptance_criterion"
                        if pin.get("kind") == "acceptance_criterion" else "to_be",
                        "class": "unfalsifiable",
                        "argument": "the elected to_be/criterion has no testable verify — "
                                    "no test could fail it, so it cannot serve as an oracle",
                        "severity": "high"})

        # ignored_fanout: a high-fan-out pin that was silently defaulted, not asked
        if _inbound_fanout(ledger, pin["id"]) >= _FANOUT_THRESHOLD \
                and pin.get("resolution_mode") == "proposed_default":
            proposals.append({
                "pin_id": pin["id"], "target": "decision", "class": "ignored_fanout",
                "argument": f"{_inbound_fanout(ledger, pin['id'])} decisions depend on this pin, "
                            "yet it was resolved as a silent proposed_default rather than asked",
                "severity": "high"})
    return proposals


def premortem_required(ledger, pin: dict) -> dict:
    """Is a premortem obligatory for this pin? `{required, because[]}` — D0, presence only.

    The obligation is derived from carriers the ledger already holds, never from a new tuned
    number. Each reason below is a fact somebody recorded, so the gate cannot quietly become a
    threshold nobody can defend:

    - `blocker|high` — the v0.3 severity threshold, already load-bearing everywhere else;
    - a landing-zone verdict of `harden_first`/`redesign` — the terrain is *known* bad (v0.8);
    - the pin has been reopened before — a recorded history of being wrong about this one;
    - inbound fan-out at the existing `_FANOUT_THRESHOLD` — the same constant the `ignored_fanout`
      class already uses, declared once and reused rather than invented twice.

    Whether the premortem is any *good* is judgment and stays with the agent; this only answers
    whether one is owed.
    """
    because = []
    if pin.get("severity") in ("blocker", "high"):
        because.append(f"severity {pin['severity']} — never handled silently")
    verdict = (pin.get("readiness") or {}).get("verdict")
    if verdict in ("harden_first", "redesign"):
        because.append(f"landing zone is {verdict} — the ground is already known to be weak")
    if any(e.get("pin_id") == pin_read(pin)["id"]
           and str(e.get("id") or "").startswith(("chl_", "rev_"))
           for e in ledger.readable("decision_log")):
        because.append("this pin has been reopened before")
    fanout = _inbound_fanout(ledger, pin_read(pin)["id"])
    if fanout >= _FANOUT_THRESHOLD:
        because.append(f"{fanout} decisions depend on it")
    return {"required": bool(because), "because": because, "determinism": "D0"}


def premortem_gaps(ledger) -> list[dict]:
    """Pins that owe a premortem and do not have one. The challenger's own queue — and the
    `needs_challenge` route of the agent-ready card (`agentready.py`)."""
    out = []
    for pin in ledger.readable_pins():
        if pin_read(pin)["state"] in ("resolved", "accepted", "deferred") or pin.get("premortem"):
            continue
        req = premortem_required(ledger, pin)
        if req["required"]:
            out.append({"pin_id": pin_read(pin)["id"], "title": pin.get("title"),
                        "because": req["because"]})
    return out


def run(ledger, apply: bool = True) -> list[dict]:
    """Scan, and (by default) apply each proposed challenge as an upheld ChallengeEvent — which
    reopens the pin (state `challenged`) and its dependents. Returns the applied/proposed list.
    Set apply=False for a dry run (report without reopening)."""
    proposals = scan(ledger)
    for c in proposals:
        if apply:
            ledger.challenge(c["pin_id"], target=c["target"], challenge_class=c["class"],
                             argument=c["argument"], severity=c["severity"], upheld=True)
    return proposals
