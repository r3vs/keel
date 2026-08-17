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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # `shape_corpus`, the derived corpus
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

    def test_contract_diff_errors_over_a_layer_that_read_nothing(self):
        """The tool's own description calls an empty `findings` the evidence of zero drift, so the
        one thing it may never do is answer `{"findings": []}` over a layer the extractor could not
        read. The refusal used to cover the carrier alone, and this is the door the playbooks reach
        for first — `reconcile_layers` refused the same file all along."""
        import shapes
        unreadable = os.path.join(self.tmp, "models.py")
        with open(unreadable, "w", encoding="utf-8") as fh:
            fh.write("# a models.py in an idiom the extractor does not read\nX = 1\n")
        with self.assertRaises(shapes.EmptyExtraction) as caught:
            tools.contract_diff(os.path.join(FIXTURES, "step0", "contract.json"),
                                sqlalchemy=unreadable)
        self.assertIn("sqlalchemy", str(caught.exception))
        self.assertIn(unreadable, str(caught.exception))

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
    FORK = {"prompt": "Which layer is truth?", "allow_freeform": True,
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
                                                       {"id": "mysql", "label": "MySQL"}],
                                 "allow_freeform": True})
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
            # v0.18: still open, still reported, and NOT stamped. The stamp has no clearing door,
            # so recording "that rule did not fit" on the pin refused the next rule that does.
            self.assertNotIn("resolution_mode", pin)

    def test_a_policy_reports_its_own_cascade_and_not_an_older_ones(self):
        """The second finding. `record_policy` called `apply_policies()`, which re-ran every policy
        in the ledger: recording pol_0002 returned pin_0002 — decided by pol_0001, over a pin added
        after pol_0001 was elected — inside its own `cascaded` list."""
        args = dict(question={"prompt": "Which layer is truth?",
                              "options": [{"id": "db", "label": "the DB"},
                                          {"id": "api", "label": "the API"}], "allow_freeform": True},
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
                                  {"id": "jwt", "label": "stateless JWT"}], "allow_freeform": True})
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
            question={"prompt": "?", "allow_freeform": True,
                      "options": [{"id": "fix", "label": "fix it"}]})["pin_id"]
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

    # -- v0.20: the two arcs report one radius, and they report their own ------------------------

    def _closed(self, title, depends_on=()):
        """A pin walked the whole way: add_pin -> record_decision -> add_remediation -> done ->
        resolve. The chain the reproduction used, through the doors an agent actually calls."""
        pid = tools.ledger_add_pin(
            self.ledger, kind="defect", title=title, severity="medium", confidence="extracted",
            provenance=[{"source": "recon", "detail": "x"}], depends_on=list(depends_on),
            question={"prompt": "Fix it how?",
                      "options": [{"id": "align", "label": "align the layers"},
                                  {"id": "drop", "label": "drop the path"}],
                      "allow_freeform": True})["pin_id"]
        tools.record_decision(self.ledger, pid, "align", rationale="r", flip_criteria="f",
                              human_answer="align them")
        item = tools.ledger_add_remediation(self.ledger, pid, action="align", ladder_rung=2)
        tools.ledger_set_remediation_status(self.ledger, pid, item["item_id"], "done")
        tools.ledger_resolve(self.ledger, pid, evidence="replayed on staging", rung="observed")
        return pid

    def test_a_reopen_reports_the_radius_it_moved_and_not_an_older_ones(self):
        """Reproduced verbatim over stdio: `also_reopened` was every pin with
        `substate == "reopened"` and `state == "needs_input"`, and nothing anywhere clears that
        substate — so a later reopen of an UNRELATED closed pin reported the earlier cascade's pins
        as its own radius. The library one layer down forbids exactly this read (v0.16 corrected
        `cross_derive` for it); the tool layer re-introduced it."""
        root = self._closed("root")
        dep = self._closed("dependent", depends_on=[root])
        dep2 = self._closed("dependent of the dependent", depends_on=[dep])

        first = tools.ledger_reopen(self.ledger, root, reason="3 double charges in 24h on prod")
        self.assertEqual((first["reopened"], first["also_reopened"]), (True, [dep, dep2]))

        alone = self._closed("unrelated, depends on nothing")
        second = tools.ledger_reopen(self.ledger, alone, reason="a second, unrelated incident",
                                     fired="incident", source="feedback:logs")
        self.assertEqual(second["also_reopened"], [],
                         "this call moved one pin; the three still carrying the mark are the "
                         "previous call's radius, and nothing clears the mark")

    def test_both_arcs_report_the_same_radius_under_the_same_key(self):
        """`ledger_challenge` runs the same cascade through the same writer and reported nothing —
        a `resolved` pin was taken back into the open set by a challenge on the pin it depends on
        and appeared in no key of the response. Two arcs, one predicate, one writer, added in one
        commit, and their radius reporting was one over."""
        root = self._closed("challenged root")
        dep = self._closed("rests on the challenged root", depends_on=[root])
        out = tools.ledger_challenge(
            self.ledger, root, target="decision", challenge_class="unstated_assumption",
            argument="the retry path was never the one this was elected for",
            severity="high", upheld=True)
        self.assertEqual((out["upheld"], out["reopened"], out["also_reopened"]), (True, True, [dep]))
        self.assertEqual(Ledger(self.ledger).pin(dep)["state"], "needs_input")
        self.assertEqual(
            set(tools.ledger_reopen.__doc__.split()) & {"also_reopened"},
            set(tools.ledger_challenge.__doc__.split()) & {"also_reopened"},
            "one cascade, one key, described at both doors")

    def test_every_pin_the_cascade_moved_is_named_in_the_log_the_agent_can_read(self):
        """The trail half, at the boundary: three pins were un-finished by one call and the log
        named the root. `also_reopened` is read off these records rather than off the pins."""
        root = self._closed("root")
        dep = self._closed("dependent", depends_on=[root])
        event = tools.ledger_reopen(self.ledger, root, reason="it came back")["event_id"]
        cascades = [e for e in Ledger(self.ledger).data["decision_log"]
                    if e["id"].startswith("cas_")]
        self.assertEqual([(e["pin_id"], e["via"], e["arc"]) for e in cascades],
                         [(dep, event, "reopen")])

    def test_the_brainstorm_cannot_write_onto_work_that_is_finished(self):
        """`ledger_add_proposals` succeeded on an `accepted` pin and on a `deferred` one, writing
        `brainstorm.proposals` onto work whose question had stopped being asked — while
        `ledger_set_question`, added in the same commit for the other half of the same funnel,
        refused both."""
        for settle in ("accept", "defer"):
            pid = self._fork(severity="low")
            Ledger(self.ledger)  # the pin exists; each branch settles it its own way
            if settle == "accept":
                concern = tools.ledger_add_pin(
                    self.ledger, kind="design_concern", title="three near-identical blocks",
                    severity="low", confidence="inferred",
                    provenance=[{"source": "reviewer", "detail": "judgment"}],
                    question={"prompt": "Consolidate?",
                              "options": [{"id": "extract", "label": "extract a helper"}],
                              "allow_freeform": True})["pin_id"]
                tools.record_decision(self.ledger, concern, "", rationale="r", flip_criteria="f",
                                      human_answer="leave it", accept_as_is=True)
                pid = concern
            else:
                tools.ledger_defer(self.ledger, pid, rationale="out of the v1 slice",
                                   flip_criteria="a second client appears",
                                   human_answer="not now — v1 is one web client")
            with self.assertRaises(ValueError, msg=settle) as ctx:
                tools.ledger_add_proposals(self.ledger, pid,
                                           [{"summary": "written onto finished work"}])
            self.assertIn("reopen", str(ctx.exception))
            self.assertIsNone(Ledger(self.ledger).pin(pid)["brainstorm"])

    def test_the_older_busier_door_composes_a_fork_under_the_same_rule(self):
        """`ledger_add_pin(question={...})` with no `allow_freeform` was accepted while
        `ledger_set_question` refused the byte-identical dict."""
        closed = {"prompt": "closed menu the agent wrote", "options": [{"id": "a", "label": "A"}]}
        with self.assertRaises(ValueError) as at_add:
            tools.ledger_add_pin(self.ledger, kind="ambiguity", title="t", severity="low",
                                 confidence="inferred",
                                 provenance=[{"source": "recon", "detail": "x"}],
                                 question=dict(closed))
        bare = tools.ledger_add_pin(self.ledger, kind="ambiguity", title="t2", severity="low",
                                    confidence="inferred",
                                    provenance=[{"source": "recon", "detail": "x"}])["pin_id"]
        with self.assertRaises(ValueError) as at_set:
            tools.ledger_set_question(self.ledger, bare, dict(closed))
        self.assertEqual(str(at_add.exception), str(at_set.exception))

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


