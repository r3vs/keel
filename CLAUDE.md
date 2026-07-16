# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This repository holds **two sibling Claude Code skills**, not runnable applications. The
deliverable is prose that a future Claude instance reads and executes:

- **`codebase-rescue`** (in `skills/codebase-rescue/`) — the **curative** skill: rescue an existing,
  misaligned, often AI-generated codebase. `SKILL.md` + `references/*.md` + `modules.json`.
- **`greenfield-forge`** (in `skills/greenfield-forge/`) — the **preventive** twin: build a NEW project
  aligned from the first commit, so it never needs rescuing. Same file layout under its own dir.
- **`core/`** — the **shared spine** both skills read/write: the decisions-ledger spec, the
  interview funnel, the brainstorm agent, and the field-shape engine. Neither skill duplicates it.
- **Agent-agnostic packaging** — `AGENTS.md` (cross-agent entry), `.claude-plugin/` (Claude Code
  plugin + marketplace), `opencode.json` + `.opencode/` (opencode via the `opencode-skills`
  plugin), `.codex/config.toml` (Codex), `agents/` (roster), `hooks/`, `commands/`, `.mcp.json`
  (MCP). Skills follow the Anthropic Agent Skills spec so they are portable. See `docs/packaging.md`.
- **Complete-package layer** — composable skills (`using-the-ledger`, `grounded-research`,
  `static-first-analysis`, `project-memory`, `learning-layer`, `writing-skills`), a memory subsystem (ledger +
  `MEMORY.md` + cognee MCP), MCP servers (`context7`/`deepwiki`/`cognee`; `github` opt-in), and
  `superpowers` **composed** (referenced in the marketplace) for the generic engineering skills.

