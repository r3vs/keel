# Module: Cross-Layer Contract Propagation (core)

The module greenfield lives or dies on — the exact mirror of rescue's `contract-reconciliation`.
Rescue **diffs** the same entity's representation across DB / ORM / API / frontend to find where
they disagree. Greenfield **defines** that representation once and **generates** each layer from
it, so they cannot disagree in the first place. Same shape engine (`core/shape-engine.md`), run
forward.

## The hinge (rescue's Phase-0 verdict, run in reverse)

Rescue's gating experiment found that a monorepo's **shared-types package is the strongest
standalone contract** — stronger than any inferred cross-layer graph edge; all of VibraFlow's
contract findings fell out of diffing the layers against `@vibraflow/shared`. That empirical
result is the whole idea of this module:

- rescue **discovers** the contract after the fact (the shared-types package is where the real
  contract already lived, so diff against it);
- greenfield **installs** the contract up front (author the shared-types package first, generate
  every layer from it, and wire the same shape-diff as a CI drift-check so no future hand-edit can
  break alignment).

The drift that rescue spends its whole engine detecting is, here, made **structurally
impossible** — and then guarded by the very same diff, kept running for the life of the project.

## The boundaries (generation targets, not extraction sources)

A data entity will be represented four+ times. In rescue those are things to read and compare;
here they are things to **emit from one source**:

| Boundary        | Generated artifact                                                       |
|-----------------|--------------------------------------------------------------------------|
| **DB schema**   | migration / DDL: tables, columns, types, nullability, constraints, enums, FKs |
| **ORM / model** | model classes / structs for the chosen ORM                               |
| **API contract**| DTOs / serializers / route stubs (typed request/response)                |
| **Frontend**    | client types / interfaces + typed fetch/query stubs                      |

Optionally also message/event schemas, GraphQL SDL, config contracts — same procedure.

## Procedure

### 1. Author the canonical entity shapes
From the **decided** data-model pins in the ledger (never from a guess), reduce each field to the
shared descriptor `{ name, type, nullable, enum?, constraints? }` (`core/shape-engine.md`). This
canonical set IS the contract; every layer is a projection of it. Only decided entities — an
entity the interview deferred produces no shape (YAGNI by construction).

### 2. Choose the contract carrier (ponytail: lightest that spans the stack)
- **TS end-to-end / monorepo** → a **shared-types package** (the strongest, lightest carrier).
- **Polyglot** (e.g. Python API + TS client) → **OpenAPI** or **JSON-schema** as the carrier,
  with generators on each side; **protobuf** if an RPC/streaming decision was elected.
Do not reach for a heavyweight schema-registry when a shared-types file suffices.

### 3. Generate each layer from the carrier
Run the type-equivalence table (`core/shape-engine.md`) in **reverse** — one canonical descriptor
→ each layer's syntax: DDL/migration, ORM model, DTO/route stub, client type + fetch stub. The
handlers' bodies are `implement` BuildItems for Phase 4 (Track A); this step only emits the
**aligned typed surfaces**. Generate against the framework's **current** API — pull it from
Context7 (`core/knowledge-sources.md`), not training-cutoff memory, so the scaffolds use today's
idioms.

### 4. Install the drift-check + contract tests (the preventive payload)
Wire the same shape-diff rescue uses into CI: re-extract every layer's shapes and diff them
against the carrier; **fail the build on any disagreement**. Generate the **contract tests** from
the carrier too (`core/contract-testing.md`) and wire them beside the drift-check — the static
diff catches shape edits, the runtime tests catch a boundary that typechecks but violates the
contract with real data. Static + dynamic together. From now on a hand-edit that lets a layer
drift is caught the moment it lands — the project stays aligned for life, not just at generation
time. This is what makes forging *durable* rather than a one-time scaffold.

## Phase-0 gating verdict — TODO (fill from `TODO.md` step 0)

> Run the step-0 experiment before generalizing: author a small contract by hand and generate the
> four layers on a real stack. Record here whether generation is **STRONG** (Plan A — generate all
> four layers) or **WEAK** (Plan B — generate the shared-types/DTO layer only, hand-write the rest
> against it, and lean on the installed drift-check to keep them aligned). Mirror how rescue
> recorded its VibraFlow verdict in `codebase-rescue/references/contract-reconciliation.md`. One data point, not a
> law — re-run per stack family before trusting generation broadly.

## What NOT to do

- **Do not hand-author the same shape in two layers.** That reintroduces exactly the drift rescue
  exists to cure. If you must hand-write a layer (Plan B), it still derives from the carrier and
  the drift-check still guards it.
- **Do not generate ahead of decided entities.** No speculative tables/DTOs "for later" — an
  undecided entity has no shape. This is the anti-slop guardrail at the contract level.
- **Do not let generation invent fields.** The carrier contains only what the domain decision
  committed to; a field with no decision is a gap to take back to the interview, not a default.
- **Do not pick a heavyweight carrier by reflex.** The lightest carrier that spans the languages
  in play wins (ponytail).

## Output

The contract carrier (the single source of truth), aligned scaffolds for each layer, and an
installed CI drift-check — written to disk, with a `BuildItem` (`action: scaffold`,
`contract_carrier` set) per generated layer, each `depends_on` the carrier. These are Wave 1 of
the Phase-3 backlog: everything else `depends_on` the contract, which is why the contract wave
comes first (it falls out of the DAG, not a hardcoded order).

## TODO (implementation)
- [ ] Per-stack generators from the normalized contract (start with live stacks, generalize via
      tree-sitter templates so new stacks are additive).
- [ ] The CI drift-check (rescue's shape-diff, wired to fail the build).
- [ ] Contract-carrier chooser (shared-types vs OpenAPI/JSON-schema/protobuf).