class TestNoReadOnlyLedgerToolDiesOnAPinShape(unittest.TestCase):
    """v0.22 — *reading a ledger is never the operation that fails on it*, quantified over the read
    tools instead of over the two somebody remembered.

    v0.21 stated that principle with no qualifier and hardened `summary` and `interview_view` for
    it. `policy_preview` — *"Read-only"* in its own first line, served as the read-only MCP tool
    `policy_preview`, and the thing a human is shown before electing a rule over a whole cluster —
    reached `pin["id"]`, `pin["state"]` and `pin["severity"]` raw. Reproduced over real stdio: on a
    two-pin ledger whose second pin carries no `severity`, `ledger_summary` and `interview_next`
    both answered and `policy_preview` returned `isError: true` with the body `'severity'`.

    So the roster is DERIVED from the server's own `readOnlyHint`, the way
    `scripts/check_tool_carriers.py` derives the write roster from the same decoration — a hand-kept
    list here would have contained exactly the two readers that were already fixed.

    **What it asserts, precisely.** A read tool may REFUSE (a policy with no rule is not a policy),
    and refusing is a `ValueError`/`LedgerError` about the call. What it may not do is die on the
    file's SHAPE, and that has one signature: an indexing error escaping to the caller. The tool
    layer turns whatever escapes into `isError` over the wire, so the distinction the wire cannot
    make is the one that has to be made here.

    **The first draft of this gate quantified over more than it exercised, and was caught by
    planting.** Called with its required argument alone, `policy_preview` refuses on *its own
    arguments* — a policy needs a rule, a scope and an outcome — and never opens a pin. So the
    roster listed the tool the whole finding was reproduced on, and reverting the fix left the gate
    green. That is the repo's third recurring shape (`docs/open-gaps.md` §18) turned on a gate
    written to close its first. Hence `MINIMAL_CALL`: the roster is still derived, the *call* is
    declared, the two are held together by set equality, and
    `test_every_minimal_call_reaches_the_file` proves each call runs on a well-formed ledger — which
    is what makes the broken-ledger run an exercise of the body rather than of a refusal.

    **v0.28 — the membership rule had a hole shaped like two tools.** The roster was
    `required == ["ledger"]`, which is not *a read-only tool that reads a ledger*: it is that minus
    every read-only tool that also takes a `pin_id`. `scope_check` and `readiness_assess` are exactly
    that class, they were in none of the three derived rosters on this branch — the two write-door
    rosters are *takes a `pin_id` and commits*, so a READ that takes a pin falls between all of them
    — and both died on the pin's own declared shapes: `'str' object has no attribute 'get'` from
    `declared_vs_actual`'s `(pin.get("readiness") or {}).get("zone")`, `'int' object is not
    iterable` from `zone_of`'s walk over `anchors`. The rule is now *the tool's first required
    argument is the ledger*, and the extra arguments are declared in `MINIMAL_CALL` like every other
    payload. `docs/open-gaps.md` §26's fourth shape, one round later and one roster over: **say the
    predicate in words, then name what does the dangerous thing and does not satisfy it.**
    """

    #: Dying on a shape looks like exactly this. A deliberate refusal never does.
    SHAPE_DEATHS = (KeyError, AttributeError, IndexError, TypeError)

    #: Substituted into `MINIMAL_CALL` at call time, because neither can be a literal in a table: a
    #: pin id has to name a pin in the fixture actually under test, and a graph has to be a file.
    PIN = "<a pin this ledger carries>"
    GRAPH = "<a graph built at HEAD>"
    HEAD = "feed1234beefcafe"

    #: The minimal LEGITIMATE call per tool: the arguments without which it refuses before reading
    #: anything. Held to the derived roster by set equality, so a read-only ledger tool added to the
    #: server has to be given its call here before this gate will pass — the membership question
    #: stays with the server, and only the payload is declared.
    MINIMAL_CALL = {
        "ledger_summary": {},
        "ledger_frontier": {},
        "ledger_fog": {},
        # Takes nothing but the ledger, and is the one read-only tool whose SUBJECT is the file's own
        # shape — so the broken-ledger corpus below is not an incidental exercise of it, it is the
        # workload. A store-health check that dies on an unhealthy store answers the wrong question.
        "memory_audit": {},
        "interview_next": {},
        "interview_seed_policies": {},
        "policy_preview": {"rule": "the DB wins on nullability",
                           "applies_to": {"kind": "contract_mismatch"},
                           "default_outcome": "opt_a"},
        "learning_report": {},
        "agent_ready": {},
        "build_waves": {},
        "challenge_oracle": {},
        "instructions_diff": {},
        # The tracker projection reads the ledger and renders every pin BEFORE it touches a
        # transport, which is what makes it a member of this roster rather than a tool that would
        # answer `no_token` on all hundred malformed pins and prove nothing. `setUp` below removes
        # the token from the environment so the run can never leave the machine.
        "tracker_diff": {"repo": "keel-test/not-a-real-repo"},
        "scope_check": {"pin_id": PIN, "changed": ["a.py"]},
        # `head` is declared even though it has a default: without it the tool shells out to git for
        # HEAD, so what it exercises would depend on the cwd the suite happens to run in.
        "readiness_assess": {"pin_id": PIN, "graph_path": GRAPH, "head": HEAD},
    }

    def setUp(self):
        """No test in this suite may leave the machine, and that is enforced rather than assumed.

        `tracker_diff` reads a token out of the environment. A developer with `GH_TOKEN` exported —
        anyone who has run `gh auth login` — would otherwise have this gate issue ~100 real HTTP
        calls to a repository that does not exist, and a green run here would mean something
        different from a green run in CI. The suite's own recorded lesson, one file over: a green
        run is a claim about the environment that produced it.
        """
        self._token_env = {k: os.environ.pop(k) for k in ("GITHUB_TOKEN", "GH_TOKEN")
                           if k in os.environ}
        self.addCleanup(os.environ.update, self._token_env)

    def _call(self, name, path, tmp):
        """The declared payload with the two sentinels resolved against THIS fixture."""
        import ledger as mod
        out = {}
        for key, value in self.MINIMAL_CALL[name].items():
            if value == self.PIN:
                # The LAST pin, and that is load-bearing: every corpus loop below APPENDS its
                # malformed record, so naming the first pin would hand these two tools a healthy
                # one and the gate would pass with the fix reverted — verified by planting exactly
                # that. Where the fault is the id itself the lookup refuses, which is a refusal
                # about the call and not an exercise; the other ~95 shapes reach the body.
                with open(path, encoding="utf-8") as fh:
                    pins = mod.read_collection(json.load(fh), "pins")
                value = mod.pin_read(pins[-1])["id"] if pins else "pin_0001"
            elif value == self.GRAPH:
                value = os.path.join(tmp, "graph.json")
                if not os.path.exists(value):
                    with open(value, "w", encoding="utf-8") as fh:
                        json.dump({"graph": {"built_at_commit": self.HEAD},
                                   "nodes": [], "links": []}, fh)
            out[key] = value
        return out

    #: **DERIVED, not listed (v0.25).** This was seven hand-written pin shapes with a comment
    #: saying it was identical to `tests/test_ledger.py`'s list "because the principle is one" —
    #: and the principle was one while the CORPUS was two copies of somebody's memory. A reviewer
    #: extended it in a scratch copy of HEAD with eleven more shapes, all naming fields
    #: `PIN_FIELDS` already declared, and this unchanged gate went red: `verification: "observed"`
    #: killed `interview_next` over stdio. So the cases come from the schema the rule is about —
    #: see `tests/shape_corpus.py`.
    #: Both corpora, because this gate's claim is about READING and the two are read the same way.
    #: `broken_pins` is every shape the schema refuses; `sparse_pins` is every shape it ALLOWS and
    #: nobody had generated — an optional path simply omitted. The second half exists because
    #: `pin_read` repairs a null or wrongly-typed value into its result and materializes an absent
    #: one only for `PIN_GUARANTEED`, so a bracket index on a non-guaranteed path survives all ~100
    #: malformations and dies on the legal file. That is how `read["provenance"]` shipped, taking
    #: both tracker tools down with a bare `KeyError` — while this very gate was green, and while
    #: `instructions_diff`, `render_map` and `ledger_summary` read the same file fine.
    @staticmethod
    def BROKEN_PINS():
        from shape_corpus import broken_pins, sparse_pins
        return broken_pins() + sparse_pins()

    @staticmethod
    def _read_only_ledger_tools():
        """`(server tool name, tools.py callable)` for every read-only tool whose FIRST required
        argument is the ledger path — read off the `@mcp.tool` decoration, never listed here.

        *First*, not *only* (v0.28). `required == ["ledger"]` reads like the same predicate and is
        not: it silently excludes every read-only tool that also takes a `pin_id`, which is a whole
        class and was two tools. What makes a tool belong here is that it READS A LEDGER; what it
        needs besides the path is a payload, and payloads are declared in `MINIMAL_CALL`.
        """
        import ast
        path = os.path.join(os.path.dirname(__file__), "..", "src", "mcp", "server.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        out = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            annotations = [kw.value for dec in node.decorator_list if isinstance(dec, ast.Call)
                           for kw in dec.keywords if kw.arg == "annotations"]
            if not any("_RO" in ast.dump(a) for a in annotations):
                continue
            names = [a.arg for a in node.args.args]
            required = names[:len(names) - len(node.args.defaults)]
            if required[:1] != ["ledger"]:
                continue
            # The body is one `return tools.<fn>(...)`; the tool layer is what this exercises.
            called = next((c.func.attr for c in ast.walk(node)
                           if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                           and isinstance(c.func.value, ast.Name) and c.func.value.id == "tools"),
                          None)
            if called:
                out.append((node.name, getattr(tools, called)))
        return out

    def test_the_roster_is_derived_and_every_member_has_a_call(self):
        roster = self._read_only_ledger_tools()
        names = [name for name, _ in roster]
        self.assertIn("policy_preview", names,
                      "the tool the finding was reproduced on must be in the derived roster, or "
                      "the derivation is checking something else")
        for late in ("scope_check", "readiness_assess"):
            self.assertIn(late, names,
                          f"{late} is a read-only tool that reads a ledger and takes a `pin_id`; "
                          f"a membership rule that excludes it is the hole v0.28 closed")
        self.assertGreaterEqual(len(roster), 5, "the derivation went vacuous")
        self.assertEqual({name for name, _ in roster}, set(self.MINIMAL_CALL),
                         "a read-only ledger tool with no declared call would be listed and never "
                         "exercised — which is exactly how the first draft of this gate passed a "
                         "plant")

    def test_every_minimal_call_reaches_the_file(self):
        """The half that makes the other half an exercise: on a WELL-FORMED ledger every declared
        call must simply answer. A call that refuses here is refusing on its arguments, so its run
        against a broken ledger proves nothing about the body."""
        tmp = tempfile.mkdtemp()
        path = _ledger_with_pins(tmp)
        for name, fn in self._read_only_ledger_tools():
            with self.subTest(tool=name):
                fn(path, **self._call(name, path, tmp))

    def test_no_read_only_ledger_tool_dies_on_a_pin_shape(self):
        tmp = tempfile.mkdtemp()
        roster = self._read_only_ledger_tools()
        cases = self.BROKEN_PINS()
        self.assertGreater(len(cases), 60, "the derived corpus went vacuous")
        for index, (label, broken) in enumerate(cases):
            path = _ledger_with_pins(tempfile.mkdtemp(dir=tmp))
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            broken = dict(broken)
            broken.setdefault("id", f"pin_{index + 900:04d}")
            data["pins"].append(broken)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            for name, fn in roster:
                with self.subTest(tool=name, pin=label):
                    try:
                        fn(path, **self._call(name, path, tmp))
                    except self.SHAPE_DEATHS as exc:
                        self.fail(f"{name} died on the file rather than answering about it: "
                                  f"{type(exc).__name__}: {exc}")
                    except Exception:
                        pass          # a refusal about the CALL is a legitimate answer

    def test_no_read_only_ledger_tool_dies_on_a_policy_shape(self):
        """The same corpus one collection over. `policies` was the collection whose CONTAINER was
        guarded a round before its FIELDS were, so it is exactly the half a pin-shaped corpus
        cannot see."""
        from shape_corpus import broken_policies, sparse_policies
        tmp = tempfile.mkdtemp()
        roster = self._read_only_ledger_tools()
        for index, (label, broken) in enumerate(broken_policies() + sparse_policies()):
            path = _ledger_with_pins(tempfile.mkdtemp(dir=tmp))
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            broken = dict(broken)
            broken.setdefault("id", f"pol_{index + 900:04d}")
            data.setdefault("policies", []).append(broken)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            for name, fn in roster:
                with self.subTest(tool=name, policy=label):
                    try:
                        fn(path, **self._call(name, path, tmp))
                    except self.SHAPE_DEATHS as exc:
                        self.fail(f"{name} died on the file rather than answering about it: "
                                  f"{type(exc).__name__}: {exc}")
                    except Exception:
                        pass

    def test_no_read_only_ledger_tool_dies_on_a_log_entry_shape(self):
        """The LOG half, derived from `LOG_ENTRY_PREFIXES`. It is here because the pin corpus could
        not see it: a well-formed log let `learning.divergences`' `e["id"].startswith(...)` survive
        a plant of its own reversal, and that expression is the one v0.18 removed from `summary()`
        with a comment naming it."""
        from shape_corpus import broken_events
        tmp = tempfile.mkdtemp()
        roster = self._read_only_ledger_tools()
        cases = broken_events()
        self.assertGreater(len(cases), 20, "the derived corpus went vacuous")
        for label, entry in cases:
            path = _ledger_with_pins(tempfile.mkdtemp(dir=tmp))
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            data.setdefault("decision_log", []).append(entry)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            for name, fn in roster:
                with self.subTest(tool=name, event=label):
                    try:
                        fn(path, **self._call(name, path, tmp))
                    except self.SHAPE_DEATHS as exc:
                        self.fail(f"{name} died on the file rather than answering about it: "
                                  f"{type(exc).__name__}: {exc}")
                    except Exception:
                        pass

    def test_no_read_only_ledger_tool_dies_on_the_shape_of_the_file_itself(self):
        """The container half and the top level, derived from `LEDGER_COLLECTIONS` the way the
        record half is derived from the shape tables. A ledger whose ROOT is a list or a string is
        the one nothing covered: it killed all four surfaces with a raw `AttributeError` because
        `Ledger.__init__` reached `self.data.get("version")` before any guard ran. The answer is a
        refusal that names the fault — never a stack trace, which is what `SHAPE_DEATHS` asserts."""
        from shape_corpus import broken_ledgers
        tmp = tempfile.mkdtemp()
        roster = self._read_only_ledger_tools()
        base_path = _ledger_with_pins(tempfile.mkdtemp(dir=tmp))
        with open(base_path, encoding="utf-8") as fh:
            base = json.load(fh)
        cases = broken_ledgers(base)
        self.assertGreater(len(cases), 12, "the derived corpus went vacuous")
        for label, data in cases:
            path = os.path.join(tempfile.mkdtemp(dir=tmp), "ledger.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            for name, fn in roster:
                with self.subTest(tool=name, file=label):
                    try:
                        fn(path, **self._call(name, path, tmp))
                    except self.SHAPE_DEATHS as exc:
                        self.fail(f"{name} died on the file rather than answering about it: "
                                  f"{type(exc).__name__}: {exc}")
                    except Exception:
                        pass

def _ast_tools():
    import ast
    path = os.path.join(os.path.dirname(__file__), "..", "src", "mcp", "tools.py")
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path), ast


