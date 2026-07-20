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
- **`src/` you write by hand. `plugins/` `build.py` writes. Nothing else exists.** Skills are
  authored under `src/skills/<name>/` (Agent Skills spec; `name` matches the directory) and the
  build makes each **self-contained** (Model B), vendoring the doctrine it needs into its own
  `references/core/` *inside `plugins/`*. `src/core/*.md` is the single **authoring source** — edit
  it there, then `python scripts/build.py`. A skill never points at `src/core/` directly (the linter
  errors on a bare `core/x.md` under a skill).
- **The gates protect the package *as installed*, not just the repo as a repo.** That distinction
  is the one this repo learned the hard way: every earlier gate anchored on `__file__` and was
  therefore blind to the only path class that is working-directory-sensitive — the strings a
  shipped file tells an agent to run. **Before committing**, all of these must be green (CI at
  `.github/workflows/ci.yml`):
  `build.py --check` · `check_consistency.py` · `verify_pointers.py` · `verify_commands.py` ·
  `python -m unittest discover -s tests`
- **A user installs into THEIR project and never works in this repo** — so the root carries no host
  config, and delivery is the install: `.mcp.json` at the plugin root (Claude reads it; Codex's
  manifest points at it) and a `config()` hook in the opencode plugin. Root `.mcp.json` /
  `opencode.json` / `.codex/config.toml` were deleted 2026-07-17: they reached nobody, the docs
  still sold them as the install path, and the three copies had already drifted.
- **Give a fact one source and let the build derive every host's shape** — never hand-mirror, and
  never grep prose for it. The roster's write verb lives in `src/core/agents.md`'s table
  (→ `disallowedTools` for Claude, `permission: {edit: …}` for opencode); the required MCP servers
  live in `src/core/knowledge-sources.md`'s table. Residual nothing closes, **stated precisely**
  (2026-07-17: the old wording *"`Bash` is a write vector Claude Code cannot restrict"* is false —
  `Bash(rm *)` matchers exist): **a plugin cannot ship a selective Bash rule nor scope one to one
  agent** — agent frontmatter takes tool names only, `permissionMode` is ignored for plugin
  subagents, and the manifest has no permissions property. Only the user's own `settings.json` can,
  session-wide. The ledger-state hook closes it at runtime.
- **Self-contained: the user installs no external plugin, ever.** Generic engineering skills (TDD,
  debugging, review, worktrees) are authored HERE and bound to the ledger — reversed 2026-07-17.
  The old *"composed from `superpowers`"* line was false twice: nothing declared it in
  `dependencies` and no `src/` file named its skills (so it was never composed), and a dependency
  installs all 16 of its skills — four of which are **stateless twins** of `core/brainstorm.md`,
  `buildloop.py` and `core/agents.md` that cannot write to the ledger. Not a reinvention, a binding:
  TDD's red step *is* an `acceptance_criterion` pin. Gate:
  `test_codex_manifest.py::test_no_source_leaves_this_repo`.
- MCP: Context7 + DeepWiki + **cognee** (graph memory; opt-in, needs the Docker container +
  `LLM_API_KEY`) are declared; GitHub is opt-in (needs a token). **Pi has no native MCP** — it is
  reached through our own extension, never a hard dependency on `pi-mcp-adapter`.

## Preferences
- **No heuristics, tech-stack agnostic** (hard rule): the shape engine and the graph must be
  deterministic — extraction reads only a stack's own types, correspondence comes from the carrier.
  No name-matching, no plural folding, no comment-sniffing, no nearest-node guessing.
