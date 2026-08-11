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


def _wide(layer: str, paths: list) -> dict:
    """A graph of one layer holding `paths`, so a sub-grouping question has something to answer."""
    return {"graph": {}, "links": [],
            "nodes": [{"id": f"file:{p}", "type": "file", "name": p.split("/")[-1],
                       "source_file": p, "layer": layer, "language": "python"} for p in paths]}


class TestSubgrouping(unittest.TestCase):
    """D5 — a layer you have to scroll to read is a layer you do not read.

    The grouping is folder-LCP and the Louvain fallback the roadmap proposed is refused, for a
    reason that outlives the dependency question: a detected community has no name a reader can
    check, and this is the surface a human opens to find out what the code IS.
    """

    def _groups(self, layer, paths):
        view = graphmap.build_view(_wide(layer, paths))
        return {(g["name"], g["count"]) for g in view["layers"][0]["groups"]}

    def test_a_small_layer_is_left_alone(self):
        paths = [f"api/m{i}.py" for i in range(graphmap._SUBGROUP_AT)]
        self.assertEqual(self._groups("api", paths), set(),
                         "a heading over a list that fits on screen is noise")

    def test_a_wide_layer_splits_on_the_folder_the_repo_already_named(self):
        paths = ([f"src/api/routes/r{i}.py" for i in range(12)]
                 + [f"src/api/handlers/h{i}.py" for i in range(12)]
                 + [f"src/api/mw/m{i}.py" for i in range(6)])
        self.assertEqual(self._groups("api", paths),
                         {("handlers", 12), ("mw", 6), ("routes", 12)})

    def test_a_wide_layer_whose_folders_say_nothing_stays_flat(self):
        """One bucket is not a grouping. The honest answer to a flat directory of 40 files is that
        it is a flat directory of 40 files — inventing a split would be the un-nameable grouping."""
        paths = [f"src/flat/f{i}.py" for i in range(40)]
        self.assertEqual(self._groups("flat", paths), set())

    def test_the_groups_partition_the_layer(self):
        """Nothing is dropped, including the files sitting directly in the shared prefix — they are
        the `.` group, and a file that vanishes from the map is worse than a card that is long."""
        paths = ([f"src/api/routes/r{i}.py" for i in range(20)]
                 + [f"src/api/top{i}.py" for i in range(8)])
        view = graphmap.build_view(_wide("api", paths))
        layer = view["layers"][0]
        grouped = [f["id"] for g in layer["groups"] for f in g["files"]]
        self.assertEqual(sorted(grouped), sorted(f["id"] for f in layer["files"]))
        self.assertEqual(sum(g["count"] for g in layer["groups"]), layer["count"])
        self.assertIn(".", {g["name"] for g in layer["groups"]})

    def test_the_page_renders_one_row_markup_for_both_shapes(self):
        """The flat layer and the grouped layer share `row()`. Two copies would be two answers to
        what a file row is, and the search filter selects on the classes it sets."""
        html = graphmap.render(_wide("api", [f"src/api/x/{i}.py" for i in range(30)]
                                     + [f"src/api/y/{i}.py" for i in range(30)]))
        self.assertEqual(html.count("function row(f)"), 1)
        self.assertIn("ghead", html)
        self.assertIn("subgrouped", html)

    def test_the_threshold_is_declared_as_a_hypothesis(self):
        src = (pathlib.Path(__file__).resolve().parent.parent / "src" / "runtime"
               / "graphmap.py").read_text(encoding="utf-8").splitlines()
        at = next(i for i, line in enumerate(src) if line.startswith("_SUBGROUP_AT"))
        above = []
        for line in reversed(src[:at]):
            if not line.startswith("#"):
                break
            above.append(line)
        self.assertTrue(any("HYPOTHESIS" in line for line in above))


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
