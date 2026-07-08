# Phase 2 — Interview (elect the to-be)

Goal: resolve the pins that need human judgment into a validated `to-be` spec **without
drowning the user in questions**. The interview is a filtered view over pins in state
`needs_input`, generated entirely from Phase 1. It is never an open-ended "tell me about
your app" script.

## The core reframe

The enemy is not the number of problems — it is the number of **decisions**. 200 SQL-i
findings are ONE decision ("parameterize everywhere?"). 15 divergent copies of an auth
helper are ONE decision ("consolidate onto which copy?"). The interview's first job is not
to ask, it is to **collapse pins into decisions**.

## The compression funnel (mandatory)

```
pins  →  clusters  →  policies  →  real questions (asked)  →  proposed defaults (bulk skim)
```

### 1. Cluster
Group pins sharing a decision under one `cluster_id` (the contract-reconciliation and
duplication modules already cluster; extend by decision-similarity). Ask ONCE per cluster;
apply the answer to the whole group. This alone typically takes 200 → ~20.

### 2. Policy questions first (highest leverage, 4–5 total)
Category-level rules that auto-resolve whole clusters by default. Ask these before any
case-level question. Examples:
- "For schema mismatches, is the DB the source of truth unless noted?"
- "Dead code with no inbound reference → remove by default?"
- "Duplication → consolidate onto the most-tested copy?"

Each answer becomes a `Policy` entity. Cascading a policy over matching pins emits
`DecisionEvent`s with `source: "policy:<id>"` — still user-originated, just amplified. ~20
clusters often reduce to ~5 policies covering the bulk.

### 3. Exception questions (only what policy doesn't cover)
What remains to ask for real: pins that contradict a policy, plus genuine `ambiguity` and
`design_concern` pins. These are few and they are the valuable ones — the true forks where
the user's intent changes what would be built.

### 4. Proposed defaults (the long tail)
Everything else is not asked. Attach a low-confidence proposed resolution (marked as a
guess), presented in bulk grouped by type. The user skims, overrides the few they disagree
with, accepts the rest. Review by exception, not by enumeration — the same principle as the
map (review the pins, not the whole wiki).

### 5. Severity threshold (hard rule)
- `blocker` / `high` → **never** silent default. Always `asked`, or at minimum top of the
  review batch.
- `medium` / `low` → may be `proposed_default`.

Volume drops sharply, but nothing important slips through passively.

### 6. Order by information gain
Among `asked` questions, ask first those that collapse the most downstream pins once
answered. Stop when the marginal question resolves little; deepen on demand. The first ~10
do ~90% of the work.

Result of the funnel: **200 pins → ~20 clusters → ~5 policies → ~10 real questions → the
rest as skimmable proposed defaults.**

## Question shape

Keep each question short: `prompt` + 2–3 `options` (+ freeform escape). All detail — the
divergent shapes, anchors, evidence — lives behind the pin on the map, pulled up on demand.
The question is not detailed; the map is. Options are usually derived directly from the
mismatch (each divergent layer shape becomes a candidate truth).

**Example (contract_mismatch):**
Prompt: "The frontend checks a `superadmin` role the DB doesn't define. What is the intended
set of roles?"
Options: `{admin,user} — DB is truth` · `add superadmin to schema` · (freeform)

## Kind-specific handling

- `design_concern` → OPTIONS, not findings. "Leave as-is" (`state: accepted`) is a valid
  answer; `to_be` stays null until the user chooses. Never phrase it as a defect.
- `ambiguity` (blocker) → must be resolved before the to-be for that area is knowable; put
  high in the order.
- `defect` → usually `question: null`; goes to remediation. Promote to `needs_input` only
  when there's a genuine scope question (e.g. "is this dead code residue, or a half-built
  feature you want completed?").
- `incompleteness` → question is typically scope: implement now / defer / drop (YAGNI).

## Parallelism with the map and brainstorm

Every question carries a reference to the pin(s) it came from, so the UI can cross-link:
click the question → the map highlights the involved nodes; click a pin → its question
surfaces. If the user opens a brainstorm on a pin, the brainstorm writes
`proposals[]`; the user's committed answer here (and only here) sets `state: decided` and
emits the `DecisionEvent` (with `flip_criteria`). The interview commits; the brainstorm
never does.

## Output

Updated ledger: `Policy` entities, `Question` objects on pins, and `DecisionEvent`s for
every committed answer (direct or policy-cascaded). Decided pins now carry a derived
`to_be`. Phase 3 diffs `to_be` against `as_is`.
