"""Tests for runtime/fingerprint.py — incremental signature fingerprints + change classifier.

Pins the value that makes re-audit cheap: a formatting / internal-logic change is COSMETIC (no
signature change) and a signature change is STRUCTURAL, the whole-tree verdict is right, and the
store-wipeout guard holds. Stdlib-only; deterministic (commit injected).
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import fingerprint as fp  # noqa: E402


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    def fp(self, rel: str, text: str) -> dict:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return fp.file_fingerprint(self.root, rel)


class TestFileFingerprint(_Tmp):
    def test_python_signature(self):
        f = self.fp("m.py", "import os\n\n\ndef greet(name, count=1):\n    return name * count\n"
                            "\n\nclass A:\n    def m(self):\n        return 1\n")
        self.assertTrue(f["has_structural_analysis"])
        sig = f["signature"]
        self.assertEqual([x["name"] for x in sig["functions"]], ["greet"])
        self.assertEqual(sig["functions"][0]["params"], ["name", "count"])
        self.assertEqual([c["name"] for c in sig["classes"]], ["A"])
        self.assertIn("os", sig["imports"])

    def test_non_python_is_content_only(self):
        f = self.fp("styles.ts", "export const x = 1;\n")
        self.assertFalse(f["has_structural_analysis"])
        self.assertIsNone(f["signature"])


class TestCompare(_Tmp):
    def test_identical_is_none(self):
        a = self.fp("m.py", "def f(a, b):\n    return a + b\n")
        self.assertEqual(fp.compare(a, dict(a)), fp.NONE)

    def test_reformat_is_cosmetic(self):
        a = self.fp("m.py", "def f(a, b):\n    return a + b\n")
        b = self.fp("m.py", "def f(a, b):\n    # sum them\n    return a  +  b\n")  # same signature
        self.assertEqual(fp.compare(a, b), fp.COSMETIC)

    def test_added_param_is_structural(self):
        a = self.fp("m.py", "def f(a, b):\n    return a\n")
        b = self.fp("m.py", "def f(a, b, c):\n    return a\n")
        self.assertEqual(fp.compare(a, b), fp.STRUCTURAL)

    def test_added_method_is_structural(self):
        a = self.fp("m.py", "class A:\n    def x(self):\n        return 1\n")
        b = self.fp("m.py", "class A:\n    def x(self):\n        return 1\n    def y(self):\n        return 2\n")
        self.assertEqual(fp.compare(a, b), fp.STRUCTURAL)

    def test_changed_import_is_structural(self):
        a = self.fp("m.py", "import os\n\n\ndef f():\n    return 1\n")
        b = self.fp("m.py", "import sys\n\n\ndef f():\n    return 1\n")
        self.assertEqual(fp.compare(a, b), fp.STRUCTURAL)

    def test_non_python_change_is_structural(self):
        a = self.fp("a.ts", "export const x = 1;\n")
        b = self.fp("a.ts", "export const x = 2;\n")
        self.assertEqual(fp.compare(a, b), fp.STRUCTURAL)  # conservative: no structural analysis

    def test_new_and_deleted(self):
        a = self.fp("m.py", "def f():\n    return 1\n")
        self.assertEqual(fp.compare(None, a), fp.NEW)
        self.assertEqual(fp.compare(a, None), fp.DELETED)


class TestClassifyUpdate(unittest.TestCase):
    def test_skip_when_nothing_structural(self):
        v = fp.classify_update({"a.py": fp.NONE, "b.py": fp.COSMETIC}, total_files=2)
        self.assertEqual(v["update"], "SKIP")

    def test_partial(self):
        v = fp.classify_update({"a.py": fp.STRUCTURAL, "b.py": fp.NONE}, total_files=10)
        self.assertEqual(v["update"], "PARTIAL")
        self.assertEqual(v["structural"], ["a.py"])

    def test_architecture_on_new_top_dir(self):
        v = fp.classify_update({"newmod/x.py": fp.NEW}, total_files=20)
        self.assertEqual(v["update"], "ARCHITECTURE")
        self.assertIn("newmod", v["directories_touched"])

    def test_full_on_big_ratio(self):
        changes = {f"f{i}.py": fp.STRUCTURAL for i in range(6)}
        v = fp.classify_update(changes, total_files=6)  # 100% structural
        self.assertEqual(v["update"], "FULL")


class TestStoreAndGuards(_Tmp):
    def test_store_and_diff_roundtrip(self):
        (self.root / "a.py").write_text("def f(a):\n    return a\n", encoding="utf-8")
        s1 = fp.store(self.root, commit="c1")
        self.assertEqual(s1["built_at_commit"], "c1")
        # reformat a.py (cosmetic) + add a new file (new)
        (self.root / "a.py").write_text("def f(a):\n    return  a  # x\n", encoding="utf-8")
        (self.root / "b.py").write_text("def g():\n    return 1\n", encoding="utf-8")
        s2 = fp.store(self.root, commit="c2")
        changes = fp.diff_stores(s1, s2)
        self.assertEqual(changes["a.py"], fp.COSMETIC)
        self.assertEqual(changes["b.py"], fp.NEW)

    def test_deterministic(self):
        (self.root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        import json
        self.assertEqual(json.dumps(fp.store(self.root, commit="x")),
                         json.dumps(fp.store(self.root, commit="x")))

    def test_save_guard_refuses_empty_over_nonempty(self):
        path = self.root / "fingerprints.json"
        self.assertTrue(fp.save_store({"version": 1, "files": {"a.py": {}}}, path))
        # a bug hands us an empty store — the guard must refuse to wipe the baseline
        self.assertFalse(fp.save_store({"version": 1, "files": {}}, path))
        self.assertIn("a.py", fp.load_store(path)["files"])  # baseline intact


if __name__ == "__main__":
    unittest.main()
