"""Tests for runtime/spend.py — token/cost telemetry over the session transcript.

Deterministic and machine-independent: these build a synthetic transcript (never read the developer's
real ~/.claude store), so the numbers are fixed. They pin the two rules the module exists to keep —
tokens are exact and always summed, cost is computed only against a supplied sheet (unpriced models
degrade to tokens-only, they don't vanish) — plus the unused-MCP optimize finding and the
unchecked-not-zero degrade.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import spend  # noqa: E402


def _write(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _session_tree():
    """A main session (opus + sonnet turns, one MCP-attributed) plus one subagent (opus)."""
    tmp = tempfile.mkdtemp()
    main = os.path.join(tmp, "session.jsonl")
    _write(main, [
        {"type": "assistant", "timestamp": "2026-07-22T10:00:00Z",
         "message": {"model": "claude-opus-4-8",
                     "usage": {"input_tokens": 100, "output_tokens": 50,
                               "cache_creation_input_tokens": 10, "cache_read_input_tokens": 5}}},
        {"type": "assistant", "timestamp": "2026-07-22T11:00:00Z", "attributionMcpServer": "context7",
         "message": {"model": "claude-sonnet-5", "usage": {"input_tokens": 200, "output_tokens": 20}}},
        {"type": "user", "timestamp": "2026-07-22T10:05:00Z"},          # not a usage row
    ])
    with open(main, "a", encoding="utf-8") as fh:
        fh.write("{ this is not valid json\n")                          # malformed tail, never fatal
    subdir = os.path.join(tmp, "session", "subagents")
    os.makedirs(subdir)
    _write(os.path.join(subdir, "agent-x.jsonl"), [
        {"type": "assistant", "agentId": "agent-x", "timestamp": "2026-07-22T10:10:00Z",
         "message": {"model": "claude-opus-4-8", "usage": {"input_tokens": 300, "output_tokens": 100}}},
    ])
    return main


class TestTokenCarrier(unittest.TestCase):
    def setUp(self):
        self.session = _session_tree()

    def test_totals_sum_every_bucket_across_main_and_subagents(self):
        agg = spend.report_session(self.session)
        self.assertEqual(agg["totals"]["input_tokens"], 600)    # 100 + 200 + 300
        self.assertEqual(agg["totals"]["output_tokens"], 170)   # 50 + 20 + 100
        self.assertEqual(agg["totals"]["cache_creation_input_tokens"], 10)
        self.assertEqual(agg["rows"], 3)                        # user + malformed excluded

    def test_per_agent_separates_main_from_the_subagent(self):
        agg = spend.report_session(self.session)
        self.assertEqual(agg["by_agent"]["main"]["input_tokens"], 300)     # 100 + 200
        self.assertEqual(agg["by_agent"]["agent-x"]["input_tokens"], 300)  # the subagent file

    def test_per_model_splits_opus_and_sonnet(self):
        agg = spend.report_session(self.session)
        self.assertEqual(agg["by_model"]["claude-opus-4-8"]["output_tokens"], 150)   # 50 + 100
        self.assertEqual(agg["by_model"]["claude-sonnet-5"]["input_tokens"], 200)


class TestCostIsNeverBakedIn(unittest.TestCase):
    def setUp(self):
        self.session = _session_tree()

    def test_no_sheet_means_no_cost_key(self):
        agg = spend.report_session(self.session)
        self.assertNotIn("cost_usd", agg)   # tokens only, by default

    def test_priced_model_costs_and_unpriced_degrades_to_tokens_only(self):
        pricing = {"claude-opus-4-8": {"input": 10, "output": 30, "cache_write": 12, "cache_read": 1}}
        agg = spend.report_session(self.session, pricing=pricing)
        self.assertIsNotNone(agg["cost_usd"])
        self.assertGreater(agg["cost_usd"], 0)
        # sonnet has no entry — it must be reported, not silently counted as free
        self.assertIn("claude-sonnet-5", agg["unpriced_models"])


class TestOptimizeAndDegrade(unittest.TestCase):
    def test_unused_mcp_servers_are_the_declared_minus_the_seen(self):
        session = _session_tree()
        agg = spend.report_session(session, declared_mcp=["context7", "deepwiki", "cognee"])
        # only context7 attributed a call; the other two are loaded every session, used never
        self.assertEqual(agg["optimize"]["unused_mcp_servers"], ["cognee", "deepwiki"])

    def test_project_report_is_unchecked_not_zero_when_no_store(self):
        agg = spend.report_project(tempfile.mkdtemp(), home=tempfile.mkdtemp())
        self.assertTrue(agg.get("unchecked"))     # a missing host store is unchecked, never 0 spend
        self.assertNotIn("totals", agg)

    def test_slug_folds_separators_and_colon(self):
        slug = spend.claude_code_slug(os.path.join("some", "dir"))
        for ch in (":", "/", "\\"):
            self.assertNotIn(ch, slug)


if __name__ == "__main__":
    unittest.main()
