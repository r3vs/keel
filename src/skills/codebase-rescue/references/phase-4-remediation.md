# Phase 4 — The Remediation Loop (do the minimum that works, TDD-driven)

Execute the roadmap as a restartable, context-resetting loop. This phase writes code, so it is
the most dangerous: on slop there are few tests protecting the little behavior that works, and
rewriting is how you regenerate slop. Discipline over cleverness.

## What the loop consumes (this is a guardrail, not a detail)

The loop consumes the **ordered roadmap from Phase 3** — the `RemediationItem`s derived from
`decided` pins with a `to_be`. It does **NOT** consume "all findings." Deferred
`incompleteness`, `accepted` `design_concern`s, and low-confidence proposed-defaults the user
accepted are NOT in the loop by definition. A loop that runs until the findings list is empty
is a loop that touches everything — that is how you regenerate slop. Consuming the roadmap, not
the findings, is the difference between a rescue and a rewrite wearing automation as a costume.

Item order = the Phase-3 topology. "Contracts before logic" falls out of the DAG; the loop does
not re-decide order.

> **Ask for the order — never reconstruct it.** `build_waves` levels the `depends_on` DAG and
> returns the waves plus what is actionable *right now*. Reading the roadmap and picking what looks
> next is how an item gets built ahead of the decision it depends on, which is the one mistake this
> phase cannot absorb. Without the MCP server: `python scripts/runtime/buildloop.py <ledger>`.

## Context management: reset, don't accumulate

The state-of-the-art way to handle a codebase too large to hold in context is not a smarter
loop — it is a **more forgetful** one. Each iteration is a **fresh invocation** that loads only:
the item, its pin, the relevant graph neighborhood (queried, not read file-by-file), and the
two test tracks. No history of prior iterations in context. All state lives on disk — the
append-only ledger, the tests written, the graph — never in the window.

Because the ledger is append-only and materialized on disk, the loop is **restartable**: if it
crashes or a session ends, it resumes from the first non-`resolved` item with zero rework. On a
large codebase that resilience is not a luxury.

## The two-track TDD protocol (the core of this phase)

Classic red→green→refactor assumes you know what the code should do. On slop you don't — that
is what the ledger's `to_be` election solved. So the tests come from the ledger, and there are
**two tracks with opposite jobs**. Confusing them is an error.

### Track A — Test-from-`to_be` (red → green)
For items that carry a decision: `align`, `implement`, and wrong-logic `refactor`.
- Write a failing test that **encodes the elected `to_be`**. This test IS the executable form
  of the decision the user made in the interview. (Closes the loop: comprehension → decision →
  test → fix → validation, all against the same artifact.)
- To count, the test must **kill the relevant mutants** — a green test that survives mutation
  did not constrain the elected behavior; it is theater. (Phase 5 checks this.)
- Implement the minimum that turns it green.

### Track B — Characterization test (already green)
For items that must NOT change behavior: `consolidate`, structural `refactor`, and `delete`
(of confirmed-dead code).
- Before touching working code, capture its current observable behavior in a test. Not because
  the behavior is right — because it is your proof you didn't break it.
- The change keeps this test green. If it goes red, you changed behavior you were only supposed
  to restructure — stop.

### Choosing the track (do not apply red-TDD to structure-only work)
| Action                  | Track |
|-------------------------|-------|
| `align` (contracts)     | A (+ B to protect surrounding callers) |
| `implement` (a gap)     | A |
| `refactor` (wrong logic)| A |
| `consolidate` (dupes)   | **B only** — you are not changing what it does |
| `refactor` (structure)  | **B only** |
| `delete` (dead code)    | B (nothing downstream should change) |

Applying a red test to a consolidation would force you to invent a spec for code that only
needed de-duplicating. Track B is the correct discipline there.

## The ponytail ladder (inside "implement the minimum")

Once a test defines the target, the ladder decides the *smallest* intervention, and the rung is
logged on the item:

```
1 YAGNI (delete) · 2 consolidate onto canonical (never an N+1th copy) · 3 stdlib ·
4 native platform · 5 installed dependency · 6 one line · 7 minimum that works
```
Rung 2 is the slop amendment: "reuse" = de-duplicate-and-canonicalize; `canonical_target`
records which copy became truth; call sites rewrite to it; divergent copies are deleted.

## The per-item loop

```
for item in roadmap.ordered_item_ids:      # fresh invocation each
  1. load item + pin + graph neighborhood + to_be     # minimal context
  2. if touching working code → Track B characterization test
  3. if item has a decision → Track A red test from to_be
  4. implement the minimum that passes; ladder decides how; log the rung
  5. two-stage review: (a) spec compliance vs to_be → (b) code quality
        verdict MERGE | ADJUST | REJECT ; ADJUST/REJECT restart THIS item
  6. Phase 5 validates on evidence (see phase-5-validate.md) → pin.state = resolved
     on failure: item returns here with failing evidence (not a global restart)
  7. clear context → next item
```

## Static signal, in-loop (not just the Phase-1 batch)

Run the deterministic static checks **on the diff, as you edit** — the type-checker,
LSP-assisted refactor, and architecture-fitness — not only in the Phase-1 scan. A type error or a
boundary violation caught in-loop is fixed before the two-stage review, at `extracted` confidence
and without spending fp-check budget. See `references/core/static-analysis.md`.

## Ground fixes in current sources

When a fix touches a library, dependency, or CVE, ground it via `references/core/knowledge-sources.md` —
Context7 for the dependency's current API, the registry / advisory for the safe version and the
migration path — rather than training-cutoff memory. Cited, with confidence set by the source; the
fix still passes the two-stage review and Phase-5 evidence gate.

## Wave checkpoints (do not run fully autonomous end-to-end)

Stop at each wave boundary from the Phase-3 roadmap — especially after **Wave 1
(truths & contracts)** — for a human checkpoint before proceeding:
- Surface the aligned state to the user.
- Re-validate downstream `depends_on` assumptions. Aligning the contracts sometimes reveals an
  elected truth was wrong; you only see it once the aligned contracts run. If so, **reopen the
  dependent pins** (back to `needs_input`) rather than building on a bad foundation.
- Re-run the **`challenger`** (`references/core/agents.md`) on the wave's decisions — the same
  upstream arc as Phase 2, now armed with build evidence. Building can expose an oracle as
  `unsatisfiable` (the elected shape can't meet what the code really needs) or resting on an
  `unstated_assumption` visible only now. A sustained `ChallengeEvent` reopens the pin (`challenged`)
  before the next wave compounds the error (`references/core/decisions-ledger-spec.md` v0.6). Distinct
  from a fired `flip_criteria`: that is production falsifying a decision *downstream*; this is the
  build falsifying the oracle *at the boundary*.

A fully autonomous start-to-finish loop on slop is over-confident. A loop that pauses at
dependency (wave) boundaries is cautious at exactly the right points.

## Output
The change, both test tracks, and the updated ledger (`status`, `ladder_rung`,
`canonical_target`, validation evidence).
