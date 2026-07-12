#!/usr/bin/env python3
"""Vendor the shared core/ doctrine into each skill so every skill is self-contained.

Model B (see CLAUDE.md "Shared core"): `core/*.md` is the single **authoring source**. Each
skill that needs a core doc carries its **own copy** under `skills/<skill>/references/core/`,
and every pointer inside a skill uses `references/core/x.md` (skill-root-relative) — no skill
points outside itself to `core/`. This makes each skill independently installable while the
edit point stays single (DRY): you edit `core/<x>.md`, then run this script and the copies
regenerate. `--check` verifies the tree already matches the source and exits 1 on any drift
(run in CI), which is what mechanically prevents the copies from diverging.

Usage:
  python scripts/sync_core.py           # materialize/refresh vendored copies + rewrite pointers
  python scripts/sync_core.py --check    # verify in sync (CI); exit 1 on drift or missing source
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
SKILLS_DIR = ROOT / "skills"
VENDOR = "references/core"  # where each skill keeps its private copies

# A skill "needs" a core doc if it points at either the bare source (`core/x.md`, pre-migration)
# or its vendored copy (`references/core/x.md`, post-migration). Capture the bare filename.
NEED_RE = re.compile(r"`(?:references/core|core)/([\w.-]+\.md)`")
# Rewrite ONLY bare `core/x.md` pointers -> `references/core/x.md`. Leaves `references/core/...`
# (idempotent) and `skills/...` cross-skill links untouched.
REWRITE_RE = re.compile(r"`core/([\w.-]+\.md)`")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def vendored_transform(text: str) -> str:
    """Deterministic transform applied to a core doc when copied into a skill: rewrite its own
    internal `core/y.md` pointers to `references/core/y.md` so they resolve within the skill."""
    return REWRITE_RE.sub(r"`references/core/\1`", text)


def core_deps(name: str) -> set:
    """core->core dependencies of one core doc (bare filenames)."""
    src = CORE / name
    return set(REWRITE_RE.findall(read(src))) if src.exists() else set()


def own_files(sroot: Path):
    """A skill's own authored files (NOT the vendored copies under references/core/)."""
    files = [p for p in (sroot / "SKILL.md", sroot / "TODO.md", sroot / "modules.json") if p.exists()]
    refs = sroot / "references"
    if refs.is_dir():
        files += sorted(refs.glob("*.md"))  # top-level only; references/core/* is vendored
    return files


def needed_core(sroot: Path) -> set:
    """Transitive closure of core docs a skill needs."""
    seen, stack = set(), []
    for f in own_files(sroot):
        stack += NEED_RE.findall(read(f))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack += [d for d in core_deps(n) if d not in seen]
    return seen


def plan(check: bool):
    changes, missing = [], []
    skills = (
        sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
        if SKILLS_DIR.is_dir()
        else []
    )
    for sroot in skills:
        need = needed_core(sroot)
        vendor_dir = sroot / VENDOR

        desired = {}
        for n in sorted(need):
            src = CORE / n
            if not src.exists():
                missing.append(f"{sroot.name}: needs core/{n} but the source does not exist")
                continue
            desired[n] = vendored_transform(read(src))

        # write/refresh needed copies
        for n, content in desired.items():
            dest = vendor_dir / n
            if not dest.exists() or read(dest) != content:
                changes.append(("WRITE", dest.relative_to(ROOT)))
                if not check:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content, encoding="utf-8")

        # drop stale copies no longer needed
        if vendor_dir.is_dir():
            for f in sorted(vendor_dir.glob("*.md")):
                if f.name not in desired:
                    changes.append(("REMOVE", f.relative_to(ROOT)))
                    if not check:
                        f.unlink()

        # rewrite the skill's own pointers: `core/x.md` -> `references/core/x.md`
        for f in own_files(sroot):
            t = read(f)
            nt = REWRITE_RE.sub(r"`references/core/\1`", t)
            if nt != t:
                changes.append(("REWRITE", f.relative_to(ROOT)))
                if not check:
                    f.write_text(nt, encoding="utf-8")

    return changes, missing


def main():
    check = "--check" in sys.argv
    changes, missing = plan(check)
    for kind, path in changes:
        print(f"{kind:8} {path}")
    for m in missing:
        print(f"MISSING  {m}")

    if check:
        if changes or missing:
            print(
                f"\nsync_core: {len(changes)} out-of-sync, {len(missing)} missing source(s) "
                f"— run: python scripts/sync_core.py"
            )
            sys.exit(1)
        vendored = sum(len(list((s / VENDOR).glob("*.md"))) for s in SKILLS_DIR.iterdir()
                       if (s / VENDOR).is_dir()) if SKILLS_DIR.is_dir() else 0
        print(f"\nsync_core: vendored core is in sync ({vendored} copies)")
        sys.exit(0)

    if missing:
        print(f"\nsync_core: {len(missing)} missing source(s) — cannot complete")
        sys.exit(1)
    print(f"\nsync_core: applied {len(changes)} change(s)")
    sys.exit(0)


if __name__ == "__main__":
    main()
