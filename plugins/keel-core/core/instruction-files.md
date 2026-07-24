<!-- GENERATED FILE - do not edit. Source: src/core/instruction-files.md at the repo root; regenerate with: python scripts/build.py -->

# Agent instruction files — the carrier the elected design travels in

The ledger is the single source of truth and **no coding agent loads it.** Every host loads exactly
one thing unprompted: a markdown instruction file next to the code. Without a bridge between the
two, a project can have a fully elected design and still hand a fresh agent — the executor in a new
worktree, a teammate on another host, a reviewer after a context reset — a blank slate.

So the ledger is **projected** into that file, the same way the shape engine's contract is projected
into DB/ORM/API layers: generated, never authored, with a drift-check that proves the projection
still matches its source. Engine: `mcp:generate_instructions` / `mcp:instructions_diff`.

## What each host actually reads (verified at the loading function, not at the docs)

| Host | Files | Order | Imports |
|---|---|---|---|
| **Claude Code** | `CLAUDE.md`, `CLAUDE.local.md`, `.claude/CLAUDE.md`, `.claude/rules/*.md`, `~/.claude/CLAUDE.md`, managed policy | root→cwd concatenated; subdirectories load lazily when a file there is read | **`@path`, depth 4** — skips code spans and fenced blocks |
| **Codex** | `AGENTS.md`, `AGENTS.override.md` (`read_agents_md`) | project root (`project_root_markers`, default `.git`) → cwd, concatenated | none; truncates past `project_doc_max_bytes` |
| **opencode** | `AGENTS.md`, falling back to `CLAUDE.md`; global `~/.config/opencode/AGENTS.md`, falling back to `~/.claude/CLAUDE.md` (`InstructionContext.observe`) | up-tree, first match per category | none; `instructions` in `opencode.json` takes paths, globs, remote URLs |
| **Pi** | `AGENTS.md`/`CLAUDE.md`, case-insensitive; global `~/.pi/agent/AGENTS.md` (`loadProjectContextFiles`) | global → ancestors → cwd, concatenated | none; `--no-context-files` disables |

Three rules fall out, and only the first is obvious:

1. **`AGENTS.md` is the carrier; `CLAUDE.md` is a two-line bridge** (`@AGENTS.md`, which Claude
   Code's own docs prescribe). A symlink also works but needs Administrator or Developer Mode on
   Windows, so the bridge file is what gets generated.
2. **No import syntax is portable.** Only Claude Code parses `@path`. On the other three an `@` line
   is a literal string. **Anything that must be always-on is inlined, never imported.** The
   corollary bit this repo itself: a root `MEMORY.md` *mentioned* in `AGENTS.md` is loaded by
   nobody — and in Claude Code a mention inside backticks is not even an import.
3. **Length is a correctness constraint.** One host truncates by bytes, another loses adherence past
   ~200 lines. The generated region is therefore an **index with a line budget**, and every clip is
   declared inside the region (`+N more — read the ledger`). A shortened list that reads as complete
   is the same lie as a clean bill of health from a scanner that never ran.

## The managed region

The instruction file is the **user's**. We own a fence and nothing else:

```
<!-- keel:begin v1 sha256=… -->   ← generated: policies · elected pins · NOT-decided pins · generated files
<!-- keel:end -->
```

Everything outside survives byte for byte. The markers are HTML comments because Claude Code strips
block-level HTML comments before injecting the file, so the fence costs zero tokens where the budget
is tightest and stays visible to a human; the other three treat them as inert text.

The begin marker carries a fingerprint of the body it fenced, which is what lets the drift-check
separate two failures a re-render cannot tell apart:

- **`hand_edited`** — the body no longer hashes to what the marker recorded. Someone wrote a decision
  *into the projection* instead of into the ledger. Reported, **never auto-healed**: regenerating
  would silently discard it. Put it in the ledger, then regenerate.
- **`stale`** — the region is intact, the ledger moved. Regenerate.

Run the generator **after the interview elects and before the build loop starts** — the executor
works in a fresh context, so it inherits the decisions only if they are already in the carrier — and
again whenever a pin is decided, reopened, or resolved.

## Per-host layers above the portable floor

`.claude/rules/*.md` with `paths:` frontmatter is the **only** conditional, path-scoped instruction
mechanism among the four (opencode's `instructions` globs select which files to concatenate, always
on; Codex and Pi have none). It is therefore an **additive** projection for one host and never the
only carrier: the same fact — which files are generated and must not be hand-edited — is inlined in
the portable region that the other three read. In a monorepo, every host walks root→cwd, so a package
gets its own `AGENTS.md`; that is the mechanism a per-layer contract should use.

## Where memory sits relative to this

Four channels, and confusing them is how a decision ends up recorded where nothing can enforce it:

| Channel | Written by | Scope | Reaches subagents |
|---|---|---|---|
| **ledger** (`core/ledger.md`) | the human's interview | the elected truth, with `flip_criteria` | yes — via this carrier |
| **`AGENTS.md` region** | this generator | projection of the above | yes (every host loads it) |
| **`MEMORY.md`** | the human | durable project facts, git-tracked | on demand — it is **not** always-on anywhere |
| **host auto-memory** (e.g. Claude Code's `~/.claude/projects/<p>/memory/`) | the agent | machine-local, never git | **no** |

The ladder runs one way: a host memory note that turns out to be a team fact is promoted to
`MEMORY.md`; a `MEMORY.md` fact that turns out to be a decision is promoted to a pin with a
`flip_criteria`, and the duplicate is deleted. Nothing flows back down, and **no channel below the
ledger may elect anything** — see `core/assumptions.md` for what an agent does instead when it is
forced to assume.
