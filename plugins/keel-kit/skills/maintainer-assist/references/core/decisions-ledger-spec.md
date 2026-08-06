<!-- GENERATED FILE - do not edit. Source: src/core/decisions-ledger-spec.md at the repo root; regenerate with: python scripts/build.py -->

# Decisions Ledger — Spec v0.16

The ledger is the **single source of truth** that the skill's three surfaces (map/wiki, interview, brainstorm) read and write. None of the three holds state of its own: they all project a view over the ledger. This is what stops three agents talking about the same problem from diverging — i.e. the exact failure mode the skill cures in codebases.

On-disk form: one `ledger.json` in the audit's output directory (portable, git-versionable). Maps 1:1 onto Postgres tables if application-level persistence is needed.

**New in v0.2:** the `Pin` object is now a **strict discriminated union on `kind`** (shared envelope + a `kind`-specific `as_is`/`to_be`/`question` payload), with an open `other` variant as an escape hatch. `DecisionEvent` gains `flip_criteria`.

---

## Entities

- **`Pin`** — the atomic unit: a delta between `as_is` (how it is now) and `to_be` (how it should be), or an ambiguity to resolve before the to-be can even be defined. It is the object pinned on the map and the pivot of an interview question.
- **`Question`** — lives ON the pin. The interview is not a separate list: it is the filtered view of pins in state `needs_input`.
- **`Proposal`** — output of the brainstorm; it writes proposals with tradeoffs, never decides.
- **`DecisionEvent`** — append-only, immutable log of the *why*; now with `flip_criteria`.
- **`SettlementEvent`** (v0.16) — append-only record of a pin leaving the open set through a door that carries **no election**: `resolve` (its authority is an observation) and `correctness_unknown` (its authority is the recorded absence of one). The three elected doors — `decide` · `accept` · `defer` — are recorded by the `DecisionEvent` they already write, which now states which state it produced (`settles_as`). One entry per settlement, never two.
- **`RemediationItem`** — the bridge to Phase 4; records the ponytail ladder rung.

---

## The 9 design decisions that carry the weight

1. **`anchors` is a cross-layer LIST**, not a single pointer. A mismatch is multi-node (a DB column *and* an API field *and* a frontend use). It rests on the knowledge graph's node IDs; each anchor carries a `role` that tells the UI how to render it.
2. **`kind` is a discriminator** that constrains the shape of `as_is`/`to_be`/`question`. A strict union for the known kinds + an open `other`.
3. **The question lives on the pin; the interview is a view** (`state == needs_input`).
4. **The brainstorm writes `proposals[]`, never `decision`.** Neutrality enforced by the schema.
5. **`decision_log` immutable, `pin.state` materialized.** Reconciliation rule: last committed decision wins on state, history preserved.
6. **`depends_on` generates the sequenced roadmap.** "Contracts before logic" falls out of the dependency graph, it is not hardcoded.
7. **`to_be` is DERIVED from decisions, not hand-written.** Roadmap = diff(to_be, as_is).
8. **The ponytail rung is recorded on proposals AND remediation.** Auditable minimalism.
9. **Every decision carries a `flip_criteria`** (idea from agentic-engineering): the observable condition under which the elected truth must be reopened. Stops a decision made on incomplete info from fossilizing.

---

## Shared envelope (all kinds)

```jsonc
{
  "id": "pin_0001",
  "kind": "contract_mismatch",   // discriminator — see variants below
  "title": "string",             // short, for the panel
  "severity": "blocker",         // blocker | high | medium | low
  "confidence": "extracted",     // extracted | inferred | ambiguous
  "provenance": [{ "source": "contract_recon", "detail": "db↔api shape diff" }],
  "anchors": [                   // DECISION 1 — cross-layer list
    { "node_id": "n_412", "layer": "db", "role": "db_source", "loc": "migrations/003.sql:12" }
  ],
  "state": "needs_input",        // detected | needs_input | brainstorming | decided | correctness_unknown | deferred | resolved | accepted
  "verification": null,          // v0.7 — { determinism, rung, evidence[] } | null. Set when a claim is checked.
  "as_is": { },                  // DISCRIMINATED by kind ↓
  "to_be": null,                 // DISCRIMINATED by kind ↓ — derived (Decision 7)
  "question": null,              // Question | null — option shape discriminated by kind
  "brainstorm": null,            // { proposals: [...], notes } | null
  "decision": null,              // { event_id, outcome } | null — only from interview
  "resolution_mode": "asked",    // v0.3 asked | policy_default | proposed_default — and `asked`
                                 // BINDS: no unasked write may settle this pin (v0.16)
  "premortem": null,             // v0.9 — { failure_modes[], guardrails[], abort_criteria[], paper_tigers[] } | null
  "depends_on": [],              // DECISION 6
  "remediation": []              // [ RemediationItem ]
}
```

---

## Variants discriminated by `kind`

### `contract_mismatch` — cross-layer disagreement (verifiable)
```jsonc
"as_is": {                       // maps layer → observed shape
  "db": "role ENUM('admin','user')",
  "api": "role: string",
  "frontend": "role === 'superadmin'",
  "disagreeing_layers": ["frontend"]
},
"to_be": { "shape": "ENUM('admin','user')", "canonical_layer": "db" },
"question": {
  "prompt": "The frontend uses 'superadmin', absent from the DB. What is the intended role set?",
  "options": [                   // candidate-truths derived from the divergent shapes
    { "id": "opt_a", "label": "Only {admin,user} — DB is truth", "implication": "remove the FE check" },
    { "id": "opt_b", "label": "Add superadmin to the schema", "implication": "migration + enum everywhere" }
  ],
  "allow_freeform": true
}
```

### `internal_contradiction` — disagreement within ONE layer (e.g. two auth flows)
```jsonc
"as_is": {
  "variants": [
    { "desc": "JWT on /api/v1", "anchor_ref": "n_501" },
    { "desc": "session cookie on /api/v2", "anchor_ref": "n_777" }
  ]
},
"to_be": { "elected": "n_501", "rationale_ref": "ev_..." },
"question": { "prompt": "...", "options": [ /* the variants as candidates */ ], "allow_freeform": true }
```

### `ambiguity` — multiple truths, must be elected BEFORE the to-be can be defined
```jsonc
"severity": "blocker",           // typically blocks defining the to-be
"as_is": {
  "candidates": [                // no "current": genuinely undecided
    { "interpretation": "orders is in v1 scope", "evidence_ref": "n_...", "confidence": "inferred" },
    { "interpretation": "orders is a future feature", "evidence_ref": "n_..." }
  ]
},
"to_be": { "elected_interpretation": "string" },
"question": { "prompt": "...", "options": [ /* the interpretations */ ], "allow_freeform": true }
```

### `incompleteness` — stub/unfinished: a WORK ITEM, not a defect
```jsonc
"as_is": {
  "present": "route POST /orders defined",
  "missing": "handler body is `pass` / stub",
  "is_intentional_stub": true    // distinguishes from a defect — do not render as an error
},
"to_be": { "behavior_spec": "string (what it must do once complete)" },
"question": {
  "prompt": "Is orders in scope for v1?",
  "options": [
    { "id": "impl", "label": "Implement now" },
    { "id": "defer", "label": "Defer (deferred)" },
    { "id": "drop", "label": "Not needed — remove (YAGNI)" }
  ],
  "allow_freeform": true
}
```

### `design_concern` — an improvable choice: JUDGMENT, not a finding
```jsonc
"as_is": {
  "current_design": "string (description)",
  "concern": "string (why it is suboptimal)"
},
"to_be": null,                   // stays null until decided — it is an OPTION, not a defect
"question": {
  "prompt": "...",
  "options": [                   // often fed by the brainstorm's proposals
    { "id": "keep", "label": "Leave as-is (accepted)" },
    { "id": "prop_1", "label": "Alternative A", "proposal_ref": "prop_1" }
  ],
  "allow_freeform": true
}
// legitimate default resolution: state = "accepted"
```

### `defect` — bug/security/dead-code/duplication: verifiable, often without an interview
```jsonc
"as_is": {
  "description": "SQL injection via string concat",
  "evidence": { "tool": "semgrep", "rule_id": "python.sqli.raw", "loc": "..." }
},
"to_be": { "corrected": "use a parameterized query" },
"question": null,                // usually no question: goes straight to remediation (still gated by the plan)
```

### `other` — open escape hatch (honors "not just a few types")
```jsonc
"kind_detail": "string (what it is)",
"as_is": { },                    // free-form
"to_be": null
```

---

## `Proposal`, `DecisionEvent`, `RemediationItem`

```jsonc
// Proposal (inside pin.brainstorm.proposals[]) — DECISION 4
{ "id": "prop_1", "summary": "string",
  "tradeoffs": { "pros": ["..."], "cons": ["..."] },
  "ladder_rung": 3, "references": ["..."], "effort": "S" }   // S | M | L

// DecisionEvent (inside decision_log[]) — DECISIONS 5 and 9, immutable
{ "id": "ev_0007", "pin_id": "pin_0001", "timestamp": "ISO-8601",
  "outcome": "opt_a",            // option id | freeform
  "rationale": "string",
  "flip_criteria": "if users appear with permissions beyond admin, reopen",  // DECISION 9
  "source": "interview",         // only "interview" commits — WHO was entitled to
  "evidence": "elicited",        // elicited | transcribed | brief | cascaded — HOW the answer got here
  "policy_id": null,             // set iff evidence is "cascaded": WHICH policy produced this
  "settles_as": "decided",       // v0.16 — decided | accepted | deferred: WHICH settled state this
                                 // election produced. Absent on pre-v0.16 events and means "decided"
  "human_answer": "yes, pull the helper out" }   // required when transcribed: the words, verbatim

// SettlementEvent (inside decision_log[]) — v0.16, immutable. ONLY for the doors with no election
{ "id": "stl_0001", "pin_id": "pin_0001", "timestamp": "ISO-8601",
  "door": "resolve",             // resolve | correctness_unknown
  "from_state": "decided",
  "to_state": "resolved",
  "verification_rung": "observed",   // the rung the close rests on; null where there was none
  "policy_hash": null }

// RemediationItem (inside pin.remediation[]) — DECISION 8
{ "id": "rem_0001",
  "action": "align",             // consolidate | implement | refactor | delete | align
  "ladder_rung": 2,
  "canonical_target": "db",      // for consolidate/align: which copy is the truth
  "status": "todo" }             // todo | in_progress | done
```

