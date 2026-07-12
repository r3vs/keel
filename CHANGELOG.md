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
- **Agent roster** (`core/agents.md`): researcher · brainstorm · executor · reviewer · measurer,
  under serialized-writing / parallel-reading.
- **Engineering hygiene**: drift-linter + pointer verifier, CI (`.github/workflows/ci.yml`), a
  version-pinning mechanism in `bootstrap.sh`, MIT `LICENSE`, `CONTRIBUTING.md`.

- **Complete-package layer** (composed, not cloned): five composable skills — `using-the-ledger`,
  `grounded-research`, `static-first-analysis`, `project-memory`, `writing-skills` (meta); a
  **memory** subsystem (ledger + `MEMORY.md` + memory MCP); **MCP** servers wired across platforms
  (`context7`, `deepwiki`, `memory`; `github` opt-in) via `.mcp.json`, `opencode.json`, and
  `.codex/config.toml`; **Codex** + any AGENTS.md-aware agent supported; and `superpowers` referenced
  in the marketplace for the generic engineering skills instead of reinventing them.

### Notes
- Pre-implementation: `evals/` hold prompts + assertions but no runtime harness yet; the greenfield
  step-0 gating experiment is not yet run. See each skill's `TODO.md`.
- Generic skills are **composed** from `superpowers` (MIT), not authored here.
