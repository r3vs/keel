# Three Trust Axes (shared core)

How much to trust a governed output — a finding, a pin, a verdict, a generated artifact — is **three
questions, not one**. This doc names them, and states the rule that keeps them from collapsing into a
single flattering number.

| Axis | The question it answers | Values |
|------|------------------------|--------|
| **Determinism** | how does this result *reproduce*? | `D0` · `D1` · `D2` |
| **Verification rung** | how hard was its claim *checked*? | `self_check` · `re_read` · `observed` · `cross_derived` |
| **Review burden** | what review does its *risk* demand? | the existing `severity` × blast radius |

**The composition rule is the whole point: the posture reported is the conjunction of all three,
never the most flattering single axis.** A `D2` output can still reach `observed` by exercising the
real path. A `D0` computation can still demand human review because its blast radius is high. Neither
axis excuses the others, and none of the three is a quality score.

## Determinism — how the result reproduces

| Level | Meaning | Replay guarantee |
|-------|---------|------------------|
| `D0` | pure computation over a carrier — AST, symbol table, schema, git history, content hash. No model call on the path. | fully replayable: same inputs always give the same output |
| `D1` | reconstructible from a recorded artifact that is itself pinned (the graph at a `built_at_commit`, a tool report, a content-addressed cache) | reproducible by re-running against that pinned artifact |
| `D2` | model judgment sits on the path | **not** replayable, but **auditable** — reconstructable from the recorded inputs, the model id, and the harness version |

`D2` is the honest default for anything a model decided. The package does not claim determinism it
cannot deliver, and it does not treat `D2` as a lesser grade: a `D2` result is reproducible by a
different evidence path, not by none.

## Verification rung — how hard the claim was checked

| Rung | What happened | Cost |
|------|---------------|------|
| `self_check` | the producing agent checked its own output | zero marginal |
| `re_read` | the claim was re-checked over the **full** diff/trajectory, not the output text alone | one re-read |
| `observed` | the behavior was **exercised and seen** — the bar the verification skill sets for `resolved` | one run |
| `cross_derived` | independently re-derived by a model from a **different provider**; agreement is the pass signal, divergence forces human review | two runs, two providers |

`cross_derived` earns its cost only on irreversible or high-severity claims. Its logic: a
single-provider hallucination is unlikely to reproduce cross-provider, so **the disagreement itself is
the safety signal** — a divergence is not a tie to be broken by picking one, it is a finding.

## The dial — when determinism is a win, and when it is a lie

Determinism is a **per-step dial, not a property of a module**. The governing rule:

> **No judgment disguised as computation, and no computation where a carrier already exists.**

Three tests decide a step's honest level:

1. **Does a carrier already encode the answer?** (AST, symbol table, schema, git log, hash) → make it
   `D0`. Calling a model here is waste, and it converts a fact into an opinion.
2. **Would the deterministic implementation be a regex imitation of judgment?** → use the agent, and
   label it `D2`. Grepping prose for a concept is the textbook case.
3. **Is the deterministic version cheaper *and* equally correct?** If it is cheaper but less correct
   it is not a win — it is a downgrade wearing a green badge.

### Why a fake-deterministic check is worse than an agent check

A check labeled deterministic asserts *"this is proven."* An agent says *"I believe."* When the first
one is actually judgment in disguise, the damage is not the judgment — it is the **authority the
label lends it**. A wrong `D2` finding gets argued with; a wrong `D0` finding gets believed.

So the failure mode this doc exists to prevent is not "used a model." It is **de-agenting a step that
needs judgment in order to earn a greener badge** — and its mirror, calling a model for something the
carrier already answers.

The package's own catalog gate encodes exactly this: a module whose `type` is `deterministic` may not
name an `agent:` engine, because an engine that reasons is `D2` however the module is labeled. Four
modules shipped mislabeled until that gate learned to check type↔engine *coherence* rather than mere
engine *presence*.

## Degrade visibly — the seam rule

A seam that cannot run has not produced a clean result; it has produced **nothing**, and the two must
never read the same. Whenever a tool, MCP server, provider, or external host is unreachable:

- the run **continues** — never hard-fail;
- the gap becomes **a fact in the ledger**, not a silent zero;
- no output inherits a rung it did not earn — an unrun check contributes no verification, so the
  claim it would have covered stays at whatever rung the remaining evidence supports.

Graceful degradation is permitted. **Pretending is not** — and the danger is precisely that graceful
degradation *looks* like success. `core/static-analysis.md` carries the concrete instance of this for
the static toolchain (the `coverage-gap` pin); this is the general rule it is an instance of.

## Output

Every governed output states its three axes rather than one confidence number, and every module in a
catalog states a determinism level its engine can actually support.
