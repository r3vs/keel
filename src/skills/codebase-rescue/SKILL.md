---
name: codebase-rescue
description: >-
  Rescue and elevate a whole codebase — especially large AI-generated / "vibecoded"
  ones — by reconciling backend, frontend, and database into an aligned, state-of-the-art
  state. Use this whenever the user wants to audit, rescue, resume, clean up, or "save" a
  codebase; whenever they mention slop code, a messy/abandoned/half-finished project,
  layers that are not aligned or contradict each other, or turning a prototype into
  something production-grade. Trigger even when the user only says things like "review my
  whole app", "the frontend and backend don't match", "pick up where I left off", "this
  codebase is a mess", or "make this production-ready" — do not wait for the word "audit".
  Prefer this skill over ad-hoc file reading or generic security review for anything that
  spans multiple layers or the codebase as a whole.
---

# Codebase Rescue

## What this is

A workflow for turning a large, misaligned, possibly unfinished codebase — the typical
output of agentic "vibecoding" — into an aligned, intentional, state-of-the-art one. It is
NOT primarily a bug/vulnerability scanner (those are the commoditized, easy part). Its
center of gravity is **architectural and cross-layer design**: wrong design choices, wrong
logic, contradictory or improvable specs, and backend/frontend/DB that drifted apart.

It works on **unfinished** codebases. It must never treat "not built yet" as "broken".

### The one idea that organizes everything

You cannot audit slop against its own code or its own docs — the code is the thing that is
wrong, and the found docs are stale or aspirational. So the skill builds two separate
artifacts and diffs them:

- **as-is** — what the code actually is now (descriptive; may faithfully describe a mess).
- **to-be** — what each part *should* be in its finished, correct state (normative). This
  is NOT extracted from the code. It is **derived from decisions the user elects** in a
  targeted interview.

> **Everything the skill "finds" is a delta: `gap = diff(to-be, as-is)`.** The remediation
> roadmap *is* that diff, sequenced by dependencies. This subsumes contract mismatches,
> dead code, wrong logic, missing work, and design concerns under one principle — so there
> is no need for a closed taxonomy of problems.

### The single source of truth: the decisions ledger

The three surfaces (map/wiki, interview, brainstorm) hold NO state of their own. They all
read and write one `ledger.json`. This is what stops three agents discussing the same
problem from diverging — the exact failure mode being cured in the codebase. The ledger
schema is authoritative: see `references/core/ledger.md` (shared with the `greenfield-forge` sibling). Read it before writing anything that
touches pins, questions, decisions, or policies.

## Prerequisites

Python and Node are assumed available (the user has accepted this). The skill degrades
gracefully to model judgment when an optional tool is missing — it never hard-fails on a
missing binary.

Run `scripts/bootstrap.sh` once to install the deterministic toolchain (single-binary
Go/Rust tools + a few pip/npm ones). See `references/toolchain.md` for what each tool does
and how findings normalize to SARIF.

## Modes

Select scope up front; when unsure, ask once with 2–3 options rather than assuming.

- **`rescue`** (default) — full five-phase workflow below. For messy/unfinished codebases.
- **`align`** — only Phase 1 + the cross-layer contract reconciliation module + interview
  on the resulting mismatches. Fastest path to "make the layers agree".
- **`audit`** — findings only (defects/security/health), no interview, no remediation. For
  a finished app where the user just wants a report.
- **`resume`** — like `rescue` but weighted toward `incompleteness`: what is stubbed vs
  missing vs done, and what to build next. Also the entry point for pins reopened by the shared
  feedback loop (`references/core/feedback-loop.md`) when a live system's `flip_criteria` fire.

## The five phases

Each phase is a **separate invocation** with a fresh context. Phases communicate ONLY
through artifacts on disk (the ledger, the wiki, the graph). This is deliberate:
comprehension, finding, and fixing each saturate context differently, so they must not
share a session. Persisting between phases is what makes the context reset possible.

### Phase 1 — Comprehension (build the as-is)

Goal: a navigable, **visual-first** map of what the code is now, with problems pinned on
it. The user reviews *pins*, never the whole wiki; attention scales with the number of
problems, not the size of the codebase.

1. Build the knowledge graph (local, multi-language) with Graphify (MIT-licensed backbone;
   models DB schema as nodes and spans DB<->API<->frontend; exports plain NetworkX
   `graph.json` with stable node ids + source locations + EXTRACTED/INFERRED/AMBIGUOUS
   confidence tags; semantic pass can run local via Ollama). This backbone lets later phases
   stay in bounded context. Cross-layer edges are INFERRED hints — the contract module
   computes field-level shape diffs itself. See `references/phase-1-comprehension.md`.
