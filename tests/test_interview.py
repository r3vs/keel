"""Tests for runtime/interview.py + the decision catalog — greenfield's Phase-1 as code.

Pins the two catalog disciplines (prune by project type, skip brief-decided forks), the
depends_on wiring, and the funnel compression (asked ordered by information gain, low-severity
tail routed to proposed_default).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import interview  # noqa: E402
from ledger import Ledger  # noqa: E402

CATALOG = (pathlib.Path(__file__).resolve().parent.parent
           / "src" / "skills" / "greenfield-forge" / "assets" / "decision-catalog.json")


def fresh_ledger() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


class TestCatalogAsset(unittest.TestCase):
    def test_catalog_is_valid_and_ordered(self):
        cat = interview.load_catalog(CATALOG)
        orders = [c["order"] for c in cat["clusters"]]
        self.assertEqual(orders, sorted(orders))            # information-gain order
        self.assertEqual(cat["clusters"][0]["id"], "outcomes")  # roots first

    def test_every_depends_on_target_exists(self):
        cat = interview.load_catalog(CATALOG)
        ids = {c["id"] for c in cat["clusters"]}
        for c in cat["clusters"]:
            for dep in c.get("depends_on", []):
                self.assertIn(dep, ids, f"{c['id']} depends_on unknown {dep}")

    def test_kinds_are_valid_ledger_kinds(self):
        from ledger import KINDS
        cat = interview.load_catalog(CATALOG)
        for c in cat["clusters"]:
            self.assertIn(c["kind"], KINDS)


class TestExpand(unittest.TestCase):
    def setUp(self):
        self.cat = interview.load_catalog(CATALOG)

    def test_web_saas_materializes_full_catalog(self):
        led = fresh_ledger()
        result = interview.expand_catalog(led, self.cat, project_type="web-saas")
        self.assertEqual(result["pruned"], [])
        self.assertEqual(len(led.data["pins"]), len(self.cat["clusters"]))

    def test_cli_prunes_api_client_identity(self):
        led = fresh_ledger()
        result = interview.expand_catalog(led, self.cat, project_type="cli")
        for pruned in ("api_contract", "client", "identity"):
            self.assertIn(pruned, result["pruned"])
        titles = {p["title"] for p in led.data["pins"]}
        self.assertNotIn("Client & rendering", titles)

    def test_depends_on_wired_to_pin_ids(self):
        led = fresh_ledger()
        interview.expand_catalog(led, self.cat, project_type="web-saas")
        persistence = next(p for p in led.data["pins"] if p["title"].startswith("Persistence"))
        domain = next(p for p in led.data["pins"] if p["title"].startswith("Product scope"))
        self.assertIn(domain["id"], persistence["depends_on"])  # persistence depends_on domain

    def test_brief_decided_forks_are_pre_committed_not_asked(self):
        led = fresh_ledger()
        result = interview.expand_catalog(led, self.cat, project_type="web-saas",
                                          brief_decisions={"persistence": "relational"})
        self.assertIn("persistence", result["pre_decided"])
        persistence = next(p for p in led.data["pins"] if p["title"].startswith("Persistence"))
        self.assertEqual(persistence["state"], "decided")
        self.assertEqual(persistence["decision"]["outcome"], "relational")

    def test_pruned_cluster_with_dependents_still_wires_surviving_deps(self):
        # client depends_on api_contract; in an api-service, client is pruned but api survives
        led = fresh_ledger()
        interview.expand_catalog(led, self.cat, project_type="api-service")
        titles = {p["title"] for p in led.data["pins"]}
        self.assertNotIn("Client & rendering", titles)
        self.assertTrue(any(t.startswith("API & contract") for t in titles))


class TestFunnel(unittest.TestCase):
    def setUp(self):
        self.cat = interview.load_catalog(CATALOG)

    def test_funnel_compresses_and_orders_by_information_gain(self):
        led = fresh_ledger()
        interview.expand_catalog(led, self.cat, project_type="web-saas")
        view = interview.funnel(led)
        # blocker/high forks are asked; the medium tail rides as proposed_default
        self.assertGreater(view["asked_count"], 0)
        self.assertGreater(view["tail_count"], 0)
        # first asked question has the most downstream dependents (highest information gain)
        downstreams = [q["downstream"] for q in view["asked"]]
        self.assertEqual(downstreams, sorted(downstreams, reverse=True))

    def test_blocker_forks_never_ride_as_proposed_default(self):
        led = fresh_ledger()
        interview.expand_catalog(led, self.cat, project_type="web-saas")
        view = interview.funnel(led)
        tail_severities = {q["severity"] for q in view["proposed_default"]}
        self.assertNotIn("blocker", tail_severities)
        self.assertNotIn("high", tail_severities)

    def test_outcomes_root_surfaces_as_highest_gain_question(self):
        led = fresh_ledger()
        interview.expand_catalog(led, self.cat, project_type="web-saas")
        view = interview.funnel(led)
        self.assertTrue(view["asked"])
        # the domain/outcomes roots (most downstream) come first
        self.assertGreaterEqual(view["asked"][0]["downstream"], view["asked"][-1]["downstream"])

    def test_default_policies_offered_per_surviving_cluster(self):
        led = fresh_ledger()
        interview.expand_catalog(led, self.cat, project_type="cli")
        offers = interview.default_policies(self.cat, led, project_type="cli")
        offer_ids = {o["cluster_id"] for o in offers}
        self.assertIn("cl_domain", offer_ids)
        self.assertNotIn("cl_client", offer_ids)   # pruned cluster offers no policy


if __name__ == "__main__":
    unittest.main()
