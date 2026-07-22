"""Tests for runtime/challenger.py — the deterministic slice of the v0.6 oracle red-team.

Pins the two mechanizable challenge classes (unfalsifiable, ignored_fanout) and the invariant
that the challenger only reopens — it never commits a DecisionEvent.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import challenger  # noqa: E402
from ledger import Ledger  # noqa: E402


def fresh() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


def acceptance_pin(led, verify, title="outcome"):
    return led.add_pin(
        kind="acceptance_criterion", title=title, severity="high", confidence="inferred",
        provenance=[{"source": "frame", "detail": "outcome"}],
        as_is={"built": None},
        to_be={"statement": "a user can do X", "verify": verify},
        question={"prompt": "in scope?", "options": [{"id": "in", "label": "yes"}],
                  "allow_freeform": True})


class TestUnfalsifiable(unittest.TestCase):
    def test_vague_but_present_verify_is_left_to_judgment(self):
        # A present-but-vague verify ("feels solid") is NOT flagged by the deterministic slice —
        # that is a judgment call for the agent-driven unfalsifiable challenge. Keyword-sniffing
        # here would be the guessing this package forbids (and "fast" hides inside "breakfast").
        led = fresh()
        pin = acceptance_pin(led, verify="auth should feel solid")
        led.decide(pin["id"], "in", "elected", "flip")
        proposals = challenger.run(led)
        self.assertEqual(proposals, [])
        self.assertEqual(led.pin(pin["id"])["state"], "decided")       # untouched by the slice

    def test_testable_verify_is_not_challenged(self):
        led = fresh()
        pin = acceptance_pin(led, verify="e2e: POST /bookings on a free slot -> 201")
        led.decide(pin["id"], "in", "elected", "flip")
        proposals = challenger.run(led)
        self.assertEqual(proposals, [])
        self.assertEqual(led.pin(pin["id"])["state"], "decided")       # untouched

    def test_empty_verify_is_challenged(self):
        led = fresh()
        pin = acceptance_pin(led, verify="")
        led.decide(pin["id"], "in", "elected", "flip")
        self.assertEqual(len(challenger.run(led)), 1)


class TestIgnoredFanout(unittest.TestCase):
    def test_high_fanout_defaulted_is_challenged(self):
        led = fresh()
        root = acceptance_pin(led, verify="e2e: real check", title="root")
        # two dependents make root high-fan-out
        for i in range(2):
            led.add_pin(kind="open_decision", title=f"dep{i}", severity="medium",
                        confidence="inferred", provenance=[{"source": "catalog", "detail": "x"}],
                        as_is={"givens": [], "built": None}, depends_on=[root["id"]])
        root["resolution_mode"] = "proposed_default"   # silently defaulted despite fan-out
        led.decide(root["id"], "in", "defaulted", "flip")
        proposals = challenger.run(led)
        classes = {p["class"] for p in proposals}
        self.assertIn("ignored_fanout", classes)

    def test_high_fanout_properly_asked_is_not_challenged_for_fanout(self):
        led = fresh()
        root = acceptance_pin(led, verify="e2e: real check", title="root")
        for i in range(2):
            led.add_pin(kind="open_decision", title=f"dep{i}", severity="medium",
                        confidence="inferred", provenance=[{"source": "catalog", "detail": "x"}],
                        as_is={"givens": [], "built": None}, depends_on=[root["id"]])
        root["resolution_mode"] = "asked"
        led.decide(root["id"], "in", "properly asked", "flip")
        classes = {p["class"] for p in challenger.run(led)}
        self.assertNotIn("ignored_fanout", classes)


class TestNeutrality(unittest.TestCase):
    def test_challenger_never_writes_a_decision_event(self):
        led = fresh()
        pin = acceptance_pin(led, verify="")   # empty verify: the deterministic unfalsifiable case
        led.decide(pin["id"], "in", "elected", "flip")
        before = len([e for e in led.data["decision_log"] if e["id"].startswith("ev_")])
        challenger.run(led)
        after = len([e for e in led.data["decision_log"] if e["id"].startswith("ev_")])
        self.assertEqual(before, after)                                 # no new decisions
        self.assertTrue(any(e["id"].startswith("chl_") for e in led.data["decision_log"]))

    def test_dry_run_reports_without_reopening(self):
        led = fresh()
        pin = acceptance_pin(led, verify="")   # empty verify: the deterministic unfalsifiable case
        led.decide(pin["id"], "in", "elected", "flip")
        proposals = challenger.run(led, apply=False)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(led.pin(pin["id"])["state"], "decided")        # not reopened


if __name__ == "__main__":
    unittest.main()