def _ledger_bound(fn, ast):
    """The local names a function bound a `Ledger` to — from `_open_existing` / `_open_or_create`.

    Anchored on the opener rather than on the convention that it is always called `led`: a door that
    calls its ledger something else is exactly the door a name-based check would miss.
    """
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                and isinstance(node.value.func, ast.Name) \
                and node.value.func.id in ("_open_existing", "_open_or_create"):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


class TestOneCommitPointForEveryLedgerWrite(unittest.TestCase):
    """v0.24 — 18 functions called `save()`, 17 of them then re-projected the live map.

    Measured by AST over `src/mcp/tools.py`, and `ledger_label_failure` was the eighteenth — while
    `_livemap_marker`'s own docstring states the rule it was breaking. Verified over stdio with a
    live map registered: the page on disk stayed byte-identical, so a `FailureEvent` the measurer
    had just written was absent from the surface a human was watching, and the next unrelated write
    made it appear.

    The fix is not the eighteenth call, so neither is the test: what is asserted is that there is
    exactly ONE place in this module where a ledger write is finished.
    """

    def test_no_door_reaches_save_except_the_commit_point(self):
        tree, ast = _ast_tools()
        offenders = []
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name == "_saved":
                continue
            bound = _ledger_bound(fn, ast)
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "save" and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in bound):
                    offenders.append(f"{fn.name}:{node.lineno}")
        self.assertEqual(offenders, [],
                         f"a ledger write that finishes outside `_saved` at {offenders} — the live "
                         "map registered for that file will not be re-projected, and the page's "
                         "own badge will go on saying it is live")

    def test_the_commit_point_does_both_halves_and_is_actually_used(self):
        tree, ast = _ast_tools()
        fns = {n.name: n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        inside = {c.func.attr for c in ast.walk(fns["_saved"])
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
        inside |= {c.func.id for c in ast.walk(fns["_saved"])
                   if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        self.assertLessEqual({"save", "_refresh_live_maps"}, inside,
                             "the one commit point stopped doing one of its two halves")
        callers = {name for name, fn in fns.items()
                   if name != "_saved" and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                                               and c.func.id == "_saved" for c in ast.walk(fn))}
        self.assertGreaterEqual(len(callers), 18,
                                "the roster went vacuous — 18 doors reached `save()` when this was "
                                "written")

    def test_the_door_that_was_the_eighteenth_re_projects_the_live_map(self):
        """The reproduction, at the tool. `label_failure` changes no pin state, which is exactly why
        it was the one nobody noticed: what it writes is an event, and the page inlines the log."""
        tmp = tempfile.mkdtemp()
        ledger = os.path.join(tmp, "ledger.json")
        out = os.path.join(tmp, "map.html")
        pin = tools.ledger_add_pin(ledger, kind="defect", title="double charge", severity="high",
                                   confidence="extracted",
                                   provenance=[{"source": "recon", "detail": "x"}])["pin_id"]
        tools.render_map(ledger, out, live=True)
        with open(out, encoding="utf-8") as fh:
            before = fh.read()
        tools.ledger_label_failure(ledger, pin, failure_class="untested_path",
                                   detail="the same failure came back in production",
                                   phase="production")
        with open(out, encoding="utf-8") as fh:
            after = fh.read()
        self.assertNotEqual(before, after)
        self.assertIn("the same failure came back in production", after,
                      "the event reached the file and not the surface a human is watching")


class TestOneRefusalForTheQuoteRule(unittest.TestCase):
    """v0.24 — *an agent-relayed election must quote the human* had four enforcement points.

    Two in `record_decision` (the `transcribed` rung, and the freeform path where the human's words
    ARE the outcome), one in `record_policy`, one in `ledger_defer`. They agreed, which is the shape
    every finding on this branch started as. Membership — WHICH rung owes a quote — is
    `ledger.QUOTED_RUNGS`; the refusal is `_require_quote`; and the roster below is derived.
    """

    def test_every_door_that_takes_the_words_asks_the_one_refusal_for_them(self):
        tree, ast = _ast_tools()
        roster, asked = set(), set()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if fn.name.startswith("_"):
                continue
            if "human_answer" not in [a.arg for a in fn.args.args]:
                continue
            roster.add(fn.name)
            if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                   and c.func.id == "_require_quote" for c in ast.walk(fn)):
                asked.add(fn.name)
        self.assertEqual(roster, {"record_decision", "record_policy", "ledger_defer",
                                  # v0.31 — the two fog exits. Neither elects an outcome, and both
                                  # take the words for the reason `ledger_defer` does: each one
                                  # stops something being asked. Graduating settles HOW the fork is
                                  # put, which is where an agent would smuggle the answer in;
                                  # clearing settles that there is no fork at all.
                                  "ledger_graduate_fog", "ledger_clear_fog"},
                         "the derivation stopped finding the doors it was written for")
        self.assertEqual(roster, asked,
                         "a door that accepts the human's words and enforces the rule itself is "
                         "the fifth site — put it through `_require_quote`")

    def test_the_membership_question_lives_with_the_schema(self):
        import ledger as mod
        self.assertEqual(mod.QUOTED_RUNGS, ("transcribed",))
        for rung in mod.DECISION_EVIDENCE:
            with self.subTest(rung=rung):
                if rung in mod.QUOTED_RUNGS:
                    with self.assertRaises(ValueError):
                        tools._require_quote("", rung)
                else:
                    tools._require_quote("", rung)      # must not raise
        with self.assertRaises(ValueError):
            tools._require_quote("   ", "transcribed")  # whitespace is not a quote
        with self.assertRaises(ValueError):
            tools._require_quote("", "elicited", freeform=True)   # the words ARE the outcome

    def test_all_four_sites_still_refuse_over_the_tool_layer(self):
        """The behavioural half, reproduced verbatim at each door. A carrier that no longer refuses
        is worse than four sentences that agree."""
        tmp = tempfile.mkdtemp()
        ledger = os.path.join(tmp, "ledger.json")
        pin = tools.ledger_add_pin(
            ledger, kind="open_decision", title="session or jwt", severity="medium",
            confidence="inferred", provenance=[{"source": "interview", "detail": "frame"}],
            question={"prompt": "session or jwt?",
                      "options": [{"id": "session", "label": "server sessions"},
                                  {"id": "jwt", "label": "stateless jwt"}],
                      "allow_freeform": True})["pin_id"]
        calls = {
            "record_decision (transcribed)": lambda: tools.record_decision(
                ledger, pin, "session", rationale="simplest", flip_criteria="multi-region"),
            "record_decision (freeform)": lambda: tools.record_decision(
                ledger, pin, "freeform", rationale="simplest", flip_criteria="multi-region"),
            "ledger_defer": lambda: tools.ledger_defer(
                ledger, pin, rationale="later", flip_criteria="if a customer asks"),
            "record_policy": lambda: tools.record_policy(
                ledger, rule="the DB wins on nullability",
                applies_to={"kind": "contract_mismatch"}, default_outcome="db"),
        }
        for label, call in calls.items():
            with self.subTest(door=label):
                with self.assertRaises(ValueError) as ctx:
                    call()
                self.assertIn("human_answer", str(ctx.exception))


class TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach(unittest.TestCase):
    """v0.24 — the roster half of `ledger.PIN_WRITE_DOORS`, derived from this module.

    Reproduced over real stdio on one `resolved` defect: `ledger_set_question` and
    `ledger_add_proposals` refused it in near-identical sentences, and `ledger_add_remediation`,
    `ledger_set_remediation_status`, `ledger_premortem` and `ledger_set_readiness` accepted it.

    **The roster is derived and the CALL is declared**, held together by set equality — the shape
    `TestNoReadOnlyLedgerToolDiesOnAPinShape` was corrected to after its first draft quantified over
    a tool it never exercised. A write door added to this module has to be given a call here, and
    the ledger method it reaches has to be given a disposition, before the suite passes.
    """

    #: tool name -> the arguments beyond `ledger` and `pin_id`. Everything else is derived.
    CALL = {
        "record_decision": {"option_id": "opt_a", "rationale": "r", "flip_criteria": "f",
                            "human_answer": "opt A"},
        "ledger_defer": {"rationale": "r", "flip_criteria": "f", "human_answer": "not now"},
        # `rung` is part of the minimal LEGITIMATE call here: a reopen demotes the envelope,
        # so a resolve with no fresh rung refuses as `unverified` — a true refusal about a
        # different rule, which would make the closed-work run below prove nothing.
        "ledger_resolve": {"evidence": "re-observed on staging", "rung": "observed"},
        "ledger_add_remediation": {"action": "align", "ladder_rung": 3},
        "ledger_set_remediation_status": {"item_id": "rem_0001", "status": "todo"},
        "ledger_set_readiness": {"verdict": "ready", "zone": {"files": ["a.py"]},
                                 "evidence": {"graph": "n/a"}},
        "ledger_mark_correctness_unknown": {"blocked_by": "no oracle", "attempted": ["tests"]},
        "ledger_premortem": {"failure_modes": [{"class": "unfalsifiable",
                                                "description": "the oracle cannot fail"}],
                             "guardrails": ["measure p95 on prod"]},
        "ledger_label_failure": {"failure_class": "untested_path", "detail": "it came back",
                                 "phase": "production"},
        "ledger_cross_derive": {"claim": "the retry is idempotent",
                                "derivations": [{"provider": "anthropic", "model": "o",
                                                 "result": "yes"},
                                                {"provider": "openai", "model": "g",
                                                 "result": "no"}],
                                "agreement": "disagree"},
        "ledger_reopen": {"reason": "it came back in production", "fired": "incident"},
        "ledger_challenge": {"target": "to_be", "challenge_class": "unfalsifiable",
                             "argument": "the oracle cannot fail", "severity": "high",
                             "upheld": True},
        "ledger_set_question": {"question": {"prompt": "which side wins?",
                                             "options": [{"id": "db", "label": "db"},
                                                         {"id": "api", "label": "api"}],
                                             "allow_freeform": True}},
        "ledger_add_proposals": {"proposals": [{"summary": "token bucket at the edge"}]},
        "ledger_claim": {"holder": "sess_a"},
        # No holder: `release` with one releases only that holder's claim, and this fixture's pin
        # carries none — so passing a holder would make the run answer a different question.
        "ledger_release": {},
    }

    @staticmethod
    def _write_doors():
        """(tool name, the `Ledger` methods it calls) for every function here that takes a `pin_id`
        and finishes a write. Both halves matter: `pin_id` is what makes it a PER-PIN door, and
        `_saved` is what makes it a write."""
        import inspect

        import ledger as mod
        tree, ast = _ast_tools()
        mutators = {n for n, _ in inspect.getmembers(mod.Ledger, inspect.isfunction)
                    if n in mod.PIN_WRITE_DOORS}
        out = {}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "pin_id" not in [a.arg for a in fn.args.args]:
                continue
            bound = _ledger_bound(fn, ast)
            calls = {c.func.attr for c in ast.walk(fn)
                     if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                     and isinstance(c.func.value, ast.Name) and c.func.value.id in bound}
            if "_saved" not in {c.func.id for c in ast.walk(fn)
                                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}:
                continue
            out[fn.name] = calls & mutators
        return out

    def test_the_roster_is_derived_and_every_door_is_declared_on_both_sides(self):
        import ledger as mod
        doors = self._write_doors()
        self.assertGreaterEqual(len(doors), 13, "the derivation went vacuous")
        self.assertEqual(set(doors), set(self.CALL),
                         "a per-pin write door with no declared call would be listed and never "
                         "exercised — which is exactly how a gate passes a plant")
        reached = set().union(*doors.values())
        self.assertEqual(reached, set(mod.PIN_WRITE_DOORS),
                         "a `Ledger` method an agent can reach with a pin_id, and nothing saying "
                         "what it does to FINISHED work — declare it in `PIN_WRITE_DOORS`")

    def _resolved(self, tmp):
        """One `resolved` defect, carrying a fork so the election doors reach their own gate rather
        than refusing earlier for a different reason."""
        ledger = os.path.join(tmp, "ledger.json")
        pin = tools.ledger_add_pin(
            ledger, kind="defect", title="double charge on retry", severity="high",
            confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
            as_is={"description": "d"},
            question={"prompt": "which fix?",
                      "options": [{"id": "opt_a", "label": "idempotency key"}],
                      "allow_freeform": True})["pin_id"]
        item = tools.ledger_add_remediation(ledger, pin, action="align",
                                            ladder_rung=2)["item_id"]
        tools.ledger_set_remediation_status(ledger, pin, item, "done")
        tools.ledger_resolve(ledger, pin, evidence="replayed on staging; one charge",
                             rung="observed")
        return ledger, pin

    def test_every_declared_call_runs_on_work_that_is_not_finished(self):
        """The half that makes the other half an exercise: on an OPEN pin each declared call must
        simply answer. A call that refuses here is refusing on its arguments, so its run against a
        resolved pin proves nothing about the rule."""
        for tool_name, kwargs in sorted(self.CALL.items()):
            with self.subTest(door=tool_name):
                tmp = tempfile.mkdtemp()
                ledger, pin = self._resolved(tmp)
                tools.ledger_reopen(ledger, pin, reason="it came back", fired="incident")
                if tool_name == "ledger_set_question":
                    continue        # write-if-absent, and this fixture poses a fork on purpose
                getattr(tools, tool_name)(ledger, pin, **kwargs)

    def test_finished_work_is_refused_or_recorded_exactly_as_the_table_says(self):
        """The reproduction, quantified. The expectation per door is DERIVED from the table: a
        `refuse` or `settlement` method must raise, an `arc` or `records_only` one must not."""
        import ledger as mod
        raises = {"refuse", "settlement"}
        self.assertLessEqual(raises, set(mod.CLOSED_WORK_DISPOSITIONS))
        for tool_name, methods in sorted(self._write_doors().items()):
            dispositions = {mod.PIN_WRITE_DOORS[m] for m in methods}
            expect_raise = bool(dispositions & raises)
            with self.subTest(door=tool_name, dispositions=sorted(dispositions)):
                tmp = tempfile.mkdtemp()
                ledger, pin = self._resolved(tmp)
                call = lambda: getattr(tools, tool_name)(ledger, pin, **self.CALL[tool_name])
                if expect_raise:
                    with self.assertRaises(Exception) as ctx:
                        call()
                    self.assertIn("finished", str(ctx.exception),
                                  "the refusal must say the work is over, not fail for some other "
                                  "reason — that is how a door passes this gate vacuously")
                else:
                    call()


class TestNoWriteDoorDiesOnThePinAlreadyInTheFile(unittest.TestCase):
    """v0.26 — the read path was hardened twice; the write doors read the same pins.

    Reproduced over real `uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd,
    on shapes `shape_corpus` already derives: **42 crash sites across all fourteen per-pin write
    doors.** `KeyError: 'state'` at every one, from `_gate_closed`; `'str' object has no attribute
    'get'` at `add_remediation`, `challenge`, `reopen` and `cross_derive`; `KeyError: 'title'` at
    the election door `record_decision`, before `decide` was reached; `KeyError: 'depends_on'` at
    `set_readiness`. A write door that crashes on the file it was given is the same defect as a
    reader that does, and it is worse — the caller is mid-transaction.

    Both halves are derived. The roster is `TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach
    ._write_doors()`, which is *any tool taking a `pin_id` that reaches the commit point*; the
    corpus is `shape_corpus.broken_pins()`, which is every violation `PIN_SHAPES` can describe.
    Nothing here is a list of what somebody reproduced.
    """

    CRASH = (AttributeError, TypeError, KeyError, IndexError)

    @staticmethod
    def _looks_a_pin_up(name, source_tree=None):
        """The attribute names this tool calls on its ledger with a `pin_id`."""
        tree, ast = _ast_tools()
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
        bound = _ledger_bound(fn, ast)
        return {c.func.attr for c in ast.walk(fn)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and isinstance(c.func.value, ast.Name) and c.func.value.id in bound}

    def test_no_write_door_looks_a_pin_up_any_other_way(self):
        """The structural half, and the one that would have caught `record_decision`: it reached
        `decide` (which is guarded) and died at `_prompt_from_pin` on its OWN `led.pin(pin_id)`,
        three lines earlier. So the rule is not *a door reaches the carrier* but **the carrier is
        the only per-pin lookup on the write path**."""
        roster = TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach
        doors = roster._write_doors()
        self.assertGreaterEqual(len(doors), 13, "the derivation went vacuous")
        for name in sorted(doors):
            with self.subTest(door=name):
                self.assertNotIn("pin", self._looks_a_pin_up(name),
                                 f"{name} looks a pin up through the READ lookup, which guards a "
                                 f"shape instead of refusing it — use `writable_pin`")

    def test_every_ledger_method_a_door_reaches_goes_through_the_carrier(self):
        """The same rule one layer in, over `PIN_WRITE_DOORS` — derived, so a door added to the
        table inherits it. A method that delegates to another door is covered by that door."""
        import ast
        import inspect

        import ledger as mod
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for name in sorted(mod.PIN_WRITE_DOORS):
            fn = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == name)
            called = {c.func.attr for c in ast.walk(fn)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                      and isinstance(c.func.value, ast.Name) and c.func.value.id == "self"}
            with self.subTest(door=name):
                self.assertTrue("writable_pin" in called or called & set(mod.PIN_WRITE_DOORS),
                                f"`Ledger.{name}` takes a pin_id and never reaches `writable_pin`, "
                                f"so it indexes whatever the file holds")
                self.assertNotIn("pin", called,
                                 f"`Ledger.{name}` uses the READ lookup on the write path")

    def test_no_door_crashes_on_any_shape_the_schema_can_describe(self):
        """The behavioural half: every derived door against every derived broken pin. A refusal is
        the answer; a `KeyError` naming a line of ours about somebody's file is the finding."""
        from shape_corpus import broken_pins
        import ledger as mod
        roster = TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach
        doors = sorted(roster._write_doors())
        cases = broken_pins()
        self.assertGreaterEqual(len(cases), 100, "the corpus derivation went vacuous")
        tmp = tempfile.mkdtemp()
        crashes = []
        for index, (label, broken) in enumerate(cases):
            pin_id = mod.pin_read(broken)["id"]
            for door in doors:
                path = os.path.join(tmp, f"l{index}.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"version": mod.SCHEMA_VERSION, "pins": [json.loads(
                        json.dumps(broken))], "decision_log": [], "policies": []}, fh)
                try:
                    getattr(tools, door)(path, pin_id, **roster.CALL[door])
                except self.CRASH as exc:
                    crashes.append(f"{door} on [{label}]: {type(exc).__name__}: {exc}")
                except Exception:
                    pass                      # a refusal naming what cannot be read is the answer
        self.assertEqual(crashes, [], "\n".join(crashes[:20]))