---

## Lifecycle

```
detected ──(generates question)──▶ needs_input ──(opens brainstorm)──▶ brainstorming
                                     │                                   │
                                     │◀────────(proposals written)───────┘
                                     │
                          (user commits in interview)
                                     ▼
                                  decided ──(spawn remediation)──▶ resolved
                                     │           │        ▲
                              (or deferred /     │        │ (behavior finally observed)
                                  accepted)      ▼        │
                                        correctness_unknown
                                       (work done, correctness NOT establishable)
```

`brainstorming` is transient/optional. `deferred` = out of scope now (YAGNI at the spec level). `accepted` = acknowledged, intentionally left as-is (the legitimate outcome of a `design_concern`). `correctness_unknown` (v0.7) = the work was done and the behavior could **not** be observed with the available evidence — see below.

---

## Ponytail amendment for slop (rung 2)

> **2. Already in the codebase (maybe duplicated)? → consolidate onto ONE canonical copy, don't add an (N+1)-th.**

For this, `RemediationItem` has `action: "consolidate"` and `canonical_target`: the fix records which copy becomes the truth and that the others converge onto it.

---

## v0.3 — Clustering, Policy, resolution_mode (question compression)

The problem: **200 findings are not 200 decisions.** 200 SQL injections are ONE decision; 15 divergent copies of a helper are ONE decision. v0.3 adds the funnel that compresses the questions.

### `cluster_id` on the `Pin`
Pins that share a decision (same kind of mismatch, same duplicated helper, same vuln class) carry the same `cluster_id`. The interview asks **once per cluster** and applies to the group. It is variant-analysis used to dedupe the *questions*, not just the patterns.

### `resolution_mode` on the `Pin`
- `asked` — a real question (ambiguity, design_concern, blocker)
- `policy_default` — resolved by a user-set Policy (passive review)
- `proposed_default` — a low-confidence long-tail guess (skim in bulk, override by exception)

### New entity `Policy`
A category rule the user sets in the interview that auto-resolves matching pins.
```jsonc
{ "id": "pol_schema_truth",
  "applies_to": { "kind": "contract_mismatch" },
  "rule": "DB is the source of truth by default",
  "default_outcome": "db",            // v0.12 — an OPTION ID, offered by the pins it decides
  "set_by": "interview",
  "evidence": "transcribed",          // v0.11 — elicited | transcribed | brief; how the user elected it
  "human_answer": "the DB wins unless I say otherwise",  // required when transcribed, verbatim
  "exceptions": ["pin_0042"] }        // excluded pins that stay `asked`
```
When a Policy cascades over a pin it generates a `DecisionEvent` with `source: "policy:<id>"` pointing back to the user's choice: it stays a **user-originated** decision, only amplified. Neutrality holds (the brainstorm still commits nothing). It cascades over a pin only if that pin's own `question` offers `default_outcome` (v0.12, below); the others are held back and stay `asked`. Both that rule and the threshold above it are one predicate, `Ledger.unasked_verdict` (v0.14) — shared with the only other write that settles a pin nobody was shown, the project brief.

**A `Policy` is also the only shape a cluster-wide answer may take.** `decide()` writes one event for one pin; there is no fan-out flag, because a fan-out has to name the rule it applies and the radius it covers, and that is what this entity is. (v0.14 — it had one, and it bypassed every rule on this page.)

**Elected through `mcp:ledger_record_policy`, which cannot elect one.** A policy decides a whole cluster, so it is held to the discipline a single decision gets and not less: a catalog offer is taken verbatim (`mcp:interview_seed_policies` is what offers them, with the pins each would decide), a policy the offers did not contain must state its rule, scope and outcome and quote the user, and a relayed policy with no quote is refused. Where the host can elicit, the server shows the rule, the outcome it writes *and* the blast radius, and writes only on acceptance. `evidence` on the `Policy` records which of those happened — the same axis as on a `DecisionEvent`, and it belongs here because this is where the human actually answered.

### `evidence` — how the human's answer reached the log (v0.10)

`source` says who was *entitled* to commit, and every writer can claim `interview`. `evidence` says how the answer actually travelled, because the failure modes differ and averaging them would hide the weak one:

- **`elicited`** — the MCP server asked the user through the host and wrote the reply itself (`mcp:ledger_record_decision` on a client that declares the elicitation capability). The agent never held the value, so it could not have invented it.
- **`transcribed`** — an agent relayed what the user said. `human_answer` carries the words verbatim, and is **required**: without a quote, an honest relay and a fabricated one are the same line in the ledger.
- **`brief`** — settled in the project brief at frame time; the brief is the evidence. Which is exactly why it is gated like a cascade (v0.14): *nobody was asked here*, so the outcome must be one the pin's own `question` offers and a `blocker`/`high` pin is never settled this way. Written by `interview.expand_catalog` from `brief_decisions`, and what it may not carry comes back in `brief_held_back` and is asked — as does a key naming no cluster at all, in `brief_unmatched` (v0.16).
- **`cascaded`** (v0.11) — derived from a `Policy` the user elected. The answer reached the log once, at the policy election; this event amplifies it, and `policy_id` names the `Policy` that carries the rung and the quote. Its failure mode is neither invention nor mis-relay but **fit**: the rule may not suit this pin. Written by `Ledger.apply_policy` and by nothing else — `cascaded` and a `policy:` source imply each other, checked both ways.

It defaults to `transcribed`, the weaker rung, on purpose: a writer that says nothing has not earned the stronger claim, and understating what is known is the safe direction to be wrong in. That default is also why `cascaded` had to become its own rung: a cascade took it, so the log said "an agent relayed what the user said" about a decision nobody relayed, and all three surfaces repeated it faithfully. The alternative — every surface testing `source` for a `policy:` prefix — is string-parsing where an explicit field is available.

**Made visible by** — named, because "visible" with no surface is the claim this package exists to catch, and it was exactly that for one version: the map's decision card states the rung, colours the weak one, quotes `human_answer`, and for a `cascaded` one shows the `Policy` it came from and how *that* was elected (`mcp:render_map`); `mcp:ledger_summary` returns `decisions_by_evidence` beside `failures_by_class`, so an agent reads the rungs *before* acting; and the projected `AGENTS.md` region carries one line when any decision was relayed, cascaded, or written with no rung at all (`mcp:generate_instructions` — one line and no more, because that region is byte-budgeted). A rung one of the three does not know is the same bug wearing a new name, so adding one means teaching all three. The same three carry the `Policy` itself (v0.15) — its own card on the map, `policies_by_evidence` in the summary, one sentence in the region — because the election a cascade derives from is a decision, and this rule is about decisions, not only about rungs.

This is the same move as `provenance: agent_assumption` — the weak path is not forbidden, it is made **visible**, so a reader can weigh it and the challenger can attack it. Forbidding it outright is what the package did before v0.10, by shipping no election tool at all: that stopped an agent from choosing and also stopped the human from being recorded, so no pin could reach `decided` on any host.

### Threshold rule (confirmed)
What may end up in a silent default without disturbing anyone:
- `severity: blocker | high` → **never** silent. Always `asked`, or at least at the top of the batch to review.
- `severity: medium | low` → may go to `proposed_default`.

Volume collapses but nothing important slips away passively.

### The full funnel
```
200 pins → ~20 clusters → ~5 policies → ~10 real questions (asked)
         → the rest in proposed_default, skimmable in bulk
```
Order the `asked` questions by **information gain**: first the ones that, once answered, collapse the most downstream pins. The first ~10 do 90% of the work.

---

## v0.4 — Greenfield extension (twin skill `greenfield-forge`)

The ledger is **shared** by the repo's two sibling skills. `codebase-rescue` is curative (starts from as-is, derives the to-be backward); `greenfield-forge` is preventive (elects the to-be *first*, as-is grows until it coincides). Same schema, same anti-divergence property. A forged project carries its own `ledger.json`: it is the **audit baseline** rescue can later diff against the real code — closing the loop rescue cannot close on slop (whose docs are stale/aspirational; a forged ledger is not).

v0.4 adds, **additively** (no change to the existing variants):
- a new `Pin` `kind`: **`open_decision`** — the design fork not yet built;
- a new entity **`BuildItem`** — the twin of `RemediationItem` for construction.

### New `kind`: `open_decision` — design fork (greenfield)

Unlike `design_concern` (suboptimal **existing** code) and `incompleteness` (a stub inside code that exists), `open_decision` concerns a choice that **precedes** the code: nothing is built yet. `as_is` is null (or carries only the *givens* from the brief); `to_be` is derived from the election in the interview; the `question` is the fork with options and downstream implications.

