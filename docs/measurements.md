# Measurements — what the runtime finds on real public codebases

This repository asserts, in several places, that its comprehension and contract tooling finds real
drift in real code. Until this file it published **no numbers at all**, on any repository, ever.
That is the same shape as every other defect the gates here exist to catch — a claim with no
carrier — sitting on the package's central promise. This file is the carrier.

## How to read the numbers, and the one rule that governs them

**These numbers are provenance-stamped and deliberately OUTSIDE `scripts/check_stated_facts.py`'s
`SCOPE`.** That gate's rule is *"the number is computed here, never kept here"* — every fact it
guards names a function one call away that recomputes it. Nothing on this page is recomputable that
way: each number is the output of running the runtime against a **specific commit of somebody
else's repository**, over a network, on a machine with a particular parser installed. A gate cannot
recompute that in CI, and a gate that pretends to would be checking a cached answer against itself.
So the honesty mechanism here is different and is stated per section: **repo + commit + date +
the exact command**, and nothing else on this page may be restated elsewhere in the repo as a
present-tense fact. If a number here matters enough to appear in `README.md`, it goes there as a
**pointer to this file**, never as a bare figure.

Two rules were followed while producing it, and both cost something:

- **Nothing is filtered.** Every finding the runtime emitted is counted, including the classes that
  turn out to be the runtime's own false positives. A tool's error rate is a measurement *of the
  tool*; deleting it from the tool's own report is the single edit that makes the report worthless.
  The largest number below is a false-positive class, and it is the first one reported.
- **A null result is a result.** The second repository was chosen expecting drift and produced
  **zero findings**, because the extractor could not read its files. That is written up at the same
  length as the run that worked, with the cause located to the function and the line.

**Method — the environment, stated because wall times are meaningless without it.** Linux
container, CPython 3.11.15, `tree-sitter` 0.26.0 + `tree-sitter-language-pack` 1.12.5 installed (so
the primary extraction backend was live, not the stdlib fallback). Keel at commit
`1e85249fe8d219ca6a2eba2b9fc11c7dfad23dc5`. Measured **2026-08-13**. Each figure is **one run, not a
benchmark**: no repetitions, no warm cache control, no statistics. Treat wall times as an order of
magnitude, and the finding counts as exact — the latter are deterministic, which is the whole point
of the EXTRACTED tier.

Everything below is reproducible with `scripts/measure_public.py`, which exists so this page can be
re-derived instead of believed. It imports the runtime directly — `graph_build.build_graph`,
`understand.overview`, `tours.build_tour`, `shapes.reconcile_layers` — i.e. the same functions the
MCP tools `understand_repo` and `reconcile_layers` call.

---

## Repo 1 — `keystonejs/keystone` (MIT)

Commit `af1ba93c39218e32e1ae66269e94021f99dccc8b`, shallow clone, 2026-08-13.

**Why this repo.** It is the hardest possible case for a drift finder, and that is the point.
Keystone **generates** its Prisma schema *and* its GraphQL SDL from one authored `schema.ts`, and it
checks both into the repo beside each other in 61 example applications. Two layers, one source, no
human keeping them in step. If contract-reconciliation is mostly noise, this is where the noise
shows up naked, because there is almost nothing real for it to find. It is the control, not the
demo.

### Comprehension (`understand` mode)

```
python scripts/measure_public.py --repo <keystone> --label keystonejs/keystone --comprehension
```

| | |
|---|---|
| files graphed | 1,072 |
| symbols | 2,175 |
| edges | 3,822 |
| languages | typescript ×982 · graphql ×70 · javascript ×19 · sql ×1 |
| `build_graph` | **26.5 s** |
| `overview` | 0.01 s |
| `build_tour` | 0.01 s |

The shape of that split is the finding: the graph build is **99.9%** of the cost and the two things
an operator actually reads are free. Whatever `understand` mode is, it is a parse budget with a
report attached — which is an argument for caching `graph.json` (the staleness gate in `graph.py`
already assumes you will) and no argument at all for trimming the overview.

Top hotspots by in-degree: `index.ts` (99 dependents), `util.tsx` (57), `utils.ts` (52). Detected
entry points were the Admin-UI page modules and `packages/fields-document/src/index.ts`. The tour
came out at 13 steps.

