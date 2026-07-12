#!/usr/bin/env python3
"""Drift linter for the two sibling skills in this repo.

Verifies that each skill's modules.json, references/, and SKILL.md stay in sync, and that the
shared core/ (ledger, funnel, brainstorm, shape-engine) is referenced and not orphaned.

Path convention (see CLAUDE.md):
  - A pointer `references/x.md` resolves relative to the SKILL's own root.
  - A pointer `core/x.md`      resolves relative to the REPO root (shared by both skills).

Run in CI: `python scripts/check_consistency.py` (exit 1 on drift).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# skill name -> its root, relative to the repo root
SKILLS = {
    "codebase-rescue": "skills/codebase-rescue",
    "greenfield-forge": "skills/greenfield-forge",
}

errors, warnings = [], []

REF_RE = re.compile(r"`(references/[\w\-./]+\.md)`")   # skill-relative
CORE_RE = re.compile(r"`(core/[\w\-./]+\.md)`")        # repo-root-relative


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


# every .md / .json in the repo (excluding VCS + generated dirs) — used for orphan scans
all_files = [
    p for p in ROOT.rglob("*")
    if p.suffix in (".md", ".json")
    and ".git" not in p.parts
    and "node_modules" not in p.parts
]

module_count = 0
reference_dirs = []

# 1. Per-skill: modules.json references + SKILL.md pointers all resolve
for skill, rel in SKILLS.items():
    sroot = (ROOT / rel).resolve()
    mod_path, skill_path = sroot / "modules.json", sroot / "SKILL.md"

    if not mod_path.exists():
        errors.append(f"[{skill}] missing modules.json")
    else:
        try:
            mods = json.loads(read(mod_path))
        except json.JSONDecodeError as e:
            errors.append(f"[{skill}] modules.json is invalid JSON: {e}")
            mods = {"modules": []}
        for m in mods.get("modules", []):
            module_count += 1
            ref = m.get("reference")
            if not ref:
                errors.append(f"[{skill}] module '{m.get('id', '?')}' has no reference")
            elif not (sroot / ref).exists():
                errors.append(f"[{skill}] module '{m.get('id', '?')}' -> missing reference '{ref}'")

    if not skill_path.exists():
        errors.append(f"[{skill}] missing SKILL.md")
        continue
    text = read(skill_path)
    for ref in sorted(set(REF_RE.findall(text))):
        if not (sroot / ref).exists():
            errors.append(f"[{skill}] SKILL.md points to missing '{ref}'")
    for ref in sorted(set(CORE_RE.findall(text))):
        if not (ROOT / ref).exists():
            errors.append(f"[{skill}] SKILL.md points to missing shared '{ref}'")

    if (sroot / "references").is_dir():
        reference_dirs.append((skill, sroot))

# 2. Per-skill orphan check: every references/*.md is pointed at from this skill (warn only)
for skill, sroot in reference_dirs:
    referrers = read(sroot / "SKILL.md") + read(sroot / "modules.json")
    ref_files = list((sroot / "references").glob("*.md"))
    for f in ref_files:
        rel_ref = f"references/{f.name}"
        siblings = "".join(read(g) for g in ref_files if g != f)
        if rel_ref not in referrers + siblings:
            warnings.append(f"[{skill}] orphan reference (not linked anywhere): {rel_ref}")

# 3. Shared core orphan check: every core/*.md is referenced by some other file (warn only)
core_dir = ROOT / "core"
core_files = list(core_dir.glob("*.md")) if core_dir.is_dir() else []
for f in core_files:
    rel_ref = f"core/{f.name}"
    if not any(rel_ref in read(p) for p in all_files if p != f):
        warnings.append(f"orphan core file (not linked anywhere): {rel_ref}")

# 4. No leftover scaffolding stubs in skill content (SKILL.md, references/, core/).
#    Repo meta-docs (CLAUDE.md, README.md) may legitimately mention the marker.
content_md = list(core_files)
for _skill, _rel in SKILLS.items():
    _sroot = (ROOT / _rel).resolve()
    if (_sroot / "SKILL.md").exists():
        content_md.append(_sroot / "SKILL.md")
    if (_sroot / "references").is_dir():
        content_md += list((_sroot / "references").glob("*.md"))
for f in content_md:
    if "STUB — scaffold only" in read(f):
        errors.append(f"unfilled stub remains: {f.relative_to(ROOT)}")

# 5. Packaging manifests are valid JSON, and the agent roster matches across adapters
#    (Claude agents/*.md  ↔  opencode.json "agent" block).
opencode_agents = None
for m in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "opencode.json"):
    p = ROOT / m
    if not p.exists():
        warnings.append(f"packaging manifest missing: {m}")
        continue
    try:
        data = json.loads(read(p))
    except json.JSONDecodeError as e:
        errors.append(f"{m} is invalid JSON: {e}")
        continue
    if m == "opencode.json":
        opencode_agents = set((data.get("agent") or {}).keys())

roster = sorted(f.stem for f in (ROOT / "agents").glob("*.md")) if (ROOT / "agents").is_dir() else []
if opencode_agents is not None and roster and set(roster) != opencode_agents:
    errors.append(
        f"agent roster mismatch: Claude agents/={roster} vs opencode.json agent={sorted(opencode_agents)}"
    )

for w in warnings:
    print(f"WARN  {w}")
for e in errors:
    print(f"ERROR {e}")

ref_total = sum(len(list((s / 'references').glob('*.md'))) for _, s in reference_dirs)
print(
    f"\n{len(SKILLS)} skills, {module_count} modules, {len(core_files)} core files, "
    f"{ref_total} references, {len(roster)} agents — "
    f"{len(errors)} errors, {len(warnings)} warnings"
)
sys.exit(1 if errors else 0)
