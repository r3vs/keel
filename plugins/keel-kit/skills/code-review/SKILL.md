---
name: code-review
description: Review a change against the contract it claims to satisfy, and reopen rather than decide — a reviewer surfaces findings as pins, never elects the fix. Covers requesting a review, giving one, and receiving one without deferring to authority. Use before merging, when asked to review a diff or PR, or when responding to review feedback.
license: MIT
---

# Code Review

The reviewer is a **read-only role** (`references/core/agents.md`). That is not a limitation on
thoroughness — it is the property that makes review safe to automate: a reviewer who can also change
the code will fix what it thinks is wrong, and a wrong fix applied confidently is worse than a
finding raised and rejected. **Reviewers reopen. The human elects.**

## Requesting a review — give the contract, withhold the conclusion

Hand over the diff **and what it is supposed to satisfy** (the pin, the criterion, the contract).
Do **not** hand over your conclusion that it does. A reviewer told "this correctly implements X"
evaluates your sentence, not your code — the agreement it produces is worthless because it was
primed. State the claim as a question, or state nothing.

Include: the pins in scope, how you verified it, and what you are unsure about. Uncertainty is the
most useful thing you can pass on and the easiest thing to omit.

Withholding the conclusion is half of it; the other half is independence from the author. Re-running
the tests the author already passed proves nothing an author building *to* those tests could not
have staged — so the behavior is **exercised against the elected criterion by a role that did not
write the code**, never trusted from the author's own run.

In the full workflow that role is the `measurer`, which runs its evidence gate *before* review
precisely so the deterministic proof is independent and paid for once
(`references/core/agents.md`). A reviewer reading that record is **not** accepting the author's
self-report — it is reading an independent re-execution — and re-running a deterministic check a
second time buys nothing, because determinism means the second run cannot disagree. What does not
duplicate is judgment: the evidence proves the criterion *passes*, and the reviewer judges whether
it passes **for the right reason**. Reviewing standalone, with no measurer in the loop? Then
exercising the behavior yourself is on you — the independence requirement is on the *role that ran
it*, not on which name it wears.

## Giving a review — precedence, first match wins

Work in this order and stop at the first that applies:

1. **The contract is misread.** The change satisfies something other than what the pin says. **Fix
   the contract first** — everything downstream is noise until the target is agreed. This is the
   finding people skip, and it is the most valuable one.
2. **Valid and actionable.** A defect, a missing case, a real risk. Say what breaks and under which
   input — a finding without a failure scenario is an opinion.
3. **Valid trade-off.** Legitimate, with costs the author may have accepted deliberately. Say so as
   a trade-off, not a defect.
4. **Noise.** Style a formatter should own, preference, restatement. Do not raise it.

**Bound the loop.** Three cycles maximum. If the same class of finding recurs past that, the
disagreement is about the contract, not the code — escalate it to a pin and let the interview settle
it. And watch for review theater: more than two rounds producing nothing actionable means you are
validating, not reviewing. Say that out loud rather than manufacturing findings.

## Receiving a review — neither defer nor defend

- A finding is a hypothesis about your code. **Check it.** Correct findings get fixed; incorrect
  ones get answered with evidence.
- **Authority is not evidence.** "A senior said so" and "the model said so" are the same claim, and
  neither is a reason. Ask for the failure scenario.
- Disagreement that survives explanation is a **pin**, not an argument to win. Record it, let it be
  elected, move on.

## Binding to the ledger

Bind it through the `ledger_*` MCP tools — the server resolves paths, so they work from the user's
cwd (see `using-the-ledger`).

The reviewer is **read-only** (`edit: deny`) — it reads the ledger with `ledger_summary`, it does
not write it.

- A finding is surfaced as a pin — `defect` (it is wrong), `design_concern` (a trade-off worth
  electing), or `incompleteness` (it is unfinished) — but the pin is **written by the executor
  acting on the verdict** (`add-pin`), never by the read-only reviewer itself.
- **A reviewer never sets `state: decided`.** It returns a verdict — `MERGE` / `ADJUST` / `REJECT` —
  that restarts the item; the same neutrality the `brainstorm` and `challenger` hold: it surfaces, it
  never elects. (The roles that *reopen* an elected decision are the `challenger` upstream and the
  feedback loop downstream — not the reviewer.)
- If review reveals the *elected decision* was wrong rather than the code, hand the evidence to the
  **`challenger`** (`references/core/agents.md`) — that is the **upstream** arc: the oracle was
  never satisfiable, and the build is what exposed it. Do not route it through the feedback loop
  (`references/core/feedback-loop.md`), which is the *downstream* arc for a decision that **was**
  sound until production moved. Same reopen, opposite ends of the lifecycle, different evidence and
  different repair — and only the challenger's `ChallengeEvent` records the argument, so a reopen
  taken here would land in an append-only ledger with no *why*. Patching code to satisfy an unsound
  decision hides the finding that actually mattered.
