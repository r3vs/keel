"""The human-run door, and the rung it is entitled to state (spec v0.29).

`decide()` has always held that `evidence` is a fact about WHICH PATH RAN, so only the code that ran
it may state it — and nothing enforced that. A direct `record_decision(..., evidence="elicited")`
from a plain script wrote the strongest rung in the vocabulary, which is the shape of every finding
this repo keeps making: a rule stated in a docstring, proved of nobody.

So the entitled set is derived here by AST rather than asserted in prose, and the door's one
precondition — a human's hand on it — is exercised as behaviour, against a real ledger, checking the
file byte-for-byte afterwards. A guard that is only described is a guard that is not there.
"""
import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DOOR = os.path.join(SRC, "mcp", "decide.py")

sys.path.insert(0, os.path.join(SRC, "mcp"))
sys.path.insert(0, os.path.join(SRC, "runtime"))
from ledger import Ledger  # noqa: E402

#: The paths that ASK a human, and the function in each that writes the answer down. Anything else
#: passing `elicited` is a caller claiming an ask it did not perform — which is the whole failure the
#: rung exists to make impossible, so the test names the members and fails on a third.
ENTITLED = {
    ("mcp/server.py", "ledger_record_decision"),
    ("mcp/server.py", "ledger_record_policy"),
    ("mcp/decide.py", "decide_pin"),
    ("mcp/decide.py", "set_policy"),
}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _py_files():
    for base, dirs, names in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != "node_modules"]
        for n in names:
            if n.endswith(".py"):
                yield os.path.join(base, n)


def _claims_elicited(path):
    """(file, enclosing function) for every place this file states the `elicited` rung IN CODE.

    Both spellings, because a rule that knew one would be satisfied by the other: the keyword
    argument (`record_decision(..., evidence="elicited")`, how the door writes it) and the local
    assignment (`evidence = "elicited"`, how the server's elicitation branch writes it).
    """
    tree = ast.parse(_read(path))
    rel = os.path.relpath(path, SRC).replace(os.sep, "/")
    found = set()

    def visit(node, fn):
        here = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (kw.arg == "evidence" and isinstance(kw.value, ast.Constant)
                        and kw.value.value == "elicited"):
                    found.add((rel, here))
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and node.value.value == "elicited":
            if any(isinstance(t, ast.Name) and t.id == "evidence" for t in node.targets):
                found.add((rel, here))
        for child in ast.iter_child_nodes(node):
            visit(child, here)

    visit(tree, "<module>")
    return found


class TestOnlyAnAskingPathMayClaimItAsked(unittest.TestCase):
    def test_the_entitled_set_is_exactly_the_paths_that_ask(self):
        claimed = set()
        for f in _py_files():
            claimed |= _claims_elicited(f)
        self.assertEqual(
            claimed, ENTITLED,
            "`elicited` claims that no agent held the value. Every place that states it must be a "
            "path that actually asked a human — the server's elicitation branch, or the human-run "
            "door. A new member here is a caller claiming an ask it did not perform; a missing one "
            "means a path that asks has stopped saying so.")

    def test_the_library_default_is_still_the_weaker_rung(self):
        """The entitled set is only meaningful while everything else lands on `transcribed`."""
        import inspect
        sig = inspect.signature(Ledger.decide)
        self.assertEqual(sig.parameters["evidence"].default, "transcribed")


