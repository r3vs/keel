#!/usr/bin/env bash
# Install the built package into a host that has no plugin format of its own.
#
# Claude Code and Codex do not need this — they install from the marketplace:
#   Claude Code:  /plugin marketplace add r3vs/codebase-rescue
#                 /plugin install codebase-rescue@codebase-alignment   (alignment-core comes with it)
#   Codex:        codex plugin marketplace add r3vs/codebase-rescue
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

cat <<MSG

Two things this cannot do for you, because neither host takes them as config:

  MCP     opencode: copy the mcpServers block from plugins/alignment-core/.mcp.json into your
          opencode.json (swap \${CLAUDE_PLUGIN_ROOT} for the real path).
          Pi: it has no native MCP — our extension is the bridge (see below).

  hooks   No portable format exists: opencode's are a plugin module, Pi's an extension.
          Copy plugins/alignment-core/adapters/{opencode/plugin,pi/extensions}/ into
          .opencode/plugin/ and ~/.pi/agent/extensions/. Both are thin — they delegate to the same
          ledger-gate.py every other host calls, so the rule exists once.
MSG
