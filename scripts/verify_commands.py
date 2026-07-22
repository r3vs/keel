#!/usr/bin/env python3
"""Executable-pointer verifier — the gate the .md pointer checkers never covered.

`verify_pointers.py` validates backticked `*.md` pointers; `check_consistency.py` validates
modules/references/roster. Both anchor on `__file__`, so both are immune to the working
directory — and both are blind to the one class of path that is NOT: the strings a shipped
file tells an **agent** to run or read.

The failure they miss
---------------------
A shipped skill is copied to an install location (Claude Code: ``~/.claude/plugins/cache/…``)
and the agent's working directory is **the user's target project**. So a bare repo-relative
string like ``python runtime/ledger.py`` resolves to ``<target-project>/runtime/ledger.py``:
not found. Worse than not-found — ``runtime/`` and ``scripts/`` are common directory names, so
a target project with its own ``runtime/ledger.py`` gets the **wrong script executed against
its data**, silently.

The rule this enforces
----------------------
In any shipped, agent-facing file, a path into this package must **exist inside the shipped unit**,
so a caller that knows the path can find it. It does NOT verify cwd-resolution, because **no host
resolves a skill-relative command against the skill directory deterministically**: opencode and Pi
resolve relative paths against the *user's* project, and Claude Code's cwd is the user's project too.
That is exactly why the MCP server is the preferred channel — its location is host-resolved, so the
whole path class disappears — and the bundled CLI is the floor. So this gate validates **presence in
the package**, in two forms:

* under ``skills/`` -> the path is **skill-root-relative** and exists under that skill: the bytes are
  vendored into the unit that ships, and the agent reaches them either through the MCP tool or by
  resolving the path against the skill base directory the host injects (never against its own cwd);
* in a **plugin-root adapter** (``agents/``, ``commands/``, ``hooks/``) -> the path is
  ``${CLAUDE_PLUGIN_ROOT}``-anchored, because the adapter ships into a cache dir whose location is
  only knowable at runtime.

Anything else is drift, and it is invisible until a user installs the package.

Severity
--------
* **ERROR** — an *instruction*: a command the agent will run (``python x.py``, ``bash x.sh``),
  or a document a plugin-root adapter tells it to read. These actively break or misfire.
* **WARN** — a *description*: prose naming a repo path ("implemented in ``runtime/shapes.py``").
  Harmless to execution, but it is a dangling reference from an installed skill's point of
  view, so it is surfaced rather than silently accepted.

Run in CI: `python scripts/verify_commands.py` (exit 1 on any ERROR).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Top-level directories that exist in THIS repo and will not exist in a user's project.
# A shipped file naming one of these without a plugin-root anchor cannot resolve after install.
REPO_DIRS = ("runtime", "scripts", "src", "tests", "core", "assets")

# Trees whose files ship to users and are read by an agent. `src/core` is the authoring source
# for the vendored copies, so a bad command there would propagate into every skill — catching it
# at the source gives a better error than catching it N times in the generated copies.
SHIPPED_TREES = ("src", ".opencode")

# Claude-Code plugin-root adapters: never standalone, but they DO ship — into a cache dir — so
# their paths must be ${CLAUDE_PLUGIN_ROOT}-anchored, not repo-relative.
#
# `.opencode/` is deliberately NOT here: ${CLAUDE_PLUGIN_ROOT} is a Claude Code variable and
# expands to nothing elsewhere. An opencode command names the skill and lets the native `skill`
# tool resolve it — so a path there is a mistake no anchor can fix.
ADAPTER_TREES = ("src/agents", "src/commands", "src/hooks")

# Repo-development artifacts. These are excluded from the build (see scripts/build.py) for the same
# reason they are excluded here: a build checklist, an eval harness, and the contributor guide are
# ours, not the user's, so they are never subject to the install-time resolution rule.
DEV_ARTIFACTS = ("TODO.md",)
DEV_TREES = ("evals", "writing-skills")

PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"

# An HTML comment is metadata for whoever opens the file, not an instruction to the agent
# (Claude Code strips block-level comments from CLAUDE.md before they reach context). Scanning
# them would flag the generated-file banners, which address a developer in the source repo.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# An instruction to RUN something: `python x.py`, `python3 x.py`, `bash x.sh`, `sh x.sh`, `./x.sh`.
CMD_RE = re.compile(
    r"(?:python3?|bash|sh)\s+[\"']?([$\w{}\-./]+\.(?:py|sh))"
    r"|(?<![\w./])\./([\w\-./]+\.sh)"
)
# An instruction to READ something, in an adapter: a backticked repo-root path.
ADAPTER_PTR_RE = re.compile(r"`((?:" + "|".join(REPO_DIRS) + r"|skills)/[\w\-./]+\.\w+)`")
# A descriptive mention: a backticked repo path anywhere in shipped prose.
MENTION_RE = re.compile(r"`((?:" + "|".join(REPO_DIRS) + r")/[\w\-./]+\.(?:py|sh|json|toml))`")

errors: list[str] = []
warnings: list[str] = []


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def skill_root(f: Path) -> Path | None:
    """The skill directory a file belongs to, or None if it is not under src/skills/."""
    parts = f.relative_to(ROOT).parts
    if len(parts) >= 3 and parts[:2] == ("src", "skills"):
        return ROOT / "src" / "skills" / parts[2]
    return None


def tree_of(f: Path) -> str:
    return "/".join(f.relative_to(ROOT).parts[:2])


def is_dev(f: Path) -> bool:
    parts = f.relative_to(ROOT).parts
    return f.name in DEV_ARTIFACTS or any(p in DEV_TREES for p in parts)


def resolves(path: str, f: Path) -> bool:
    """Does `path`, as written in `f`, resolve once this package is installed?"""
    if path.startswith(PLUGIN_ROOT):
        return True  # the host expands it to the plugin's real location
    if path.startswith(("http://", "https://")):
        return True
    # Skill-bundled assets are VENDORED BY THE BUILD, so they do not exist in the source tree —
    # the check is against what build.py will put there, i.e. the authoring source. Verified 2026-07-17
    # on opencode + Pi source: both resolve a skill's relative paths against the USER'S project, not
    # the skill dir, so the model must be handed a path that is inside the skill. `../` is not an
    # option: it reads (or misses) something in their repo.
    if skill_root(f) is not None or f.is_relative_to(ROOT / "src" / "core"):
        if path.startswith("scripts/runtime/"):
            return (ROOT / "src" / "runtime" / Path(path).name).exists()
        if path.startswith("scripts/") and path.endswith(".sh"):
            return (ROOT / "src" / "tools" / Path(path).name).exists()
        sroot = skill_root(f)
        return bool(sroot and (sroot / path).exists())
    return False


def scan(f: Path) -> None:
    text = HTML_COMMENT_RE.sub("", read(f))
    rel = f.relative_to(ROOT)
    tree = tree_of(f)

    # 1. Commands the agent will execute.
    for m in CMD_RE.finditer(text):
        path = m.group(1) or m.group(2)
        if path.startswith(REPO_DIRS) or path.startswith("skills/"):
            if not resolves(path, f):
                errors.append(f"[{rel}] runnable path does not resolve after install: `{path}`")

    # 2. Documents a plugin-root adapter tells the agent to read.
    if tree in ADAPTER_TREES:
        for hit in sorted(set(ADAPTER_PTR_RE.findall(text))):
            errors.append(
                f"[{rel}] adapter points at a repo path with no plugin-root anchor: `{hit}` "
                f"— use {PLUGIN_ROOT}/{hit}"
            )

    # 3. Descriptive mentions of a repo path in shipped prose (dangling once installed).
    for hit in sorted(set(MENTION_RE.findall(text))):
        if not resolves(hit, f):
            warnings.append(f"[{rel}] shipped prose names a repo path: `{hit}`")


targets: list[Path] = []
for tree in SHIPPED_TREES:
    d = ROOT / tree
    if not d.is_dir():
        continue
    targets += [p for p in sorted(d.rglob("*")) if p.suffix in (".md", ".sh", ".json")]

targets = [f for f in targets if not is_dev(f)]
for f in targets:
    scan(f)

for w in warnings:
    print(f"WARN  {w}")
for e in errors:
    print(f"ERROR {e}")

print(
    f"\n{len(targets)} shipped files scanned — {len(errors)} errors, {len(warnings)} warnings"
)
sys.exit(1 if errors else 0)
