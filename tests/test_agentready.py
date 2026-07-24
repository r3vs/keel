"""Tests for the Agent-Ready Gate, the premortem mode and the shared failure taxonomy
(core/decisions-ledger-spec.md v0.9). Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import agentready  # noqa: E402
import challenger  # noqa: E402
import ledger as ledgermod  # noqa: E402
from ledger import Ledger, LedgerError  # noqa: E402


def make_ledger() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


def crit(led: Ledger, **over) -> dict:
    """A decided acceptance_criterion with an oracle and a landing site — the ready baseline."""
    kw = dict(kind="acceptance_criterion", title="refunds work", severity="medium",
              confidence="extracted", provenance=[{"source": "interview", "detail": "x"}],
              anchors=[{"node_id": "", "layer": "api", "role": "impl", "loc": "src/pay/charge.ts:5"}],
              as_is={"built": None}, to_be={"statement": "refunds work", "verify": "e2e refund"})
    kw.update(over)
    pin = led.add_pin(**kw)
    if kw.get("_decide", True):
        led.decide(pin["id"], "yes", "because", "flip when refunds change")
    return pin


class TestFailureTaxonomy(unittest.TestCase):
    def test_the_challenge_classes_are_a_subset_not_a_parallel_list(self):
        """One vocabulary. Two lists for one concept is the divergence this package hunts."""
        self.assertTrue(set(ledgermod.CHALLENGE_CLASSES) <= set(ledgermod.FAILURE_CLASSES))

    def test_label_failure_changes_no_state(self):
        led = make_ledger()
        pin = crit(led)
        led.label_failure(pin["id"], "untested_path", "no test covered the refund path", "review")
        self.assertEqual(led.pin(pin["id"])["state"], "decided")

    def test_other_needs_detail_like_every_other_escape_hatch(self):
        led = make_ledger()
        pin = crit(led)
        with self.assertRaises(LedgerError):
            led.label_failure(pin["id"], "other", "", "build")

    def test_failures_reach_the_summary(self):
        """An event class that lives only in the log is the black hole again."""
        led = make_ledger()
        pin = crit(led)
        led.label_failure(pin["id"], "environment", "no docker on the runner", "evidence")
        self.assertEqual(led.summary()["failures_by_class"], {"environment": 1})

    def test_foresight_joins_feared_against_happened(self):
        led = make_ledger()
        pin = crit(led)
        led.premortem(pin["id"],
                      failure_modes=[{"class": "untested_path", "description": "nothing covers it"}],
                      guardrails=["write the characterization test first"])
        led.label_failure(pin["id"], "untested_path", "it happened", "review")
        led.label_failure(pin["id"], "external_change", "the SDK moved", "build")
        f = led.foresight(pin["id"])
        self.assertEqual(f["anticipated"], ["untested_path"])
        self.assertEqual(f["surprises"], ["external_change"])


class TestPremortem(unittest.TestCase):
    def test_failures_without_responses_are_a_worry_list(self):
        led = make_ledger()
        pin = crit(led)
        with self.assertRaises(LedgerError):
            led.premortem(pin["id"],
                          failure_modes=[{"class": "environment", "description": "no runner"}])

    def test_a_paper_tiger_without_evidence_is_an_ignored_risk(self):
        led = make_ledger()
        pin = crit(led)
        with self.assertRaises(LedgerError):
            led.premortem(pin["id"],
                          failure_modes=[{"class": "environment", "description": "no runner"}],
                          guardrails=["pin the image"],
                          paper_tigers=[{"risk": "concurrent writes corrupt the ledger"}])

    def test_no_failure_modes_at_all_is_refused(self):
        led = make_ledger()
        pin = crit(led)
        with self.assertRaises(LedgerError):
            led.premortem(pin["id"], failure_modes=[], guardrails=["x"])

    def test_premortem_is_labeled_judgment_and_moves_no_state(self):
        led = make_ledger()
        pin = crit(led)
        pm = led.premortem(pin["id"],
                           failure_modes=[{"class": "stale_carrier", "description": "old graph"}],
                           abort_criteria=["anchors still unresolved after a rebuild"])
        self.assertEqual(pm["determinism"], "D2")
        self.assertEqual(led.pin(pin["id"])["state"], "decided")

    def test_obligation_comes_from_carriers_not_a_new_threshold(self):
        led = make_ledger()
        low = crit(led, severity="low")
        self.assertFalse(challenger.premortem_required(led, low)["required"])
        high = crit(led, severity="high")
        self.assertTrue(challenger.premortem_required(led, high)["required"])

    def test_a_pin_reopened_before_owes_a_premortem(self):
        led = make_ledger()
        pin = crit(led, severity="low")
        led.reopen(pin["id"], "production disagreed")
        req = challenger.premortem_required(led, pin)
        self.assertTrue(req["required"])
        self.assertIn("this pin has been reopened before", req["because"])

    def test_gaps_lists_only_what_is_owed_and_absent(self):
        led = make_ledger()
        owed = crit(led, severity="blocker")
        crit(led, severity="low")                       # not owed
        done = crit(led, severity="high")
        led.premortem(done["id"],
                      failure_modes=[{"class": "scope_creep", "description": "spreads"}],
                      guardrails=["hold the declared zone"])
        self.assertEqual([g["pin_id"] for g in challenger.premortem_gaps(led)], [owed["id"]])


class TestAgentReadyGate(unittest.TestCase):
    def test_the_two_layers_are_never_merged_into_one_verdict(self):
        led = make_ledger()
        pin = crit(led)
        c = agentready.card(led, pin["id"])
        self.assertEqual(c["preconditions"]["determinism"], "D0")
        self.assertEqual(c["quality"]["determinism"], "D2")
        self.assertNotIn("ready", c["preconditions"])   # no fused boolean anywhere

    def test_no_oracle_routes_to_the_interview(self):
        led = make_ledger()
        pin = crit(led, to_be={"statement": "refunds work"})   # no verify
        c = agentready.card(led, pin["id"])
        self.assertEqual(c["route"], "needs_interview")

    def test_no_landing_site_routes_to_research(self):
        led = make_ledger()
        pin = crit(led, anchors=[])
        c = agentready.card(led, pin["id"])
        self.assertEqual(c["route"], "needs_research")

    def test_existing_code_with_no_assessed_terrain_routes_to_research(self):
        led = make_ledger()
        pin = crit(led)          # has anchors, no readiness recorded
        self.assertEqual(agentready.card(led, pin["id"])["route"], "needs_research")

    def test_a_greenfield_item_on_an_empty_tree_owes_no_terrain(self):
        """Reporting `unassessed` where nothing exists manufactures a gap out of emptiness."""
        led = make_ledger()
        pin = crit(led, anchors=[])
        led.add_remediation(pin["id"], "implement", 7, canonical_target="src/pay/refund.ts",
                            build_track="A")
        c = agentready.card(led, pin["id"])
        self.assertEqual(c["preconditions"]["checks"]["terrain"]["state"], "not_applicable")
        self.assertEqual(c["route"], "ready")

    def test_open_hardening_prerequisites_route_to_hardening(self):
        led = make_ledger()
        pin = crit(led)
        blocker = led.add_pin(kind="defect", title="fragile", severity="high",
                              confidence="extracted",
                              provenance=[{"source": "x", "detail": "y"}],
                              as_is={"description": "d"},
                              anchors=[{"node_id": "", "layer": "api", "role": "impl",
                                        "loc": "src/pay/charge.ts:12"}])
        led.set_readiness(pin["id"], "harden_first",
                          zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                          evidence={}, hardens=[blocker["id"]], rationale="unresolved blocker")
        self.assertEqual(agentready.card(led, pin["id"])["route"], "needs_hardening")

    def test_redesign_is_a_human_call_not_an_executor_one(self):
        led = make_ledger()
        pin = crit(led)
        led.set_readiness(pin["id"], "redesign",
                          zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                          evidence={}, rationale="the zone cannot bear it")
        c = agentready.card(led, pin["id"])
        self.assertEqual(c["route"], "human_only")
        self.assertIn("human", c["hand_to"])

    def test_an_owed_premortem_routes_to_the_challenger(self):
        led = make_ledger()
        pin = crit(led, severity="high")
        led.set_readiness(pin["id"], "ready",
                          zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                          evidence={}, rationale="quiet and covered")
        c = agentready.card(led, pin["id"])
        self.assertEqual(c["route"], "needs_challenge")
        self.assertEqual(c["hand_to"], agentready.OWNERS["needs_challenge"])
        led.premortem(pin["id"],
                      failure_modes=[{"class": "contract_drift", "description": "shapes diverge"}],
                      abort_criteria=["drift-check red after generation"])
        self.assertEqual(agentready.card(led, pin["id"])["route"], "ready")

    def test_the_gate_is_advisory_and_never_shrinks_the_queue(self):
        led = make_ledger()
        import buildloop
        pin = crit(led, to_be={"statement": "refunds work"})   # unready: no verify
        led.add_remediation(pin["id"], "implement", 7, build_track="A")
        self.assertIn(pin["id"], [p["id"] for p in buildloop.ready(led)])
        g = agentready.gate(led)
        self.assertEqual(g["handable_now"], [])
        self.assertEqual(g["by_route"]["needs_interview"], [pin["id"]])


if __name__ == "__main__":
    unittest.main()
