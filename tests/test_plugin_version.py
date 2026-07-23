"""A host decides "do I need to update?" by comparing the version STRING, and nothing else.

This is the sixth instance of this repo's signature bug — an artifact that claims something the
shipped bytes do not do, staying green throughout — and the first one where the *host itself*
reports the false claim out loud. `claude plugin update` on an install 51 commits and 202 files
behind printed, four times in a row:

    √ codebase-rescue is already at the latest version (0.1.0).

It was not the latest version. It was `c621f45` against a `4d80d27` HEAD. The CLI was not wrong
either: `VERSION` had never moved since the first build, so `0.1.0` really did equal `0.1.0`. Both
halves were internally consistent and their conjunction shipped stale bytes to every installed copy,
including ours. `build.py --check` was green the whole time, because it asks whether `plugins/`
matches `src/` — never whether the number attached to `plugins/` still means anything.

**Why the existing gates all miss it, precisely.** Every one of them is a *correspondence* check
between two things in this repo: modules ↔ references, `src/` ↔ `plugins/`, pointers ↔ files. The
version is not a correspondence — it is a claim about a **previous release**, an object that lives
outside the working tree. No amount of checking the tree against itself can evaluate it. That is
also why the fix needs an anchor with the release in it.

**The anchor is a git tag, and the carrier is the tree object.** `claude plugin tag` writes
`{name}--v{version}` at release; `git diff <tag> -- plugins/<name>` asks git — not a heuristic, not
a string match, not a mtime — whether the bytes under that path still equal the bytes that shipped
under that number. Content moved while the number stood still is the *only* failure this file
reports, and it is exactly the condition under which a host lies to a user.

    tag foo--v0.2.0 exists, VERSION == 0.2.0, plugins/foo changed  ->  FAIL, bump VERSION
    VERSION == 0.3.0, no foo--v0.3.0 tag yet                       ->  pass, unreleased by definition

The second line is not a loophole. An untagged version was never served to anyone, so no install can
be holding it, so there is nothing for a host to compare wrongly. The gate arms itself the moment a
release exists and disarms the moment the number moves — which is precisely the window in which the
mistake is possible.

**Untracked files are checked separately and this is load-bearing.** `git diff <tag> -- <path>`
compares the working tree against the tag but is blind to files git has never seen, and a NEW
generated file is a perfectly good staleness carrier — `build.py` adds those routinely (six Codex
agent TOMLs and `core/model-tiers.md` arrived exactly that way in the window above). A gate that
inspects only known files would have waved that release through.

**The residual, named rather than papered over.** This binds the version to the tag; it cannot bind
the tag to the release. Ship without ever running `claude plugin tag` and every check here skips
forever, silently — the same self-healing silence `test_codex_manifest.py` warns about. There is no
carrier inside the repo for "a release happened", so this is a discipline, not a gate: **tag at
release, or this file is decoration.** `git tag {name}--v{VERSION}` on the release commit, one per
plugin, is the whole obligation.

CI must fetch tags for any of this to run. `actions/checkout@v4` defaults to `fetch-depth: 1` and
brings none, so the workflow pins `fetch-depth: 0`; without it every assertion below skips green.
"""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"


def git(*args):
    """Run git in the repo. Returns (exit_code, stdout). Never raises — a missing git is a skip."""
    try:
        p = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        return None, ""
    return p.returncode, p.stdout.strip()


class PluginVersionTracksContent(unittest.TestCase):
    def setUp(self):
        code, _ = git("rev-parse", "--git-dir")
        if code != 0:
            self.skipTest("not a git checkout — the anchor is a tag, so there is nothing to compare")
        self.plugins = sorted(p for p in PLUGINS.iterdir() if p.is_dir())
        self.assertTrue(self.plugins, "plugins/ is empty — run scripts/build.py")

    def _version(self, plugin: Path) -> str:
        """The version a host actually reads: the one in the shipped manifest, not build.py's constant."""
        manifest = plugin / ".claude-plugin" / "plugin.json"
        self.assertTrue(manifest.is_file(), f"{plugin.name}: no .claude-plugin/plugin.json")
        return json.loads(manifest.read_text(encoding="utf-8"))["version"]

    def test_released_version_still_matches_its_content(self):
        """If a tag claims this version shipped, the bytes under it must still be those bytes."""
        for plugin in self.plugins:
            with self.subTest(plugin=plugin.name):
                version = self._version(plugin)
                tag = f"{plugin.name}--v{version}"
                code, _ = git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
                if code != 0:
                    self.skipTest(f"{tag} does not exist — this version was never released")

                rel = f"plugins/{plugin.name}"
                changed, _ = git("diff", "--quiet", tag, "--", rel)
                self.assertEqual(
                    changed, 0,
                    f"{rel} differs from what shipped as {version}, but the version is still {version}. "
                    f"A host compares the string alone, so every installed copy will be told it is "
                    f"already up to date. Bump VERSION in scripts/build.py and rebuild.")

                _, untracked = git("ls-files", "--others", "--exclude-standard", "--", rel)
                self.assertEqual(
                    untracked, "",
                    f"{rel} has files git has never seen, so the diff above could not weigh them:\n"
                    f"{untracked}\nCommit them (they are build output) or bump VERSION.")

    def test_every_plugin_is_stamped_with_the_same_version(self):
        """One constant stamps all four. A per-plugin version would need a per-plugin bump rule."""
        versions = {p.name: self._version(p) for p in self.plugins}
        self.assertEqual(
            len(set(versions.values())), 1,
            f"plugins disagree on the version they ship: {versions}. They are stamped from one "
            f"VERSION in scripts/build.py; a split means something was hand-edited.")

    def test_marketplace_serves_the_version_the_plugins_carry(self):
        """The marketplace entry is what a host reads BEFORE fetching; the manifest is what it gets.

        These are two separate files making the same claim, and the marketplace's is the one that
        decides whether an update is even attempted. Disagreement means the host resolves an update
        it will then refuse, or skips one it needed."""
        marketplace = ROOT / ".claude-plugin" / "marketplace.json"
        self.assertTrue(marketplace.is_file(), "no root .claude-plugin/marketplace.json")
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        for entry in data["plugins"]:
            with self.subTest(plugin=entry["name"]):
                self.assertEqual(
                    entry["version"], self._version(PLUGINS / entry["name"]),
                    f"marketplace advertises {entry['name']} at {entry['version']}, the plugin "
                    f"manifest says otherwise")


if __name__ == "__main__":
    unittest.main()
