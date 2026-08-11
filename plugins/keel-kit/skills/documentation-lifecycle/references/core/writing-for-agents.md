<!-- GENERATED FILE - do not edit. Source: src/core/writing-for-agents.md at the repo root; regenerate with: python scripts/build.py -->

# Writing for agents (shared core)

Every other doc in `core/` says *what to decide*. This one says **how the prose that carries a
decision has to be written for an agent to act on it** — a skill, an `AGENTS.md`, a reference reached
by a pointer. The packaging differs; the writing does not, and the target is the same in all three:
the agent taking the same **process** every run, not producing the same output.

This package is unusual in that the prose *is* the product. A wrong sentence here is not a typo, it
is a behavior change with no test — which is why the levers below are written as tests, not as
style advice.

## The pointer is the trigger

A **context pointer** is a reference held in the agent's context that names material outside it and
encodes the condition for reaching it. Three things in this package are the same object wearing
different names:

| Pointer | Points at | Fires when |
|---|---|---|
| a skill's `description` | the whole skill body | the host judges the task matches |
| a backticked pointer to a vendored core doc | that doc | the agent reads the line and follows it |
| a line in the projected `AGENTS.md` region | the ledger | the agent needs the elected design |

**The pointer's wording, not its target, decides whether the material is reached.** A load-bearing
target behind a weakly worded pointer is a variance bug: some runs find it, some do not, and the
body is blameless. Sharpen the wording first; inline the material only if sharpening fails.

A pointer does two jobs — say what the material is, and name the **branches** that should trigger
reaching it. Prune it harder than the body, because it is paid for on every turn where the body is
paid for only when it fires:

- **Front-load the discriminating word.** The pointer is where the triggering work happens.
- **One trigger per branch.** Two synonyms for one case are one branch written twice.
- **Cut identity the body already carries.**

The build encodes the backticked form as a rule, not a convention: a backticked core-doc path is a
**dependency edge**, and the build vendors that doc into every skill whose prose carries the line. So
a see-also mention stays plain text, and a backtick is a declaration that the skill cannot run
without it. Backtick a doc you merely admire and you have grown every vendoring skill by its whole
transitive closure.

## The two loads

Every document and every pointer spends one of two budgets, and the choice is which one:

- **Context load** — always-loaded material: a skill `description`, the projected `AGENTS.md` region,
  anything sitting in the window every turn. It costs tokens and attention whether or not it fires.
  This package already treats it as a correctness constraint rather than an efficiency one:
  one host truncates by bytes and another loses adherence past ~200 lines, so the projected region
  is a budgeted index and every clip it makes is declared inside it — the instruction-files doctrine
  holds the per-host numbers.
- **Cognitive load** — the cost on the human: knowing which documents exist and when to reach for
  each. **Not a cost to minimise.** It is the price of human agency, and this package spends it
  deliberately everywhere the human elects — the interview, the veto on an assumption, the three
  doors out of a pin. Spend it where judgment is the human's; remove it where it is not.

Material behind a pointer escapes context load at the price of the pointer's own line. Material with
no pointer rides entirely on cognitive load — which is exactly what a router skill exists to pay
down.

### Which load a skill spends: the invocation axis

A skill is **model-invoked** (the host may fire it, and so may the human) or **user-invoked** (only
the human, by name). The test is one question — *could the agent usefully reach for this on its own?*
— and one non-test, because it is the mistake that gets made: **reuse is a reason to extract a skill,
never a reason to make it model-invoked.**

Model-invocation is this package's default and mostly the right one: an agent that meets a broken
build should reach `systematic-debugging` without being told, and `codebase-rescue` /
`greenfield-forge` activate off their `description` by design. What the axis buys is that the default
becomes a **decision** instead of an omission — and it costs something real, so it has to be one:

- A user-invoked skill's description leaves the model's context entirely — verified at each host's
  own loader, and recorded with the mechanism it takes there, in this repo's packaging notes.
- It also **cannot be reached by another skill**, and on Claude Code it is **not preloaded into a
  subagent** — which matters here, where the roster runs six of them.

So a skill that only ever starts because a human said so pays context load for nothing, and a skill
the roster needs must stay model-invoked whatever else is true of it.

## Where a piece of material sits

Three rungs, ranked by how immediately the agent needs the material:

1. **In-file step** — what the agent does, in order.
2. **In-file reference** — consulted on demand. Often a legitimately flat peer-set (every rule of a
   review on one rung); that is an arrangement, not a smell.
3. **Disclosed reference** — pushed behind a pointer and loaded only when it fires. In this package
   that is `references/*.md` for skill-local material and `core/*.md` for shared.

**Progressive disclosure** is the move down the ladder, and the cleanest test for it is **branching**:
inline what every branch needs, disclose what only some branches reach. It is not primarily a token
optimisation — when a document has steps, undisclosed reference buries them, and attending to them
becomes a coin flip.

**Co-location** is the within-file companion: the ladder decides how far down a piece sits,
co-location decides what sits beside it. Keep a concept's definition, its rules and its caveats under
one heading, so reading one part brings its neighbours. Scattering fragments one meaning across many
places; duplication repeats one meaning in two. They are different defects with different fixes.

