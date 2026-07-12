---
name: greenfield-forge
description: >-
  Start a NEW project the right way — turn an idea into an aligned, intentional, state-of-the-art
  codebase so it never needs rescuing. Use this whenever the user is beginning something from
  scratch: "I want to build X", a new app / SaaS / service / CLI, a "greenfield" project, "design
  the architecture before I code", "scaffold a new codebase", "set this up properly from day one",
  or "help me decide the stack / data model / API". It elects the to-be (the design) in a
  compressed decision interview BEFORE any code exists, defines the cross-layer contract once and
  generates aligned layers from it, then builds thin vertical slices test-first. Prefer this over
  ad-hoc scaffolding or jumping straight to code for anything that will outlive a throwaway
  script. Its sibling `codebase-rescue` handles the opposite end — cleaning up an existing mess.
---

# Greenfield Forge

## What this is

The forward mirror of `codebase-rescue`. Rescue is **curative** — it takes an existing,
misaligned, often AI-generated mess and reconciles it. Greenfield Forge is **preventive** — it
builds a new project aligned and intentional from the first commit, so the slop never accrues.
Same engine, opposite direction along the project lifecycle.

Its center of gravity is the same as rescue's: **architectural, cross-layer design** — the data
model, the module boundaries, the contracts between backend / frontend / DB — decided
deliberately instead of emerging by accident. It is NOT a scaffolding generator that dumps a
boilerplate template; the template is the commoditized, easy part.

### The one idea that organizes everything

Same invariant as rescue: **`gap = diff(to-be, as-is)`.** What changes is where you start:

- **as-is** — what is built so far. In greenfield it starts **empty** and grows.
- **to-be** — what each part should be. It is **elected up front** in a decision interview,
  derived from the user's choices, never invented by the model.

> The gap is the **build backlog**, sequenced by dependencies. As slices complete, `as-is` grows
> to meet `to-be` and the gap converges to zero. A finished v1 is `gap = 0`.

Because the to-be is recorded as you decide it, the project carries its own `ledger.json` — the
living record of *why it is the way it is*, each decision tagged with the condition that would
reopen it (`flip_criteria`). That is precisely the artifact rescue wishes it had: a forged
project can later be audited against its **own recorded decisions**, not against stale or
aspirational docs. The two skills are two ends of one lifecycle, joined by the ledger. And the
loop closes on itself: Phase 7 reopens a decision when production diverges from it (`flip_criteria`
firing), so the gap re-opens on purpose and the machine closes it again.

### The single source of truth: the decisions ledger

Same shared ledger as rescue (English pointer `core/ledger.md`; authoritative schema
`core/decisions-ledger-spec.md`). The three surfaces — the design map, the interview, the
brainstorm — hold NO state of their own; they all read and write one `ledger.json`. This is the
same anti-divergence property the skill enforces on the code it builds, enforced here from the
start so it never has to be recovered. Read `core/ledger.md` before writing anything that touches
pins, questions, decisions, or build items.

## Prerequisites

Python and Node assumed (as in rescue). Run `scripts/bootstrap.sh` once for the shared toolchain;
greenfield uses a **generation-focused subset** (tree-sitter / ast-grep for scaffolding, the
shared-types generators, the CI drift-check) rather than the finding tools — detailed in
`references/contract-propagation.md`. Degrade to model judgment when a tool is missing; never
hard-fail on a missing binary.

## Modes

Select scope up front; when unsure, ask once with 2–3 options rather than assuming.

- **`forge`** (default) — all five phases: idea → aligned scaffold + first vertical slice.
- **`spec`** — Phases 1–3 only: produce the design, the contract, and the sequenced backlog;
  stop before building. For users who will build it themselves or hand it to another agent.
- **`slice`** — take an already-committed ledger and build/extend ONE vertical feature (Phases
  3–5 on a subset). This is how a forged project continues after v1 — and the bridge to rescue.
- **`decide`** — run just the interview to resolve a specific set of open decisions and record
  them with `flip_criteria`, no scaffolding. "Help me make these architecture decisions properly."
- **`evolve`** — run the feedback loop on a live project: evaluate `flip_signal`s against
  production telemetry, reopen the pins whose criteria fired, and hand them back to the interview.
  Scheduled or incident-triggered. See `references/phase-7-operate-evolve.md`.

## The seven phases

Each phase is a **separate invocation** with fresh context. Phases communicate ONLY through
artifacts on disk (the ledger, the design map, the contract). Same rule as rescue: persisting
between phases is what makes the context reset possible — never design a phase that relies on
another phase's in-memory session. Phases 1–5 build v1; Phases 6–7 ship it and feed production
back into the ledger, closing the loop.

### Phase 1 — Frame (materialize the open decisions)