### Cross-layer reconciliation (Prisma ↔ GraphQL, 61 pairs)

```
python scripts/measure_public.py --repo <keystone> --label keystonejs/keystone \
    --pair-dirs 'examples/*' --a prisma=schema.prisma --b graphql=schema.graphql
```

61 example applications carried both files. Extracted: **120 Prisma models / 450 fields** against
**1,381 GraphQL types / 6,621 fields**. Total wall time for all 61 diffs: **0.33 s** — reconciliation
is free; the parse is the cost, and here the parse is a `.prisma` and a `.graphql` file rather than
a repository.

**1,770 findings across 61 pairs** (29.0 per pair), which sounds like a catastrophe and is not.
The distribution is what matters:

| kind | count | share | what it actually is |
|---|---:|---:|---|
| `extra_entity` | 1,263 | 71.4% | **almost entirely structural.** 43 distinct type names × 61 apps. 123 are the operation roots (`Query`, `Mutation`); 1,098 are generated input/filter/admin-meta types (`*WhereInput`, `*OrderByInput`, `Keystone*Meta`). A GraphQL SDL contains these **by construction** and no database has a counterpart. 1,221 of 1,263 (96.7%) fall in those two buckets. |
| `nullability_mismatch` | 194 | 11.0% | **one class, one direction, 194 of 194**: `prisma nullable=False vs graphql nullable=True`. This is Keystone's access-control convention — an output field may resolve to `null` when read access is denied — so the DB column is `NOT NULL` and the API type is nullable on purpose. |
| `type_mismatch` | 130 | 7.3% | 117 (90%) are `string→uuid` (113) and `int→uuid` (4): a Prisma `String @id`/`Int @id` against a GraphQL `ID!`. The remaining 13 are `string→enum`, which are real. |
| `extra_field` | 100 | 5.6% | the relation object and the virtual counters that exist only in the API (`author`, `tagsCount`). |
| `missing_field` | 59 | 3.3% | the foreign-key scalar and the exploded file/image columns that exist only in the DB (`banner_id`, `banner_filesize`, …). |
| `unresolved` | 22 | 1.2% | the engine refusing to assert: one side's type did not resolve, reported as a note with `confidence: ambiguous` rather than as a mismatch. This is honesty rule 1 firing 22 times. |
| `missing_entity` | **2** | 0.1% | a Prisma model with no GraphQL type at all. |

### The two findings that were real, and they were both true positives

Out of 1,770, exactly two said *a table exists in the database and is not in the API*:

- `examples/empty-lists/schema.prisma` — model **`Tag`** has no GraphQL type.
- `examples/omit/schema.prisma` — model **`Nice`** has no GraphQL type.

Both are correct, and checking them at the source is what makes this a measurement rather than an
anecdote: `examples/omit/schema.ts:40-42` carries the comment *"this list is completely omitted ->
it won't be in the public GraphQL schema"* above `omit: true`, and `examples/empty-lists/schema.ts:50-53`
declares `Tag: list({ … omit: true })`. So the tool found the only two places in 61 applications
where a persisted entity is deliberately withheld from the API — and found nothing else of that
class, in a corpus where nothing else of that class exists.

That is the honest headline, and it is not "1,770 problems found". It is: **on two layers generated
from one source, the carrier-less diff produced 2 semantic findings, both true, both intentional,
and 1,532 findings — 86.6% — attributable to exactly three systematic conventions it does not yet
encode** (1,221 structural GraphQL-only types + 194 output-nullability + 117 `ID`↔scalar). Of the
238 that remain, 159 are the FK-scalar/relation-object split counted twice, 42 are the `extra_entity`
remainder, 22 are the engine declining to assert, 13 are real `enum` disagreements, and 2 are the
`missing_entity` findings above.

### Four findings about *the tool*, which are worth more than the ones about the repo

Each of these is a false-positive class this run measured on Keel itself, with the site named:

1. **`_STRINGLY_LAYERS` does not include `graphql`** (`src/runtime/shapes.py:40`). The equivalence
   table already projects `string ⟷ uuid/datetime` across a JS/TS boundary, on the stated ground
   that the client has no native uuid type. GraphQL's `ID` is the same situation and is not listed,
   which is 117 of the 130 `type_mismatch` findings — 90% of that class, from one missing tuple
   entry. **Not fixed here**: touching the equivalence table is a change to the shape engine's
   semantics and belongs to a change that owns `shapes.py`, not to the measurement that found it.
