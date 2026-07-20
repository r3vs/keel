# Study — Understand-Anything → what to copy into this repo

**Subject:** [Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)
(MIT; by Yuxiang Lin / Infinite Universe, originally by Lum1104) — "turn any codebase into an
interactive knowledge graph you can explore, search, and ask questions about."

**Why we studied it:** it is a mature, shipping, MIT-licensed implementation of *exactly the part
our design only sketches* — Phase-1 comprehension (build the as-is graph + a navigable visual map).
Our own `references/toolchain.md` still names **Graphify** as the primary graph backbone even though
our step-0 gating verdict rated its cross-layer value **WEAK**, and our runtime already runs
tree-sitter for extraction. Understand-Anything (UA) resolves that tension by example.

**Scope discipline (read first):** UA is **100 % as-is comprehension**. It has *no* to-be, *no*
decisions ledger, *no* interview, *no* contract-reconciliation, *no* remediation. Our center of
gravity — `gap = diff(to-be, as-is)` with `to-be` elected by a human — is precisely what UA lacks.
So everything below slots **under Phase 1 only**. The one way to misread this study is to let a
best-in-class *comprehension* engine drag our center of gravity back toward comprehension. It must
not. UA makes our as-is cheaper, incremental, and more legible; it does not change what the skill
is *for*.

---

## 0. TL;DR

**One headline recommendation** and a **shortlist**. Details in §4–§5.

> **Headline — resolve the Graphify tension by building the structural spine ourselves with
> tree-sitter (the parser we already run), modeled on UA's MIT builder.** Our step-0 verdict is that
> Graphify's *only* usable output is the structural spine (files/symbols/tables + `imports`/`calls`
> as EXTRACTED edges); its cross-layer edges are noise we already refuse to ride (`graph.py` only
> walks EXTRACTED edges). UA proves you can produce that exact spine — deterministically,
> incrementally, MIT, offline — from tree-sitter, which `runtime/treesitter_extract.py` already
> loads. Reframe the backbone from "Graphify PRIMARY" to "tree-sitter-native builder recommended;
> Graphify optional," dropping an external dependency whose main output we distrust.

| # | Copy candidate | Maps to our need | On-thesis? | Effort | Lands in |
|---|---|---|---|---|---|
| 1 | **Tree-sitter-native structural graph** (drop Graphify dependency) | Phase-1 backbone; kills a distrusted dep | ✅ resolves our own open tension | M | `phase-1-comprehension.md`, `toolchain.md`, `runtime/graph.py` exporter |
| 2 | **Signature-level fingerprints + change-classifier** (incremental) | `resume` mode + cheap re-audit; near-zero tokens on cosmetic diffs | ✅ | M | `phase-1-comprehension.md`, new `runtime/fingerprint.py` |
| 3 | **4-tier graph validate/repair** (sanitize→normalize→autoFix→drop-broken w/ referential integrity) | guardrail for LLM-authored graphs; sibling of our findings gate | ✅ | M | `phase-1-comprehension.md`, `runtime/graph.py` |
| 4 | **Docs-as-`claim`-nodes** — parse the target's own README/ADRs, diff claims vs code | direct mechanism for "found docs are stale/aspirational" → `contract_mismatch`/`internal_contradiction` pins | ✅✅ novel & on-thesis | M | `phase-1-comprehension.md`, `contract-reconciliation.md` |
| 5 | **Diff/impact overlay + "unmapped files"** signal | roadmap prioritization (P3) + change-scope check (P5) | ✅ | S | `phase-3-roadmap.md`, `phase-5-validate.md`, `map.py` |
| 6 | **Deterministic-script / LLM-semantics split, made explicit** | reproducibility + anti-hallucination discipline we already hold implicitly | ✅ | S | `phase-1-comprehension.md` |
| 7 | **`importMap` + 1:1-emission self-check + deterministic recovery** | trustworthy structural edges without LLM edge-drop/invention | ✅ | S–M | `phase-1-comprehension.md` |
| 8 | **Layered-lens visual map** (overview clusters → drill into layer → expand container) | make a big as-is map legible in one view (our `map.py` is flat) | ✅ | S–M | `map.py`, `phase-1-comprehension.md` |
| 9 | **Domain view** (Domain→Flow→Step + entry-point detector) | business-logic comprehension *before* the interview | ✅ | M | new module + `phase-1` |
| 10 | **Persona-adaptive deterministic templater** (one graph → many renderings) | exec summary / onboarding / roadmap from one ledger, no LLM | ➖ nice-to-have | S | `map.py` siblings |
| 11 | **Cross-platform gotcha: omit agent `model` frontmatter** | our adapters (opencode/pi/codex/cursor) hit the same bug | ✅ correctness | S | roster/build |

