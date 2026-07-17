#!/usr/bin/env python3
"""Intra-playbook pointer verifier.

Complements check_consistency.py (which only validates SKILL.md pointers and module
references) by checking that EVERY backtick-wrapped `*.md` pointer inside the two skill
directories and core/ resolves. Catches cross-references between playbooks and into core/
that the drift-linter does not look at. Run in CI; exits 1 on any dangling pointer.

Resolution rule (see CLAUDE.md): a `references/x.md` pointer resolves relative to the
skill's own root; a `core/x.md` pointer (and any full `<skill>/references/x.md`) resolves
relative to the repo root.

Note this checks *documents*, not *commands* — an agent-facing `python x.py` string is a
different class with a different resolution rule, and is the job of verify_commands.py.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_CORE = ROOT / "src" / "core"      # the authoring source for the shared doctrine
SKILLS = ROOT / "src" / "skills"      # authored skill prose (the vendored copies live in plugins/)
PTR = re.compile(r"`([\w\-./]+\.md)`")


def skill_root(f: Path) -> Path:
    parts = f.relative_to(ROOT).parts
    if len(parts) >= 3 and parts[:2] == ("src", "skills"):
        return SKILLS / parts[2]
    return ROOT


targets = []
if (SKILLS).is_dir():
    targets += sorted(SKILLS.rglob("*.md"))
if (SRC_CORE).is_dir():
    targets += sorted(SRC_CORE.glob("*.md"))

def resolves(ptr: str, f: Path) -> bool:
    # `references/core/x.md` is the SHIPPED form and deliberately does not exist in the source:
    # build.py vendors src/core/x.md to that path inside each plugin. So it is checked against the
    # authoring source by rule. (This is the trade for having one generation instead of two —
    # the source tree carries a pointer that only resolves after the build, and this rule is what
    # keeps that honest rather than unchecked.)
    if ptr.startswith("references/core/"):
        return (SRC_CORE / Path(ptr).name).exists()
    # `ROOT / "src"` resolves the intra-core `core/x.md` links inside the authoring source. That
    # bare form is also deliberate: it is what a plugin-root adapter uses (<plugin>/core/x.md), and
    # build.py rewrites it to the vendored form on the way into a skill.
    return any((base / ptr).exists() for base in (ROOT, ROOT / "src", skill_root(f), f.parent))


bad = []
for f in targets:
    for ptr in sorted(set(PTR.findall(f.read_text(encoding="utf-8")))):
        if not resolves(ptr, f):
            bad.append(f"{f.relative_to(ROOT)}  ->  {ptr}")

for b in bad:
    print(f"DANGLING  {b}")
print(f"\n{len(targets)} skill/core files scanned — {len(bad)} dangling pointers")
sys.exit(1 if bad else 0)
