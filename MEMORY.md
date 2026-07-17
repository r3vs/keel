# Project Memory

Durable, cross-session facts about THIS repository (see the `project-memory` skill). **Dev-only —
this file must never ship to users**: it describes *this* repo, so shipping it would inject our
facts into someone else's project. Keep it small; promote real decisions to the ledger.

Loaded as always-on context by AGENTS.md-aware agents (opencode, Codex, Pi). **Claude Code reads
`CLAUDE.md`, not `AGENTS.md`** — it reaches this file through CLAUDE.md's `@AGENTS.md` import.

## Facts
- This repo is a **package of agent skills** — the deliverable is prose a future agent executes,
  plus a runtime spine (`runtime/`, stdlib-only, **179 tests** in CI), `scripts/run_evals.py`, and
  the ast-grep rule pack. **Step-0 verdicts, both now on trustworthy data**: greenfield STRONG
  (full generation is Plan A); rescue's VibraFlow **re-run on a fresh graph 2026-07-14** →
  **WEAK** cross-layer correspondence, so standalone extraction is Plan A and the carrier is the
  correspondence source of truth. The WEAK verdict is citable — the stale-graph challenge is closed.
- **`core/decisions-ledger-spec.md` is the authoritative ledger schema** (English); `core/ledger.md`
  is the short English pointer summary. (Historical note: the spec was authored in Italian and
  translated to English on 2026-07-14.)
- Skills live under `skills/<name>/` (Agent Skills spec; `name` matches the directory) and are
  **self-contained** (Model B): each keeps its own copy of the shared doctrine under
  `references/core/`. `core/*.md` is the single **authoring source** — edit it there, then run
  `python scripts/sync_core.py` to regenerate the vendored copies. A skill never points at `core/`
  directly (the linter errors on a bare `core/x.md` under `skills/`).
- **The gates protect the package *as installed*, not just the repo as a repo.** That distinction
  is the one this repo learned the hard way: every earlier gate anchored on `__file__` and was
  therefore blind to the only path class that is working-directory-sensitive — the strings a
  shipped file tells an agent to run. **Before committing**, all of these must be green (CI at
  `.github/workflows/ci.yml`):
  `check_consistency.py` · `sync_core.py --check` · `verify_pointers.py` · `verify_commands.py` ·
  `python -m unittest discover -s tests`
- The agent roster's source of truth is `core/agents.md`. Adapters mirror it and the linter enforces
  **both** name parity **and permission parity** — `agents/*.md` via `disallowedTools` (Claude Code
  has no `permission` field, and an omitted `tools:` inherits *everything*), `opencode.json` via
  `permission: {edit: …}`. Residual the linter cannot close: **`Bash` is a write vector Claude Code
  cannot restrict** — the ledger-state hook is what closes it at runtime.
- Generic engineering skills (TDD, debugging, planning, review) are **composed** from `superpowers`,
  not authored here — don't reinvent them.
- MCP: Context7 + DeepWiki + **cognee** (graph memory; opt-in, needs the Docker container +
  `LLM_API_KEY`) are declared; GitHub is opt-in (needs a token). **Pi has no native MCP** — it is
  reached through our own extension, never a hard dependency on `pi-mcp-adapter`.

## Preferences
- **No heuristics, tech-stack agnostic** (hard rule): the shape engine and the graph must be
  deterministic — extraction reads only a stack's own types, correspondence comes from the carrier.
  No name-matching, no plural folding, no comment-sniffing, no nearest-node guessing.
