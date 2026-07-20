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
    """Copy the plugin out, chdir into a foreign project, and only then ask if it works."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.cache = os.path.join(cls.tmp, "cache")        # stands in for ~/.claude/plugins/cache/
        cls.userproj = os.path.join(cls.tmp, "userproj")  # stands in for the user's repo
        os.makedirs(cls.cache)
        os.makedirs(cls.userproj)
        shutil.copytree(PLUGINS / "codebase-rescue", os.path.join(cls.cache, "codebase-rescue"))
        cls.skill = os.path.join(cls.cache, "codebase-rescue", "skills", "codebase-rescue")
        cls.rt = os.path.join(cls.skill, "scripts", "runtime")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _ledger(self):
        sys.path.insert(0, self.rt)
        try:
            from ledger import Ledger
        finally:
            sys.path.pop(0)
        path = os.path.join(tempfile.mkdtemp(), "ledger.json")
        led = Ledger(path)
        led.add_pin(kind="contract_mismatch", title="users.email nullable in DB, required in API",
                    severity="high", confidence="extracted",
                    provenance=[{"source": "contract_recon", "detail": "db<->api shape diff"}])
        led.save()
        return path

    def test_the_runtime_is_vendored_into_the_skill(self):
        # Not "somewhere in the plugin" — inside the SKILL. Every agent resolves a skill's assets
        # relative to the skill's own directory, which is what makes one payload work on all four.
        self.assertTrue(os.path.isdir(self.rt), "scripts/runtime/ missing from the shipped skill")
        for mod in ("ledger.py", "shapes.py", "map.py"):
            self.assertTrue(os.path.isfile(os.path.join(self.rt, mod)), f"{mod} not vendored")

    def test_vendored_cli_runs_with_the_cwd_set_to_a_foreign_project(self):
        # The regression that started all of this: `python runtime/ledger.py` from here would hit
        # <userproj>/runtime/ledger.py — absent, or worse, someone else's script.
        led = self._ledger()
        r = subprocess.run([sys.executable, os.path.join(self.rt, "ledger.py"), "summary", led],
                           capture_output=True, text=True, cwd=self.userproj)
        self.assertEqual(r.returncode, 0, f"vendored ledger.py failed from a foreign cwd:\n{r.stderr}")
        self.assertTrue(json.loads(r.stdout), "summary of a ledger with a pin must not be empty")

    def test_flat_imports_survive_vendoring(self):
        # The runtime imports siblings flatly (`from ledger import Ledger`) because each module is
        # invoked as a script, which puts its own dir on sys.path[0]. Vendoring must not break that.
        led = self._ledger()
        r = subprocess.run([sys.executable, os.path.join(self.rt, "buildloop.py"), led],
                           capture_output=True, text=True, cwd=self.userproj)
        self.assertEqual(r.returncode, 0,
                         f"buildloop.py imports ledger.py flatly; vendoring broke it:\n{r.stderr}")

    def test_the_map_renders_self_contained_from_an_install(self):
        led = self._ledger()
        out = os.path.join(self.tmp, "map.html")
        r = subprocess.run([sys.executable, os.path.join(self.rt, "map.py"), led, "-o", out],
                           capture_output=True, text=True, cwd=self.userproj)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as fh:
            html = fh.read()
        self.assertNotIn("<script src=", html, "the map must not fetch anything at view time")

    def test_no_shipped_file_names_a_repo_relative_runtime_path(self):
        # verify_commands.py enforces this on the source; this asserts it survived the build, since
        # the build is what a user actually receives.
        bad = []
        for p in Path(self.cache).rglob("*.md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for needle in ("python runtime/", "python3 runtime/", "bash scripts/bootstrap.sh"):
                if needle in text:
                    bad.append(f"{p.relative_to(self.cache)}: {needle}")
        self.assertEqual(bad, [], "shipped prose still names a path that cannot resolve after install")


if __name__ == "__main__":
    unittest.main()