2. **A GraphQL SDL's operation roots and generated input types have no DB counterpart by
   construction**, and `reconcile_layers` has no notion of that, so they arrive as 1,098 + 123
   `extra_entity` findings. Symmetric diffing is right (honesty rule 2 — neither side is truth);
   what is missing is a way to say *this side has a structural tier the other cannot have*.
3. **Output nullability is a policy, not a shape.** 194 findings in one direction is not 194 facts;
   it is one fact about an access-control convention, restated per field.
4. **The FK-scalar/relation-object split** (`banner_id` vs `banner`) produces a `missing_field` and
   an `extra_field` for the same relation — one disagreement counted twice, in two kinds.

None of these makes the tool wrong; every finding above is defensible under the rules
`core/shape-engine.md` sets. They make it **loud**, and loudness on a generated pair is exactly what
a measurement is for. The operator-facing consequence is concrete: on a Prisma↔GraphQL pair the
signal lives in `missing_entity`, `unresolved` and the non-`ID` `type_mismatch`es — **37 of 1,770,
2.1%** — and the other 97.9% needs clustering, or an equivalence-table entry, before a human sees
it. Rescue's fp-check gate and clustering are aimed at exactly this, and this is the first number
this repo has ever had for how much work they are being asked to do.

---

## Repo 2 — `Netflix/dispatch` (Apache-2.0) — a null result

Commit `dd2837e82a0bf5565b1b4b4b91ea30b7262d4061`, shallow clone, 2026-08-13.

**Why this repo, and what was expected.** It is a large production Python service whose SQLAlchemy
models and Pydantic DTOs are **hand-written and independently maintained**, frequently in the same
file (`src/dispatch/incident/models.py` holds `Incident` beside `IncidentBase`, `IncidentCreate`,
`IncidentRead`, `IncidentUpdate`). That is the drift surface rescue's contract-reconciliation is
named for, and this run was expected to be the one that produced real mismatches. Stating the
expectation matters, because the result was zero and presenting a miss as a designed control would
be the padding this page refuses.

### Comprehension (`understand` mode) — this half worked

| | |
|---|---|
| files graphed | 879 |
| symbols | 5,360 |
| edges | 8,616 |
| languages | python ×717 · javascript ×137 · typescript ×23 · sql ×2 |
| `build_graph` | **3.05 s** |
| `overview` + `build_tour` | 0.07 s |

Worth putting beside Keystone: **879 files in 3.05 s against 1,072 files in 26.5 s** — **3.5 ms vs
24.7 ms per file, 7.1×** for the TypeScript-heavy tree. Python goes through the stdlib `ast`;
TypeScript goes through tree-sitter, and that gap is where `understand` mode's budget lives. Top
hotspots were `dispatch/database/core.py` (142 dependents) and two `models.py` (113, 89) — which is
the graph correctly pointing at the layer the next section then failed to read.

### Cross-layer reconciliation — 0 entities, 0 fields, 0 findings

```
python scripts/measure_public.py --repo <dispatch> --label Netflix/dispatch \
    --a sqlalchemy=src/dispatch/incident/models.py --b pydantic=src/dispatch/incident/models.py
```

```
entities: {"sqlalchemy": 0, "pydantic": 0}
findings: 0
```

Extended across the whole service: **65 `models.py` files**, from which the SQLAlchemy extractor
recovered **0 entities from 0 files** and the Pydantic extractor **13 entities from 2 files**.

**An empty diff over two empty extractions is the failure mode most easily mistaken for a clean
bill of health**, which is why `measure_public.py` reports both sides' entity counts whatever the
finding count is. The cause is not mysterious and is not a bug — it is three undeclared
preconditions in the extractors, each locatable:

1. **`extract_sqlalchemy` requires an explicit `__tablename__`** (`src/runtime/shapes.py:196-201`;
   a class without one is `continue`d). Dispatch derives table names on its declarative base:
   **0 occurrences of `__tablename__`** across those 65 files.
