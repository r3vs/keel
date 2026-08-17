# The design-taste lens (judgment) — one lens, run in both directions

The deterministic detector settles what is a **fact**: a contrast ratio, a token off the elected
`DESIGN.md`, a broken image. It deliberately does **not** judge **taste** — whether a UI reads as
*designed* or as *generated*. That half is real and valuable, but it is **judgment, not fact**, so it
lives on the other side of the fp-check line: a read-only lens (`core/agents.md`) producing
`design_concern` pins that **do** pass fp-check and are **options, never defects**.

Never assert a taste judgment as a defect — that reintroduces the vibecoding failure mode inside the
auditor.

**It is one lens with two directions**, because the presentation layer obeys the package's one idea
like every other layer — `gap = diff(to_be, as_is)`:

- **Backward (a UI exists).** Point it at what is there: does this read as designed, or as the
  statistical center of everything the model has seen? Rescue's `design-taste` module, Phase 1.
- **Forward (no UI exists yet).** Point it at what is *proposed*: two or three deliberately different
  directions, rendered, each naming the tells it refuses — and the human elects one, which becomes
  the DTCG contract. Greenfield's `design-propagation` step 1, then `design-taste` again at Phase 5
  over what was actually built.

Same catalog, same pin kind, same hard rule in both directions: **the lens proposes and never
elects.**

## Look at the render, not at the source

The tells are compositional — rhythm, hierarchy, what the hero says, how motion behaves — and not one
of them is visible in JSX. A lens that reads source files judges the *implementation* of a design and
then reports on the design.

So the order is fixed, and it is the fp-check line applied to pixels:

1. **Render it.** `design_scan` accepts URLs and a `viewport`, and renders them in a real browser, so
   each elected breakpoint is checked rather than assumed. A screenshot is a PNG, which
   `image_palette` and `palette_verify` decode in the stdlib.
2. **Spend the deterministic half first** — contrast, token membership, which colors actually occupy
   the frame and over what fraction of it. Facts, `confidence: extracted`, skipping fp-check.
3. **Judge only what survives.** A taste claim that is really a contrast failure is a fact somebody
   downgraded to an opinion, and it will be argued with instead of fixed.

When nothing can be rendered — no dev server, a component with no story, a target this host cannot
run — the surface is **`unchecked`, with the reason**, never a clean bill. Same rule the engines
themselves apply when a backend is missing.

## The tells (the "generated, not designed" catalog)

Adapted, with attribution, from two public catalogs (we author the lens; we install neither skill):

- **Impeccable's rule catalog** (Paul Bakaus, Apache-2.0) — the AI-slop clusters it names:
  purple/violet gradients, gradient text on headings, side-tab accent borders, nested cards,
  everything-centered layouts, monotonous spacing, bounce/elastic easing, glow-on-dark, hairline
  border + wide shadow, decorative grid backgrounds.
- **Anthropic's `frontend-design` philosophy** — five judgments the lens applies: **hero as thesis**
  (open with the subject's most characteristic thing, not a generic big number); **typography as
  personality** (pair display/body deliberately, not the default everyone reaches for); **structure
  encodes meaning** (numbered markers reflect a real sequence, not decoration); **deliberate motion**
  (animation serves the subject; scattered effects read as AI); **matching complexity to vision**
  (elegance is executing the chosen vision well, not adding).

The through-line both share: models reproduce the **statistical center** of design, so "looks like
every other AI UI" is the smell. Name the *class* — "this is the templated-default gradient tell",
"typography is neutral where the brief wants personality" — never just the instance. A blocking or
reopening verdict must teach, per the roster's teach-on-rejection rule (`core/agents.md`).

## Proposing a direction (the forward run)

A text-only agent cannot invent a tasteful palette by vibing one, and this package does not let it
try. What it can do is the `brainstorm` role's job, applied to the design fork: produce **two or
three deliberately different directions**, each of which is

- a **DTCG token set** — the machine contract, not an adjective;
- a one-line **thesis**: what the subject actually is, and what this direction does about it;
- the tells it **refuses**, by name from the catalog above, and what it does instead;
- a **rendered artifact** the human can look at — the `prototype` discipline: throwaway code that
  answers one design question, whose only durable output is the elected contract.

Then two checks before anything is elected. `palette_verify` runs each direction's claimed tokens
against its **own render**: a token that occupies no pixels is a contract that lies about itself.
`design_scan` runs over the same render, so a direction that is merely inaccessible is eliminated as
a fact rather than argued about as a preference.

Three rules keep this from collapsing back into vibing:

- **Differentiated, not variants.** Three directions that differ only in accent hue are one direction
  with a color picker, and offering them is how a fork gets rubber-stamped.
- **Recommend one, with a reason.** The role proposes *and* recommends; a menu handed to the human is
  work not done. It still never elects.
- **Nothing becomes the contract until a human has seen it rendered.** The election is on the
  artifact, not on the description of it — two people imagining the same words differently is the
  exact failure `prototype` exists to end.

The elected direction's token set goes to `generate_tokens` and becomes the enforced contract; the
prototypes are discarded. What the interview elects is recorded in cluster 5b of the decision
catalog like any other fork.

## How it binds

- **`design_concern` pins**, `confidence: inferred`, through fp-check — never `extracted`, and never
  a `contract_mismatch` (that kind is reserved for the deterministic token violation).
- **Options with tradeoffs.** "Leave as-is" (`state: accepted`) is a legitimate elected outcome; the
  `to_be` stays null until the user chooses. A taste finding is input to the interview, not a fix.
- **Read-only roles only.** The `reviewer` applies the lens as its design dimension on any diff that
  changes a rendered surface; the `challenger` may use it to refute an elected design `to_be` as
  templated or unfalsifiable. Neither writes code, neither decides.
- **Grounded, not vibed.** A taste claim cites the tell it matches — a catalog rule, a design
  principle — and carries its confidence, like any externally-grounded proposal
  (`core/knowledge-sources.md`).

## Scope, and what the lens must not do

**Scope is inherited, never chosen.** The lens reads what the deterministic detector already governs
— an elected `DESIGN.md`, the UI files or URLs `design_scan` reported, the render of the slice under
validation — so a repo with no presentation layer produces nothing rather than something. A lens that
picks its own scope finds what it went looking for.

**It does not overrule an elected oracle.** When a reference image *is* the specification (building a
UI from a screenshot), the picture decides: a taste observation there is a pin about the reference,
handed to the human, not a licence to redesign what they handed over.

**The limit, stated rather than implied:** an agent engine is D2, and nothing computes whether a
judgment lens actually ran. That holds for every `type: judgment` module in either catalog — which is
why the field never claims otherwise, and why the findings still pass fp-check like any other
inference.

## Floor · lens · ceiling

1. **Floor (deterministic, always on):** the detector + DTCG token membership — facts, fp-check-skipping.
2. **Lens (judgment, this doc):** the taste critique as read-only pins, in either direction.
3. **Ceiling (generation, opt-in, per-host):** the visual tools that *produce* design — Claude Design,
   Open Design — whose non-deterministic output the floor then verifies.

## Attribution

The rule catalog is **Impeccable's** (Paul Bakaus, Apache-2.0); the five design principles are
**Anthropic's** `frontend-design` skill. We adapt their *guidance* into a ledger-bound lens with
attribution and **install neither skill** — the self-contained rule holds: nothing external ships,
and the lens is ours, bound to the one source of truth.
