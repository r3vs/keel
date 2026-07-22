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

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
ROSTER = ROOT / "src" / "core" / "agents.md"
AUTHORED = ROOT / "src" / "agents"
CLAUDE = PLUGINS / "alignment-core" / "agents"
OPENCODE = PLUGINS / "alignment-core" / "adapters" / "opencode" / "agent"
CODEX = PLUGINS / "alignment-core" / "adapters" / "codex" / "agents"

PERM = re.compile(r"^- ((?:`[\w-]+`(?:, )?)+)\s*→\s*\*\*edit: (deny|allow)\*\*", re.M)
ROLE = re.compile(r"`([\w-]+)`")


def roster() -> dict:
    out = {}
    for blob, verb in PERM.findall(ROSTER.read_text(encoding="utf-8")):
        for r in ROLE.findall(blob):
            out[r] = verb
    return out


# Profile A's model must be an Anthropic alias or a full claude-* id; opencode's must be
# provider-qualified. `max` is session-only, so it is not a legal frontmatter effort.
CLAUDE_ALIASES = {"sonnet", "opus", "haiku", "fable"}
CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh"}


def _frontmatter(base: Path, role: str) -> str:
    return (base / f"{role}.md").read_text(encoding="utf-8").split("---\n", 2)[1]


def _value(frontmatter: str, key: str):
    m = re.search(rf"(?mi)^\s*{key}\s*:\s*(\S+)\s*$", frontmatter)
    return m.group(1) if m else None


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

    # Study finding E1 offered two safe options — "omit `model` (OR map it per host)". These enforce
    # the second: per-role models are now an elected feature, so instead of forbidding `model:` we
    # guard the exact hazard E1 named — a model id its host cannot resolve. Strictly stronger than the
    # old blanket "no `model:` anywhere".

    def test_no_host_emits_model_inherit(self):
        # The literal #167 bug: `inherit` is a Claude-only keyword; opencode/Pi read it as a model id
        # and raise ProviderModelNotFoundError. We emit concrete ids per host, never `inherit`.
        for role in sorted(roster()):
            for host, base in (("claude", CLAUDE), ("opencode", OPENCODE)):
                with self.subTest(role=role, host=host):
                    self.assertNotRegex(_frontmatter(base, role), r"(?mi)^\s*model\s*:\s*inherit\b",
                                        "`inherit` is Claude-only; opencode/Pi reject it (E1 / UA #167)")

    def test_claude_models_are_anthropic_aliases(self):
        # Claude frontmatter takes an alias (sonnet/opus/haiku/fable) or a full claude-* id — never a
        # `provider/model-id`, and a wrong value is silently ignored, so assert the value is real.
        for role in sorted(roster()):
            model = _value(_frontmatter(CLAUDE, role), "model")
            with self.subTest(role=role):
                self.assertIsNotNone(model, "Profile A pins a model for every roster role")
                self.assertTrue(model in CLAUDE_ALIASES or model.startswith("claude-"),
                                f"claude model `{model}` is not an alias or a claude-* id")

    def test_opencode_models_are_provider_qualified(self):
        # opencode resolves `provider/model-id`; a bare alias (or `inherit`) is the #167 error. Every
        # opencode model must carry a provider namespace.
        for role in sorted(roster()):
            model = _value(_frontmatter(OPENCODE, role), "model")
            with self.subTest(role=role):
                self.assertIsNotNone(model, "the opencode profile pins a model for every roster role")
                self.assertIn("/", model, f"opencode model `{model}` must be `provider/model-id`")

    def test_claude_effort_is_a_legal_frontmatter_value(self):
        # `max` is session-only; a wrong effort is silently ignored by Claude Code.
        for role in sorted(roster()):
            effort = _value(_frontmatter(CLAUDE, role), "effort")
            with self.subTest(role=role):
                if effort is not None:
                    self.assertIn(effort, CLAUDE_EFFORTS,
                                  f"claude effort `{effort}` is not low|medium|high|xhigh")

    def test_codex_agents_are_valid_toml_with_only_the_three_keys(self):
        # Codex's role config layer is `deny_unknown_fields`, so a wrong key HARD-errors (not silent
        # like Claude). Assert each per-role file is valid TOML carrying a model + ONLY the three
        # verified keys — the guard that we never ship a field Codex would reject.
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")
        allowed = {"model", "model_reasoning_effort", "developer_instructions"}
        for role in sorted(roster()):
            p = CODEX / f"{role}.toml"
            with self.subTest(role=role):
                self.assertTrue(p.exists(), f"Codex per-role file {role}.toml must be generated")
                data = tomllib.loads(p.read_text(encoding="utf-8"))
                self.assertIn("model", data, "Codex agent must pin a model (Profile B)")
                self.assertEqual(set(data) - allowed, set(),
                                 "Codex role config denies unknown fields — emit only the three keys")

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