2. **`extract_sqlalchemy` reads only annotated assignments** (`shapes.py:204`) — `ast.AnnAssign`,
   i.e. the SQLAlchemy 2.0 typed-ORM style `id: Mapped[int] = mapped_column(...)`. Dispatch is 1.x
   style: **653 occurrences of `= Column(`, 0 of `mapped_column(`**. Every one is a plain
   `ast.Assign` and is skipped.
3. **`extract_pydantic` requires a base whose name literally contains `BaseModel`**
   (`src/runtime/shapes.py:262`). Dispatch's DTOs inherit a project-local `DispatchBase`:
   **131 classes inherit `DispatchBase`, 4 inherit `BaseModel` directly.** The 13 entities recovered
   are those 4 and their same-file descendants.

So the honest statement of this repo's result is: **the shape engine's Python stacks read the
modern, explicitly-typed dialect, and a large real-world codebase in the older idiom is invisible to
them — silently, reporting zero rather than reporting that it could not read anything.** The silence
is the more serious half. `reconcile_layers` returning `[]` means "these two layers agree" and
"I parsed neither" with the same value, and the only reason this page can tell them apart is that
`measure_public.py` prints the entity counts alongside.

Three consequences, all deliberately left as findings rather than fixed under a measurement commit:
the 1.x `Column()` idiom and inherited `__tablename__` are a real extractor gap; the `BaseModel`
base check should follow an inheritance chain or accept a declared base; and **`reconcile_layers`
should distinguish "no findings" from "no input"** — arguably by refusing, the way `_treesitter_only`
refuses rather than returning `{}`.

---

## The behavioral eval harness — what one case actually costs

Not a comprehension measurement, but produced by the same session and subject to the same rule.
`scripts/run_evals.py --execute` was run against `using-the-ledger` case 1 with the built
`keel-core` plugin loaded (`--plugin-dir`), Claude Code CLI 2.x, `--permission-mode acceptEdits`,
fixture `tests/fixtures/slop-repo`. **Three executions of the same case, 2026-08-13:**

| run | wall | turns | cost | called a `ledger_*` MCP tool? | machine-checked verdict |
|---|---:|---:|---:|---|---|
| 1 | 77.8 s | 15 | $0.390 | yes (`ledger_surface_assumption`) | FAIL (harness bug — see below) |
| 2 | 75.2 s | 12 | $0.394 | yes (`ledger_add_pin`) | **PASS** |
| 3 | 38.9 s | 8 | — | **no** | FAIL |

A fourth execution, `greenfield-forge` case 2 (no declared fixture, so an empty directory — which
for greenfield is the correct as-is, not a fallback): **26.5 s, 1 turn, $0.071, zero tool calls**,
and the machine check `≥4 pins with kind='open_decision'` FAILED against an empty ledger. The
agent answered the prompt in prose without invoking anything. On n=1 that is an observation and not
a verdict — it is exactly as consistent with "the prompt reads as a question" as with "the skill
did not fire" — and disentangling the two needs the repetitions this page does not have. It is
recorded because a harness whose first greenfield run does nothing is the kind of result that
quietly does not get written down.

Two things this measured, both of which changed the code in this commit:

- **A behavioral eval is not deterministic.** Three runs of one prompt produced three different tool
  sequences and two different verdicts. A single red `--execute` is evidence to look at, not a
  regression to revert, and the CI job is advisory partly for that reason.
- **Run 1's FAIL was the harness, not the skill.** The check looked for `mcp__keel__ledger_*`; the
  host had actually named the tool `mcp__plugin_keel-core_keel__ledger_surface_assumption`, because
  a plugin loaded via `--plugin-dir` has its MCP servers namespaced (`system/init` lists them as
  `plugin:keel-core:keel`). A constant remembered instead of verified produced a clean, confident,
  wrong FAIL — on the first run, on the check that mattered. It is now a regex covering both
  namespacings, with `tests/test_run_evals.py` holding it shut.

**A residual, named rather than left to be discovered:** no observed run left a `ledger.json` on
disk, so the `pin(...)`/`log_entry(...)` predicates — the ledger-reading half of the check
registry — have been exercised against synthetic ledgers in `tests/test_run_evals.py` and **not yet
against an artifact a live agent wrote**. They are unproven end-to-end, and that is the first thing
to look at the next time a credentialed runner is available.

---