```jsonc
"kind": "open_decision",
"severity": "high",              // for downstream fan-out: high if many decisions depend on it
"as_is": {
  "givens": ["must run on-prem", "the team knows Postgres"],  // constraints from the brief, not implementation
  "built": null                  // nothing yet — not a defect, it is the starting point
},
"to_be": null,                   // derived from the election (Decision 7) — never hand-written
"question": {
  "prompt": "Persistence model for v1?",
  "options": [
    { "id": "opt_pg",  "label": "Relational Postgres (single datastore)", "implication": "schema-first; contract = shared-types" },
    { "id": "opt_doc", "label": "Document store",                          "implication": "flexible schema; runtime validation" }
  ],
  "allow_freeform": true
},
"depends_on": [],                // wired by the decision-catalog: e.g. 'API style' depends_on 'data model'
"cluster_id": "cl_persistence"   // related forks resolved by a single policy
```

Lifecycle identical to the other pins: `detected → needs_input → (brainstorming) → decided → resolved`. Once `decided`, Phase 3 does not compute a reconciliation diff but **generates** the `BuildItem`s that realize the elected `to_be` (as-is grows until it coincides). `deferred` = out of v1 scope (stays future backlog, the natural hook into `slice` mode); `accepted` does not apply (there is no existing design to leave as-is).

Threshold rule unchanged: a high-fan-out `open_decision` (many inbound `depends_on`) is typically `high`/`blocker` → **always `asked`**, never a silent default — letting the model silently fill an undecided fork is the seed of slop. Tail forks (naming, style details) may go to `proposed_default`.

### New entity: `BuildItem` — the greenfield twin of `RemediationItem`

Where `RemediationItem` closes a gap on existing code, `BuildItem` **builds** what a decision committed to. Same discipline (ponytail rung recorded, bare minimum), different verbs. It lives in the same `pin.remediation[]` container.

```jsonc
{ "id": "bld_0001",
  "action": "scaffold",          // scaffold | implement | wire | configure
  "build_track": "A",            // A = red→green from the elected to_be (primary) · B = characterization (only when extending)
  "ladder_rung": 7,              // YAGNI for construction: never build beyond what the decision requires
  "contract_carrier": "shared-types",  // for 'scaffold' of the contract: the single source the layers are generated from
  "status": "todo" }             // todo | in_progress | done
```

**An item carries no `depends_on`, deliberately.** Sequence belongs to the pin — `pin.depends_on`
holds global ids, is validated on write ("the DAG is real, not aspirational"), and is what
`buildloop.waves()` actually levels. Items run in list order within their pin, which suffices
because the executor takes one scope at a time. The field existed until v0.9 and was inert three
ways: ids were allocated per-pin, so `rem_0001` named an item on *every* pin and a cross-pin
reference was ambiguous by construction; nothing validated them; and no line of the runtime read
them. Removed rather than repaired — a schema field addressed to nobody reads as a capability.

`action`:
- **`scaffold`** — generate from a single source: the contract → DDL/ORM/DTO/client types aligned *by construction*; or the paved road (test harness, linter, CI, session-start hook).
- **`implement`** — realize the behavior of a vertical slice (Track A: red test from the `to_be`, then the minimum that makes it pass).
- **`wire`** — connect already-scaffolded pieces (a route to its handler, a form to its endpoint).
- **`configure`** — deterministic settings descending from a decision (env, secrets, feature flags).

The waves fall out of the **pins'** `depends_on` (contract & data model → paved road → core slice → secondary features → polish), they are not hardcoded — exactly like rescue's reconciliation waves. The diff `gap = diff(to_be, as_is)` stays the invariant: here `as_is` starts empty and the roadmap is the build backlog, which tends to zero at completed v1.

---

## v0.5 — Full loop: outcome, observable feedback, release & operate

v0.5 closes the lifecycle loop. It adds the **root** upstream of the decisions (the acceptance criteria) and the **return arc** from production (the observable `flip_criteria` that reopen pins). All additive: no existing variant changes.

### New `kind`: `acceptance_criterion` — the testable outcome that roots the DAG

Until now the chain was `decision → contract → test`. The zeroth rung was missing: `outcome → decision`. An `acceptance_criterion` is a **user-observable** and **testable** result from which the decisions descend. It roots the DAG: the architecture `open_decision`s `depends_on` the criteria they serve to satisfy, and the Track-A tests reference them.

```jsonc
"kind": "acceptance_criterion",
"severity": "high",
"as_is": { "built": null },
"to_be": {                        // the outcome, in testable form (Given/When/Then or equivalent)
  "statement": "a user can book a free slot and receives a confirmation",
  "verify": "e2e: POST /bookings on a free slot → 201 + confirmation event"
},
"question": {                     // bounded, NOT 'tell me about the app': is it in v1 scope?
  "prompt": "Is self-service booking a v1 outcome?",
  "options": [
    { "id": "in",  "label": "Yes, in v1 scope" },
    { "id": "def", "label": "Defer (deferred)" }
  ],
  "allow_freeform": true
},
"depends_on": []                  // outcomes are roots: nothing depends upstream of them
```

Acceptance criteria are the **engineering half** of requirements (problem statement + testable outcomes), not product management (user research, personas) — which stays out of scope. Anti-slop rule unchanged: an undeclared outcome is not silently assumed; it is elicited as a bounded fork or stays out. Security decisions from the threat model (STRIDE) are `open_decision`s with `provenance: "threat-model"` — no new kind is needed.

### Observable `flip_criteria` + `ReopenEvent` — the return arc

Until now `flip_criteria` was prose ("reopen if a module needs independent scaling"). To close the loop we make it **evaluable** against telemetry, in optional structured form alongside the prose:

```jsonc
// inside a DecisionEvent, next to the prose flip_criteria:
"flip_signal": {
  "signal": "module:orders p95_latency",
  "comparator": ">",
  "threshold": "200ms",
  "window": "sustained 7d",
  "source": "metrics"            // metrics | logs | traces | manual_checkpoint | incident
}
```

When the signal fires, the Operate&Evolve phase emits an immutable `ReopenEvent` and moves the dependent pins back to `needs_input` (state `reopened`). The arc **does not decide** — it only reopens, then hands back to the interview (`slice`) or to rescue. Neutrality holds as it does for the brainstorm.

```jsonc
// ReopenEvent (inside decision_log[]) — immutable
{ "id": "rev_0003", "pin_id": "pin_0001", "timestamp": "ISO-8601",
  "reason": "flip_signal fired: orders p95 340ms > 200ms for 9d",
  "fired": "flip_signal",
  "source": "feedback:metrics" }   // originated from production, not the user
```

A `flip_signal` without telemetry degrades to `manual_checkpoint`: a "did X happen?" question at a wave boundary or interval, never a hard-fail.

### `BuildItem` for Release and Operate

Phases 6 (Release) and 7 (Operate) introduce no new entities: they are `BuildItem`s with an extended `action`, and their pins are `open_decision` / `configure`.

```jsonc
"action": "instrument"           // + the existing scaffold | implement | wire | configure
// release:  migrations = implement (expand/contract) · deploy/flag/versioning = configure · rollback = procedure
// operate:  instrumentation (logs/metrics/traces/health) = instrument · SLO + signal manifest = configure
```

The **signal manifest** produced in Operate is what the `flip_signal`s watch: it is the physical anchor of the feedback arc. Without instrumentation the arc has no input — which is why Operate's codebase slice is a **precondition** of Evolve, not an extra.

---

## v0.6 — Oracle challenge (adversarial arc *upstream*)

Until now the elected truth was treated as correct until proven otherwise **by production**: `flip_signal`/`ReopenEvent` reopen it only when *reality changes* (downstream arc), and the wave-checkpoint doubts it only *during* the build. The **upstream** arc was missing: what if the oracle — an `acceptance_criterion`, the elected `to_be`, a `Policy` — is wrong *from the start*, before anything is built on it? A frozen wrong oracle is **worse** than no oracle: it scales its own wrongness and wears the authority of a green check. v0.6 adds the role and event that **challenge the oracle** adversarially, right after the interview and at every wave. Additive: no existing variant changes.

### `ChallengeEvent` — the neutral challenge that can reopen a pin

A read-only `challenger` (role defined in the agents doctrine, the adversarial twin of the `reviewer`: the reviewer *enforces* the oracle, the challenger *doubts* it) examines the `decided` pins and their `to_be`/criteria and actively tries to **refute** them. Like the brainstorm and the feedback loop it is **neutral: it challenges, it does not decide.** It emits an immutable `ChallengeEvent`; if the challenge survives the threshold review, it moves the pin back to `needs_input` (sub-state `challenged`, the twin of `reopened`) and hands it back to the interview — which stays the only thing that commits.

```jsonc
// ChallengeEvent (inside decision_log[]) — immutable, neutral
{ "id": "chl_0002", "pin_id": "pin_0007", "timestamp": "ISO-8601",
  "target": "acceptance_criterion",  // acceptance_criterion | to_be | policy | decision
  "class": "unfalsifiable",          // unfalsifiable | inconsistent | unsatisfiable | unfounded_infeasibility | unstated_assumption | ignored_fanout | other
  "argument": "the criterion 'the app is fast' has no testable verify: no test can fail it",
  "severity": "high",                // same threshold as pins: high/blocker → always re-asked, never a default
  "upheld": true,                    // outcome of the threshold review; true → reopens
  "source": "challenge:challenger" } // originated from the agent, never commits
```

