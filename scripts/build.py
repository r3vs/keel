#!/usr/bin/env python3
"""Build the installable plugins from `src/`. The one and only generation step.

The rule, entire:

    src/        you write it, by hand. Nothing generated lives here.
    plugins/    build.py writes it. Nothing hand-written lives here.

That is the whole structure. It replaced three overlapping answers to "is this source or output?":
`skills/` used to be 51 authored files sitting beside 60 generated ones; `sync_core.py` and
`sync_runtime.py` vendored into that tree and committed the copies; then this script vendored them
*again* into `plugins/` and `dist/`. Three generations, two commits of the same bytes, 17 copies of
`ledger.py`, and an `skills/` tree nobody could read because half of it was output.

Both sync scripts are folded in here. They were a workaround for having no build step — once this
file existed, their copies in the source tree were vestigial. The vendoring itself stays: see below.

Why vendor at all (verified 2026-07-17, not assumed)
----------------------------------------------------
A skill must be **self-contained**, because neither opencode nor Pi resolves a skill's relative
paths against the skill directory — both resolve against **the user's project**. So a
`../../core/ledger.md` in a skill body does not read our file; it reads (or misses) something in
*their* repo. opencode v2 rejects it outright (`relative_escape`). And on a global install, a
sibling `~/.agents/core/` sits outside the project, so `external_directory` prompts the user on
every single read — vendoring inside the skill dir is what keeps that silent.

Why the duplication that remains is irreducible
------------------------------------------------
Claude Code gives plugins **no cross-plugin file access** (`${CLAUDE_PLUGIN_ROOT}` is per-plugin;
there is no marketplace-root variable; `../` is blocked). So each plugin carries what its skills
need. Combined with per-skill self-containment, `ledger.py` ends up in every skill that runs it —
which is a true fact about the design, not waste.

`plugins/` is generated **and committed** because a marketplace installs from the repo; `--check`
in CI is what stops it drifting from `src/`.

Usage:
  python scripts/build.py           # regenerate plugins/
  python scripts/build.py --check   # verify in sync (CI); exit 1 on drift
"""
import ast
import filecmp
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CORE, RUNTIME, TOOLS, SKILLS = SRC / "core", SRC / "runtime", SRC / "tools", SRC / "skills"
OUT = ROOT / "plugins"

VERSION = "0.1.0"
AUTHOR = {"name": "r3vs"}
HOMEPAGE = "https://github.com/r3vs/codebase-rescue"
KEYWORDS = ["skills", "codebase", "rescue", "greenfield", "architecture", "cross-layer-contract",
            "decisions-ledger", "refactoring", "tdd"]

# Repo-development artifacts that live beside authored skill content but are not product: a build
# checklist and an eval harness are ours, not the user's.
SKILL_EXCLUDE = {"TODO.md", "evals"}
# `writing-skills` documents contributing to THIS repo (its stated authority is CONTRIBUTING.md +
# CLAUDE.md). It is our contributor guide in a skill's clothes and must never ship.
DEV_ONLY_SKILLS = {"writing-skills"}

# --- vendoring rules (absorbed from the former sync_core.py / sync_runtime.py) ----------------
# A skill needs a core doc / runtime module / tool if its own authored prose names the vendored
# path. Anchored on the vendored form: a bare `core/x.md` or `runtime/x.py` is drift by definition
# (verify_commands.py errors on it) and must not silently satisfy a closure.
NEED_CORE = re.compile(r"`(?:references/core|core)/([\w.-]+\.md)`")
NEED_RUNTIME = re.compile(r"scripts/runtime/(\w+)\.py")
NEED_TOOL = re.compile(r"scripts/([\w-]+)\.sh")
# Rewrite a bare `core/x.md` -> `references/core/x.md` so it resolves inside the shipped skill.
REWRITE_CORE = re.compile(r"`core/([\w.-]+\.md)`")

