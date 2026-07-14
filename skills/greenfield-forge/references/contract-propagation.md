# Module: Cross-Layer Contract Propagation (core)

The module greenfield lives or dies on — the exact mirror of rescue's `contract-reconciliation`.
Rescue **diffs** the same entity's representation across DB / ORM / API / frontend to find where
they disagree. Greenfield **defines** that representation once and **generates** each layer from
it, so they cannot disagree in the first place. Same shape engine (`references/core/shape-engine.md`), run
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
shared descriptor `{ name, type, nullable, enum?, constraints? }` (`references/core/shape-engine.md`). This
canonical set IS the contract; every layer is a projection of it. Only decided entities — an
entity the interview deferred produces no shape (YAGNI by construction).

### 2. Choose the contract carrier (ponytail: lightest that spans the stack)
- **TS end-to-end / monorepo** → a **shared-types package** (the strongest, lightest carrier).
- **Polyglot** (e.g. Python API + TS client) → **OpenAPI** or **JSON-schema** as the carrier,
  with generators on each side; **protobuf** if an RPC/streaming decision was elected.
Do not reach for a heavyweight schema-registry when a shared-types file suffices.

### 3. Generate each layer from the carrier
Run the type-equivalence table (`references/core/shape-engine.md`) in **reverse** — one canonical descriptor
→ each layer's syntax: DDL/migration, ORM model, DTO/route stub, client type + fetch stub. The
handlers' bodies are `implement` BuildItems for Phase 4 (Track A); this step only emits the
**aligned typed surfaces**. Generate against the framework's **current** API — pull it from
Context7 (`references/core/knowledge-sources.md`), not training-cutoff memory, so the scaffolds use today's
idioms.

### 4. Install the drift-check + contract tests (the preventive payload)
Wire the same shape-diff rescue uses into CI: re-extract every layer's shapes and diff them
against the carrier; **fail the build on any disagreement**. Generate the **contract tests** from
the carrier too (`references/core/contract-testing.md`) and wire them beside the drift-check — the static
diff catches shape edits, the runtime tests catch a boundary that typechecks but violates the
contract with real data. Static + dynamic together. From now on a hand-edit that lets a layer
drift is caught the moment it lands — the project stays aligned for life, not just at generation
time. This is what makes forging *durable* rather than a one-time scaffold.

## Phase-0 gating verdict — **STRONG** (2026-07-14; FastAPI + SQLAlchemy 2 + Postgres + TS client)

Run once on the polyglot live stack (the harder carrier case — same family as rescue's VibraFlow):
a hand-authored 4-entity contract (`{name,type,nullable,enum?,constraints?}` descriptor set as a
JSON carrier; User/Project/Task/Comment exercising uuid, string+constraints, enum×2, bool, int,
datetime, json, nullables, FKs with on-delete) generated all four layers, and **each generated
layer was machine-validated**, not eyeballed:

- **DDL** (Postgres migration): PG `ENUM` types, `gen_random_uuid()` PKs, FKs with
  `ON DELETE`, indexes. (Authored to current idiom; not executed — no live Postgres in the
  experiment env.)
- **ORM** (SQLAlchemy 2.0 `Mapped`/`mapped_column`): imports clean; `Base.metadata` builds all
  4 tables.
- **API** (Pydantic-v2 DTOs + FastAPI route stubs): app assembles and `app.openapi()` —
  which forces validation of every response model — emits 9 paths / 10 schemas.
- **Client** (TS types + typed fetch stubs): `tsc --strict` passes.

**Verdict: full four-layer generation is Plan A for this stack family.** The scaffolds are
idiomatic (current-API idioms, typed end-to-end) and a developer would build on them, not throw
them away.

**Recorded frictions — why the drift-check stays mandatory even under Plan A:**
1. **Reserved-word collisions**: the contract field `metadata` collides with SQLAlchemy's
   `Base.metadata`; the generator must know per-layer reserved-name tables (attribute `metadata_`
   + column alias + DTO `validation_alias`). A naive generator ships a broken model here.
2. **Enum storage is a silent drift source**: SQLAlchemy stores enum member *names* by default —
   the DDL's PG ENUM holds *values*; `values_callable` was required. This typechecks on every
   layer and still breaks at the DB boundary — exactly the class of mismatch only the shape-diff /
   contract tests catch.
3. **Casing policy is a decision, not a derivation** (snake_case wire vs camelCase TS): must be
   elected in the interview and carried by the contract, else it is an `ambiguity`.
4. **Semantic validators are not derivable** (email stayed `str`; `EmailStr` would be generation
   inventing semantics): if wanted, the descriptor grows an optional `format` — a contract
   decision, never a generator default.

One data point, not a law — re-run per stack family before trusting generation broadly (mirror of
how rescue recorded its VibraFlow verdict in
`skills/codebase-rescue/references/contract-reconciliation.md`).

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

## Runtime

The generate-mode engine is `runtime/generate.py` (repo root; stdlib-only, tested in CI):
`Contract.load(contract.json)` → `generate_all()` emits DDL / SQLAlchemy 2 / Pydantic v2 / TS
from one descriptor set, `choose_carrier(stack)` picks the lightest carrier. As a CLI:
`python runtime/generate.py --contract contract.json --out scaffold/`. The alignment guarantee
is mechanical: `tests/test_generate.py` generates every layer and runs `runtime/shapes.py`'s
drift-check over the result — a correct generator round-trips to **zero drift**, so a future edit
that breaks alignment fails CI. This is the STRONG step-0 verdict as an executable invariant.

## TODO (implementation)
- [x] Per-stack generators from the normalized contract (live stacks done; tree-sitter template
      generalization for further stacks stays additive). → `runtime/generate.py`
- [x] The CI drift-check (rescue's shape-diff, wired to fail the build). → `runtime/shapes.py`
      at the repo root: extractors for the live stacks + carrier diff, exit 1 on drift;
      validated against this module's own step-0 artifacts (`tests/test_shapes.py`).
- [x] Contract-carrier chooser (shared-types vs OpenAPI/JSON-schema/protobuf). →
      `generate.choose_carrier(stack)`.
