"""Four BEHAVIORAL invariant tests — not unit tests (Block 4 of docs/design/sota-alignment.md).

The difference matters and is the reason these live in their own file. A unit test asks whether a
function returns the right value. These ask whether a *rule the package promises* actually holds at
the seam where it would be broken:

1. an action on a protected path makes the gate **fire** — and the assertion is on the gate's own
   output, never on "the task finished". A test that only checks completion passes just as happily
   when the gate never ran, which is the exact way a security control rots into decoration.
2. every state-mutating path on the ledger goes through a **governed channel** — asserted, rather
   than agreed. Adding a mutator without deciding its channel fails here.
3. every path that reaches `Ledger.decide` is **enumerated from the source** and reaches the single
   predicate. 2 asks whether a mutator has a channel; 3 asks the question that was actually being
   dodged — *how many ways in are there*. It is computed, not listed from memory, because the last
   three times this rule was fixed it was fixed at a door, and the next door did not know.
4. every write-time rule `decide` enforces is one the **reader** can replay over a file written
   before it existed. 3 is about doors, 4 is about rules; both were fixed once per instance until
   the instance count made the class visible.

Stdlib unittest (also runs under pytest).
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp"))

import ledger as ledgermod  # noqa: E402

GATE = os.path.join(os.path.dirname(__file__), "..", "src", "hooks", "ledger-gate.py")


def _blocking_ledger(tmp: str) -> str:
    """A ledger with an unresolved blocker awaiting the human — the state the gate must deny in."""
    out = os.path.join(tmp, ".audit")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "ledger.json")
    led = ledgermod.Ledger(path)
    led.add_pin(kind="ambiguity", title="two auth flows", severity="blocker",
                confidence="ambiguous", provenance=[{"source": "recon", "detail": "x"}],
                question={"prompt": "which one?", "allow_freeform": True,
                          "options": [{"id": "a", "label": "A"}]})
    led.save()
    return path


def run_gate(cwd: str, file_path: str, tool: str = "Edit") -> dict:
    payload = {"cwd": cwd, "tool_name": tool, "tool_input": {"file_path": file_path}}
    proc = subprocess.run([sys.executable, GATE], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)
    if not proc.stdout.strip():
        return {"decision": None, "raw": proc.stdout}
    return json.loads(proc.stdout)


class TestTheGateActuallyFires(unittest.TestCase):
    """Invariant 1 — assert the CONTROL fired, never that the task completed."""

    def test_a_protected_path_produces_an_explicit_deny(self):
        tmp = tempfile.mkdtemp()
        _blocking_ledger(tmp)
        out = run_gate(tmp, os.path.join(tmp, "src", "app", "payments.py"))
        hook = out.get("hookSpecificOutput", {})
        self.assertEqual(hook.get("permissionDecision"), "deny",
                         "the gate must DENY, and this test must fail if it merely stays silent")
        self.assertTrue(str(hook.get("permissionDecisionReason", "")).strip(),
                        "a deny with no reason is a wall, not a gate")

    def test_silence_is_a_failure_here_not_a_pass(self):
        """The anti-pattern, made explicit: 'no output' is exactly what an un-run gate produces,
        so any assertion that tolerates it proves nothing about the control."""
        tmp = tempfile.mkdtemp()
        _blocking_ledger(tmp)
        out = run_gate(tmp, os.path.join(tmp, "src", "app", "payments.py"))
        self.assertNotEqual(out.get("decision", "MISSING"), None)

    def test_the_gate_is_invisible_where_it_does_not_apply(self):
        """Earning the right to block: no ledger in the project means no interference at all."""
        tmp = tempfile.mkdtemp()
        out = run_gate(tmp, os.path.join(tmp, "src", "app", "payments.py"))
        self.assertEqual(out.get("decision"), None)

    def test_it_never_blocks_the_red_test_it_depends_on(self):
        tmp = tempfile.mkdtemp()
        _blocking_ledger(tmp)
        out = run_gate(tmp, os.path.join(tmp, "tests", "test_payments.py"))
        self.assertEqual(out.get("decision"), None)


class TestEveryWritePassesAGovernedChannel(unittest.TestCase):
    """Invariant 2 — the MCP-is-the-only-channel rule, asserted instead of assumed."""

    #: Mutators the MCP layer deliberately does NOT expose, each with the reason. The human interview
    #: is the only thing that elects, so `decide` and `accept` having no tool is the design, not a
    #: gap — exposing them would hand an agent the one power the whole package withholds.
    HUMAN_ONLY = {
        "decide": "no tool of its own; every path to it is enumerated and gated by "
                  "TestEveryPathToDecideIsGated below — which is the honest form of this claim. It "
                  "used to read 'reached only through record_decision', and that was false: "
                  "expand_catalog and apply_policy also reach it, and a fan-out flag on "
                  "record_decision reached it four times per call",
        "accept": "same channel: record_decision(accept_as_is=True), gated to design_concern",
        "add_policy": "reached only through record_policy, which records a policy the human elected "
                      "— from an offer taken verbatim, or quoted — and cannot set one",
        "apply_policy": "same channel: the cascade is what electing a policy MEANS, so it runs "
                        "inside record_policy, once, on the policy just elected — never as a step "
                        "an agent can take alone or re-run over pins nobody was shown",
    }
    #: Mutators reached through another governed entry point rather than a tool of their own.
    #:
    #: Four entries left here in v0.16, and every one of them was a state the product could not
    #: reach. `set_question` had ZERO call sites anywhere and was exempted as "the interview funnel
    #: writes it" (`interview.funnel` reads). `add_proposals` is the only writer of the
    #: `brainstorming` state and nothing called it. `reopen`'s reason described *when* it should run
    #: and never said what runs it. `challenge`'s said "exposed as challenge_oracle, which applies
    #: upheld ChallengeEvents" — false of that function, which only proposes. All four now have
    #: tools, and `TestAnINTERNALMutatorIsActuallyReached` is why a fifth cannot be parked here on a
    #: sentence: an exemption whose stated reason is wrong is worse than none, because the check has
    #: then been asked and answered.
    INTERNAL = {
        "assign_resolution_modes": "runs inside the interview funnel",
        "set_governance": "stamped automatically by tools._open_or_create — the server knows its "
                          "own root and version, so this is never a question put to a model",
        "save": "persistence, not a state transition",
    }

    def _mutators(self) -> set:
        """Public Ledger methods that write. Read-only views are excluded by name, and the list of
        exclusions is short and explicit so a new writer cannot hide among them."""
        readonly = {"pin", "interview_view", "summary", "foresight", "policy_preview",
                    "question_offers", "unasked_verdict", "settlement_verdict", "reopen_verdict",
                    # v0.20: reads the `cas_` records `_reopen_minimal` appended and returns their
                    # pin ids. It is on this list rather than in INTERNAL because it writes nothing
                    # — the whole reason it exists is that the tool layer was deriving that radius
                    # from a substate instead of reading the records.
                    "cascaded_by",
                    # v0.21: the container half of the guarded read path. Both return a NEW list of
                    # the entries a reader may index; neither touches `self.data`. They are here
                    # and not in INTERNAL for `cascaded_by`'s reason — INTERNAL is for writers
                    # reached through another door, and a reader reached through no door at all is
                    # not a write path anybody needs to govern.
                    "readable", "readable_pins",
                    # v0.26: `pin`'s twin on the WRITE path, and it is here for exactly the reason
                    # `pin` is. It looks a record up and REFUSES when this runtime cannot read it;
                    # it assigns nothing. Naming it a mutator because every mutator calls it would
                    # make the classification a claim about who its callers are rather than about
                    # what it does — and its callers are already the governed doors.
                    "writable_pin",
                    # v0.28: the same pair one level out. `writable_collection` returns the list the
                    # file already holds or refuses; `writable_pins` returns `(record, read)` pairs
                    # built from it. Both look up and refuse, and neither assigns — what a caller
                    # does with the records they hand back is the caller's transition, and every one
                    # of those callers is already a governed door.
                    "writable_collection", "writable_pins"}
        out = set()
        for name, fn in inspect.getmembers(ledgermod.Ledger, inspect.isfunction):
            if name.startswith("_") or name in readonly:
                continue
            out.add(name)
        return out

    def test_no_mutator_is_unclassified(self):
        import tools as mcp_tools
        exposed = {n for n, _ in inspect.getmembers(mcp_tools, inspect.isfunction)}
        unclassified = []
        for name in sorted(self._mutators()):
            if name in self.HUMAN_ONLY or name in self.INTERNAL:
                continue
            # a tool named for the method, or the ledger_-prefixed form of it
            if name in exposed or f"ledger_{name}" in exposed:
                continue
            unclassified.append(name)
        self.assertEqual(unclassified, [],
                         "every ledger mutator needs a declared channel: an MCP write tool, "
                         "HUMAN_ONLY, or INTERNAL with the reason. An unclassified writer is a "
                         "write path nobody governs.")

    def test_an_agent_can_record_an_election_but_never_make_one(self):
        """The invariant is about who CHOOSES, and it used to be enforced by having no tool at all.

        That conflated choosing with writing. It did stop an agent electing — and it also stopped
        the human being recorded, so once the CLI went away no pin on any host could reach
        `decided`, and everything hanging off that state (the DecisionEvent, flip_criteria, the
        reopen loop, `roadmap = diff(to_be, as_is)`) was unreachable with the tests green.

        So the assertion moves from "the capability does not exist" to "the capability cannot be
        abused", which is the stronger claim: the outcome must come from the pin's own question.
        """
        import tools as mcp_tools
        exposed = {n for n, _ in inspect.getmembers(mcp_tools, inspect.isfunction)}
        for forbidden in ("decide", "ledger_decide", "accept", "ledger_accept"):
            self.assertNotIn(forbidden, exposed, "no tool may elect on the caller's own authority")
        self.assertIn("record_decision", exposed, "the human needs a door, or nothing is ever decided")

        led = ledgermod.Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        pin = led.add_pin(
            kind="design_concern", title="three near-identical blocks", severity="low",
            confidence="inferred", provenance=[{"source": "recon", "detail": "x"}],
            as_is={"current_design": "copy-paste", "concern": "drift"},
            question={"prompt": "Consolidate?",
                      "options": [{"id": "keep", "label": "leave it"},
                                  {"id": "extract", "label": "extract a helper"}],
                      "allow_freeform": True})
        led.save()

        with self.assertRaises(ValueError, msg="an outcome outside the offered menu is an election"):
            mcp_tools.record_decision(led.path, pin["id"], "rewrite_in_rust",
                                      rationale="r", flip_criteria="f", human_answer="do that")
        # The freeform refusal, exercised on the only kind of file that can still carry a closed
        # menu. v0.20 moved `allow_freeform` into `_validate_question`, so no door writes `False`
        # any more — but `record_decision`'s refusal governs ledgers written before that, exactly as
        # `nonconforming` and `decision_rung` govern the events older runtimes wrote. So the flag is
        # flipped on the saved file, not passed to a door: a rule enforced at the write governs no
        # file that already exists, which is why the read side keeps its branch.
        def _rewrite(flag):
            with open(led.path, encoding="utf-8") as fh:
                data = json.load(fh)
            data["pins"][0]["question"]["allow_freeform"] = flag
            with open(led.path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)

        _rewrite(False)
        with self.assertRaises(ValueError, msg="freeform must be permitted by the question"):
            mcp_tools.record_decision(led.path, pin["id"], "freeform",
                                      rationale="r", flip_criteria="f", human_answer="something else")
        _rewrite(True)
        with self.assertRaises(ValueError, msg="relaying without a quote is an unfalsifiable claim"):
            mcp_tools.record_decision(led.path, pin["id"], "extract", rationale="r", flip_criteria="f")

        out = mcp_tools.record_decision(led.path, pin["id"], "extract", rationale="r",
                                        flip_criteria="if the helper grows a second caller shape",
                                        human_answer="yes, pull the helper out")
        self.assertEqual((out["state"], out["outcome"], out["evidence"]),
                         ("decided", "extract", "transcribed"))
        event = ledgermod.Ledger(led.path).data["decision_log"][-1]
        self.assertEqual(event["human_answer"], "yes, pull the helper out",
                         "the words the decision rests on must be in the ledger, not only in a chat")

    def test_an_agent_can_record_a_policy_election_but_never_make_one(self):
        """The same invariant one level up, where the leverage is: a policy decides a whole cluster.

        It had no door at all — `add_policy`/the cascade were reachable by nothing on any host,
        while four shipped passages told an agent the user elects a policy and that it then
        cascades. The door added here must not become the shortcut the absence was protecting
        against, so what it refuses is asserted before what it writes.
        """
        import tools as mcp_tools
        exposed = {n for n, _ in inspect.getmembers(mcp_tools, inspect.isfunction)}
        self.assertNotIn("add_policy", exposed, "a policy is elected, never set by an agent")
        self.assertIn("record_policy", exposed, "the human needs a door, or nothing ever cascades")

        led = ledgermod.Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        fork = {"prompt": "Which layer is truth?",
                "allow_freeform": True,
                "options": [{"id": "db", "label": "the DB"}, {"id": "api", "label": "the API"}]}
        pins = [led.add_pin(kind="contract_mismatch", title=f"drift {i}", severity=sev,
                            confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                            cluster_id="cl_shape", as_is={"db": "int", "api": "string"},
                            question=fork)
                for i, sev in enumerate(("low", "medium", "blocker"))]
        led.save()

        with self.assertRaises(ValueError, msg="a policy needs a rule, a scope and an outcome"):
            mcp_tools.record_policy(led.path, applies_to={"cluster_id": "cl_shape"},
                                    human_answer="db wins")
        with self.assertRaises(ValueError, msg="relaying a policy without a quote is unfalsifiable"):
            mcp_tools.record_policy(led.path, rule="DB wins", default_outcome="db",
                                    applies_to={"cluster_id": "cl_shape"})
        with self.assertRaises(ValueError, msg="an offer the catalog never made is an invention"):
            mcp_tools.record_policy(led.path, offer_id="cl_not_a_cluster", human_answer="sure")
        with self.assertRaises(ValueError, msg="an excepted pin that does not exist excepts nothing"):
            mcp_tools.record_policy(led.path, rule="DB wins", default_outcome="db",
                                    applies_to={"cluster_id": "cl_shape"},
                                    exceptions=["pin_9999"], human_answer="db wins")

        preview = mcp_tools.policy_prompt(led.path, rule="DB wins", default_outcome="db",
                                          applies_to={"cluster_id": "cl_shape"})
        out = mcp_tools.record_policy(led.path, rule="DB wins", default_outcome="db",
                                      applies_to={"cluster_id": "cl_shape"},
                                      human_answer="the DB wins unless I flag one")
        self.assertEqual(out["cascaded"], preview["would_decide"],
                         "what the user was shown must be what the cascade did")
        self.assertEqual(out["held_back"], [pins[2]["id"]],
                         "blocker|high is never settled by a policy — the threshold rule")
        self.assertEqual(out["not_offered"], [],
                         "these pins all pose the fork this policy answers")
        after = ledgermod.Ledger(led.path)
        event = after.data["decision_log"][-1]
        self.assertEqual((event["evidence"], event["policy_id"]), ("cascaded", out["policy_id"]))
        self.assertEqual(after.data["policies"][-1]["human_answer"],
                         "the DB wins unless I flag one",
                         "the words a whole cluster rests on must be in the ledger, not a chat")

    def test_the_classification_itself_stays_honest(self):
        """A stale exemption is worse than none: it names a method that no longer exists and reads
        as governance while covering nothing."""
        mutators = self._mutators()
        stale = sorted((set(self.HUMAN_ONLY) | set(self.INTERNAL)) - mutators)
        self.assertEqual(stale, [], "these exemptions name methods that are gone")

    def test_an_INTERNAL_mutator_is_actually_reached(self):
        """The inverse gate, and the one that would have caught four exemptions at once.

        `test_no_mutator_is_unclassified` asks whether every writer has a *declared* channel. It
        cannot ask whether the declaration is TRUE, and for four versions it was not: `set_question`
        and `add_proposals` had zero call sites in anything that ships, `reopen` had none either, and
        `challenge`'s only caller was `challenger.run`, which nothing calls. Each carried a sentence
        naming an entry point, and the sentences were prose. `check_tool_carriers.py` sees write
        tools that EXIST and are named by nobody; it cannot see a capability that was never given a
        tool, and this is the direction it does not cover.

        So the carrier is the call graph, not the reason string: an INTERNAL mutator must be reached
        transitively from something an agent can call, computed over the ASTs of `src/runtime/*.py`
        and `src/mcp/*.py`, rooted at the functions of `tools.py` that `server.py` actually serves.
        `HUMAN_ONLY` is held to the same standard — `decide` is withheld from agents, not from the
        product, and a `decide` nothing reaches is the state nobody can produce all over again.
        """
        ast_ = TestEveryPathToDecideIsGated
        modules = ast_._modules()
        served = {n.name for n in modules["server.py"].body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                          and d.func.attr == "tool" for d in n.decorator_list)}
        self.assertGreater(len(served), 40, "no @mcp.tool functions found — this gate went vacuous")
        edges = {}
        for tree in modules.values():
            for name, fn in ast_._functions(tree).items():
                edges.setdefault(name, set()).update(ast_._calls(fn))
        reachable, frontier = set(), list(served)
        while frontier:
            name = frontier.pop()
            for callee in edges.get(name, ()):  # names, by final component — the same rule as above
                if callee not in reachable:
                    reachable.add(callee)
                    frontier.append(callee)
        unreached = sorted(n for n in (set(self.INTERNAL) | set(self.HUMAN_ONLY))
                           if n not in reachable)
        self.assertEqual(unreached, [],
                         "these ledger mutators are exempted from having a tool AND are called by "
                         "nothing an agent can reach. That is not a governed channel, it is a state "
                         "the runtime can produce and the product cannot — give it a door or delete "
                         "it, and never leave the reason as a sentence nobody re-checked.")


class TestEveryPathToDecideIsGated(unittest.TestCase):
    """Invariant 3 — CLOSE THE CLASS: enumerate every path to `Ledger.decide` structurally, and
    assert each one reaches the single predicate.

    Why this class exists, and why it is AST and not prose. The offered-options rule was implemented
    once per door: on the single-pin door, then (a version later, after it was found missing) on the
    policy door. An adversarial reviewer then drove the identical violation through **two doors
    nobody had looked at** — `decide(apply_to_cluster=True)`, which fanned one answer across a whole
    cluster, and `interview_expand(brief_decisions=...)`, which wrote any string onto any cluster at
    any severity. 617 tests and eight green linters missed all of it, because every test asked
    whether a *known* door was guarded.

    So the assertion is not "these doors are guarded". It is **"these are all the doors"**, computed
    from the source rather than remembered, plus "each reaches the predicate". A door added later
    fails `test_the_enumeration_is_complete` on the day it is added.

    Scope is what ships and can write: `src/runtime/*.py` and `src/mcp/*.py`. `scripts/` and
    `tests/` call `decide` freely and are dev-only by construction — they are not a channel an agent
    reaches on any host.
    """

    ROOTS = ("runtime", "mcp")
    #: The single predicate, in its two halves. `unasked_verdict` composes the severity threshold
    #: with `question_offers`; `question_offers` is the offered-options rule itself, and is what the
    #: single-pin door reaches directly (the threshold does not apply where the human WAS asked).
    PREDICATES = ("unasked_verdict", "question_offers")

    #: Every function that calls `Ledger.decide`, and the call chain by which it reaches a predicate.
    #: Each hop is checked as an AST edge, so the chain cannot be aspirational. Hops are
    #: module-qualified: `policy_preview` names both a Ledger method and an MCP tool, and a chain
    #: that resolved to the wrong one would pass while proving nothing.
    DECIDE_CALLERS = {
        ("ledger.py", "accept"): [],
        ("ledger.py", "defer"): [],
        ("ledger.py", "apply_policy"): [("ledger.py", "policy_preview"),
                                        ("ledger.py", "unasked_verdict")],
        ("interview.py", "expand_catalog"): [("ledger.py", "unasked_verdict")],
        ("tools.py", "record_decision"): [("ledger.py", "question_offers")],
    }
    #: The callers with an empty chain need their reason here, or "no gate" reads as an oversight.
    #: Both are meta-answers about scope rather than branches of the pin's own fork, so the
    #: offered-options half of the predicate has nothing to check — and neither is unasked, which is
    #: what the other half is for. What holds them is `settlement_verdict` plus the quote their MCP
    #: door demands, and `TestLeavingTheOpenSetIsGovernedToo` is where that is asserted.
    UNGATED = {
        ("ledger.py", "accept"): "not a door: `accept` is reached only from record_decision's "
                                 "accept_as_is branch, which gates it on kind == design_concern and "
                                 "on the human having been shown this pin. Its outcome is `keep`, "
                                 "which is the leave-as-is answer rather than an elected option.",
        ("ledger.py", "defer"): "not a door: `defer` is reached only from ledger_defer, which "
                                "demands the human's verbatim answer exactly as record_decision "
                                "does. Its outcome is `defer` — the not-now answer, which the "
                                "spec's own question shape offers as an option — rather than an "
                                "elected branch of this pin's fork.",
    }

    @classmethod
    def _modules(cls) -> dict:
        base = os.path.join(os.path.dirname(__file__), "..", "src")
        out = {}
        for root in cls.ROOTS:
            for path in sorted(os.listdir(os.path.join(base, root))):
                if path.endswith(".py"):
                    full = os.path.join(base, root, path)
                    with open(full, encoding="utf-8") as fh:
                        out[path] = ast.parse(fh.read(), filename=full)
        return out

    @staticmethod
    def _functions(tree: ast.AST) -> dict:
        """name -> node, for every def in the module (methods included)."""
        return {n.name: n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    @staticmethod
    def _calls(node: ast.AST) -> set:
        """The names this function calls, by the final component: `x.decide()` and `decide()` both
        count as `decide`. Nested defs are excluded — they are their own callers."""
        out, inner = set(), {c for n in ast.iter_child_nodes(node)
                             for c in ast.walk(n)
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for child in ast.walk(node):
            if child in inner or not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Attribute):
                out.add(func.attr)
            elif isinstance(func, ast.Name):
                out.add(func.id)
        return out

    def _callers_of(self, name: str) -> set:
        found = set()
        for module, tree in self._modules().items():
            for fn_name, fn in self._functions(tree).items():
                if fn_name == name:
                    continue                       # the definition itself is not a caller
                if name in self._calls(fn):
                    found.add((module, fn_name))
        return found

    def test_the_enumeration_is_complete(self):
        """The load-bearing assertion of this file: set EQUALITY against the source."""
        self.assertEqual(
            self._callers_of("decide"), set(self.DECIDE_CALLERS),
            "a path to Ledger.decide was added or removed. Every one must be declared here WITH the "
            "chain by which it reaches the predicate — that is what stops the next door from being "
            "the third one nobody looked at.")

    def test_every_path_reaches_the_predicate(self):
        modules = self._modules()
        for (module, caller), chain in sorted(self.DECIDE_CALLERS.items()):
            with self.subTest(caller=f"{module}::{caller}"):
                if not chain:
                    self.assertIn((module, caller), self.UNGATED,
                                  "a path with no gate needs a stated reason, or it is a hole")
                    continue
                self.assertIn(chain[-1][1], self.PREDICATES,
                              "a chain must END at the predicate, not merely at something plausible")
                current = self._functions(modules[module])[caller]
                for hop_module, hop in chain:
                    self.assertIn(hop, self._calls(current),
                                  f"{caller} does not call {hop} — the declared chain is prose")
                    current = self._functions(modules[hop_module])[hop]

    def test_the_predicate_is_one_predicate_and_not_two(self):
        """`unasked_verdict` must be built ON `question_offers`, not beside it. Two functions that
        happen to agree today are the shape this whole class exists to refuse."""
        fns = self._functions(self._modules()["ledger.py"])
        self.assertIn("question_offers", self._calls(fns["unasked_verdict"]))

    # -- and the same four paths, exercised ---------------------------------

    FORK = {"prompt": "Consolidate?",
            "options": [{"id": "keep", "label": "leave it"},
                        {"id": "extract", "label": "extract a helper"}],
            "allow_freeform": True}
    OTHER = {"prompt": "Which layer is truth?",
             "allow_freeform": True,
             "options": [{"id": "db", "label": "the DB"}, {"id": "api", "label": "the API"}]}
    PROV = [{"source": "recon", "detail": "x"}]

    def _cluster(self):
        led = ledgermod.Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(kind="design_concern", title="the pin the human saw", severity="low",
                    confidence="inferred", provenance=self.PROV, cluster_id="cl_dupe",
                    as_is={"current_design": "copy-paste", "concern": "drift"}, question=self.FORK)
        led.add_pin(kind="contract_mismatch", title="offers only db|api", severity="low",
                    confidence="extracted", provenance=self.PROV, cluster_id="cl_dupe",
                    as_is={"db": "int", "api": "string"}, question=self.OTHER)
        led.add_pin(kind="defect", title="poses no question at all", severity="low",
                    confidence="extracted", provenance=self.PROV, cluster_id="cl_dupe",
                    as_is={"description": "d"})
        led.add_pin(kind="design_concern", title="a blocker", severity="blocker",
                    confidence="inferred", provenance=self.PROV, cluster_id="cl_dupe",
                    as_is={"current_design": "x", "concern": "y"}, question=self.FORK)
        led.save()
        return led

    def test_the_single_pin_door_decides_one_pin(self):
        import tools as mcp_tools
        led = self._cluster()
        out = mcp_tools.record_decision(led.path, "pin_0001", "extract", rationale="r",
                                        flip_criteria="a second caller shape appears",
                                        human_answer="yes, pull the helper out")
        after = ledgermod.Ledger(led.path)
        self.assertEqual((out["state"], len(after.data["decision_log"])), ("decided", 1))
        self.assertEqual([p["state"] for p in after.data["pins"]],
                         ["decided", "needs_input", "detected", "needs_input"],
                         "one human answer, one pin — the siblings are still open questions")

    def test_the_cluster_fan_out_is_not_a_parameter_anywhere(self):
        """Asserted at both boundaries an agent can reach, because the flag was declared on the
        server, forwarded by the tool and applied by the library — three files, one hole."""
        import inspect
        import tools as mcp_tools
        for fn in (ledgermod.Ledger.decide, mcp_tools.record_decision):
            self.assertNotIn("apply_to_cluster", inspect.signature(fn).parameters,
                             f"{fn.__qualname__} can fan one answer across pins nobody was shown")

    def test_the_policy_cascade_holds_back_what_the_predicate_refuses(self):
        import tools as mcp_tools
        led = self._cluster()
        out = mcp_tools.record_policy(led.path, rule="extract the helper everywhere",
                                      default_outcome="extract",
                                      applies_to={"cluster_id": "cl_dupe"},
                                      human_answer="extract it wherever it repeats")
        self.assertEqual(out["cascaded"], ["pin_0001"])
        self.assertEqual(out["not_offered"], ["pin_0002", "pin_0003"])
        self.assertEqual(out["held_back"], ["pin_0004"])

    def test_the_brief_is_held_to_the_same_predicate(self):
        import interview
        led = self._cluster()
        catalog = {"clusters": [
            {"id": "persistence", "order": 1, "kind": "open_decision", "severity": "high",
             "title": "Persistence", "options": [{"id": "relational", "label": "SQL"}]},
            {"id": "sync", "order": 2, "kind": "open_decision", "severity": "medium",
             "title": "Sync", "options": [{"id": "reqresp", "label": "request/response"}]}]}
        result = interview.expand_catalog(led, catalog, project_type="web-saas", brief_decisions={
            # offered, but `high` — the threshold holds
            "persistence": {"outcome": "relational", "quote": "postgres, schema-first"},
            # medium, but nothing offers it
            "sync": {"outcome": "mongodb", "quote": "mongo everywhere"}})
        self.assertEqual(result["pre_decided"], [])
        self.assertEqual([h["reason"] for h in result["brief_held_back"]],
                         ["held_back", "not_offered"])


class TestEveryWriteTimeRuleGainsItsReader(unittest.TestCase):
    """Invariant 4 — CLOSE THE OTHER HALF OF THE CLASS: a rule the writer enforces must be a rule
    the reader can replay over a file written before it existed.

    v0.13 named this failure — *"a new rule arrives with a writer and no reader"* — and then shipped
    it: `decide()` held six checks inline, `nonconforming` re-implemented **one** of them by hand,
    and nothing made the next one gain a reader. Invariant 3 is the same shape one axis over (there:
    every DOOR reaches the predicate; here: every RULE reaches the floor), and both are asserted
    from the source rather than from a list somebody maintains.

    The AST is the carrier because the alternative — "we will remember to add it to the table" — is
    exactly what failed. A `_require` added back into `decide` fails on the day it is added.
    """

    #: The AST reader is invariant 3's, deliberately: two readers of the same source in one file
    #: would be the duplication these invariants exist to refuse.
    AST = TestEveryPathToDecideIsGated

    def test_decide_holds_no_rule_outside_the_shared_table(self):
        fns = self.AST._functions(self.AST._modules()["ledger.py"])
        calls = self.AST._calls(fns["decide"])
        self.assertNotIn("_require", calls,
                         "a rule enforced inline in `decide` is invisible to `nonconforming`, so "
                         "every ledger already on disk keeps claiming a conformance it was never "
                         "checked for. Put it in EVENT_RULES.")
        self.assertIn("_check_event", calls, "the writer must run the shared table")

    def test_the_floor_is_the_same_table_and_not_a_copy_of_it(self):
        fns = self.AST._functions(self.AST._modules()["ledger.py"])
        self.assertIn("event_violations", self.AST._calls(fns["nonconforming"]),
                      "the floor must REPLAY the writer's rules, not re-state them")
        self.assertIn("EVENT_RULES",
                      {n.id for n in ast.walk(fns["_check_event"]) if isinstance(n, ast.Name)},
                      "the writer must iterate the table itself, not a private copy of it")

    def test_a_rule_added_to_the_table_is_reported_by_the_floor_without_being_taught(self):
        """The counterfactual, run rather than asserted: append a rule to the table and the floor
        reports it — which is what 'gains its reader by construction' has to mean."""
        original = ledgermod.EVENT_RULES
        try:
            ledgermod.EVENT_RULES = original + (
                ("a_rule_added_later", lambda e: e.get("outcome") != "planted",
                 lambda e: "planted"),)
            # A WHOLE ledger, not just the log: since v0.21 the floor also reports a collection
            # that is not there (`collection_shape`), so a fixture missing two of the three would
            # be testing this rule against a file that breaks a different one.
            out = ledgermod.nonconforming({"pins": [], "policies": [],
                                           "decision_log": [{"id": "ev_0001", "outcome": "planted",
                                                             "source": "interview",
                                                             "evidence": "brief",
                                                             "brief_quote": "one relational store",
                                                             "flip_criteria": "x"}]})
            self.assertEqual(out, {"a_rule_added_later": ["ev_0001"]})
        finally:
            ledgermod.EVENT_RULES = original


class TestGovernanceIsStamped(unittest.TestCase):
    def test_an_ungoverned_decision_says_so_instead_of_omitting_the_field(self):
        led = ledgermod.Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        pin = led.add_pin(kind="defect", title="t", severity="low", confidence="extracted",
                          provenance=[{"source": "x", "detail": "y"}], as_is={"description": "d"})
        led.decide(pin["id"], "o", "r", "f")
        event = led.data["decision_log"][-1]
        self.assertIn("policy_hash", event)
        self.assertIsNone(event["policy_hash"])

    def test_a_permission_change_is_a_hash_delta_in_the_trail(self):
        import governance
        tmp = tempfile.mkdtemp()
        roster = os.path.join(tmp, "agents.md")
        with open(roster, "w", encoding="utf-8") as fh:
            fh.write("- reviewer -> edit: deny\n")
        led = ledgermod.Ledger(os.path.join(tmp, "ledger.json"))
        led.set_governance(governance.record(roster=roster, spec_version="0.9"))
        pin = led.add_pin(kind="defect", title="t", severity="low", confidence="extracted",
                          provenance=[{"source": "x", "detail": "y"}], as_is={"description": "d"})
        led.decide(pin["id"], "o", "r", "f")
        before = led.data["decision_log"][-1]["policy_hash"]

        with open(roster, "w", encoding="utf-8") as fh:
            fh.write("- reviewer -> edit: allow\n")          # the permission widens
        led.set_governance(governance.record(roster=roster, spec_version="0.9"))
        led.decide(pin["id"], "o2", "r", "f")
        after = led.data["decision_log"][-1]["policy_hash"]

        self.assertIsNotNone(before)
        self.assertNotEqual(before, after)

    def test_an_unresolvable_input_is_reported_not_dropped(self):
        import governance
        rec = governance.record(roster="/nope/agents.md", spec_version="0.9")
        self.assertIn("roster", rec["missing"])



class TestAMarkWithNoClearingDoorIsWrittenForAStandingReason(unittest.TestCase):
    """v0.18. `resolution_mode: "asked"` is **permanent** — nothing in this package clears it, and
    since v0.16 `unasked_verdict` reads it as the pin's own standing demand. That makes every writer
    of it a decision about the pin's whole future, so the writers are enumerated by set EQUALITY
    over the AST, each with the reason, exactly as the callers of `decide` and `_settle` are.

    The gap this closes is the one that made §12 possible: a seventh writer could be added for a
    seventh reason, and none of the six carried its reason anywhere a reader could compare. Two of
    them carried it as a code comment while a policy cascade contradicted them.

    **No door clears the mark, and none should** — a door that unsets *this must be asked* is a door
    that can silence the severity threshold, and an agent could reach it. So the correctness of the
    field rests entirely on this list.
    """

    AST = TestEveryPathToDecideIsGated

    #: `(module, function)` -> why this pin's demand to be asked is a STANDING property of the pin.
    #: Every entry has to survive the question "would this still be true after any later rule runs?"
    #: — which `not_offered` does not, and which is why `apply_policy` and `expand_catalog` now
    #: consult `ledger.STANDING_REFUSALS` instead of marking every pin they did not decide.
    WRITERS = {
        ("ledger.py", "surface_assumption"):
            "a forced assumption is vetoable BY A HUMAN — that is the whole of what surfacing it "
            "means, and no cascade may take the veto away",
        ("ledger.py", "apply_policy"):
            "the severity threshold and a mark the pin already carries, via STANDING_REFUSALS. It "
            "used to mark `not_offered` too, which is a fact about the RULE's fit and put the pin "
            "beyond every later policy for ever",
        ("ledger.py", "assign_resolution_modes"):
            "the funnel's opening split: blocker|high are asked, the medium|low tail may batch",
        # `cross_derive` wrote this itself until v0.24, for the reason *a contested claim is never
        # re-defaulted silently*. Same reason, same mark — through the arcs' one writer now, which
        # is what made the rest of that writer's obligations reach it too.
        ("ledger.py", "_reopen_minimal"):
            "a reopened truth is never re-defaulted silently — production, the challenger or a "
            "provider disagreement just falsified the last answer, and re-defaulting it would "
            "answer it the same way again",
        ("ledger.py", "mark_correctness_unknown"):
            "the pin carries the fork that asks what to do about work nobody could verify; a "
            "cascade answering it would be the silent close this state exists to prevent",
        ("interview.py", "expand_catalog"):
            "the brief's own threshold half, via STANDING_REFUSALS — same predicate, same tuple, "
            "and it had the identical `not_offered` defect for the identical reason",
    }

    def _asked_writers(self) -> set:
        """Every function that assigns the literal `"asked"` to a `resolution_mode` subscript.

        Anchored on the assignment node, not on a grep for the word: the carrier is the write."""
        found = set()
        for module, tree in self.AST._modules().items():
            for fn_name, fn in self.AST._functions(tree).items():
                for node in ast.walk(fn):
                    if not isinstance(node, ast.Assign):
                        continue
                    if not any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                               and t.slice.value == "resolution_mode" for t in node.targets):
                        continue
                    if any(isinstance(c, ast.Constant) and c.value == "asked"
                           for c in ast.walk(node.value)):
                        found.add((module, fn_name))
        return found

    def test_the_enumeration_of_writers_is_complete(self):
        self.assertEqual(self._asked_writers(), set(self.WRITERS),
                         "a writer of a mark nothing can clear needs its reason declared here. If "
                         "the reason is about a RULE rather than about the pin, it does not belong "
                         "on the pin at all — that is what v0.18 removed.")

    def test_nothing_clears_the_mark_anywhere(self):
        """The other half, and the reason the list above is load-bearing rather than documentation.
        A `del pin["resolution_mode"]`, or an assignment of anything else over an existing `asked`,
        would be a door that can silence the threshold rule."""
        offenders = []
        for module, tree in self.AST._modules().items():
            for fn_name, fn in self.AST._functions(tree).items():
                for node in ast.walk(fn):
                    if isinstance(node, ast.Delete):
                        for t in node.targets:
                            if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                                    and t.slice.value == "resolution_mode"):
                                offenders.append((module, fn_name, "del"))
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "pop" and node.args
                            and isinstance(node.args[0], ast.Constant)
                            and node.args[0].value == "resolution_mode"):
                        offenders.append((module, fn_name, "pop"))
        self.assertEqual(offenders, [],
                         "nothing clears `resolution_mode`, deliberately — fix the writer instead")

    def test_the_shared_tuple_is_what_both_unasked_doors_read(self):
        """One rule, one home. The two writers that turn an `unasked_verdict` bucket into the mark
        are the two that had the same bug, and a rule spelled out at two doors is a rule one of them
        gets fixed without."""
        import ledger as ledgermod_
        self.assertEqual(ledgermod_.STANDING_REFUSALS, ("held_back", "must_be_asked"))
        for bucket in ledgermod_.STANDING_REFUSALS:
            self.assertIn(bucket, ledgermod_.UNASKED_BUCKETS)
        self.assertNotIn("not_offered", ledgermod_.STANDING_REFUSALS)

        readers = set()
        for module, tree in self.AST._modules().items():
            for fn_name, fn in self.AST._functions(tree).items():
                if any(isinstance(n, ast.Name) and n.id == "STANDING_REFUSALS"
                       for n in ast.walk(fn)):
                    readers.add((module, fn_name))
        self.assertEqual(readers, {("ledger.py", "apply_policy"),
                                   ("interview.py", "expand_catalog")},
                         "these are the two writes that settle a pin nobody was shown, so these "
                         "are the two that decide what a refusal records on the pin")

if __name__ == "__main__":
    unittest.main()
