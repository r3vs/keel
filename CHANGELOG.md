# Changelog

All notable changes to this project are documented here. The project is design-complete and
pre-implementation; versions track the design + packaging, not a released runtime.

## [0.1.0] — unreleased

### Added
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

### Notes
- Pre-implementation: `evals/` hold prompts + assertions but no runtime harness yet; the greenfield
  step-0 gating experiment is not yet run. See each skill's `TODO.md`.
- Generic skills are **composed** from `superpowers` (MIT), not authored here.
- The vendored `references/core/` copies are generated — edit `core/*.md`, then run `sync_core.py`.