The **challenge classes** (the `class`) are the typical ways an oracle is wrong upstream, not a closed taxonomy (`other` stays the escape hatch):
- `unfalsifiable` — the `to_be`/criterion has no `verify` that could fail (no test can refute it) → it is not an oracle, it is a slogan.
- `inconsistent` — two mutually incoherent criteria/decisions (satisfying one violates the other).
- `unsatisfiable` — the `to_be` is not realizable from the known `givens`/constraints (an impossible commitment).
- `unfounded_infeasibility` — the mirror of `unsatisfiable`, and the oracle-form of under-reaching: the `to_be` gives up a *reachable* outcome because it is **assumed** impossible ("this cannot be done here") without that infeasibility ever being shown. Reopen so the human re-decides with the real feasibility in view — the self-limiting twin of the over-reaching assumption (`references/core/self-model.md`).
- `unstated_assumption` — the decision rests on an assumption never declared (see `provenance: agent_assumption` below): reopen it by making it explicit.
- `ignored_fanout` — a high-fan-out `open_decision`/criterion resolved as if it were not one (a silent default where `asked` was needed).

Neutrality rule (enforced as for brainstorm/feedback-loop): the challenger writes **only** `ChallengeEvent`s and, if `upheld`, moves the pin to `needs_input`. It does not write a `DecisionEvent`, does not elect, does not edit code. Identical threshold: a sustained `high`/`blocker` challenge is **always** `asked` again, never a silent default. **Reopens the minimum** — the challenged pin plus only the dependents that rested on the falsified oracle (via `depends_on`), exactly like the feedback loop. A challenger that reopens everything regenerates the very churn the skills cure.

### `provenance: agent_assumption` — the forced assumption made vetoable

Precondition of the challenge, and an anti-slop rule in its own right: when an agent **must** assume to proceed on under-specified input, it does not encode the assumption silently — it materializes it as a pin (or as a `provenance` entry on the pin it is creating) with `confidence: inferred|ambiguous` and `provenance: [{ "source": "agent_assumption", "detail": "..." }]`. This makes the assumption **visible** on the map, **vetoable** in the interview, and **challengeable** by the challenger (class `unstated_assumption`) — instead of becoming a mute decision. It is the schema-level translation of the principle "on vague input, raise the effort by surfacing the gaps, not by guessing confidently". The surface-level doctrine lives in the assumptions doc; only the data form lives here.

### Why this is the missing arc

The feedback loop closes the loop *downstream* (production falsifies the decision → reopen). The challenger closes the loop *upstream* (the oracle is incoherent/untestable/unsatisfiable → reopen **before** building). Together they cover the two ways an elected truth can be wrong: wrong *become* (reality changed) and wrong *born*. Both arcs **reopen and do not decide** — neutrality is the same anti-divergence property that holds the whole ledger together.

---

## v0.7 — Honest verification: `correctness_unknown` and the three trust axes

Both arcs above assume the verdict on a *closed* pin is binary: it was fixed, or it was not. On a legacy repo that is a lie the schema was forcing. Tests may not exist, the path may be unreachable locally, the effect may only be visible in an environment nobody has. The doctrine already said the right thing in prose — *"an unverifiable claim reported as verified is worse than an open one"* — but with only `resolved` on offer, the honest outcome had nowhere to go, and every pressure pointed at a false `resolved`.

v0.7 gives that sentence a state, and gives every checked claim the three-axis envelope from `references/core/trust-axes.md`. Additive: no existing variant changes.

### New state: `correctness_unknown`

Between `decided` and `resolved`. It means: **the work was done, and the correctness of the outcome could not be established from the available evidence.** It is not a failure and not a defect — it is the honest report of a missing oracle.

Reaching it is disciplined, not a shrug: it is only legitimate **after** the evidence stack has actually been walked, best signal first — existing tests → static checks (type-check, constraints) → a generated smoke probe or behavioral observation → diff-risk review. `correctness_unknown` is what remains when all of those were tried and none could speak.

```jsonc
"state": "correctness_unknown",
"verification": {
  "determinism": "D1",              // D0 | D1 | D2 — how the check reproduces
  "rung": "re_read",                // self_check | re_read | observed | cross_derived
  "attempted": ["tests", "typecheck", "smoke_probe"],   // the stack that was walked
  "blocked_by": "no runnable environment for the payments path",
  "evidence": [{ "kind": "typecheck", "ref": "tsc --noEmit", "outcome": "pass" }]
}
```

The state **blocks closure** and forces an explicit next move — retry with more context · add the missing check (a new `acceptance_criterion` pin, which is how the zone *earns* the ability to be verified next time) · request manual takeover · narrow the scope · accept the risk explicitly (`accepted`, with the unknown named). What it may never do is decay into `resolved` because time passed.

