# The Decisions Ledger (authoritative schema) — shared core

The full, authoritative schema lives in `core/decisions-ledger-spec.md`.
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
- Only the interview commits decisions; the brainstorm only writes `proposals[]`; the challenger
  and the feedback loop only reopen.

**Runtime:** the spec's load-bearing rules are not left to care — they are implemented once, for
every skill, in the ledger runtime (stdlib-only, tested in CI): pin CRUD with kind validation,
append-only events, the policy cascade under the severity threshold, assumption surfacing, both
reopen arcs, and the interview view. **Operate the ledger through it; never hand-edit
`ledger.json`** — a hand-written pin bypasses every one of those rules silently.

A skill that runs the ledger names the tool where it uses it (the `ledger_summary` /
`interview_next` MCP tools, or the runtime the build vendored into that skill). This doc
deliberately does not: it is vendored into skills that only need the *schema*, and naming a
runnable path here would drag the whole implementation into every one of them.