## What was not measured

Stated so the gaps are visible rather than implied by silence:

- **Only 2 repositories, 1 stack pair each.** Prisma↔GraphQL and SQLAlchemy↔Pydantic. Six of the
  engine's stacks (`ddl`, `drizzle`, `django`, `typescript`, and the four tree-sitter-only backend
  stacks) have no public-repo number here at all.
- **A third candidate was dropped and is worth recording**: `hoppscotch/hoppscotch` (MIT) pairs a
  hand-written `prisma/schema.prisma` against NestJS `*.model.ts` API types. `extract_typescript`
  returned `{}` for those files — it reads `export interface` and type aliases, and a decorated
  `@ObjectType() export class` is not either. A fourth extractor gap, found the same way as the
  three above.
- **No before/after.** Nothing here shows that using the tooling improved an outcome; it shows what
  the tooling reports. That is a different and much more expensive experiment.
- **No repetition, no other machine.** Every wall time is n=1 on one container.

---

# Postscript, 2026-08-13 — the five gaps closed, and the same two repos re-run

Everything above stands as written: it is the record of what the engine did on the day it was
measured, and nothing in it has been edited to look better in hindsight. This section is what
happened when the five findings *about the tool* were fixed and the identical commands were run
again — including the two places where the diagnosis above turns out to have been **wrong**, which
is the part that would have been quietly dropped if the fix and the measurement had been written by
two different hands.

**Method, restated because the rule demands it per section.** Same container, same interpreter
(CPython 3.11.15), same backend (`tree-sitter` 0.26.0 + `tree-sitter-language-pack` 1.12.5, so the
primary extraction path was live). Same two repositories at the **same commits** as above —
`keystonejs/keystone` `af1ba93c39218e32e1ae66269e94021f99dccc8b`, `Netflix/dispatch`
`dd2837e82a0bf5565b1b4b4b91ea30b7262d4061`, both re-fetched as shallow clones and verified by
`git rev-parse`. Keel at `a09e657` **plus the changes in the commit that carries this postscript**
(the runtime is not the same runtime, which is the entire point; every other variable is held).
Measured **2026-08-13**. Still one run each, still no statistics.

## What changed in the engine, in the order the section above listed the gaps

1. **`reconcile_layers` refuses a diff over nothing** (`shapes.EmptyExtraction`). A side that
   extracted zero entities raises, naming which side, its path, and the preconditions its extractor
   needed met — `[]` no longer means both "these layers agree" and "I parsed neither".
   `propose_correspondence` refuses on the same ground, and `drift_check` refuses a carrier that
   declares no entities.
2. **The SQLAlchemy 1.x idiom is read**: a plain `x = Column(Integer, ...)` beside the 2.0
   `Mapped`/`mapped_column` form, with the ORM's own nullability default, foreign keys, sizes and
   enums. A class with columns and **no `__tablename__`** is keyed by its class name, with
   `entity_meta` recording that the key was derived — never by inventing the table name, which is
   the pluralization guess this engine refuses everywhere else. Declarative mixin columns are
   merged, because SQLAlchemy's semantics say they are the table's columns.
3. **Pydantic follows the base chain** across the file plus a bounded number of static import hops,
   so a project-local `DispatchBase(BaseModel)` descendant counts. Nothing is imported; a chain that
   leaves the batch stays unresolved rather than being accepted for looking like a base.
4. **The equivalence table gained GraphQL** — and split in two while doing it (see the correction
   below).
5. **The two noise classes are classified, not filtered**: `structural_tier` on the GraphQL spec's
   root operation types, `relation_pair`/`relation_role` on the FK-scalar/relation-object split.
   Every finding keeps its kind and still appears, so every raw count above remains derivable.

## Correction 1 — finding 1 above named the wrong site, and the fix is not the one it proposed

