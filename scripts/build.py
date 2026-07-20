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

Why vendor at all — distribution atomicity, and nothing else
------------------------------------------------------------
The Agent Skills spec's unit of distribution is the standalone skill folder, and `scripts/install.sh`
symlinks **each skill dir individually** into `~/.agents/skills/`. A sibling `~/.agents/core/` is not
part of what travels. Vendoring buys guaranteed presence of the bytes **inside the unit that ships**.
That is the whole argument.

What used to stand here — and is refuted, so nobody rebuilds it (re-audited 2026-07-17 at the
consuming functions, `anomalyco/opencode` + `earendil-works/pi`): `relative_escape` is opencode-**v2
only** and fires only for *relative* paths, an absolute path outside being promoted to
`external_directory` rather than rejected; `external_directory` prompts **once per subtree per
project**, persists on "always", is pre-approvable by one config rule — and fires **identically for
vendored files**, because our own default install target `~/.agents/skills` is itself outside the
user's project, so vendoring takes the external-subtree count 2 → 1, never 1 → 0; and **Pi has no
read confinement at all**, though the old sentence named both hosts.

The counterfactual that inverts the old reasoning: **both hosts inject the skill's absolute base
directory and instruct the model to resolve against it** (opencode `core/src/tool/skill.ts`: "Base
directory for this skill: …"; Pi `harness/skills.js`: "References are relative to …"). Under that
contract a `../` composes to an absolute path and behaves exactly like a vendored one. The old
mechanism only bites when the model ignores the host's instruction — and there vendoring fails
*worse*: `references/core/x.md` is lexically internal, so it does not error, it silently reads the
user's own file at that path.

Worth naming under this repo's no-heuristics rule: no host resolves skill-relative reads
deterministically. Both delegate it to the model via injected prose.

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
TS_BANNER = ("/**\n * GENERATED FILE - do not edit. Source: the MCP table in "
             "src/core/knowledge-sources.md;\n * regenerate with: python scripts/build.py\n *")

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
            "Composable helpers, each useful on its own and each bound to the decisions ledger: the "
            "engineering loop (test-driven-development, systematic-debugging, code-review, "
            "verification-before-completion, branch-lifecycle), plus grounded-research (cite current "
            "sources, never stale memory), static-first-analysis (strongest deterministic signal "
            "before judgment), project-memory (durable facts), and learning-layer (senior-grade "
            "output while the operator levels up)."
        ),
        # The five engineering skills are authored here rather than composed from an external
        # marketplace, and the reason is not NIH — it is that a generic TDD skill cannot make its
        # red step an `acceptance_criterion` pin. A skill that runs beside the ledger without
        # writing to it is a stateless twin of the single source of truth, which is the exact
        # divergence this package exists to find. Binding is the whole point; the prose is the
        # cheap part.
        "skills": ["test-driven-development", "systematic-debugging", "code-review",
                   "verification-before-completion", "branch-lifecycle",
                   "grounded-research", "static-first-analysis", "project-memory", "learning-layer"],
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
        # Claude Code reads this at the plugin root; Codex's manifest points at it. Two hosts, one
        # file, zero user action.
        out[".mcp.json"] = mcp_json()
        # opencode has no manifest slot for servers, so its plugin declares them in a `config()`
        # hook. Third host, same table, still zero user action.
        out["adapters/opencode/plugin/mcp.ts"] = opencode_mcp_plugin()
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
    """Codex's manifest is near-identical to Claude Code's, so one generator emits both. Three real
    differences: the directory is `.codex-plugin/`; Codex has **no `dependencies`** (a Codex user
    installs each plugin explicitly); and **every path is `./`-prefixed or it is silently dropped**.

    That third one shipped broken for months. `codex-rs/core-plugins/src/manifest.rs`:

        let Some(relative_path) = path.strip_prefix("./") else {
            tracing::warn!("ignoring {field}: path must start with `./` relative to plugin root");
            return None; };

    `resolve_manifest_paths`, `resolve_manifest_mcp_servers` and `resolve_manifest_hooks` all route
    through that one function, and the array variants `filter_map` each element through it
    INDIVIDUALLY. So a bare `skills/foo` is not an error — it is a `None` and a log line. The
    manifest parses, validates, installs, and declares nothing.

    Why it survived every gate: this file used to cite `PluginManifestMcpServers::Path` as proof
    Codex ate our shape. That citation was true and worthless — it named the **type that holds the
    value**, not the **function that consumes it**. The type accepts any `String`; the resolver
    accepts a `./`-prefixed one. Cite consumers, never types: `tests/test_codex_manifest.py` holds
    the invariant, because a rule without a gate rots.
    """
    m = {"name": name, "version": VERSION, "description": spec["description"], "keywords": KEYWORDS}
    if spec["skills"]:
        m["skills"] = [f"./skills/{s}" for s in spec["skills"]]
    if spec.get("mcp"):
        m["mcpServers"] = "./.mcp.json"
    if spec.get("hooks"):
        m["hooks"] = "./hooks/hooks.json"
    return json.dumps(m, indent=2) + "\n"


