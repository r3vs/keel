# Phase 5 — Validate (data decides) — the loop's evidence gate

Step 5 of the build loop — the **first** gate on a finished item, before any review judgment is
spent. A slice is not done because the build is green — prove it realizes the
elected `to_be`, with evidence specific to the item kind. Read-only: the validator produces a
verdict, never a change or a guess. This is rescue's Phase 5 with the checks pointed at *newly
built* work instead of *closed gaps*.

## Checks by item kind

- **contract scaffold** — re-extract the field shapes across every generated layer and diff them
  against the carrier with `contract_diff`.
  Must be **zero drift** — aligned by construction, so **an empty `findings` is the evidence** and
  anything else means the propagation is broken, not that the diff is being fussy. The installed CI
  drift-check is the standing form of this same call. Plus the generated **contract tests** pass at
  runtime (`references/core/contract-testing.md`): typecheck-green is not enough — the boundary must
  honor the shape with real data.
- **implemented feature (`open_decision` → `to_be`)** — the decided behavior now exists, is
  **reachable** from an entry point (traceable through the built slice), and its **Track-A test
  kills the relevant mutants** (green-but-mutation-surviving does not validate).
- **wired item** — the connection carries a real request/response end-to-end (not just typechecks);
  the boundary test is green.
- **rendered UI slice** — the deterministic half first and at every elected breakpoint:
  `design_scan` over the running URL with a `viewport`, `tokens_diff` against the DTCG contract.
  Those are facts and they block. **Then** the taste lens (`references/core/design-taste.md`) reads
  the *render* — the `design-taste` module in this phase — because generating a UI from one contract
  is precisely the process most likely to land on the statistical center of everything the model has
  seen, and nothing upstream of here is looking for that. Its output is `design_concern` pins:
  options for the interview, never a merge gate.
- **paved road (`scaffold`/`configure`)** — the harness actually runs: tests execute, the linter
  runs, the CI config is valid, the SessionStart hook works. Capture the evidence, don't assume it.

**Record what was applied, not only what it found.** Each module of this phase closes with
`mcp:ledger_record_run` (targets, what derived them, the commit) — the empty run included — and
`mcp:module_coverage` reports the phase-5 modules with no run at this commit as `module-unrun` pins.
A validate step nobody ran and a validate step that found nothing read identically otherwise, and
this phase is the one place where that confusion is expensive.

## Rules

- **Green build ≠ done.** Require the specific evidence above per kind. For decision-bearing items
  the Track-A test is the oracle — the same test that drove the build is the evidence.
- **Record the evidence, and record what it was run against** — write it into the pin (auditable)
  together with the diff/commit it covers, because the two-stage review that follows reads this
  record instead of re-deriving it. On failure return the item to Phase 4 with the failing evidence
  attached — a local retry of that item, NOT a global restart — and the review never runs on it.
- **Evidence is necessary, not sufficient.** `pin.state = resolved` requires the evidence, **and** a
  `MERGE` from the two-stage review, **and** a `verification.rung` of `observed` or `cross_derived`
  — three things, and the door refuses without the third (`mcp:ledger_resolve(rung=…)`). This gate
  proves the oracle *passes*; it cannot see whether it
  passes for the right reason. Never set `resolved` from this gate alone.
- Mutation results gate whether a Track-A test is trustworthy: a test that does not kill mutants is
  not accepted as validation.
- **Check the slice against its own declared boundary** (`scope_check`) once the tree stops being
  empty. Files outside the zone the pin recorded are candidate `scope_creep`; files inside and
  untouched are not a finding. In `forge` mode on a fresh tree there is often no boundary to check
  against, and it says `checked: false` rather than reporting a clean pass — unchecked is not clean.
- **Once there is history, ask git what this diff usually touches** (`cochange_omissions`). It is
  worth less here than in rescue and worth stating why: a young project has little recorded
  behaviour, so the carrier is thin by construction. It grows exactly as `slice` and `evolve` mode
  accumulate the coupling that generation was supposed to prevent — which makes it the honest check
  on whether the contract really is the single carrier the forge claims it is.

## Convergence check (greenfield-specific)

Validation also advances the whole project's state, because greenfield has a terminal condition
rescue does not: **`gap = 0`**. On each resolution, flip the slice's nodes on the to-be map from
ghost→solid and recompute the completeness traffic-light. The gap `diff(to_be, as_is)` shrinks
toward zero; v1 is done when every in-scope decided pin is `resolved`. `deferred` pins remain as
the future backlog — the natural entry point for `slice` mode, and eventually for `codebase-rescue`
auditing the built system against this very ledger. The loop closes on itself: the decisions you
recorded here are the audit baseline later.
