---
name: static-first-analysis
description: Use the strongest deterministic static signal before model judgment, and in-loop on the diff — type-checkers/compilers, LSP/SCIP navigation, and architecture-fitness / dependency-constraint checks. Deterministic findings carry high confidence and skip the false-positive gate. Use when analyzing, refactoring, or validating code.
disable-model-invocation: true
license: MIT
---

# Static-First Analysis

The static-analysis doctrine (`references/core/static-analysis.md`) as an invokable skill. Static signal is
cheap, deterministic, and high-confidence — reach for it before model judgment, and run it in-loop.

## The high-value signals
- **Type-checkers / compilers** (`tsc --noEmit`, mypy/pyright, `cargo check`, `go vet`) — a type
  error is a fact, tied to contracts and logic; carries `extracted` confidence and skips fp-check.
- **LSP / SCIP** — precise defs/refs/call-hierarchy and safe rename; more reliable than an inferred
  graph for navigation and blast-radius.
- **Architecture-fitness** (import-linter, dependency-cruiser, ArchUnit, ts-arch) — enforce the
  elected boundaries; a violation is a `design_concern` (rescue) or a CI gate (greenfield).

## How to use it well
- **In-loop, not just batch**: run on the diff as you edit, via the language server where possible.
- **Confidence from determinism**: deterministic findings skip the heavy fp-check — reserve that
  budget for the judgment findings that actually need it.
- **Degrade gracefully**: no checker for a language → fall back to grep/graph and note the gap.

## When a whole RULE keeps being wrong

`findings_gate` judges one finding at a time and is blind to the pattern that actually poisons a
stream: a rule that is wrong over and over, every instance individually plausible. Record each
verdict with `generator_observe` (`confirmed` / `refuted` — silence is never confirmation), then run
`generator_screen` to route by measured precision.

A rule below the declared bar is **muted, loudly**: its findings still appear, carrying the
precision that muted them, and one confirmed finding moves the ratio back. A signal that vanishes
silently is worse than a noisy one, because at least the noise tells you it is there.