def required_servers() -> dict:
    """The MCP servers the doctrine mandates, **parsed from the table in
    src/core/knowledge-sources.md** — the same way the write verb is parsed from the roster table.
    That doc orders the agent to ground claims via those servers, so it is the thing entitled to say
    which they are. Nothing here hardcodes them.

    Why parsed and not grepped: "GitHub" appears in that doc twice as ordinary English (DeepWiki
    indexes *public GitHub repos*; *GitHub Advisory* is a registry). A word-match would "find" a
    server nobody declared — a heuristic, and this package does not guess. Correspondence comes from
    a declared fact or not at all.

    opt-in servers are named in the same table and deliberately NOT returned: each needs external
    setup (cognee a container + key, github a token), and a declared-but-unreachable server is a
    broken entry in every user's session.
    """
    servers = dict(MCP_REQUIRED.findall(read(CORE / "knowledge-sources.md")))
    if not servers:
        problems.append(
            "src/core/knowledge-sources.md declares no required MCP servers — the doctrine orders "
            "the agent to ground claims somewhere; if that changed, say so there, not here"
        )
    return servers


def mcp_json() -> str:
    """Claude Code + Codex both eat this shape, and both load it **from the installed plugin** —
    Claude via `.mcp.json` at the plugin root, Codex via its manifest's `mcpServers: "./.mcp.json"`
    (verified in openai/codex: `resolve_manifest_mcp_servers` -> `resolve_manifest_path`, i.e. the
    function that CONSUMES the value — an earlier version of this line cited the type that holds it,
    `PluginManifestMcpServers::Path`, and that is exactly how the missing `./` shipped). So for those
    two hosts, installing the plugin IS the MCP delivery; there is nothing for the user to copy.

    The bug this closes: these servers used to be declared only in this repo's own root config files,
    which no user ever receives — and the docs told users to *clone the repo and work inside it*,
    which is not installing a plugin. The delivery is the install, or it does not exist.
    """
    servers = {
        "codebase-alignment": {
            "type": "stdio",
            "command": "uv",
            # The host expands this; a repo-relative path would resolve into the USER'S project.
            "args": ["run", "--script", "${CLAUDE_PLUGIN_ROOT}/mcp/server.py"],
        }
    }
    for name, url in required_servers().items():
        servers[name] = {"type": "http", "url": url}
    return json.dumps({"mcpServers": servers}, indent=2) + "\n"


