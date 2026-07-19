"""Tests for runtime/tours.py — the dependency-ordered guided tour (understand mode).

Pins the teaching contract: entry points are what nothing imports, the walk is entry-first, steps
are grouped by layer in first-reached order, and the whole thing is deterministic and LLM-free.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import tours  # noqa: E402


def sample_graph() -> dict:
    """app (root) → api/svc → db/models: a clean 3-layer chain with one leaf class."""
    return {
        "graph": {"built_at_commit": "abc1234"},
        "nodes": [
            {"id": "file:app.py", "type": "file", "name": "app.py",
             "source_file": "app.py", "layer": "root", "language": "python", "start_line": 1},
            {"id": "file:api/svc.py", "type": "file", "name": "svc.py",
             "source_file": "api/svc.py", "layer": "api", "language": "python", "start_line": 1},
            {"id": "file:db/models.py", "type": "file", "name": "models.py",
             "source_file": "db/models.py", "layer": "db", "language": "python", "start_line": 1},
        ],
        "links": [
            {"source": "file:app.py", "target": "file:api/svc.py",
             "type": "imports", "confidence": "extracted"},
            {"source": "file:api/svc.py", "target": "file:db/models.py",
             "type": "imports", "confidence": "extracted"},
        ],
    }


class TestTour(unittest.TestCase):
    def setUp(self):
        self.tour = tours.build_tour(sample_graph())

    def test_entry_point_is_the_unimported_file(self):
        self.assertEqual(self.tour["entry_points"][0], "app.py")

    def test_steps_grouped_by_layer_in_dependency_order(self):
        self.assertEqual([s["layer"] for s in self.tour["steps"]], ["root", "api", "db"])
        self.assertEqual([s["order"] for s in self.tour["steps"]], [0, 1, 2])
        self.assertEqual(self.tour["steps"][0]["files"], ["app.py"])
        self.assertEqual(self.tour["steps"][2]["files"], ["db/models.py"])

    def test_stats(self):
        self.assertEqual(self.tour["stats"]["files"], 3)
        self.assertEqual(self.tour["stats"]["layers"], 3)

    def test_deterministic(self):
        import json
        self.assertEqual(json.dumps(self.tour), json.dumps(tours.build_tour(sample_graph())))

    def test_empty_graph(self):
        t = tours.build_tour({"nodes": [], "links": []})
        self.assertEqual(t["steps"], [])
        self.assertEqual(t["stats"]["files"], 0)

    def test_cyclic_still_has_entry(self):
        # a 2-file import cycle has no in_degree-0 root; the tour must still start somewhere
        g = {
            "nodes": [
                {"id": "file:a.py", "type": "file", "source_file": "a.py", "layer": "root"},
                {"id": "file:b.py", "type": "file", "source_file": "b.py", "layer": "root"},
            ],
            "links": [
                {"source": "file:a.py", "target": "file:b.py", "type": "imports"},
                {"source": "file:b.py", "target": "file:a.py", "type": "imports"},
            ],
        }
        t = tours.build_tour(g)
        self.assertTrue(t["entry_points"])
        self.assertEqual(t["stats"]["files"], 2)


if __name__ == "__main__":
    unittest.main()
