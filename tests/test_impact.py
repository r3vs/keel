"""Tests for runtime/impact.py — the diff/impact overlay (study item C2).

Pins: changed files map to nodes, affected = reverse-reachable dependents, cross-layer + unmapped
drive risk, and an unmapped (new/renamed) file is surfaced as un-audited surface. Deterministic.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import impact  # noqa: E402


def sample_graph() -> dict:
    """app (root) → api/svc (api) → db/models (db); models declares a User class."""
    return {
        "graph": {"built_at_commit": "abc"},
        "nodes": [
            {"id": "file:app.py", "type": "file", "source_file": "app.py", "layer": "root"},
            {"id": "file:api/svc.py", "type": "file", "source_file": "api/svc.py", "layer": "api"},
            {"id": "file:db/models.py", "type": "file", "source_file": "db/models.py", "layer": "db"},
            {"id": "sym:db/models.py:User", "type": "class", "name": "User",
             "source_file": "db/models.py", "layer": "db"},
        ],
        "links": [
            {"source": "file:app.py", "target": "file:api/svc.py",
             "type": "imports", "confidence": "extracted"},
            {"source": "file:api/svc.py", "target": "file:db/models.py",
             "type": "imports", "confidence": "extracted"},
            {"source": "file:db/models.py", "target": "sym:db/models.py:User",
             "type": "contains", "confidence": "extracted"},
        ],
    }


class TestOverlay(unittest.TestCase):
    def test_changed_and_affected(self):
        ov = impact.overlay(sample_graph(), ["db/models.py"])
        self.assertIn("file:db/models.py", ov["changed_node_ids"])
        self.assertIn("sym:db/models.py:User", ov["changed_node_ids"])
        # svc imports models → svc is affected (a reverse-reachable dependent)
        self.assertIn("file:api/svc.py", ov["affected_node_ids"])
        self.assertNotIn("file:db/models.py", ov["affected_node_ids"])  # changed, not double-counted

    def test_cross_layer_is_high_risk(self):
        ov = impact.overlay(sample_graph(), ["db/models.py"])
        self.assertEqual(set(ov["affected_layers"]), {"db", "api"})
        self.assertEqual(ov["risk"]["level"], "high")  # >1 layer touched

    def test_depth_two_reaches_app(self):
        ov = impact.overlay(sample_graph(), ["db/models.py"], depth=2)
        self.assertIn("file:app.py", ov["affected_node_ids"])  # app → svc → models

    def test_unmapped_file(self):
        ov = impact.overlay(sample_graph(), ["brand/new.py"])
        self.assertEqual(ov["unmapped_files"], ["brand/new.py"])
        self.assertEqual(ov["changed_node_ids"], [])
        self.assertEqual(ov["risk"]["level"], "high")  # un-audited surface

    def test_no_change_is_low_risk(self):
        ov = impact.overlay(sample_graph(), [])
        self.assertEqual(ov["risk"]["level"], "low")
        self.assertEqual(ov["affected_node_ids"], [])

    def test_deterministic(self):
        import json
        a = impact.overlay(sample_graph(), ["db/models.py"])
        b = impact.overlay(sample_graph(), ["db/models.py"])
        self.assertEqual(json.dumps(a), json.dumps(b))


class TestGitHelper(unittest.TestCase):
    def test_outside_git_returns_empty_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            # a bare temp dir is not a git repo; the helper must degrade, not raise
            self.assertEqual(impact.changed_files_from_git(pathlib.Path(d), "HEAD~1"), [])


if __name__ == "__main__":
    unittest.main()
