# Phase 5 — Validate (data decides) — the loop's evidence gate

Step 6 of the remediation loop. A fix is not done because the build is green — prove the gap
closed, with evidence specific to the pin kind. Read-only: the validator produces a verdict,
never a change or a guess.

## Checks by pin kind

- **contract_mismatch / internal_contradiction** — re-extract the shapes at every anchor,
  re-diff. Must now agree with the elected canonical `to_be`. Any residual disagreement → not
  resolved.
- **incompleteness (implemented)** — the previously-missing behavior now exists, is
  **reachable** (graph edge from an entry point), and its **Track-A test kills the relevant
  mutants** (green-but-mutation-surviving does not validate).
- **defect / security** — re-run the specific tool signal (e.g. the semgrep rule) on the path:
  gone. Re-check reachability.
- **duplication (consolidated)** — jscpd shows the copies collapsed to one; all call sites
  point at `canonical_target`; the **Track-B characterization test is still green** (behavior
  unchanged).
- **structural refactor / delete** — Track-B test still green; graph shows no dangling
  references introduced.

## Rules
- **Green build ≠ done.** Require the specific evidence above per kind. For decision-bearing
  items, the Track-A test is the oracle — the same test that drove the fix is the evidence.
- **Only on evidence** set `pin.state = resolved` and record the validation evidence in the pin
  (auditable). Otherwise return the item to Phase 4 with the failing evidence attached — a
  local retry of that item, NOT a global restart.
- Mutation results from `module-test-validity` gate whether a Track-A test is trustworthy: a
  test that does not kill mutants is not accepted as validation.
