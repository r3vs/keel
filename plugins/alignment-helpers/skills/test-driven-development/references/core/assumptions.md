<!-- GENERATED FILE - do not edit. Source: src/core/assumptions.md at the repo root; regenerate with: python scripts/build.py -->

# Surfacing Assumptions (shared core)

Shared doctrine both skills read. It governs the agent's **own** behavior, not the codebase's: what
an agent does when the input is under-specified and it must assume something to proceed. The rule is
one line — **never encode a forced assumption silently; materialize it as a vetoable, challengeable
pin** — and the rest of this file is why and how.

## The failure mode it prevents

A model calibrates its output to the *register* of the prompt, not to the objective difficulty of
the task. An expert-sounding but under-specified prompt pushes it to assume *at a high level* and
fill the gaps **confidently** — which is exactly how confident-but-wrong output is born, and how the
vibecoding failure mode re-enters through the auditor. The correct response to under-specification is
not "try harder and guess better"; it is **raise the effort on making the gaps explicit**. High
effort on a vague input means *enumerate what is missing and surface it*, never *elaborate a
confident guess*. This doctrine is the schema-level enforcement of that principle.

It is the precondition for two other mechanisms: you cannot **challenge** an oracle (the
`challenger` role) that rests on a hidden assumption, and you cannot **learn** from a decision that was
never made visible. A silent assumption defeats both arcs — so it is never allowed to be silent.

## The rule (non-negotiable)

- **A forced assumption is a pin, not a default.** When an agent must assume to proceed, it writes
  the assumption into the ledger — either as its own pin, or as a `provenance`
  entry on the pin it is creating — with `provenance: [{ source: "agent_assumption", detail: "…" }]`
  and `confidence: inferred | ambiguous` (never `extracted`; an assumption is not a fact).
- **Confidence tags the guess honestly.** `inferred` = a defensible reading from real signal;
  `ambiguous` = genuinely undecided, multiple readings live. The severity threshold then applies as
  always: a `blocker`/`high` assumption is **always `asked`**, never a silent `proposed_default`
  (the interview-funnel rule). Only low-stakes assumptions may ride as a proposed default the user
  skims and overrides by exception.
- **One assumption, one line of why.** Record *what* was assumed and *what would change if it is
  wrong* (its blast radius via `depends_on`), so the interview can veto it with the cost in view and
  the challenger can refute it (class `unstated_assumption`).
- **Prefer asking to assuming when the stakes clear the threshold; prefer a surfaced default to a
  silent one otherwise.** Do not stall the whole task on a low-stakes gap — assume, tag, and move —
  but never let a load-bearing gap be filled without the human seeing it.
- **The agent never upgrades its own assumption into a decision.** Only the interview commits. An
  `agent_assumption` pin stays `needs_input` until the human elects it (exactly like every other
  pin) — surfacing it is not deciding it.

## What this is *not*

Not a mandate to interrogate the user about everything — that is the mirror failure (drowning the
user in questions), which the interview funnel exists to prevent. The funnel still compresses:
cluster the assumptions, resolve whole classes by policy, ask only the load-bearing few. The point
is not *more questions*; it is that **no load-bearing gap gets filled invisibly**. A cheap,
low-stakes assumption surfaced as a proposed default is fully compliant with this doctrine.

## Output

Ledger pins/provenance carrying `source: agent_assumption` and an honest `confidence`, subject to
the same funnel and severity threshold as every other pin — visible on the map, vetoable in the
interview, and challengeable by the `challenger`. A gap the agent had to fill is now a thing the
human can see and reverse, not a silent decision.
