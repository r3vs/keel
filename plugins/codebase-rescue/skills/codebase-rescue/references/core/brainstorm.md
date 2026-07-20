<!-- GENERATED FILE - do not edit. Source: src/core/brainstorm.md at the repo root; regenerate with: python scripts/build.py -->

# Brainstorm Agent (parallel, on-demand) — shared core

**Shared by both skills.** The user opens it on ONE pin to think through the best answer to give
in the interview — a fix (rescue) or a design choice (greenfield). Kept structurally separate
from the interview to preserve neutrality. It reads and writes the same `ledger.json`.

## Contract

- **Loads context for that one pin only** — its anchors, `as_is` (null for a greenfield
  `open_decision`), the graph/map neighborhood, the partial `to_be` if any. NOT the whole ledger.
- **Proposes 2–3 options** written to `pin.brainstorm.proposals[]`, each with:
  - `summary`, `tradeoffs` (pros/cons), `effort` (S/M/L)
  - `ladder_rung` — the ponytail ladder applied to the *solution* (does it even need to exist?
    can we consolidate something existing? stdlib? platform? dependency? one line?). This keeps
    the brainstorm from always proposing the most elaborate option.
  - `references` — how well-architected codebases solve THIS specific problem, **grounded in real
    sources** via `references/core/knowledge-sources.md`: DeepWiki on exemplar repos, Context7 for the current
    API of a candidate library, Exa/web for open SOTA — each cited, confidence set by the source.
    Never reason in a vacuum; never let an uncited result decide.
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
