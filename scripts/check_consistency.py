#!/usr/bin/env python3
"""Drift linter for the skills + shared core in this repo.

Verifies that each skill's modules.json, references/, and SKILL.md stay in sync, that the
shared core/ (the authoring source) is vendored into every skill that needs it, and that no
skill points at the source directly (Model B — each skill is self-contained; see CLAUDE.md).

It also asks the question none of that answers: is each shipped playbook **dispatched** — does
anything actually run it — or is it only mentioned? See section 2.

Path convention (see CLAUDE.md):
  - `references/x.md` (incl. the vendored `references/core/x.md`) resolves relative to the
    SKILL's own root.
  - src/core/*.md is the single source; scripts/build.py vendors it into each shipped skill.
    A bare `core/x.md` pointer under skills/ is drift (a copy was not vendored).

Run in CI: `python scripts/check_consistency.py` (exit 1 on drift); pair with build.py --check.
"""
import ast, json, re, sys
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
#
# The engine must also be COHERENT with the declared type, which the first version of this gate never
# checked: it verified that *an* engine was named, so `type: deterministic` + `engine: agent:*` passed
# — a model on the path wearing a deterministic label. Four greenfield modules shipped that way. An
# agent engine is D2 whatever the module says, and a fake-deterministic label is worse than an honest
# judgment one, because a wrong D0 finding gets believed where a wrong D2 finding gets argued with
# (core/trust-axes.md).
#
# The engine is REQUIRED of a deterministic module and OPTIONAL of a judgment one — but when a
# judgment module declares one, it is checked exactly as hard. The interview is the case that forced
# this: it elects by human judgment (D2, so `type: judgment` is right) and yet its output reaches
# disk through exactly one tool, `ledger_record_decision`, so naming that tool is the difference
# between a workflow and a description of one. The first version of this branch only looked at the
# engine when the type was `deterministic`, which meant a judgment module could name a tool the
# server does not expose and nothing would notice — an unvalidated claim, in the gate whose whole job
# is validating claims. `scripts/check_tool_carriers.py` runs the other direction: from the server's
# write tools back to the prose, failing when one is named by nothing that ships.
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
    """Tool names src/mcp/server.py advertises, parsed from its `@mcp.tool` decorations — the one
    source of truth, so a module's engine cannot name a tool the server does not expose (validate
    against the thing that serves, never a hand-kept second list).

    An AST walk, not a line scan. The line scan matched `def ` at column 0 and so was blind to every
    `async def` tool: `ledger_record_decision` — the only tool that can move a pin to `decided` — was
    invisible to this gate, which would have rejected the module that correctly named it. The same
    trap `tests/test_mcp_output_contracts.py` records at the top of its file: an async tool is still
    a tool, and a checker that cannot see one reports clean about a surface it never read.
    """
    tree = ast.parse(read(ROOT / "src" / "mcp" / "server.py"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
                for d in node.decorator_list)
    }


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
            else:
                engine = m.get("engine")
                if not engine:
                    if m.get("type") == "deterministic":
                        errors.append(
                            f"[{skill}] module '{m.get('id', '?')}' declares type=deterministic but "
                            "names no `engine` — say what produces its output: an `mcp:<tool>` MCP "
                            "tool, an `external:<tool>`, or an `agent:<how>`. A deterministic module "
                            "with no declared mechanism is prose wearing a label"
                        )
                elif (mm := MCP_ENGINE_RE.match(engine)):
                    if mm.group(1) not in MCP_TOOLS:
                        errors.append(
                            f"[{skill}] module '{m.get('id', '?')}' names engine '{engine}' but "
                            f"src/mcp/server.py advertises no `{mm.group(1)}` tool"
                        )
                elif engine.startswith("agent:"):
                    if m.get("type") == "deterministic":
                        errors.append(
                            f"[{skill}] module '{m.get('id', '?')}' declares type=deterministic but "
                            f"its engine '{engine}' reasons — an agent on the path is D2 however the "
                            "module is labeled. Declare it type=judgment; `agent:<how>` stays a "
                            "legitimate engine, just not a deterministic one (core/trust-axes.md)"
                        )
                elif not engine.startswith("external:"):
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

