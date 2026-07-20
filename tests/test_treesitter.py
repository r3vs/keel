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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import shapes  # noqa: E402
import treesitter_extract as tse  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
HAVE_TS = tse.available()
skip_no_ts = unittest.skipUnless(HAVE_TS, "tree-sitter backend not installed")


class TestAlwaysOn(unittest.TestCase):
    """The stdlib-only guarantees — run with or without tree-sitter installed."""

    def test_available_is_bool(self):
        self.assertIsInstance(tse.available(), bool)

    def test_regex_backend_forces_the_stdlib_parser(self):
        # backend="regex" is the explicit opt-out (the always-available stdlib fallback);
        # it never touches tree-sitter, whatever the default is.
        self.assertIsNone(shapes._try_treesitter("typescript", "x", "regex"))

    def test_bad_backend_name_errors(self):
        with self.assertRaises(ValueError):
            shapes._try_treesitter("typescript", "x", "nonsense")

    def test_registry_has_the_stack_specs(self):
        self.assertIn("typescript", tse.REGISTRY)
        self.assertIn("graphql", tse.REGISTRY)
        self.assertIn("sql", tse._CUSTOM)

    def test_default_and_auto_and_regex_agree_on_fixture(self):
        # the default is now tree-sitter-preferred ("auto"); on the aligned fixture it must equal
        # the explicit regex path (byte-identical drop-in) whether tree-sitter is present or not.
        default = shapes.extract_typescript(FIXTURES / "step0" / "types.ts")
        auto = shapes.extract_typescript(FIXTURES / "step0" / "types.ts", backend="auto")
        regex = shapes.extract_typescript(FIXTURES / "step0" / "types.ts", backend="regex")
        self.assertEqual(default, auto)
        self.assertEqual(auto, regex)


@skip_no_ts
class TestOneGrammarFailingIsNotTheBackendFailing(unittest.TestCase):
    """`available()` answered a question that stopped implying the one callers actually ask.

    It used to be that "tree-sitter imports" meant "every grammar is here": the language pack
    compiled all ~165 into the wheel. It now ships a ~2 MB wheel and downloads each grammar from
    GitHub releases on first use. So the import survives offline, air-gapped, behind a proxy, or on
    a checksum mismatch — and the grammar does not arrive.

    The gap predates that change. The no-arg probe returns True on the mere presence of
    `tree_sitter_typescript`, after which extracting **Go** raised straight out of `backend="auto"`
    — the mode whose docstring promises to "transparently fall back to the stdlib parser". A
    promise the code does not keep is the exact bug this package exists to find, so it does not get
    to live in this package.

    These run with or without tree-sitter installed: the failure is injected, never depended on.
    """

    def setUp(self):
        self._real = tse._language
        tse._LANG_CACHE.clear()

    def tearDown(self):
        tse._language = self._real
        tse._LANG_CACHE.clear()

    def _break(self, exc=None):
        def boom(grammar):
            raise exc or tse.TreeSitterUnavailable("download failed: connection refused")
        tse._language = boom

    def test_probing_a_language_loads_that_language(self):
        # The only honest way to know a grammar is usable is to use it. A probe that just checks
        # for the library is the thing that lied.
        self._break()
        self.assertFalse(tse.available("go"))

    def test_auto_degrades_when_one_grammar_cannot_load(self):
        self._break()
        self.assertIsNone(shapes._try_treesitter("go", "type U struct { ID string }", "auto"))

    def test_explicit_treesitter_backend_still_fails_loudly(self):
        # Degrading is right for `auto` and wrong here: this caller asked for tree-sitter by name,
        # and silently handing back stdlib output would answer a question they did not ask.
        self._break()
        with self.assertRaises(RuntimeError):
            shapes._try_treesitter("go", "type U struct { ID string }", "treesitter")

    def test_a_failure_is_attempted_once_not_once_per_file(self):
        # Not an optimization. A rescue walks thousands of files; re-attempting a network fetch per
        # file turns a clean fallback into what looks like a hang.
        attempts = []

        def counting(grammar):
            attempts.append(grammar)
            raise RuntimeError("download failed: connection refused")

        tse._LANG_CACHE.clear()
        tse._language = self._real
        orig = tse.__dict__.get("_grammar_for")
        try:
            import tree_sitter_language_pack as pack
        except Exception:
            self.skipTest("language pack not installed; the negative cache needs a real load path")
        real_get = pack.get_language
        pack.get_language = counting
        try:
            for _ in range(5):
                tse.available("go")
            self.assertEqual(len(attempts), 1, "the failure must be cached, not re-attempted")
        finally:
            pack.get_language = real_get
            self.assertIs(orig, tse.__dict__.get("_grammar_for"))

    def test_the_error_names_the_real_cause_not_the_last_one(self):
        # Collapsing to the fallback's error prints "No module named tree_sitter_go" when the truth
        # was a failed download — a misleading diagnosis on the very failure mode this survives.
        try:
            import tree_sitter_language_pack as pack
        except Exception:
            self.skipTest("language pack not installed")
        real_get = pack.get_language
        pack.get_language = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("download failed: connection refused"))
        try:
            tse._LANG_CACHE.clear()
            tse._language = self._real
            with self.assertRaises(tse.TreeSitterUnavailable) as caught:
                tse._language("go")
            self.assertIn("connection refused", str(caught.exception))
        finally:
            pack.get_language = real_get


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
        regex = shapes.extract_typescript(p, backend="regex")["Widget"]
        self.assertNotIn("metadata", regex)                  # the stdlib line parser silently drops it

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
class TestSqlExtractor(unittest.TestCase):
    def test_matches_regex_ddl_dropin(self):
        # byte-identical to the stdlib DDL parser on the fixture (incl. enums, FK, constraints)
        path = FIXTURES / "step0" / "001_initial.sql"
        ts = tse.extract(path.read_text(encoding="utf-8"), "sql")
        regex = shapes.extract_ddl(path, backend="regex")
        self.assertEqual(ts, regex)

    def test_real_postgres_forms_no_patches(self):
        # the grammar parses real Postgres natively — no IF-NOT-EXISTS / schema-prefix / multi-word
        # / numeric patches (the exact shapes that broke the regex on plastital_lca)
        sql = ("CREATE TABLE IF NOT EXISTS public.db_impatti (\n"
               "  id numeric PRIMARY KEY,\n"
               "  created_at timestamp with time zone,\n"
               "  descrizione character varying(255)\n);")
        t = tse.extract(sql, "sql")["db_impatti"]
        self.assertEqual(t["id"]["type"], "float")                 # numeric
        self.assertEqual(t["created_at"]["type"], "datetime")      # timestamp with time zone
        self.assertEqual(t["descrizione"]["type"], "string")       # character varying(255)
        self.assertEqual(t["descrizione"]["constraints"]["max_length"], 255)


