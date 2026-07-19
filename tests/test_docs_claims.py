"""Tests for runtime/docs_claims.py — docs-as-claims, the deterministic floor (study item C1).

Pins: claims + their code refs are extracted from markdown (fenced code ignored), refs resolve
against the graph, a dangling ref becomes a CANDIDATE pin (inferred, doc_claim, to_be null) — never
an assertion. Deterministic.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import docs_claims as dc  # noqa: E402

DOC = """\
# Auth

- The `login` function handles authentication.
- See `getUserProfile` in `src/legacy.py` for the old flow.
- Plain prose with no code references at all.

```python
this `ignored` reference is inside a fence
```
"""


def graph() -> dict:
    return {
        "nodes": [
            {"id": "file:api/auth.py", "type": "file", "source_file": "api/auth.py"},
            {"id": "sym:api/auth.py:login", "type": "function", "name": "login",
             "source_file": "api/auth.py"},
        ],
        "links": [],
    }


class TestExtract(unittest.TestCase):
    def test_only_claims_with_code_refs(self):
        claims = dc.extract_claims(DOC, "README.md")
        texts = [c["text"] for c in claims]
        self.assertEqual(len(claims), 2)   # heading + the prose-only bullet are skipped
        self.assertTrue(any("login" in t for t in texts))
        self.assertTrue(any("getUserProfile" in t for t in texts))

    def test_fenced_code_is_ignored(self):
        for c in dc.extract_claims(DOC, "README.md"):
            self.assertNotIn("ignored", c["refs"]["identifiers"])


class TestCheckAndPins(unittest.TestCase):
    def setUp(self):
        self.checked = dc.check_claims(dc.extract_claims(DOC, "README.md"), graph())

    def test_grounded_vs_dangling(self):
        by_ref = {}
        for c in self.checked:
            by_ref.update({r: "grounded" for r in c["grounded"]})
            by_ref.update({r: "dangling" for r in c["dangling"]})
        self.assertEqual(by_ref.get("login"), "grounded")
        self.assertEqual(by_ref.get("getUserProfile"), "dangling")
        self.assertEqual(by_ref.get("src/legacy.py"), "dangling")

    def test_candidate_pin_is_a_candidate_not_an_assertion(self):
        pins = dc.candidate_pins(self.checked)
        self.assertEqual(len(pins), 1)
        p = pins[0]
        self.assertEqual(p["kind"], "contract_mismatch")
        self.assertEqual(p["provenance"], "doc_claim")
        self.assertEqual(p["confidence"], "inferred")   # never 'extracted' — the discipline
        self.assertIsNone(p["to_be"])                    # the interview decides, not the runtime

    def test_grounded_claim_makes_no_pin(self):
        grounded_only = [c for c in self.checked if not c["dangling"]]
        self.assertEqual(dc.candidate_pins(grounded_only), [])


class TestAnalyze(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pathlib.Path(d) / "README.md"
            doc.write_text(DOC, encoding="utf-8")
            res = dc.analyze([str(doc)], graph())
            self.assertEqual(res["stats"]["candidates"], 1)
            self.assertEqual(res["stats"]["claims"], 2)


if __name__ == "__main__":
    unittest.main()
