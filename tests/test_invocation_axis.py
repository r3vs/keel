"""A skill's invocation choice is authored once and reaches every host that has a mechanism.

The axis: **model-invoked** (the host may fire the skill, and so may the human) vs **user-invoked**
(only the human, by name). It is not a style preference — it decides whether the skill's
`description` sits in the model's context on every turn, and whether another skill or a preloaded
subagent can reach it at all.

Every host fact below was verified at the thing that CONSUMES the value, never at a docs mention:

* **Claude Code** — `disable-model-invocation: true` in the frontmatter. Its own behaviour table
  states the consequence in the column that matters: *"Description not in context"*. It also
  documents two costs this repo has to weigh — the skill is no longer preloaded into a subagent, and
  Claude Code blocks the model's call rather than warning about it.
* **Pi** — reads the **same key**, which is the finding that makes the authored line worth more than
  it looks. `@earendil-works/pi-coding-agent`, `dist/core/skills.js`::

      disableModelInvocation: frontmatter["disable-model-invocation"] === true,
      ...
      const visibleSkills = skills.filter((s) => !s.disableModelInvocation);

  in `formatSkillsForPrompt`, whose own docstring says the excluded skills *"can only be invoked
  explicitly via /skill:name commands"* — the human keeps a door, which is exactly what makes this
  user-invocation rather than deactivation.
* **Codex** — a sidecar instead: `agents/openai.yaml` beside `SKILL.md`, carrying
  `policy.allow_implicit_invocation: false`, documented as *"Codex won't implicitly invoke the skill
  based on user prompt; explicit `$skill` invocation still works."* That is the one host whose shape
  differs, so it is the one thing the build generates.
* **opencode** — the deliberate absence, asserted here so nobody "fixes" it by emitting a permission
  rule. A skill there is reachable ONLY through the model's `skill` tool
  (`packages/opencode/src/tool/skill.ts`, where `ctx.ask({permission: "skill", ...})` fires *inside*
  that tool's `execute`), so there is no human-only door to preserve: denying the skill permission
  removes it from everyone. A disabled skill is not a user-invoked skill, and pretending otherwise
  would ship a third meaning for one word.

What this test locks down is the ONE-SOURCE property, not the mechanism's existence: the frontmatter
key is authored, and Codex's file is derived from it. A hand-written `agents/openai.yaml` that says
`false` for a skill whose frontmatter says nothing is precisely the drift a parity linter would have
to chase, and this repo's rule is to generate instead.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build as B  # noqa: E402

POLICY_LINE = "  allow_implicit_invocation: false"


def _user_invoked(skill: str) -> bool:
    fm = B.FRONTMATTER.match((B.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8"))
    return bool(fm and B.CODEX_POLICY.search(fm.group(1)))


class TestOneSource(unittest.TestCase):
    def test_codex_sidecar_is_generated_for_exactly_the_user_invoked_skills(self):
        """The derivation, in both directions — no sidecar without the key, none missing with it."""
        for skill in B.shipped_skills():
            payload = B.skill_payload(skill)
            has_sidecar = f"skills/{skill}/agents/openai.yaml" in payload
            self.assertEqual(
                has_sidecar, _user_invoked(skill),
                f"{skill}: frontmatter says user-invoked={_user_invoked(skill)} but the build "
                f"{'emits' if has_sidecar else 'omits'} agents/openai.yaml",
            )
            if has_sidecar:
                self.assertIn(POLICY_LINE, payload[f"skills/{skill}/agents/openai.yaml"])

    def test_no_skill_hand_writes_the_sidecar(self):
        """Authoring one by hand would be a second source of truth for one fact."""
        stray = sorted(p.relative_to(ROOT).as_posix()
                       for p in B.SKILLS.rglob("agents/openai.yaml"))
        self.assertEqual(stray, [], "authored Codex sidecars found; set the frontmatter key instead")

    def test_the_shipped_sidecar_is_the_generated_one(self):
        """`build.py --check` covers this repo-wide; this names the file so a failure reads clearly."""
        for plugin in sorted(p.name for p in B.OUT.iterdir() if p.is_dir()):
            for f in sorted((B.OUT / plugin).rglob("agents/openai.yaml")):
                skill = f.parent.parent.name
                self.assertTrue(
                    _user_invoked(skill),
                    f"{f.relative_to(ROOT)} ships for a skill whose frontmatter does not ask for it",
                )
                self.assertIn(POLICY_LINE, f.read_text(encoding="utf-8"))


class TestTheKeyIsSpeltTheWayBothHostsParseIt(unittest.TestCase):
    """Claude Code and Pi both match the literal `disable-model-invocation`, and Pi compares against
    `=== true`. A truthy-but-different value (`yes`, `True`, `1`) is therefore read as *false* by Pi
    while Claude Code's YAML would take it — one authored line, two behaviours. Refuse the shapes
    that split, rather than documenting them."""

    LOOSE = re.compile(r"^disable-model-invocation:\s*(.+?)\s*$", re.M)

    def test_the_value_is_the_bare_lowercase_true(self):
        for skill in sorted(d.name for d in B.SKILLS.iterdir() if d.is_dir()):
            text = (B.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            fm = B.FRONTMATTER.match(text)
            if not fm:
                continue
            for value in self.LOOSE.findall(fm.group(1)):
                self.assertEqual(
                    value, "true",
                    f"{skill}: `disable-model-invocation: {value}` — Pi tests `=== true` after a "
                    f"YAML parse, so anything but a bare lowercase `true` silently keeps the skill "
                    f"model-invoked there while Claude Code hides it",
                )


if __name__ == "__main__":
    unittest.main()
