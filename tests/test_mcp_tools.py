"""The MCP tool bodies — stdlib only, no FastMCP, no subprocess. Runs in CI unconditionally.

`src/mcp/tools.py` is the part that is ours; `server.py` is a FastMCP adapter whose correctness is
FastMCP's problem. So the logic is tested here with nothing installed, and the protocol is smoke-
tested separately (test_mcp_server.py) where it can be skipped if uv is absent.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))
import tools  # noqa: E402
from ledger import Ledger  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _ledger_with_pins(tmp):
    led = Ledger(os.path.join(tmp, "ledger.json"))
    led.add_pin(kind="contract_mismatch", title="users.email nullable in DB, required in API",
                severity="high", confidence="extracted",
                provenance=[{"source": "contract_recon", "detail": "db↔api shape diff"}])
    led.add_pin(kind="design_concern", title="no rate limiting on the public API",
                severity="low", confidence="inferred",
                provenance=[{"source": "reviewer", "detail": "judgment, not a defect"}])
    led.save()
    return led.path


class TestReadOnlyTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = _ledger_with_pins(self.tmp)

    def test_ledger_summary_counts_real_pins(self):
        out = tools.ledger_summary(self.ledger)
        self.assertIsInstance(out, dict)
        self.assertTrue(out, "a ledger with two pins must not summarize to nothing")

    def test_interview_next_returns_the_funnel_view(self):
        self.assertIsNotNone(tools.interview_next(self.ledger))

    def test_build_waves_levels_the_dag(self):
        self.assertIn("waves", tools.build_waves(self.ledger))

    def test_challenge_oracle_proposes_and_does_not_decide(self):
        with open(self.ledger, encoding="utf-8") as fh:
            before = json.load(fh)
        out = tools.challenge_oracle(self.ledger)
        self.assertIn("proposed", out)
        with open(self.ledger, encoding="utf-8") as fh:
            after = json.load(fh)
        self.assertEqual(before, after, "challenge_oracle must not mutate the ledger — it proposes")

    def test_reads_refuse_a_missing_ledger_instead_of_inventing_an_empty_one(self):
        # Ledger(path) creates a fresh ledger when the file is absent — right for writes, a trap
        # for reads: a mistyped path would answer "no pins" and the agent would conclude there is
        # nothing to do. Every read tool must refuse rather than answer confidently and wrongly.
        missing = os.path.join(self.tmp, "nope.json")
        for name in ("ledger_summary", "interview_next", "build_waves", "challenge_oracle"):
            with self.subTest(tool=name), self.assertRaises(FileNotFoundError):
                getattr(tools, name)(missing)
        self.assertFalse(os.path.exists(missing), "a read tool must not create the ledger it read")


class TestWritingTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = _ledger_with_pins(self.tmp)

    def test_render_map_writes_a_self_contained_file(self):
        out = os.path.join(self.tmp, "map.html")
        tools.render_map(self.ledger, out)
        with open(out, encoding="utf-8") as fh:
            html = fh.read()
        self.assertTrue(html.lstrip().lower().startswith("<!doctype html"))
        self.assertNotIn("<script src=", html, "the map must stay self-contained — no external fetch")

    def test_generate_then_diff_round_trips_to_zero_drift(self):
        # The property both skills rest on, exercised through the MCP tool surface rather than the
        # library: generate every layer from one contract, then diff them back against it.
        contract = os.path.join(FIXTURES, "step0", "contract.json")
        gen = tools.generate_layers(contract, os.path.join(self.tmp, "gen"))
        self.assertTrue(gen["written"], "generate_layers wrote nothing")

        drift = tools.contract_diff(
            contract,
            ddl=gen["written"]["ddl"],
            sqlalchemy=gen["written"]["sqlalchemy"],
            pydantic=gen["written"]["pydantic"],
            typescript=gen["written"]["typescript"],
        )
        # Asserted as a shape, not sniffed. This line used to read
        #     drift.get("findings", drift) if isinstance(drift, dict) else drift
        # and that hedge is why the bug lived: the tool was handing back a bare list, MCP rejected
        # every call, and the test accommodated both shapes instead of pinning one.
        self.assertIsInstance(drift, dict, "structuredContent must be a JSON object")
        self.assertEqual(drift["findings"], [],
                         f"generated layers must round-trip to zero drift, got: {drift['findings']}")

    def test_generate_layers_can_restrict_to_a_subset(self):
        contract = os.path.join(FIXTURES, "step0", "contract.json")
        gen = tools.generate_layers(contract, os.path.join(self.tmp, "sub"), layers=["ddl"])
        self.assertEqual(list(gen["written"]), ["ddl"])


class TestLedgerWrites(unittest.TestCase):
    """The non-electing ledger writes, exposed as MCP tools (the path-robust channel; the CLI is the
    floor). Electing an outcome (decide/accept) stays human-only and has no tool."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "ledger.json")

    def test_add_pin_then_resolve_persists_with_evidence(self):
        pin = tools.ledger_add_pin(self.ledger, kind="defect", title="off-by-one", severity="high",
                                   confidence="extracted",
                                   provenance=[{"source": "systematic-debugging", "detail": "repro"}])
        pid = pin["pin_id"]
        tools.ledger_add_remediation(self.ledger, pid, action="implement", ladder_rung=1)
        item_id = Ledger(self.ledger).pin(pid)["remediation"][0]["id"]
        tools.ledger_set_remediation_status(self.ledger, pid, item_id, "done")
        out = tools.ledger_resolve(self.ledger, pid, evidence="observed: repro no longer reproduces",
                                   rung="observed")
        self.assertEqual(out["state"], "resolved")
        self.assertEqual(Ledger(self.ledger).pin(pid)["evidence"], "observed: repro no longer reproduces")

    def test_writes_bootstrap_a_missing_ledger(self):
        # Unlike reads (which refuse a missing path), a write creates the ledger — the first pin lands.
        self.assertFalse(os.path.exists(self.ledger))
        tools.ledger_add_pin(self.ledger, kind="open_decision", title="which db?", severity="medium",
                             confidence="inferred", provenance=[{"source": "frame", "detail": "x"}])
        self.assertTrue(os.path.exists(self.ledger))

    def test_there_is_no_electing_write_tool(self):
        # The 'no decide tool' doctrine, enforced at the tool surface.
        self.assertFalse(hasattr(tools, "ledger_decide"))
        self.assertFalse(hasattr(tools, "ledger_accept"))

    #: The fork these clustered pins pose. A policy may only write an outcome the pin's own question
    #: offers (v0.12), so a cluster with no question is a cluster no policy can cascade over.
    FORK = {"prompt": "Which layer is truth?",
            "options": [{"id": "db", "label": "the DB"}, {"id": "api", "label": "the API"}]}

    def _cluster(self, n=3):
        for i, sev in enumerate(("low", "medium", "high")[:n]):
            tools.ledger_add_pin(self.ledger, kind="contract_mismatch", title=f"drift {i}",
                                 severity=sev, confidence="extracted", cluster_id="cl_shape",
                                 question=self.FORK,
                                 provenance=[{"source": "recon", "detail": "shape diff"}])

    def test_a_catalog_offer_is_taken_verbatim_or_not_at_all(self):
        """The offer is the mandate the user was shown. Restating it in the caller's own words is
        how a recorded policy comes to differ from the one anybody agreed to."""
        self._cluster()
        offers = tools.interview_seed_policies(self.ledger)["offers"]
        offer = next(o for o in offers if o["cluster_id"] == "cl_persistence")
        self.assertIn("would_decide", offer, "an offer without its blast radius is half the question")
        with self.assertRaises(ValueError):
            tools.record_policy(self.ledger, offer_id=offer["cluster_id"], rule="my own words",
                                human_answer="sure")
        out = tools.record_policy(self.ledger, offer_id=offer["cluster_id"],
                                  human_answer="yes, take the default")
        policy = Ledger(self.ledger).data["policies"][-1]
        self.assertEqual(policy["rule"], offer["rule"])
        self.assertEqual(policy["applies_to"], offer["applies_to"])
        self.assertEqual(policy["default_outcome"], offer["default_outcome"])
        self.assertEqual(out["evidence"], "transcribed")

    def test_a_stated_default_that_no_option_carries_is_not_an_offer(self):
        """v0.12. `nfrs` states a default naming four of its own options at once, so accepting it
        would write a sentence as the outcome of a pin offering `validation | errors | ... `. It is
        returned as stated-but-asked, and taking it by offer_id is refused with that reason — not
        with silence that reads as "no default here"."""
        self._cluster()
        seeded = tools.interview_seed_policies(self.ledger)
        asked = {o["cluster_id"] for o in seeded["no_default_outcome"]}
        self.assertIn("cl_nfrs", asked)
        self.assertNotIn("cl_nfrs", {o["cluster_id"] for o in seeded["offers"]})
        with self.assertRaises(ValueError) as caught:
            tools.record_policy(self.ledger, offer_id="cl_nfrs", human_answer="sure")
        self.assertIn("no single one of its options carries it", str(caught.exception))

    def test_a_policy_cannot_write_an_outcome_the_pin_never_offered(self):
        """The blocker, at the door an agent actually reaches. `record_decision` refuses an
        option_id the pin does not offer; `record_policy` wrote the caller's own sentence onto every
        pin in the cluster. Reproduced verbatim from the review: an outcome no pin's question
        offers, on pins that offer a closed set."""
        for i in range(2):
            tools.ledger_add_pin(self.ledger, kind="open_decision", title=f"datastore {i}",
                                 severity="low", confidence="inferred", cluster_id="cl_data",
                                 provenance=[{"source": "recon", "detail": "d"}],
                                 question={"prompt": "Which datastore?",
                                           "options": [{"id": "postgres", "label": "Postgres"},
                                                       {"id": "mysql", "label": "MySQL"}]})
        out = tools.record_policy(
            self.ledger, rule="the agent's own sentence, never uttered by the user",
            applies_to={"cluster_id": "cl_data"},
            default_outcome="mongodb — an outcome no pin's question offers",
            human_answer="whatever, you decide")
        self.assertEqual(out["cascaded"], [], "nothing may be decided on an unoffered outcome")
        self.assertEqual(out["not_offered"], ["pin_0001", "pin_0002"])
        led = Ledger(self.ledger)
        self.assertEqual(led.data["decision_log"], [], "no DecisionEvent may exist for it")
        for pin in led.data["pins"]:
            self.assertEqual(pin["state"], "needs_input")
            self.assertEqual(pin["resolution_mode"], "asked")

    def test_a_policy_reports_its_own_cascade_and_not_an_older_ones(self):
        """The second finding. `record_policy` called `apply_policies()`, which re-ran every policy
        in the ledger: recording pol_0002 returned pin_0002 — decided by pol_0001, over a pin added
        after pol_0001 was elected — inside its own `cascaded` list."""
        args = dict(question={"prompt": "Which layer is truth?",
                              "options": [{"id": "db", "label": "the DB"},
                                          {"id": "api", "label": "the API"}]},
                    kind="contract_mismatch", severity="low", confidence="extracted",
                    provenance=[{"source": "recon", "detail": "d"}])
        tools.ledger_add_pin(self.ledger, title="one", cluster_id="cl_one", **args)
        first = tools.record_policy(self.ledger, rule="A", applies_to={"cluster_id": "cl_one"},
                                    default_outcome="db", human_answer="A")
        self.assertEqual(first["cascaded"], ["pin_0001"])

        tools.ledger_add_pin(self.ledger, title="two", cluster_id="cl_one", **args)   # found later
        tools.ledger_add_pin(self.ledger, title="three", cluster_id="cl_two", **args)
        second = tools.record_policy(self.ledger, rule="B", applies_to={"cluster_id": "cl_two"},
                                     default_outcome="api", human_answer="B")

        self.assertEqual(second["cascaded"], ["pin_0003"],
                         "a policy reports what IT decided; pin_0002 belongs to no election")
        led = Ledger(self.ledger)
        self.assertEqual(led.pin("pin_0002")["state"], "needs_input",
                         "accepting one policy must not cascade an older one over pins added since "
                         "— nobody was shown them when they accepted it")
        self.assertEqual([(e["pin_id"], e["policy_id"]) for e in led.data["decision_log"]],
                         [("pin_0001", first["policy_id"]), ("pin_0003", second["policy_id"])])

    def test_the_preview_writes_nothing_and_matches_what_the_cascade_does(self):
        self._cluster()
        args = dict(rule="the DB is truth", applies_to={"cluster_id": "cl_shape"},
                    default_outcome="db")
        preview = tools.policy_prompt(self.ledger, **args)
        self.assertEqual(Ledger(self.ledger).data["policies"], [],
                         "previewing a policy must not create one")
        out = tools.record_policy(self.ledger, human_answer="the DB is truth here", **args)
        self.assertEqual(out["cascaded"], preview["would_decide"])
        self.assertEqual(out["held_back"], preview["held_back"])
        led = Ledger(self.ledger)
        for pin_id in out["cascaded"]:
            event_id = led.pin(pin_id)["decision"]["event_id"]
            event = next(e for e in led.data["decision_log"] if e["id"] == event_id)
            self.assertEqual(event["evidence"], "cascaded",
                             "a cascade must not be recorded as an agent's relay")
            self.assertEqual(event["policy_id"], out["policy_id"])


