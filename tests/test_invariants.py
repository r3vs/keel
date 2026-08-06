"""Two BEHAVIORAL invariant tests — not unit tests (Block 4 of docs/design/sota-alignment.md).

The difference matters and is the reason these live in their own file. A unit test asks whether a
function returns the right value. These ask whether a *rule the package promises* actually holds at
the seam where it would be broken:

1. an action on a protected path makes the gate **fire** — and the assertion is on the gate's own
   output, never on "the task finished". A test that only checks completion passes just as happily
   when the gate never ran, which is the exact way a security control rots into decoration.
2. every state-mutating path on the ledger goes through a **governed channel** — asserted, rather
   than agreed. Adding a mutator without deciding its channel fails here.

Stdlib unittest (also runs under pytest).
"""
from __future__ import annotations

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
                question={"prompt": "which one?", "options": [{"id": "a", "label": "A"}]})
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
        "decide": "reached only through record_decision, which records an election and cannot make one",
        "accept": "same channel: record_decision(accept_as_is=True), gated to design_concern",
        "add_policy": "reached only through record_policy, which records a policy the human elected "
                      "— from an offer taken verbatim, or quoted — and cannot set one",
        "apply_policy": "same channel: the cascade is what electing a policy MEANS, so it runs "
                        "inside record_policy, once, on the policy just elected — never as a step "
                        "an agent can take alone or re-run over pins nobody was shown",
    }
    #: Mutators reached through another governed entry point rather than a tool of their own.
    INTERNAL = {
        "set_question": "the interview funnel writes it (interview_next drives the surface)",
        "add_proposals": "the brainstorm agent's own write path; neutral by schema",
        "assign_resolution_modes": "runs inside the interview funnel",
        "reopen": "the feedback loop's downstream arc, driven by a fired flip_signal",
        "challenge": "exposed as challenge_oracle, which applies upheld ChallengeEvents",
        "set_governance": "stamped automatically by tools._open_or_create — the server knows its "
                          "own root and version, so this is never a question put to a model",
        "save": "persistence, not a state transition",
    }

    def _mutators(self) -> set:
        """Public Ledger methods that write. Read-only views are excluded by name, and the list of
        exclusions is short and explicit so a new writer cannot hide among them."""
        readonly = {"pin", "interview_view", "summary", "foresight", "policy_preview",
                    "question_offers"}
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
                      "allow_freeform": False})
        led.save()

        with self.assertRaises(ValueError, msg="an outcome outside the offered menu is an election"):
            mcp_tools.record_decision(led.path, pin["id"], "rewrite_in_rust",
                                      rationale="r", flip_criteria="f", human_answer="do that")
        with self.assertRaises(ValueError, msg="freeform must be permitted by the question"):
            mcp_tools.record_decision(led.path, pin["id"], "freeform",
                                      rationale="r", flip_criteria="f", human_answer="something else")
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


if __name__ == "__main__":
    unittest.main()