def _every_write_door():
    """Every write door an agent can reach, per-pin and ledger-wide, with its declared payload.

    The union of the two derived rosters — `TestALedgerWideWriteDoorIsOnARosterToo
    ::test_the_two_rosters_together_are_every_write_door_in_this_module` is what asserts that union
    is the whole module, so a door added tomorrow arrives here without anyone remembering.
    """
    per_pin = TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach
    wide = TestALedgerWideWriteDoorIsOnARosterToo
    out = [(name, True, per_pin.CALL[name]) for name in sorted(per_pin._write_doors())]
    out += [(name, False, kwargs) for name, (_disposition, kwargs) in sorted(wide.WIDE.items())]
    # The one sentinel a ledger-wide payload can carry, resolved against the shared fixture the way
    # `_targets` resolves the per-pin one. `_fixture` seeds exactly one fog patch and asserts its
    # id, so this is a lookup rather than a guess.
    return [(name, is_pin, {k: (_FOG_ID if v == wide.FOG else v) for k, v in kwargs.items()})
            for name, is_pin, kwargs in out]


#: The id `_fixture`'s single fog patch gets. Held there, not hoped for here.
_FOG_ID = "fog_0001"


def _fixture(tmp):
    """`(ledger data, candidate pin ids)` — one ledger every declared call above can run against.

    The catalog is seeded (`record_policy` resolves its `offer_id` out of it), and the first pin has
    walked remediation → resolve → reopen, which is what `test_every_declared_call_runs_on_work
    _that_is_not_finished` established as the state where each declared call answers rather than
    refusing on a rule of its own. The second poses NO fork, because `ledger_set_question` is
    write-if-absent and the first one carries the fork every election door needs.
    """
    ledger = os.path.join(tmp, "ledger.json")
    tools.interview_expand(ledger)
    pin = tools.ledger_add_pin(
        ledger, kind="defect", title="double charge on retry", severity="high",
        confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
        as_is={"description": "d"},
        question={"prompt": "which fix?", "options": [{"id": "opt_a", "label": "idempotency key"}],
                  "allow_freeform": True})["pin_id"]
    item = tools.ledger_add_remediation(ledger, pin, action="align", ladder_rung=2)["item_id"]
    tools.ledger_set_remediation_status(ledger, pin, item, "done")
    tools.ledger_resolve(ledger, pin, evidence="replayed on staging", rung="observed")
    tools.ledger_reopen(ledger, pin, reason="it came back", fired="incident")
    bare = tools.ledger_add_pin(
        ledger, kind="defect", title="a finding whose fork nobody has written yet", severity="low",
        confidence="extracted", provenance=[{"source": "recon", "detail": "x"}])["pin_id"]
    # One fog patch, so the two doors that CONSUME one have something to consume. Its id is asserted
    # rather than assumed, because `_every_write_door` resolves the `FOG` sentinel to it.
    patch = tools.ledger_add_fog(
        ledger, area="billing", sensed="trials are special-cased in three places",
        provenance=[{"source": "interview", "detail": "phase 2"}])["fog_id"]
    assert patch == _FOG_ID, f"the fixture's fog id moved to {patch}; `_FOG_ID` names it"
    with open(ledger, encoding="utf-8") as fh:
        return json.load(fh), (pin, bare)


