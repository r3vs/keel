#!/usr/bin/env python3
"""Intra-playbook pointer verifier.

Complements check_consistency.py (which only validates SKILL.md pointers and module
references) by checking that EVERY backtick-wrapped `*.md` pointer inside the two skill
directories and core/ resolves. Catches cross-references between playbooks and into core/
that the drift-linter does not look at. Run in CI; exits 1 on any dangling pointer.

Resolution rule (see CLAUDE.md): a `references/x.md` pointer resolves relative to the
skill's own root; a `core/x.md` pointer (and any full `<skill>/references/x.md`) resolves
relative to the repo root.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIRS = {"codebase-rescue", "greenfield-forge"}
PTR = re.compile(r"`([\w\-./]+\.md)`")


def skill_root(f: Path) -> Path:
    parts = f.relative_to(ROOT).parts
    return ROOT / parts[0] if parts and parts[0] in SKILL_DIRS else ROOT


targets = []
for d in ("codebase-rescue", "greenfield-forge", "core"):
    if (ROOT / d).is_dir():
        targets += sorted((ROOT / d).rglob("*.md"))

bad = []
for f in targets:
    for ptr in sorted(set(PTR.findall(f.read_text(encoding="utf-8")))):
        bases = (ROOT, skill_root(f), f.parent)
        if not any((base / ptr).exists() for base in bases):
            bad.append(f"{f.relative_to(ROOT)}  ->  {ptr}")

for b in bad:
    print(f"DANGLING  {b}")
print(f"\n{len(targets)} skill/core files scanned — {len(bad)} dangling pointers")
sys.exit(1 if bad else 0)
