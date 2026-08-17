# The look-again loop — and the line running through the middle of it

Every image-to-UI tool converges on the same loop, because it works: generate, render the result,
look at both pictures, fix the difference, repeat. This is the adapted version of that loop, and the
adaptation is one cut: **the comparison is two comparisons, on opposite sides of the determinism
line, and they must not be reported as one verdict.**

## The two halves

| half | what it asks | trust | consequence |
|---|---|---|---|
| **Token membership + a11y** — `design_scan` on the running URL | does the rendered component use a value the contract does not contain? is the contrast computable and failing? | **D0** — set membership and arithmetic, `confidence: extracted`, skips fp-check | **blocks.** A `design-system-*` hit is a `contract_mismatch` against the generated `DESIGN.md` |
| **Pixel comparison** — the render against the reference image | does it *look* like the picture? | **D2** — a deterministic mechanism over a noisy signal | a **human-reviewed pin.** Surfaced, never auto-resolved, never a merge gate |

The reason the second half cannot be promoted, stated plainly because promoting it is the standing
temptation: anti-aliasing, font hinting, sub-pixel layout and GPU/OS rendering differences all produce
pixel disagreement in a *correct* implementation, and the reference screenshot was captured on
someone else's machine at an unknown density. The mechanism is deterministic; the signal is not.
Treating a diff percentage as a pass/fail gate is how a team ends up pinning a font stack to make a
number go down. This is the Chromatic/Percy pattern — a human accepts or rejects, and acceptance sets
the new baseline.

## Running it

1. **Render the real component**, not a prototype: the dev server, or Playwright driving the app.
   The committed Playwright spec is the deterministic carrier for any *behavior* being verified; the
   browser session is for authoring and looking.
2. **Run the deterministic half** — `design_scan` against the URL, at each elected breakpoint
   (`viewport`), so the mobile answer from the interview is actually checked rather than assumed.
   Every hit is a finding with a carrier; the `design-system-*` ones are contract violations.
3. **Check that both halves are about the same render — `render_agreement`.** The scan renders the
   URL itself; your screenshot was captured separately. Same page at two viewports is two designs,
   and a difference named against the wrong one wastes the whole pass. `mismatch` → re-capture at
   the scanned viewport before comparing anything.
4. **Compare pictures for the judgment half.** State the specific difference in words — *"the card
   gutter is visibly wider than the reference"*, *"the heading weight is lighter"* — not a percentage.
   A named difference is a pin someone can decide; a diff score is a number nobody can act on.
5. **Route each difference before fixing it.** This is where the loop earns its keep, and it is one
   question: *is this a defect in what I built, or a decision nobody made?* A misapplied token is a
   defect — fix it. A gutter that differs because the reference's spacing scale was never elected is
   an `open_decision` — pin it, and stop trying to fix it in code.
6. **Fix, re-render, repeat** — with a stopping rule.

## The stopping rule

The loop's characteristic failure is that it never ends: each pass finds a smaller difference, every
fix is locally plausible, and convergence is asymptotic because the target is a photograph of a
different machine's rendering. So it stops on a condition, not on satisfaction:

- **Stop when the deterministic half is clean** — no `design-system-*` mismatch, no computable a11y
  failure at any elected breakpoint. That is the merge gate, and it is reachable.
- **Stop the judgment half after the differences stop being nameable in one sentence.** When the
  remaining delta needs a magnified crop to describe, it is below the threshold at which the
  reference itself is authoritative.
- **Stop immediately and pin instead** whenever a fix requires inventing something from Bucket 3
  (`references/reading-an-image.md`). Chasing a visual match into an undecided area is how the
  picture ends up making decisions again, one pixel at a time, at the very end of the process where
  nobody is watching for it.
- **Three passes with no nameable difference resolved** is a stop. Record what remains as a
  `design_concern` with the reference attached and let a human look once.

## What a resolved pin means here

A UI pin resolves when the behavior was **observed**, not when the render looked close. For a
component from a screenshot that means: its `acceptance_criterion` spec passes in a real browser, and
the deterministic design half is clean at the elected breakpoints. A pixel-diff approval is a human's
signature on a judgment — it is recorded as such, with the reviewer named, and it never stands in for
the observation.
