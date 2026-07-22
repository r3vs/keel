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

## Asserted against the generated schema — never hand-duplicated

Contract tests are **authored** (they are Track-A tests), but they assert request/response against
the **carrier-derived schema the generator already emits** (the Pydantic / TypeScript models from
`generate.py`) — never against a shape copied by hand. That is what keeps them from drifting: when
the carrier changes, the regenerated schema changes with it, so a test that imports the generated
schema moves too or fails loudly. A fixture that *duplicates* the contract shape is itself a drift
source; assert against the generated schema instead. (The **schema** is generated; the test is the
authored, agent-orchestrated half — there is deliberately no contract-test *generator* in the runtime.)

## The two directions

- **greenfield (generate mode)** — the contract tests are **Track-A** tests, authored as the
  layers are generated and pinned to the carrier-derived schema. Each asserts that a boundary, driven
  with a carrier-conformant request, returns a carrier-conformant response *at runtime*. They are green
  by construction once the slice is built, and they guard the boundary forever after.
- **rescue (reconcile mode)** — after the interview elects the canonical shape for a
  `contract_mismatch`, a contract test pins the **reconciled** boundary so it cannot silently
  regress. Here it doubles as a Phase-5 validation oracle: the mismatch is closed only when the
  boundary passes the contract test, not merely when shapes re-diff clean.

## Levels (pick by the topology decision)

- **Boundary schema validation** — the default: validate request/response against the
  carrier-derived schema at each API boundary.
- **Consumer-driven contracts (CDC)** — when the topology decision elected services: the
  consumer's expectations, generated from the shared carrier, run against the provider in CI.
- **Property-based** — generate inputs from the contract types to exercise the boundary beyond
  hand-picked cases (highest value on the `blocker`/`high` boundaries).

## Procedure

1. Author boundary tests that validate request + response against the carrier-derived schema
   (the generated Pydantic / TS models), never against a hand-copied shape.
2. Run them at each boundary in CI, **beside the drift-check** — static and dynamic together.
3. A failure means a layer drifted *behaviorally* from the contract: route it back as a
   `contract_mismatch` (rescue) or a failed Track-A item (greenfield).

## What NOT to do

- Don't duplicate the drift-check. Contract tests are the runtime complement, not a re-run of the
  static shape diff.
- Don't hand-duplicate the contract shape in a fixture — assert against the carrier-derived schema
  the generator already emits.
- Don't test beyond the contract here. Business-logic behavior is the normal Track-A test's job;
  contract tests assert *the boundary honors the shape*, nothing more.

## Output

Contract tests per boundary, asserting against the generated schema, wired into CI next to the
drift-check. Referenced by
greenfield's Phase 5 (validate) and `contract-propagation`, and by rescue's Phase 5 and
`contract-reconciliation`.
