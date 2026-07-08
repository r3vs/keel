# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

`codebase-rescue` is a **Claude Code skill**, not a runnable application. The deliverable is
prose that a future Claude instance reads and executes: `SKILL.md` is the orchestrator / entry
point, and `references/*.md` are the per-phase and per-module playbooks it loads on demand. There
is almost no executable code — only two helper scripts (a toolchain installer and a CI
drift-linter). The skill itself is **design-complete but pre-implementation**; `TODO.md` is the
build checklist (start with step 0, the Graphify gating experiment, which decides the shape of the
core engine).

The skill's *runtime* behavior — what it does when invoked on a target codebase — is fully
described in `SKILL.md`. Read it before changing how the skill works. Working on this repo means
editing that design, not running an app.

## Commands

No build step and no test suite exist yet (`evals/evals.json` holds prompts but no assertions).
The only executable checks:

```bash
python scripts/check_consistency.py   # drift-linter — run before calling any doc change done; exits 1 on drift
bash scripts/bootstrap.sh             # install the deterministic toolchain (idempotent, best-effort, never hard-fails)
```

On Windows use `python` (present) and run the `.sh` script from the Bash shell / Git Bash.

## The one idea to hold in your head

Everything the skill produces is a delta: **`gap = diff(to-be, as-is)`**.
- **as-is** = what the code currently is (descriptive; may faithfully describe a mess).
- **to-be** = what it *should* be, **derived from decisions the user elects in an interview** —
  never extracted from the code.

Contract mismatches, dead code, wrong logic, missing work, and design concerns are all unified
under this one principle — which is why there is deliberately no closed taxonomy of problem types.

## Architecture of the skill (this spans several files)

- **The decisions ledger is the single source of truth.** Three surfaces — the visual map/wiki,
  the interview, and the brainstorm — hold *no state of their own*; they all read/write one
  `ledger.json`. This is deliberate: it is the exact anti-divergence property the skill enforces on
  the codebases it rescues. Schema authority: `decisions-ledger-spec.md`; English pointer summary:
  `references/ledger.md`.
- **A `Pin` is a discriminated union on `kind`** (`contract_mismatch | internal_contradiction |
  ambiguity | incompleteness | design_concern | defect | other`). The `kind` constrains the shape
  of the pin's `as_is` / `to_be` / `question` payload.
- **Five phases, each a separate invocation with fresh context**, communicating ONLY through
  on-disk artifacts (the ledger, the wiki, the graph). Persisting between phases is what makes the
  context reset possible — never design a phase that relies on another phase's in-memory session.
- **Modes select scope up front:** `rescue` (default, all five phases), `align` (contracts only),
  `audit` (findings only, no interview), `resume` (weighted toward incompleteness).
- **`contract-reconciliation` is the core module** — the cross-layer engine that diffs field-level
  shapes across DB↔ORM↔API↔frontend. Read `references/contract-reconciliation.md` in full before
  touching it.

## Editing conventions & invariants

- **The three-way sync is enforced by the drift-linter — keep it green.**
  `check_consistency.py` requires: every module in `modules.json` has a `reference` file that
  exists; every `` `references/…md` `` pointer in `SKILL.md` resolves; no `references/*.md` is
  orphaned (warning); no file still contains `STUB — scaffold only`. So when you add or rename a
  module, update `modules.json` **and** its playbook **and** any `SKILL.md` pointer together.
- **Sources of truth:** `modules.json` is authoritative for the module catalog;
  `decisions-ledger-spec.md` (v0.3) is authoritative for the ledger schema. Do not let `SKILL.md`
  or the reference summaries drift from them.
- **`decisions-ledger-spec.md` is written in Italian** — the rest of the repo is English, and
  `references/ledger.md` is the short English pointer to it. Preserve that split unless asked to
  translate.
- **Read the relevant reference before executing or editing a phase/module — do not work from
  memory.** `SKILL.md` states this as a rule, and the playbooks carry detail that `SKILL.md`
  deliberately omits.
- Runtime artifacts (`ledger.json`, `graph.json`, `*.skill`, `.audit/`, `docs/audits/`) are
  gitignored — the skill generates them; they are never authored or committed here.
