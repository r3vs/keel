<!-- GENERATED FILE - do not edit. Source: src/core/feedback-loop.md at the repo root; regenerate with: python scripts/build.py -->

# The Feedback Loop (shared core) — the lifecycle's closing arc

The arc that turns two open-ended skills into a **closed loop**. Both skills produce a ledger
full of decisions, each carrying a `flip_criteria` — the observable condition under which the
elected truth should be reopened. This module is the **observer that acts on them**: it watches
production, detects fired flip criteria, and reopens the affected pins — handing them back to the
interview (`greenfield-forge slice`) or to `codebase-rescue resume`.

It is shared: a forged project and a rescued one both accumulate flip criteria, and both benefit
from the same watcher. The mechanism reuses machinery that already exists — it adds **no new
decision-making**. Like the brainstorm, it is neutral: it **reopens, it never decides**.

## Inputs

1. **The observable flip criteria.** Every `DecisionEvent` may carry a structured `flip_signal`
   (`references/core/decisions-ledger-spec.md` v0.5): `{ signal, comparator, threshold, window, source }`.
   The prose `flip_criteria` remains the human-readable intent; the `flip_signal` is its
   machine-evaluable form.
2. **The signal manifest.** Produced by the Operate phase (instrumentation + SLO defs): the map
   from each `flip_signal.signal` to a real telemetry source (a metric, a log query, a trace
   attribute, an incident label, or a manual checkpoint).

Without a manifest the loop still runs — every `flip_signal` degrades to a `manual_checkpoint`:
a periodic "did X happen?" asked at a wave boundary or on a schedule. Never a hard fail.

## Procedure

1. **Gather** the `flip_signal`s across all `decided` pins.
2. **Evaluate** each against its telemetry source (or the manual checkpoint). A signal is *fired*
   when the comparator/threshold holds over the window (e.g. `orders p95 > 200ms sustained 7d`).
3. **On a fired signal**, emit an immutable `ReopenEvent` (`source: "feedback:<source>"`) and set
   the pin — and only the genuine dependents that assumed the now-falsified truth — back to
   `needs_input` (state `reopened`). The `ReopenEvent` records *why*, so the interview re-decides
   with the new information rather than from scratch.
4. **Hand off.** Reopened pins flow into the interview: `greenfield-forge slice` for a forged
   project, `codebase-rescue resume` for a rescued one. The elected new truth then flows forward
   through the normal phases (contract → build → validate) — the loop turns.

## Guardrails

- **Reopen, never decide.** The loop emits `ReopenEvent`s and moves pins to `needs_input`. It
  writes no `DecisionEvent`, elects no truth, edits no code. Neutrality is schema-enforced.
- **Reopen the minimum.** Only the pin whose signal fired, plus dependents that genuinely rested
  on the falsified truth (via `depends_on`) — never the whole ledger. A loop that reopens
  everything regenerates churn, the same failure mode the skills cure.
- **Degrade, don't fabricate.** No telemetry for a signal → manual checkpoint. Never invent a
  reading or infer a firing the data doesn't support.
- **Cadence is a mode, not a daemon in-context.** `evolve` runs on a schedule or on an incident;
  each run is a fresh invocation reading the ledger + manifest from disk (same context-reset
  discipline as every other phase).
- **A reopen teaches.** The `ReopenEvent.reason` is written to be read: it names *which class* of
  assumption production falsified and *why the flip criterion was the right tripwire* — not a bare
  "signal fired". Same teach-on-rejection posture as the reviewer/challenger (agents doctrine): the
  observer that reopens also explains, so the loop raises the operator, not just the code.

## Why this is the payoff of `flip_criteria`

The ledger anticipated this arc from v0.1: every decision already declared the condition to
reopen it. The feedback loop is simply the piece that *observes that condition in production*. It
makes the ledger a **living ADR** — one that knows when it is stale — and it is the physical link
from a running system back to the decisions that shaped it: the code diverged from the decision
because reality changed, so reopen. That is what closes the lifecycle into a loop.
