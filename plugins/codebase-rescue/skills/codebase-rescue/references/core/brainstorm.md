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
- **Writes ONLY proposals**, through **`mcp:ledger_add_proposals`** — one pin per call. NEVER sets
  `state: decided`, NEVER writes a `DecisionEvent`, NEVER edits code. Neutrality is enforced by the
  schema, not by good intentions: a proposal carrying a `decision` or an `outcome` is refused, and
  at most one may be marked `recommended` — two make the gap between what was recommended and what
  the human elected uncomputable, and that gap is the point of the mark.

## Why separate from the interview
If the agent that proposes a solution also asks the question, it phrases the question to lead
toward its preferred solution — reintroducing "opinion as finding," the exact vibecoding
failure mode. The interview stays neutral (collects decisions); the brainstorm explores
(proposes options). Only the user's committed answer in the interview (`source: "interview"`)
decides — and a proposal becomes the decision only if the user picks it there.

## UI
The "brainstorm" button on a pin opens this agent; its proposals surface back as options on
that pin's interview question, so the user's exploration flows straight into their answer.

That sentence was false for as long as it existed, and the correction is worth carrying here rather
than only in the spec: writing proposals moves the pin to `brainstorming`, and the interview view
used to select `needs_input` and `correctness_unknown` only — so opening the brainstorm on a hard
fork is what took that fork **off** the interview's list, while `ledger_summary` went on counting it
as an open question. Since ledger v0.17 the view selects `brainstorming` too and each funnel entry
carries the proposals, which is what makes the sentence above describe the machine.

## v1 note
In v1 this can be a *mode* invoked on a pin (same agent, fresh context) rather than a truly
concurrent second agent — the concurrent version adds ledger-sync cost and is a v2 goal. The
neutrality contract above holds either way.
