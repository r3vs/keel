"""Tests for generator-level false-positive discipline — the layer above FpGate
(Block 4 of docs/design/sota-alignment.md). Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import generators  # noqa: E402


def judged(reg: dict, gen: str, confirmed: int, refuted: int) -> None:
    for _ in range(confirmed):
        generators.observe(reg, gen, "confirmed")
    for _ in range(refuted):
        generators.observe(reg, gen, "refuted")


class TestPrecision(unittest.TestCase):
    def test_one_of_one_is_not_a_hundred_percent(self):
        """Below the declared sample floor there is no verdict — a provisional number gets quoted."""
        reg = generators.new_registry()
        judged(reg, "tool:rule", confirmed=1, refuted=0)
        self.assertIsNone(generators.precision(reg, "tool:rule"))
        self.assertEqual(generators._verdict(reg, "tool:rule")["verdict"], "unproven")

    def test_precision_is_counted_outcomes_not_an_estimate(self):
        reg = generators.new_registry()
        judged(reg, "tool:rule", confirmed=1, refuted=3)
        self.assertEqual(generators.precision(reg, "tool:rule"), 0.25)

    def test_silence_never_counts_as_confirmation(self):
        """Treating 'nobody complained' as evidence is the self-certifying loop this repo rejects."""
        reg = generators.new_registry()
        for _ in range(10):
            generators.observe(reg, "tool:rule", "pending")
        self.assertIsNone(generators.precision(reg, "tool:rule"))


class TestScreening(unittest.TestCase):
    def _finding(self, gen: str, file: str = "a.py", message: str = "m") -> dict:
        tool, rule = gen.split(":")
        return {"tool": tool, "rule_id": rule, "file": file, "message": message}

    def test_a_repeatedly_wrong_rule_is_muted(self):
        reg = generators.new_registry()
        judged(reg, "tool:bad", confirmed=1, refuted=5)
        out = generators.screen(reg, [self._finding("tool:bad")])
        self.assertEqual(out["surfaced"], [])
        self.assertEqual(len(out["muted"]), 1)

    def test_muting_is_loud_and_carries_the_number_that_caused_it(self):
        """A signal that vanishes silently is worse than a noisy one."""
        reg = generators.new_registry()
        judged(reg, "tool:bad", confirmed=1, refuted=5)
        out = generators.screen(reg, [self._finding("tool:bad")])
        self.assertLess(out["muted"][0]["precision"], 0.5)
        self.assertIn("below the declared bar", out["muted"][0]["why"])

    def test_muting_reverses_itself_through_its_own_carrier(self):
        reg = generators.new_registry()
        judged(reg, "tool:bad", confirmed=1, refuted=3)
        self.assertEqual(generators._verdict(reg, "tool:bad")["verdict"], "muted")
        judged(reg, "tool:bad", confirmed=4, refuted=0)
        self.assertEqual(generators._verdict(reg, "tool:bad")["verdict"], "trusted")

    def test_a_recently_refuted_rule_sits_out(self):
        reg = generators.new_registry()
        judged(reg, "tool:ok", confirmed=4, refuted=1)
        self.assertTrue(generators.cooling_down(reg, "tool:ok"))
        reg["runs"] += 5
        self.assertFalse(generators.cooling_down(reg, "tool:ok"))

    def test_the_same_root_cause_under_two_rule_ids_is_a_near_duplicate(self):
        reg = generators.new_registry()
        out = generators.screen(reg, [
            self._finding("a:r1", file="pay.py", message="possible sql injection here"),
            self._finding("b:r2", file="pay.py", message="possible sql injection here"),
        ])
        self.assertEqual(len(out["near_duplicates"]), 1)

    def test_nothing_is_ever_deleted(self):
        reg = generators.new_registry()
        judged(reg, "tool:bad", confirmed=0, refuted=4)
        findings = [self._finding("tool:bad"), self._finding("tool:good", file="b.py")]
        out = generators.screen(reg, findings)
        total = sum(len(out[k]) for k in ("surfaced", "muted", "cooling", "near_duplicates"))
        self.assertEqual(total, len(findings))

    def test_the_two_determinism_levels_are_reported_apart(self):
        reg = generators.new_registry()
        out = generators.screen(reg, [])
        self.assertEqual(out["ratio_determinism"], "D0")     # counted outcomes
        self.assertEqual(out["verdict_determinism"], "D1")   # an unmeasured bar

    def test_the_policy_declares_itself_a_hypothesis(self):
        self.assertTrue(generators.new_registry()["policy"]["hypothesis"])


if __name__ == "__main__":
    unittest.main()
