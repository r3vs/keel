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

import sys
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

    def test_the_installer_itself_refuses_the_override_by_default(self):
        """The other half of the same residual, and the half that reaches somebody.

        The test above proves this repo *documents* the override. A document is not where the
        person about to run the command is looking: they are at a terminal with a path in their
        hand. So the script says it too, and — because a warning that scrolls past is a warning an
        unattended run cannot read — it **refuses** unless told otherwise.

        Asserted as behaviour rather than as wording: a target with a `.claude` component, an
        explicit opt-in flag, and a default that is refusal. What the message says is prose and may
        be improved; that there is a branch at all is the gate.
        """
        script = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn(".claude/", script,
                      "scripts/install.sh does not look at its target at all — pointing it at "
                      "~/.claude/skills replaces the bundled /code-review with no warning from "
                      "any host, and now from us either")
        self.assertIn("--claude-personal", script,
                      "there is no way to mean it: a guard with no opt-in is a guard someone "
                      "removes rather than satisfies")
        self.assertRegex(script, r"-t 0",
                         "the guard does not distinguish a person from a script; a non-interactive "
                         "run must refuse rather than fall through to the override")


if __name__ == "__main__":
    unittest.main()
