<!-- GENERATED FILE - do not edit. Source: core/contract-testing.md at the repo root; regenerate with: python scripts/sync_core.py -->

# Contract Testing (shared core) — the runtime complement to the drift-check

Both skills own a cross-layer contract (rescue reconciles one from divergent layers; greenfield
propagates one to all layers). The **drift-check** guarantees the layers' *shapes* match the
carrier — but statically. Contract testing is its **dynamic** complement: it proves each running
boundary actually **honors** the contract at runtime, not just at typecheck.

Both are needed, and they catch different failures:

| Check            | Kind    | Catches                                                              |
|------------------|---------|---------------------------------------------------------------------|
| **Drift-check**  | static  | a layer's declared shape edited away from the carrier               |
| **Contract test**| dynamic | a boundary that typechecks but returns/accepts the wrong shape at runtime — nullability that only appears with real data, enum values the code emits but the type forbids, serialization drift, an error path that breaks the response contract |

## Generated from the carrier — never hand-authored

Contract tests are generated **from the contract carrier** (`references/core/shape-engine.md` descriptor),
so they cannot drift from it — the same principle as the generated layers. A hand-written fixture
that duplicates the contract shape is itself a drift source; generate the fixtures.

## The two directions

- **greenfield (generate mode)** — the contract tests are **Track-A** tests, born from the
  carrier as the layers are generated. Each asserts that a boundary, driven with a
  carrier-conformant request, returns a carrier-conformant response *at runtime*. They are green
  by construction once the slice is built, and they guard the boundary forever after.
- **rescue (reconcile mode)** — after the interview elects the canonical shape for a
  `contract_mismatch`, a contract test pins the **reconciled** boundary so it cannot silently
  regress. Here it doubles as a Phase-5 validation oracle: the mismatch is closed only when the
  boundary passes the generated contract test, not merely when shapes re-diff clean.

## Levels (pick by the topology decision)

- **Boundary schema validation** — the default: validate request/response against the
  carrier-derived schema at each API boundary.
- **Consumer-driven contracts (CDC)** — when the topology decision elected services: the
  consumer's expectations, generated from the shared carrier, run against the provider in CI.
- **Property-based** — generate inputs from the contract types to exercise the boundary beyond
  hand-picked cases (highest value on the `blocker`/`high` boundaries).

## Procedure

1. From the carrier, generate boundary tests (request + response validated against the schema).
2. Run them at each boundary in CI, **beside the drift-check** — static and dynamic together.
3. A failure means a layer drifted *behaviorally* from the contract: route it back as a
   `contract_mismatch` (rescue) or a failed Track-A item (greenfield).

## What NOT to do

- Don't duplicate the drift-check. Contract tests are the runtime complement, not a re-run of the
  static shape diff.
- Don't hand-author fixtures that can drift from the carrier — generate them.
- Don't test beyond the contract here. Business-logic behavior is the normal Track-A test's job;
  contract tests assert *the boundary honors the shape*, nothing more.

## Output

Generated contract tests per boundary, wired into CI next to the drift-check. Referenced by
greenfield's Phase 5 (validate) and `contract-propagation`, and by rescue's Phase 5 and
`contract-reconciliation`.