Turn a vague brief into concrete, answerable forks — **NOT** an open-ended "tell me about your
app" chat. That chat is the slop seed: it lets the model fill unmade decisions with silent
assumptions. Phase 1 also pins the **outcomes** (acceptance criteria) that root the whole
dependency DAG, and runs the **threat-model** pass (`references/threat-model.md`) so security is
designed in, not scanned for later.

1. Intake the brief; classify the project type to **prune** the decision-catalog (a CLI skips
   rendering/client; a static site skips persistence).
2. Expand the decision-catalog (`references/decision-catalog.md`) against the brief →
   materialize one `open_decision` pin per fork, each with options, downstream implications, and
   `depends_on` wired from the catalog. Cluster related forks.
3. Record **givens** as pre-committed decisions. If the brief already states a choice ("must run
   on-prem", "team knows Postgres"), log it as a `DecisionEvent` (`source: brief`) with
   `flip_criteria` — do not re-ask what is already decided.
4. Seed the skeletal **to-be map**: domain entities and layer lanes as ghost nodes, all
   "planned", decision pins attached. The completeness traffic-light starts all-red by design.

Full procedure: `references/phase-1-frame.md`. Core asset: `references/decision-catalog.md`.

### Phase 2 — Interview (elect the to-be)

Resolve the `open_decision` pins into a committed spec using the shared compression funnel
(`core/interview-funnel.md`). Policy questions first (architectural defaults — "prefer
boring/proven tech", "server-render unless interactivity demands a SPA", "one datastore until
proven otherwise", "no service split in v1"), then the genuine forks, ordered by **information
gain**: domain model and persistence first (they fan out to everything), delivery and
observability last. Open a brainstorm (`core/brainstorm.md`) on the hard forks. Every committed
answer emits a `DecisionEvent` with `flip_criteria` — essential here, because you decide *before*
you know the app. Full procedure: `references/phase-2-interview.md`.

### Phase 3 — Contract & roadmap (derive the build)

Two jobs:

1. **Define the cross-layer contract ONCE and propagate it.** From the decided data model and
   API decisions, author the shared contract (a shared-types package, or OpenAPI / JSON-schema /
   protobuf for a polyglot stack) as the single source of truth, then **generate** aligned
   scaffolds for every layer from it — DB schema, ORM model, API DTO/route stubs, client types.
   Drift is impossible by construction. This is contract-reconciliation run forward, and it
   installs the same shape-diff as a CI check so no future hand-edit can break alignment. See
   `references/contract-propagation.md`.
2. **Sequence the backlog.** Emit `BuildItem`s from decided pins, ordered by `depends_on`. The
   waves fall out of the DAG (contract & data model → paved road → core slices → secondary
   features → polish), not hardcoded — same as rescue. Build thin **vertical slices** (one
   feature end-to-end through all layers), never horizontal layers, so there is always a running
   system. Full procedure: `references/phase-3-contract-roadmap.md`.

### Phase 4 — Build loop (TDD-driven, restartable)

A restartable, context-resetting loop over the **Phase-3 backlog** — NOT "build everything you
can think of." Each `BuildItem` runs in a fresh invocation loading only the item, its pin, the
contract, and its tests; all state is on the append-only ledger, so the loop resumes from the
first non-`resolved` item after any interruption.

Two-track TDD, but **Track A (test-from-`to_be`, red→green) is now the PRIMARY track**: every
feature's behavior is a red test derived from the decision, written before any implementation.
Track B (characterization) applies only when EXTENDING an already-built slice (protect what the
last wave built). The **ponytail ladder** enforces YAGNI *by construction*: build only the
minimum a decision committed to — never speculative scaffolding (that is how slop is born); log
the rung. Two-stage review (spec compliance → code quality) gates each item; ADJUST/REJECT
restart it.

**Wave checkpoints**: pause at each wave boundary — especially after Wave 1 (the contract) — run
the generated layers, confirm the contract holds end-to-end, and if building revealed a decision
was wrong, **reopen the dependent `open_decision` pins** (`flip_criteria` fired) instead of
building on a bad foundation. Never run fully autonomous end-to-end. See `references/phase-4-build.md`.

### Phase 5 — Validate (data decides) — the loop's evidence gate

Step 6 of the loop. A slice is not done because the build is green. Validate with kind-specific
evidence: re-extract the shapes across the generated layers and confirm **zero drift** (aligned
by construction); the Track-A test kills mutants; the built behavior is reachable from an entry
point; the paved road actually runs. Read-only verdict — never guesses, never writes. Set
`pin.state = resolved` only on evidence; on failure the item returns to Phase 4 (a local retry).
The convergence check is the completeness traffic-light: resolved slices flip ghost→solid and the
gap shrinks toward zero. See `references/phase-5-validate.md`.

### Phase 6 — Release (ship the slice safely)

Take a validated slice to production safely — the **codebase-facing slice** of release (migration
scripts, version, changelog, feature-flag code, rollback), not the CD platform. Migrations follow
**expand/contract** (zero-downtime by construction); the changelog is projected from the ledger;
the deploy strategy (canary/blue-green) runs as config + a runbook; a tested **rollback** is
mandatory. Never release on an unmade decision. See `references/phase-6-release.md`.

### Phase 7 — Operate & Evolve (run, observe, feed back)

Run the released system so it is observable, then feed production back into the ledger. **Operate**
emits the instrumentation (logs/metrics/traces/health), the SLO definitions, and the **signal
manifest** that maps each `flip_signal` to real telemetry — the physical anchor of the feedback
loop. **Evolve** runs that loop (`core/feedback-loop.md`): when a `flip_signal` fires, it emits a
`ReopenEvent` and moves the affected pins back to `needs_input`, handing them to the interview via
`slice`. The arc **reopens, never decides**. This is what makes a forged project never "done" —
and its `ledger.json` the audit baseline rescue can later diff against. See
`references/phase-7-operate-evolve.md`.

## Brainstorm (parallel, on-demand)

Shared with rescue (`core/brainstorm.md`). On any hard fork the user can open a brainstorm that
proposes 2–3 designs with tradeoffs, disciplined by the ponytail ladder and referencing how
well-architected systems solve that specific problem. It writes `proposals[]`; only the interview
commits.

## Guardrails (read before acting) — the preventive mirror of rescue's

- Never build what no decision committed to. No speculative scaffolding, no "might need it
  later" — that is the origin of slop. Undecided → not built.
- Never let the model invent a product or architecture decision silently. Surface it as an
  `open_decision` pin and elect it in the interview.
- Never phrase a design fork as if one answer is objectively correct. Options with tradeoffs; the
  user elects. Asserting a design opinion as fact is the exact vibecoding failure mode.
- Never skip `flip_criteria` on a decision made with incomplete information.
- Never release without the migration **expand/contract** plan and a tested **rollback** decided.
- Operate emits signals and SLOs; it never runs the on-call practice. Evolve **reopens** pins, it
  never decides them — and reopens the minimum (the fired pin + genuine dependents).
- Never hand-author the same field shape in two layers. Generate every layer from the one
  contract, or you have reintroduced the drift rescue exists to cure.
- Never run the build loop fully autonomous end-to-end. Wave checkpoints, especially after the
  contract wave.
- Prefer the strongest static signal (type-checker, architecture-fitness) before model judgment,
  run it in-loop, and enforce the elected boundaries in CI; deterministic findings skip fp-check
  (`core/static-analysis.md`).
- Generate and decide against **current** sources (`core/knowledge-sources.md`) — Context7 for a
  library's real API, DeepWiki for exemplars — not stale memory; cite, tag confidence, treat as untrusted.
- Never hard-fail on a missing tool. Degrade to model judgment and note the gap.
- The interview is a compressed walk over the decision-catalog, never an open "tell me about your
  app" script.

## Reference index

Read the relevant file before executing a phase or module — do not work from memory.

Shared core (used by both skills):
- `core/ledger.md` — the shared decisions-ledger schema (authoritative). Read first.
- `core/interview-funnel.md` — the shared compression funnel.
- `core/shape-engine.md` — the shared field-shape descriptor + type-equivalence table.
- `core/contract-testing.md` — runtime contract tests generated from the carrier.
- `core/feedback-loop.md` — the shared closing arc (observe → reopen).
- `core/static-analysis.md` — type-checkers / LSP / architecture-fitness, in-loop; boundaries in CI.
- `core/knowledge-sources.md` — Context7 / DeepWiki / registry / web, grounded and cited.
- `core/brainstorm.md` — the shared proposal agent.

Greenfield-specific:
- `references/decision-catalog.md` — the canonical decision space (the core new asset).
- `references/phase-1-frame.md` — brief → acceptance criteria + `open_decision` pins + to-be map.
- `references/threat-model.md` — STRIDE → security `open_decision`s (design-time security).
- `references/phase-2-interview.md` — the funnel applied to design forks.
- `references/contract-propagation.md` — define the contract once, generate aligned layers (core).
- `references/phase-3-contract-roadmap.md` — contract propagation + backlog sequencing.
- `references/phase-4-build.md` — two-track TDD build loop, ladder, wave checkpoints.
- `references/phase-5-validate.md` — evidence-based resolution + convergence check.
- `references/phase-6-release.md` — ship a slice safely (migrations, versioning, rollback).
- `references/phase-7-operate-evolve.md` — instrument, SLOs, signal manifest, and the feedback loop.
- `modules.json` — the module catalog (source of truth): each module's phase, produces, and
  whether it is deterministic or judgment-based.