The section *"Four findings about the tool"* says `_STRINGLY_LAYERS` is missing `graphql`, and calls
that one missing tuple entry the cause of 117 findings. Adding the entry with the `ID` rule
disabled and re-running all 61 pairs produces **1,770 findings and 130 `type_mismatch`es — the
original run, kind for kind and count for count**. (That counterfactual was executed, not reasoned: same commits, the rule
switched off in-process.) The reason is visible the moment the finding's own detail string is
read rather than its summary: every one of the 117 is `prisma=string vs graphql=uuid` (113) or
`prisma=int vs graphql=uuid` (4). The projection is **directional** — it excuses a *stringly* layer
carrying `string` where the other side has `uuid`/`datetime` — and here the GraphQL side is the one
holding `uuid`, because both extraction backends canonicalize `ID` to `uuid`. The rule that was
actually needed is about `ID` itself: it is opaque by specification (serialized as a String,
accepting an Int on input), so an SDL cannot say what the store holds, and against `string`/`int`/
`uuid` it must not assert. Against `bool`/`enum`/`json`/`datetime` it still does.

The tuple entry went in anyway, for the half that *is* true (an SDL has no native `uuid` or
`datetime` either) — and doing so surfaced a trap the old shape hid: **one tuple was granting two
different equivalences.** GraphQL has `Int` and `Float` and can get that distinction wrong, so
joining `_STRINGLY_LAYERS` would have silently handed it the JS `number` equivalence as well. The
list is now two, `_STRINGLY_LAYERS` and `_ONE_NUMBER_LAYERS`, and `src/core/shape-engine.md` states
each projection with the type-system fact it rests on.

## Correction 2 — the 1,098 are not what finding 2 called them

Finding 2 attributes 1,098 `extra_entity` findings to *"generated input/filter/admin-meta types
(`*WhereInput`, `*OrderByInput`, `Keystone*Meta`)"*. Counting the distinct entity names in the run
says otherwise: **no `*WhereInput` or `*OrderByInput` name appears in any finding, on any of the 61
pairs.** Both extraction backends read GraphQL *object* type definitions only — an `input` block is
a different production in the grammar and never enters the diff. The 1,263 `extra_entity` findings
are 43 distinct names, and they decompose exactly:

| group | distinct names | findings | what it is |
|---|---:|---:|---|
| operation roots | 3 | 123 | `Query` ×61, `Mutation` ×61, `Subscription` ×1 — the spec's own root types |
| `Keystone*` admin-UI meta | 18 | 1,098 | one vendor's introspection tier, present in every app |
| per-app output types | 22 | 42 | auth payloads, document-field outputs, virtual outputs |

Only the first group is classified. The GraphQL specification names those three types; nothing in
the specification, or in any file this engine reads, says `KeystoneAdminUIFieldMeta` is structural.
Encoding one vendor's prefix as a rule is the guess this repo forbids its own linters, so **1,098 of
the 1,263 stay unclassified and are recorded here as the residual** — the conservative half. Closing
it needs a design decision the doctrine has not made: a way for the human to *declare* a structural
tier (a prefix, a namespace, a list) so the engine reads it rather than infers it. That is the same
shape as `reconcile_layers(correspondence=...)` — the human elects, the engine then treats it as
fact — and it is left as an open decision rather than implemented in a measurement commit.

## Repo 1 re-run — `keystonejs/keystone`, 61 pairs, identical command

```
python scripts/measure_public.py --repo <keystone> --label keystonejs/keystone \
    --pair-dirs 'examples/*' --a prisma=schema.prisma --b graphql=schema.graphql
```

Extraction is unchanged on both sides — **120 Prisma models / 450 fields** against **1,381 GraphQL
types / 6,621 fields**, the same figures as above, which is the control that says nothing else moved.

| kind | before | after | Δ |
|---|---:|---:|---:|
| `extra_entity` | 1,263 | 1,263 | — |
| `nullability_mismatch` | 194 | 194 | — |
| `type_mismatch` | 130 | **13** | **−117 (−90.0%)** |
| `extra_field` | 100 | 100 | — |
| `missing_field` | 59 | 59 | — |
| `unresolved` | 22 | 22 | — |
| `missing_entity` | 2 | 2 | — |
| **total** | **1,770** | **1,653** | −117 (−6.6%) |

The entire delta is one class and it is fully attributable: 113 `string→uuid` + 4 `int→uuid`, all of
them a Prisma `String @id`/`Int @id` under a GraphQL `ID!`. The 13 survivors are the
`prisma=string vs graphql=enum` findings the section above already called real, and they are
untouched — the rule was written to leave them alone and did.