# 2. Per-skill DISPATCH check: every references/*.md is REACHED by this skill's flow — not merely
#    mentioned somewhere in it.
#
#    This replaced an orphan check that asked whether a reference was "linked anywhere": SKILL.md,
#    modules.json, or any sibling reference. That question is answered *yes* by a see-also, and a
#    see-also is not a step. `design-taste-lens.md` was named by a sibling playbook — in a paragraph
#    whose point was that the taste half is NOT that module — and by a row in SKILL.md's conditional
#    index, and nothing ever ran it. A capability with an author, an attribution and no dispatch,
#    green the whole time. That is this repo's signature failure (CLAUDE.md: *"twelve playbooks
#    invoke the runtime zero times"*) wearing a linter's approval.
#
#    The rule is structural, and it asks WHO points rather than reading HOW the pointer is phrased.
#    Telling a handoff from a cross-reference is a semantic read of prose, which this repo forbids
#    everywhere else and would forbid here; so the line is drawn at the pointing file's ROLE, which
#    is structure. Two dispatch idioms exist in this package and both count:
#
#      (A) **the catalog** — a `### Phase N` section, or a playbook that section names, reads
#          `modules.json`; that dispatches every module declaring `phase: N`. Rescue's Phase 1.
#      (B) **the flow** — SKILL.md names it outside the conditional index, or a playbook SKILL.md
#          names does. Greenfield throughout, and rescue's Phases 2-3.
#
#    Depth stops one hop past SKILL.md on purpose: SKILL.md is the index and a phase playbook is the
#    procedure, so what either names, it names as a step. A leaf naming a leaf is a cross-reference,
#    and counting it is exactly how the old check passed the bug above.
#
#    `## Read this when` is excluded by name, because the section says what it is in its own
#    preamble — *"Each row is a **condition**, not a topic"*. A lookup keyed by condition is how an
#    agent finds a playbook it already knows it needs; it dispatches nothing on its own.
CONDITIONAL_INDEX = re.compile(r"^## Read this when\s*$")
PHASE_HEADING = re.compile(r"^### Phase (\d+)")
SECTION_SPLIT = re.compile(r"^(#{2,3} .+)$", re.M)

#: references deliberately reached by no dispatch, each with the reason it is defensible. Empty,
#: and that is the intended steady state: the honest fix for an undispatched playbook is to give it
#: a module entry or a line in the phase that owns it — not a note explaining the silence.
UNDISPATCHED_OK: dict[str, str] = {}


def _sections(text: str) -> list:
    """[(heading, body)] split on `##` and `###` alike — a `### Phase N` gets its own entry."""
    parts = SECTION_SPLIT.split(text)
    out = [("", parts[0])]
    for i in range(1, len(parts), 2):
        out.append((parts[i], parts[i + 1] if i + 1 < len(parts) else ""))
    return out


for skill, sroot in reference_dirs:
    skill_text = read(sroot / "SKILL.md")
    flow, phase_sections = set(), {}
    for heading, body in _sections(skill_text):
        if CONDITIONAL_INDEX.match(heading):
            continue
        flow.update(REF_RE.findall(body))
        if (ph := PHASE_HEADING.match(heading)):
            phase_sections[int(ph.group(1))] = body

    # (A) which phases dispatch the catalog — the section itself, or a playbook it names, reads it
    catalog_phases = set()
    for phase, body in phase_sections.items():
        named = [read(sroot / r) for r in REF_RE.findall(body)]
        if any("modules.json" in t for t in [body] + named):
            catalog_phases.add(phase)

    # (B) one hop: what the flow's own playbooks name, they name as a step
    depth1 = set()
    for rel in sorted(flow):
        depth1.update(REF_RE.findall(read(sroot / rel)))

    dispatched = set(flow) | depth1
    try:
        for m in json.loads(read(sroot / "modules.json") or "{}").get("modules", []):
            if m.get("phase") in catalog_phases:
                dispatched.add(m.get("reference"))
    except json.JSONDecodeError:
        pass                       # already reported above; do not double-report

    for f in sorted((sroot / "references").glob("*.md")):
        rel_ref = f"references/{f.name}"
        if rel_ref in dispatched or rel_ref in UNDISPATCHED_OK:
            continue
        errors.append(
            f"[{skill}] undispatched playbook: {rel_ref} — nothing runs it. Give it a "
            f"`modules.json` entry in a phase whose playbook reads the catalog, or name it in the "
            f"phase that owns it. Being mentioned by a sibling reference, or by a row in "
            f"`## Read this when`, is a cross-reference and a lookup — neither is a step."
        )

