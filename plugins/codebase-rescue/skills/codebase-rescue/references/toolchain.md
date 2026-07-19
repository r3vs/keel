# Deterministic Toolchain

Install with `scripts/bootstrap.sh` (Python + Node assumed). Every tool is best-effort: a
missing tool degrades to model judgment, never a hard failure. Normalize all output to
SARIF/JSON so fp-check and the interview see one format.

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

## Backbones
- **tree-sitter-native structural builder** — RECOMMENDED backbone. Build the graph's structural
  spine (files/symbols/tables as EXTRACTED nodes; `imports`/`calls` as EXTRACTED edges) from
  `web-tree-sitter` WASM grammars — the same parser `scripts/runtime/treesitter_extract.py` already loads,
  so it adds no new dependency. Deterministic, offline, incremental (signature fingerprints), and it
  produces exactly the spine `scripts/runtime/graph.py` consumes with nothing wasted. Prior art to model on:
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
  Not required: the as-is map ships as one self-contained HTML file (`scripts/runtime/map.py`); CodeWiki is a
  heavier alternative only if a full external wiki is wanted.

## Gated per language (run only when tokei detects the language)
- Dead code: vulture(py) · knip(js/ts) · deadcode(go) · cargo-udeps(rust)
- Mutation (test validity, slow — critical modules only): mutmut(py) · stryker(js/ts) · pit(java) · cargo-mutants(rust)

## Git analytics (near-zero install)
Churn, churn×complexity hotspots, co-change coupling, bus factor — a git-log script;
complexity comes from lizard. code-maat (JVM) optional for richer coupling.
