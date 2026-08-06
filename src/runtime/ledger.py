"""Decisions-ledger runtime — the one implementation both skills bind to.

Schema authority: `core/decisions-ledger-spec.md` (v0.15). This module materializes the
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
  it, so "what we feared" and "what happened" are comparable instead of two prose piles;
- v0.11 `cascaded` — a policy-cascaded DecisionEvent names its own rung and the `Policy` that
  produced it, instead of taking the `transcribed` default and claiming a relay nobody made;
- v0.12 the cascade is held to the offered-options rule the single-pin door already held: a pin
  whose own `question` does not offer the policy's `default_outcome` is held back, not decided on
  a value nobody offered it — and a policy cascades ONCE, over the radius its elector was shown;
- v0.13 those rules bind at the WRITE, so a file written earlier does not satisfy them. Two
  consequences, both handled here rather than at each surface: the rung of a pre-v0.11 cascade is
  READ from the carrier its writer left (`decision_rung`), and the `version` stamp does not rise
  above what the file's own content conforms to (`nonconforming`). Nothing in the log is rewritten;
- v0.14 those rules live in ONE predicate instead of in one door. Every write that settles a pin
  whose own question was never put to the human — the policy cascade, the brief — goes through
  `unasked_verdict`, and `decide()` no longer fans out over a cluster at all, so one human answer
  can no longer become four DecisionEvents without a `Policy` to carry the election;
- v0.15 the same move for the v0.13 reader: the write-time rules an event can be judged by live in
  ONE table (`EVENT_RULES`), which `decide()` validates a new event against and `nonconforming`
  replays over an old one — so a rule added later gains its reader by construction instead of
  being false of every existing file until somebody remembers. And an elected `Policy` is visible
  as a decision on all three surfaces even when it cascaded over no pin at all.

On-disk form: one `ledger.json` (portable, git-versionable) written atomically.
The target codebase's ledger lives in *that* repo's audit output dir — never in this one.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = "0.15"

# Every version this code can read. The spec has only ever grown by addition — a new `kind`, a new
# event, a new state — so a ledger written by an older runtime is still valid input, and rejecting it
# would strand the one artifact the whole package treats as durable truth. Reading an older file
# raises its `version` in memory ONLY when its content conforms to the newer rules (`nonconforming`);
# the raise lands on disk at the next `save()`.
#
# "0.10" is absent because no runtime ever wrote it: the spec bumped to v0.10 and this constant did
# not follow, so every ledger on disk from that period says "0.9". That drift was not cosmetic —
# `tools._governance_record` stamps SCHEMA_VERSION as the `spec_version` component of `policy_hash`,
# so a spec change that leaves it alone is a rule change the trail cannot show. Hence the jump.
READABLE_VERSIONS = ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.11", "0.12", "0.13",
                     "0.14", "0.15")

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

# How the human's answer reached the DecisionEvent. Not a confidence score — four different
# failure modes, kept apart so a reader can weigh them (see `Ledger.decide`).
DECISION_EVIDENCE = ("elicited", "transcribed", "brief", "cascaded")

# How a human's election reached a `Policy`. The same rungs minus `cascaded`: a policy is elected,
# never derived from another policy, so that rung has no meaning here and is refused rather than
# silently tolerated.
POLICY_EVIDENCE = ("elicited", "transcribed", "brief")

# severities that must never be silently defaulted (the threshold rule, v0.3)
_NEVER_SILENT = ("blocker", "high")

# A pin these states describe is not open to being settled again by anyone.
SETTLED_STATES = ("decided", "resolved", "accepted", "deferred")

# What `Ledger.unasked_verdict` can answer, and therefore the buckets every radius over it reports
# (v0.14). Ordered so a caller can present them the way a human reads them: what it decides first,
# then the two refusals, then the pins that were never in scope. `policy_preview` builds its return
# shape from this tuple, so adding a bucket cannot leave one surface reporting four and another five.
UNASKED_BUCKETS = ("would_decide", "held_back", "not_offered", "excepted", "already_settled")


class LedgerError(ValueError):
    """A spec rule was violated."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise LedgerError(msg)


