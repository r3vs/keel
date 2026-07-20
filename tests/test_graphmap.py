"""Tests for runtime/graphmap.py — the layered-lens graph map (study item D).

Mirrors test_map.py's guardable properties (CI has no browser): one self-contained file (data inlined,
no external fetch), script-safe, and the view model is right (layers grouped, coupling counted). The
interactive rendering itself is verified in a real Chromium via Playwright during development.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import graphmap  # noqa: E402


def sample_graph() -> dict:
    return {
        "graph": {"built_at_commit": "abc1234"},
        "nodes": [
            {"id": "file:app.py", "type": "file", "name": "app.py", "source_file": "app.py",
             "layer": "root", "language": "python"},
            {"id": "file:api/svc.py", "type": "file", "name": "svc.py", "source_file": "api/svc.py",
             "layer": "api", "language": "python"},
            {"id": "file:db/models.py", "type": "file", "name": "models.py",
             "source_file": "db/models.py", "layer": "db", "language": "python"},
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


class TestView(unittest.TestCase):
    def test_layers_and_files(self):
        v = graphmap.build_view(sample_graph())
        names = [l["name"] for l in v["layers"]]
        self.assertEqual(names, ["api", "db", "root"])   # sorted
        db = next(l for l in v["layers"] if l["name"] == "db")
        self.assertEqual([f["name"] for f in db["files"]], ["models.py"])
        # the file carries its symbols + neighbourhood
        self.assertIn("User", db["files"][0]["symbols"])

    def test_inter_layer_coupling(self):
        v = graphmap.build_view(sample_graph())
        pairs = {(c["from"], c["to"]): c["count"] for c in v["coupling"]}
        self.assertEqual(pairs.get(("root", "api")), 1)
        self.assertEqual(pairs.get(("api", "db")), 1)

    def test_tour_folded_in(self):
        tour = {"steps": [{"order": 0, "title": "Layer: root", "layer": "root", "files": ["app.py"]}]}
        v = graphmap.build_view(sample_graph(), tour)
        self.assertEqual(v["tour"][0]["title"], "Layer: root")


class TestRender(unittest.TestCase):
    def setUp(self):
        self.html = graphmap.render(sample_graph(), title="t")

    def test_full_self_contained_document(self):
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("</html>", self.html)
        for pattern in (r'(src|href)\s*=\s*["\']https?:', r'@import', r'fetch\('):
            self.assertIsNone(re.search(pattern, self.html), f"external resource: {pattern}")

    def test_data_inlined_and_reaches_page(self):
        self.assertIn("const VIEW =", self.html)
        self.assertIn("models.py", self.html)
        self.assertIn('"coupling"', self.html)

    def test_script_safe(self):
        data_line = next(l for l in self.html.splitlines() if l.startswith("const VIEW ="))
        self.assertNotIn("</", data_line)

    def test_empty_graph_renders(self):
        out = graphmap.render({"nodes": [], "links": []})
        self.assertIn("<!doctype html>", out.lower())

    def test_render_file_writes(self):
        with tempfile.TemporaryDirectory() as d:
            g = pathlib.Path(d) / "graph.json"
            g.write_text(json.dumps(sample_graph()), encoding="utf-8")
            out = graphmap.render_file(g, pathlib.Path(d) / "map.html")
            self.assertTrue(out.exists())
            self.assertIn("models.py", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
