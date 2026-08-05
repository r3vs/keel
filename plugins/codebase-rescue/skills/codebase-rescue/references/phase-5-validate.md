# Phase 5 — Validate (data decides) — the loop's evidence gate

Step 5 of the remediation loop — the **first** gate on a finished item, before any review judgment
is spent. A fix is not done because the build is green — prove the gap
closed, with evidence specific to the pin kind. Read-only: the validator produces a verdict,
never a change or a guess.

## Checks by pin kind

- **contract_mismatch / internal_contradiction** — re-extract the shapes at every anchor,
  re-diff. Must now agree with the elected canonical `to_be`. Any residual disagreement → not
  resolved. Plus the generated **contract test** (`references/core/contract-testing.md`) passes at the
  boundary — the runtime complement to the static re-diff. The re-diff is the same engine that found
  it: `contract_diff` against the carrier, or `reconcile_layers` head-to-head when there is none.
  **An empty `findings` is the evidence** (both tools answer `{"findings": [...]}`) — anything else
  is not resolved, however convincing the diff looks by eye.
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
- **Confirm the change stayed in scope** (the `impact_overlay` tool). Diff the touched files against
  the graph: the change should reach only the pin's intended nodes/anchors — an unexpected node in the
  `affected_node_ids` set is a regression signal, not a pass. Files in the diff that map to **no**
  graph node (`unmapped_files`) are new or renamed code the graph does not know yet — flag them for
  incremental re-analysis before the wave is declared done, so a fix does not silently introduce
  un-audited surface.
- **Check the change against its own declared boundary** (`scope_check`). `impact_overlay` says what
  the diff *reaches*; this says whether it stayed inside the zone the pin already recorded — a
  boundary a human saw and accepted, not one drawn afterwards. Files outside it are candidate
  `scope_creep` in the shared failure vocabulary. Files inside it and untouched are **not** a
  finding: a blast radius is what could be affected, and the ladder aims below it by design. No
  declared boundary at all reports `checked: false`, because an unchecked scope must never read as
  a clean one.
- **Ask git what this diff usually touches** (`cochange_omissions`). A second, independent carrier
  for the same cross-layer thesis the field-shape engine serves: shapes compare *declared structure*
  and miss coupling that lives in config, fixtures, docs and convention; history compares *recorded
  behaviour* and catches exactly that. When both point at the same file, the finding is strong.
  **When they disagree, that is itself the finding** — so never merge them into one score. The
  output is frequencies and candidates, never a verdict: a deliberate omission and a forgotten one
  look identical from git.
- **Record the evidence, and record what it was run against.** Write the validation evidence into
  the pin (auditable) together with the diff/commit it covers: the two-stage review reads this
  record instead of re-deriving it, and evidence it cannot tie to the diff in front of it is not
  evidence. On failure return the item to Phase 4 with the failing evidence attached — a local
  retry of that item, NOT a global restart — and the review never runs on it.
- **Evidence is necessary, not sufficient.** `pin.state = resolved` requires the evidence **and** a
  `MERGE` from the two-stage review that follows. This gate proves the oracle *passes*; it cannot
  see whether it passes for the right reason — a Track-A test that special-cases its own input is
  green here and is exactly what the reviewer exists to catch. Never set `resolved` from this gate
  alone.
- Mutation results from `module-test-validity` gate whether a Track-A test is trustworthy: a
  test that does not kill mutants is not accepted as validation.
