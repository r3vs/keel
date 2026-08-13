---
name: prototype
description: Answer one design question with throwaway code instead of more conversation — a runnable state/logic demo, or several radically different UI variations to react to. Raises an open_decision from talk to something observed, and the human still elects. Use when a decision turns on how something behaves or looks and arguing about it on paper has stopped converging.
disable-model-invocation: true
license: MIT
---

# Prototype

A prototype is **throwaway code that answers one question**. Not a head start on the build, not a
demo, not a spike that quietly becomes production — one question, answered, then the code stops
mattering and the answer does not.

It exists here for a specific reason. This package's weakest evidence is conversation: a fork about
*how something should behave* or *what it should look like* gets settled by two people imagining the
same words differently, and the pin records agreement that was never real. A prototype turns that
fork into something both parties **look at**. It is the cheapest way to raise the rung on a decision
that talk cannot close.

## Which question — the branch decides the artifact

Name the question first, out loud, in one sentence. Then:

| The question is | Build | Because |
|---|---|---|
| *"does this state model / this logic hold up?"* | one self-contained runnable file — buttons to drive the machine by hand, plus a guided walkthrough of the cases that are hard to reason about on paper | the human has to be able to push it through the awkward transitions themselves |
| *"what should this look like / feel like?"* | **several radically different variations**, switchable from one place | a single variation is a proposal wearing the costume of an experiment; the answer only appears in the contrast |

Getting the branch wrong wastes the whole prototype. If the question is genuinely ambiguous and the
human is not reachable, pick by what surrounds it — a backend module is the first row, a page or a
component the second — and **state the assumption at the top of the artifact**, where it is visible
rather than buried (`references/core/assumptions.md`).

## The rules that keep it throwaway

1. **Marked as a prototype from the first line.** Put it next to what it prototypes so the context is
   obvious, and name it so nobody mistakes it for production. Obey whatever layout the project
   already uses; a prototype is not the place to invent structure.
2. **One command to run it.** No setup ritual. A human who has to think about how to start it will
   not start it.
3. **No persistence.** State lives in memory. Persistence is usually the thing being *checked*, not
   something to lean on. If the question genuinely involves storage, use a scratch store with a name
   that says "wipe me".
4. **No polish.** No tests, no error handling beyond what makes it run, no abstractions. Every hour
   spent making it good is an hour spent making it harder to throw away.
5. **Surface the state.** After each action, or on each variation switch, show the full relevant
   state. The point is to make the invisible visible; a prototype you cannot see inside answers
   nothing.
6. **Timebox it, and say the box out loud.** A prototype that grows past its question has become an
   implementation nobody elected.

## The human elects. Always.

**Building the variations and then picking one yourself is the failure this skill is most likely to
commit.** It feels efficient and it destroys the entire value: the artifact existed to let the human
see the difference, and choosing on their behalf hands them a decision they were supposed to make.
Present the options, say which you would pick and why — that is a proposal, and proposing is allowed
— then stop and wait. Same rule as every other read-only role here: it surfaces, it never elects
(`references/core/agents.md`).

## Binding to the ledger

Bind it through the `ledger_*` MCP tools — the server resolves paths, so they work from the user's
cwd (see `using-the-ledger`).

The pin **pre-exists**: an `open_decision` (greenfield) or a `design_concern` / `ambiguity` (rescue)
that the interview could not close. Read it with `ledger_summary` and prototype *that* question, not
an adjacent one you find more interesting.

- **The prototype is evidence, not an outcome.** It does not resolve the pin. It gives the human
  something to answer with, and their answer is what `ledger_record_decision` records — at the rung
  the host actually achieved, never upgraded because the artifact was convincing
  (`references/core/trust-axes.md`).
- **Keep the artifact as a primary source.** Commit it to a throwaway branch out of the default
  branch, and put a pointer to that branch on the pin. The main branch keeps only the validated
  decision. Six months later the pin says what was chosen; the branch says what it was chosen
  *against*, which is the part that gets argued about again.
- **Fold in the decision, delete the scaffolding.** If a snippet the prototype produced encodes the
  decision more precisely than prose can — a state machine, a reducer, a schema, a type shape —
  inline that fragment in the pin and say it came from a prototype. Trim it to the decision-bearing
  part; a working demo pasted into a pin is not a contract.
- **A prototype that answered nothing is still a result.** Record it: the question survived, and the
  fact that a runnable artifact did not settle it is information about the question, usually that it
  was two questions.
