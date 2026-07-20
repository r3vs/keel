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
        findings = drift.get("findings", drift) if isinstance(drift, dict) else drift
        self.assertFalse(findings, f"generated layers must round-trip to zero drift, got: {findings}")

    def test_generate_layers_can_restrict_to_a_subset(self):
        contract = os.path.join(FIXTURES, "step0", "contract.json")
        gen = tools.generate_layers(contract, os.path.join(self.tmp, "sub"), layers=["ddl"])
        self.assertEqual(list(gen["written"]), ["ddl"])


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


if __name__ == "__main__":
    unittest.main()
