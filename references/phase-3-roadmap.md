# Phase 3 — Diff & Roadmap (derive the work)

Turn decided pins into a dependency-sequenced plan. Nothing here is authored by hand: the work
is the mechanical diff between the elected `to_be` and the observed `as_is`, ordered by the
dependency graph.

## Steps

1. **Compute the delta per decided pin.** For each pin in `decided` (directly or via a
   policy), diff `to_be` against `as_is` and emit one or more `RemediationItem`s with an
   `action`: `align` | `consolidate` | `implement` | `refactor` | `delete`. `accepted` and
   `deferred` pins produce no items.
2. **Build the dependency DAG** from `pin.depends_on`. "Align contracts before touching logic"
   is not hardcoded — it falls out: a logic pin whose correct behavior depends on a field's
   shape `depends_on` that contract pin; an `align` item `depends_on` the "elect canonical
   source" decision that tells it which layer is truth.
3. **Topologically sort.** Within a topological level, order by `severity`, then `effort`
   (cheap wins first).
4. **Detect cycles.** Mutual `depends_on` = a knot (e.g. two contracts each assumed as the
   other's truth). Surface it as a blocker pin: the user must pick which to break first. Do not
   auto-resolve.
5. **Emit `roadmap.ordered_item_ids`** plus a human-facing plan.

## The waves (emergent, not hardcoded)

The topology almost always produces this shape — present it this way, but let the DAG decide:

- **Wave 1 — Truths & contracts.** Elect canonical sources; `align` the data model and
  cross-layer contracts. Everything else depends on this.
- **Wave 2 — Fill gaps.** `implement` the `incompleteness` items the user scoped in.
- **Wave 3 — Logic & structure.** `refactor` wrong logic; `consolidate` duplicated copies.
- **Wave 4 — Cleanup.** `delete` dead code, collapse remaining dupes.

## Guardrail
Never schedule a rewrite. Every item is minimum-change (the Phase-4 ladder enforces this).
"Rewrite module X" appears ONLY if the user explicitly opted a `design_concern` into a rewrite
in Phase 2 — otherwise scope creep is a bug, not a plan.
