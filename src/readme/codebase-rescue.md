# codebase-rescue

**The curative half of Keel.** Point it at an existing, misaligned, often AI-generated codebase and
it reconciles backend, frontend and database into an aligned state — by extracting what the code
*is*, making you elect what it *should be*, and closing the difference one pinned item at a time.

```bash
/plugin install codebase-rescue@keel
```
```text
> this codebase is a mess — the frontend, backend and DB don't agree. rescue it.
```

`keel-core` follows automatically (the MCP server, the agent roster, the hooks). On **Codex**,
install it explicitly — Codex has no dependency resolution.

---

## What it's actually for

Your contract says `role` is `admin | member`. Your database enum only has `admin`.

Nothing crashes. No linter fires. Each layer type-checks **against itself**. Then someone invites a
teammate, Postgres rejects the INSERT, and the agent that wrote both sides cheerfully builds the
next feature on top of the lie.

That is **drift** — it lives *between* files, and every tool you own works inside one.

---

## The one idea

```
gap = diff(to-be, as-is)
```

- **as-is** — what the code actually is. **Extracted, never guessed.**
- **to-be** — what it should be. Derived from decisions **you elect in an interview**, never
  reverse-engineered from the code. (Code that is wrong describes itself perfectly.)

Rescue runs that diff **backward**: the as-is already exists, so derive the to-be, then close the
gap. Its sibling `greenfield-forge` runs it forward. Same spine, same ledger file.

Contract mismatches, dead code, wrong logic, missing work and design concerns are all the same
object — which is why there is deliberately **no taxonomy to memorise**.

---

## Modes — pick the scope up front

| Mode | What runs | Use when |
|---|---|---|
| **`rescue`** *(default)* | all five phases | the codebase is messy or half-finished |
| **`align`** | Phase 1 + contract reconciliation + interview on the mismatches | fastest path to "make the layers agree" |
| **`audit`** | findings only — no interview, no remediation | a finished app; you just want the report |
| **`resume`** | like `rescue`, weighted toward `incompleteness` | *"what's stubbed vs missing vs done — what next?"* Also the entry point when a live system's `flip_criteria` fire |
| **`understand`** | **Phase 1 only**, comprehension as the *deliverable* | learning / onboarding onto an unfamiliar codebase |

`understand` deserves the distinction: it stops at the **as-is**. No interview, no `to_be`, no
roadmap, no remediation. Findings, if run at all, are neutral map annotations — never a backlog.
`audit` reports problems; `understand` teaches you how the system fits together.

```text
> /rescue align
> /rescue understand
> /rescue learn:deep
```

**Learning layer** — orthogonal to the mode. With `keel-kit` installed, every phase explains the
*why* behind each choice so your elected `to_be` is better-informed. It runs at `guided` by default;
`learn:<level>` sets only the **intensity** (`essential` · `guided` · `deep`) — a volume, not an
on/off, so no setting silently drops the coaching. Explanations *accompany* delivery and never
delay it.

---

## The five phases

Each phase is a **separate invocation with a fresh context**, talking only through artifacts on
disk. Nothing depends on the agent remembering anything. Ctrl-C at any point; resume tomorrow.

### Phase 1 — Comprehend (build the as-is)
A navigable, **visual-first** map of what the code is now, with problems pinned on it.

1. Build the tree-sitter-native knowledge graph — DB schema as nodes, spans DB↔API↔frontend, stable
   node ids with source locations and `EXTRACTED` / `INFERRED` / `AMBIGUOUS` confidence tags.
2. Generate the as-is wiki: architecture map, ER diagram, contract-diff panels, sequence diagrams,
   hotspot heatmap. Text is minimal and on demand, behind each pin.
3. Run the deterministic finding tools and the analysis modules into one normalized SARIF/JSON
   stream.
4. Materialize each finding as a **pin**, anchored to graph nodes and **clustered**, so N instances
   of one decision collapse into one.

You review *pins*, never the whole wiki. Attention scales with the number of problems, not the size
of the codebase.

### Phase 2 — Interview (elect the to-be)
The compression funnel is **mandatory** — a naive one-question-per-finding interview is a failure:

```
pins → clusters → policies → real questions (asked) → proposed defaults (skim in bulk)
```

- **Policy questions first** (4–5, highest leverage): category rules that auto-resolve whole
  clusters — *"the DB is source of truth for schema mismatches unless noted"*. Cascading a policy
  still emits user-originated decisions, just amplified.
- **Exception questions**: only the pins policies don't cover, plus genuine ambiguity.
- **Proposed defaults**: everything else, skimmed in bulk, overridden by exception.
- **Hard rule**: `blocker` / `high` pins **never** go to silent default.
- Questions are ordered by **information gain** — those that collapse the most downstream pins go
  first.

200 findings typically compress to **~10 real questions**.

`design_concern` pins are **options, not findings** — *"leave as-is"* is a legitimate answer.
Asserting a design opinion as a defect would reintroduce the vibecoding failure mode inside the
auditor.

