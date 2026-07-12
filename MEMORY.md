# Project Memory

Durable, cross-session facts about THIS repository (see the `project-memory` skill). Loaded as
always-on context via `AGENTS.md`. Keep it small; promote real decisions to the ledger.

## Facts
- This repo is a **package of agent skills**, not a runnable app — the deliverable is prose a future
  agent executes. Design-complete, pre-implementation (see each skill's `TODO.md`).
- **`core/decisions-ledger-spec.md` is Italian by design**; the rest is English (`core/ledger.md`
  is the English pointer). Do not "fix" this.
- Skills live under `skills/<name>/` (Agent Skills spec; `name` matches the directory). `core/` is
  the shared, repo-root-relative spine; `references/` is skill-root-relative.
- **Before committing**: `python scripts/check_consistency.py` and `python scripts/verify_pointers.py`
  must be green (they run in CI at `.github/workflows/ci.yml`).
- The agent roster's source of truth is `core/agents.md`; `agents/*.md` (Claude) and
  `opencode.json`'s `agent` block mirror it — the linter enforces parity.
- Generic engineering skills (TDD, debugging, planning, review) are **composed** from `superpowers`,
  not authored here — don't reinvent them.
- MCP: Context7 + DeepWiki + memory are auto-enabled; GitHub is opt-in (needs a token).

## Preferences
- (record durable user preferences here as they emerge)
