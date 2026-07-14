"""Tests for runtime/map.py — the visual map artifact.

The map is a user-facing deliverable, verified rendered in a browser during development (the pin
list, the three-column contract-diff with the disagreeing layer flagged, the linked interview
question, and the traffic-light all render from the inlined ledger, no console errors). These
tests pin the properties CI can guard without a browser: the output is one self-contained file
(data inlined, no external fetch), it is script-safe, and every pin's data reaches the page.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import map as mapmod  # noqa: E402
from ledger import Ledger  # noqa: E402


def demo_ledger() -> Ledger:
    led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
    led.add_pin(
        kind="contract_mismatch", title="role enum drift", severity="blocker",
        confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
        anchors=[{"node_id": None, "layer": "db", "role": "src", "loc": "m.sql:12"}],
        as_is={"db": "ENUM('admin','user')", "frontend": "'superadmin'",
               "disagreeing_layers": ["frontend"]},
        question={"prompt": "Intended role set?",
                  "options": [{"id": "a", "label": "DB is truth", "implication": "drop FE check"}],
                  "allow_freeform": True})
    return led


class TestSelfContained(unittest.TestCase):
    def setUp(self):
        self.html = mapmod.render(demo_ledger().data, title="demo")

    def test_is_a_full_html_document(self):
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("</html>", self.html)

    def test_no_external_resources(self):
        # a self-contained artifact opens offline: no external scripts/styles/fetch/img
        for pattern in (r'src\s*=\s*["\']https?:', r'href\s*=\s*["\']https?:',
                        r'@import', r'fetch\(["\']https?:'):
            self.assertIsNone(re.search(pattern, self.html),
                              f"external resource matched {pattern!r}")

    def test_ledger_data_is_inlined(self):
        self.assertIn("const LEDGER =", self.html)
        self.assertIn("role enum drift", self.html)          # pin title reached the page
        self.assertIn("disagreeing_layers", self.html)       # contract-diff data inlined

    def test_script_safe_closing_tags_escaped(self):
        # no raw </script> from data could break out of the inline script
        script_body = self.html.split("const LEDGER =", 1)[1]
        data_line = script_body.split("\n", 1)[0]
        self.assertNotIn("</script", data_line.lower())

    def test_empty_ledger_renders(self):
        empty = Ledger(os.path.join(tempfile.mkdtemp(), "l.json"))
        out = mapmod.render(empty.data)
        self.assertIn("<!doctype html>", out.lower())

    def test_render_file_writes_html(self):
        led = demo_ledger()
        led.save()
        out_path = os.path.join(tempfile.mkdtemp(), "map.html")
        result = mapmod.render_file(led.path, out_path)
        self.assertTrue(os.path.exists(result))
        self.assertIn("role enum drift", result.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
