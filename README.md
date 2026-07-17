# codebase-alignment — an agent-agnostic skills package

A complete, installable package for keeping a codebase aligned across its whole lifecycle, built
around two deep, differentiated skills — one **curative**, one **preventive** — on a single
decisions-ledger spine. Installs as a plugin on **Claude Code, Codex, opencode and Pi** — you point
it at *your* project; nothing here needs to be cloned or copied by hand except for the two hosts
that have no plugin manifest.

- **`codebase-rescue`** — rescue a large, misaligned, often AI-generated ("vibecoded") codebase,
  reconciling backend, frontend, and database into an aligned, state-of-the-art state. Works on
  unfinished codebases and treats "not built yet" as a work item, not a defect.
- **`greenfield-forge`** — build a NEW project aligned from the first commit,
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

One rule covers the whole tree: **`src/` you write by hand. `plugins/` `build.py` writes. Nothing
else exists.**

- **`src/`** — everything authored, and it never ships: `skills/` (the two methodology skills plus
  the composable helpers), `core/` (the shared spine — ledger spec v0.6, interview funnel,
  brainstorm, shape engine, contract testing, feedback loop, static-analysis and knowledge-sources
  doctrine, the agent roster), `runtime/` (the deterministic engine, stdlib-only), `mcp/` (the
  FastMCP adapter that serves it), `agents/`, `commands/`, `hooks/`, `adapters/`, `tools/`.
- **`plugins/`** — **generated build output, and the only thing that ships.** Four plugins, each
  carrying both a `.claude-plugin/` and a `.codex-plugin/` manifest. Committed because a marketplace
  installs from the repo; `python scripts/build.py --check` is what stops it drifting from `src/`.
- **`tests/` `scripts/` `docs/`** and the root `.md` files develop the repo and never ship.

Generic engineering skills (TDD, debugging, planning, review, worktrees) are **composed** from
[`superpowers`](https://github.com/obra/superpowers), not reinvented.

Each skill is **self-contained**: the build vendors the doctrine and runtime a skill needs *inside*
it, because neither opencode nor Pi resolves a skill's relative paths against the skill directory —
both resolve against the user's own project. See `docs/packaging.md`.

## Install

> **Naming note:** the GitHub repo and the flagship plugin are both `codebase-rescue`; the
> **marketplace** is `codebase-alignment`. Hence `codebase-rescue@codebase-alignment` below.

**Claude Code**
```
/plugin marketplace add r3vs/codebase-rescue
/plugin install codebase-rescue@codebase-alignment     # or greenfield-forge@…, alignment-helpers@…
```
`alignment-core` comes along automatically (`dependencies`), bringing the MCP server, the roster,
the hooks and the `/rescue` · `/forge` commands.

**Codex**
```
codex plugin marketplace add r3vs/codebase-rescue
codex plugin install codebase-rescue                   # Codex has no dependencies — add alignment-core too
```

**opencode / Pi** — neither has a plugin manifest, so a script places their pieces:
```
git clone https://github.com/r3vs/codebase-rescue && cd codebase-rescue
python scripts/build.py && bash scripts/install.sh
```
Keep the clone: everything is symlinked into it, so a rebuild needs no reinstall.

**MCP is part of the install on every host that can take it** — you never copy a server block by
hand. Claude Code and Codex read the plugin's own `.mcp.json`; opencode gets the same servers from a
`config()` hook in the plugin file the script places. Pi has no native MCP; its extension bridges.
The servers are generated from `src/core/knowledge-sources.md` — the doctrine that *orders* the agent
to use them is the thing entitled to name them.

See `docs/packaging.md` for the per-host shapes, memory, and the compose model.

## Try it in 5 minutes

**Rescue an existing messy repo** (Claude Code, plugin installed):

```text
> this codebase is a mess — the frontend, backend and DB don't agree. rescue it.
```

The skill self-triggers (or invoke it explicitly), and the phases run as separate, restartable
invocations that communicate only through on-disk artifacts:

1. **Comprehension** — builds the as-is map; every problem becomes a *pin* in `ledger.json`
   (contract mismatches, intentional stubs rendered as neutral work items — never as errors).
2. **Interview** — you elect the truth: 200 findings compress to ~10 real questions via
   clusters + policies. Nothing is decided for you; blocker/high items are always asked.
3. **Roadmap → TDD remediation → validate** — the gap between elected to-be and as-is is closed
   item by item, each decision carrying its `flip_criteria` (the condition to reopen it).

Watch the state at any point — the ledger is the single source of truth all surfaces project. Just
ask; the plugin's MCP server exposes it as typed tools (`ledger_summary`, `interview_next`,
`contract_diff`, `blast_radius`, `build_waves`, `render_map`, …), so the agent discovers them rather
than being told a path:

```text
> summarise the ledger, then show me the open questions best-first
```

**Forge a new project** the same way: `> new project: <brief> — forge it`, and the interview
elects the design *before* any code exists; one contract then generates DB/ORM/API/client
aligned by construction, guarded for life by a CI drift-check.

## Status
Design-complete across two methodology skills + six composable helpers, packaged
agent-agnostically, with the **runtime largely implemented** (~240 tests in CI). Authored under
`src/runtime/`; reaching the agent as MCP tools, and vendored into each skill that runs it as the
portable floor:

| Piece | Source | MCP tool |
|---|---|---|
| Decisions-ledger runtime (spec v0.6) | `src/runtime/ledger.py` | `ledger_summary` |
| Field-shape engine + CI drift-check (8 stacks incl. Drizzle/Prisma/Django/GraphQL) | `src/runtime/shapes.py` | `contract_diff` · `reconcile_layers` |
| Contract generators (round-trip to zero drift) | `src/runtime/generate.py` | `generate_layers` |
| Findings + false-positive gate (SARIF/OSV) | `src/runtime/findings.py` | `findings_gate` |
| Decision catalog + interview funnel | `src/runtime/interview.py` + `assets/decision-catalog.json` | `interview_next` |
| Oracle challenger (deterministic classes) | `src/runtime/challenger.py` | `challenge_oracle` |
| Phase-4 wave scheduler | `src/runtime/buildloop.py` | `build_waves` |
| Visual map (self-contained HTML) | `src/runtime/map.py` | `render_map` |
| Graph anchoring + blast-radius (deterministic, by `file:line`) | `src/runtime/graph.py` | `blast_radius` |
| Tree-sitter backend (primary; generic engine + declarative per-grammar data) | `src/runtime/treesitter_extract.py` | — |
| Eval harness + ast-grep rule pack + fixtures | `scripts/run_evals.py`, `assets/ast-grep/`, `tests/fixtures/` | — |

**Step-0 verdicts recorded** (both now on trustworthy data): greenfield (FastAPI+SQLAlchemy+TS)
STRONG → full generation is Plan A; rescue **re-run on a fresh VibraFlow graph** (2026-07-14, after
the stale-graph challenge) → WEAK cross-layer correspondence → standalone extraction is Plan A,
confirmed by the shape engine pulling 113 tables / 1290 fields from VibraFlow's real Drizzle
schema. What remains is agent-orchestrated at runtime (the per-item TDD loop), the Go/Java/Rust/C#
stacks graduating from fixtures to real repos, and executing the evals against a live agent runner.
See each `TODO.md`.

## License
MIT (`LICENSE`). The external toolchain keeps its own licenses — notably GitNexus is PolyForm
Noncommercial (optional, opt-in).
