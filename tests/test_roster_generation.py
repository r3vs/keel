"""The agent roster: one source, every host derived from it.

This replaces a ~45-line parity linter, and the replacement has to be strictly stronger or it is a
regression. The linter compared two hand-written copies of the same six roles and checked their
names and write verb — while the copies had already drifted in *prose*, which name-and-verb parity
can never see. A parity linter is a smell: it says two things should be one thing, generated.

So these assert the property the linter could only approximate: **the write verb exists in exactly
one place**, and both hosts' mechanisms are computed from it. If someone re-introduces a second
place, a test here fails rather than a linter negotiating with it.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
ROSTER = ROOT / "src" / "core" / "agents.md"
AUTHORED = ROOT / "src" / "agents"
CLAUDE = PLUGINS / "alignment-core" / "agents"
OPENCODE = PLUGINS / "alignment-core" / "adapters" / "opencode" / "agent"

PERM = re.compile(r"^- ((?:`[\w-]+`(?:, )?)+)\s*→\s*\*\*edit: (deny|allow)\*\*", re.M)
ROLE = re.compile(r"`([\w-]+)`")


def roster() -> dict:
    out = {}
    for blob, verb in PERM.findall(ROSTER.read_text(encoding="utf-8")):
        for r in ROLE.findall(blob):
            out[r] = verb
    return out


class TestTheRosterIsTheOnlySource(unittest.TestCase):
    def test_the_roster_declares_a_verb_for_every_role(self):
        verbs = roster()
        self.assertTrue(verbs, "src/core/agents.md must declare `<role> → **edit: deny|allow**`")
        self.assertEqual(set(verbs), {p.stem for p in AUTHORED.glob("*.md")},
                         "roster and authored prompts must name the same roles")

    def test_exactly_one_role_writes(self):
        # "Serialized writing, parallel reading" is the roster's central claim. It is only true if
        # precisely one role is allowed to write — assert the claim, not the plumbing.
        self.assertEqual([r for r, v in roster().items() if v == "allow"], ["executor"])

    def test_the_authored_prompts_declare_no_permissions(self):
        # The whole point: a second place to state the verb is a second place to get it wrong.
        for p in sorted(AUTHORED.glob("*.md")):
            with self.subTest(role=p.stem):
                self.assertNotIn("disallowedTools:", p.read_text(encoding="utf-8"),
                                 "permissions are derived from the roster, not authored here")

    def test_the_opencode_roster_ships_inside_the_plugin(self):
        # This used to assert that the ROOT opencode.json held no `agent` block — that file once
        # carried six hand-written prompts which had already drifted from src/agents/. The file is
        # gone now (it was config for this repo, which no installing user works in), so the real
        # claim is the positive one: the roster reaches the user through the built plugin.
        placed = sorted(PLUGINS.glob("*/adapters/opencode/agent/*.md"))
        self.assertTrue(placed, "the opencode roster must be generated into plugins/*/adapters/")
        self.assertEqual({p.stem for p in placed}, set(roster()))


class TestBothHostsAreDerived(unittest.TestCase):
    def test_claude_denies_the_write_tools_for_every_read_only_role(self):
        for role, verb in sorted(roster().items()):
            text = (CLAUDE / f"{role}.md").read_text(encoding="utf-8")
            with self.subTest(role=role, host="claude"):
                if verb == "deny":
                    for tool in ("Write", "Edit"):
                        self.assertRegex(text, rf"disallowedTools:.*{tool}")
                else:
                    self.assertNotIn("disallowedTools:", text)

    def test_opencode_carries_the_same_verb(self):
        for role, verb in sorted(roster().items()):
            text = (OPENCODE / f"{role}.md").read_text(encoding="utf-8")
            with self.subTest(role=role, host="opencode"):
                self.assertRegex(text, rf"permission:\s*\n\s*edit:\s*{verb}")

    def test_both_hosts_get_the_identical_body(self):
        # The failure the old linter could not see: same role, two hand-written prompts, drifted.
        for role in sorted(roster()):
            with self.subTest(role=role):
                body = lambda p: p.read_text(encoding="utf-8").split("---\n", 2)[2]
                self.assertEqual(body(CLAUDE / f"{role}.md"), body(OPENCODE / f"{role}.md"),
                                 "the two hosts must not be able to describe the same role differently")


class TestTheBuildEnforcesIt(unittest.TestCase):
    """A guarantee nobody checks is a guarantee that decays. Prove the build actually fails."""

    def _build(self):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"), "--check"],
                              capture_output=True, text=True, cwd=ROOT)

    def test_check_is_green_as_committed(self):
        r = self._build()
        self.assertEqual(r.returncode, 0, f"plugins/ is out of sync with src/:\n{r.stdout}")

    def test_a_role_without_a_prompt_fails_the_build(self):
        original = ROSTER.read_text(encoding="utf-8")
        try:
            ROSTER.write_bytes(original.replace(
                "- `executor` → **edit: allow**", "- `executor`, `ghost` → **edit: allow**"
            ).encode("utf-8"))
            r = self._build()
            self.assertNotEqual(r.returncode, 0, "a roster role with no prompt must fail the build")
            self.assertIn("ghost", r.stdout)
        finally:
            ROSTER.write_bytes(original.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