**Classification, on the same run:** 123 findings now carry `structural_tier: operation_root` and 74
carry a `relation_pair` — 197 of 1,653 (11.9%) that a clustering pass can fold without reading a
detail string. The 74 are 37 disagreements counted twice (`authorId`/`author` ×14 pairs,
`assignedToId`/`assignedTo` ×9, `banner_id`/`banner` ×2, and 12 others), which is a **smaller and
better-founded** number than the 159 the section above assigned to that class: 159 was the whole of
`missing_field` + `extra_field`, and the virtual counters (`postsCount`, `tagsCount`) are not
relation pairs. The unpaired remainder includes the exploded file columns (`banner_filesize`,
`banner_width`, …), which pair with the same `banner` object by convention and are deliberately not
folded — only the `_id`/`Id` suffix is matched, because `banner_url` would be a real column and a
prefix rule cannot tell them apart.

**The signal share, recomputed:** the operator-facing figure above was *"the signal lives in
`missing_entity`, `unresolved` and the non-`ID` `type_mismatch`es — 37 of 1,770, 2.1%"*. Those same
37 findings now sit in 1,653, i.e. **2.2%**. The tool got 90% quieter in one class and the
signal-to-noise ratio barely moved, because the noise that remains is the 1,263 structural
`extra_entity` findings and the 194 nullability-policy findings — the two classes this commit did
**not** close. That is the honest headline of the re-run, and it is not the flattering one.

## Repo 2 re-run — `Netflix/dispatch`, the null result resolved

### The exact command the null was recorded under

```
python scripts/measure_public.py --repo <dispatch> --label Netflix/dispatch \
    --a sqlalchemy=src/dispatch/incident/models.py --b pydantic=src/dispatch/incident/models.py
```

| | before | after |
|---|---:|---:|
| `sqlalchemy` entities / fields | 0 / 0 | **1 / 32** |
| `pydantic` entities / fields | 0 / 0 | **12 / 141** |
| findings | 0 | 13 |

The one ORM entity is `Incident`, keyed by its class name with `entity_key_source:
{"sqlalchemy": "class_name"}` on every finding it appears in, and it carries all 32 columns
including `created_at`/`updated_at` inherited from `TimeStampMixin` one import hop away. All 13
findings are entity-level (1 `missing_entity`, 12 `extra_entity`): `Incident` and `IncidentRead` do
not match by name, and the engine refuses to guess past that, exactly as designed.

### Extended across the service — 65 `models.py` files

```
python scripts/measure_public.py --repo <dispatch> --label Netflix/dispatch \
    --pair-dirs 'src/dispatch/**' --a sqlalchemy=models.py --b pydantic=models.py
```

The **before** column here is measured, not carried over: the same command was run against the
pre-change extractor (`git stash` on `shapes.py`, nothing else moved), because the original section
recorded entity counts for these 65 files without running this command, which did not have its
`--pair-dirs` shape then.

| | before | after |
|---|---:|---:|
| SQLAlchemy entities / fields / files | 0 / 0 / 0 | **79 / 819 / 62** |
| Pydantic entities / fields / files | 13 / 67 / 2 | **421 / 2,965 / 65** |
| pairs diffed | 65 | 62 |
| pairs **refused** | 0 | **3** |
| findings | 13 | 482 |

**63 of those 65 pairs previously reported `0 findings` over `0` entities on both sides** — that is
the whole of gap 1 in one line, on real input, and no output of that run said anything else. The
13 findings it did report all come from the two files whose DTOs happened to inherit `BaseModel`
directly.

**The refusal fired on real input on its first outing**, and on the case it was written for:
`src/dispatch/ai/models.py`, `src/dispatch/plugins/dispatch_slack/models.py` and
`src/dispatch/search/models.py` hold Pydantic DTOs and no ORM model at all, so the SQLAlchemy side
reads empty. The output now names the layer, the path, and what the extractor expected to see,
instead of contributing a silent zero to a total.

The 482 findings are all entity-level, for the reason the section above predicted and this run
confirms with a number: the two layers share no naming convention (`Incident` vs `IncidentRead`),
and the best field-overlap candidate for that pair scores **0.34** — below the engine's own 0.5
proposal floor, so the default `--propose` yields nothing. That is a true statement about the
repository, not a failure: the overlap is low precisely *because* the ORM keeps `commander_id`,
`incident_priority_id`, … where the DTO keeps `commander`, `incident_priority`, … — the FK-scalar
split, in the one place where it costs correspondence rather than just noise.