@skip_no_ts
class TestBackendLanguageStacks(unittest.TestCase):
    """The generic engine covers backend struct/class stacks — each a declarative spec (query +
    type map + a nullability convention as DATA), not a new parser. Adding a stack = adding data."""

    def test_go_pointer_nullability_and_qualified_types(self):
        out = tse.extract("type User struct {\n\tID uuid.UUID\n\tEmail *string\n\tAge int\n}\n",
                          "go")["User"]
        self.assertEqual(out["ID"]["type"], "uuid")          # uuid.UUID (package-qualified)
        self.assertTrue(out["Email"]["nullable"])            # *string → pointer is nullable
        self.assertFalse(out["Age"]["nullable"])

    def test_java_primitive_vs_boxed_nullability(self):
        out = tse.extract("class User {\n  int age;\n  Integer score;\n  String name;\n}\n",
                          "java")["User"]
        self.assertFalse(out["age"]["nullable"])             # primitive int → non-null
        self.assertTrue(out["score"]["nullable"])            # boxed Integer → nullable
        self.assertTrue(out["name"]["nullable"])             # object reference → nullable

    def test_rust_option_nullability(self):
        out = tse.extract("struct User {\n  id: Uuid,\n  email: Option<String>,\n}\n",
                          "rust")["User"]
        self.assertEqual(out["id"]["type"], "uuid")
        self.assertTrue(out["email"]["nullable"])            # Option<String> → nullable

    def test_csharp_nullable_type(self):
        out = tse.extract("class User {\n  public Guid Id { get; set; }\n"
                          "  public int? Age { get; set; }\n}\n", "csharp")["User"]
        self.assertEqual(out["Id"]["type"], "uuid")          # Guid → uuid
        self.assertTrue(out["Age"]["nullable"])              # int? → nullable

    def test_registered_in_shapes_extractors(self):
        for lang in ("go", "java", "rust", "csharp"):
            self.assertIn(lang, shapes.EXTRACTORS)


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