CORE_BANNER = ("<!-- GENERATED FILE - do not edit. Source: src/core/{name} at the repo root; "
               "regenerate with: python scripts/build.py -->\n\n")
PY_BANNER = ("# GENERATED FILE - do not edit. Source: src/runtime/{name} at the repo root;\n"
             "# regenerate with: python scripts/build.py\n")

# --- the agent roster, generated per host -----------------------------------------------------
# The write verb lives in exactly ONE place: the roster table in src/core/agents.md. It used to
# live in three — that doc, `agents/*.md`, and a hand-written `agent` block in opencode.json — with
# a 45-line parity linter guarding them. A parity linter is a smell: it says two things should be
# one thing, generated. (And it was already losing: the opencode prompts had drifted in prose,
# which name-and-verb parity could never see.) So the verb is parsed from the roster and each
# host's permission mechanism is derived from it.
ROSTER_PERM = re.compile(r"^- ((?:`[\w-]+`(?:, )?)+)\s*→\s*\*\*edit: (deny|allow)\*\*", re.M)
ROLE_IN_LIST = re.compile(r"`([\w-]+)`")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)
# Claude Code has no `permission` field; the supported deny is `disallowedTools`. Denying the write
# TOOLS is the strongest static guarantee available — `Bash` stays reachable and is closed at
# runtime by the ledger gate instead.
DENY_TOOLS = "Write, Edit, NotebookEdit"

# The MCP servers the doctrine REQUIRES, parsed from its own table (src/core/knowledge-sources.md).
# `- `name` → **http** `url` — …`  is required; `→ **opt-in**` is named there and deliberately left
# undeclared. Same shape as the roster: the doc that states the rule is the source the build reads.
MCP_REQUIRED = re.compile(r"^- `([\w-]+)` → \*\*http\*\* `(\S+)`", re.M)

PLUGINS = {
    "alignment-core": {
        "description": (
            "The spine: the decisions-ledger MCP server (contract diff, blast radius, interview "
            "funnel, wave scheduler, findings gate), the researcher/brainstorm/executor/reviewer/"
            "challenger/measurer roster, the enforcement hooks, and the using-the-ledger skill. "
            "Installed automatically as a dependency of codebase-rescue and greenfield-forge."
        ),
        "skills": ["using-the-ledger"],
        "agents": True, "hooks": True, "mcp": True, "core_docs": True,
        "dependencies": [],
    },
    "codebase-rescue": {
        "description": (
            "Curative: rescue a large, misaligned, often AI-generated codebase — reconcile backend, "
            "frontend and database into an aligned state. Runs the diff backward: as-is exists, "
            "derive the to-be from an elected interview, close the gap."
        ),
        "skills": ["codebase-rescue"], "commands": ["rescue"],
        "dependencies": ["alignment-core"],
    },
    "greenfield-forge": {
        "description": (
            "Preventive: build a new project aligned from the first commit. Elects the design in a "
            "compressed interview before any code exists, then generates every layer from one "
            "contract so they cannot drift."
        ),
        "skills": ["greenfield-forge"], "commands": ["forge"],
        "dependencies": ["alignment-core"],
    },
    "alignment-helpers": {
        "description": (
            "Composable helpers, each useful on its own: grounded-research (cite current sources, "
            "never stale memory), static-first-analysis (strongest deterministic signal before "
            "judgment), project-memory (durable facts), and learning-layer (senior-grade output "
            "while the operator levels up)."
        ),
        "skills": ["grounded-research", "static-first-analysis", "project-memory", "learning-layer"],
        # It depends on the core, and the honest reason is the MCP servers, not the ledger:
        # `grounded-research` IS the Context7/DeepWiki doctrine as a skill, and core is where those
        # servers are declared. This used to say `dependencies: []` and "no runtime dependency" —
        # which read well and shipped a skill that orders the agent to use a server it never got.
        "dependencies": ["alignment-core"],
    },
}

