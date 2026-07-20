"""Codex resolves a manifest path only if it starts with `./`. Everything else is dropped in silence.

This is the fourth instance of this repo's signature bug — claiming what the shipped artifact does
not do, staying green throughout — and the first one that *passes* the question the other three
failed. "What does this resolve to when the cwd is someone else's project?" A `skills/foo` in a
Codex manifest is plugin-root-relative and answers that question correctly. It still declared
nothing, because the host's parser demands a syntax nobody read.

`codex-rs/core-plugins/src/manifest.rs`:

    fn resolve_manifest_path(
        plugin_root: &PathUri,
        field: &'static str,
        path: Option<&str>,
    ) -> Option<PathUri> {
        let path = path?;
        if path.is_empty() {
            return None;
        }
        let Some(relative_path) = path.strip_prefix("./") else {
            tracing::warn!("ignoring {field}: path must start with `./`
              relative to plugin root");
            return None;
        };
        // ... remaining validation ...
    }

`resolve_manifest_paths` (skills), `resolve_manifest_mcp_servers` and `resolve_manifest_hooks` all
route through it, and the `Vec<String>` variants `filter_map` each element through it INDIVIDUALLY —
so a bad element is dropped alone, without taking its siblings or the parse down with it. Not an
error. A `None` and a log line.

**And then nothing bad happened, which is the actually interesting part.** The first draft of this
file said all four plugins installed on Codex with zero skills, zero MCP servers and zero hooks.
That was false, and it was false by *exactly the reasoning error the file exists to warn about*.
Read what consumes the dropped result — `loader.rs`:

    fn plugin_skill_roots(...) -> Vec<AbsolutePathBuf> {
        let mut paths = if manifest_paths.skills.is_empty() {
            default_skill_roots(plugin_root)          // -> <plugin_root>/skills
        } else { manifest_paths.skills.clone() };

Every path dropped ⇒ the vec is empty ⇒ **default discovery**. Same for `mcpServers`
(`plugin_mcp_config_paths` → `<root>/.mcp.json`) and `hooks` (`load_plugin_hooks`'s `None` arm →
`<root>/hooks/hooks.json`) — both reached because `resolve_manifest_*` returns `None` via `.map()`
rather than an empty `Some`. Our layout is precisely Codex's default layout, so **the real-world
impact of the missing `./` was zero**: three inert declarations, silently doing what the defaults
would have done anyway.

**So the lesson is one turn sharper than "cite consumers, never types."** That is how the bug got
in: `build.py::mcp_json()` cited *"verified in openai/codex: `PluginManifestMcpServers::Path`"* and
`test_mcp_declaration.py` asserted `mcpServers == ".mcp.json"`, pinning the broken value — both true
statements about the type that HOLDS the value rather than the function that CONSUMES it. But
`resolve_manifest_path` is only the function that **rejects** the value. Stopping there produced a
confident, wrong severity. **Every citation is one link in a chain, and a chain has an end: follow
the value until something either uses it or replaces it.** Here it was replaced, by a default.

**Which leaves a real reason for this file, and it is `commands`.** That field has no fallback:
`load_plugin_command_paths` returns `Some(vec![])` when the key is present but every path was
dropped, and its consumer is `.unwrap_or_else(|| vec![plugin_root.join(PLUGIN_COMMANDS_DIR)])` —
which fires on `None`, not on `Some(vec![])`. So declaring `commands` without `./` is **strictly
worse than not declaring it at all**: omit it and you get `<root>/commands`; get it wrong and you
get nothing. We ship `commands/` directories and declare no `commands` key, so we are correct today
by accident. This gate is what makes it correct on purpose.

What this file asserts, and why in this shape:

- **The invariant, not the list.** The first draft hand-listed the three fields we happened to emit.
  `RawPluginManifest` actually has **five** path-valued keys — `skills`, `mcpServers`, `apps`,
  `hooks`, `commands` — plus four more nested under `interface` (`composerIcon`, `logo`, `logoDark`,
  `screenshots`), which reach the same resolver through `resolve_interface_asset_path`, a pure
  delegation. A list of three was already wrong the day it was written. So every key is classified,
  and an UNCLASSIFIED key **fails**: a new manifest field must be a deliberate decision, not a
  default into silence.
- **`interface` is mixed, so it recurses.** Eleven of its sub-keys are plain metadata and four are
  paths. Classifying `interface` wholesale as plain would wave every icon through — the same silent
  drop, one level down. (Do **not** extend this gate to a skill's `agents/openai.yaml`: that file's
  assets go through `resolve_asset_path`, where `./` is *optional*, the first component must be
  `assets`, and `..` is allowed within the plugin's shared asset root. Different consumer,
  different rules — which is the whole thesis of this file.)
- **Value shape decides, exactly as the untagged enum decides.** serde tries `Path(String)` before
  `Object`/`Inline`, so a string is a path and an object is inline data. `hooks` may be either. We
  mirror that rule rather than restating its outcome, because `keywords` is also an array of strings
  and must never be `./`-prefixed — the field tells you *whether* to resolve, the value tells you
  *what* gets resolved.
- **Structure, never prose.** Two earlier checks in this suite were written as string-matches and
  both failed on the comment explaining the very thing they matched (see `test_mcp_declaration.py`).
  A match cannot tell use from mention. JSON keys and values are a carrier; there is nothing to
  guess.
- **Emptiness fails.** Every path assertion below passes vacuously on a manifest that declares
  nothing. Codex's default discovery means that state is survivable rather than fatal — which is
  exactly why it needs asserting: a failure that heals itself is a failure nobody reports.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"

# Every key whose STRING values Codex hands to `resolve_manifest_path`, read off `RawPluginManifest`
# and its resolvers — not off the subset we happen to emit. Object values are inline data and are
# never resolved: the untagged enum's own discriminator, so it is ours too.
#
# `commands` is the one with teeth. The others fall back to default discovery when their paths are
# dropped (`<root>/skills`, `<root>/.mcp.json`, `<root>/hooks/hooks.json`, `<root>/.app.json`), so a
# missing `./` is inert. `commands` does not: present-but-all-dropped yields `Some(vec![])`, and its
# consumer's `.unwrap_or_else` fires only on `None`. Declaring it wrong is worse than omitting it.
PATH_VALUED = {"skills", "mcpServers", "apps", "hooks", "commands"}

# Path-valued sub-keys of `interface`, which reach the same resolver via `resolve_interface_asset_path`
# (a pure delegation to `resolve_manifest_path`). The other 11 sub-keys — displayName, shortDescription,
# longDescription, developerName, category, capabilities, websiteURL, privacyPolicyURL,
# termsOfServiceURL, defaultPrompt, brandColor — are plain metadata.
INTERFACE_PATH_VALUED = {"composerIcon", "logo", "logoDark", "screenshots"}

# Fields Codex reads as plain data. Present so that a key in NEITHER set fails: silence is how the
# `./` bug shipped, and an unclassified field is silence with extra steps.
PLAIN = {"name", "version", "description", "keywords", "interface"}


def manifests() -> dict:
    found = {p.parent.parent.name: json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(PLUGINS.glob("*/.codex-plugin/plugin.json"))}
    assert found, "no Codex manifests in plugins/ — run scripts/build.py"
    return found


INTERFACE_PLAIN = {"displayName", "shortDescription", "longDescription", "developerName",
                   "category", "capabilities", "websiteURL", "privacyPolicyURL",
                   "termsOfServiceURL", "defaultPrompt", "brandColor"}


def resolved_strings(value) -> list:
    """The strings this value will hand to `resolve_manifest_path`, mirroring the untagged enum.

    String -> Path(String). List -> Paths(Vec<String>), element by element. Object -> Inline, which
    is data Codex reads directly and never resolves, so it contributes nothing here.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def path_valued_items(m: dict):
    """(label, string) for every value in this manifest that reaches `resolve_manifest_path`."""
    for field in sorted(PATH_VALUED & set(m)):
        for s in resolved_strings(m[field]):
            yield field, s
    for sub in sorted(INTERFACE_PATH_VALUED & set(m.get("interface") or {})):
        for s in resolved_strings(m["interface"][sub]):
            yield f"interface.{sub}", s


