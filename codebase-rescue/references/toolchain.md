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

## Backbones
- **graphify** (graph, pip `graphifyy`) — PRIMARY backbone. MIT license. 31+ languages via
  tree-sitter; models DB schema (`sql` extra) as nodes; spans DB<->API<->frontend; "why"
  nodes; EXTRACTED/INFERRED/AMBIGUOUS confidence; plain NetworkX `graph.json`. Semantic pass
  runs local via Ollama (no code leaves the machine). Cross-layer edges are INFERRED hints.
- **gitnexus** (graph, npm) — OPTIONAL secondary, deterministic blast-radius only. NOTE:
  PolyForm Noncommercial license (no commercial use); code-structure only (no DB schema);
  does not link separate frontend/backend trees. Not the backbone.
- **codewiki** (pip) — visual-first as-is wiki; subscription mode runs on the Claude login.

## Gated per language (run only when tokei detects the language)
- Dead code: vulture(py) · knip(js/ts) · deadcode(go) · cargo-udeps(rust)
- Mutation (test validity, slow — critical modules only): mutmut(py) · stryker(js/ts) · pit(java) · cargo-mutants(rust)

## Git analytics (near-zero install)
Churn, churn×complexity hotspots, co-change coupling, bus factor — a git-log script;
complexity comes from lizard. code-maat (JVM) optional for richer coupling.
