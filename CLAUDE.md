# CLAUDE.md

@AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. **Claude Code reads `CLAUDE.md`, not `AGENTS.md`** — the `@AGENTS.md` import above is
the bridge, so the cross-agent entry point and this file can never say different things. Every
other host (opencode, Codex, Pi, Cursor) reads `AGENTS.md` directly.

> **The whole structure, in one rule:**
>
> > **`src/` you write by hand. `plugins/` `build.py` writes. Nothing else exists.**
>
> `src/` holds *everything* authored — core doctrine, runtime, the MCP adapter, the skills' prose,
> agents, commands, hooks, the TS adapters, tools — and never ships. `plugins/` is generated output,
> committed because a marketplace installs from the repo, and guarded by `build.py --check`.
> `tests/` `scripts/` `docs/` and the root `.md` files develop the repo and never ship. (A plugin's
> root `CLAUDE.md` is not loaded by Claude Code anyway — plugins contribute context through skills,
> agents and hooks.)
>
> That rule replaced three overlapping answers to "is this source or output?": `skills/` used to be
> 51 authored files sitting beside 60 generated ones, `sync_core.py`/`sync_runtime.py` vendored into
> that tree and committed the copies, then `build.py` vendored them *again* into `plugins/` and
> `dist/`. Three generations, 17 copies of `ledger.py`, 2.70× duplication. Now: one generation,
> 7 copies (1 source + 6 that are structurally forced), 1.66×.

## What this repository is

This repository holds **two sibling Claude Code skills**, not runnable applications. The
deliverable is prose that a future Claude instance reads and executes:

- **`codebase-rescue`** (in `skills/codebase-rescue/`) — the **curative** skill: rescue an existing,
  misaligned, often AI-generated codebase. `SKILL.md` + `references/*.md` + `modules.json`.
- **`greenfield-forge`** (in `skills/greenfield-forge/`) — the **preventive** twin: build a NEW project
  aligned from the first commit, so it never needs rescuing. Same file layout under its own dir.
- **`src/core/`** — the **shared spine** both skills read/write: the decisions-ledger spec, the
  interview funnel, the brainstorm agent, and the field-shape engine. Neither skill duplicates it.
- **`src/runtime/` + `src/mcp/`** — the deterministic spine and its MCP adapter. `build.py` vendors
  the runtime into each skill that runs it (the portable floor) *and* the MCP server serves it as
  typed tools — which is what makes the capability **discoverable** rather than merely available.
- **`plugins/`** — **generated build output; the only thing that ships.** Four plugins
  (`alignment-core`, `codebase-rescue`, `greenfield-forge`, `alignment-helpers`), each with both a
  `.claude-plugin/` and a `.codex-plugin/` manifest. opencode and Pi link their skills straight out
  of here (`scripts/install.sh`) — a separate staging tree would just be a third copy of the same
  bytes.