Where **we are already ahead of UA** (do not regress): per-finding **confidence** + **severity
threshold** (UA has only edge `weight`, no node confidence — its own gap for a tool that rates
findings); **field-level contract reconciliation** across DB↔ORM↔API↔frontend (UA stops at
file/symbol edges); the **decisions ledger** and the whole to-be arc.

---

## 1. What Understand-Anything is (and is not)

A Claude-Code (+ Copilot/Cursor/Codex/Gemini/…) **plugin skill** whose runtime is prose (`SKILL.md`
+ agent `.md` files) driving bundled deterministic Node/Python scripts and a compiled TypeScript
core. `/understand` runs a multi-agent pipeline that writes a single `.ua/knowledge-graph.json`;
`/understand-dashboard` opens an interactive React/React-Flow dashboard over it; secondary commands
(`-chat`, `-diff`, `-domain`, `-knowledge`, `-onboard`, `-explain`, `-figma`) are lenses over the
same graph.

- **Is:** a reproducible, incremental, offline-capable **as-is** builder; a shareable graph artifact
  (commit the JSON, teammates skip the pipeline); a legible visual explorer.
- **Is not:** any notion of *correct* / *intended*. It describes; it never prescribes. No user
  decisions, no gap, no remediation. It would happily draw a beautiful map of a mess and call the
  job done — which is the exact failure mode our skill exists to cure.

**License:** MIT — we may vendor code or lift patterns freely, with attribution. This is the
cheapest rung of our own ponytail ladder ("reuse before build").

---

## 2. Thesis check — where UA sits relative to us

UA is one box inside our Phase 1. The comparison that matters:

| Capability | Understand-Anything | This repo (rescue/greenfield) | Verdict |
|---|---|---|---|
| Build as-is structural graph | ✅ mature, tree-sitter, incremental | ◻ designed; leans on Graphify (rated WEAK) | **copy from UA** |
| Visual navigable map | ✅ React-Flow dashboard + standalone viewer | ◻ `map.py` single HTML, flat | **copy patterns** |
| Per-node/finding **confidence** | ✗ only edge `weight 0–1` | ✅ `extracted/inferred/ambiguous` + severity threshold | **we lead** |
| **to-be** (intended state) | ✗ none | ✅ elected in interview | **we lead (core)** |
| Decisions ledger / single source of truth | ✗ (graph is as-is only) | ✅ `ledger.json` + `Pin` union | **we lead (core)** |
| Field-level contract diff DB↔ORM↔API↔FE | ✗ file/symbol edges only | ✅ `shapes.py` + `contract-reconciliation` | **we lead (core)** |
| Incremental re-analysis | ✅ signature fingerprints | ◻ re-runs; `resume` mode wants this | **copy from UA** |
| Docs → structured claims | ✅ `/understand-knowledge` (`claim` nodes) | ◻ principle stated, no mechanism | **copy + bend on-thesis** |
| Change-impact / blast-radius | ✅ `diff-overlay` + risk heuristic | ✅ `graph.py` blast-radius (partial) | **copy the overlay + unmapped signal** |

**Reassuring convergence** — UA independently arrived at three invariants we treat as load-bearing,
which is strong evidence our architecture is right:

1. **Phases communicate only through on-disk artifacts.** UA's `intermediate/` directory is "the
   sole inter-phase message bus; the design explicitly forbids any phase relying on another's
   in-memory state." That is verbatim our "each phase is a separate invocation; persist between
   phases is what makes the context reset possible."
2. **One graph, many stateless lenses.** UA's dashboard/chat/onboard/diff all read one
   `knowledge-graph.json` and hold no state of their own — structurally identical to our "map,
   interview, brainstorm hold no state; they all read/write one `ledger.json`."