# -- reading events an older runtime wrote (v0.13) --------------------------------------------
#
# `decide()` has required `source` to be `"interview"` or `"policy:<id>"` at every version of this
# schema, and `apply_policy` is the only writer of the second form. So a `policy:` source IS a
# cascade, in any file this runtime can open — which makes it the carrier to read when the newer,
# explicit fields are absent. `policy_id` (v0.11) is what a surface should JOIN on; this is what
# says whether there is anything to join.
_POLICY_SOURCE = "policy:"


def cascaded_from(event: dict) -> Optional[str]:
    """The `Policy` id this DecisionEvent was cascaded from, or None."""
    explicit = event.get("policy_id")
    if explicit:
        return str(explicit)
    source = str(event.get("source") or "")
    if not source.startswith(_POLICY_SOURCE):
        return None
    return source[len(_POLICY_SOURCE):] or None


def decision_rung(event: dict) -> str:
    """How this decision's answer reached the log — read, not taken on the event's word. `""` if
    the file records none.

    The two disagree for exactly one population, and it is not hypothetical. Before v0.11 the
    cascade called `decide()` with no `evidence`, so the parameter default `transcribed` landed on
    disk for an answer nobody relayed. v0.11 fixed the WRITE; every ledger written before it still
    says `transcribed`, and every surface faithfully repeated *"an agent relayed what the user
    said — ⚠ relayed with no quote"* over the user's own elected policy. A rule enforced only at
    the write governs no file that already exists.

    So the rung is read from the strongest carrier the event actually has. Nothing is rewritten:
    the log is immutable, the event keeps the bytes its writer wrote, and the three surfaces stop
    describing a cascade as a relay. Where the read differs from the record, the surface that
    weighs it says so (the map's card names the recorded value); a count does not, because
    "cascaded" is what happened.
    """
    if cascaded_from(event):
        return "cascaded"
    return str(event.get("evidence") or "")


# -- the rules a DecisionEvent carries on its own (v0.15) --------------------------------------
#
# One table, two callers, and that is the whole point. `decide()` runs it over the very dict it is
# about to append; `nonconforming` runs it over every event already on a file. Before v0.15 the
# writer held six rules as inline `_require` calls and the reader knew ONE of them by hand — so
# "a rule enforced at the write governs no file that already exists" (v0.13) was fixed for the one
# rule somebody remembered to teach the reader, and a rule added later would be false of every
# existing ledger with nothing to say so. Now a rule added here gains its reader by construction,
# and the repo's invariant suite fails if `decide` grows a rule outside this table.
#
# Membership is decided by ONE question: **is the violation decidable from the stored event alone?**
# That is why the table holds `decide`'s checks and not `record_decision`'s quote rule (which is
# about who was asked, at a boundary the event does not record) and not the v0.12 offered-options
# rule (which needs the pin's `question` — mutable, and possibly edited long after the decision, so
# an option missing today does not prove it was missing then). Holding a file below its floor on
# evidence that weak would be the same false claim pointing the other way.
#
# Each entry is `(name, holds(event) -> bool, message(event) -> str)`. The name is what
# `pre_rule_events` reports, so it names the RULE, never the symptom.
EVENT_RULES = (
    ("committing_source",
     lambda e: str(e.get("source") or "") == "interview"
     or str(e.get("source") or "").startswith(_POLICY_SOURCE),
     lambda e: "only the interview (or a user-set policy cascade) commits; "
               f"got {e.get('source')!r}"),
    ("evidence_rung",
     lambda e: e.get("evidence") in DECISION_EVIDENCE,
     lambda e: f"evidence must be one of {DECISION_EVIDENCE}; got {e.get('evidence')!r}"),
    ("cascade_rung",
     lambda e: (e.get("evidence") == "cascaded")
     == str(e.get("source") or "").startswith(_POLICY_SOURCE),
     lambda e: "`cascaded` is the rung of a policy cascade and of nothing else: a policy-sourced "
               "event must carry it, and a directly-answered one must not "
               f"(source={e.get('source')!r}, evidence={e.get('evidence')!r})"),
    ("cascade_policy_id",
     lambda e: (e.get("evidence") == "cascaded") == bool(e.get("policy_id")),
     lambda e: "a cascaded decision must name the policy it derives from, and only a cascaded one "
               "may name one — otherwise the rung says a policy decided this and nothing says "
               "which, or a field points at a policy that decided nothing"),
    ("flip_criteria",
     lambda e: bool(e.get("flip_criteria")),
     lambda e: "flip_criteria is required — a decision without a reopen condition fossilizes"),
    ("flip_signal_source",
     lambda e: "flip_signal" not in e
     or (e.get("flip_signal") or {}).get("source") in FLIP_SIGNAL_SOURCES,
     lambda e: f"flip_signal.source must be one of {FLIP_SIGNAL_SOURCES}"),
)


