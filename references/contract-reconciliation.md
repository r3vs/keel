# Module: Cross-Layer Contract Reconciliation (core)

This is the module the skill lives or dies on. It turns a vague "the layers aren't aligned"
into precise, verifiable pins. It is deterministic-ish: it compares representations of the
same data entity across boundaries and reports where they disagree. Everything here anchors
to knowledge-graph node IDs where the graph provides them, else to source locations
(`file:line`) — so pins can render as cross-layer diffs on the map. (Phase-0 verdict below:
on real stacks the graph often lacks DB-schema nodes, so `file:line` anchoring is the norm and
`node_id` may be null.)

## Phase-0 gating verdict — RESOLVED (2026-07-09, VibraFlow run)

The gating experiment in `TODO.md` step 0 has been run once, on a real monorepo (VibraFlow:
~177K LOC, TS + Python, Postgres + Drizzle + React). **Verdict: WEAK cross-layer correspondence
from the graph — standalone shape extraction is Plan A, not the fallback.**

Evidence from that run's graph (`graphify-out/graph.json`, 11 079 nodes / 18 742 edges):
- Edge confidence: 18 518 EXTRACTED, **222 INFERRED, 2 AMBIGUOUS**. The Ollama semantic pass
  barely fired — only 1 `shares_data_with` and 1 `semantically_similar_to` edge in the whole
  graph.
- **0 DB-schema nodes** — Graphify did not model the Postgres schema as nodes on this stack, so
  there were no DB anchors for cross-layer edges to attach to in the first place.

Consequences, now baked into this module's posture:
1. **Compute contracts STANDALONE from source** (DDL/migration, ORM model, DTO/route, shared
   types). Do not wait on the graph's cross-layer edges — treat any that exist as weak
   corroboration only.
2. **Use the graph ONLY for** anchoring, imports/calls reachability (blast radius), and
   community structure — never for field-level correspondence.
3. **Anchor pins to `source_location` (`file:line`), accepting `node_id: null`.** Do not anchor
   to nodes the graph lacks, and never to files a stale graph still references but that no
   longer exist.
4. **A monorepo shared-types package is the strongest standalone contract when present.** On
   VibraFlow, `@vibraflow/shared` *was* the explicit contract the inferred edges failed to
   supply; DB↔shared diffing off it produced all 11 contract pins deterministically.
5. **Check route returns against the shared types, not just the FE hooks.** Where the frontend
   asserts `api.get<T>()` with no runtime validation, TS already ties the hooks to shared types
   — the real drift is raw `pg` / untyped route returns vs those types.

One data point, not a law: re-run the experiment on a stack where Graphify *does* emit
DB-schema nodes and richer semantic edges before generalizing this verdict.

## The boundaries

A data entity is represented four+ times. Extract each representation, then reconcile.

| Boundary        | Source of the representation                                             |
|-----------------|-------------------------------------------------------------------------|
| **DB schema**   | migrations / DDL, or live introspection: tables, columns, types, nullability, constraints, enums, FKs |
| **ORM / model** | model classes / structs (SQLAlchemy, Prisma, TypeORM, Django, GORM, Ecto…): what the code *believes* the schema is |
| **API contract**| route handlers, DTOs, serializers, request/response schemas, OpenAPI if present |
| **Frontend**    | fetch/query calls, TS types / interfaces, form fields, what the UI reads and sends |

Optionally also: message/event schemas, GraphQL SDL, config contracts. Same procedure.

## Procedure

### 1. Build the entity correspondence
The hard part is knowing that `users.role` (DB), `User.role` (ORM), `role` in `GET /user`
(API), and `user.role` (frontend) are the *same* field.

IMPORTANT (validated against the graph backbone): the graph gives **entity/path-level**
correspondence, NOT field-level shape correspondence. Graphify connects `frontend component
→ API handler → ORM repository → DB table` as nodes+edges, but those cross-layer edges are
its **INFERRED** tier (LLM semantic pass, unbenchmarked). The DB tables/columns and the code
entities themselves are deterministic nodes (EXTRACTED). So:

