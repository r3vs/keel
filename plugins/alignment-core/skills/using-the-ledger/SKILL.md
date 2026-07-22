---
name: using-the-ledger
description: Use the shared decisions ledger correctly from any task — read pins, add a finding, run the compressed interview, record a decision with flip_criteria, and never let an agent commit a decision the human did not elect. The spine both codebase-rescue and greenfield-forge run on.
license: MIT
---

# Using the Ledger

The decisions ledger is the single source of truth the whole package runs on. This is the short
"how to use it" for any task; the authority is `references/core/ledger.md` (schema
`references/core/decisions-ledger-spec.md`).

## The rules that matter
- One `ledger.json`; the map, interview, and brainstorm hold no state — they project a view over it.
- A `Pin` is a delta `gap = diff(to_be, as_is)`, discriminated by `kind`. `to_be` is DERIVED from
  the user's elected decision — never authored from code.
- **Only the interview commits.** No agent sets `state: decided` or writes a `DecisionEvent`; the
  brainstorm writes `proposals[]` only. The human elects.
- Every `DecisionEvent` carries a `flip_criteria` (when to reopen) — essential for decisions made
  on thin information.
- Compress questions with the funnel (`references/core/interview-funnel.md`): cluster → policy → exception →
  proposed-default; `blocker`/`high` never go to silent default.

## Use it to
- read the current pins/decisions before acting;
- add a finding as a pin (with `confidence`/`provenance`; deterministic static findings carry
  `extracted` and skip fp-check);
- record an elected decision (interview only) with a `flip_criteria`;
- feed the feedback loop (`references/core/feedback-loop.md`): a fired `flip_signal` reopens a pin.

## Operate it through the runtime — never by hand

Every rule above is enforced in code. A hand-written pin in `ledger.json` bypasses all of them
**silently**: kind validation, the severity threshold, append-only events, the
`agent_assumption` confidence rule. There is no error — just a ledger that quietly stopped meaning
what the spec says it means.

| you want | MCP tool |
|---|---|
| the state, before acting | `ledger_summary` |
| the next real questions | `interview_next` |
| add a finding / defect / `open_decision` | `ledger_add_pin` |
| plan & close the gap | `ledger_add_remediation` · `ledger_set_remediation_status` · `ledger_resolve` |
| surface a forced assumption | `ledger_surface_assumption` |

The reads are automatable **and so is every non-electing write** — add a finding, plan its
remediation, mark an item done, resolve a pin. `ledger_resolve` demands `evidence` (what you
*observed* closed the gap, not that code was written): the tool itself enforces `resolved =
observed`. What stays off-limits to every agent is the one **electing** write — only the human's
committed interview answer sets `state: decided` and appends a `DecisionEvent`, so there is
deliberately no `ledger_decide` tool.

**The MCP tools are the only channel.** The server's location is resolved by the host, so the
`ledger_*` tools work from the user's project cwd — the whole class of path-resolution bugs a bundled
CLI carried simply disappears. All four hosts reach the server this way: Claude Code and Codex through
`.mcp.json`, opencode through its plugin's config hook, and Pi through the bridge extension this
package ships. It needs `uv` on PATH (the host spawns the server as `uv run`); that is a hard
prerequisite, and its absence fails loudly rather than degrading to a path that cannot resolve.

**Reading a ledger that isn't there is not an empty ledger.** The tools refuse a missing path rather
than answering "no pins", because that answer reads as "nothing to do" and is the most expensive
wrong answer this package can give.
