#!/usr/bin/env bash
# Claude Code SessionStart hook — the activation contract. Output becomes session context.
# Deliberately compact (one screen): mandatory-entry rule + full skill inventory, no filler.
cat <<'MSG'
[keel] MANDATORY WORKFLOW CHECK — before acting on ANY task, check whether one of
these skills applies; if it does, you MUST enter through its SKILL.md and follow its phases.
These are workflows, not suggestions — skipping Phase 1 to "just start coding" is the exact
failure mode this package exists to prevent.

Methodology (deep, phase-gated):
  - codebase-rescue  : existing messy/misaligned/AI-generated codebase -> align it. Also for
                       "review my whole app", "backend and frontend don't match", "pick this up".
  - greenfield-forge : NEW project -> elect the design in an interview BEFORE code exists.

Composable helpers (use mid-task whenever relevant):
  - using-the-ledger      : read/write ledger.json state (via the ledger_* MCP tools)
  - grounded-research     : external knowledge — escalate Local->Context7->DeepWiki->Web, cite it
  - static-first-analysis : strongest static signal before judgment
  - project-memory        : durable facts (ledger + MEMORY.md + memory MCP)
  - learning-layer        : teach the operator from the delta while delivering senior output
  - writing-skills        : authoring/editing any skill in this package

Non-negotiable discipline (all agents):
  1. No code edits before the skill's interview elects the to-be. Only the human commits a decision.
  2. Forced to assume on vague input? Surface it as a vetoable pin (agent_assumption) — never encode
     it silently.
  3. Read the referenced playbook before executing a phase — do not work from memory.
MSG