class TestEveryCodexPathResolves(unittest.TestCase):
    def test_every_manifest_key_is_classified(self):
        # The gate that survives Codex adding a field. An unknown key is not benign: if it is
        # path-valued and we never say so, it drops silently and this suite reports success.
        for plugin, m in sorted(manifests().items()):
            with self.subTest(plugin=plugin):
                self.assertFalse(
                    set(m) - PATH_VALUED - PLAIN,
                    "unclassified key in a Codex manifest. Read the field's resolver in "
                    "codex-rs/core-plugins/src/manifest.rs — then follow the value PAST the "
                    "rejecter to whatever consumes or defaults it — and add it to PATH_VALUED "
                    "or PLAIN above",
                )

    def test_every_interface_sub_key_is_classified(self):
        # `interface` is the mixed one: 4 paths, 11 plain. Waving the object through as plain is
        # the same silent drop, one level down.
        for plugin, m in sorted(manifests().items()):
            with self.subTest(plugin=plugin):
                self.assertFalse(
                    set(m.get("interface") or {}) - INTERFACE_PATH_VALUED - INTERFACE_PLAIN,
                    "unclassified key under `interface` — classify it against "
                    "resolve_interface_asset_path",
                )

    def test_every_path_valued_string_starts_with_dot_slash(self):
        for plugin, m in sorted(manifests().items()):
            for field, value in path_valued_items(m):
                with self.subTest(plugin=plugin, field=field, value=value):
                    self.assertTrue(
                        value.startswith("./"),
                        f"`{field}: {value}` is dropped by resolve_manifest_path with only a "
                        "tracing::warn. For most fields default discovery quietly covers for it; "
                        "for `commands` nothing does. Emit ./-prefixed paths in "
                        "build.py::codex_manifest",
                    )

    def test_no_path_escapes_the_plugin_root(self):
        # `./` is necessary, not sufficient: `./../x` satisfies the prefix check and then leaves the
        # plugin. Codex's resolver rejects it downstream too, but ours is the tree that must not
        # generate it — a path out of the plugin root resolves into the USER'S project, which is
        # instance 1 of this bug class, reintroduced through the door instance 4 opened.
        for plugin, m in sorted(manifests().items()):
            for field, value in path_valued_items(m):
                with self.subTest(plugin=plugin, field=field, value=value):
                    self.assertNotIn("..", Path(value).parts)

    def test_every_declared_path_exists(self):
        # `resolve_manifest_path` does no existence check — `./` alone buys nothing if the target is
        # missing. Codex will not tell us; the fallbacks will not either, because a declared-and-
        # resolvable path SUPPRESSES default discovery rather than supplementing it
        # (`plugin_skill_roots` is `if empty { default } else { manifest }` — a replacement, despite
        # OpenAI's own published spec claiming the opposite).
        for plugin, m in sorted(manifests().items()):
            for field, value in path_valued_items(m):
                with self.subTest(plugin=plugin, field=field, value=value):
                    self.assertTrue((PLUGINS / plugin / value).exists(),
                                    f"{plugin}'s manifest declares {field} -> {value}, which is "
                                    "not in the shipped tree")