changes: list[str] = []
problems: list[str] = []


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def note(kind: str, path: Path):
    changes.append(f"{kind:8} {path.relative_to(ROOT)}")


# --- closures ---------------------------------------------------------------------------------

def authored(skill: str) -> list[Path]:
    """A skill's hand-written files — the only thing that may seed a closure."""
    sdir = SKILLS / skill
    return [p for p in sorted(sdir.rglob("*"))
            if p.is_file() and not any(part in SKILL_EXCLUDE for part in p.relative_to(sdir).parts)]


def core_closure(skill: str) -> set:
    """Core docs a skill needs, transitively: a doc may point at another doc."""
    seen, stack = set(), []
    for f in authored(skill):
        stack += NEED_CORE.findall(read(f))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        src = CORE / n
        if not src.exists():
            problems.append(f"{skill}: needs core/{n}, which does not exist in src/core/")
            continue
        stack += [d for d in REWRITE_CORE.findall(read(src)) if d not in seen]
    return seen


def runtime_imports(name: str, universe: set) -> set:
    """Sibling modules `name` imports. Parsed with `ast`, not grepped: the runtime's internal
    imports are deliberately deferred inside functions (so a missing optional backend degrades
    instead of hard-failing at import), which a line scan would model badly."""
    src = RUNTIME / f"{name}.py"
    if not src.exists():
        return set()
    found = set()
    for node in ast.walk(ast.parse(read(src))):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found & universe - {name}


def runtime_closure(skill: str) -> set:
    """Runtime modules a skill needs, transitively. A worklist over a `seen` set, so the
    shapes <-> treesitter_extract cycle converges instead of recursing forever."""
    universe = {p.stem for p in RUNTIME.glob("*.py")}
    seeds = set()
    for f in authored(skill):
        seeds |= set(NEED_RUNTIME.findall(read(f)))
    # A vendored core doc can name a runtime module too — and then the skill really does need it,
    # or the doc it just received would dangle.
    for doc in core_closure(skill):
        if (CORE / doc).exists():
            seeds |= set(NEED_RUNTIME.findall(read(CORE / doc)))
    for missing in sorted(seeds - universe):
        problems.append(f"{skill}: needs scripts/runtime/{missing}.py, not in src/runtime/")

    seen, stack = set(), list(seeds & universe)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack += [d for d in runtime_imports(n, universe) if d not in seen]
    return seen


def tool_closure(skill: str) -> set:
    out = set()
    for f in authored(skill):
        out |= set(NEED_TOOL.findall(read(f)))
    for doc in core_closure(skill):
        if (CORE / doc).exists():
            out |= set(NEED_TOOL.findall(read(CORE / doc)))
    for t in sorted(out):
        if not (TOOLS / f"{t}.sh").exists():
            problems.append(f"{skill}: needs scripts/{t}.sh, not in src/tools/")
    return {t for t in out if (TOOLS / f"{t}.sh").exists()}


# --- payloads ---------------------------------------------------------------------------------

def skill_payload(skill: str) -> dict:
    """relpath (inside the plugin) -> text. Everything a self-contained shipped skill needs."""
    out = {}
    sdir = SKILLS / skill
    for f in authored(skill):
        rel = f.relative_to(sdir).as_posix()
        text = read(f) if f.suffix in (".md", ".json", ".yml", ".txt") else None
        # A skill's own pointers move from the authoring form to the vendored form.
        out[f"skills/{skill}/{rel}"] = REWRITE_CORE.sub(r"`references/core/\1`", text) if text else f
    for doc in sorted(core_closure(skill)):
        src = CORE / doc
        if src.exists():
            body = CORE_BANNER.format(name=doc) + REWRITE_CORE.sub(r"`references/core/\1`", read(src))
            out[f"skills/{skill}/references/core/{doc}"] = body
    for mod in sorted(runtime_closure(skill)):
        out[f"skills/{skill}/scripts/runtime/{mod}.py"] = PY_BANNER.format(name=f"{mod}.py") + read(RUNTIME / f"{mod}.py")
    for t in sorted(tool_closure(skill)):
        out[f"skills/{skill}/scripts/{t}.sh"] = read(TOOLS / f"{t}.sh")
    return out


