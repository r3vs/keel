"""Tests for runtime/graph.py — deterministic graph anchoring + blast-radius (no heuristics).

The graph does exactly the two things the Phase-0 verdict leaves it — anchor a pin to a node_id
BY file:line, and blast-radius over the EXTRACTED spine — and nothing it is not (no field-level
correspondence, no name-matching, no reliance on INFERRED edges). These tests pin that posture:
resolution is loc-only and never fabricates, and blast-radius ignores INFERRED edges.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import graph as graphmod  # noqa: E402
from graph import Graph, _parse_loc, _same_commit, anchor_ledger  # noqa: E402


def sample_graph(built_at: str = "abc1234deadbeef") -> Graph:
    """A tiny NetworkX-shaped graph: a db table, its ORM model + api dto, and some dependents.

    Edges (source depends on target):
        model_user  --imports-->      table_users     (EXTRACTED)
        dto_user    --references-->    table_users     (EXTRACTED)
        module_db   --contains-->     table_users     (EXTRACTED)
        report_svc  --calls-->        model_user       (EXTRACTED)
        widget      --shares_data-->  table_users     (INFERRED)   <- must NOT count
    """
    data = {
        "directed": True, "multigraph": False,
        "graph": {"built_at_commit": built_at},
        "nodes": [
            {"id": "table_users", "type": "table", "name": "users",
             "source_file": "packages/db/schema/users.ts", "line": 12},
            {"id": "model_user", "type": "class", "name": "User",
             "source_file": "backend/models.py", "line": 30, "end_line": 40},
            {"id": "dto_user", "type": "interface", "name": "User",
             "source_file": "frontend/types.ts", "line": 5},
            {"id": "report_svc", "type": "function", "name": "build_report",
             "source_file": "backend/reports.py", "line": 8},
            {"id": "widget", "type": "component", "name": "UserWidget",
             "source_file": "frontend/UserWidget.tsx", "line": 40},
            {"id": "module_db", "type": "module", "name": "db",
             "source_file": "packages/db/schema/users.ts", "line": 1},
        ],
        "links": [
            {"source": "model_user", "target": "table_users", "type": "imports",
             "confidence": "EXTRACTED"},
            {"source": "dto_user", "target": "table_users", "type": "references",
             "confidence": "EXTRACTED"},
            {"source": "module_db", "target": "table_users", "type": "contains",
             "confidence": "EXTRACTED"},
            {"source": "report_svc", "target": "model_user", "type": "calls",
             "confidence": "EXTRACTED"},
            {"source": "widget", "target": "table_users", "type": "shares_data_with",
             "confidence": "INFERRED"},
        ],
    }
    return Graph(data)


class TestParseLoc(unittest.TestCase):
    def test_file_line(self):
        self.assertEqual(_parse_loc("a/b/c.ts:12"), ("a/b/c.ts", 12))

    def test_file_line_col_takes_line_not_col(self):
        self.assertEqual(_parse_loc("a/b/c.ts:12:5"), ("a/b/c.ts", 12))

    def test_windows_drive_letter_preserved(self):
        self.assertEqual(_parse_loc("C:/x/y.ts:30"), ("C:/x/y.ts", 30))
        self.assertEqual(_parse_loc("C:/x/y.ts:30:2"), ("C:/x/y.ts", 30))

    def test_backslashes_normalized(self):
        self.assertEqual(_parse_loc("a\\b\\c.ts:12"), ("a/b/c.ts", 12))

    def test_no_line(self):
        self.assertEqual(_parse_loc("a/b/c.ts"), ("a/b/c.ts", None))

    def test_dict_and_int(self):
        self.assertEqual(_parse_loc({"file": "f.py", "line": 9}), ("f.py", 9))
        self.assertEqual(_parse_loc(7), (None, 7))
        self.assertEqual(_parse_loc(None), (None, None))


class TestSameCommit(unittest.TestCase):
    def test_prefix_match(self):
        self.assertTrue(_same_commit("abc1234deadbeef", "abc1234"))
        self.assertTrue(_same_commit("abc1234", "abc1234deadbeef"))

    def test_mismatch_and_too_short(self):
        self.assertFalse(_same_commit("abc1234", "def5678"))
        self.assertFalse(_same_commit("abc12", "abc12"))     # < 7 chars: not a real sha
        self.assertFalse(_same_commit("", "abc1234"))


class TestResolution(unittest.TestCase):
    def setUp(self):
        self.g = sample_graph()

    def test_exact_loc(self):
        self.assertEqual(self.g.resolve({"loc": "backend/models.py:30"}), "model_user")

    def test_containment_by_declared_range(self):
        # line 35 falls inside model_user's declared [30, 40] range — deterministic containment
        self.assertEqual(self.g.resolve({"loc": "backend/models.py:35"}), "model_user")

    def test_no_containment_without_a_range_is_not_guessed(self):
        # table_users has a start line (12) but no end_line; line 20 is NOT nearest-matched
        self.assertIsNone(self.g.resolve({"loc": "packages/db/schema/users.ts:20"}))

    def test_never_fabricates(self):
        self.assertIsNone(self.g.resolve({"loc": "nowhere/x.py:1"}))     # unknown file
        self.assertIsNone(self.g.resolve({"loc": "backend/models.py"}))  # file only, no line
        self.assertIsNone(self.g.resolve({"entity": "User", "layer": "db"}))  # no name matching
        self.assertIsNone(self.g.resolve({}))


class TestBlastRadius(unittest.TestCase):
    def setUp(self):
        self.g = sample_graph()

    def test_direct_dependents_all_extracted_edges(self):
        # every EXTRACTED edge into the table counts (imports, references, contains) — no
        # editorial edge-type filter; the INFERRED shares_data edge does not
        self.assertEqual(set(self.g.blast_radius("table_users", max_depth=1)),
                         {"model_user", "dto_user", "module_db"})

    def test_transitive_depth(self):
        self.assertEqual(set(self.g.blast_radius("table_users", max_depth=2)),
                         {"model_user", "dto_user", "module_db", "report_svc"})

    def test_inferred_edge_excluded(self):
        # `widget` only reaches the table via an INFERRED edge → never counted at default conf
        self.assertNotIn("widget", self.g.blast_radius("table_users", max_depth=3))

    def test_inferred_included_only_when_explicitly_lowered(self):
        r = self.g.blast_radius("table_users", max_depth=1, min_conf="inferred")
        self.assertIn("widget", set(r))

    def test_edge_type_scope_is_opt_in(self):
        # the caller MAY scope by type; by default nothing is filtered
        only_imports = self.g.blast_radius("table_users", max_depth=1, edge_types={"imports"})
        self.assertEqual(set(only_imports), {"model_user"})

    def test_dependencies_forward(self):
        self.assertEqual(set(self.g.dependencies("report_svc", max_depth=2)),
                         {"model_user", "table_users"})


class TestAnchorLedger(unittest.TestCase):
    def _ledger(self):
        return {"version": "0.6", "pins": [{
            "id": "pin_0001", "kind": "contract_mismatch",
            "anchors": [
                {"node_id": None, "layer": "db", "role": "db_source",
                 "loc": "packages/db/schema/users.ts:12"},
                {"node_id": None, "layer": "client", "role": "consumer", "entity": "User"},
                {"node_id": None, "layer": "db", "loc": "nowhere.py:1"},   # unresolved
            ],
        }]}

    def test_enriches_only_loc_resolvable_anchors(self):
        led = self._ledger()
        report = anchor_ledger(led, sample_graph(), max_depth=2)
        anchors = led["pins"][0]["anchors"]
        self.assertEqual(anchors[0]["node_id"], "table_users")   # resolved by exact loc
        self.assertIsNone(anchors[1]["node_id"])                 # entity-only: never name-matched
        self.assertIsNone(anchors[2]["node_id"])                 # unknown file
        self.assertEqual(report["resolved"], 1)
        self.assertEqual(report["unresolved"], 2)

    def test_attaches_blast_radius(self):
        led = self._ledger()
        anchor_ledger(led, sample_graph(), max_depth=2)
        table_anchor = led["pins"][0]["anchors"][0]
        self.assertIn("blast_radius", table_anchor)
        # model_user, dto_user, module_db (depth1) + report_svc (depth2)
        self.assertEqual(table_anchor["blast_radius"]["count"], 4)

    def test_never_overwrites_existing_node_id(self):
        led = self._ledger()
        led["pins"][0]["anchors"][0]["node_id"] = "hand_set"
        anchor_ledger(led, sample_graph())
        self.assertEqual(led["pins"][0]["anchors"][0]["node_id"], "hand_set")

    def test_stale_graph_refuses_to_write(self):
        led = self._ledger()
        report = anchor_ledger(led, sample_graph(built_at="0000000stale"),
                               head="abc1234deadbeef")
        self.assertTrue(report["stale"])
        self.assertTrue(report["skipped_stale"])
        self.assertIsNone(led["pins"][0]["anchors"][0]["node_id"])   # nothing written

    def test_current_graph_proceeds_with_prefix_head(self):
        led = self._ledger()
        report = anchor_ledger(led, sample_graph(built_at="abc1234deadbeef"),
                               head="abc1234")            # short HEAD, prefix of built_at
        self.assertFalse(report["stale"])
        self.assertEqual(led["pins"][0]["anchors"][0]["node_id"], "table_users")

    def test_force_overrides_staleness(self):
        led = self._ledger()
        report = anchor_ledger(led, sample_graph(built_at="0000000stale"),
                               head="abc1234deadbeef", force=True)
        self.assertTrue(report["stale"])
        self.assertFalse(report["skipped_stale"])
        self.assertEqual(led["pins"][0]["anchors"][0]["node_id"], "table_users")


class TestEdgesKeyAndMetadata(unittest.TestCase):
    def test_edges_key_alias_and_top_level_commit(self):
        # some dumps use "edges" instead of "links", and a top-level built_at_commit
        g = Graph({
            "built_at_commit": "feed1234beef",
            "nodes": [{"id": "a", "name": "A", "source_file": "a.py", "line": 1},
                      {"id": "b", "name": "B", "source_file": "b.py", "line": 1}],
            "edges": [{"source": "b", "target": "a", "type": "calls", "confidence": "extracted"}],
        })
        self.assertEqual(g.built_at_commit, "feed1234beef")
        self.assertEqual(g.blast_radius("a", max_depth=1), ["b"])


class TestCLI(unittest.TestCase):
    def test_dry_run_reports_without_writing(self):
        d = tempfile.mkdtemp()
        gpath, lpath = os.path.join(d, "graph.json"), os.path.join(d, "ledger.json")
        with open(gpath, "w", encoding="utf-8") as fh:
            json.dump(sample_graph().raw, fh)
        with open(lpath, "w", encoding="utf-8") as fh:
            json.dump({"version": "0.6", "pins": [{"id": "pin_0001", "anchors":
                      [{"node_id": None, "loc": "packages/db/schema/users.ts:12"}]}]}, fh)
        before = pathlib.Path(lpath).read_text(encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = graphmod.main(["--graph", gpath, "--ledger", lpath, "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(pathlib.Path(lpath).read_text(encoding="utf-8"), before)  # untouched

    def test_stale_exit_code(self):
        d = tempfile.mkdtemp()
        gpath, lpath = os.path.join(d, "graph.json"), os.path.join(d, "ledger.json")
        with open(gpath, "w", encoding="utf-8") as fh:
            json.dump(sample_graph(built_at="0000000stale").raw, fh)
        with open(lpath, "w", encoding="utf-8") as fh:
            json.dump({"version": "0.6", "pins": []}, fh)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = graphmod.main(["--graph", gpath, "--ledger", lpath, "--head", "abc1234deadbeef"])
        self.assertEqual(rc, 2)   # refused: stale


if __name__ == "__main__":
    unittest.main()
