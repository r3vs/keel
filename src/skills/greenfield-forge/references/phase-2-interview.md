# Phase 2 — Interview (elect the to-be)

Resolve the `open_decision` pins from Phase 1 into a committed `to-be` spec. The **mechanism is
shared** — read `references/core/interview-funnel.md` first; it is authoritative for the funnel (cluster →
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

> **The frame is code, not a script to improvise.** The `interview_next` tool expands the decision
> catalog into `open_decision` / `acceptance_criterion` pins and seeds the per-cluster default
> policies, then returns the funnelled view in catalog order, threshold already enforced.
> Improvising the question order is how "what are the core entities" ends up asked third, after two
> questions its answer would have collapsed.

## The hard forks — brainstorm before deciding

For a genuinely open architectural fork (monolith vs services, datastore family, API style), the
user can open a **brainstorm** (`references/core/brainstorm.md`): 2–3 designs with tradeoffs, disciplined by
the ponytail ladder and referencing how well-architected systems solve that specific problem. The
brainstorm proposes; only the answer committed here decides.

## flip_criteria is not optional here

In greenfield you decide **before you know the app** — on the least information you will ever have.
So every committed `DecisionEvent` must carry a `flip_criteria`: the observable condition under
which to reopen it ("chose a modular monolith; reopen if a module needs independent scaling",
"single-tenant; reopen when a second tenant is real"). This is what stops an early decision made
on thin information from fossilizing — the ledger becomes a living ADR that knows when it is stale.

## Kind-specific handling

- `acceptance_criterion` (from Phase 1) → resolve **first**: they root the DAG, so electing which
  outcomes are in v1 collapses the most downstream forks. Electing an outcome as `deferred` prunes
  a whole subtree of architecture decisions with it.
- security `open_decision` (from the threat-model pass) → the policies carry the bulk (default-deny
  authz, validate-at-boundary, encrypt PII); only genuine forks on sensitive assets are `asked`.
  "Accept this risk" is a legitimate recorded answer for a low-value asset — never phrased as a defect.
- `open_decision` (high fan-out) → always `asked`, high in the order; its answer unblocks a whole
  subtree of dependent forks.
- `open_decision` (leaf / stylistic) → may be `proposed_default` (the architectural policies
  usually cover it); the user skims and overrides by exception.
- A fork the user wants to punt → `deferred`: it leaves v1 scope as a future backlog item (the
  natural handoff to `slice` mode later), not silent scaffolding.

> **Composability (optional):** the `learning-layer` skill can wrap this surface non-invasively —
> capture the user's own decision attempt *before* the derived `to_be` is revealed, then teach the
> 1–2 highest-leverage misses. It never blocks or alters the interview; absent it, this runs as
> written.

## Challenge the oracle (before it becomes the contract)

In greenfield the stakes are higher than in rescue: the elected `to_be` doesn't just guide a fix, it
becomes the **contract** every layer is generated from (Phase 3). An unsound decision here propagates
into DB schema, API, and client *by construction* — the very drift-proofing that makes greenfield
strong also makes a bad oracle harder to walk back. So before Phase 3, the `challenger`
(`references/core/agents.md`, the reviewer's upstream twin) red-teams the committed decisions
(`references/core/decisions-ledger-spec.md` v0.6):

- **unfalsifiable** — an `acceptance_criterion` with no testable `verify`; it can't root a Track-A
  test, so it can't root the DAG. Reopen for a testable form.
- **inconsistent** — two decisions (or a policy and a fork) that can't both hold in one design.
- **unsatisfiable** — a `to_be` not reachable from the `givens` (e.g. "on-prem, no cloud" vs a
  managed-service choice).
- **unstated_assumption** — a decision resting on a brief gap the agent filled silently
  (`references/core/assumptions.md`); reopen with it surfaced.
- **ignored_fanout** — a high-`depends_on` fork resolved as a silent default instead of `asked`.

> **Start from the mechanized classes.** `challenge_oracle` decides the ones that need no judgment
> — a criterion with no `verify` is unfalsifiable as a matter of fact — and returns proposals
> without writing. That output is where the `challenger` agent begins; its judgment belongs on the
> classes a checker cannot reach (`unsatisfiable` against the givens, `unstated_assumption`).

A sustained challenge emits an immutable `ChallengeEvent`, returns the pin to `needs_input`
(`challenged`), and reopens the **minimum** (the fork + genuine dependents) back into this interview.
The challenger **challenges, never decides**; only a re-answer commits. Catching an unsound decision
now costs one question; catching it after the contract is generated costs a regeneration across
every layer.

## Output

Updated ledger: `Policy` entities, `Question` objects on pins, a `DecisionEvent` (with
`flip_criteria`) for every committed answer — direct or policy-cascaded — and any `ChallengeEvent`s
from the challenge pass. Decided pins now carry a derived `to_be` (the elected spec); challenged pins
are back in `needs_input`. The to-be map fills in: ghost nodes gain their committed shape. Phase 3
turns the *surviving* decided pins into the contract and the build backlog.