def _planted(tmp, data, index=0):
    """`data` written to its own ledger file, so each case starts from the same bytes."""
    path = os.path.join(tempfile.mkdtemp(dir=tmp), f"l{index}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _targets(base, tmp, candidates):
    """`door -> pin id` — the fixture pin each declared payload can actually be applied to.

    Derived by ASKING (each candidate is tried on a scratch copy and the first that answers wins),
    not declared: naming the door that needs the questionless pin is how a table acquires an
    exemption nobody re-checks. A door that answers on neither is a fail, loudly — a gate whose
    subject is what happens *inside* a door proves nothing about one that refused on its arguments.
    """
    out, unrunnable = {}, []
    for index, (door, per_pin, kwargs) in enumerate(_every_write_door()):
        if not per_pin:
            out[door] = None
            continue
        for pin_id in candidates:
            try:
                getattr(tools, door)(_planted(tmp, base, 900 + index), pin_id, **kwargs)
            except Exception:                             # noqa: BLE001
                continue
            out[door] = pin_id
            break
        else:
            unrunnable.append(door)
    if unrunnable:
        raise AssertionError(f"no fixture pin lets {unrunnable} run, so every case below would be "
                             f"a refusal about the call rather than an exercise of the door")
    return out


class TestNoWriteDoorDiesOnAPinItIsNotWritingTo(unittest.TestCase):
    """v0.28 — `writable_pin` guards the pin being written and no other.

    Reproduced with a WELL-FORMED target both times, over real
    `uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd: a `ledger_reopen` and
    a `ledger_set_readiness` on a healthy pin both died with `KeyError: 'id'` because a DIFFERENT pin
    in the file carried none, and `ledger_add_pin` / `ledger_surface_assumption` /
    `interview_expand` / `ledger_cross_derive` died the same way on a bare string among the pins. The
    blast radius of one malformed record was the whole file.

    Both axes are derived and neither names a function: the doors are the union of the two rosters,
    the bystanders are `shape_corpus.broken_pins()` — every violation `PIN_SHAPES` can describe. The
    sibling class one up runs the same corpus with the broken pin as the TARGET, where the answer is
    a refusal; here the answer is that nothing happens to the call at all.
    """

    CRASH = (AttributeError, TypeError, KeyError, IndexError)

    def test_no_door_crashes_because_a_different_pin_is_unreadable(self):
        from shape_corpus import broken_pins
        tmp = tempfile.mkdtemp()
        base, candidates = _fixture(tempfile.mkdtemp())
        doors = _every_write_door()
        targets = _targets(base, tmp, candidates)
        cases = broken_pins()
        self.assertGreaterEqual(len(doors), 17, "the roster union went vacuous")
        self.assertGreaterEqual(len(cases), 100, "the corpus derivation went vacuous")
        crashes = []
        for index, (label, broken) in enumerate(cases):
            broken = json.loads(json.dumps(broken))
            if isinstance(broken.get("id"), str):
                broken["id"] = f"pin_{index + 900:04d}"    # unless the fault IS the id
            data = json.loads(json.dumps(base))
            data["pins"].append(broken)
            data["pins"].append("a bare string where a pin goes")
            for door, per_pin, kwargs in doors:
                path = _planted(tmp, data, index)
                args = (path, targets[door]) if per_pin else (path,)
                try:
                    getattr(tools, door)(*args, **kwargs)
                except self.CRASH as exc:
                    crashes.append(f"{door} on a bystander [{label}]: "
                                   f"{type(exc).__name__}: {exc}")
                except Exception:
                    pass          # a refusal about the CALL is a legitimate answer
        self.assertEqual(crashes, [], "\n".join(crashes[:20]))


class TestADoorThatReportsFailureCommittedNothing(unittest.TestCase):
    """v0.28 — three doors ran their reporting AFTER the commit, so a write landed and the caller
    was told it had not.

    Reproduced over real `uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd:
    two `resolved` pins, one `ledger_reopen`, and one hand-written log entry naming a `via` and no
    `pin_id`. `Ledger.cascaded_by` indexed `e["pin_id"]` raw, and it runs after `_saved` — so the
    root pin came back `needs_input` in the file and the tool answered `isError: KeyError: 'pin_id'`.
    An agent that reads that error retries, and the retry is a second reopen of a pin the first call
    already reopened.

    **Report-after-commit is its own bug class**, independent of the read that happened to raise:
    whatever a door returns must describe what happened. So the rule is positional and it is checked
    positionally — the commit is the LAST thing a door does — and the behavioural half derives its
    trap from what each door itself writes rather than from the one file a reviewer built.
    """

    @staticmethod
    def _committing_functions():
        """`name -> (body, index of the statement that commits)` for every door in the module."""
        tree, ast = _ast_tools()
        out = {}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            at = [i for i, stmt in enumerate(fn.body)
                  if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                         and c.func.id == "_saved" for c in ast.walk(stmt))]
            if at:
                out[fn.name] = (fn.body, at)
        return out, ast

    def test_the_commit_is_the_last_thing_every_door_does(self):
        """The structural half, quantified over every function that commits — so the nineteenth
        door inherits the rule instead of being written without it.

        A door may end with the commit, or with `return <name>` after it: the answer is computed
        first and then handed back untouched. Anything else — a lookup, a join, a dict literal that
        indexes a pin — is an expression that can raise on somebody's file with the write already on
        disk, which is the whole finding.
        """
        doors, ast = self._committing_functions()
        self.assertGreaterEqual(len(doors), 17, "the derivation went vacuous")
        for name, (body, at) in sorted(doors.items()):
            with self.subTest(door=name):
                self.assertEqual(len(at), 1, f"{name} commits more than once")
                index = at[0]
                if index == len(body) - 1:
                    continue
                self.assertEqual(index, len(body) - 2,
                                 f"{name} does {len(body) - 1 - index} more things after "
                                 f"committing; whatever it returns must describe what happened")
                tail = body[-1]
                self.assertTrue(isinstance(tail, ast.Return) and isinstance(tail.value, ast.Name),
                                f"{name} builds its answer after the commit — build it first, then "
                                f"commit, then `return` the name")

    def test_a_door_that_raises_left_the_file_byte_identical(self):
        """The behavioural half, and the trap is DERIVED from each door rather than declared: run
        the door once, read back the log ids it appended, then re-run it on a fresh copy of the same
        fixture carrying a hand-written `cas_` entry that names one of those ids as its `via` and
        nothing else. That is the reproduction — generalised to every door, including doors that
        read no radius at all, where the entry is simply inert.
        """
        tmp = tempfile.mkdtemp()
        base, candidates = _fixture(tempfile.mkdtemp())
        doors = _every_write_door()
        targets = _targets(base, tmp, candidates)
        self.assertGreaterEqual(len(doors), 17, "the roster union went vacuous")
        trapped, failures = set(), []
        before = {str(e.get("id")) for e in base["decision_log"]}
        for index, (door, per_pin, kwargs) in enumerate(doors):
            clean = _planted(tmp, base, index)
            args = (clean, targets[door]) if per_pin else (clean,)
            getattr(tools, door)(*args, **kwargs)
            with open(clean, encoding="utf-8") as fh:
                appended = [str(e.get("id")) for e in json.load(fh)["decision_log"]
                            if str(e.get("id")) not in before]
            for via in appended or [""]:
                planted = json.loads(json.dumps(base))
                planted["decision_log"].append({"id": "cas_9001", "via": via})
                path = _planted(tmp, planted, 100 + index)
                with open(path, encoding="utf-8") as fh:
                    was = fh.read()
                if via:
                    trapped.add(door)
                try:
                    getattr(tools, door)(*((path, targets[door]) if per_pin else (path,)), **kwargs)
                except Exception as exc:                  # noqa: BLE001
                    with open(path, encoding="utf-8") as fh:
                        now = fh.read()
                    if was != now:
                        failures.append(f"{door} reported {type(exc).__name__}: {exc} — and the "
                                        f"write is on disk. A caller that retries writes twice.")
        self.assertEqual(failures, [], "\n".join(failures[:10]))
        # The non-vacuity floor, derived rather than counted: a door that reads a cascade radius is
        # a door the planted `via` actually reaches, and those are exactly the three the finding was
        # reproduced on. If one of them stops appending an event, this loop stops being a trap for
        # it and says so instead of passing quietly.
        tree, ast = _ast_tools()
        radius_readers = {fn.name for fn in ast.walk(tree)
                          if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                          and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                                  and c.func.attr == "cascaded_by" for c in ast.walk(fn))}
        self.assertTrue(radius_readers, "nothing reads a radius, so the derivation went vacuous")
        self.assertLessEqual(radius_readers, trapped,
                             f"{sorted(radius_readers - trapped)} read a cascade radius and had no "
                             f"`via` planted — the trap missed the doors it was derived for")