def opencode_mcp_plugin() -> str:
    """opencode's MCP delivery: a plugin `config(cfg)` hook, generated from the same table.

    opencode has no manifest to declare servers in — but a plugin CAN contribute them (verified in
    anomalyco/opencode: `config(cfg)` receives the live merged config and may mutate it). We already ship
    an opencode plugin for the ledger gate, so the user gets the servers by installing, exactly like
    Claude Code and Codex. What stood here before was a heredoc in install.sh telling the user to
    hand-copy a JSON block — unnecessary, and one hand-copy away from drift.

    Two shape differences from Claude's `.mcp.json`, both verified, neither guessable:
      - opencode's discriminator is `local`/`remote`, not `stdio`/`http`;
      - a local server's `command` is an ARRAY, not command+args.
    And `${CLAUDE_PLUGIN_ROOT}` is a Claude-ism: opencode never expands it, so the path to our own
    server is resolved from the plugin's own location instead.
    """
    remote = {n: {"type": "remote", "url": u} for n, u in required_servers().items()}
    return f'''\
{TS_BANNER}
 * opencode's MCP delivery — the servers `core/knowledge-sources.md` orders the agent to use.
 *
 * opencode has no plugin manifest to declare servers in, but `config(cfg)` hands a plugin the live
 * merged config to mutate. So installing this plugin delivers the servers, the same way installing
 * the Claude/Codex plugin does. The alternative — which this replaced — was telling the user to
 * hand-copy a JSON block out of our repo.
 *
 * The user's own config wins on every key: this fills gaps, it does not overwrite choices.
 */
import type {{ Plugin }} from "@opencode-ai/plugin"
import {{ existsSync }} from "node:fs"
import {{ dirname, resolve }} from "node:path"
import {{ fileURLToPath }} from "node:url"

// opencode's discriminator is `remote`/`local` — NOT Claude's `http`/`stdio`.
const REMOTE = {json.dumps(remote, indent=2)}

// `${{CLAUDE_PLUGIN_ROOT}}` is a Claude-ism opencode never expands, so resolve from this file.
// A local `command` is an array here, not command + args.
const SERVER = resolve(dirname(fileURLToPath(import.meta.url)), "../../../mcp/server.py")

export const McpServers: Plugin = async () => ({{
  config: (cfg: any) => {{
    const ours: Record<string, unknown> = {{ ...REMOTE }}
    // Degrade gracefully, never hard-fail: if this plugin was copied out of the built tree rather
    // than linked into it, our server is unreachable — declaring it anyway would hand the user a
    // broken entry. The doctrine's remote servers still land.
    if (existsSync(SERVER)) {{
      ours["codebase-alignment"] = {{ type: "local", command: ["uv", "run", "--script", SERVER] }}
    }}
    cfg.mcp = {{ ...ours, ...(cfg.mcp ?? {{}}) }}
  }},
}})
'''


def marketplace() -> str:
    return json.dumps({
        "name": "codebase-alignment", "version": VERSION,
        "description": "Curative + preventive codebase-alignment plugins on a shared decisions-ledger core.",
        "owner": AUTHOR,
        # Every entry is OURS, and `tests/test_codex_manifest.py` holds that shut. The catalog used
        # to carry a `superpowers` entry under the banner "generic engineering skills are COMPOSED,
        # not reinvented here". It is gone, for two reasons that compound:
        #
        # 1. **It was never composed.** No plugin declared it in `dependencies`; no file in `src/`
        #    named one of its skills. Four documents asserted a mechanism that did not exist — the
        #    house failure mode, in the one place that advertises us. (Its `source` was also
        #    `"github:obra/superpowers"`, a shorthand that is not a thing, so the entry could not
        #    even be fetched. Nobody noticed, because nobody needed it.)
        # 2. **Composing it was the wrong goal anyway.** A dependency installs the WHOLE plugin —
        #    16 skills, of which `brainstorming`, `writing-plans`/`executing-plans` and
        #    `subagent-driven-development` are stateless twins of `core/brainstorm.md`,
        #    `buildloop.py` and `core/agents.md`. None of them can write to the ledger, and none
        #    ever will. Putting a forgetting twin beside the single source of truth is the exact
        #    divergence this package exists to prevent — we would have shipped our own anti-pattern.
        #
        # So the generic skills are authored here, ledger-aware. That is not reinventing TDD; it is
        # writing the TDD whose red step is an `acceptance_criterion` pin. The doctrine is now
        # "self-contained": a user installs our plugins and needs no external plugin, ever.
        "plugins": [{"name": n, "description": s["description"], "version": VERSION,
                     "source": f"./plugins/{n}", "category": "development", "author": AUTHOR}
                    for n, s in PLUGINS.items()],
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
