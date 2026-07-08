#!/usr/bin/env python3
"""Drift linter for the codebase-rescue skill.
Verifies that modules.json, references/, and SKILL.md stay in sync.
Run in CI: `python scripts/check_consistency.py` (exit 1 on drift).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors, warnings = [], []

# 1. modules.json valid + every module reference file exists
mods = json.loads((ROOT / "modules.json").read_text())
mod_refs = set()
for m in mods["modules"]:
    ref = m.get("reference")
    if not ref:
        errors.append(f"module '{m['id']}' has no reference")
        continue
    mod_refs.add(ref)
    if not (ROOT / ref).exists():
        errors.append(f"module '{m['id']}' -> missing reference file '{ref}'")

# 2. every reference pointer in SKILL.md exists
skill = (ROOT / "SKILL.md").read_text()
for ref in sorted(set(re.findall(r"`(references/[\w\-./]+\.md)`", skill))):
    if not (ROOT / ref).exists():
        errors.append(f"SKILL.md points to missing '{ref}'")

# 3. every references/*.md is referenced somewhere (module or SKILL) — warn only
referenced = mod_refs | set(re.findall(r"references/[\w\-./]+\.md", skill))
for f in (ROOT / "references").glob("*.md"):
    rel = f"references/{f.name}"
    if rel not in referenced:
        warnings.append(f"orphan reference (not linked anywhere): {rel}")

# 4. no leftover scaffolding stubs
for f in (ROOT / "references").glob("*.md"):
    if "STUB — scaffold only" in f.read_text():
        errors.append(f"unfilled stub remains: references/{f.name}")

for w in warnings: print(f"WARN  {w}")
for e in errors:   print(f"ERROR {e}")
print(f"\n{len(mods['modules'])} modules, "
      f"{len(list((ROOT/'references').glob('*.md')))} references — "
      f"{len(errors)} errors, {len(warnings)} warnings")
sys.exit(1 if errors else 0)
