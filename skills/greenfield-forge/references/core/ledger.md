# The Decisions Ledger (authoritative schema) — shared core

The full, authoritative schema lives in `references/core/decisions-ledger-spec.md` (written in Italian).
It is **shared by both skills** in this repo — `codebase-rescue` (curative) and
`greenfield-forge` (preventive) read and write the same `ledger.json`. Read the spec before
writing anything that touches pins, questions, decisions, policies, or build/remediation items.
Summary of what matters here:

- One `ledger.json` is the single source of truth; map/interview/brainstorm hold no state of
  their own — they project a view over it. This is the exact anti-divergence property both
  skills enforce on the codebases they touch.
- `Pin` is a discriminated union on `kind` (contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | **open_decision** | other), with an
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
- Only the interview commits decisions; the brainstorm only writes `proposals[]`.
