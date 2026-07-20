"""Tests for runtime/query.py — the graph query surface (understand mode).

Pins: weighted ranking (a name hit outranks a path hit), 1-hop neighborhood expansion, and stable
ordering. Retrieval is a pure function of the graph — deterministic, no LLM.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import query  # noqa: E402


def sample_graph() -> dict:
    return {
        "nodes": [
            {"id": "file:api/auth.py", "type": "file", "name": "auth.py",
             "source_file": "api/auth.py", "layer": "api"},
            {"id": "sym:api/auth.py:login", "type": "function", "name": "login",
             "source_file": "api/auth.py", "layer": "api", "start_line": 3, "end_line": 6,
             "summary": "handle auth login", "tags": ["auth", "session"]},
            {"id": "sym:db/models.py:User", "type": "class", "name": "User",
             "source_file": "db/models.py", "layer": "db", "start_line": 1, "end_line": 2},
        ],
        "links": [
            {"source": "file:api/auth.py", "target": "sym:api/auth.py:login", "type": "contains"},
            {"source": "sym:api/auth.py:login", "target": "sym:db/models.py:User", "type": "calls"},
        ],
    }


class TestQuery(unittest.TestCase):
    def test_tag_and_summary_match(self):
        res = query.search(sample_graph(), "auth")
        self.assertTrue(res["results"])
        # login (tag+summary) and auth.py (path) both match; login should rank first
        self.assertEqual(res["results"][0]["name"], "login")

    def test_name_hit_outranks_path_hit(self):
        res = query.search(sample_graph(), "user")
        self.assertEqual(res["results"][0]["name"], "User")  # name weight 4 > path weight 2

    def test_neighborhood_expansion(self):
        res = query.search(sample_graph(), "login")
        top = res["results"][0]
        self.assertIn("neighbors", top)
        # login calls User (forward) and is contained by auth.py (reverse)
        self.assertTrue(any("User" in x or "db/models.py" in x for x in top["neighbors"]["depends_on"]))
        self.assertTrue(any("auth.py" in x for x in top["neighbors"]["depended_on_by"]))

    def test_empty_and_nomatch(self):
        self.assertEqual(query.search(sample_graph(), "")["results"], [])
        self.assertEqual(query.search(sample_graph(), "zzzznomatch")["total_matched"], 0)

    def test_deterministic(self):
        import json
        a = query.search(sample_graph(), "auth")
        b = query.search(sample_graph(), "auth")
        self.assertEqual(json.dumps(a), json.dumps(b))

    def test_no_expand(self):
        res = query.search(sample_graph(), "login", expand=False)
        self.assertNotIn("neighbors", res["results"][0])


if __name__ == "__main__":
    unittest.main()
