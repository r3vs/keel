# GENERATED FILE - do not edit. Source: src/runtime/ledger.py at the repo root;
# regenerate with: python scripts/build.py
"""Decisions-ledger runtime — the one implementation both skills bind to.

Schema authority: `core/decisions-ledger-spec.md` (v0.6). This module materializes the
spec's load-bearing rules as code, deliberately stack-agnostic and stdlib-only:

- append-only `decision_log` (DecisionEvent / ReopenEvent / ChallengeEvent — never edited);
- `Pin` as a discriminated union on `kind` (strict envelope, open `other` escape hatch);
- brainstorm/challenger/feedback **neutrality**: proposals and challenges can never commit
  a decision — only `source: "interview"` (or a user-set policy cascade) elects;
- the severity threshold: `blocker|high` pins are never silently defaulted — policies skip
  them and `proposed_default` is reserved for `medium|low`;
- `provenance: agent_assumption` — a forced assumption enters as a vetoable pin with
  `confidence: inferred|ambiguous`, never as a silent default;
- minimal reopen: an upheld challenge / fired flip signal reopens the pin plus only its
  decided `depends_on` dependents (transitively), nothing else.

On-disk form: one `ledger.json` (portable, git-versionable) written atomically.
The target codebase's ledger lives in *that* repo's audit output dir — never in this one.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = "0.6"

KINDS = {
    "contract_mismatch",
    "internal_contradiction",
    "ambiguity",
    "incompleteness",
    "design_concern",
    "defect",
    "open_decision",       # v0.4 — greenfield fork, nothing built yet
    "acceptance_criterion",  # v0.5 — testable outcome rooting the DAG
    "other",
}
SEVERITIES = ("blocker", "high", "medium", "low")
CONFIDENCES = ("extracted", "inferred", "ambiguous")
STATES = ("detected", "needs_input", "brainstorming", "decided", "deferred", "resolved", "accepted")
RESOLUTION_MODES = ("asked", "policy_default", "proposed_default")
CHALLENGE_CLASSES = (
    "unfalsifiable", "inconsistent", "unsatisfiable", "unfounded_infeasibility",
    "unstated_assumption", "ignored_fanout", "other",
)
CHALLENGE_TARGETS = ("acceptance_criterion", "to_be", "policy", "decision")
REMEDIATION_ACTIONS = ("consolidate", "implement", "refactor", "delete", "align")
BUILD_ACTIONS = ("scaffold", "implement", "wire", "configure", "instrument")  # v0.5 adds instrument
EFFORTS = ("S", "M", "L")
FLIP_SIGNAL_SOURCES = ("metrics", "logs", "traces", "manual_checkpoint", "incident")

# severities that must never be silently defaulted (the threshold rule, v0.3)
_NEVER_SILENT = ("blocker", "high")


class LedgerError(ValueError):
    """A spec rule was violated."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise LedgerError(msg)


def _validate_question(question: Optional[dict]) -> None:
    if question is None:
        return
    _require(isinstance(question, dict), "question must be a dict")
    _require(bool(question.get("prompt")), "question.prompt is required")
    options = question.get("options", [])
    _require(isinstance(options, list), "question.options must be a list")
    for opt in options:
        _require(bool(opt.get("id")) and bool(opt.get("label")),
                 "every question option needs id and label")