2. Generate the as-is wiki (visual-first: architecture map, ER diagram, contract-diff
   panels, sequence diagrams, hotspot heatmap). Text is minimal and on-demand behind each
   pin. Do NOT produce a wiki that reads as prose to be read start-to-finish.
3. Run the deterministic finding tools (`references/toolchain.md`) and the analysis
   modules (`modules.json`). Emit one normalized findings stream (SARIF/JSON).
4. Materialize each finding as a `Pin` in the ledger, anchored to graph nodes, clustered
   (`cluster_id`) so N instances of one decision collapse to one.

Full procedure: `references/phase-1-comprehension.md`.
Core module: `references/contract-reconciliation.md` (the cross-layer engine — the most
valuable and most verifiable part; read it in full).

### Phase 2 — Interview (elect the to-be)

Goal: resolve the pins that need human judgment into a validated to-be spec, **without
drowning the user in questions**. The interview is not a script; it is a filtered view of
pins in state `needs_input`, driven entirely by what Phase 1 surfaced.

Apply the compression funnel (this is mandatory — a naive one-question-per-finding
interview is a failure):

```
pins → clusters → policies → real questions (asked) → proposed defaults (skim in bulk)
```

1. **Cluster**: one question per `cluster_id`, applied to the group.
2. **Policy questions first** (4–5, highest leverage): category rules that auto-resolve
   whole clusters by default (e.g. "DB is source of truth for schema mismatches unless
   noted"). Each becomes a `Policy` entity; cascading it emits `DecisionEvent`s with
   `source: "policy:<id>"` — still user-originated, just amplified.
3. **Exception questions**: only pins the policies don't cover, plus genuine `ambiguity`
   and `design_concern` pins.
4. **Proposed defaults**: everything else gets a low-confidence proposed resolution the
   user skims in bulk and overrides by exception.
5. **Severity threshold** (hard rule): `blocker`/`high` pins NEVER go to silent default —
   always `asked` or top of the review batch. `medium`/`low` may be `proposed_default`.
6. Order `asked` questions by **information gain** — those that collapse the most
   downstream pins first.

Keep each question short: prompt + 2–3 options. All detail (divergent shapes, anchors,
evidence) lives behind the pin on the map, pulled up on demand. The question is not
detailed; the map is.

`design_concern` pins are OPTIONS, not findings: "leave as-is" (`state: accepted`) is a
legitimate answer, and their `to_be` stays null until the user chooses. Never assert a
design opinion as a defect — that reintroduces the vibecoding failure mode inside the
auditor.

**Challenge pass (after the interview commits).** A `challenger` (`references/core/agents.md`) then
red-teams the freshly elected `to_be`s: an oracle that is unfalsifiable, self-contradictory,
unsatisfiable, or resting on an undeclared assumption is worse than none — it fossilizes. A
sustained `ChallengeEvent` reopens the pin (`challenged`) back into this interview *before* Phase 4
builds on it (`references/core/decisions-ledger-spec.md` v0.6). It challenges, never decides.

Full procedure: `references/phase-2-interview.md`.

### Phase 3 — Diff & roadmap (derive the work)

Compute `gap = diff(to-be, as-is)` per pin, then sequence remediation by `depends_on`
(topological), then by severity. The dependency order is not hardcoded — "align contracts
before fixing logic" falls out of the graph. Output: a sequenced roadmap of
`RemediationItem`s, each pointing back to its pin. See `references/phase-3-roadmap.md`.

### Phase 4 — Remediation loop (TDD-driven, restartable)

A restartable, context-resetting loop over the **Phase-3 roadmap** — NOT over "all findings".
Deferred/accepted/proposed-default pins are not in the loop by definition; a loop that empties
the findings list touches everything and regenerates slop. Each item runs in a **fresh
invocation** loading only the item, its pin, the graph neighborhood, and its tests — all state
is on the append-only ledger on disk, so the loop resumes from the first non-`resolved` item
after any interruption.

**Two-track TDD** (tests come from the ledger, not invented):
- **Track A — test-from-`to_be` (red→green)** for decision-bearing items (`align`, `implement`,
  wrong-logic `refactor`). The red test encodes the elected `to_be`; it must kill mutants to
  count. Same test is the Phase-5 oracle.
- **Track B — characterization test (already green)** for behavior-preserving items
  (`consolidate`, structural `refactor`, `delete`). Proves you didn't break what worked. Never
  apply red-TDD to structure-only work.

Inside "implement the minimum", the **ponytail ladder** decides the smallest intervention and
logs the rung (rung 2 amended for slop = consolidate onto a canonical copy, never an N+1th).
Two-stage review (spec compliance → code quality) gates each item; ADJUST/REJECT restart that
item. **Wave checkpoints**: pause at each roadmap wave boundary (especially Wave 1, contracts)
for human review — if aligning contracts revealed an elected truth was wrong, reopen the
dependent pins instead of building on a bad foundation. Never run fully autonomous end-to-end.
See `references/phase-4-remediation.md`.

### Phase 5 — Validate (data decides) — the loop's evidence gate

Step 6 of the loop. A fix is not done because the build is green. Validate the gap closed with
kind-specific evidence: re-diff contract shapes at the anchors, re-query the graph, confirm the
Track-A test kills mutants (Track-B still green for refactors). Read-only verdict — never
guesses, never writes. Set `pin.state = resolved` only on evidence; on failure the item returns
to Phase 4 (a local retry, not a global restart). See `references/phase-5-validate.md`.

## Brainstorm (parallel, on-demand)

At any point the user can pin a problem and open a brainstorm session on it. The brainstorm
agent loads full context for that one pin and proposes 2–3 options with tradeoffs, each
disciplined by the ponytail ladder and referencing how well-architected codebases solve
that specific problem. It writes to `pin.brainstorm.proposals[]` and **never** commits a
decision — only the interview does. See `references/core/brainstorm.md`.

## Guardrails (read before acting)

- Never treat intentional incompleteness as a defect. `incompleteness` pins with
  `is_intentional_stub: true` render as neutral work items, not errors.
- Never present a design judgment as a finding. Judgments are options with tradeoffs.
- Never let the brainstorm agent commit a decision.
- Never expand scope into a rewrite by default. Minimum change to reach alignment.
- Never generate one question per finding. Cluster → policy → exception → proposed default.
- Prefer the strongest static signal (type-checker, architecture-fitness) before model judgment,
  and run it in-loop; deterministic findings carry `extracted` confidence and skip fp-check
  (`references/core/static-analysis.md`).
- Ground claims in the right external source (`references/core/knowledge-sources.md`) instead of stale memory;
  it feeds proposals, never commits; cite it, tag its confidence, treat it as untrusted input.
- When under-specification forces an assumption, surface it as a vetoable pin
  (`references/core/assumptions.md`) — never encode it silently. Making the gap explicit *is* the
  high-effort response; a confident guess is the low one.
- After the interview, run the `challenger` pass over the elected `to_be`s; a sustained
  `ChallengeEvent` reopens the pin before remediation builds on an unsound oracle
  (`references/core/agents.md`). It challenges, never decides.
- Never hard-fail on a missing tool. Degrade to model judgment and note the gap.

## Reference index

Read the relevant file before executing a phase or module — do not work from memory.

Shared core (used by both skills; see the `greenfield-forge` sibling):
- `references/core/ledger.md` — the decisions-ledger schema (authoritative). Read first.
- `references/core/interview-funnel.md` — the compression funnel (shared mechanism).
- `references/core/shape-engine.md` — the field-shape descriptor + type-equivalence table.
- `references/core/contract-testing.md` — runtime contract tests that pin a reconciled boundary.
- `references/core/feedback-loop.md` — the shared closing arc; can reopen rescue pins when live `flip_criteria` fire.
- `references/core/static-analysis.md` — using type-checkers / LSP / architecture-fitness well, in-loop.
- `references/core/knowledge-sources.md` — Context7 / DeepWiki / registry / web, grounded and cited.
- `references/core/brainstorm.md` — the parallel proposal agent.
- `references/core/assumptions.md` — surface a forced assumption as a vetoable pin, never silently.
- `references/core/agents.md` — the roster (researcher · brainstorm · executor · reviewer · challenger · measurer); the challenger red-teams the elected oracle.

Rescue-specific:
- `references/toolchain.md` — deterministic tools, install, SARIF normalization.
- `references/phase-1-comprehension.md` — graph, wiki, finding, pin materialization.
- `references/contract-reconciliation.md` — the cross-layer engine (core module).
- `references/phase-2-interview.md` — how rescue sources the shared funnel (pins = findings).
- `references/phase-3-roadmap.md` — diff + dependency sequencing.
- `references/phase-4-remediation.md` — the ponytail ladder in practice.
- `references/phase-5-validate.md` — evidence-based resolution.
- `modules.json` — the module catalog (source of truth): each module's phase, tool(s),
  pin `kind` produced, and whether it is deterministic or judgment-based.
