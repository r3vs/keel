# From an approved picture to a design contract

Where the evidence becomes something the build can be held to. The hinge is a rule this package
already stated and could not previously perform:

> A text-only agent cannot invent a tasteful palette or type pairing, so the tokens are **captured
> from an approved visual direction, or imported — never authored from a vibe.**

That rule named three capture paths and shipped a mechanism for one of them (import an existing
brand or a Figma export). "The human saw a direction and approved it" was the intended path and had
no carrier. **A screenshot the user chose and handed over is exactly that artifact**: a visual
direction, already seen, already approved, by the only party entitled to approve it. This file is
how it becomes a contract.

## First: decide whether there should be a contract at all

Not every picture earns a token system, and generating one anyway is the YAGNI failure in its
design-layer form. The interview decides, and there are three honest outcomes:

- **A design system is elected** → a DTCG token contract, generated layers, and a drift-check for the
  life of the project. This is the path below.
- **The project already has one** → do not author a second. `extract_tokens` harvests what the
  codebase already declares as CSS custom properties into a candidate DTCG contract; the screenshot's
  palette is then checked *against* it, and every off-palette color in the reference becomes a
  question — adopt the reference, or conform to the house system — rather than a silent third
  palette. **A screenshot that disagrees with the project's design system is a decision, not a
  license.**
- **No formal system in this scope** ("just build the page") → no DTCG, no generated layers. The
  universal a11y and slop checks still run. Skip to building components.

## The contract, and why it is DTCG

The machine contract is a **W3C Design Tokens (DTCG)** JSON — the stable, externally-governed,
multi-vendor carrier. `DESIGN.md` is *generated from it*, never authored as the primary artifact; so
are the CSS custom properties and the Tailwind `@theme` block. One source, three projections, and a
round-trip that proves alignment. That decision, and the reasons behind rejecting DESIGN.md's own
frontmatter as the machine contract, are not re-argued here — they are settled in the design-tokens
runtime and greenfield's design-propagation module.

What this skill adds is where the token *values* come from, and the discipline over them:

1. **Colors** — from the elected subset of the verified palette. A color that failed
   `palette_verify` never enters the contract; a color that passed enters with its measured coverage
   recorded in the pin's provenance, because "this is the accent" and "this covers 0.4% of the
   reference" are two different claims and the second one is checkable.
2. **Names** — from the human, in the interview. The name is the token's meaning, and meaning is
   Bucket 2. `color.brand.primary` and `color.accent.link` are different designs with the same hex.
3. **Type and spacing** — inferred from the image, elected in the interview, and preferably
   **snapped to a scale the human picks** rather than transcribed pixel-for-pixel. A screenshot
   measured to the pixel produces `--space-13px`, which is a transcription, not a system.
4. **What the picture cannot fill** — every token role the elected system requires and the reference
   does not show (a danger color, a disabled surface, a focus ring) is an `open_decision`, offered
   with a grounded proposal. **Never derived by tinting the accent and shipping it.**

## Generating, and the guard

`generate_tokens` writes `tokens.css`, `theme.css` and `DESIGN.md` from the contract. `tokens_diff`
re-extracts the CSS variables and diffs them back: a correct generator round-trips to **zero drift**,
and the check is wired into CI so that a hand-edit to a generated token fails the build. Both halves
matter and they catch different things — `tokens_diff` catches an edit to the *definitions*,
`design_scan` catches a component that *uses* a value the contract does not contain.

## Then build the real components

The token step emits the design surfaces, **not the UI**. Components are ordinary build items:
test-first, in the project's real framework, referencing the generated variables — which makes them
structurally token-bound, since a component that names only `var(--color-brand-primary)` cannot drift
off the contract without the drift being visible as a literal.

Each component from the reference becomes an `acceptance_criterion` pin with its behavior from the
interview (Bucket 3, item 5), not from the picture. "The submit button is blue and 40px tall" is not
an acceptance criterion; "submitting with an empty email shows the inline error" is, and it is
verifiable in a browser.

**There is no prototype in this pipeline.** The token economy of "generate HTML, then rebuild it
properly" buys a demo and costs a rewrite plus a second source of truth for as long as the demo
survives. We are context-rich by construction — the ledger, the data contract and the component
inventory are all in hand — so the real thing is built directly against the contract. The one
legitimate use of throwaway markup is *showing a human a direction so they can approve it*, and in
this skill that step already happened: they handed you the screenshot.