1. **Use the graph's cross-layer edges as HINTS, carrying their confidence tag.** An
   `EXTRACTED` edge (within code) is reliable; an `INFERRED`/`AMBIGUOUS` cross-layer edge is
   a candidate correspondence, not a fact — it lowers the resulting pin's `confidence`.
2. **Compute the field-level shapes yourself** from the anchored `source_location`s the
   graph gives you (the skill's own extractors read the DDL/model/DTO/fetch site and
   normalize each to `{name,type,nullable,enum?,constraints?}`). The graph tells you *which*
   entities to compare; the skill computes *whether their shapes disagree*.
3. **Name + shape heuristics** only where the graph is silent, tagged `confidence: inferred`.
4. **Never fabricate a correspondence.** If a field on one side has no counterpart, that is
   itself a finding (see `incompleteness` and orphan detection below), not a guess.

### 2. Normalize each representation to a common shape descriptor
Reduce every side to the shared descriptor `{ name, type, nullable, enum?, constraints? }` and
cross type systems via the equivalence table — both **authoritative in `core/shape-engine.md`**
(shared with `greenfield-forge`, which runs the same engine in reverse to *generate* aligned
layers instead of diffing them). When equivalence is uncertain, mark `confidence: ambiguous`
rather than asserting a mismatch; when a field has no counterpart, that absence is itself the
finding — never fabricate a correspondence.

### 3. Diff and classify
For each corresponded entity, diff the descriptors across layers and emit a pin:

- **Shape/type/enum disagreement** across layers → `contract_mismatch`. `as_is` = the
  per-layer shapes; `disagreeing_layers` = which sides deviate from the majority/candidate
  truth. Example: DB enum `{admin,user}` vs frontend check `role==='superadmin'`.
- **Two+ conflicting implementations within one layer** (e.g. two auth flows) →
  `internal_contradiction`.
- **A field exists on one side, absent on another** → depends on direction:
  - Frontend sends/reads a field the API/DB doesn't have → `contract_mismatch` (or
    `ambiguity` if it's unclear whether the field is planned).
  - DB column nothing writes to; API field nothing consumes → orphan → `incompleteness`
    (maybe a half-built feature) or `defect` (dead) — let the completeness module decide.
- **Correspondence itself uncertain** (can't tell if two things are the same entity) →
  `ambiguity`, `severity: blocker` (blocks defining the to-be until the user clarifies).

### 4. Anchor and cluster
Each pin's `anchors[]` lists one entry per involved layer with `role`
(`db_source`/`api_contract`/`frontend_consumer`/…) and `loc`. This is what lets the map
highlight all involved nodes and render the three-column contract-diff panel.

Cluster pins that share a decision: all mismatches resolvable by the same policy (e.g. "DB
is source of truth") get one `cluster_id` so the interview asks once.

## What NOT to do

- Do not report a mismatch when one side is simply unbuilt — that is `incompleteness`, and
  it renders as a neutral work item, not an error. Check the completeness module's signal.
- Do not elect the canonical layer yourself. When layers disagree, the pin carries the
  divergent shapes as candidate truths and the *user* elects the canonical one in the
  interview (or via a policy). Electing it here would be the "opinion as finding" failure.
- Do not flatten a `confidence: inferred` correspondence into a hard mismatch. Low-confidence
  correspondences produce low-confidence pins, which (per the severity threshold) may go to
  proposed-default rather than interrupt the user.

## Output

Pins of kind `contract_mismatch` / `internal_contradiction` / `ambiguity`, written to the
ledger, each anchored cross-layer and clustered. These become the primary agenda of the
Phase 2 interview, and — once the user elects truths — the primary driver of the Phase 3
roadmap (contracts align before logic is touched, which falls out of `depends_on`).

## TODO (implementation)
- [ ] Per-stack extractors for the four boundaries (start with the user's live stacks, then
      generalize via tree-sitter queries so new stacks are additive, not rewrites).
- [ ] Type-equivalence table across DB/ORM/API/TS type systems.
- [ ] Correspondence resolver: **standalone shapes first** (Phase-0 verdict), with graph edges
      as weak corroboration only and for anchoring/reachability. (Was "graph edges first" —
      flipped by the VibraFlow run.)
