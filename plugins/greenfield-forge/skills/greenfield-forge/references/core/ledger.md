<!-- GENERATED FILE - do not edit. Source: src/core/ledger.md at the repo root; regenerate with: python scripts/build.py -->

# The Decisions Ledger (authoritative schema) — shared core

The full, authoritative schema lives in `references/core/decisions-ledger-spec.md`.
It is **shared by both skills** in this repo — `codebase-rescue` (curative) and
`greenfield-forge` (preventive) read and write the same `ledger.json`. Read the spec before
writing anything that touches pins, questions, decisions, policies, or build/remediation items.
Summary of what matters here:

- One `ledger.json` is the single source of truth; map/interview/brainstorm hold no state of
  their own — they project a view over it. This is the exact anti-divergence property both
  skills enforce on the codebases they touch.
- `Pin` is a discriminated union on `kind` (contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | **open_decision** |
  **acceptance_criterion** | other), with an
  `other` escape hatch so the taxonomy stays open. `open_decision` (v0.4) is the greenfield
  fork: nothing is built yet, so `as_is` is null and `to_be` is elected before any code exists.
- `to_be` is DERIVED from user decisions, never authored from code. `gap = diff(to_be, as_is)`.
  In rescue, `as_is` is extracted from code and the gap is a remediation roadmap; in greenfield,
  `as_is` starts empty and the gap is the build backlog, converging to zero.
- `decision_log` is append-only and immutable; `pin.state` is the materialized current view.
  Every DecisionEvent carries `flip_criteria` (the condition under which to reopen it) — which
  matters most in greenfield, where decisions are made on incomplete information.
- v0.3 adds `cluster_id`, `resolution_mode` (asked | policy_default | proposed_default), the
  `Policy` entity, and the severity threshold: blocker/high never go to silent default.
- v0.4 adds the `open_decision` kind and the `BuildItem` entity (greenfield twin of
  `RemediationItem`: actions `scaffold | implement | wire | configure`, with `build_track`).
- v0.5 adds the `acceptance_criterion` kind (the testable outcome that roots the DAG) and the
  observable `flip_signal` + `ReopenEvent` (the return arc from production).
- v0.6 adds the **upstream** adversarial arc: a `ChallengeEvent` (from the read-only `challenger`
  role) that refutes an elected oracle — an `acceptance_criterion`, a `to_be`, a `Policy` — as
  unfalsifiable / inconsistent / unsatisfiable / resting on an unstated assumption / ignoring
  fan-out, and reopens the pin (state `challenged`) *before* it is built on. Plus
  `provenance: agent_assumption`: a forced assumption is materialized as a vetoable, challengeable
  pin (`confidence: inferred|ambiguous`) instead of a silent decision (the assumptions doctrine).
  Both arcs **reopen, never decide** — the feedback loop closes the loop downstream, the challenger
  upstream.
- v0.10/v0.11 add `evidence` on the `DecisionEvent` — how the human's answer reached the log
  (`elicited | transcribed | brief | cascaded`), with `human_answer` quoting a relay verbatim and
  `policy_id` naming the `Policy` behind a cascade. The `Policy` carries its own rung, because a
  policy is where the human actually answered for a whole cluster.
- v0.12 holds the cascade to the rule a single decision was already held to: an outcome lands on a
  pin only if that pin's own `question` offers it (so `default_outcome` is an option id), and a
  policy cascades once, over the radius its elector was shown.
- v0.13 makes those rules bind the READER too, since a rule enforced at the write governs no file
  that already exists: the rung of a pre-v0.11 cascade is read from the carrier its writer left
  (never rewritten — the log is immutable), and `version` is a floor that rises only when the file's
  own content conforms to the newer rules.
- v0.14 moves those rules out of the doors and into ONE predicate, because guarding a door only
  guards that door: the same violation went through a cluster fan-out flag and through the project
  brief. Every write that settles a pin whose fork was never put to the human — the cascade, the
  brief — asks `unasked_verdict`; a decision writes one event for one pin; and a cluster-wide answer
  can only be a `Policy`, which is the one thing that records the rule, the quote and the radius.
