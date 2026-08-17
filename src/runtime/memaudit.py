"""The ledger audited as a MEMORY — the eight ways a durable store fails, turned into carriers.

Every gate this package ships points outward, at the user's code. None points at the ledger itself,
and the ledger is the one artifact everything else derives from: the map projects it, `instructions`
writes it into `AGENTS.md`, `tracker` pushes it to an issue box, `settlement_verdict` decides what
may close on the strength of what it says. A store that quietly rots takes every projection with it,
and nothing in this repo would have said a word.

**The failure modes are not ours to invent, and this file does not.** The `MODEL — MEMORY` edge of
the interaction-centric taxonomy (Raj et al., *Model or Harness? An Interaction-Centric Taxonomy for
Localizing Agent Failures*, arXiv:2607.28802, 2026-07-30) enumerates eight, split write-side and
read-side: Missed Write · State Staleness · Overgeneralization · Memory Rationale Erosion ·
Pollution · Redundancy · Missed Read · Memory Following Failure. They are reproduced here because a
taxonomy read once and paraphrased is the rationale erosion it names.

Read them against this schema and the split that matters is not write/read — it is **decidable from
the file, or not**:

- Six are decidable, because the ledger already carries the carrier each one needs: a closing rung
  with no re-derivable evidence (staleness), a scope that selects more than the instance that
  produced it (overgeneralization), `policy_weakness` (rationale erosion), field size and transcript
  signatures (pollution), normalized equality (redundancy), two standing policies selecting one pin
  (following failure).
- **Two are not, and this module says so instead of approximating them.** Missed Write and Missed
  Read are claims about what happened in a session, not about what the file says: the fact that was
  never written leaves no trace in the store that failed to hold it, and a read that never happened
  is visible only where the reads are — the tool layer. Reporting them from the file would mean
  ranking absence, which is the one inference this package forbids everywhere else.

**Read-only, and structurally so.** Like `tracker.py`, this module constructs no `Ledger` and
imports no write door; `to_pins` takes a ledger the CALLER already holds, so the write stays at the
caller's own door where the human can see it. An audit that could edit what it audits is not an
audit.

**Every finding names the pin or policy it is about and the rule it broke.** None of them decides
anything: they are `design_concern` pins like any other, and closing one is the human's move through
the interview. The auditor reopens; it never elects.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Optional

# The eight modes, verbatim in intent, each with the carrier that decides it here. `carrier: None`
# is a declaration, not a TODO: it is what this file cannot answer from a `ledger.json` alone.
MEMORY_MODES = (
    {"id": "missed_write", "side": "write", "carrier": None,
     "why_not": "the fact that was never written leaves no trace in the store; deciding it needs "
                "the session transcript, which this file is not"},
    {"id": "state_staleness", "side": "write", "carrier": "closing rung with no re-derivable evidence"},
    {"id": "overgeneralization", "side": "write", "carrier": "policy scope wider than its instance"},
    {"id": "rationale_erosion", "side": "write", "carrier": "policy_weakness, and its cascade"},
    {"id": "pollution", "side": "write", "carrier": "transcript signatures and field size"},
    {"id": "redundancy", "side": "write", "carrier": "normalized equality of title / rule"},
    {"id": "missed_read", "side": "read", "carrier": None,
     "why_not": "a read that did not happen is visible at the tool layer, not in the store; the "
                "MCP server sees it and this module does not"},
    {"id": "memory_following_failure", "side": "read",
     "carrier": "two standing policies selecting one pin"},
)

#: The modes this module answers. Derived, never a second list — a hand-kept copy is the drift the
#: package exists to find.
DECIDABLE = tuple(m["id"] for m in MEMORY_MODES if m["carrier"])
UNDECIDABLE = tuple(m["id"] for m in MEMORY_MODES if not m["carrier"])

# HYPOTHESIS: a durable field longer than this carries something that was not meant to be durable.
# Chosen against the widest field this runtime itself writes — a `rule` or an `as_is.description`
# runs to a few hundred characters — with room to spare, so the finding fires on pasted output
# rather than on a carefully-written sentence. Tune it if a real project's prose trips it.
_MAX_DURABLE_CHARS = 2000

# HYPOTHESIS: a policy whose scope selects more pins than this, from an election that cited one,
# is generalizing rather than recording. Two is the smallest number that is not the instance
# itself, and the smallest that can be wrong — a scope selecting exactly the pin it came from is
# a record, one selecting three is a rule nobody stated.
_SCOPE_BREADTH = 2

#: Signatures of transient material in a durable field. Each is a LITERAL that a machine emits and
#: a person writing a decision does not: a Python traceback header, an ANSI escape, a shell prompt
#: echo of a failed command, a JSON dump opener at the head of the value. Not keyword-guessing —
#: these are the exact strings their producers emit, which is what makes the check a carrier.
_TRANSCRIPT_SIGNATURES = (
    "Traceback (most recent call last)",
    "\x1b[",
    "\r\n\r\n",
)
_STACK_FRAME = re.compile(r'^\s+File "[^"]+", line \d+', re.M)


def _text_fields(record: Any) -> list[tuple[str, str]]:
    """Every durable free-text value in a record, as `(path, value)`, one level into objects.

    One level, deliberately. The pollution check is about what a writer PASTED into a field, and a
    paste lands in the field it was passed to. Walking arbitrarily deep would turn every nested
    envelope into a second reading of the same string.
    """
    out: list[tuple[str, str]] = []
    if not isinstance(record, dict):
        return out
    for key, value in record.items():
        if isinstance(value, str):
            out.append((key, value))
        elif isinstance(value, dict):
            for sub, subvalue in value.items():
                if isinstance(subvalue, str):
                    out.append((f"{key}.{sub}", subvalue))
    return out


def normalized(text: Any) -> str:
    """The comparison key for redundancy: NFKC, casefolded, whitespace collapsed, terminal
    punctuation dropped.

    Exact-after-normalization and nothing more. Two pins that *mean* the same thing in different
    words are not caught here and must not be: judging that is a model's job, and a duplicate
    reported on a model's say-so is the finding this package refuses everywhere else. What this
    catches is the same sentence written twice, which is what Redundancy actually looks like in a
    store an agent writes to across sessions.
    """
    if not isinstance(text, str):
        return ""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(folded.split()).rstrip(".!?:;,")


def _finding(mode: str, subject: str, detail: str, severity: str) -> dict:
    return {"mode": mode, "subject": subject, "detail": detail, "severity": severity}


def _closing_rung(pin: dict) -> Optional[str]:
    from ledger import _CLOSING_RUNGS
    envelope = pin.get("verification")
    if not isinstance(envelope, dict):
        return None
    rung = envelope.get("rung")
    return rung if rung in _CLOSING_RUNGS else None


def state_staleness(pins: Iterable[dict]) -> list[dict]:
    """A pin closed on a claim nobody can re-derive.

    `resolved` means *observed*, and the envelope is the single carrier of how hard the thing was
    checked — but a rung records how hard, never **against what**. A pin that closed at `observed`
    with an `evidence` list carrying no `ref` says the behaviour was seen and gives the next reader
    no way to see it again. After an upstream change the repository may still build while the claim
    is silently false, and the store keeps saying `resolved` (the class Yuan et al. name
    artifact-anchored verification memory, arXiv:2608.04278).

    The finding is the ABSENCE of a re-derivation handle, not a judgment about the claim. A pin
    carrying `ref: "pytest -k payments"` passes here whether or not that command still passes —
    checking that is the measurer's job, and it can only do it because the ref is there.
    """
    from ledger import CLOSED_STATES
    out = []
    for pin in pins:
        if pin.get("state") not in CLOSED_STATES:
            continue
        rung = _closing_rung(pin)
        if rung is None:
            continue
        evidence = (pin.get("verification") or {}).get("evidence")
        refs = [e.get("ref") for e in evidence if isinstance(e, dict)] if isinstance(evidence, list) else []
        if not any(isinstance(r, str) and r.strip() for r in refs):
            out.append(_finding(
                "state_staleness", str(pin.get("id") or ""),
                f"closed at rung {rung!r} with no evidence ref — the claim states that the "
                f"behaviour was seen and carries nothing that would show it again, so an upstream "
                f"change cannot invalidate it and this pin will read as verified forever",
                "high"))
    return out


def overgeneralization(policies: Iterable[dict], pins: Iterable[dict]) -> list[dict]:
    """A standing rule that selects more than the case that produced it.

    The store's job is to hold what was elected. A policy whose `applies_to` is empty selects every
    pin in the file — including every pin written after it, which nobody was asked about — and one
    that selects several while the election cited one instance has quietly become a law. Both are
    the same failure at different widths, and the second is the one that gets past a reviewer.
    """
    from ledger import policy_selects
    pin_list = [p for p in pins if isinstance(p, dict)]
    out = []
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        applies_to = policy.get("applies_to")
        pid = str(policy.get("id") or "")
        if isinstance(applies_to, dict) and not applies_to:
            out.append(_finding(
                "overgeneralization", pid,
                f"empty scope: this rule selects all {len(pin_list)} pins in the file and every pin "
                f"written after it — a universal default nobody was asked to grant",
                "high"))
            continue
        selected = [p for p in pin_list if policy_selects(applies_to, p)]
        if len(selected) >= _SCOPE_BREADTH:
            out.append(_finding(
                "overgeneralization", pid,
                f"scope selects {len(selected)} pins ({', '.join(str(p.get('id')) for p in selected[:5])}"
                f"{'…' if len(selected) > 5 else ''}) — check the election behind it covered that "
                f"breadth rather than one case generalized",
                "medium"))
    return out


def rationale_erosion(policies: Iterable[dict], decision_log: Iterable[dict]) -> list[dict]:
    """The rule survives, the reason for it does not — and then it gets optimized away.

    `policy_weakness` already names the three shapes (`no_rung`, `unknown_rung`, `unquoted_relay`);
    what was missing is anybody reading it as a property of the STORE rather than of one policy. The
    second half is the cascade: a decision recorded as `cascaded` inherits its authority from the
    policy that fired, so a weak policy launders its weakness into every decision it defaults.
    """
    from ledger import cascaded_from, policy_weakness
    weak: dict[str, str] = {}
    out = []
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        flaw = policy_weakness(policy)
        if flaw:
            pid = str(policy.get("id") or "")
            weak[pid] = flaw
            out.append(_finding(
                "rationale_erosion", pid,
                f"{flaw}: the rule is recorded and the reason it was elected is not, so a later "
                f"reader has the action without its constraint",
                "medium"))
    for event in decision_log:
        if not isinstance(event, dict):
            continue
        source = cascaded_from(event)
        if source and source in weak:
            out.append(_finding(
                "rationale_erosion", str(event.get("id") or event.get("pin_id") or ""),
                f"cascaded from policy {source!r}, which is itself {weak[source]} — the decision "
                f"carries an authority its source never had",
                "medium"))
    return out


def pollution(records: Iterable[dict], collection: str) -> list[dict]:
    """Transient material written into a durable field.

    Two carriers, both literal. A **signature** a machine emits and a person does not — a traceback
    header, an ANSI escape, a stack frame line. And a **size** past which the value stopped being a
    decision and became a paste. Neither reads the meaning of the text.
    """
    out = []
    for record in records:
        rid = str(record.get("id") or "") if isinstance(record, dict) else ""
        for path, value in _text_fields(record):
            hit = next((s for s in _TRANSCRIPT_SIGNATURES if s in value), None)
            if hit is None and _STACK_FRAME.search(value):
                hit = 'File "…", line N'
            if hit is not None:
                out.append(_finding(
                    "pollution", f"{collection}:{rid}",
                    f"{path} carries {hit!r} — machine output pasted into a durable field, which "
                    f"every projection of this ledger now repeats",
                    "medium"))
            elif len(value) > _MAX_DURABLE_CHARS:
                out.append(_finding(
                    "pollution", f"{collection}:{rid}",
                    f"{path} is {len(value)} characters (budget {_MAX_DURABLE_CHARS}) — past this "
                    f"the field is holding a transcript rather than a decision",
                    "low"))
    return out


def redundancy(records: Iterable[dict], field: str, collection: str) -> list[dict]:
    """The same thing written twice, in a store an agent appends to across sessions.

    Reported once per duplicate GROUP, naming every member, because a finding per member is itself
    the redundancy it is reporting.
    """
    groups: dict[str, list[str]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = normalized(record.get(field))
        if key:
            groups.setdefault(key, []).append(str(record.get("id") or ""))
    out = []
    for key, ids in groups.items():
        if len(ids) > 1:
            out.append(_finding(
                "redundancy", f"{collection}:{','.join(ids)}",
                f"{len(ids)} entries share one {field} after normalization ({key[:80]!r}) — the "
                f"store holds the same statement {len(ids)} times and a reader has no way to know "
                f"which one the projections used",
                "low"))
    return out


def memory_following_failure(policies: Iterable[dict], pins: Iterable[dict]) -> list[dict]:
    """Two standing rules select one pin, and nothing says which one wins.

    This is the read-side failure the file CAN decide: the store was consulted and gave two answers.
    Whichever default fired, the other rule was read and not followed, and the pin's own record says
    nothing about the collision — so the same pin can settle differently on two runs with no event
    marking that anything was ambiguous. It is the ambiguous-dispatch law of every keyed surface,
    applied to the one keyed surface this package owns.
    """
    from ledger import policy_selects
    policy_list = [p for p in policies if isinstance(p, dict)]
    out = []
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        hits = [str(p.get("id") or "") for p in policy_list if policy_selects(p.get("applies_to"), pin)]
        if len(hits) > 1:
            out.append(_finding(
                "memory_following_failure", str(pin.get("id") or ""),
                f"selected by {len(hits)} standing policies ({', '.join(hits)}) — the store answers "
                f"this pin twice and records no precedence, so which rule applied is not derivable "
                f"from the file",
                "high"))
    return out


def audit(data: Any) -> dict:
    """Every decidable mode, over one ledger's data. The undecidable two are REPORTED as such.

    The shape mirrors `coverage.report`: what ran, what it found, and — the half that matters here —
    what this carrier cannot answer, named rather than left as a silent zero. A clean audit that did
    not check two of the eight modes and says `0 findings` is the same sentence as a scan that never
    ran, which is the failure `coverage.py` exists for one layer down.
    """
    from ledger import read_collection, readable_ledger
    readable = readable_ledger(data)
    pins = read_collection(readable, "pins")
    policies = read_collection(readable, "policies")
    log = read_collection(readable, "decision_log")

    findings: list[dict] = []
    findings += state_staleness(pins)
    findings += overgeneralization(policies, pins)
    findings += rationale_erosion(policies, log)
    findings += pollution(pins, "pin")
    findings += pollution(policies, "policy")
    findings += redundancy(pins, "title", "pin")
    findings += redundancy(policies, "rule", "policy")
    findings += memory_following_failure(policies, pins)

    by_mode: dict[str, int] = {}
    for f in findings:
        by_mode[f["mode"]] = by_mode.get(f["mode"], 0) + 1
    return {
        "checked": list(DECIDABLE),
        "undecidable": [{"mode": m["id"], "why_not": m["why_not"]}
                        for m in MEMORY_MODES if not m["carrier"]],
        "findings": findings,
        "finding_count": len(findings),
        "by_mode": by_mode,
    }


def to_pins(ledger, findings: list[dict]) -> list[dict]:
    """One `design_concern` pin per finding, written through the CALLER's ledger.

    `confidence: extracted` — every one of these is a property of the file, computed, not judged.
    `kind_detail` carries the mode so the map and the tracker can group them, and so a reader can
    tell a store-health finding from a finding about the user's code, which is the distinction that
    makes this auditable at all.
    """
    out = []
    for f in findings:
        out.append(ledger.add_pin(
            kind="design_concern",
            title=f"memory: {f['mode']} on {f['subject']}",
            severity=f["severity"],
            confidence="extracted",
            provenance=[{"source": "memaudit", "detail": f["detail"]}],
            as_is={"description": f["detail"]},
            kind_detail=f"memory-{f['mode'].replace('_', '-')}",
        ))
    return out