class TestTheManifestActuallyDeclaresSomething(unittest.TestCase):
    """Every assertion above passes on an empty manifest — which is exactly what the bug shipped."""

    def test_every_plugin_declares_its_skills_to_codex(self):
        for plugin, m in sorted(manifests().items()):
            with self.subTest(plugin=plugin):
                claude = json.loads(
                    (PLUGINS / plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
                )
                if not (PLUGINS / plugin / "skills").is_dir():
                    continue
                self.assertTrue(
                    m.get("skills"),
                    f"{plugin} ships skills/ but its Codex manifest declares none — Codex users "
                    "install this plugin and get an empty directory",
                )
                self.assertEqual(
                    len(m["skills"]), len(list((PLUGINS / plugin / "skills").iterdir())),
                    "every skill on disk must be declared; Codex has no directory scan",
                )
                # Not a parity check of two hand-kept lists: one generator emits both manifests, so
                # a count that diverges means the generator forgot a host, which is the failure
                # this whole file exists for.
                self.assertEqual(m["name"], claude["name"])

    def test_the_plugin_that_declares_servers_points_codex_at_them(self):
        for plugin, m in sorted(manifests().items()):
            if not (PLUGINS / plugin / ".mcp.json").exists():
                continue
            with self.subTest(plugin=plugin):
                self.assertEqual(m.get("mcpServers"), "./.mcp.json")


class TestTheMarketplaceCanActuallyFetchEveryPlugin(unittest.TestCase):
    """The catalog is self-contained: every plugin in it is ours, fetched from this repo.

    **The rule:** a programmer and their coding agent get everything they need by installing our
    plugins. No external plugin, ever. So the marketplace advertises nothing it does not ship.

    This class was born guarding the opposite. The catalog carried a `superpowers` entry under the
    banner *"generic engineering skills are COMPOSED, not reinvented here"*, and its `source` was
    `"github:obra/superpowers"` — a shorthand that does not exist. Anthropic's table
    (code.claude.com `/en/plugin-marketplaces#plugin-sources`) gives a **string** source as a
    relative path that *"Must start with `./`"*, and every git host as an **object**. So the entry
    could not be fetched at all.

    Nobody noticed for months, because **nobody needed it**: no plugin declared it in
    `dependencies`, and no file in `src/` named one of its skills. Four documents asserted a
    mechanism that did not exist — this repo's own failure mode, printed on the shop window.

    And fixing the syntax would have been the wrong repair. A dependency installs the WHOLE plugin:
    16 skills, of which `brainstorming`, `writing-plans`/`executing-plans` and
    `subagent-driven-development` are **stateless twins** of `core/brainstorm.md`, `buildloop.py`
    and `core/agents.md`. None can write to the ledger. A forgetting twin beside the single source
    of truth is precisely the divergence this package exists to find in other people's codebases.

    So the invariant below is the doctrine, mechanised: **no source may leave this repo.** The
    generic skills are authored here and bound to the ledger — which is why they are not a
    reinvention: superpowers' TDD cannot make its red step an `acceptance_criterion` pin, and ours
    is nothing but that.
    """

    def sources(self) -> list:
        m = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        return [(p["name"], p["source"]) for p in m["plugins"]]

    def test_no_source_leaves_this_repo(self):
        # The doctrine, as a carrier check. Every non-`./` source type Anthropic defines — `github`,
        # `url`, `git-subdir`, `npm` — is by construction a plugin we do not ship and cannot pin to
        # our own tests. One appearing here means "install our plugins and you have everything"
        # stopped being true, and it must fail loudly rather than be discovered by a user.
        for name, src in self.sources():
            with self.subTest(plugin=name):
                self.assertIsInstance(
                    src, str,
                    f"{name}: an object source fetches a plugin from outside this repo. Our "
                    "catalog ships only what we author — if this skill is needed, write it here "
                    "and bind it to the ledger",
                )
                self.assertTrue(
                    src.startswith("./"),
                    f"{name}: a STRING source is a relative path and must start with './'. "
                    f"Got {src!r} — `github:owner/repo` is not a source form that exists",
                )

    def test_every_source_points_at_a_plugin_we_actually_built(self):
        for name, src in self.sources():
            with self.subTest(plugin=name):
                self.assertTrue((ROOT / src / ".claude-plugin" / "plugin.json").is_file(),
                                f"{name}: {src} is not a built plugin")

    def test_the_catalog_lists_exactly_what_we_build(self):
        # Both directions. A plugin we build but never list is unreachable; a plugin we list but
        # never build is the superpowers entry all over again — advertised, unfetchable, unnoticed.
        built = {p.name for p in PLUGINS.iterdir() if (p / ".claude-plugin").is_dir()}
        self.assertEqual({n for n, _ in self.sources()}, built)


if __name__ == "__main__":
    unittest.main()
