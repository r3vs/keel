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
Everything here only proposes challenges; `ledger.challenge(upheld=True)` is what reopens, and only
the interview ever commits.
"""
from __future__ import annotations

from typing import Optional

# a pin at or above this inbound-fan-out, defaulted rather than asked, is an ignored_fanout smell
_FANOUT_THRESHOLD = 2


def _inbound_fanout(ledger, pin_id: str) -> int:
    return sum(1 for p in ledger.data["pins"] if pin_id in p.get("depends_on", []))


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
    for pin in ledger.data["pins"]:
        if pin["state"] not in ("decided", "accepted"):
            continue

        # unfalsifiable: an elected outcome/to_be with no testable verify
        if pin["kind"] in ("acceptance_criterion", "open_decision", "contract_mismatch",
                           "internal_contradiction", "ambiguity"):
            to_be = pin.get("to_be")
            if isinstance(to_be, dict) and ("verify" in to_be or pin["kind"] == "acceptance_criterion"):
                if not _has_testable_verify(pin):
                    proposals.append({
                        "pin_id": pin["id"], "target": "acceptance_criterion"
                        if pin["kind"] == "acceptance_criterion" else "to_be",
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
