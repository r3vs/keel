---
name: codebase-rescue
description: >-
  Rescue a misaligned, often AI-generated codebase — reconcile backend, frontend and database
  into one aligned state. Trigger on: "this codebase is a mess", "the
  frontend and backend don't match", "pick up where I left off", "make this production-ready",
  "review my whole app", vibecoded, slop, half-finished. Prefer it to ad-hoc file reading across
  layers.
---

# Codebase Rescue

## What this is

A workflow for turning a large, misaligned, possibly unfinished codebase — the typical output of
agentic "vibecoding" — into an aligned, intentional, state-of-the-art one. It is NOT primarily a
bug/vulnerability scanner (those are the commoditized, easy part). Its center of gravity is
**architectural and cross-layer design**: wrong design choices, wrong logic, contradictory or
improvable specs, and backend/frontend/DB that drifted apart.

It works on **unfinished** codebases. It must never treat "not built yet" as "broken".

### The one idea that organizes everything

You cannot audit slop against its own code or its own docs — the code is the thing that is wrong,
and the found docs are stale or aspirational. So the skill builds two separate artifacts and diffs
them:

- **as-is** — what the code actually is now (descriptive; may faithfully describe a mess).
- **to-be** — what each part *should* be in its finished, correct state (normative). This is NOT
  extracted from the code. It is **derived from decisions the user elects** in a targeted interview.

> **Everything the skill "finds" is a delta: `gap = diff(to-be, as-is)`.** The remediation roadmap
> *is* that diff, sequenced by dependencies. This subsumes contract mismatches, dead code, wrong
> logic, missing work, and design concerns under one principle — so there is no need for a closed
> taxonomy of problems.

### The single source of truth: the decisions ledger

The three surfaces (map/wiki, interview, brainstorm) hold NO state of their own. They all read and
write one `ledger.json`. This is what stops three agents discussing the same problem from diverging
— the exact failure mode being cured in the codebase. Read `references/core/ledger.md` (shared with
the `greenfield-forge` sibling) before writing anything that touches pins, questions, decisions, or
policies.

## Before you act

Read `references/guardrails.md` first — the rules that are cheap to violate fast, the prerequisites
and how they degrade, and the learning-layer, which only the **operator** can compose
(`learn:<level>` sets its intensity, never whether it runs). It is short, and it is the file that
stops the auditor reproducing the failure it was hired to find.

## Modes

Select scope up front; when unsure, ask once with 2–3 options rather than assuming.

| Mode | Scope |
|---|---|
| **`rescue`** (default) | the full five phases below — for messy/unfinished codebases |
| **`align`** | Phase 1 + the cross-layer contract module + an interview on the resulting mismatches. Fastest path to "make the layers agree" |
| **`audit`** | findings only (defects/security/health): no interview, no remediation. For a finished app where the user wants a report |
| **`resume`** | `rescue` weighted toward `incompleteness` — what is stubbed vs missing vs done, and what to build next. Also the entry point for pins the shared feedback loop reopened when a live system's `flip_criteria` fired (`references/core/feedback-loop.md`) |
| **`understand`** | **Phase 1 only**, and comprehension is the *deliverable*, not a step: the layered as-is map + dependency-ordered guided tours + explain-a-node + a query surface over the graph, for learning/onboarding. Stops at the as-is — no interview, no `to_be`, no roadmap, no remediation. Findings, if run, are neutral map annotations, never a backlog |

`audit` reports problems; `understand` teaches how the system fits together. When the request is
`understand`, read "Comprehension as an end" in `references/phase-1-comprehension.md` before
starting — the two modes share Phase 1 and differ in what they are allowed to produce.

## The five phases

Each phase is a **separate invocation** with a fresh context. Phases communicate ONLY through
artifacts on disk (the ledger, the wiki, the graph). This is deliberate: comprehension, finding,
and fixing each saturate context differently, so they must not share a session. Persisting between
phases is what makes the context reset possible.

### Phase 1 — Comprehension (build the as-is)

Goal: a navigable, **visual-first** map of what the code is now, with problems pinned on it. The
user reviews *pins*, never the whole wiki; attention scales with the number of problems, not the
size of the codebase.

1. Build the knowledge graph with the tree-sitter-native `build_graph` tool — the backbone, no
   external install, DB schema as nodes, DB↔API↔frontend spans, stable ids and EXTRACTED /
   INFERRED / AMBIGUOUS confidence tags. Cross-layer edges are INFERRED hints; the contract module
   computes field-level shape diffs itself.
2. Generate the as-is wiki (architecture map, ER diagram, contract-diff panels, sequence diagrams,
   hotspot heatmap). Text is minimal and on-demand behind each pin. Do NOT produce a wiki that
   reads as prose to be read start-to-finish.
3. Run the deterministic finding tools and the analysis modules (`modules.json`). Emit one
   normalized findings stream (SARIF/JSON).
4. Materialize each finding as a `Pin` anchored to graph nodes and clustered (`cluster_id`), so N
   instances of one decision collapse to one.

Full procedure: `references/phase-1-comprehension.md`. Read `references/contract-reconciliation.md`
**in full** whenever the work touches more than one layer — it is the cross-layer engine and the
most verifiable part of the skill.

### Phase 2 — Interview (elect the to-be)

Goal: resolve the pins that need human judgment into a validated to-be spec, **without drowning the
user in questions**. The interview is not a script; it is a filtered view of pins in state
`needs_input`, driven entirely by what Phase 1 surfaced.

The compression funnel is mandatory — a naive one-question-per-finding interview is a failure:

```
pins → clusters → policies → real questions (asked) → proposed defaults (skim in bulk)
```

