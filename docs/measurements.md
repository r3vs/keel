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
