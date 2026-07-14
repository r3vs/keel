# codebase-rescue — Build checklist

Status: **design complete; runtime spine started** (SKILL.md + 16 module playbooks + ledger
spec v0.6 + drift-linter green). The gating experiment (step 0) was run once on a real monorepo
but its graph was stale — the verdict is **challenged** and the re-run is pending (see below and
`references/contract-reconciliation.md`). Done since:
the shared ledger runtime (`runtime/ledger.py`, tested in CI), the ast-grep rule pack
(`assets/ast-grep/`, fixture-validated), and the eval harness (`scripts/run_evals.py`). What
remains is mostly the per-stack extractors, the SARIF/fp-check gate, and the map artifact.

Work top-down: each block depends on the ones above it. Detail for every item lives in the
referenced playbook.

---

## 0. Gating experiment — CHALLENGED (2026-07-14): the 2026-07-09 run used a STALE graph → re-run
The VibraFlow run was made right after this repo's creation, against a `graphify-out/` **not
rebuilt for VibraFlow's current code** — an unstated assumption (graph currency) now upheld as a
challenge. Its WEAK verdict is unreliable evidence about Graphify; the standalone-extraction
posture survives only as a safe default (it never depended on the graph, and is now implemented
in `runtime/shapes.py`).
- [x] Pick a real slop codebase. → VibraFlow (~177K LOC monorepo: TS + Python, Postgres +
      Drizzle + React) — still the right fixture.
- [ ] **Re-run with a fresh graph**: rebuild Graphify output on VibraFlow's *current* code
      (delete/regenerate `graphify-out/`), then re-answer the one question: **are the graph's
      cross-layer correspondences usable for computing contract diffs, or too INFERRED/noisy?**
- [ ] Re-record the verdict in `references/contract-reconciliation.md` (replace the challenged
      section); flip the correspondence-resolver posture in §1 if the fresh graph earns it.
- Original (stale-graph) record, kept for audit: 222 INFERRED of 18 742 edges, 2 semantic,
  0 DB-schema nodes → verdict WEAK, standalone promoted to Plan A.

## 1. Core engine — the contract-reconciliation code (v0 landed in `runtime/shapes.py`)
- [x] **Per-stack extractors** for the live stacks (Postgres DDL, SQLAlchemy 2, Pydantic v2,
      TS interfaces) → normalize to `{name,type,nullable,enum?,constraints?}`; tested against
      the step-0 fixtures (clean on aligned layers, catches injected drift).
      → `runtime/shapes.py`, `tests/test_shapes.py`
- [x] Additional stacks are additive — `runtime/shapes.py` now also extracts **Drizzle**
      (TS ORM, balanced-brace table bodies), **Prisma** (schema, `String @default(uuid())`→uuid),
      **Django** models, and **GraphQL SDL**; each normalizes to the one descriptor, aligned
      fixtures diff clean against the shared contract, injected drift is caught
      (`tests/test_stacks.py`). Full **tree-sitter** query generalization (vs the current
      regex/line parsers) stays the next step for arbitrary stacks.
      → `references/contract-reconciliation.md`
- [x] **Type-equivalence table** across DB/ORM/API/TS type systems; `ambiguous` where uncertain
      (unresolved types downgrade to notes, never asserted mismatches; client uuid/datetime →
      string projections honored). → `runtime/shapes.py`
- [ ] **Correspondence resolver** — name+shape heuristics work for carrier-anchored flows
      (`drift_check` maps carrier→table→DTO-class→interface); graph-edge anchoring and
      carrier-less layer-pair matching still open. Never fabricate.

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

## 5. Test & tuning (the deferred phase, now due)
- [ ] Build fixtures: 2–3 real slop repos as test cases (any messy multi-layer codebase you have
      can serve as one — it is only a test target, never a dependency).
- [x] Add assertions to `evals/evals.json`. → done — 5 cases, each with an `assertions[]` array;
      what's missing is the runtime harness that executes them (see below).
- [ ] Execute the evals via `scripts/run_evals.py` against the fixtures (LLM-judge over the
      assertions; structural validation runs in CI).
- [ ] Run the skill on the fixtures, review outputs, iterate (skill-creator loop).
- [ ] **SkillOpt** — optimize `SKILL.md` against the benchmark with validation gates; optimize the
      description for triggering.

## 6. Package & ship — DONE at repo level
- [x] `README.md` for humans (SKILL.md is for the model). → repo-root `README.md`.
- [x] Choose the license. → MIT (`LICENSE`); GitNexus stays excluded from commercial use (opt-in only).
- [x] Claude Code marketplace: `.claude-plugin/marketplace.json` + `plugin.json` (plus opencode,
      Codex, and AGENTS.md adapters — see `docs/packaging.md`).

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
      INFERRED hints, field-level diff computed by the skill).
- [x] Two-track TDD + restartable per-item remediation loop with wave checkpoints.
- [x] bootstrap.sh (toolchain) + check_consistency.py (drift-linter) + evals scaffold.
- [x] Ledger v0.6: `ChallengeEvent` (upstream oracle red-team) + `agent_assumption` provenance; the
      read-only `challenger` role wired into Phase 2 + wave checkpoints; teach-on-rejection convention.
