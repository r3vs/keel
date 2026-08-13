---
name: greenfield-forge
description: >-
  Start a NEW project aligned from the first commit: elect the design in an interview before any
  code exists, then generate every layer from one contract. Trigger on "I want to build X",
  greenfield, a new app / SaaS / service / CLI, "design the architecture before I code", "scaffold
  a new codebase", "set this up properly from day one", "help me decide the stack".
---

# Greenfield Forge

## What this is

The forward mirror of `codebase-rescue`. Rescue is **curative** — it reconciles an existing,
misaligned, often AI-generated mess. Greenfield Forge is **preventive** — it builds a new project
aligned from the first commit, so the slop never accrues. Same engine, opposite direction, same
center of gravity: **architectural, cross-layer design** — data model, module boundaries, the
contracts between backend / frontend / DB — decided deliberately instead of emerging by accident.
NOT a scaffolding generator that dumps a template; the template is the commoditized, easy part.

### The one idea that organizes everything

Same invariant as rescue: **`gap = diff(to-be, as-is)`.** What changes is where you start:

- **as-is** — what is built so far. In greenfield it starts **empty** and grows.
- **to-be** — what each part should be. It is **elected up front** in a decision interview, derived
  from the user's choices, never invented by the model.

> The gap is the **build backlog**, sequenced by dependencies. As slices complete, `as-is` grows to
> meet `to-be` and the gap converges to zero. A finished v1 is `gap = 0`.

Because the to-be is recorded as you decide it, the project carries its own `ledger.json` — the
living record of *why it is the way it is*, each decision tagged with the condition that would
reopen it (`flip_criteria`). That is precisely the artifact rescue wishes it had: a forged project
can later be audited against its **own recorded decisions**, never against stale docs. And the loop
closes on itself — Phase 7 reopens a decision when production diverges from it.

### The single source of truth: the decisions ledger

Same shared ledger as rescue (English pointer `references/core/ledger.md`; authoritative schema
`references/core/decisions-ledger-spec.md`). The three surfaces — the design map, the interview, the
brainstorm — hold NO state of their own; they all read and write one `ledger.json`: the same
anti-divergence property the skill enforces on the code it builds, enforced from the start so it
never has to be recovered. Read `references/core/ledger.md` before writing anything that touches
pins, questions, decisions, or build items.

## Before you act

Read `references/guardrails.md` first — the rules that are cheap to violate fast, plus the
prerequisites and how they degrade. They bite earlier here than in rescue: the first speculative
file, the first silently-invented decision, is where a project starts becoming a rescue.

## Modes

Select scope up front; when unsure, ask once with 2–3 options rather than assuming.

| Mode | Scope |
|---|---|
| **`forge`** (default) | Phases 1–6: idea → aligned scaffold + first vertical slice → first release |
| **`spec`** | Phases 1–3 only: the design, the contract and the sequenced backlog; stop before building. For users who will build it themselves or hand it to another agent |
| **`slice`** | take an already-committed ledger and build/extend ONE vertical feature (Phases 3–5 on a subset). How a forged project continues after v1 — and the bridge to rescue |
| **`decide`** | just the interview, to resolve a specific set of open decisions and record them with `flip_criteria`, no scaffolding. *"Help me make these architecture decisions properly."* |
| **`evolve`** | the feedback loop on a live project: evaluate `flip_signal`s against production telemetry, reopen the pins whose criteria fired, hand them back to the interview. Scheduled or incident-triggered (`references/phase-7-operate-evolve.md`) |

## The seven phases

Each phase is a **separate invocation** with fresh context, communicating ONLY through artifacts on
disk (the ledger, the design map, the contract). Same rule as rescue: persisting between phases is
what makes the context reset possible — never design a phase that relies on another's in-memory
session. Phases 1–5 build v1; Phases 6–7 ship it and feed production back into the ledger.

### Phase 1 — Frame (materialize the open decisions)

Turn a vague brief into concrete, answerable forks — **NOT** an open-ended "tell me about your app"
chat. That chat is the slop seed: it lets the model fill unmade decisions with silent assumptions.

