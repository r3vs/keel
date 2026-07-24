"""The PreToolUse gate — rule #1 turned from a paragraph into a mechanism.

The gate's value is entirely in *when it does not fire*. A gate that blocks ordinary work gets
disabled within a day, and then rule #1 is back to being a suggestion. So most of this file asserts
the allow paths, and the deny path is checked for the two things that make a block survivable: it
must name what is blocking, and it must say what to do next.

Driven as a subprocess over the real stdin/stdout contract, because that contract is the thing that
can break.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

GATE = os.path.join(os.path.dirname(__file__), "..", "src", "hooks", "ledger-gate.py")


def _pin(state="needs_input", severity="high", title="users.email nullable in DB, required in API"):
    return {"id": "pin_001", "kind": "contract_mismatch", "title": title,
            "severity": severity, "state": state}


class GateHarness(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp()
        self.src = os.path.join(self.cwd, "src", "app.py")
        os.makedirs(os.path.dirname(self.src), exist_ok=True)

    def write_ledger(self, pins, rel=".audit/ledger.json"):
        p = os.path.join(self.cwd, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"pins": pins}, fh)
        return p

    def run_gate(self, tool="Edit", path=None, cwd=None, raw=None):
        payload = raw if raw is not None else json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": path if path is not None else self.src},
            "cwd": cwd if cwd is not None else self.cwd,
        })
        r = subprocess.run([sys.executable, GATE], input=payload,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, f"the gate must always exit 0; stderr:\n{r.stderr}")
        if not r.stdout.strip():
            return None
        return json.loads(r.stdout)["hookSpecificOutput"]


class TestStaysOutOfTheWay(GateHarness):
    """Everything here must produce no decision. This is the majority of real sessions."""

    def test_no_ledger_means_no_opinion(self):
        # The single most important case: a user not running a rescue/forge must never notice this.
        self.assertIsNone(self.run_gate())

    def test_a_clean_ledger_does_not_block(self):
        self.write_ledger([_pin(state="decided"), _pin(state="resolved")])
        self.assertIsNone(self.run_gate())

    def test_low_and_medium_pins_do_not_block(self):
        # Only blocker/high are forbidden from silent default, so only they justify a block.
        self.write_ledger([_pin(severity="medium"), _pin(severity="low")])
        self.assertIsNone(self.run_gate())

    def test_reading_is_never_gated(self):
        self.write_ledger([_pin()])
        for tool in ("Read", "Grep", "Glob", "Bash"):
            with self.subTest(tool=tool):
                self.assertIsNone(self.run_gate(tool=tool))

    def test_tests_are_never_blocked(self):
        # Track A writes the failing test FIRST. Blocking that would break the discipline this
        # gate exists to protect — the gate would be eating its own workflow.
        self.write_ledger([_pin()])
        for p in ("tests/test_users.py", "src/users.test.ts", "src/__tests__/users.ts",
                  "app/users_test.go", "src/users.spec.js"):
            with self.subTest(path=p):
                self.assertIsNone(self.run_gate(path=os.path.join(self.cwd, p)))

    def test_prose_and_the_ledger_itself_are_never_blocked(self):
        self.write_ledger([_pin()])
        for p in ("README.md", "notes.txt", ".audit/ledger.json", ".audit/map.html"):
            with self.subTest(path=p):
                self.assertIsNone(self.run_gate(path=os.path.join(self.cwd, p)))


class TestBlocksPrematureCode(GateHarness):
    def test_blocks_product_code_while_a_blocker_awaits_the_user(self):
        self.write_ledger([_pin(severity="blocker")])
        out = self.run_gate()
        self.assertEqual(out["permissionDecision"], "deny")

    def test_blocks_every_write_tool(self):
        self.write_ledger([_pin()])
        for tool in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
            with self.subTest(tool=tool):
                self.assertEqual(self.run_gate(tool=tool)["permissionDecision"], "deny")

    def test_a_root_level_ledger_is_found_too(self):
        self.write_ledger([_pin()], rel="ledger.json")
        self.assertEqual(self.run_gate()["permissionDecision"], "deny")

    def test_the_block_teaches_instead_of_just_refusing(self):
        # A bare "denied" gets worked around. The reason must name the offending pin and the way
        # forward, or the agent's next move is to try again with a different tool.
        self.write_ledger([_pin(title="which role set is canonical?")])
        reason = self.run_gate()["permissionDecisionReason"]
        self.assertIn("which role set is canonical?", reason, "must name what is blocking")
        self.assertIn("interview", reason.lower(), "must name the way forward")
        self.assertRegex(reason, r"[Tt]est", "must say tests are still allowed")


class TestHostMemoryAsksInsteadOfBlocking(GateHarness):
    """The one branch that neither allows nor denies.

    Auto-memory is the package's one unguarded write path: the agent chooses what to persist, the
    store is machine-local and never reviewed, and no host emits a memory-specific hook event. All
    three legs were observed 2026-07-24 — including that this gate used to let it straight through,
    because every memory file is `.md` and the prose exemption swallowed it.
    """

    def mem(self, name="notes.md"):
        return os.path.join(os.path.expanduser("~"), ".claude", "projects",
                            "C--Users-x-proj", "memory", name)

    def test_asks_when_a_blocker_is_open(self):
        self.write_ledger([_pin(severity="blocker")])
        out = self.run_gate(path=self.mem())
        self.assertEqual(out["permissionDecision"], "ask",
                         "must ask, never deny — denying would put this gate in the business of "
                         "blocking prose, which it promises it never does")

    def test_the_prose_exemption_no_longer_swallows_it(self):
        """The exact hole this closes: `.md` is exempt everywhere else, and every memory file is `.md`."""
        self.write_ledger([_pin()])
        self.assertIsNone(self.run_gate(path=os.path.join(self.cwd, "docs", "notes.md")))
        self.assertEqual(self.run_gate(path=self.mem())["permissionDecision"], "ask")

    def test_silent_when_nothing_is_blocking(self):
        # Same rule as the rest of the gate: invisible when it does not apply. This is what earns
        # the right to interrupt when it does.
        self.write_ledger([_pin(state="decided")])
        self.assertIsNone(self.run_gate(path=self.mem()))

    def test_silent_with_no_ledger_at_all(self):
        self.assertIsNone(self.run_gate(path=self.mem()))

    def test_the_prompt_names_the_honest_alternative(self):
        # An "ask" that only says no gets clicked through. It must say where the thing belongs.
        self.write_ledger([_pin(title="which role set is canonical?")])
        reason = self.run_gate(path=self.mem())["permissionDecisionReason"]
        self.assertIn("which role set is canonical?", reason, "must name what is blocking")
        self.assertIn("ledger_add_pin", reason, "must name where a decision belongs instead")
        self.assertIn("ledger", reason.lower())

    def test_a_configured_autoMemoryDirectory_is_read_from_the_carrier(self):
        """Where memory lives is read from `autoMemoryDirectory`, not guessed from a layout."""
        elsewhere = os.path.join(self.cwd, "custom-mem")
        os.makedirs(os.path.join(self.cwd, ".claude"), exist_ok=True)
        with open(os.path.join(self.cwd, ".claude", "settings.json"), "w", encoding="utf-8") as fh:
            json.dump({"autoMemoryDirectory": elsewhere}, fh)
        self.write_ledger([_pin()])
        out = self.run_gate(path=os.path.join(elsewhere, "MEMORY.md"))
        self.assertEqual(out["permissionDecision"], "ask")

    def test_a_broken_settings_file_degrades_to_the_default(self):
        os.makedirs(os.path.join(self.cwd, ".claude"), exist_ok=True)
        with open(os.path.join(self.cwd, ".claude", "settings.json"), "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        self.write_ledger([_pin()])
        self.assertEqual(self.run_gate(path=self.mem())["permissionDecision"], "ask")
        self.assertIsNone(self.run_gate(path=os.path.join(self.cwd, "docs", "x.md")))

    def test_product_code_still_denies(self):
        """The new branch must not soften the original one."""
        self.write_ledger([_pin()])
        self.assertEqual(self.run_gate()["permissionDecision"], "deny")


class TestFailsOpen(GateHarness):
    """A gate that can wedge a session is worse than no gate: a missed block costs one bad edit
    the reviewer catches; a false block costs the whole session."""

    def test_malformed_event_fails_open(self):
        self.assertIsNone(self.run_gate(raw="not json at all"))

    def test_empty_stdin_fails_open(self):
        self.assertIsNone(self.run_gate(raw=""))

    def test_corrupt_ledger_fails_open(self):
        p = os.path.join(self.cwd, ".audit", "ledger.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{ this is not json")
        self.assertIsNone(self.run_gate())

    def test_ledger_without_a_pins_key_fails_open(self):
        p = os.path.join(self.cwd, ".audit", "ledger.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"unexpected": "shape"}, fh)
        self.assertIsNone(self.run_gate())

    def test_missing_fields_fail_open(self):
        self.assertIsNone(self.run_gate(raw=json.dumps({"tool_name": "Edit"})))


if __name__ == "__main__":
    unittest.main()
