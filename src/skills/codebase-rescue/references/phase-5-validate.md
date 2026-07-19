# Phase 5 — Validate (data decides) — the loop's evidence gate

Step 6 of the remediation loop. A fix is not done because the build is green — prove the gap
closed, with evidence specific to the pin kind. Read-only: the validator produces a verdict,
never a change or a guess.

## Checks by pin kind

- **contract_mismatch / internal_contradiction** — re-extract the shapes at every anchor,
  re-diff. Must now agree with the elected canonical `to_be`. Any residual disagreement → not
  resolved. Plus the generated **contract test** (`references/core/contract-testing.md`) passes at the
  boundary — the runtime complement to the static re-diff. The re-diff is the same engine that found
  it: `contract_diff` against the carrier, or `reconcile_layers` head-to-head when there is none.
  **An empty result is the evidence** — anything else is not resolved, however convincing the diff
  looks by eye.
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
- **Static signal is evidence too.** The type-checker passes on the touched files and any
  architecture-fitness constraint stays green — deterministic, high-confidence, and cheaper than
  re-running judgment checks (`references/core/static-analysis.md`).
- **Confirm the change stayed in scope** (`scripts/runtime/impact.py`). Diff the touched files against
  the graph: the change should reach only the pin's intended nodes/anchors — an unexpected node in the
  `affected_node_ids` set is a regression signal, not a pass. Files in the diff that map to **no**
  graph node (`unmapped_files`) are new or renamed code the graph does not know yet — flag them for
  incremental re-analysis before the wave is declared done, so a fix does not silently introduce
  un-audited surface.
- **Only on evidence** set `pin.state = resolved` and record the validation evidence in the pin
  (auditable). Otherwise return the item to Phase 4 with the failing evidence attached — a
  local retry of that item, NOT a global restart.
- Mutation results from `module-test-validity` gate whether a Track-A test is trustworthy: a
  test that does not kill mutants is not accepted as validation.
