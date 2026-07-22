# The design-taste lens (judgment) — the reviewer/challenger's design eye

The deterministic detector (`references/module-design-alignment.md`) settles what is a **fact**: a
contrast ratio, a token off the DESIGN.md, a broken image. It deliberately does **not** judge
**taste** — whether a UI reads as *designed* or as *generated*. That half is real and valuable, but it
is **judgment, not fact**, so it lives on the other side of the fp-check line: a **reviewer /
challenger lens** (`references/core/agents.md`), read-only, producing `design_concern` pins that **do**
pass fp-check and are **options, never defects**.

This is the same fact-vs-taste split the package draws everywhere, applied to the presentation layer:
the detector's hits skip fp-check (facts); the taste lens's observations go through it (judgments the
interview weighs). Never assert a taste judgment as a defect — that reintroduces the vibecoding failure
mode inside the auditor.

## What the lens looks for (the "generated, not designed" tells)

Adapted, with attribution, from two public catalogs (we author the lens; we install neither skill):

- **Impeccable's rule catalog** (Paul Bakaus, Apache-2.0) — its `description` / `skillGuideline` prose
  reads as PR-comment guidance already, organized by category. The AI-slop clusters it names:
  purple/violet gradients, gradient text on headings, side-tab accent borders, nested cards,
  everything-centered layouts, monotonous spacing, bounce/elastic easing, glow-on-dark, hairline
  border + wide shadow, decorative grid backgrounds.
- **Anthropic's `frontend-design` philosophy** (the first-party Claude design skill) — five judgments
  the lens applies: **hero as thesis** (open with the subject's most characteristic thing, not a
  generic big number); **typography as personality** (pair display/body deliberately, not the default
  Inter/Roboto everyone reaches for); **structure encodes meaning** (numbered markers reflect a real
  sequence, not decoration); **deliberate motion** (animation serves the subject, scattered effects
  read as AI); **matching complexity to vision** (elegance is executing the chosen vision well).

The through-line both share: models reproduce the **statistical center** of design, so "looks like
every other AI UI" is the smell. The lens names the *class* ("this is the templated-default gradient
tell", "typography is neutral where the brief wants personality"), not just an instance — a blocking or
reopening verdict must teach, per the roster's "teach on rejection" rule (`references/core/agents.md`).

## How it binds

- **Judgment `design_concern` pins**, `confidence: inferred`, through fp-check — never `extracted`, and
  never a `contract_mismatch` (that kind is reserved for the deterministic token violation).
- **Options with tradeoffs.** "Leave as-is" (`state: accepted`) is a legitimate elected outcome; the
  `to_be` stays null until the user chooses. A taste finding is input to the interview, not a fix
  handed down.
- **Read-only roles only.** The `reviewer` applies the lens as its design dimension (after spec +
  quality); the `challenger` may use it to refute an elected design `to_be` as templated or
  unfalsifiable. Neither writes code, neither decides — same neutrality as every read-only gate.
- **Grounded, not vibed.** A taste claim cites the tell it matches (a catalog rule, a frontend-design
  principle) and carries its confidence, the same discipline as any external-knowledge-backed proposal
  (`references/core/knowledge-sources.md`).

## Floor · lens · ceiling

Three layers, kept distinct:

1. **Floor (deterministic, always on):** the Impeccable detector + DTCG token-membership — facts,
   fp-check-skipping (`references/module-design-alignment.md`).
2. **Lens (judgment, this doc):** the taste critique as read-only reviewer/challenger pins.
3. **Ceiling (generation, opt-in, per-host):** the visual tools that *produce* design — Claude Design /
   Open Design — whose non-deterministic output the floor then verifies (the per-host section of
   `references/module-design-alignment.md`).

## Attribution

The rule catalog is **Impeccable's** (Paul Bakaus, Apache-2.0); the five design principles are
**Anthropic's** `frontend-design` skill. We adapt their *guidance* into a ledger-bound lens with
attribution and **install neither skill** — the self-contained rule holds: nothing external ships,
and the lens is ours, bound to the one source of truth.
