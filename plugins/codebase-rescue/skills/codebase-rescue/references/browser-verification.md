# Browser verification (Playwright) — observe the running UI, deterministically where it can be

The one place the package's "**resolved means *observed***" rule meets the frontend: a UI behavior or
a rendered design is verified by **driving a real browser**, not by reading source. The deterministic
carrier is a **committed Playwright spec** — the executor writes it, the measurer/reviewer re-run it
read-only — so a UI acceptance is reproducible and diffable like any test, never a one-off screenshot
someone eyeballed once.

`external:playwright`. Best-effort: absent, this whole surface degrades to what static analysis and
Impeccable's source/URL scans already cover, and the gap is noted — never a hard failure.

## Three uses, in priority order

### 1. Behavioral verification (primary) — `measurer` / verification-before-completion
A UI `acceptance_criterion` ("submitting the form with an empty email shows the inline error") becomes
a **red Track-A Playwright spec** the executor writes before building (`references/phase-4-remediation.md`),
and the **Phase-5 oracle** the measurer re-runs (`references/phase-5-validate.md`). The spec is the
committed carrier; the run is the evidence. This is the UI half of "a fix is not done because the
build is green" — the behavior was reproduced in a browser, or it is not resolved.

### 2. Design verification on the production render — the determinism split
When a design was explored in a visual tool, its HTML prototype is throwaway; the real UI is **rebuilt
as real components** and must be checked against the elected design contract. Two halves, on opposite
sides of the fp-check line:

- **Token-membership = deterministic.** Point `design_scan` at the running app's **URL** (`impeccable
  detect` renders it in a real browser): a production component using an off-token color / font /
  radius / size is a `design-system-*` `contract_mismatch` against the same DESIGN.md the prototype
  was captured into (`references/module-design-alignment.md`). A computed contrast ratio, a
  set-membership check — facts, `confidence: extracted`, skip fp-check.
- **Pixel-level "does it look right" = judgment.** Visual-regression (a screenshot diff) is a
  deterministic *mechanism* over a **noisy signal** — anti-aliasing, font hinting, GPU/OS rendering
  all produce false positives without a heavily pinned environment. So a visual diff is routed to a
  **human-reviewed pin** (the Chromatic/Percy pattern — accept/reject sets a new baseline), never
  auto-resolved. Gate merge on token-membership + the a11y subset (both deterministic); surface the
  visual diff for a human. Do **not** present a pixel diff as equivalently deterministic to the
  token check.

This also lets the human **approve the real component** without a throwaway prototype: render it
(dev server / Playwright), look at it, elect it. Visual judgment enters through a human's eyes on the
real artifact, not through a text-only agent inventing it.

### 3. Defect reproduction — `systematic-debugging`
A UI defect's Given/When/Then is pinned as a committed Playwright **repro spec** — the reproduction
that must exist before the fix, and that must pass after it (`references/module-logic.md` and the
systematic-debugging discipline: the root cause lands in the `defect` pin, the repro in the spec).

## The Playwright MCP (declared — delivered by the install)

Microsoft's **Playwright MCP** (`@playwright/mcp`) exposes the browser to an agent as an
**accessibility-tree snapshot** (structured, deterministic — not pixels), which suits *authoring* and
*exploration*: an agent finds the selectors and flows, then writes them into the committed spec. The
built plugin **declares** it (a `stdio` server, `npx -y @playwright/mcp@latest`), the same way it
delivers our own server — so a user gets the browser tools by installing, and the capability is
**discoverable**, not merely available.

It is declared, **not** opt-in, and the distinction is precise: the declared-vs-opt-in line is
*"connects with zero setup?"*. Unlike **cognee** (which cannot connect without a Docker container and
a key), the Playwright MCP **connects immediately** — stdio via npx, no container, no key. Its only
prerequisite is browser **binaries** for an actual navigation (`npx playwright install`), which is a
graceful **use-time** degrade — a clear "install the browser" error on first action, not a broken
server in every session. That is exactly how the toolchain treats every other tool: present and
discoverable, degrading with a note when a dependency is missing, never a hard failure. The committed
spec + CLI remain the deterministic verification *carrier*; the MCP is the *authoring/exploration*
surface on top — Microsoft's own split (CLI + skills for coding agents, MCP for exploration).

## Discipline

- **The committed spec is the deterministic carrier; the MCP is authoring.** A verdict rests on a
  re-runnable spec, never on a live interactive session no one can reproduce.
- **The executor writes; the measurer/reviewer/challenger only run it read-only** (the roster's
  single-writer rule — `references/core/agents.md`).
- **Deterministic vs judgment stays split**: token-membership and the a11y subset block; visual
  regression and aesthetic judgment go to human-reviewed pins.
- **Degrade, never hard-fail**: no Playwright → note the uncovered behavior/design as a coverage gap
  (the same doctrine as a missing static tool), never a silent pass.

## Attribution

Playwright and the Playwright MCP are Microsoft's (Apache-2.0). We consume them as toolchain tools and
bind their evidence to the ledger; we ship none of their code.
