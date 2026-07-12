#!/usr/bin/env bash
# Claude Code SessionStart hook — a short activation nudge. The output becomes session context so
# the agent knows the skills exist and how they must be entered. Deliberately tiny (no context bloat).
cat <<'MSG'
[codebase-alignment] Two skills are available on a shared decisions-ledger core:
  - codebase-rescue  : align an existing, misaligned / AI-generated codebase.
  - greenfield-forge : build a NEW project aligned from the first commit.
Read AGENTS.md, then the relevant skills/<name>/SKILL.md. Do NOT start coding before the skill's
Phase 1 — that is the anti-slop discipline. Only the human's committed interview answer elects a
decision; agents find, propose, build, and verify.
MSG