Each skill is **design-complete with the runtime largely implemented**; its `TODO.md` is the build
checklist. Greenfield's step-0 verdict is recorded (STRONG → full four-layer generation is
Plan A); rescue's VibraFlow verdict was **re-run on a fresh graph** (2026-07-14 — WEAK cross-layer
correspondence, so standalone extraction is Plan A). The runtime lives under `runtime/`
(core stdlib-only, ~170 tests in CI): `ledger.py` (spec v0.6), `shapes.py` (field-shape engine +
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

No build step exists. The executable checks:

```bash
python scripts/check_consistency.py   # drift-linter — modules ↔ references ↔ SKILL (both skills + core); exits 1 on drift
python scripts/verify_pointers.py     # intra-playbook cross-reference check (complements the linter); exits 1 on dangling
python -m unittest discover -s tests  # ledger-runtime tests (spec v0.6 rules as executable checks)
bash scripts/bootstrap.sh             # install the deterministic toolchain (idempotent, best-effort, never hard-fails)
```

The ledger runtime (`runtime/ledger.py`, stdlib-only) is the one implementation of the spec both
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
  the codebases they touch. Schema authority: `core/decisions-ledger-spec.md` (shared, v0.6);
  English pointer summary: `core/ledger.md`.
- **A `Pin` is a discriminated union on `kind`** (`contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | open_decision | acceptance_criterion |
  other`). The `kind` constrains the shape of the pin's `as_is` / `to_be` / `question` payload.
  `open_decision` (v0.4) is the greenfield fork (nothing built yet); `acceptance_criterion` (v0.5)
  is the testable outcome that roots the dependency DAG. A `ChallengeEvent` (v0.6) is not a pin kind
  but an append-only event: the read-only `challenger` refutes an elected oracle and reopens the pin
  *upstream* (before build), the mirror of the feedback loop's downstream reopen. Both reopen, never
  decide. `provenance: agent_assumption` (v0.6) makes a forced assumption a vetoable pin, not a
  silent decision (`core/assumptions.md`).
- **Each phase is a separate invocation with fresh context**, communicating ONLY through on-disk
  artifacts (the ledger, the map, the graph/contract). Rescue has five phases; greenfield has seven
  (Frame → Interview → Contract → Build → Validate → Release → Operate & Evolve), the last two
  closing the loop back to the interview via `flip_criteria`. Persisting between phases is what
  makes the context reset possible — never design a phase that relies on another's in-memory session.
- **Modes select scope up front.** Rescue: `rescue` (default) · `align` · `audit` · `resume`.
  Greenfield: `forge` (default) · `spec` · `slice` · `decide` · `evolve`.
- **Each skill has a core cross-layer module** built on the shared field-shape engine
  (`core/shape-engine.md`): rescue's `contract-reconciliation` **diffs** field shapes across
  DB↔ORM↔API↔frontend to find drift; greenfield's `contract-propagation` **generates** those layers
  from one contract so they cannot drift. Read the relevant playbook in full before touching it.
- **The interview funnel, the brainstorm, contract-testing, and the feedback loop are shared**
  (`core/interview-funnel.md`, `core/brainstorm.md`, `core/contract-testing.md`,
  `core/feedback-loop.md`): same machinery, different direction (rescue reconciles/finds; greenfield
  generates/prevents). The feedback loop (`flip_criteria` → reopen) is what closes the lifecycle.
- **Cross-cutting doctrines are shared too** (`core/static-analysis.md`, `core/knowledge-sources.md`,
  `core/assumptions.md`): how to use static tools well (type-checkers / LSP / architecture-fitness,
  in-loop, deterministic findings skipping fp-check — and *authoring the spec so the strongest signal
  applies*); which external knowledge source per phase (Context7 / DeepWiki / registry / web), with
  grounding, confidence, and untrusted-input discipline; and how an agent surfaces its **own** forced
  assumptions as vetoable pins instead of encoding them silently (the anti-slop rule turned on the
  agent itself).
- **The shared `core/` is a single authoring source, vendored into each skill (Model B).** All the
  shared modules above are authored once under `core/*.md` (the edit point), but each skill keeps its
  **own copy** under `skills/<skill>/references/core/x.md` so it is self-contained (independently
  installable — no skill ever points outside its own tree at `core/`). `scripts/sync_core.py`
  materializes those copies (following the `core→core` dependency closure) and rewrites the pointers;
  its `--check` mode (in CI) fails if any copy drifts. Two rules keep the surface lean: inside
  `core/*.md`, only **load-bearing** dependencies are backticked pointers (see-also mentions stay
  plain text, so the closure — and each helper's vendored set — stays minimal), and every copy is
  stamped with a `GENERATED FILE — do not edit` banner. Plugin-root adapters (`agents/`,
  `commands/`, `hooks/`) may point at `core/` directly — they never ship standalone. This is the very anti-divergence property the
  skills enforce on codebases, applied to the skills' own shared prose — the linter, not discipline,
  keeps the copies identical.

## Packaging (agent-agnostic)

Authored once to the Anthropic Agent Skills spec (`skills/<name>/SKILL.md`; `name` matches the
dir, `description` ≥ 20 chars), then wrapped by thin per-platform adapters — no skill content
duplicated:
- **Claude Code**: `.claude-plugin/{plugin.json,marketplace.json}`, `agents/*.md`,
  `hooks/hooks.json`, `commands/*.md`, auto-discovered from the plugin root (`source: "./"`).
- **opencode**: `opencode.json` (enables `opencode-skills`, defines the `agent` roster, loads
  `AGENTS.md`), `.opencode/command/*.md`, `scripts/install-opencode.sh` (links `.opencode/skills`).
- **Any AGENTS.md-aware agent** (Codex, Cursor, …): root `AGENTS.md`.

`core/agents.md` is the roster source of truth; `agents/*.md` (Claude) and `opencode.json`'s
`agent` block must mirror it — `check_consistency.py` enforces roster parity and validates the
packaging manifests are valid JSON. Full details: `docs/packaging.md`.

## Editing conventions & invariants

- **The consistency gates are enforced in CI — keep them green.**
  `check_consistency.py` validates **every skill and the shared core**: every module in each
  `modules.json` has a `reference` that exists; every `` `references/…md` `` pointer in a `SKILL.md`
  resolves relative to that skill's root (this now includes the vendored `` `references/core/…md` ``);
  **no skill file points at the source directly** (a bare `` `core/…md` `` under `skills/` is an error
  — vendor it); and no skill content file still contains `STUB — scaffold only`.
  `sync_core.py --check` verifies each vendored `references/core/x.md` still equals its `core/x.md`
  source, and `verify_pointers.py` checks every cross-reference resolves. When you add or rename a
  module, update its `modules.json` **and** its playbook **and** any `SKILL.md` pointer together.
- **Path convention:** `references/x.md` is skill-root-relative (rescue's root is
  `skills/codebase-rescue/`, greenfield's is `skills/greenfield-forge/`), and this **includes the
  vendored `references/core/x.md` copies**. A file that points at another skill's playbook uses the
  full repo-root-relative `skills/<skill>/references/x.md` path — those deliberate cross-skill links
  are the only pointers that leave a skill's own tree.
- **Sources of truth:** each skill's `modules.json` is authoritative for its module catalog;
  `core/*.md` is the single authoring source for the shared doctrine — **edit it there, never in a
  `references/core/` copy**, then run `scripts/sync_core.py` (the copies are generated). Within that,
  `core/decisions-ledger-spec.md` (v0.6) is authoritative for the ledger schema. Do not let a
  `SKILL.md`, a reference summary, or a vendored copy drift from them.
- **`core/decisions-ledger-spec.md` is the authoritative schema** (English, like the rest of the
  repo); `core/ledger.md` is the short English pointer summary to it.
- **Read the relevant reference before executing or editing a phase/module — do not work from
  memory.** `SKILL.md` states this as a rule, and the playbooks carry detail that `SKILL.md`
  deliberately omits.
- Runtime artifacts (`ledger.json`, `graph.json`, `*.skill`, `.audit/`, `docs/audits/`) are
  gitignored — the skill generates them; they are never authored or committed here.
