"""The package as INSTALLED — the one thing every other gate was blind to.

This repo's defining bug was not a bad line of code: it was that every gate anchored on `__file__`
and validated the repo *as a repo*, while the artifact users actually get is a directory **copied
somewhere else**, driven with the working directory set to **their** project. Nothing checked that,
so `python runtime/ledger.py` shipped for months resolving to `<user-project>/runtime/ledger.py`.

So these tests refuse to run anything in place. They copy `plugins/<name>` to a temp directory —
standing in for `~/.claude/plugins/cache/<id>/` — `chdir` into an unrelated empty project, and only
then ask whether the thing works. If a change breaks install-time resolution again, this fails.
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"

# Artifacts that describe THIS repo's development. Shipping any of them means a user's install
# carries our build checklist, our linters, or (worst) our MEMORY.md facts about our own repo.
DEV_ARTIFACTS = ("TODO.md", "CLAUDE.md", "MEMORY.md", "CHANGELOG.md", "CONTRIBUTING.md")
DEV_DIRS = ("tests", "evals", "scripts/build.py", "writing-skills", ".github")


class TestBuildOutputIsClean(unittest.TestCase):
    def test_plugins_are_built(self):
        self.assertTrue(PLUGINS.is_dir(), "plugins/ is missing — run: python scripts/build.py")

    def test_no_dev_artifact_ships(self):
        for p in PLUGINS.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(PLUGINS).as_posix()
            with self.subTest(file=rel):
                self.assertNotIn(p.name, DEV_ARTIFACTS, f"{rel} is repo-development, not product")
                for d in DEV_DIRS:
                    self.assertNotIn(d, rel, f"{rel} is repo-development, not product")

    def test_the_skill_that_documents_this_repo_does_not_ship(self):
        # writing-skills names CONTRIBUTING.md + CLAUDE.md as its authority and tells the reader to
        # run our consistency linters. It is our contributor guide wearing a skill's clothes.
        self.assertEqual(list(PLUGINS.rglob("writing-skills")), [])

    def test_build_is_reproducible(self):
        # Generated + committed only works if regenerating is a no-op. Otherwise every contributor
        # produces a different tree and the CI check becomes noise everyone learns to ignore.
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"), "--check"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, f"plugins/ is out of sync with source:\n{r.stdout}")


class TestManifests(unittest.TestCase):
    def _manifest(self, plugin, flavour=".claude-plugin"):
        with open(PLUGINS / plugin / flavour / "plugin.json", encoding="utf-8") as fh:
            return json.load(fh)

    def test_every_plugin_has_both_manifests(self):
        for p in sorted(x for x in PLUGINS.iterdir() if x.is_dir()):
            with self.subTest(plugin=p.name):
                self.assertTrue((p / ".claude-plugin" / "plugin.json").is_file())
                self.assertTrue((p / ".codex-plugin" / "plugin.json").is_file(),
                                "Codex's manifest is near-identical — one generator must emit both")

    def test_workflow_plugins_depend_on_the_core(self):
        # rescue/forge cannot read core's FILES (per-plugin ${CLAUDE_PLUGIN_ROOT}, no marketplace
        # root, no ../ traversal). They reach it through its MCP tools, which are session-global —
        # and `dependencies` is what guarantees it is installed and enabled at all.
        for p in ("codebase-rescue", "greenfield-forge"):
            with self.subTest(plugin=p):
                self.assertIn("alignment-core", self._manifest(p).get("dependencies", []))

    def test_the_core_depends_on_nothing(self):
        self.assertEqual(self._manifest("alignment-core").get("dependencies", []), [])

    def test_marketplace_points_at_every_built_plugin(self):
        with open(ROOT / ".claude-plugin" / "marketplace.json", encoding="utf-8") as fh:
            market = json.load(fh)
        sources = {e["source"] for e in market["plugins"] if isinstance(e["source"], str)}
        for p in sorted(x.name for x in PLUGINS.iterdir() if x.is_dir()):
            with self.subTest(plugin=p):
                self.assertIn(f"./plugins/{p}", sources)

    def test_mcp_server_path_is_plugin_root_anchored(self):
        # The whole bug class in one assertion: a repo-relative path here resolves into the USER'S
        # project at runtime, because that is what the working directory is.
        with open(PLUGINS / "alignment-core" / ".mcp.json", encoding="utf-8") as fh:
            entry = json.load(fh)["mcpServers"]["codebase-alignment"]
        self.assertEqual(entry["command"], "uv", "zero-install depends on uv resolving PEP 723")
        joined = " ".join(entry["args"])
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", joined)
        self.assertNotIn("src/", joined, "src/ is authoring source and never ships")


class TestRunsFromAnInstalledLocation(unittest.TestCase):
    """Copy the plugin out, chdir into a foreign project, and only then ask if it works.

    The CLI floor is gone: the channel is the MCP server, so what must survive the copy is the
    server importing its vendored runtime from a foreign cwd — the same regression class (a bare
    `runtime/` on sys.path would hit the *user's* tree), one channel over."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.cache = os.path.join(cls.tmp, "cache")        # stands in for ~/.claude/plugins/cache/
        cls.userproj = os.path.join(cls.tmp, "userproj")  # stands in for the user's repo
        os.makedirs(cls.cache)
        os.makedirs(cls.userproj)
        # The MCP server ships in alignment-core; the workflow skill ships beside it. Copy both:
        # the server + its runtime is what must run, the skill is what must name no dead CLI path.
        shutil.copytree(PLUGINS / "alignment-core", os.path.join(cls.cache, "alignment-core"))
        shutil.copytree(PLUGINS / "codebase-rescue", os.path.join(cls.cache, "codebase-rescue"))
        cls.mcp = os.path.join(cls.cache, "alignment-core", "mcp")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_runtime_is_vendored_where_the_server_imports_it(self):
        # Not "somewhere in the plugin" — beside the server (mcp/runtime/), because that is the dir
        # tools.py puts on sys.path. This is the payload that makes one server work on every host.
        self.assertTrue(os.path.isfile(os.path.join(self.mcp, "server.py")), "server.py not vendored")
        self.assertTrue(os.path.isfile(os.path.join(self.mcp, "tools.py")), "tools.py not vendored")
        rt = os.path.join(self.mcp, "runtime")
        for mod in ("ledger.py", "shapes.py", "map.py"):
            self.assertTrue(os.path.isfile(os.path.join(rt, mod)), f"{mod} not vendored beside the server")

    def test_the_tool_layer_imports_its_runtime_from_a_foreign_cwd(self):
        # The regression that started all of this, in its post-CLI form: tools.py adds mcp/runtime to
        # sys.path and the runtime imports its siblings flatly (`from ledger import Ledger`). Run it
        # with the cwd set to an unrelated project — a bare `runtime/` would resolve to
        # <userproj>/runtime, not the vendored one. No uv needed: this is the library layer, which is
        # exactly the part that must survive the copy; the FastMCP wrapper is tested in test_mcp_server.
        code = (
            "import sys; sys.path.insert(0, r'%s'); "
            "import tools; import buildloop; "                 # buildloop imports ledger flatly
            "print('ok', tools.ledger_summary.__name__, buildloop.__name__)" % self.mcp
        )
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=self.userproj)
        self.assertEqual(r.returncode, 0, f"vendored tool layer failed to import from a foreign cwd:\n{r.stderr}")
        self.assertIn("ok ledger_summary buildloop", r.stdout)

    def test_no_shipped_file_names_a_repo_relative_runtime_path(self):
        # verify_commands.py enforces this on the source; this asserts it survived the build, since
        # the build is what a user actually receives. With the CLI gone, `scripts/runtime/` is a
        # dangling instruction too, so it joins the forbidden set.
        bad = []
        for p in Path(self.cache).rglob("*.md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for needle in ("python runtime/", "python3 runtime/", "python scripts/runtime/",
                           "python3 scripts/runtime/", "bash scripts/bootstrap.sh"):
                if needle in text:
                    bad.append(f"{p.relative_to(self.cache)}: {needle}")
        self.assertEqual(bad, [], "shipped prose still names a path that cannot resolve after install")


if __name__ == "__main__":
    unittest.main()
