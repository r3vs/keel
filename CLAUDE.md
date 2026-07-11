# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This repository holds **two sibling Claude Code skills**, not runnable applications. The
deliverable is prose that a future Claude instance reads and executes:

- **`codebase-rescue`** (in `codebase-rescue/`) — the **curative** skill: rescue an existing,
  misaligned, often AI-generated codebase. `SKILL.md` + `references/*.md` + `modules.json`.
- **`greenfield-forge`** (in `greenfield-forge/`) — the **preventive** twin: build a NEW project
  aligned from the first commit, so it never needs rescuing. Same file layout under its own dir.
- **`core/`** — the **shared spine** both skills read/write: the decisions-ledger spec, the
  interview funnel, the brainstorm agent, and the field-shape engine. Neither skill duplicates it.

Each skill is **design-complete but pre-implementation**; its `TODO.md` is the build checklist
(each starts with a step-0 gating experiment that decides the shape of its core engine). There is
almost no executable code — only two helper scripts (a toolchain installer and a CI drift-linter).

A skill's *runtime* behavior — what it does when invoked — is fully described in its `SKILL.md`.
Read it before changing how that skill works. Working on this repo means editing that design, not
running an app.

## Commands

No build step and no test suite exist yet (each skill's `evals/evals.json` holds prompts but no
assertions).
The only executable checks:

```bash
python scripts/check_consistency.py   # drift-linter — modules ↔ references ↔ SKILL (both skills + core); exits 1 on drift
python scripts/verify_pointers.py     # intra-playbook cross-reference check (complements the linter); exits 1 on dangling
bash scripts/bootstrap.sh             # install the deterministic toolchain (idempotent, best-effort, never hard-fails)
```

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
  the codebases they touch. Schema authority: `core/decisions-ledger-spec.md` (shared, v0.5);
  English pointer summary: `core/ledger.md`.
- **A `Pin` is a discriminated union on `kind`** (`contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | open_decision | acceptance_criterion |
  other`). The `kind` constrains the shape of the pin's `as_is` / `to_be` / `question` payload.
  `open_decision` (v0.4) is the greenfield fork (nothing built yet); `acceptance_criterion` (v0.5)
  is the testable outcome that roots the dependency DAG.
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
- **Two cross-cutting doctrines are shared too** (`core/static-analysis.md`,
  `core/knowledge-sources.md`): how to use static tools well (type-checkers / LSP / architecture-
  fitness, in-loop, deterministic findings skipping fp-check) and which external knowledge source
  per phase (Context7 / DeepWiki / registry / web), with grounding, confidence, and untrusted-input
  discipline.

## Editing conventions & invariants

- **The three-way sync is enforced by the drift-linter — keep it green.**
  `check_consistency.py` validates **both skills and the shared core**: every module in each
  `modules.json` has a `reference` that exists; every `` `references/…md` `` pointer in a `SKILL.md`
  resolves (relative to that skill's root) and every `` `core/…md` `` pointer resolves (relative to
  the repo root); no reference or core file is orphaned (warning); no skill content file still
  contains `STUB — scaffold only`. When you add or rename a module, update its `modules.json`
  **and** its playbook **and** any `SKILL.md` pointer together.
- **Path convention:** `references/x.md` is skill-root-relative (rescue's root is `codebase-rescue/`,
  greenfield's is `greenfield-forge/`); `core/x.md` is always repo-root-relative and shared. A core
  file that points at one skill's playbook uses the full `<skill>/references/x.md` path.
- **Sources of truth:** each skill's `modules.json` is authoritative for its module catalog;
  `core/decisions-ledger-spec.md` (v0.5) is authoritative for the ledger schema (shared). Do not
  let a `SKILL.md` or a reference summary drift from them.
- **`core/decisions-ledger-spec.md` is written in Italian** — the rest of the repo is English, and
  `core/ledger.md` is the short English pointer to it. Preserve that split unless asked to
  translate.
- **Read the relevant reference before executing or editing a phase/module — do not work from
  memory.** `SKILL.md` states this as a rule, and the playbooks carry detail that `SKILL.md`
  deliberately omits.
- Runtime artifacts (`ledger.json`, `graph.json`, `*.skill`, `.audit/`, `docs/audits/`) are
  gitignored — the skill generates them; they are never authored or committed here.
