"""Tests for learning-with-a-carrier (Block 5 of docs/design/sota-alignment.md): capture the
divergences the ledger already holds, and refuse to APPLY anything that is not a check.
Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import learning  # noqa: E402
from ledger import Ledger, LedgerError  # noqa: E402


def make_ledger() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


def pin_with_proposals(led: Ledger, recommended_id: str = "p1") -> dict:
    pin = led.add_pin(kind="open_decision", title="which cache?", severity="medium",
                      confidence="inferred", provenance=[{"source": "x", "detail": "y"}],
                      as_is={"built": None})
    led.add_proposals(pin["id"], [
        {"id": "p1", "summary": "redis", "recommended": recommended_id == "p1"},
        {"id": "p2", "summary": "in-process", "recommended": recommended_id == "p2"},
    ])
    return pin


class TestCapture(unittest.TestCase):
    def test_the_gap_between_recommended_and_elected_is_the_signal(self):
        led = make_ledger()
        pin = pin_with_proposals(led)
        led.decide(pin["id"], "p2", "cheaper to operate", "flip if load grows")
        div = learning.divergences(led)
        self.assertEqual(len(div["brainstorm_vs_election"]), 1)
        row = div["brainstorm_vs_election"][0]
        self.assertEqual((row["recommended"], row["elected"]), ("p1", "p2"))

    def test_agreement_is_not_a_divergence(self):
        led = make_ledger()
        pin = pin_with_proposals(led)
        led.decide(pin["id"], "p1", "agreed", "flip if load grows")
        self.assertEqual(learning.divergences(led)["brainstorm_vs_election"], [])

    def test_an_election_that_names_no_proposal_is_reported_not_scored(self):
        """Counting it as agreement would silently inflate the model's apparent hit rate."""
        led = make_ledger()
        pin = pin_with_proposals(led)
        led.decide(pin["id"], "something else entirely", "r", "f")
        div = learning.divergences(led)
        self.assertEqual(div["brainstorm_vs_election"], [])
        self.assertEqual(len(div["unmatched_elections"]), 1)

    def test_two_recommendations_are_refused_because_the_gap_becomes_uncomputable(self):
        led = make_ledger()
        pin = led.add_pin(kind="open_decision", title="t", severity="low", confidence="inferred",
                          provenance=[{"source": "x", "detail": "y"}], as_is={"built": None})
        with self.assertRaises(LedgerError):
            led.add_proposals(pin["id"], [
                {"id": "p1", "summary": "a", "recommended": True},
                {"id": "p2", "summary": "b", "recommended": True},
            ])

    def test_challenges_failures_and_reopens_all_count(self):
        led = make_ledger()
        pin = led.add_pin(kind="acceptance_criterion", title="t", severity="medium",
                          confidence="extracted", provenance=[{"source": "x", "detail": "y"}],
                          as_is={"built": None}, to_be={"statement": "s", "verify": "v"})
        led.decide(pin["id"], "o", "r", "f")
        led.challenge(pin["id"], "acceptance_criterion", "unsatisfiable", "cannot hold", "high",
                      upheld=True)
        led.label_failure(pin["id"], "untested_path", "nothing covered it", "review")
        led.reopen(pin["id"], "production disagreed")
        div = learning.divergences(led)
        self.assertEqual(len(div["upheld_challenges"]), 1)
        self.assertEqual(len(div["failures"]), 1)
        self.assertEqual(len(div["reopens"]), 1)

    def test_capture_is_a_read_and_says_so(self):
        self.assertEqual(learning.divergences(make_ledger())["determinism"], "D0")


class TestGraduation(unittest.TestCase):
    def _cand(self, **over) -> dict:
        c = {"id": "r1", "evidence": ["pin_0001"],
             "carrier": {"kind": "ast_grep", "expression": "$X.query($Y)"}}
        c.update(over)
        return c

    def test_a_rule_with_a_carrier_becomes_a_check(self):
        out = learning.graduate(self._cand())
        self.assertTrue(out["graduated"])
        self.assertEqual(out["state"], "check")
        self.assertEqual(out["determinism"], "D0")

    def test_a_belief_with_no_carrier_stays_a_proposal_and_is_never_applied(self):
        out = learning.graduate(self._cand(carrier={"kind": "note", "expression": "be careful"}))
        self.assertFalse(out["graduated"])
        self.assertEqual(out["state"], "proposal")

    def test_a_carrier_kind_with_no_expression_is_a_label(self):
        out = learning.graduate(self._cand(carrier={"kind": "lint_rule", "expression": "  "}))
        self.assertFalse(out["graduated"])
        self.assertEqual(out["state"], "proposal")

    def test_a_rule_with_no_evidence_is_rejected_outright(self):
        """Not a proposal — an opinion with no divergence behind it is not an observation at all."""
        out = learning.graduate(self._cand(evidence=[]))
        self.assertEqual(out["state"], "rejected")

    def test_the_carrier_list_is_closed(self):
        """An open list grows a `note` member, and a note is a belief with extra steps."""
        self.assertNotIn("note", learning.CARRIER_KINDS)
        self.assertNotIn("memory", learning.CARRIER_KINDS)

    def test_a_graduated_rule_is_governed_by_the_measured_fp_rate(self):
        out = learning.graduate(self._cand())
        self.assertTrue(out["generator"])
        self.assertIn("generators.py", out["note"])


class TestReport(unittest.TestCase):
    def test_with_no_cycles_run_it_is_correctly_empty(self):
        rep = learning.report(make_ledger())
        self.assertEqual(rep["divergences"]["total"], 0)
        self.assertEqual(rep["checks"], [])
        self.assertIn("observes nothing", rep["note"])

    def test_nothing_is_applied_only_made_eligible(self):
        led = make_ledger()
        rep = learning.report(led, candidates=[
            {"id": "r1", "evidence": ["pin_0001"],
             "carrier": {"kind": "test", "expression": "tests/test_refund.py::test_partial"}}])
        self.assertEqual(len(rep["checks"]), 1)
        self.assertIn("only the human's interview answer ever elects", rep["note"])

    def test_clusters_group_by_the_closed_vocabulary_not_by_prose(self):
        led = make_ledger()
        pin = led.add_pin(kind="defect", title="t", severity="low", confidence="extracted",
                          provenance=[{"source": "x", "detail": "y"}], as_is={"description": "d"})
        for detail in ("first", "second"):
            led.label_failure(pin["id"], "stale_carrier", detail, "build")
        led.label_failure(pin["id"], "environment", "one-off", "build")
        cl = learning.report(led)["clusters"]
        self.assertEqual([(c["class"], c["size"]) for c in cl], [("stale_carrier", 2)])


if __name__ == "__main__":
    unittest.main()