### With the correspondence elected — a stated condition, not a result

```
python scripts/measure_public.py --repo <dispatch> --label Netflix/dispatch \
    --pair-dirs 'src/dispatch/**' --propose --min-overlap 0.3 \
    --a sqlalchemy=models.py --b pydantic=models.py
```

Two conditions are stated because both weaken the claim: the proposal floor was **moved from 0.5 to
0.3** (a new `--min-overlap` flag on the measurement script, which is why the JSON records it), and
the proposals were **elected by the script rather than by a human**, which `core/shape-engine.md`
says is the human's move. Under those conditions, 70 pairings across 61 file-pairs, and the first
field-level reading this engine has ever produced on this repository:

| kind | count | what it is |
|---|---:|---|
| `extra_entity` | 333 | DTO variants (`*Create`, `*Update`, `*Pagination`) with no table — structural, unclassified |
| `missing_field` | 243 | 63 of them tagged `relation_pair`; most of the rest are `created_at`/`updated_at`/`search_vector` |
| `unresolved` | 130 | the engine declining to assert — a nested DTO or a `TSVectorType` on one side |
| `extra_field` | 118 | 63 tagged `relation_pair`; also `project_id`, which the ORM declares as a `@declared_attr` method |
| `nullability_mismatch` | 30 | 22 in one direction (ORM nullable, DTO required), 8 in the other |
| `missing_entity` | 9 | |
| `type_mismatch` | **1** | |
| **total** | **864** | 126 tagged `relation_pair`, 531 carrying `entity_key_source` |

**The one `type_mismatch`, checked at the source** — the same discipline the two Keystone findings
got: `src/dispatch/data/source/models.py:69` declares `cost = Column(Integer)` and
`src/dispatch/data/source/models.py:140` declares `cost: float | None`. An integer column read and
written through a float DTO, in one file, seventy lines apart. That is a true positive of exactly the
class this engine is named for, on a large production service, and this page had none until now.

The 30 nullability findings are the other candidate class — 22 of them are an ORM column with no
`nullable=False` against a DTO field declared required, which is the drift the section above
*expected* to find here and could not, because nothing was parsed. They are not individually
verified and are not claimed as true positives; they are recorded as the largest unexamined group.

## New residuals this commit created or left, named rather than discovered later

- **Declarative mixins extract as entities.** `TimeStampMixin`, `ContactMixin` and friends are
  classes with columns and no table name, which is the exact shape of a mapped class whose base
  supplies the name — statically indistinguishable. They appear as entities with
  `entity_key_source: class_name`, and one of them (`EvergreenMixin` ↔ `EvergreenBase`) was elected
  as a correspondence in the run above.
- **A `@declared_attr` column is invisible.** `ProjectMixin.project_id` is a method returning a
  `Column`; the column exists only after the function runs, and this extractor does not run it. It
  surfaces as a DTO-side `extra_field`.
- **`Incident` is not `incident`.** The entity key is the class name, so a diff against a DDL layer
  that uses the real table name will report both sides missing. `propose_correspondence` is the
  path, and this is the strongest argument yet for a carrier.
- **The nullability-policy class (194 on keystone) is untouched.** Finding 3 above — *output
  nullability is a policy, not a shape* — is neither fixed nor classified here, because "an API may
  return null when access is denied" is a convention a project declares, not a fact any file states.
  It is the largest remaining single-direction class on that run.
- **A GraphQL root renamed through `schema { query: MyQuery }` is not classified.** The tier check
  uses the specification's default type names; a schema that renames its roots gets no tag. Reading
  the `schema` block would need the SDL text at diff time, which `reconcile_layers` does not have.
- **Comprehension was re-run and reproduced its counts, not its wall times.** keystone: 1,072 files
  / 2,175 symbols / 3,822 edges, identical to the first run, in **47.0 s** against 26.5 s.
  dispatch: 879 / 5,360 / 8,616, identical, in **2.69 s** against 3.05 s. The deterministic half is
  deterministic; the timings are n=1 on a shared container and the first run's *"treat wall times as
  an order of magnitude"* was, if anything, understated.
