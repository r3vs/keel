# Changelog

All notable changes to this project are documented here. The design is complete and the runtime
spine has started; versions track design + packaging + runtime together.

## [0.1.0] — unreleased

### Added
- **Runtime** — the executable layer both skills bind to (all stdlib-only, tested in CI;
  **~150 tests** across `tests/`):
  - `runtime/ledger.py` — the shared decisions-ledger runtime (spec v0.6): kind-discriminated pin
    validation, append-only Decision/Reopen/Challenge events, enforced brainstorm/challenger/
    feedback **neutrality**, the severity threshold (blocker/high never silently defaulted), policy
    cascade, `agent_assumption` surfacing, minimal transitive reopen on both arcs, RemediationItem/
    BuildItem verbs, an information-gain-ordered interview view, a read-only CLI.
  - `runtime/shapes.py` — the field-shape engine (`core/shape-engine.md`): extractors for
    **Postgres DDL, SQLAlchemy 2, Pydantic v2, TypeScript, Drizzle, Prisma, Django, GraphQL**
    (new stacks are additive), the cross-type-system diff with both honesty rules (unresolved →
    `ambiguous` note; absence is the finding), and the **CI drift-check CLI** (exit 1 on drift) —
    rescue's contract-reconciliation core and greenfield's guardrail.
  - `runtime/generate.py` — greenfield's **contract generators**: one descriptor → DDL / SQLAlchemy
    / Pydantic / TS, aligned by construction. Proven by a **round-trip test** (generate → drift-check
    == zero drift), turning the step-0 STRONG verdict into an executable invariant; `choose_carrier`
    picks shared-types / OpenAPI / protobuf.
  - `runtime/findings.py` — the mandatory **false-positive gate** (`module-fp-check.md`): normalize
    SARIF + OSV to one stream, the CONFIRM/DOWNGRADE/DROP gate (five ordered checks, injected
    reachability + stub oracles defaulting to keep, deterministic diagnostics skip the gate),
    root-cause clustering to one pin with N anchors, a showable DROP audit trail.
  - `runtime/interview.py` + `skills/greenfield-forge/assets/decision-catalog.json` — the
    **decision-frame + funnel**: the 11-cluster catalog as machine-usable data; `expand_catalog`
    prunes by project type and skips brief-decided forks; `funnel` compresses to the asked questions
    ordered by transitive information gain with the tail as `proposed_default`.
  - `runtime/challenger.py` — the deterministic slice of the v0.6 oracle red-team (`unfalsifiable`,
    `ignored_fanout`), emitting upheld `ChallengeEvent`s that reopen via the ledger; judgment classes
    stay agent-driven. Neutrality tested (never writes a DecisionEvent).
  - `runtime/buildloop.py` — the shared **Phase-4 wave scheduler**: levels the BuildItem/pin DAG
    topologically (cycle-detecting), yields ready pins, gates each wave checkpoint; restart-safe
    because the ledger is the state.
  - `runtime/map.py` — the **visual map** as one self-contained HTML file (no build step, no
    external fetch): clickable pins, three-column contract-diff, linked interview questions,
    completeness traffic-light, as-is/to-be toggle; shared by both skills.
  - `scripts/run_evals.py` — eval harness: `--validate` (CI structural gate) and `--run` (behavioral
    execution against a real agent runner + fixture, LLM-judge per assertion; no pretend mode).
  - `skills/codebase-rescue/assets/ast-grep/` — the placeholder/stub rule pack: 8 python+typescript
    rules + `sgconfig.yml` + ripgrep markers, fixture-validated (18 findings, 0 false positives).
  - Fixtures: `tests/fixtures/slop-repo/` (a misaligned mini-repo whose planted drift/stub/SQLi the
    runtime detects) and `tests/fixtures/briefs/` (crud-saas, cli-tool, api-service).
- **Greenfield step-0 gating experiment run** (2026-07-14): verdict **STRONG** — one 4-entity
  contract carrier generated all four layers (DDL, SQLAlchemy 2 ORM, Pydantic-v2/FastAPI DTOs +
  routes, TS client), each machine-validated; full generation is Plan A for that stack family,
  with four recorded frictions keeping the CI drift-check mandatory
  (`skills/greenfield-forge/references/contract-propagation.md`).
- **Activation contract**: the SessionStart hook upgraded from a nudge to a mandatory-workflow
  bootstrap (entry rule + 8-skill inventory + the three non-negotiable disciplines).
- **Cursor install steps** (README + `docs/packaging.md`) and a README note on the
  repo-vs-package naming split (`codebase-rescue` repo, `codebase-alignment` package).
- **Two sibling skills on a shared core**: `codebase-rescue` (curative) and `greenfield-forge`
  (preventive), unified by `gap = diff(to-be, as-is)` and one append-only decisions ledger.
- **Full lifecycle loop** for greenfield (7 phases): frame (acceptance criteria + threat model) →
  interview → contract & roadmap → build → validate → release → operate & evolve, closing back via
  observable `flip_criteria` + `ReopenEvent` (ledger v0.5).
