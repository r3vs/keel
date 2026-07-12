---
name: using-the-ledger
description: Use the shared decisions ledger correctly from any task — read pins, add a finding, run the compressed interview, record a decision with flip_criteria, and never let an agent commit a decision the human did not elect. The spine both codebase-rescue and greenfield-forge run on.
license: MIT
---

# Using the Ledger

The decisions ledger is the single source of truth the whole package runs on. This is the short
"how to use it" for any task; the authority is `core/ledger.md` (schema
`core/decisions-ledger-spec.md`).

## The rules that matter
- One `ledger.json`; the map, interview, and brainstorm hold no state — they project a view over it.
- A `Pin` is a delta `gap = diff(to_be, as_is)`, discriminated by `kind`. `to_be` is DERIVED from
  the user's elected decision — never authored from code.
- **Only the interview commits.** No agent sets `state: decided` or writes a `DecisionEvent`; the
  brainstorm writes `proposals[]` only. The human elects.
- Every `DecisionEvent` carries a `flip_criteria` (when to reopen) — essential for decisions made
  on thin information.
- Compress questions with the funnel (`core/interview-funnel.md`): cluster → policy → exception →
  proposed-default; `blocker`/`high` never go to silent default.

## Use it to
- read the current pins/decisions before acting;
- add a finding as a pin (with `confidence`/`provenance`; deterministic static findings carry
  `extracted` and skip fp-check);
- record an elected decision (interview only) with a `flip_criteria`;
- feed the feedback loop (`core/feedback-loop.md`): a fired `flip_signal` reopens a pin.