- v0.15 does the same for v0.13's half: the write-time rules an event can be judged by live in ONE
  table, which the writer validates against and the floor replays, so a rule added later gains its
  reader by construction instead of being false of every file already on disk. And an elected
  `Policy` is a decision on **all three** surfaces — its own card on the map, `policies_by_evidence`
  in the summary, one line in the projected `AGENTS.md` — whether or not it cascaded over any pin.
- v0.16 adds the SECOND predicate, for the question next to v0.14's: `unasked_verdict` governs what
  may be *written* onto a pin nobody was asked about, and nothing governed whether a pin may **leave
  the open set** at all. So `settlement_verdict(pin, door)` answers that for all five doors that
  move a pin in or out of a settled state (`decide` · `accept` · `defer` · `resolve` ·
  `correctness_unknown`), and each one is recorded: the three elected doors by the `DecisionEvent`
  they already write (now stating `settles_as`), the two unelected ones by a `SettlementEvent`.
  Concretely — **deferring is an election**, quoted and reversible like any other; a pin in
  `correctness_unknown` (or carrying a `verification` that reaches no closing rung) does **not**
  resolve; a CLOSED pin is not settled again by any door, it is reopened; and
  `resolution_mode: "asked"` **binds** — the pin's own standing demand to be asked is read by the
  unasked predicate rather than merely written by six sites.
- v0.17 gives the way BACK the same treatment, having found it reachable by nobody: both reopen arcs
  and the two forks-in-waiting had no tool on any host, so `settlement_verdict`'s own refusal
  (*"Reopen it first"*) named an arc nothing could run. `reopen_verdict(pin, arc)` answers *would
  this arc move this pin*, `_reopen_minimal` is its single writer (the twin of `_settle`), and each
  event now records `reopened` beside `upheld` rather than leaving a reader to infer it from a
  `substate` nothing clears. `set_question` becomes **write-if-absent** with `allow_freeform`
  required — a fork composed after the fact may not bound what the human may answer — and a pin in
  `brainstorming` stays in the interview view, because asking the brainstorm for options used to be
  what took the fork off the agenda.
- v0.18 corrects four rules that were false of the thing they were printed on. A policy scope whose
  value is `null` selects the pins carrying **no value** for that field — legitimate, and
  indistinguishable from a wildcard by reading the scope — so the radius now carries `scope_note`
  saying which, and how many of how many. `resolution_mode: "asked"` is written only for a refusal
  that is a **standing property of the pin** (`held_back` · `must_be_asked`): `not_offered` is a
  fact about the *rule's* fit, and recording it on the pin put that pin beyond every later policy,
  permanently, with no clearing door — deliberately still none, since a door that unsets *must be
  asked* can silence the threshold rule. The `correctness_unknown` fork's `accept` option states
  what the door will actually do with it, asked of `settlement_verdict` rather than written beside
  it. `defer` no longer takes a caller-stated rung at the library either: one path reaches it, and
  only the code that ran a path may name it. And `summary` survives a log entry with no `id` —
  reading a ledger is never the operation that fails on it — with the unrecognised entry reported
  under `pre_rule_events`, never skipped in silence.
- v0.20 holds the reopen half to the settlement half's own rules — four rules true on one side of a
  pairing and absent on the other. Every pin a cascade sweeps back into the open set gets a
  **`CascadeEvent`**, the way every pin a door settles gets a `SettlementEvent`: one arc call could
  un-finish a whole dependent closure and leave a record for its origin only. The **radius** each
  arc reports is read off those records rather than off a `substate` nothing clears — a later
  reopen of an unrelated pin was reporting an earlier cascade's pins as its own — and **both** arcs
  report it, having run the same cascade through the same writer. `challenge` (and the challenger's
  premortem mode) holds `source` to a closed vocabulary as `reopen` always has, so an arc that never
  elects cannot sign itself `interview`. `add_proposals` refuses finished work, as `set_question`
  already did. And `allow_freeform` is required at **every** door that composes a fork, not only at
  the one where the rule was written: a menu an agent composed may not bound what the human may
  answer, and `add_pin` composes the identical object.
