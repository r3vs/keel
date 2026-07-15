#!/usr/bin/env bash
# Codebase Rescue — deterministic toolchain bootstrap.
# Python and Node are assumed present. Every install is best-effort: a missing tool must
# NOT abort the run — the skill degrades to model judgment and notes the gap.
# Idempotent: safe to re-run.

set -uo pipefail
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s (skill will degrade for this capability)\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- Pinned versions (reproducibility) --------------------------------------------------
# Deterministic toolchain: pin a version (e.g. SEMGREP_VER=1.106.0) and commit it. Empty = latest
# (convenient, NOT reproducible). This is the mechanism — fill in the pins you want to freeze.
: "${SEMGREP_VER:=}";  : "${LIZARD_VER:=}";   : "${JSCPD_VER:=}";        : "${ASTGREP_VER:=}"
: "${GRAPHIFY_VER:=}"; : "${CODEWIKI_VER:=}"; : "${IMPORTLINTER_VER:=}"; : "${DEPCRUISER_VER:=}"
pipspec() { [ -n "${2:-}" ] && printf '%s==%s' "$1" "$2" || printf '%s' "$1"; }
npmspec() { [ -n "${2:-}" ] && printf '%s@%s'  "$1" "$2" || printf '%s' "$1"; }

echo "== Codebase Rescue toolchain =="

# --- Core single-binary tools (Go/Rust, no runtime) ------------------------------------
# Prefer a native install path; fall back per-OS. These are the Tier-0/Tier-1 workhorses.
install_binary () { # name  brew_pkg  install_hint
  local name="$1" brew_pkg="$2" hint="$3"
  if have "$name"; then ok "$name (present)"; return; fi
  if have brew; then brew install "$brew_pkg" >/dev/null 2>&1 && { ok "$name (brew)"; return; }; fi
  warn "$name not installed — $hint"
}

install_binary tokei        tokei        "cargo install tokei | https://github.com/XAMPPRocky/tokei"
install_binary scc          scc          "https://github.com/boyter/scc/releases"
install_binary gitleaks     gitleaks     "https://github.com/gitleaks/gitleaks/releases"
install_binary osv-scanner  osv-scanner  "https://github.com/google/osv-scanner/releases"
install_binary trivy        trivy        "https://github.com/aquasecurity/trivy/releases"
install_binary rg           ripgrep      "https://github.com/BurntSushi/ripgrep/releases"

# --- Python-based tools ----------------------------------------------------------------
if have pipx || have pip3 || have pip; then
  PIP="pipx install"; have pipx || PIP="python3 -m pip install --user"
  for pkg in semgrep lizard; do
    case "$pkg" in semgrep) ver="$SEMGREP_VER";; lizard) ver="$LIZARD_VER";; *) ver="";; esac
    if have "$pkg"; then ok "$pkg (present)"; else
      $PIP "$(pipspec "$pkg" "$ver")" >/dev/null 2>&1 && ok "$pkg ($PIP)" || warn "$pkg not installed"
    fi
  done
else
  warn "no pip/pipx — semgrep, lizard unavailable"
fi

# --- Node-based tools ------------------------------------------------------------------
if have npm; then
  for spec in "jscpd:jscpd:$JSCPD_VER" "ast-grep:@ast-grep/cli:$ASTGREP_VER"; do
    bin="${spec%%:*}"; rest="${spec#*:}"; pkg="${rest%%:*}"; ver="${rest##*:}"
    if have "$bin" || { [ "$bin" = "ast-grep" ] && have sg; }; then ok "$bin (present)"; else
      npm i -g "$(npmspec "$pkg" "$ver")" >/dev/null 2>&1 && ok "$bin (npm)" || warn "$bin not installed"
    fi
  done
  # Optional secondary graph engine (deterministic blast-radius only).
  # NOTE: gitnexus is PolyForm Noncommercial — install only if non-commercial use is acceptable.
  if [ "${RESCUE_INSTALL_GITNEXUS:-0}" = "1" ]; then
    have gitnexus || npm i -g gitnexus >/dev/null 2>&1 && ok "gitnexus (npm, optional)" || warn "gitnexus not installed (optional)"
  fi
else
  warn "no npm — jscpd, ast-grep, gitnexus unavailable"
fi

# --- Wiki backbone (CodeWiki, runs on the Claude login in subscription mode) -----------
if have pip3 || have pip; then
  # Graphify = PRIMARY graph backbone (MIT). PyPI package name is graphifyy (double y).
  have graphify || { python3 -m pip install --user "$(pipspec graphifyy "$GRAPHIFY_VER")" >/dev/null 2>&1 && ok "graphify (pip, primary backbone)"; } || warn "graphify not installed — GRAPH BACKBONE MISSING, core module degrades to heuristics"
  have codewiki || { python3 -m pip install --user "$(pipspec codewiki "$CODEWIKI_VER")" >/dev/null 2>&1 && ok "codewiki (pip)"; } || warn "codewiki not installed — as-is wiki degraded"
fi

# --- Optional shape-engine backend: tree-sitter (generic extractor generalization) -----
# runtime/treesitter_extract.py uses it when present for more robust TS/GraphQL/arbitrary-stack
# extraction (a stack = a query, not a new parser). The runtime stays stdlib-only and degrades to
# the regex/ast parsers when it is absent — so this is genuinely optional.
if have pip3 || have pip; then
  python3 -c "import tree_sitter, tree_sitter_language_pack" >/dev/null 2>&1 \
    && ok "tree-sitter (present, optional shape-engine backend)" \
    || { python3 -m pip install --user tree-sitter tree-sitter-language-pack >/dev/null 2>&1 \
         && ok "tree-sitter (pip, optional shape-engine backend)"; } \
    || warn "tree-sitter not installed — shape engine uses the stdlib parsers (fine)"
fi

# --- Static analysis: architecture-fitness (best-effort; type-checkers are per-language) --
# Closes the doc<->installer gap: core/static-analysis.md documents these. Install the
# language-agnostic ones here; the per-language type-checkers are in the on-demand list below.
if have pip3 || have pip; then
  have lint-imports || { python3 -m pip install --user "$(pipspec import-linter "$IMPORTLINTER_VER")" >/dev/null 2>&1 && ok "import-linter (pip)"; } || warn "import-linter not installed — architecture-fitness degrades (py)"
fi
if have npm; then
  have depcruise || { npm i -g "$(npmspec dependency-cruiser "$DEPCRUISER_VER")" >/dev/null 2>&1 && ok "dependency-cruiser (npm)"; } || warn "dependency-cruiser not installed — architecture-fitness degrades (js/ts)"
fi

# --- Per-language, gated tools (informational; install on demand per detected language) -
cat <<'NOTE'

  Per-language tools are installed on demand once tokei reports the languages present:
    dead code    : vulture(py) · knip(js/ts) · deadcode(go) · cargo-udeps(rust)
    mutation     : mutmut(py) · stryker(js/ts) · pit(java) · cargo-mutants(rust)  [critical modules only]
    static types : tsc(ts) · mypy/pyright(py) · cargo check(rust) · go vet(go)    [highest-value static signal]
    navigation   : LSP server / SCIP indexer per language                         [precise refs, safe rename]
    architecture : ArchUnit(jvm) · ts-arch(ts)  [import-linter/dependency-cruiser installed above]

  Done. Missing tools are fine — the skill degrades to model judgment where a tool is absent.
NOTE
