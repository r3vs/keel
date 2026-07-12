#!/usr/bin/env bash
# Make the codebase-alignment skills discoverable by opencode.
#
# opencode's `opencode-skills` plugin scans `.opencode/skills/`, but our single canonical copy
# lives under `skills/` (portable, Agent Skills spec). This links the two so there is no
# duplication and no drift. Idempotent; best-effort (falls back to a copy where symlinks are
# unavailable, e.g. Windows without developer mode).
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
link="$root/.opencode/skills"

mkdir -p "$root/.opencode"

if [ -e "$link" ] || [ -L "$link" ]; then
  echo "✓ .opencode/skills already present — nothing to do"
else
  if ln -s "../skills" "$link" 2>/dev/null; then
    echo "✓ symlinked .opencode/skills -> ../skills"
  else
    cp -R "$root/skills" "$link" && echo "! symlink unavailable; copied skills -> .opencode/skills (re-run after edits)"
  fi
fi

echo "✓ opencode.json already enables the plugin:  \"plugin\": [\"opencode-skills\"]"
echo "Done. Run opencode in this directory; the two skills load on demand via opencode-skills."
