"""Tests for runtime/explain.py — the explain-a-node drill-down (understand mode).

Pins: target resolution (id · path · path:symbol) never guesses, the neighborhood is assembled from
the graph, the real source is read when a root is given, and a URL is never a node.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import explain  # noqa: E402


def sample_graph() -> dict:
    return {
        "nodes": [
            {"id": "file:api/svc.py", "type": "file", "name": "svc.py",
             "source_file": "api/svc.py", "layer": "api", "start_line": 1},
            {"id": "sym:api/svc.py:login", "type": "function", "name": "login",
             "source_file": "api/svc.py", "layer": "api", "start_line": 1, "end_line": 2},
            {"id": "sym:db/models.py:User", "type": "class", "name": "User",
             "source_file": "db/models.py", "layer": "db", "start_line": 1, "end_line": 2},
        ],
        "links": [
            {"source": "file:api/svc.py", "target": "sym:api/svc.py:login", "type": "contains"},
            {"source": "sym:api/svc.py:login", "target": "sym:db/models.py:User", "type": "calls"},
        ],
    }


class TestResolve(unittest.TestCase):
    def setUp(self):
        import graph as graphmod
        self.g = graphmod.Graph(sample_graph())

    def test_by_node_id(self):
        self.assertEqual(explain.resolve_target(self.g, "sym:api/svc.py:login"),
                         "sym:api/svc.py:login")

    def test_by_path(self):
        self.assertEqual(explain.resolve_target(self.g, "api/svc.py"), "file:api/svc.py")

    def test_by_path_symbol(self):
        self.assertEqual(explain.resolve_target(self.g, "api/svc.py:login"),
                         "sym:api/svc.py:login")

    def test_url_is_never_a_node(self):
        self.assertIsNone(explain.resolve_target(self.g, "http://example.com/x.py"))

    def test_unresolvable(self):
        self.assertIsNone(explain.resolve_target(self.g, "nope/missing.py:ghost"))


class TestExplain(unittest.TestCase):
    def test_neighborhood(self):
        ctx = explain.explain(sample_graph(), "api/svc.py:login")
        self.assertTrue(ctx["found"])
        self.assertEqual(ctx["node"]["type"], "function")
        # login calls User (forward), is contained by svc.py (reverse)
        self.assertTrue(any("User" in x or "db/models.py" in x
                            for x in ctx["neighborhood"]["depends_on"]))
        self.assertTrue(any("svc.py" in x for x in ctx["neighborhood"]["depended_on_by"]))
        self.assertEqual(len(ctx["checklist"]), 5)

    def test_contains_children_for_a_file(self):
        ctx = explain.explain(sample_graph(), "api/svc.py")
        self.assertIn("login", ctx["neighborhood"]["contains"])

    def test_not_found(self):
        ctx = explain.explain(sample_graph(), "does/not/exist.py")
        self.assertFalse(ctx["found"])
        self.assertIn("checklist", ctx)

    def test_reads_real_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "api").mkdir()
            (root / "api" / "svc.py").write_text("def login():\n    return 1\n", encoding="utf-8")
            ctx = explain.explain(sample_graph(), "api/svc.py:login", root=str(root))
            self.assertIsNotNone(ctx["source"])
            self.assertIn("def login", ctx["source"]["text"])


if __name__ == "__main__":
    unittest.main()
