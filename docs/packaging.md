# Packaging — agent-agnostic by design

The skills are authored **once** to the [Anthropic Agent Skills specification] and run across
agents through thin per-platform adapters. Nothing skill-specific is duplicated per platform.

```
neutral content (portable)                 per-platform adapters (thin)
------------------------------             ------------------------------------
AGENTS.md            cross-agent entry     .claude-plugin/plugin.json     Claude Code
skills/<name>/SKILL.md  (+ references/)    .claude-plugin/marketplace.json
core/*.md            shared spine          agents/*.md  hooks/  commands/
core/agents.md       agent roster          opencode.json (plugin+agents+mcp) opencode
MEMORY.md            project memory        .opencode/command/*.md
                                           scripts/install-opencode.sh
                                           .mcp.json / .codex/config.toml    MCP (Claude / Codex)
```

## Why this works everywhere

- **`skills/<name>/SKILL.md`** uses the Agent Skills frontmatter (`name` `^[a-z0-9-]+$` matching
  the directory, `description` ≥ 20 chars, optional `license`/`allowed-tools`). Claude Code loads
  these natively; **opencode** discovers them via the `opencode-skills` plugin (Agent Skills spec).
- **`AGENTS.md`** at the repo root is the emerging cross-agent instructions file — read by opencode
  (and Cursor, Codex, …). It is deliberately short (loaded as always-on context); the depth lives
  behind the skills.
- **`core/agents.md`** defines the agent roster once; each adapter materializes it natively.

## Install

**Claude Code** — add the marketplace, then the plugin:
```
/plugin marketplace add r3vs/codebase-rescue
/plugin install codebase-alignment@codebase-alignment
```
Skills, `agents/`, `commands/` (`/rescue`, `/forge`), and the `SessionStart` hook load from the
plugin root (`.claude-plugin/plugin.json`, `source: "./"`).

**opencode** — enable the plugin and link the skills in:
```
# opencode.json already has:  "plugin": ["opencode-skills"]
bash scripts/install-opencode.sh     # links .opencode/skills -> ../skills
```
The five agents and the `/rescue` · `/forge` commands come from `opencode.json` +
`.opencode/command/`. `instructions: ["AGENTS.md"]` orients every session.

**Cursor** — open the repo (or add it to the workspace root); Cursor reads `AGENTS.md` natively,
which routes it to `skills/<name>/SKILL.md`. For live docs + memory, add the servers from
`.mcp.json` (context7, deepwiki, memory) under *Cursor Settings → MCP*.

**Any other AGENTS.md-aware agent** — point it at the repo; it reads `AGENTS.md`, which sends it to
`skills/<name>/SKILL.md` and `core/`.

## MCP servers

The methodology's live-knowledge and memory servers are declared per platform:
- **Claude Code** — `.mcp.json` (`context7`, `deepwiki` over HTTP; `memory` over stdio).
- **opencode** — the `mcp` block in `opencode.json` (same three enabled; `github` present but
  disabled — enable it and set a token).
- **Codex** — `.codex/config.toml` (`context7`, `memory` stdio; DeepWiki/GitHub HTTP as documented).

`context7` (live library/framework docs) and `deepwiki` (public-repo exemplars) power
`core/knowledge-sources.md`; `memory` powers the memory subsystem. **GitHub is opt-in** — the
official server (`https://api.githubcopilot.com/mcp/`) needs a token.

## Memory

Durable, cross-session memory in three layers (the `project-memory` skill): the **ledger**
(decision-memory, with `flip_criteria`), **`MEMORY.md`** (project facts, always-on via `AGENTS.md`
and opencode `instructions`), and the optional **memory MCP** (`@modelcontextprotocol/server-memory`).

## Composing generic skills

Generic engineering skills (TDD, debugging, planning, code review, git worktrees) are **not**
reinvented here — [`superpowers`](https://github.com/obra/superpowers) (Jesse Vincent, MIT) does
them well and cross-platform. It is listed in `.claude-plugin/marketplace.json` as a composed entry,
and recommended for opencode (`"plugin": ["superpowers"]`) and Codex. This package supplies the
**differentiated methodology**; compose the generic from best-in-class rather than duplicating it.

## Codex & other AGENTS.md agents

Codex reads `AGENTS.md` natively (project + `~/.codex`), so the methodology and skills are available
with zero extra config; `.codex/config.toml` adds the MCP servers. Any other AGENTS.md-aware agent
(Cursor, …) works the same way — the root `AGENTS.md` is the universal entry.

## Shared-core resolution

`core/*.md` is the single **authoring source** for the shared doctrine, and each skill is
**self-contained** (Model B): `scripts/sync_core.py` vendors the docs a skill needs into its own
`references/core/` (following the `core→core` dependency closure) and rewrites the pointers, so no
skill ever points outside its own tree. A skill directory therefore ships complete on every
platform — Claude Code, opencode (`install-opencode.sh` links the one `skills/` tree), or a bare
`AGENTS.md` agent — with no external `core/` dependency at read time. `core/` travels with the
package as the edit point only; CI's `sync_core.py --check` fails if any vendored copy drifts from
it, so the duplication can never diverge — the very anti-divergence property the skills enforce on
the codebases they touch, applied to their own shared prose.

### Why not just write the text directly in each skill (and delete `core/`)?

Because the same doctrine is load-bearing in several places at once — the ledger spec alone is
used by both methodology skills, two helpers, and the challenger agent. Written "directly where
needed" it becomes N hand-maintained copies with **no mechanical guard**: the next spec bump
updates some copies and misses others, and nothing can flag it because there is no source to
compare against. That silent divergence is the exact failure mode this package exists to cure, so
the repo applies its own medicine: one source, generated copies, a CI gate. The copies exist only
because the Agent Skills spec's unit of distribution is a **standalone skill folder** — a skill
copied out of the repo must not contain dangling pointers.

Three rules keep the model honest:
- every vendored copy carries a `GENERATED FILE — do not edit` banner (the source is `core/`);
- the sharing surface stays **minimal**: only load-bearing dependencies are backticked pointers
  (which the closure follows); see-also mentions stay plain text, so helpers vendor only the doc
  that is their actual subject;
- `agents/*.md` and other **plugin-root adapters may point at `core/` directly** — they are not
  skills, never ship standalone, and always travel with the repo root. Only files under `skills/`
  must use vendored copies (the linter enforces exactly this split).

## Keeping adapters honest

`core/agents.md` is the source of truth for the roster; `agents/*.md` (Claude) and the `agent`
block in `opencode.json` (opencode) must mirror it. `scripts/check_consistency.py`,
`scripts/sync_core.py --check` (vendored core ↔ source), and `scripts/verify_pointers.py` guard the
docs; all three run in CI (`.github/workflows/ci.yml`).

## External tool licenses

This repo's code and prose are MIT (`LICENSE`). The deterministic toolchain it *invokes* keeps its
own licenses — notably **GitNexus is PolyForm Noncommercial** (optional secondary graph engine; not
installed unless `RESCUE_INSTALL_GITNEXUS=1`). Graphify (primary backbone) is MIT.

[Anthropic Agent Skills specification]: https://code.claude.com/docs
