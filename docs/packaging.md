# Packaging — agent-agnostic by design

The skills are authored **once** to the [Anthropic Agent Skills specification] and run across
agents through thin per-platform adapters. Nothing skill-specific is duplicated per platform.

```
authored once (src/, never ships)          generated per host (plugins/, the only output)
------------------------------             ------------------------------------------------
src/skills/<name>/SKILL.md                 .claude-plugin/plugin.json     Claude Code
src/core/*.md        shared spine          .codex-plugin/plugin.json      Codex
src/core/agents.md   agent roster          agents/*.md  commands/  hooks/hooks.json
src/runtime/         the engine            .mcp.json                      MCP (Claude + Codex)
src/mcp/             its MCP adapter       adapters/opencode/{agent,command,plugin}/
src/agents|commands|hooks|adapters/        adapters/pi/extensions/
AGENTS.md            cross-agent entry     skills/<name>/  (doctrine + runtime vendored inside)
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

**The user installs into their own project.** That sentence is the whole design constraint, and
getting it wrong is what this document used to do: it told Cursor and Codex users to *"open the
repo"* and copy MCP servers out of a `.mcp.json` at **our** root. That is not installing a plugin —
it is cloning a demo, and it meant two of four hosts had no delivery mechanism at all. Root host
config (`.mcp.json`, `opencode.json`, `.codex/config.toml`) is therefore **gone**; anything a user
needs is delivered by the install, and `tests/test_mcp_declaration.py` keeps it that way.

**Claude Code** — add the marketplace, then the plugin:
```
/plugin marketplace add r3vs/codebase-rescue
/plugin install codebase-rescue@codebase-alignment
```
`alignment-core` follows automatically via `dependencies`. Skills, `agents/`, `commands/`
(`/rescue`, `/forge`), the hooks and the MCP servers all load from the plugin root.

**Codex** — same marketplace, one difference that matters:
```
codex plugin marketplace add r3vs/codebase-rescue
codex plugin install codebase-rescue
codex plugin install alignment-core     # Codex has no `dependencies` — install the core explicitly
```

**opencode / Pi** — neither has a plugin manifest, so their pieces are generated into
`plugins/alignment-core/adapters/` (a directory Claude Code ignores) and a script places them:
```
git clone https://github.com/r3vs/codebase-rescue && cd codebase-rescue
python scripts/build.py && bash scripts/install.sh
```
Skills go to `~/.agents/skills` (both hosts auto-discover it); the roster, the commands, the ledger
gate and the MCP servers go to `~/.config/opencode/` and `~/.pi/agent/`. Everything is symlinked
into the clone, so keep it — a rebuild then needs no reinstall.

## MCP servers

**Delivery is the install, on every host that can take it — there is no block to copy.** The servers
are generated from the table in `src/core/knowledge-sources.md`: the doctrine that *orders* the agent
to ground its claims in them is the thing entitled to name them, so a server cannot be mandated in
prose and missing from the product.

| Host | How it arrives | Shape |
|---|---|---|
| **Claude Code** | `.mcp.json` at the plugin root, read on install | `type: stdio` / `http` |
| **Codex** | the same file — its manifest's `mcpServers: ".mcp.json"` points at it | same |
| **opencode** | a `config(cfg)` hook in the placed plugin mutates the live merged config | `type: local` / `remote`, `command` is an **array** |
| **Pi** | no native MCP — its extension is the bridge | — |

Two host facts there are verified in source, not inferred, and neither is guessable from the others:
Codex's manifest genuinely accepts a path (`PluginManifestMcpServers::Path`), and opencode's
discriminator is `local`/`remote` rather than Claude's `stdio`/`http`. Emitting Claude's shape into
opencode would parse as valid JSON and silently declare nothing. `${CLAUDE_PLUGIN_ROOT}` is likewise
a Claude-ism no other host expands, so the opencode plugin resolves our server from its own location.

**What ships**: `context7` (live library/framework docs) and `deepwiki` (public-repo exemplars) —
the two servers `core/knowledge-sources.md` requires.

**What is named but deliberately NOT declared**: `cognee` and `github`. Each needs external setup —
a container plus an `LLM_API_KEY`, a token — and a declared-but-unreachable server is a broken entry
in *every* user's session, which is the opposite of the doctrine's own "degrade gracefully, never
hard-fail". Both root configs used to declare cognee `enabled: true`, which could only ever have
worked on the machine that wrote them.

**Cognee memory is opt-in and has a setup cost** (unlike the old zero-config `server-memory`): it
is served by the `cognee/cognee-mcp` Docker container and runs its own LLM extraction, so start the
container and give it a key, then add it to **your own** MCP config:
```
# .env holds LLM_API_KEY=sk-...
docker run -e TRANSPORT_MODE=http --env-file ./.env -p 8000:8000 --rm -it cognee/cognee-mcp:main
```
```json
{ "mcpServers": { "cognee": { "type": "http", "url": "http://localhost:8000/mcp" } } }
```
Prefer **deliberate writes** (`cognee.remember("…")`) over conversational auto-capture, so the graph
stays curated. If you don't want the container + key, skip it — the ledger + `MEMORY.md` cover
durable memory without it.

## Memory

Durable, cross-session memory in three layers (the `project-memory` skill): the **ledger**
(decision-memory, with `flip_criteria`), **`MEMORY.md`** (project facts, always-on via `AGENTS.md`
and opencode `instructions`), and the optional **cognee MCP** (`cognee/cognee-mcp`) — a
queryable, self-editing graph for associative recall at scale, opt-in per the setup above.

## Composing generic skills

Generic engineering skills (TDD, debugging, planning, code review, git worktrees) are **not**
reinvented here — [`superpowers`](https://github.com/obra/superpowers) (Jesse Vincent, MIT) does
them well and cross-platform. It is listed in `.claude-plugin/marketplace.json` as a composed entry,
and recommended for opencode (`"plugin": ["superpowers"]`) and Codex. This package supplies the
**differentiated methodology**; compose the generic from best-in-class rather than duplicating it.

## Cursor & other AGENTS.md-only agents

An agent that reads `AGENTS.md` but has no plugin format is a partial target, and saying so plainly
is better than the shortcut this document used to take (*"open the repo"*). Install the skills the
way opencode and Pi do — `bash scripts/install.sh` places them where an `.agents/skills` reader
finds them — and add the MCP servers from `plugins/alignment-core/.mcp.json` through that agent's
own settings UI. The distinction that matters: you are pointing your agent at **your** project and
giving it our skills, not opening our repo and working inside it.

## Shared-core resolution

`src/core/*.md` is the single **authoring source** for the shared doctrine, and each skill is
**self-contained** (Model B): `scripts/build.py` vendors the docs a skill needs into its own
`references/core/` (following the `core→core` dependency closure) and rewrites the pointers, so no
skill ever points outside its own tree. A skill directory therefore ships complete on every
platform, with no external `core/` dependency at read time. `src/core/` is the edit point only and
never ships; CI's `build.py --check` fails if any vendored copy drifts from it, so the duplication
can never diverge — the very anti-divergence property the skills enforce on the codebases they
touch, applied to their own shared prose.

**Why vendor at all — verified on the opencode and Pi sources, not assumed.** Neither host resolves
a skill's relative paths against the skill directory; **both resolve against the user's project**. So
a `../../core/x.md` in a skill body does not read our file — it reads, or misses, something in
*their* repo (opencode v2 rejects it outright: `relative_escape`). Self-containment is enforced by no
host; our linter is the only thing between us and a bug both would happily ship.

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
- every vendored copy carries a `GENERATED FILE — do not edit` banner (the source is `src/core/`);
- the sharing surface stays **minimal**: only load-bearing dependencies are backticked pointers
  (which the closure follows); see-also mentions stay plain text, so helpers vendor only the doc
  that is their actual subject;
- `agents/*.md` and other **plugin-root adapters resolve `${CLAUDE_PLUGIN_ROOT}/core/x.md`** — they
  are not inside any skill, so the build gives them a plugin-root copy. Only files under `skills/`
  must use the per-skill vendored copies (the linter enforces exactly this split).

## Keeping adapters honest

Nothing here is kept in sync by hand, because a parity linter is a smell — it says two things should
be one thing, generated. So each fact lives once and the build derives every host's shape from it:

| Fact | Its one source | Derived into |
|---|---|---|
| the agent roster + its write verb | the table in `src/core/agents.md` | `disallowedTools` (Claude) · `permission.edit` (opencode) |
| the required MCP servers | the table in `src/core/knowledge-sources.md` | `.mcp.json` (Claude + Codex) · the opencode plugin's `config()` hook |
| the ledger gate's rule | `src/hooks/ledger-gate.py` | `hooks.json` (Claude + Codex) · thin TS adapters (opencode + Pi) that carry no logic |

Both tables are **parsed, never grepped** — "GitHub" appears in the knowledge-sources prose twice as
ordinary English (DeepWiki indexes *public GitHub repos*; *GitHub Advisory* is a registry), and a
word-match would "find" a server nobody declared. Correspondence comes from a declared fact or not
at all.

The gates: `scripts/build.py --check` (every generated file still equals its source),
`scripts/check_consistency.py`, `scripts/verify_pointers.py`, `scripts/verify_commands.py` (every
command a shipped file tells an agent to run resolves *after install*, not just here), and
`python -m unittest discover -s tests`. All run in CI (`.github/workflows/ci.yml`).

The residual none of them close: **`Bash` is a write vector Claude Code cannot restrict** — the
ledger gate closes that at runtime.

## External tool licenses

This repo's code and prose are MIT (`LICENSE`). The deterministic toolchain it *invokes* keeps its
own licenses — notably **GitNexus is PolyForm Noncommercial** (optional secondary graph engine; not
installed unless `RESCUE_INSTALL_GITNEXUS=1`). Graphify (primary backbone) is MIT.

[Anthropic Agent Skills specification]: https://code.claude.com/docs