class TestALedgerWideWriteDoorIsOnARosterToo(unittest.TestCase):
    """v0.27 — the write-door roster had a hole the exact shape of `interview_expand`.

    Every roster this branch derived is *a tool taking a `pin_id` that reaches the commit point*.
    Four tools reach the commit point and take no `pin_id` at all, so all four were outside every
    gate the write half of the surface acquired — and `TestNoWriteDoorDiesOnAMemberOfAListArgument`
    named two of them in a hand-written table, which is the wrong half of the wrong list.

    The defect the hole was hiding: **`interview_expand` was not idempotent.** Two calls on the
    default catalog left 24 pins for 12 clusters — every fork in the funnel duplicated, the newer
    copy taking the `depends_on` edges and the older one (which may already carry a decision, a
    brainstorm, a remediation) orphaned beside it. It is the Phase-1 step an agent re-runs after a
    context reset, i.e. the door most likely to be called twice by a caller that cannot tell whether
    it already ran.

    So the roster is derived over BOTH halves and their union is asserted to be every write door in
    the module, and each ledger-wide door declares what a second identical call does. Both
    directions are exercised: a `projects` door must add nothing, a `creates` door must add
    something — otherwise the classification is a free pass rather than a claim.
    """

    #: tool -> (disposition, the arguments beyond `ledger`).
    #:
    #: `projects` — it materialises a fixed external set into the ledger, so a second call must be a
    #: no-op. `creates` — each call records a fresh act (a finding, an assumption, an election), and
    #: two of those are two records; collapsing them would be this runtime deciding that two things
    #: a human did are one thing. `consumes` (v0.31) — the door CONSUMES the record it names, so a
    #: second identical call must refuse: the fog patch it graduated or cleared is gone, and a door
    #: that quietly did nothing there would let a caller believe it had graduated something twice.
    #:
    #: Substituted at call time, because a fog id has to name a patch in the fixture under test —
    #: the same reason `MINIMAL_CALL` cannot hold a literal pin id.
    FOG = "<a fog patch this ledger carries>"

    WIDE = {
        "ledger_add_pin": ("creates", {
            "kind": "defect", "title": "t", "severity": "low", "confidence": "extracted",
            "provenance": [{"source": "recon", "detail": "x"}]}),
        "ledger_surface_assumption": ("creates", {"title": "t", "detail": "d"}),
        "interview_expand": ("projects", {}),
        "record_policy": ("creates", {"offer_id": "cl_persistence",
                                      "human_answer": "yes, take the default"}),
        "ledger_add_fog": ("creates", {
            "area": "billing",
            "sensed": "three call sites already special-case trials",
            "provenance": [{"source": "interview", "detail": "phase 2"}]}),
        "ledger_graduate_fog": ("consumes", {
            "fog_id": FOG, "human_answer": "ask it as plan versus flag",
            "question": {"prompt": "Do trials get their own plan, or a flag on the paid one?",
                         "options": [{"id": "plan", "label": "their own plan"},
                                     {"id": "flag", "label": "a flag"}],
                         "allow_freeform": True}}),
        "ledger_clear_fog": ("consumes", {
            "fog_id": FOG, "rationale": "trials were cut from v1 entirely",
            "human_answer": "drop it, no trials in v1"}),
    }

    @staticmethod
    def _wide_doors():
        """Every function here that finishes a write and takes no `pin_id` — the other half of
        `TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach._write_doors`."""
        tree, ast = _ast_tools()
        out = set()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "pin_id" in [a.arg for a in fn.args.args]:
                continue
            if "_saved" in {c.func.id for c in ast.walk(fn)
                            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}:
                out.add(fn.name)
        return out

    def test_the_two_rosters_together_are_every_write_door_in_this_module(self):
        """The hole, asserted rather than remembered: a door that writes and is on neither roster
        is a door no write-path gate can see."""
        tree, ast = _ast_tools()
        every = {fn.name for fn in ast.walk(tree)
                 if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and "_saved" in {c.func.id for c in ast.walk(fn)
                                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}}
        per_pin = set(TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach._write_doors())
        wide = self._wide_doors()
        self.assertGreaterEqual(len(every), 17, "the derivation went vacuous")
        self.assertEqual(per_pin | wide, every)
        self.assertEqual(wide, set(self.WIDE),
                         "a ledger-wide write door with no declared call is exactly the position "
                         "`interview_expand` was in when it duplicated every fork in the funnel")

    def _seeded(self):
        """A ledger with the catalog already in it — `record_policy` resolves its offer from that
        catalog, and every door here needs a file that exists."""
        ledger = os.path.join(tempfile.mkdtemp(), "ledger.json")
        tools.interview_expand(ledger)
        return ledger

    @staticmethod
    def _records(ledger):
        with open(ledger, encoding="utf-8") as fh:
            data = json.load(fh)
        return {name: len(data.get(name) or [])
                for name in ("pins", "decision_log", "policies", "fog")}

    def _substituted(self, ledger, kwargs: dict) -> dict:
        """The declared call with its sentinels resolved against THIS fixture."""
        out = dict(kwargs)
        if out.get("fog_id") == self.FOG:
            out["fog_id"] = tools.ledger_add_fog(
                ledger, area="billing", sensed="trials are special-cased in three places",
                provenance=[{"source": "interview", "detail": "phase 2"}])["fog_id"]
        return out

    def test_a_second_identical_call_does_what_the_door_declares(self):
        for name, (disposition, declared) in sorted(self.WIDE.items()):
            with self.subTest(door=name, disposition=disposition):
                ledger = self._seeded()
                kwargs = self._substituted(ledger, declared)
                getattr(tools, name)(ledger, **kwargs)
                once = self._records(ledger)
                if disposition == "consumes":
                    with self.assertRaises(Exception, msg=f"{name} consumed the record it names, "
                                                          f"so calling it again must refuse rather "
                                                          f"than quietly do nothing"):
                        getattr(tools, name)(ledger, **kwargs)
                    self.assertEqual(self._records(ledger), once,
                                     "a refused call left something behind")
                    continue
                getattr(tools, name)(ledger, **kwargs)
                twice = self._records(ledger)
                if disposition == "projects":
                    self.assertEqual(twice, once,
                                     f"{name} projects a fixed set into the ledger, so calling it "
                                     f"again must add nothing — it used to add all of it again")
                else:
                    self.assertNotEqual(twice, once,
                                        f"{name} is declared as recording a fresh act each time; "
                                        f"if a second call adds nothing it is a projection and the "
                                        f"declaration is wrong")

    def test_the_projection_door_leaves_the_pins_it_found_exactly_as_they_were(self):
        """Idempotent is not the same as harmless: the pins already there must come back untouched,
        with their ids, so the `depends_on` edges an earlier call wired still resolve."""
        ledger = self._seeded()
        with open(ledger, encoding="utf-8") as fh:
            before = json.load(fh)["pins"]
        out = tools.interview_expand(ledger)
        with open(ledger, encoding="utf-8") as fh:
            after = json.load(fh)["pins"]
        self.assertEqual(before, after)
        self.assertEqual(out["created"], [])
        self.assertEqual({e["pin_id"] for e in out["already_present"]},
                         {p["id"] for p in after},
                         "every pin the catalog put here is named back, so the caller can wire to "
                         "the fork that exists rather than assume none does")
        self.assertEqual({e["cluster_id"] for e in out["already_present"]},
                         set(out["id_map"]),
                         "and each one is in `id_map`, which is what `depends_on` is wired from")

    def test_a_brief_naming_a_fork_that_already_exists_is_reported_not_applied(self):
        """The one input the second call can still carry. It is not silently dropped and it is not
        applied: the pin exists, and settling an existing pin is `record_decision`'s door."""
        ledger = self._seeded()
        with open(ledger, encoding="utf-8") as fh:
            log_before = json.load(fh)["decision_log"]
        out = tools.interview_expand(ledger, brief_decisions={
            "persistence": {"outcome": "relational", "quote": "one relational store for v1"}})
        entry = next(e for e in out["already_present"] if e["cluster_id"] == "persistence")
        self.assertEqual(entry["brief_ignored"], "relational")
        with open(ledger, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["decision_log"], log_before)


