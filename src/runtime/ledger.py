"""Decisions-ledger runtime — the one implementation both skills bind to.

Schema authority: `core/decisions-ledger-spec.md` (v0.9). This module materializes the
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
  decided `depends_on` dependents (transitively), nothing else;
- v0.7 `correctness_unknown` + the `verification` envelope: when a claim states how hard it
  was checked, that statement binds — `resolved` requires the `observed` rung, so a pin whose
  correctness could not be established lands in an honest state instead of a green close;
- v0.9 one closed failure vocabulary (`FAILURE_CLASSES`, a strict superset of the challenge
  classes) used by the challenger's premortem *before* the work and by `label_failure` *after*
  it, so "what we feared" and "what happened" are comparable instead of two prose piles.

On-disk form: one `ledger.json` (portable, git-versionable) written atomically.
The target codebase's ledger lives in *that* repo's audit output dir — never in this one.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = "0.9"

# Every version this code can read. The spec has only ever grown by addition — a new `kind`, a new
# event, a new state — so a ledger written by an older runtime is still valid input, and rejecting it
# would strand the one artifact the whole package treats as durable truth. Reading an older file
# upgrades its `version` in memory; the upgrade lands on disk at the next `save()`.
READABLE_VERSIONS = ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9")

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
STATES = (
    "detected", "needs_input", "brainstorming", "decided",
    "correctness_unknown",  # v0.7 — work done, correctness NOT establishable from available evidence
    "deferred", "resolved", "accepted",
)
DETERMINISM = ("D0", "D1", "D2")                                  # v0.7 — how a result reproduces
VERIFICATION_RUNGS = ("self_check", "re_read", "observed", "cross_derived")  # v0.7 — how hard checked
READINESS_VERDICTS = ("ready", "harden_first", "redesign")        # v0.8 — can the ground bear it?
RESOLUTION_MODES = ("asked", "policy_default", "proposed_default")
CHALLENGE_CLASSES = (
    "unfalsifiable", "inconsistent", "unsatisfiable", "unfounded_infeasibility",
    "unstated_assumption", "ignored_fanout", "other",
)
CHALLENGE_TARGETS = ("acceptance_criterion", "to_be", "policy", "decision")

# v0.9 — ONE closed vocabulary for how work fails, shared by the prospective premortem, the
# retrospective label, and recovery. It is a strict superset of CHALLENGE_CLASSES rather than a
# second list beside it: a challenge is a failure mode of the *oracle*, foreseen before the work,
# so the words must be the same words. Two vocabularies for one concept is precisely the divergence
# this package exists to find — `test_failure_taxonomy_contains_the_challenge_classes` holds it shut.
FAILURE_CLASSES = CHALLENGE_CLASSES + (
    "contract_drift",      # layers disagreed about a shape — this package's own thesis
    "missing_capability",  # the work needed something that does not exist (tool, API, fixture)
    "environment",         # toolchain, runtime, network, permission — outside the code
    "untested_path",       # the change hit a path nothing exercised
    "scope_creep",         # the work exceeded its declared boundary
    "stale_carrier",       # a trusted artifact (graph, doc, lockfile, cache) described a dead state
    "nondeterminism",      # the outcome did not reproduce — flake, ordering, time, concurrency
    "external_change",     # a third party moved: dependency, upstream API, remote repo
)
FAILURE_PHASES = ("plan", "build", "evidence", "review", "production")
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
            found = self.data.get("version")
            _require(found in READABLE_VERSIONS,
                     f"ledger schema {found!r} is not readable by this runtime "
                     f"(known: {', '.join(READABLE_VERSIONS)})")
            self.data["version"] = SCHEMA_VERSION
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

    # -- governance (v0.9) ---------------------------------------------------

    def set_governance(self, record: Optional[dict]) -> Optional[dict]:
        """Pin which rules are in force. Every event appended afterwards carries its `policy_hash`.

        Built by `governance.record(...)` over the roster, the permission table, the spec version and
        the skill version. Changing any of them changes the hash, so a widened permission becomes a
        visible delta in the trail instead of an invisible change of meaning.
        """
        self.data["governance"] = record
        return record

    def _policy_hash(self) -> Optional[str]:
        """The hash in force, or None. `None` is written explicitly onto every event: an ungoverned
        decision must read as ungoverned, and an absent field would read as fine."""
        return (self.data.get("governance") or {}).get("policy_hash")

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
        """The brainstorm writes proposals[] with tradeoffs — it can never decide.

        A proposal may be marked `recommended` (v0.9). Recommending is what a brainstorm is *for*;
        deciding is what it may never do, and the neutrality check below is unchanged. At most one,
        because the whole value of the mark is that it becomes comparable to what the human then
        elects — the gap between the two is the single best learning signal in the ledger, and two
        recommendations make it uncomputable (`runtime/learning.py`).
        """
        pin = self.pin(pin_id)
        _require(sum(1 for p in proposals if p.get("recommended")) <= 1,
                 "at most one proposal may be `recommended` — two make the recommendation "
                 "uncomparable to what the human elects, which is the point of marking it")
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
                "policy_hash": self._policy_hash(),
            }
            if flip_signal is not None:
                event["flip_signal"] = dict(flip_signal)
            self.data["decision_log"].append(event)
            target["state"] = "decided"
            target.pop("substate", None)
            target["decision"] = {"event_id": event["id"], "outcome": outcome}
            events.append(event)
        return events

    def set_readiness(
        self,
        pin_id: str,
        verdict: str,
        zone: dict,
        evidence: dict,
        hardens: Optional[list] = None,
        rationale: str = "",
    ) -> dict:
        """v0.8 — record the landing-zone verdict, and wire the hardening prerequisites.

        The premortem of the *terrain*, not of the plan: can the code this change lands on bear it?
        The evidence is D0 (graph, git, ledger); the verdict is D2 (judgment over that evidence) and
        is stored saying so, because a threshold invented here would be a number with no carrier.

        `harden_first` means the prerequisite work **blocks** the change: the hardening pins join
        `depends_on`, so the existing wave scheduler orders them first with no new mechanism, and
        the existing rule that only `resolved`/`accepted` close an edge means the change cannot
        start until the ground is actually fixed.
        """
        pin = self.pin(pin_id)
        _require(verdict in READINESS_VERDICTS, f"verdict must be one of {READINESS_VERDICTS}")
        zone_files = {f for f in (zone or {}).get("files", [])}
        _require(bool(zone_files), "a readiness verdict needs a zone — assess before concluding")
        hardens = [str(h) for h in (hardens or [])]
        if verdict == "harden_first":
            _require(bool(hardens),
                     "harden_first without prerequisites is a worry, not a verdict — name the pins "
                     "that must land first")
        else:
            _require(not hardens, f"only harden_first carries prerequisites, not {verdict!r}")

        by_id = {p["id"]: p for p in self.data["pins"]}
        for h in hardens:
            _require(h != pin_id, "a pin cannot harden itself")
            _require(h in by_id, f"no pin {h}")
            # CHANGE-JUSTIFIED, enforced rather than promised: remediation is admitted only when it
            # reduces *this* change's risk. A pin whose anchors lie outside the landing zone is
            # someone else's cleanup, and admitting it is how a bounded gate becomes a rewrite.
            anchors = [(a.get("loc") or "").split(":")[0] for a in by_id[h].get("anchors", [])]
            _require(any(a in zone_files for a in anchors if a),
                     f"{h} anchors outside the landing zone — hardening must be justified by THIS "
                     "change, not by the code being imperfect elsewhere")
            _require(not self._reaches(h, pin_id, by_id),
                     f"{h} already depends on {pin_id} — hardening it here would close a cycle")
            if h not in pin["depends_on"]:
                pin["depends_on"].append(h)

        pin["readiness"] = {
            "verdict": verdict,
            "determinism": "D2",           # the verdict is judgment...
            "evidence_determinism": "D0",  # ...over deterministic evidence. Never merged.
            "zone": {"files": sorted(zone_files), "nodes": len(zone.get("nodes", []))},
            "evidence": evidence,
            "hardens": hardens,
            "rationale": rationale,
        }
        return pin

    @staticmethod
    def _reaches(start: str, target: str, by_id: dict) -> bool:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            if cur in seen or cur not in by_id:
                continue
            seen.add(cur)
            stack.extend(by_id[cur].get("depends_on", []))
        return False

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
            "policy_hash": self._policy_hash(),
        }
        self.data["decision_log"].append(event)
        if upheld:
            self._reopen_minimal(pin, substate="challenged")
        return event

    def premortem(
        self,
        pin_id: str,
        failure_modes: list[dict],
        guardrails: Optional[list] = None,
        abort_criteria: Optional[list] = None,
        paper_tigers: Optional[list[dict]] = None,
        source: str = "challenge:challenger",
    ) -> dict:
        """v0.9 — the challenger's SECOND mode: assume the plan already failed, work backwards.

        The first mode refutes the oracle (*is the criterion sound?*); this one grants the criterion
        and asks how the work dies anyway. Same read-only role, same neutrality — it writes
        guardrails and abort criteria, never a decision and never a state change. The roster stays
        at six because this is a mode, not a member.

        Two rules keep it from becoming a worry list:
        - a premortem that names failures and no response is not a premortem, so at least one
          guardrail or abort criterion is required;
        - a `paper_tiger` (a risk that looks grave and is already mitigated) must carry the
          **evidence** of its mitigation. Without that it is not a dismissed risk, it is a risk
          somebody decided to feel calm about — and the field would become the noise it exists
          to remove.
        """
        pin = self.pin(pin_id)
        _require(isinstance(failure_modes, list) and bool(failure_modes),
                 "a premortem needs at least one failure mode — 'nothing will go wrong' is the "
                 "belief the exercise exists to break")
        for fm in failure_modes:
            _require(isinstance(fm, dict), "each failure mode must be an object")
            _require(fm.get("class") in FAILURE_CLASSES,
                     f"failure mode class must be one of {FAILURE_CLASSES}")
            _require(fm.get("class") != "other" or bool(fm.get("detail")),
                     "class 'other' requires detail (the open escape hatch is named, not blank)")
            _require(bool(str(fm.get("description", "")).strip()),
                     "each failure mode needs a description of how it kills the work")
        guardrails = [str(g) for g in (guardrails or []) if str(g).strip()]
        abort_criteria = [str(a) for a in (abort_criteria or []) if str(a).strip()]
        _require(bool(guardrails or abort_criteria),
                 "name at least one guardrail or abort criterion — failures without responses "
                 "are a worry list, not a premortem")
        tigers = []
        for pt in paper_tigers or []:
            _require(isinstance(pt, dict) and bool(str(pt.get("risk", "")).strip()),
                     "each paper_tiger needs the risk it names")
            _require(bool(str(pt.get("evidence", "")).strip()),
                     "a paper_tiger needs the EVIDENCE that it is already mitigated — without it "
                     "this is not a dismissed risk, it is an ignored one")
            tigers.append({"risk": str(pt["risk"]), "evidence": str(pt["evidence"])})
        pin["premortem"] = {
            "failure_modes": failure_modes,
            "guardrails": guardrails,
            "abort_criteria": abort_criteria,
            "paper_tigers": tigers,
            "determinism": "D2",     # imagining how it dies is judgment, and says so
            "source": source,
            "timestamp": _now(),
        }
        return pin["premortem"]

    def cross_derive(self, pin_id: str, claim: str, derivations: list[dict],
                     agreement: str, notes: str = "") -> dict:
        """v0.9 — the `cross_derived` rung: the same claim re-derived by a DIFFERENT provider.

        A single-provider hallucination is stubborn under repetition and fragile under substitution:
        ask the same model twice and it reproduces its own error, ask a different family and it
        rarely invents the same wrong thing. So agreement is a genuine strengthening and
        **disagreement is the signal**, not a nuisance to average away.

        What is deterministic here is narrow and checked: at least two derivations, and at least two
        **distinct providers** — two runs of one model are a repetition wearing an independence
        badge. Whether two answers *mean* the same thing is judgment, so `agreement` is supplied by
        the caller and stored as the D2 it is.

        Divergence does not silently mark the pin weaker: it moves it to `needs_input`
        (`contested`), because a claim two independent derivations disagree about is exactly the one
        a human must look at. It does **not** cascade to dependents the way an upheld challenge
        does — nobody yet knows which side is wrong, and reopening the neighbourhood on an unresolved
        disagreement would be churn, not caution.

        Deliberately not mandatory at any severity: making it obligatory above a threshold doubles
        the cost of the most expensive pins, and that trade should be elected with a measured number
        in hand rather than assumed here.
        """
        pin = self.pin(pin_id)
        _require(agreement in ("agree", "disagree", "partial"),
                 "agreement must be agree | disagree | partial")
        _require(bool(str(claim).strip()), "name the claim being re-derived")
        derivations = list(derivations or [])
        _require(len(derivations) >= 2,
                 "cross-derivation needs at least two derivations — one is just the original claim")
        for d in derivations:
            _require(isinstance(d, dict), "each derivation must be an object")
            for field in ("provider", "model", "result"):
                _require(bool(str(d.get(field, "")).strip()),
                         f"each derivation needs a non-blank {field}")
        providers = {str(d["provider"]).strip().lower() for d in derivations}
        _require(len(providers) >= 2,
                 "at least two DISTINCT providers — re-running one model reproduces its own error, "
                 "so same-provider repetition is not independent evidence "
                 "(see core/model-tiers.md, profile D)")
        record = {
            "claim": str(claim).strip(),
            "derivations": derivations,
            "providers": sorted(providers),
            "agreement": agreement,
            "agreement_determinism": "D2",   # 'do these mean the same thing' is judgment
            "independence_determinism": "D0",  # 'were the providers distinct' is checked
            "notes": notes,
            "timestamp": _now(),
        }
        pin.setdefault("cross_derivations", []).append(record)
        if agreement == "agree":
            verification = pin.get("verification") or {}
            verification["rung"] = "cross_derived"
            verification["cross_derived_by"] = sorted(providers)
            pin["verification"] = verification
        elif pin["state"] != "accepted":
            pin["question"] = {
                "prompt": (f"Two independent providers disagree on: {record['claim']}. "
                           "Which derivation holds?"),
                "options": [{"id": f"d{i}", "label": f"{d['provider']}/{d['model']}: {d['result']}"}
                            for i, d in enumerate(derivations)]
                           + [{"id": "neither", "label": "Neither — the claim itself is wrong"}],
                "allow_freeform": True,
            }
            pin["state"] = "needs_input"
            pin["substate"] = "contested"
            pin["resolution_mode"] = "asked"   # a contested claim is never re-defaulted silently
        return record

    def label_failure(self, pin_id: str, failure_class: str, detail: str,
                      phase: str, source: str = "measurer") -> dict:
        """v0.9 — label a failure that ACTUALLY happened, in the same words the premortem used.

        Appends an immutable FailureEvent. It changes no state: labeling is observation, and the
        response (reopen, challenge, re-plan) stays a separate, explicit act. Sharing the vocabulary
        with the premortem is the whole point — it is what lets 'what we feared' and 'what happened'
        be compared at all, instead of being two prose piles nobody can join.
        """
        self.pin(pin_id)
        _require(failure_class in FAILURE_CLASSES, f"class must be one of {FAILURE_CLASSES}")
        _require(failure_class != "other" or bool(detail),
                 "class 'other' requires detail (the open escape hatch is named, not blank)")
        _require(phase in FAILURE_PHASES, f"phase must be one of {FAILURE_PHASES}")
        _require(bool(str(detail).strip()), "a failure label needs what actually happened")
        event = {
            "id": self._next_id("fal_", self.data["decision_log"]),
            "pin_id": pin_id,
            "timestamp": _now(),
            "class": failure_class,
            "detail": str(detail).strip(),
            "phase": phase,
            "source": source,
            "policy_hash": self._policy_hash(),
        }
        self.data["decision_log"].append(event)
        return event

    def foresight(self, pin_id: str) -> dict:
        """What was feared vs what happened, joined on the shared vocabulary.

        `anticipated` are classes the premortem named and that then occurred; `surprises` are classes
        that occurred and nobody foresaw; `paper_tigers_held` are dismissed risks that stayed
        dismissed. D0 — a set comparison over recorded events, no scoring: the numbers are small,
        rare and human, and a rate computed over them would be a statistic with no population.
        """
        pin = self.pin(pin_id)
        foreseen = {fm.get("class") for fm in (pin.get("premortem") or {}).get("failure_modes", [])}
        happened = [e for e in self.data["decision_log"]
                    if e.get("pin_id") == pin_id and e["id"].startswith("fal_")]
        occurred = {e["class"] for e in happened}
        tigers = {pt["risk"] for pt in (pin.get("premortem") or {}).get("paper_tigers", [])}
        return {
            "pin": pin_id,
            "has_premortem": bool(pin.get("premortem")),
            "anticipated": sorted(foreseen & occurred),
            "unrealized": sorted(foreseen - occurred),
            "surprises": sorted(occurred - foreseen),
            "paper_tigers_named": sorted(tigers),
            "failures": happened,
            "determinism": "D0",
        }

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
            "policy_hash": self._policy_hash(),
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
                        contract_carrier: Optional[str] = None) -> dict:
        """RemediationItem (rescue verbs) or BuildItem (greenfield verbs, build_track set).

        **No item-level `depends_on`.** Ordering lives one level up, on the pin, and only there:
        `add_pin(depends_on=...)` validates each id exists, and `buildloop.waves()` levels *pins* by
        it. Items are worked in list order within their pin (`buildloop.next_item`), which is enough
        because the executor takes one scope at a time — so a second ordering channel would have
        nothing to say that this one cannot.

        The field used to exist and was inert three ways: ids were allocated per-pin
        (`rem_0001` on every pin, so a cross-pin reference was ambiguous by construction), nothing
        validated them, and no line of the runtime ever read them. Kept out rather than repaired: a
        parameter that accepts anything and changes nothing is worse than its absence, because it
        reads as a capability.
        """
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

    def resolve(self, pin_id: str, evidence: Optional[str] = None) -> dict:
        pin = self.pin(pin_id)
        _require(pin["state"] == "decided" or pin["kind"] == "defect",
                 "only a decided pin (or a defect) can resolve")
        _require(all(i["status"] == "done" for i in pin["remediation"]),
                 "resolve requires every remediation item done")
        _require(len(pin["remediation"]) > 0,
                 "resolve without remediation is a silent close — record what closed the gap")
        # v0.6 'resolved = observed': the evidence is what was OBSERVED to close the gap,
        # not merely that the code was written.
        if evidence is not None:
            _require(bool(str(evidence).strip()), "evidence, when given, must not be blank")
            pin["evidence"] = evidence
        # v0.7: when the pin states how hard its claim was checked, that statement binds. A pin
        # verified only by the agent re-reading its own output has not been observed, and `resolved`
        # means observed — so the honest destination is `correctness_unknown`, not a green close.
        rung = (pin.get("verification") or {}).get("rung")
        if rung is not None:
            _require(rung in ("observed", "cross_derived"),
                     f"resolve needs rung 'observed' or 'cross_derived', not {rung!r} — a claim "
                     "checked only by self-check or re-read belongs in correctness_unknown")
        pin["state"] = "resolved"
        return pin

    def mark_correctness_unknown(
        self,
        pin_id: str,
        blocked_by: str,
        attempted: Optional[list] = None,
        determinism: Optional[str] = None,
        rung: Optional[str] = None,
    ) -> dict:
        """v0.7 — the work was done and correctness could NOT be established.

        Not a failure and not a defect: the honest report of a missing oracle. It is legitimate only
        after the evidence stack was actually walked (tests -> static checks -> smoke probe ->
        diff-risk review), which is why `attempted` and `blocked_by` are recorded rather than
        optional decoration. The state blocks closure; the next move is an explicit decision.
        """
        pin = self.pin(pin_id)
        _require(pin["state"] in ("decided", "resolved") or pin["kind"] == "defect",
                 "correctness_unknown applies to work that was actually done")
        _require(bool(str(blocked_by).strip()),
                 "correctness_unknown must say what blocked verification — an unexplained unknown "
                 "is the confident report wearing a humble label")
        attempted = list(attempted or [])
        _require(bool(attempted),
                 "record the evidence stack that was walked (tests, typecheck, smoke_probe, "
                 "diff_review) — reaching for this state without trying is a shrug, not a finding")
        if determinism is not None:
            _require(determinism in DETERMINISM, f"determinism must be one of {DETERMINISM}")
        if rung is not None:
            _require(rung in VERIFICATION_RUNGS, f"rung must be one of {VERIFICATION_RUNGS}")
        pin["verification"] = {
            "determinism": determinism,
            "rung": rung,
            "attempted": attempted,
            "blocked_by": str(blocked_by).strip(),
        }
        # The state forces an explicit next move, so it carries the fork that asks for one. Without
        # this the pin would block closure while asking nobody anything — the original question is
        # already answered (its DecisionEvent is in the immutable log); this is the live one.
        pin["question"] = {
            "prompt": (f"Correctness could not be established: {pin['verification']['blocked_by']}. "
                       "What now?"),
            "options": [
                {"id": "retry", "label": "Retry with more context"},
                {"id": "add_check", "label": "Add the missing check first",
                 "implication": "a new acceptance_criterion — the zone earns verifiability"},
                {"id": "takeover", "label": "Manual takeover"},
                {"id": "narrow", "label": "Narrow the scope to what IS verifiable"},
                {"id": "accept", "label": "Accept the risk, unknown named",
                 "implication": "state becomes accepted, with the unverified remainder recorded"},
            ],
            "allow_freeform": True,
        }
        pin["resolution_mode"] = "asked" if pin["severity"] in _NEVER_SILENT \
            else pin.get("resolution_mode", "asked")
        pin["state"] = "correctness_unknown"
        return pin

    # -- views (the surfaces hold no state of their own) ------------------------

    def interview_view(self) -> list[dict]:
        """The interview IS the filtered view of pins awaiting a human answer, ordered by
        information gain: the ones that collapse the most downstream pins come first.

        Two states await an answer, for different reasons. `needs_input` means the decision has not
        been made. `correctness_unknown` (v0.7) means the decision was made and *verification*
        failed — the pin needs a next-move answer, not a re-election. Both belong here: a state that
        blocks closure and appears on no surface is a black hole, and the pin most likely to be
        forgotten is exactly the one nobody could verify.
        """
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

        pending = [p for p in self.data["pins"]
                   if p["state"] in ("needs_input", "correctness_unknown")]
        sev_rank = {s: i for i, s in enumerate(SEVERITIES)}
        # An unverifiable blocker outranks information gain. Fan-out orders questions that are still
        # open; a `blocker|high` whose correctness could not be established is not a question to
        # sequence well, it is one that must not be skimmed past (the v0.3 threshold rule applied to
        # the verification exit).
        def unverifiable_first(p: dict) -> int:
            return 0 if (p["state"] == "correctness_unknown"
                         and p["severity"] in _NEVER_SILENT) else 1
        return sorted(
            pending,
            key=lambda p: (unverifiable_first(p), -transitive(p["id"]),
                           sev_rank[p["severity"]], p["id"]),
        )

    def summary(self) -> dict:
        by_state: dict[str, int] = {}
        for p in self.data["pins"]:
            by_state[p["state"]] = by_state.get(p["state"], 0) + 1
        # v0.9: failures surface here or they surface nowhere. An event class that only exists in
        # the log is the same black hole `correctness_unknown` was before it reached the interview.
        by_failure: dict[str, int] = {}
        for e in self.data["decision_log"]:
            if e["id"].startswith("fal_"):
                by_failure[e["class"]] = by_failure.get(e["class"], 0) + 1
        return {
            "version": self.data["version"],
            "pins": len(self.data["pins"]),
            "by_state": by_state,
            "events": len(self.data["decision_log"]),
            "policies": len(self.data["policies"]),
            "open_questions": len(self.interview_view()),
            "failures_by_class": by_failure,
            "premortems": sum(1 for p in self.data["pins"] if p.get("premortem")),
        }


def _json_arg(raw: Optional[str], field: str) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--{field}: invalid JSON ({exc})")
