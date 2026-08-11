<!-- GENERATED FILE - do not edit. Source: src/core/phase-boundaries.md at the repo root; regenerate with: python scripts/build.py -->

# Phase boundaries — what to do with the context when a chunk of work ends (shared core)

This package already answers the *big* version of this question: each phase is a separate invocation
with fresh context, and the phases communicate only through on-disk artifacts. The ledger **is** the
handoff. That is why a context reset between phases is cheap here and expensive in a package without
one — the decisions are not in the window, so losing the window does not lose them.

What that leaves unanswered is the small version, which comes up constantly: you have just finished
a chunk of work *inside* a phase, and the next chunk is about to start. That gap is the **phase
boundary**, and it is the only place this decision belongs. Mid-chunk there is nothing to decide —
carry on, or split what remains into subagents. Compacting mid-chunk is how an agent loses the
thread.

## Five options

| Option | What it does |
|---|---|
| **Continue** | stay put; no switch at all |
| **Clear** | empty the window and start from nothing |
| **Hand off** | write a portable artifact and seed a session anywhere from it |
| **Subagent** | send the task to its own window and get a report back |
| **Compact** | compress this context and continue from the summary |

## The order — first yes wins

1. **Can you continue?** Yes when the next chunk needs this one as a **primary source**, or there is
   simply room. Interview → build is the standard yes: the build wants the reasoning as it happened,
   not a summary of it. Continue costs nothing and loses nothing, so rule it out before anything
   else.
2. **Is everything here irrelevant to what comes next?** Then **clear**. It is the cheapest move on
   the board and it is not terminal. The cost of getting it wrong is one-way, though: clear a
   relevant context and you lose the *why*, and re-reading the diff never gives it back. In this
   package that risk is smaller than elsewhere by exactly as much as you wrote down — a decision in
   the ledger survives the clear; a decision only spoken does not.
3. **Does something have to travel?** Then **hand off**. The list is short and it is the whole list:
   a different host, a different directory or repo, another person, or a side task you found
   mid-chunk and do not want to derail the current one for. What a handoff buys is **portability**.
   If nothing is travelling, you do not need it.
4. **Can the task run unattended?** Scoped tightly enough that nobody needs to steer it — then send
   it to a **subagent** and leave this session untouched. Read-only work is the standard case, which
   is why five of the six roles here are read-only and fan out.
5. **Otherwise, compact.** Relevant context, same host, same directory, and you need to stay in the
   loop. Pass it an instruction, so the summary keeps what the next chunk needs.

Compact is the **default, not the first reach**. It sits at the bottom because the four questions
above it are each cheaper or more precise, and the failure mode when someone starts here is a fresh
session that is confidently wrong about a decision the summary flattened.

## Primary and secondary sources

Every move except *continue* turns a primary source into a secondary one — the session as it
happened, replaced by an account of it:

| Source | Information | Noise | Room to move |
|---|---|---|---|
| primary (continue) | full | a lot | little |
| secondary (compact, handoff) | lossy | less | a lot |

That is why question 1 comes first: you pay the lossiness only when staying costs more than it
saves. It is also the reason the ledger is written *during* a phase and not at the end of one — a
pin recorded while the reasoning is still primary keeps the `why`; a pin reconstructed after a
compaction inherits whatever the summary kept.

## Judge the boundary, not your own headroom

The obvious way to run this tree is to ask yourself how much room you have left. **That is a
self-report, and this package does not accept those as evidence** — an agent's estimate of its own
remaining capacity is a claim, not a measurement, and it is the same class of self-assessment
`core/self-model.md` refuses elsewhere. Prefer the structural signal: a chunk of work **ended**.
That is observable, and it is the trigger.

These are still judgement calls — the same boundary can honestly go two ways on two days. The value
is in asking the questions **in order**, at a boundary, rather than in the middle of the work.