class TestNoWriteDoorDiesOnAMemberOfAListArgument(unittest.TestCase):
    """v0.25 — three write doors refused the same malformed argument three different ways, and two
    of them did not refuse it at all.

    Reproduced over real stdio against the shipped plugin: `ledger_premortem` said *"each failure
    mode must be an object"*, while `ledger_add_proposals` returned `'str' object has no attribute
    'get'` and `ledger_add_pin`'s assumption check returned the same from inside a generator
    expression. A refusal is a sentence an agent can act on; a `TypeError` naming a line of ours is
    a stack trace about a mistake of theirs — and the argument is one an agent COMPOSES, so it is
    the argument most likely to arrive wrong.

    The rule gets one carrier (`ledger._require_objects`) and this quantifies over every door that
    takes a list, with the probe points DERIVED from the declared call of the roster one class up —
    which is itself held to the derived door roster by set equality. Nothing here is a list of the
    three doors somebody reproduced.
    """

    #: The doors that take no `pin_id`, and therefore fall outside the per-pin roster. **Not a
    #: second table (v0.27):** this used to be two hand-written entries here, which is how it went
    #: unnoticed that four tools are in that position and not two — the same hole that let
    #: `interview_expand` duplicate every fork in the funnel. It is now the ledger-wide roster,
    #: which is itself held to the derived set by equality one class up.
    CREATE_CALL = {name: kwargs for name, (_disposition, kwargs)
                   in TestALedgerWideWriteDoorIsOnARosterToo.WIDE.items()}

    @staticmethod
    def _lists_under(value, prefix=""):
        """Every dotted path to a list INSIDE this argument, the argument itself included.

        **v0.26 — the rule was paid only at TOP-LEVEL list arguments.** This walk used to be one
        `isinstance(value, list)` per kwarg, so a list one level inside a dict argument was outside
        the whole mechanism: `ledger_add_pin(question={"options": ["a bare string"]})` and
        `ledger_set_question` with the byte-identical dict both returned `'str' object has no
        attribute 'get'` over real stdio — the exact failure `_require_objects` was written to
        close, at the two doors that compose the fork the whole funnel runs on. Recursive, so a
        third nesting level arrives under the gate rather than under the next reviewer.
        """
        out = []
        if isinstance(value, list):
            out.append(prefix)
        elif isinstance(value, dict):
            for key, sub in value.items():
                out += TestNoWriteDoorDiesOnAMemberOfAListArgument._lists_under(
                    sub, f"{prefix}.{key}" if prefix else key)
        return out

    @staticmethod
    def _broken_at(value, path):
        """A deep copy of `value` with the list at `path` replaced by one bare string."""
        bare = ["a bare string where an object goes"]
        steps = path.split(".")
        if len(steps) == 1:                 # the argument IS the list
            return bare
        broken = json.loads(json.dumps(value))
        node = broken
        for step in steps[1:-1]:
            node = node[step]
        node[steps[-1]] = bare
        return broken

    def _probes(self):
        """(tool, kwargs, the dotted path to a list) for every list an agent can pass to a door,
        at any depth."""
        roster = TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach
        out = []
        for per_pin, table in ((True, roster.CALL), (False, self.CREATE_CALL)):
            for tool_name, kwargs in sorted(table.items()):
                for key, value in kwargs.items():
                    for path in self._lists_under(value, key):
                        out.append((tool_name, kwargs, path, per_pin))
        return out

    def test_the_probe_set_is_derived_and_not_empty(self):
        probes = self._probes()
        self.assertGreaterEqual(len(probes), 5, "the derivation went vacuous")
        self.assertIn("ledger_premortem", {t for t, _k, _a, _p in probes})
        self.assertIn("ledger_add_proposals", {t for t, _k, _a, _p in probes})
        self.assertIn("ledger_add_pin", {t for t, _k, _a, _p in probes})
        self.assertIn(("ledger_set_question", "question.options"),
                      {(t, a) for t, _k, a, _p in probes},
                      "a list one level inside a dict argument is the v0.26 finding, and the probe "
                      "set that cannot reach it is the gate that missed it")

    def test_a_bare_string_where_an_object_goes_is_refused_not_crashed(self):
        from ledger import Ledger
        roster = TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach
        for tool_name, kwargs, argument, per_pin in self._probes():
            with self.subTest(door=tool_name, argument=argument):
                tmp = tempfile.mkdtemp()
                path = os.path.join(tmp, "ledger.json")
                led = Ledger(path)
                pin = led.add_pin(kind="defect", title="double charge", severity="high",
                                  confidence="extracted",
                                  provenance=[{"source": "recon", "detail": "x"}],
                                  question={"prompt": "which?",
                                            "options": [{"id": "a", "label": "A"},
                                                        {"id": "b", "label": "B"}],
                                            "allow_freeform": True})
                led.save()
                top, _, _rest = argument.partition(".")
                broken = dict(kwargs)
                broken[top] = self._broken_at(kwargs[top], argument)
                args = (path, pin["id"]) if per_pin else (path,)
                try:
                    getattr(tools, tool_name)(*args, **broken)
                except (AttributeError, TypeError, KeyError, IndexError) as exc:
                    self.fail(f"{tool_name}({argument}=…) crashed on an argument an agent composed "
                              f"rather than refusing it: {type(exc).__name__}: {exc}")
                except Exception:
                    pass          # a refusal naming the argument is the answer
                # `roster.CALL` is only read here to prove the two classes share one source
                self.assertIn(tool_name, set(roster.CALL) | set(self.CREATE_CALL))


