"""The Bash search nudge — doctrine turned into a sentence that arrives at the right moment.

A warn-only hook lives or dies on its false-positive rate. It cannot be disabled by a permission
prompt, so the way it fails is quieter: it says something wrong, the reader learns to skip it, and
from then on it costs attention and delivers nothing. So most of this file asserts the SILENT
paths, and the firing paths are checked for the one property that makes a warning useful — naming
the tool to reach for instead.

Driven as a subprocess over the real stdin/stdout contract, like `test_ledger_gate.py`: that
contract is the thing that can break.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "src", "hooks", "search-nudge.py")


class NudgeHarness(unittest.TestCase):
    def setUp(self):
        # A fresh temp dir per test, so the once-per-session state cannot leak between cases.
        self.tmp = tempfile.mkdtemp()
        self.session = "session-" + self.id()

    def run_hook(self, command=None, tool="Bash", session=None, raw=None):
        payload = raw if raw is not None else json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "tool_input": {"command": command},
            "session_id": self.session if session is None else session,
        })
        env = dict(os.environ, TMPDIR=self.tmp)
        r = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                           text=True, timeout=30, env=env)
        self.assertEqual(r.returncode, 0, f"hook must always exit 0, got {r.returncode}: {r.stderr}")
        if not r.stdout.strip():
            return None
        return json.loads(r.stdout)["systemMessage"]

    def assertSilent(self, command, why=""):
        self.assertIsNone(self.run_hook(command), f"should not warn on {command!r} — {why}")

    def assertWarns(self, command, mentions):
        message = self.run_hook(command)
        self.assertIsNotNone(message, f"expected a warning for {command!r}")
        self.assertIn(mentions, message)
        return message


class TestItFires(NudgeHarness):
    def test_find_points_at_glob_and_fd(self):
        self.assertWarns("find . -name '*.py'", "`fd`")

    def test_recursive_grep_points_at_rg(self):
        self.assertWarns("grep -r TODO .", "`rg`")

    def test_recursive_grep_offers_the_structural_answer_too(self):
        # The whole reason the doctrine exists: a question with syntax in it wants an AST, and
        # nothing in a grep-shaped habit ever suggests that.
        self.assertWarns("grep -rn 'def ' src/", "ast-grep")

    def test_plain_grep_still_speaks_but_only_once(self):
        message = self.assertWarns("grep TODO file.py", "`rg`")
        # The specific rule and the generic one must not both fire for one command.
        self.assertNotIn("recursive", message)

    def test_find_after_a_pipe_is_still_a_tree_walk(self):
        self.assertWarns("cd src && find . -type f", "`fd`")


class TestItStaysQuiet(NudgeHarness):
    def test_the_tools_it_recommends(self):
        self.assertSilent("rg TODO src/", "already the recommended tool")
        self.assertSilent("fd -e py src/", "already the recommended tool")
        self.assertSilent("ast-grep run --lang python -p 'print($$$A)'", "already structural")

    def test_a_pipe_filter_is_not_a_search(self):
        # `rg` does not replace this: the tree is not involved at all.
        self.assertSilent("gh pr list | grep open", "filters another command's output")
        self.assertSilent("ps aux | grep -i python", "filters another command's output")

    def test_prose_about_commands_is_not_a_command(self):
        self.assertSilent('git commit -m "stop using grep -r for this"', "a commit message")
        self.assertSilent('gh issue comment -m "find . was slow"', "an issue body")

    def test_a_heredoc_body_is_data_being_written(self):
        self.assertSilent("cat <<'EOF' > notes.md\ngrep -r TODO .\nEOF", "a file being written")

    def test_echoing_a_command_is_not_running_it(self):
        self.assertSilent("echo 'run grep -r TODO .'", "echo, not execution")

    def test_body_file_names_a_path_and_is_left_alone(self):
        # `--body-file` is a path, not prose — stripping it would blind the scanner to a real
        # command sitting after it on the same line.
        self.assertWarns("gh pr create --body-file b.md && find . -name x", "`fd`")

    def test_a_non_bash_tool_is_none_of_its_business(self):
        self.assertIsNone(self.run_hook("grep -r x .", tool="Edit"))

    def test_garbage_input_exits_clean(self):
        self.assertIsNone(self.run_hook(raw="not json at all"))
        self.assertIsNone(self.run_hook(raw="[]"))
        self.assertIsNone(self.run_hook(raw=json.dumps({"tool_name": "Bash"})))
        self.assertIsNone(self.run_hook(command=None))


class TestOncePerRulePerSession(NudgeHarness):
    def test_the_same_rule_speaks_once(self):
        self.assertWarns("grep -r TODO .", "`rg`")
        self.assertSilent("grep -r FIXME src/", "the rule already spoke this session")

    def test_a_different_rule_still_speaks(self):
        self.assertWarns("grep -r TODO .", "`rg`")
        self.assertWarns("find . -name '*.py'", "`fd`")

    def test_a_different_session_starts_over(self):
        self.assertWarns("grep -r TODO .", "`rg`")
        self.session = "a-different-session"
        self.assertWarns("grep -r TODO .", "`rg`")

    def test_no_session_identity_fails_open(self):
        # Losing the dedup is cheap; losing the first warning is the whole value.
        self.assertIsNotNone(self.run_hook("find . -name x", session=""))
        self.assertIsNotNone(self.run_hook("find . -name x", session=""))

    def test_a_hostile_session_id_cannot_steer_the_write(self):
        # Hashed, not interpolated: this must not create a file outside the temp dir.
        self.assertIsNotNone(self.run_hook("find . -name x", session="../../etc/passwd"))
        stray = os.path.join(os.path.dirname(self.tmp), "etc")
        self.assertFalse(os.path.exists(stray), "state file escaped the temp directory")


class TestItIsWiredIn(unittest.TestCase):
    """A hook nobody registers is a file, not a mechanism."""

    def test_hooks_json_registers_it_on_bash(self):
        path = os.path.join(os.path.dirname(__file__), "..", "src", "hooks", "hooks.json")
        with open(path, encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]["PreToolUse"]
        entry = [h for h in hooks if h.get("matcher") == "Bash"]
        self.assertEqual(len(entry), 1, "expected exactly one Bash PreToolUse entry")
        self.assertIn("search-nudge.py", entry[0]["hooks"][0]["command"])

    def test_it_does_not_share_a_matcher_with_the_ledger_gate(self):
        # The gate DENIES; this one only warns. One matcher carrying both would give the deny
        # path a second way to fail and the warn path a way to block.
        path = os.path.join(os.path.dirname(__file__), "..", "src", "hooks", "hooks.json")
        with open(path, encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]["PreToolUse"]
        for entry in hooks:
            commands = " ".join(h["command"] for h in entry["hooks"])
            self.assertFalse(
                "ledger-gate.py" in commands and "search-nudge.py" in commands,
                "the blocking gate and the warn-only nudge must stay on separate matchers",
            )


if __name__ == "__main__":
    unittest.main()