- **Shared core doctrines**: decisions-ledger spec, interview funnel, brainstorm, field-shape
  engine, contract-testing, feedback-loop, static-analysis, knowledge-sources, and the agent roster.
- **Agent-agnostic packaging**: Agent-Skills-spec `skills/<name>/`, root `AGENTS.md`, a Claude Code
  plugin (`.claude-plugin/`, `agents/`, `hooks/`, `commands/`) and an opencode adapter
  (`opencode.json` + `opencode-skills` + `.opencode/command/` + `scripts/install-opencode.sh`).
- **Agent roster** (`core/agents.md`): researcher · brainstorm · executor · reviewer · challenger ·
  measurer, under serialized-writing / parallel-reading.
- **Three-gap harness** (the definitive-harness pass): the package now closes three gaps with one
  anti-divergence machine, not one.
  - *Oracle gap* — a new read-only **`challenger`** role + `ChallengeEvent` (ledger **v0.6**) that
    red-teams an elected oracle **upstream** (unfalsifiable / inconsistent / unsatisfiable / unstated
    assumption / ignored fan-out) and reopens the pin before code rests on it — the feedback loop's
    upstream twin. Both **reopen, never decide**.
  - *Silent-assumption gap* — `core/assumptions.md` doctrine + `provenance: agent_assumption`: a
    forced assumption is materialized as a vetoable, challengeable pin, never encoded silently.
  - *Operator gap* — a composable **`learning-layer`** skill: senior-grade output *while the user
    learns*, via one-mode (default-on, opt-out) micro-retrieval, teach-from-the-delta ranked to 1–2
    items, teach-the-class, and a **learner-model** gradebook (the operator-gap twin of the ledger)
    that measures mastery, fades scaffolds on evidence, and detects cargo-cult.
  - *Teach-on-rejection* — a blocking gate (reviewer / challenger / feedback loop) now names the
    class and the recognition cue, not a bare verdict — raising the operator, not just the code.
  - *Prefer-the-checkable-formulation* — a selection heuristic in `core/static-analysis.md`: author
    the spec so the strongest static signal applies, not only run it in-loop.
- **Engineering hygiene**: drift-linter + pointer verifier, CI (`.github/workflows/ci.yml`), a
  version-pinning mechanism in `bootstrap.sh`, MIT `LICENSE`, `CONTRIBUTING.md`.

- **Complete-package layer** (composed, not cloned): six composable skills — `using-the-ledger`,
  `grounded-research`, `static-first-analysis`, `project-memory`, `learning-layer`, `writing-skills`
  (meta); a
  **memory** subsystem (ledger + `MEMORY.md` + memory MCP); **MCP** servers wired across platforms
  (`context7`, `deepwiki`, `memory`; `github` opt-in) via `.mcp.json`, `opencode.json`, and
  `.codex/config.toml`; **Codex** + any AGENTS.md-aware agent supported; and `superpowers` referenced
  in the marketplace for the generic engineering skills instead of reinventing them.

### Changed
- **Self-contained skills (Model B)**: the shared `core/` is now a single **authoring source**,
  vendored into each skill under `references/core/` by `scripts/sync_core.py` (following the
  `core→core` dependency closure). No skill points at `core/` directly, so every skill directory
  ships complete on any platform. CI gained `sync_core.py --check` (keeps each copy identical to its
  source), and `check_consistency.py` now errors on a bare `` `core/x.md` `` pointer under `skills/`.
- **Model B slimmed** (after review feedback that the vendoring surface was confusing): see-also
  cross-links inside `core/*.md` demoted to plain text so the dependency closure only follows
  load-bearing pointers — vendored copies drop **65 → 39** and each helper skill now carries only
  the doc(s) that are its actual subject; every vendored copy is stamped with a
  `GENERATED FILE — do not edit` banner by `sync_core.py`; `check_consistency.py` gained
  **command parity** (`commands/` ↔ `.opencode/command/`); and `docs/packaging.md` now answers
  "why not write the text directly in each skill?" explicitly.

### Notes
- Greenfield's step-0 verdict is recorded (STRONG → full four-layer generation is Plan A).
  Rescue's 2026-07-09 VibraFlow verdict is **challenged (2026-07-14)**: the run used a stale
  `graphify-out/` graph, so its WEAK conclusion about graph usability is unreliable — re-run on
  a freshly built graph is pending; standalone extraction (`runtime/shapes.py`) holds as the
  graph-free safe default. Still prose-only: the per-stack generators, tree-sitter extractor
  generalization, the SARIF/fp-check gate, and the map artifact — see each skill's `TODO.md`.
  Evals execute via `scripts/run_evals.py --run` once a fixture repo is wired.
- Generic skills are **composed** from `superpowers` (MIT), not authored here.
- The vendored `references/core/` copies are generated — edit `core/*.md`, then run `sync_core.py`.
