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
: "${IMPECCABLE_VER:=}"; : "${PLAYWRIGHT_VER:=}"
pipspec() { [ -n "${2:-}" ] && printf '%s==%s' "$1" "$2" || printf '%s' "$1"; }
# Grammars are fetched at runtime keyed by the pack's version, so pinning it pins the extraction —
# leave empty for latest, per the convention above. 1.12.5 (2026-07-07) is what this repo is tested
# against: MIT, abi3 wheels incl. win_amd64/win_arm64, no compiler at install, `tree-sitter>=0.23`.
TREE_SITTER_VER=""
TS_LANG_PACK_VER=""
npmspec() { [ -n "${2:-}" ] && printf '%s@%s'  "$1" "$2" || printf '%s' "$1"; }

echo "== Codebase Rescue toolchain =="

# --- uv: a HARD prerequisite (the CLI floor is gone) ------------------------------------
# The runtime is reached ONLY through the MCP server, which the host spawns as
# `uv run --script .../server.py`. There is no bundled-CLI floor anymore, so without uv on PATH the
# deterministic runtime is entirely unavailable. Rather than let that fail silently mid-run, uv is a
# hard prerequisite: install it, and if that cannot be done, ABORT loudly — a fail-fast the operator
# can act on, never a silent degrade. (Every OTHER tool below stays best-effort.)
if ! have uv; then
  if have curl; then
    curl -LsSf https://astral.sh/uv/install.sh 2>/dev/null | sh >/dev/null 2>&1 || true
  elif have wget; then
    wget -qO- https://astral.sh/uv/install.sh 2>/dev/null | sh >/dev/null 2>&1 || true
  fi
  # The installer puts uv in ~/.local/bin, which may not be on PATH for this shell yet.
  have uv || { [ -x "$HOME/.local/bin/uv" ] && export PATH="$HOME/.local/bin:$PATH"; }
fi
if have uv; then
  ok "uv (present) — MCP server can start"
else
  printf '  \033[31m✗\033[0m %s\n' "uv MISSING and could not be installed — the MCP server cannot \
start and the runtime is unavailable. Install it from https://astral.sh/uv and re-run. Aborting." >&2
  exit 1
fi

# Warm the dependency cache so the server also starts offline. A cold cache with no network is
# uv's one hard failure: first run needs the network, every run after does not.
if have uv; then
  # `dirname "$0")/../..` is the repo root in dev, where src/mcp/server.py lives (the old `/..`
  # stopped one level short, so the path had a doubled `src/` and never resolved). In the shipped
  # skill the server is in a sibling plugin (keel-core/mcp) and is not reachable relatively, so
  # the `-f` test fails and the host warms it on its own first spawn. Report only what actually ran.
  _server="$(cd "$(dirname "$0")/../.." && pwd)/src/mcp/server.py"
  if [ -f "$_server" ] && timeout 180 uv run --script "$_server" --help >/dev/null 2>&1; then
    ok "MCP dependency cache warmed (server starts offline from here on)"
  else
    warn "MCP server not reachable from here to warm — its deps resolve on the host's first spawn (needs network then)"
  fi
fi

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
  # impeccable = the design-alignment detector (Paul Bakaus, Apache-2.0; no-LLM). Needs Node >=22.12.
  # Absent → design-alignment reports 'unchecked', never a clean bill (coverage-gap doctrine).
  # playwright = browser verification (Microsoft, Apache-2.0). The CLI installs here; the browser
  # BINARIES are a separate opt-in (`npx playwright install`, hundreds of MB) — not pulled by default.
  for spec in "jscpd:jscpd:$JSCPD_VER" "ast-grep:@ast-grep/cli:$ASTGREP_VER" "impeccable:impeccable:$IMPECCABLE_VER" "playwright:playwright:$PLAYWRIGHT_VER"; do
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
  # Graphify = OPTIONAL alternative graph source (MIT). The backbone is the stdlib + tree-sitter
  # builder graph_build.py (the build_graph tool), which needs no install. PyPI package is graphifyy (double y).
  have graphify || { python3 -m pip install --user "$(pipspec graphifyy "$GRAPHIFY_VER")" >/dev/null 2>&1 && ok "graphify (pip, optional graph source)"; } || warn "graphify not installed — optional; the tree-sitter builder graph_build.py is the backbone"
  have codewiki || { python3 -m pip install --user "$(pipspec codewiki "$CODEWIKI_VER")" >/dev/null 2>&1 && ok "codewiki (pip)"; } || warn "codewiki not installed — as-is wiki degraded"