3. **Staleness gate.** UA refuses to trust a graph whose `gitCommitHash` ≠ HEAD — the same guard as
   our `built_at_commit == HEAD` refusal in `graph.py`.

---

## 3. The deterministic / LLM split (the transferable spine)

UA's single most transferable idea, and one we already hold *implicitly* via confidence tags but
never state as a rule: **a deterministic script owns every structural fact; the LLM owns only
semantics** (summary, tags, complexity, layer names, tour narrative). Agents are told "trust the
script; do not re-read source." The payoffs:

- **Reproducible** — the same code always yields the same nodes/edges. (Our `extracted` tier *is*
  this; we should say so explicitly in Phase 1 and forbid the LLM from re-deriving structure.)
- **Cheap** — no tokens spent re-deriving imports.
- **Low-hallucination** — the `importMap` is resolved once (per-language resolvers honoring
  `tsconfig paths`, Python `__init__`, Go module prefix, PSR-4, …), handed to each analyzer as
  facts, and each analyzer must emit import edges **1:1 with a stated self-check**
  (`edge-count == Σ imports`); a deterministic recovery pass re-adds any the LLM dropped (they lose
  ~25 % in practice). This is the same spirit as our fp-check gate: **make the machine-checkable
  thing machine-checked.**

We should adopt the *framing* even where we keep our own extractors: Phase 1 should say, in one
place, "structure is EXTRACTED by code and is not the LLM's to invent; the LLM is only ever adding
the semantic overlay, and its structural claims are verified against the extractor."

---

## 4. Headline — resolve the Graphify tension

**The problem, in our own words (TODO step 0, `contract-reconciliation.md`):** on a fresh VibraFlow
graph, Graphify produced 75 INFERRED edges (0 truly semantic) and **no field-level cross-layer
correspondence**. `graph.py` therefore uses the graph for exactly two things — `file:line` anchoring
and blast-radius over **EXTRACTED** edges — and the contract module computes field diffs itself. In
other words: **we depend on an external pip package for a "spine" we could extract ourselves, and we
throw away everything else it produces.**

**What UA shows:** that spine is cheap to build natively. `extract-structure.mjs` +
`extract-import-map.mjs` produce files/symbols/imports/calls deterministically from tree-sitter WASM
grammars (15 languages with full extractors; graceful degradation otherwise) — and we *already load
tree-sitter* in `runtime/treesitter_extract.py` for field extraction. Building the structural graph
from the same parser is additive, not a new dependency.

**Recommended reframe (design-level, reversible):**

- `toolchain.md` / `phase-1-comprehension.md`: promote a **tree-sitter-native structural builder**
  (modeled on UA, MIT) to the recommended backbone; demote **Graphify** to "optional / one source
  of a compatible `graph.json`," with the step-0 WEAK verdict cited inline. **GitNexus** stays where
  it is (optional, noncommercial).
- **Impedance note (be precise):** UA emits its own schema (`nodes/edges/layers/tour`); `graph.py`
  reads a NetworkX node-link `graph.json` (`nodes`+`links`, `file:line`, confidence tags). Adopting
  UA's builder therefore means **one small adapter** — either a NetworkX exporter on the builder's
  output, or teaching `graph.py` to read UA's shape. `graph.py`'s two jobs (anchor by `file:line`,
  reverse-reach over EXTRACTED edges) are unchanged; only the *producer* of the graph changes.
- **Do not** rip Graphify out of the runtime in this pass — `graph.py` reads whatever produces a
  compatible `graph.json`, so this is a guidance change plus a future builder, not a rewrite.

This is the crispest "copy from UA" there is: it closes a tension the repo already documented,
removes a distrusted dependency, and unifies on a parser we already ship.

---

## 5. The copy ledger (detail)

Grouped; each item repeats effort and the on-thesis check. UA source paths are under
`understand-anything-plugin/`.

### A. Phase-1 comprehension engine

- **A1 — Tree-sitter-native structural builder (M).** §4. Source: `skills/understand/*.mjs`,
  `packages/core/src/plugins/**`. Lands in `phase-1-comprehension.md`, `toolchain.md`, a future
  `runtime/graph_build.py` + NetworkX exporter.
