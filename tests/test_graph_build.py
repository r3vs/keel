"""Tests for runtime/graph_build.py — the deterministic structural-graph backbone.

Pins the contract the study bought: structure is EXTRACTED by code (Python via stdlib `ast`), the
output is exactly the node-link shape graph.py consumes, imports resolve only when unambiguous
(no fabrication), and validate/repair drops dangling edges. Stdlib-only, so it runs in CI as-is.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import graph_build  # noqa: E402
import graph as graphmod  # noqa: E402


def _write_repo(root: pathlib.Path) -> None:
    (root / "api").mkdir()
    (root / "db").mkdir()
    (root / "app.py").write_text(
        "from api.service import Service\n\n\ndef main():\n    return Service().run()\n",
        encoding="utf-8")
    (root / "api" / "service.py").write_text(
        "from db.models import get_user\n\n\nclass Service:\n"
        "    def run(self):\n        return get_user()\n",
        encoding="utf-8")
    (root / "db" / "models.py").write_text(
        "class User:\n    pass\n\n\ndef get_user():\n    return User()\n",
        encoding="utf-8")


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        _write_repo(self.root)
        self.data = graph_build.build_graph(self.root, commit="deadbee")

    def tearDown(self):
        self.tmp.cleanup()

    def _ids(self, typ):
        return {n["id"] for n in self.data["nodes"] if n["type"] == typ}

    def _edges(self, typ):
        return {(e["source"], e["target"]) for e in self.data["links"] if e["type"] == typ}

    def test_file_nodes_and_layers(self):
        files = {n["source_file"]: n for n in self.data["nodes"] if n["type"] == "file"}
        self.assertEqual(set(files), {"app.py", "api/service.py", "db/models.py"})
        self.assertEqual(files["app.py"]["layer"], "root")
        self.assertEqual(files["api/service.py"]["layer"], "api")
        self.assertEqual(files["db/models.py"]["layer"], "db")
        self.assertTrue(all(n["confidence"] == "extracted" for n in self.data["nodes"]))

    def test_symbols_extracted(self):
        names = {n["name"] for n in self.data["nodes"] if n["type"] in ("function", "class", "method")}
        self.assertIn("main", names)
        self.assertIn("Service", names)
        self.assertIn("Service.run", names)      # method carries its qualname
        self.assertIn("User", names)
        self.assertIn("get_user", names)

    def test_imports_resolve_unambiguously(self):
        imports = self._edges("imports")
        self.assertIn(("file:app.py", "file:api/service.py"), imports)
        self.assertIn(("file:api/service.py", "file:db/models.py"), imports)
        # no import to a non-existent internal file, and no self-import
        for s, t in imports:
            self.assertIn(t, self._ids("file"))
            self.assertNotEqual(s, t)

    def test_contains_and_calls(self):
        # resolve symbol ids by (file, name) so the test is not coupled to exact line numbers
        def sym(file, name):
            hits = [n["id"] for n in self.data["nodes"]
                    if n.get("source_file") == file and n.get("name") == name]
            self.assertEqual(len(hits), 1, f"{name} in {file}: {hits}")
            return hits[0]

        contains = self._edges("contains")
        self.assertIn(("file:db/models.py", sym("db/models.py", "get_user")), contains)
        self.assertIn(("file:db/models.py", sym("db/models.py", "User")), contains)
        # get_user() calls User() — intra-file, resolvable by name → a calls edge
        self.assertIn((sym("db/models.py", "get_user"), sym("db/models.py", "User")),
                      self._edges("calls"))

    def test_deterministic(self):
        again = graph_build.build_graph(self.root, commit="deadbee")
        self.assertEqual(json.dumps(self.data), json.dumps(again))

    def test_built_at_commit_and_graphpy_roundtrip(self):
        self.assertEqual(self.data["graph"]["built_at_commit"], "deadbee")
        g = graphmod.Graph(self.data)  # graph.py must consume it with no adapter
        importers = g.blast_radius("file:db/models.py", max_depth=2, edge_types=["imports"])
        self.assertIn("file:api/service.py", importers)
        self.assertIn("file:app.py", importers)  # transitive at depth 2


class TestValidateRepair(unittest.TestCase):
    def test_drops_broken_and_reports(self):
        dirty = {
            "nodes": [
                {"id": "a"}, {"id": "a"},              # duplicate
                {"name": "noid"},                       # no id
                {"id": "b", "confidence": "weird"},     # bad confidence
            ],
            "links": [
                {"source": "a", "target": "b", "type": "Imports"},   # kept, lowercased
                {"source": "a", "target": "ghost", "type": "calls"},  # dangling target
                {"source": "a"},                                       # no target
            ],
        }
        clean, issues = graph_build.validate_repair(dirty)
        self.assertEqual({n["id"] for n in clean["nodes"]}, {"a", "b"})
        self.assertEqual(len(clean["links"]), 1)
        self.assertEqual(clean["links"][0], {"source": "a", "target": "b",
                                             "type": "imports", "confidence": "extracted"})
        cats = {i["category"] for i in issues}
        self.assertEqual(cats, {"node.duplicate_id", "node.no_id",
                                "node.confidence", "edge.dangling", "edge.no_endpoint"})

    def test_referential_integrity_holds_on_real_build(self):
        # a real build must already be clean: no dangling edges, unique ids
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write_repo(root)
            data = graph_build.build_graph(root)
            _clean, issues = graph_build.validate_repair(data)
            self.assertEqual(issues, [], f"a fresh build should be clean, got {issues}")


class TestLayerOf(unittest.TestCase):
    def test_strips_generic_containers(self):
        self.assertEqual(graph_build.layer_of("src/api/users.py"), "api")
        self.assertEqual(graph_build.layer_of("packages/core/x.ts"), "core")
        self.assertEqual(graph_build.layer_of("frontend/pages/home.tsx"), "frontend")
        self.assertEqual(graph_build.layer_of("main.py"), "root")
        self.assertEqual(graph_build.layer_of("src/main.py"), "root")


if __name__ == "__main__":
    unittest.main()
