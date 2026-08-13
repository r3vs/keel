#!/usr/bin/env python3
"""The Claude-side manifests, validated by something that blocks.

This repo already has a manifest gate with teeth — but it is Codex's
(`tests/test_codex_manifest.py`, born of a `./` prefix nobody read). The Claude side has had only
`claude plugin validate --strict`, in a job marked `continue-on-error: true` because the CLI is not
reliably installable in CI. That is a validator whose failures nobody is required to look at, which
is the same shape as no validator: the `--strict` run exists to catch *"a misspelled field name or a
field left over from another tool's manifest"*, and a misspelled field is exactly what Claude Code
then **ignores in silence** (*"Claude Code ignores top-level fields it does not recognize"*). Warning
in one place, silence in the other, and nothing in between that stops a merge.

So this is the blocking floor underneath the advisory CLI. It re-decides nothing the CLI decides
better; it asserts the handful of invariants whose failure mode is quiet.

**What it adds that an existing gate does not** — each line here is a hole, not a second opinion:

  * **An unrecognized or wrong-typed field.** Docs, at the consumer: an unknown key is ignored at
    load; a *recognized* key with the wrong type is worse — *"the plugin fails to load"* (`keywords`
    as a string is the doc's own example). Nothing of ours checks either.
  * **`dependencies` leaving this repo.** `test_codex_manifest.py::test_no_source_leaves_this_repo`
    holds the marketplace `source` shut and is the doctrine's home; it says nothing about
    `dependencies`, which is the *other* door out — and a real one, since Claude Code has a
    documented `allowCrossMarketplaceDependenciesOn` for exactly that traffic. A dependency on a
    plugin we do not ship reintroduces "install this other thing first" through the back.
  * **A `.mcp.json` in a plugin that is not `keel-core`.** `test_mcp_declaration.py::declared()`
    opens `plugins/keel-core/.mcp.json` by name. The day a second plugin ships servers, every
    assertion in that file keeps passing and says nothing about them. This walks the tree.
  * **A reserved marketplace name.** Anthropic reserves sixteen names plus impersonations, and
    re-checks *"every time it loads a marketplace, not only when you add one"* — so a name that
    becomes reserved later stops loading for users who already installed. Cheap to check, invisible
    when it bites.
  * **Version identity across the four plugins and every catalog entry.** `build.py --check` proves
    `plugins/` equals what `build.py` generates — which is a different claim. If the generator grows
    a per-plugin version, `--check` stays green and the identity breaks; and `plugin.json` wins over
    the marketplace entry, so a split leaves the catalog advertising a version nobody installs.
  * **A path field that does not resolve.** Claude requires `./` on every manifest path (*"All paths
    must be relative to the plugin root and start with `./`, except that the `skills` field also
    accepts `.`"*) and existence is checked by nobody. We emit no path fields today — Claude
    auto-discovers our layout, which is why we correctly declare none — so this is the gate that
    holds the day someone adds one, which is precisely when the Codex twin of this bug shipped.

**Not checked here, on purpose.** Frontmatter, hook schemas and skill bodies are the CLI's job and
`check_consistency.py`'s; marketplace `source` self-containment is `test_codex_manifest.py`'s and
stays there. One fact, one owner.

Every field classification below is read off the published reference — the table that says what
Claude Code *does* with the value — and the docs' own wording is quoted at the constant. Where the
docs are silent the code says so rather than guessing.

Run in CI: `python scripts/validate_manifests.py` (exit 1 on any violation).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

#: Default target: this repo. Every function below takes the tree as an argument instead of
#: reaching for it, so `tests/test_validate_manifests.py` can point the whole gate at a temporary
#: copy and assert that a planted violation is REPORTED. A linter that only ever runs on a tree
#: known to be clean proves nothing about what it would catch — this repo has had gates that were
#: vacuous for months, and the cheapest defence is making the failure path reachable from a test.
ROOT = pathlib.Path(__file__).resolve().parent.parent

#: *"Unique identifier (kebab-case, no spaces)"* — the rule for a plugin `name`, a marketplace
#: `name`, and a marketplace entry's `name`. All three are public-facing install strings.
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: semver.org's own recommended regex, trimmed to the three numeric parts plus optional
#: prerelease/build. `version` is documented as a *"Semantic version"* whose presence PINS the
#: plugin — a value that does not parse pins nothing and updates silently.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

#: A dependency's `version` is not a version — it is an **npm semver RANGE**, and the distinction is
#: the whole reason this exists beside `SEMVER` above. *"A [semver range](…node-semver#ranges) such
#: as `~2.1.0`, `^2.0`, `>=1.4`, or `=2.1.0`"* — note `^2.0` and `>=1.4`, which `SEMVER` rejects, so
#: reusing that regex here would fail this repo's own manifest.
#:
#: Verified at the consumer rather than at the type: an unparseable range is a `range-conflict`,
#: whose documented causes include *"a range is not valid semver syntax"*, and *"Claude Code disables
#: the affected plugin until you resolve the error"* — a failure that happens on the user's machine,
#: after install, silently as far as this repo is concerned. It is also the one string in any
#: manifest we generate by **string surgery** (`f"^{'.'.join(VERSION.split('.')[:2])}"` in
#: build.py), which is exactly the shape that produces `^0.` from a one-part version and passes
#: every other gate. This is a conservative reader of node-semver's grammar: comparator sets over
#: partial versions, hyphen ranges, `||` alternation, `*`/`x` wildcards. It accepts a superset of
#: what we emit and rejects the syntaxes from other ecosystems that look plausible here (`~>2.0`).
_PARTIAL = (r"v?(?:\d+|[xX*])(?:\.(?:\d+|[xX*]))?(?:\.(?:\d+|[xX*]))?"
            r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")
_COMPARATOR = rf"(?:[<>]=?|=|\^|~)?\s*{_PARTIAL}"
_RANGE_SET = rf"(?:\*|{_PARTIAL}\s+-\s+{_PARTIAL}|{_COMPARATOR}(?:\s+{_COMPARATOR})*)"
SEMVER_RANGE = re.compile(rf"^\s*{_RANGE_SET}(?:\s*\|\|\s*{_RANGE_SET})*\s*$")

#: Manifest keys whose STRING values Claude Code resolves as a path relative to the plugin root,
#: read off the "Path behavior rules" section rather than off the subset we emit — the same
#: discipline `tests/test_codex_manifest.py` arrived at after listing three of five.
#: `experimental.themes` / `experimental.monitors` are nested and handled separately below.
PATH_VALUED = {"skills", "commands", "agents", "hooks", "mcpServers", "outputStyles", "lspServers"}

#: Nested path-valued keys under `experimental`. The rest of `experimental` is free-form: Claude
#: *"ignores a non-object value"* there, so an unknown sub-key is not a load error and is not
#: treated as one here.
EXPERIMENTAL_PATH_VALUED = {"themes", "monitors"}

#: Keys Claude Code reads as data, with the type it demands. A recognized key with the wrong type
#: is the failure worth catching: *"the plugin fails to load"*. `hooks` and `mcpServers` are absent
#: from this map because they are dual — a path string OR an inline object — and are classified by
#: value shape, exactly as Codex's untagged enum forced us to do on the other side.
PLAIN_TYPES: dict[str, type] = {
    "$schema": str,
    "name": str,
    "displayName": str,
    "version": str,
    "description": str,
    "author": dict,
    "homepage": str,
    "repository": str,
    "license": str,
    "keywords": list,
    "metadata": dict,
    "defaultEnabled": bool,
    "dependencies": list,
    "experimental": dict,
}

#: Names reserved for Anthropic, plus the impersonation rule. A marketplace under one of these
#: *"stops loading and reports that it is registered from an untrusted source"* — for users who
#: already added it, not only at registration.
RESERVED_MARKETPLACE_NAMES = {
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace", "anthropic-plugins",
    "agent-skills", "anthropic-agent-skills", "knowledge-work-plugins", "life-sciences",
    "claude-for-legal", "claude-for-financial-services", "financial-services-plugins",
    "first-party-plugins", "healthcare",
}

#: A directory or file whose presence means the plugin contributes something once installed. Claude
#: auto-discovers all of these, which is why our manifests declare no paths — and also why a plugin
#: with none of them would install, validate, and do nothing.
COMPONENT_SURFACES = ("skills", "commands", "agents", "hooks", ".mcp.json", ".lsp.json", "SKILL.md")

#: MCP transports Claude Code accepts. `stdio` needs a `command`; the two network forms need a
#: `url`. The published example omits `type` entirely — so requiring it is OUR rule, and it has a
#: reason: the same bytes are handed to Codex (`mcpServers: "./.mcp.json"`), and `build.py` derives
#: opencode's `local`/`remote` from this discriminator. An entry with no `type` is a shape that
#: cannot be translated.
TRANSPORTS = {"stdio": "command", "http": "url", "sse": "url"}

#: Findings for the run in progress. Module-level rather than threaded through eight signatures,
#: and `validate()` clears it on entry — this is a single-threaded gate, and the alternative was an
#: accumulator parameter on every function that has nothing else to say.
errors: list[str] = []


def fail(where: str, message: str) -> None:
    errors.append(f"ERROR {where}: {message}")


def load(path: pathlib.Path, where: str) -> dict | None:
    """Parse a manifest, reporting rather than raising — one bad file must not hide the others."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(where, "missing — run scripts/build.py")
        return None
    except json.JSONDecodeError as exc:
        fail(where, f"is not valid JSON ({exc}). Claude Code reports this as a corrupt manifest "
                    "and the plugin does not load")
        return None
    if not isinstance(data, dict):
        fail(where, "must be a JSON object")
        return None
    return data