- **The engineering loop, authored here and bound to the ledger** — `test-driven-development` (the
  red step IS an `acceptance_criterion` pin), `systematic-debugging` (root cause lands in the
  `defect` pin, not the commit message), `code-review` (reopens, never decides — the reviewer is
  read-only by design), `verification-before-completion` (a pin resolves when the behavior was
  *observed*, not when the code was written), `branch-lifecycle` (a worktree per scope makes the
  executor's "one scope at a time" enforceable instead of promised).
- **Complete-package layer** — composable skills (`using-the-ledger`, `grounded-research`,
  `static-first-analysis`, `project-memory`, `learning-layer`), a memory subsystem (ledger +
  `MEMORY.md` + cognee MCP), and MCP servers (`context7`/`deepwiki`/`cognee`; `github` opt-in).
  `writing-skills` is **dev-only** — it documents contributing to this repo and never ships.

  **Self-contained is a hard rule: the user installs no external plugin, ever.** Everything a
  programmer and their coding agent need ships from this repo, and
  `tests/test_codex_manifest.py::test_no_source_leaves_this_repo` is the gate. This reversed the old
  *"generic skills are **composed** from `superpowers`, not reinvented here"* doctrine, which failed
  twice over: **it was never composed** (no plugin declared it in `dependencies`, no file in `src/`
  named one of its skills, and its `source` shorthand could not even fetch — four documents
  asserting a mechanism that did not exist); and **composing it was the wrong goal**, because a
  dependency installs the *whole* plugin, and `brainstorming` / `writing-plans` / `executing-plans`
  / `subagent-driven-development` are **stateless twins** of `core/brainstorm.md`, `buildloop.py` and
  `core/agents.md` that cannot write to the ledger. A forgetting twin beside the single source of
  truth is the exact divergence this package exists to find.

  So the generic skills are authored here and **bound to the ledger** — not a reinvention, a
  binding: superpowers' TDD cannot make its red step an `acceptance_criterion` pin; ours is nothing
  but that. The gap is small because the spine already owns the twins — what is missing is
  `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `code-review`
  and a branch/worktree lifecycle. superpowers is MIT: where its prose is good, adapt it with
  attribution rather than pretend we did not read it.

Each skill is **design-complete with the runtime largely implemented**; its `TODO.md` is the build
checklist. Greenfield's step-0 verdict is recorded (STRONG → full four-layer generation is
Plan A); rescue's VibraFlow verdict was **re-run on a fresh graph** (2026-07-14 — WEAK cross-layer
correspondence, so standalone extraction is Plan A). The runtime lives under `src/runtime/`
(core stdlib-only, 262 tests in CI): `ledger.py` (spec v0.6), `shapes.py` (field-shape engine +
drift-check, 8 stacks), `treesitter_extract.py` (the **primary** extraction backend — a real grammar per language, so
real-world TS/GraphQL/SQL parse with no per-repo patches; declarative per-grammar data, degrades to
the stdlib parsers when absent), `generate.py` (contract generators,
round-trip to zero drift), `findings.py` (SARIF/OSV + fp-check gate), `interview.py` +
`assets/decision-catalog.json` (frame + funnel), `challenger.py`, `buildloop.py` (Phase-4 wave
scheduler), `map.py` (self-contained visual map), `graph.py` (graph anchoring + blast-radius over
graphify's `graph.json`, staleness-gated). Plus the eval harness (`scripts/run_evals.py`), the
consistency linters under `scripts/`, and rescue's ast-grep rule pack. What remains is
agent-orchestrated at runtime (the per-item TDD loop).

A skill's *runtime* behavior — what it does when invoked — is fully described in its `SKILL.md`.
Read it before changing how that skill works. Working on this repo means editing that design, not
running an app.

## Commands

**There IS a build step, and `plugins/` is its committed output.**

```bash
python scripts/build.py               # src/ -> plugins/. The ONE generation step; the only thing that ships.
python scripts/check_consistency.py   # drift-linter — modules ↔ references ↔ SKILL; roster names AND permissions
python scripts/verify_pointers.py     # every *.md cross-reference resolves; exits 1 on dangling
python scripts/verify_commands.py     # every agent-facing COMMAND resolves after install; exits 1 on drift
python -m unittest discover -s tests  # ledger runtime, MCP tools + server, ledger gate, installed package
bash src/tools/bootstrap.sh           # toolchain + uv (idempotent, best-effort, never hard-fails)
bash scripts/install.sh               # link the built skills into ~/.agents/skills (opencode + Pi)
```

`build.py --check` is the drift gate; every check above runs in CI. Generated output is committed
because a marketplace installs from the repo — `--check` is what stops it drifting from `src/`.

**The distinction that organizes all of it:** these gates validate the package **as installed**, not
just the repo as a repo. Every earlier gate anchored on `__file__` and so was blind to the one path
class that is working-directory-sensitive — the strings a shipped file tells an agent to run. That
is how `python runtime/ledger.py` shipped for months, unable to resolve anywhere but here, with CI
green throughout. `verify_commands.py` and `tests/test_installed_package.py` exist for that class.

The ledger runtime (`src/runtime/ledger.py`, stdlib-only) is the one implementation of the spec both
skills bind to. Each skill's `evals/evals.json` holds prompts **with assertions**;
`scripts/run_evals.py` validates their structure (CI) and executes them when an agent runner is
available.

Both Python checks run in CI on every PR (`.github/workflows/ci.yml`). On Windows use `python`
(present) and run the `.sh` script from the Bash shell / Git Bash.

## The one idea to hold in your head

Both skills produce the same delta: **`gap = diff(to-be, as-is)`**.
- **as-is** = what the code currently is (descriptive). In `codebase-rescue` it is extracted from
  existing code (which may faithfully describe a mess); in `greenfield-forge` it starts **empty**
  and grows as slices are built.
- **to-be** = what it *should* be, **derived from decisions the user elects in an interview** —
  never extracted from the code.

Rescue runs the diff **backward** (as-is exists → derive the to-be → close the gap); greenfield
runs it **forward** (elect the to-be first → build until as-is meets it → gap → 0). Contract
mismatches, dead code, wrong logic, missing work, design concerns, and greenfield's open decisions
are all unified under this one principle — which is why there is deliberately no closed taxonomy.

## Architecture (shared across both skills; spans several files)

- **The decisions ledger is the single source of truth.** Three surfaces — the visual map/wiki,
  the interview, and the brainstorm — hold *no state of their own*; they all read/write one
  `ledger.json`. This is deliberate: it is the exact anti-divergence property the skills enforce on
  the codebases they touch. Schema authority: `src/core/decisions-ledger-spec.md` (shared, v0.6);
  English pointer summary: `src/core/ledger.md`.
- **A `Pin` is a discriminated union on `kind`** (`contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | open_decision | acceptance_criterion |
  other`). The `kind` constrains the shape of the pin's `as_is` / `to_be` / `question` payload.
  `open_decision` (v0.4) is the greenfield fork (nothing built yet); `acceptance_criterion` (v0.5)
  is the testable outcome that roots the dependency DAG. A `ChallengeEvent` (v0.6) is not a pin kind
  but an append-only event: the read-only `challenger` refutes an elected oracle and reopens the pin
  *upstream* (before build), the mirror of the feedback loop's downstream reopen. Both reopen, never
  decide. `provenance: agent_assumption` (v0.6) makes a forced assumption a vetoable pin, not a
  silent decision (`src/core/assumptions.md`).
- **Each phase is a separate invocation with fresh context**, communicating ONLY through on-disk
  artifacts (the ledger, the map, the graph/contract). Rescue has five phases; greenfield has seven
  (Frame → Interview → Contract → Build → Validate → Release → Operate & Evolve), the last two
  closing the loop back to the interview via `flip_criteria`. Persisting between phases is what
  makes the context reset possible — never design a phase that relies on another's in-memory session.
- **Modes select scope up front.** Rescue: `rescue` (default) · `align` · `audit` · `resume`.
  Greenfield: `forge` (default) · `spec` · `slice` · `decide` · `evolve`.
- **Each skill has a core cross-layer module** built on the shared field-shape engine
  (`src/core/shape-engine.md`): rescue's `contract-reconciliation` **diffs** field shapes across
  DB↔ORM↔API↔frontend to find drift; greenfield's `contract-propagation` **generates** those layers
  from one contract so they cannot drift. Read the relevant playbook in full before touching it.
- **The interview funnel, the brainstorm, contract-testing, and the feedback loop are shared**
  (`src/core/interview-funnel.md`, `src/core/brainstorm.md`, `src/core/contract-testing.md`,
  `src/core/feedback-loop.md`): same machinery, different direction (rescue reconciles/finds; greenfield
  generates/prevents). The feedback loop (`flip_criteria` → reopen) is what closes the lifecycle.
- **Cross-cutting doctrines are shared too** (`src/core/static-analysis.md`, `src/core/knowledge-sources.md`,
  `src/core/assumptions.md`): how to use static tools well (type-checkers / LSP / architecture-fitness,
  in-loop, deterministic findings skipping fp-check — and *authoring the spec so the strongest signal
  applies*); which external knowledge source per phase (Context7 / DeepWiki / registry / web), with
  grounding, confidence, and untrusted-input discipline; and how an agent surfaces its **own** forced
  assumptions as vetoable pins instead of encoding them silently (the anti-slop rule turned on the
  agent itself).
- **The shared doctrine is authored once in `src/core/` and vendored into each SHIPPED skill
  (Model B).** The copies exist only in `plugins/` — `build.py` materializes them (following the
  `core→core` dependency closure), rewrites `` `core/x.md` `` to `` `references/core/x.md` ``, and
  stamps each with a `GENERATED FILE — do not edit` banner. `--check` fails CI if any copy drifts.
  The source tree carries none: a `references/core/x.md` pointer in `src/skills/` resolves *by rule*
  to `src/core/x.md`, and the linters encode that rule.

  **Why vendor at all — distribution atomicity, and nothing else.** The rule is right; every earlier
  reason given for it was wrong, and re-auditing them at the *consuming function* (2026-07-17) killed
  all three. The honest argument: the Agent Skills spec's unit of distribution is the standalone
  skill folder, and `scripts/install.sh` symlinks **each skill dir individually** into
  `~/.agents/skills/`. A sibling `~/.agents/core/` is **not part of what travels**. Vendoring buys
  guaranteed presence of the bytes inside the unit that ships — and buys nothing whatsoever about
  path resolution or permission prompts.

  What was refuted, so nobody rebuilds the argument out of it: `relative_escape` is opencode-**v2
  only** and fires only for *relative* paths (an absolute path outside is promoted to
  `external_directory`, not rejected); `external_directory` prompts **once per subtree per project**,
  persists on "always", is pre-approvable by one config rule, and — decisively — **fires identically
  for vendored files**, because our own default install target `~/.agents/skills` is itself outside
  the user's project; and **Pi has no confinement at all**, though the sentence named both hosts.

  The counterfactual that inverts it: **both hosts inject the skill's absolute base directory and
  instruct the model to resolve against it** (opencode `core/src/tool/skill.ts`: *"Base directory for
  this skill: …"*; Pi `harness/skills.js`: *"References are relative to …"*). Under that contract
  `../` composes into an absolute path and behaves exactly like a vendored one. Our old mechanism
  only bites when the model ignores the host's instruction — and there **vendoring fails worse**:
  `references/core/x.md` is lexically *internal*, so it does not error, it silently reads the user's
  own file at that path.

  Worth naming under this repo's no-heuristics rule: **no host resolves skill-relative reads
  deterministically.** Both delegate it to the model via injected prose. Self-containment is enforced
  by no host either — our linter is the only thing between us and a bug both would ship happily.

  One rule keeps the surface lean: inside `src/core/*.md`, only **load-bearing** dependencies are
  backticked pointers (see-also mentions stay plain text), so the closure stays minimal. Watch for
  the inverse: one line in `core/ledger.md` naming a runnable path drags all of `ledger.py` into
  every skill that vendors that doc — a shared doc should not name a command unless every vendoring
  skill actually runs it. Plugin-root adapters (`src/agents/`, `src/commands/`, `src/hooks/`) point
  at `${CLAUDE_PLUGIN_ROOT}/core/x.md` — they are not inside a skill, and the build gives them a
  plugin-root copy.

## Packaging (agent-agnostic)

Authored once to the Anthropic Agent Skills spec (`skills/<name>/SKILL.md`; `name` matches the dir,
`description` ≥ 20 chars), then **built** into per-host artifacts. All four hosts have skills AND
plugins — in four different shapes, so the shapes are generated, never hand-kept:

| | Claude Code | Codex | opencode | Pi |
|---|---|---|---|---|
| skills | plugin `skills/` | `.agents/skills` | `.opencode`/`.claude`/`.agents` | `.pi`/`.agents` |
| plugin | `.claude-plugin/` + `dependencies` | `.codex-plugin/` (no deps) | a JS/TS **module** | `pi` key in package.json |
| hooks | `hooks.json`, 27 events | `hooks.json`, 10 events | **TS only** — hooks *are* the plugin API | **TS only** — extension events |
| MCP | yes | yes | yes | **no** (via an extension) |
| instructions | **CLAUDE.md only** | AGENTS.md | AGENTS.md | AGENTS.md/CLAUDE.md |

Four facts that decide the design, each learned by being wrong first:
- **The only true universal is `SKILL.md`** — not MCP, not plugins. `.agents/skills/` covers
  Codex + opencode + Pi; Claude Code is the outlier (plugin or `.claude/skills`).
- **Claude Code does not read `AGENTS.md`.** `CLAUDE.md` imports it with `@AGENTS.md`.
- **Frontmatter's floor is `name` + `description`** — Codex silently drops the rest, so nothing
  portable may depend on `allowed-tools`.
- **There is no portable hook format.** Claude Code and Codex share a near-identical `hooks.json`
  (one generator emits both); opencode and Pi need TypeScript. So `hooks/ledger-gate.py` holds the
  rule **once** and every host calls it — the adapters carry no logic.

`src/core/agents.md` is the roster source of truth; the build derives each host's mechanism from its
table — `tools:` + `disallowedTools` for Claude (agents have no `permission` field; `permissionMode`
exists but is **ignored for plugin subagents**) and `permission: {edit: …}` for opencode — so neither
is hand-kept and `build.py --check` is the guarantee. For the 5 read-only roles the `tools:`
allowlist is the enforcement; `disallowedTools` is a backstop that survives someone adding `Write`
to `tools:` later.

The residual it cannot close, **stated precisely** (the old wording — *"`Bash` is a write vector
Claude Code cannot restrict"* — is simply false, and was refuted by reading the docs it was never
checked against): Claude Code restricts Bash fine. `Bash(rm *)`-style matchers exist, with
`deny → ask → allow` precedence and first-match-wins. What is true is narrower and still sufficient:
**a plugin cannot ship a selective Bash rule, nor scope one to a single agent.** Three facts, each
verified: `disallowedTools`/`tools` take tool *names* (no documented `Bash(pattern)` support in an
agent definition); `permissionMode` is ignored for plugin subagents; and the plugin manifest has no
property for permission rules at all. Selective `Bash(...)` rules live only in the **user's own**
`settings.json`, session-wide — which a plugin cannot write. And we deliberately grant `Bash` to the
read-only roles (they need it for static analysis), so blunt denial is not available either. That is
what the ledger gate closes at runtime. Full details: `docs/packaging.md`.

> Loose thread, flagged rather than guessed: the manifest has a top-level `settings` — *"Only the
> documented allowlisted keys are applied"* — and that allowlist is **not documented anywhere**.
> Whether a plugin can ship `permissions.deny` through it is **UNVERIFIED**. Do not build on it
> without an observed test; this is exactly the type-vs-parser trap.

## The user works in THEIR repo, never in this one

This is the constraint that decides the whole packaging surface, and it is the one I have now gotten
wrong twice in the same way — each time by reasoning about the repo instead of about the install.

**The root carries no host config.** `.mcp.json`, `opencode.json` and `.codex/config.toml` used to
sit here, and they were indefensible three times over:

- **They reach nobody.** Someone who installs a plugin opens *their* project. Root config is loaded
  only when the cwd is this repo — i.e. only for us.
- **The docs sold them as the delivery mechanism anyway.** `README` told Cursor and Codex users to
  *"open the repo (or add it to your workspace root)"* and copy servers out of `.mcp.json`;
  `install.sh` printed *"copy the mcpServers block into your opencode.json"*. That is not installing
  a plugin, it is cloning a demo — and it meant two of four hosts had no install path at all.
- **Three hand-written copies of one fact had already drifted**: deepwiki present for Claude, missing
  for Codex; cognee `enabled: true` in two of them, which the doctrine forbids *because it cannot
  connect* without a container; context7 over `npx` in one and http in the others.

**Delivery is the install, on every host that can take it** — all generated from the doctrine's own
table (`src/core/knowledge-sources.md`), because the doc that *orders* the agent to use a server is
the thing entitled to name it:

| Host | Mechanism | Verified in — **name the function that CONSUMES the value** |
|---|---|---|
| Claude Code | `.mcp.json` at the plugin root, auto-discovered | docs: *"Location: `.mcp.json` in plugin root"*; the manifest need not reference it, and ours correctly doesn't |
| Codex | its manifest's `mcpServers: "./.mcp.json"` → the same file | `openai/codex`: `resolve_manifest_mcp_servers` → `resolve_manifest_path` (the `./` is load-bearing) → `plugin_mcp_config_paths` |
| opencode | a `config(cfg)` hook in the plugin mutates the live merged config | `anomalyco/opencode`: `Plugin.state`'s hook loop (by reference; return value is `Effect.ignore`d), ordered before MCP by `project/bootstrap.ts` |
| Pi | no native MCP; its extension bridges | `earendil-works/pi`: zero `\bmcp\b` matches across the published `dist/` |

Citing a **type** here is how the Codex `./` bug shipped for months (`PluginManifestMcpServers::Path`
accepts any `String`; `resolve_manifest_path` accepts only a `./`-prefixed one). Citing the
**rejecter** is how I then got its severity wrong. Follow the value until something uses or replaces
it. Also: `anomalyco/opencode` now redirects to `anomalyco/opencode` — the old name is a citation nobody
re-checked.

Two host facts there are **verified, not inferred**, and neither follows from the others: opencode's
discriminator is `local`/`remote` (not Claude's `stdio`/`http`) and its local `command` is an array,
so emitting Claude's shape would be valid JSON that declares nothing; and `${CLAUDE_PLUGIN_ROOT}` is
a Claude-ism no other host expands. `tests/test_mcp_declaration.py` holds all of it shut, including
the root staying clean.

**The cost this knowingly pays:** we no longer dogfood our own MCP server while developing here, and
dogfooding is a real detector — *"twelve playbooks invoke the runtime zero times"* survived for
months because nobody saw the tools in a list. But a root file that mirrors the product is not
dogfooding; it is a fourth hand-written copy, and it drifted like the other three. To eat our own
food, install the plugin the way a user does (`/plugin marketplace add ./`) — from a project that
is not this one.

## Editing conventions & invariants

- **The consistency gates are enforced in CI — keep them green.**
  `check_consistency.py` validates **every skill and the shared core**: every module in each
  `modules.json` has a `reference` that exists; every `` `references/…md` `` pointer in a `SKILL.md`
  resolves relative to that skill's root (this now includes the vendored `` `references/core/…md` ``);
  **no skill file points at the source directly** (a bare `` `core/…md` `` under `skills/` is an error
  — vendor it); and no skill content file still contains `STUB — scaffold only`.
  `build.py --check` verifies every vendored copy still equals its `src/` source, and
  `verify_pointers.py` checks every cross-reference resolves. When you add or rename a module, update
  its `modules.json` **and** its playbook **and** any `SKILL.md` pointer together.
- **Path convention:** `references/x.md` is skill-root-relative (rescue's root is
  `src/skills/codebase-rescue/`), and this **includes the vendored `references/core/x.md` copies** —
  which exist only after `build.py` runs, and are checked against `src/core/` by rule until then.
- **Sources of truth:** each skill's `modules.json` is authoritative for its module catalog;
  `src/core/*.md` is the single authoring source for the shared doctrine — **edit it there, never in
  a `plugins/**/references/core/` copy**, then run `scripts/build.py`. Within that,
  `src/core/decisions-ledger-spec.md` (v0.6) is authoritative for the ledger schema. Do not let a
  `SKILL.md`, a reference summary, or a vendored copy drift from them.
- **`src/core/decisions-ledger-spec.md` is the authoritative schema** (English, like the rest of the
  repo); `src/core/ledger.md` is the short English pointer summary to it.
- **Read the relevant reference before executing or editing a phase/module — do not work from
  memory.** `SKILL.md` states this as a rule, and the playbooks carry detail that `SKILL.md`
  deliberately omits.
- Runtime artifacts (`ledger.json`, `graph.json`, `*.skill`, `.audit/`, `docs/audits/`) are
  gitignored — the skill generates them; they are never authored or committed here.