- v0.21 applies two of those fixes where the round that made them did not look. *Reading a ledger is
  never the operation that fails on it* was true of the log and false of the **pins**: `summary` and
  `interview_view` died with a bare `KeyError` on six pin shapes, on files the map and the
  `AGENTS.md` projection read without complaint. One guarded read (`Ledger.readable` for the
  container, `pin_read` for the fields) replaces them, and every value it substitutes is reported
  under `pre_rule_events` by a `PIN_RULES` entry — the same table shape, and the same refusal to
  skip in silence, that the log half already had. And the states the interview reads are now
  **`INTERVIEW_STATES`** rather than a literal, because the map re-derived them and printed the
  funnel's countdown — *if you say nothing, the interview settles this* — on `detected` pins, which
  pose no fork and reach the interview on no host.
- v0.22 asks the same question of the CARRIERS a settlement door decides on. The way back into the
  open set rewrote the state and left every other one standing, so a pin reopened **by an incident**
  came back still claiming its behaviour had been observed, and re-closed on the evidence the
  incident had refuted. `SETTLEMENT_CARRIERS` names each carrier and what the arcs owe it — the
  `verification` claim is demoted (the rung comes off, `blocked_by` says what refuted it), the
  remediation record stands, because what did not survive is the claim the work *worked* — and the
  table is held to the predicate's own AST. The dispute mark moves to `_settle`, so `resolve` stops
  writing `resolved` over a live `substate: reopened`; `unasked_verdict` and `policy_preview` join
  the guarded read, since a read-only tool must never be the call that fails on a ledger; and
  `add_proposals` refuses a pin that poses no fork, where its own output is unreachable.
- v0.23 carries that same read to the two **projections**, which is where two rounds of hardening it
  had never reached: neither `map.render` nor `instructions.render` builds a `Ledger`, so a guard
  living on the class was a guard neither could use. `readable_ledger` is the one door for a caller
  holding ledger DATA, `policy_read` is `pin_read`'s twin for the third collection, and
  `severity_rank` is now the package's ONE severity ordering — the copy in the `AGENTS.md`
  projection read a *missing* severity as `low`, so a pin whose file states nothing outranked one
  that states a severity outside the set, in the section a tight budget clips first. On the map,
  what the guard drops is now **stated on the page**: `nonconforming` reaches a banner, the traffic
  light never reads green over a file it could not read, and `mount` is a failure boundary that
  renders what it could not project instead of leaving a pane blank. A surface that cannot render
  something says so where a human reads — never blank, never raised.
- Only the interview commits decisions; the brainstorm only writes `proposals[]`; the challenger
  and the feedback loop only reopen — and *reopening is appended before anything moves*, including
  the cross-derivation arc, which may never rewrite the pin's `question`.
- **Every surface outside this file is a projection of it, and projections are one-way.** The map,
  the interview, the `AGENTS.md` region and the issue tracker (`tracker_project`) all render from
  the ledger and none of them is read back into it: an answer typed into a generated issue or into
  a managed region elects nothing, because no tool reads it. That is the same anti-divergence
  property the ledger enforces on the codebases these skills touch, applied to the ledger's own
  audience — a second place a decision can be written is a second place it can disagree.

**Runtime:** the spec's load-bearing rules are not left to care — they are implemented once, for
every skill, in the ledger runtime (stdlib-only, tested in CI): pin CRUD with kind validation,
append-only events, the policy cascade under the severity threshold, assumption surfacing, both
reopen arcs, and the interview view. **Operate the ledger through it; never hand-edit
`ledger.json`** — a hand-written pin bypasses every one of those rules silently.

A skill that runs the ledger names the tool where it uses it (the `ledger_summary` /
`interview_next` MCP tools, or the runtime the build vendored into that skill). This doc
deliberately does not: it is vendored into skills that only need the *schema*, and naming a
runnable path here would drag the whole implementation into every one of them.
