# Project Memory

Durable, cross-session facts about THIS repository (see the `project-memory` skill). Loaded as
always-on context via `AGENTS.md`. Keep it small; promote real decisions to the ledger.

## Facts
- This repo is a **package of agent skills**, not a runnable app — the deliverable is prose a future
  agent executes. Design-complete, pre-implementation (see each skill's `TODO.md`).
- **`core/decisions-ledger-spec.md` is Italian by design**; the rest is English (`core/ledger.md`
  is the English pointer). Do not "fix" this.
- Skills live under `skills/<name>/` (Agent Skills spec; `name` matches the directory) and are
  **self-contained** (Model B): each keeps its own copy of the shared doctrine under
  `references/core/`. `core/*.md` is the single **authoring source** — edit it there, then run
  `python scripts/sync_core.py` to regenerate the vendored copies. A skill never points at `core/`
  directly (the linter errors on a bare `core/x.md` under `skills/`).
- **Before committing**: `python scripts/check_consistency.py`, `python scripts/sync_core.py --check`,
  and `python scripts/verify_pointers.py` must be green (they run in CI at `.github/workflows/ci.yml`).
- The agent roster's source of truth is `core/agents.md`; `agents/*.md` (Claude) and
  `opencode.json`'s `agent` block mirror it — the linter enforces parity.
- Generic engineering skills (TDD, debugging, planning, review) are **composed** from `superpowers`,
  not authored here — don't reinvent them.
- MCP: Context7 + DeepWiki + memory are auto-enabled; GitHub is opt-in (needs a token).

## Preferences
- (record durable user preferences here as they emerge)