class TestUnderstandFamily(unittest.TestCase):
    """The understand-mode graph tools, exposed over MCP now that the CLI is being removed. The
    graph is the foundational disk artifact; the rest read it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "app.py"), "w", encoding="utf-8") as fh:
            fh.write("import os\ndef handler():\n    return os.getpid()\n")
        self.graph = os.path.join(self.tmp, "graph.json")

    def test_build_graph_writes_and_query_reads_it(self):
        out = tools.build_graph(self.tmp, self.graph)
        self.assertEqual(out["written"], self.graph)
        self.assertTrue(os.path.exists(self.graph))
        self.assertGreaterEqual(out["nodes"], 1)
        self.assertIn("results", tools.graph_query(self.graph, "handler"))
        self.assertIn("entry_points", tools.domain_view(self.tmp))
        self.assertIn("steps", tools.guided_tour(self.graph))

    def test_impact_refuses_without_a_change_set(self):
        tools.build_graph(self.tmp, self.graph)
        with self.assertRaises(ValueError):
            tools.impact_overlay(self.graph)   # neither `changed` nor `git_base` — refuse, don't guess


class TestBlastRadiusStalenessGate(unittest.TestCase):
    """The gate is the whole reason a graph answer is trustworthy: impact computed against code
    that has since moved is worse than no answer. So these assert it REFUSES, not that it copes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _graph(self, built_at, nodes=(), links=()):
        p = os.path.join(self.tmp, "graph.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"graph": {"built_at_commit": built_at},
                       "nodes": list(nodes), "links": list(links)}, fh)
        return p

    def test_refuses_a_stale_graph(self):
        g = self._graph("0000000000000000000000000000000000000000")
        with self.assertRaises(Exception) as cm:
            tools.blast_radius(g, "some:node", head="feed1234beefcafe")
        self.assertIn("stale", str(cm.exception).lower())

    def test_refuses_when_head_cannot_be_resolved(self):
        # No head, and none resolvable -> refuse. Silently skipping the gate would be the one
        # failure mode worse than being stale.
        g = self._graph("feed1234beefcafe")
        with self.assertRaises(Exception) as cm:
            tools.blast_radius(g, "some:node", head="")
        self.assertRegex(str(cm.exception).lower(), r"head|stale")

    def test_answers_on_a_current_graph(self):
        head = "feed1234beefcafe"
        g = self._graph(head,
                        nodes=[{"id": "a", "name": "A", "source_file": "a.py", "line": 1},
                               {"id": "b", "name": "B", "source_file": "b.py", "line": 1}],
                        links=[{"source": "b", "target": "a", "type": "calls",
                                "confidence": "extracted"}])
        out = tools.blast_radius(g, "a", head=head)
        self.assertIn("b", out["impacted"], "b calls a, so changing a must impact b")


