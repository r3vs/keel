# greenfield-forge — Build checklist

Status: **design complete; runtime spine started** — twin of `codebase-rescue`, sharing the
`core/` spine (ledger, funnel, brainstorm, shape-engine, contract-testing, feedback-loop).
SKILL.md + 10 playbooks + the shared core; the drift-linter covers both skills and is green.
Step 0 is **done** (verdict STRONG, below) and the shared ledger runtime exists
(`runtime/ledger.py`, tested in CI). What remains is mostly the per-stack generators and the map.

Work top-down: each block depends on the ones above it. Detail for every item lives in the
referenced playbook.

---

## 0. Gating experiment — DONE (2026-07-14) → verdict: **STRONG**, full generation is Plan A
The riskiest assumption in greenfield is the mirror of rescue's: rescue bet that the graph's
cross-layer edges were usable (they weren't — extractors standalone won). Greenfield bets that
**one authored contract can generate aligned, idiomatic scaffolds** across a real stack.
- [x] Pick a target stack. → FastAPI + SQLAlchemy 2 + Postgres + React/TS client (the polyglot
      case — harder carrier problem, same family as rescue's VibraFlow).
- [x] Author a small contract by hand. → 4 entities (User/Project/Task/Comment) as a JSON
      descriptor-set carrier, exercising the full equivalence table (uuid, enum, json, datetime,
      nullables, FKs + on-delete).
- [x] Generate the four layer scaffolds and judge. → **good enough to build on** — and
      machine-validated, not eyeballed: ORM imports + builds all tables, `app.openapi()` forces
      DTO validation (9 paths / 10 schemas), `tsc --strict` passes on the client.
- [x] Record the verdict in `references/contract-propagation.md`.
      → done — see the "Phase-0 gating verdict" section: **STRONG** (Plan A), with four recorded
        frictions (reserved-word collisions, enum name-vs-value storage, casing policy, semantic
        validators) that keep the CI drift-check mandatory even under full generation.

## 1. Core engine — the contract-propagation code
- [ ] **Per-stack generators** from one normalized contract (`references/core/shape-engine.md` descriptor) →
      DDL/migration, ORM model, DTO/route, client types. Start with live stacks; generalize via
      tree-sitter templates so new stacks are additive. → `references/contract-propagation.md`
- [x] **The CI drift-check** — the same shape-diff rescue uses, wired to fail the build when a
      hand-edit breaks alignment. This is the preventive payload. → `runtime/shapes.py`
      (`python runtime/shapes.py --contract contract.json --ddl … --sqlalchemy … --pydantic …
      --typescript …` exits 1 on drift); tested by `tests/test_shapes.py`.
- [ ] **Contract-carrier chooser** — shared-types package for a TS monorepo; OpenAPI/JSON-schema/
      protobuf for polyglot. Ponytail: the lightest carrier that suffices.

## 2. Ledger runtime — DONE (shared with rescue; one implementation)
- [x] Reuse the shared ledger runtime → `runtime/ledger.py` (repo root) implements the spec once
      for both skills, greenfield deltas included: `open_decision` + `acceptance_criterion` kinds,
      `BuildItem` (build verbs + `build_track` + `contract_carrier`), `flip_signal`/`ReopenEvent`.
      Tested by `tests/test_ledger.py` in CI.

## 3. Decision-frame + interview generator
- [ ] **Decision-catalog authoring** — turn `references/decision-catalog.md` into a machine-usable
      catalog (forks, options, implications, depends_on, default policies) that the frame module
      expands and prunes against the brief.
- [ ] **Interview generator** — reuse the shared funnel (`references/core/interview-funnel.md`); materialize
      Question objects from `open_decision` pins, ordered by information gain.
      → `references/phase-2-interview.md`
- [ ] **Challenger pass** (shared with rescue; read-only) — after the interview commits and at each
      wave checkpoint, refute each elected `acceptance_criterion`/`to_be`/`Policy` (unfalsifiable /
      inconsistent / unsatisfiable / unstated_assumption / ignored_fanout) *before* Phase 3 turns it
      into the contract; emit a `ChallengeEvent`, reopen on a sustained challenge. Reopens, never
      decides. → `references/phase-2-interview.md`, `references/phase-4-build.md`, `references/core/agents.md`
- [ ] **Assumption-surfacing** — when a brief gap forces an assumption, materialize it as a pin with
      `provenance: agent_assumption` (never a silent given). Shared discipline with rescue.
      → `references/core/assumptions.md`

## 4. React artifact — the to-be design map (uses the frontend-design skill)
- [ ] Ghost/planned nodes that flip solid as BuildItems resolve; contract panels; linked
      interview questions; brainstorm button; completeness traffic-light converging to green.
- [ ] **Decide first (open):** build from scratch, or share rescue's map component and toggle
      as-is/to-be rendering? (ponytail — reuse before build.) → `references/phase-1-frame.md`

## 5. Build-loop harness
- [ ] Restartable per-item loop (fresh invocation per BuildItem), Track-A-primary two-track TDD,
      ladder logging, two-stage review, wave checkpoints. Much of this mirrors rescue's Phase-4
      harness — share what is generic. → `references/phase-4-build.md`

## 6. Test & tuning
- [ ] Build fixtures: 2–3 real briefs (a CRUD SaaS, a CLI tool, an API service) as test cases.
- [x] Add assertions to `evals/evals.json`. → done — 6 cases, each with an `assertions[]` array;
      what's missing is the runtime harness that executes them (see below).
- [ ] Execute the evals via `scripts/run_evals.py` against the fixtures (LLM-judge over the
      assertions; structural validation runs in CI).
- [ ] Run the skill on the fixtures, review outputs, iterate (skill-creator loop).
- [ ] **SkillOpt** — optimize `SKILL.md` against the benchmark; optimize the description for
      triggering ("new project", "from scratch", "greenfield", "design before I build").

## 7. Package & ship — DONE at repo level
- [x] `README.md` section for humans (SKILL.md is for the model). → repo-root `README.md`.
- [x] Same license as rescue. → MIT (`LICENSE`).
- [x] Shared `core/` bundling decision. → **resolved: Model B** — `scripts/sync_core.py` vendors
      `core/*.md` into each skill's `references/core/` (CI `--check` keeps the copies identical),
      so every skill ships self-contained.

---

## Open decisions (resolve as you reach them)
- [x] **Contract generation depth:** set by step 0 → **all four layers** (Plan A) for the
      FastAPI/SQLAlchemy/Postgres/TS family; re-run step 0 before assuming it for a new family.
- [ ] **Map component:** fork rescue's, or share one with an as-is/to-be toggle.
- [ ] **Slice mode handoff:** does `slice` mode share code with rescue's `resume` mode? (both
      operate Phases 3–5 on a subset of a committed ledger.)

---

## Done (design phase)
- [x] Reframed rescue's `gap = diff(to-be, as-is)` forward: as-is starts empty, gap = build
      backlog converging to zero.
- [x] Chose maximal reuse of the rescue machine; extracted the shared `core/` (ledger, funnel,
      brainstorm, shape-engine) so neither skill duplicates the spine.
- [x] Ledger v0.4–v0.5: `open_decision` + `acceptance_criterion` kinds, `BuildItem` + `ReopenEvent`,
      observable `flip_criteria`.
- [x] Ledger v0.6 (shared): `ChallengeEvent` (upstream oracle red-team) + `agent_assumption`
      provenance; the read-only `challenger` wired into Phase 2 + wave checkpoints — the mirror of
      the downstream feedback loop, catching an unsound oracle before it becomes the contract.
- [x] SKILL.md orchestrator: 7 phases, 5 modes (forge/spec/slice/decide/evolve), preventive guardrails.
- [x] 10 playbooks (decision-catalog, contract-propagation, threat-model, phases 1–7); drift-linter green.
- [x] Contract-propagation posture: author once, generate aligned, install the drift-check + contract tests.
- [x] Closed the lifecycle loop: acceptance criteria (roots) → … → release + operate (codebase slice)
      → the Evolve feedback arc (`flip_criteria` → reopen), reusing the existing machine.
