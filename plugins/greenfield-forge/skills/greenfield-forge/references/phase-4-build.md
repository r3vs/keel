# Phase 4 — The Build Loop (do the minimum that works, TDD-driven)

Execute the Phase-3 backlog as a restartable, context-resetting loop. This is rescue's remediation
loop run forward: instead of closing a gap on existing code, each iteration **builds** what a
decision committed to. It writes code, so the same discipline applies — the danger here is not
breaking working code (there is little yet) but **building ahead of the decisions**, which is how
slop is born in the first place.

## What the loop consumes (a guardrail, not a detail)

The loop consumes the **ordered backlog from Phase 3** — `BuildItem`s derived from `decided` pins
with a `to_be`. It does NOT consume "everything the app could have." `deferred` pins and the long
tail the user never scoped in are not in the loop by definition. A loop that builds until it runs
out of ideas is a loop that generates slop. Consuming the backlog, not your imagination, is the
difference between forging and vibecoding with extra steps.

Item order = the Phase-3 topology. "Contract before client" falls out of the DAG; the loop does
not re-decide order.

> **Ask for the order — never reconstruct it.** `build_waves` levels the `depends_on` DAG and
> returns the waves plus what is actionable right now. Eyeballing the backlog is how a slice gets
> built before the contract it consumes.

## Context management: reset, don't accumulate

Each iteration is a **fresh invocation** loading only: the item, its pin and `to_be`, the contract
carrier, and its tests. No history of prior iterations in context. All state lives on the
append-only ledger on disk, so the loop is **restartable** — after any interruption it resumes
from the first non-`resolved` item with zero rework.

**Checkpoint on a *measured* context budget, not a feeling.** If a single slice saturates context,
hand off — write state to the ledger and start fresh for the remainder — rather than push into a
degraded window. The trigger is measured (the harness's live context measure crossing a budget
calibrated by the `spend` telemetry), never a vibe. A checkpoint on evidence is the reset working, not
a failure.

## Two-track TDD — Track A is primary here

The tests come from the ledger's `to_be`, not from invention. Two tracks, opposite jobs:

### Track A — Test-from-`to_be` (red → green) — the main track
For every decision-bearing item (`implement`, and `wire` where behavior is asserted):
- Write a failing test that **encodes the elected `to_be`**. This test IS the executable form of
  the decision the user made in the interview. In greenfield this is the *normal* case — nearly
  every feature is built this way.
- To count, the test must **kill the relevant mutants** (Phase 5 checks this); a green test that
  survives mutation constrained nothing.
- Implement the minimum that turns it green.

### Track B — Characterization (already green) — only when extending
Applies only when a later wave **touches an already-built slice** — capture the built behavior
first, keep it green through the change. In a from-scratch v1 this track is rare; it grows in
importance once `slice` mode extends a live system (and it is where the handoff to rescue begins).

## The ponytail ladder = YAGNI by construction

Once a test defines the target, the ladder picks the *smallest* intervention and logs the rung:

```
1 YAGNI (don't build it) · 2 reuse/generate from the contract (never a hand-duplicated shape) ·
3 stdlib · 4 native platform · 5 installed dependency · 6 one line · 7 minimum that works
```

Rung 1 is the whole point of greenfield: the cheapest feature is the one a decision did not ask
for and you therefore do not build. Rung 2 is "generate it from the carrier" — the anti-drift
default. Never build past what the item's `to_be` requires. When a rung reaches an installed
dependency (rung 5), generate against its **current** API via Context7 (`references/core/knowledge-sources.md`),
not training-cutoff memory.

## The per-item loop

```
for item in roadmap.ordered_item_ids:      # fresh invocation each
  1. load item + pin + to_be + contract + tests     # minimal context
  2. if extending an already-built slice → Track B characterization test
  3. if item has a decision → Track A red test from to_be
  4. build the minimum that passes; ladder decides how; log the rung
  5. two-stage review: (a) spec compliance vs to_be → (b) code quality
        verdict MERGE | ADJUST | REJECT ; ADJUST/REJECT restart THIS item
  6. Phase 5 validates on evidence (see phase-5-validate.md) → pin.state = resolved
     on failure: item returns here with failing evidence (not a global restart)
  7. clear context → next item
```

## Static signal, in-loop

Run the **type-checker** and **architecture-fitness** on the diff as you build
(`references/core/static-analysis.md`). Generating layers from the contract means the type-checker catches a
contract violation before any test runs; a boundary-constraint violation fails fast. Deterministic,
`extracted` confidence, no fp-check budget spent.

## Wave checkpoints (do not run fully autonomous end-to-end)

Stop at each wave boundary — especially after **Wave 1 (contract & paved road)** — for a human
checkpoint:
- Run the generated layers end-to-end; confirm the contract holds and the drift-check is green.
- Re-validate downstream `depends_on` assumptions. **Building sometimes falsifies a decision** you
  made on thin information — the elected shape turns out wrong once real code runs against it. When
  it does, the pin's `flip_criteria` has fired: **reopen the dependent `open_decision` pins** (back
  to `needs_input`) rather than building on a foundation you now know is wrong. This is the loop's
  self-correction, and it is why greenfield is not fire-and-forget.
- Re-run the **`challenger`** (`references/core/agents.md`) on the wave's decisions — the Phase-2
  upstream arc, now with build evidence. It is cheapest to catch an `unsatisfiable` `to_be` or an
  `unstated_assumption` here, before the contract propagates it into another layer; a sustained
  `ChallengeEvent` reopens the pin (`challenged`) (`references/core/decisions-ledger-spec.md` v0.6).
  A `flip_criteria` firing is production falsifying a decision downstream; a `ChallengeEvent` is the
  build falsifying the oracle at the boundary — same reopen, opposite end of the lifecycle.

A fully autonomous idea-to-app loop is how you get confident slop. A loop that pauses at wave
boundaries is cautious at exactly the dependency points that matter.

## Output

The built slice, both test tracks where they apply, and the updated ledger (`status`,
`ladder_rung`, `contract_carrier`, validation evidence). The to-be map's nodes for this slice flip
ghost→solid.
