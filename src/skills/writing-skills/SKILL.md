---
name: writing-skills
description: Author or edit a skill in this package correctly — the Agent Skills spec frontmatter, the references/core path convention, keeping the drift-linter and roster parity green, and staying agent-agnostic (Claude Code + opencode + AGENTS.md). Use when adding, renaming, or editing a skill, module, or agent.
license: MIT
---

# Writing Skills

How this package stays self-extending without drifting. Authority: `CONTRIBUTING.md` + `CLAUDE.md`.

## A skill is
`skills/<name>/SKILL.md` with Agent-Skills frontmatter: `name` (lowercase-with-hyphens, **matching
the directory**) and `description` (≥ 20 chars, saying what it does AND when to use it), optional
`license`. Bundle `references/*.md` (skill-relative) alongside; shared docs live in `core/*.md`
(repo-root-relative).

## Keep the invariants green (they run in CI)
- `python scripts/build.py --check` — every generated file still equals its `src/` source.
- `python scripts/check_consistency.py` — modules ↔ references ↔ SKILL, valid packaging manifests.
- `python scripts/verify_pointers.py` — every `*.md` pointer resolves.
- `python scripts/verify_commands.py` — every command a shipped file names resolves **after
  install**, not merely here. The other gates anchor on `__file__` and cannot see that class.
- Three-way sync: a new or renamed module updates its `modules.json`, its playbook, AND any
  `SKILL.md` pointer together.

## Stay agent-agnostic
Author to the spec once; never hard-code a platform. And when a fact has to exist in several hosts'
shapes, **give it one source and let the build derive them** — do not mirror it by hand and add a
parity linter, which is a smell: it says two things should be one thing, generated. A new agent role
goes in the roster table in `references/core/agents.md` and nowhere else; the build emits Claude's
`disallowedTools` and opencode's `permission: {edit: …}` from it. Same for the MCP servers the
doctrine mandates. Parse those tables — never grep the prose around them for names.

## Discipline (the ponytail ladder, applied to the package itself)
Read the relevant reference before editing — don't work from memory. Prefer reuse over a new skill:
does this capability already exist in `core/` or another skill? Extend before you add — the package
must not become the elaborate slop the skills exist to cure.
