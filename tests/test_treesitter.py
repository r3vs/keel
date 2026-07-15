"""Tests for runtime/treesitter_extract.py — the optional tree-sitter generalization.

Two layers, matching the design:
  - The stdlib-only contract holds ALWAYS (no tree-sitter needed): the default backend is regex,
    a bad backend name errors, and `backend="auto"` degrades to regex when tree-sitter is absent.
  - When tree-sitter IS installed, the adapters are drop-in: they reproduce the regex extractors'
    output byte-for-byte on the fixtures (so the drift-check is identical), generalize across a
    second, very different grammar (GraphQL), and recover multi-line fields the line parser drops.

The tree-sitter tests skip cleanly when the backend is not installed — CI's stdlib-only runtime
stays green either way (AGENTS.md: degrade gracefully, never hard-fail)."""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import shapes  # noqa: E402
import treesitter_extract as tse  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
HAVE_TS = tse.available()
skip_no_ts = unittest.skipUnless(HAVE_TS, "tree-sitter backend not installed")


class TestAlwaysOn(unittest.TestCase):
    """The stdlib-only guarantees — run with or without tree-sitter installed."""

    def test_available_is_bool(self):
        self.assertIsInstance(tse.available(), bool)

    def test_default_backend_is_regex_and_stdlib(self):
        # default path must not touch tree-sitter (the stdlib-only invariant)
        self.assertIsNone(shapes._try_treesitter("typescript", "x", "regex"))

    def test_bad_backend_name_errors(self):
        with self.assertRaises(ValueError):
            shapes._try_treesitter("typescript", "x", "nonsense")

    def test_registry_has_two_grammars(self):
        self.assertIn("typescript", tse.REGISTRY)
        self.assertIn("graphql", tse.REGISTRY)

    def test_auto_backend_matches_regex_on_fixture(self):
        # whether or not tree-sitter is present, backend="auto" yields the same shapes on the
        # aligned fixture — installed → via tree-sitter, absent → via regex fallback.
        auto = shapes.extract_typescript(FIXTURES / "step0" / "types.ts", backend="auto")
        regex = shapes.extract_typescript(FIXTURES / "step0" / "types.ts", backend="regex")
        self.assertEqual(auto, regex)


@skip_no_ts
class TestTypeScriptAdapter(unittest.TestCase):
    def test_matches_regex_extractor(self):
        src = (FIXTURES / "step0" / "types.ts").read_text(encoding="utf-8")
        ts = tse.extract_typescript(src)
        regex = shapes.extract_typescript(FIXTURES / "step0" / "types.ts")
        self.assertEqual(ts, regex)         # drop-in: identical descriptors, so drift is identical

    def test_enum_with_three_members_resolves(self):
        # regression: `a | b | c` parses as a nested union; the flatten must still find all values
        src = (FIXTURES / "step0" / "types.ts").read_text(encoding="utf-8")
        status = tse.extract_typescript(src)["Task"]["status"]
        self.assertEqual((status["type"], status["enum"]),
                         ("enum", ["todo", "in_progress", "done"]))

    def test_recovers_multiline_field_regex_drops(self):
        multiline = ("export interface Widget {\n"
                     "  id: string; // uuid\n"
                     "  metadata: Record<\n    string,\n    unknown\n  > | null;\n"
                     "  count: number;\n}\n")
        ts = tse.extract_typescript(multiline)["Widget"]
        self.assertEqual(ts["metadata"]["type"], "json")     # tree-sitter recovers it
        self.assertTrue(ts["metadata"]["nullable"])
        fd, p = tempfile.mkstemp(suffix=".ts")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(multiline)
        regex = shapes.extract_typescript(p)["Widget"]
        self.assertNotIn("metadata", regex)                  # the line parser silently drops it

    def test_through_shapes_entrypoint(self):
        forced = shapes.extract_typescript(FIXTURES / "step0" / "types.ts", backend="treesitter")
        regex = shapes.extract_typescript(FIXTURES / "step0" / "types.ts", backend="regex")
        self.assertEqual(forced, regex)


@skip_no_ts
class TestGraphQLAdapter(unittest.TestCase):
    def test_matches_regex_extractor(self):
        src = (FIXTURES / "stacks" / "schema.graphql").read_text(encoding="utf-8")
        ts = tse.extract_graphql(src)
        regex = shapes.extract_graphql(FIXTURES / "stacks" / "schema.graphql")
        self.assertEqual(ts, regex)

    def test_nonnull_and_enum(self):
        src = (FIXTURES / "stacks" / "schema.graphql").read_text(encoding="utf-8")
        user = tse.extract_graphql(src)["User"]
        self.assertFalse(user["id"]["nullable"])            # ID! → non-null
        self.assertEqual(user["role"]["type"], "enum")      # Role enum resolved
        self.assertTrue(user["description"]["nullable"]) if "description" in user else None


@skip_no_ts
class TestGenericDispatch(unittest.TestCase):
    def test_extract_dispatch(self):
        src = (FIXTURES / "step0" / "types.ts").read_text(encoding="utf-8")
        self.assertIn("User", tse.extract(src, "typescript"))

    def test_unknown_lang_raises(self):
        with self.assertRaises(KeyError):
            tse.extract("x", "cobol")

    def test_drift_check_via_treesitter_is_clean(self):
        # the aligned step-0 stack still diffs clean when TS goes through tree-sitter
        findings = shapes.drift_check(
            str(FIXTURES / "step0" / "contract.json"),
            typescript=str(FIXTURES / "step0" / "types.ts"),
            backend="treesitter")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
