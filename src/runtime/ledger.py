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
from typing import Any, Iterable, Optional

SCHEMA_VERSION = "0.30"

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
#
# `SCHEMA_VERSION` is appended rather than typed (v0.27): the two are one fact stated twice, and the
# bump to 0.27 raised the stamp and left the tuple, so this runtime refused every file it had just
# written — `_open_or_create` on its own output, `LedgerError: schema '0.27' is not readable`. It was
# found by a plant in an unrelated gate, which is luck; the constructor is the only consumer and
# nothing asserted the reflexive case. `tests/test_ledger.py::TestThisRuntimeReadsWhatItWrites` does
# now, and this line makes the failure unreachable rather than merely tested.
READABLE_VERSIONS = ("0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.11", "0.12", "0.13",
                     "0.14", "0.15", "0.16", "0.17", "0.18", "0.19", "0.20", "0.21", "0.22",
                     "0.23", "0.24", "0.25", "0.26", "0.27", "0.28", "0.29", SCHEMA_VERSION)

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

# The rungs whose entire claim is that an AGENT carried a human's words, and which therefore owe the
# words (v0.24). Named here so that "an agent-relayed election must quote the human" has one carrier
# instead of four sites that agree today: `mcp/tools.py` spelled the rule out at `record_decision`
# twice, at `record_policy`, and at `ledger_defer`, in four sentences nothing held together, and
# `mcp/tools.py::_require_quote` is the one door all four now pass through.
#
# The rule is enforced at the MCP boundary rather than in `decide`, and that placement is
# deliberate and unchanged (see `decide`): the boundary is the only place an AGENT makes the claim,
# and taxing this library's own callers for a risk none of them carry would be a second contract.
# What lives here is the membership question — WHICH rung owes a quote — because that is a fact
# about the schema, and the tuple is what a fourth rung would have to join to acquire the rule.
QUOTED_RUNGS = ("transcribed",)

# The one value in the outcome position that is NOT an option id: at both election doors it selects
# the "answer in your own words" path, where the human's words are the outcome rather than evidence
# for it. It is a bare string in an agent-facing signature and so cannot become unrepresentable the
# way `server.py::_ACCEPT_AS_IS_ROW` did (that one maps to `None`, which no option id can be) — and
# nothing constrains an option id, because an agent authors them at `add_pin`. A question offering
# an option called `freeform` therefore renders two branches that arrive at the door as one token:
# the human picks the option, `record_decision` takes the freeform arm, and the ledger records the
# free text as the outcome of a fork that never offered it — on the `elicited` rung, where the whole
# claim is that nobody touched the value. So the collision is refused where the fork is COMPOSED
# (`_validate_question`), not resolved by precedence where it is elected: two branches a caller
# cannot tell apart is the same defect as two rows a human cannot tell apart, one layer down.
FREEFORM_OUTCOME = "freeform"

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

# **How the rule "finished work is refused" reaches every per-pin write door (v0.24).** One entry
# per door, four dispositions, and the table is what a new door has to join before the suite passes
# — `tests/test_ledger.py::TestFinishedWorkIsRefusedAtEveryDoorThatWritesToAPin` derives the roster
# from the MCP tools that take a `pin_id` and save, so a door added after this line cannot be
# missing from it and cannot be silent about which of the four it is.
#
# It exists because the rule was PROSE at the two doors this branch added it to and absent
# everywhere else. Reproduced over stdio on one `resolved` defect: `ledger_set_question` and
# `ledger_add_proposals` refused it in near-identical sentences, and `ledger_add_remediation`,
# `ledger_set_remediation_status`, `ledger_premortem` and `ledger_set_readiness` all wrote to it
# happily — a second remediation item on closed work, a premortem of a plan that already finished,
# a landing-zone verdict that can add `depends_on` edges to a pin nobody will build.
#
#   * `refuse` — writing here un-finishes the work, so the door says so and names the arc that does
#     it properly. `CLOSED_STATES` and not `SETTLED_STATES`, which is the line `set_question` drew
#     first: a `decided` pin is re-electable by the human, and everything downstream of an election
#     is still legitimately being planned.
#   * `settlement` — the door already asks `settlement_verdict`, which answers `already_closed`
#     before any branch speaks. A second refusal here would be a second contract for one rule.
#   * `arc` — the way BACK. Refusing finished work at these would be refusing the only move that
#     un-finishes it, which is the wall this package keeps writing gates against.
#   * `records_only` — an observation ABOUT the pin that changes no state a builder reads.
#     `label_failure` is the honest case and the reason this is a table rather than a blanket: a
#     failure in production is exactly what you label on a `resolved` pin, and then you `reopen`.
#     `release` (v0.30) is the second: on finished work there is no claim left to drop — `_settle`
#     already took it — so the door is a no-op that reports `released: false`, and refusing it would
#     make cleaning up after a dead session a thing you have to check before doing.
CLOSED_WORK_DISPOSITIONS = ("refuse", "settlement", "arc", "records_only")
PIN_WRITE_DOORS = {
    "set_question": "refuse",
    "add_proposals": "refuse",
    "add_remediation": "refuse",
    "set_remediation_status": "refuse",
    "set_readiness": "refuse",
    "premortem": "refuse",
    "decide": "settlement",
    "accept": "settlement",
    "defer": "settlement",
    "resolve": "settlement",
    "mark_correctness_unknown": "settlement",
    "reopen": "arc",
    "challenge": "arc",
    "cross_derive": "arc",
    "label_failure": "records_only",
    # v0.30. `claim` refuses for the plain reason: taking finished work reserves a unit of work
    # nobody is going to do, and the pin would sit off the frontier held by a session that will
    # never release it. It is the one door here whose refusal is not about un-finishing anything.
    "claim": "refuse",
    "release": "records_only",
}

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
# **Three, and the third arrived by being found rather than by being counted (v0.24).**
# `cross_derive(agreement="disagree")` writes `"reopened": true` on its own event and moved the pin
# into the open set with its own three lines of state — so it was an arc in everything but
# membership, and membership is what the tolls are charged on. It paid none of them: v0.22's carrier
# invalidation, v0.20's `cas_` record, and the closed-state question all live at `_reopen_minimal`,
# which it never called. Reproduced over real stdio: `add_pin(defect) -> add_remediation -> done ->
# cross_derive(agree)` (the envelope reaches the `cross_derived` rung) `-> cross_derive(disagree)`
# took the pin back into the open set still carrying that rung, and `ledger_resolve` then closed it
# with `evidence="no new observation of any kind"`.
#
# The lesson is the one this branch keeps re-learning in new clothes: **a rule fixed for the members
# of a set is unfixed for whatever satisfies the set's definition without being in it.** So the arcs
# are what they do, and the two axes on which the three differ are declared below rather than
# expressed as a second code path.
REOPEN_ARCS = ("reopen", "challenge", "cross_derive")

# The substate each arc leaves behind. A table rather than a string every caller passes, for the
# same reason `_STATE_BY_DOOR` is one: the substate IS which arc ran, so a second carrier for that
# fact is a divergence waiting to happen.
_SUBSTATE_BY_ARC = {"reopen": "reopened", "challenge": "challenged",
                    "cross_derive": "contested"}

# Which states each arc MOVES, and whether it sweeps up the settled dependents with it. The two
# facts that used to be the difference between "an arc" and "cross_derive", written down so that
# being different costs a table entry instead of a separate writer.
#
#   * **`ARC_MOVES`** — the downstream and upstream arcs act on work that was SETTLED (an
#     observation about a pin nobody settled is still true and moves nothing). A cross-derivation
#     disagreement is about a CLAIM rather than about an election, so it also marks an open pin
#     `contested` — but it may not un-close finished work, which is v0.16's narrowing of this same
#     call and is why the complement is spelled against `CLOSED_STATES`.
#   * **`ARC_CASCADES`** — the two settlement arcs reopen the settled `depends_on` closure, because
#     what was falsified was the truth those dependents rest on. `cross_derive` does not, and that
#     is `cross_derive`'s own long-standing decision kept verbatim: *nobody yet knows which side is
#     wrong, and reopening the neighbourhood on an unresolved disagreement would be churn, not
#     caution.* Declaring it is the change — an arc that cascades nothing now says so where a reader
#     of the table can see it, instead of by not being an arc.
ARC_MOVES = {
    "reopen": SETTLED_STATES,
    "challenge": SETTLED_STATES,
    "cross_derive": tuple(s for s in STATES if s not in CLOSED_STATES),
}
ARC_CASCADES = {"reopen": True, "challenge": True, "cross_derive": False}

# Every carrier a SETTLEMENT DOOR gates on, and what the way BACK into the open set owes each one
# (v0.22). The question this table exists to force, asked once here instead of per arc:
# **which carriers does a settlement door decide on, and which of them does the reopen leave
# standing?**
#
# **The table said DOOR and its gate asked one FUNCTION (v0.26).** `TestTheWayBackOwesTheDoorsTheir
# Carriers` derived the set from the AST of `settlement_verdict` alone, so the sentence above was
# proved of the predicate and asserted of the five doors — and `resolve` gated on a fifth carrier
# the table does not name: `_require(pin.get("evidence") or evidence)`, the pin's OWN `evidence`
# field, which is the observation the LAST resolve rested on. After a reopen that field names
# precisely what production refuted, so the stale sentence satisfied the demand for the fresh one.
# The gate now derives from every door's `_require` conditions as well as from the predicate — a
# `_require` is this runtime's one refusal, so a read inside one is a read the settlement is
# decided by — and `resolve` now demands the observation THIS call rests on. The table is unchanged
# because the fix removed the carrier rather than adding a disposition: an arc cannot owe anything
# to a claim no door reads.
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
# from the arc table rather than re-listed beside it. It carried `"contested"` as a literal for four
# versions, with a comment explaining that `cross_derive` *"is the third writer and the only one that
# is not an arc"* — which is the whole of v0.24's finding, written down beside the table and read by
# nobody as the exemption it was. There is no literal here now.
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
REOPENED_SUBSTATES = tuple(_SUBSTATE_BY_ARC[a] for a in REOPEN_ARCS)

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

# What `Ledger.reopen_verdict` can answer. Neither non-moving answer is a refusal: every arc appends
# its event either way and reports whether anything moved, which is the shape `cross_derive` was
# corrected to in v0.16 for the identical condition — an observation about a pin that cannot be
# un-settled is still an observation, and dropping it would lose the one signal the learning layer
# and the premortem gate both read (`has been reopened before`).
#
# They are two answers and not one because they are two different facts about the pin, and a caller
# acts differently on each: `nothing_settled` says there was nothing to bring back (reached only by
# the two arcs that act on settled work), `already_closed` says the work is FINISHED and the way in
# is the door that records why (reached only by `cross_derive`, whose `ARC_MOVES` stop at
# `CLOSED_STATES`). Merging them would print "nothing was settled" over a `resolved` pin.
REOPEN_BUCKETS = ("would_reopen", "nothing_settled", "already_closed")

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