def path_strings(value) -> list[str]:
    """The strings this value hands to Claude's path resolver. An object is inline data."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def check_paths(where: str, root: pathlib.Path, field: str, value) -> None:
    if not isinstance(value, (str, list)):
        # A path field that is neither a string nor an array of them: recognized key, wrong type,
        # which the docs put in the "plugin fails to load" bucket. Silence here would let it past.
        fail(where, f"`{field}` is {type(value).__name__}; a path field is a string or an array "
                    f"of strings")
        return
    for raw in path_strings(value):
        # `skills` is the documented exception: `.` and `./` both denote the plugin root.
        ok_prefix = raw.startswith("./") or (field == "skills" and raw == ".")
        if not ok_prefix:
            fail(where, f"`{field}: {raw}` — every manifest path must start with `./` "
                        f"(`skills` may also be `.`). Claude Code rejects the manifest; Codex "
                        f"drops the entry with only a log line")
            continue
        if ".." in pathlib.PurePosixPath(raw).parts:
            fail(where, f"`{field}: {raw}` escapes the plugin root — after install that resolves "
                        f"into the USER'S project")
            continue
        if not (root / raw).exists():
            fail(where, f"`{field}: {raw}` is not in the shipped tree. A declared path REPLACES "
                        f"default discovery for most fields, so a missing target means the "
                        f"component silently disappears")


def check_plugin_manifest(name: str, data: dict, root: pathlib.Path) -> None:
    where = f"plugins/{name}/.claude-plugin/plugin.json"

    declared_name = data.get("name")
    if not isinstance(declared_name, str) or not declared_name:
        fail(where, "`name` is the ONE required field and it is missing or not a string")
    else:
        if not KEBAB.match(declared_name):
            fail(where, f"`name: {declared_name}` is not kebab-case. It is the install string a "
                        f"user types and the prefix every component is namespaced under")
        if declared_name != name:
            fail(where, f"`name: {declared_name}` does not match the directory `{name}`, which is "
                        f"what the marketplace `source` points at")

    version = data.get("version")
    if not isinstance(version, str):
        fail(where, "`version` is missing. Without it the version comes from a fallback chain and "
                    "the plugin is not pinned, so users take updates we never published")
    elif not SEMVER.match(version):
        fail(where, f"`version: {version}` is not semver")

    for key, value in sorted(data.items()):
        if key in PATH_VALUED:
            if key in ("hooks", "mcpServers") and isinstance(value, dict):
                continue                          # inline configuration, not a path — see PLAIN_TYPES
            check_paths(where, root, key, value)
        elif key == "experimental":
            if isinstance(value, dict):
                for sub in sorted(EXPERIMENTAL_PATH_VALUED & set(value)):
                    check_paths(where, root, f"experimental.{sub}", value[sub])
        elif key in PLAIN_TYPES:
            if not isinstance(value, PLAIN_TYPES[key]):
                fail(where, f"`{key}` is {type(value).__name__}, expected "
                            f"{PLAIN_TYPES[key].__name__}. A recognized field with the wrong type "
                            f"is a LOAD failure, not a warning")
        else:
            fail(where, f"`{key}` is not a field Claude Code recognizes. It is ignored at load and "
                        f"only `claude plugin validate --strict` warns — which is the job that "
                        f"cannot block. If the field is real, add it to PLAIN_TYPES or PATH_VALUED "
                        f"with the doc line that says what consumes it")

    author = data.get("author")
    if isinstance(author, dict) and not author.get("name"):
        fail(where, "`author.name` is required whenever `author` is present")

    if not any((root / surface).exists() for surface in COMPONENT_SURFACES):
        fail(where, "this plugin ships no skills/, commands/, agents/, hooks/, .mcp.json, .lsp.json "
                    "or root SKILL.md — it installs, validates, and contributes nothing")


def check_dependencies(name: str, data: dict, built: set[str]) -> None:
    """Self-containment, on the door `test_no_source_leaves_this_repo` does not watch.

    That test holds the marketplace `source` — where a plugin is FETCHED from. `dependencies` is
    where one is PULLED from, auto-installed and transitively enabled, and Claude Code has a
    marketplace-level `allowCrossMarketplaceDependenciesOn` precisely because a dependency can
    point outside the catalog it was declared in. The doctrine is the same doctrine: the user
    installs no external plugin, ever.
    """
    where = f"plugins/{name}/.claude-plugin/plugin.json"
    declared = data.get("dependencies")
    if not isinstance(declared, list):
        return                       # absent, or the wrong type — already reported by PLAIN_TYPES
    for entry in declared:
        # Documented as `["helper-lib", {"name": "secrets-vault", "version": "~2.1.0"}]`.
        dep = entry.get("name") if isinstance(entry, dict) else entry
        if not isinstance(dep, str):
            fail(where, f"`dependencies` entry {entry!r} is neither a name nor an object with one")
            continue
        constraint = entry.get("version") if isinstance(entry, dict) else None
        if constraint is not None and not (isinstance(constraint, str)
                                           and SEMVER_RANGE.match(constraint)):
            fail(where, f"`{dep}` is constrained to {constraint!r}, which is not a semver RANGE. "
                        f"An unparseable range is a `range-conflict` at load and Claude Code "
                        f"*disables the plugin* until it is fixed — on the user's machine, after "
                        f"install, where nothing here can see it. Ranges look like `^0.6`, "
                        f"`~2.1.0`, `>=1.4`, `=2.1.0`")
        if dep not in built:
            fail(where, f"depends on `{dep}`, which this repo does not build. Everything a "
                        f"programmer and their agent need ships from here — a dependency we do "
                        f"not author is an external install we told the user they would never do")


def check_mcp(name: str, root: pathlib.Path) -> int:
    """Validate a plugin's `.mcp.json` if it has one. Returns the number of servers checked."""
    path = root / ".mcp.json"
    if not path.exists():
        return 0
    where = f"plugins/{name}/.mcp.json"
    data = load(path, where)
    if data is None:
        return 0
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        fail(where, "declares no `mcpServers` object. The file's presence is the whole declaration "
                    "on Claude Code AND Codex — an empty one installs and serves nothing")
        return 0
    for server, entry in sorted(servers.items()):
        if not isinstance(entry, dict):
            fail(where, f"server `{server}` is not an object")
            continue
        transport = entry.get("type")
        if transport not in TRANSPORTS:
            fail(where, f"server `{server}` declares type {transport!r}; expected one of "
                        f"{sorted(TRANSPORTS)}. build.py maps this discriminator onto opencode's "
                        f"local/remote, where a wrong value is valid JSON that declares nothing")
            continue
        required = TRANSPORTS[transport]
        if not entry.get(required):
            fail(where, f"server `{server}` is `{transport}` but has no `{required}`")
    return len(servers)