One question per `cluster_id`; **policy questions first** (4–5, highest leverage — each accepted
rule becomes a `Policy` through `ledger_record_policy`, which cascades in the same call); then
exceptions the policies do not cover, plus genuine `ambiguity` and `design_concern` pins;
everything else gets a low-confidence proposed default the user skims in bulk. Order `asked`
questions by **information gain**. Hard rule: `blocker`/`high` pins NEVER go to silent default.
`design_concern` pins are OPTIONS, not findings — "leave as-is" is a legitimate answer, and
asserting a design opinion as a defect reintroduces the vibecoding failure mode inside the auditor.

Full procedure: `references/phase-2-interview.md`; the shared mechanism is
`references/core/interview-funnel.md`. After the interview commits, the read-only `challenger`
red-teams the freshly elected `to_be`s and a sustained `ChallengeEvent` reopens the pin *before*
Phase 4 builds on it (`references/core/agents.md`).

### Phase 3 — Diff & roadmap (derive the work)

Compute `gap = diff(to-be, as-is)` per pin, then sequence remediation by `depends_on`
(topological), then by severity. The dependency order is not hardcoded — "align contracts before
fixing logic" falls out of the graph. Output: a sequenced roadmap of `RemediationItem`s, each
pointing back to its pin.

Then **write the elected to-be into the repo's `AGENTS.md`** with `generate_instructions` (plus the
`CLAUDE.md` bridge — Claude Code does not read `AGENTS.md`). No host loads `ledger.json`; without
the carrier every Phase-4 executor starts from the blank slate that produced the mess. See
`references/phase-3-roadmap.md`, and `references/core/instruction-files.md` when the repo already
has an `AGENTS.md` you must not disturb.

### Phase 4 — Remediation loop (TDD-driven, restartable)

A restartable, context-resetting loop over the **Phase-3 roadmap** — NOT over "all findings". A
loop that empties the findings list touches everything and regenerates slop. Each item runs in a
**fresh invocation** loading only the item, its pin, the graph neighborhood and its tests; all
state is on the append-only ledger, so the loop resumes from the first non-`resolved` item after
any interruption.

Two-track TDD, and the tests come from the ledger rather than being invented: **Track A**
(test-from-`to_be`, red→green) for decision-bearing items, where the red test encodes the elected
`to_be` and must kill mutants; **Track B** (characterization, already green) for behavior-preserving
items. Never apply red-TDD to structure-only work. Each item then passes **two gates in a fixed
order — evidence, then judgment**, and pauses at every roadmap wave boundary for human review.
Never run fully autonomous end-to-end. Read `references/phase-4-remediation.md` before the first
item — it carries the ponytail ladder, the gate order and the wave-checkpoint rule in full.

### Phase 5 — Validate (data decides) — the loop's evidence gate

Step 5 of the loop, and the **first** gate on a finished item. A fix is not done because the build
is green. Validate the gap closed with kind-specific evidence: re-diff contract shapes at the
anchors, re-query the graph, confirm the Track-A test kills mutants. Read-only verdict — never
guesses, never writes. **Evidence is necessary, not sufficient**: `pin.state = resolved` needs this
evidence, *and* a MERGE, *and* a `verification.rung` of `observed` or `cross_derived` — and
`mcp:ledger_resolve` refuses without the third. On failure the item returns to Phase 4, a local
retry rather than a global restart. See `references/phase-5-validate.md`.

## Brainstorm (parallel, on-demand)

At any point the user can pin a problem and open a brainstorm on it. The agent loads full context
for that one pin and proposes 2–3 options with tradeoffs, disciplined by the ponytail ladder and
referencing how well-architected codebases solve that specific problem. It writes to
`pin.brainstorm.proposals[]` and **never** commits a decision — only the interview does. See
`references/core/brainstorm.md`.

## Read this when

Read the relevant file before executing a phase or module — do not work from memory. Each row is a
**condition**, not a topic: the playbooks carry detail this file deliberately omits.

| When | Read |
|---|---|
| before acting, in any mode | `references/guardrails.md` |
| before writing anything that touches pins, questions, decisions or policies | `references/core/ledger.md` |
| running Phase 1, or `understand` mode | `references/phase-1-comprehension.md` |
| the work touches more than one layer (DB ↔ ORM ↔ API ↔ frontend) | `references/contract-reconciliation.md` |
| a UI is rendered and its tokens/fonts/colors/radii must match an elected `DESIGN.md` | `references/module-design-alignment.md` |
| a UI claim needs to be *observed* in a real browser before a pin resolves | `references/browser-verification.md` |
| reviewing or challenging how a UI *looks*, as judgment rather than as drift | `references/core/design-taste.md` |
| installing or normalizing the deterministic finding tools | `references/toolchain.md` |
| running the interview | `references/phase-2-interview.md` · `references/core/interview-funnel.md` |
| diffing field shapes, or deciding whether two types are equivalent | `references/core/shape-engine.md` |
| pinning a reconciled boundary so it cannot silently drift again | `references/core/contract-testing.md` |
| sequencing the roadmap, or writing the `AGENTS.md` carrier | `references/phase-3-roadmap.md` · `references/core/instruction-files.md` |
| running the remediation loop | `references/phase-4-remediation.md` |
| deciding whether an item's gap actually closed | `references/phase-5-validate.md` |
| a static tool could answer this before a model does | `references/core/static-analysis.md` |
| a claim depends on a library/framework fact not in this repo | `references/core/knowledge-sources.md` |
| under-specified input is forcing you to assume something | `references/core/assumptions.md` |
| opening a brainstorm on a hard pin | `references/core/brainstorm.md` |
| fanning out work, or choosing who may write | `references/core/agents.md` |
| a live system's `flip_criteria` fired and pins came back | `references/core/feedback-loop.md` |
| you need the module catalog: phase, tools, pin `kind`, deterministic vs judgment | `modules.json` |
