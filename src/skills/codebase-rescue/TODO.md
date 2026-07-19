# codebase-rescue — Build checklist

Status: **design complete; runtime largely implemented** (SKILL.md + 16 module playbooks + ledger
spec v0.6 + drift-linter green). The gating experiment (step 0) has been **re-run on a fresh graph**
(2026-07-14): verdict **WEAK** cross-layer correspondence → standalone extraction is Plan A, now on
a current graph (`built_at_commit` == HEAD) and confirmed on the real repo (see below and
`references/contract-reconciliation.md`). Implemented and tested in CI: the shared ledger runtime
(`runtime/ledger.py`), the field-shape engine + drift-check (`runtime/shapes.py`, incl. Drizzle/
Prisma/Django/GraphQL, plus an optional **tree-sitter** generic backend
`runtime/treesitter_extract.py`), the findings + fp-check gate (`runtime/findings.py`), the
interview funnel + challenger (`runtime/interview.py`, `runtime/challenger.py`), the Phase-4 wave
scheduler (`runtime/buildloop.py`), the visual map (`runtime/map.py`), **graph anchoring +
blast-radius** (`runtime/graph.py`), the ast-grep rule pack, the eval harness, and a slop-repo
fixture. What remains is agent-orchestrated at runtime (the per-item TDD loop).

Work top-down: each block depends on the ones above it. Detail for every item lives in the
referenced playbook.

---

## 0. Gating experiment — RESOLVED on a FRESH graph (2026-07-14 re-run) → WEAK, standalone is Plan A
The 2026-07-09 run used a stale `graphify-out/` (built at commit 38330055, **37 commits behind**
HEAD e0d00d6 — the unstated-assumption challenge was correct). Now re-run on a current graph.
- [x] Pick a real slop codebase. → VibraFlow (~177K LOC monorepo: TS + Python, Postgres +
      Drizzle + React).
