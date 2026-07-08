# The Decisions Ledger (authoritative schema)

The full, authoritative schema lives in `decisions-ledger-spec.md` (shipped alongside this
skill). Read it before writing anything that touches pins, questions, decisions, policies,
or remediation items. Summary of what matters here:

- One `ledger.json` is the single source of truth; map/interview/brainstorm hold no state.
- `Pin` is a discriminated union on `kind` (contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | other), with an `other` escape
  hatch so the taxonomy stays open.
- `to_be` is DERIVED from user decisions, never authored from code. `gap = diff(to_be, as_is)`.
- `decision_log` is append-only and immutable; `pin.state` is the materialized current view.
  Every DecisionEvent carries `flip_criteria` (the condition under which to reopen it).
- v0.3 adds `cluster_id`, `resolution_mode` (asked | policy_default | proposed_default), and
  the `Policy` entity, plus the severity threshold: blocker/high never go to silent default.
- Only the interview commits decisions; the brainstorm only writes `proposals[]`.