Four steps: classify the project type to **prune** the decision-catalog (a CLI skips
rendering/client; a static site skips persistence); expand `references/decision-catalog.md` against
the brief into one `open_decision` pin per fork, `depends_on` wired from the catalog and related
forks clustered; record the brief's **givens** as pre-committed `DecisionEvent`s (`source: brief`)
with `flip_criteria`, so nothing already decided is re-asked; and seed the skeletal **to-be map** as
ghost nodes with the completeness traffic-light all-red by design.

Phase 1 also pins the **outcomes** (acceptance criteria) that root the whole dependency DAG. Read
`references/threat-model.md` in this phase whenever the project handles user data, authentication,
payments or anything network-reachable — security is designed in here, not scanned for later. Full
procedure: `references/phase-1-frame.md`.

### Phase 2 — Interview (elect the to-be)

Resolve the `open_decision` pins into a committed spec using the shared compression funnel
(`references/core/interview-funnel.md`). Policy questions first — architectural defaults like
"prefer boring/proven tech", "server-render unless interactivity demands a SPA", "one datastore
until proven otherwise", "no service split in v1" — then the genuine forks, ordered by **information
gain**: domain model and persistence first (they fan out to everything), delivery and observability
last. Open a brainstorm (`references/core/brainstorm.md`) on the hard forks.

Every committed answer emits a `DecisionEvent` with `flip_criteria` — essential here, because you
decide *before* you know the app. Two tools commit: `ledger_record_decision` for one fork,
`ledger_record_policy` for an accepted architectural default. Neither can elect; they record what
the user chose. Then a **challenger** pass (`references/core/agents.md`) red-teams the elected
decisions, and a sustained `ChallengeEvent` reopens the pin *before* Phase 3 turns it into contract
and backlog — it challenges, never decides. `references/phase-2-interview.md`.

### Phase 3 — Contract & roadmap (derive the build)

1. **Define the cross-layer contract ONCE and propagate it.** Author the shared contract (a
   shared-types package, or OpenAPI / JSON-schema / protobuf for a polyglot stack) as the single
   source of truth, then **generate** every layer from it — DB schema, ORM model, API DTO/route
   stubs, client types. Drift is impossible by construction, and the same shape-diff installs as a
   CI check so no future hand-edit can break alignment. Read `references/contract-propagation.md`
   before authoring it, and `references/design-propagation.md` as well whenever a UI is rendered.
2. **Sequence the backlog.** Emit `BuildItem`s from decided pins, ordered by `depends_on`. The waves
   fall out of the DAG (contract & data model → paved road → core slices → secondary features →
   polish), not hardcoded — same as rescue. Build thin **vertical slices**, one feature end-to-end
   through all layers, so there is always a running system
   (`references/phase-3-contract-roadmap.md`).
3. **Write the elected design into the file agents actually load.** `generate_instructions` projects
   the ledger into a managed region of the project's `AGENTS.md` (plus the `CLAUDE.md` bridge, since
   Claude Code does not read `AGENTS.md`) and marks the generated layers never-hand-edit. Paved road,
   not release step: Phase 4 runs every `BuildItem` in a **fresh context**, so an executor inherits
   the decisions only if the carrier already holds them (`references/core/instruction-files.md`).

### Phase 4 — Build loop (TDD-driven, restartable)

A restartable, context-resetting loop over the **Phase-3 backlog** — NOT "build everything you can
think of". Each `BuildItem` runs in a fresh invocation loading only the item, its pin, the contract
and its tests; all state is on the append-only ledger, so the loop resumes from the first
non-`resolved` item after any interruption.

Two-track TDD, with **Track A (test-from-`to_be`, red→green) as the PRIMARY track**: a red test
derived from the decision, written before implementation. Track B (characterization) applies only
when EXTENDING a built slice. The **ponytail ladder** enforces YAGNI *by construction* — only the
minimum a decision committed to, and log the rung. Each item passes **two gates in a fixed order —
evidence, then judgment**, and pauses at every wave boundary, especially after Wave 1. If building
revealed a decision was wrong, hand that evidence to the **`challenger`**, which owns the one reopen
path there: the *upstream* arc, where the oracle was never satisfiable, as distinct from a fired
`flip_criteria`, which is production falsifying a sound decision. Never fully autonomous
end-to-end. Read `references/phase-4-build.md` before the first item.