for stale in sorted(set(UNDISPATCHED_OK) - {
        f"references/{f.name}" for _, s in reference_dirs for f in (s / "references").glob("*.md")}):
    warnings.append(f"stale UNDISPATCHED_OK entry (no such reference): {stale}")

# 3. Core source usage: each core/*.md is the authoring source and should be vendored into at
#    least one skill (scripts/build.py). A source no skill vendors is unused (warn only).
core_dir = ROOT / "src" / "core"
core_files = list(core_dir.glob("*.md")) if core_dir.is_dir() else []
# A core doc earns its place by being vendored into at least one SHIPPED skill. The copies live
# in plugins/ (build output) — the source tree holds none by design.
vendored_names = {g.name for g in (ROOT / "plugins").rglob("references/core/*.md")}     if (ROOT / "plugins").is_dir() else set()
# Exception: a few core docs are BUILD POLICY, not skill doctrine. build.py PARSES them to generate
# per-host config, and no skill vendors them because the agent receives the result (e.g. its model)
# from the generated adapter frontmatter, never by reading the doc at runtime. They sit in core/
# beside agents.md because they are the roster's policy — "unused by any skill" is correct for them,
# not drift.
BUILD_POLICY_CORE = {"model-tiers.md"}
for f in core_files:
    if f.name not in vendored_names and f.name not in BUILD_POLICY_CORE:
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

# ── frontmatter must PARSE, because of how it fails ────────────────────────────────────────────
# A YAML plain scalar cannot contain ": ". Write `description: Second mode: the premortem` and the
# whole block fails to parse — and the failure is silent and severe: the agent loads with EMPTY
# metadata, so `tools:` and `disallowedTools:` are dropped and a read-only role runs unrestricted.
# The permission table in core/agents.md would still *say* `edit: deny` while nothing enforced it.
#
# `claude plugin validate --strict` catches this, but only in CI on the generated output, which is
# both late and one repo away from the line somebody edited. This catches it at the source, on the
# authored file, before the build even runs. No YAML dependency: the rule being checked is exactly
# the one plain scalars have, so it is a parse of the same shape rather than a guess about it.
def _frontmatter_scalar_problems(path: Path) -> list:
    text = read(path)
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return [f"{path.relative_to(ROOT).as_posix()}: frontmatter opened with --- and never closed"]
    out = []
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s+(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value[:1] in "\"'" or value[:1] in "[{|>":     # quoted / flow / block scalars are fine
            continue
        if ": " in value or value.endswith(":"):
            out.append(
                f"{path.relative_to(ROOT).as_posix()}: `{key}` is an unquoted YAML scalar "
                f"containing ': ' — the frontmatter will NOT parse, and it fails silently: the "
                f"agent/skill loads with empty metadata, so any `tools:` allowlist is dropped and a "
                f"read-only role runs unrestricted. Rephrase without the colon, or quote the value."
            )
    return out


for _md in sorted((ROOT / "src" / "agents").glob("*.md")) + \
        sorted((ROOT / "src" / "skills").rglob("SKILL.md")) + \
        sorted((ROOT / "src" / "commands").glob("*.md")):
    errors.extend(_frontmatter_scalar_problems(_md))

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
