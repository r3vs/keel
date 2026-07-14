"""Tests for runtime/findings.py — the mandatory false-positive gate (module-fp-check.md).

The gate is the module's whole value: no finding reaches the user without a CONFIRM/DOWNGRADE/DROP
verdict. These tests pin each of the five ordered checks and the survivor→pin mapping.
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import findings as F  # noqa: E402
from ledger import Ledger  # noqa: E402

FIX = pathlib.Path(__file__).parent / "fixtures" / "findings"


class TestNormalizers(unittest.TestCase):
    def test_sarif_extracts_and_maps_security_severity(self):
        stream = F.normalize_sarif(
            __import__("json").loads((FIX / "semgrep.sarif").read_text(encoding="utf-8")))
        self.assertEqual(len(stream), 4)
        sqli = [f for f in stream if f["rule_id"] == "python.sqli.raw"]
        self.assertTrue(all(f["severity"] == "high" for f in sqli))  # security-severity 8.5 → high
        weak = next(f for f in stream if f["rule_id"] == "python.weak-hash")
        self.assertEqual(weak["severity"], "low")                    # 3.0 → low
        self.assertEqual(weak["tool"], "semgrep")

    def test_osv_extracts_package_vulns(self):
        stream = F.normalize_osv(
            __import__("json").loads((FIX / "osv.json").read_text(encoding="utf-8")))
        self.assertEqual(len(stream), 1)
        self.assertEqual(stream[0]["tool"], "osv")
        self.assertIn("lodash", stream[0]["message"])

    def test_load_and_normalize_auto_detects_both(self):
        stream = F.load_and_normalize([str(FIX / "semgrep.sarif"), str(FIX / "osv.json")])
        self.assertEqual(len(stream), 5)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.stream = F.normalize_sarif(
            __import__("json").loads((FIX / "semgrep.sarif").read_text(encoding="utf-8")))

    def test_migration_safe_pattern_dropped_but_real_sqli_confirmed(self):
        gated = F.FpGate().run(self.stream)
        # the two real SQLi (users, orders) merge into ONE confirmed cluster with 2 anchors;
        # the migration instance is dropped by the safe-pattern, not merged in.
        sqli = [c for c in gated["confirmed"] if "sqli" in c["cluster_id"]]
        self.assertEqual(len(sqli), 1)
        self.assertEqual(sqli[0]["count"], 2)
        self.assertEqual({a["file"] for a in sqli[0]["anchors"]},
                         {"app/users.py", "app/orders.py"})
        dropped_files = {d["lead"]["file"] for d in gated["dropped"]}
        self.assertIn("db/migrations/003.py", dropped_files)

    def test_low_severity_single_signal_downgraded(self):
        gated = F.FpGate().run(self.stream)
        weak = [c for c in gated["downgraded"] if "weak-hash" in c["cluster_id"]]
        self.assertEqual(len(weak), 1)
        self.assertIn("single low-confidence", weak[0]["reason"])

    def test_reachability_oracle_downgrades_lone_dead_finding(self):
        # a lone finding whose file is unreachable downgrades via check 2 (before corroboration)
        gate = F.FpGate(reachable=lambda f: False if "legacy_unused" in f else None)
        gated = gate.run(self.stream)
        weak = next(c for c in gated["downgraded"] if "weak-hash" in c["cluster_id"])
        self.assertIn("unreachable", weak["reason"])

    def test_fully_unreachable_cluster_downgrades_none_confirmed(self):
        # both SQLi instances unreachable → the whole root-cause cluster downgrades (a root cause
        # live *anywhere* would confirm; here it is dead everywhere)
        gate = F.FpGate(reachable=lambda f: False if f.startswith("app/") else None)
        gated = gate.run(self.stream)
        self.assertEqual([c for c in gated["confirmed"] if "sqli" in c["cluster_id"]], [])
        self.assertEqual(len([c for c in gated["downgraded"] if "sqli" in c["cluster_id"]]), 1)

    def test_intentional_stub_dropped(self):
        gate = F.FpGate(intentional_stub=lambda f, l: f == "app/users.py")
        gated = gate.run(self.stream)
        dropped_files = {d["lead"]["file"] for d in gated["dropped"]}
        self.assertIn("app/users.py", dropped_files)

    def test_deterministic_finding_skips_gate(self):
        det = [F.finding("mypy", "mypy.assignment", "incompatible type", "medium",
                         "app/x.py", 3)]
        gated = F.FpGate(reachable=lambda f: False).run(det)  # even 'unreachable' can't drop it
        self.assertEqual(len(gated["confirmed"]), 1)
        self.assertIn("deterministic", gated["confirmed"][0]["reason"])

    def test_audit_log_shows_drops(self):
        gated = F.FpGate().run(self.stream)
        log = F.audit_log(gated)
        self.assertTrue(any("migrations" in e["example"] for e in log))


class TestToPins(unittest.TestCase):
    def test_survivors_become_defect_pins_with_clustered_anchors(self):
        stream = F.normalize_sarif(
            __import__("json").loads((FIX / "semgrep.sarif").read_text(encoding="utf-8")))
        gated = F.FpGate().run(stream)
        import tempfile
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        pins = F.to_pins(led, gated)
        self.assertTrue(pins)
        sqli_pin = next(p for p in pins if "sqli" in p["title"].lower())
        self.assertEqual(sqli_pin["kind"], "defect")
        self.assertEqual(sqli_pin["confidence"], "extracted")        # confirmed → extracted
        self.assertEqual(len(sqli_pin["anchors"]), 2)                # 2 instances, one pin
        self.assertEqual(sqli_pin["as_is"]["evidence"]["instances"], 2)

    def test_downgraded_pin_lowers_confidence(self):
        stream = F.normalize_sarif(
            __import__("json").loads((FIX / "semgrep.sarif").read_text(encoding="utf-8")))
        gated = F.FpGate().run(stream)
        import tempfile
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        F.to_pins(led, gated)
        weak = next(p for p in led.data["pins"] if "weak-hash" in p["title"])
        self.assertEqual(weak["confidence"], "inferred")             # downgraded → inferred


if __name__ == "__main__":
    unittest.main()
