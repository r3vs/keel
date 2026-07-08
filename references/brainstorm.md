# Brainstorm Agent (parallel, on-demand)

A separate agent the user opens on ONE pinned problem to think through the best solution — i.e.
the best answer to give in the interview. Kept structurally separate from the interview to
preserve neutrality.

## Contract

- **Loads context for that one pin only** — its anchors, `as_is`, the graph neighborhood, the
  partial `to_be` if any. NOT the whole audit.
- **Proposes 2–3 options** written to `pin.brainstorm.proposals[]`, each with:
  - `summary`, `tradeoffs` (pros/cons), `effort` (S/M/L)
  - `ladder_rung` — the ponytail ladder applied to the *solution* (does it even need to exist?
    can we consolidate something existing? stdlib? platform? dependency? one line?). This keeps
    the brainstorm from always proposing the most elaborate option.
  - `references` — how well-architected codebases solve THIS specific problem. May web-search
    the current state of the art rather than reason in a vacuum.
- **Writes ONLY proposals.** NEVER sets `state: decided`, NEVER writes a `DecisionEvent`, NEVER
  edits code. Neutrality is enforced by the schema, not by good intentions.

## Why separate from the interview
If the agent that proposes a solution also asks the question, it phrases the question to lead
toward its preferred solution — reintroducing "opinion as finding," the exact vibecoding
failure mode. The interview stays neutral (collects decisions); the brainstorm explores
(proposes options). Only the user's committed answer in the interview (`source: "interview"`)
decides — and a proposal becomes the decision only if the user picks it there.

## UI
The "brainstorm" button on a pin opens this agent; its proposals surface back as options on
that pin's interview question, so the user's exploration flows straight into their answer.

## v1 note
In v1 this can be a *mode* invoked on a pin (same agent, fresh context) rather than a truly
concurrent second agent — the concurrent version adds ledger-sync cost and is a v2 goal. The
neutrality contract above holds either way.
