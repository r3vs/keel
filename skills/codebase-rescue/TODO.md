# codebase-rescue — Build checklist

Status: **design complete; runtime spine started** (SKILL.md + 16 module playbooks + ledger
spec v0.6 + drift-linter green). The gating experiment (step 0) has been run once on a real
monorepo — verdict recorded below and in `references/contract-reconciliation.md`. Done since:
the shared ledger runtime (`runtime/ledger.py`, tested in CI), the ast-grep rule pack
(`assets/ast-grep/`, fixture-validated), and the eval harness (`scripts/run_evals.py`). What
remains is mostly the per-stack extractors, the SARIF/fp-check gate, and the map artifact.

Work top-down: each block depends on the ones above it. Detail for every item lives in the
referenced playbook.

---

## 0. Gating experiment — DONE (2026-07-09, VibraFlow run) → verdict: WEAK, standalone is Plan A
- [x] Pick a real slop codebase (ideally your own, where backend/frontend/DB diverged).
      → VibraFlow (~177K LOC monorepo: TS + Python, Postgres + Drizzle + React).
- [x] Run `scripts/bootstrap.sh`; run Graphify on it.
- [x] Answer the one question that decides everything: **are Graphify's cross-layer
      correspondences usable for computing contract diffs, or too INFERRED/noisy?**
      → **WEAK** — 222 INFERRED of 18 742 edges (only 2 semantic), and **0 DB-schema nodes**.
        Extractors work standalone; the graph is used only for anchoring + reachability.
        **The fallback is now Plan A.**
- [x] Record the verdict in `references/contract-reconciliation.md`.
      → done — see the "Phase-0 gating verdict" section there (standalone-first posture,
        `file:line` anchoring, and the shared-types-package-as-contract finding).

## 1. Core engine — the contract-reconciliation code (v0 landed in `runtime/shapes.py`)
- [x] **Per-stack extractors** for the live stacks (Postgres DDL, SQLAlchemy 2, Pydantic v2,
      TS interfaces) → normalize to `{name,type,nullable,enum?,constraints?}`; tested against
      the step-0 fixtures (clean on aligned layers, catches injected drift).
      → `runtime/shapes.py`, `tests/test_shapes.py`
- [ ] Generalize extractors via tree-sitter queries so new stacks (Django, Drizzle, GraphQL…)
      are additive. → `references/contract-reconciliation.md`
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
- [ ] **Interview generator** — materialize `Question`s from `needs_input` pins; run the funnel
      (cluster → policy → exception → proposed-default), ordered by information gain.
      → `references/phase-2-interview.md`
- [ ] **Challenger pass** (read-only oracle red-team) — after the interview commits and at each
      wave checkpoint, refute each elected `to_be`/`acceptance_criterion` (unfalsifiable /
      inconsistent / unsatisfiable / unstated_assumption / ignored_fanout), emit a `ChallengeEvent`,
      reopen on a sustained challenge. Reopens, never decides.
      → `references/phase-2-interview.md`, `references/phase-4-remediation.md`, `references/core/agents.md`
- [ ] **SARIF adapters + fp-check** — run semgrep/gitleaks/osv/trivy/lizard/jscpd, normalize to one
      stream, implement the CONFIRM/DOWNGRADE/DROP gate with graph reachability.
      → `references/module-fp-check.md`, `references/toolchain.md`
- [x] **ast-grep rule pack** in `assets/ast-grep/` — 8 rules (py+ts: fake-auth, swallowed
      exceptions, not-implemented, trivial bodies) + `sgconfig.yml` + `ripgrep-markers.txt`,
      validated against positive/negative fixtures (18 hits / 0 false positives).

## 4. React artifact — the visual-first map (uses the frontend-design skill)
- [ ] Clickable pins, three-column contract-diff panels, linked interview questions, brainstorm
      button, completeness traffic-light.
- [ ] **Decide first (open):** build from scratch, or wrap CodeWiki output and overlay pins?
      (ponytail applies — reuse before build.) → `references/phase-1-comprehension.md`

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

## Open decisions (resolve as you reach them)
- [ ] **Wiki:** custom React vs wrapper over CodeWiki (reuse vs build).
- [ ] **Ledger persistence:** plain `ledger.json` on disk only, or Postgres-backed for an app layer?
- [ ] **Brainstorm:** a mode in v1, or a truly parallel second agent? (marked v2 — YAGNI on yourself)

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
