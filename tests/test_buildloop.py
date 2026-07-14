"""Tests for runtime/buildloop.py — the wave scheduler that levels the Phase-4 DAG.

Proves the ordering rules ("contracts before logic" falls out of depends_on, not a hardcode),
readiness (deps closed + own work unfinished), the wave checkpoint gate, restart-safety, and
cycle detection.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import buildloop  # noqa: E402
from ledger import Ledger  # noqa: E402


def fresh() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


def build_chain(led):
    """contract → api → client, each a decided open_decision with one scaffold BuildItem."""
    contract = led.add_pin(kind="open_decision", title="contract", severity="high",
                           confidence="inferred", provenance=[{"source": "c", "detail": "x"}],
                           as_is={"givens": [], "built": None})
    api = led.add_pin(kind="open_decision", title="api", severity="medium", confidence="inferred",
                      provenance=[{"source": "c", "detail": "x"}],
                      as_is={"givens": [], "built": None}, depends_on=[contract["id"]])
    client = led.add_pin(kind="open_decision", title="client", severity="medium",
                         confidence="inferred", provenance=[{"source": "c", "detail": "x"}],
                         as_is={"givens": [], "built": None}, depends_on=[api["id"]])
    for p in (contract, api, client):
        led.decide(p["id"], "opt", "elected", "flip")
        led.add_remediation(p["id"], action="scaffold", ladder_rung=7, build_track="A")
    return contract, api, client


class TestWaves(unittest.TestCase):
    def test_waves_level_the_dag(self):
        led = fresh()
        contract, api, client = build_chain(led)
        wv = buildloop.waves(led)
        self.assertEqual(wv[0], [contract["id"]])   # no deps → wave 0
        self.assertEqual(wv[1], [api["id"]])         # depends on contract → wave 1
        self.assertEqual(wv[2], [client["id"]])      # depends on api → wave 2

    def test_cycle_detected(self):
        led = fresh()
        a = led.add_pin(kind="open_decision", title="a", severity="low", confidence="inferred",
                        provenance=[{"source": "c", "detail": "x"}], as_is={"givens": [], "built": None})
        b = led.add_pin(kind="open_decision", title="b", severity="low", confidence="inferred",
                        provenance=[{"source": "c", "detail": "x"}], as_is={"givens": [], "built": None},
                        depends_on=[a["id"]])
        a["depends_on"] = [b["id"]]                  # introduce a cycle
        with self.assertRaises(ValueError):
            buildloop.waves(led)


class TestReadiness(unittest.TestCase):
    def test_only_contract_ready_initially(self):
        led = fresh()
        contract, api, client = build_chain(led)
        ready = [p["title"] for p in buildloop.ready(led)]
        self.assertEqual(ready, ["contract"])        # api/client blocked on upstream

    def test_closing_a_wave_unblocks_the_next(self):
        led = fresh()
        contract, api, client = build_chain(led)
        item = contract["remediation"][0]
        led.set_remediation_status(contract["id"], item["id"], "done")
        led.resolve(contract["id"])
        ready = [p["title"] for p in buildloop.ready(led)]
        self.assertEqual(ready, ["api"])             # now api is ready, client still blocked

    def test_next_item_returns_first_todo(self):
        led = fresh()
        contract, _, _ = build_chain(led)
        pin, item = buildloop.next_item(led)
        self.assertEqual(pin["title"], "contract")
        self.assertEqual(item["action"], "scaffold")

    def test_next_item_none_when_all_resolved(self):
        led = fresh()
        c, a, cl = build_chain(led)
        for p in (c, a, cl):
            led.set_remediation_status(p["id"], p["remediation"][0]["id"], "done")
            led.resolve(p["id"])
        self.assertIsNone(buildloop.next_item(led))


class TestCheckpoint(unittest.TestCase):
    def test_wave_incomplete_until_items_done(self):
        led = fresh()
        contract, _, _ = build_chain(led)
        cp = buildloop.checkpoint(led, 0)
        self.assertFalse(cp["complete"])
        self.assertIn(contract["id"], cp["pending"])
        led.set_remediation_status(contract["id"], contract["remediation"][0]["id"], "done")
        led.resolve(contract["id"])
        self.assertTrue(buildloop.checkpoint(led, 0)["complete"])


class TestRestartSafety(unittest.TestCase):
    def test_ready_recomputes_from_persisted_state(self):
        led = fresh()
        build_chain(led)
        led.save()
        # simulate a crash + restart: reload from disk, ready() must be identical
        reloaded = Ledger(led.path)
        self.assertEqual([p["title"] for p in buildloop.ready(reloaded)], ["contract"])

    def test_defect_is_actionable_without_a_decision(self):
        led = fresh()
        d = led.add_pin(kind="defect", title="sqli", severity="blocker", confidence="extracted",
                        provenance=[{"source": "semgrep", "detail": "sqli"}],
                        as_is={"description": "x"})
        led.add_remediation(d["id"], action="refactor", ladder_rung=1)
        self.assertEqual([p["title"] for p in buildloop.ready(led)], ["sqli"])


if __name__ == "__main__":
    unittest.main()
