---
name: wizard
description: Handle a step only the human can take — an API key, a console click, a card on file, an approval, a machine you cannot reach. Writes the block down so the work restarts, gives the human an instruction they can actually follow, and closes it on something observed rather than on "done". Use when you are blocked on a person rather than on code.
license: MIT
---

# Wizard — the steps only a human can take

Some steps are not slow, or hard, or unclear. They are **impossible for you**: creating the account,
accepting the terms, putting a card on file, clicking approve in a console, plugging in the dongle,
naming the production domain, holding the credential that must never reach a transcript.

This skill is the exact inverse of `references/core/assumptions.md`. That one governs what you do
when you must **guess** to proceed. This one governs what you do when you must **wait** — and the
two meet in one place, named at the bottom.

## What counts

A step is human-only when it fails on **authority, identity, or physical reach**, not on effort:

- **Authority** — approving a spend, merging to a protected branch, accepting a licence, granting an
  OAuth scope. Somebody is being held responsible, and the mechanism exists so a person is.
- **Identity** — anything behind their login, their MFA, their card, their email confirmation.
- **Reach** — a device, a network, a physical machine, a vendor console with no API.

A step is **not** human-only because it is tedious, because the docs are bad, or because you would
rather not. Those are yours. Check for an API, a CLI, an environment variable and an existing
credential **before** you decide a human is required — an agent that hands work back it could have
done is the over-cautious failure `references/core/self-model.md` names, and it costs the operator
exactly as much as the confident guess does.

## Do not route around it

Three routes look like progress and are not. Each one produces a green build over a step nobody
took:

1. **The stub that stays.** A fake key, a mocked client, a hardcoded token that makes the call
   "work". The suite passes and proves nothing — the tautological test, one layer up.
2. **The silent downgrade.** Switching to the free tier, the local emulator, the in-memory store,
   without saying so. The design the human elected is now not the design being built, and the ledger
   still says it is.
3. **The optimistic pass.** Writing the code that uses the credential, calling it done, and leaving
   the first real run for someone else. You have moved the failure, not removed it.

If you genuinely cannot wait — the human is unreachable and the rest of the work depends on this —
that is a **forced assumption**, and it gets surfaced as a vetoable pin like any other. It does not
get to be a stub with a comment.

## Write the block down before you ask

The reason is restartability, and it is the same reason every phase here persists to disk: the
session that asks is rarely the session that resumes. Record it as a pin, in the ledger, with

- **what is blocked** — the pins that cannot move until this lands, as `depends_on` edges, so the
  scheduler stops offering them rather than handing an executor an item that will fail;
- **what the human must do**, in the instruction shape below;
- **how you will know it happened** — the observation, decided *now*, while you still remember what
  you were trying to do.

Then **release the claim** (`ledger_release`). A pin waiting on a person is not a pin you are
working, and holding it keeps it off the frontier for every other session while nothing happens.

## Write the instruction so it can be followed and checked

Most human-only steps fail on the instruction, not on the human. Write it the way this package
writes every other step:

- **One action per line, verb first.** "Open …", "Click …", "Copy the value into …". Not a
  paragraph the reader has to parse into steps.
- **Name the exact surface.** The console, the page, the button's label as it actually reads. If you
  are unsure what the screen says, say you are unsure rather than inventing a label — a confident
  wrong label costs more than an honest gap.
- **Say where the output goes.** `.env`, a secret manager, a CI variable, by name. A key the human
  obtains and has nowhere to put is a step that will be done twice.
- **End on a check they can run.** One command whose output tells them it worked. Without it the
  only completion signal is their belief, and belief is what the next section refuses.
- **Say what you will do with it.** People are correctly reluctant to paste credentials at an agent.
  Prefer a path where the secret never enters the transcript — they put it in the file, you read the
  file's effect, not its contents.

## Close it on something observed, never on "done"

**"I did it" is `self_check`.** It is a report about the world from someone who is not the ledger,
and a pin does not close on one. The observation is yours to make:

| The step was | Closed by |
|---|---|
| obtain an API key | a call that now returns 200 with it |
| create the account / project | the resource enumerating from the CLI |
| grant a permission | the operation that used to be denied, succeeding |
| put a card on file | the plan reading as active |
| approve a deploy | the release existing at the version you expected |

If you cannot observe it, say so and record the pin as `correctness_unknown` rather than resolving
it. That is the honest exit and it already exists here; a resolved pin nobody verified is worse than
an open one, because it stops being asked about.

The human being annoyed by the re-check is a real cost and it is smaller than the alternative. Do it
once, quietly, and report the result — not the checking.

## While you wait

Do the work that does not depend on it, and only that. Take the next item off `ledger_frontier`,
which now excludes what you just blocked. Do not start the dependent work "so it is ready" — that is
the optimistic pass with a schedule attached.

If everything left depends on the block, say that plainly and stop. A session that keeps producing
output while genuinely blocked is producing the thing this package exists to remove.

## Binding to the ledger

The block is an **`incompleteness`** pin — a work item, not a defect — with `severity` set by what
it blocks, not by how annoying it is. Its remediation item is the human's, and it carries the
observation as its own acceptance check.

Two rules do the real work, and neither is generic advice:

- **It closes at `rung="observed"`**, like every other pin here, which is what makes "they said they
  did it" insufficient by construction rather than by discipline.
- **The forced-assumption door is the only bypass.** If you proceed without the step, you have
  assumed something — that the free tier is equivalent, that the permission will be granted, that
  the key will look like the docs say — and that assumption is a pin with a veto on it
  (`references/core/assumptions.md`), not a comment in the code.

Ask the human once, well, and make the asking cheap to act on. Then get out of their way.