# -- v0.30: the claim -----------------------------------------------------------------------------
#
# Who is working on this pin RIGHT NOW, and since when. Both `null` by default, and neither is a
# state: a pin can be `needs_input` and claimed, or `decided` and claimed, and folding ownership
# into the lifecycle would multiply every state in `STATES` by two and break every transition table
# in the spec.
#
# It exists because the concurrency this package already invites — *"the user may run unblocked
# items in parallel"* — was safe against corruption and unprotected against DUPLICATION.
# `branch-lifecycle` declares a scope's file globs and `conflicts_with` excludes two scopes that
# touch the same files, so two worktrees cannot corrupt each other. All of that is about files. Two
# sessions resolving the same pin may legitimately touch DISJOINT files — one writes the fix, one
# writes the test — so `conflicts_with` correctly reports no conflict while both do the same work.
# The overlap is in the work ITEM, which is the one thing the ledger owns and the filesystem does
# not. On a `grilling`-shaped pin it is worse than waste: the second session asks the human a
# question the first already answered, because sessions share no context.
#
# **It is advisory, and that is a design choice rather than a shortcut.** A claim never gates a
# write: an agent that legitimately needs to write a claimed pin (the human said so) must not be
# stopped by it. The failure it prevents is duplicated WORK, not concurrent ACCESS — the ledger's
# existing write discipline covers the latter, and conflating the two would put a lock in a file
# nobody can unlock.
CLAIM_CARRIERS = ("claimed_by", "claimed_at")

# What a reader may conclude about a pin's ownership. Three answers, because "claimed" alone cannot
# distinguish the two cases a scheduler must treat differently: a peer is on it, versus a session
# died holding it. There is no daemon here to reap the second, so staleness is computed at READ time
# from `claimed_at` — which is why the TTL below is a number this file has to declare.
CLAIM_STATES = ("unclaimed", "live", "stale")

# HYPOTHESIS: how long a claim stays live without being renewed. One hour is a guess about how long
# a session works one pin before it either settles it or dies, and it is tuned from one side only:
# too short re-offers a pin somebody is still on (duplicated work, the thing this prevents), too
# long parks a pin nobody is on (a frontier that shrinks and never grows back). The asymmetry says
# which way to err — a stale claim is reclaimed with a note, and a claim that expires under a live
# session is silently the bug this field was added to remove — so it errs long. Renewing is free
# (`claim` by the same holder re-stamps it), so a session that outlives an hour is expected to say
# so rather than to be assumed dead.
CLAIM_TTL_SECONDS = 3600

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
    "cross_derivations", "evidence", "claimed_by", "claimed_at",
)