Those five are the options of the fork the state **generates**, and it generates one only where the pin poses none (next paragraph). On a pin that already carries the human's own fork the five are not offered, and saying they are "recorded as a `DecisionEvent` like any other" was false there for a round: what is recorded on such a pin is an answer to **its own** question. That is not a gap the schema needs closing, because four of the five are acts in the world rather than ledger writes, and what the ledger records is the act's outcome through a door that exists — a re-election (`record_decision`, against the pin's own options), a new `acceptance_criterion` pin (`add_pin`), an `accept` where the kind allows it, a `defer`, or a `resolve` once an observation reaches the closing rung. The one thing no door does is *extend* an existing fork with the five moves, and nothing here should: `question.options[].id` is the carrier the offered-options rule anchors on, and an agent adding branches to a human's menu is that rule dismantled from the side.

Because it forces a move, it **carries the fork that asks for one**: entering the state writes that five-option `question` onto a pin that has none, and the pin joins the **interview view** alongside `needs_input`. It is written **only** where none exists — the same rule `cross_derive` is held to, for the same reason. It used to be written unconditionally, so marking a pin the human had *decided* deleted their own fork (an elected `s3|gcs` replaced by `retry|add_check|takeover|narrow|accept`), and `question.options[].id` is the carrier the offered-options rule anchors on at both doors. What puts the pin in front of a human is its **state**, which the interview view selects on; overwriting the menu adds nothing to that and costs the human their question. The two states await a human for different reasons — `needs_input` means the decision was never made, `correctness_unknown` means it was made and the *verification* failed — but both await one, and a state that blocks closure while appearing on no surface is a black hole, not a gate. A `blocker`/`high` pin here sorts **above** information gain: fan-out is how you order questions that are still open, and an unverifiable blocker is not a question to sequence well, it is one that must not be skimmed past.

It also does not satisfy a dependent: only `resolved` and `accepted` close a `depends_on` edge, so downstream work cannot build on an outcome nobody could verify.

Threshold rule, consistent with the rest of the spec: `severity: blocker | high` in `correctness_unknown` is **always** `asked` — never a proposed default, never batch-skimmed. An unverifiable blocker is exactly the thing that must reach a human.

### The `verification` envelope — three axes, never one number

Any pin that carries a checked claim may carry `verification`. The three axes are **orthogonal** and are reported together; the posture is their **conjunction, never the most flattering one**:

| Field | Answers | Values |
|---|---|---|
| `determinism` | how does the result reproduce? | `D0` carrier computation · `D1` reconstructible from a pinned artifact · `D2` model judgment on the path |
| `rung` | how hard was the claim checked? | `self_check` · `re_read` (over the full diff, not the output) · `observed` (behavior exercised and seen) · `cross_derived` (re-derived by a different provider) |
| review burden | what review does the risk demand? | the existing `severity` × blast radius — **no new field** |

Two consequences the schema now makes checkable. A pin may not be `resolved` at rung `self_check`: `resolved` means `observed`, which is the verification skill's rule restated as data — and a pin carrying **no `verification` at all** is refused on the same rule, since it records even less than a weak rung does. And a `D2` finding does not inherit the `extracted` confidence or the `fp-check` bypass that a `D0` carrier finding earns — the discount belongs to the carrier, not to the label.

`cross_derived` is the rung that turns the mixed-provider roster into a safety signal: for irreversible or high-severity claims the claim is re-derived by a model from a **different provider**, agreement is the pass, and **divergence forces human review rather than a tie-break**. A single-provider hallucination rarely reproduces cross-provider, so the disagreement *is* the finding.

### Why this is not more ceremony

Every other state in this spec exists to stop a decision being made by nobody. `correctness_unknown` stops a *verification* being claimed by nobody — the same anti-divergence property applied to the last step, where until now the schema quietly rewarded the confident report.

---

## v0.8 — Landing-zone readiness: the premortem of the terrain

The challenger doubts the **oracle**; the wave checkpoint doubts the **build**. Neither asks the question that comes before both when work lands on code that already exists: *can this ground bear the change at all?* Adding a feature to a fragile, untested, heavily-coupled zone is not a planning problem, it is a **terrain** problem, and planning around it produces a correct plan that fails anyway.

v0.8 adds the gate that asks it, and the dependency wiring that acts on the answer. Additive: no existing variant changes, and — deliberately — **no new edge type**. The hardening prerequisites are ordinary `depends_on` entries, so the wave scheduler orders them with no new mechanism and the existing rule that only `resolved`/`accepted` close an edge already means a change cannot start until the ground is really fixed.

### The `readiness` object

```jsonc
"readiness": {
  "verdict": "harden_first",        // ready | harden_first | redesign
  "determinism": "D2",              // the VERDICT is judgment...
  "evidence_determinism": "D0",     // ...over deterministic evidence. Never merged into one score.
  "zone": { "files": ["src/pay/charge.ts", "..."], "nodes": 34 },
  "evidence": {
    "open_pins_in_zone": [{ "pin": "pin_0012", "severity": "blocker", "state": "needs_input" }],
    "untested_files": ["src/pay/charge.ts"],
    "churn": { "src/pay/charge.ts": 41 },
    "coupled_outside_zone": [{ "file": "src/billing/invoice.ts", "co_commits": 7 }]
  },
  "hardens": ["pin_0012"],          // prerequisites — also appended to depends_on
  "rationale": "the charge path carries an unresolved blocker and no test reaches it"
}
```

The **zone** is the blast radius of the planned change: the pins' anchors plus what transitively depends on them. The **evidence** is four carriers, all `D0` — the ledger's own unresolved pins whose anchors land in the zone (the cheapest signal there is: you are about to build on ground this ledger already says is broken), files no test file reaches through a graph edge, `git log` churn, and files that historically co-change with the zone from *outside* it.

That last one is a second, independent carrier for the thesis the shape engine already serves. Shapes compare **declared structure**; co-change compares **recorded behaviour** — what the team has actually had to edit together. Two carriers agreeing is a strong finding; two disagreeing is itself the finding, which is why they are reported separately and never merged into one score.

### The verdict is judgment, and says so

`ready` / `harden_first` / `redesign` is a `D2` conclusion over `D0` evidence, and the object records both determinism levels rather than blending them (`references/core/trust-axes.md`). Inventing a threshold here — *"coupling above 0.6 means harden"* — would be a number with no carrier wearing a green badge, which is precisely what this schema now forbids elsewhere. The runtime computes facts and **refuses to conclude**; the agent concludes; the human elects what to do about it.

### The two disciplines, one of them mechanical

Without bounds this gate becomes an open-ended rewrite, so:

- **blast-radius-scoped** — evidence counts only what lies *inside* the zone. A hotspot elsewhere is not this change's problem and never enters the bundle.
- **change-justified** — a pin may become a hardening prerequisite **only if its own anchors land in the zone**, and this one is *enforced*, not promised: the ledger refuses the edge otherwise. Remediation is admitted because it reduces *this* change's risk, never because the code is imperfect elsewhere. (A cycle check refuses the mirror error: hardening something that already depends on the change.)

`harden_first` with no prerequisites named is rejected as well — that is a worry, not a verdict.

### Why this is the bridge between the two skills

Rescue derives the to-be backward from existing code; forge elects it forward and builds. They have always shared the ledger, but they were still two workflows meeting at a handoff. The `hardens` edge makes them **one DAG**: a rescue pin becomes a *blocking prerequisite* of a forge `BuildItem`, ordered by the same scheduler, closed by the same evidence rule. *Make the change easy, then make the easy change* — and a zone that hardens itself is also the zone that has earned the ability to be verified, which is the same thing `correctness_unknown` asks for one step later.

---

## v0.9 — One failure vocabulary, and the challenger's second mode

Two additions that are really one: a closed set of words for how work fails, and the exercise that uses those words *before* the work rather than after.

### `FAILURE_CLASSES` — a superset of the challenge classes, not a second list

```
unfalsifiable · inconsistent · unsatisfiable · unfounded_infeasibility ·
unstated_assumption · ignored_fanout · other                    ← the v0.6 challenge classes
contract_drift · missing_capability · environment · untested_path ·
scope_creep · stale_carrier · nondeterminism · external_change  ← added in v0.9
```

The containment is the design, not a convenience. A challenge *is* a failure mode of the oracle, foreseen before the work starts — so the words must be the same words. Two vocabularies for one concept is precisely the divergence this package exists to find in other people's codebases, and shipping it in our own schema would have been the front-door version of that bug. A test asserts `CHALLENGE_CLASSES ⊂ FAILURE_CLASSES`, so they cannot drift apart later.

The **vocabulary** is `D0` — it is an enum, and membership is checked. The **classification** is `D2`: deciding that this failure was `stale_carrier` rather than `environment` is judgment, and the spec says so instead of letting the enum's crispness imply otherwise.

### `premortem` on the pin — the challenger's second mode

The challenger's first mode refutes the oracle: *is the elected criterion sound?* The premortem grants the criterion and asks a different question: *assume this already failed — what killed it?* Same role, same read-only posture, so **the roster stays at six**. A seventh member would have been ceremony; a second mode is the same reviewer looking the other way.

```jsonc
"premortem": {
  "failure_modes": [
    { "class": "stale_carrier", "description": "the graph predates the migration, so the zone is wrong" }
  ],
  "guardrails": ["rebuild the graph and re-assess before planning"],
  "abort_criteria": ["the zone still resolves fewer than all anchors after a rebuild"],
  "paper_tigers": [
    { "risk": "concurrent writes corrupt the ledger",
      "evidence": "writes are atomic via tempfile+replace (runtime/ledger.py save)" }
  ],
  "determinism": "D2",
  "source": "challenge:challenger"
}
```

Two refusals keep it from decaying into a worry list:

- **failures with no response are rejected** — at least one guardrail or abort criterion. Naming what could go wrong and stopping there is the ritual version of the exercise.
- **a `paper_tiger` must carry its evidence.** A paper tiger is a risk that *looks* grave and is already mitigated; the field exists to suppress noise, so admitting one without proof of mitigation would let it generate the noise instead. Without evidence it is not a dismissed risk, it is an ignored one.

When a premortem is **owed** is `D0`, and derived only from carriers the ledger already holds — the `blocker|high` threshold, a landing-zone verdict of `harden_first`/`redesign`, a recorded history of this pin being reopened, or inbound fan-out at the same threshold `ignored_fanout` already uses. No new tuned number enters the schema.

### `FailureEvent` — the same words, after the fact

```jsonc
{ "id": "fal_0001", "pin_id": "pin_0007", "class": "untested_path",
  "detail": "the refund path had no test; the regression only appeared in staging",
  "phase": "review", "source": "measurer", "timestamp": "…" }
```

Append-only like every other event, and it **changes no state**: labeling is observation, and the response — reopen, challenge, re-plan — stays a separate, explicit act. `phase` is one of `plan | build | evidence | review | production`.

Because both ends share the vocabulary, they join: `foresight(pin)` returns `anticipated` (feared and happened), `unrealized` (feared, did not), and `surprises` (happened, nobody saw it coming). That is a set comparison — `D0`, no scoring. There is deliberately **no hit-rate metric**: these events are rare, human and few, and a percentage computed over them would be a statistic with no population, which is exactly the kind of number the trust-axes doc refuses.

The surprises are the interesting column. A premortem that anticipates everything is either very good or written after the fact, and only the immutable timestamps can tell you which.

### `cross_derivations` — the `cross_derived` rung, earned rather than declared

The verification ladder's top rung (v0.7) had no mechanism: anything could claim it. Now it is earned by re-deriving one claim with a **different provider**.

```jsonc
"cross_derivations": [{
  "claim": "lib X still supports streaming in v4",
  "derivations": [
    { "provider": "anthropic", "model": "…", "result": "yes, see docs §…" },
    { "provider": "openai",    "model": "…", "result": "no — removed in v4" }
  ],
  "providers": ["anthropic", "openai"],
  "agreement": "disagree",
  "independence_determinism": "D0",   // were the providers distinct? checked
  "agreement_determinism": "D2"       // do the answers MEAN the same? judged
}]
```

The reason this works at all is asymmetric: a single-provider hallucination is **stubborn under repetition and fragile under substitution**. Ask the same model twice and it reproduces its own error; ask a different family and it rarely invents the same wrong thing. So the schema enforces the only part that is checkable — at least two derivations from at least two *distinct* providers — and refuses same-provider repetition, which is repetition wearing an independence badge.

Agreement sets `verification.rung = "cross_derived"`. **Disagreement is the signal, not a nuisance**: a pin **not in `CLOSED_STATES`** moves to `needs_input` with substate `contested`, because a claim two independent providers disagree about is exactly the one a human must look at. A pin already in `CLOSED_STATES` is not reopened here — the disagreement is still appended, `reopened` comes back false, and un-finishing settled work keeps its own arc (`reopen`, which records why).

`decided` is on the reopened side of that line, and deliberately: it is in `SETTLED_STATES` but **not** in `CLOSED_STATES`, and the whole reason those two sets were split is that a human election is *correctable* while finished work is not un-finished on an agent's say-so. So a decided pin whose claim two providers dispute comes back to the interview, and the human re-elects or does not. This paragraph read "an **open** pin" for one round, as though open and closed exhausted the states — the predicate is `pin["state"] not in CLOSED_STATES`, which is a third thing and is what the code has always computed.

Both derivations become the pin's options **only where the pin poses no fork yet** — writing a menu where one exists would let an agent decide what the human is allowed to choose, which is the offered-options rule dismantled from the side. Where the human's fork already exists it is left exactly as its author left it, and the derivations stay on the pin under `cross_derivations`, which `map.py` renders immediately above the question. That last clause is the part to keep honest: for one round the field had a writer and no reader at all, so a pin that came back to the interview `contested` showed its original menu and said nowhere what had disagreed.

It deliberately does **not** cascade to dependents the way an upheld challenge does — nobody yet knows which side is wrong, and reopening the neighbourhood on an unresolved disagreement is churn, not caution.

The rung is **not mandatory at any severity**. Making it obligatory above a threshold roughly doubles the cost of the most expensive pins, and that trade should be elected with a measured number in hand rather than assumed by a schema.

### `governance` + `policy_hash` — under which rules was this decided?

An append-only log answers *what* was decided and *why*. It has never answered a third question that matters just as much when something later goes wrong: **under which rules?** Between two decisions the roster can change, a permission can widen, this schema can gain a state, and a skill's prose can be edited. A trail that cannot show that is a trail somebody will one day read wrongly, with total confidence.

```jsonc
"governance": {
  "policy_hash": "…",
  "components": { "roster": "…", "permissions": "…", "spec_version": "…", "skill_version": "…" },
  "missing": []
}
```

Every event appended afterwards carries that `policy_hash`, stamped **before the outcome takes effect**. So a widened permission becomes a *visible hash delta in the trail* instead of an invisible change of meaning.

Three properties, each chosen against a plausible alternative:

- **It is a join key, not a security device.** Its only job is to make *"these two decisions were taken under different rules"* answerable. Treating it as tamper-evidence would be a claim the artifact cannot support — anyone who can edit the ledger can edit the hash.
- **The components travel with the digest.** A bare hash tells you two decisions differ; the components tell you *which rule* changed, which is the only form of the answer anybody can act on.
- **Absence is recorded, not implied.** An ungoverned ledger stamps `policy_hash: null` explicitly on every event. A missing field would read as fine, and an input that cannot be resolved lands in `missing` rather than being dropped — a fingerprint over three of four inputs is not a smaller fingerprint, it is a misleading one.

---

## v0.11 — The policy election gets a door, and the cascade says what it is

Two halves of one failure, found by reading v0.10 back against what shipped.

**The write half of the policy step had no door.** `Ledger.add_policy` and `Ledger.apply_policies` existed, worked, and were reachable by nobody: no MCP tool created a `Policy` or ran the cascade, and MCP is the only runtime channel on all four hosts. Meanwhile the shipped prose told an agent that the user elects a policy and that it then cascades — four passages of it, in the funnel doctrine, both Phase-2 playbooks and greenfield's Phase 1. Same shape as the v0.10 gap one level up: `decide()` worked and nothing could reach it, so no pin could be decided; here nothing could set a policy, so the funnel's *highest-leverage* step — the one that turns 20 clusters into 5 questions — was prose describing a mechanism the artifact did not perform.

The door is `mcp:ledger_record_policy`, built on the same invariant as `mcp:ledger_record_decision`: **an agent may record an election, never make one.** It refuses an `offer_id` the catalog does not make, refuses an offer restated in the caller's own words, refuses a policy with no rule / scope / outcome, refuses an exception naming a pin that does not exist, and refuses a relayed policy with no verbatim quote. Where the client declares elicitation the server asks the user itself, showing the rule **and the pins it would decide**, and writes only on acceptance. That blast radius is not decoration: a policy is an election over a cluster, so what is being elected *is* the radius, and `Ledger.policy_preview` — the same matcher `apply_policies` cascades over, so the two cannot drift — is what makes it showable before the write instead of discoverable after it.

**The cascade lied about itself.** `apply_policies` called `decide()` without an `evidence`, so every cascaded decision took the `transcribed` default: the map rendered *"an agent relayed what the user said"* plus *"⚠ relayed with no quote"*, `decisions_by_evidence` counted it under `transcribed`, and the projected `AGENTS.md` stated that N of N decisions were relayed by an agent. All three were false about the user's own elected policy, and all three were faithful readings of what the ledger said.

So a cascade gets its own rung, `cascaded`, and its own pointer, `policy_id`. This is not a fourth flavour of "weak": *how the human's answer reached the log* is genuinely different here — it reached it once, at the policy election, and this event is derived from that — and the derived failure mode is **fit**, not invention. The rejected alternative was to leave the default and have each surface test `source` for a `policy:` prefix: string-parsing where an explicit field is available, in a package whose own rule is to anchor on the carrier.

`evidence` and `human_answer` move onto the `Policy` itself for the same reason: that is where the human actually answered, so that is where the rung belongs, and every cascaded event points back at it rather than restating a quote nobody gave *here*.

---

## v0.12 — The cascade is held to the rule the single decision was already held to

v0.11 gave the policy election a door. The door wrote through a gap: **`record_decision` refuses an outcome the pin's own `question` never offered, and the policy path did not.** A caller could pass `default_outcome` in its own words and it landed as the `outcome` of every matching pin — including pins whose question offered a closed set that did not contain it. Reproduced both ways before the fix: over real stdio, an elicited policy stamped *"DROP the api layer and regenerate from scratch"* onto two pins offering `db | api`; through the pure layer, `default_outcome="mongodb"` onto pins offering `postgres | mysql`. Both landed. The single-pin door refuses exactly that.

**The rule, and it is the whole of it: an outcome may be written onto a pin only if that pin's own `question` offers it.** The carrier is `question.options[].id`, compared by equality — the same field the single-pin door checks, so both doors admit the same set for a given pin. Labels do not count (prose for a human) and `allow_freeform` does not widen it (freeform is legitimate where the human's own words ARE that pin's outcome; a policy outcome is one sentence elected over a cluster, and is nobody's words *here*). A pin that does not offer it is **held back** — a new `not_offered` bucket beside `held_back`, both leaving the pin `asked`. Two different reasons to refuse a silent default, named separately because "why is this pin still open" is a question a reader has to be able to answer.

