# codebase-rescue — Build checklist

Status: **design complete & internally coherent** (SKILL.md + 16 module playbooks + ledger
spec v0.3 + drift-linter green). The gating experiment (step 0) has now been run once on a real
monorepo — verdict recorded below and in `references/contract-reconciliation.md`. What remains is
mostly real code.

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

## 1. Core engine — the contract-reconciliation code (currently prose TODOs)
- [ ] **Per-stack extractors** (DDL/migration, ORM model, API DTO/route, frontend call/type) →
      normalize each to `{name,type,nullable,enum?,constraints?}`. Start with live stacks
      (FastAPI/Django + React + Postgres); generalize via tree-sitter queries so new stacks are
      additive. → `references/contract-reconciliation.md`
- [ ] **Type-equivalence table** across DB/ORM/API/TS type systems; `ambiguous` where uncertain.
- [ ] **Correspondence resolver** — graph edges first, name+shape heuristics second, never fabricate.

## 2. Ledger runtime — the glue between phases
- [ ] Code (stack-agnostic; no dependency on any specific app's infrastructure) that materializes
      policies, assigns `resolution_mode`, enforces the severity threshold, and appends immutable
      `DecisionEvent`s. → `core/decisions-ledger-spec.md`, `core/ledger.md`

## 3. Interview generator + findings gate
- [ ] **Interview generator** — materialize `Question`s from `needs_input` pins; run the funnel
      (cluster → policy → exception → proposed-default), ordered by information gain.
      → `references/phase-2-interview.md`
- [ ] **SARIF adapters + fp-check** — run semgrep/gitleaks/osv/trivy/lizard/jscpd, normalize to one
      stream, implement the CONFIRM/DOWNGRADE/DROP gate with graph reachability.
      → `references/module-fp-check.md`, `references/toolchain.md`
- [ ] **ast-grep rule pack** in `assets/` — the YAML rules the placeholder-stub and completeness
      playbooks reference but that don't exist yet.

## 4. React artifact — the visual-first map (uses the frontend-design skill)
- [ ] Clickable pins, three-column contract-diff panels, linked interview questions, brainstorm
      button, completeness traffic-light.
- [ ] **Decide first (open):** build from scratch, or wrap CodeWiki output and overlay pins?
      (ponytail applies — reuse before build.) → `references/phase-1-comprehension.md`

## 5. Test & tuning (the deferred phase, now due)
- [ ] Build fixtures: 2–3 real slop repos as test cases (any messy multi-layer codebase you have
      can serve as one — it is only a test target, never a dependency).
- [ ] Add assertions to `evals/evals.json` (currently prompts only).
- [ ] Run the skill on the fixtures, review outputs, iterate (skill-creator loop).
- [ ] **SkillOpt** — optimize `SKILL.md` against the benchmark with validation gates; optimize the
      description for triggering.

## 6. Package & ship
- [ ] `README.md` for humans (SKILL.md is for the model).
- [ ] Choose the license (MIT is clean; Graphify is MIT — GitNexus stays excluded from commercial use).
- [ ] If shipping as a Claude Code marketplace: `marketplace.json` + `plugin.json`.

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