class TestLiveMap(unittest.TestCase):
    """live=True registers the map so every later ledger write re-projects it — the map projecting
    the *live* ledger, driven by the MCP layer itself (no per-host hook, no running server)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "ledger.json")
        tools.ledger_add_pin(self.ledger, kind="defect", title="first pin", severity="low",
                             confidence="inferred", provenance=[{"source": "x", "detail": "y"}])
        self.out = os.path.join(self.tmp, "map.html")

    def _html(self):
        with open(self.out, encoding="utf-8") as fh:
            return fh.read()

    def test_live_render_registers_a_marker_and_badge(self):
        tools.render_map(self.ledger, self.out, live=True)
        self.assertTrue(os.path.exists(self.ledger + ".livemap"))
        self.assertIn("livebadge", self._html())

    def test_a_ledger_write_reprojects_the_live_map(self):
        tools.render_map(self.ledger, self.out, live=True)
        self.assertNotIn("second pin", self._html())
        # no one calls render_map again — the write itself re-projects the registered live map
        tools.ledger_add_pin(self.ledger, kind="defect", title="second pin", severity="low",
                             confidence="inferred", provenance=[{"source": "x", "detail": "y"}])
        self.assertIn("second pin", self._html())

    def test_frozen_render_stops_the_live_refresh(self):
        tools.render_map(self.ledger, self.out, live=True)
        self.assertTrue(os.path.exists(self.ledger + ".livemap"))
        tools.render_map(self.ledger, self.out, live=False)   # freeze the shareable artifact
        self.assertFalse(os.path.exists(self.ledger + ".livemap"))
        tools.ledger_add_pin(self.ledger, kind="defect", title="third pin", severity="low",
                             confidence="inferred", provenance=[{"source": "x", "detail": "y"}])
        self.assertNotIn("third pin", self._html())   # no longer tracked
        self.assertNotIn("livebadge", self._html())


class TestInstructionCarrierRoundTrip(unittest.TestCase):
    """The generated-file list must survive a regeneration that does not re-state it.

    It is transient input, but the tool is re-run for unrelated reasons all the time — a pin gets
    decided, a policy is added. If the list vanished then, `AGENTS.md` would lose its never-hand-edit
    section while `.claude/rules/` kept asserting it, and `instructions_diff` would answer `in_sync`
    because it was asked the same incomplete question. Two carriers of one fact, disagreeing, with a
    green drift-check on top: exactly what this module exists to make impossible.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = _ledger_with_pins(self.tmp)
        self.rule = os.path.join(self.tmp, ".claude", "rules", "keel-generated-files.md")

    def _agents(self):
        with open(os.path.join(self.tmp, "AGENTS.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_a_rerun_without_the_argument_preserves_both_carriers(self):
        tools.generate_instructions(self.ledger, self.tmp, generated=["src/types.ts"],
                                    generated_from="contract.json", generated_by="generate_layers")
        self.assertIn("src/types.ts", self._agents())
        self.assertTrue(os.path.isfile(self.rule))

        out = tools.generate_instructions(self.ledger, self.tmp)   # unrelated regeneration
        self.assertEqual(out["generated"], ["src/types.ts"])
        self.assertIn("src/types.ts", self._agents())
        self.assertTrue(os.path.isfile(self.rule), "the Claude rule must not outlive or precede the region")
        self.assertTrue(tools.instructions_diff(self.ledger, self.tmp)["in_sync"])

    def test_clearing_is_explicit_and_takes_the_claude_rule_with_it(self):
        tools.generate_instructions(self.ledger, self.tmp, generated=["src/types.ts"])
        out = tools.generate_instructions(self.ledger, self.tmp, generated=[])
        self.assertEqual(out["generated"], [])
        self.assertNotIn("src/types.ts", self._agents())
        self.assertFalse(os.path.isfile(self.rule),
                         "an emptied list must remove the rule, or the two carriers disagree")

    def test_diff_recovers_the_same_list_the_generator_would(self):
        # The generate/diff pair must answer the same question the same way, or the drift-check is
        # checking something the generator never wrote.
        tools.generate_instructions(self.ledger, self.tmp, generated=["a.ts", "b.sql"])
        self.assertEqual(tools.instructions_diff(self.ledger, self.tmp)["generated"],
                         ["a.ts", "b.sql"])

    def test_an_opted_out_bridge_is_not_reported_as_missing(self):
        tools.generate_instructions(self.ledger, self.tmp, bridge=False)
        self.assertFalse(os.path.isfile(os.path.join(self.tmp, "CLAUDE.md")))
        self.assertEqual(tools.instructions_diff(self.ledger, self.tmp)["claude_bridge"], "missing")
        out = tools.instructions_diff(self.ledger, self.tmp, bridge=False)
        self.assertEqual(out["claude_bridge"], "not_requested")
        self.assertTrue(out["in_sync"], "opting out of the bridge says nothing about the region")


class TestSettlingAPinThroughTheAgentsOwnDoors(unittest.TestCase):
    """v0.16, at the boundary an AGENT reaches — which is the boundary the reproductions used.

    Each of these was run over real `uv run --script` stdio with no human in the loop before it was
    a test. The pure-layer versions live in `test_ledger.py`; these assert that the tool an agent
    actually calls refuses the same thing, because the last four rounds all ended with a rule that
    held in the library and not at the door (or the reverse).
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "ledger.json")

    def _fork(self, severity="blocker"):
        out = tools.ledger_add_pin(
            self.ledger, kind="open_decision", title="session or JWT", severity=severity,
            confidence="inferred", provenance=[{"source": "catalog", "detail": "identity"}],
            question={"prompt": "Session or JWT?",
                      "options": [{"id": "session", "label": "server sessions"},
                                  {"id": "jwt", "label": "stateless JWT"}]})
        return out["pin_id"]

    def test_the_four_call_chain_that_closed_an_unverifiable_blocker(self):
        """Reproduced verbatim: add_pin(defect, blocker) -> add_remediation ->
        set_remediation_status(done) -> mark_correctness_unknown -> resolve. The fifth call
        returned `resolved`; a pin that had just declared its own correctness unestablishable
        closed green, with no human anywhere in the chain."""
        pid = tools.ledger_add_pin(
            self.ledger, kind="defect", title="double charge under retry", severity="blocker",
            confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
            as_is={"description": "double charge"})["pin_id"]
        item = tools.ledger_add_remediation(self.ledger, pid, action="align", ladder_rung=2)
        tools.ledger_set_remediation_status(self.ledger, pid, item["item_id"], "done")
        out = tools.ledger_mark_correctness_unknown(
            self.ledger, pid, blocked_by="no runnable payments environment",
            attempted=["tests", "typecheck", "smoke_probe"])
        self.assertEqual(out["state"], "correctness_unknown")
        with self.assertRaises(ValueError):
            tools.ledger_resolve(self.ledger, pid, evidence="looks right now")
        self.assertEqual(tools.ledger_summary(self.ledger)["by_state"],
                         {"correctness_unknown": 1})

    def test_an_agent_alone_cannot_defer_a_blocker(self):
        """`ledger_defer` took (ledger, pin_id) and settled the pin. `interview_next` went from
        asked_count 1 to 0, `open_questions` from 1 to 0, and `decision_log` stayed empty."""
        pid = self._fork()
        with self.assertRaises(ValueError) as ctx:
            tools.ledger_defer(self.ledger, pid, rationale="out of the v1 slice",
                               flip_criteria="a non-cookie client appears")
        self.assertIn("human_answer", str(ctx.exception))
        self.assertEqual(tools.interview_next(self.ledger)["asked_count"], 1,
                         "the question must still be asked")
        self.assertEqual(tools.ledger_summary(self.ledger)["events"], 0)

    def test_a_quoted_deferral_settles_the_pin_and_says_so_in_the_log(self):
        pid = self._fork()
        out = tools.ledger_defer(self.ledger, pid, rationale="auth is out of the v1 slice",
                                 flip_criteria="a second client appears that cannot hold a cookie",
                                 human_answer="not now — v1 is one web client")
        self.assertEqual((out["state"], out["outcome"]), ("deferred", "defer"))
        summary = tools.ledger_summary(self.ledger)
        self.assertEqual(summary["open_questions"], 0)
        self.assertEqual(summary["settlements_by_door"], {"defer": 1},
                         "a settlement no surface counts is the black hole this schema keeps "
                         "rediscovering")
        led = Ledger(self.ledger)
        self.assertEqual(led.data["decision_log"][-1]["human_answer"],
                         "not now — v1 is one web client")

    def test_record_decision_and_the_unasked_predicate_answer_the_same_way(self):
        """Two doors, two answers, one question — the LOW finding. `record_decision` re-decided a
        resolved pin back to `decided` while `unasked_verdict` called the same pin
        `already_settled`."""
        pid = tools.ledger_add_pin(
            self.ledger, kind="defect", title="d", severity="medium", confidence="extracted",
            provenance=[{"source": "recon", "detail": "x"}], as_is={"description": "d"},
            question={"prompt": "?", "options": [{"id": "fix", "label": "fix it"}]})["pin_id"]
        item = tools.ledger_add_remediation(self.ledger, pid, action="align", ladder_rung=1)
        tools.ledger_set_remediation_status(self.ledger, pid, item["item_id"], "done")
        tools.ledger_resolve(self.ledger, pid, evidence="observed: no longer reproduces",
                            rung="observed")
        led = Ledger(self.ledger)
        self.assertEqual(led.unasked_verdict(led.pin(pid), "fix"), "already_settled")
        with self.assertRaises(Exception):
            tools.record_decision(self.ledger, pid, "fix", rationale="r", flip_criteria="f",
                                  human_answer="fix it")
        self.assertEqual(Ledger(self.ledger).pin(pid)["state"], "resolved")

    def test_a_policy_scope_naming_no_pin_field_is_refused_at_the_door(self):
        """`applies_to={"nope": null}` matched EVERY pin in the ledger — reproduced end to end
        through `ledger_record_policy`, whose radius is what a human elects the policy from."""
        self._fork(severity="medium")
        with self.assertRaises(Exception) as ctx:
            tools.record_policy(self.ledger, rule="everything is a session",
                                default_outcome="session", applies_to={"nope": None},
                                human_answer="sessions everywhere")
        self.assertIn("not a Pin field", str(ctx.exception))
        self.assertEqual(Ledger(self.ledger).data["policies"], [])

    def test_a_cross_derivation_disagreement_leaves_the_offered_options_alone(self):
        pid = self._fork(severity="medium")
        tools.record_decision(self.ledger, pid, "jwt", rationale="r", flip_criteria="f",
                              human_answer="JWT, we have three clients")
        out = tools.ledger_cross_derive(
            self.ledger, pid, claim="JWT revocation is solvable here", agreement="disagree",
            derivations=[{"provider": "anthropic", "model": "m", "result": "yes"},
                         {"provider": "openai", "model": "n", "result": "no"}])
        self.assertTrue(out["reopened"])
        self.assertTrue(out["event_id"].startswith("xdr_"))
        pin = Ledger(self.ledger).pin(pid)
        self.assertEqual([o["id"] for o in pin["question"]["options"]], ["session", "jwt"],
                         "the menu the human answers from belongs to the ledger, not the caller")
        self.assertEqual(tools.decision_prompt(self.ledger, pid)["options"][0]["id"], "session")

    def test_the_returned_reopened_is_the_events_own_answer(self):
        """Two carriers for one fact, disagreeing — in the return shape of the tool whose subject is
        two derivations disagreeing. `reopened` was re-derived as `substate == "contested"`, and
        `substate` is written by the reopen and never cleared, so a SECOND, AGREEING derivation came
        back `reopened: true` while the `xdr_` event it had just written said false."""
        pid = self._fork(severity="medium")
        tools.record_decision(self.ledger, pid, "jwt", rationale="r", flip_criteria="f",
                              human_answer="JWT, we have three clients")
        disagreeing = [{"provider": "anthropic", "model": "m", "result": "yes"},
                       {"provider": "openai", "model": "n", "result": "no"}]
        agreeing = [{"provider": "anthropic", "model": "m", "result": "yes"},
                    {"provider": "openai", "model": "n", "result": "yes"}]
        first = tools.ledger_cross_derive(self.ledger, pid, claim="revocation is solvable",
                                          agreement="disagree", derivations=disagreeing)
        self.assertTrue(first["reopened"])
        second = tools.ledger_cross_derive(self.ledger, pid, claim="revocation is solvable",
                                           agreement="agree", derivations=agreeing)
        events = [e for e in Ledger(self.ledger).data["decision_log"]
                  if e["id"].startswith("xdr_")]
        self.assertEqual(second["event_id"], events[-1]["id"])
        self.assertEqual(second["reopened"], events[-1]["reopened"])
        self.assertFalse(second["reopened"], "an agreement reopens nothing")

    def test_the_defer_door_does_not_let_its_caller_state_its_own_rung(self):
        """`ledger_defer(..., evidence="elicited")` settled a `blocker` fork on the rung whose whole
        claim is that the agent never carried the value — reproduced against a client declaring no
        elicitation capability, so nobody was asked by anybody. `record_decision` has never allowed
        it: the rung is decided by WHICH PATH RAN, never by a parameter."""
        import inspect
        self.assertNotIn("evidence", inspect.signature(tools.ledger_defer).parameters,
                         "provenance the caller states is provenance the caller invents")
        pid = self._fork()
        out = tools.ledger_defer(self.ledger, pid, rationale="not now",
                                 flip_criteria="when a second client appears",
                                 human_answer="not now — v1 is one web client")
        self.assertEqual(out["evidence"], "transcribed")
        self.assertEqual(Ledger(self.ledger).data["decision_log"][-1]["evidence"], "transcribed")


if __name__ == "__main__":
    unittest.main()