So `default_outcome` is an **option id** and therefore a non-empty string. It was `Any`, and the cascade JSON-encoded anything else into the event: a blob no question could offer, which under this rule would decide nothing anywhere. Refusing it says that at the door instead of at every pin.

**And the elicitation shows it.** The message put to the human was `Set this policy?` + the rule + the pin count, answered with a two-value accept/decline — the outcome string appeared nowhere in it, while the write claimed the strongest rung there is. What a message omits was not elected, whatever the write then claims. It now names the rule, the outcome it writes, and both held-back sets. `record_decision`'s message was re-checked against the same standard and passes for a structural reason worth keeping: each choice *leads* with the option id, and the option id is exactly what is written, so the outcome cannot go missing without the choice going missing.

**The greenfield catalog path was the same defect wearing a legitimate face.** An offer's `default_outcome` was the `default_policy` sentence itself, so accepting the persistence offer would write *"one relational datastore until a concrete need proves otherwise; schema-first"* as the outcome of a pin whose question offered `relational | document | kv | none`. The user *was* shown that sentence — as a **rule** — and no pin ever offered it as an outcome. A cluster now declares `default_policy_outcome`, one of its own option ids, and only those clusters make offers. Six do; six state a default that no single option carries (`nfrs` names four at once, `delivery`'s is conditional on the topology fork, `outcomes` has no options) and come back under `no_default_outcome` instead of being dropped, so "this default must be asked" cannot be misread as "this cluster has no default".

**One policy, once, over the radius its elector was shown.** `apply_policies()` re-ran every policy in the ledger on every call, so recording `pol_0002` returned pins `pol_0001` had decided as its own, and accepting any policy silently cascaded every older one over pins added since. Settled pins are skipped, so the only pins a re-run could ever touch were pins created *after* an election — precisely the ones its elector was never shown. It is now `apply_policy(policy)`: the cascade happens at the election, over that radius, and pins that appear later are asked or covered by a policy elected with them in view. The returned shape says what happened, per policy: `cascaded` (this policy, this call), `held_back`, `not_offered`, `excepted`, `already_settled`.

---

## v0.13 — A rule enforced at the write governs no file that already exists

v0.11 and v0.12 are write-time rules, and both were checked only where the write happens. Every ledger already on disk was written under the older ones, and this schema treats that file as durable truth — so "fixed" had to mean fixed for those too. It did not. A reviewer built a v0.9 ledger holding exactly what the pre-v0.11 cascade wrote (`source: "policy:pol_0001"`, `evidence: "transcribed"`, no `policy_id`, no quote) and ran all three surfaces: `ledger_summary` answered `{"transcribed": 1}`, the projected `AGENTS.md` said *"1 relayed by an agent"*, and the map printed *"⚠ relayed with no quote — nothing here separates it from an invention"*. Three faithful readings of a field, all three false about the user's own elected policy — the exact sentence v0.11 was written to delete, still shipping, because the fix bound the writer and the reader was never asked.

**The rung is read, not copied.** `Ledger.decision_rung(event)` answers *how did this answer reach the log* from the strongest carrier the event has: `decide()` has required `source` to be `interview` or `policy:<id>` at every version of this schema, and only the cascade writes the second, so a `policy:` source **is** a cascade in any readable file. Where the newer explicit fields are absent that is the only carrier there is, and reading it is what the surfaces now do — once, in the library, never by each surface sniffing a string for a prefix. The map states the disagreement rather than quietly winning it: the card names the value the file actually records and says it was the default of the call that wrote it.

**Nothing in the log is rewritten.** The alternative was a migration that reclassifies those events, and it is refused on the entity's own terms: `DecisionEvent` is an append-only, immutable log. A migration would also have to *invent* `policy_id` by taking `source` apart and store the result as though the writer had recorded it — a reconstruction indistinguishable, afterwards, from a fact. The log keeps the bytes its writer wrote; the reading is corrected where reading happens.

**And the version stamp is earned, not applied.** Loading a readable ledger used to overwrite `version` with the runtime's own, unconditionally and with no backfill: a bare load+save turned that v0.9 file into one *claiming* v0.12, whose invariants it did not satisfy. So `version` is a **floor** — the newest rule set the file's own content conforms to — and it rises only when `Ledger.nonconforming(data)` is empty. A file holding a pre-v0.11 cascade keeps the version it was written under, forever, which costs nothing (the schema grows by addition, so every later runtime still reads it) and claims nothing false. `ledger_summary` returns `pre_rule_events` beside `version`, so the refusal is visible rather than merely correct.

`nonconforming` is deliberately narrow: **only rules whose violation is decidable from the event alone.** The v0.12 offered-options rule is not — it needs the pin's `question`, which is mutable and may have been edited long after the decision, so an option absent today does not prove it was absent then. Holding a file below its floor on evidence that weak would be the same false claim pointing the other way.

The general shape, since this is now the fourth instance of it in this document: **a new rule arrives with a writer and no reader.** The question that catches it is not "is the new rule enforced" but *"name every artifact this rule is now false of, and say what reads them."*

