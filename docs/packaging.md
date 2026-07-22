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
| **Codex** | the same file — its manifest's `mcpServers: "./.mcp.json"` points at it | same |
| **opencode** | a `config(cfg)` hook in the placed plugin mutates the live merged config | `type: local` / `remote`, `command` is an **array**, `environment` (not `env`) |
| **Pi** | no native MCP — its extension is the bridge | — |

Host facts verified **at the function that consumes the value**, not inferred, and none guessable
from the others:

- **Codex needs the `./`.** `resolve_manifest_mcp_servers` → `resolve_manifest_path`, which does
  `path.strip_prefix("./")` and returns `None` + a `tracing::warn` otherwise. This doc used to cite
  `PluginManifestMcpServers::Path` as the verification — the type that *holds* the value, which
  accepts any `String`. That citation is how `".mcp.json"` shipped for months. (Its severity was
  low: `plugin_mcp_config_paths` falls back to `<root>/.mcp.json`, so the declaration was inert
  rather than fatal. **`commands` has no such fallback** — declaring it without `./` is strictly
  worse than omitting it.)
- **opencode's discriminator is `local`/`remote`**, not Claude's `stdio`/`http` — and it is
  *ternaried*, not switched (`mcp.type === "remote" ? connectRemote : connectLocal`), so `"stdio"`
  is silently treated as **local**, then `const [cmd, ...args] = mcp.command` destructures the
  string `"npx"` into `cmd="n"`, `args=["p","x"]` → ENOENT. Valid JSON, no error, no server.
- **`enabled` defaults to ON** (`if (mcp.enabled === false)` — strict). Absence is not "off".
- **Nothing validates what a plugin writes into `cfg.mcp`.** File-borne config hard-fails through
  `ConfigParse.schema`; plugin-borne config bypasses it entirely and degrades to
  `logWarning("server unavailable")`. If our emitted shape ever goes wrong, CI stays green and the
  user gets a plugin that installs and declares nothing — the exact Codex signature, in a place no
  gate of ours currently watches.
- **`${CLAUDE_PLUGIN_ROOT}`** is a Claude-ism. opencode's `ConfigVariable.substitute` expands
  exactly `{env:VAR}` and `{file:path}`; an unknown `${...}` passes through **literal**, producing a
  nonexistent path rather than an error. So the opencode plugin resolves our server from
  `import.meta.url` instead. On Claude Code it does expand inside `.mcp.json` — officially, in a
  stdio server's `command`, `args` and `env`, which is exactly how we use it.

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

## The generic skills are ours, because they must be ledger-aware

**The rule: a programmer and their coding agent get everything they need from our plugins. No
external plugin, ever.** `tests/test_codex_manifest.py` enforces it — no marketplace source may
leave this repo.

This reverses a doctrine that stood here for months: *"generic engineering skills (TDD, debugging,
planning, code review, git worktrees) are **composed** from [`superpowers`](https://github.com/obra/superpowers),
not reinvented here."* Two things were wrong with it, and the second is the one that matters.

**It was never composed.** No plugin declared superpowers in `dependencies`; no file in `src/` named
one of its skills. The entry's `source` was `"github:obra/superpowers"` — a shorthand that does not
exist — so it could not even be fetched. Four documents asserted a mechanism that was not there, on
the shop window, for months. The house failure mode.

**And composing it was the wrong goal.** A dependency installs the *whole* plugin: 16 skills, of
which `brainstorming`, `writing-plans`/`executing-plans`, `dispatching-parallel-agents` and
`subagent-driven-development` are **stateless twins** of `core/brainstorm.md`, `buildloop.py` and
`core/agents.md`. None of them writes to the ledger; none ever will. Putting a forgetting twin
beside the single source of truth is exactly the divergence this package exists to find in other
people's codebases — we would have shipped our own anti-pattern, unpinned (the entry carried no
`ref`/`sha`), with session-start hooks, through our own catalog.

So: not a reinvention, a **binding**. superpowers' TDD cannot make its red step an
`acceptance_criterion` pin. Ours is nothing but that. Same for the rest — a debugging loop that
opens and closes a `defect` pin, a review that reopens rather than decides, a worktree discipline
that makes the executor's "one scope at a time" enforceable instead of promised.

The gap is smaller than 16 because the spine already owns the twins. What is genuinely missing:
`test-driven-development`, `systematic-debugging`, `verification-before-completion`, `code-review`
(their request/receive pair), and a branch/worktree lifecycle. superpowers is MIT, so where its
prose is good the honest move is to adapt it with attribution — not to pretend we did not read it.

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

**Why vendor at all — distribution atomicity, and nothing else.** The Agent Skills spec's unit of
distribution is the **standalone skill folder**, and `scripts/install.sh` links each skill directory
individually into the host — a sibling `core/` is not part of what travels. Vendoring guarantees the
bytes a skill needs live *inside* the unit that ships. It buys nothing about path resolution: both
opencode and Pi inject the skill's own base directory and delegate resolution to the model (no host
resolves skill-relative reads deterministically), so a `../../core/x.md` is not rejected — it is
lexically internal and would silently read the user's *own* file at that path. Self-containment is
enforced by no host; our linter is the only thing between us and a bug both would happily ship.

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

The residual none of them close: **a plugin cannot ship a selective, agent-scoped `Bash` rule.**
Claude Code restricts `Bash` fine — `Bash(rm *)`-style matchers exist, with `deny → ask → allow`
precedence — but only in the user's own `settings.json`, session-wide, which a plugin cannot write.
The ledger gate closes that residual at runtime.

## External tool licenses

This repo's code and prose are MIT (`LICENSE`). The deterministic toolchain it *invokes* keeps its
own licenses — notably **GitNexus is PolyForm Noncommercial** (optional secondary graph engine; not
installed unless `RESCUE_INSTALL_GITNEXUS=1`). Graphify (optional graph source) is MIT.

[Anthropic Agent Skills specification]: https://code.claude.com/docs
