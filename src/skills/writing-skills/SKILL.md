---
name: writing-skills
description: Author or edit a skill in this package correctly — how the prose itself has to be written for an agent to act on it, the Agent Skills spec frontmatter, the invocation axis, the references/core path convention, keeping the drift-linter and roster parity green, and staying agent-agnostic (Claude Code + Codex + opencode + Pi). Use when adding, renaming, or editing a skill, module, or agent.
license: MIT
---

# Writing Skills

How this package stays self-extending without drifting. Authority: `CONTRIBUTING.md` + `CLAUDE.md`.

## Write it as prose an agent acts on — read this first
The deliverable of this repo is prose, so **how it is written is the product**, not its presentation.
`references/core/writing-for-agents.md` is the authority: context pointers (a `description` IS one,
and its wording is what decides whether the body is ever reached), the two loads, the information
hierarchy, completion criteria, leading words, and the pruning tests. Read it before authoring, and
apply the no-op test to every sentence you add here.

## A skill is
`skills/<name>/SKILL.md` with Agent-Skills frontmatter: `name` (lowercase-with-hyphens, **matching
the directory**) and `description` (≥ 20 chars, saying what it does AND when to use it), optional
`license`. Bundle `references/*.md` (skill-relative) alongside; shared docs live in `core/*.md`
(repo-root-relative).

**Choose the invocation deliberately.** Omitting `disable-model-invocation` is a choice, not a
default: it spends permanent context load on the description in exchange for the agent being able to
reach the skill itself. Add `disable-model-invocation: true` only when the honest answer to *could
the agent usefully reach for this on its own?* is no — and remember what it also costs, because both
are verified rather than assumed: the skill becomes unreachable **by another skill**, and on Claude
Code it is **no longer preloaded into a subagent**, which this package's six-role roster depends on.
Author the key once in the frontmatter; Claude Code and Pi both read it, and the build derives
Codex's `agents/openai.yaml` from it. opencode has no mechanism that keeps the human's reach — see
the packaging notes for the residual.

## Keep the invariants green (they run in CI)
**Run every gate — the list is the Commands block in `CLAUDE.md`**, complete against
`.github/workflows/ci.yml`. It is not copied here; the copy that used to be here named four of them
under a heading that reads as the set, which is the same claiming-vs-doing bug the gates catch.

Two are worth knowing by name while authoring a skill:
- `python scripts/verify_commands.py` — every command a shipped file names resolves **after
  install**, not merely here. The other gates anchor on `__file__` and cannot see that class.
- `python scripts/check_tool_carriers.py` — every WRITE tool the MCP server exposes is named by a
  shipped playbook. Describing an act in English without naming the tool that performs it is the
  failure this whole repo is organized around; that gate is where it gets caught.

Three-way sync: a new or renamed module updates its `modules.json`, its playbook, AND any
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
