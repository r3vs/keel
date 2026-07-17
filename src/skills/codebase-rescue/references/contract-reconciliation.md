# Module: Cross-Layer Contract Reconciliation (core)

This is the module the skill lives or dies on. It turns a vague "the layers aren't aligned"
into precise, verifiable pins. It is deterministic-ish: it compares representations of the
same data entity across boundaries and reports where they disagree. Everything here anchors
to knowledge-graph node IDs where the graph provides them, else to source locations
(`file:line`) — so pins can render as cross-layer diffs on the map. (`file:line` anchoring with
`node_id: null` is always legitimate — do not block on graph coverage; the fresh Phase-0 re-run
below confirms the graph carries DB nodes for anchoring but no field-level correspondence edges.)

## Phase-0 gating verdict — RESOLVED on a FRESH graph (2026-07-14 re-run)

The 2026-07-09 verdict was challenged (its graph turned out stale) and has now been **re-run on a
freshly rebuilt graph**. Same posture (standalone-first), one piece of evidence **corrected**, and
now trustworthy because the graph is current.

**Staleness confirmed, then eliminated.** The challenged graph was built at commit `38330055`,
objectively **37 commits behind** VibraFlow's HEAD (`e0d00d6`) — the `unstated_assumption`
challenge was correct. `graphify update .` re-extracted the current code (45 s, deterministic, no
LLM) to a graph whose `built_at_commit` now equals HEAD.

**Fresh graph (9 335 nodes / 15 905 edges):**
- Edge confidence: 15 830 EXTRACTED, **75 INFERRED, 0 AMBIGUOUS** (fewer INFERRED than the stale
  222). True semantic edges (`shares_data_with` / `semantically_similar_to`) are **0** — the
  semantic pass needs a Gemini/Google API key that was never set (`cost.json` shows 0 tokens across
  all historical runs), so it never fired. Cross-layer *correspondence* edges are effectively
  absent by construction here.
- **DB-schema nodes DO exist** — ~204 nodes live in `packages/backend/src/db/schema/*`, including
  real Drizzle table consts (`budgets`, `secretScanResults`, `dataDeletionRequests`, …).
  **This corrects the stale verdict's "0 DB-schema nodes" claim, which was wrong**: on a
  Drizzle/TS stack the DB schema *is* TS code, so Graphify's AST pass models the tables as nodes.
- **But those nodes carry only module-structure edges** — `imports` / `re_exports` / `calls` — to
  the rest of the codebase, **not field-level correspondence edges**. A table node tells you where
  it lives and who imports it (anchoring + blast radius); it does **not** tell you which API field
  maps to which column. That correspondence is exactly what the graph does not encode.

**Verdict (fresh, trustworthy): WEAK cross-layer correspondence from the graph — standalone shape
extraction is Plan A.** Same conclusion as before, now on a current graph and for a sharper reason:
not "no DB nodes" but "the DB nodes exist, yet no field-level cross-layer edges connect them; and
the semantic pass that might infer such edges requires an unset API key."

**Positively confirmed on the real repo:** `scripts/runtime/shapes.py`'s standalone Drizzle extractor pulls
**113 tables / 1 290 fields** from VibraFlow's actual `db/schema/*.ts` (after being hardened for
real Drizzle: single quotes, multi-line method chains, cross-file/named enums, `decimal`) —
including `budgets.spent_usd`, the field behind the known budget-enforcement blocker. The
standalone path works end-to-end on the live target; the graph path for field correspondence does
not.

Consequences, baked into this module's posture (unchanged — the fresh run reaffirms them):
1. **Compute contracts STANDALONE from source** (DDL/migration, ORM model, DTO/route, shared
   types) via `scripts/runtime/shapes.py`. Treat any graph cross-layer edges as weak corroboration only.
2. **Use the graph ONLY for** anchoring, imports/calls reachability (blast radius), and community
   structure — never for field-level correspondence. This is exactly what `scripts/runtime/graph.py` does,
   **deterministically**: it resolves a pin anchor to a `node_id` **by `file:line` only** and walks
   **reverse reachability over the graph's own EXTRACTED edges** for blast-radius — never an
   INFERRED/semantic edge, and with no editorial edge-type filter.
3. **Anchor pins to `source_location` (`file:line`), accepting `node_id: null`.** Do not anchor to
   nodes the graph lacks, and never to files a stale graph still references. `scripts/runtime/graph.py`
   fills `node_id` (and a compact blast-radius) onto each anchor **only from an exact/containment
   `file:line` match** — no name matching, no pluralization, no nearest-line guess — leaves it null
   otherwise, and **refuses to write at all when `built_at_commit` != HEAD** (a graph 37 commits
   behind is worse than none — rebuild with `graphify update <path>` first).
4. **A monorepo shared-types package is the strongest standalone contract when present** — diff the
   layers against it (carrier-anchored `shapes.drift_check`); when absent, diff two layers directly
   (`shapes.reconcile_layers`).
5. **Check route returns against the shared types, not just the FE hooks** — the real drift is raw
   `pg` / untyped route returns vs those types.

One data point per stack, not a law: re-run per stack family — and always on a graph rebuilt for
the current code (`graphify update <path>`; confirm `built_at_commit`), the lesson the stale run
paid for.

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
cross type systems via the equivalence table — both **authoritative in `references/core/shape-engine.md`**
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

Once a truth is elected and the boundary is aligned in Phase 4, a generated **contract test**
(`references/core/contract-testing.md`) pins the reconciled boundary so it cannot silently regress — the
runtime complement to re-diffing shapes in Phase 5.

## TODO (implementation)
- [x] Per-stack extractors for the four boundaries — the live stacks in `scripts/runtime/shapes.py`
      (DDL/SQLAlchemy/Pydantic/TS + Drizzle/Prisma/Django/GraphQL), **generalized** via
      `scripts/runtime/treesitter_extract.py`: one generic engine driven by declarative per-grammar **data**
      (a query + type maps — no per-stack code, no heuristics), so a new stack is a data entry, not
      a rewrite. Optional backend, degrades to the stdlib parsers.
- [x] Type-equivalence table across DB/ORM/API/TS type systems — in `scripts/runtime/shapes.py`
      (`_ann_to_canonical`, the `_*_TYPE_MAP`s, and `diff_shapes`' equivalence/honesty rules).
- [x] Correspondence resolver: **standalone shapes first** — implemented in `scripts/runtime/shapes.py`
      (`drift_check` carrier-anchored, `reconcile_layers` carrier-less), with graph edges as
      corroboration/anchoring only. The fresh Phase-0 re-run (above) settled the graph's weight:
      DB nodes for anchoring, no field-level correspondence edges.
- [x] Graph-edge *anchoring* of pins — `scripts/runtime/graph.py` attaches `node_id` + blast-radius **only
      from an exact/containment `file:line` match** (staleness-gated, EXTRACTED edges only), leaving
      `node_id: null` legitimate. It does no correspondence itself; the carrier (`drift_check`)
      stays the correspondence source of truth. This is navigation + impact, exactly the scope the
      Phase-0 verdict leaves the graph.
