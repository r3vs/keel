#!/usr/bin/env bash
# Install the built package into a host that has no plugin format of its own.
#
# Claude Code installs entirely from the marketplace and needs nothing here:
#   Claude Code:  /plugin marketplace add r3vs/codebase-rescue
#                 /plugin install codebase-rescue@codebase-alignment   (alignment-core comes with it)
#   Codex:        codex plugin marketplace add r3vs/codebase-rescue    (skills/MCP/hooks)
# Codex is a PARTIAL exception: its marketplace plugin delivers skills/MCP/hooks, but a Codex plugin
# manifest cannot declare agents (verified in openai/codex), so Profile B's per-role model files are
# placed here into ~/.codex/agents/ — run this too if you want per-role models on Codex.
#
# opencode and Pi have no plugin manifest, so their pieces are generated into
# plugins/alignment-core/adapters/ (a directory Claude Code simply ignores) and placed here. There
# is no separate staging tree: `plugins/` is the ONE output, and a second copy of the same bytes is
# exactly what this layout exists to stop.
#
# Every linked skill is already self-contained — the build vendored its doctrine and runtime inside
# it. Verified 2026-07-17, not assumed: neither opencode nor Pi resolves a skill's relative paths
# against the skill directory (both resolve against the USER'S project), so a skill reaching outside
# itself would read something in their repo, or nothing at all.
set -uo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
core="$root/plugins/alignment-core/adapters"

skills_dir="${1:-$HOME/.agents/skills}"     # opencode + Pi both auto-discover this
oc_dir="${OPENCODE_DIR:-$HOME/.config/opencode}"
pi_dir="${PI_DIR:-$HOME/.pi/agent}"
codex_dir="${CODEX_DIR:-$HOME/.codex}"

if [ ! -d "$root/plugins" ]; then
  echo "! plugins/ not built — run: python scripts/build.py" >&2
  exit 1
fi

place() { # src dest  -> symlink where possible (a rebuild then needs no reinstall), else copy
  local src="$1" dest="$2"
  [ -e "$dest" ] || [ -L "$dest" ] && rm -rf "$dest"
  mkdir -p "$(dirname "$dest")"
  if ln -s "$src" "$dest" 2>/dev/null; then echo link; else cp -R "$src" "$dest" && echo copy; fi
}

linked=0 copied=0
for skill in "$root"/plugins/*/skills/*/; do
  [ -d "$skill" ] || continue
  case "$(place "$skill" "$skills_dir/$(basename "$skill")")" in
    link) linked=$((linked + 1)) ;;
    copy) copied=$((copied + 1)) ;;
  esac
done
echo "✓ ${linked} skill(s) linked into $skills_dir"
[ "$copied" -gt 0 ] && echo "! ${copied} copied instead (symlinks unavailable) — re-run after each build"

# The roster and commands: generated from src/core/agents.md + src/commands, so opencode and Claude
# Code can no longer describe the same role differently — which had already happened when both were
# hand-written.
if [ -d "$core/opencode" ]; then
  n=0
  for f in "$core"/opencode/agent/*.md; do
    [ -f "$f" ] && place "$f" "$oc_dir/agent/$(basename "$f")" >/dev/null && n=$((n + 1))
  done
  for p in "$root"/plugins/*/adapters/opencode/command/*.md; do
    [ -f "$p" ] && place "$p" "$oc_dir/command/$(basename "$p")" >/dev/null && n=$((n + 1))
  done
  echo "✓ ${n} opencode agent(s)/command(s) placed in $oc_dir"
fi

# The opencode plugin: the ledger gate AND the MCP servers. Both are *installed*, not printed as
# homework — this used to end with a heredoc telling the user to hand-copy a JSON block out of our
# repo into their opencode.json, which is not an install, and is one copy away from drift.
#
# Linked file-by-file rather than as a directory, and that is load-bearing: both plugin files
# resolve a sibling out of the BUILT tree (`mcp.ts` → ../../../mcp/server.py, `ledger-gate.ts` →
# ./ledger-gate.py). Node resolves an ESM symlink to its realpath, so linking keeps those relations
# intact; a copy would sever them. `mcp.ts` degrades gracefully when that happens.
if [ -d "$core/opencode/plugin" ]; then
  n=0
  for f in "$core"/opencode/plugin/*; do
    [ -f "$f" ] && place "$f" "$oc_dir/plugin/$(basename "$f")" >/dev/null && n=$((n + 1))
  done
  echo "✓ ${n} opencode plugin file(s) placed in $oc_dir/plugin — ledger gate + MCP servers"
fi

# Pi: same two concerns, its own shape (an extension, not a plugin).
if [ -d "$core/pi/extensions" ]; then
  n=0
  for f in "$core"/pi/extensions/*; do
    [ -f "$f" ] && place "$f" "$pi_dir/extensions/$(basename "$f")" >/dev/null && n=$((n + 1))
  done
  echo "✓ ${n} Pi extension file(s) placed in $pi_dir/extensions"
fi

# Codex: its plugin manifest cannot declare agents, so Profile B's per-role model files (model +
# model_reasoning_effort + developer_instructions) are placed here into ~/.codex/agents/, which Codex
# auto-discovers. The marketplace plugin still delivers skills/MCP/hooks; this only adds per-role models.
if [ -d "$core/codex/agents" ]; then
  n=0
  for f in "$core"/codex/agents/*.toml; do
    [ -f "$f" ] && place "$f" "$codex_dir/agents/$(basename "$f")" >/dev/null && n=$((n + 1))
  done
  echo "✓ ${n} Codex per-role agent(s) placed in $codex_dir/agents (auto-discovered)"
fi

cat <<MSG

MCP is wired for you on every host that can take it — the servers come from the plugin, not from a
block you copy: Claude Code and Codex read the plugin's own .mcp.json, opencode gets them from the
config() hook in the plugin file just placed. Pi has no native MCP; its extension is the bridge.

Nothing needs to be copied out of this repo by hand. Keep the clone where it is: everything above
is symlinked INTO it, so moving or deleting it breaks the install. Re-run this only if you move it;
a plain rebuild needs no reinstall, which is why these are links.
MSG
