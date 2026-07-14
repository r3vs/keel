# The Interview Compression Funnel (shared core)

The interview mechanism is **shared by both skills**. It is the same machine in both:
a filtered, compressed view over the pins in state `needs_input`, that resolves them into
committed decisions **without drowning the user in questions**. What differs is only the
*source* of the pins — and that lives in each skill's Phase-2 playbook, not here:

- `codebase-rescue` — pins are **code findings** (`skills/codebase-rescue/references/phase-2-interview.md`).
- `greenfield-forge` — pins are **open decisions** (`skills/greenfield-forge/references/phase-2-interview.md`).

This file is the authority for the *mechanism*. Read it before writing either skill's interview.

## The core reframe

The enemy is not the number of pins — it is the number of **decisions**. In rescue, 200
SQL-injection findings are ONE decision ("parameterize everywhere?"). In greenfield, twelve
forks about API shape may collapse to ONE policy ("the shared-types package is the contract").
The interview's first job is not to ask — it is to **collapse pins into decisions**.

Neither skill's interview is an open-ended "tell me about your app / your code" script. It is
always driven by concrete pins with 2–3 options each. (In greenfield, "tell me about your app"
is the exact failure mode to avoid: an open chat lets the model fill unmade decisions with
silent assumptions — which is how slop is born. The decision-catalog replaces the open chat.)

## The funnel (mandatory)

```
pins  →  clusters  →  policies  →  real questions (asked)  →  proposed defaults (bulk skim)
```

1. **Cluster.** Group pins sharing one decision under a `cluster_id`; ask ONCE per cluster and
   apply to the group. Typically 200 → ~20.
2. **Policy questions first** (4–5, highest leverage). Category-level rules that auto-resolve
   whole clusters by default. Each becomes a `Policy`; cascading it emits `DecisionEvent`s with
   `source: "policy:<id>"` — still user-originated, just amplified. ~20 clusters → ~5 policies.
3. **Exception questions** — only what a policy doesn't cover: pins that contradict a policy,
   plus the genuine forks (rescue: `ambiguity` / `design_concern`; greenfield: high-fan-out
   `open_decision`). Few, and the valuable ones.
4. **Proposed defaults** — the long tail. Attach a low-confidence proposed resolution (marked
   as a guess), presented in bulk by type. The user skims, overrides by exception, accepts the
   rest. Review by exception, not by enumeration.
5. **Severity threshold (hard rule).** `blocker`/`high` → **never** silent default (always
   `asked`, or at minimum top of the review batch). `medium`/`low` → may be `proposed_default`.
6. **Order `asked` questions by information gain** — those that collapse the most downstream
   pins once answered go first. The first ~10 do ~90% of the work.

Result: **200 pins → ~20 clusters → ~5 policies → ~10 real questions → the rest as skimmable
proposed defaults.**

## Question shape (both skills)

Keep each question short: `prompt` + 2–3 `options` (+ freeform escape). All detail — divergent
shapes and evidence (rescue), or option implications and downstream `depends_on` (greenfield) —
lives behind the pin on the map, pulled up on demand. **The question is not detailed; the map
is.** Options are derived, not invented: from the divergent layer shapes (rescue) or from the
decision-catalog's option set (greenfield).

## What only the interview may do

Only the interview commits a decision: it sets `state: decided` and emits the `DecisionEvent`
(with `flip_criteria`). The brainstorm (`references/core/brainstorm.md`) only writes `proposals[]` and
never decides. This separation is what keeps the interview neutral in both skills.