class Ledger:
    """One ledger.json: pins + append-only decision_log + policies."""

    def __init__(self, path: str):
        self.path = path
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.data = json.load(fh)
            _require(self.data.get("version") == SCHEMA_VERSION,
                     f"ledger schema {self.data.get('version')!r} != {SCHEMA_VERSION}")
        else:
            self.data = {"version": SCHEMA_VERSION, "pins": [], "decision_log": [], "policies": []}

    # -- persistence -------------------------------------------------------

    def save(self) -> None:
        """Atomic write: the ledger is the single source of truth — never half-written."""
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # -- lookups -----------------------------------------------------------

    def pin(self, pin_id: str) -> dict:
        for p in self.data["pins"]:
            if p["id"] == pin_id:
                return p
        raise LedgerError(f"no such pin: {pin_id}")

    def _next_id(self, prefix: str, collection: list, key: str = "id") -> str:
        n = 1 + sum(1 for item in collection if str(item.get(key, "")).startswith(prefix))
        return f"{prefix}{n:04d}"

    # -- pins ---------------------------------------------------------------

    def add_pin(
        self,
        kind: str,
        title: str,
        severity: str,
        confidence: str,
        provenance: list[dict],
        anchors: Optional[list[dict]] = None,
        as_is: Optional[dict] = None,
        to_be: Optional[dict] = None,
        question: Optional[dict] = None,
        depends_on: Optional[list[str]] = None,
        cluster_id: Optional[str] = None,
        kind_detail: Optional[str] = None,
    ) -> dict:
        _require(kind in KINDS, f"unknown kind {kind!r}")
        _require(kind != "other" or bool(kind_detail),
                 "kind 'other' requires kind_detail (the open escape hatch is named, not blank)")
        _require(severity in SEVERITIES, f"severity must be one of {SEVERITIES}")
        _require(confidence in CONFIDENCES, f"confidence must be one of {CONFIDENCES}")
        _require(isinstance(provenance, list) and len(provenance) > 0,
                 "provenance is required (who found this, how)")
        _validate_question(question)
        for dep in depends_on or []:
            self.pin(dep)  # must exist — the DAG is real, not aspirational

        # v0.6: a forced assumption is vetoable, never confidently asserted
        if any(src.get("source") == "agent_assumption" for src in provenance):
            _require(confidence in ("inferred", "ambiguous"),
                     "an agent_assumption pin must carry confidence inferred|ambiguous")

        pin = {
            "id": self._next_id("pin_", self.data["pins"]),
            "kind": kind,
            "title": title,
            "severity": severity,
            "confidence": confidence,
            "provenance": provenance,
            "anchors": anchors or [],
            "state": "needs_input" if question else "detected",
            "as_is": as_is,
            "to_be": to_be,
            "question": question,
            "brainstorm": None,
            "decision": None,
            "depends_on": depends_on or [],
            "remediation": [],
        }
        if cluster_id:
            pin["cluster_id"] = cluster_id
        if kind_detail:
            pin["kind_detail"] = kind_detail
        self.data["pins"].append(pin)
        return pin

    def surface_assumption(
        self,
        title: str,
        detail: str,
        severity: str = "medium",
        confidence: str = "inferred",
        question: Optional[dict] = None,
        **kwargs: Any,
    ) -> dict:
        """v0.6 anti-slop rule: a forced assumption becomes a pin, never a silent default.

        blocker|high assumptions are always asked (threshold rule); the default question
        is the veto: 'keep the assumption or correct it?'.
        """
        if question is None:
            question = {
                "prompt": f"Assumed to proceed: {detail}. Keep or correct?",
                "options": [
                    {"id": "keep", "label": "Keep the assumption"},
                    {"id": "correct", "label": "Correct it (state the real intent)"},
                ],
                "allow_freeform": True,
            }
        pin = self.add_pin(
            kind=kwargs.pop("kind", "ambiguity"),
            title=title,
            severity=severity,
            confidence=confidence,
            provenance=[{"source": "agent_assumption", "detail": detail}],
            question=question,
            **kwargs,
        )
        pin["resolution_mode"] = "asked" if severity in _NEVER_SILENT else \
            pin.get("resolution_mode", "asked")
        return pin

    def set_question(self, pin_id: str, question: dict) -> dict:
        pin = self.pin(pin_id)
        _validate_question(question)
        _require(pin["state"] not in ("resolved",), "cannot re-question a resolved pin")
        pin["question"] = question
        pin["state"] = "needs_input"
        return pin

    # -- brainstorm (neutral by schema) --------------------------------------

    def add_proposals(self, pin_id: str, proposals: list[dict], notes: str = "") -> dict:
        """The brainstorm writes proposals[] with tradeoffs — it can never decide."""
        pin = self.pin(pin_id)
        for prop in proposals:
            _require(bool(prop.get("summary")), "a proposal needs a summary")
            _require(prop.get("effort") in EFFORTS if "effort" in prop else True,
                     f"proposal effort must be one of {EFFORTS}")
            _require("decision" not in prop and "outcome" not in prop,
                     "neutrality: a proposal must not carry a decision/outcome")
            prop.setdefault("id", f"prop_{len(proposals)}")
            prop.setdefault("tradeoffs", {"pros": [], "cons": []})
        pin["brainstorm"] = {"proposals": proposals, "notes": notes}
        if pin["state"] == "needs_input":
            pin["state"] = "brainstorming"
        return pin

    # -- decisions (append-only; only the interview commits) ----------------

    def decide(
        self,
        pin_id: str,
        outcome: str,
        rationale: str,
        flip_criteria: str,
        source: str = "interview",
        flip_signal: Optional[dict] = None,
        apply_to_cluster: bool = False,
    ) -> list[dict]:
        """Append a DecisionEvent and materialize pin.state (last committed wins).

        Design decision 9: every decision carries flip_criteria. Neutrality: only
        `interview` or a user-set `policy:<id>` may commit — the brainstorm, the
        challenger, and the feedback loop cannot.
        """
        _require(source == "interview" or source.startswith("policy:"),
                 f"only the interview (or a user-set policy cascade) commits; got {source!r}")
        _require(bool(flip_criteria),
                 "flip_criteria is required — a decision without a reopen condition fossilizes")
        if flip_signal is not None:
            _require(flip_signal.get("source") in FLIP_SIGNAL_SOURCES,
                     f"flip_signal.source must be one of {FLIP_SIGNAL_SOURCES}")

        pin = self.pin(pin_id)
        targets = [pin]
        if apply_to_cluster and pin.get("cluster_id"):
            targets += [p for p in self.data["pins"]
                        if p.get("cluster_id") == pin["cluster_id"] and p["id"] != pin_id]

        events = []
        for target in targets:
            event = {
                "id": self._next_id("ev_", self.data["decision_log"]),
                "pin_id": target["id"],
                "timestamp": _now(),
                "outcome": outcome,
                "rationale": rationale,
                "flip_criteria": flip_criteria,
                "source": source,
            }
            if flip_signal is not None:
                event["flip_signal"] = dict(flip_signal)
            self.data["decision_log"].append(event)
            target["state"] = "decided"
            target.pop("substate", None)
            target["decision"] = {"event_id": event["id"], "outcome": outcome}
            events.append(event)
        return events

    def defer(self, pin_id: str) -> dict:
        """Out of scope now (YAGNI at spec level) — stays as future backlog."""
        pin = self.pin(pin_id)
        _require(pin["state"] != "resolved", "cannot defer a resolved pin")
        pin["state"] = "deferred"
        return pin

    def accept(self, pin_id: str, rationale: str, flip_criteria: str) -> dict:
        """Leave-as-is: the legitimate default resolution of a design_concern only."""
        pin = self.pin(pin_id)
        _require(pin["kind"] == "design_concern",
                 "accepted applies to design_concern only (open_decision has nothing to keep)")
        self.decide(pin_id, outcome="keep", rationale=rationale, flip_criteria=flip_criteria)
        pin["state"] = "accepted"
        return pin

    # -- policies (v0.3: user decisions, amplified) ---------------------------

    def add_policy(self, applies_to: dict, rule: str, default_outcome: Any,
                   exceptions: Optional[list[str]] = None) -> dict:
        policy = {
            "id": self._next_id("pol_", self.data["policies"]),
            "applies_to": applies_to,
            "rule": rule,
            "default_outcome": default_outcome,
            "set_by": "interview",
            "exceptions": exceptions or [],
        }
        self.data["policies"].append(policy)
        return policy

    def apply_policies(self) -> list[dict]:
        """Cascade user-set policies over matching pins.

        Threshold rule (v0.3): blocker|high pins are never auto-resolved — they stay
        `asked` even when a policy matches; medium|low resolve as `policy_default`
        with a DecisionEvent whose source names the policy (user-originated, amplified).
        """
        decided = []
        for policy in self.data["policies"]:
            for pin in self.data["pins"]:
                if pin["state"] in ("decided", "resolved", "accepted", "deferred"):
                    continue
                if pin["id"] in policy["exceptions"]:
                    continue
                if not all(pin.get(k) == v for k, v in policy["applies_to"].items()):
                    continue
                if pin["severity"] in _NEVER_SILENT:
                    pin["resolution_mode"] = "asked"   # top of the review batch, never silent
                    continue
                self.decide(
                    pin["id"],
                    outcome=json.dumps(policy["default_outcome"], ensure_ascii=False)
                    if not isinstance(policy["default_outcome"], str)
                    else policy["default_outcome"],
                    rationale=policy["rule"],
                    flip_criteria=f"an exception to policy {policy['id']} surfaces",
                    source=f"policy:{policy['id']}",
                )
                pin["resolution_mode"] = "policy_default"
                decided.append(pin)
        return decided

    def assign_resolution_modes(self) -> None:
        """v0.3 funnel: blocker|high → asked; the medium|low long tail may batch."""
        for pin in self.data["pins"]:
            if pin["state"] in ("needs_input", "detected") and "resolution_mode" not in pin:
                pin["resolution_mode"] = (
                    "asked" if pin["severity"] in _NEVER_SILENT else "proposed_default"
                )

    # -- the two reopen arcs (both reopen, neither decides) -------------------

    def challenge(
        self,
        pin_id: str,
        target: str,
        challenge_class: str,
        argument: str,
        severity: str,
        upheld: bool,
        source: str = "challenge:challenger",
    ) -> dict:
        """v0.6 upstream arc: adversarially refute an elected oracle *before* build.

        Appends an immutable ChallengeEvent; if upheld, moves the pin (and only its
        decided dependents) back to needs_input/challenged. Never writes a DecisionEvent.
        """
        _require(target in CHALLENGE_TARGETS, f"target must be one of {CHALLENGE_TARGETS}")
        _require(challenge_class in CHALLENGE_CLASSES,
                 f"class must be one of {CHALLENGE_CLASSES}")
        _require(severity in SEVERITIES, f"severity must be one of {SEVERITIES}")
        pin = self.pin(pin_id)
        event = {
            "id": self._next_id("chl_", self.data["decision_log"]),
            "pin_id": pin_id,
            "timestamp": _now(),
            "target": target,
            "class": challenge_class,
            "argument": argument,
            "severity": severity,
            "upheld": upheld,
            "source": source,
        }
        self.data["decision_log"].append(event)
        if upheld:
            self._reopen_minimal(pin, substate="challenged")
        return event

    def reopen(self, pin_id: str, reason: str, fired: str = "flip_signal",
               source: str = "feedback:metrics") -> dict:
        """v0.5 downstream arc: production falsified the decision — reopen, don't decide."""
        pin = self.pin(pin_id)
        event = {
            "id": self._next_id("rev_", self.data["decision_log"]),
            "pin_id": pin_id,
            "timestamp": _now(),
            "reason": reason,
            "fired": fired,
            "source": source,
        }
        self.data["decision_log"].append(event)
        self._reopen_minimal(pin, substate="reopened")
        return event

    def _reopen_minimal(self, pin: dict, substate: str) -> None:
        """Reopen the minimum: the pin plus its decided depends_on dependents, transitively.

        A challenger that reopens everything regenerates the very churn the skills cure.
        """
        to_reopen = {pin["id"]}
        changed = True
        while changed:
            changed = False
            for p in self.data["pins"]:
                if p["id"] in to_reopen:
                    continue
                if any(dep in to_reopen for dep in p.get("depends_on", [])) \
                        and p["state"] in ("decided", "resolved", "accepted"):
                    to_reopen.add(p["id"])
                    changed = True
        for p in self.data["pins"]:
            if p["id"] in to_reopen:
                p["state"] = "needs_input"
                p["substate"] = substate
                p["resolution_mode"] = "asked"   # a reopened truth is never re-defaulted silently

    # -- remediation / build (the bridge to Phase 4) ---------------------------

    def add_remediation(self, pin_id: str, action: str, ladder_rung: int,
                        canonical_target: Optional[str] = None,
                        build_track: Optional[str] = None,
                        contract_carrier: Optional[str] = None,
                        depends_on: Optional[list[str]] = None) -> dict:
        """RemediationItem (rescue verbs) or BuildItem (greenfield verbs, build_track set)."""
        pin = self.pin(pin_id)
        is_build = build_track is not None
        allowed = BUILD_ACTIONS if is_build else REMEDIATION_ACTIONS
        _require(action in allowed,
                 f"action {action!r} not in {allowed} ({'BuildItem' if is_build else 'RemediationItem'})")
        _require(pin["state"] == "decided" or pin["kind"] == "defect",
                 "remediation follows a decision (defects may go straight to the plan)")
        if is_build:
            _require(build_track in ("A", "B"), "build_track must be A or B")
        item = {
            "id": self._next_id("rem_" if not is_build else "bld_", pin["remediation"]),
            "action": action,
            "ladder_rung": ladder_rung,
            "status": "todo",
        }
        if canonical_target:
            item["canonical_target"] = canonical_target
        if build_track:
            item["build_track"] = build_track
        if contract_carrier:
            item["contract_carrier"] = contract_carrier
        if depends_on:
            item["depends_on"] = depends_on
        pin["remediation"].append(item)
        return item

    def set_remediation_status(self, pin_id: str, item_id: str, status: str) -> dict:
        _require(status in ("todo", "in_progress", "done"), "bad remediation status")
        pin = self.pin(pin_id)
        for item in pin["remediation"]:
            if item["id"] == item_id:
                item["status"] = status
                return item
        raise LedgerError(f"no remediation item {item_id} on {pin_id}")

    def resolve(self, pin_id: str) -> dict:
        pin = self.pin(pin_id)
        _require(pin["state"] == "decided" or pin["kind"] == "defect",
                 "only a decided pin (or a defect) can resolve")
        _require(all(i["status"] == "done" for i in pin["remediation"]),
                 "resolve requires every remediation item done")
        _require(len(pin["remediation"]) > 0,
                 "resolve without remediation is a silent close — record what closed the gap")
        pin["state"] = "resolved"
        return pin

    # -- views (the surfaces hold no state of their own) ------------------------

    def interview_view(self) -> list[dict]:
        """The interview IS the filtered view of needs_input pins, ordered by
        information gain: the ones that collapse the most downstream pins come first."""
        dependents: dict[str, int] = {}
        for p in self.data["pins"]:
            for dep in p.get("depends_on", []):
                dependents[dep] = dependents.get(dep, 0) + 1

        def transitive(pin_id: str, seen: frozenset = frozenset()) -> int:
            total = 0
            for p in self.data["pins"]:
                if pin_id in p.get("depends_on", []) and p["id"] not in seen:
                    total += 1 + transitive(p["id"], seen | {p["id"]})
            return total

        pending = [p for p in self.data["pins"] if p["state"] == "needs_input"]
        sev_rank = {s: i for i, s in enumerate(SEVERITIES)}
        return sorted(
            pending,
            key=lambda p: (-transitive(p["id"]), sev_rank[p["severity"]], p["id"]),
        )

    def summary(self) -> dict:
        by_state: dict[str, int] = {}
        for p in self.data["pins"]:
            by_state[p["state"]] = by_state.get(p["state"], 0) + 1
        return {
            "version": self.data["version"],
            "pins": len(self.data["pins"]),
            "by_state": by_state,
            "events": len(self.data["decision_log"]),
            "policies": len(self.data["policies"]),
            "open_questions": len(self.interview_view()),
        }


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect a ledger.json (read-only views)")
    parser.add_argument("command", choices=["summary", "interview"])
    parser.add_argument("path", help="path to ledger.json")
    args = parser.parse_args(argv)

    ledger = Ledger(args.path)
    if args.command == "summary":
        print(json.dumps(ledger.summary(), indent=2, ensure_ascii=False))
    else:
        for pin in ledger.interview_view():
            prompt = (pin.get("question") or {}).get("prompt", "(no question materialized)")
            print(f"[{pin['severity']:>7}] {pin['id']}  {pin['title']}\n          {prompt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
