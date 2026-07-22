# Module: Design Propagation (core)

Contract-propagation applied to the layer types cannot describe: the **rendered design**. Where
`contract-propagation` authors the data contract once and generates every data layer from it,
design-propagation authors the **design contract once** — a set of **W3C Design Tokens (DTCG)** — and
generates every design layer from it, so a UI cannot drift off the design system any more than a DTO
can drift off the data model. It is the exact preventive mirror of rescue's `design-alignment`: the
token drift rescue spends its engine *finding*, greenfield makes impossible to introduce, then guards
for the life of the project.

## The contract carrier is DTCG, not DESIGN.md frontmatter

The machine contract of record is a **DTCG token JSON** — the W3C Design Tokens Format Module (stable
2025.10; a 40+ vendor standard: Figma, Style Dictionary, Terrazzo, Tokens Studio, Penpot). It is the
stable, externally-governed, non-drifting carrier this package's doctrine demands. `DESIGN.md` is
**generated from it**, not authored as the primary artifact — exactly as Google's own
`@google/design.md` CLI exports DTCG. This is deliberate and load-bearing:

- DESIGN.md's own frontmatter is a **single-vendor alpha** spec (Google Stitch, `version: alpha`)
  and already has an **incompatible fork** (Open Design's prose-only dialect, machine data in a
  sibling `tokens.css`/`design-tokens.json`). Betting the machine contract on it is the drift trap we
  avoid everywhere else.
- So the tokens are the truth; DESIGN.md is one generated projection (the one Impeccable reads to
  enforce membership), CSS variables another, a Tailwind `@theme` another.

## The hinge (rescue's design diff, run in reverse)

- rescue **discovers** design drift after the fact: `impeccable detect` against the code, and where a
  DESIGN.md governs, a `design-system-*` hit is a `contract_mismatch`.
- greenfield **installs** the design contract up front: elect the DTCG tokens, generate every layer
  from them, and wire the drift-check so a hand-edit that reaches for an off-token font/color/radius
  fails the build.

A token set is an `enum` of allowed values, and membership is the check — the field-shape engine
(`references/core/shape-engine.md`) pointed at the presentation layer, run forward.

## Procedure

### 1. Elect the DTCG token contract — captured or imported, never invented blind
The decision-catalog's **cluster 5b** (design system) is elected in the interview like any fork. A
text-only agent cannot *invent* a tasteful palette or type pairing — so the tokens are **captured or
imported**, never authored from a vibe:
- **captured from an approved visual direction** — the human drives a visual tool (the opt-in ceiling
  below), *sees* and approves a direction, and its tokens become the DTCG contract;
- **imported** — an existing brand, a Figma Variables export (DTCG-native), or a component library's
  tokens;
- and only a decided design system yields a contract: "no formal system in v1" → no DTCG, only the
  universal a11y/slop checks run (YAGNI). Ground token choices in current sources where useful
  (`references/core/knowledge-sources.md`), cite them, but the **interview decides** — the generator
  never picks a palette.

### 2. Generate every design layer from the one contract (`generate_tokens`)
`generate_tokens(contract, out)` projects the DTCG JSON into the aligned layers:
- **CSS custom properties** (`tokens.css`) — the exact, lossless projection the build consumes;
- **Tailwind v4 `@theme`** (`theme.css`) — the same tokens as Tailwind utilities;
- **`DESIGN.md`** (Stitch frontmatter) — the surface Impeccable enforces membership against.

This step emits the **token surfaces**, not the UI — exactly as `contract-propagation` emits the
typed DTO/client surfaces and leaves handler bodies to Phase 4. The **real components** that use
these tokens are `implement` BuildItems built **test-first in Phase 4**, in the project's actual
framework, referencing the generated CSS variables / Tailwind theme — so they are **structurally
token-bound** (a component literally cannot name a value outside the contract) and are **real
components, never throwaway HTML**. There is no prototype to re-implement and no transpile step: the
token economy of "generate HTML, then rebuild it as real components" is avoided because we generate
the contract once and build the real thing against it directly (context-rich by construction — we
have the ledger, the data contract, and the component inventory).

### 3. Install the drift-check (the preventive payload)
Wire two checks into CI, both deterministic:
- **`tokens_diff`** — re-extract the CSS variables and diff them against the DTCG contract; a
  hand-edit that changes a generated token value fails the build (the design twin of `contract_diff`;
  a correct generated layer round-trips to zero drift).
- **`impeccable detect --no-advisory`** — membership over the actual UI source/render against the
  generated `DESIGN.md`; an off-token font/color/radius/size is a `design-system-*` failure.
The static `tokens_diff` catches edits to the token *definitions*; `impeccable detect` catches a
component that *uses* an off-contract value. Static + membership together, for the life of the project.

## What NOT to do

- **Do not generate throwaway prototypes.** We are context-rich; build the real components against the
  contract. Throwaway HTML belongs only to *divergent visual exploration* in the opt-in tools below,
  and even there its only durable output is the DTCG contract — the HTML is discarded.
- **Do not auto-transpile** an HTML/Figma prototype into framework code — a confirmed anti-pattern
  (the refactor usually costs more than building against the contract).
- **Do not hand-maintain tokens in two places.** The DTCG JSON is the one source; every layer is
  generated. A palette duplicated into a component reintroduces the drift this exists to cure.
- **Do not invent tokens the interview did not elect.** No speculative palette; an undecided design
  system has no DTCG contract.
- **Do not treat DESIGN.md as the machine contract.** It is a generated projection; edit the DTCG.

## Runtime

`design_tokens.py` (stdlib-only, tested in CI) backs `generate_tokens` (DTCG → CSS / Tailwind /
DESIGN.md) and `tokens_diff` (the drift-check). Alignment is mechanical: the generator's own tests
generate the CSS layer and run `tokens_diff` over it — a correct generator round-trips to **zero
drift**. Verified end-to-end: a DTCG contract → generated DESIGN.md → `impeccable detect` reads it and
flags off-contract usage as `design-system-*`. Richer generators (Style Dictionary, Terrazzo) that add
iOS/Android targets are preferred **when present**; this stdlib floor covers the web targets offline.

## Visual generation (opt-in, per-host — the ceiling, not the floor)

The *capturing* of a design direction in step 1 can use a visual tool the user already has — **Claude
Design** on Claude Code, **Open Design** on any host — as an opt-in ceiling. Our deterministic layer
is the floor and the **alignment guarantee**: whatever those non-deterministic tools emit re-enters as
an ordinary diff, verified against the elected DTCG contract by the drift-check above. We bundle
neither (self-contained). Details + sequencing: the per-host section of
`skills/codebase-rescue/references/module-design-alignment.md`.

## Relationship

- **`contract-propagation`** is the same move on the data contract; this is it on the design contract.
  Both author a carrier, generate every layer, and wire a CI drift-check; both sit in Wave 1.
- **Rescue's `design-alignment`** (`skills/codebase-rescue/references/module-design-alignment.md`) is
  the curative twin — it *finds* the drift this module *prevents*.

## Attribution

The **DTCG** token format is the W3C Design Tokens Community Group's. The `DESIGN.md` format is
**Google's** (Stitch, `google-labs-code/design.md`, Apache-2.0). The detector and its `design-system-*`
membership checks are **Impeccable's** (Paul Bakaus, Apache-2.0). We generate DTCG→layers ourselves
and consume `detect` as a CI scanner; we ship none of their code.
