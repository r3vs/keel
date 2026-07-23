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

A `DESIGN.md` (Google's **Stitch** format — `google-labs-code/design.md`, Apache-2.0, which Impeccable
reads) carries the design system as YAML frontmatter; an optional `.impeccable/design.json` sidecar
extends it. The parts the detector enforces:

- **`typography`** — named roles with `fontFamily` and `fontSize` (plus an enumerated `scale`); the
  allowed fonts and the type ramp.
- **`colors`** — a name→value palette; a literal color outside it (within a small channel tolerance)
  is off-contract.
- **`rounded`** — the radius scale; a `border-radius` off the scale is off-contract.

This is the **field-shape engine applied to design tokens**: each token set is an `enum` of allowed
values, and membership is the check (`references/core/shape-engine.md` — "enum-membership", "never
fabricate"). Reading these as a contract is why a token drift is a *fact*, not an opinion.

**Only an *extracted-and-confirmed* DESIGN.md is a `contract_mismatch` source.** A well-formed
`DESIGN.md` is normally **captured from the code that actually renders** (Impeccable's own `/document`
extracts tokens from CSS vars / Tailwind / component source / the computed styles of the rendered
page, then refreshes to "the values the code actually uses"). A DESIGN.md **hand-authored and never
reconciled** with the code is *aspirational* — the code being off it may mean the doc is stale, not
that the code drifted. So treat an un-confirmed DESIGN.md as an `open_decision` (its tokens are a
proposed `to_be` to elect in the interview), and only after it has been confirmed against the real
tokens once does a `design-system-*` hit become a true `contract_mismatch`. The detector still runs;
what changes is the *kind* of pin the un-confirmed case produces.

## The contract carrier is DTCG — rescue extracts the as-is, elects the to-be

The machine contract of design is a **W3C DTCG** token set (the stable, 40+ vendor standard), not the
DESIGN.md frontmatter (Google Stitch alpha, with an incompatible Open Design fork). DESIGN.md is a
*generated projection* of the tokens — the one Impeccable reads to enforce membership. Rescue runs the
diff **backward**, exactly as it does for the data contract:

1. **as-is** — extract the code's **de-facto** design tokens (`extract_tokens`: the CSS custom
   properties the codebase declares, classified by value — a hex is a color, a `px` is a dimension —
   ambiguous values dropped, never guessed). This is a *candidate* DTCG, descriptive of the mess.
2. **to-be** — the user **elects** the DTCG token set in the interview (accept the extracted
   candidate, refine it — e.g. split the flat dimension group into radius / font-size / spacing — or
   import a real brand). Only the elected set is the contract.
3. **enforce** — `generate_tokens` projects the elected DTCG into a `DESIGN.md`, and `impeccable
   detect` flags every off-token usage as `design-system-*` → `contract_mismatch`; `tokens_diff`
   guards the generated CSS layer. Same `gap = diff(to_be, as_is)`, on the presentation layer.

## Verifying a re-implementation on the **production render** (not a prototype)

When a design comes from a visual tool (the opt-in ceiling below), its HTML prototype is **throwaway**;
what survives is the elected DTCG contract. The real UI is **rebuilt as real components** in the
project's framework (the Phase-4 loop), never transpiled from the HTML. To verify that rebuild honors
the design, point `design_scan` at the **running app's URL** (`impeccable detect` renders it in a real
browser): a production component that uses an off-token color/font/radius is caught as a
`design-system-*` `contract_mismatch` against the same DESIGN.md — deterministic. This is the
token-membership half; the pixel-level "does it look right" half is **judgment** (visual regression),
routed to a human-reviewed pin, never auto-resolved (`references/browser-verification.md`).

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
subcommand. We do **not** run it inside this deterministic module, and we do **not** install its
skill (self-contained). Where subjective design quality matters, it is a **reviewer / challenger
lens** — a judgment pin that DOES pass fp-check, authored here and adapted **with attribution** from
Impeccable's rule catalog and Anthropic's `frontend-design` principles, kept on the read-only side of
the roster. Full playbook: `references/design-taste-lens.md`. Keeping fact (the detector) and taste
(the critique) on opposite sides of the fp-check line is the same fact-vs-taste split this package
draws everywhere.

## Visual generation (opt-in, per-host — the ceiling)

The tools that *produce* design — turn a brief into a visual — are the **ceiling**, not the floor.
They are **opt-in, per-host, and never bundled** (both are external; self-contained holds). Our
deterministic layer is the floor and the **alignment guarantee**: whatever a non-deterministic
generator emits re-enters as an ordinary diff, verified against the elected DTCG contract by
`tokens_diff` + `impeccable detect` — enforced *more* strictly on a generator-originated diff, not less.

- **Claude Code → Claude Design** (Anthropic Labs). Web-only, human-in-the-loop; it produces
  HTML/CSS, not framework components, and ingests a design system as *prose* (no DESIGN.md parser, no
  autonomous API — it cannot be driven headless). **Sequencing matters:** establish the DTCG contract
  first (run the rescue), *then* point Claude Design at the codebase — pointed at un-rescued code it
  learns and mass-reproduces the existing drift ("messy material teaches messy patterns"). Its output
  is starting code, re-verified here like any diff.
- **Other hosts → Open Design** (nexu-io, Apache-2.0). An **opt-in MCP** (`od mcp install`) on Claude
  Code / Codex / opencode / Pi, local-first (Ollama = offline). Its own `DESIGN.md` is a
  **different, prose-only dialect** (machine data in a sibling `design-tokens.json`) — so consume its
  `design-tokens.json` (DTCG) as a candidate contract, **not** its prose. Its `od-code-migration`
  refreshes a repo to a design via a build/test loop and gates at **the PR**; rescue gates at **the
  pin** (per-drift election before any edit) — its migration diff can feed our ledger as input, not
  replace it.

Neither is declared by default: an external app / hosted product that fails to connect for everyone
who has not installed it is the cognee anti-pattern. The floor needs neither.

## Relationship to the rest

- **`contract-reconciliation`** is the same engine on the data contract; this is it on the design
  contract. Both emit `contract_mismatch`; both are deterministic; both sequence contract-first.
- **Greenfield's `design-propagation`** is the preventive mirror: author the `DESIGN.md` from decided
  design pins up front and wire `impeccable detect` as a CI drift-check, so the drift this module
  *finds* is, there, made impossible to introduce (`skills/greenfield-forge/references/design-propagation.md`).
- **Browser verification** (`references/browser-verification.md`) — render the real components and
  check the **production render**: `design_scan` on the running URL for deterministic token-membership,
  visual regression as a human-reviewed judgment pin. Also drives interaction-gated states a
  single-shot render misses.

## Degrade, never hard-fail

If `impeccable` is not runnable (needs Node ≥ 22.12 + npx, or a global binary), `design_scan` returns
`{"unchecked": true, "reason": ...}` — a design finder that could not run is **"not looked at", never
"no slop"** (the coverage-gap doctrine). `scripts/bootstrap.sh` installs it best-effort; its absence
is a visible gap in the ledger, not a silent clean bill.

## Attribution

The `DESIGN.md` format is **Google's** — the Stitch design spec, open-sourced as
`google-labs-code/design.md` (Apache-2.0, `version: alpha`). The detector, its rule catalog, and the
`design-system-*` membership checks that read a DESIGN.md are **Impeccable's** (Paul Bakaus,
Apache-2.0). We consume `detect --json`, add the ledger binding, and adapt the rule catalog for the
taste lens with attribution; we ship none of their code.
