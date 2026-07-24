"""Tests for runtime/readiness.py + the ledger's readiness wiring — the premortem of the terrain
(core/decisions-ledger-spec.md v0.8). Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import readiness  # noqa: E402
from ledger import Ledger, LedgerError  # noqa: E402


def write_graph(tmp: str, head: str = "abc1234") -> str:
    """A tiny graph: charge.ts <- checkout.ts, plus a test that only reaches checkout."""
    data = {
        "built_at_commit": head,
        "nodes": [
            {"id": "n1", "name": "charge", "file": "src/pay/charge.ts", "line": 1, "end_line": 40},
            {"id": "n2", "name": "checkout", "file": "src/pay/checkout.ts", "line": 1, "end_line": 20},
            {"id": "n3", "name": "spec", "file": "src/pay/checkout.test.ts", "line": 1, "end_line": 9},
        ],
        "edges": [
            {"source": "n2", "target": "n1", "type": "imports", "confidence": "extracted"},
            {"source": "n3", "target": "n2", "type": "imports", "confidence": "extracted"},
        ],
    }
    path = os.path.join(tmp, "graph.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def make_ledger(tmp: str) -> Ledger:
    return Ledger(os.path.join(tmp, "ledger.json"))


def pin_at(led: Ledger, loc: str, **over) -> dict:
    kw = dict(kind="defect", title="t", severity="high", confidence="extracted",
              provenance=[{"source": "x", "detail": "y"}], as_is={"description": "d"},
              anchors=[{"node_id": "", "layer": "api", "role": "impl", "loc": loc}])
    kw.update(over)
    return led.add_pin(**kw)


class TestZoneAndEvidence(unittest.TestCase):
    def test_zone_is_reverse_reachability_from_the_anchors(self):
        tmp = tempfile.mkdtemp()
        g = readiness.graphmod.load(write_graph(tmp))
        zone = readiness.zone_of(g, [{"loc": "src/pay/charge.ts:5"}])
        self.assertIn("src/pay/charge.ts", zone["files"])
        self.assertIn("src/pay/checkout.ts", zone["files"])   # depends on charge -> must bear it

    def test_unresolvable_anchor_is_reported_not_dropped(self):
        """A zone from half the anchors is not a smaller zone, it is an unknown one."""
        tmp = tempfile.mkdtemp()
        g = readiness.graphmod.load(write_graph(tmp))
        zone = readiness.zone_of(g, [{"loc": "src/nope/gone.ts:3"}])
        self.assertEqual(zone["unresolved_anchors"], ["src/nope/gone.ts:3"])

    def test_untested_counts_only_what_no_test_reaches(self):
        tmp = tempfile.mkdtemp()
        g = readiness.graphmod.load(write_graph(tmp))
        untested = readiness.untested_in_zone(g, ["n1", "n2"])
        self.assertIn("src/pay/charge.ts", untested)          # nothing under a test path reaches it
        self.assertNotIn("src/pay/checkout.ts", untested)     # the spec imports it

    def test_open_pins_in_zone_is_the_cheapest_carrier(self):
        tmp = tempfile.mkdtemp()
        led = make_ledger(tmp)
        inside = pin_at(led, "src/pay/charge.ts:12", severity="blocker")
        pin_at(led, "src/unrelated/other.ts:3")               # outside: must not appear
        found = readiness._open_pins_in_zone(led.data, {"src/pay/charge.ts"})
        self.assertEqual([f["pin"] for f in found], [inside["id"]])

    def test_stale_graph_refuses_rather_than_degrades(self):
        tmp = tempfile.mkdtemp()
        led = make_ledger(tmp)
        with self.assertRaises(readiness.StaleGraph):
            readiness.assess(write_graph(tmp, head="old1234"), led.data,
                             [{"loc": "src/pay/charge.ts:5"}], repo=tmp, head="new1234")

    def test_assess_states_no_verdict(self):
        """The runtime computes facts and refuses to conclude — the verdict is D2, elsewhere."""
        tmp = tempfile.mkdtemp()
        led = make_ledger(tmp)
        out = readiness.assess(write_graph(tmp), led.data, [{"loc": "src/pay/charge.ts:5"}],
                               repo=tmp, head="abc1234")
        self.assertEqual(out["determinism"], "D0")
        self.assertNotIn("verdict", out)


class TestReadinessWiring(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.mkdtemp()
        led = make_ledger(tmp)
        change = pin_at(led, "src/pay/charge.ts:5", kind="acceptance_criterion",
                        as_is={"built": None},
                        to_be={"statement": "refunds work", "verify": "e2e"})
        return led, change

    def test_harden_first_blocks_the_change_through_depends_on(self):
        led, change = self._setup()
        blocker = pin_at(led, "src/pay/charge.ts:12", severity="blocker")
        led.set_readiness(change["id"], "harden_first",
                          zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                          evidence={"open_pins_in_zone": [{"pin": blocker["id"]}]},
                          hardens=[blocker["id"]], rationale="unresolved blocker in the zone")
        self.assertIn(blocker["id"], change["depends_on"])
        import buildloop
        led.decide(change["id"], "in", "r", "flip")
        self.assertNotIn(change["id"], [p["id"] for p in buildloop.ready(led)])

    def test_change_justified_is_enforced_not_promised(self):
        """A pin anchored outside the zone is someone else's cleanup."""
        led, change = self._setup()
        elsewhere = pin_at(led, "src/admin/panel.ts:9")
        with self.assertRaises(LedgerError):
            led.set_readiness(change["id"], "harden_first",
                              zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                              evidence={}, hardens=[elsewhere["id"]])

    def test_harden_first_without_prerequisites_is_a_worry_not_a_verdict(self):
        led, change = self._setup()
        with self.assertRaises(LedgerError):
            led.set_readiness(change["id"], "harden_first",
                              zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                              evidence={}, hardens=[])

    def test_ready_carries_no_prerequisites(self):
        led, change = self._setup()
        other = pin_at(led, "src/pay/charge.ts:12")
        with self.assertRaises(LedgerError):
            led.set_readiness(change["id"], "ready",
                              zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                              evidence={}, hardens=[other["id"]])

    def test_cycle_is_refused(self):
        led, change = self._setup()
        dependent = pin_at(led, "src/pay/charge.ts:12", depends_on=[change["id"]])
        with self.assertRaises(LedgerError):
            led.set_readiness(change["id"], "harden_first",
                              zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                              evidence={}, hardens=[dependent["id"]])

    def test_the_two_determinism_levels_are_recorded_separately(self):
        led, change = self._setup()
        pin = led.set_readiness(change["id"], "ready",
                                zone={"files": ["src/pay/charge.ts"], "nodes": ["n1"]},
                                evidence={"untested_files": []}, rationale="tested and quiet")
        self.assertEqual(pin["readiness"]["determinism"], "D2")           # the verdict
        self.assertEqual(pin["readiness"]["evidence_determinism"], "D0")  # what it read

    def test_a_verdict_needs_a_zone(self):
        led, change = self._setup()
        with self.assertRaises(LedgerError):
            led.set_readiness(change["id"], "ready", zone={"files": []}, evidence={})


if __name__ == "__main__":
    unittest.main()