class TestTheDoorTakesNoAnswerFromItsCaller(unittest.TestCase):
    """The guard stops an agent ANSWERING the door. This stops one passing the answer in.

    Structural rather than behavioural on purpose: a flag that carries an answer would be invisible
    to a test that only pipes stdin, and it is exactly what a future convenience commit adds.
    """

    def setUp(self):
        self.tree = ast.parse(_read(DOOR))
        self.fns = {n.name: n for n in ast.walk(self.tree)
                    if isinstance(n, ast.FunctionDef)}

    def test_the_writing_functions_accept_only_a_target(self):
        expected = {"decide_pin": ["ledger", "pin_id"],
                    "set_policy": ["ledger", "offer_id", "project_type"]}
        for name, params in expected.items():
            self.assertIn(name, self.fns, f"{name} is the door's write path and must exist")
            got = [a.arg for a in self.fns[name].args.args]
            self.assertEqual(got, params,
                             f"{name} takes a target and nothing an answer could ride in on. "
                             f"An `option_id=` or `human_answer=` parameter here would let the "
                             f"caller supply what the rung swears the caller never held.")

    def test_no_writing_function_reads_the_command_line(self):
        """`main` parses argv and hands down a target; the writers never look at it themselves.

        Stated over the writers rather than over `main`, because that is where it bites: argv is
        read at module scope too (`main(sys.argv[1:])`), so a rule phrased as "argv appears in one
        function" is satisfied by a file that reads it in none.
        """
        for name in ("decide_pin", "set_policy"):
            reads = [n for n in ast.walk(self.fns[name])
                     if isinstance(n, ast.Attribute) and n.attr == "argv"]
            self.assertFalse(reads,
                             f"{name} writes an election; reading argv there would let its outcome "
                             f"come from the command line an agent composed")

    def test_every_write_the_door_makes_states_the_rung(self):
        writes = [n for n in ast.walk(self.tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr in ("record_decision", "record_policy")]
        self.assertEqual(len(writes), 2, "the door has exactly two writes: a pin and a policy")
        for call in writes:
            kw = {k.arg: k.value for k in call.keywords}
            self.assertIsInstance(kw.get("evidence"), ast.Constant)
            self.assertEqual(kw["evidence"].value, "elicited")


class TestTheGuardIsAMechanism(unittest.TestCase):
    """Run it the way an agent would have to, and check the file afterwards."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        led = Ledger(os.path.join(self.tmp, "ledger.json"))
        led.add_pin(kind="ambiguity", title="is orders in v1 scope?", severity="blocker",
                    confidence="inferred",
                    provenance=[{"source": "static", "detail": "routes reference a missing model"}],
                    as_is={"candidates": [{"interpretation": "in scope"},
                                          {"interpretation": "future"}]},
                    question={"prompt": "Which reading holds?",
                              "options": [{"id": "in_scope", "label": "ships in v1"},
                                          {"id": "future", "label": "a later feature"}],
                              "allow_freeform": True})
        led.save()
        self.ledger = led.path
        self.before = self._digest()

    def _digest(self):
        with open(self.ledger, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def _run(self, stdin):
        return subprocess.run([sys.executable, DOOR, "pin", self.ledger, "pin_0001"],
                              input=stdin, capture_output=True, text=True, timeout=60)

    def test_a_pipe_carrying_the_answers_is_refused(self):
        out = self._run("1\nbecause\nif the v1 cut list drops orders\ny\n")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not a terminal", out.stdout + out.stderr)
        self.assertEqual(self.before, self._digest(), "a refused run writes nothing")

    def test_a_file_redirect_carrying_the_answers_is_refused(self):
        path = os.path.join(self.tmp, "answers.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("1\nbecause\nif the v1 cut list drops orders\ny\n")
        with open(path, "rb") as fh:
            out = subprocess.run([sys.executable, DOOR, "pin", self.ledger, "pin_0001"],
                                 stdin=fh, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not a terminal", out.stdout + out.stderr)
        self.assertEqual(self.before, self._digest(), "a refused run writes nothing")

    def test_the_pin_is_still_open_after_both(self):
        self.assertEqual(Ledger(self.ledger).pin("pin_0001")["state"], "needs_input")


class TestTheServerNamesADoorItCannotRun(unittest.TestCase):
    """The path class `verify_commands.py` guards: nobody may WRITE the door's location, so the
    server computes it. Checked without importing FastMCP."""

    def setUp(self):
        self.server = os.path.join(SRC, "mcp", "server.py")
        self.src = _read(self.server)

    def test_the_door_sits_where_the_server_looks_for_it(self):
        self.assertTrue(os.path.isfile(DOOR),
                        "`_human_door` resolves `decide.py` beside `server.py`; the build ships "
                        "every *.py in src/mcp, so the two travel together or neither does")

    def test_both_declined_elicitations_hand_over_the_path(self):
        tree = ast.parse(self.src)
        for fn in ("ledger_record_decision", "ledger_record_policy"):
            node = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.AsyncFunctionDef) and n.name == fn)
            calls = [c for c in ast.walk(node) if isinstance(c, ast.Call)
                     and isinstance(c.func, ast.Name) and c.func.id == "_human_door"]
            self.assertTrue(calls,
                            f"{fn} raises when the client declines; without the door's absolute "
                            f"path in that message the agent has nothing to tell the user, and the "
                            f"pin is undecidable on that host")


class TestTheDoorShipsWithTheServer(unittest.TestCase):
    def test_every_built_plugin_that_ships_the_server_ships_the_door(self):
        plugins = os.path.join(ROOT, "plugins")
        if not os.path.isdir(plugins):
            self.skipTest("plugins/ not built in this checkout")
        source = _read(DOOR)
        checked = 0
        for name in sorted(os.listdir(plugins)):
            server = os.path.join(plugins, name, "mcp", "server.py")
            if not os.path.isfile(server):
                continue
            door = os.path.join(plugins, name, "mcp", "decide.py")
            self.assertTrue(os.path.isfile(door),
                            f"{name} ships the server, so the electing surface it refuses to "
                            f"provide on a declining client must ship beside it")
            self.assertEqual(_read(door), source)
            checked += 1
        self.assertTrue(checked, "no built plugin ships the MCP server — the sweep proved nothing")


class TestTheDoorWritesWhatTheHumanTyped(unittest.TestCase):
    """The happy path, in-process — the half a TTY guard makes unreachable from a test runner.

    Everything above proves the door REFUSES. A guard with no exercised success path is a file that
    might refuse everything, which is the failure mode of a gate nobody ran forwards.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(SRC, "mcp"))
        import decide
        self.decide = decide
        self.tmp = tempfile.mkdtemp()
        led = Ledger(os.path.join(self.tmp, "ledger.json"))
        led.add_pin(kind="ambiguity", title="is orders in v1 scope?", severity="blocker",
                    confidence="inferred",
                    provenance=[{"source": "static", "detail": "routes reference a missing model"}],
                    question={"prompt": "Which reading holds?", "allow_freeform": True,
                              "options": [{"id": "in_scope", "label": "ships in v1"},
                                          {"id": "future", "label": "a later feature"}]})
        led.save()
        self.ledger = led.path

    def _typed(self, *answers):
        """Stand in for the person at the keyboard; `decide_pin` reads through `input` only."""
        it = iter(answers)
        import builtins
        original = builtins.input
        builtins.input = lambda *_: next(it)
        self.addCleanup(setattr, builtins, "input", original)

    def test_picking_an_option_records_it_on_the_strong_rung(self):
        self._typed("1", "orders is already half-wired into the routes",
                    "if the v1 cut list drops orders", "y")
        self.assertEqual(self.decide.decide_pin(self.ledger, "pin_0001"), 0)
        led = Ledger(self.ledger)
        self.assertEqual(led.pin("pin_0001")["state"], "decided")
        event = led.data["decision_log"][-1]
        self.assertEqual(event["outcome"], "in_scope")
        self.assertEqual(event["evidence"], "elicited")
        self.assertTrue(event["flip_criteria"], "a decision with no reopen condition fossilizes")

    def test_declining_the_confirmation_writes_nothing(self):
        self._typed("2", "r", "f", "n")
        self.assertEqual(self.decide.decide_pin(self.ledger, "pin_0001"), 1)
        self.assertEqual(Ledger(self.ledger).pin("pin_0001")["state"], "needs_input")

    def test_the_freeform_row_makes_the_words_the_outcome(self):
        self._typed("3", "neither reading is right", "r", "f", "y")
        self.assertEqual(self.decide.decide_pin(self.ledger, "pin_0001"), 0)
        event = Ledger(self.ledger).data["decision_log"][-1]
        self.assertEqual(event["outcome"], "neither reading is right")
        self.assertEqual(event["human_answer"], "neither reading is right")


if __name__ == "__main__":
    unittest.main()