**Sprawl** is the failure mode with no single bad line: a document simply too long, where attention
thins across the excess. The cure is the ladder, not tighter sentences.

## Steps end on a criterion, and the criterion is a lever

Every step ends on a **completion criterion** — the condition that says the work is done. Two
properties make it load-bearing, and they fail differently:

- **Clarity** — can the agent tell done from not-done? A vague bound invites **premature
  completion**: the step ends because ending is available. Defend in order — **sharpen the bound
  first**, because it is local and cheap; only if it is irreducibly fuzzy *and* you observe the rush,
  split the sequence so the later steps are out of view. Hiding works **only across a real context
  boundary** — a handoff or a subagent dispatch. An inline call leaves the later steps in context and
  clears nothing.
- **Demand** — how much the criterion requires. *"Every modified model accounted for"* forces work
  that *"produce a change list"* does not. Demand is what drives the digging an agent does inside a
  step, and it is not step-bound: *"every rule applied"* binds a body of flat reference exactly as
  *"every step done"* binds a sequence.

The strongest criteria are both checkable and exhaustive. This package's sharpest one is not prose
at all — a pin resolves on `rung="observed"`, and the tool refuses the close without it. Where a
criterion can be made mechanical, make it mechanical; where it cannot, write the bound the agent can
check itself against.

**Watch this rule bite the document you are writing.** These pointers are dependency edges, so an
admiring backtick is a build instruction. Naming the instruction-files doctrine here as a `core/`
pointer — for a claim it merely *supports* — pulled its whole transitive closure, the ledger spec
included, into every skill that vendors this file. The evidence stayed; the backtick went. That is
the rule working, and it is cheaper to catch here than in a shipped skill that quadrupled in size.

## Leading words

A **leading word** is a compact concept the model already holds from pretraining, repeated as a
**token** and never as a sentence, so it accumulates a distributed definition and anchors a whole
region of behavior in almost no tokens. Coining one works if you define it, but an invented word
recruits no priors — you pay in definition tokens what a pretrained word gives free. Reach for the
existing word first.

It anchors twice. In the body, execution: the same behavior every time the word appears. In a
pointer, invocation: when the same word lives in the user's prompts, in the docs and in the code, the
agent links them and reaches the material more reliably. This package runs on them already — *pin*,
*as-is* / *to-be*, *rung*, *carrier*, *seam*, *frontier*, and *tight* / *red* for a debugging loop.

Hunt for the passages they retire. A triad spelled out at three sites, a pointer spending a sentence
to gesture at one idea:

- "fast, deterministic, low-overhead" → **tight**.
- "a reproduction you can believe" → **red** — a fuzzy gate becomes a binary observable state.

**Negation is the failure mode beside this lever.** Steering by prohibition drags the forbidden
behavior into context and makes it *more* available, not less: *don't think of an elephant*. State
the positive target so the banned behavior is never spoken. A prohibition earns its place only as a
hard guardrail you cannot phrase positively — and this package has real ones (*never elect on the
user's behalf*, *never derive the to-be from the as-is*). Keep those, and pair each with the positive
act that replaces it, so attention lands on what to do instead.

## Pruning

- **One meaning, one place.** Changing a behavior should be a one-place edit. Duplication costs
  maintenance and tokens and inflates a meaning's apparent rank. (A leading word is the deliberate
  inverse: it repeats the *token*, never the *meaning*.)
- **The environment is a source of truth, and a doc that restates it is a cache.** A cache earns its
  load only when the lookup is expensive. Cache what cannot be looked up — the unwritten convention,
  the reason behind a choice, the gotcha no config confesses — and leave the one-command lookups
  where they cannot go stale. This is the rule one of this repo's gates enforces on the
  subset that is decidable: the number is **computed** by whatever knows it, never kept in prose.
- **No-ops.** An instruction the model already obeys by default pays load to say nothing. The test —
  does this change behavior versus the default? — is **model-relative, not reader-relative**: two
  people disagreeing about a no-op are disagreeing about the default, and they settle it by running
  the document, not by arguing. When a sentence fails, delete the sentence rather than trim its
  words. The test grades leading words too: a word too weak to beat the default is a no-op, and the
  fix is a stronger word, not a different technique.
- **Sediment** is the default fate: stale layers settle because adding feels safe and removing feels
  risky, until someone has to core down through them to find what is still live. This repo's standing
  register of what it knows is wrong with itself is the answer for facts; for a document, the answer
  is a pruning pass that is allowed to delete.

## Attribution

The lever names and much of their framing are adapted, with thanks, from the MIT-licensed
`writing-for-agents` skill in [`mattpocock/skills`](https://github.com/mattpocock/skills) — context
pointers, the two loads, the information hierarchy, clarity-and-demand, leading words, and the no-op
test are its formulation, sharpened here against this package's own carriers. The bindings to the
ledger, the build's dependency-edge rule, and the per-host invocation facts are ours.
