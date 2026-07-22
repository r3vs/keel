# Module: Design Alignment (deterministic)

The cross-layer contract engine, turned on the layer the others cannot see: the **rendered
presentation**. `contract-reconciliation` diffs an entity's shape across DB / ORM / API / frontend
*types*; this module diffs the **design** — fonts, colors, radii, type ramp, and the a11y/slop tells
of AI-generated UI — against the project's own declared design system. It is the presentation-layer
face of the one idea: `gap = diff(to-be, as-is)`, where the to-be is a `DESIGN.md`.

## The detection is NOT reinvented — the binding is ours

Detection shells **Impeccable** (`pbakaus/impeccable`, Apache-2.0): a **no-LLM** scanner for
AI-slop tells and design-quality / accessibility issues across HTML / CSS / JSX / TSX / Vue / Svelte,
and — when the project carries a `DESIGN.md` — for drift away from that declared design system. We
consume its `detect --json` like any toolchain scanner (semgrep, knip) and add the one thing a lint
report cannot have: a place in the **ledger**. Each hit becomes a pin that flows through the same
interview → remediation → resolve-when-observed machinery as every DB/logic pin, in the single source
of truth. A design finding that lived only in Impeccable's report would be a **stateless twin** beside
the ledger — the exact divergence this package exists to find. That binding — not a reimplementation —
is why the self-contained rule is satisfied: Impeccable is a scanner in the toolchain, not a sibling
skill we install.

## Two pin kinds, split by a deterministic carrier (never by judgment)

Impeccable's own antipattern **id** is the carrier — no prose-grep, no model call:

| Impeccable hit | Pin kind | Why |
|---|---|---|
| `design-system-font` · `design-system-color` · `design-system-radius` · `design-system-font-size` | **`contract_mismatch`** | a token (font/color/radius/size) used in the code that the project's `DESIGN.md` does **not** declare — `as_is` = the code's token, `to_be` = the DESIGN.md's. The frontend analog of a shape diff. |
| everything else (`low-contrast`, `overused-font`, `skipped-heading`, `gpt-thin-border-wide-shadow`, …) | **`design_concern`** | a universal a11y / slop tell that holds with or without a project design system — an *option* the interview weighs, not a contract breach. |

The `design-system-*` ids are emitted **only when a `DESIGN.md` actually governs the files**
(Impeccable resolves it by walking up from each file to the project root — `.git` / `package.json` /
`.impeccable`), so a `contract_mismatch` here is never fabricated: its existence *is* the proof a
contract was in force. No DESIGN.md in the repo → no `design-system-*` hits → only `design_concern`s,
and "adopt a DESIGN.md" becomes a legitimate interview outcome (a remediation), not an assumed default.

## The DESIGN.md contract — what it declares

A `DESIGN.md` (Google Stitch convention, Impeccable's) carries the design system as YAML frontmatter;
an optional `.impeccable/design.json` sidecar extends it. The parts the detector enforces:

- **`typography`** — named roles with `fontFamily` and `fontSize` (plus an enumerated `scale`); the
  allowed fonts and the type ramp.
- **`colors`** — a name→value palette; a literal color outside it (within a small channel tolerance)
  is off-contract.
- **`rounded`** — the radius scale; a `border-radius` off the scale is off-contract.

This is the **field-shape engine applied to design tokens**: each token set is an `enum` of allowed
values, and membership is the check (`references/core/shape-engine.md` — "enum-membership", "never
fabricate"). Reading these as a contract is why a token drift is a *fact*, not an opinion.

## Method

1. **Run the detector** through the `design_scan` MCP tool over the frontend paths (files, dirs, or
   **URLs** — a URL renders in a real browser via Puppeteer, so cascade- and layout-dependent issues
   that source scanning misses are caught). `design_scan` normalizes `detect --json` into the
   package's finding shape and routes each hit to its pin kind by the table above.
2. **Deterministic findings skip fp-check.** No model ran — WCAG contrast is a computed ratio, an
   off-palette color is set-membership — so every hit carries `confidence: extracted` and bypasses the
   false-positive gate, exactly like a type error (`references/core/static-analysis.md`). Do **not**
   route these through `findings_gate`'s fp-check; they are facts.
3. **Advisory hits are surfaced, floored, and flagged.** Impeccable marks some rules `advisory`
   (off-palette color, em-dash overuse): real signals it never counts as failures. `design_scan`
   floors them to `severity: low` and stamps `advisory: true`, so the interview sees the whole design
   picture while the severity threshold keeps them off the blocker path — surface everything, block on
   nothing soft.
4. **Materialize pins**, clustered by `check_id` so N instances of one drift collapse to one decision
   (Phase-1 rule). A `contract_mismatch` against the DESIGN.md sequences like any contract pin —
   before the logic that depends on it. A `design_concern` is an **option**: "leave as-is"
   (`state: accepted`) is a legitimate interview answer; never present a taste judgment as a defect
   (that is the vibecoding failure mode inside the auditor).
5. **Responsive / scoped passes** when a decision needs them: `design_scan(..., viewport="390x844")`
   for a mobile-width URL render, `scope="type,layout"` to restrict the domain. Optional, not default.

## The *taste* half is a lens, not this detector

Impeccable also ships an **LLM critique** — the subjective "does this look designed or generated"
judgment — as its own *skill* (installed via `impeccable install`), deliberately **not** a `detect`
subcommand. We do **not** run it inside this deterministic module. Where subjective design quality
matters, it is a **reviewer / challenger lens** (`references/core/agents.md`): a judgment pin that
DOES pass fp-check, adapted from Impeccable's rule catalog **with attribution**, kept on the
read-only side of the roster. Keeping fact (the detector) and taste (the critique) on opposite sides
of the fp-check line is the same fact-vs-taste split this package draws everywhere.

## Relationship to the rest

- **`contract-reconciliation`** is the same engine on the data contract; this is it on the design
  contract. Both emit `contract_mismatch`; both are deterministic; both sequence contract-first.
- **Greenfield's `design-propagation`** is the preventive mirror: author the `DESIGN.md` from decided
  design pins up front and wire `impeccable detect` as a CI drift-check, so the drift this module
  *finds* is, there, made impossible to introduce (`skills/greenfield-forge/references/design-propagation.md`).
- **Browser verification** — a browser driver (Playwright) can drive the app into an
  interaction-gated state and hand the rendered URL to `design_scan`, for design checks that only
  appear after a user flow. Optional synergy; Impeccable's own single-shot URL render covers the
  common case.

## Degrade, never hard-fail

If `impeccable` is not runnable (needs Node ≥ 22.12 + npx, or a global binary), `design_scan` returns
`{"unchecked": true, "reason": ...}` — a design finder that could not run is **"not looked at", never
"no slop"** (the coverage-gap doctrine). `scripts/bootstrap.sh` installs it best-effort; its absence
is a visible gap in the ledger, not a silent clean bill.

## Attribution

The detector, its rule catalog, the `design-system-*` DESIGN.md checks, and the `DESIGN.md` (Google
Stitch) convention are **Impeccable's** (Paul Bakaus, Apache-2.0). We consume `detect --json` and add
the ledger binding; we ship none of its code, and the taste-lens adaptation credits its catalog.