- **A2 — Signature-level fingerprints + change-classifier (M).** `fingerprint.ts` hashes the whole
  file (NONE fast-path) *and* signatures (fn params/returns/exports, class members, imports) to tell
  **COSMETIC** from **STRUCTURAL**; `change-classifier.ts` maps counts to **SKIP / PARTIAL /
  ARCHITECTURE / FULL**. Re-audit and `resume` become near-zero-token when only formatting/internal
  logic changed. Copy two hard-won guards verbatim: *build the fingerprint baseline before writing
  `meta.json`* (else auto-update loops on FULL forever) and *LOAD-PATCH-SAVE refusing to write when a
  non-empty store loads as `{}`* (store-wipeout guard). On-thesis: ✅ (directly powers `resume`).
- **A3 — Deterministic/LLM split, stated as a rule (S).** §3.
- **A4 — `importMap` + 1:1 self-check + recovery (S–M).** §3. Even without the full builder, resolve
  internal imports once and verify the LLM's edges against them.

### B. Graph data model & guardrails

- **B1 — 4-tier validate/repair pipeline (M) — highest-leverage single file.** `packages/core/src/
  schema.ts::validateGraph`: **sanitize** (null→[], lowercase enums) → **normalize** (~90 alias
  strings → canonical, *kind-aware*) → **autoFix** (fill defaults, clamp `weight` to [0,1], each fix
  emits a `GraphIssue{level,category,message,path}`) → **validate + drop-broken** (per-item parse;
  drop invalid nodes; **drop edges whose source/target don't resolve**; filter dangling `nodeIds`
  from layers/tours; fatal only if not-an-object / no project / zero nodes). This is precisely what
  any LLM-authored graph (ours included) needs, and it is the graph-side sibling of our findings
  gate. Copy the alias tables too. On-thesis: ✅.
- **B2 — Adopt UA's node/edge vocabulary where it's richer than ours (S).** Node types are a
  discriminated union on `type` (code `file/function/class/module/concept`; infra
  `service/endpoint/table/schema/resource/config/pipeline/document`; plus domain/knowledge/design
  families). Edges carry `{source,target,type,direction,weight}` grouped into 9 categories
  (structural/behavioral/data-flow/dependencies/semantic/infrastructure/domain/knowledge/design).
  The category grouping — *not* a closed taxonomy — matches our "no closed problem taxonomy" stance
  and gives contract/data-flow/dependency reconciliation a natural filter granularity. **Keep our
  confidence tags** — UA has none at node level; that is our advantage, not something to drop.
- **B3 — `.ua/`-style persistence + `filePath` relativization (S).** Deterministic on-disk artifacts
  the phases pass through (graph/meta/fingerprints/config), and a privacy step that relativizes
  paths (inside→relative, outside→basename) so a user's home layout never lands in committed JSON.
  We already persist to disk; borrow the relativization.

### C. On-thesis feature bends (comprehension → alignment)

