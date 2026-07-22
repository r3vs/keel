# Module: Design Propagation (core)

Contract-propagation applied to the layer types cannot describe: the **rendered design**. Where
`contract-propagation` authors the data contract once and generates every layer from it,
design-propagation authors the **design contract** once — a `DESIGN.md` of tokens — and makes every
future UI edit answer to it via a CI check. It is the exact preventive mirror of rescue's
`design-alignment`: the token drift rescue spends its engine *finding*, greenfield makes impossible
to introduce and then guards for the life of the project. Same idea as the data contract, one layer
over.

## The hinge (rescue's design diff, run in reverse)

- rescue **discovers** design drift after the fact: it runs Impeccable's `detect` and, where a
  `DESIGN.md` exists, a `design-system-*` hit is a `contract_mismatch` against it.
- greenfield **installs** the design contract up front: author the `DESIGN.md` from the decided
  design-system pin, then wire that very same `detect` as a CI drift-check so a hand-edit that
  introduces an off-token font / color / radius / size **fails the build**.

A token set is an `enum` of allowed values, and membership is the check — the same field-shape engine
that guards the data contract (`references/core/shape-engine.md`), pointed at the presentation layer.
Drift that would otherwise be a matter of taste caught (if ever) in review becomes a deterministic
build failure the moment it lands.

## What the DESIGN.md declares (the contract carrier)

A `DESIGN.md` (Google's **Stitch** format — `google-labs-code/design.md`, Apache-2.0) carries the design system as YAML frontmatter;
an optional `.impeccable/design.json` sidecar extends it with tonal ramps. The parts `detect`
enforces — i.e. the tokens worth deciding:

- **`typography`** — named roles with `fontFamily` and `fontSize`, plus an enumerated `scale`: the
  allowed fonts and the type ramp.
- **`colors`** — the name→value palette (a literal color outside it, within a small channel
  tolerance, is off-contract).
- **`rounded`** — the radius scale.

This is the design analog of contract-propagation's shared-types package: the **single source** every
UI slice's styling is a projection of.

## Procedure

### 1. Author the DESIGN.md from the decided design-system pin (never from a vibe)
The decision-catalog's **cluster 5b** (design system) is elected in the interview like any fork. From
that committed pin — palette, type ramp, radii (or "mirror a component library's tokens") — author the
`DESIGN.md` frontmatter. Only a decided design system produces a `DESIGN.md`; if the interview chose
"no formal system in v1", there is no contract and only the universal a11y/slop checks run (YAGNI by
construction — do not invent tokens the user did not decide). Ground token choices in current sources
where useful (`references/core/knowledge-sources.md`), cite them, but the **interview decides** — the
generator never picks a palette.

### 2. Generate the UI scaffolds against the tokens
The typed component/style scaffolds a slice needs reference the DESIGN.md tokens (CSS variables /
theme object) rather than literals, so alignment holds by construction. The component *bodies* are
`implement` BuildItems for Phase 4 (Track A); this step emits the **token surface** they build on,
exactly as contract-propagation emits typed layer surfaces, not handler logic.

### 3. Wire `impeccable detect` as the CI drift-check (the preventive payload)
Add `impeccable detect --no-advisory <ui paths>` to CI. Its exit code is non-zero on any
`design-system-*` violation (a token off the DESIGN.md) or hard quality issue, so the build **fails
on design drift** — the presentation-layer twin of contract-propagation's shape-diff. Keep the
advisory rules as a **non-blocking report** (drop them from the gate with `--no-advisory`, surface
them in review), so soft signals inform without blocking. For a rendered pass, point `detect` at the
running app's **URL** — Impeccable renders it in a real browser (Puppeteer) and catches cascade- and
layout-dependent drift a source scan misses; add `--viewport 390x844` for a mobile-width gate.

### 4. From now on, drift is impossible to introduce silently
A future hand-edit that reaches for a one-off color or an undeclared font is caught the moment it
lands — the project stays design-aligned for life, not just at scaffold time. This is what makes the
design system *durable* rather than a document that rots. Adding a token is then a deliberate
DESIGN.md edit (a design decision), not an accident in a component.

## What NOT to do

- **Do not hand-maintain tokens in two places.** The DESIGN.md is the one source; components
  reference it. Duplicating the palette into a component reintroduces exactly the drift this exists
  to cure.
- **Do not invent tokens the interview did not decide.** No speculative palette "for later"; an
  undecided design system has no DESIGN.md. Anti-slop at the design level.
- **Do not gate CI on advisory rules.** Advisory (off-palette soft, em-dash overuse) informs; only
  the hard `design-system-*` and quality failures block. Blocking on taste is the vibecoding failure
  mode wearing a CI hat.
- **Do not treat the DESIGN.md as generated output.** Unlike the shared-types carrier (generated from
  the data model), the DESIGN.md is *authored from a decision* — it is a `contract_carrier` the agent
  writes, and the drift-check guards it. Regenerating it from code would invert the contract.

## Output

The `DESIGN.md` (the design contract), token-referencing UI scaffolds, and an installed CI
drift-check (`impeccable detect --no-advisory`) — written to disk, with a `BuildItem`
(`action: scaffold`, `contract_carrier` set to the DESIGN.md) and a `configure` item for the CI
wiring, both in **Wave 1** alongside the data contract (everything UI `depends_on` the design
contract, so it comes first — it falls out of the DAG, not a hardcoded order).

## Relationship

- **`contract-propagation`** is the same move on the data contract; this is it on the design
  contract. Both author a carrier and wire a CI drift-check; both sit in Wave 1.
- **Rescue's `design-alignment`** (`skills/codebase-rescue/references/module-design-alignment.md`) is
  the curative twin — it *finds* the drift this module *prevents*. The `design-system-*` findings
  there are violations of the DESIGN.md this module authors.

## Attribution

The `DESIGN.md` format is **Google's** (the Stitch spec, `google-labs-code/design.md`, Apache-2.0,
`version: alpha`). The detector and its `design-system-*` membership checks are **Impeccable's** (Paul
Bakaus, Apache-2.0). We generate the DESIGN.md from the decided design contract and consume `detect`
as a CI scanner; we ship none of their code. (This playbook is being reworked so the machine contract
is **W3C DTCG** tokens, with DESIGN.md generated from them — see the design-layer plan.)