**Then the challenge pass.** A read-only `challenger` red-teams what you just elected: an oracle
that is unfalsifiable, self-contradictory, unsatisfiable or resting on an undeclared assumption is
worse than none — it fossilizes. A sustained refutation reopens the pin *before* anything is built
on it. It challenges; it never decides.

### Phase 3 — Diff & roadmap
Compute the gap per pin, then sequence by `depends_on` (topological), then by severity. The order is
**not hardcoded** — *"align contracts before fixing logic"* falls out of the graph.

### Phase 4 — Remediation loop (TDD-driven, restartable)
A loop over the **roadmap**, not over "all findings" — a loop that empties the findings list touches
everything and regenerates slop. Each item runs in a fresh invocation loading only that item, its
pin, the graph neighborhood and its tests.

**Two-track TDD**, with tests coming from the ledger rather than invented:
- **Track A — test-from-`to_be` (red → green)** for decision-bearing items. The red test *encodes*
  the elected `to_be` and must kill mutants to count. That same test is the Phase-5 oracle.
- **Track B — characterization test (already green)** for behavior-preserving work. Proves you
  didn't break what worked. Never apply red-TDD to structure-only changes.

The **ponytail ladder** picks the smallest intervention that works and logs the rung — for slop,
rung 2 means consolidating onto a canonical copy, never adding an N+1th.

Then **two gates, in a fixed order: evidence, then judgment.** The evidence gate (Phase 5) is
deterministic and cheap, so it runs first and a change that doesn't close the gap never costs review
judgment. The two-stage review runs second and reads that record rather than re-deriving it — what
it adds is the part evidence cannot see: is the criterion satisfied **honestly**, or special-cased
into passing? A pin resolves only on evidence **and** a `MERGE`.

**Wave checkpoints**: it pauses at each roadmap wave boundary — especially Wave 1, contracts — for
human review. If aligning contracts revealed that an elected truth was wrong, that evidence goes to
the `challenger`, which owns the one reopen path there and records the argument. **It never runs
fully autonomous end-to-end.**

### Phase 5 — Validate (data decides)
A fix is not done because the build is green. The gap must be shown closed with kind-specific
evidence: re-diff the contract shapes at the anchors, re-query the graph, confirm the Track-A test
kills mutants. Read-only verdict, run by a role that did not write the code — the executor's "it
passes" is a claim to check, never evidence. On failure the item returns to Phase 4 as a local
retry, not a global restart.

---

## The 28 analysis modules

Phase 1 runs a catalog, not an ad-hoc read. Each module declares its `type` — and `deterministic`
is a **promise**: it names the engine that produces the finding.

**Cross-layer & contract** — `contract-reconciliation` (the core engine: field shapes diffed across
DB↔ORM↔API↔frontend) · `design-alignment` (the same diff on the rendered UI — fonts, colors, radii,
a11y — against an elected `DESIGN.md`) · `docs-claims` (docs treated as claims; the dangling ones
are flagged).

**Comprehension** — `graph-build` · `graph-query` · `guided-tours` · `explain-node` · `layered-map` ·
`domain-entrypoints` · `wiki-asis` · `incremental-fingerprint` (the resume baseline) · `diff-impact`.

**Correctness & security** — `security-sast` · `secrets` · `dependencies` · `type-check` ·
`test-validity` · `logic-correctness` *(judgment)*.

**Health & maintainability** — `architecture-fitness` (elected boundaries as executable constraints)
· `complexity` · `duplication` · `dead-code` · `hotspots-coupling` · `placeholder-stub` ·
`coverage` (which analyses **did not run** — the anti-overclaim module).

**Judgment layer** — `completeness` (stubbed vs missing vs done) · `fp-check` (the false-positive
gate — which deterministic findings **skip**) · `interview-generator`.

---

## The guardrails, stated plainly

- **No code edits before Phase 2 elects the to-be.** This is enforced by a `PreToolUse` hook from
  `keel-core`, not by a paragraph asking nicely.
- **No agent commits a decision.** Only your committed interview answer elects anything.
- **Forced to assume?** The agent must surface the assumption as a **vetoable pin** rather than
  encode it silently. On a vague prompt, high effort means making the gaps explicit — not guessing
  confidently.
- **Every decision carries `flip_criteria`** — the condition under which it reopens itself later.
- **`resolved` means observed**, not "the code was written".

---

## What it produces

| Artifact | What it is |
|---|---|
| `ledger.json` | the append-only single source of truth — every pin, decision and event |
| `graph.json` | the structural graph, with stable node ids and source locations |
| the visual map | a self-contained HTML map of the ledger, pins anchored on the architecture |
| the as-is wiki | visual-first: architecture, ER, contract-diff panels, hotspots |
| the roadmap | sequenced `RemediationItem`s, each pointing back at its pin |

All of it is gitignored by design — it is generated, never authored.

---

Sibling: [`greenfield-forge`](https://github.com/r3vs/keel/tree/main/plugins/greenfield-forge) — the
same machinery run forward, for a project that doesn't exist yet. A forged project's ledger becomes
the audit baseline a rescue can diff against years later. Same file, not two products.

Repo and architecture: [github.com/r3vs/keel](https://github.com/r3vs/keel) · MIT.
