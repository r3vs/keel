# Deterministic Toolchain

Install with `scripts/bootstrap.sh` (Python + Node assumed). Every tool is best-effort: a
missing tool degrades to model judgment, never a hard failure.

**Normalization is a command, not an aspiration.** Every tool below emits SARIF or JSON; the
`findings_gate` tool turns that into pins — pass it the reports (`.audit/*.sarif .audit/*.json`).

That is the single entry point for every finding module (security, maintainability,
placeholder-stub, test-validity, type-check, architecture-fitness). It normalizes, gates through
fp-check, clusters by root cause, and maps survivors to `defect` / `incompleteness` pins. The line
that used to stand here — *"normalize all output to SARIF/JSON so fp-check and the interview see
one format"* — described this and never said to run it, which is how a tested implementation and a
playbook that reimplements it by judgment end up side by side.

**Coverage is a fact, not a hope.** After the tools run, the `coverage_gaps` tool (pass it the
`langs` tokei detected and the `reports`) compares the capabilities EXPECTED for the present stacks
against the tools that actually produced a report, and writes a `coverage-gap` `incompleteness` pin
for each uncovered one. A tool that did not run is a **visible gap, never a silent clean 0**
(`references/core/static-analysis.md`).

**Type-checker output is the exception worth knowing:** `findings_gate` marks rule-ids prefixed
`mypy` / `tsc` / `pyright` / `typecheck` / `compile` / `syntax` as **deterministic**, so they skip
fp-check entirely and are never DROPPED as suspected false positives. A proven diagnostic needs no
corroboration (`references/core/static-analysis.md`). That is also why it is worth authoring
constraints so the strongest signal applies: a boundary expressed as an import-linter rule becomes
a fact, where the same boundary expressed in prose stays an opinion.

## Always-on (multi-language, fast install)
- **tokei / scc** — census: which languages exist → which gated tools to run; complexity estimate.
- **semgrep** (CE) — SAST, 30+ languages, `--config=auto`, SARIF. (OpenGrep fork for cross-file taint.)
- **ast-grep** — tree-sitter structural search/rewrite; the engine for placeholder/stub rules.
- **ripgrep** — fast text pass (TODO/FIXME/NotImplemented/empty-catch).
- **gitleaks** — secrets in working tree AND full git history.
- **osv-scanner** + **trivy** — deps (SCA), IaC misconfig, license, SBOM.
- **lizard** — cyclomatic complexity / function length, ~15 languages.
- **jscpd** — copy-paste / clone detection, 150+ formats.

## Static navigation & type signal (SOTA — often under-used; read `references/core/static-analysis.md`)
- **Type-checkers / compilers** — `tsc --noEmit`, mypy/pyright (py), `cargo check` / rust-analyzer,
  `go vet`. The highest-value static signal, tied directly to contracts and logic; a type error is
  a fact (`extracted` confidence), not a guess, and skips the heavy fp-check. Run per language tokei
  detects; also the in-loop signal during Phase-4 remediation.
- **LSP / SCIP index** — precise defs/refs/call-hierarchy and safe rename. The SOTA navigation
  primitive, more reliable than the graph's cross-layer edges (Phase-0 verdict); prefer it where a
  language server exists, the graph complements it.
- **Architecture-fitness / dependency-constraint** — import-linter (py), dependency-cruiser / ts-arch
  (js/ts), ArchUnit (jvm). Encodes the elected boundaries as executable constraints → `design_concern`
  on violation (rescue) or a CI gate (greenfield).

## Dynamic / browser verification (UI behavior + rendered design)
- **Playwright** (`external:playwright`) — drive a real browser to verify UI behavior and the
  **production render**. The carrier is a **committed spec** (re-runnable, diffable), not a one-off
  screenshot: the executor writes it, the measurer re-runs it read-only as the Phase-5 oracle.
  Token-membership on the render (`impeccable detect <url>`) is deterministic; a pixel visual-regression
  diff is judgment (human-reviewed pin). The Playwright **MCP** (accessibility-tree snapshots) is an
  **opt-in** authoring aid, not declared by default — it needs browser binaries (`npx playwright
  install`). Full playbook: `references/browser-verification.md`. Best-effort; absent → the UI surface
  degrades to static + Impeccable source scans, noted as a coverage gap.

## Backbones
- **tree-sitter-native structural builder** — RECOMMENDED backbone. Build the graph's structural
  spine (files/symbols/tables as EXTRACTED nodes; `imports`/`calls` as EXTRACTED edges) from
  `web-tree-sitter` WASM grammars — the same parser the tree-sitter extraction backend already loads,
  so it adds no new dependency. Deterministic, offline, incremental (signature fingerprints), and it
  produces exactly the spine the `blast_radius` graph consumes with nothing wasted. Prior art to model on:
  [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) (MIT). See
  `references/phase-1-comprehension.md`; the rationale is the step-0 verdict below.
- **graphify** (graph, pip `graphifyy`) — OPTIONAL alternative source of a compatible NetworkX
  `graph.json`. MIT; 31+ languages via tree-sitter; models DB schema (`sql` extra) as nodes; "why"
  nodes; EXTRACTED/INFERRED/AMBIGUOUS confidence; Ollama-local semantic pass. **Demoted from
  primary:** the step-0 gating verdict (`references/contract-reconciliation.md`) found its
  cross-layer edges are the INFERRED tier we already refuse to ride (~0 usable semantic edges on a
  real repo) — we use only its structural spine, which the native builder produces without the
  external dependency.
- **gitnexus** (graph, npm) — OPTIONAL secondary, deterministic blast-radius only. NOTE:
  PolyForm Noncommercial license (no commercial use); code-structure only (no DB schema);
  does not link separate frontend/backend trees. Not the backbone.
- **codewiki** (pip) — OPTIONAL visual-first as-is wiki (subscription mode runs on the Claude login).
  Not required: the as-is map ships as one self-contained HTML file (the `render_map` tool); CodeWiki is a
  heavier alternative only if a full external wiki is wanted.

## Gated per language (run only when tokei detects the language)
- Dead code: vulture(py) · knip(js/ts) · deadcode(go) · cargo-udeps(rust)
- Mutation (test validity, slow — critical modules only): mutmut(py) · stryker(js/ts) · pit(java) · cargo-mutants(rust)

## Git analytics (near-zero install)
Churn, churn×complexity hotspots, co-change coupling, bus factor — a git-log script;
complexity comes from lizard. code-maat (JVM) optional for richer coupling.
