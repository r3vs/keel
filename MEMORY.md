# Project Memory

Durable, cross-session facts about THIS repository (see the `project-memory` skill). **Dev-only —
this file must never ship to users**: it describes *this* repo, so shipping it would inject our
facts into someone else's project. Keep it small; promote real decisions to the ledger.

**No host loads this file, and that is the first fact it has to be honest about.** It used to open
by claiming it was "loaded as always-on context by AGENTS.md-aware agents (opencode, Codex, Pi)"
and that "Claude Code reaches this file through CLAUDE.md's `@AGENTS.md` import". Neither is true:
`AGENTS.md` *names* `MEMORY.md` in prose, which is a pointer, not an import — and **no import syntax
is portable** (only Claude Code parses `@path`). The same audit that built the instruction carrier
killed this claim in `project-memory`'s playbook (`CLAUDE.md`, *"loaded by nobody, on any of the
four hosts"*) and left it standing here, in the file the claim was about. So: an agent reads this
because it was told to, or because a human pasted it. Nothing loads it for you.

**Every number below is restated from a carrier, not remembered** — this file is in
`scripts/check_stated_facts.py`'s `SCOPE`, so a stale count fails CI instead of waiting for someone
to edit the line beside it. It was added there on 2026-08-13, having sat outside the scope of the
gate written for exactly its failure shape.

## Facts
- This repo is a **package of agent skills** — the deliverable is prose a future agent executes,
  plus a runtime spine (`src/runtime/`, core stdlib-only, **1359 tests green in CI**),
  `scripts/run_evals.py`, and the ast-grep rule pack. **Step-0 verdicts, both now on trustworthy
  data**: greenfield STRONG (full generation is Plan A); rescue's VibraFlow **re-run on a fresh
  graph 2026-07-14** → **WEAK** cross-layer correspondence, so standalone extraction is Plan A and
  the carrier is the correspondence source of truth. The WEAK verdict is citable — the stale-graph
  challenge is closed.
- **`src/core/decisions-ledger-spec.md` is the authoritative ledger schema** — English, and
  **currently v0.32**; `src/core/ledger.md` is the short English pointer summary. The runtime
  implementing it is `src/runtime/ledger.py`, and `ledger.SCHEMA_VERSION` is what every prose claim
  about the version is checked against. (Historical note: the spec was authored in Italian and translated to
  English on 2026-07-14. `docs/design/dynamic-workflows.md` was the last Italian file and was
  translated 2026-08-13.)
- **`src/` you write by hand. `plugins/` `build.py` writes. Nothing else exists.** Skills are
  authored under `src/skills/<name>/` (Agent Skills spec; `name` matches the directory) and the
  build makes each **self-contained** (Model B), vendoring the doctrine it needs into its own
  `references/core/` *inside `plugins/`*. `src/core/*.md` is the single **authoring source** — edit
  it there, then `python scripts/build.py`. A skill never points at `src/core/` directly (the linter
  errors on a bare `core/x.md` under a skill). **20 skills are authored; 19 ship** —
  `writing-skills` is our contributor guide in a skill's clothes, held back by `DEV_ONLY_SKILLS`.
- **A skill's `description` is rent on a budget the package does not own.** Claude Code keeps every
  skill's name and description in context, capped at 1% of the window, and on overflow drops
  descriptions *starting with the least-invoked skill* — which on a cold repo is all of ours. So
  only skills whose trigger is a **situation nobody names** stay model-invoked (today:
  `codebase-rescue`, `greenfield-forge`, `systematic-debugging`, `screenshot-to-code`); everything a
  person can reach by typing its name sets `disable-model-invocation: true`. The practical
  consequence for anyone adding a skill: **the budget is a shared pool, so a new model-invoked
  description is spent out of the existing ones**, and it is nearly exhausted.
  `scripts/check_description_budget.py` prints the live total and holds the ceiling — read it there
  rather than restating a number here. Evidence and five residuals, one of them since closed: `docs/open-gaps.md` §31.
- **One authored version string, and the release is a git tag.** `VERSION` in `scripts/build.py` is
  the only place a version is written by hand; every `.claude-plugin/` manifest, every
  `.codex-plugin/` manifest and the root `.claude-plugin/marketplace.json` are **stamped from it by
  the build** — the marketplace file is generated output that happens to live outside `plugins/`.
  A host decides "do I need to update?" by comparing that **string and nothing else**, so the number
  must move whenever the bytes move; `tests/test_plugin_version.py` makes that a gate by diffing
  `plugins/<name>` against the `{name}--v{version}` tag. That gate **skips green until the tag
  exists**, which is why tagging at merge is a documented release step (`CONTRIBUTING.md`) rather
  than a habit.
- **The gates protect the package *as installed*, not just the repo as a repo.** That distinction
  is the one this repo learned the hard way: every earlier gate anchored on `__file__` and was
  therefore blind to the only path class that is working-directory-sensitive — the strings a
  shipped file tells an agent to run. **Before committing, every gate must be green — the list is
  the Commands block in `CLAUDE.md`**, which is complete against `.github/workflows/ci.yml`. It is
  not restated here: this bullet used to carry its own copy and the copy was short by four
  (`check_hypotheses` · `check_schema_fields` · `check_tool_carriers` · `run_evals --validate`),
  which is the class the gates exist to catch, in the note that tells a session which gates exist.
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
- **Four MCP servers are declared, and cognee is not one of them.** The shipped `.mcp.json` carries
  `keel` (our own, 73 typed MCP tools over `uv run --script`), `playwright` (rendered-DOM
  extraction), `context7` and `deepwiki`. **`cognee` and `github` are named in the doctrine's table
  and deliberately left undeclared** — each needs external setup (a container plus `LLM_API_KEY`; a
  token), and a declared-but-unreachable server is a broken entry in every user's session.
  `tests/test_mcp_declaration.py::test_opt_in_servers_are_named_but_not_declared` is the gate. This
  bullet used to say cognee *was* declared, which contradicted the build rule two bullets up: the
  build only declares a row the table marks `→ **http**`. **Pi has no native MCP** — it is reached
  through our own extension, never a hard dependency on `pi-mcp-adapter`.
- **Node is a prerequisite of one skill, not of the package.** `run-workflow` vendors the TS
  workflow engine and needs Node; everything else runs on `uv` + MCP, and the skill degrades to
  sequential execution when Node is absent. Scoping it that way was an election, not an assumption
  (`docs/design/dynamic-workflows.md` §8 A-1, §10).

## Preferences
- **No heuristics, tech-stack agnostic** (hard rule): the shape engine and the graph must be
  deterministic — extraction reads only a stack's own types, correspondence comes from the carrier.
  No name-matching, no plural folding, no comment-sniffing, no nearest-node guessing.