### Phase 5 — Validate (data decides) — the loop's evidence gate

Step 5 of the loop, and the **first** gate on a finished item. A slice is not done because the build
is green. Re-extract the shapes across the generated layers and confirm **zero drift**; the Track-A
test kills mutants; the behavior is reachable from an entry point; the paved road runs. Read-only
verdict — never guesses, never writes. **Evidence is necessary, not sufficient**: `pin.state =
resolved` needs this evidence, *and* a MERGE, *and* a `verification.rung` of `observed` or
`cross_derived` — `mcp:ledger_resolve` refuses without the third. On failure the item returns to
Phase 4. Resolved slices flip ghost→solid and the gap shrinks toward zero
(`references/phase-5-validate.md`).

### Phase 6 — Release (ship the slice safely)

The **codebase-facing slice** of release (migration scripts, version, changelog, feature-flag code,
rollback), not the CD platform. Migrations follow **expand/contract** (zero-downtime by
construction); the changelog is projected from the ledger; the deploy strategy runs as config plus a
runbook; a tested **rollback** is mandatory. Never release on an unmade decision
(`references/phase-6-release.md`).

### Phase 7 — Operate & Evolve (run, observe, feed back)

**Operate** emits the instrumentation (logs/metrics/traces/health), the SLO definitions, and the
**signal manifest** mapping each `flip_signal` to real telemetry — the physical anchor of the
feedback loop. **Evolve** runs that loop (`references/core/feedback-loop.md`): a fired `flip_signal`
emits a `ReopenEvent` and moves the affected pins back to `needs_input`, handing them to the
interview via `slice`. The arc **reopens, never decides** — which is what makes a forged project
never "done", and its `ledger.json` the audit baseline rescue can later diff against
(`references/phase-7-operate-evolve.md`).

## Brainstorm (parallel, on-demand)

Shared with rescue (`references/core/brainstorm.md`). On any hard fork the user can open a
brainstorm that proposes 2–3 designs with tradeoffs, disciplined by the ponytail ladder and
referencing how well-architected systems solve that problem. It writes `proposals[]`; only the
interview commits.

## Read this when

Read the file before executing its phase or module — do not work from memory. Each row is a
**condition**, not a topic: the playbooks carry detail this file deliberately omits.

| When | Read |
|---|---|
| before acting, in any mode | `references/guardrails.md` |
| before writing anything that touches pins, decisions or build items | `references/core/ledger.md` |
| framing a brief into forks | `references/phase-1-frame.md` · `references/decision-catalog.md` |
| the project handles user data, auth, payments, or is network-reachable | `references/threat-model.md` |
| running the interview | `references/phase-2-interview.md` · `references/core/interview-funnel.md` |
| authoring the cross-layer contract, or generating a layer from it | `references/contract-propagation.md` |
| a UI is rendered and its tokens must not drift | `references/design-propagation.md` |
| deciding whether two field shapes are the same shape, or pinning a generated boundary so a hand-edit cannot silently break it | `references/core/shape-engine.md` · `references/core/contract-testing.md` |
| sequencing the backlog, or writing the `AGENTS.md` carrier | `references/phase-3-contract-roadmap.md` · `references/core/instruction-files.md` |
| running the build loop, then deciding whether a slice actually holds | `references/phase-4-build.md` · `references/phase-5-validate.md` |
| shipping a slice: migrations, versioning, rollback | `references/phase-6-release.md` |
| instrumenting, or a `flip_signal` fired | `references/phase-7-operate-evolve.md` · `references/core/feedback-loop.md` |
| a static tool could answer this before a model does, or the claim depends on a library fact not in this repo | `references/core/static-analysis.md` · `references/core/knowledge-sources.md` |
| the brief is silent and you are about to assume something | `references/core/assumptions.md` |
| opening a brainstorm on a hard fork, or fanning out work and choosing who may write | `references/core/brainstorm.md` · `references/core/agents.md` |
| you need the module catalog: phase, produces, deterministic vs judgment | `modules.json` |
