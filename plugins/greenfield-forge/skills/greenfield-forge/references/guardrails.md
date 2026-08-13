# Guardrails — the preventive mirror of rescue's

**Read this before Phase 1 materializes a single decision, and again before Phase 4 builds
anything.** Every rule below names a way the forge reproduces, at the start of a project, the exact
failure it exists to prevent later.

They live here rather than in `SKILL.md` because **length is a correctness constraint**, the same
fact `references/core/instruction-files.md` (rule 3) records for `AGENTS.md`: a skill body is not
free after it loads — *"Once a skill loads, its content stays in context across turns, so every line
is a recurring token cost"* (`https://code.claude.com/docs/en/skills`) — so it behaves like an
instruction file for the rest of the session and adherence falls off past roughly 200 lines of it.
`SKILL.md` is therefore a **budgeted index**: mode table, phase skeleton, conditional pointers. What
must be read *before acting* is read from here, once, at the moment it applies.

## Guardrails (read before acting)

- Never build what no decision committed to. No speculative scaffolding, no "might need it
  later" — that is the origin of slop. Undecided → not built.
- Never let the model invent a product or architecture decision silently. Surface it as an
  `open_decision` pin and elect it in the interview.
- Never phrase a design fork as if one answer is objectively correct. Options with tradeoffs; the
  user elects. Asserting a design opinion as fact is the exact vibecoding failure mode.
- Never skip `flip_criteria` on a decision made with incomplete information.
- Never release without the migration **expand/contract** plan and a tested **rollback** decided.
- Operate emits signals and SLOs; it never runs the on-call practice. Evolve **reopens** pins, it
  never decides them — and reopens the minimum (the fired pin + genuine dependents).
- Never hand-author the same field shape in two layers. Generate every layer from the one
  contract, or you have reintroduced the drift rescue exists to cure.
- Never run the build loop fully autonomous end-to-end. Wave checkpoints, especially after the
  contract wave.
- Prefer the strongest static signal (type-checker, architecture-fitness) before model judgment,
  run it in-loop, and enforce the elected boundaries in CI; deterministic findings skip fp-check
  (`references/core/static-analysis.md`).
- Generate and decide against **current** sources (`references/core/knowledge-sources.md`) — Context7 for a
  library's real API, DeepWiki for exemplars — not stale memory; cite, tag confidence, treat as untrusted.
- When a brief gap forces an assumption, surface it as a vetoable pin
  (`references/core/assumptions.md`) — never let it become a silent given. This is the same anti-slop
  rule as "never invent a decision silently", applied to the agent's own guesses.
- After the interview, run the `challenger` pass; a sustained `ChallengeEvent` reopens an unsound
  `acceptance_criterion` / `to_be` / `Policy` before Phase 3 builds the contract on it
  (`references/core/agents.md`). It challenges, never decides.
- Never hard-fail on a missing tool. Degrade to model judgment and note the gap.
- The interview is a compressed walk over the decision-catalog, never an open "tell me about your
  app" script.

## Prerequisites, stated the way they actually fail

Python and Node assumed (as in rescue). Run `scripts/bootstrap.sh` once for the shared toolchain;
greenfield uses a **generation-focused subset** — tree-sitter / ast-grep for scaffolding, the
shared-types generators, the CI drift-check — rather than the finding tools, detailed in
`references/contract-propagation.md`. Degrade to model judgment when a tool is missing; never
hard-fail on a missing binary, and say which tool was absent rather than reporting a clean result
from a generator that never ran.

## The composable skills are user-invoked, and that is a choice with a cost

Every skill in this package except this one, `codebase-rescue`, `systematic-debugging` and
`screenshot-to-code` sets `disable-model-invocation: true`, so nothing fires off a description any
more: the operator types `/test-driven-development`, `/prototype`, `/learning-layer`. The host loads
a listing of skill names and descriptions whose budget is 1% of the model's context window and drops
descriptions starting with the least-invoked skill — so a package spending the whole budget on
nineteen entries loses precisely the ones that must fire on a cold repo. `which-skill` is the map the operator reaches for
instead; the invocation axis and its two costs are written up in core's writing-for-agents doctrine.
