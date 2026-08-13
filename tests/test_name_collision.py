"""A shipped skill whose name a bundled command already owns must be TAUGHT namespaced.

The instance, verified at Claude Code's own precedence table rather than remembered:

  * *"A skill at any of these levels also overrides a bundled skill with the same name. For example,
    a `code-review` skill in your project's `.claude/skills/` replaces the bundled `/code-review`."*
  * *"Plugin skills use a `plugin-name:skill-name` namespace, so they can't conflict with other
    levels."*
  * *"The bare `/fancy` also invokes the skill unless another command already uses that name."*
    — `https://code.claude.com/docs/en/skills`

So `/keel-kit:code-review` always resolves and the bare `/code-review` runs **Anthropic's**, with
nothing telling the operator which one they got. `docs/open-gaps.md` §31 recorded the decision — keep
the name, because it is what the skill *is*, and teach the qualified form — and prose that carries a
decision with no gate is the shape this repo keeps finding in other people's repos. This is the gate.

Two properties, and the second is the one that survives a future skill nobody has written yet:

  1. the collision set is **derived** — every shipped skill whose name appears in Claude Code's
     bundled command list — rather than a hand-kept list of one; and
  2. for each colliding skill, the router and the owning plugin's README must both spell the
     namespaced form, with the plugin name asked of `build.PLUGINS` instead of typed here.

The declared limit: `BUNDLED` is a copy of somebody else's roster, dated and cited. Claude Code can
add a bundled skill tomorrow and nothing here will notice — that is a fact about their release notes,
not a hole this gate can close, and it is written down rather than left implied.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build as B  # noqa: E402

#: Claude Code's bundled skills/commands, read from its commands reference on **2026-08-13**. The
#: names are the collision surface: a plugin skill sharing one of them loses the bare `/name`, and a
#: skill installed at the personal or project level REPLACES the bundled one outright.
BUNDLED = {
    "batch", "claude-api", "code-review", "dataviz", "debug", "deep-research", "design-sync",
    "doctor", "init", "install-github-app", "loop", "morning", "output-style", "pr-comments",
    "release-notes", "review", "security-review", "simplify", "verify",
}

ROUTER = ROOT / "src" / "skills" / "which-skill" / "SKILL.md"


def _plugin_of(skill: str) -> str:
    for name, spec in B.PLUGINS.items():
        if skill in spec["skills"]:
            return name
    raise AssertionError(f"{skill} ships in no plugin — build.PLUGINS and the skill tree disagree")


class TestCollidingSkillsTeachTheQualifiedName(unittest.TestCase):
    def setUp(self):
        self.colliding = sorted(set(B.shipped_skills()) & BUNDLED)

    def test_there_is_at_least_one_collision_to_check(self):
        """`code-review` is it today. If this ever goes empty the assertions below become vacuous
        and would pass silently, which is the failure mode every gate here is written against."""
        self.assertTrue(self.colliding,
                        "no shipped skill collides with a bundled name — either the roster changed "
                        "or BUNDLED went stale; do not delete this file, re-derive it")

    def test_the_router_spells_the_namespaced_command(self):
        text = ROUTER.read_text(encoding="utf-8")
        for skill in self.colliding:
            with self.subTest(skill=skill):
                qualified = f"/{_plugin_of(skill)}:{skill}"
                self.assertIn(
                    qualified, text,
                    f"{ROUTER.name} names `{skill}` without ever spelling `{qualified}`. The bare "
                    f"command runs Claude Code's bundled skill instead, silently — the map is the "
                    f"one place the operator looks to find out.")

    def test_the_plugin_readme_spells_it_too(self):
        """The router is for someone already inside the package; the README is what a chooser
        reads. Both name the skill, so both have to name the door that actually opens it."""
        for skill in self.colliding:
            with self.subTest(skill=skill):
                plugin = _plugin_of(skill)
                readme = ROOT / "src" / "readme" / f"{plugin}.md"
                self.assertIn(f"/{plugin}:{skill}", readme.read_text(encoding="utf-8"),
                              f"{readme.name} documents `{skill}` without the namespaced command")

    def test_packaging_documents_the_override_install_path(self):
        """The sharper half of the same residual: `scripts/install.sh` takes the target directory as
        its first argument, so `bash scripts/install.sh ~/.claude/skills` places every skill at the
        PERSONAL level — where ours does not merely lose the bare name, it replaces the bundled
        `/code-review` in every project the user opens, with no warning from any host. That is an
        install path this repo makes reachable in one argument, so this repo has to document it."""
        packaging = (ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")
        self.assertIn("~/.claude/skills", packaging,
                      "docs/packaging.md never mentions the install target that overrides a bundled "
                      "skill — the one collision case the plugin namespace does NOT save")
        for skill in self.colliding:
            with self.subTest(skill=skill):
                self.assertIn(skill, packaging)

    def _install(self, target: Path, *flags: str, env: dict | None = None):
        """Run the real installer at `target`, with every host directory it writes to redirected
        into the same throwaway tree. Nothing here may touch the developer's own `~`."""
        home = target.parent
        environment = dict(os.environ,
                           HOME=str(home), OPENCODE_DIR=str(home / "opencode"),
                           PI_DIR=str(home / "pi"), CODEX_DIR=str(home / "codex"), **(env or {}))
        return subprocess.run([shutil.which("bash") or "bash",
                               str(ROOT / "scripts" / "install.sh"), str(target), *flags],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              env=environment)

    def test_the_installer_itself_refuses_the_override_by_default(self):
        """The other half of the same residual, and the half that reaches somebody.

        The test above proves this repo *documents* the override. A document is not where the
        person about to run the command is looking: they are at a terminal with a path in their
        hand. So the script says it too, and — because a warning that scrolls past is a warning an
        unattended run cannot read — it **refuses** unless told otherwise.

        Asserted by RUNNING it, which this test claimed to do while matching three substrings of the
        script's source: `.claude/`, `--claude-personal`, `-t 0`. Turning `exit 3` into `exit 0`, or
        inverting the guard's own condition, leaves all three present and the test green — a gate
        that passes on a guard someone disarmed is the source-text anti-pattern
        `tests/test_app_javascript.py` quotes `test_map.py` about (*"would pass on a renderer that
        never runs"*). Two legs, because the guard is two facts: with no tty and no flag it refuses
        and places nothing, and the opt-in is a real door rather than a documented one.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "home" / ".claude" / "skills"
            r = self._install(target)
            self.assertEqual(r.returncode, 3,
                             f"install.sh did not refuse an override target — it exited "
                             f"{r.returncode}.\n{r.stdout}\n{r.stderr}")
            self.assertFalse(target.exists() and any(target.iterdir()),
                             "install.sh refused and placed something anyway; 'nothing was placed' "
                             "is the sentence it prints and the property that matters")
            self.assertIn(".claude", r.stderr, "the refusal never says what it objected to")

    def test_the_opt_in_is_a_door_and_not_only_a_documented_one(self):
        """`--claude-personal` must actually get through, or the guard is a wall with a sign on it.

        The same run proves the other half of the refusal above: the skills DO land when somebody
        means it, so the empty directory in that test is the guard's doing and not a broken script.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "home" / ".claude" / "skills"
            r = self._install(target, "--claude-personal")
            self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
            placed = sorted(p.name for p in target.iterdir()) if target.exists() else []
            self.assertTrue(placed, "the opt-in got through and placed no skill at all")
            self.assertIn("code-review", placed,
                          "the skill whose bundled twin this whole guard is about did not land, so "
                          "the run proves nothing about the override it warns of")


if __name__ == "__main__":
    unittest.main()
