"""Decisions-ledger runtime — the one implementation both skills bind to.

Schema authority: `core/decisions-ledger-spec.md` (v0.22). This module materializes the
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
  as a decision on all three surfaces even when it cascaded over no pin at all;
- v0.16 the SECOND predicate. v0.14 gave *"may this outcome land on this pin without asking"* one
  home; nothing governed *"may this pin leave the open set at all"*, so four doors reached a settled
  pin past every rule the first predicate holds. `Ledger.settlement_verdict(pin, door)` answers the
  second question for all five doors that move a pin in or out of `SETTLED_STATES`, `_settle` is the
  only writer of a settled state, and every one of those transitions appends a `SettlementEvent` —
  so *"how did this pin stop being open, and on whose authority"* is answerable from the log for
  every door and not only for `decided`. `resolution_mode: "asked"` is honoured by `unasked_verdict`
  too: six sites write it to assert "this one must be asked" and, until now, nothing read it.
- v0.17 the way BACK. v0.16 gave the five doors that settle a pin one predicate, one writer and one
  event, and left the two arcs that un-settle one with no predicate, no shared writer and no MCP
  tool — so `settlement_verdict`'s own refusal text (*"Reopen it first"*) named an arc no host could
  reach, and the whole settlement table was a one-way door. `reopen_verdict(pin, arc)` answers
  *"would this arc actually move this pin"* for both, `_reopen_minimal` is the only writer of the
  reopened state, and each arc's event records `reopened` rather than leaving a reader to infer it
  from a substate that is never cleared. `set_question` becomes write-if-absent (a pin recorded with
  no fork could not reach the interview at all), and `interview_view` selects `brainstorming` too:
  asking the brainstorm for options used to be what took a fork off the agenda.
- v0.18 four rules that were false of the thing they were printed on. A policy scope naming a real
  field with a `null` value still selected every pin that carries no value for it, so `scope_note`
  makes the preview SAY what the matcher does — v0.16 closed the misspelt key, not the class.
  `resolution_mode: "asked"` is written only for a refusal that is a standing property of the PIN
  (`STANDING_REFUSALS`): `not_offered` says the RULE did not fit, and recording a fact about a rule
  on a pin put that pin beyond every later policy, for ever, with no clearing door. The generated
  `correctness_unknown` fork stated an implication its own door refuses, so the sentence is now
  computed from `settlement_verdict` rather than written beside it. And `defer` no longer takes a
  caller-stated rung: there is one path there and it is the relay, so only the code that ran it may
  name it — the shape `mcp:ledger_defer` already had, one layer down.
- v0.20 the reopen half, held to the settlement half's own rules. v0.17 built the two arcs well and
  then let four asymmetries stand against their siblings, each observed over real stdio. `_settle`
  appends a per-pin `SettlementEvent` for every pin it settles and `_reopen_minimal` appended nothing
  for the whole dependent closure it swept back into the open set, so three finished pins were
  un-finished by one call and the log named one — now every cascaded pin gets a `CascadeEvent`
  (`cas_`), and `cascaded_by` reads the radius back off those records instead of off a substate
  nothing clears. The upstream arc reports that radius too, because it runs the same cascade.
  `challenge` (and `premortem`, the same role's other mode) holds `source` to `_CHALLENGE_SOURCES`
  as `reopen` always held its own — an arc whose safety argument is *it never elects* was accepting
  `source="interview"`. `add_proposals` refuses `CLOSED_STATES`, as `set_question` — its twin from
  the same commit, for the other half of the same funnel — already did. And `allow_freeform` moves
  into `_validate_question`: the rule was enforced at `set_question` and absent at `add_pin`, which
  is the older and busier door onto the identical object.
- v0.21 the same rule as v0.18's dispatch key, applied to the OTHER collection. `summary` and
  `interview_view` indexed `pin["state"]`, `pin["severity"]` and `pin["id"]` directly and died with a
  bare `KeyError` on six pin shapes — on files the map and the `AGENTS.md` projection read without
  complaint. So the READ path has one guarded entry (`Ledger.readable` + `pin_read`), what it
  substitutes is reported by `nonconforming` through `PIN_RULES` exactly as `log_entry_kind` reports
  an unnamed log entry, and nothing is skipped in silence.
- v0.22 the CARRIERS, where v0.20 did the events and v0.21 did the reads. A settlement door decides
  on what the pin says about itself, and the way BACK into the open set rewrote the state and left
  every other one of those carriers exactly as the closed pin had it. Reproduced over stdio: a
  defect walked `resolve(rung="observed")` then `reopen(fired="incident")`, and came back open still
  claiming its behaviour had been OBSERVED — on the evidence the incident had just refuted — so it
  re-closed through the gate that exists to stop precisely that. `SETTLEMENT_CARRIERS` names every
  carrier `settlement_verdict` reads and what the arcs owe it, `_reopen_minimal` is the one place
  that pays, and the table is held to the predicate's own AST, so a door that starts reading a sixth
  carrier fails until the arcs are told what to do with it. The same rule one field over:
  `pin.pop("substate", …)` lived in `decide`, so a pin reopened and then honestly re-resolved ended
  `state=resolved substate=reopened` — it now lives in `_settle`, which is the writer that already
  says in its own docstring why. And two doors that reached past their own principle: `unasked_verdict`
  and `policy_preview` — a read-only tool — indexed `pin["id"]`, `pin["state"]` and `pin["severity"]`
  raw, so v0.21's *reading a ledger is never the operation that fails on it* held for two readers of
  three; and `add_proposals`, which refuses `CLOSED_STATES`, silently accepted a `detected` pin,
  whose fork does not exist and whose brainstorm therefore reaches no surface.

On-disk form: one `ledger.json` (portable, git-versionable) written atomically.
The target codebase's ledger lives in *that* repo's audit output dir — never in this one.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = "0.22"

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
                     "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21", "0.22")

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

# Why a standing rule is one a reader must WEIGH before trusting what cascaded out of it. `""` when
# it is not one of these. Three codes rather than a boolean, for the reason every count in this file
# is kept apart: they fail differently, and "1 weak" says which sentence to write nowhere.
POLICY_WEAKNESS = ("no_rung", "unknown_rung", "unquoted_relay")

# severities that must never be silently defaulted (the threshold rule, v0.3)
_NEVER_SILENT = ("blocker", "high")

# Its complement over `SEVERITIES`, DERIVED rather than listed (v0.21). `assign_resolution_modes`
# wrote `proposed_default` for anything that is not `blocker|high`, which is the right rule for the
# four severities the schema has and the wrong one for a value it does not: a severity this runtime
# cannot rank was being told that silence may settle it. Membership is the question, so the negation
# is asked of the closed set rather than of the two names inside it.
_MAY_BE_SILENT = tuple(s for s in SEVERITIES if s not in _NEVER_SILENT)

# A pin these states describe is not open to being settled again by anyone.
SETTLED_STATES = ("decided", "resolved", "accepted", "deferred")

# The states in which the work on a pin is FINISHED. `decided` is settled but not finished: the
# human may re-elect it (last committed wins, and the log keeps both events), which is a correction
# and not a second close. Reaching a state below again is a second close, and the way back is
# `reopen` — which records why. Kept apart from `SETTLED_STATES` because the two answer different
# questions: `SETTLED_STATES` is "may an UNASKED write touch this" (no, for all four),
# `CLOSED_STATES` is "may any door settle this again" (no, and ask `reopen` instead).
CLOSED_STATES = ("resolved", "accepted", "deferred")

# The settled states whose instruction to a builder is **do not build this** (v0.19). A third
# reading of `SETTLED_STATES`, beside `CLOSED_STATES`, and it exists because a surface was answering
# it with a hardcoded state name: `instructions.py` sorted on `state == "deferred"` and printed a
# heading claiming `defer` was the only settled state that means "not built" — while `accept` is
# defined one function up as leaving the concern exactly as it is, which is the same instruction.
# So a blocker-severity `accepted` pin outranked an elected `decided` medium under the byte clip,
# inside a section headed *build on these*.
#
# `decided` and `resolved` are the complement: something was elected to be built, or was built and
# observed. Named here rather than in the projection for the reason every set in this block is:
# a state added to the schema with "leave it alone" semantics must arrive at the surfaces that sort
# and title by it, and a name written into one of them does not travel.
LEAVE_AS_IS_STATES = ("accepted", "deferred")

# Pins awaiting something. The complement of `SETTLED_STATES`, named rather than derived because
# `correctness_unknown` belongs here on purpose: it blocks closure and joins the interview view.
OPEN_STATES = ("detected", "needs_input", "brainstorming", "correctness_unknown")

# The states the INTERVIEW reads — `OPEN_STATES` minus `detected`, and a fourth reading of the same
# axis for the reason the other three are named: a surface was answering this question with its own
# condition. `interview_view` held the tuple as a literal, so every other surface that says what the
# interview will do with a pin had to re-derive it, and the map's `modeLine` re-derived it wrongly:
# it printed the funnel's countdown — *"if you say nothing, the interview settles this with the
# proposed answer"* — on six `detected` pins, which reach the interview on no host and pose no fork
# for a proposed answer to be an answer to. That is §10's finding stated on the page that exists to
# make the mode honest.
#
# `detected` is out of it because a pin with no fork is what `detected` MEANS (`add_pin` writes
# `needs_input` iff a question came with it, and `set_question` moves it the moment one arrives).
# `correctness_unknown` is in it for the reason `OPEN_STATES` names: it is a pin awaiting a
# next-move answer, not a re-election.
INTERVIEW_STATES = ("needs_input", "brainstorming", "correctness_unknown")

# The rungs at which a claim may CLOSE. `resolved` means observed — the verification skill's rule
# restated as data (v0.7) — and this is the tuple that says so, read by `settlement_verdict`.
_CLOSING_RUNGS = ("observed", "cross_derived")

# -- the doors that move a pin in or out of `SETTLED_STATES` (v0.16) ---------------------------
#
# Four settle; the fifth un-settles. They are ONE table because the question a reader has to be able
# to ask of the trail is not "was this decided" but *"how did this pin stop being open, and on whose
# authority"* — and a trail that answers it for one door out of five answers it wrongly.
SETTLEMENT_DOORS = ("decide", "accept", "defer", "resolve", "correctness_unknown")
# The three whose authority is an election (a DecisionEvent). `resolve`'s authority is an
# observation; `correctness_unknown`'s is the absence of one.
_ELECTION_DOORS = ("decide", "accept", "defer")
_ELECTION_STATES = ("decided", "accepted", "deferred")
_STATE_BY_DOOR = {
    "decide": "decided",
    "accept": "accepted",
    "defer": "deferred",
    "resolve": "resolved",
    "correctness_unknown": "correctness_unknown",
}

# What `Ledger.settlement_verdict` can answer. Each refusal names ONE reason, and the strongest one,
# for the same reason `UNASKED_BUCKETS` does: "why is this pin still open" is a question a reader
# has to be able to act on.
SETTLEMENT_BUCKETS = (
    "would_settle",      # this door may run on this pin
    "already_closed",    # the work is finished — reopen it rather than close it twice
    "wrong_kind",        # leaving-as-is is the resolution of a design_concern and of nothing else
    "not_decided",       # nothing was elected yet, and this door closes elected work
    "remediation_open",  # no remediation recorded, or an item still open
    "unverified",        # correctness was NOT established — `resolved` means observed
)

# -- the two arcs that put a pin BACK into the open set (v0.17) --------------------------------
#
# The mirror of `SETTLEMENT_DOORS`, and it arrives one version later for a reason worth keeping in
# the file rather than in a commit message: v0.16 gave the five doors that settle a pin one
# predicate, one writer and one event, and left the two arcs that un-settle one with none of the
# three — no predicate, no shared writer, and (the part nobody could see from inside this module) no
# MCP tool on any host. So `_SETTLEMENT_REASONS` shipped a refusal reading *"Reopen it first"* about
# an arc nothing could reach, and the settlement table was a one-way door.
REOPEN_ARCS = ("reopen", "challenge")

# The substate each arc leaves behind. A table rather than a string every caller passes, for the
# same reason `_STATE_BY_DOOR` is one: the substate IS which arc ran, so a second carrier for that
# fact is a divergence waiting to happen.
_SUBSTATE_BY_ARC = {"reopen": "reopened", "challenge": "challenged"}

# Every carrier a SETTLEMENT DOOR reads off a pin, and what the way BACK into the open set owes each
# one (v0.22). The question this table exists to force, asked once here instead of per arc:
# **which carriers does `settlement_verdict` decide on, and which of them does the reopen leave
# standing?**
#
# v0.20 gave the arcs the settlement half's EVENTS. This is the same asymmetry one layer in, on the
# thing the doors actually read. `_reopen_minimal` wrote `state`, `substate` and `resolution_mode`
# and nothing else, so a reopened pin walked back into the open set still carrying the pin's own
# claim that its behaviour had been OBSERVED. Reproduced over real stdio: a defect closed at the
# `observed` rung, `reopen(fired="incident", reason="p95 blew the threshold")`, then `resolve` again
# with no new observation of any kind — `settlement_verdict` read the envelope the incident had just
# refuted and answered `would_settle`. The gate whose entire purpose is *`resolved` means OBSERVED*
# was opened by the evidence the reopen exists to invalidate.
#
# Three dispositions, and each one is an answer rather than a shrug:
#
#   * `rewritten` — the arc writes it. `state` is the arc's whole output.
#   * `invalidated` — the pin's own CLAIM about the work, which is what a reopen refutes. It is
#     demoted, never deleted: the rung comes off (absence is read as the weaker rung everywhere in
#     this file, and `settlement_verdict` reads it that way) and `blocked_by` says what refuted it,
#     which is the field the map's verification card and `interview.funnel` already read. What was
#     claimed before is still in the log — the `stl_` event records the rung it closed at, and the
#     `rev_`/`chl_`/`cas_` event records the reopen — so "it was observed, then production refuted
#     it" reads as the history it is, which is the standard `resolve` already sets for `blocked_by`.
#   * `not_a_claim` — a fact the reopen does not touch. `kind` is what the pin IS. `remediation` is
#     the record that actions were TAKEN, which stayed true: what did not survive is the claim that
#     they worked, and that claim is `verification`. Clearing item statuses would say the work was
#     never done, which is a different falsehood, and the pin's re-entry into the open set is what
#     puts a new item in front of a human.
#
# Held to `settlement_verdict`'s own AST by `tests/test_ledger.py::TestTheWayBackOwesTheDoorsTheir
# Carriers`, so a door that starts gating on a sixth carrier fails until the arcs are told what
# that carrier is owed — which is the only arrangement in which "every carrier" is a claim about the
# code rather than about two functions remembering each other.
REOPEN_DISPOSITIONS = ("rewritten", "invalidated", "not_a_claim")
SETTLEMENT_CARRIERS = {
    "state": "rewritten",
    "kind": "not_a_claim",
    "remediation": "not_a_claim",
    "verification": "invalidated",
}

# Every substate a pin carries because something put it BACK in front of the human (v0.19), composed
# from the arc table rather than re-listed beside it — `cross_derive` is the third writer and the
# only one that is not an arc, so it is the only literal here.
#
# It is named because a pin in one of these carries an **outcome that is under dispute**, and a
# surface that prints that outcome without saying so prints a build instruction. `instructions.py`
# did exactly that: `grep -c substate` over it returned 0, so a pin two providers had contradicted
# reached every host's always-on context formatted identically to an elected decision. The map has
# distinguished them loudly since v0.16; the one file every host loads unprompted had no reader.
#
# `_settle` clears it on every door that lands the pin in `SETTLED_STATES`, so the mark means
# *disputed and not re-answered* rather than *was disputed once*. It was `decide`'s own `pop` until
# v0.22, which held for the three election doors and left `resolve` — the door whose authority is an
# observation, and therefore the one a downstream reopen is most often followed by — writing
# `resolved` over a live dispute mark.
REOPENED_SUBSTATES = ("contested",) + tuple(_SUBSTATE_BY_ARC[a] for a in REOPEN_ARCS)

# What put a settled pin back in front of the human, on the DOWNSTREAM arc. `flip_signal` is the
# decision's own declared tripwire; `manual_checkpoint` is what a `flip_signal` with no telemetry
# degrades to (`core/feedback-loop.md`); `incident` is production saying it the loudest way it can.
# Closed, because "what fired" is the whole of what a reopen rests on — the arc writes no outcome
# and needs no quote precisely because it is reporting an observation, and a free-text field there
# would let an agent write its own justification where production's belongs.
REOPEN_TRIGGERS = ("flip_signal", "manual_checkpoint", "incident")

# Where the reading came from, composed from the same closed vocabulary a `flip_signal` declares its
# own source with. One list, so "watched by metrics" and "reopened by metrics" cannot drift into
# meaning two different things.
_FEEDBACK_SOURCES = tuple(f"feedback:{src}" for src in FLIP_SIGNAL_SOURCES)

# Who may refute an oracle on the UPSTREAM arc (v0.20). Closed for exactly the reason the downstream
# arc's list is closed, and it was open for four versions: `Ledger.challenge(source=…)` took any
# string, so `source="interview"` — the value that means *a human elected this* — was accepted onto a
# ChallengeEvent that then reopened a human's `decided` pin. An arc whose whole safety argument is
# *it never elects* must not be able to sign itself as the electing door.
#
# One member, and the singleton is the roster's answer rather than an oversight: `core/agents.md`
# makes the challenger **"the one reopen path at the wave checkpoint"** and says in the same
# paragraph why the obvious second candidate is not one — *"a reviewer reopening directly would
# silently perform T3 work at T2"*. `challenge:cross_derivation` is deliberately NOT here: that is
# the source `cross_derive` stamps on its own `xdr_` event, and admitting it at this door would let
# an agent hand-write the event the cross-derivation path exists to produce.
CHALLENGE_ORIGINS = ("challenger",)
_CHALLENGE_SOURCES = tuple(f"challenge:{origin}" for origin in CHALLENGE_ORIGINS)

# What `Ledger.reopen_verdict` can answer. `nothing_settled` is NOT a refusal: both arcs append
# their event either way and report whether anything moved, which is the shape `cross_derive` was
# corrected to in v0.16 for the identical condition — an observation about a pin that cannot be
# un-settled is still an observation, and dropping it would lose the one signal the learning layer
# and the premortem gate both read (`has been reopened before`).
REOPEN_BUCKETS = ("would_reopen", "nothing_settled")

# What `Ledger.unasked_verdict` can answer, and therefore the buckets every radius over it reports
# (v0.14). Ordered so a caller can present them the way a human reads them: what it decides first,
# then the refusals, then the pins that were never in scope. `policy_preview` builds its return
# shape from this tuple, so adding a bucket cannot leave one surface reporting four and another six.
UNASKED_BUCKETS = ("would_decide", "held_back", "must_be_asked", "not_offered", "excepted",
                   "already_settled")

# Which of those refusals is a standing property OF THE PIN, and therefore the only ones worth
# recording on it as `resolution_mode: "asked"` (v0.18). Both entries here are already true of the
# pin before any rule was written: `held_back` is its severity, `must_be_asked` is the mark it
# already carries. `not_offered` is deliberately absent — it says *this RULE's outcome is not on
# this pin's menu*, which is a fact about the rule, and stamping it on the pin turned a fit problem
# into a permanent property with no clearing door. One badly scoped policy therefore put a `medium`
# pin beyond every later policy, including the one that fitted it, and `assign_resolution_modes`
# only ever fills the field where it is ABSENT, so nothing could undo it. The compression of the
# medium/low long tail is the whole reason the funnel exists, and it stopped working silently.
#
# Both callers of `unasked_verdict` that create this mark read this tuple (`Ledger.apply_policy`,
# `interview.expand_catalog`), so the rule has one home rather than one per door — v0.14's lesson,
# applied to the thing the predicate's answer is written INTO rather than to the answer itself.
STANDING_REFUSALS = ("held_back", "must_be_asked")

# Every id prefix a `decision_log` entry may carry, and therefore every kind of entry a reader may
# dispatch on (v0.18). Declared because `summary()` dispatches on the prefix: an entry carrying no
# id at all made it die with a bare `KeyError`, on the one call an agent makes BEFORE acting, on a
# file it did not write. No version of this package ever wrote such an entry — it is hand-editing —
# which is exactly why the read path must survive it: **reading a ledger is never the operation that
# fails on it.** Unrecognised entries are reported by `nonconforming` under `log_entry_kind` rather
# than skipped in silence, on the same rule the `settles_as` skip one function down already follows.
#
# `cas_` (v0.20) is the CascadeEvent, and it is the entry the reopen half was missing. `_settle`
# appends one `stl_` for every pin it settles; `_reopen_minimal` moved a pin's whole settled
# dependent closure back into the open set and appended **nothing** for any of them, so three
# `resolved` pins were un-finished by one call and the log named one. That is the same asymmetry the
# v0.16 settlement work removed in the other direction, left standing on the arcs that undo it.
LOG_ENTRY_PREFIXES = ("ev_", "stl_", "chl_", "xdr_", "fal_", "rev_", "cas_")

# The `Pin` fields a `Policy` scope may match on (v0.16). A scope key naming no field of a pin
# matched EVERY pin — `pin.get("nope") == None` is true of all of them — so `applies_to={"nope":
# null}` was a universal selector wearing a filter's clothes, and the preview a human elects a
# policy from showed the whole ledger as its radius. Declared here and held to what the writers
# actually write by `tests/test_ledger.py::TestAPolicyScopeNamesRealFields`, so a field added to the
# envelope without being scopeable fails rather than silently becoming unmatchable.
PIN_FIELDS = (
    "id", "kind", "kind_detail", "title", "severity", "confidence", "provenance", "anchors",
    "state", "substate", "as_is", "to_be", "question", "brainstorm", "decision", "depends_on",
    "remediation", "cluster_id", "resolution_mode", "verification", "readiness", "premortem",
    "cross_derivations", "evidence",
)


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


def policy_weakness(policy: dict) -> str:
    """Why this standing rule must be weighed before what cascaded out of it is trusted — one of
    `POLICY_WEAKNESS`, or `""`.

    One rule, one implementation, for the same reason `decision_rung` is one: two surfaces were
    counting the SAME ledger and reporting different numbers. On the repo's own preview fixture the
    map badged two standing rules weak and the projected `AGENTS.md` said one — because the map
    asked "is the rung weak" and the projection asked "is the quote missing". Neither was wrong on
    its own terms, which is exactly why a reader could not act on either: one ledger, two numbers.

    The classification is here, in the module that owns the schema; the *sentence* stays with each
    surface, because a badge and a projected instruction line address different readers. The map
    gets this result inlined (`map.weak_policies`), the way it already gets `derived_rungs` —
    a second implementation in the page's JavaScript would be reachable by no test without a
    browser, and would drift.

    A relay WITH the human's words is not on the list, and that is the same judgement the spec
    makes about `transcribed` everywhere else: the weak rung is permitted precisely because the
    quote is there to be weighed. What the map's card still shows for one is the rung and the
    quote; what it no longer shows is a badge saying something is missing when nothing is.
    """
    rung = str(policy.get("evidence") or "")
    if not rung:
        return "no_rung"
    if rung not in POLICY_EVIDENCE:
        return "unknown_rung"
    if rung == "transcribed" and not policy.get("human_answer"):
        return "unquoted_relay"
    return ""


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
    # v0.16. Absence is NOT a violation and that is the table's own membership rule at work: every
    # event written before this field existed produced `decided`, which is what its absence means,
    # so a file that predates it conforms and keeps its floor. What is decidable from the event
    # alone — and therefore checkable — is a value that names a state no election can produce.
    ("settled_state",
     lambda e: "settles_as" not in e or e.get("settles_as") in _ELECTION_STATES,
     lambda e: f"settles_as names the state an ELECTION produces, one of {_ELECTION_STATES}; got "
               f"{e.get('settles_as')!r} — `resolved` is a verification outcome and "
               "`correctness_unknown` the refusal to reach one, and neither is elected"),
)


def event_violations(event: dict) -> list:
    """The names of the `EVENT_RULES` this DecisionEvent does not satisfy, in table order."""
    return [name for name, holds, _ in EVENT_RULES if not holds(event)]


def _check_event(event: dict) -> None:
    """Refuse to write an event that breaks a rule — reporting the first, strongest one."""
    for name, holds, message in EVENT_RULES:
        _require(holds(event), message(event))


# -- THE READ PATH: what a reader may index on a pin (v0.21) -----------------------------------
#
# v0.18 made every read in `summary`'s log loop a `.get`, the dispatch key included, under a
# principle stated with no qualifier: **reading a ledger is never the operation that fails on it.**
# It was applied to one of the two collections. `summary` and `interview_view` went on indexing
# `pin["state"]`, `pin["severity"]` and `pin["id"]` directly, and a reviewer reproduced six pin
# shapes that made both die with a bare `KeyError` — a severity outside `SEVERITIES`, a severity
# missing, a severity `null`, a state missing, an id missing, and an absent `pins` key — on files
# `map.render` and `instructions.render` read start to finish without complaint. `summary` is what
# an agent calls BEFORE acting on a file it did not write, so a file it cannot read is a file it
# acts on blind.
#
# ONE guarded path, not six guards, and the split is the two things that can be wrong: the
# CONTAINER (`Ledger.readable`) and the FIELDS (`pin_read`). Six sites that agree today are what
# the sibling rounds have spent themselves untangling.
#
# **Nothing is substituted in silence**, which is the same answer the log half already gives:
# `PIN_RULES` is to a pin what `EVENT_RULES` is to a DecisionEvent, `nonconforming` replays it, and
# what it finds is visible in `summary()`'s `pre_rule_events` beside the counts the pin is missing
# from. Its membership question differs from `EVENT_RULES`' and is worth stating rather than
# copying: `EVENT_RULES` asks *is the violation decidable from the stored event alone*, because its
# rules arrived after the events they judge. Every rule here has been enforced by `add_pin` since
# the first version, so no file this package wrote can break one — like `log_entry_kind`, these are
# hand-editing rather than a legacy shape, and what the table buys is the reader.
#
# **The difference that follows, stated because its sibling makes the opposite choice loudly.**
# `EVENT_RULES` has TWO callers — `_check_event` at the write and `nonconforming` at the read — and
# that is its whole argument: a rule added to it gains its reader by construction. This table has
# ONE, and adding a writer half would be a second refusal for a fact `add_pin` already settles.
# Three of the five cannot fail there at all, because `add_pin` composes the value itself (`id` from
# `_next_id`, `state` from whether a question came with it, `depends_on` filtered by `self.pin(dep)`
# refusing anything that names no pin); the other two have their own `_require`s reading the SAME
# closed sets this table reads, so the two can differ in wording and never in verdict.
# `tests/test_ledger.py::…::test_no_pin_this_runtime_writes_can_break_one_of_these_rules` asserts
# that rather than leaving it as a claim.
#
# Each entry is `(name, holds(pin) -> bool, message(pin) -> str)`, and every one of them takes a
# pin that IS an object: an entry that is not one is reported once, by `entry_shape`, rather than
# four times by four rules that could not be asked of it.
#
# The three lists a ledger is made of, named because the guarded read is about all three and so are
# both shape rules. `summary` read each one as `self.data[…]` and died the same way on each; fixing
# the one that was reported would have left the file's other two halves for the next reviewer.
LEDGER_COLLECTIONS = ("pins", "decision_log", "policies")
PIN_RULES = (
    ("pin_id",
     lambda p: bool(str(p.get("id") or "")),
     lambda p: "a pin carries no `id`, so nothing can depend on it, name it or link to it"),
    ("pin_state",
     lambda p: p.get("state") in STATES,
     lambda p: f"state must be one of {STATES}; got {p.get('state')!r} — every surface that sorts, "
               f"counts or gates on a pin reads this field"),
    ("pin_severity",
     lambda p: p.get("severity") in SEVERITIES,
     lambda p: f"severity must be one of {SEVERITIES}; got {p.get('severity')!r} — the threshold "
               f"rule and the interview's ordering both read it"),
    ("pin_depends_on",
     lambda p: isinstance(p.get("depends_on", []), list)
     and all(isinstance(d, str) for d in p.get("depends_on", [])),
     lambda p: f"depends_on must be a list of pin ids; got {p.get('depends_on')!r} — the DAG every "
               f"wave is levelled by is read off it"),
    ("pin_question",
     lambda p: p.get("question") is None or isinstance(p.get("question"), dict),
     lambda p: f"question must be an object or absent; got {type(p.get('question')).__name__} — "
               f"`interview.funnel` reads `question.prompt` off it, so a fork that is not an object "
               f"takes the whole funnel down rather than one entry"),
)


def pin_violations(pin: dict) -> list:
    """The names of the `PIN_RULES` this pin does not satisfy, in table order.

    The mirror of `event_violations`, and it takes an object for the same reason that one does: a
    `pins` entry that is not an object is `entry_shape`'s answer, not four rules' worth of it."""
    return [name for name, holds, _ in PIN_RULES if not holds(pin)]


def pin_read(pin: Any) -> dict:
    """The five fields the read path INDEXES, as a reader may use them. Never raises.

    What each absence becomes, and why — a substitution nobody can name is a heuristic:

      * `id`, `state` — `""`. Neither is in any closed vocabulary, so a pin with no state is in no
        state's bucket and one with no id is depended on by nothing. It is still counted, still
        rendered, and reported under `pre_rule_events`.
      * `severity` — `""`, which `severity_rank` sorts LAST. Not `low`, which would be reading a
        claim the file does not make; not `blocker`, which would be inventing urgency out of a
        broken field. The pin stays IN the view either way — the ordering is by information gain
        among severities this runtime can rank, and an unrankable one is not evidence of anything.
      * `depends_on` — `[]` unless it is a list of strings. A bare string here is iterable, so the
        old readers walked it character by character and built a DAG out of letters.
      * `question` — `{}` unless it is an object, which is falsy exactly where `pin["question"]`
        already was. It is here because `interview.funnel` indexes `question.prompt`, and it is the
        only one of the five whose value is returned by reference: a reader may look at the fork,
        never rewrite it (`set_question` is the door, and it is write-if-absent).
    """
    src = pin if isinstance(pin, dict) else {}
    deps = src.get("depends_on")
    question = src.get("question")
    return {
        "id": str(src.get("id") or ""),
        "state": str(src.get("state") or ""),
        "severity": str(src.get("severity") or ""),
        "depends_on": [d for d in deps if isinstance(d, str)] if isinstance(deps, list) else [],
        "question": question if isinstance(question, dict) else {},
    }


def severity_rank(severity: str) -> int:
    """Where a severity sorts — `SEVERITIES`' own order, and a value it does not carry sorts last."""
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)


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

    One rule here is NOT an `EVENT_RULES` entry, and the reason is that table's own membership
    question rather than an exception to it (v0.18). `log_entry_kind` is about *every* entry in the
    log, not about a DecisionEvent, and `decide` cannot violate it — `_next_id` composes the id — so
    there is nothing for the writer half of that table to check. What it buys is a reader: an entry
    whose id names no kind is dispatched by nothing, and `summary()` used to die on it with a bare
    `KeyError`. Reporting it here means the one surface that already says *"this file predates or
    breaks a rule"* says this too, instead of the count quietly being short by one.

    **`PIN_RULES` joins it in v0.21, for the same reason one collection over.** The pin half of the
    read path substitutes a value where the file carries none (`pin_read`), and a substitution
    nobody can see is worse than the crash it replaced — so every substitution has a rule name here.
    These rules are not `EVENT_RULES`' membership question restated: `add_pin` has enforced all five
    since v0.3, so no file this package wrote can break one, which puts them in `log_entry_kind`'s
    class rather than in the floor-of-a-legacy-file class. The consequence is deliberate and is the
    same one every other entry carries: a file with an unreadable pin does not get its `version`
    raised, because the stamp is a claim of conformance and that file does not conform.
    """
    def entries(name: str) -> list:
        value = data.get(name)
        return value if isinstance(value, list) else []

    out: dict = {}
    # The two rules about the SHAPE of the file rather than about the content of a record, checked
    # first because every rule below assumes them. A reader walks a missing collection as an empty
    # one, so the file says "no findings" — the worst thing a ledger can say — and until v0.21
    # nothing said otherwise; a non-object entry made this function itself raise `AttributeError`
    # before it could report anything at all.
    for name in LEDGER_COLLECTIONS:
        value = data.get(name)
        if not isinstance(value, list):
            out.setdefault("collection_shape", []).append(f"{name}: {type(value).__name__}")
            continue
        for index, entry in enumerate(value):
            if not isinstance(entry, dict):
                out.setdefault("entry_shape", []).append(f"{name}[{index}]")
    for index, event in enumerate(entries("decision_log")):
        if not isinstance(event, dict):
            continue                                    # already reported as `entry_shape`
        eid = str(event.get("id") or "")
        if not eid.startswith(LOG_ENTRY_PREFIXES):
            # Named by position, because the thing that is wrong with it is that it has no name.
            out.setdefault("log_entry_kind", []).append(f"decision_log[{index}]")
            continue
        if not eid.startswith("ev_"):
            continue
        for rule in event_violations(event):
            out.setdefault(rule, []).append(eid)
    for index, pin in enumerate(entries("pins")):
        if not isinstance(pin, dict):
            continue                                    # already reported as `entry_shape`
        # By id where there is one, by position where there is not — the same rule `log_entry_kind`
        # follows, for the same reason: a thing with no name is named by where it sits.
        label = str(pin.get("id") or "")
        for rule in pin_violations(pin):
            out.setdefault(rule, []).append(label or f"pins[{index}]")
    return out


def _door_for(settles_as: str) -> str:
    """The ELECTION door that produces this state. Refuses anything else, so `settles_as` cannot
    become a way to write an arbitrary state onto a pin through the decision path — `resolved` is a
    verification outcome and `correctness_unknown` is the refusal to reach one; neither is elected,
    so neither is reachable from `decide`."""
    door = next((d for d in _ELECTION_DOORS if _STATE_BY_DOOR[d] == settles_as), "")
    _require(bool(door),
             f"settles_as must be one of {sorted(_STATE_BY_DOOR[d] for d in _ELECTION_DOORS)} — "
             f"the states an ELECTION produces; got {settles_as!r}")
    return door


def _validate_question(question: Optional[dict]) -> None:
    """Every rule a fork must satisfy, at every door that composes one.

    **`allow_freeform` moved here in v0.20, and where it used to live is the whole finding.** v0.17
    introduced it at `set_question` — *a menu an agent composed may not bound what the human may
    answer* — and left `add_pin`, which is the older door, the busier one, and the one that composes
    the identical object. Reproduced over real stdio: `ledger_add_pin(question={prompt, options})`
    with no `allow_freeform` was accepted, and `ledger_set_question` with the byte-identical dict was
    refused. A rule that holds at one of two doors onto the same field is not a rule, it is a habit
    of whoever wrote the newer door.

    There is no case where it should not hold, and that is why it is here rather than duplicated:
    **every** question in this system is written by an agent — the human answers one, they never
    author one — so the way out is owed at every door, including any door added later. Every fork
    this runtime composes already sets it (`surface_assumption`, `cross_derive`,
    `mark_correctness_unknown`, `interview._fork_question`), which is what makes moving the rule a
    tightening of `add_pin` and a change of nothing else.
    `tests/test_ledger.py::TestEveryForkThisRuntimeComposes` holds the two that install a fork
    without passing any door to it from the AST — and that test is where the third name in that list
    came from, because it was not in the first draft of the exemption dict.
    """
    if question is None:
        return
    _require(isinstance(question, dict), "question must be a dict")
    _require(bool(question.get("prompt")), "question.prompt is required")
    options = question.get("options", [])
    _require(isinstance(options, list), "question.options must be a list")
    for opt in options:
        _require(bool(opt.get("id")) and bool(opt.get("label")),
                 "every question option needs id and label")
    _require(bool(question.get("allow_freeform")),
             "a fork an agent composed must set allow_freeform: the menu is what the human is "
             "allowed to choose from, and an agent that writes a closed one has decided the shape "
             "of their answer. Same rule at every door that composes a question — `add_pin` and "
             "`set_question` compose the identical object.")


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

    def readable(self, name: str) -> list[dict]:
        """The entries of one of `LEDGER_COLLECTIONS` a reader can index — the CONTAINER half of the
        guarded read path.

        Two things it refuses to do, both of which every reader here did until v0.21: die because
        the collection is absent (`summary` and `interview_view` both raised `KeyError: 'pins'`), and
        hand a caller an entry that is not an object. All three collections and not only the one that
        was reported — `summary` read each as `self.data[…]` and died the same way on each, and
        `nonconforming` already tolerated a missing `decision_log` while `summary` did not, which is
        one function's own two halves disagreeing about one file.

        A dropped entry is not hidden: `nonconforming` reports it under `entry_shape` and a missing
        collection under `collection_shape`, both visible in `summary()`'s `pre_rule_events` beside
        the counts they are missing from.

        The WRITE path deliberately keeps `self.data[…]`: a write onto a file this runtime cannot
        read is a different question from a read of it, and the answer there is to refuse.
        """
        value = self.data.get(name)
        return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []

    def readable_pins(self) -> list[dict]:
        """`readable("pins")` — named because it is the one nearly every reader wants."""
        return self.readable("pins")

    def pin(self, pin_id: str) -> dict:
        # Through the guarded read for the same reason every other lookup is: `p["id"]` raised on a
        # pin that carries none, and this is the one function every tool on every host calls first.
        for p in self.readable_pins():
            if pin_read(p)["id"] == pin_id:
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
        """Give a pin that poses NO fork the fork it needs to reach the interview (v0.17).

        `ledger_add_pin`'s `question` is optional, reasonably: whoever finds a thing is not always
        whoever knows what the fork is. But `question` is what the whole funnel runs on —
        `interview_view` selects on it, `interview.funnel` builds its entries from `question.prompt`,
        and both election doors refuse an outcome it does not offer — so a finding recorded without
        one was `detected` for ever and reached the interview on no host. This method existed for
        four versions with zero callers and no tool, which is why nobody could tell.

        **Write-if-absent, and that is the rule, not a courtesy.** It used to assign over whatever
        was there. `question.options[].id` is the carrier the offered-options rule anchors on at
        both doors, so a general-purpose question setter is how that invariant gets dismantled from
        the side — the same act v0.16 removed from `cross_derive` and from
        `mark_correctness_unknown`, each of which had been silently replacing a human's own fork.

        **The composed menu may not bound the human** — `allow_freeform` is required, and as of
        v0.20 it is required by `_validate_question`, which is to say at every door that composes a
        fork rather than at this one. It was introduced here and enforced here only, while `add_pin`
        — older, busier, composing the identical object — took a closed menu without complaint. With
        the flag the options are a suggestion and the human's own words are still a legal outcome
        (`record_decision(option_id="freeform")`); without it, an agent hands over a menu it wrote
        itself and calls it a question.

        **What it deliberately does NOT do is append `provenance: agent_assumption`**, which is the
        obvious move and is wrong here. `add_pin` couples that source to the pin's `confidence`
        (`inferred|ambiguous` required), so appending it afterwards would manufacture exactly the
        combination that door refuses — one rule, two doors, two answers, which is the shape v0.14
        through v0.16 were spent removing. `confidence` describes how the pin's `as_is` was
        established, and composing a fork later says nothing about that.

        The state moves only where it was blocking: `detected` -> `needs_input`. A
        `correctness_unknown` pin is already in the interview view on its state alone and forcing
        `needs_input` would erase what the verification envelope is there to say; a `decided` pin is
        not un-decided by acquiring a question, because un-deciding is the reopen arc and has its
        own door.
        """
        pin = self.pin(pin_id)
        _require(bool(question), "a question is required — this door exists to add one")
        _validate_question(question)
        _require(not pin.get("question"),
                 f"{pin_id} already poses a fork. `question.options[].id` is the carrier the "
                 f"offered-options rule anchors on at both election doors, so replacing it decides "
                 f"what the human may choose next — write-if-absent is the whole rule here.")
        _require(pin["state"] not in CLOSED_STATES,
                 f"the work on {pin_id} is finished ({pin['state']}); posing it a new question is "
                 f"un-finishing it, which is the reopen arc and has its own door (`reopen`, which "
                 f"records why).")
        pin["question"] = question
        if pin["state"] == "detected":
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

        **Finished work is refused (v0.20), in `set_question`'s words and for `set_question`'s
        reason.** The two doors were added in the same commit, for the two halves of the same funnel
        — one gives a pin the fork it lacks, the other gives that fork its options — and only one of
        them checked the state. Reproduced over real stdio: `ledger_add_proposals` succeeded on an
        `accepted` pin and on a `deferred` one, writing `brainstorm.proposals` onto work whose
        question had stopped being asked. Proposing options for a question nobody will be asked is
        not neutral, it is exploration addressed to a closed room — and the funnel then has to decide
        whether to show it, which is the state a `brainstorming` write is supposed to settle.

        `CLOSED_STATES` and not `SETTLED_STATES`, which is the same line `set_question` draws:
        `decided` is re-electable by the human, so exploring the alternatives to a live election is
        exactly what a brainstorm is for. The way back into the other three is `reopen`, which
        records why.

        **And a pin that poses no fork is refused too (v0.22).** The closed-state refusal above was
        written from one end of the range and left the other open: a `detected` pin was accepted in
        silence, and the write is unreachable by construction rather than merely unhelpful. This
        moves `needs_input -> brainstorming`, so a `detected` pin stays `detected` — outside
        `INTERVIEW_STATES`, which is the tuple every surface that shows a fork selects on — and the
        proposals land where no host will ever put them in front of anyone. Reproduced over stdio:
        `isError: false`, `{"state": "detected", "proposals": [...]}`, and `interview_next` then
        reported `total_open: 0`.

        The refusal reads the `question` and not the state, because the fork is what the proposals
        are options FOR — `detected` is the state that says a pin has none (`add_pin` writes
        `needs_input` iff a question came with it, and `set_question` moves it the moment one
        arrives), so gating on the state would be checking the shadow. `set_question` is the door,
        and it is named in the refusal: the sibling half of this same funnel, added in the same
        commit, for exactly this pin.

        The closed check is asked FIRST, on `settlement_verdict`'s own stated rule — *a rule that
        every door must obey is asked before any door speaks* — so a closed pin that also poses no
        fork is told the stronger of the two reasons: the work is over, and the answer is `reopen`,
        not `set_question`.
        """
        pin = self.pin(pin_id)
        _require(pin["state"] not in CLOSED_STATES,
                 f"the work on {pin_id} is finished ({pin['state']}); proposing options for it is "
                 f"un-finishing it, which is the reopen arc and has its own door (`reopen`, which "
                 f"records why).")
        _require(bool(pin_read(pin)["question"]),
                 f"{pin_id} poses no fork, and a proposal is an option for one. This door moves a "
                 f"pin from `needs_input` to `brainstorming`, so a pin with no question keeps the "
                 f"state it has and its proposals reach no surface — `interview_view` selects "
                 f"{INTERVIEW_STATES}. Pose the fork first (`set_question`), then propose against "
                 f"it.")
        _require(sum(1 for p in proposals if p.get("recommended")) <= 1,
                 "at most one proposal may be `recommended` — two make the recommendation "
                 "uncomparable to what the human elects, which is the point of marking it")
        for index, prop in enumerate(proposals, 1):
            _require(bool(prop.get("summary")), "a proposal needs a summary")
            _require(prop.get("effort") in EFFORTS if "effort" in prop else True,
                     f"proposal effort must be one of {EFFORTS}")
            _require("decision" not in prop and "outcome" not in prop,
                     "neutrality: a proposal must not carry a decision/outcome")
            # `f"prop_{len(proposals)}"` — the LIST's length, constant across the loop, so every
            # auto-id'd proposal on a pin got the same id: two proposals, both `prop_2`. Invisible
            # for as long as no host could call this at all, and reproduced on the first real
            # `mcp:ledger_add_proposals` call. The id is a carrier — `learning.divergences` decides
            # whether the human took the recommendation by matching `pin.decision.outcome` against
            # these ids, and the funnel entry lists them — so duplicates make "which option did the
            # human take" unanswerable, which is the one question the mark exists to answer.
            #
            # The DecisionEvent carries no `proposal_ref` and never has: this comment and the
            # refusal below both said it did, and the spec puts that field on
            # `question.options[]` — an OPTION pointing back at the proposal it was fed by
            # (`{"id": "prop_1", "label": …, "proposal_ref": "prop_1"}`). Checked at the writer
            # (`decide` composes `id/pin_id/timestamp/outcome/rationale/flip_criteria/source/
            # evidence/settles_as/policy_hash`, and nothing else) and at the reader
            # (`learning.divergences`, which compares the outcome to `proposals[].id` directly).
            # The claim was wrong in the direction that matters least and is corrected anyway,
            # because a refusal message is the one sentence an agent reads at the moment it is
            # confused.
            prop.setdefault("id", f"prop_{index}")
            prop.setdefault("tradeoffs", {"pros": [], "cons": []})
        ids = [p["id"] for p in proposals]
        _require(len(set(ids)) == len(ids),
                 f"two proposals share an id ({sorted(ids)}) — the election names an option and "
                 f"`learning.divergences` matches that outcome against these ids, so a repeated id "
                 f"makes 'which option did the human take' unanswerable from the ledger")
        pin["brainstorm"] = {"proposals": proposals, "notes": notes}
        # Two states, not one (v0.22). `needs_input` is the only one this runtime can put here —
        # a pin carrying a fork is never left `detected` by any door it writes — but the refusal
        # above is anchored on the FORK, so a hand-edited pin that has one and says `detected`
        # reaches this line, and leaving it there would be the same unreachable write one shape
        # over. `brainstorming` is in `INTERVIEW_STATES`; `detected` is exactly what is not.
        # `correctness_unknown` and `decided` are deliberately absent: each says something stronger
        # than "being thought about", and overwriting it would erase what it is there to say.
        if pin["state"] in ("needs_input", "detected"):
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
        settles_as: str = "decided",
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

        `settles_as` names which settled state this election produces — `decided`, or the two
        outcomes that are elections about scope rather than about the fork: `accepted` (leave it as
        it is) and `deferred` (not now). It is not a fan-out flag and cannot become one: it selects
        the DOOR, one pin, one event, and the door is what `settlement_verdict` judges. Both used to
        write `pin["state"]` themselves after calling this, which is how `deferred` became a settled
        state reachable with no election, no threshold, no quote and nothing in the log (v0.16).
        """
        # The "a transcribed decision must quote the human" rule is enforced one layer out, in
        # `mcp/tools.py::record_decision`, because that is the only boundary an AGENT can reach and
        # so the only place the claim is actually made. Enforcing it here as well would tax the
        # library's own callers — `expand_catalog`, `accept`, the tests — for a risk none of them
        # carry. It is also, for the same reason, not an `EVENT_RULES` entry: the event records the
        # quote, never whether one was owed.
        pin = self.pin(pin_id)
        door = _door_for(settles_as)
        # Gated BEFORE the event is built: a refusal must not leave an orphan DecisionEvent in an
        # append-only log. `_settle` asks the same predicate again, because it is the single writer
        # of a settled state and a writer that trusts its callers is a writer with five contracts.
        self._gate_settlement(pin, door)
        event = {
            "id": self._next_id("ev_", self.data["decision_log"]),
            "pin_id": pin["id"],
            "timestamp": _now(),
            "outcome": outcome,
            "rationale": rationale,
            "flip_criteria": flip_criteria,
            "source": source,
            "evidence": evidence,
            # Which settled state this election produced (v0.16). On the event because the event is
            # what the log keeps: `accept` and `defer` used to write the state themselves after this
            # returned, so the log recorded an outcome of `keep` or `defer` and left a reader to
            # guess whether the pin had ended up `accepted`, `deferred` or merely `decided`.
            "settles_as": _STATE_BY_DOOR[door],
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
        # The dispute mark is cleared by `_settle` (v0.22), not here: it used to be popped on this
        # line, which gave the rule to the three doors that are elections and to none of the two
        # that are not — so `resolve` left `substate: "reopened"` standing on finished work.
        pin["decision"] = {"event_id": event["id"], "outcome": outcome}
        self._settle(pin, door, decision_event=event["id"])
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

    def defer(self, pin_id: str, rationale: str, flip_criteria: str,
              human_answer: str = "") -> dict:
        """Out of scope now (YAGNI at spec level) — stays as future backlog. **An election.**

        It used to be a bare `pin["state"] = "deferred"` behind ONE check (`state != "resolved"`):
        no severity threshold, no election, no quote, nothing appended to the log. Reachable by the
        agent alone as `mcp:ledger_defer`, it moved a `blocker` fork out of `SETTLED_STATES`' open
        complement in one call — `interview_next` dropped it, `ledger_summary.open_questions` went
        down by one, `decision_log` stayed empty, and nothing recorded that a choice had been
        avoided. That is the same hole `ledger_decide` never existed in order to avoid, on the state
        next to it.

        So deferring is what it always was in the spec's own question shape — an **answer**
        (`{"id": "defer", "label": "Defer (deferred)"}`) — and it is recorded as one: a
        DecisionEvent with outcome `defer`, a `flip_criteria` saying what brings it back, and the
        rung the answer travelled on. `mcp:ledger_defer` always demands the human's words, because
        there is exactly ONE path there and it is the relay: the tool takes no `evidence` parameter
        and writes `transcribed`. It briefly took one, and a single keyword settled a `blocker` fork
        on the `elicited` rung with nobody asked — the rung is a fact about WHICH PATH RAN, so only
        the code that ran it may state it. There is no elicitation path here; if one is ever added,
        that path sets the rung, exactly as `mcp/server.py::ledger_record_decision` does.

        Deliberately NOT held to the offered-options rule: `defer` is a meta-answer about scope, not
        a choice among the fork's branches, and demanding that every question list a `defer` option
        would make punting depend on whoever authored the pin. What holds it instead is the same
        thing that holds `accept`: the human was shown THIS pin, and said not now, in their words.

        **And the rung is not a parameter here either (v0.18).** v0.16 removed it from `ledger_defer`
        and left it on this method with the paragraph above already saying why it should not be
        there: *there is exactly ONE path here and it is the relay*. A default is not a refusal —
        the next caller passes `evidence="elicited"` and the library writes it, which is precisely
        the write the tool one layer up refuses, and the tool is the only thing that was stopping
        it. `decide` keeps the parameter legitimately, because two paths do reach it and the rung is
        a fact about WHICH ONE RAN; a parameter naming a path that does not exist is a claim, not a
        default. If deferral ever gains an elicitation path, that path sets the rung — by calling
        `decide` with it, exactly as `mcp/server.py::ledger_record_decision` does.
        """
        self.decide(pin_id, outcome="defer", rationale=rationale, flip_criteria=flip_criteria,
                    evidence="transcribed", human_answer=human_answer, settles_as="deferred")
        return self.pin(pin_id)

    def accept(self, pin_id: str, rationale: str, flip_criteria: str,
               evidence: str = "transcribed", human_answer: str = "") -> dict:
        """Leave-as-is: the legitimate default resolution of a design_concern only.

        The kind check moved into `settlement_verdict` (`wrong_kind`) rather than living here: it is
        a rule about which door may settle which pin, and every such rule now has one home.
        """
        self.decide(pin_id, outcome="keep", rationale=rationale, flip_criteria=flip_criteria,
                    evidence=evidence, human_answer=human_answer, settles_as="accepted")
        return self.pin(pin_id)

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
        gives: a pin that poses no fork cannot be decided through the fork it does not pose. A pin
        whose `question` is not an object offers nothing either, and says so through `pin_read`
        (v0.22) rather than through an `AttributeError` — `PIN_RULES`' `pin_question` is what reports
        it, on the same principle its caller one function down now follows.
        """
        options = pin_read(pin)["question"].get("options")
        return any(isinstance(o, dict) and o.get("id") == outcome
                   for o in (options if isinstance(options, list) else []))

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

          * **`resolution_mode: "asked"`** (v0.16) — the pin says of itself that it must be asked.
            Six sites write it and, until now, exactly two read it, both comparing against
            `"proposed_default"` only: so the field asserted an invariant nothing enforced. Two of
            the six write it carrying the assertion as a comment — *"a reopened truth is never
            re-defaulted silently"*, *"a contested claim is never re-defaulted silently"* — and a
            policy cascade re-defaulted both, silently. The others are the same statement in other
            words: a surfaced `agent_assumption` is vetoable *by a human*, a pin whose correctness
            could not be established carries the fork that asks what to do about it, and a pin a
            previous cascade already held back is not one a later cascade may take. Reading the
            field is the whole fix; nothing new is written.

        Order matters and is asserted rather than assumed: settled and excepted first (those are not
        refusals, they are pins outside the radius), then the threshold, then the pin's own demand to
        be asked, then the options. A reader asking "why is this pin still open" gets one reason, and
        the strongest one.

        **Read through `pin_read` (v0.22).** It indexed `pin["state"]`, `pin["severity"]` and
        `pin["id"]` raw, and its read-only caller is `policy_preview` — served as the read-only MCP
        tool `policy_preview`, put in front of a human before they elect a rule. Reproduced over
        stdio on a two-pin ledger whose second pin carries no `severity`: `ledger_summary` and
        `interview_next` both answered (v0.21 hardened exactly those two) and `policy_preview`
        returned `isError: true` with the body `'severity'`. The principle carries no qualifier —
        *reading a ledger is never the operation that fails on it* — and it had been applied to two
        readers of three.
        The threshold is asked of `_MAY_BE_SILENT` rather than of `_NEVER_SILENT`, which is
        `assign_resolution_modes`' own correction and matters for exactly one input: a severity this
        runtime cannot rank is not evidence that silence may settle the pin, so it is held back.
        Identical for every severity the schema has.
        """
        read = pin_read(pin)
        if read["state"] in SETTLED_STATES:
            return "already_settled"
        if read["id"] in excepted:
            return "excepted"
        if read["severity"] not in _MAY_BE_SILENT:
            return "held_back"          # threshold rule — never silent
        if pin.get("resolution_mode") == "asked":
            return "must_be_asked"      # the pin's own standing demand — v0.16
        if not self.question_offers(pin, outcome):
            return "not_offered"        # offered-options rule — never invented
        return "would_decide"

    # -- THE SECOND PREDICATE: may this pin leave the open set at all? (v0.16) -----------------

    def settlement_verdict(self, pin: dict, door: str) -> str:
        """May this pin change its settlement through this door? Returns one of
        `SETTLEMENT_BUCKETS`.

        `unasked_verdict` governs *what may be written onto a pin nobody was asked about*. It says
        nothing about the other axis, and for four versions nothing did — so a pin could leave the
        open set through doors that checked one thing each, or nothing at all. All four were
        reproduced over real stdio by an agent with no human in the loop:

          * `defer` moved a `blocker` fork into `SETTLED_STATES` on a single `state != "resolved"`
            check: no threshold, no election, no quote, nothing appended. The question stopped being
            asked and the log did not record that a choice had been avoided.
          * `resolve` enforced the v0.7 observation rung only `if rung is not None`, and
            `mark_correctness_unknown` writes `rung: None` when the caller does not supply one — so
            a pin that had *just declared its own correctness unestablishable* then closed green.
          * `record_decision` had no settled check at all, so it re-decided a `resolved` or
            `accepted` pin back to `decided` while `unasked_verdict` refused the same pin as
            `already_settled`: two doors, two answers, one question.
          * `accept`'s kind rule lived in `accept`, which is where every rule this repo has had to
            fix twice started out.

        So the second question gets the treatment the first one got in v0.14: ONE predicate, every
        door, the reason named rather than merged. What it deliberately does NOT decide is *who was
        asked* — that is the first predicate's job, and the two are composed, never blended: an
        election door passes both (`unasked_verdict` when nobody was asked, `question_offers` at the
        single-pin door), a verification door passes only this one.

        The asymmetry between `SETTLED_STATES` and `CLOSED_STATES` is deliberate and is the whole of
        the "two doors, two answers" fix: a `decided` pin may be re-elected by the human — that is a
        correction, and the append-only log keeps both events — while a CLOSED one may not be
        settled again by anybody, because the work is over. The way back from closed is `reopen`,
        which records why.

        **The closed check runs before the per-door branches, for all five doors.** It did not, and
        one door read it after answering — which is how the rule this predicate introduced was
        falsified by an ordering inside the predicate itself. A rule that every door must obey is
        asked before any door speaks; that is the only arrangement in which "every door" is a claim
        about the code rather than about five branches remembering the same thing.

        **One carrier, read on both sides.** Deleting the `state == "correctness_unknown"` refusal
        was right — it made `rung` a gate-opening move that could not open its gate — but it was
        only half the change, and the other half was the half that mattered: the envelope was then
        read as `is not None`, so a pin whose state declared its own correctness unestablishable and
        whose envelope was simply absent came back `would_settle` and closed green. Absence is read
        as the weaker rung everywhere else here (`_client_can_elicit` is False on any exception; a
        missing `evidence` is unrecorded, not transcribed), and it is read that way now.
        """
        _require(door in SETTLEMENT_DOORS, f"door must be one of {SETTLEMENT_DOORS}; got {door!r}")
        state = pin["state"]
        # Asked of EVERY door, and asked first. It used to be asked after the `correctness_unknown`
        # branch had already answered, which made `resolved` an *accepting* condition for the one
        # door that un-settles a pin: four agent-only calls (add_pin -> add_remediation ->
        # set_remediation_status -> resolve -> mark_correctness_unknown) took a pin out of the closed
        # set and back into it, with no `reopen` and nothing recording why finished work had been
        # un-finished. A rule this table introduced, falsified by the same table's own ordering.
        if state in CLOSED_STATES:
            return "already_closed"
        if door == "correctness_unknown":
            # The mirror door: it takes a pin out of `decided` — settled, but not finished — so
            # "was there work to be unable to verify" is its question. `resolved` is no longer one of
            # its inputs: that pin's work is over, and the way back is `reopen`, which records why.
            if state == "decided" or pin["kind"] == "defect":
                return "would_settle"
            return "not_decided"
        if door == "accept" and pin["kind"] != "design_concern":
            return "wrong_kind"
        if door == "resolve":
            # `correctness_unknown` is a state a DECIDED pin passes through (for a non-defect it is
            # reachable from nowhere else), so the election is not in doubt here and the question is
            # only whether a later observation reached the rung. The state used to be refused as
            # `unverified` on this line, before anything read the pin's own `verification` — which
            # made `rung` a gate-opening move that could not open its gate: `resolve` writes the rung
            # and calls `_settle`, `_settle` re-asks this predicate, and the state has not moved. So
            # the envelope below is the single carrier of "how hard was this checked", and the state
            # is not a second one that outranks it.
            if state not in ("decided", "correctness_unknown") and pin["kind"] != "defect":
                return "not_decided"
            if not pin.get("remediation") or any(i["status"] != "done" for i in pin["remediation"]):
                return "remediation_open"
            # The envelope is the single carrier, so it is read the way absence is read everywhere
            # else in this package: as the WEAKER rung, never as permission. `rung: None` inside a
            # `verification` envelope is not "no claim made", it is the strongest possible claim
            # that this must not close — and an envelope that is not there at all says even less
            # than that. Reading `is not None` as "no statement, so no objection" left the gate with
            # no carrier in the one case it was written for: a pin whose state declared its own
            # correctness unestablishable, carrying no envelope, closed green on `evidence="I
            # looked"`. `resolved` means OBSERVED, and nothing observed is recorded here.
            if (pin.get("verification") or {}).get("rung") not in _CLOSING_RUNGS:
                return "unverified"
        return "would_settle"

    #: Why each refusal is a refusal, in the words a caller can act on. A bucket with no sentence
    #: here would surface as a bare token, which is how a gate becomes something people route around.
    _SETTLEMENT_REASONS = {
        "already_closed":
            "the work on this pin is finished ({state}) — closing it again records a second ending "
            "for one piece of work. Reopen it first (the reopen arc records why), then decide.",
        "wrong_kind":
            "leaving-as-is is the legitimate resolution of a design_concern and of nothing else; "
            "this pin is a {kind}, which has nothing to keep.",
        "not_decided":
            "this door acts on work that was elected, and this pin is in {state}, which is not a "
            "state an election produced. Record the decision first.",
        "remediation_open":
            "resolve requires recorded remediation with every item done — a close with nothing to "
            "point at is a silent close.",
        "unverified":
            "`resolved` means OBSERVED (v0.7). This pin records no verification reaching the "
            "`observed` or `cross_derived` rung (state {state}) — and a pin carrying no "
            "`verification` at all records less than one that reached a weak rung, not more, so "
            "the honest destination is correctness_unknown, not a green close. Pass `rung` to "
            "resolve once you have observed the behaviour.",
    }

    def _gate_settlement(self, pin: dict, door: str) -> None:
        verdict = self.settlement_verdict(pin, door)
        _require(verdict == "would_settle",
                 f"{door} refused on {pin['id']} ({verdict}): "
                 + self._SETTLEMENT_REASONS.get(verdict, "").format(state=pin["state"],
                                                                    kind=pin["kind"]))

    def _settle(self, pin: dict, door: str, decision_event: Optional[str] = None,
                verification_rung: Optional[str] = None) -> Optional[dict]:
        """THE only writer of a settled state, and the only appender of a `SettlementEvent`.

        Every one of the five doors passes through here, so the gate cannot be a rule each door
        remembers — that is v0.14's lesson applied to the second predicate.

        **The event is appended only where an election is not already carrying it.** An election has
        a `DecisionEvent`, and that event now states which settled state it produced (`settles_as`),
        so appending a second record beside it would be two carriers for one fact — the divergence
        this package exists to find. `resolve` and `correctness_unknown` have no election behind
        them: their authority is an observation, or the recorded absence of one, and until v0.16
        neither left anything in the log at all. So the log answers *"how did this pin stop being
        open, and on whose authority"* for all five doors, with exactly one entry each.

        **The dispute mark is cleared here too (v0.22), which is what "the gate cannot be a rule each
        door remembers" was already claiming.** `pin.pop("substate", None)` lived in `decide`, so
        `accept` and `defer` got it (they ARE `decide`) and `resolve` did not: a pin reopened by an
        incident and then re-closed on a fresh observation, at an explicit `rung="observed"` — the
        fully honest path — ended `state=resolved substate=reopened`, and `REOPENED_SUBSTATES` says
        in its own words that the mark means *disputed and not re-answered*. Two consumers then read
        one object and contradicted each other about it.

        Cleared on the DESTINATION rather than per door, so the rule is one line and needs no second
        list: a door that lands the pin in `SETTLED_STATES` has ended the dispute, and the fifth door
        — `correctness_unknown` — has not, because it hands the pin back to the human still carrying
        the outcome that was disputed. Deriving it from the state table is what stops that
        distinction from being a name someone has to remember to add.
        """
        self._gate_settlement(pin, door)
        event = None
        if decision_event is None:
            event = {
                "id": self._next_id("stl_", self.data["decision_log"]),
                "pin_id": pin["id"],
                "timestamp": _now(),
                "door": door,
                "from_state": pin["state"],
                "to_state": _STATE_BY_DOOR[door],
                "verification_rung": verification_rung,
                "policy_hash": self._policy_hash(),
            }
            self.data["decision_log"].append(event)
        if _STATE_BY_DOOR[door] in SETTLED_STATES:
            pin.pop("substate", None)
        pin["state"] = _STATE_BY_DOOR[door]
        return event

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

        v0.16: and the scope names real fields. `pin.get(k) == v` is True for **every** pin when `k`
        is not a pin field and `v` is null, so `applies_to={"nope": null}` was a universal selector
        that read as a filter — reproduced end to end through `mcp:ledger_record_policy`. The radius
        is the thing a human elects a policy from, so a scope key that matches by not existing is
        not a narrow bug, it is the preview describing a different policy than the one being set.

        v0.18: that closed the misspelt key, not the class. **Most `Pin` fields are optional**, so a
        scope naming a REAL one with a `null` value still selects every pin carrying no value for it
        — `{"cluster_id": null}` reproduced as *"every pin in no cluster"*, which on a ledger where
        almost nothing is clustered is the whole ledger again, this time past the v0.16 check. It is
        not refused, because selecting the un-clustered pins is a legitimate thing to want and a
        refusal with no replacement is a wall; and it is not given an operator (`{"$exists": false}`)
        either, because a query language arriving one operator at a time is how a scope stops being
        readable by the human electing it. So the matcher SAYS what it does, in `scope_note`, and it
        says it here — in the one function `apply_policy` calls — so the preview and the cascade
        cannot describe the radius differently.

        v0.22: through the guarded read, because this is a READ — it says so in its own first line
        and it is served as a read-only tool. It walked `self.data["pins"]` (the write path's
        accessor) and indexed `pin["id"]`, so one pin missing one field made the call an `isError`
        on the host, on the same file `ledger_summary` and `interview_next` answered about.
        """
        for key in applies_to or {}:
            _require(key in PIN_FIELDS,
                     f"applies_to key {key!r} is not a Pin field ({', '.join(PIN_FIELDS)}). A key "
                     "no pin carries matches EVERY pin when its value is null, so this scope would "
                     "be the whole ledger wearing a filter's clothes.")
        excepted = frozenset(exceptions or [])
        out: dict = {bucket: [] for bucket in UNASKED_BUCKETS}
        for pin in self.readable_pins():
            if not all(pin.get(k) == v for k, v in applies_to.items()):
                continue
            out[self.unasked_verdict(pin, default_outcome, excepted)].append(pin_read(pin)["id"])
        out["scope_note"] = self._absence_note(applies_to)
        return out

    def _absence_note(self, applies_to: dict) -> str:
        """What a `null` in the scope actually selects, in words, or `""` when there is none.

        Counted with the matcher's own comparison rather than a second one: `pin.get(k) == v` is
        what admits the pin, so `== None` is what the sentence has to count. `to_be`, `question`
        and `decision` are written as explicit nulls, which is why the wording is *carries no value
        for* rather than *does not have the key* — the two differ on exactly those fields, and a
        sentence that got it backwards would be the preview lying more precisely.
        """
        parts = []
        total = len(self.data["pins"])
        for key, value in (applies_to or {}).items():
            if value is not None:
                continue
            matched = sum(1 for p in self.data["pins"] if p.get(key) == value)
            parts.append(f"every pin that carries no value for `{key}` — {matched} of {total}")
        if not parts:
            return ""
        return ("this scope selects by ABSENCE: it matches " + "; ".join(parts)
                + ". A null is not a wildcard and not a typo, but on an optional field the two "
                  "look identical from the radius — scope on a value the pins actually carry if "
                  "that is what you meant.")

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
        # Every refusal stays open; only the ones that are a standing property of the PIN are
        # recorded on it (v0.18, `STANDING_REFUSALS`). `not_offered` used to be recorded here too,
        # and that mark is permanent: nothing clears `resolution_mode`, `assign_resolution_modes`
        # fills only where it is absent, and `unasked_verdict` reads `"asked"` as the pin's own
        # standing demand. So one policy whose outcome a pin did not offer put that pin beyond
        # EVERY later policy — including the one written for it, whose outcome its question does
        # offer and whose severity is under the threshold. `not_offered` is a fact about the rule's
        # fit, and it is reported as one, in the radius this call returns.
        for bucket in STANDING_REFUSALS:
            for pin_id in radius[bucket]:
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
        """v0.3 funnel: blocker|high → asked; the medium|low long tail may batch.

        Reads through `pin_read` (v0.21) because `interview.funnel` calls this FIRST and
        `interview_view` second: guarding the second and not the first would have left the funnel
        dying one line earlier on the same file, which is the shape this round is about. A pin whose
        severity this runtime cannot rank gets `asked` — the only safe direction, since the whole
        point of the mark is that `blocker|high` are never silently defaulted, and a severity nobody
        can read is not evidence that silence is safe.
        """
        for pin in self.readable_pins():
            read = pin_read(pin)
            if read["state"] in ("needs_input", "detected") and "resolution_mode" not in pin:
                pin["resolution_mode"] = (
                    "proposed_default" if read["severity"] in _MAY_BE_SILENT else "asked"
                )

    # -- the two reopen arcs (both reopen, neither decides) -------------------

    def reopen_verdict(self, pin: dict, arc: str) -> str:
        """Would this arc actually move this pin? One of `REOPEN_BUCKETS` (v0.17).

        **Not a gate, and the difference is the point.** The five settlement doors ask permission
        because settling is irreversible-ish and unasked; these two arcs report something that
        happened — a signal fired, an oracle was refuted — and an observation about a pin that was
        never settled is still a true observation. So the event is appended either way and this
        predicate decides only whether anything *moves*. `cross_derive` was corrected to exactly this
        shape in v0.16, for the identical condition, and reusing it is deliberate: two answers to
        "the state will not take this write" on one file would be the divergence, not the fix.

        **Neither package predicate governs these arcs, and saying so is part of the design rather
        than an omission.** `unasked_verdict` governs *what outcome may land on a pin nobody was
        asked about*: these arcs write no outcome at all — no `DecisionEvent`, no `settles_as`, no
        `outcome` parameter anywhere on either signature — which is precisely why they are safe to
        expose to an agent when `decide` is not, and it is asserted from the AST rather than claimed
        here (`tests/test_ledger.py::TestComingBackIntoTheOpenSetIsGovernedToo`).
        `settlement_verdict` governs *a pin leaving the open set*: these move it the other way, and
        the only state either can produce is `needs_input`.

        What is left to check is therefore small and honest: a pin in `SETTLED_STATES` has something
        to bring back; a pin already open has not, and re-stamping `resolution_mode: "asked"` on it
        would be the only lasting effect — a mark nothing clears.
        """
        _require(arc in REOPEN_ARCS, f"arc must be one of {REOPEN_ARCS}; got {arc!r}")
        return "would_reopen" if pin["state"] in SETTLED_STATES else "nothing_settled"

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

        **`upheld` is a judgment, and v0.17 says whose.** It is the challenger's — the read-only
        role whose entire mandate is to doubt an elected oracle and hand the pin back. "Read-only"
        in the roster means *about decisions*: the challenger may reopen, and only the human's
        re-answer commits, so upholding is inside its mandate and electing is not. What the arc owes
        in exchange is the thing that makes the judgment checkable, and it is the same thing a
        `transcribed` decision owes: the `argument`. An upheld challenge with nothing stated reopens
        a human's election on an assertion, which is the unquoted relay one arc over — so a blank
        argument is refused here rather than being a matter of taste at the tool.

        **`upheld` and `reopened` are two facts, and the event records both.** A challenge upheld
        against a pin nobody ever settled is a true refutation that moves nothing; reading the move
        back off the pin's `substate` — which the reopen writes and nothing clears — is the exact
        two-carriers-for-one-fact bug v0.16 found in `cross_derive`'s return shape.
        """
        _require(target in CHALLENGE_TARGETS, f"target must be one of {CHALLENGE_TARGETS}")
        _require(challenge_class in CHALLENGE_CLASSES,
                 f"class must be one of {CHALLENGE_CLASSES}")
        _require(severity in SEVERITIES, f"severity must be one of {SEVERITIES}")
        _require(bool(str(argument).strip()),
                 "a challenge IS its argument — state what refutes the oracle. An upheld challenge "
                 "with nothing stated reopens a human's election on an agent's say-so, which is the "
                 "unquoted relay wearing the neutral arc's clothes")
        _require(source in _CHALLENGE_SOURCES,
                 f"source must be one of {_CHALLENGE_SOURCES}; got {source!r}. The upstream arc "
                 f"originates in the read-only role whose mandate is to doubt an elected oracle — "
                 f"and an arc that never elects may not sign itself with the door that does "
                 f"(`interview` was accepted here for four versions, on an event that then reopened "
                 f"a human's decided pin)")
        pin = self.pin(pin_id)
        reopened = bool(upheld) and self.reopen_verdict(pin, "challenge") == "would_reopen"
        event = {
            "id": self._next_id("chl_", self.data["decision_log"]),
            "pin_id": pin_id,
            "timestamp": _now(),
            "target": target,
            "class": challenge_class,
            "argument": argument,
            "severity": severity,
            "upheld": upheld,
            "reopened": reopened,
            "source": source,
            "policy_hash": self._policy_hash(),
        }
        self.data["decision_log"].append(event)
        if reopened:
            self._reopen_minimal(pin, "challenge", via=event["id"])
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

        `source` is held to `_CHALLENGE_SOURCES` (v0.20), the same closed vocabulary `challenge`
        checks. Mode 1 and mode 2 of one role, one parameter, one default: fixing the vocabulary at
        the mode that reopens and leaving it open at the mode that does not is how the next reader
        learns that the rule is about consequences rather than about who is speaking. It is not —
        the record says who wrote it, and a record that can be signed `interview` is a record about
        nobody.
        """
        pin = self.pin(pin_id)
        _require(source in _CHALLENGE_SOURCES,
                 f"source must be one of {_CHALLENGE_SOURCES}; got {source!r} — the same vocabulary "
                 f"`challenge` checks, because this is the same role's second mode")
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

        **v0.16 — three things this used to do that a read-only arc may not.** It reopened a pin the
        human had elected while appending nothing to the append-only log, so a decision could be
        un-made with no record that anything had happened; it did the same to a `resolved` or
        `deferred` pin, un-closing finished work on an agent's say-so; and it **overwrote
        `pin["question"]`** with options composed from the caller's own derivations. That third one
        is the worst and is why it is stated separately: `question.options[].id` is the carrier the
        entire offered-options rule anchors on, at both doors, so an agent that rewrites it decides
        what the human is allowed to choose next — the invariant v0.12–v0.14 built, dismantled from
        the side.

        So: the disagreement is appended as an immutable `xdr_` event; the pin's own question is
        left exactly as it was, and one is written only where none exists (creating a fork is what
        `surface_assumption` legitimately does; replacing one is not); and a **closed** pin is not
        reopened here at all — the event is recorded and `reopened` comes back false, because
        un-closing finished work needs its own justification and has its own arc. The other two arcs
        already worked this way: `challenge` and `reopen` each append before they move anything.
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
        # Recorded BEFORE anything moves, and recorded whatever happens next: an arc that reopens
        # without appending is a state change nobody can audit, which is exactly what this was.
        event = {
            "id": self._next_id("xdr_", self.data["decision_log"]),
            "pin_id": pin_id,
            "timestamp": _now(),
            "claim": record["claim"],
            "providers": record["providers"],
            "agreement": agreement,
            "reopened": agreement != "agree" and pin["state"] not in CLOSED_STATES,
            "source": "challenge:cross_derivation",
            "policy_hash": self._policy_hash(),
        }
        self.data["decision_log"].append(event)
        record["event_id"] = event["id"]
        if agreement == "agree":
            verification = pin.get("verification") or {}
            verification["rung"] = "cross_derived"
            verification["cross_derived_by"] = sorted(providers)
            pin["verification"] = verification
        elif event["reopened"]:
            if not pin.get("question"):
                # Only where there is no fork to destroy. The derivations stay on the pin either
                # way (`cross_derivations`) and `map.py` renders them immediately above the
                # question, so the human sees WHAT disagreed without an agent editing the menu they
                # are allowed to answer from.
                #
                # That second clause was a claim with no carrier when it was written: the field had
                # one writer — this line — and zero readers, so a disagreement that reopened a pin
                # reached the map, the summary and the projected AGENTS.md in no form at all. It was
                # written in the commit that closed a claim with no carrier. The reader came first
                # this time; do not weaken it back to "it is on the pin", which is true of every
                # field nobody reads.
                pin["question"] = {
                    "prompt": (f"Two independent providers disagree on: {record['claim']}. "
                               "Which derivation holds?"),
                    "options": [{"id": f"d{i}",
                                 "label": f"{d['provider']}/{d['model']}: {d['result']}"}
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
        """v0.5 downstream arc: production falsified the decision — reopen, don't decide.

        This is the arc `settlement_verdict` points at when it refuses to close finished work twice
        (*"Reopen it first"*), and for four versions that sentence named something no host could
        run. What makes it safe to hand an agent — where `decide` is not — is that it writes no
        outcome: there is no `outcome`, no `settles_as` and no way to add one without failing
        `TestComingBackIntoTheOpenSetIsGovernedToo`. So it needs no quote and no offered option.

        What it needs instead is the observation it rests on, stated in carriers rather than in
        prose: `fired` names which kind of tripwire tripped (`REOPEN_TRIGGERS`), `source` names
        where the reading came from (`_FEEDBACK_SOURCES`, composed from the same vocabulary a
        `flip_signal` declares its own source with), and `reason` is required to say what was
        actually seen. The last of those can only be checked for presence — whether a reason names
        *which class of assumption production falsified* is judgment, and `core/feedback-loop.md` is
        where that standard is set, not here.
        """
        pin = self.pin(pin_id)
        _require(bool(str(reason).strip()),
                 "a reopen must say what production showed. It un-settles work a human elected, and "
                 "'signal fired' with no reading is a state change nobody downstream can weigh")
        _require(fired in REOPEN_TRIGGERS,
                 f"fired must be one of {REOPEN_TRIGGERS}; got {fired!r}. A flip_signal with no "
                 f"telemetry degrades to manual_checkpoint — it does not become a new word")
        _require(source in _FEEDBACK_SOURCES,
                 f"source must be one of {_FEEDBACK_SOURCES}; got {source!r}. The downstream arc "
                 f"originates in production, and its origins are the ones a flip_signal can name")
        event = {
            "id": self._next_id("rev_", self.data["decision_log"]),
            "pin_id": pin_id,
            "timestamp": _now(),
            "reason": str(reason).strip(),
            "fired": fired,
            # Recorded, never inferred later from `substate`: the substate is written by whichever
            # arc moved the pin and is never cleared, so a second falsification of an already-open
            # pin would read as having moved it. Same fact, same fix, as `cross_derive`'s `reopened`.
            "reopened": self.reopen_verdict(pin, "reopen") == "would_reopen",
            "source": source,
            "policy_hash": self._policy_hash(),
        }
        self.data["decision_log"].append(event)
        self._reopen_minimal(pin, "reopen", via=event["id"])
        return event

    def cascaded_by(self, event_id: str) -> list[str]:
        """The pins an arc's event moved BESIDE its own — read off the records that call appended.

        The reader half of `_reopen_minimal`'s `cas_` events, and it exists so that no surface has to
        answer *"what else did this move"* by looking at the pins. The tool layer did exactly that:
        it listed every pin with `substate == "reopened"` and `state == "needs_input"`, and nothing
        anywhere clears that substate — so after one legitimate cascade, an unrelated `ledger_reopen`
        on an unrelated pin reported the earlier cascade's pins as its own radius. That is the same
        derive-from-an-uncleared-substate bug v0.16 removed from `cross_derive`'s return shape,
        re-introduced one layer up, against the very field this arc writes.

        One carrier, one reader: the per-pin events say what moved, this reads them back, and both
        tools call it, so the two arcs cannot report their radius differently.
        """
        return [e["pin_id"] for e in self.data["decision_log"] if e.get("via") == event_id]

    def _reopen_minimal(self, pin: dict, arc: str, via: str) -> list[str]:
        """THE only writer of the reopened state, and the only place either arc moves anything.

        `_settle`'s twin, and it is one function for the same reason: a rule that lives in an arc has
        to be remembered by the next arc, and there are exactly two of them precisely because nobody
        was counting. Returns the ids it moved BESIDE `pin`, so a caller never has to re-derive the
        radius from a state it just wrote.

        Reopen the minimum: the pin plus its settled `depends_on` dependents, transitively. An arc
        that reopens everything regenerates the very churn the skills cure.

        **Every pin it moves beside `pin` gets its own `cas_` record (v0.20), and that is the half of
        `_settle`'s twinning that was missing.** `_settle` appends one `stl_` per settlement; this
        appended nothing for anybody. Observed over real stdio: three pins each walked
        `add_pin → record_decision → add_remediation → done → resolve`, one `ledger_reopen` on the
        root took all three back into the open set, and the log named the root. Finished work was
        un-finished with no trail — the exact asymmetry the settlement work existed to remove, left
        standing on the direction that undoes it.

        The origin pin is deliberately **not** given one, on `_settle`'s own rule stated in
        `_settle`'s own words: *the event is appended only where something is not already carrying
        it*. The `rev_`/`chl_` event is about that pin and already records `reopened`, so a second
        entry beside it would be two carriers for one fact. What had no carrier at all is everything
        the closure swept up, and that is what this writes.

        `via` has no default on purpose. A cascade record that points at nothing is a state change
        with no cause, which is the condition this whole method was added to remove — so a third arc
        has to say which event it is cascading from before it can call this at all.

        **And every pin it moves has the claims a settlement door gates on invalidated (v0.22).**
        That is `SETTLEMENT_CARRIERS`, and it is the same asymmetry v0.20 removed one layer out: this
        wrote the state and left `verification` exactly as the closed pin had it, so a pin reopened
        BY an incident still told the next `resolve` that its behaviour had been observed — and
        `settlement_verdict` believed it, because the envelope is the single carrier of that fact by
        design. Writing the state without invalidating the claim the state was reached on is a reopen
        that only the surfaces see.
        """
        if self.reopen_verdict(pin, arc) != "would_reopen":
            return []
        substate = _SUBSTATE_BY_ARC[arc]
        to_reopen = {pin["id"]}
        changed = True
        while changed:
            changed = False
            for p in self.data["pins"]:
                if p["id"] in to_reopen:
                    continue
                # NOTE: three states, where `SETTLED_STATES` has four — `deferred` is not cascaded
                # over. Kept exactly as it was rather than "corrected", because whether a pin elected
                # OUT of scope rested on the falsified truth is a real question and no evidence here
                # settles it. Recorded in `docs/open-gaps.md` under §5 rather than resolved by
                # guessing: inventing a rationale for someone else's tuple is how a hardcoded list
                # acquires the authority of a decision.
                if any(dep in to_reopen for dep in p.get("depends_on", [])) \
                        and p["state"] in ("decided", "resolved", "accepted"):
                    to_reopen.add(p["id"])
                    changed = True
        cascaded: list[str] = []
        for p in self.data["pins"]:
            if p["id"] not in to_reopen:
                continue
            if p["id"] != pin["id"]:
                # The record `_settle` writes for every settlement, written here for every pin the
                # closure sweeps up. `via` joins it to the arc event that caused it, which is what
                # makes the radius readable (`cascaded_by`) instead of guessable from a substate.
                self.data["decision_log"].append({
                    "id": self._next_id("cas_", self.data["decision_log"]),
                    "pin_id": p["id"],
                    "timestamp": _now(),
                    "arc": arc,
                    "via": via,
                    "from_state": p["state"],
                    "to_state": "needs_input",
                    "substate": substate,
                    "policy_hash": self._policy_hash(),
                })
                cascaded.append(p["id"])
            p["state"] = "needs_input"
            p["substate"] = substate
            p["resolution_mode"] = "asked"   # a reopened truth is never re-defaulted silently
            self._invalidate_settlement_claims(p, arc, via)
        return cascaded

    def _invalidate_settlement_claims(self, pin: dict, arc: str, via: str) -> None:
        """Take back, on the pin, every claim a settlement door would read as permission (v0.22).

        One function for `SETTLEMENT_CARRIERS`' `invalidated` entries, called from the one place
        either arc moves a pin, for `_settle`'s reason: a rule that lives in an arc has to be
        remembered by the next arc.

        **Demoted, not deleted.** The rung comes off because the observation it named was refuted —
        and `settlement_verdict` reads a missing rung as the weaker claim, which is how absence is
        read everywhere in this file. `blocked_by` then says what refuted it, in the field the map's
        verification card and `interview.funnel` already read, so the pin tells a human why it cannot
        close instead of going quiet. `attempted` and `determinism` stay exactly where their writer
        left them: what was tried was still tried.

        **An envelope that claims nothing is left alone.** A pin with no `verification`, or one whose
        rung is already below `_CLOSING_RUNGS`, has made no claim for this to take back — and writing
        an envelope onto it would be manufacturing a statement the file never made, which is the
        `mark_correctness_unknown`/`cross_derive` overwrite v0.16 removed twice.
        """
        envelope = pin.get("verification") or {}
        if envelope.get("rung") not in _CLOSING_RUNGS:
            return
        pin["verification"] = {
            **envelope,
            "rung": None,
            "blocked_by": (f"this pin closed at the `{envelope['rung']}` rung; that observation "
                           f"was refuted by {via} ({arc}), and nothing has been observed since"),
        }

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

    def resolve(self, pin_id: str, evidence: Optional[str] = None,
                rung: Optional[str] = None) -> dict:
        """Close a pin against what was OBSERVED. Every rule is `settlement_verdict`'s (v0.16).

        `rung` is the door out of `correctness_unknown`, out of a stale weak envelope, and out of no
        envelope at all, and it has to exist: the rung check binds on every resolve, so without a
        way to state a *later* observation a pin could never close by any route — a gate with no
        gate-opening move is a wall, and people route around walls. What it cannot do is launder: it
        records a rung the caller claims to have reached, on a pin whose `blocked_by` stays exactly
        where its writer left it, so "it was blocked, then it was observed" reads as the history it
        is rather than as a clean slate.

        It is optional rather than required for one honest reason: `cross_derive` writes the
        `cross_derived` rung onto the pin when two providers agree, and that pin is already at a
        closing rung when it gets here. A pin carrying no such rung needs one passed, which is what
        `resolved` meaning OBSERVED costs.
        """
        pin = self.pin(pin_id)
        if evidence is not None:
            _require(bool(str(evidence).strip()), "evidence, when given, must not be blank")
            pin["evidence"] = evidence
        if rung is not None:
            _require(rung in _CLOSING_RUNGS,
                     f"a resolving rung is one of {_CLOSING_RUNGS}, not {rung!r} — the other two "
                     "rungs are what `correctness_unknown` exists to record")
            _require(pin.get("evidence") or evidence,
                     "a claimed rung needs the observation it rests on — pass `evidence`")
            pin["verification"] = {**(pin.get("verification") or {}), "rung": rung}
        self._settle(pin, "resolve", verification_rung=(pin.get("verification") or {}).get("rung"))
        return pin

    def _accept_implication(self, pin: dict) -> str:
        """What choosing `accept` on THIS pin actually does — asked of `settlement_verdict`, which
        is the authority on it and is one call away (v0.18).

        The sentence used to be a constant reading *"state becomes accepted, with the unverified
        remainder recorded"*, and it was false wherever it was printed. On a `defect` — the kind
        that reaches `correctness_unknown` without a decision, and therefore the kind that most
        often carries this generated fork — `settlement_verdict(pin, "accept")` is `wrong_kind`:
        leaving-as-is is the resolution of a `design_concern` and of nothing else. On a
        `design_concern` the door does open, but a non-defect reaches this state only from
        `decided`, where the pin already carries the human's own fork that v0.16 stopped
        overwriting — so the promise held on exactly the pins the menu was never written on.

        That inversion matters more than its severity suggests. The offered-options rule makes the
        option list a **promise about what can happen**, not a list of suggestions: an agent may
        record only an outcome this pin's own question offered. An option whose stated implication
        the machinery refuses turns that promise into decoration, on the one pin kind whose reader
        has already been told *we could not establish this is right*.

        Neither branch loosens `accept`'s kind rule, which is load-bearing and was moved into the
        predicate precisely so it would stop being re-litigated at each door. The kind is what the
        predicate answers on, so this reads the same before and after `_settle` moves the state.
        """
        if self.settlement_verdict(pin, "accept") == "would_settle":
            return ("the risk becomes the recorded decision; recording it as leave-as-is "
                    "(`accept_as_is`) then closes the pin as `accepted`, with the unverified "
                    "remainder recorded")
        return ("the risk becomes the recorded decision and the pin becomes `decided` — "
                f"leaving-as-is closes a design_concern and nothing else, so a {pin['kind']} "
                "cannot reach `accepted` from here")

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
        # The one door that moves a pin OUT of a settled state, and it is on the same table as the
        # four that move it in (v0.16) — `not_decided` is what "applies to work that was actually
        # done" now says, in the words every other door answers in.
        self._gate_settlement(pin, "correctness_unknown")
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
        # The state forces an explicit next move, so it carries a fork that asks for one — written
        # ONLY where the pin has none. It used to be written unconditionally, which is the same act
        # v0.16 removed from `cross_derive` one file over and named as dismantling the offered-options
        # rule from the side: `question.options[].id` is the carrier that rule anchors on at both
        # doors, so an agent-authored menu replacing the human's own fork decides what they are
        # allowed to choose next. Reproduced on a pin the human had DECIDED — their `s3|gcs` fork was
        # simply gone. The pin is in the interview view on its state alone (`interview_view` selects
        # `correctness_unknown`), and `blocked_by` is on the pin either way, so nothing is lost by
        # leaving an existing fork exactly where its author left it.
        if not pin.get("question"):
            pin["question"] = {
                "prompt": (f"Correctness could not be established: "
                           f"{pin['verification']['blocked_by']}. What now?"),
                "options": [
                    {"id": "retry", "label": "Retry with more context"},
                    {"id": "add_check", "label": "Add the missing check first",
                     "implication": "a new acceptance_criterion — the zone earns verifiability"},
                    {"id": "takeover", "label": "Manual takeover"},
                    {"id": "narrow", "label": "Narrow the scope to what IS verifiable"},
                    {"id": "accept", "label": "Accept the risk, unknown named",
                     "implication": self._accept_implication(pin)},
                ],
                "allow_freeform": True,
            }
        pin["resolution_mode"] = "asked" if pin["severity"] in _NEVER_SILENT \
            else pin.get("resolution_mode", "asked")
        self._settle(pin, "correctness_unknown",
                     verification_rung=pin["verification"]["rung"])
        return pin

    # -- views (the surfaces hold no state of their own) ------------------------

    def interview_view(self) -> list[dict]:
        """The interview IS the filtered view of pins awaiting a human answer, ordered by
        information gain: the ones that collapse the most downstream pins come first.

        Three states await an answer, for different reasons. `needs_input` means the decision has not
        been made. `correctness_unknown` (v0.7) means the decision was made and *verification*
        failed — the pin needs a next-move answer, not a re-election. `brainstorming` (v0.17) means
        somebody asked the brainstorm for options on this fork, which is what a hard fork is supposed
        to do when it gets stuck — and until v0.17 doing it took the fork **off** the agenda:
        `add_proposals` moves the pin out of `needs_input`, this view selected two states, and
        nothing moved it back. The pin stayed in `summary()`'s `open_questions` count the whole time,
        so the ledger reported a question the funnel could not produce.

        All three belong here for one reason: a state that awaits a human and appears on no surface
        is a black hole, and the pins most likely to be forgotten are exactly the one nobody could
        verify and the one that was hard enough to need help.

        The three states are `INTERVIEW_STATES` rather than a literal (v0.21). They were a literal
        here and re-derived on the map, which re-derived them wrongly — see that constant. Every
        field this sorts on is read through `pin_read`, because this and `summary` (which calls it)
        are what an agent runs first on a file it did not write.
        """
        reads = [(p, pin_read(p)) for p in self.readable_pins()]

        def transitive(pin_id: str, seen: frozenset = frozenset()) -> int:
            total = 0
            for _, r in reads:
                if pin_id in r["depends_on"] and r["id"] not in seen:
                    total += 1 + transitive(r["id"], seen | {r["id"]})
            return total

        pending = [(p, r) for p, r in reads if r["state"] in INTERVIEW_STATES]
        # An unverifiable blocker outranks information gain. Fan-out orders questions that are still
        # open; a `blocker|high` whose correctness could not be established is not a question to
        # sequence well, it is one that must not be skimmed past (the v0.3 threshold rule applied to
        # the verification exit).
        def unverifiable_first(r: dict) -> int:
            return 0 if (r["state"] == "correctness_unknown"
                         and r["severity"] in _NEVER_SILENT) else 1
        return [p for p, _ in sorted(
            pending,
            key=lambda pr: (unverifiable_first(pr[1]), -transitive(pr[1]["id"]),
                            severity_rank(pr[1]["severity"]), pr[1]["id"]),
        )]

    def summary(self) -> dict:
        # v0.21: through the guarded read, for the reason the log loop below was made `.get`-only in
        # v0.18 — this is the call an agent makes BEFORE acting, on a file it did not write. A pin
        # with no state counts under `""` rather than crashing the whole summary, and `pin_state`
        # in `pre_rule_events` two keys down is what says why that bucket exists.
        by_state: dict[str, int] = {}
        pins = self.readable_pins()
        for p in pins:
            state = pin_read(p)["state"]
            by_state[state] = by_state.get(state, 0) + 1
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
        # v0.16: how pins stopped being open, by door. Same reasoning as `decisions_by_evidence` one
        # axis over — a settlement read by nobody is the black hole this schema keeps finding, and
        # "4 resolved, 9 deferred" is a different ledger to walk into than "13 closed". The doors
        # fail differently (a defer avoids a question; a resolve answers one), so they are counted
        # apart and never summed. Both carriers are read, because a settlement is recorded by the
        # election that produced it where there is one and by its own event where there is not; a
        # count over one of the two would be exactly the half-blind reading v0.13 was about.
        by_door: dict[str, int] = {}
        log = self.readable("decision_log")
        for e in log:
            # v0.18: every read here is a `.get`, and the dispatch key most of all. It was
            # `e["id"]`, which made a log entry with no id a bare `KeyError` — `ledger_summary`
            # returned `isError` over the wire and the agent's FIRST call on a file it did not
            # write was the one that failed. No version of this package wrote such an entry, so it
            # is hand-editing rather than a legacy shape; the principle is the same one the
            # `settles_as` skip below already follows and does not carry that qualification.
            # Reading a ledger is never the operation that fails on it. An entry this loop cannot
            # dispatch is reported by `nonconforming` under `log_entry_kind` (visible in
            # `pre_rule_events`, right beside this count), and a recognised entry missing the field
            # its own kind is counted by lands in `unrecorded` — the same answer `decision_rung`
            # already gives one line down, rather than a second vocabulary for absence.
            eid = str(e.get("id") or "")
            if eid.startswith("fal_"):
                cls = e.get("class") or "unrecorded"
                by_failure[cls] = by_failure.get(cls, 0) + 1
            elif eid.startswith("stl_"):
                door = e.get("door") or "unrecorded"
                by_door[door] = by_door.get(door, 0) + 1
            elif eid.startswith("ev_"):
                rung = decision_rung(e) or "unrecorded"
                by_evidence[rung] = by_evidence.get(rung, 0) + 1
                # Counted only where this runtime can name the door. `_door_for` REFUSES a
                # `settles_as` naming a state no election produces — the right answer on the write
                # path, and a crash on the read path: one such event made `ledger_summary` return
                # `isError` over the wire, on exactly the file class `nonconforming()` exists to
                # describe. Reading a ledger must never be the operation that fails on it; the
                # summary is what an agent calls BEFORE acting, so a file it cannot read is a file
                # it acts on blind. Nothing is hidden by skipping: the same event is already
                # reported by `pre_rule_events["settled_state"]`, from the same rule table, which is
                # the surface that says "this file predates or breaks a rule" for every other rule.
                settles_as = e.get("settles_as") or "decided"
                if settles_as in _ELECTION_STATES:
                    door = _door_for(settles_as)
                    by_door[door] = by_door.get(door, 0) + 1
        # v0.15: the same count for the POLICIES, because a policy IS a decision — one the human
        # made over a whole cluster — and the count above says nothing about the election every
        # `cascaded` entry in it rests on. A policy elected with no rung recorded, or relayed with
        # no quote, is the thing to weigh before trusting the cascade that came out of it. Read off
        # `Policy.evidence` directly: unlike a DecisionEvent's rung there is nothing to derive here
        # (a policy is elected, never cascaded from another), so a reader function would be
        # ceremony. `policies` stays a plain count so an existing caller keeps its answer.
        pol_by_evidence: dict[str, int] = {}
        policies = self.readable("policies")
        for p in policies:
            rung = str(p.get("evidence") or "") or "unrecorded"
            pol_by_evidence[rung] = pol_by_evidence.get(rung, 0) + 1
        return {
            # The floor, not this runtime's version: it stays where the file's own content puts it
            # while `pre_rule_events` is non-empty, so the two are read together.
            "version": self.data.get("version"),
            "pre_rule_events": {rule: len(ids) for rule, ids in self.pre_rule.items()},
            # Every count below is over what a reader can actually walk, so a file with an
            # unreadable entry is short by one HERE and says so two lines up under `entry_shape`.
            # The alternative — counting an entry nothing else in this dict can describe — is a
            # total that no other number in the summary adds up to.
            "pins": len(pins),
            "by_state": by_state,
            "events": len(log),
            "policies": len(policies),
            "policies_by_evidence": pol_by_evidence,
            "open_questions": len(self.interview_view()),
            "failures_by_class": by_failure,
            "decisions_by_evidence": by_evidence,
            "settlements_by_door": by_door,
            "premortems": sum(1 for p in pins if p.get("premortem")),
        }


def _json_arg(raw: Optional[str], field: str) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--{field}: invalid JSON ({exc})")