def check_marketplace(tree: pathlib.Path, built: set[str], versions: dict[str, str]) -> int:
    data = load(tree / ".claude-plugin" / "marketplace.json", ".claude-plugin/marketplace.json")
    if data is None:
        return 0
    where = ".claude-plugin/marketplace.json"

    name = data.get("name")
    if not isinstance(name, str) or not KEBAB.match(name or ""):
        fail(where, f"`name: {name!r}` must be present and kebab-case")
    elif name in RESERVED_MARKETPLACE_NAMES:
        fail(where, f"`{name}` is reserved for Anthropic. Claude Code re-checks reserved names on "
                    f"every load, so an already-installed marketplace stops loading")

    owner = data.get("owner")
    if not isinstance(owner, dict) or not owner.get("name"):
        fail(where, "`owner` is required and its `name` is required within it")

    entries = data.get("plugins")
    if not isinstance(entries, list) or not entries:
        fail(where, "`plugins` is required and must list at least one plugin")
        return 0

    listed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            fail(where, f"plugin entry {entry!r} is not an object")
            continue
        entry_name = entry.get("name")
        if not isinstance(entry_name, str) or not KEBAB.match(entry_name or ""):
            fail(where, f"entry `name: {entry_name!r}` must be present and kebab-case")
            continue
        listed.add(entry_name)
        if not isinstance(entry.get("source"), (str, dict)):
            fail(where, f"`{entry_name}` has no `source` — it is a required field")
        entry_version = entry.get("version")
        if entry_version is not None and not SEMVER.match(str(entry_version)):
            fail(where, f"`{entry_name}` declares version {entry_version!r}, which is not semver")
        # `plugin.json` wins over the entry, so a divergence advertises a version nobody installs.
        if entry_name in versions and entry_version not in (None, versions[entry_name]):
            fail(where, f"`{entry_name}` is {entry_version} in the catalog and "
                        f"{versions[entry_name]} in its plugin.json. plugin.json wins, so the "
                        f"catalog is advertising a version no user receives")

    for missing in sorted(built - listed):
        fail(where, f"`{missing}` is built but not listed — it is unreachable from the marketplace")
    for phantom in sorted(listed - built):
        fail(where, f"`{phantom}` is listed but not built in plugins/")
    return len(entries)


