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

## 1. Core engine — the contract-propagation code — DONE (`runtime/generate.py`)
- [x] **Per-stack generators** from one normalized contract (the shape-engine descriptor) →
      DDL/migration (Postgres), ORM model (SQLAlchemy 2), DTO (Pydantic v2), client types (TS).
      → `runtime/generate.py`. Proven by the **round-trip test**: generate all four → the
      shape drift-check finds **zero drift** (aligned by construction), and the step-0 frictions
      (reserved-word aliases, enum `values_callable`, snake_case wire) are handled in code, not
      left to the developer. `tests/test_generate.py`. Tree-sitter template generalization for
      further stacks stays additive on the list.
- [x] **The CI drift-check** — the same shape-diff rescue uses, wired to fail the build when a
      hand-edit breaks alignment. This is the preventive payload. → `runtime/shapes.py`
      (`python runtime/shapes.py --contract contract.json --ddl … --sqlalchemy … --pydantic …
      --typescript …` exits 1 on drift); tested by `tests/test_shapes.py`.
- [x] **Contract-carrier chooser** — `generate.choose_carrier(stack)`: shared-types for a TS
      monorepo, OpenAPI/JSON-schema for polyglot, protobuf when an RPC/streaming decision is
      elected. Ponytail: the lightest carrier that suffices. `tests/test_generate.py`.

## 2. Ledger runtime — DONE (shared with rescue; one implementation)
- [x] Reuse the shared ledger runtime → `runtime/ledger.py` (repo root) implements the spec once
      for both skills, greenfield deltas included: `open_decision` + `acceptance_criterion` kinds,
      `BuildItem` (build verbs + `build_track` + `contract_carrier`), `flip_signal`/`ReopenEvent`.
      Tested by `tests/test_ledger.py` in CI.

## 3. Decision-frame + interview generator — DONE (`runtime/interview.py` + catalog asset)
- [x] **Decision-catalog authoring** — `assets/decision-catalog.json`: the 11 clusters (0–10) as
      machine-usable data (forks, options, implications, depends_on, default policies, per-type
      prune lists, information-gain order). Authoring source stays `references/decision-catalog.md`.
- [x] **Interview generator** — `runtime/interview.py`: `expand_catalog()` prunes by project type,
      skips brief-decided forks (pre-committed, never re-asked), wires `depends_on` to pin ids;
      `funnel()` compresses to the asked questions ordered by **transitive** information gain with
      the low-severity tail as `proposed_default`. `tests/test_interview.py`.
- [x] **Challenger pass** — the mechanizable classes are in `runtime/challenger.py`
      (`unfalsifiable` = an elected `to_be`/criterion with no testable `verify`; `ignored_fanout`
      = a high-fan-out pin silently defaulted), emitting `ChallengeEvent`s via the ledger. The
      judgment classes (`inconsistent`/`unsatisfiable`) stay agent-driven per the playbook.
      → `references/phase-2-interview.md`, `references/core/agents.md`
- [x] **Assumption-surfacing** — shared with rescue via `Ledger.surface_assumption()`
      (`provenance: agent_assumption`, confidence enforced, threshold applied).
      → `references/core/assumptions.md`

## 4. Visual map — DONE (shared `runtime/map.py`, as-is/to-be toggle)
- [x] The to-be design map: pins render their elected `to_be` under the **to-be** toggle
      (`open_decision`/`acceptance_criterion`), contract panels, linked interview questions,
      completeness traffic-light. As BuildItems/decisions resolve, the traffic-light converges to
      green. → `runtime/map.py`, `tests/test_map.py`.
- [x] **Decided:** **share rescue's map** with an as-is/to-be toggle (one component, not a fork) —
      ponytail: reuse before build. → `references/phase-1-frame.md`

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
- [x] **Map component:** → **share one** with an as-is/to-be toggle (`runtime/map.py`), not a fork.
- [x] **Slice mode handoff:** → **yes, share the ledger runtime**. `slice` (greenfield) and
      `resume` (rescue) both operate Phases 3–5 on a subset of a committed ledger; both read/write
      the same `runtime/ledger.py` (the interview view, funnel, and challenger are ledger
      operations, not mode-specific code). The mode only scopes *which* pins are in play.

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
