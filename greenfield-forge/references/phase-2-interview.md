# Phase 2 — Interview (elect the to-be)

Resolve the `open_decision` pins from Phase 1 into a committed `to-be` spec. The **mechanism is
shared** — read `core/interview-funnel.md` first; it is authoritative for the funnel (cluster →
policy → exception → proposed-default), the severity threshold, and information-gain ordering.
This playbook is only how *greenfield* sources and frames the pins.

## What differs from rescue

The pins are **open decisions**, not code findings. So:

- **Policies are architectural defaults**, offered first because they carry the most leverage:
  - "Prefer boring, proven technology over novel."
  - "One relational datastore until a concrete need proves otherwise."
  - "Modular monolith, not services, in v1."
  - "Server-render unless interactivity genuinely demands a SPA."
  - "Generate every layer from one contract; never hand-duplicate a shape."
  Each becomes a `Policy` that auto-resolves the matching long-tail forks by default; the user
  overrides by exception.
- **Information-gain order is the catalog order**: domain model and persistence first (they fan
  out to everything downstream), delivery and observability last. Answering "what are the core
  entities and what's in v1" collapses more of the tree than any other question — ask it first.
- **Options come from the catalog**, each carrying its downstream implication, so the user sees
  what a choice commits them to before choosing.

## The hard forks — brainstorm before deciding

For a genuinely open architectural fork (monolith vs services, datastore family, API style), the
user can open a **brainstorm** (`core/brainstorm.md`): 2–3 designs with tradeoffs, disciplined by
the ponytail ladder and referencing how well-architected systems solve that specific problem. The
brainstorm proposes; only the answer committed here decides.

## flip_criteria is not optional here

In greenfield you decide **before you know the app** — on the least information you will ever have.
So every committed `DecisionEvent` must carry a `flip_criteria`: the observable condition under
which to reopen it ("chose a modular monolith; reopen if a module needs independent scaling",
"single-tenant; reopen when a second tenant is real"). This is what stops an early decision made
on thin information from fossilizing — the ledger becomes a living ADR that knows when it is stale.

## Kind-specific handling

- `open_decision` (high fan-out) → always `asked`, high in the order; its answer unblocks a whole
  subtree of dependent forks.
- `open_decision` (leaf / stylistic) → may be `proposed_default` (the architectural policies
  usually cover it); the user skims and overrides by exception.
- A fork the user wants to punt → `deferred`: it leaves v1 scope as a future backlog item (the
  natural handoff to `slice` mode later), not silent scaffolding.

## Output

Updated ledger: `Policy` entities, `Question` objects on pins, and a `DecisionEvent` (with
`flip_criteria`) for every committed answer — direct or policy-cascaded. Decided pins now carry a
derived `to_be` (the elected spec). The to-be map fills in: ghost nodes gain their committed
shape. Phase 3 turns those decided pins into the contract and the build backlog.