def roster() -> dict:
    """role -> "deny" | "allow", from the one table that is the source of truth."""
    out = {}
    for roles_blob, verb in ROSTER_PERM.findall(read(CORE / "agents.md")):
        for role in ROLE_IN_LIST.findall(roles_blob):
            out[role] = verb
    if not out:
        problems.append("src/core/agents.md declares no `<role> → **edit: deny|allow**` permissions")
    return out


def agent_parts(role: str) -> tuple[dict, str]:
    """(frontmatter fields, body) of an authored role prompt."""
    m = FRONTMATTER.match(read(SRC / "agents" / f"{role}.md"))
    if not m:
        problems.append(f"src/agents/{role}.md has no frontmatter")
        return {}, ""
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields, m.group(2)


def claude_agent(role: str, verb: str) -> str:
    fields, body = agent_parts(role)
    lines = [f"name: {role}", f"description: {fields.get('description', '')}"]
    if fields.get("tools"):
        lines.append(f"tools: {fields['tools']}")
    if verb == "deny":
        lines.append(f"disallowedTools: {DENY_TOOLS}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def command_parts(cmd: str) -> tuple[dict, str]:
    m = FRONTMATTER.match(read(SRC / "commands" / f"{cmd}.md"))
    if not m:
        problems.append(f"src/commands/{cmd}.md has no frontmatter")
        return {}, ""
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields, m.group(2).strip() + "\n"


def opencode_agent(role: str, verb: str) -> str:
    """opencode's own shape: `permission: {edit: …}` (its `tools` field is deprecated in favour of
    permission), and the SAME body — so the two hosts can no longer say different things about the
    same role, which is precisely what had already happened."""
    fields, body = agent_parts(role)
    return (
        "---\n"
        f"description: {fields.get('description', '')}\n"
        "mode: subagent\n"
        "permission:\n"
        f"  edit: {verb}\n"
        "---\n" + body
    )


def plugin_payload(name: str, spec: dict) -> dict:
    out = {}
    for skill in spec["skills"]:
        out.update(skill_payload(skill))
    if spec.get("agents"):
        verbs = roster()
        authored = {p.stem for p in (SRC / "agents").glob("*.md")}
        for extra in sorted(authored - set(verbs)):
            problems.append(f"src/agents/{extra}.md has no permission in src/core/agents.md")
        for missing in sorted(set(verbs) - authored):
            problems.append(f"src/core/agents.md lists `{missing}` but src/agents/{missing}.md is absent")
        for role, verb in sorted(verbs.items()):
            if role not in authored:
                continue
            out[f"agents/{role}.md"] = claude_agent(role, verb)
            # opencode has no plugin format, so its adapter rides along inside the plugin (which
            # Claude Code simply ignores) and `scripts/install.sh` places it. One output tree.
            out[f"adapters/opencode/agent/{role}.md"] = opencode_agent(role, verb)
    if spec.get("core_docs"):
        # The agents resolve ${CLAUDE_PLUGIN_ROOT}/core/<doc>.md — a plugin-root copy, distinct from
        # the per-skill vendoring, because an agent is not inside any skill.
        for c in sorted(CORE.glob("*.md")):
            out[f"core/{c.name}"] = CORE_BANNER.format(name=c.name) + read(c)
    if spec.get("mcp"):
        for m in sorted((SRC / "mcp").glob("*.py")):
            out[f"mcp/{m.name}"] = read(m)
        for r in sorted(RUNTIME.glob("*.py")):
            out[f"mcp/runtime/{r.name}"] = read(r)
        out[".mcp.json"] = mcp_json()
    if spec.get("hooks"):
        for h in sorted((SRC / "hooks").iterdir()):
            if h.is_file():
                out[f"hooks/{h.name}"] = read(h)
        # opencode and Pi have no portable hook format — theirs is a TypeScript module, not config.
        # Each adapter delegates to the same ledger-gate.py the manifest hosts call, so the rule
        # exists once and the adapters carry no logic. Ship the gate beside each one.
        for host, sub in (("opencode", "plugin"), ("pi", "extensions")):
            for ts in sorted((SRC / "adapters" / host / sub).glob("*.ts")):
                out[f"adapters/{host}/{sub}/{ts.name}"] = read(ts)
            out[f"adapters/{host}/{sub}/ledger-gate.py"] = read(SRC / "hooks" / "ledger-gate.py")
    for cmd in spec.get("commands", []):
        fields, body = command_parts(cmd)
        out[f"commands/{cmd}.md"] = (
            f"---\ndescription: {fields.get('description', '')}\n---\n{body}\n$ARGUMENTS\n"
        )
        # opencode's command form: same body, its own frontmatter. The body names the skill and
        # never a path — both hosts resolve a skill by NAME, so there is nothing here to diverge.
        out[f"adapters/opencode/command/{cmd}.md"] = (
            f"---\ndescription: {fields.get('description', '')}\nagent: researcher\n---\n{body}"
        )

    out[".claude-plugin/plugin.json"] = manifest(name, spec)
    out[".codex-plugin/plugin.json"] = codex_manifest(name, spec)
    return out


def manifest(name: str, spec: dict) -> str:
    m = {"name": name, "description": spec["description"], "version": VERSION, "author": AUTHOR,
         "homepage": HOMEPAGE, "repository": HOMEPAGE, "license": "MIT", "keywords": KEYWORDS}
    if spec["dependencies"]:
        # Auto-installed and transitively enabled — what lets rescue/forge stay thin while the MCP
        # server exists exactly once.
        m["dependencies"] = spec["dependencies"]
    return json.dumps(m, indent=2) + "\n"


def codex_manifest(name: str, spec: dict) -> str:
    """Codex's manifest is near-identical to Claude Code's, so one generator emits both. Two real
    differences: the directory is `.codex-plugin/`, and Codex has **no `dependencies`** — a Codex
    user installs each plugin explicitly."""
    m = {"name": name, "version": VERSION, "description": spec["description"], "keywords": KEYWORDS}
    if spec["skills"]:
        m["skills"] = [f"skills/{s}" for s in spec["skills"]]
    if spec.get("mcp"):
        m["mcpServers"] = ".mcp.json"
    if spec.get("hooks"):
        m["hooks"] = "hooks/hooks.json"
    return json.dumps(m, indent=2) + "\n"


def mcp_json() -> str:
    """Every MCP server the package needs at runtime — ours, plus the ones its doctrine mandates.

    The required list is **parsed from the table in src/core/knowledge-sources.md**, the same way the
    write verb is parsed from the roster table: that doc orders the agent to ground claims via those
    servers, so it is the thing entitled to say which they are. Nothing here hardcodes them.

    Why it is parsed and not grepped: "GitHub" appears in that doc twice as ordinary English
    (DeepWiki indexes *public GitHub repos*; *GitHub Advisory* is a registry). A word-match would
    "find" a server nobody declared — a heuristic, and this package does not guess. Correspondence
    comes from a declared fact or not at all.

    The bug this closes: those servers used to be declared only in this repo's own root `.mcp.json`,
    which no user ever receives — so the product commanded a capability it never shipped.
    """
    servers = {
        "codebase-alignment": {
            "type": "stdio",
            "command": "uv",
            # The host expands this; a repo-relative path would resolve into the USER'S project.
            "args": ["run", "--script", "${CLAUDE_PLUGIN_ROOT}/mcp/server.py"],
        }
    }
    doc = read(CORE / "knowledge-sources.md")
    for name, url in MCP_REQUIRED.findall(doc):
        servers[name] = {"type": "http", "url": url}
    if len(servers) == 1:
        problems.append(
            "src/core/knowledge-sources.md declares no required MCP servers — the doctrine orders "
            "the agent to ground claims somewhere; if that changed, say so there, not here"
        )
    # opt-in servers are named in the same table and deliberately NOT declared: each needs external
    # setup (cognee a container + key, github a token), and a declared-but-unreachable server is a
    # broken entry in every user's session.
    return json.dumps({"mcpServers": servers}, indent=2) + "\n"


def marketplace() -> str:
    return json.dumps({
        "name": "codebase-alignment", "version": VERSION,
        "description": "Curative + preventive codebase-alignment plugins on a shared decisions-ledger core.",
        "owner": AUTHOR,
        "plugins": [{"name": n, "description": s["description"], "version": VERSION,
                     "source": f"./plugins/{n}", "category": "development", "author": AUTHOR}
                    for n, s in PLUGINS.items()]
        + [{"name": "superpowers",
            "description": ("Composed, not authored here: Jesse Vincent's generic engineering skills "
                            "(TDD, systematic debugging, planning, code review, git worktrees)."),
            "source": "github:obra/superpowers", "category": "development",
            "author": {"name": "Jesse Vincent"}}],
    }, indent=2) + "\n"


# --- write ------------------------------------------------------------------------------------

def emit(path: Path, content, check: bool):
    """content is text, or a Path to copy verbatim (binary-safe)."""
    if isinstance(content, Path):
        if path.exists() and filecmp.cmp(content, path, shallow=False):
            return
        note("COPY", path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(content, path)
        return
    data = content.encode("utf-8")   # bytes, so newlines stay LF on every OS
    if path.exists() and path.read_bytes() == data:
        return
    note("WRITE", path)
    if not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def build(check: bool):
    for skill in sorted(p.name for p in SKILLS.iterdir() if p.is_dir()):
        if skill in DEV_ONLY_SKILLS:
            continue
        if not any(skill in s["skills"] for s in PLUGINS.values()):
            problems.append(f"{skill}: authored but assigned to no plugin — it would never ship")

    produced = set()
    for name, spec in PLUGINS.items():
        for rel, content in plugin_payload(name, spec).items():
            path = OUT / name / rel
            produced.add(path)
            emit(path, content, check)

    mpath = ROOT / ".claude-plugin" / "marketplace.json"
    produced.add(mpath)
    emit(mpath, marketplace(), check)

    # Anything the build did not just produce is stale — a renamed skill would otherwise linger in
    # every user's install forever. Interpreter debris is neither source nor output: running the
    # built MCP server writes __pycache__ into the plugin, and treating that as drift would fail
    # --check for anyone who had simply tried the server.
    if OUT.exists():
        for p in sorted(OUT.rglob("*"), reverse=True):
            if "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            if p.is_file() and p not in produced:
                note("REMOVE", p)
                if not check:
                    p.unlink()
            elif p.is_dir() and not check and not any(p.iterdir()):
                p.rmdir()


def main():
    check = "--check" in sys.argv
    build(check)
    for c in changes:
        print(c)
    for p in problems:
        print(f"PROBLEM  {p}")

    n = sum(1 for p in OUT.rglob("*") if p.is_file()) if OUT.exists() else 0
    if check:
        if changes or problems:
            print(f"\nbuild: {len(changes)} out-of-sync, {len(problems)} problem(s) "
                  f"— run: python scripts/build.py")
            sys.exit(1)
        print(f"\nbuild: plugins/ in sync ({len(PLUGINS)} plugins, {n} files)")
        sys.exit(0)

    if problems:
        print(f"\nbuild: {len(problems)} problem(s) — cannot complete")
        sys.exit(1)
    print(f"\nbuild: {len(changes)} change(s) — {len(PLUGINS)} plugins, {n} files")
    sys.exit(0)


if __name__ == "__main__":
    main()