class TestEveryProjectionSaysWhatItCouldNotRead(unittest.TestCase):
    """v0.25 — the projection every fresh agent loads was the one surface with no such line.

    On one hostile ledger the three surfaces gave three accounts of one file: `ledger_summary`
    reported the pins and the nonconformances, the map showed a banner, and the region generated
    into the user's `AGENTS.md` listed the readable pins and said nothing at all — the shortest
    list, in the one file every host loads unprompted. A projection that silently drops what it
    could not read tells an agent there is less here than there is.

    The roster is DERIVED from `tools.py` itself: a function that takes a `ledger` and ANSWERS
    `written` has produced a surface a reader will open. Nothing is listed, so a third projection
    arrives under this gate — and the derivation is the answer rather than the signature, because
    `instructions_diff` also takes a `ledger` and a `root` and writes nothing at all.
    """

    @staticmethod
    def _projections():
        tree, ast = _ast_tools()
        out = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = [a.arg for a in node.args.args]
            if "ledger" not in names:
                continue
            answers_written = any(
                isinstance(k, ast.Constant) and k.value == "written"
                for ret in ast.walk(node) if isinstance(ret, ast.Return)
                for d in ast.walk(ret) if isinstance(d, ast.Dict) for k in d.keys if k is not None)
            if not answers_written:
                continue
            key = "out" if "out" in names else "root"
            out.append((node.name, getattr(tools, node.name), key))
        return out

    def test_the_roster_is_derived_and_holds_both_projections(self):
        names = {n for n, _f, _k in self._projections()}
        self.assertEqual(names, {"render_map", "generate_instructions"},
                         "a tool that takes a ledger and writes a file is a projection, and every "
                         "one of them owes a reader this line")

    def test_every_projection_names_the_rules_the_file_breaks(self):
        from ledger import nonconforming
        from shape_corpus import worst_ledger
        data = worst_ledger()
        report = nonconforming(data)
        self.assertGreater(len(report), 10, "the corpus stopped producing a hostile file")
        for name, fn, kind in self._projections():
            with self.subTest(projection=name):
                tmp = tempfile.mkdtemp()
                path = os.path.join(tmp, "ledger.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                target = os.path.join(tmp, "map.html") if kind == "out" else tmp
                fn(path, target)
                chunks = []
                for root, _d, files in os.walk(tmp):
                    for f in files:
                        if f == "ledger.json":
                            continue
                        with open(os.path.join(root, f), encoding="utf-8") as fh:
                            chunks.append(fh.read())
                produced = "\n".join(chunks)
                missing = [rule for rule in report if rule not in produced]
                self.assertEqual(missing, [],
                                 f"{name} produced a surface that never mentions {missing} — one "
                                 f"ledger, and this surface's account of it is shorter than "
                                 f"`ledger_summary`'s")


class TestARenderFailureNeverBreaksTheWriteThatTriggeredIt(unittest.TestCase):
    """v0.25 — `_refresh_live_maps`' docstring said *"a render failure must never break the ledger
    write that triggered it"* and its handler caught `(OSError, ValueError)`.

    Not `AttributeError`, `TypeError` or `KeyError` — which are the failure classes this whole
    round is about. So a ledger the renderer chokes on would have taken down a write that had
    already succeeded and been persisted: the pin is on disk, the tool returns `isError`, and the
    agent is told its write failed and does it again.

    The rule is the docstring's own, so the gate is the docstring's: whatever the projection
    raises, the write stands."""

    def test_the_write_stands_when_the_projection_raises(self):
        import map as M
        tmp = tempfile.mkdtemp()
        ledger = os.path.join(tmp, "ledger.json")
        out = os.path.join(tmp, "map.html")
        pin = tools.ledger_add_pin(ledger, kind="defect", title="double charge", severity="high",
                                   confidence="extracted",
                                   provenance=[{"source": "recon", "detail": "x"}])["pin_id"]
        tools.render_map(ledger, out, live=True)
        original = M.render_file

        def exploding(*_a, **_kw):
            raise AttributeError("'str' object has no attribute 'get'")

        M.render_file = exploding
        try:
            tools.ledger_label_failure(ledger, pin, failure_class="untested_path",
                                       detail="it came back", phase="production")
        finally:
            M.render_file = original
        with open(ledger, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertTrue([e for e in data["decision_log"] if str(e.get("id")).startswith("fal_")],
                        "the write was rolled back by a render that has nothing to do with it")

    def test_a_marker_this_runtime_did_not_write_does_not_break_the_write(self):
        """The same rule one line up: the marker is read with `.get`, and a marker holding a JSON
        list met it."""
        tmp = tempfile.mkdtemp()
        ledger = os.path.join(tmp, "ledger.json")
        out = os.path.join(tmp, "map.html")
        pin = tools.ledger_add_pin(ledger, kind="defect", title="t", severity="low",
                                   confidence="extracted",
                                   provenance=[{"source": "recon", "detail": "x"}])["pin_id"]
        tools.render_map(ledger, out, live=True)
        marker = tools._livemap_marker(ledger)
        for content in ('["not an object"]', '"not an object"', "{}", "not json at all"):
            with self.subTest(marker=content):
                marker.write_text(content, encoding="utf-8")
                tools.ledger_label_failure(ledger, pin, failure_class="untested_path",
                                           detail="d", phase="production")


class TestAForkWhoseBranchesArriveAsOneTokenIsRefused(unittest.TestCase):
    """`_validate_question` closes this at composition. A ledger can still be hand-edited, so the
    election door refuses rather than picking one of the two meanings — which is what it did before:
    the freeform arm won, and the free text was recorded as the outcome of a fork that never offered
    it, on whichever rung the caller claimed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "ledger.json")
        led = Ledger(self.ledger)
        pin = led.add_pin(kind="ambiguity", title="which reading holds?", severity="low",
                          confidence="inferred",
                          provenance=[{"source": "static", "detail": "two readings"}],
                          question={"prompt": "which?", "allow_freeform": True,
                                    "options": [{"id": "keep", "label": "keep it"}]})
        # Hand-edited past the composition gate — the only way this pin can exist.
        pin["question"]["options"].append({"id": "freeform", "label": "some other route"})
        led.save()
        self.pin_id = pin["id"]

    def test_the_door_refuses_and_the_pin_stays_open(self):
        with self.assertRaises(ValueError) as caught:
            tools.record_decision(self.ledger, self.pin_id, "freeform", "r", "f",
                                  human_answer="in my own words")
        self.assertIn("two different outcomes", str(caught.exception))
        self.assertEqual(Ledger(self.ledger).pin(self.pin_id)["state"], "needs_input")

    def test_the_other_option_on_the_same_pin_still_elects(self):
        """The refusal is about the colliding token, not about the pin."""
        out = tools.record_decision(self.ledger, self.pin_id, "keep", "r", "f",
                                    human_answer="keep it")
        self.assertEqual(out["state"], "decided")


if __name__ == "__main__":
    unittest.main()
