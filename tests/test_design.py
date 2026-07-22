"""Tests for runtime/design.py — the Impeccable detector, bound to the ledger.

Offline and deterministic: they never invoke the real `impeccable` (CI has no Node), so they pin the
two things that are ours — the normalization of the detector's real JSON shape into pin-ready findings
(deterministic → confidence 'extracted' → skips fp-check), and the coverage-gap degrade when the
detector cannot run (unchecked, never a false clean bill). The sample is the real 3.3.1 `detect --json`
schema.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import design  # noqa: E402

# The real shape emitted by `impeccable detect --json` (v3.3.1), captured from a live run.
SAMPLE = [
    {"antipattern": "low-contrast", "name": "Low contrast text",
     "description": "Text does not meet WCAG AA contrast requirements.",
     "severity": "warning", "category": "quality", "file": "ui/page.html", "line": 0,
     "snippet": "3.5:1 (need 4.5:1) — text #888888 on #ffffff"},
    {"antipattern": "overused-font", "name": "Overused font",
     "description": "Inter/Roboto/... no longer feel distinctive.",
     "severity": "warning", "category": "slop", "file": "ui/page.html", "line": 0,
     "snippet": "Primary font: inter"},
]


class TestNormalize(unittest.TestCase):
    def test_maps_to_pin_ready_findings(self):
        out = design.normalize(SAMPLE)
        self.assertEqual(len(out), 2)
        f = out[0]
        self.assertEqual(f["check_id"], "impeccable/low-contrast")
        self.assertEqual(f["kind"], "design_concern")
        self.assertEqual(f["severity"], "medium")           # warning → medium
        self.assertEqual(f["detail"], "3.5:1 (need 4.5:1) — text #888888 on #ffffff")
        self.assertEqual(f["file"], "ui/page.html")
        self.assertEqual(f["source"], "impeccable")

    def test_every_hit_is_a_fact_that_skips_fp_check(self):
        # the detector runs no model, so every finding is extracted-confidence and bypasses fp-check
        for f in design.normalize(SAMPLE):
            self.assertEqual(f["confidence"], "extracted")

    def test_tolerates_garbage_rows(self):
        out = design.normalize([None, "x", 3, {}])   # only the {} is a dict
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["check_id"], "impeccable/design")   # missing antipattern → 'design'


class TestDegrade(unittest.TestCase):
    def test_scan_is_unchecked_not_clean_when_detector_absent(self):
        with mock.patch.object(design, "_detect_cmd", return_value=None):
            self.assertFalse(design.available())
            out = design.scan(["ui/"])
            self.assertTrue(out.get("unchecked"))          # a finder that could not run is 'unchecked'
            self.assertNotIn("findings", out)              # never a false empty (clean) result

    def test_available_reflects_the_detector(self):
        with mock.patch.object(design, "_detect_cmd", return_value=["impeccable"]):
            self.assertTrue(design.available())


if __name__ == "__main__":
    unittest.main()
