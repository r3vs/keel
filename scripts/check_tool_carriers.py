#!/usr/bin/env python3
"""Every WRITE tool the MCP server exposes must be named by prose that ships.

The repo's signature failure, third recorded instance: *twelve playbooks invoked the runtime zero
times* — the prose described each activity in English, the code implemented it, and nothing joined
them. The MCP server was the answer to that (a served tool is *discoverable*, so an agent can find
`contract_diff` with no playbook naming it), and it is a real answer — but only for the tools an
agent goes looking for. A tool nothing directs it to reach for gets reached for by nobody, and the
tests stay green throughout, because a test calls the function directly.

So this asks the one question the other gates do not. `check_consistency.py` asks whether a named
thing exists; `verify_commands.py` asks whether a named path resolves after install. Both check the
things that ARE named. This checks the inverse — whether a capability that changes state on disk was
ever named at all — and it is the only direction in which silence is the bug.

Scope: **every** served tool. It was WRITE-only for most of this gate's life, on an argument that
read this way: *a read tool that only the tool index names is defensible — reading costs nothing, the
agent can discover it, and a wrong read is visible in its own output.* Two thirds of that is still
true and it is the wrong axis. What the argument measures is the cost of a **wrong read**; what this
gate is about is a **missing step**, and a step does not become cheap by being read-only.

`ledger_fog` is the instance that settled it. Its own docstring carried the instruction — *"Read it
at the start of an interview round"* — and no playbook did; the interview funnel named the three fog
WRITE doors and `ledger_summary` beside them, so the workflow wrote to a register it never read.
Discovery does not save that: an agent discovers a tool once it knows it needs one, and not knowing
is the failure. Worse, on the hosts that **defer** tool schemas — Claude Code's verified default, and
Pi behind its one proxy tool — a description is not in context at all until something already made
the agent search for it, so an instruction living only in a docstring reaches nobody. (opencode loads
the surface up front per its own docs, which is exactly why "some host would show it" is not an
argument.) That deferral is what makes 70 tools affordable; it is also what makes a docstring a bad
place to keep a step.

So the question is the same for both halves — *is this capability named by prose that ships?* — and a
tool that is genuinely discovery-only takes an `UNNAMED_OK` entry with the reason, which is the shape
this repo uses everywhere else for a declared exception.

Two carrier classes count, because the skills are read by an agent in two forms:

  * **prose** — the shipped `.md` under `src/skills/` plus `src/core/*.md`: the playbook that tells
    an agent to act. **Shipped** is asked of `build.py`, not re-decided here — see `prose_carriers`.
  * **structure** — a `modules.json` module whose `engine` is `mcp:<tool>`. Parsed as JSON, not
    grepped: an engine declaration is a stronger binding than a sentence, and `check_consistency.py`
    already validates it against the server.

The prose side is a name match, and that is the whole claim being made — *this file names this tool*.
It is not a semantic read of the prose (this repo forbids grepping prose for meaning), so it cannot
tell a good instruction from a bad one. It tells apart the only thing it claims to: named from
unnamed. A file that names a tool and then tells the agent something false is a different bug, and
the gate for that one is a human reading the playbook.

Run in CI: `python scripts/check_tool_carriers.py` (exit 1 when a write tool has no carrier).
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "src" / "mcp" / "server.py"
FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402  — the authority on what ships; never a second copy of that fact

#: Files that name tools without directing anyone to run them. Excluded from the carrier set with
#: the reason, because "it is mentioned somewhere" is exactly the weak evidence that let
#: `ledger_record_decision` and `interview_expand` ship reachable by no phase.
CATALOGS = {
    "src/skills/using-the-ledger/SKILL.md":
        "the tool index — a table of tools by intent. Naming a tool there proves it is catalogued, "
        "not that any workflow reaches for it. You read the index once you already know you need a "
        "tool; not knowing is the failure this gate is about.",
    "src/core/decisions-ledger-spec.md":
        "the schema authority. It names a tool to DEFINE a state (`evidence: elicited` cites "
        "ledger_record_decision to say what that rung means) — a definition of what the ledger "
        "holds, never an instruction to an agent to run anything.",
}

#: Write tools deliberately named by no shipped prose, each with the reason it is defensible.
#: Empty, and that is the intended steady state: this gate exists because the honest fix for an
#: unnamed write tool is almost always to name it in the playbook that already describes the act,
#: not to record a reason for the silence. A legitimate entry would be a tool whose only caller is
#: another tool, or one kept for an external integration no skill drives.
UNNAMED_OK: dict[str, str] = {}


def _const_dicts(tree: ast.Module) -> dict:
    """Module-level annotation constants (`_RO`, `_RW`, `_RW_CREATE`), `**` unpacking included."""
    out: dict = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Dict)):
            continue
        out[node.targets[0].id] = _dict_value(node.value, out)
    return out


def _dict_value(node: ast.Dict, consts: dict) -> dict:
    value: dict = {}
    for key, val in zip(node.keys, node.values):
        if key is None:                                   # {**_RW, ...}
            if not isinstance(val, ast.Name) or val.id not in consts:
                raise SystemExit(f"ERROR cannot resolve `**{ast.unparse(val)}` in {SERVER.name}")
            value.update(consts[val.id])
        else:
            value[ast.literal_eval(key)] = ast.literal_eval(val)
    return value


def served_tools() -> dict:
    """`{tool name: writes?}` for every tool the server advertises.

    Structural, from the decoration that ships — never a hand-kept second list, which would drift
    from the server the first time somebody added a tool. The write flag is no longer what decides
    whether a tool is checked (see the module docstring); it is kept because the error message is
    sharper when it can say which kind of capability went unnamed.
    """
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    consts = _const_dicts(tree)
    tools = {}
    for node in tree.body:
        if not isinstance(node, FUNC):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "tool"):
                continue
            tools[node.name] = True
            for kw in dec.keywords:
                if kw.arg == "annotations" and isinstance(kw.value, ast.Dict):
                    tools[node.name] = not _dict_value(kw.value, consts).get("readOnlyHint")
    if not tools:
        raise SystemExit("ERROR no @mcp.tool decorations found in src/mcp/server.py — the decorator "
                         "shape changed and this gate just went vacuous")
    if not any(tools.values()):
        raise SystemExit("ERROR no WRITE tool found — every tool reported readOnlyHint, which is "
                         "false of a server that writes the ledger. The annotation shape changed.")
    return tools


def shipped_md() -> list:
    """Every authored `.md` the build actually emits into a plugin — asked of `build.py`.

    The glob this replaced (`src/skills/**/*.md`) called its result "shipped prose files" and was
    not: it swept up both `TODO.md` build checklists and all of `writing-skills`, which is our
    contributor guide in a skill's clothes. So a write tool named only in a TODO satisfied a gate
    whose own output said otherwise — this gate asserting a scope it did not have, which is the
    class it exists to catch.

    `build.shipped_skill_files()` is the authority and there is deliberately no exclusion list here:
    a hand-kept copy of "what ships" would drift the first time a skill was renamed or a new dev-only
    one added, which is the same second-carrier bug one level up.

    `src/core/*.md` is included whole: `keel-core` declares `core_docs`, so every one of them is
    copied to the plugin root, and the per-skill closure vendors the load-bearing ones on top.
    """
    return ([f for f in build.shipped_skill_files() if f.suffix == ".md"]
            + sorted(build.CORE.glob("*.md")))


def prose_carriers() -> dict:
    """path -> text, for every shipped .md that is allowed to count as naming a tool."""
    out = {}
    for path in shipped_md():
        rel = path.relative_to(ROOT).as_posix()
        if rel in CATALOGS:
            continue
        out[rel] = path.read_text(encoding="utf-8")
    return out


def engine_carriers() -> dict:
    """tool -> [modules.json entries declaring `engine: mcp:<tool>`], read as JSON.

    Same authority as `shipped_md` above, for the same reason: this half kept its own
    `src/skills/*/modules.json` glob after the prose half was narrowed, so a module catalog in a
    dev-only skill would have counted as a carrier for a tool no user can reach. Nothing exploits
    that today — `writing-skills` ships no `modules.json` — which is exactly how the prose half got
    to be wrong for months before anyone read its output. One question ("what ships?"), one answer.
    """
    out: dict = {}
    for path in sorted(f for f in build.shipped_skill_files() if f.name == "modules.json"):
        rel = path.relative_to(ROOT).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue                     # check_consistency.py owns that error; do not double-report
        for module in data.get("modules", []):
            match = re.fullmatch(r"mcp:(\w+)", str(module.get("engine") or ""))
            if match:
                out.setdefault(match.group(1), []).append(f"{rel}#{module.get('id', '?')}")
    return out


def main() -> int:
    tools = served_tools()
    shipped = {p.relative_to(ROOT).as_posix() for p in shipped_md()}
    prose = prose_carriers()
    engines = engine_carriers()

    # A CATALOGS key that no longer ships excludes nothing while still reading as governance — the
    # same stale-exemption failure the UNNAMED_OK check below reports.
    stale_catalogs = sorted(set(CATALOGS) - shipped)

    unnamed, exempt_used = [], 0
    for tool in tools:
        if tool in UNNAMED_OK:
            exempt_used += 1
            continue
        named_by = engines.get(tool, []) + [
            rel for rel, text in prose.items() if re.search(rf"\b{re.escape(tool)}\b", text)]
        if not named_by:
            unnamed.append(tool)

    for tool in unnamed:
        act = ("WRITES, and no shipped playbook names it" if tools[tool] else
               "is served, and no shipped playbook names it")
        print(f"ERROR `{tool}` {act}. Name it where the act is "
              f"already described — the phase that performs it, or the module's `engine` — or add it "
              f"to UNNAMED_OK with the reason. A capability nobody names is a step the workflow "
              f"never takes, and nothing fails to say so.")

    stale = sorted(set(UNNAMED_OK) - set(tools))
    for tool in stale:
        print(f"ERROR UNNAMED_OK exempts `{tool}`, which the server no longer exposes. A stale "
              f"exemption reads as governance while covering nothing.")

    for rel in stale_catalogs:
        print(f"ERROR CATALOGS excludes `{rel}`, which the build does not ship. A stale exclusion "
              f"reads as governance while covering nothing.")

    bad = len(unnamed) + len(stale) + len(stale_catalogs)
    writes = sum(1 for w in tools.values() if w)
    print(f"\n{len(tools)} served tool(s) ({writes} write, {len(tools) - writes} read) checked "
          f"against {len(prose)} shipped prose files and "
          f"{sum(len(v) for v in engines.values())} engine declaration(s) "
          f"({len(CATALOGS)} catalog file(s) excluded, {exempt_used} exemption(s) used) — "
          f"{bad} error(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