- **C1 — Docs-as-`claim`-nodes (M) — novel & squarely on-thesis.** UA's `/understand-knowledge`
  parses a wiki into `article/entity/claim` nodes with `builds_on/contradicts/exemplifies` edges.
  Do **not** copy the Karpathy-wiki parser (won't fire on a normal repo). **Copy the vocabulary and
  bend it:** parse the target's *own* README / `/docs` / ADRs into `claim` nodes and treat each as an
  **aspirational `to_be` assertion**, then diff claims against the as-is code. A claim the code
  contradicts is not "documentation debt" — it is a `contract_mismatch` / `internal_contradiction`
  pin whose resolution the interview decides (update the doc, or fix the code). This gives our
  load-bearing principle — "you cannot audit slop against its own docs; found docs are stale or
  aspirational" — an actual *mechanism* instead of a caveat. Also portable regardless of source: the
  merge script's **type-alias normalization, entity dedup-with-edge-remap, and dangling-edge
  removal** (see B1).
- **C2 — Diff/impact overlay + "unmapped files" (S).** `diff-analyzer.ts::buildDiffContext`: changed
  files → nodes → `contains`-children → 1-hop `affected` → affected layers → a **risk score**
  (complex node touched / >1 layer / >5 affected / unmapped files). Two uses for us: **P3 roadmap**
  prioritization (blast radius is how you sequence and risk-rate the backlog) and **P5 validation**
  (after a fix, confirm it touched only intended nodes/contracts; `unmappedFiles` = new/renamed files
  needing re-analysis). We already compute blast-radius in `graph.py`; add the **overlay sidecar**
  (`{changedNodeIds, affectedNodeIds}`) so `map.py` can highlight affected pins, and the
  unmapped-files signal. Swap UA's generic risk heuristic for pin-severity/contract weighting.
- **C3 — Domain view: Domain→Flow→Step + entry-point detector (M).** `extract-domain-context.py` is
  a framework-agnostic, cap-bounded entry-point detector (Express/Flask/FastAPI/Nest/Next/CLI/cron/
  GraphQL/gRPC…); the `domain-analyzer` turns raw entry points into a business hierarchy with
  `businessRules` and `crossDomainInteractions`. Value: the user cannot elect a *to-be* until they
  can see the *as-is* in **business** terms; `businessRules` seed `design_concern`/`incompleteness`
  pins. Steal the detector outright; fold the hierarchy into a comprehension module + the interview.
- **C4 — Explain-a-pin drill-down (S).** `explain-builder.ts`: assemble a node's graph neighborhood
  (`path:function` resolution + `contains`-children + 1-hop + owning layer) **then read the real
  source** for ground truth, against a fixed 5-point checklist. A ready-made "explain this pin's
  file/endpoint in depth" surface for investigating one finding.

### D. Visual map (our `map.py` is a deliberate single HTML file — copy patterns, not the stack)

Our decision to ship a zero-dependency single HTML file (not wrap the heavy React dashboard) stands.
Harvest patterns that survive that constraint:

- **D1 — Layered lens (S–M):** overview = one card per layer with aggregate counts and log-scaled
  inter-layer edges → click to drill into a layer → expand a container to see files. This is the
  single best fix for the "hairball" that kills flat maps. Concepts port to vanilla SVG/canvas.
- **D2 — Container derivation heuristic (S):** `utils/containers.ts` — group by folder longest-common-
  prefix; if <2 buckets or one holds >70 %, **fall back to Louvain**; dissolve single-child
  containers. ~150 lines of pure logic, no framework.
- **D3 — Type/layer coloring (S):** `--color-node-{type}` CSS-var scheme + a small `LAYER_PALETTE`
  (index `% n`) + left-color-bar node cards; inline as one `<style>`.
- **D4 — Hand-rolled SVG export (S):** `ExportMenu.tsx::buildCleanSvg` already renders nodes/edges to
  dependency-free `<svg>` — the literal seed of a self-contained map.
- **D5 — Guided-tour player + heuristic generator (M):** BFS-from-entry-point topo order → 5–15
  pedagogical steps; the generator needs no LLM.

Skip for the single-file map: the two-stage async ELK caching machinery and the whole viewer
HTTP/token/allowlist server (only relevant if we ever *serve* rather than *embed*).

### E. Packaging & ergonomics

- **E1 — Omit agent `model` frontmatter (S, correctness).** UA learned (their issue #167) that
  `model: inherit` is a Claude-Code-only keyword that opencode/others reject as a literal model id
  (`ProviderModelNotFoundError`). We ship opencode/pi/codex adapters and are exposed to the same bug
  — verify our roster/build omits `model` (or maps it per host).
- **E2 — Commit-the-graph team sharing + `--auto-update` post-commit hook (S).** Commit the graph
  JSON so teammates skip the pipeline; a PostToolUse(Bash) hook matches `git (commit|merge|rebase)`
  and incrementally patches the graph. Pairs with A2. For us: the *ledger* is already the committed
  artifact; the incremental-refresh hook is the transferable ergonomic.
- **E3 — `.understandignore` generator (S):** seed from `.gitignore`, dedupe against defaults, honor
  `!` negation, count only user-driven exclusions. Nice scoping ergonomics for large monorepos.

### F. Greenfield-forge opportunities (noted, not scoped here)

- **F1 — Figma design→code contract (L, high but conditional).** `/understand-figma` builds a token
  graph (`color/type/effect/grid` + `uses_token` edges) and screen/component structure from the
  Figma REST API. This is the most *on-mission* extension of contract-reconciliation: a **5th layer,
  design↔frontend**. A Figma token is a genuine *to-be* contract to diff against implemented React/
  Vue — missing screens, components drifting from the design system, hardcoded colors that should be
  tokens (a `contract_mismatch` pin). Caveats that keep it out of this pass: needs a Figma file +
  `FIGMA_TOKEN` + network (breaks offline), and the token-drift diff doesn't exist yet. Take it only
  if design-system alignment becomes an explicit goal.

---

## 6. Do NOT copy (discipline)

- **The center of gravity.** UA has no to-be/ledger/decisions; adopting its comprehension engine must
  not quietly turn us into "a prettier as-is map." Everything above is *under* Phase 1.
- **Node-level confidence loss.** UA has none. Keep our `extracted/inferred/ambiguous` + severity
  threshold; they are load-bearing for the interview and the FP gate.
- **The heavy dashboard stack** (React 19 + React-Flow + ELK + Zustand + Tailwind + a Node viewer
  server with token/allowlist). We already decided on a zero-dependency single HTML file; copy the
  *patterns* (§D), not the stack.
- **The Karpathy-wiki parser** literally (C1 copies the vocabulary, not the parser).
- **Design opinions as findings.** UA freely narrates; our guardrail (judgments are options, not
  defects) still governs anything we render on the map.

---

## 7. What this pass changed, and the follow-up

**Applied now (design-level, prose; CI-green):**

- `references/phase-1-comprehension.md` — reframed the Step-1 backbone to a tree-sitter-native
  builder (Graphify demoted to optional, WEAK verdict cited); stated the deterministic/LLM split as
  a rule (§3); added incremental fingerprinting for `resume`/re-audit (A2); added the graph
  validate/repair guardrail (B1); added the docs-as-`claim`-nodes mechanism (C1).
- `references/toolchain.md` — Backbones section: tree-sitter-native builder recommended, Graphify
  demoted with the step-0 citation, `web-tree-sitter` noted as the portable extraction path.
- `references/phase-3-roadmap.md` / `references/phase-5-validate.md` — the diff/impact overlay +
  unmapped-files signal (C2) as prioritization / change-scope inputs.
- `TODO.md` — a new "Adopt from Understand-Anything (MIT)" section tracking A1–A4, B1–B3, C1–C4,
  D1–D5, E1–E3, F1 with the effort ratings above, pointing back to this study.

`contract-reconciliation.md` was **left untouched** on purpose — it is the verified core engine and a
study pass has no business editing it; C1 (docs-as-claims) already lands cleanly in Phase-1 Step 3,
and F1 (design↔frontend) is greenfield future scope recorded in the TODO.

**Update (follow-on decision).** Acting on the finality question in §2 — *does this repo also want
comprehension as an end, the way UA does?* — an **`understand` mode** was added: comprehension as the
deliverable (navigable map + dependency-ordered tours + explain-a-node + a query surface), **Phase 1
only, no interview / no remediation**. It gives UA's own use case ("I just want to understand /
onboard onto this codebase, not fix it") a first-class home while staying strictly *descriptive* — it
never invents a `to_be` — so the comprehension engine serves the skill without becoming a second
product. Spec: `SKILL.md` Modes + `references/phase-1-comprehension.md` ("Comprehension as an end");
its affordances are powered by follow-ups C3–C6 + the D-series map work.

**Deliberately not applied now (implementation, needs its own change):** the tree-sitter builder
+ NetworkX exporter (A1), `runtime/fingerprint.py` (A2), the validate/repair code (B1), the
docs-as-claim extractor (C1), the diff-overlay sidecar in `map.py` (C2), and the domain module (C3).
These are code, tested, in follow-up PRs — this pass records the design and the plan.

---

## 8. Provenance & license

- Studied at commit of `main` on 2026-07-19 via a full clone.
- Understand-Anything is **MIT** (© Yuxiang Lin; Infinite Universe, Inc.). Reuse of code or verbatim
  patterns must carry the MIT notice; ideas need no permission but we attribute as a courtesy and to
  keep provenance honest — the same discipline `knowledge-sources.md` demands of any external input.
- This study is analysis, not vendored code. Any code lifted in a follow-up PR will carry attribution
  at the file that uses it.
