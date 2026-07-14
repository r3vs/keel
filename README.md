# codebase-alignment — an agent-agnostic skills package

A complete, installable package for keeping a codebase aligned across its whole lifecycle, built
around two deep, differentiated skills — one **curative**, one **preventive** — on a single
decisions-ledger spine. Runs on **Claude Code, opencode, and Codex** (any AGENTS.md-aware agent).

- **`codebase-rescue`** — rescue a large, misaligned, often AI-generated ("vibecoded") codebase,
  reconciling backend, frontend, and database into an aligned, state-of-the-art state. Works on
  unfinished codebases and treats "not built yet" as a work item, not a defect.
- **`greenfield-forge`** (`skills/greenfield-forge/`) — build a NEW project aligned from the first commit,
  so it never needs rescuing. Elects the design in a compressed decision interview *before* any
  code exists, defines the cross-layer contract once and generates aligned layers from it, then
  builds thin vertical slices test-first.

Both center on architecture — design choices, logic, specs, and layers that agree — not just bugs
and vulnerabilities.

## The shared idea
Two artifacts, diffed: **as-is** (what the code is now) and **to-be** (what it should be, derived
from decisions the user elects in a targeted interview). Everything is a delta:
`gap = diff(to-be, as-is)`. Rescue runs it backward (as-is exists → derive to-be → close the gap);
greenfield runs it forward (elect to-be → build until as-is meets it → gap → 0). A single
append-only decisions ledger is the source of truth for the three surfaces (map/wiki, interview,
brainstorm) — and a forged project's ledger is the audit baseline rescue can later diff against.

Rescue — five phases: comprehension → interview → diff/roadmap → TDD remediation loop → validate.
Greenfield — seven: frame → interview → contract & roadmap → build loop → validate → release →
operate & evolve, the last two feeding production back into the ledger (`flip_criteria` → reopen)
to close the loop.

## Layout
- `skills/codebase-rescue/` — the curative skill (`SKILL.md` + `references/` + `modules.json` + `evals/`).
- `skills/greenfield-forge/` — the preventive skill (same layout).
- `skills/{using-the-ledger,grounded-research,static-first-analysis,project-memory,learning-layer,writing-skills}/`
  — composable helper skills (`learning-layer` closes the **operator** gap: senior-grade output while
  the user learns). Generic skills (TDD, debug, planning, review) are **composed** from
  [`superpowers`](https://github.com/obra/superpowers), not reinvented.
- `core/` — the shared spine, and the single **authoring source** for it: `decisions-ledger-spec.md`
  (schema, v0.6, Italian), `ledger.md` (English pointer), `interview-funnel.md`, `brainstorm.md`,
  `shape-engine.md`, `contract-testing.md`, `feedback-loop.md`, `static-analysis.md`,
  `knowledge-sources.md`, `assumptions.md`, `agents.md`. Each skill is **self-contained**: `scripts/sync_core.py`
  vendors the doctrine it needs into `skills/<skill>/references/core/`, so no skill points outside
  its own tree (CI's `sync_core.py --check` keeps the copies identical to the source).
- **Packaging**: `AGENTS.md`, `.claude-plugin/`, `opencode.json`, `.codex/config.toml`, `agents/`,
  `hooks/`, `commands/`, `.mcp.json`, `MEMORY.md` — see `docs/packaging.md`.
- each skill's `TODO.md` — its build checklist. **Do step 0 (the gating experiment) first.**
- `scripts/{bootstrap.sh,check_consistency.py,sync_core.py,verify_pointers.py,install-opencode.sh}` —
  toolchain, drift-linter, core-vendoring sync, pointer verifier, opencode installer (checks run in CI).

## Install

> **Naming note:** the GitHub repo is `codebase-rescue` (the historical name of the flagship
> skill); the installable package/plugin is **`codebase-alignment`**. The commands below are
> consistent with that split.

- **Claude Code**: `/plugin marketplace add r3vs/codebase-rescue` → `/plugin install codebase-alignment@codebase-alignment`
- **opencode**: `opencode.json` already has `"plugin": ["opencode-skills"]`; run `bash scripts/install-opencode.sh`
- **Cursor**: open the repo (or add it to your workspace root) — Cursor reads `AGENTS.md` natively;
  add the MCP servers from `.mcp.json` in *Cursor Settings → MCP* if you want live docs + memory.
- **Codex / any AGENTS.md agent**: point it at the repo — it reads `AGENTS.md` (MCP in `.codex/config.toml`).

See `docs/packaging.md` for MCP, memory, and the compose model.

## Status
Design-complete and internally coherent across two methodology skills + six composable helpers;
packaged agent-agnostically; the drift-linter and pointer verifier are green in CI. What remains is
runtime implementation — see each `TODO.md`.

## License
MIT (`LICENSE`). The external toolchain keeps its own licenses — notably GitNexus is PolyForm
Noncommercial (optional, opt-in).
