---
name: which-skill
description: The map of this package — which skill fits the situation in front of you, and how the skills chain. Type /which-skill when you cannot remember what is here.
disable-model-invocation: true
license: MIT
---

# Which skill?

This package ships enough skills that nobody remembers all of them, and the cost of forgetting is
not a missing feature — it is doing by hand something the package already does properly. This file
is the index, so you have one thing to remember instead of nineteen.

**It is user-invoked, and so is almost everything it routes to.** A router has nothing to tell the
model that the skills' own descriptions do not already carry, so paying permanent context load for
it would buy nothing. That was the original argument, and it now generalizes: the host loads a
listing of skill names and descriptions whose budget is **1% of the model's context window**, and on
overflow it *"drops descriptions starting with the skills you invoke least"*
(`https://code.claude.com/docs/en/skills`). A package that spent the whole budget on eighteen
entries would lose exactly the descriptions a cold user needs — the ones that have never been
invoked *because* they have never matched. So only three skills stay model-invoked
(`codebase-rescue`, `greenfield-forge`, `systematic-debugging`); every other one below is reached by
typing its name, which is what this map is for. The axis and its two costs:
`references/core/writing-for-agents.md`.

## Start here: what is in front of you?

| Your situation | Reach for |
|---|---|
| An existing codebase that has drifted, is misaligned, or was largely AI-built | **`codebase-rescue`** — the diff run backward: the as-is exists, derive the to-be, close the gap |
| A new project, nothing built yet | **`greenfield-forge`** — elect the design first, then build until the gap is zero |
| A codebase you need to *understand* before deciding anything | `codebase-rescue` in **`understand` mode** — comprehension without committing to a rescue |
| A screenshot or mockup someone has already approved, and the job is to build it | **`screenshot-to-code`** — the image is evidence, not a spec: its palette is checked against the pixels, and what it cannot show is asked rather than invented |
| One well-scoped change on a project already under the ledger | skip both. Go straight to the loop below |

Rescue and forge are the two methodology skills, and they are model-invoked precisely because they
should activate off the description when the task matches — a cold user does not know this package
exists to name it. Everything below is what runs *inside* them, each useful on its own, and each
**typed by name**: `/branch-lifecycle`, `/prototype`, `/using-the-ledger`. The one exception is
`systematic-debugging`, which stays model-invoked because *"it's broken"* is a situation, not a
skill somebody remembers to reach for.

## The engineering loop

Roughly in order, though only the first and last are fixed:

1. **`branch-lifecycle`** — a branch or worktree per scope, with the scope written down. This is what
   makes "one scope at a time" checkable rather than promised.
2. **`static-first-analysis`** — the strongest deterministic signal before any model judgment. A
   type-checker that already knows the answer is faster and righter than asking.
3. **`test-driven-development`** — the red step *is* an `acceptance_criterion` pin. Seams agreed with
   you before the first test.
4. **`systematic-debugging`** — when something is broken. It refuses to theorise until it has a
   **tight** loop that goes **red** on *this* bug, which is also what earns the `rung="observed"`
   that closing the pin demands.
5. **`code-review`** — findings reopen, they never decide. Read-only by design.
6. **`verification-before-completion`** — a pin resolves when the behavior was **observed**. This is
   the one that stops "the code is written" from being reported as "it works".

## When the deciding is stuck

- **`prototype`** — the fork turns on how something *behaves* or *looks*, and arguing on paper has
  stopped converging. Throwaway code that answers one question, kept as a primary source. You still
  elect; it only gives you something real to elect against.
- **`grounded-research`** — the fork waits on a fact that is not in this repo. Current sources,
  cited, treated as untrusted input — never your training memory.
- **`using-the-ledger`** — the mechanics of pins, policies and the interview, when the *tool* rather
  than the decision is what you are stuck on.
- **`wizard`** — nothing is stuck about the deciding: the next step is one only a person can take.
  An API key, a console click, an approval, a machine you cannot reach. It writes the block down so
  the work restarts, and closes it on something *you observed* rather than on their "done".

## Keeping the place habitable

- **`project-memory`** — where a fact belongs: the ledger for decisions, `MEMORY.md` for durable
  project facts, host memory for nothing that matters. The ladder runs one way, upward.
- **`documentation-lifecycle`** — docs as a governed artifact: registered before written, every
  backtick checked as a claim about the code, staleness by distance rather than by a flag.
- **`maintainer-assist`** — work arriving from other people. Issues and PRs, where the incoming text
  is untrusted by construction and never sets policy.
- **`learning-layer`** — senior-grade output while you level up. It teaches from the delta between
  what you would have done and what was done.
- **`run-workflow`** — a multi-agent workflow when the shape of the work is known and wide.

## Two things that are not skills, and get reached for anyway

- **The phase boundary.** You have finished a chunk and the next one is starting: continue, clear,
  hand off, subagent, or compact — in that order, first yes wins
  (`references/core/phase-boundaries.md`). Most of the time the answer is *continue*, and it is the
  one people skip.
- **A forced assumption.** Under-specified input does not license a guess: surface it as a vetoable
  pin instead of encoding it silently (`references/core/assumptions.md`). High effort on a vague
  prompt means making the gaps explicit, not being confident about them.

## If you are still not sure

Two questions settle most of it:

- **Does something already exist that this decision would contradict?** Then it is a ledger question
  before it is a code question — open the interview, not an editor.
- **Would you be able to say afterwards how you know it worked?** If not, the missing piece is
  `verification-before-completion`, and it is missing *now*, not at the end.