def event_violations(event: dict) -> list:
    """The names of the `EVENT_RULES` this DecisionEvent does not satisfy, in table order."""
    return [name for name, holds, _ in EVENT_RULES if not holds(event)]


def _check_event(event: dict) -> None:
    """Refuse to write an event that breaks a rule — reporting the first, strongest one."""
    for name, holds, message in EVENT_RULES:
        _require(holds(event), message(event))


def nonconforming(data: dict) -> dict:
    """`rule -> [event ids]` for events a rule added AFTER they were written would refuse. `{}` for
    a file this runtime could have produced.

    This is what decides whether `version` may be raised. A stamp is a claim of conformance, and
    the load path used to raise it on any readable file with no backfill of any kind: a bare
    load+save turned a v0.9 ledger holding unrunged cascades into one *claiming* v0.12, whose
    invariants it did not satisfy and could not be made to satisfy without editing an append-only
    log. So the stamp is a floor — the newest rule set the file's own content conforms to — and it
    rises only when nothing is left behind.

    It replays `EVENT_RULES`, which is the same table `decide()` validates a new event against
    (v0.15) — so the answer to "which write-time rules does the floor know about" is *all of the
    ones an event can be judged by*, derived rather than remembered. It used to know exactly one,
    hand-copied, with nothing forcing the next rule to gain a reader; that is the v0.13 lesson
    applied to itself.

    The narrowness is unchanged and is the table's own membership rule: only violations decidable
    **from the event alone**. See `EVENT_RULES` for what that excludes and why.
    """
    out: dict = {}
    for event in data.get("decision_log") or []:
        if not str(event.get("id") or "").startswith("ev_"):
            continue
        for rule in event_violations(event):
            out.setdefault(rule, []).append(str(event.get("id")))
    return out


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
            # The stamp is a claim, so it is earned rather than applied. A file holding an event a
            # later rule would refuse keeps the version it was written under; raising it would make
            # this file assert invariants its own content does not satisfy, which is the failure
            # this package exists to find. Reported by `summary()`, so the refusal is visible and
            # not merely correct.
            self.pre_rule = nonconforming(self.data)
            if not self.pre_rule:
                self.data["version"] = SCHEMA_VERSION
        else:
            self.data = {"version": SCHEMA_VERSION, "pins": [], "decision_log": [], "policies": []}
            self.pre_rule = {}

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
        evidence: str = "transcribed",
        human_answer: str = "",
        policy_id: Optional[str] = None,
    ) -> dict:
        """Append ONE DecisionEvent for ONE pin and materialize its state (last committed wins).

        One pin, and that is now structural (v0.14). It used to take `apply_to_cluster`, and with it
        one call wrote the same outcome — and the same `human_answer` — onto every pin sharing the
        `cluster_id`, with no filter of any kind: a pin offering a different option set, a pin posing
        no question at all, a `blocker`. The three rules the doors above enforce were bypassed by one
        boolean, and the reason is worth keeping rather than just the fix: **there is no rung for
        that write.** `elicited` and `transcribed` describe an answer given about THIS pin; a fan-out
        gives one answer about several, which is what `cascaded` means — and `cascaded` requires a
        `Policy` to point at, because the `Policy` is what carries the rule, the quote and the radius
        the human was shown. An honest cluster fan-out therefore IS a policy. It is
        `apply_policy`, reached through `mcp:ledger_record_policy`, and the funnel's "200 findings →
        one decision" runs there with a preview, a held-back list and a `not_offered` list.

        Returns the event (a dict, not a list of one): a call that can write exactly one event should
        not have a return shape that suggests otherwise.

        Design decision 9: every decision carries flip_criteria. Neutrality: only
        `interview` or a user-set `policy:<id>` may commit — the brainstorm, the
        challenger, and the feedback loop cannot.

        `evidence` records HOW the human's answer reached this line, because `source: interview`
        only says who is *entitled* to commit and every writer can claim it. The rungs differ in
        what could have gone wrong, so they are kept apart instead of averaged:

          * `elicited` — the server asked the user through the host and wrote the reply itself. The
            agent never carried the value, so it could not have invented it.
          * `transcribed` — an agent relayed what the user said, recorded verbatim in
            `human_answer`. Weaker: honest relay and confabulation look identical here.
          * `brief` — pre-decided in the project brief at frame time; the brief is the evidence.
          * `cascaded` — derived from a `Policy` the user elected (v0.11). The answer reached the
            log ONCE, at the policy election, and this event is an amplification of it; the
            `Policy` named by `policy_id` carries its own rung and quote. Its failure mode is
            neither invention nor mis-relay but **fit**: the policy may not suit this pin.

        It defaults to `transcribed`, the WEAKER rung, deliberately: a caller that says nothing has
        not earned the strong claim, and the safe direction to be wrong in is understating what is
        known. Only the elicitation path may pass `elicited`, and it is the only caller that does.

        `cascaded` and a `policy:` source imply each other, checked both ways. Before v0.11 a cascade
        took the `transcribed` default, so `apply_policy` wrote "an agent relayed what the user
        said" onto a decision nobody relayed, and every surface repeated it. The alternative — each
        surface sniffing `source` for a `policy:` prefix — is string-parsing where an explicit field
        is available, which this package forbids elsewhere and would not survive here either.

        That check binds this write and no file that already exists, which is why the read side has
        `decision_rung` (v0.13): for a ledger written before v0.11 the `policy:` source is the only
        carrier there is, so it is read there — once, here in the library, not sniffed by each
        surface.

        And every rule named above lives in `EVENT_RULES` rather than in this function (v0.15), so
        the reader that decides whether an OLDER file satisfies them (`nonconforming`) replays the
        same table instead of knowing one of them by hand.
        """
        # The "a transcribed decision must quote the human" rule is enforced one layer out, in
        # `mcp/tools.py::record_decision`, because that is the only boundary an AGENT can reach and
        # so the only place the claim is actually made. Enforcing it here as well would tax the
        # library's own callers — `expand_catalog`, `accept`, the tests — for a risk none of them
        # carry. It is also, for the same reason, not an `EVENT_RULES` entry: the event records the
        # quote, never whether one was owed.
        pin = self.pin(pin_id)
        event = {
            "id": self._next_id("ev_", self.data["decision_log"]),
            "pin_id": pin["id"],
            "timestamp": _now(),
            "outcome": outcome,
            "rationale": rationale,
            "flip_criteria": flip_criteria,
            "source": source,
            "evidence": evidence,
            "policy_hash": self._policy_hash(),
        }
        if policy_id:
            event["policy_id"] = policy_id
        if human_answer:
            event["human_answer"] = human_answer
        if flip_signal is not None:
            event["flip_signal"] = dict(flip_signal)
        # Validated as the dict it will be, not as the arguments it came from (v0.15): the reader
        # (`nonconforming`) only ever sees the dict, so a rule checked on anything else is a rule
        # the reader cannot replay. Nothing is appended if this raises.
        _check_event(event)
        self.data["decision_log"].append(event)
        pin["state"] = "decided"
        pin.pop("substate", None)
        pin["decision"] = {"event_id": event["id"], "outcome": outcome}
        return event

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

    def accept(self, pin_id: str, rationale: str, flip_criteria: str,
               evidence: str = "transcribed", human_answer: str = "") -> dict:
        """Leave-as-is: the legitimate default resolution of a design_concern only."""
        pin = self.pin(pin_id)
        _require(pin["kind"] == "design_concern",
                 "accepted applies to design_concern only (open_decision has nothing to keep)")
        self.decide(pin_id, outcome="keep", rationale=rationale, flip_criteria=flip_criteria,
                    evidence=evidence, human_answer=human_answer)
        pin["state"] = "accepted"
        return pin

    # -- policies (v0.3: user decisions, amplified) ---------------------------

    def add_policy(self, applies_to: dict, rule: str, default_outcome: str,
                   exceptions: Optional[list[str]] = None,
                   evidence: str = "transcribed", human_answer: str = "") -> dict:
        """Record a policy the HUMAN elected. `evidence`/`human_answer` say how that election
        reached the log, exactly as they do on a `DecisionEvent` — and here they matter more, not
        less: a policy decides a whole cluster, so an unevidenced one is an agent deciding at scale.

        The rung is stored on the policy rather than repeated on each cascaded event: the answer
        travelled once, at this election, and every event it produces points back here by
        `policy_id`. Quoting is enforced one layer out, in `mcp/tools.py::record_policy`, for the
        same reason it is for `decide` — that is the only boundary an agent can reach.

        v0.12: `default_outcome` is an **option id**, and so a non-empty string. It used to be
        `Any`, and the cascade JSON-encoded anything else into the event's `outcome` — a blob no
        pin's question could ever have offered, which under the offered-options rule below would
        hold back every pin the policy was elected to decide. Refusing it here says that plainly
        instead of letting it look like a policy that decides nothing.
        """
        _require(evidence in POLICY_EVIDENCE,
                 f"policy evidence must be one of {POLICY_EVIDENCE}; got {evidence!r}")
        _require(isinstance(default_outcome, str) and default_outcome.strip(),
                 "default_outcome must be the option id each cascaded pin's own question offers — "
                 f"a non-empty string, not {type(default_outcome).__name__}")
        policy = {
            "id": self._next_id("pol_", self.data["policies"]),
            "applies_to": applies_to,
            "rule": rule,
            "default_outcome": default_outcome,
            "set_by": "interview",
            "exceptions": exceptions or [],
            "evidence": evidence,
        }
        if human_answer:
            policy["human_answer"] = human_answer
        self.data["policies"].append(policy)
        return policy

    @staticmethod
    def question_offers(pin: dict, outcome: str) -> bool:
        """Does THIS pin's own `question` offer this outcome? (v0.12)

        The carrier is `question.options[].id`, compared by equality — the same field
        `mcp/tools.py::record_decision` checks on the single-pin door, so both doors admit exactly
        the same set of outcomes for a given pin. Two things deliberately do NOT widen it:

          * **labels.** A label is prose written for a human to read; the id is what gets written.
          * **`allow_freeform`.** Freeform is legitimate on the single-pin path because there the
            human's own words ARE the outcome. A policy outcome is by construction not this pin's
            human's words — it is one sentence elected over a cluster — so reading `allow_freeform`
            as "any outcome may be cascaded here" would reopen the hole this closes, on every pin
            whose question happens to carry a freeform escape.

        A pin with no question offers nothing, which is the same answer `decision_prompt` already
        gives: a pin that poses no fork cannot be decided through the fork it does not pose.
        """
        return any(o.get("id") == outcome
                   for o in ((pin.get("question") or {}).get("options") or []))

    def unasked_verdict(self, pin: dict, outcome: str,
                        excepted: frozenset[str] = frozenset()) -> str:
        """**THE predicate.** May this outcome be written onto this pin, given that this pin's own
        question was never put to the human? Returns the bucket, one of `UNASKED_BUCKETS` (v0.14).

        Every write that settles a pin the human was not shown goes through exactly this call —
        the policy cascade (`apply_policy`, via `policy_preview`) and the project brief
        (`interview.expand_catalog`). It exists because the rule kept being implemented *per door*:
        v0.12 put the offered-options check on the policy door after finding it only on the
        single-pin door, and a reviewer then got the identical violation through two doors nobody had
        looked at — `decide(apply_to_cluster=True)` and `interview_expand(brief_decisions=...)`.
        A rule that lives in a door has to be remembered by every new caller, and one always does
        not; a rule that lives in a predicate is passed by construction, and this repo's invariant
        suite enumerates the callers of `decide` from the AST, so a new one that skips this fails.

        The two rules it composes are the funnel's, and neither is new:

          * **the severity threshold** — `blocker`/`high` are never *silently* defaulted
            (`core/interview-funnel.md` §5). Silence is the operative word and the reason this
            predicate is about being unasked rather than about writing: a blocker answered pin by pin
            through `record_decision` is exactly right, which is why that door does not call this.
          * **offered options** — `question_offers`, the same function and the same carrier
            (`question.options[].id`) the single-pin door checks. `allow_freeform` does not widen it
            here: freeform is legitimate where the human's own words ARE that pin's outcome, and by
            construction they are not, on a pin nobody put to them.

        Order matters and is asserted rather than assumed: settled and excepted first (those are not
        refusals, they are pins outside the radius), then the threshold, then the options. A reader
        asking "why is this pin still open" gets one reason, and the strongest one.
        """
        if pin["state"] in SETTLED_STATES:
            return "already_settled"
        if pin["id"] in excepted:
            return "excepted"
        if pin["severity"] in _NEVER_SILENT:
            return "held_back"          # threshold rule — never silent
        if not self.question_offers(pin, outcome):
            return "not_offered"        # offered-options rule — never invented
        return "would_decide"

    def policy_preview(self, applies_to: dict, default_outcome: str,
                       exceptions: Optional[list[str]] = None) -> dict:
        """What a policy with this scope and this outcome WOULD do, without doing it. Read-only.

        A policy is an election over a cluster, so the thing a human is being asked to elect is a
        blast radius — and it must be showable before the write, not discoverable after it. Same
        split as `decision_prompt` / `record_decision`: the thing that asks runs without the power
        to write.

        `apply_policy` calls this and cascades over exactly `would_decide`, so the preview cannot
        drift from the cascade — one matcher, two callers.

        `default_outcome` is a parameter and not optional (v0.12) because a pin is admitted to the
        cascade only if **its own question offers that outcome**; a preview computed without it
        would be a radius for a different policy than the one being elected. Pins that match the
        scope but do not offer it land in `not_offered` and stay open — held back exactly as
        `blocker`/`high` pins are, for a different reason that is named separately rather than
        merged into one bucket a reader cannot act on.

        v0.14: this is now only the SCOPE — which pins the policy matches. The per-pin judgment is
        `unasked_verdict`, shared with the brief, so the two cannot answer differently.
        """
        excepted = frozenset(exceptions or [])
        out: dict = {bucket: [] for bucket in UNASKED_BUCKETS}
        for pin in self.data["pins"]:
            if not all(pin.get(k) == v for k, v in applies_to.items()):
                continue
            out[self.unasked_verdict(pin, default_outcome, excepted)].append(pin["id"])
        return out

    def apply_policy(self, policy: dict) -> dict:
        """Cascade ONE policy — the one just elected — and report exactly what it did.

        Threshold rule (v0.3): blocker|high pins are never auto-resolved — they stay
        `asked` even when a policy matches; medium|low resolve as `policy_default`
        with a DecisionEvent whose source names the policy (user-originated, amplified)
        and whose rung is `cascaded` (v0.11), pointing back at the election by `policy_id`.

        Offered-options rule (v0.12): a matching pin whose own `question` does not offer
        `default_outcome` is held back too. The single-pin door has always refused an outcome the
        pin's question never offered; a policy decides MORE pins than a single decision does, so it
        cannot be governed less. Both rules are `unasked_verdict` (v0.14) — this method states them
        in prose and applies not one of them itself, which is what stops the prose and the write from
        drifting.

        One policy, not all of them (v0.12). This used to be `apply_policies()`, which re-ran every
        policy in the ledger on every call. Already-settled pins are skipped, so the only pins a
        re-run could ever touch were pins added SINCE that policy was elected — precisely the ones
        its elector was never shown. It also made the caller's report false: recording pol_0002
        returned the pins pol_0001 had just cascaded over as its own. What a human elects is the
        radius they were shown, so the cascade happens once, here, over that radius; pins that
        appear later are asked, or covered by a policy elected with them in view.

        Returns the radius it just applied — the same shape `policy_preview` returns, and by
        construction the same values, since it is that call.
        """
        radius = self.policy_preview(policy["applies_to"], policy["default_outcome"],
                                     policy["exceptions"])
        # never silent, for either reason: both stay open and go to the top of the review batch
        for pin_id in radius["held_back"] + radius["not_offered"]:
            self.pin(pin_id)["resolution_mode"] = "asked"
        for pin_id in radius["would_decide"]:
            pin = self.pin(pin_id)
            self.decide(
                pin_id,
                outcome=policy["default_outcome"],
                rationale=policy["rule"],
                flip_criteria=f"an exception to policy {policy['id']} surfaces",
                source=f"policy:{policy['id']}",
                evidence="cascaded",
                policy_id=policy["id"],
            )
            pin["resolution_mode"] = "policy_default"
        return radius

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
        # v0.10: the rung each decision reached. The summary is what an agent reads BEFORE acting, and
        # "17 decided, 15 of them on an agent's say-so" changes what a reviewer does next — while the
        # rung stored on the event and read by nobody changes nothing. Counts, never a blended score:
        # the four rungs fail differently and averaging them would hide the weak one. `cascaded`
        # (v0.11) is counted like the rest: "9 of 12 cascaded" says one policy election is carrying
        # most of this ledger, which is a different thing to weigh than nine answered questions.
        # v0.13: the rung is READ (`decision_rung`), not copied off the field. A pre-v0.11 cascade
        # records `transcribed` — a parameter default, not a relay anybody made — and counting it
        # there told an agent that N decisions rest on an agent's say-so when they rest on the
        # user's own elected policy.
        by_evidence: dict[str, int] = {}
        for e in self.data["decision_log"]:
            if e["id"].startswith("fal_"):
                by_failure[e["class"]] = by_failure.get(e["class"], 0) + 1
            elif e["id"].startswith("ev_"):
                rung = decision_rung(e) or "unrecorded"
                by_evidence[rung] = by_evidence.get(rung, 0) + 1
        # v0.15: the same count for the POLICIES, because a policy IS a decision — one the human
        # made over a whole cluster — and the count above says nothing about the election every
        # `cascaded` entry in it rests on. A policy elected with no rung recorded, or relayed with
        # no quote, is the thing to weigh before trusting the cascade that came out of it. Read off
        # `Policy.evidence` directly: unlike a DecisionEvent's rung there is nothing to derive here
        # (a policy is elected, never cascaded from another), so a reader function would be
        # ceremony. `policies` stays a plain count so an existing caller keeps its answer.
        pol_by_evidence: dict[str, int] = {}
        for p in self.data["policies"]:
            rung = str(p.get("evidence") or "") or "unrecorded"
            pol_by_evidence[rung] = pol_by_evidence.get(rung, 0) + 1
        return {
            # The floor, not this runtime's version: it stays where the file's own content puts it
            # while `pre_rule_events` is non-empty, so the two are read together.
            "version": self.data["version"],
            "pre_rule_events": {rule: len(ids) for rule, ids in self.pre_rule.items()},
            "pins": len(self.data["pins"]),
            "by_state": by_state,
            "events": len(self.data["decision_log"]),
            "policies": len(self.data["policies"]),
            "policies_by_evidence": pol_by_evidence,
            "open_questions": len(self.interview_view()),
            "failures_by_class": by_failure,
            "decisions_by_evidence": by_evidence,
            "premortems": sum(1 for p in self.data["pins"] if p.get("premortem")),
        }


def _json_arg(raw: Optional[str], field: str) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--{field}: invalid JSON ({exc})")
