#!/usr/bin/env bash
# Codebase Rescue — deterministic toolchain bootstrap.
# Python and Node are assumed present. Every install is best-effort: a missing tool must
# NOT abort the run — the skill degrades to model judgment and notes the gap.
# Idempotent: safe to re-run.

set -uo pipefail
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s (skill will degrade for this capability)\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

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
    if have "$pkg"; then ok "$pkg (present)"; else
      $PIP "$pkg" >/dev/null 2>&1 && ok "$pkg ($PIP)" || warn "$pkg not installed"
    fi
  done
else
  warn "no pip/pipx — semgrep, lizard unavailable"
fi

# --- Node-based tools ------------------------------------------------------------------
if have npm; then
  for spec in "jscpd:jscpd" "ast-grep:@ast-grep/cli"; do
    bin="${spec%%:*}"; pkg="${spec##*:}"
    if have "$bin" || { [ "$bin" = "ast-grep" ] && have sg; }; then ok "$bin (present)"; else
      npm i -g "$pkg" >/dev/null 2>&1 && ok "$bin (npm)" || warn "$bin not installed"
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
  have graphify || { python3 -m pip install --user graphifyy >/dev/null 2>&1 && ok "graphify (pip, primary backbone)"; } || warn "graphify not installed — GRAPH BACKBONE MISSING, core module degrades to heuristics"
  have codewiki || { python3 -m pip install --user codewiki >/dev/null 2>&1 && ok "codewiki (pip)"; } || warn "codewiki not installed — as-is wiki degraded"
fi

# --- Per-language, gated tools (informational; install on demand per detected language) -
cat <<'NOTE'

  Per-language tools are installed on demand once tokei reports the languages present:
    dead code : vulture(py) · knip(js/ts) · deadcode(go) · cargo-udeps(rust)
    mutation  : mutmut(py) · stryker(js/ts) · pit(java) · cargo-mutants(rust)  [run only on critical modules]

  Done. Missing tools are fine — the skill degrades to model judgment where a tool is absent.
NOTE
