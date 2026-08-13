---
name: using-the-ledger
description: Use the shared decisions ledger correctly from any task — read pins, add a finding, run the compressed interview, record a decision with flip_criteria, and never let an agent commit a decision the human did not elect. The spine both codebase-rescue and greenfield-forge run on.
disable-model-invocation: true
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
- read the current pins/decisions before acting — `ledger_summary`, never by opening the file;
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
| the next real questions | `interview_next` (create them first with `interview_expand`) |
| the opening policy offers, before asking anything | `interview_seed_policies` (offers only — a Policy exists once the human elects it) |
| what a rule would decide, before proposing it | `policy_preview` (writes nothing; `would_decide` is what the user is really electing) |
| the human accepted a policy | `ledger_record_policy` (creates it and cascades it — nothing else does either) |
| add a finding / defect / `open_decision` | `ledger_add_pin` |
| the human answered a fork | `ledger_record_decision` |
| plan & close the gap | `ledger_add_remediation` · `ledger_set_remediation_status` · `ledger_resolve` |
| surface a forced assumption | `ledger_surface_assumption` |
| the work was done but correctness is not establishable | `ledger_mark_correctness_unknown` |
| the human said not now | `ledger_defer` (an election: it settles the pin, so it is quoted like any other) |
| the tracker your team reads, brought level with the ledger | `tracker_project` · `tracker_diff` (read-only) — see `references/tracker-projection.md` |

**`ledger_summary` is the first act, before anything else on this page** — not `Read`, not `cat`,
not a `jq` over `ledger.json`. The typed read is the guarded read: it resolves the path the host
resolved, it *refuses* a ledger that is not there instead of answering "no pins", and it returns the
shape the spec guarantees rather than whatever a hand-parse made of a file the schema has since
moved on from. An agent that opens the file to read it has already left the channel, and the write
is the next thing it will do by hand.

The reads are automatable **and so is every non-electing write** — add a finding, plan its
remediation, mark an item done, resolve a pin. `ledger_resolve` demands `evidence` (what you
*observed* closed the gap, not that code was written): the tool itself enforces `resolved =
observed`, and it refuses a pin whose verification never reached the `observed` / `cross_derived`
rung — a weak envelope, an envelope with no rung, and **no envelope at all** alike, because none of
them records an observation. So pass `rung` once you have actually observed it, unless
`ledger_cross_derive` already agreed the claim onto the pin. Its two honest
exits matter as much: `ledger_mark_correctness_unknown` when the evidence stack was walked and
nothing could speak, and `ledger_defer` when the work is out of scope — a pin that leaves the loop by
either door is still on the ledger, which is the difference between scoping and forgetting.

**Deferring is the exception to "every non-electing write is automatable", because it is not one.**
It settles the pin: the question stops being asked and `open_questions` drops. So `ledger_defer` is
the third electing door and wants what the other two want — the user's verbatim answer, and a
`flip_criteria` saying what brings the fork back.

**Electing stays the human's; recording it is yours.** `ledger_record_decision` writes the
`DecisionEvent` and moves the pin to `decided`, and it cannot be used to choose: the outcome must be
one the pin's own `question` offered, freeform only where the question allows it, and
`flip_criteria` is required so nothing fossilizes. If the host supports elicitation the **server**
asks the user and writes the reply itself — you never carry the value, and whatever you passed is
ignored. Otherwise you relay, and must quote the user verbatim in `human_answer`; that lands as
`evidence: transcribed`, the weaker rung, visible to anyone reading the log. There is still no
`ledger_decide`: no tool elects on its own authority.

The same holds one level up, where it matters more. `ledger_record_policy` records a **policy** the
human accepted and cascades it over the cluster — many pins from one answer — so it is held to the
same discipline: a catalog offer is taken verbatim by `offer_id`, any other policy must state its
rule, scope and outcome and quote the user, and the server asks the user itself where the host can
elicit. Preview the radius first (`policy_preview`); the cascaded decisions record
`evidence: cascaded` and point back at the policy, so nothing later claims a relay nobody made.

**Including the rule that matters most: `default_outcome` is an option id, and a pin gets it only if
its own `question` offers it.** Pins that don't come back in `not_offered`, still open — ask them.
That is the same check `ledger_record_decision` makes for one pin, and a policy decides more pins
than one decision does, so it is not governed less. It cascades **once**, over the radius the user
was shown; pins found later are asked, or covered by a policy elected with them in view.

**One predicate, every door.** That rule plus the severity threshold is one question asked in one
place: *may this outcome land on a pin whose own fork was never put to the human?* Two tools reach
it — the policy cascade, and `interview_expand`'s `brief_decisions`, whose held-back forks come back
in `brief_held_back` and get asked. There is no cluster flag on `ledger_record_decision`: it decides
the one pin the user answered about, and a fan-out is a policy, which is the only thing that can
name the rule and the radius it covers.

Use it. A pin that never reaches `decided` blocks its own remediation, its dependents, and the
reopen loop — the analysis was done and none of it can land.

**The MCP tools are the only channel.** The server's location is resolved by the host, so the
`ledger_*` tools work from the user's project cwd — the whole class of path-resolution bugs a bundled
CLI carried simply disappears. All four hosts reach the server this way: Claude Code and Codex through
`.mcp.json`, opencode through its plugin's config hook, and Pi through the bridge extension this
package ships. It needs `uv` on PATH (the host spawns the server as `uv run`); that is a hard
prerequisite, and its absence fails loudly rather than degrading to a path that cannot resolve.

**Reading a ledger that isn't there is not an empty ledger.** The tools refuse a missing path rather
than answering "no pins", because that answer reads as "nothing to do" and is the most expensive
wrong answer this package can give.

## Where the ledger reaches people who never open it

Two projections, one shape. A fresh agent gets the elected design through `generate_instructions`,
which writes a fenced region into the `AGENTS.md` every host loads. A **team** gets the open pins
through `tracker_project`, which writes one issue per open pin into the tracker they already stand
in front of — generated, fenced, closed when the pin settles.

Both are windows. Neither is a door: an answer typed into an issue comment, like a decision written
into the `AGENTS.md` region, elects nothing and is read by no tool. Both report a hand-edited region
instead of overwriting it, because what somebody wrote there may be the only copy of a real
decision — and the fix for both is the same, to put it in the ledger and re-project.

`tracker_diff` does now **show** you the comments — `awaiting_human_review`, one entry per comment
on a projected issue, carrying the pin it belongs to. Reading is not writing: the queue exists so a
fork answered in a thread stops being invisible to everyone holding the ledger, and every entry ends
in the interview, in a pin, or in nothing. The full playbook, including what each drift verdict
means, how to work that queue, and what stays the team's: `references/tracker-projection.md`.