---

## v0.14 — The rule lived in a door, so every new door had to remember it

v0.12 put the offered-options rule on the policy door after finding it only on the single-pin door. It was still a rule *per door*, and an adversarial reviewer got the identical violation through **two more doors nobody had looked at** — both reproduced over real `uv run --script` stdio:

- **the cluster fan-out.** `decide(..., apply_to_cluster=True)`, reachable from `mcp:ledger_record_decision`, copied one answer onto every pin sharing the `cluster_id` with no filter of any kind. On a four-pin cluster it decided a pin offering a different option set, a pin posing **no question at all**, and a **`blocker`** — four `DecisionEvent`s each carrying the same `human_answer`, from an elicitation that named ONE pin. And the shipped rescue playbook *recommended* it, in the same bullet list as the offered-options rule it bypassed.
- **the project brief.** `interview_expand(brief_decisions=...)` called `decide()` on whatever string the caller supplied, for any cluster, at any severity: `{"persistence": "mongodb — an outcome no option offers", "identity": "roll our own crypto"}` committed `high` pins to outcomes their own forks never offered, on the `brief` rung — the rung whose entire meaning is *nobody was asked*.

**So the rule stops being a rule and becomes a predicate.** `Ledger.unasked_verdict(pin, outcome, excepted)` answers one question — *may this outcome land on this pin, given that this pin's own question was never put to the human?* — and returns the bucket: `already_settled` · `excepted` · `held_back` (the severity threshold) · `not_offered` (offered options) · `would_decide`. `policy_preview` is now just the **scope** (which pins the policy matches) over that predicate, `apply_policy` cascades over exactly its `would_decide`, and the brief calls it per pin. The single-pin door deliberately does not: there the human *was* shown this pin, so the threshold does not apply — but its offered-options check is `Ledger.question_offers`, the same function the predicate's second half calls, so the two cannot admit different sets.

**And the fan-out is gone rather than gated.** `decide()` writes one event for one pin, structurally. The reason is worth more than the fix: there is no *rung* for a fan-out. `elicited` and `transcribed` describe an answer given about **this** pin; one answer covering pins nobody was shown individually is what `cascaded` means, and `cascaded` requires a `Policy` to point at — because the `Policy` is what carries the rule, the quote and the radius the human accepted. An honest cluster fan-out **is** a policy. `mcp:ledger_record_policy` already does exactly that, with a preview, a held-back list and a `not_offered` list, so "200 findings → one decision" keeps working through the door that can say, on each pin, whose answer this was.

**A `brief` decision is held to the same gate**, for the reason the rung itself gives: it means *answered from the project brief, without asking*. So the outcome must be one of the fork's own option ids, and a `blocker`/`high` fork is never settled that way — the threshold rule says never *silently* defaulted, and this is the definition of silent. What the brief cannot carry is returned in `brief_held_back` (cluster, pin, reason, and the ids the fork does offer) and stays an open question, rather than being dropped or written anyway. A key that matched **no cluster** is returned too, in `brief_unmatched` (v0.16): it settled nothing and created nothing, so a caller told to check the held-back list would have found a fork it believed settled on no list at all.

**Separately, the elicited option id was recovered by parsing a display string.** The server built each choice as `f"{id} — {label}"` and read the answer back with `.split(" — ")[0]`. Nothing constrains an option id and an agent authors them via `mcp:ledger_add_pin`, so ids `keep` and `keep — and also delete the module` render two distinct rows that parse to the same token: the human picks the second, the server writes the first, on the `elicited` rung — the rung whose whole claim is that the agent never touched the value. The mapping is now **carried**: display → option id, built once, looked up by equality, injectivity checked at the source (two options that render identically are refused, not resolved), and an answer outside the map leaves the pin open instead of being snapped to the nearest row. The leave-as-is row maps to `None`, which no option id can be.

The general shape, and it is not the same one as v0.13: **a rule enforced at a door is a rule every future door must remember, and one always will not.** The question that catches it is *"what is the predicate, and can I name every caller of it?"* — asked structurally, over the AST of the runtime rather than from memory, so a door added later fails the gate instead of slipping past it.

---

## v0.15 — The reader is derived from the writer, and an elected policy is visible whether or not it bound a pin

Two findings from the same reading pass, and the first is v0.14's own move applied to v0.13's half of the problem.

**The floor knew one rule by hand.** v0.13 made `version` a floor that rises only when `nonconforming(data)` is empty, and stated the general shape it was fixing: *a new rule arrives with a writer and no reader.* It then shipped exactly that. `decide()` held six checks as inline `_require` calls; `nonconforming` re-implemented **one** of them from memory, and nothing anywhere forced the next write-time rule to gain a reader — the previous session said so in its own report and could not derive the list.

So the rules an event can be judged by live in **one table**, `EVENT_RULES`, with two callers and no third implementation: `decide()` validates the very dict it is about to append, and `nonconforming` replays the same table over every event already on disk. A rule added there is enforced at the write **and** true of the floor, by construction rather than by memory. The repo's invariant suite closes the class the way v0.14 closed its own: `decide` may hold no rule outside the table, asserted over the AST, and every rule in the table must carry a sample event that violates it — so a rule with no reachable failure fails the gate.