def validate(tree: pathlib.Path = ROOT) -> tuple[list[str], int, int, int]:
    """Run every check against `tree`. Returns (errors, plugins, catalog entries, servers).

    Separated from `main` so the failure paths are testable. Emptiness is an ERROR rather than a
    vacuous pass: every assertion in here is satisfied by a `plugins/` with nothing in it, and this
    repo has shipped that exact shape of green before.
    """
    errors.clear()
    plugins = tree / "plugins"
    if not plugins.is_dir():
        fail("plugins/", "does not exist — run scripts/build.py")
        return list(errors), 0, 0, 0

    roots = sorted(p for p in plugins.iterdir() if (p / ".claude-plugin").is_dir())
    if not roots:
        fail("plugins/", "no plugin carries a .claude-plugin/ — run scripts/build.py")
        return list(errors), 0, 0, 0

    built = {p.name for p in roots}
    versions: dict[str, str] = {}
    servers = 0

    for root in roots:
        name = root.name
        data = load(root / ".claude-plugin" / "plugin.json",
                    f"plugins/{name}/.claude-plugin/plugin.json")
        if data is None:
            continue
        check_plugin_manifest(name, data, root)
        check_dependencies(name, data, built)
        servers += check_mcp(name, root)
        if isinstance(data.get("version"), str):
            versions[name] = data["version"]

    # One version for the whole package, because that is what it is: four plugins that are
    # installed together (three declare `dependencies: ["keel-core"]`) and released as one tag.
    # `build.py --check` cannot see this — it proves plugins/ matches the generator, and a
    # generator that emitted per-plugin versions would pass it.
    if len(set(versions.values())) > 1:
        fail("plugins/*/.claude-plugin/plugin.json",
             "the plugins do not share one version: "
             + ", ".join(f"{n}={v}" for n, v in sorted(versions.items())))

    entries = check_marketplace(tree, built, versions)
    return list(errors), len(roots), entries, servers


def main() -> int:
    found, plugins, entries, servers = validate(ROOT)
    for message in found:
        print(message)
    print(f"\n{plugins} plugin manifest(s), {entries} catalog entry(ies) and {servers} MCP "
          f"server declaration(s) checked — {len(found)} error(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
