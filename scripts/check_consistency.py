#!/usr/bin/env python3
"""Drift linter for the skills + shared core in this repo.

Verifies that each skill's modules.json, references/, and SKILL.md stay in sync, that the
shared core/ (the authoring source) is vendored into every skill that needs it, and that no
skill points at the source directly (Model B — each skill is self-contained; see CLAUDE.md).

Path convention (see CLAUDE.md):
  - `references/x.md` (incl. the vendored `references/core/x.md`) resolves relative to the
    SKILL's own root.
  - core/*.md is the single source; scripts/sync_core.py copies it into skills/*/references/core/.
    A bare `core/x.md` pointer under skills/ is drift (a copy was not vendored).

Run in CI: `python scripts/check_consistency.py` (exit 1 on drift); pair with sync_core.py --check.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# skill name -> its root, relative to the repo root
# Auto-discover every skill: a dir under skills/ that has a SKILL.md.
SKILLS = {
    p.name: f"skills/{p.name}"
    for p in sorted((ROOT / "skills").iterdir())
    if p.is_dir() and (p / "SKILL.md").exists()
} if (ROOT / "skills").is_dir() else {}

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

    if mod_path.exists():  # modules.json is optional — only the two methodology skills have one
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

    if (sroot / "references").is_dir():
        reference_dirs.append((skill, sroot))

# 1b. Model-B invariant: no skill file may point at the shared source directly — it must vendor
#     a copy (references/core/x.md) via scripts/sync_core.py. A bare `core/x.md` under skills/ is
#     drift. CORE_RE requires the backtick immediately before "core/", so it never matches the
#     vendored `references/core/x.md` form.
if (ROOT / "skills").is_dir():
    for p in sorted((ROOT / "skills").rglob("*.md")):
        for hit in sorted(set(CORE_RE.findall(read(p)))):
            errors.append(
                f"[{p.relative_to(ROOT)}] un-vendored core pointer `{hit}` — run scripts/sync_core.py"
            )

# 2. Per-skill orphan check: every references/*.md is pointed at from this skill (warn only)
for skill, sroot in reference_dirs:
    referrers = read(sroot / "SKILL.md") + read(sroot / "modules.json")
    ref_files = list((sroot / "references").glob("*.md"))
    for f in ref_files:
        rel_ref = f"references/{f.name}"
        siblings = "".join(read(g) for g in ref_files if g != f)
        if rel_ref not in referrers + siblings:
            warnings.append(f"[{skill}] orphan reference (not linked anywhere): {rel_ref}")

# 3. Core source usage: each core/*.md is the authoring source and should be vendored into at
#    least one skill (scripts/sync_core.py). A source no skill vendors is unused (warn only).
core_dir = ROOT / "core"
core_files = list(core_dir.glob("*.md")) if core_dir.is_dir() else []
vendored_names = set()
if (ROOT / "skills").is_dir():
    for s in sorted((ROOT / "skills").iterdir()):
        vd = s / "references" / "core"
        if vd.is_dir():
            vendored_names |= {g.name for g in vd.glob("*.md")}
for f in core_files:
    if f.name not in vendored_names:
        warnings.append(f"unused core source (never vendored into any skill): core/{f.name}")

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
for m in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "opencode.json", ".mcp.json"):
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
vendored_total = sum(
    len(list((s / 'references' / 'core').glob('*.md')))
    for s in (ROOT / 'skills').iterdir() if (s / 'references' / 'core').is_dir()
) if (ROOT / 'skills').is_dir() else 0
print(
    f"\n{len(SKILLS)} skills, {module_count} modules, {len(core_files)} core sources "
    f"({vendored_total} vendored copies), {ref_total} references, {len(roster)} agents — "
    f"{len(errors)} errors, {len(warnings)} warnings"
)
sys.exit(1 if errors else 0)
