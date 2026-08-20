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
import json
import os
import pathlib
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


class TestTheRelayDoorIsNamedAsTheHostServesIt(unittest.TestCase):
    """The guard sends an agent to `ledger_record_decision`, which the HOST may refuse in turn.

    That second refusal is not keel's and keel cannot fix it: a selective permission rule lives in
    the user's own settings, session-wide, and a plugin cannot ship one (`docs/packaging.md`). What
    keel can do is stop everybody guessing the name, because a bundled server is namespaced twice —
    `mcp__plugin_<plugin>_<server>__<tool>` — and the bare `mcp__<server>__<tool>` matches nothing.
    `docs/measurements.md` records an eval run failing on exactly that substitution, and the failure
    mode is the expensive one: a rule that matches nothing looks like a setting that did not take.

    So the name is COMPOSED from the two manifests that decide it, and this holds the composition to
    them rather than to a string written here.
    """

    def _built(self):
        root = pathlib.Path(ROOT) / "plugins" / "keel-core"
        if not (root / "mcp" / "tools.py").is_file():
            self.skipTest("plugins/ not built — run scripts/build.py")
        return root

    def test_the_name_is_composed_from_the_manifests_beside_it(self):
        root = self._built()
        plugin = json.loads((root / ".claude-plugin" / "plugin.json")
                            .read_text(encoding="utf-8"))["name"]
        servers = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        ours = [k for k, v in servers.items() if "server.py" in " ".join(v.get("args") or [])]
        self.assertEqual(len(ours), 1, f"exactly one declared server may run our server.py: {ours}")

        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); import tools;"
             "print(tools.scoped_tool_name('ledger_record_decision'))",
             str(root / "mcp")],
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(),
                         f"mcp__plugin_{plugin}_{ours[0]}__ledger_record_decision",
                         "the composed name drifted from the manifests it is composed from — which "
                         "is the only way this can be wrong, since nothing writes it")

    def test_the_source_tree_says_the_bare_name_rather_than_guessing_a_prefix(self):
        """`src/mcp/` is not an install. A plugin prefix invented where no manifest exists would be
        the fabricated provenance this package is built to find, so the honest answer is shorter."""
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); import tools;"
             "print(tools.scoped_tool_name('ledger_record_decision'))",
             str(pathlib.Path(ROOT) / "src" / "mcp")],
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "ledger_record_decision")

    def test_the_refusal_hands_over_that_name_and_not_the_bare_one(self):
        """Driven, not read: the guard is where an agent meets this, so the string is checked on the
        stderr of a real refusal rather than in the source that composes it."""
        root = self._built()
        # A PIPE, not DEVNULL. On Windows `NUL` is a character device and `isatty()` answers True
        # for it, so a DEVNULL stdin walks straight past the guard and fails on the ledger instead —
        # the same shape the module docstring already records for msys `< /dev/null`. The sibling
        # tests above drive it with `input=`, and this one does the same for the same reason.
        out = subprocess.run(
            [sys.executable, str(root / "mcp" / "decide.py"), "pin", "nope.json", "pin_0001"],
            input="", capture_output=True, text=True, encoding="utf-8", timeout=120)
        said = out.stdout + out.stderr
        self.assertIn("refusing: stdin is not a terminal", said)
        plugin = json.loads((root / ".claude-plugin" / "plugin.json")
                            .read_text(encoding="utf-8"))["name"]
        self.assertIn(f"mcp__plugin_{plugin}_", said,
                      "the refusal sends an agent to a tool without saying what the host calls it, "
                      "which is the hop everybody has got wrong so far")


    def test_the_segments_are_normalised_the_way_the_host_normalises_them(self):
        """*"any character outside `A-Z`, `a-z`, `0-9`, `_`, and `-` is replaced with `_`"* — the
        published rule, said twice: the MCP page, and the Agent SDK's own `.d.ts` in this repo's
        `node_modules` (*"server names are normalized: non-[a-zA-Z0-9_-] becomes _"*).

        Both halves are asserted on purpose. Our real segments are already clean, so a test that
        only checked the substitution would be checking a branch no shipped input reaches — and one
        that only checked today's name would pass on an implementation that does not normalise at
        all. The pair says: the rule is implemented, AND implementing it changed nothing today.
        """
        mod = self._tools_module()
        self.assertEqual(mod._host_segment("keel-core"), "keel-core")
        self.assertEqual(mod._host_segment("keel"), "keel")
        for dirty, clean in (("my.plugin", "my_plugin"), ("a/b", "a_b"), ("x y", "x_y"),
                             ("caffè", "caff_"), ("v1.2.3", "v1_2_3")):
            self.assertEqual(mod._host_segment(dirty), clean)

    def test_the_composition_actually_passes_the_segments_through_it(self):
        """Mechanical, because behaviour cannot see this: `keel-core` and `keel` normalise to
        themselves, so a composition that skipped `_host_segment` entirely would return the same
        string on every input this package ships. The only way to hold the rule is to read the call.
        """
        import ast
        src = _read(pathlib.Path(ROOT) / "src" / "mcp" / "tools.py")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "scoped_tool_name")
        joined = [n for n in ast.walk(fn) if isinstance(n, ast.JoinedStr)]
        self.assertTrue(joined, "scoped_tool_name no longer composes an f-string")
        wrapped = {n.func.id for j in joined for n in ast.walk(j)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn("_host_segment", wrapped,
                      "the two segments read off disk must go through the host's own normalisation "
                      "rule; a name that grows a dot later would compose to a string the host never "
                      "serves, and fail by matching NOTHING")

    def _tools_module(self):
        import importlib.util
        path = pathlib.Path(ROOT) / "src" / "mcp" / "tools.py"
        spec = importlib.util.spec_from_file_location("_keel_tools_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


class TestTheRefusalHandsOverARunnableLine(unittest.TestCase):
    r"""`server.py` prints `uv run --script <door> …` when a TOOL refuses. This is the other entry:
    somebody already started the door itself, with some python, through a pipe.

    Observed in a real session — an agent that had *just executed this file* went on to invent
    `.venv-win\Scripts\python.exe` and retype a version-stamped plugin-cache path, because the
    refusal said what not to do and nothing about how to do it. `sys.executable` is the one
    interpreter known to work, and `argv` is the caller's own target.
    """

    def _refuse(self, *args):
        """Driven through a real pipe. NOT `subprocess.DEVNULL`: on Windows that opens `NUL`, a
        character device, and `isatty()` answers True for it — the guard never fires and the run
        fails somewhere else entirely, which is a green test asserting nothing."""
        out = subprocess.run(
            [sys.executable, str(pathlib.Path(ROOT) / "src" / "mcp" / "decide.py"), *args],
            input="", capture_output=True, text=True, encoding="utf-8", timeout=120)
        said = out.stdout + out.stderr
        self.assertIn("refusing: stdin is not a terminal", said, said)
        return said

    def _pasted_line(self, said):
        marker = "To run this door yourself, in your own terminal, paste:"
        self.assertIn(marker, said, "the refusal offers no way to do the thing it refused")
        return said.split(marker, 1)[1].strip().splitlines()[0].strip()

    def test_the_line_names_this_interpreter_and_this_door(self):
        line = self._pasted_line(self._refuse("pin", "nope.json", "pin_0001"))
        for token in (pathlib.Path(sys.executable).name, "decide.py", "pin_0001", "nope.json"):
            self.assertIn(token, line, f"{token!r} missing from {line!r}")

    def test_the_line_runs_and_lands_back_on_the_same_guard(self):
        """The round-trip is the point. Asserting the string *looks* right would pass on a line
        whose quoting is broken, which is the failure mode that matters: the default Windows plugin
        cache lives under a profile directory with a space in it.
        """
        line = self._pasted_line(self._refuse("pin", "nope.json", "pin_0001"))
        again = subprocess.run(line, shell=True, input="", capture_output=True,
                               text=True, encoding="utf-8", timeout=120)
        self.assertIn("refusing: stdin is not a terminal", again.stdout + again.stderr,
                      f"the composed line did not reach the door it names: {line!r}")

    def test_with_no_arguments_it_offers_the_shape_rather_than_a_broken_line(self):
        line = self._pasted_line(self._refuse())
        self.assertIn("<pin_id>", line)
        self.assertIn("decide.py", line)


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


class TestTheSittingIsAWalkAndNotASecondDoor(unittest.TestCase):
    """`session` walks the funnel. Everything that makes it safe is that it does nothing else.

    The rung is checked one class up, by equality over the whole tree: `run_session` appearing in
    `ENTITLED` would fail there. What is checked here is the other half — that the walk reaches the
    ledger only through `decide_pin`, so the guarantee it inherits is the one that was already
    tested rather than a new one nobody exercised.
    """

    def setUp(self):
        self.tree = ast.parse(_read(DOOR))
        self.fn = next(n for n in ast.walk(self.tree)
                       if isinstance(n, ast.FunctionDef) and n.name == "run_session")

    def test_the_walk_writes_only_through_the_door(self):
        writes = [n for n in ast.walk(self.fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr in ("record_decision", "record_policy", "save", "decide")]
        self.assertFalse(writes,
                         "a sitting that wrote directly would be a third electing path, and it "
                         "would be one nothing in this file's guard story covers")
        calls = [n for n in ast.walk(self.fn) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "decide_pin"]
        self.assertTrue(calls, "the walk must elect through the door it wraps")

    def test_the_walk_takes_no_answer_from_its_caller(self):
        self.assertEqual([a.arg for a in self.fn.args.args], ["ledger"],
                         "a session takes a ledger and nothing an answer could ride in on")

    def test_the_order_is_the_interviews_and_is_re_derived(self):
        """Not `interview_view` copied, not a sort written here: the funnel, called inside the loop.

        A list captured before the first write would ask questions a cascade had already settled,
        which is the stateless-twin shape this package refuses — here it would be a twin of the
        interview's own ordering, sitting on the human's time.
        """
        loop = next(n for n in ast.walk(self.fn) if isinstance(n, ast.While))
        inside = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr == "interview_next"]
        self.assertTrue(inside, "the funnel must be re-read inside the loop, not before it")


class TestASittingPutsEachQuestionOnce(unittest.TestCase):
    """Behavioural, in-process — the same half the TTY guard hides from a runner."""

    def setUp(self):
        sys.path.insert(0, os.path.join(SRC, "mcp"))
        import decide
        self.decide = decide
        self.tmp = tempfile.mkdtemp()
        led = Ledger(os.path.join(self.tmp, "ledger.json"))
        for sev, title in (("blocker", "is orders in v1 scope?"),
                           ("high", "which auth model?"),
                           ("low", "which date format?")):
            led.add_pin(kind="ambiguity", title=title, severity=sev, confidence="inferred",
                        provenance=[{"source": "static", "detail": "two layers disagree"}],
                        question={"prompt": f"{title} — which reading holds?",
                                  "allow_freeform": True,
                                  "options": [{"id": "a", "label": "the first"},
                                              {"id": "b", "label": "the second"}]})
        led.save()
        self.ledger = led.path
        self.asked = []

    def _typed(self, *answers):
        """The person at the keyboard, who eventually walks away: the iterator raises `EOFError`
        when it runs dry, which is Ctrl-D and not a crash — a test that ran out of answers into a
        `StopIteration` would be asserting on a traceback."""
        it = iter(answers)
        import builtins
        original = builtins.input

        def fake(label=""):
            self.asked.append(label)
            try:
                return next(it)
            except StopIteration:
                raise EOFError
        builtins.input = fake
        self.addCleanup(setattr, builtins, "input", original)

    def _pin_answer(self, row):
        return [row, "because the routes already assume it", "if the v1 cut list changes", "y"]

    def test_a_sitting_decides_every_open_pin_in_one_run(self):
        self._typed(*self._pin_answer("1"), *self._pin_answer("1"),
                    "y", *self._pin_answer("1"))
        self.assertEqual(self.decide.run_session(self.ledger), 0)
        led = Ledger(self.ledger)
        for pid in ("pin_0001", "pin_0002", "pin_0003"):
            self.assertEqual(led.pin(pid)["state"], "decided", f"{pid} was left behind")
        self.assertEqual([e["evidence"] for e in led.data["decision_log"]], ["elicited"] * 3,
                         "a walk around the door inherits the door's rung and states no other")

    def test_it_asks_in_the_interviews_order_worst_first(self):
        self._typed(*self._pin_answer("1"), *self._pin_answer("1"),
                    "y", *self._pin_answer("1"))
        self.decide.run_session(self.ledger)
        self.assertEqual([e["pin_id"] for e in Ledger(self.ledger).data["decision_log"]],
                         ["pin_0001", "pin_0002", "pin_0003"],
                         "equal fan-out leaves severity to order the questions; the blocker is not "
                         "the one a tiring human reaches last")

    def test_a_skipped_pin_is_not_asked_again_in_the_same_sitting(self):
        """The termination rule. Without it a pin nobody answers is the loop's fixed point, and the
        door would sit there asking it until the human closed the terminal."""
        skip_row = "4"                    # two options, freeform, then skip — the last row
        self._typed(skip_row, *self._pin_answer("1"), "y", *self._pin_answer("1"))
        self.assertEqual(self.decide.run_session(self.ledger), 0)
        led = Ledger(self.ledger)
        self.assertEqual(led.pin("pin_0001")["state"], "needs_input", "skip must write nothing")
        self.assertEqual(led.pin("pin_0002")["state"], "decided")
        self.assertEqual(led.pin("pin_0003")["state"], "decided")

    def test_walking_away_keeps_what_was_already_written(self):
        """Ctrl-D halfway is not a rollback: every door here commits per pin, and the closing line
        has to say what stands rather than the single-pin form's "nothing was written"."""
        self._typed(*self._pin_answer("1"))
        self.assertEqual(self.decide.run_session(self.ledger), 0)
        led = Ledger(self.ledger)
        self.assertEqual(led.pin("pin_0001")["state"], "decided")
        self.assertEqual(led.pin("pin_0002")["state"], "needs_input")

    def test_main_routes_the_session_form_past_the_guard(self):
        """The one path neither sibling covers, and it is this repo's signature gap.

        The subprocess tests reach `main` and are refused by `_guard` BEFORE any argv is parsed, so
        a `session` branch that was never wired would leave them green; the tests above call
        `run_session` directly and never touch the routing. So this drives `main` with the guard's
        precondition satisfied — a stdin that says it is a terminal, which is the true statement
        for the person this form is written for.
        """
        import unittest.mock

        class _AtAKeyboard:
            def isatty(self):
                return True
        self.addCleanup(setattr, self.decide.sys, "stdin", self.decide.sys.stdin)
        self.decide.sys.stdin = _AtAKeyboard()
        self._typed(*self._pin_answer("1"), *self._pin_answer("1"), "n")
        self.assertEqual(self.decide.main(["session", self.ledger]), 0)
        self.assertEqual(Ledger(self.ledger).pin("pin_0001")["state"], "decided",
                         "`session` reached no walk: main parsed it as an unknown form")

    def test_the_bulk_tail_is_offered_and_declining_it_writes_nothing(self):
        """The tail is the half a policy would settle. It must be OFFERED — a sitting that walked it
        silently would put questions the funnel had already judged not worth putting — and declining
        must leave it exactly as it was."""
        self._typed(*self._pin_answer("1"), *self._pin_answer("1"), "n")
        self.assertEqual(self.decide.run_session(self.ledger), 0)
        led = Ledger(self.ledger)
        self.assertEqual(led.pin("pin_0001")["state"], "decided")
        self.assertEqual(led.pin("pin_0002")["state"], "decided")
        self.assertEqual(led.pin("pin_0003")["state"], "needs_input",
                         "the tail was declined; nothing in it may move")
        self.assertTrue(any("Walk them too" in label for label in self.asked),
                        "a tail that is walked or skipped without being named is this file "
                        "deciding for the human which questions are worth their time")

    def test_an_unelectable_pin_does_not_end_the_sitting(self):
        led = Ledger(self.ledger)
        led.data["pins"][0]["question"] = {"prompt": "no options, no freeform", "options": []}
        led.save()
        self._typed(*self._pin_answer("1"), "y", *self._pin_answer("1"))
        self.assertEqual(self.decide.run_session(self.ledger), 0)
        led = Ledger(self.ledger)
        self.assertEqual(led.pin("pin_0001")["state"], "needs_input")
        self.assertEqual(led.pin("pin_0002")["state"], "decided")
        self.assertEqual(led.pin("pin_0003")["state"], "decided")


class TestTheGuardCoversEveryForm(unittest.TestCase):
    """The TTY precondition is checked once, in `main`, for every form. A session that skipped it
    would be the pipe-answerable door this file exists to make impossible, at 23x the size."""

    def setUp(self):
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

    def test_a_pipe_carrying_a_whole_sittings_answers_is_refused(self):
        out = subprocess.run([sys.executable, DOOR, "session", self.ledger],
                             input="1\nbecause\nif the cut list changes\ny\n" * 3,
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("not a terminal", out.stdout + out.stderr)
        self.assertEqual(Ledger(self.ledger).pin("pin_0001")["state"], "needs_input")

    def test_the_usage_line_offers_every_form_the_door_accepts(self):
        """The shape printed on a bad invocation is a slice of the docstring, so adding a form
        without widening the slice silently hides it — the kind of drift a comment cannot catch."""
        import re
        doc = _read(DOOR).split('"""')[1]
        offered = {m for m in re.findall(r"<this file> (\w+)", doc)}
        tail = "\n".join(doc.strip().splitlines()[-4:])
        self.assertEqual(offered, {"pin", "policy", "session"})
        for form in offered:
            self.assertIn(f"<this file> {form}", tail,
                          f"`{form}` is a form this door accepts and the printed usage omits it")


if __name__ == "__main__":
    unittest.main()
