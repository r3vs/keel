"""Tests for runtime/map.py — the visual map artifact.

The map is a user-facing deliverable and its correctness is a DOM, so it is verified rendered in a
browser — repeatably, via `python scripts/preview_map.py`, whose docstring lists what to look at.
That pass covers the pin list, the `as_is`/`to_be` projection over every shape the spec allows, the
three-column contract-diff with the disagreeing layer flagged, the linked interview question, the
traffic-light, the `evidence` states of a decision card (elicited / brief / transcribed with a
quote / transcribed with none / cascaded, which also shows the policy and how it was elected)
reading as *different strengths* before the words are read, and
hostile content rendering as text rather than executing — in light and dark.

These tests pin only what CI can guard without a browser: the output is one self-contained file
(data inlined, no external fetch), it is script-safe, and every pin's data reaches the page.
Deliberately NOT here: assertions that the template *contains* the strings a correct renderer would
emit. Matching source text against expected content is the heuristic this package refuses
everywhere else; it would pass on a renderer that never runs.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import map as mapmod  # noqa: E402
from ledger import Ledger  # noqa: E402


def demo_ledger() -> Ledger:
    led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
    led.add_pin(
        kind="contract_mismatch", title="role enum drift", severity="blocker",
        confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
        anchors=[{"node_id": None, "layer": "db", "role": "src", "loc": "m.sql:12"}],
        as_is={"db": "ENUM('admin','user')", "frontend": "'superadmin'",
               "disagreeing_layers": ["frontend"]},
        question={"prompt": "Intended role set?",
                  "options": [{"id": "a", "label": "DB is truth", "implication": "drop FE check"}],
                  "allow_freeform": True})
    return led


class TestSelfContained(unittest.TestCase):
    def setUp(self):
        self.html = mapmod.render(demo_ledger().data, title="demo")

    def test_is_a_full_html_document(self):
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("</html>", self.html)

    def test_no_external_resources(self):
        # a self-contained artifact opens offline: no external scripts/styles/fetch/img
        for pattern in (r'src\s*=\s*["\']https?:', r'href\s*=\s*["\']https?:',
                        r'@import', r'fetch\(["\']https?:'):
            self.assertIsNone(re.search(pattern, self.html),
                              f"external resource matched {pattern!r}")

    def test_ledger_data_is_inlined(self):
        self.assertIn("const LEDGER =", self.html)
        self.assertIn("role enum drift", self.html)          # pin title reached the page
        self.assertIn("disagreeing_layers", self.html)       # contract-diff data inlined

    def test_script_safe_closing_tags_escaped(self):
        # no raw </script> from data could break out of the inline script
        script_body = self.html.split("const LEDGER =", 1)[1]
        data_line = script_body.split("\n", 1)[0]
        self.assertNotIn("</script", data_line.lower())

    def test_empty_ledger_renders(self):
        empty = Ledger(os.path.join(tempfile.mkdtemp(), "l.json"))
        out = mapmod.render(empty.data)
        self.assertIn("<!doctype html>", out.lower())

    def test_render_file_writes_html(self):
        led = demo_ledger()
        led.save()
        out_path = os.path.join(tempfile.mkdtemp(), "map.html")
        result = mapmod.render_file(led.path, out_path)
        self.assertTrue(os.path.exists(result))
        self.assertIn("role enum drift", result.read_text(encoding="utf-8"))


class TestGraphAnchoredRendering(unittest.TestCase):
    """Anchors enriched by runtime/graph.py (node_id + blast_radius) reach the page — the map
    stays a self-contained projection: the graph is needed at anchor time, never at view time."""

    def test_node_id_and_blast_radius_inlined(self):
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(
            kind="contract_mismatch", title="role enum drift", severity="blocker",
            confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
            anchors=[{"node_id": "table_users", "layer": "db", "role": "src",
                      "loc": "packages/db/schema/users.ts:12",
                      "blast_radius": {"count": 3, "depth": 2, "edges": "structural/extracted",
                                       "sample": ["backend/models.py:30", "frontend/types.ts:5"]}}],
            as_is={"db": "x", "frontend": "y", "disagreeing_layers": ["frontend"]})
        html = mapmod.render(led.data, title="anchored")
        self.assertIn("table_users", html)          # node_id inlined
        self.assertIn("impact:", html)               # blast-radius line present
        self.assertIn("backend/models.py:30", html)  # sample dependent inlined
        # still self-contained: no external fetch introduced
        self.assertNotIn("fetch(", html.split("const LEDGER =", 1)[1].split("\n", 1)[0])


class TestDecisionEvidenceIsInlined(unittest.TestCase):
    """The decision card states the rung, which lives on the DecisionEvent — so the page must carry
    `decision_log`, not just `pins`.

    This is the only part of that feature CI can hold without a browser, and it is worth holding:
    trimming the inlined payload to `pins` is an obvious "optimization" that would turn the lookup
    into a dangling id and silently drop the rung — with the page still rendering, still
    self-contained, and every other test still green. Asserting that the *template* contains the
    words a correct card would print is the heuristic this file refuses; asserting the data the
    lookup needs is a fact about the artifact."""

    def test_the_event_the_pin_points_at_reaches_the_page(self):
        led = demo_ledger()
        pin = led.data["pins"][0]
        led.decide(pin["id"], "a", "the DB enum is narrowest", "a fourth role appears",
                   evidence="transcribed", human_answer="option a — the DB is truth")
        html = mapmod.render(led.data, title="decided")
        event_id = pin["decision"]["event_id"]
        payload = json.loads(html.split("const LEDGER =", 1)[1]
                             .split(";\n", 1)[0].replace("<\\/", "</"))
        event = next((e for e in payload.get("decision_log", []) if e["id"] == event_id), None)
        self.assertIsNotNone(event, "the map cannot resolve pin.decision.event_id — the rung is "
                                    "unreachable from the page, whatever the card says")
        self.assertEqual(event["evidence"], "transcribed")
        self.assertEqual(event["human_answer"], "option a — the DB is truth")

    def test_a_cascaded_card_can_reach_the_policy_that_decided_it(self):
        """The `cascaded` card states the rule the user elected and how they elected it, so the
        second join — event.policy_id -> policies[] — has to land on the page too. It is a join on a
        field, not on `source`'s `policy:<id>` prefix: a surface that parses a string to find its
        record is one refactor away from silently finding nothing."""
        led = demo_ledger()
        pin = led.data["pins"][0]
        pin["severity"] = "low"                      # blocker|high is held back by the threshold
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="the DB is truth",
                             default_outcome="a",   # the id this pin's own question offers (v0.12)
                             human_answer="db wins unless I flag one")
        led.apply_policy(pol)
        payload = json.loads(mapmod.render(led.data, title="cascaded").split("const LEDGER =", 1)[1]
                             .split(";\n", 1)[0].replace("<\\/", "</"))
        event = next(e for e in payload["decision_log"] if e["id"] == pin["decision"]["event_id"])
        self.assertEqual(event["evidence"], "cascaded")
        policy = next((p for p in payload.get("policies", []) if p["id"] == event["policy_id"]), None)
        self.assertIsNotNone(policy, "the map cannot resolve event.policy_id — the card would have "
                                     "to say a policy decided this and be unable to say which")
        self.assertEqual((policy["rule"], policy["evidence"], policy["human_answer"]),
                         ("the DB is truth", "transcribed", "db wins unless I flag one"))


class TestLiveMode(unittest.TestCase):
    """live=True turns the map into a self-reloading dev monitor; live=False (the default) stays the
    frozen single-file artifact. The self-contained invariant must survive live mode."""

    def test_default_is_frozen(self):
        html = mapmod.render(demo_ledger().data, title="demo")
        self.assertNotIn("livebadge", html)
        self.assertNotIn("location.reload", html)

    def test_live_adds_self_reload_and_badge(self):
        html = mapmod.render(demo_ledger().data, title="demo", live=True)
        self.assertIn("livebadge", html)        # the LIVE badge
        self.assertIn("location.reload", html)  # the self-reload loop
        self.assertIn("decmap.live", html)      # selection/view/state persisted across reload

    def test_live_stays_self_contained(self):
        # the whole point of the map: even live, one offline file with no external fetch
        html = mapmod.render(demo_ledger().data, title="demo", live=True)
        for pattern in (r'src\s*=\s*["\']https?:', r'href\s*=\s*["\']https?:', r'@import', r'fetch\('):
            self.assertIsNone(re.search(pattern, html),
                              f"live mode introduced an external resource: {pattern!r}")
        self.assertTrue(html.lstrip().lower().startswith("<!doctype html>"))

    def test_render_file_live_flag(self):
        led = demo_ledger(); led.save()
        out_path = os.path.join(tempfile.mkdtemp(), "map.html")
        mapmod.render_file(led.path, out_path, live=True)
        with open(out_path, encoding="utf-8") as fh:
            self.assertIn("livebadge", fh.read())


if __name__ == "__main__":
    unittest.main()
