"""Tests for runtime/coverage.py — the coverage manifest that turns a silent 'tool did not run' into
a visible coverage-gap pin. The whole point: 'unchecked' must never read as 'clean'."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import coverage  # noqa: E402
from ledger import Ledger  # noqa: E402


def _sarif(tmp: str, *tool_names: str) -> str:
    p = os.path.join(tmp, "report.sarif")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"runs": [{"tool": {"driver": {"name": n}}, "results": []} for n in tool_names]}, fh)
    return p


class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_nothing_run_is_all_gaps_not_clean(self):
        r = coverage.report(["Python"], [])
        caps = {g["capability"] for g in r["gaps"]}
        self.assertIn("sast", caps)
        self.assertIn("type-check", caps)
        self.assertEqual(r["ran"], [])

    def test_a_tool_that_ran_closes_its_capability(self):
        r = coverage.report(["Python"], [_sarif(self.tmp, "semgrep")])
        caps = {g["capability"] for g in r["gaps"]}
        self.assertNotIn("sast", caps)      # semgrep covered it
        self.assertIn("secrets", caps)      # gitleaks still missing

    def test_capability_alternative_tool_counts(self):
        # type-check Python is satisfied by pyright OR mypy — running either is not a gap.
        gaps = {g["capability"] for g in coverage.report(["Python"], [_sarif(self.tmp, "pyright")])["gaps"]}
        self.assertNotIn("type-check", gaps)

    def test_absent_language_is_not_a_gap(self):
        # a Python-only repo must not be dinged for missing Rust/Go coverage.
        for g in coverage.report(["Python"], [])["gaps"]:
            self.assertNotIn("Rust", g["stacks"])
            self.assertNotIn("Go", g["stacks"])

    def test_security_and_types_are_high_severity(self):
        sev = {g["capability"]: g["severity"] for g in coverage.report(["Python"], [])["gaps"]}
        self.assertEqual(sev["sast"], "high")
        self.assertEqual(sev["secrets"], "high")
        self.assertEqual(sev["type-check"], "high")
        self.assertEqual(sev["dead-code"], "medium")

    def test_gaps_become_extracted_incompleteness_pins(self):
        led = Ledger(os.path.join(self.tmp, "ledger.json"))
        gaps = coverage.report(["Python"], [])["gaps"]
        pins = coverage.to_pins(led, gaps)
        self.assertEqual(len(pins), len(gaps))
        for p in pins:
            self.assertEqual(p["kind"], "incompleteness")
            self.assertEqual(p["kind_detail"], "coverage-gap")
            self.assertEqual(p["confidence"], "extracted")   # the absence is a fact, not a guess

    def test_osv_json_is_attributed_to_its_tool(self):
        p = os.path.join(self.tmp, "osv.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"results": []}, fh)
        self.assertIn("osv-scanner", coverage.ran_tools([p]))

    def test_a_malformed_report_did_not_run(self):
        p = os.path.join(self.tmp, "broken.sarif")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(coverage.ran_tools([p]), set())   # unreadable == did not run, never a phantom pass


if __name__ == "__main__":
    unittest.main()
