#!/usr/bin/env python3
"""Drift linter for the skills + shared core in this repo.

Verifies that each skill's modules.json, references/, and SKILL.md stay in sync, that the
shared core/ (the authoring source) is vendored into every skill that needs it, and that no
skill points at the source directly (Model B — each skill is self-contained; see CLAUDE.md).

Path convention (see CLAUDE.md):
  - `references/x.md` (incl. the vendored `references/core/x.md`) resolves relative to the
    SKILL's own root.
  - src/core/*.md is the single source; scripts/build.py vendors it into each shipped skill.
    A bare `core/x.md` pointer under skills/ is drift (a copy was not vendored).

Run in CI: `python scripts/check_consistency.py` (exit 1 on drift); pair with build.py --check.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# skill name -> its root, relative to the repo root
# Auto-discover every skill: a dir under skills/ that has a SKILL.md.
SKILLS = {
    p.name: f"src/skills/{p.name}"
    for p in sorted((ROOT / "src" / "skills").iterdir())
    if p.is_dir() and (p / "SKILL.md").exists()
} if (ROOT / "src" / "skills").is_dir() else {}

errors, warnings = [], []

REF_RE = re.compile(r"`(references/[\w\-./]+\.md)`")   # skill-relative
CORE_RE = re.compile(r"`(core/[\w\-./]+\.md)`")        # repo-root-relative

# A `deterministic` module must declare an `engine` — what actually produces its output. Three
# honest forms: an `mcp:<tool>` MCP tool (the CLI is gone — the runtime is reached only through the
# MCP server, so the engine names the tool, validated below against src/mcp/server.py's own
# `@mcp.tool` decorations), an `external:<tool>` (a third-party tool emits it, e.g. codewiki), or an
# `agent:<how>` (the greenfield "generate/scaffold from a decided source" sense — produced by the
# agent, not a runtime). This replaced a prose-grep of the reference file, which let modules sharing a
# playbook free-ride on one runnable mention — and grepping prose for correspondence is the very
# heuristic this repo forbids. The check is per-module and deterministic: the engine is declared, and
# an `mcp:` tool is checked to actually exist on the server (the carrier, never a second list).
MCP_ENGINE_RE = re.compile(r"^mcp:(\w+)$")


SRC_CORE = ROOT / "src" / "core"


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def ref_resolves(ref: str, sroot: Path) -> bool:
    """A skill-relative `references/x.md` pointer.

    `references/core/x.md` is the SHIPPED form and deliberately absent from the source tree:
    build.py vendors `src/core/x.md` to that path inside each plugin. Checking it against the
    authoring source by rule is the trade for having ONE generation instead of two — the source
    carries a pointer that only resolves post-build, and this rule is what keeps that honest.
    """
    if ref.startswith("references/core/"):
        return (SRC_CORE / Path(ref).name).exists()
    return (sroot / ref).exists()


# every .md / .json in the repo (excluding VCS + generated dirs) — used for orphan scans
all_files = [
    p for p in ROOT.rglob("*")
    if p.suffix in (".md", ".json")
    and ".git" not in p.parts
    and "node_modules" not in p.parts
]

module_count = 0
reference_dirs = []

def mcp_tools() -> set:
    """Tool names src/mcp/server.py advertises, parsed structurally from its `@mcp.tool`
    decorations — the one source of truth, so a module's engine cannot name a tool the server does
    not expose (validate against the thing that serves, never a hand-kept second list)."""
    lines = read(ROOT / "src" / "mcp" / "server.py").splitlines()
    out = set()
    for i, line in enumerate(lines):
        if line.startswith("def ") and i:
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and lines[j].lstrip().startswith("@mcp.tool"):
                out.add(line[4:].split("(", 1)[0].strip())
    return out


MCP_TOOLS = mcp_tools()


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
            elif not ref_resolves(ref, sroot):
                errors.append(f"[{skill}] module '{m.get('id', '?')}' -> missing reference '{ref}'")
            elif m.get("type") == "deterministic":
                engine = m.get("engine")
                if not engine:
                    errors.append(
                        f"[{skill}] module '{m.get('id', '?')}' declares type=deterministic but "
                        "names no `engine` — say what produces its output: an `mcp:<tool>` MCP tool, "
                        "an `external:<tool>`, or an `agent:<how>`. A deterministic module with no "
                        "declared mechanism is prose wearing a label"
                    )
                elif (mm := MCP_ENGINE_RE.match(engine)):
                    if mm.group(1) not in MCP_TOOLS:
                        errors.append(
                            f"[{skill}] module '{m.get('id', '?')}' names engine '{engine}' but "
                            f"src/mcp/server.py advertises no `{mm.group(1)}` tool"
                        )
                elif not (engine.startswith("external:") or engine.startswith("agent:")):
                    errors.append(
                        f"[{skill}] module '{m.get('id', '?')}' engine '{engine}' is not a "
                        "recognized form (mcp:<tool> | external:<tool> | agent:<how>)"
                    )

    if not skill_path.exists():
        errors.append(f"[{skill}] missing SKILL.md")
        continue
    text = read(skill_path)
    for ref in sorted(set(REF_RE.findall(text))):
        if not ref_resolves(ref, sroot):
            errors.append(f"[{skill}] SKILL.md points to missing '{ref}'")

    if (sroot / "references").is_dir():
        reference_dirs.append((skill, sroot))

# 1b. Model-B invariant: no skill file may point at the shared source directly — it must vendor
#     a copy (references/core/x.md) via scripts/build.py. A bare `core/x.md` under skills/ is
#     drift. CORE_RE requires the backtick immediately before "core/", so it never matches the
#     vendored `references/core/x.md` form.
if (ROOT / "src" / "skills").is_dir():
    for p in sorted((ROOT / "src" / "skills").rglob("*.md")):
        for hit in sorted(set(CORE_RE.findall(read(p)))):
            errors.append(
                f"[{p.relative_to(ROOT)}] un-vendored core pointer `{hit}` — run scripts/build.py"
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
#    least one skill (scripts/build.py). A source no skill vendors is unused (warn only).
core_dir = ROOT / "src" / "core"
core_files = list(core_dir.glob("*.md")) if core_dir.is_dir() else []
# A core doc earns its place by being vendored into at least one SHIPPED skill. The copies live
# in plugins/ (build output) — the source tree holds none by design.
vendored_names = {g.name for g in (ROOT / "plugins").rglob("references/core/*.md")}     if (ROOT / "plugins").is_dir() else set()
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

# 5. Packaging manifests are valid JSON.
#    NOTE what is deliberately NOT here any more: roster name-parity and permission-parity across
#    adapters. Those were ~45 lines guarding two hand-written copies of the same six roles — and
#    they were losing: the copies had already drifted in PROSE, which name-and-verb parity cannot
#    see. A parity linter is a smell; it says two things should be one thing, generated. So the
#    write verb now lives once (the roster table in src/core/agents.md), build.py derives each
#    host's mechanism from it (`disallowedTools` for Claude, `permission.edit` for opencode), and
#    build.py --check is the guarantee. The residual it cannot close is narrower than it once read:
#    a plugin cannot ship a selective, agent-scoped `Bash` rule — the ledger gate closes that at runtime.
#
#    NOTE what else is deliberately gone: the root `opencode.json` / `.mcp.json` / `.codex/config.toml`.
#    They were host config for THIS repo, and a user installing a plugin never works in this repo —
#    they work in their own. Yet the docs told them to "open the repo" and copy servers out of those
#    files, so three hand-written copies of one fact existed and had already drifted (deepwiki missing
#    from Codex; cognee `enabled: true` in two, which the doctrine forbids because it cannot connect).
#    Delivery is now the install on every host that can take it, generated from the doctrine's table:
#    `.mcp.json` in the plugin (Claude reads it at the plugin root, Codex's manifest points at it) and
#    a `config()` hook in the opencode plugin. `tests/test_mcp_declaration.py` keeps the root clean.
for m in (".claude-plugin/marketplace.json",):
    p = ROOT / m
    if not p.exists():
        warnings.append(f"packaging manifest missing: {m}")
        continue
    try:
        json.loads(read(p))
    except json.JSONDecodeError as e:
        errors.append(f"{m} is invalid JSON: {e}")

roster = sorted(f.stem for f in (ROOT / "src" / "agents").glob("*.md")) if (ROOT / "src" / "agents").is_dir() else []
claude_cmds = sorted(f.stem for f in (ROOT / "src" / "commands").glob("*.md")) if (ROOT / "src" / "commands").is_dir() else []

for w in warnings:
    print(f"WARN  {w}")
for e in errors:
    print(f"ERROR {e}")

ref_total = sum(len(list((s / 'references').glob('*.md'))) for _, s in reference_dirs)
vendored_total = sum(
    len(list((s / 'references' / 'core').glob('*.md')))
    for s in (ROOT / 'src' / 'skills').iterdir() if (s / 'references' / 'core').is_dir()
) if (ROOT / 'src' / 'skills').is_dir() else 0
print(
    f"\n{len(SKILLS)} skills, {module_count} modules, {len(core_files)} core sources "
    f"({vendored_total} vendored copies), {ref_total} references, {len(roster)} agents, "
    f"{len(claude_cmds)} commands — {len(errors)} errors, {len(warnings)} warnings"
)
sys.exit(1 if errors else 0)