- [x] **Re-run with a fresh graph** — `graphify update .` re-extracted current code (45 s,
      deterministic, no LLM) → 9 335 nodes / 15 905 edges, `built_at_commit` == HEAD. Answer to the
      gating question: **WEAK** — 75 INFERRED (down from 222), **0** true semantic edges (the
      semantic pass needs an unset Gemini/Google key), and while DB-schema nodes DO exist (~204
      Drizzle table nodes — the stale verdict's "0 DB nodes" was **wrong**), they carry only
      module-structure edges, no field-level cross-layer correspondence. Standalone stays Plan A.
- [x] Re-recorded the verdict in `references/contract-reconciliation.md` (replaced the challenged
      section). Confirmed positively: `runtime/shapes.py` extracts **113 tables / 1 290 fields**
      from VibraFlow's real Drizzle schema (incl. `budgets.spent_usd`) — the standalone path works
      end-to-end on the live repo; the graph path for correspondence does not.

## 1. Core engine — the contract-reconciliation code (v0 landed in `runtime/shapes.py`)
- [x] **Per-stack extractors** for the live stacks (Postgres DDL, SQLAlchemy 2, Pydantic v2,
      TS interfaces) → normalize to `{name,type,nullable,enum?,constraints?}`; tested against
      the step-0 fixtures (clean on aligned layers, catches injected drift).
      → `runtime/shapes.py`, `tests/test_shapes.py`
- [x] Additional stacks are additive — `runtime/shapes.py` now also extracts **Drizzle**
      (TS ORM, balanced-brace table bodies), **Prisma** (schema, `String @default(uuid())`→uuid),
      **Django** models, and **GraphQL SDL**; each normalizes to the one descriptor, aligned
      fixtures diff clean against the shared contract, injected drift is caught
      (`tests/test_stacks.py`).
      → `references/contract-reconciliation.md`
- [x] **Tree-sitter = the PRIMARY extraction path (declarative, no heuristics)** —
      `runtime/treesitter_extract.py`: one **generic engine driven by declarative per-grammar DATA**
      (a `STACKS` entry = a tree-sitter query + type/​node maps — no per-stack code, no comment
      sniffing, no name matching), plus a small custom walk where a grammar's shape differs (SQL).
      `shapes.py` **defaults to `backend="auto"`** — a real grammar parses the whole language, so
      real-world **TS / GraphQL / Postgres SQL** just work with no per-repo patches (the fragility
      that made the regex parsers need a fix per codebase). Verified specs for those three, each a
      **byte-identical drop-in** with the stdlib parser on the fixtures. Not a hard dependency: it
      **degrades to the stdlib parsers** when tree-sitter is absent (stdlib-only still runs; the
      ledger/core stay stdlib-only). `tests/test_treesitter.py`; the suite is green both with
      tree-sitter and with it simulated absent. **Still open:** migrate the last two regex
      extractors (Drizzle, Prisma) onto tree-sitter — same one-spec-per-stack pattern; the Python
      `ast` extractors (SQLAlchemy/Pydantic/Django) are already real parsers and stay.
      → `references/contract-reconciliation.md`
- [x] **Type-equivalence table** across DB/ORM/API/TS type systems; `ambiguous` where uncertain
      (unresolved types downgrade to notes, never asserted mismatches; the uuid/datetime↔string
      equivalence for stringly-typed layers is applied deterministically at diff time — symmetric,
      never sniffed from a comment). → `runtime/shapes.py`
- [x] **Correspondence resolver (deterministic)** — carrier-anchored flows via `drift_check`
      (carrier→table→DTO-class→interface, the carrier declaring table→entity explicitly), **and
      carrier-less pairwise reconcile** via `shapes.reconcile_layers(...)` with **case-insensitive
      EXACT** entity matching (no pluralization guessing — that is English-specific), `missing_entity`
      /`extra_entity` when a side is absent — never fabricates. Cross-convention correspondence
      (`users` table vs `User` model) comes from the carrier, the Phase-0 verdict's strongest anchor.
      `tests/test_shapes.py::TestCarrierlessReconcile`.
- [x] **Graph-edge anchoring (deterministic)** — `runtime/graph.py`: loads graphify's NetworkX
      `graph.json`, resolves a pin anchor to a stable `node_id` **only by its `file:line`** (exact,
      or a node's declared line-range — no name matching, no plural fold, no basename/nearest
      guess), computes **blast-radius** by reverse reachability over the graph's own **EXTRACTED
      edges** (its confidence tag — never the INFERRED cross-layer edges, no editorial edge-type
      filter), enforces the `built_at_commit == HEAD` staleness gate (refuses to write on a stale
      graph — worse than none), and enriches the ledger's `anchors[]` in place so the map navigates
      + shows impact while staying self-contained. `tests/test_graph.py`. The fresh step-0 re-run
      settled the substance (DB nodes for anchoring, no field-level correspondence edges), so this
      is exactly the navigation + blast-radius enhancement it was scoped to be; the carrier stays
      the correspondence source of truth.

## 2. Ledger runtime — DONE (`runtime/ledger.py`, stdlib-only, 35 tests in CI)
- [x] Code (stack-agnostic) that materializes policies, assigns `resolution_mode`, enforces the
      severity threshold, and appends immutable `DecisionEvent`s. → `runtime/ledger.py`,
      tested by `tests/test_ledger.py` (runs in CI).
- [x] **Assumption-surfacing** — `Ledger.surface_assumption()`: pin with
      `provenance: agent_assumption`, `confidence: inferred|ambiguous` enforced, threshold applied.
- [x] **ChallengeEvent append + reopen** — `Ledger.challenge()`: immutable event, `challenged`
      substate, minimal transitive reopen via `depends_on`, neutrality enforced (no
      `DecisionEvent` writable by any non-interview source).

## 3. Interview generator + findings gate
- [x] **Interview generator** — the funnel is code in `runtime/interview.py` (`funnel()`:
      materializes the `needs_input` view, assigns `resolution_mode`, orders the asked questions by
      transitive information gain, routes the low-severity tail to `proposed_default`) + the
      ledger's `apply_policies()` (cluster → policy → exception). Shared with greenfield.
      → `references/phase-2-interview.md`
- [x] **Challenger pass** — `runtime/challenger.py` mechanizes the deterministic classes
      (`unfalsifiable` = an elected `to_be`/criterion with no testable `verify`; `ignored_fanout`
      = a high-fan-out pin silently defaulted), emitting upheld `ChallengeEvent`s that reopen via
      the ledger; the judgment classes (`inconsistent`/`unsatisfiable`/`unstated_assumption`) stay
      agent-driven through the same `ledger.challenge()` sink. Reopens, never decides.
      `tests/test_challenger.py`.
      → `references/phase-2-interview.md`, `references/phase-4-remediation.md`, `references/core/agents.md`
- [x] **SARIF adapters + fp-check** — `runtime/findings.py`: normalize SARIF
      (semgrep/gitleaks/trivy) + OSV JSON to one stream, the CONFIRM/DOWNGRADE/DROP gate with the
      five ordered checks (injected reachability + intentional-stub oracles, defaulting to keep;
      deterministic diagnostics skip the gate), root-cause clustering to one pin with N anchors,
      and a showable DROP audit trail. `tests/test_findings.py`.
      → `references/module-fp-check.md`, `references/toolchain.md`
- [x] **ast-grep rule pack** in `assets/ast-grep/` — 8 rules (py+ts: fake-auth, swallowed
      exceptions, not-implemented, trivial bodies) + `sgconfig.yml` + `ripgrep-markers.txt`,
      validated against positive/negative fixtures (18 hits / 0 false positives).

## 4. Visual-first map — DONE (`runtime/map.py`, shared with greenfield)
- [x] Clickable pins, three-column contract-diff panels (disagreeing layer flagged), linked
      interview questions with options+implications, anchors, completeness traffic-light,
      as-is/to-be toggle. Verified rendered in a browser (no console errors);
      `tests/test_map.py` guards it stays self-contained. → `runtime/map.py`
- [x] **Decided:** build a **zero-dependency single HTML file** rather than wrap CodeWiki —
      ponytail: the lightest thing that works, opens offline, safe to hand to anyone. The
      map/wiki holds no state; it projects a view over `ledger.json`.
      → `references/phase-1-comprehension.md`

## 5. Test & tuning
- [x] Build a fixture slop repo → `tests/fixtures/slop-repo/` (planted cross-layer drift + an
      intentional stub + a SQLi); `tests/test_fixture_slop_repo.py` asserts the runtime detects
      the planted problems (shape drift, the stub, the injection). More real repos can be added.
- [x] Add assertions to `evals/evals.json`. → 5 cases, each with an `assertions[]` array;
      structure validated in CI (`scripts/run_evals.py --validate`).
- [x] Eval **execution wired** — `scripts/run_evals.py --run --runner "claude -p" --fixture
      tests/fixtures/slop-repo --skill codebase-rescue` runs the cases + LLM-judges each assertion.
      Running it needs an agent runner present (no pretend mode); the fixture + command are ready.
- [x] **SkillOpt** — the `description` is hand-optimized for triggering (broad trigger phrases,
      "don't wait for the word audit"); the automated benchmark loop runs via the eval harness
      above once an agent runner is available. Fixtures + harness are in place.

## 6. Package & ship — DONE at repo level
- [x] `README.md` for humans (SKILL.md is for the model). → repo-root `README.md`.
- [x] Choose the license. → MIT (`LICENSE`); GitNexus stays excluded from commercial use (opt-in only).
- [x] Claude Code marketplace: `.claude-plugin/marketplace.json` + `plugin.json` (plus opencode,
      Codex, and AGENTS.md adapters — see `docs/packaging.md`).

## 7. Adopt from Understand-Anything (MIT) — study `docs/studies/understand-anything.md` (2026-07-19)
Understand-Anything is a shipping, MIT-licensed Phase-1 comprehension engine (tree-sitter graph +
incremental fingerprints + shareable viewer). It has **no** to-be / ledger / interview, so everything
here slots **under Phase 1** and must not pull the skill's center of gravity back to comprehension.
Full rationale + the balanced comparison (incl. where our design already leads) are in the study.

Applied now (design / prose; CI-green):
- [x] Reframe the Phase-1 backbone to a **tree-sitter-native builder**; Graphify demoted to optional
      (step-0 WEAK). → `references/phase-1-comprehension.md`, `references/toolchain.md`
- [x] State the **deterministic-facts / LLM-semantics split** as a Phase-1 rule; add `importMap` +
      1:1 edge self-check + deterministic recovery. → `references/phase-1-comprehension.md`
- [x] Add the **graph validate/repair guardrail** (drop-broken + referential integrity) and
      **incremental fingerprinting** for `resume`/re-audit. → `references/phase-1-comprehension.md`
- [x] Add **docs-as-`claim`-nodes** as a finding source (doc claim vs code → `contract_mismatch` /
      `internal_contradiction` pin). → `references/phase-1-comprehension.md`
- [x] Align Step 2 to the single-file map + **layered-lens** legibility patterns (also fixes the
      stale CodeWiki framing). → `references/phase-1-comprehension.md`
- [x] **Added the `understand` mode** — comprehension as an *end* (navigable map + dependency-ordered
      tours + explain-a-node + query surface, Phase 1 only, no interview/remediation): the
      Understand-Anything finality, kept strictly descriptive so it never becomes a second product.
      Its affordances are powered by follow-ups C3 / C4 / D below, plus a heuristic tour generator and
      a graph query surface. → `SKILL.md`, `references/phase-1-comprehension.md` ("Comprehension as an end")

Implemented (code, stdlib-only, tested — the `understand`-mode runtime + its backbone):
- [x] **A1 (Python-complete)** `runtime/graph_build.py` — deterministic structural builder emitting
      the exact node-link `graph.json` `runtime/graph.py` consumes: file/function/class/method nodes,
      `contains`/`imports`/`calls` edges, per-file `layer`, `built_at_commit`. Python via stdlib
      `ast` (imports resolved only when unambiguous — no fabrication). **Still open:** the tree-sitter
      symbol extractor for other languages (a `STACKS`-style query table; today they get file nodes).
      `tests/test_graph_build.py`.
- [x] **B1** graph validate/repair — `graph_build.validate_repair`: drop no-id / duplicate nodes,
      **drop dangling edges** (referential integrity), coerce confidence, lowercase edge types,
      return a showable `GraphIssue[]`. `tests/test_graph_build.py::TestValidateRepair`.
- [x] **C4** `runtime/explain.py` — explain-a-node drill-down (resolve id/path/path:symbol → graph
      neighborhood + read real source, fixed 5-point checklist). `tests/test_explain.py`.
- [x] **C5** `runtime/tours.py` — dependency-ordered guided tour (entry-point-first BFS, grouped by
      layer, LLM-free). `tests/test_tours.py`.
- [x] **C6** `runtime/query.py` — weighted graph query surface (name/summary/tag search → 1-hop
      expansion). `tests/test_query.py`.
- [x] **orchestrator** `runtime/understand.py` — the mode entrypoint: build → layered overview
      (languages · layers · hotspots) → tour, persisted to disk; pure as-is (no `to_be`/interview).
      `tests/test_understand.py`.
- [x] **A2** `runtime/fingerprint.py` — signature fingerprints (COSMETIC vs STRUCTURAL) + change
      classifier (SKIP / PARTIAL / ARCHITECTURE / FULL); both guards implemented (commit stamped with
      the store; `save_store` refuses to wipe a non-empty baseline). `tests/test_fingerprint.py`.
- [x] **E1** verified the roster emits **no** agent `model:` frontmatter on any host (the UA #167
      bug structurally cannot occur here) and **guarded it** with a regression test.
      `tests/test_roster_generation.py::...test_no_host_emits_a_model_frontmatter_line`.

Still open (code — each its own PR; effort S/M/L per the study):
- [ ] **A1 (tree-sitter)** per-language symbol extraction for non-Python (declarative query table
      mirroring `treesitter_extract.STACKS`), so JS/TS/Go/… get symbols, not just file nodes (M).
- [ ] **C1** docs→claim extractor + claim-vs-code diff emitting pins (M).
- [ ] **C2** diff/impact overlay sidecar (`{changedNodeIds, affectedNodeIds}`) in `runtime/map.py`
      + "unmapped files → needs re-analysis" signal for Phase 3 / Phase 5 (S).
- [ ] **C3** domain view module (Domain→Flow→Step + framework-agnostic entry-point detector) (M).
- [ ] **D1–D4** layered-lens + container heuristic + type/layer colouring + hand-rolled SVG export
      in `runtime/map.py` (S–M).
- [ ] **F1** (greenfield-forge) Figma design→frontend as a **5th contract layer** — only if
      design-system alignment becomes an explicit goal (L).

---

## Open decisions — resolved
- [x] **Wiki:** custom vs wrapper over CodeWiki → **build one zero-dependency HTML file**
      (`runtime/map.py`); reuse-before-build weighed CodeWiki but a single self-contained file
      that projects the ledger is lighter and has no runtime dependency.
- [x] **Ledger persistence:** → **plain `ledger.json` on disk** for v1 (portable, git-versionable,
      diffable). The spec already maps 1:1 onto Postgres tables if an app layer ever needs it —
      YAGNI until then.
- [x] **Brainstorm:** → **an agent in the roster** (`agents/brainstorm.md`), invoked on demand,
      not a always-on parallel process. A truly parallel second agent stays a v2 option (YAGNI).

---

## Done (design phase)
- [x] Failure-mode analysis of vibecoded codebases (validated against 2025–26 literature).
- [x] Studied ~15 adjacent projects; chose what to reuse vs build.
- [x] Decisions-ledger spec v0.3 (discriminated union, clustering, policies, flip-criteria).
- [x] SKILL.md orchestrator: 5 phases, 4 modes, guardrails.
- [x] 16 module/phase playbooks written (no stubs; drift-linter green).
- [x] Graphify chosen as backbone; external constraint validated (node IDs ✓, cross-layer as
      INFERRED hints, field-level diff computed by the skill). → **reframed 2026-07-19: tree-sitter-native
      builder now recommended, Graphify optional (see §7 + the study).**
- [x] Two-track TDD + restartable per-item remediation loop with wave checkpoints.
- [x] bootstrap.sh (toolchain) + check_consistency.py (drift-linter) + evals scaffold.
- [x] Ledger v0.6: `ChallengeEvent` (upstream oracle red-team) + `agent_assumption` provenance; the
      read-only `challenger` role wired into Phase 2 + wave checkpoints; teach-on-rejection convention.
