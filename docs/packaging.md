# Packaging — agent-agnostic by design

The skills are authored **once** to the [Anthropic Agent Skills specification] and run across
agents through thin per-platform adapters. Nothing skill-specific is duplicated per platform.

```
neutral content (portable)                 per-platform adapters (thin)
------------------------------             ------------------------------------
AGENTS.md            cross-agent entry     .claude-plugin/plugin.json     Claude Code
skills/<name>/SKILL.md  (+ references/)    .claude-plugin/marketplace.json
core/*.md            shared spine          agents/*.md  hooks/  commands/
core/agents.md       agent roster          opencode.json (plugin+agents+…) opencode
                                           .opencode/command/*.md
                                           scripts/install-opencode.sh
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

**Any other AGENTS.md-aware agent** — point it at the repo; it reads `AGENTS.md`, which sends it to
`skills/<name>/SKILL.md` and `core/`.

## Shared-core resolution

Both skills reference `core/*.md` at the plugin/repo root (the DRY single source). When installed,
the whole tree ships together, so `core/` is present alongside `skills/`. The `install-opencode.sh`
link keeps opencode's per-skill discovery pointing at the same one `skills/` tree — no duplication,
no drift (the property the skills themselves enforce).

## Keeping adapters honest

`core/agents.md` is the source of truth for the roster; `agents/*.md` (Claude) and the `agent`
block in `opencode.json` (opencode) must mirror it. `scripts/check_consistency.py` +
`scripts/verify_pointers.py` guard the docs; both run in CI (`.github/workflows/ci.yml`).

## External tool licenses

This repo's code and prose are MIT (`LICENSE`). The deterministic toolchain it *invokes* keeps its
own licenses — notably **GitNexus is PolyForm Noncommercial** (optional secondary graph engine; not
installed unless `RESCUE_INSTALL_GITNEXUS=1`). Graphify (primary backbone) is MIT.

[Anthropic Agent Skills specification]: https://code.claude.com/docs