fi

# --- Optional shape-engine backend: tree-sitter (generic extractor generalization) -----
# the tree-sitter extraction backend uses it when present for more robust TS/GraphQL/arbitrary-stack
# extraction (a stack = a query, not a new parser). The runtime stays stdlib-only and degrades to
# the regex/ast parsers when it is absent — so this is genuinely optional.
#
# INSTALLING IT IS NO LONGER ENOUGH, and that is the whole reason for the prefetch below.
# tree-sitter-language-pack used to compile ~165 grammars INTO the wheel; import implied presence.
# It now ships a ~2 MB wheel and DOWNLOADS each grammar from GitHub releases **on first use**,
# cached under ~/.cache/tree-sitter-language-pack/. So a machine can import the library and still
# have zero usable grammars — on this repo's own dev box, 11 of 306 are present.
#
# That turns the network into a mid-run dependency: without a warm cache a rescue fetches while it
# analyses, and an offline/air-gapped/proxied box degrades per-grammar at the worst moment. Same
# problem, same answer as the uv cache warm-up above: pull them now, while failing is free.
# `available(lang)` in treesitter_extract.py probes per-grammar and falls back to the stdlib
# parsers, so every line here is best-effort and none of it can hard-fail.
if have pip3 || have pip; then
  python3 -c "import tree_sitter, tree_sitter_language_pack" >/dev/null 2>&1 \
    && ok "tree-sitter (present, optional shape-engine backend)" \
    || { python3 -m pip install --user \
           "$(pipspec tree-sitter "$TREE_SITTER_VER")" \
           "$(pipspec tree-sitter-language-pack "$TS_LANG_PACK_VER")" >/dev/null 2>&1 \
         && ok "tree-sitter (pip, optional shape-engine backend)"; } \
    || warn "tree-sitter not installed — shape engine uses the stdlib parsers (fine)"

  # Warm the grammar cache for the stacks shapes.py supports, so extraction never fetches mid-run.
  # The list is READ FROM THE RUNTIME, not restated here: treesitter_extract.STACKS is the one
  # declaration of which grammars exist, and a second copy in a shell script is a copy that drifts.
  # Pass the base dir in explicitly: __file__ inside `python3 -` is the literal "<stdin>", so it
  # cannot locate the runtime. `dirname "$0")/../..` is the repo root in dev (src/runtime lives there);
  # in the shipped skill the runtime is in a sibling plugin (keel-core/mcp/runtime) and is not
  # reachable relatively, so no candidate resolves and the block degrades to the `|| warn` below.
  _boot_base="$(cd "$(dirname "$0")/../.." && pwd)"
  python3 - "$_boot_base" <<'PY' 2>/dev/null || warn "grammar prefetch skipped — grammars fetch on first use (needs network then)"
import sys, pathlib
base = pathlib.Path(sys.argv[1])
for p in ("mcp/runtime", "src/runtime"):
    d = base / p
    if d.is_dir():
        sys.path.insert(0, str(d))
        break
import treesitter_extract as ts                      # noqa: E402
from tree_sitter_language_pack import prefetch, downloaded_languages  # noqa: E402
want = sorted({s["grammar"] for s in ts.STACKS.values()} | set(ts._CUSTOM))
# downloaded_languages() reports the name as REQUESTED and available_languages() the canonical one
# ("csharp" vs "c_sharp" for the same grammar), so a set-difference across the two silently
# re-fetches forever. prefetch() is already idempotent — let it do the diffing.
prefetch(want)
print(f"  prefetched {len(want)} grammars: {', '.join(want)}")
PY
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