Membership is decided by one question, unchanged from v0.13 and now written where the rules are: **is the violation decidable from the stored event alone?** That is why the table holds the six checks on `source` / `evidence` / `policy_id` / `flip_criteria` / `flip_signal`, and holds neither the quote rule (about who was asked — a boundary the event does not record) nor the v0.12 offered-options rule (it needs the pin's mutable `question`). Six replayed rules instead of one is also a wider floor: a file whose events predate `evidence` (pre-v0.10) now says so under `evidence_rung` instead of being silently stamped as current.

**And a `Policy` was a decision no surface would show unless it happened to cascade.** A policy the human elects over a cluster is an election — the strongest-leverage one in the funnel — yet the map could only reach it by joining **backward** from a pin some cascade had decided. So a policy that bound no pin (every match held back by the severity threshold, or offered by no pin's own question, or matching nothing yet) rendered nowhere at all, while `ledger_summary` counted it and the projected `AGENTS.md` listed it under "Standing rules". Three surfaces, three different answers about one elected rule — which is the divergence this schema exists to refuse, in the schema's own artifact.

The spec's rule was already written, one section up: *"a rung one of the three does not know is the same bug wearing a new name, so adding one means teaching all three."* It said *rung*, and the thing that went missing was the *election*. So it is restated in the general form: **whatever the human elects is a decision, and a decision is visible on all three surfaces or on none.** Concretely — the map leads its list with the standing rules and gives each its own card (rule, scope, the `default_outcome` the user accepted, the rung, the quote, and the decisions that name it, or a plain statement that none do); `ledger_summary` returns `policies_by_evidence` beside `decisions_by_evidence`, because the fit of every `cascaded` decision rests on how *that* election was made; and the `AGENTS.md` region's evidence line gains one sentence when a rule was elected with no rung or relayed with no quote — the only clause there that can fire on an empty `decision_log`, which is precisely the state that was invisible.

The map card also renders `default_outcome` at last: a reader could see **which** rule decided a pin and not **what** that rule writes. Where the two disagree — only reachable by a file written outside the cascade — the card says so rather than showing both values and leaving it to be noticed.

---

## v0.16 — The second predicate: leaving the open set was governed by nobody

v0.14 gave *"may this outcome land on this pin, given that this pin's own question was never put to the human?"* a single home, and the attacks on it failed. What had no counterpart was the question one layer out: **may this pin leave the open set at all, and what does the trail say about it?** Four doors reached a settled pin past every rule the first predicate holds, all four reproduced over real `uv run --script` stdio by an agent with **no human in the loop**:

- **`defer` settled a pin on one check.** `state != "resolved"`, and that was the whole of it: no severity threshold, no election, no quote, nothing appended to the append-only log — and it was agent-reachable as `mcp:ledger_defer` with **zero test coverage anywhere**. A `blocker` `open_decision` posing a session|jwt fork was deferred by the agent alone; `interview_next` went from `asked_count 1` to `0`, `ledger_summary.open_questions` from 1 to 0, and `decision_log` stayed empty. The question stopped being asked and nothing recorded that a choice had been avoided. That is the hole `ledger_decide` has never existed in order to avoid, sitting on the state next to it.
- **`correctness_unknown` did not block closure.** `resolve` enforced the v0.7 observation rung only `if rung is not None`, and `mark_correctness_unknown` writes `rung: None` whenever the caller does not supply one — which the tool's own optional parameter invites. Four agent-only calls (`ledger_add_pin(kind=defect, severity=blocker)` → `ledger_add_remediation` → `ledger_set_remediation_status(done)` → `ledger_mark_correctness_unknown`) left a pin that had just declared its own correctness unestablishable, and `ledger_resolve` then closed it green. `rung: None` inside a `verification` envelope is not "no claim was made"; it is the strongest possible claim that this must not close, and reading it as absence is what let the state this section of the spec exists for be walked straight past.
- **`record_decision` had no settled check at all**, so it re-decided a `resolved` or `accepted` pin back to `decided` while `unasked_verdict` refused the same pin as `already_settled`. Two doors, two answers, one question.
- **`resolution_mode: "asked"` asserted an invariant nothing enforced.** Six sites write it and two read it, both comparing against `"proposed_default"` only. Two of the six carry the assertion as a comment — *"a reopened truth is never re-defaulted silently"*, *"a contested claim is never re-defaulted silently"* — and a policy cascade re-defaulted both, silently. The field whose entire purpose is to record *this pin must be asked* was invisible to the predicate whose entire purpose is to decide whether asking may be skipped.

### `Ledger.settlement_verdict(pin, door)`

One predicate, five doors, one bucket each: `would_settle` · `already_closed` · `wrong_kind` · `not_decided` · `remediation_open` · `unverified`. Every rule that used to live in an individual door lives here — `accept`'s kind check included, because a rule left in its door is a rule the next door has to remember, and the previous four versions of this document are what that costs. `_settle` is the only writer of a settled state and the only place the gate is asked, so passing it is structural rather than remembered.

Two properties of the predicate are load-bearing, and gathering the rules into one function did not by itself give either.

**A rule every door must obey is asked before any door speaks.** The closed check ran *after* the `correctness_unknown` branch had already answered, which made `resolved` an accepting condition for the one door that un-settles a pin: `resolve` → `mark_correctness_unknown` took a pin out of the closed set and back into it, with no `reopen` and nothing recording why finished work had been un-finished — the `CLOSED_STATES` rule falsified by an ordering inside the predicate that introduced it. One table is not one answer unless the shared rules run first.

**A gate needs a move that opens it, and that move must be able to reach it.** `resolved` means *observed*, so a pin whose `verification` envelope never reached a closing rung does not close — and the way out is a later observation, recorded as `rung` on `resolve`. That parameter could not open its own gate: the refusal was returned on the pin's **state**, before anything read the envelope, and `resolve` writes the rung and then re-asks the same predicate with the state unmoved. So the door raised the refusal whose own text told the caller to pass `rung`. The envelope is the single carrier of *how hard was this checked*; the state is not a second one that outranks it. A gate with no gate-opening move is a wall, and this document's own reasoning is that people route around walls.

**And a single carrier is read on both sides, or it is not a carrier.** Deleting that state check was right and was only half the change. The envelope was then read as `if verification is not None`, so **absence became permission**: a `ledger.json` whose pin is `state: "correctness_unknown"` with its remediation done and no `verification` key at all returned `would_settle`, and `ledger_resolve(evidence="I looked")` closed it green — the defect this predicate exists to prevent, re-entered from the other side, on the one state it was written for. A pin carrying no envelope records *less* than one that reached a weak rung, not more. Absence is read as the weaker rung everywhere else in this package — `_client_can_elicit` returns False on any exception, a missing `evidence` reads as unrecorded rather than transcribed — and it is read that way here: the rung must reach `observed` or `cross_derived`, whether the envelope is weak, empty or absent. The cost is stated plainly: every resolve now passes `rung`, unless `cross_derive` already wrote a closing one onto the pin.

The two predicates **compose and are never blended**. `unasked_verdict` answers *who was asked*; `settlement_verdict` answers *may this pin's settlement change*. An election door passes both — the first through `question_offers` at the single-pin door or through `unasked_verdict` where nobody was asked, the second through the door table. A verification door passes only the second, because there is no outcome being elected.

**`SETTLED_STATES` and `CLOSED_STATES` are different sets on purpose**, and that difference *is* the two-doors-two-answers fix. A `decided` pin may be re-elected by the human — that is a correction, the log keeps both events, and only the asked door can do it. A **closed** pin (`resolved` · `accepted` · `deferred`) may not be settled again by anybody: the work is over, and the way back is `reopen`, which records why. So the asked door and the unasked door now answer the same question about a finished pin, and differ only where they should.

### Deferring is an election, because it settles

The spec's own `incompleteness` fork has always offered `{ "id": "defer", "label": "Defer (deferred)" }` as an **option**. Deferring stops the question being asked and takes the pin off `open_questions`; that is a settlement, so it is recorded as one — a `DecisionEvent` with outcome `defer`, a `flip_criteria` saying what brings it back (a deferral with no return condition is a deletion with better manners), and the rung the answer travelled on. `mcp:ledger_defer` demands the human's verbatim words, exactly as `mcp:ledger_record_decision` does.

**And, exactly as `mcp:ledger_record_decision` does, it does not let its caller state that rung.** It briefly did: one keyword, `evidence="elicited"`, settled a `blocker` fork on the rung whose entire claim is that the agent never carried the value — reproduced against a client declaring no elicitation capability, so nobody was asked by anybody. The rung is a fact about **which path ran**, and only the code that ran it can state it: the server's own elicitation path writes `elicited`, and a tool the agent relays through writes `transcribed` and requires the quote. Making deferring an election and then letting the caller describe its own provenance is the invariant re-opened one field to the left.

It is deliberately **not** held to the offered-options rule. `defer` is a meta-answer about scope, not a branch of the pin's own fork, and requiring every question to list a defer option would make punting depend on whoever authored the pin. What holds it instead is what holds `accept`: the human was shown **this** pin, and said not now, in their own words.

### The trail answers the same question at every door

Entering `decided` was always recorded — that is what a `DecisionEvent` is — and the other four transitions were recorded nowhere. Now the `DecisionEvent` states which state the election produced (`settles_as`, an `EVENT_RULES` entry, so the floor replays it and its **absence conforms**: every event written before the field existed produced `decided`, which is what its absence means), and the two doors with no election behind them append a `SettlementEvent`. One entry per settlement and never two: a second record beside the DecisionEvent would be two carriers for one fact, which is the divergence this schema exists to refuse. `ledger_summary` returns `settlements_by_door`, reading **both** carriers — because "4 resolved, 9 deferred" is a different ledger to walk into than "13 closed", and the doors are never summed. An event whose `settles_as` names a state **no** door produces is skipped in that count and reported, as every other broken rule is, under `pre_rule_events`: the write path refuses such a value, and the read path must not — `summary` is what an agent calls *before* acting, so a file it cannot read is a file it acts on blind. **Reading a ledger is never the operation that fails on it**, least of all on the file class `nonconforming` exists to describe.

### `cross_derive` was reopening from the side

Disagreement between two providers is supposed to reopen a pin — *divergence forces human review rather than a tie-break* — and the arc is read-only, like the challenger and the feedback loop. Both of those **append before they move anything**. This one appended nothing, un-decided a human-elected pin, un-closed a `resolved` one, and — the part that matters most — **overwrote `pin["question"]` with options composed from the caller's own derivations**. `question.options[].id` is the carrier the entire offered-options rule anchors on at both doors, so an agent that rewrites it decides what the human is allowed to choose next: the invariant v0.12 through v0.14 built, dismantled from the side.

So: the disagreement is appended as an immutable `xdr_` event before anything moves; the pin's own question is left exactly as it was, and one is written only where none exists (creating a fork is what `surface_assumption` legitimately does — replacing one is not); and a **closed** pin is recorded and not reopened, because un-closing finished work needs its own justification and has its own arc.

What the tool reports as `reopened` is that event's own field, read back — not a second derivation from the pin. Derived, it was `substate == "contested"`, which is a *different fact wearing the same name*: `substate` is written by the reopen and never cleared, so a second, **agreeing** derivation reported `reopened: true` while the event it had just written recorded `false`. Two carriers for one fact, disagreeing, in the return shape of the tool whose whole subject is two derivations disagreeing.

### A policy scope must name real fields

`applies_to` was matched with `pin.get(k) == v`, which is `True` for **every** pin when `k` is not a pin field and `v` is null. `applies_to={"nope": null}` was therefore a universal selector wearing a filter's clothes, reproduced end to end through `mcp:ledger_record_policy`. The radius is the thing a human elects a policy *from*, so a scope key that matches by not existing is not a narrow bug — it is the preview describing a different policy than the one being set. Scope keys are now checked against `PIN_FIELDS`, and a test holds that constant to what the writers actually write, so a field added to the envelope without becoming scopeable fails rather than silently becoming unmatchable.

### One answer per question, on every surface that reports it

Three more readings of one ledger disagreed, each found by opening the map in a browser rather than by any test:

- **How many standing rules must a reader weigh?** The map badged two on the repo's own preview fixture and the projected `AGENTS.md` said one — the map asked *is the rung weak*, the projection asked *is the quote missing*. Neither was wrong on its own terms, which is exactly why a reader could act on neither. `Ledger.policy_weakness(policy)` is now the single answer (`no_rung` · `unknown_rung` · `unquoted_relay`), applied once in Python and **inlined into the map** the way `decision_rung` already is; only the wording stays per-surface, because a badge and a line of always-on context address different readers. A relay **with** the quote is deliberately not on the list: the weak rung is permitted precisely because the quote is there to be weighed.
- **A rung the surface does not know is not an absent one.** A card badged the rung the file records and printed *"no evidence rung recorded"* underneath it — one card asserting both. Three states, not two: known, recorded-but-unknown-here (most likely added to the schema after the artifact was generated), and absent.
- **The map kept its own list of settled states.** v0.16 made `deferred` one of them and that hand-written list did not learn it, so a deferred `blocker` was counted as an open blocker in the loudest colour the page has — reporting a question the human had answered as one nobody had. The set is taken from `SETTLED_STATES` now, and the bar says *settled* rather than *resolved*, because one of those states means "not now".

Same rule as the rung table one section up, one turn further: **a surface that re-decides a classification is a second implementation of it**, and two implementations of one rule have already begun to drift.

### The general shape

v0.14's was *"a rule enforced at a door is a rule every future door must remember."* This one is one layer out and is not the same: **a predicate answers the question it was written for, and says nothing about the question next to it.** `unasked_verdict` was correct, complete and well-tested — for *what may be written*. Nothing asked *whether this pin may stop being open at all*, so four doors answered it independently and one of them answered it with nothing. The question that catches it is not "is the predicate sound" but *"name the state transition, and say which predicate governs it"* — asked of every transition, not only of the one that was just fixed.
