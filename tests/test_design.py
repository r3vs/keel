"""Tests for runtime/design.py — the Impeccable detector, bound to the ledger.

Offline and deterministic: they never invoke the real `impeccable` (CI has no Node), so they pin the
things that are ours — the normalization of the detector's real JSON shape into pin-ready findings
(deterministic → confidence 'extracted' → skips fp-check), the deterministic split of a `design-system-*`
DESIGN.md violation into a `contract_mismatch` vs a universal tell into a `design_concern`, the advisory
flag, the `--scope`/`--viewport`/`--no-advisory` passthrough, and the coverage-gap degrade when the
detector cannot run (unchecked, never a false clean bill). Every row below was captured from a live
`impeccable detect --json` (v3.3.1) run, including one against a project carrying a DESIGN.md.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import design  # noqa: E402

# The real shape emitted by `impeccable detect --json` (v3.3.1), captured from a live run against a
# project WITH a DESIGN.md — so it mixes universal tells (low-contrast, overused-font) with
# DESIGN.md token-membership violations (design-system-*), exactly as the detector emits them.
SAMPLE = [
    {"antipattern": "low-contrast", "name": "Low contrast text",
     "description": "Text does not meet WCAG AA contrast requirements.",
     "severity": "warning", "category": "quality", "file": "ui/page.html", "line": 0,
     "snippet": "3.5:1 (need 4.5:1) — text #888888 on #ffffff"},
    {"antipattern": "design-system-font", "name": "Font outside DESIGN.md",
     "description": "A font is used that is not declared in DESIGN.md typography.",
     "severity": "warning", "category": "quality", "file": "ui/page.html", "line": 3,
     "snippet": "font-family: Inter is not declared in DESIGN.md typography"},
    {"antipattern": "design-system-color", "name": "Color outside DESIGN.md",
     "description": "A literal color is outside the DESIGN.md palette.",
     "severity": "advisory", "category": "quality", "file": "ui/page.html", "line": 3,
     "snippet": "Undocumented color #abcdef is outside DESIGN.md colors"},
    {"antipattern": "overused-font", "name": "Overused font",
     "description": "Inter/Roboto/... no longer feel distinctive.",
     "severity": "warning", "category": "slop", "file": "ui/page.html", "line": 3,
     "snippet": "Primary font: inter"},
]


class TestNormalize(unittest.TestCase):
    def test_maps_to_pin_ready_findings(self):
        out = design.normalize(SAMPLE)
        self.assertEqual(len(out), 4)
        f = out[0]
        self.assertEqual(f["check_id"], "impeccable/low-contrast")
        self.assertEqual(f["severity"], "medium")           # warning → medium
        self.assertEqual(f["detail"], "3.5:1 (need 4.5:1) — text #888888 on #ffffff")
        self.assertEqual(f["file"], "ui/page.html")
        self.assertEqual(f["source"], "impeccable")

    def test_design_system_hit_is_a_contract_mismatch(self):
        # a design-system-* id is a violation of the elected DESIGN.md contract → contract_mismatch,
        # decided by the id prefix (the carrier), never by judgment
        by_ap = {f["check_id"]: f for f in design.normalize(SAMPLE)}
        self.assertEqual(by_ap["impeccable/design-system-font"]["kind"], "contract_mismatch")
        self.assertEqual(by_ap["impeccable/design-system-color"]["kind"], "contract_mismatch")

    def test_universal_tell_is_a_design_concern(self):
        by_ap = {f["check_id"]: f for f in design.normalize(SAMPLE)}
        self.assertEqual(by_ap["impeccable/low-contrast"]["kind"], "design_concern")
        self.assertEqual(by_ap["impeccable/overused-font"]["kind"], "design_concern")

    def test_severity_advisory_string_is_low_priority_but_not_floored(self):
        # design-system-color carries severity:"advisory" (STRING) but NOT the boolean `advisory`
        # field. Impeccable's own CLI still fails on it, so it is a low-PRIORITY real finding — low
        # severity, and crucially NOT flagged non-blocking, or we'd silently demote a real DESIGN.md
        # contract violation out of the blocker path (the exact bug this asserts against).
        by_ap = {f["check_id"]: f for f in design.normalize(SAMPLE)}
        adv = by_ap["impeccable/design-system-color"]
        self.assertEqual(adv["severity"], "low")
        self.assertNotIn("advisory", adv)                   # the STRING is not the boolean floor
        self.assertEqual(adv["kind"], "contract_mismatch")  # still a real contract violation
        self.assertNotIn("advisory", by_ap["impeccable/low-contrast"])

    def test_advisory_boolean_flag_is_the_only_floor(self):
        # ONLY the boolean `advisory: true` (today: em-dash-overuse) is a genuine non-blocking floor —
        # surfaced, floored to low, flagged. The severity string alone never sets the flag.
        out = design.normalize([{"antipattern": "em-dash-overuse", "category": "slop",
                                 "severity": "warning", "advisory": True, "file": "x.md", "line": 1}])
        self.assertTrue(out[0].get("advisory"))
        self.assertEqual(out[0]["severity"], "low")

    def test_every_hit_is_a_fact_that_skips_fp_check(self):
        # the detector runs no model, so every finding is extracted-confidence and bypasses fp-check
        for f in design.normalize(SAMPLE):
            self.assertEqual(f["confidence"], "extracted")

    def test_tolerates_garbage_rows(self):
        out = design.normalize([None, "x", 3, {}])   # only the {} is a dict
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["check_id"], "impeccable/design")   # missing antipattern → 'design'


class TestScanArgv(unittest.TestCase):
    """The optional passthroughs reach impeccable's real flags, without shell interpolation."""

    def _run_capturing_argv(self, **kw):
        seen = {}

        class _Proc:
            stdout = "[]"

        def fake_run(argv, **_):
            seen["argv"] = argv
            return _Proc()

        with mock.patch.object(design, "_detect_cmd", return_value=["impeccable"]), \
             mock.patch.object(design.subprocess, "run", side_effect=fake_run):
            design.scan(["ui/"], **kw)
        return seen["argv"]

    def test_defaults_are_plain_detect_json(self):
        argv = self._run_capturing_argv()
        self.assertEqual(argv[:3], ["impeccable", "detect", "--json"])
        self.assertNotIn("--scope", argv)
        self.assertNotIn("--viewport", argv)
        self.assertNotIn("--no-advisory", argv)

    def test_scope_viewport_and_no_advisory_passthrough(self):
        argv = self._run_capturing_argv(scope=["type", "layout"], viewport="390x844", no_advisory=True)
        self.assertIn("--scope", argv)
        self.assertEqual(argv[argv.index("--scope") + 1], "type,layout")
        self.assertEqual(argv[argv.index("--viewport") + 1], "390x844")
        self.assertIn("--no-advisory", argv)


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