class LedgerError(ValueError):
    """A spec rule was violated."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise LedgerError(msg)


def _require_objects(items: Any, name: str, why: str) -> list:
    """THE refusal for a list argument whose members this runtime indexes (v0.25). Returns the list.

    Three write doors refused the same malformed argument three different ways, and two of them did
    not refuse it at all: `premortem` said *"each failure mode must be an object"*, while
    `add_proposals` reached `p.get("recommended")` and `add_pin`'s assumption check reached
    `src.get("source")` — both a raw `AttributeError` over the wire, on an argument an agent
    composes and therefore gets wrong. A refusal is a sentence a caller can act on; a `TypeError`
    from inside a comprehension is a stack trace naming a line of ours about a mistake of theirs.

    Same shape as the read half one section up and for the same reason: the rule *"a member of this
    list is an object"* gets ONE carrier, and
    `tests/test_mcp_server.py::TestNoWriteDoorDiesOnAMemberOfAListArgument` quantifies over every
    write tool the server serves rather than over the three that were reported.
    """
    _require(isinstance(items, list),
             f"{name} must be a list — {why}; got {type(items).__name__}")
    for index, item in enumerate(items):
        _require(isinstance(item, dict),
                 f"{name}[{index}] must be an object — {why}; got {type(item).__name__}")
    return items


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


def refuted_claim(pin: Any) -> str:
    """The refutation standing on this pin's `verification` envelope, or `""` (v0.24).

    Two carriers make one fact, and neither alone is it: `blocked_by` is HISTORY — `resolve` keeps it
    verbatim when a later observation closes the pin, so *"it was blocked, then it was observed"*
    reads as the sequence it is — and a rung below `_CLOSING_RUNGS` only says nothing has closed it
    yet. Together they say the thing a writer has to ask: **something refuted this pin's claim and
    nothing has answered it.**

    It exists because a closing rung may be written by more than one door, and the doors rest on
    different things. `resolve` rests on an observation the caller states (`evidence` is required
    with `rung`), which is the declared way out of a refutation and must stay open — a gate with no
    gate-opening move is a wall. `cross_derive` rests on two providers re-deriving the claim, which
    is not an observation of anything: reproduced over real stdio four calls apart,
    `resolve(rung="observed") -> reopen(fired="incident")` demoted the envelope and wrote
    `blocked_by`, `ledger_resolve` correctly refused as `unverified`, and one agent-authored
    `cross_derive(agreement="agree")` merged a closing rung back onto that same envelope and the pin
    closed. The reopen arc's whole purpose, undone by the door beside it.

    Never raises, on `pin_read`'s rule: a reader is not the operation that fails on a file.
    """
    envelope = pin.get("verification") if isinstance(pin, dict) else None
    if not isinstance(envelope, dict) or envelope.get("rung") in _CLOSING_RUNGS:
        return ""
    return str(envelope.get("blocked_by") or "")


# Every door that writes the `rung` of a `verification` envelope, and what it rests on (v0.24).
# Declared for `SETTLEMENT_CARRIERS`' reason, one field further in: `_CLOSING_RUNGS` is what
# `settlement_verdict` opens on, so *who may write one* is a question with as many answers as there
# are writers, and there were four with nothing naming them together. Held to the AST of everything
# that ships by `tests/test_ledger.py::TestOnlyAFreshObservationRaisesARefutedClaim`, so a fifth
# writer has to say which of these it is before the suite passes.
#
#   * `fresh_observation` — the caller states what was seen, and the runtime demands it (`resolve`
#     requires `evidence` alongside `rung`). This is the way out of a refutation, and stays open.
#   * `re_derivation` — a different provider reached the same claim. A genuine strengthening and
#     **not an observation**, so it may not overwrite a standing refutation: gated on
#     `refuted_claim`.
#   * `records_absence` — writes a rung BELOW the closing ones, or none at all. It cannot open a
#     settlement gate by construction, so it is asked nothing.
#   * `demotion` — the arcs' own writer, which takes a closing rung OFF. It is what creates the
#     condition the first two are judged against.
VERIFICATION_RUNG_WRITERS = {
    "resolve": "fresh_observation",
    "cross_derive": "re_derivation",
    "mark_correctness_unknown": "records_absence",
    "_invalidate_settlement_claims": "demotion",
}
RUNG_WRITER_KINDS = ("fresh_observation", "re_derivation", "records_absence", "demotion")

# Which rungs each kind of writer may actually put on an envelope (v0.26).
#
# **The table above declared four kinds and enforced none of them, and the one that mattered was
# the one whose description asserted the enforcement.** `records_absence` reads *"writes a rung
# BELOW the closing ones, or none at all. It cannot open a settlement gate by construction, so it
# is asked nothing"* — and `mark_correctness_unknown` accepted `rung` against `VERIFICATION_RUNGS`,
# the whole vocabulary, closing rungs included. So the door whose entire meaning is *correctness
# could NOT be established* handed the pin the claim that its behaviour WAS observed, on
# `verification`, which `SETTLEMENT_CARRIERS` names as the single carrier `resolve` opens on.
# Reproduced over real stdio against the shipped plugin, five calls with no human in the loop:
# `resolve(rung="observed")` closed the pin, `reopen(fired="incident")` demoted the envelope and
# `ledger_resolve` correctly refused as `unverified` — then one
# `ledger_mark_correctness_unknown(blocked_by="no oracle exists for this", rung="observed")` wrote
# the closing rung straight back onto that envelope, and `ledger_resolve(evidence="I looked")`
# closed the pin green. That is v0.24's laundering finding one door over: `cross_derive` was gated
# on `refuted_claim` because a re-derivation is not an observation, and the door beside it could
# still simply assert one.
#
# So the third column stops being prose. `_writable_rung` is its one refusal, every writer in the
# table above pays it with its own name, and
# `tests/test_ledger.py::TestOnlyAFreshObservationRaisesARefutedClaim` asserts that from the AST —
# so a fifth writer must say which kind it is AND go through the gate before the suite passes.
#
#   * `fresh_observation` — `_CLOSING_RUNGS`, and nothing weaker: `resolve` is the door that CLOSES,
#     and a rung below the closing ones is what `correctness_unknown` exists to record.
#   * `re_derivation` — `cross_derived` alone. It is not an observation, and `refuted_claim` is the
#     second half of that rule, unchanged.
#   * `records_absence` — everything that is NOT a closing rung, plus `None`. Derived from
#     `_CLOSING_RUNGS` rather than listed, so a rung added to `VERIFICATION_RUNGS` lands on the
#     correct side of this line without anybody choosing.
#   * `demotion` — `None` only. Taking a claim off is the whole of what the arcs do to an envelope.
RUNG_WRITER_RUNGS = {
    "fresh_observation": _CLOSING_RUNGS,
    "re_derivation": ("cross_derived",),
    "records_absence": tuple(r for r in VERIFICATION_RUNGS if r not in _CLOSING_RUNGS) + (None,),
    "demotion": (None,),
}


def _writable_rung(writer: str, rung: Any) -> Any:
    """THE refusal for a rung a door may not write — the one carrier of `RUNG_WRITER_RUNGS`.

    Returns the rung, so a writer pays it in the expression that writes it and cannot pay it
    somewhere the value then changes.
    """
    kind = VERIFICATION_RUNG_WRITERS[writer]
    allowed = RUNG_WRITER_RUNGS[kind]
    _require(rung in allowed,
             f"`{writer}` is a {kind} writer of the verification envelope, so the rungs it may "
             f"record are {allowed}; got {rung!r}. `verification.rung` is the single carrier "
             f"`settlement_verdict` opens the `resolved` gate on, and {_CLOSING_RUNGS} say the "
             f"behaviour was OBSERVED — only `resolve`, which demands the observation it rests on, "
             f"may state that.")
    return rung


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
    # v0.24 — the rung that owed nothing. `elicited` is unreachable BY AN AGENT (the path that asked
    # computes it — the server's elicitation branch, or the human-run door added in v0.29 — and the
    # agent holds the value in neither), `transcribed` demands `human_answer` at every door,
    # `cascaded` demands `policy_id` on both sides of the biconditional above — and `brief` demanded
    # nothing at all, so `interview_expand(brief_decisions=…)` moved pins to `decided` on the
    # caller's word that a project brief said so. The rung means *answered from the brief without
    # asking*, so what it owes is the brief: the passage, verbatim, per fork. Same shape as
    # `human_answer` and for the same sentence — without it, an honest reading of a brief and an
    # invented one are the same line in the ledger.
    #
    # A biconditional, like `cascade_policy_id`: only a brief-rung event may carry the field, so it
    # cannot become a decoration other rungs sprinkle on. It is the second rule in this table with a
    # retroactive edge, and the edge is stated rather than discovered — a ledger whose `brief` events
    # predate this carries no such passage and none can be reconstructed, so `nonconforming` reports
    # them under `pre_rule_events` and the version floor does not rise. That is the honest reading of
    # those files: they record a claim nothing backs.
    ("brief_quote",
     lambda e: (e.get("evidence") == "brief") == bool(str(e.get("brief_quote") or "").strip()),
     lambda e: "the `brief` rung means the project brief settled this fork without anyone being "
               "asked, so the brief is the evidence and `brief_quote` must carry the passage "
               "verbatim — and only a brief-rung event may carry one, or the field claims a "
               "document that decided nothing"),
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


# -- THE SHAPE TABLE: the one carrier the read path, the rules and the corpus all derive from -----
#
# **v0.25, and the lesson is the corpus rather than any one field.** The three parts above —
# `PIN_RULES` ↔ `pin_read` held by set equality, `nonconforming` replaying the table — were correct
# and were checked against a HAND-WRITTEN list of seven broken pins in two test modules. A reviewer
# extended that list with eleven more shapes, every one of them naming a field `PIN_FIELDS` already
# declares, and the unchanged gates failed: `verification: "observed"` and
# `brainstorm: {"proposals": "opt_a"}` killed `interview_next` over stdio, on the surface the branch
# had spent three rounds naming. **The gates proved what somebody had thought to write down.**
#
# So the schema declares the SHAPE of every path a reader indexes, once, and everything else is
# derived from it: the rules (`PIN_RULES`), the substitution (`pin_read`), the sentence the map
# prints (`shape_note`), and the test corpus. A field added tomorrow is covered by all four without
# anyone remembering.
#
# **The membership rule, stated so the table can be held to the writers rather than trusted.** A
# path is declared iff a reader can INDEX INTO its value — every object and every list this runtime
# writes into a record — plus the top-level scalars a reader coerces (`title` is `.strip()`ped,
# `severity` is ranked, `id`/`state` are bucketed). A scalar nested inside a declared object is NOT
# here, and the reason is the same one that keeps `EVENT_RULES` narrow: nothing indexes into a
# string, so a wrong-typed one renders oddly and kills nothing.
# `tests/test_ledger.py::TestTheShapeTableIsTheWritersOwnShapes` walks every writer and holds both
# directions of that rule.
#
# The shape vocabulary is closed and small. `None` always holds — every one of these fields is
# optional and `add_pin` itself writes `as_is`/`to_be`/`question`/`brainstorm`/`decision` as `None`,
# so "absent" and "explicitly null" are one case and always were.
SHAPE_HOLDS = {
    "str": lambda v: isinstance(v, str),
    "object": lambda v: isinstance(v, dict),
    "list": lambda v: isinstance(v, list),
    "list[str]": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
    "list[object]": lambda v: isinstance(v, list) and all(isinstance(x, dict) for x in v),
}
#: What a reader gets where the file's value does not hold its shape. Never a plausible value: `""`
#: is not `low`, `{}` is not an invented envelope, `[]` is not a DAG edge. The substitution is
#: always the EMPTY reading, and `nonconforming` names every one of them.
SHAPE_EMPTY: dict = {"str": "", "object": {}, "list": [], "list[str]": [], "list[object]": []}
#: The English for a shape, in the sentence a surface prints to a human.
SHAPE_ENGLISH = {"str": "a string", "object": "an object", "list": "a list",
                 "list[str]": "a list of strings", "list[object]": "a list of objects"}

#: Every path inside a `Pin` whose value a reader indexes into, plus the coerced top-level scalars.
#: Dotted where it is nested. Ordered as the schema lists them (`PIN_FIELDS`), so `PIN_RULES` and
#: `pre_rule_events` read in the envelope's own order rather than alphabetically.
PIN_SHAPES = {
    "id": "str",
    # v0.26 — the THIRD closed vocabulary a pin carries, and until now the only one with no rule.
    # `state` and `severity` are both here with a membership rule in `PIN_STRONGER`; `kind` was in
    # neither table, so a pin whose `kind` was `7` or `"defekt"` was reported by `nonconforming` on
    # no surface while its two siblings were reported on every one. It is not a nested scalar and
    # not free text: `settlement_verdict` refuses `accept` on anything but a `design_concern` and
    # opens two branches for a `defect`, `_accept_implication` prints it, and the map and the
    # projection both dispatch on it — so a value outside `KINDS` silently takes a pin down a
    # branch nobody elected. That is exactly what the membership rule below means by a scalar a
    # reader COERCES, and it belongs to the same class as the two that were already declared.
    "kind": "str",
    "title": "str",
    "severity": "str",
    "state": "str",
    "provenance": "list[object]",
    "anchors": "list[object]",
    "as_is": "object",
    # The one key inside `as_is` that is not free-form per kind: the map builds a `Set` out of it to
    # colour the layers that disagree, so it is indexed and therefore declared. Found by this
    # table's own writer gate rather than by reading the map — which is what the gate is for.
    "as_is.disagreeing_layers": "list[str]",
    "to_be": "object",
    "question": "object",
    "question.options": "list[object]",
    "brainstorm": "object",
    "brainstorm.proposals": "list[object]",
    "decision": "object",
    "depends_on": "list[str]",
    "remediation": "list[object]",
    "verification": "object",
    "verification.attempted": "list",
    "verification.cross_derived_by": "list[str]",
    "readiness": "object",
    "readiness.zone": "object",
    "readiness.evidence": "object",
    "readiness.hardens": "list[str]",
    "premortem": "object",
    "premortem.failure_modes": "list[object]",
    "premortem.guardrails": "list",
    "premortem.abort_criteria": "list",
    "premortem.paper_tigers": "list[object]",
    "cross_derivations": "list[object]",
    # v0.30 — two top-level scalars a reader COERCES, which is the half of the membership rule that
    # is not about indexing. `claimed_at` is parsed (`datetime.fromisoformat`), and a value that is
    # not a string raises inside `claim_state`, which `frontier` calls for every pin — so one
    # hand-edited timestamp would take the scheduler down for the whole file. `claimed_by` is
    # coerced to a bool by the same predicate and printed by the map: `{"who": "a"}` is truthy, so
    # an unreadable value would render a pin as held by a holder no surface can name. Both read as
    # the EMPTY string where the file's value does not hold, and `""` is falsy, so the honest
    # reading of a claim this runtime cannot read is *not claimed* — never an invented holder, and
    # never a live claim nobody can release.
    "claimed_by": "str",
    "claimed_at": "str",
}

#: The same table for the ledger's other record. Three paths, and all three were already rules.
POLICY_SHAPES = {"id": "str", "rule": "str", "applies_to": "object"}

#: Where a path's rule is STRONGER than its shape, the stronger one is the rule — one name, one
#: verdict, no second entry saying a weaker version of the same thing. Each is `(holds, message)`
#: and each implies the declared shape, which
#: `tests/test_ledger.py::TestTheShapeTableIsTheWritersOwnShapes` asserts rather than assumes.
PIN_STRONGER = {
    "id": (lambda v: isinstance(v, str) and bool(v),
           lambda v: "a pin carries no `id`, so nothing can depend on it, name it or link to it"),
    # `isinstance` first, and it is not belt-and-braces: `KINDS` is the one closed vocabulary in
    # this file held as a `set`, so `v in KINDS` on an unhashable value raises `TypeError` instead
    # of answering False — and this predicate runs inside `nonconforming`, which runs inside
    # `Ledger.__init__`. Found by the derived corpus on its first run: `kind: {"rung": "observed"}`
    # took every surface down at the load, which is the failure this whole table exists to remove.
    "kind": (lambda v: isinstance(v, str) and v in KINDS,
             lambda v: f"kind must be one of {sorted(KINDS)}; got {v!r} — it is what the pin IS, "
                       f"and `settlement_verdict` sends a `defect` and a `design_concern` down "
                       f"different branches on it"),
    "state": (lambda v: v in STATES,
              lambda v: f"state must be one of {STATES}; got {v!r} — every surface that sorts, "
                        f"counts or gates on a pin reads this field"),
    "severity": (lambda v: v in SEVERITIES,
                 lambda v: f"severity must be one of {SEVERITIES}; got {v!r} — the threshold rule "
                           f"and the interview's ordering both read it"),
}
POLICY_STRONGER = {
    "id": (lambda v: isinstance(v, str) and bool(v),
           lambda v: "a policy carries no `id`, so no cascaded decision can name the rule it "
                     "derives from"),
    "rule": (lambda v: isinstance(v, str) and bool(v.strip()),
             lambda v: f"rule must be a non-empty string; got {v!r} — it IS the standing rule, and "
                       f"it is what both the map's card and the projected AGENTS.md print"),
}

#: The paths `pin_read` MATERIALISES when the file carries none, and the only ones. Every caller
#: below indexes them unconditionally and has since v0.21, which is the whole reason they are named
#: here rather than discovered: a projection that materialised the rest would put an empty
#: `verification` envelope and an empty fork on every pin in the file, and the map's cards select on
#: presence (`if(p.question)`, `if(p.decision)`). So the SAME table drives two readings that differ
#: on exactly one axis — whether an absent path is filled — and `pin_read(pin, fill=False)` is the
#: projection's.
PIN_GUARANTEED = ("id", "state", "severity", "depends_on", "question", "title", "decision")
POLICY_GUARANTEED = ("id", "rule", "applies_to")

#: The declared paths a WRITE door may assume are on the pin, because `add_pin` composes every one
#: of them on every pin it writes (v0.26).
#:
#: `PIN_GUARANTEED` is the READER's answer to the same question and it is a different answer on
#: purpose: a reader gets an absent path MATERIALISED, and a writer gets the write REFUSED. That
#: split is this file's standing rule — *reading a ledger is never the operation that fails on it,
#: and a write onto a record this runtime cannot read is exactly the operation that must fail*
#: (`Ledger.__init__` says it of the file; this says it of the record). Materialising on the write
#: path is not available: `question` and `decision` are `PIN_GUARANTEED` and `add_pin` writes both
#: as an explicit `None`, so filling them would put `{}` on every pin in the file — and `{}` is
#: falsy in Python and TRUTHY in JavaScript, which is an empty fork card on the map for every
#: finding in the ledger.
#:
#: The membership rule is the writer's own output and nothing else, which is why the tuple can be
#: held to it rather than trusted:
#: `tests/test_ledger.py::TestAWriteOntoAPinThisRuntimeCannotReadIsRefused` derives the set from a
#: pin `add_pin` actually composes and asserts equality. A path added to the envelope tomorrow joins
#: it iff `add_pin` writes it, and the doors may then index it.
PIN_REQUIRED = ("id", "kind", "title", "severity", "state", "provenance", "anchors",
                "depends_on", "remediation")


def _at(record: dict, path: str) -> Any:
    """The value at a dotted path, or `None` where any step is absent or not an object."""
    node: Any = record
    for step in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(step)
    return node


def _shape_message(path: str, shape: str, required: bool) -> Any:
    """The sentence for a path whose rule is its declared shape — one function so the two halves of
    that rule (`must hold the shape`, `must be there at all`) cannot be worded by two authors."""
    def message(record: dict) -> str:
        if required and _at(record, path) is None:
            return (f"`{path}` is absent, and `add_pin` writes it on every pin — so every per-pin "
                    f"write door indexes it unconditionally and dies here on a record this runtime "
                    f"did not compose. A reader substitutes {SHAPE_EMPTY[shape]!r}; a write is "
                    f"refused, because inventing half a record is not a write anyone asked for")
        return (f"`{path}` must be {SHAPE_ENGLISH[shape]}"
                f"{'' if required else ' or absent'}; got {type(_at(record, path)).__name__} — a "
                f"reader indexes into it, so what the file carries is read as "
                f"{SHAPE_EMPTY[shape]!r} and reported here rather than silently substituted")
    return message


def _rules_from(shapes: dict, stronger: dict, prefix: str, required: tuple = ()) -> tuple:
    """`(name, holds(record) -> bool, message(record) -> str)` per declared path.

    One rule per path and one name per path: where `stronger` carries an entry the rule is that
    one, because a membership rule already implies the shape and two entries would report one
    fault twice under two names.

    `required` (v0.26) is the third thing a path's rule can say, and it is one rule rather than a
    second table for the same reason: a path that is absent and a path that is the wrong type are
    the same fault to every caller — the value cannot be indexed — so they are one name, one
    verdict, and one entry in `pre_rule_events`. Every `stronger` entry already implies presence
    (`v in STATES` is false of `None`), so the two never both apply to one path.
    """
    out = []
    for path, shape in shapes.items():
        name = prefix + path.replace(".", "_")
        if path in stronger:
            holds, message = stronger[path]
            out.append((name,
                        (lambda p, h: lambda r: h(_at(r, p)))(path, holds),
                        (lambda p, m: lambda r: m(_at(r, p)))(path, message)))
            continue
        must = path in required
        out.append((
            name,
            (lambda p, s, m: lambda r: (_at(r, p) is None and not m)
             or SHAPE_HOLDS[s](_at(r, p)))(path, shape, must),
            _shape_message(path, shape, must),
        ))
    return tuple(out)


PIN_RULES = _rules_from(PIN_SHAPES, PIN_STRONGER, "pin_", PIN_REQUIRED)
#: A `Policy` is the ledger's other record with its own surfaces, and it acquired the pin half's
#: exact bug one collection over: `instructions.render` called `.strip()` on `policy["rule"]` and
#: `.items()` on `policy["applies_to"]`, so an elected standing rule whose scope is a string took
#: down the projection every host loads. Same table, same derivation, one prefix apart.
POLICY_RULES = _rules_from(POLICY_SHAPES, POLICY_STRONGER, "policy_")


def shape_note(rule: str) -> str:
    """The one-line English a SURFACE prints for a derived rule name, or `""` for a name this table
    did not produce.

    The map keeps hand-written sentences for the rules that carry argued prose, and falls back to
    this for the derived ones — because a table of thirty-one hand-written sentences beside a table
    of thirty-one derived rules is the drift this round exists to remove. The page cannot fall
    behind the schema: the sentences are inlined from here, exactly as `__SETTLED__` and
    `__ASKABLE__` already are.
    """
    for shapes, prefix in ((PIN_SHAPES, "pin_"), (POLICY_SHAPES, "policy_")):
        for path, shape in shapes.items():
            if prefix + path.replace(".", "_") != rule:
                continue
            record = "pin" if prefix == "pin_" else "standing rule"
            return (f"a {record}'s `{path}` that is not {SHAPE_ENGLISH[shape]} — every surface "
                    f"reads it as {SHAPE_EMPTY[shape]!r}, so what the file carries is on no page")
    return ""


def shape_notes() -> dict:
    """`rule name -> sentence` for every rule the two shape tables derive. What the map inlines."""
    out = {}
    for shapes, prefix in ((PIN_SHAPES, "pin_"), (POLICY_SHAPES, "policy_")):
        for path in shapes:
            name = prefix + path.replace(".", "_")
            out[name] = shape_note(name)
    return out


def policy_violations(policy: dict) -> list:
    """The names of the `POLICY_RULES` this policy does not satisfy, in table order."""
    return [name for name, holds, _ in POLICY_RULES if not holds(policy)]


def pin_violations(pin: dict) -> list:
    """The names of the `PIN_RULES` this pin does not satisfy, in table order.

    The mirror of `event_violations`, and it takes an object for the same reason that one does: a
    `pins` entry that is not an object is `entry_shape`'s answer, not four rules' worth of it."""
    return [name for name, holds, _ in PIN_RULES if not holds(pin)]


def _shape_guarded(record: Any, shapes: dict, guaranteed: tuple, fill: bool) -> dict:
    """`record` as a reader may index it: every declared path that does not hold its shape replaced
    by that shape's EMPTY value, everything else carried through untouched. Never raises.

    Copies rather than rewrites — the file is not touched and `nonconforming(data)` still answers
    about it as it stands. `fill` decides the one axis the two callers differ on: a reader that
    indexes a path unconditionally needs it present (`fill=True`, the default), a PROJECTION must
    not invent a record the file does not carry (`fill=False`).
    """
    out = dict(record) if isinstance(record, dict) else {}
    for path, shape in shapes.items():
        parent, _, leaf = path.rpartition(".")
        holder = out if not parent else _at(out, parent)
        if not isinstance(holder, dict):
            continue                       # the parent is itself substituted; nothing to guard in
        present = leaf in holder and holder[leaf] is not None
        if present and SHAPE_HOLDS[shape](holder[leaf]):
            continue
        if not present and not (fill and path in guaranteed):
            continue
        if parent:                         # copy-on-write, so the file's own sub-object is not hit
            holder = dict(holder)
            _set_at(out, parent, holder)
        empty = SHAPE_EMPTY[shape]
        # A fresh mutable each time: one shared `{}` handed to every pin in the file would be one
        # object a caller could write a fork into and see on every other pin.
        holder[leaf] = type(empty)(empty) if isinstance(empty, (dict, list)) else empty
    return out


def _set_at(record: dict, path: str, value: Any) -> None:
    parent, _, leaf = path.rpartition(".")
    holder = record if not parent else _at(record, parent)
    if isinstance(holder, dict):
        holder[leaf] = value


def pin_read(pin: Any, fill: bool = True) -> dict:
    """The pin as a reader may index it — every path `PIN_SHAPES` declares, guaranteed to hold its
    declared shape. Never raises.

    What each substitution becomes is the shape's empty value, and the argument for each is the
    same one: **a substitution nobody can name is a heuristic**, so the reading is always the
    emptiest true one and `nonconforming` reports every instance.

      * `id`, `state` — `""`. Neither is in any closed vocabulary, so a pin with no state is in no
        state's bucket and one with no id is depended on by nothing. It is still counted, still
        rendered, and reported under `pre_rule_events`.
      * `severity` — `""`, which `severity_rank` sorts LAST. Not `low`, which would be reading a
        claim the file does not make; not `blocker`, which would be inventing urgency out of a
        broken field. The pin stays IN the view either way — the ordering is by information gain
        among severities this runtime can rank, and an unrankable one is not evidence of anything.
      * `depends_on` — `[]` unless it is a list of strings. A bare string here is iterable, so the
        old readers walked it character by character and built a DAG out of letters.
      * `question`, `decision` — `{}`, falsy exactly where the raw field already was.
      * `verification`, `brainstorm.proposals` — `{}` / `[]` (v0.25). These are the two that were
        missing, and both killed `interview_next` over stdio: `(pin.get("verification") or {}).get`
        on a string, and a `proposals` that is truthy and not a list of objects walked character by
        character into `p.get(...)`.

    `fill` is the only axis on which the two readings differ, and it is named rather than forked:
    with it, the seven paths every caller indexes unconditionally are materialised; without it, an
    absent path stays absent, which is what a PROJECTION needs — the map's cards select on presence,
    and filling them would put an empty envelope on every pin in the file.
    """
    return _shape_guarded(pin, PIN_SHAPES, PIN_GUARANTEED, fill)


def policy_read(policy: Any, fill: bool = True) -> dict:
    """`pin_read`'s twin, one collection over, off the same machinery and the same argument.

    It exists because the pin half was fixed alone: `rule` met `.strip()` and `applies_to` met
    `.items()` in `instructions.render`, on a collection the same function had already learned to
    guard the container of. `applies_to` reads as `{}` where the file's value cannot be read, and
    `{}` is the UNIVERSAL selector — the widest possible reading and therefore the honest one: a
    scope this runtime cannot read must not quietly narrow the radius a human is shown.
    """
    return _shape_guarded(policy, POLICY_SHAPES, POLICY_GUARANTEED, fill)


def severity_rank(severity: str) -> int:
    """Where a severity sorts — `SEVERITIES`' own order, and a value it does not carry sorts last.

    **The one severity ordering in this package** (v0.23). `instructions.py` kept a second table
    that read a MISSING severity as `low`, so a pin whose file says nothing about how bad it is
    sorted AHEAD of a pin that states a severity outside the set, in the section a tight budget
    clips — two surfaces ordering the same pins by two tables, and the newer one contradicting the
    argued direction of the older. The direction is `pin_read`'s and is stated there: an unrankable
    severity is not evidence of anything, so it sorts last, and *missing* and *unrecognised* are the
    same amount of nothing. `readiness.py` and `findings.py` kept their own copies of the same four
    pairs; they are gone too, and `tests/test_ledger.py::TestOneSeverityOrderingForTheWholePackage`
    is what stops a fourth.
    """
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES)


def downstream_of(pin_id: str, reads: Iterable[dict]) -> set[str]:
    """Every pin that transitively depends on `pin_id` — the SET of them, never a count of paths.

    **The one answer to "how much does this fork collapse" in this package** (v0.27). It was two
    answers, in two byte-identical nested functions: `Ledger.interview_view`'s `transitive` and
    `interview.funnel`'s `transitive_downstream`. Both summed `1 + recurse(...)` over the inbound
    edges with a `seen` set carried DOWN one branch and never across siblings — which counts simple
    PATHS. On the smallest diamond a real roadmap makes (`B` and `C` both depend on `A`, `D` on
    both) the answer for `A` was **4**, and `A` has three pins downstream of it. `D` was counted once
    through `B` and once through `C`.

    Both surfaces are the interview's ordering by information gain, so the inflation is not
    cosmetic: it is the number the funnel hands the human and the key `interview_view` sorts on, and
    it grows with every diamond — i.e. fastest exactly where the DAG is most entangled and the
    ordering matters most. The old walk was also exponential in the number of diamonds (a chain of
    twenty doubles twenty times), on a file an agent hands us.

    Reachability, not arithmetic, so the shape of the graph cannot change the answer: a reverse
    index over the edge, then a frontier. `pin_id` itself is never in the result — a `depends_on`
    cycle in a hand-edited file makes a pin its own descendant, and "this fork collapses itself" is
    not a fact about anything.

    `reads` must be the GUARDED reads (`pin_read` output), for the reason every walker of this edge
    reads it that way: a bare string in `depends_on` is iterable, so the raw field builds a DAG out
    of letters.
    """
    inbound: dict[str, list[str]] = {}
    for r in reads:
        for dep in r["depends_on"]:
            inbound.setdefault(dep, []).append(r["id"])
    out: set[str] = set()
    frontier = [pin_id]
    while frontier:
        for nxt in inbound.get(frontier.pop(), ()):
            if nxt != pin_id and nxt not in out:
                out.add(nxt)
                frontier.append(nxt)
    return out


def _stamp(value: Any) -> Optional[datetime]:
    """An ISO timestamp as a tz-aware moment, or `None` where it is not one this runtime can read.

    Naive stamps are read as UTC, because that is what `_now` writes and a naive value here can only
    have come from a hand edit or an older writer. Returning `None` rather than raising is the same
    rule the shape table follows one section up: reading a ledger is never the operation that fails
    on it, and a timestamp nobody can parse is an absence, not an exception.
    """
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def claim_state(read: dict, now: Optional[datetime] = None) -> str:
    """Is anybody working on this pin — `unclaimed` | `live` | `stale` (v0.30).

    Takes a `pin_read` result, so a malformed `claimed_by` has already become `""` and reads as
    unclaimed. Three answers rather than two, because a scheduler must treat *a peer is on it* and
    *a session died holding it* differently, and there is no daemon here to tell them apart: the
    difference is computed at read time from `claimed_at` against `CLAIM_TTL_SECONDS`.

    An unparseable or absent `claimed_at` under a present holder is **stale**, not live. That is the
    conservative reading in the only direction that matters: a claim this runtime cannot date cannot
    be shown to be live, and treating it as live would park a pin behind a timestamp nobody can fix.
    The pin stays reclaimable, the reclaim says it reclaimed one, and `nonconforming` names the
    field on every surface that reports it.
    """
    if not read.get("claimed_by"):
        return "unclaimed"
    stamped = _stamp(read.get("claimed_at"))
    if stamped is None:
        return "stale"
    moment = now or datetime.now(timezone.utc)
    return "live" if (moment - stamped).total_seconds() < CLAIM_TTL_SECONDS else "stale"


def read_collection(data: Any, name: str) -> list[dict]:
    """One of `LEDGER_COLLECTIONS` as a reader can index it — the CONTAINER half of the guarded
    read, for a caller holding raw ledger DATA rather than a `Ledger`.

    `Ledger.readable` is this function with `self.data` supplied, and that is the whole point: v0.21
    put the guard on the `Ledger` method, and the two surfaces that read a ledger **as data** —
    `map.render` and `instructions.render`, neither of which constructs a `Ledger` — went on walking
    `data.get("policies") or []` and calling `.get` on whatever came out. Four reproductions over
    stdio, all of them `'str' object has no attribute 'get'`, on files `ledger_summary` reported the
    nonconformance of in the same session.

    A dropped entry is never hidden: `nonconforming` reports a non-list collection under
    `collection_shape` and a non-object entry under `entry_shape`.
    """
    value = (data or {}).get(name) if isinstance(data, dict) else None
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def readable_ledger(data: Any) -> dict:
    """The whole file as a reader may index it: all three collections guarded, everything else
    (`version`, `governance`, anything a later schema adds) carried through untouched.

    This is what a PROJECTION reads. The map inlines its output into the page and the instruction
    region is generated from it, so neither surface can be handed an entry the schema does not
    describe — which is what makes the page's own JavaScript safe without a second guard written in
    a second language. The original is not mutated and not rewritten: a shallow copy with three keys
    replaced, so `nonconforming(data)` still answers about the file as it stands.

    **The FIELDS come through too, from v0.25.** Guarding the container and handing the page a pin
    whose `verification` is a string is half a read path: the map's own JavaScript then renders
    *"no rung recorded"* over a file that records one, and nothing on the page contradicted it. So
    every entry goes through its record's guarded read with `fill=False` — malformed values are
    substituted, ABSENT ones stay absent, because the page's cards select on presence and a filled
    envelope would appear on every pin in the file.
    """
    out = dict(data) if isinstance(data, dict) else {}
    for name in LEDGER_COLLECTIONS:
        entries = read_collection(data, name)
        if name == "pins":
            entries = [pin_read(e, fill=False) for e in entries]
        elif name == "policies":
            entries = [policy_read(e, fill=False) for e in entries]
        out[name] = entries
    return out


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
    # v0.25 — the rule about the FILE, asked before any rule about a record in it. A ledger whose
    # top level is not an object killed all four surfaces with a raw `AttributeError` (`[...]` and
    # `"..."` both reproduced on every one of them), and this function was among the things that
    # died: it is `Ledger.__init__`'s first call, so the report that exists to describe an
    # unreadable file was itself unable to open one. `readable_ledger` already answered `{}` for it
    # and said nothing, which is the silent-substitution failure one layer up.
    if not isinstance(data, dict):
        return {"ledger_shape": [type(data).__name__]}

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
        #
        # Through `pin_read` (v0.25), because `str(pin.get("id") or "")` was a SECOND answer to
        # "what is this pin's id": on `id: 7` this report said `7` and every surface said `""`, so
        # the map could not join its per-record card to the report entry about that very record.
        # One carrier for the id, and a record this runtime cannot name is named by where it sits —
        # which is what the surfaces then look for.
        label = pin_read(pin)["id"]
        for rule in pin_violations(pin):
            out.setdefault(rule, []).append(label or f"pins[{index}]")
    # The third collection, on the same terms as the second (v0.23). `add_policy` settles every one
    # of these at the write, exactly as `add_pin` does for `PIN_RULES`, so what the table buys here
    # is the READER — and a policy is the record with the widest blast radius in the file, because
    # one of them decides a whole cluster.
    for index, policy in enumerate(entries("policies")):
        if not isinstance(policy, dict):
            continue                                    # already reported as `entry_shape`
        label = policy_read(policy)["id"]
        for rule in policy_violations(policy):
            out.setdefault(rule, []).append(label or f"policies[{index}]")
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
    # v0.26 — through the ONE carrier, which is where the rule was already written and was being
    # paid only at TOP-LEVEL list arguments. `_require_objects` was introduced for `proposals`,
    # `provenance`, `anchors`, `failure_modes` and `paper_tigers` — every list an agent hands a door
    # directly — and a list one level inside a dict argument was outside all of it. Reproduced over
    # real stdio on the shipped plugin: `ledger_add_pin(question={"options": ["a bare string"]})`
    # and `ledger_set_question` with the byte-identical dict both returned `'str' object has no
    # attribute 'get'`, from the `opt.get("id")` two lines below — the exact failure the rule was
    # written to close, one nesting level down, at the two doors that compose the fork the whole
    # funnel runs on.
    options = _require_objects(question.get("options", []), "question.options",
                               "each one is a branch of the fork with an `id` and a `label`, and "
                               "`question.options[].id` is the carrier the offered-options rule "
                               "anchors on at both election doors")
    for opt in options:
        _require(bool(opt.get("id")) and bool(opt.get("label")),
                 "every question option needs id and label")
        _require(opt.get("id") != FREEFORM_OUTCOME,
                 f"an option may not be called {FREEFORM_OUTCOME!r}: that is the token both "
                 f"election doors read as 'the human answered in their own words', so a menu "
                 f"carrying it offers two branches that arrive as one — the door would record the "
                 f"free text as the outcome of a fork that never offered it. Rename the option "
                 f"(`write_in`, `other`, `something_else`); the way out itself is already offered "
                 f"by allow_freeform, which every composed fork must set anyway.")
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
            # v0.25 — the first thing asked of the file, because everything below indexes it. A
            # ledger whose top level is a list or a string reached `self.data.get("version")` and
            # died with a bare `AttributeError` on all four surfaces at once. The refusal is a
            # `LedgerError` and not a guarded read: this constructor serves the WRITE path too, and
            # a write onto a file this runtime cannot read is exactly the operation that must fail.
            # The two PROJECTIONS build no `Ledger` and answer instead — `readable_ledger` reads it
            # as an empty file and `nonconforming` names it under `ledger_shape`.
            _require(isinstance(self.data, dict),
                     f"a ledger is an object with `pins`, `decision_log` and `policies`; this file "
                     f"holds a bare {type(self.data).__name__} at its top level, so there is "
                     f"nothing here to read a version, a pin or a decision off")
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

        The WRITE path does not come through here: a write onto a file this runtime cannot read is a
        different question from a read of it, and the answer there is to refuse —
        `writable_collection` is where that refusal lives (v0.28). For two versions this paragraph
        said the write path "deliberately keeps `self.data[…]`", which described the code and named
        no refusal: there was none, and ten agent-reachable doors died with a raw
        `AttributeError`/`KeyError` on a `pins` that is an object or a `decision_log` that is absent.

        The rule itself moved to the module-level `read_collection` in v0.23, and this method is now
        that function with `self.data` supplied. It had to: the two PROJECTIONS read a ledger as
        data and never build a `Ledger`, so a guard that lived on the method was a guard they could
        not reach — which is exactly how they came to be the last two surfaces still dying on a
        shape `summary()` reports.
        """
        return read_collection(self.data, name)

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

    def writable_pin(self, pin_id: str) -> dict:
        """THE lookup of the WRITE path: the pin itself, or a refusal naming what cannot be read
        on it (v0.26).

        **Why this exists.** Two rounds hardened the read path — `pin_read` substitutes, `PIN_RULES`
        reports, `readable_ledger` carries both into the projections — and every one of the fourteen
        per-pin write doors went on indexing the raw record. A write door READS the pin already in
        the file before it writes anything, so every guarantee built for the readers applies to it,
        and none of it was applied. Reproduced over real stdio against the shipped plugin, on
        malformations the derived corpus already describes: 42 crash sites across all fourteen
        doors, the election door `ledger_record_decision` among them, each of them a bare
        `KeyError`/`AttributeError`/`TypeError` naming a line of ours about a file somebody else
        hand-edited — and the caller is mid-transaction, which is worse than a reader's crash, not
        better.
        - `KeyError: 'state'` at every door, from `_gate_closed`;
        - `AttributeError: 'str' object has no attribute 'get'` at `add_remediation`, `challenge`,
          `reopen`, `cross_derive` on a `remediation`/`verification` this runtime did not write;
        - `KeyError: 'title'` at `record_decision`, before `decide` was even reached;
        - `KeyError: 'depends_on'` at `set_readiness`, on a pin missing the list `add_pin` always
          writes.

        **Refuse rather than substitute, and that is the split, not an inconsistency.** `pin_read`
        answers *what may a reader index*; this answers *may this record be written to at all*.
        `Ledger.__init__` already draws the same line one level out for the whole file, in the same
        words: a write onto something this runtime cannot read is exactly the operation that must
        fail. Substituting here would persist the substitution — the door writes the pin back — so
        a guarded read on the write path is a silent repair of somebody's file.

        The verdict is `pin_violations`, which is `PIN_RULES`, which is derived from `PIN_SHAPES`
        and `PIN_REQUIRED`: one table for the rules, the reader's substitution, the report, the
        corpus and this refusal. The message names the rules and points at
        `mcp:ledger_summary`'s `pre_rule_events`, which is where the same names are already listed
        for the whole file — a refusal an agent cannot act on is a wall.
        """
        pin = self.pin(pin_id)
        broken = set(pin_violations(pin))
        reasons = "; ".join(message(pin) for name, _holds, message in PIN_RULES if name in broken)
        _require(not broken,
                 f"{pin_id} cannot be written to: this runtime cannot read "
                 f"{', '.join(sorted(broken))} on it. {reasons}. Every one of these is reported by "
                 f"`ledger_summary` under `pre_rule_events` — fix the record, then write.")
        return pin

    def writable_collection(self, name: str) -> list:
        """THE lookup of the WRITE path for a whole COLLECTION: the list itself, or a refusal naming
        what cannot be read (v0.28).

        **`writable_pin`'s twin, one level out, and it is the half that was stated and never
        built.** `Ledger.readable`'s own docstring has said since v0.21 that *a write onto a file
        this runtime cannot read is a different question from a read of it, and the answer there is
        to refuse*. Nothing refused. Every write door reached `self.data["pins"]` /
        `self.data["decision_log"]` / `self.data["policies"]` raw, so a container that is an object,
        a string, a number or simply absent took the door down with a stack trace naming a line of
        ours: reproduced over real stdio against the shipped plugin on **ten agent-reachable doors
        across both derived rosters** — `AttributeError: 'str' object has no attribute 'get'` out of
        `_next_id`, `AttributeError: 'dict' object has no attribute 'append'` out of the appends.

        The split is `writable_pin`'s and is the same split: `read_collection` answers *what may a
        reader index* and substitutes `[]`; this answers *may this collection be written to at all*
        and refuses. Substituting here would be worse than crashing — `save()` writes `self.data`
        back, so a door that quietly appended to a substituted `[]` would either lose the append or
        overwrite whatever the file was carrying under that key.

        The RECORD half of the same file is deliberately not this rule. One malformed pin among
        thirty does not make the file unwritable: the target of the write is refused by
        `writable_pin`, and every OTHER record is read through the read path (`writable_pins`). The
        blast radius of a bad record is that record.
        """
        _require(name in LEDGER_COLLECTIONS,
                 f"{name!r} is not one of this file's collections {LEDGER_COLLECTIONS}")
        value = self.data.get(name)
        _require(isinstance(value, list),
                 f"`{name}` cannot be written to: a ledger's `{name}` is a list, and this file "
                 f"carries {type(value).__name__ if value is not None else 'nothing'} there — so "
                 f"there is no collection to append to and no record to look up in. It is reported "
                 f"by `ledger_summary` under `pre_rule_events` as `collection_shape`; fix the file, "
                 f"then write.")
        return value

    def writable_pins(self) -> list[tuple[dict, dict]]:
        """`(record, read)` for every pin in the file — what the WRITE path may do with the pins it
        is **not** writing to (v0.28).

        **The rule this carries: a write door refuses the pin it writes to, and READS every other
        one.** `writable_pin` guarded the target and nothing else, so a write onto a perfectly
        well-formed pin died because a different pin somewhere in the file lacked an `id` —
        `set_readiness`'s `{p["id"]: p for p in self.data["pins"]}` and `_reopen_minimal`'s cascade
        walk, both reproduced with a healthy target. That makes the blast radius of one malformed
        record the whole file, which is the opposite of what the read path spent two rounds
        establishing.

        Refusing is right for the target and wrong here, and the reason is what the door is asking
        of each: it is about to WRITE the target, so inventing half a record would persist; it only
        needs to know whether the others are settled, what they depend on and what they are called,
        and `pin_read`'s substitutions answer all three the emptiest true way. A pin with no
        readable `id` is depended on by nothing and named by nothing; one with no readable `state`
        is in no state's bucket, so no cascade sweeps it up and no index claims it. It participates
        as what it is — nothing — instead of taking the call down.

        The pair is what makes one carrier serve both callers: the cascade must WRITE onto the
        record while DECIDING off the read, and handing it only the reads would have it mutate a
        copy.
        """
        return [(p, pin_read(p)) for p in self.writable_collection("pins") if isinstance(p, dict)]

    def _next_id(self, prefix: str, collection: list, key: str = "id") -> str:
        # `isinstance` before `.get`: the collection is a list this runtime can append to (that is
        # `writable_collection`'s promise) and its ENTRIES are whatever the file holds — a bare
        # string among the pins is `entry_shape`'s finding, not a reason for every id this file ever
        # mints to raise `AttributeError`.
        n = 1 + sum(1 for item in collection
                    if isinstance(item, dict) and str(item.get(key, "")).startswith(prefix))
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
        _require_objects(provenance, "provenance",
                         "each entry names the source that found this and how")
        _require(len(provenance) > 0, "provenance is required (who found this, how)")
        _require_objects(list(anchors or []), "anchors",
                         "each entry names a node and where in the tree it sits")
        _validate_question(question)
        for dep in depends_on or []:
            self.pin(dep)  # must exist — the DAG is real, not aspirational

        # v0.6: a forced assumption is vetoable, never confidently asserted
        if any(src.get("source") == "agent_assumption" for src in provenance):
            _require(confidence in ("inferred", "ambiguous"),
                     "an agent_assumption pin must carry confidence inferred|ambiguous")

        pin = {
            "id": self._next_id("pin_", self.writable_collection("pins")),
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
        self.writable_collection("pins").append(pin)
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
        pin = self.writable_pin(pin_id)
        # Asked FIRST, on `settlement_verdict`'s own stated rule and on `add_proposals`' — *a rule
        # that every door must obey is asked before any door speaks*. It ran last here, so a
        # `resolved` pin that already poses a fork was told the weaker of the two true reasons
        # (`already poses a fork`), and an agent acting on that would have gone looking for a way to
        # replace the fork rather than for `reopen`. Found by a gate that checks WHICH refusal fires.
        self._gate_closed(pin, "set_question")
        _require(bool(question), "a question is required — this door exists to add one")
        _validate_question(question)
        _require(not pin.get("question"),
                 f"{pin_id} already poses a fork. `question.options[].id` is the carrier the "
                 f"offered-options rule anchors on at both election doors, so replacing it decides "
                 f"what the human may choose next — write-if-absent is the whole rule here.")
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
        pin = self.writable_pin(pin_id)
        self._gate_closed(pin, "add_proposals")
        _require(bool(pin_read(pin)["question"]),
                 f"{pin_id} poses no fork, and a proposal is an option for one. This door moves a "
                 f"pin from `needs_input` to `brainstorming`, so a pin with no question keeps the "
                 f"state it has and its proposals reach no surface — `interview_view` selects "
                 f"{INTERVIEW_STATES}. Pose the fork first (`set_question`), then propose against "
                 f"it.")
        _require_objects(proposals, "proposals",
                         "each one carries a summary, an effort and no outcome of its own")
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
        brief_quote: str = "",
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

          * `elicited` — the answer was captured by a door the agent did not mediate, so it could
            not have invented it. Two carriers establish that, and v0.29 names both rather than the
            one mechanism this line used to describe: the MCP server asking through the host
            (`mcp/server.py`), and `mcp/decide.py`, which the deciding human runs and which refuses
            a stdin that is not a terminal. The claim is the property; the mechanism is whichever
            path ran, and only that path may state it.
          * `transcribed` — an agent relayed what the user said, recorded verbatim in
            `human_answer`. Weaker: honest relay and confabulation look identical here.
          * `brief` — pre-decided in the project brief at frame time; the brief is the evidence, and
            since v0.24 the runtime collects it: `brief_quote` carries the passage that settles this
            fork, verbatim, and the `brief_quote` rule in `EVENT_RULES` makes it a biconditional.
            It was the one member of `DECISION_EVIDENCE` whose claim had no carrier at all — the
            other three are each demanded by something — so a caller's word that a document said so
            was the whole of it.
          * `cascaded` — derived from a `Policy` the user elected (v0.11). The answer reached the
            log ONCE, at the policy election, and this event is an amplification of it; the
            `Policy` named by `policy_id` carries its own rung and quote. Its failure mode is
            neither invention nor mis-relay but **fit**: the policy may not suit this pin.

        It defaults to `transcribed`, the WEAKER rung, deliberately: a caller that says nothing has
        not earned the strong claim, and the safe direction to be wrong in is understating what is
        known. Only a path that actually asked a human may pass `elicited`, and since v0.29 there
        are two: the server's elicitation branch and the human-run door. Which callers those are is
        not left to this sentence — `tests/test_human_door.py::TestOnlyAnAskingPathMayClaimItAsked`
        derives the set by AST over every call site in the package and fails on a third.

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
        pin = self.writable_pin(pin_id)
        door = _door_for(settles_as)
        # Gated BEFORE the event is built: a refusal must not leave an orphan DecisionEvent in an
        # append-only log. `_settle` asks the same predicate again, because it is the single writer
        # of a settled state and a writer that trusts its callers is a writer with five contracts.
        self._gate_settlement(pin, door)
        event = {
            "id": self._next_id("ev_", self.writable_collection("decision_log")),
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
        if brief_quote:
            event["brief_quote"] = str(brief_quote).strip()
        if flip_signal is not None:
            event["flip_signal"] = dict(flip_signal)
        # Validated as the dict it will be, not as the arguments it came from (v0.15): the reader
        # (`nonconforming`) only ever sees the dict, so a rule checked on anything else is a rule
        # the reader cannot replay. Nothing is appended if this raises.
        _check_event(event)
        self.writable_collection("decision_log").append(event)
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
        pin = self.writable_pin(pin_id)
        self._gate_closed(pin, "set_readiness")
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

        # Every OTHER pin through the read path (v0.28, `writable_pins`): this index is not what is
        # being written, it is what the write is checked against, and a pin that carries no readable
        # `id` is a pin nothing can name as a prerequisite. It used to be `{p["id"]: p for p in
        # self.data["pins"]}`, so one such pin anywhere in the file took down a `set_readiness` on a
        # perfectly well-formed target.
        by_id = {read["id"]: read for _, read in self.writable_pins() if read["id"]}
        for h in hardens:
            _require(h != pin_id, "a pin cannot harden itself")
            _require(h in by_id, f"no pin {h}")
            # CHANGE-JUSTIFIED, enforced rather than promised: remediation is admitted only when it
            # reduces *this* change's risk. A pin whose anchors lie outside the landing zone is
            # someone else's cleanup, and admitting it is how a bounded gate becomes a rewrite.
            anchors = [(a.get("loc") or "").split(":")[0] for a in by_id[h]["anchors"]]
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
        """`by_id` holds GUARDED reads (`writable_pins`), so `depends_on` is a list of strings here
        by construction — the raw field can be a bare string, which is iterable, and this walk would
        then build a DAG out of letters."""
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            if cur in seen or cur not in by_id:
                continue
            seen.add(cur)
            stack.extend(by_id[cur]["depends_on"])
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
        return self.writable_pin(pin_id)

    def accept(self, pin_id: str, rationale: str, flip_criteria: str,
               evidence: str = "transcribed", human_answer: str = "") -> dict:
        """Leave-as-is: the legitimate default resolution of a design_concern only.

        The kind check moved into `settlement_verdict` (`wrong_kind`) rather than living here: it is
        a rule about which door may settle which pin, and every such rule now has one home.
        """
        self.decide(pin_id, outcome="keep", rationale=rationale, flip_criteria=flip_criteria,
                    evidence=evidence, human_answer=human_answer, settles_as="accepted")
        return self.writable_pin(pin_id)

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
            "id": self._next_id("pol_", self.writable_collection("policies")),
            "applies_to": applies_to,
            "rule": rule,
            "default_outcome": default_outcome,
            "set_by": "interview",
            "exceptions": exceptions or [],
            "evidence": evidence,
        }
        if human_answer:
            policy["human_answer"] = human_answer
        self.writable_collection("policies").append(policy)
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
            # `.get`, and the reason is `PIN_SHAPES`' own membership rule rather than an oversight
            # (v0.26): the table declares `remediation` a `list[object]` and stops there, because a
            # SCALAR nested inside a declared object is not something a reader indexes INTO. That is
            # true of what it renders and false of what it subscripts — `i["status"]` was a bare
            # `KeyError` on an item carrying no status, which no corpus derived from that table can
            # produce. So the rule the write path falls back to is the read path's own, stated in
            # v0.18 and carrying no qualifier: every read of a record this runtime did not write is
            # a `.get`. An item with no status is not done.
            if not pin.get("remediation") or any(i.get("status") != "done"
                                                 for i in pin["remediation"]):
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

    def _gate_closed(self, pin: dict, door: str) -> None:
        """Refuse a per-pin write onto FINISHED work — the one carrier of that rule (v0.24).

        `PIN_WRITE_DOORS` says which doors it binds and why the others are exempt; this is the
        sentence all of them share. It used to be two near-identical `_require`s at `set_question`
        and `add_proposals`, differing only in the verb, which is the shape every finding on this
        branch started as: the third door was written without either of them, and so were the fourth,
        fifth and sixth.

        The message names the way back, because a refusal an agent cannot act on is a wall, and this
        one has an opening move on every host (`mcp:ledger_reopen`).
        """
        _require(door in PIN_WRITE_DOORS, f"door must be one of {sorted(PIN_WRITE_DOORS)}; "
                                          f"got {door!r}")
        _require(pin["state"] not in CLOSED_STATES,
                 f"the work on {pin['id']} is finished ({pin['state']}); {door} would un-finish it, "
                 f"which is the reopen arc and has its own door (`reopen`, which records why).")

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

        **The claim goes the same way (v0.30), off the same destination test.** A settled pin is not
        held: releasing is explicit and it is also the settlement doors' business, because the
        failure a claim prevents is a second session taking work that is already being done, and work
        that is finished is not being done. `correctness_unknown` again does not clear, and again for
        its own reason rather than by omission — the pin comes back to the human still open, and the
        session that could not verify it is the one most likely to still be on it. `decided` DOES
        clear, which reads oddly for a beat and is right: the interview's work on that pin is over
        and the build's has not started, and the property being bought is that a claim lands before a
        unit of work rather than spanning two of them.
        """
        self._gate_settlement(pin, door)
        event = None
        if decision_event is None:
            event = {
                "id": self._next_id("stl_", self.writable_collection("decision_log")),
                "pin_id": pin["id"],
                "timestamp": _now(),
                "door": door,
                "from_state": pin["state"],
                "to_state": _STATE_BY_DOOR[door],
                "verification_rung": verification_rung,
                "policy_hash": self._policy_hash(),
            }
            self.writable_collection("decision_log").append(event)
        if _STATE_BY_DOOR[door] in SETTLED_STATES:
            pin.pop("substate", None)
            for carrier in CLAIM_CARRIERS:
                pin.pop(carrier, None)
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
        # `readable_pins`, not `self.data["pins"]` (v0.25). This function is reached by
        # `mcp:policy_preview`, which is served READ-ONLY: a ledger with no `pins` key made it a
        # bare `KeyError`, and one whose `pins` is a bool made it a `TypeError` from `len`. The
        # write path's `self.data[…]` is deliberate and stays; this is not the write path, and the
        # matcher one function up already went through the guarded read.
        pins = self.readable_pins()
        parts = []
        total = len(pins)
        for key, value in (applies_to or {}).items():
            if value is not None:
                continue
            matched = sum(1 for p in pins if p.get(key) == value)
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

        What is left to check is therefore small and honest, and it is asked of `ARC_MOVES` rather
        than of one tuple (v0.24). For the two settlement arcs the answer is unchanged: a pin in
        `SETTLED_STATES` has something to bring back; a pin already open has not, and re-stamping
        `resolution_mode: "asked"` on it would be the only lasting effect — a mark nothing clears.
        `cross_derive` moves a wider set and stops at a narrower one, because a disagreement is
        about a claim rather than about an election: it marks an OPEN pin contested, and it may not
        un-close finished work. Both facts were true before; both lived inside `cross_derive` as a
        state expression nothing else could ask.
        """
        _require(arc in REOPEN_ARCS, f"arc must be one of {REOPEN_ARCS}; got {arc!r}")
        state = pin_read(pin)["state"]
        if state in ARC_MOVES[arc]:
            return "would_reopen"
        return "already_closed" if state in CLOSED_STATES else "nothing_settled"

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
        pin = self.writable_pin(pin_id)
        reopened = bool(upheld) and self.reopen_verdict(pin, "challenge") == "would_reopen"
        event = {
            "id": self._next_id("chl_", self.writable_collection("decision_log")),
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
        self.writable_collection("decision_log").append(event)
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
        pin = self.writable_pin(pin_id)
        self._gate_closed(pin, "premortem")
        _require(source in _CHALLENGE_SOURCES,
                 f"source must be one of {_CHALLENGE_SOURCES}; got {source!r} — the same vocabulary "
                 f"`challenge` checks, because this is the same role's second mode")
        _require_objects(failure_modes, "failure_modes",
                         "each one names a class, a description and how the work dies")
        _require(bool(failure_modes),
                 "a premortem needs at least one failure mode — 'nothing will go wrong' is the "
                 "belief the exercise exists to break")
        for fm in failure_modes:
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
        for pt in _require_objects(list(paper_tigers or []), "paper_tigers",
                                   "each one names a risk and the evidence it is already mitigated"):
            _require(bool(str(pt.get("risk", "")).strip()),
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

        **v0.24 — it is an arc, and the arcs' own writer moves the pin.** That last paragraph used to
        be the reason this function wrote `state`, `substate` and `resolution_mode` itself instead of
        calling `_reopen_minimal`, and the price was everything ELSE `_reopen_minimal` does: a
        disagreement took a pin back into the open set still carrying the `verification` a settlement
        door reads as permission. Reproduced over real stdio — `add_pin(defect) -> add_remediation ->
        done -> cross_derive(agree)` (the envelope reaches `cross_derived`) `-> cross_derive
        (disagree)`, then `ledger_resolve` with `evidence="no new observation of any kind"` closed
        it. The no-cascade decision is unchanged and is now DECLARED, in `ARC_CASCADES`, where a
        reader of the arc table can see it.

        **And agreement may not launder a refuted claim.** `agree` merges a closing rung onto the
        pin's envelope — which is legitimate on a pin that has not been contradicted, and was
        legitimate on the envelope `_invalidate_settlement_claims` had just demoted: four calls
        apart, `resolve(rung="observed") -> reopen(fired="incident") -> ledger_resolve` (correctly
        refused as `unverified`) `-> cross_derive(agree)` restored a closing rung and the pin closed.
        Two providers agreeing is a re-derivation, not an observation of the thing production
        refuted, so where `refuted_claim` stands the record and the event are still written and the
        rung is not raised — `rung_raised` on the `xdr_` event says which happened, exactly as
        `reopened` does one field over.

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
        pin = self.writable_pin(pin_id)
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
        # Asked before anything is written, so the event can state what happened rather than leave a
        # reader to infer it from a pin that may have been moved by something else.
        refuted = refuted_claim(pin)
        # Recorded BEFORE anything moves, and recorded whatever happens next: an arc that reopens
        # without appending is a state change nobody can audit, which is exactly what this was.
        event = {
            "id": self._next_id("xdr_", self.writable_collection("decision_log")),
            "pin_id": pin_id,
            "timestamp": _now(),
            "claim": record["claim"],
            "providers": record["providers"],
            "agreement": agreement,
            # The arc's own predicate, asked of the arc table rather than re-expressed here. It says
            # exactly what `agreement != "agree" and pin["state"] not in CLOSED_STATES` said —
            # `ARC_MOVES["cross_derive"]` IS that complement — and now one function answers
            # "would this arc move this pin" for all three arcs.
            "reopened": (agreement != "agree"
                         and self.reopen_verdict(pin, "cross_derive") == "would_reopen"),
            # Whether the agreement actually strengthened the pin, on the event, for `reopened`'s
            # reason: an arc that changes the pin conditionally must record which way it went, or the
            # only carrier of the fact is a field a later call can overwrite.
            "rung_raised": agreement == "agree" and not refuted,
            "source": "challenge:cross_derivation",
            "policy_hash": self._policy_hash(),
        }
        self.writable_collection("decision_log").append(event)
        record["event_id"] = event["id"]
        record["rung_raised"] = event["rung_raised"]
        if refuted:
            record["refuted_claim"] = refuted
        if event["rung_raised"]:
            verification = pin.get("verification") or {}
            verification["rung"] = _writable_rung("cross_derive", "cross_derived")
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
            # The arcs' one writer (v0.24). It writes the same three fields this used to write by
            # hand — `needs_input`, the arc's own substate, and `resolution_mode: "asked"`, because a
            # contested claim is never re-defaulted silently — and, being the one writer, it also
            # takes back the `SETTLEMENT_CARRIERS` this arc had been leaving standing.
            self._reopen_minimal(pin, "cross_derive", via=event["id"])
        return record

    def label_failure(self, pin_id: str, failure_class: str, detail: str,
                      phase: str, source: str = "measurer") -> dict:
        """v0.9 — label a failure that ACTUALLY happened, in the same words the premortem used.

        Appends an immutable FailureEvent. It changes no state: labeling is observation, and the
        response (reopen, challenge, re-plan) stays a separate, explicit act. Sharing the vocabulary
        with the premortem is the whole point — it is what lets 'what we feared' and 'what happened'
        be compared at all, instead of being two prose piles nobody can join.
        """
        self.writable_pin(pin_id)
        _require(failure_class in FAILURE_CLASSES, f"class must be one of {FAILURE_CLASSES}")
        _require(failure_class != "other" or bool(detail),
                 "class 'other' requires detail (the open escape hatch is named, not blank)")
        _require(phase in FAILURE_PHASES, f"phase must be one of {FAILURE_PHASES}")
        _require(bool(str(detail).strip()), "a failure label needs what actually happened")
        event = {
            "id": self._next_id("fal_", self.writable_collection("decision_log")),
            "pin_id": pin_id,
            "timestamp": _now(),
            "class": failure_class,
            "detail": str(detail).strip(),
            "phase": phase,
            "source": source,
            "policy_hash": self._policy_hash(),
        }
        self.writable_collection("decision_log").append(event)
        return event

    def foresight(self, pin_id: str) -> dict:
        """What was feared vs what happened, joined on the shared vocabulary.

        `anticipated` are classes the premortem named and that then occurred; `surprises` are classes
        that occurred and nobody foresaw; `paper_tigers_held` are dismissed risks that stayed
        dismissed. D0 — a set comparison over recorded events, no scoring: the numbers are small,
        rare and human, and a rate computed over them would be a statistic with no population.

        A READ, through the read path (v0.28): it is the second half of what `ledger_label_failure`
        returns, and it used to index `e["id"]` over the raw log — the exact expression v0.18 removed
        from `summary()` — on a call whose first half had already been committed to disk.
        """
        pin = pin_read(self.pin(pin_id))
        premortem = pin.get("premortem") or {}
        foreseen = {fm.get("class") for fm in premortem.get("failure_modes", [])}
        happened = [e for e in self.readable("decision_log")
                    if e.get("pin_id") == pin_id and str(e.get("id", "")).startswith("fal_")]
        occurred = {e.get("class") for e in happened}
        tigers = {pt.get("risk") for pt in premortem.get("paper_tigers", [])}
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
        pin = self.writable_pin(pin_id)
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
            "id": self._next_id("rev_", self.writable_collection("decision_log")),
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
        self.writable_collection("decision_log").append(event)
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

        A READ, through the read path (v0.28). It used to index `e["pin_id"]` raw over
        `self.data["decision_log"]`, and it is called by all three arc tools AFTER the write was
        committed: on a file carrying one hand-written entry that names a `via` and no `pin_id`, the
        reopen landed on disk and the tool answered `isError`, so an agent reading that error and
        retrying reopened the pin a second time. Both halves are fixed — this one reads what a reader
        may index, and the door now computes its answer before it commits.
        """
        return [str(e.get("pin_id", "")) for e in self.readable("decision_log")
                if e.get("via") == event_id and e.get("pin_id")]

    def _reopen_minimal(self, pin: dict, arc: str, via: str) -> list[str]:
        """THE only writer of the reopened state, and the only place either arc moves anything.

        `_settle`'s twin, and it is one function for the same reason: a rule that lives in an arc has
        to be remembered by the next arc, and there are exactly two of them precisely because nobody
        was counting. Returns the ids it moved BESIDE `pin`, so a caller never has to re-derive the
        radius from a state it just wrote.

        Reopen the minimum: the pin plus — where `ARC_CASCADES` says the arc sweeps them up — its
        settled `depends_on` dependents, transitively. An arc that reopens everything regenerates the
        very churn the skills cure, and the `cross_derive` arc sweeps up nothing at all for the reason
        `cross_derive` has always given: nobody yet knows which side is wrong. That used to be
        expressed by not calling this function, which is how it also came to skip everything else
        this function does (v0.24).

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

        **And every OTHER pin is read through the read path (v0.28).** The walk indexed `p["id"]` and
        `p["state"]` over the raw list, so a reopen of a well-formed pin died with `KeyError: 'id'`
        because some unrelated pin in the file carried none — one bad record, and the whole file
        unwritable. `writable_pins` pairs each record with its guarded read: the cascade DECIDES off
        the read (a pin with no readable id is depended on by nothing; one with no readable state is
        in no settled state, so nothing sweeps it up) and WRITES onto the record.
        """
        if self.reopen_verdict(pin, arc) != "would_reopen":
            return []
        substate = _SUBSTATE_BY_ARC[arc]
        pins = self.writable_pins()
        to_reopen = {pin["id"]}
        changed = ARC_CASCADES[arc]
        while changed:
            changed = False
            for p, read in pins:
                if not read["id"] or read["id"] in to_reopen:
                    continue
                # NOTE: three states, where `SETTLED_STATES` has four — `deferred` is not cascaded
                # over. Kept exactly as it was rather than "corrected", because whether a pin elected
                # OUT of scope rested on the falsified truth is a real question and no evidence here
                # settles it. Recorded in `docs/open-gaps.md` under §5 rather than resolved by
                # guessing: inventing a rationale for someone else's tuple is how a hardcoded list
                # acquires the authority of a decision.
                if any(dep in to_reopen for dep in read["depends_on"]) \
                        and read["state"] in ("decided", "resolved", "accepted"):
                    to_reopen.add(read["id"])
                    changed = True
        cascaded: list[str] = []
        for p, read in pins:
            if read["id"] not in to_reopen:
                continue
            if read["id"] != pin["id"]:
                # The record `_settle` writes for every settlement, written here for every pin the
                # closure sweeps up. `via` joins it to the arc event that caused it, which is what
                # makes the radius readable (`cascaded_by`) instead of guessable from a substate.
                self.writable_collection("decision_log").append({
                    "id": self._next_id("cas_", self.writable_collection("decision_log")),
                    "pin_id": read["id"],
                    "timestamp": _now(),
                    "arc": arc,
                    "via": via,
                    "from_state": read["state"],
                    "to_state": "needs_input",
                    "substate": substate,
                    "policy_hash": self._policy_hash(),
                })
                cascaded.append(read["id"])
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
        # Through the read path (v0.28): this is called on every pin the cascade sweeps up, not only
        # on the one `writable_pin` cleared, so the envelope here is whatever the file holds. A
        # `verification` that is a string reads as `{}` and returns below — which is the right answer
        # anyway, since a claim nothing can read is a claim there is nothing to take back.
        envelope = pin_read(pin).get("verification") or {}
        if envelope.get("rung") not in _CLOSING_RUNGS:
            return
        pin["verification"] = {
            **envelope,
            "rung": _writable_rung("_invalidate_settlement_claims", None),
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
        pin = self.writable_pin(pin_id)
        self._gate_closed(pin, "add_remediation")
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
        pin = self.writable_pin(pin_id)
        self._gate_closed(pin, "set_remediation_status")
        for item in pin["remediation"]:
            # `.get` for `settlement_verdict`'s reason one method over: the item's own keys are
            # nested scalars, which `PIN_SHAPES` deliberately does not describe, so the read that
            # reaches them is the read path's `.get` rather than a rule.
            if item.get("id") == item_id:
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
        pin = self.writable_pin(pin_id)
        if evidence is not None:
            _require(bool(str(evidence).strip()), "evidence, when given, must not be blank")
            pin["evidence"] = evidence
        if rung is not None:
            # v0.26 — the module-level carrier rather than this door's own `_require`. It said
            # exactly what `RUNG_WRITER_RUNGS["fresh_observation"]` says, and saying it here is how
            # the door beside it came to accept a closing rung with nothing to check it against.
            _require(str(evidence or "").strip(),
                     "a claimed rung needs the observation it rests on — pass `evidence`. It used "
                     "to be satisfied by the `evidence` already ON the pin, which is the "
                     "observation the LAST resolve rested on: after a reopen that field names "
                     "exactly what production refuted, so a stale sentence opened the gate for a "
                     "fresh claim (v0.26, `SETTLEMENT_CARRIERS`)")
            pin["verification"] = {**(pin.get("verification") or {}),
                                   "rung": _writable_rung("resolve", rung)}
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
        pin = self.writable_pin(pin_id)
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
        pin["verification"] = {
            "determinism": determinism,
            # v0.26 — through the carrier, which is what `records_absence` had always claimed and
            # nothing checked. This read `_require(rung in VERIFICATION_RUNGS)`: the whole
            # vocabulary, closing rungs included, on the one door whose meaning is that correctness
            # could NOT be established. See `RUNG_WRITER_RUNGS`.
            "rung": _writable_rung("mark_correctness_unknown", rung),
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

    # -- v0.30: the claim, and the frontier it makes readable ----------------------------------

    def _claim_on_disk(self, pin_id: str) -> dict:
        """What the FILE says about this one pin's claim, right now. Never raises.

        The compare-and-set below is decided against this and not against `self.data`, and that is
        the whole mechanism: two sessions each hold their own in-memory copy, so a check against the
        copy answers *did I claim this* rather than *has anybody*. Only the two claim carriers are
        re-read — a wholesale reload would drop whatever else this session has in flight, and a door
        that silently discards a caller's other work to answer a scheduling question is a worse bug
        than the one it fixes.

        The residual is real and is named rather than papered over: between this read and the
        caller's `save()` there is a window, so this is best-effort and not a lock. That is the
        strength the field is specified at — a claim never gates a write, and the ledger's existing
        write discipline is what covers concurrent access. Buying more would mean a lock file
        nobody can unlock, which is the trap this design was written to avoid.
        """
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}
        for entry in read_collection(data, "pins"):
            read = pin_read(entry)
            if read["id"] == pin_id:
                return {c: read.get(c) for c in CLAIM_CARRIERS}
        return {}

    def claim(self, pin_id: str, holder: str, now: Optional[datetime] = None) -> dict:
        """Take this pin before doing the work. Compare-and-set; writes nothing else.

        **It writes nothing but the claim, and that is the property.** The whole point is that the
        claim lands BEFORE the work, so a door that also did something is a door somebody calls
        second — and a claim taken after the work is a receipt, not a reservation.

        Claiming a pin somebody else holds LIVE fails and names the holder; it never overwrites.
        Claiming one whose holder is yourself re-stamps it, which is how a session that outlives the
        TTL says so rather than being assumed dead. Claiming a stale one succeeds and reports
        `reclaimed` with the holder it took it from, because a silent takeover is how two sessions
        end up believing the same thing about different work.

        It goes through `writable_pin` and `_gate_closed` like every other per-pin write door, and
        the second one is what makes finished work unclaimable: a reservation on work that is over
        would park a pin off the frontier, held by a session that is never going to release it.
        That refusal is the plain kind — it is the one door on the roster whose refusal is not about
        un-finishing anything.
        """
        _require(isinstance(holder, str) and holder.strip(),
                 "a claim carries the holder that took it; an anonymous claim is a pin nobody can "
                 "be asked about and nobody can release")
        pin = self.writable_pin(pin_id)
        self._gate_closed(pin, "claim")
        held = self._claim_on_disk(pin_id)
        current = claim_state(held, now)
        incumbent = held.get("claimed_by") or ""
        if current == "live" and incumbent != holder:
            return {"pin_id": pin_id, "claimed": False, "holder": incumbent,
                    "claimed_at": held.get("claimed_at"), "claim_state": "live",
                    "why": f"{incumbent} holds this pin and the claim is still live; "
                           f"work something else, or ask them"}
        pin["claimed_by"] = holder
        pin["claimed_at"] = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        return {"pin_id": pin_id, "claimed": True, "holder": holder,
                "claimed_at": pin["claimed_at"], "claim_state": "live",
                "reclaimed": incumbent if (current == "stale" and incumbent
                                           and incumbent != holder) else None,
                "renewed": current != "unclaimed" and incumbent == holder}

    def release(self, pin_id: str, holder: str = "") -> dict:
        """Put the pin back on the frontier. Explicit, and the mirror of the door above.

        A settlement releases too (`_settle`), so this is for the other ending: a session that stops
        without finishing. Passing `holder` releases only your own claim — the honest default for an
        agent — and omitting it releases whatever is there, which is what a human clearing up after a
        dead session needs. Releasing an unheld pin is not an error: the post-condition a caller
        wants is *nobody holds this*, and refusing when it is already true would make cleanup a
        thing you have to check before doing.
        """
        pin = self.writable_pin(pin_id)
        incumbent = pin_read(pin).get("claimed_by") or ""
        if holder and incumbent and incumbent != holder:
            return {"pin_id": pin_id, "released": False, "holder": incumbent,
                    "why": f"{incumbent} holds this pin, not {holder}; release it as its holder or "
                           f"with no holder at all"}
        for carrier in CLAIM_CARRIERS:
            pin.pop(carrier, None)
        return {"pin_id": pin_id, "released": bool(incumbent), "holder": incumbent}

    def claims(self, now: Optional[datetime] = None) -> list[dict]:
        """Every pin somebody is holding, and how that claim reads — the set `frontier` drops.

        It exists so a queue never shrinks silently. A frontier that just returns fewer pins reads
        as *there is less work*, and the difference between *nothing to do* and *your peers have it
        all* is the whole reason a human is looking at the number.
        """
        out = []
        for pin in self.readable_pins():
            read = pin_read(pin)
            state = claim_state(read, now)
            if state == "unclaimed":
                continue
            out.append({"pin_id": read["id"], "title": read["title"],
                        "holder": read.get("claimed_by") or "",
                        "claimed_at": read.get("claimed_at"), "claim_state": state,
                        "state": read["state"]})
        return out

    def frontier(self, candidates: Optional[Iterable[dict]] = None,
                 now: Optional[datetime] = None) -> list[dict]:
        """Open, unblocked and unclaimed — what a session may take right now.

        The claim filter is here and only here, and the candidate set is the caller's, because
        "unblocked" is genuinely two questions and this package already answers both. The interview
        asks whether anything is still in play upstream (`OPEN_STATES`); the wave scheduler asks
        whether the upstream WORK is done (`buildloop._DONE_STATES`), which a `decided`-but-unbuilt
        dependency fails and this one passes. Those are different questions with different right
        answers, so `buildloop.frontier` passes its own candidates in rather than a third notion
        being invented here — one claim filter, two schedulers.

        A stale claim does NOT exclude a pin: that is the whole difference between the two claimed
        readings, and a frontier that hid pins behind dead sessions would be the outage this field
        was added to prevent, wearing the fix's name.
        """
        if candidates is None:
            reads = [(p, pin_read(p)) for p in self.readable_pins()]
            by_id = {r["id"]: r for _, r in reads}
            candidates = [p for p, r in reads
                          if r["state"] in OPEN_STATES
                          and not any(by_id[d]["state"] in OPEN_STATES
                                      for d in r["depends_on"] if d in by_id)]
        return [p for p in candidates if claim_state(pin_read(p), now) != "live"]

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

        The fan-out it sorts on is `downstream_of` (v0.27). It was a nested `transitive` here and a
        byte-identical `transitive_downstream` in `interview.funnel`, and both counted simple PATHS:
        one diamond in the roadmap and the pin the funnel calls most informative may simply be the
        pin with the most ways to reach the same dependants. See that function.
        """
        reads = [(p, pin_read(p)) for p in self.readable_pins()]
        guarded = [r for _, r in reads]
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
            key=lambda pr: (unverifiable_first(pr[1]), -len(downstream_of(pr[1]["id"], guarded)),
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
            # `str(...)`, and not because these are printed (v0.25): the value becomes a dict
            # KEY, so a `class` or a `door` that is a list made this whole summary a bare
            # `TypeError: unhashable type` — the same class of death `e["id"]` was, one line up,
            # two rounds after that one was fixed. Found by the derived log corpus rather than by
            # anyone reading for it: `.get` guards absence and says nothing about type.
            if eid.startswith("fal_"):
                cls = str(e.get("class") or "unrecorded")
                by_failure[cls] = by_failure.get(cls, 0) + 1
            elif eid.startswith("stl_"):
                door = str(e.get("door") or "unrecorded")
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
            # v0.30 — the two halves of the same number, never one. `open_questions` says how much
            # is unanswered; these say how much is TAKEABLE and by whom. Reporting only the first
            # would let a session read "nine open" and take the one a peer is already on, which is
            # the duplication the field exists to remove; reporting only the frontier would let a
            # queue shrink silently, which reads as progress and is its opposite.
            "frontier": len(self.frontier()),
            "claimed": {c["pin_id"]: c["holder"] for c in self.claims()},
        }


def _json_arg(raw: Optional[str], field: str) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--{field}: invalid JSON ({exc})")
