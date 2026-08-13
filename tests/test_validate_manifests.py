"""A gate is only worth its CI minute if its failure path has been observed at least once.

`scripts/validate_manifests.py` reports nothing on the tree as committed, which is the intended
steady state and also the exact condition under which a broken linter is indistinguishable from a
working one. Every prior instance of this repo's signature bug was a check that stayed green while
asserting nothing — twenty-one skipped tree-sitter tests, three inert Codex declarations, a
`python runtime/ledger.py` that could not resolve after install. So half of this file is the happy
path and half plants violations and demands they be reported.

The violations are planted on a **minimal synthetic tree**, not on a copy of `plugins/`, and that
is a deliberate choice with two payoffs. It is 6 files instead of 304, so each test builds its own
fixture and nothing leaks between them. More importantly it keeps the gate honest about its own
generality: a fixture written from the published schema rather than from our output cannot pass by
accidentally agreeing with `build.py`. The fixture is asserted clean first — a baseline that is
already red would make every mutation below prove nothing.

One structural note. `validate()` takes the tree as an argument precisely so this file exists;
`main()` is a thin printer over it. That shape was chosen for testability, and the alternative —
module constants resolved from `__file__` — is the shape that made every earlier gate in this repo
blind to anything but its own checkout.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validate_manifests as V  # noqa: E402


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def fixture(tmp: Path) -> Path:
    """A minimal, valid two-plugin tree: a core with an MCP server and a dependant.

    Deliberately NOT a copy of ours. It encodes the published schema — `name` kebab-case, one
    shared semver, a `./`-prefixed marketplace source, a dependency that resolves inside the tree —
    so a mutation below fails for the reason named, not because our own layout drifted.
    """
    write(tmp / "plugins" / "demo-core" / ".claude-plugin" / "plugin.json", {
        "name": "demo-core", "version": "1.2.3", "description": "core", "dependencies": [],
    })
    (tmp / "plugins" / "demo-core" / "skills").mkdir(parents=True)
    write(tmp / "plugins" / "demo-core" / ".mcp.json", {
        "mcpServers": {"demo": {"type": "stdio", "command": "uv", "args": ["run"]}},
    })

    write(tmp / "plugins" / "demo-kit" / ".claude-plugin" / "plugin.json", {
        "name": "demo-kit", "version": "1.2.3", "description": "kit",
        "dependencies": ["demo-core"],
    })
    (tmp / "plugins" / "demo-kit" / "skills").mkdir(parents=True)

    write(tmp / ".claude-plugin" / "marketplace.json", {
        "name": "demo-market", "version": "1.2.3", "owner": {"name": "someone"},
        "plugins": [
            {"name": "demo-core", "source": "./plugins/demo-core", "version": "1.2.3"},
            {"name": "demo-kit", "source": "./plugins/demo-kit", "version": "1.2.3"},
        ],
    })
    return tmp


def mutate(tmp: Path, relative: str, change) -> None:
    """Read a manifest, hand it to `change`, write it back. Violations are planted one at a time."""
    path = tmp / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    write(path, data)


class TestTheRealTreeIsClean(unittest.TestCase):
    def test_the_committed_plugins_pass(self):
        found, plugins, entries, servers = V.validate(ROOT)
        self.assertEqual(found, [], "\n".join(found))
        # Non-vacuity, in the same breath as the pass. Every assertion in the validator is satisfied
        # by an empty tree; a green run that checked nothing is the failure this suite is about.
        self.assertGreaterEqual(plugins, 1)
        self.assertEqual(plugins, entries, "every built plugin is listed and vice versa")
        self.assertGreaterEqual(servers, 1, "keel-core declares MCP servers — if this drops to 0 "
                                            "the .mcp.json half of the gate went silent")

    def test_an_empty_tree_is_an_error_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "plugins").mkdir()
            found, *_ = V.validate(Path(tmp))
            self.assertTrue(found, "a plugins/ with nothing in it must fail loudly — a gate that "
                                   "passes on an empty tree cannot tell 'clean' from 'absent'")


class TestTheFixtureIsAnHonestBaseline(unittest.TestCase):
    def test_a_minimal_valid_tree_reports_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            found, plugins, entries, servers = V.validate(fixture(Path(tmp)))
            self.assertEqual(found, [], "\n".join(found))
            self.assertEqual((plugins, entries, servers), (2, 2, 1))


class TestPlantedViolationsAreReported(unittest.TestCase):
    """One mutation per test, each on a fresh fixture, each asserting the substring that names it."""

    def plant(self, change_relative: str, change) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            tree = fixture(Path(tmp))
            mutate(tree, change_relative, change)
            found, *_ = V.validate(tree)
            self.assertTrue(found, "the planted violation was not reported")
            return "\n".join(found)

    CORE = "plugins/demo-core/.claude-plugin/plugin.json"
    MARKET = ".claude-plugin/marketplace.json"

    def test_unrecognized_field(self):
        # Claude Code ignores it at load; only `--strict` warns, and that job cannot block. This is
        # the whole reason the script exists, so it is the first thing asserted.
        out = self.plant(self.CORE, lambda m: m.update({"mcpSevers": "./.mcp.json"}))
        self.assertIn("mcpSevers", out)

    def test_recognized_field_with_the_wrong_type(self):
        # The docs' own example of a LOAD failure rather than a warning.
        out = self.plant(self.CORE, lambda m: m.update({"keywords": "not-an-array"}))
        self.assertIn("keywords", out)

    def test_name_that_is_not_kebab_case(self):
        out = self.plant(self.CORE, lambda m: m.update({"name": "Demo_Core"}))
        self.assertIn("kebab-case", out)

    def test_name_that_does_not_match_its_directory(self):
        out = self.plant(self.CORE, lambda m: m.update({"name": "something-else"}))
        self.assertIn("does not match the directory", out)

    def test_version_that_is_not_semver(self):
        out = self.plant(self.CORE, lambda m: m.update({"version": "1.2"}))
        self.assertIn("not semver", out)

    def test_versions_that_diverge_between_plugins(self):
        # `build.py --check` cannot see this: it proves plugins/ equals what the generator emits,
        # and a generator with a per-plugin version passes it.
        out = self.plant("plugins/demo-kit/.claude-plugin/plugin.json",
                         lambda m: m.update({"version": "9.9.9"}))
        self.assertIn("do not share one version", out)

    def test_dependency_that_leaves_this_repo(self):
        # The doctrine of test_codex_manifest.py::test_no_source_leaves_this_repo, applied to the
        # other door out.
        out = self.plant("plugins/demo-kit/.claude-plugin/plugin.json",
                         lambda m: m.update({"dependencies": ["superpowers"]}))
        self.assertIn("superpowers", out)

    def test_dependency_version_that_is_not_a_semver_range(self):
        """The one manifest string generated by string surgery, and until now read by nothing.

        `build.py` emits `{"name": "keel-core", "version": <derived>}` from
        `f"^{'.'.join(VERSION.split('.')[:2])}"` — so the string moves with VERSION and is not
        quoted here, where it would rot. A one-part VERSION makes that `^0.`, which is
        valid JSON, a recognized field, the right type, and a `range-conflict` that DISABLES the
        plugin on the user's machine. Every other gate here would have stayed green.
        """
        for bad in ("^0.", "~>2.0", "latest", ""):
            with self.subTest(range=bad):
                out = self.plant("plugins/demo-kit/.claude-plugin/plugin.json",
                                 lambda m, b=bad: m.update(
                                     {"dependencies": [{"name": "demo-core", "version": b}]}))
                self.assertIn("not a semver RANGE", out)

    def test_the_range_forms_the_docs_name_are_all_accepted(self):
        """The mirror half, and the one that matters more: a validator that rejects the syntax the
        host documents is worse than none, because it makes the correct manifest unwritable. These
        are the four spellings the dependency docs give by name, plus the two shapes `SEMVER`
        (which is for a plugin's own `version`) would refuse — which is why this is a second regex
        rather than a reuse of that one."""
        for good in ("~2.1.0", "^2.0", ">=1.4", "=2.1.0", "^0.6", "1.2.3 - 2.3.4", "*"):
            with self.subTest(range=good):
                with tempfile.TemporaryDirectory() as tmp:
                    tree = fixture(Path(tmp))
                    mutate(tree, "plugins/demo-kit/.claude-plugin/plugin.json",
                           lambda m, g=good: m.update(
                               {"dependencies": [{"name": "demo-core", "version": g}]}))
                    found, *_ = V.validate(tree)
                    self.assertEqual(found, [], f"{good} is a documented range")

    def test_path_field_without_the_required_prefix(self):
        out = self.plant(self.CORE, lambda m: m.update({"skills": ["skills/"]}))
        self.assertIn("must start with `./`", out)

    def test_path_field_that_escapes_the_plugin_root(self):
        out = self.plant(self.CORE, lambda m: m.update({"skills": ["./../elsewhere"]}))
        self.assertIn("escapes the plugin root", out)

    def test_declared_path_that_is_not_on_disk(self):
        out = self.plant(self.CORE, lambda m: m.update({"commands": ["./commands/deploy.md"]}))
        self.assertIn("not in the shipped tree", out)

    def test_plugin_that_ships_no_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = fixture(Path(tmp))
            (tree / "plugins" / "demo-kit" / "skills").rmdir()
            found, *_ = V.validate(tree)
            self.assertIn("contributes nothing", "\n".join(found))

    def test_mcp_server_with_no_type(self):
        out = self.plant("plugins/demo-core/.mcp.json",
                         lambda m: m["mcpServers"]["demo"].pop("type"))
        self.assertIn("declares type None", out)

    def test_mcp_stdio_server_with_no_command(self):
        out = self.plant("plugins/demo-core/.mcp.json",
                         lambda m: m["mcpServers"]["demo"].pop("command"))
        self.assertIn("has no `command`", out)

    def test_mcp_file_that_is_not_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = fixture(Path(tmp))
            (tree / "plugins" / "demo-core" / ".mcp.json").write_text("{oops", encoding="utf-8")
            found, *_ = V.validate(tree)
            self.assertIn("not valid JSON", "\n".join(found))

    def test_reserved_marketplace_name(self):
        out = self.plant(self.MARKET, lambda m: m.update({"name": "anthropic-plugins"}))
        self.assertIn("reserved for Anthropic", out)

    def test_marketplace_without_an_owner(self):
        out = self.plant(self.MARKET, lambda m: m.pop("owner"))
        self.assertIn("`owner` is required", out)

    def test_entry_version_that_contradicts_the_plugin(self):
        # `plugin.json` wins, so the catalog would advertise a version nobody receives.
        out = self.plant(self.MARKET, lambda m: m["plugins"][0].update({"version": "4.5.6"}))
        self.assertIn("advertising a version no user receives", out)

    def test_built_plugin_missing_from_the_catalog(self):
        out = self.plant(self.MARKET, lambda m: m["plugins"].pop())
        self.assertIn("built but not listed", out)

    def test_catalog_entry_with_no_plugin_behind_it(self):
        out = self.plant(self.MARKET, lambda m: m["plugins"].append(
            {"name": "ghost-plugin", "source": "./plugins/ghost-plugin"}))
        self.assertIn("listed but not built", out)

    def test_entry_without_a_source(self):
        out = self.plant(self.MARKET, lambda m: m["plugins"][0].pop("source"))
        self.assertIn("has no `source`", out)


if __name__ == "__main__":
    unittest.main()
