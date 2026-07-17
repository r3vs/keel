# Phase 7 — Operate & Evolve (run, observe, feed back)

The closing phase, and the one that makes a forged project **never "done"**: run the released
system so it is observable, then feed production signals back into the ledger so decisions made on
thin early information can be reopened when reality diverges. Two parts — Operate produces the
signals; Evolve acts on them.

The **codebase-facing slice** is in; the SRE *practice* is out. In: the instrumentation the code
emits, the SLO definitions, the signal manifest. Out: on-call rotation, incident command, paging,
capacity planning as an ops function.

## Operate — make the system observable (mostly Wave-1 paved road, made explicit)

From the observability decisions (a decided NFR in Phase 2), the code emits:
- **Instrumentation** (`BuildItem action: instrument`): structured logs, metrics, traces, and
  health / readiness endpoints — carried in the code, not bolted on.
- **SLO definitions** as artifacts (`configure`): the targets the system is held to.
- **The signal manifest** (`configure`): the map from each decision's `flip_signal.signal` to a
  real telemetry source (a metric query, a log filter, a trace attribute, an incident label, or a
  `manual_checkpoint`). **This is the physical anchor of the feedback arc** — without it, the
  arc has no inputs, which is why this slice is a precondition of Evolve, not an extra.

## Evolve — turn the loop (via the shared feedback loop)

Run `references/core/feedback-loop.md`: evaluate the `flip_signal`s against the manifest's telemetry, and on
a fired signal emit a `ReopenEvent` and move the affected pin (plus its genuine dependents) back
to `needs_input` (`reopened`). The reopened pins flow into the interview via `slice` mode; the
new truth then flows forward through contract → build → validate → release again. The arc
**reopens, never decides** — neutrality holds exactly as in the brainstorm.

Cadence is the `evolve` mode: a scheduled run or an incident-triggered one, each a fresh
invocation reading the ledger + manifest from disk.

## Why this closes the loop

`gap = diff(to_be, as_is)` re-opens here. A forged project's as-is met its to-be at v1 (gap = 0)
— but the *world* moves, and a `flip_signal` firing is the observable proof that an elected truth
no longer fits. Reopening the pin re-creates a gap, on purpose, and the machine closes it again.
The ledger becomes a **living ADR** that knows when it is stale, and the same `ledger.json` is the
audit baseline `codebase-rescue` can diff against — the two skills meeting at the loop's seam.

## Guardrail

Operate emits signals and defines SLOs; it does not run the on-call practice. Evolve reopens
pins; it does not decide them. Reopen the **minimum** — the fired pin and genuine dependents, never
the whole ledger. Degrade a signal with no telemetry to a manual checkpoint; never fabricate a
reading.

## Output

An instrumented system, SLO definitions, a signal manifest wired to the telemetry, and — when
signals fire — `ReopenEvent`s that turn the loop back to the interview.
