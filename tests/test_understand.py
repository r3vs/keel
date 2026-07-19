"""Tests for runtime/understand.py — the understand-mode orchestrator (comprehension as an end).

Pins: it builds the bundle (graph + overview + tour) from a real tree, the overview census + hotspots
are right, and the bundle persists to disk (phases talk through disk). Pure as-is — no ledger, no
interview appears anywhere in the output.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import understand  # noqa: E402


def _write_repo(root: pathlib.Path) -> None:
    (root / "api").mkdir()
    (root / "db").mkdir()
    (root / "app.py").write_text(
        "from api.svc import Service\n\n\ndef main():\n    return Service().run()\n", encoding="utf-8")
    (root / "api" / "svc.py").write_text(
        "from db.models import get_user\n\n\nclass Service:\n"
        "    def run(self):\n        return get_user()\n", encoding="utf-8")
    (root / "db" / "models.py").write_text(
        "class User:\n    pass\n\n\ndef get_user():\n    return User()\n", encoding="utf-8")


class TestUnderstand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        _write_repo(self.root)
        self.bundle = understand.understand(self.root, commit="beadfed")

    def tearDown(self):
        self.tmp.cleanup()

    def test_overview_census(self):
        ov = self.bundle["overview"]
        self.assertEqual(ov["files"], 3)
        self.assertEqual(ov["languages"], {"python": 3})
        self.assertEqual(set(ov["layers"]), {"root", "api", "db"})
        self.assertEqual(ov["built_at_commit"], "beadfed")

    def test_hotspots_present_and_ranked(self):
        hot = self.bundle["overview"]["hotspots"]
        self.assertTrue(hot)
        counts = [h["dependents"] for h in hot]
        self.assertEqual(counts, sorted(counts, reverse=True))  # ranked desc

    def test_tour_layers(self):
        layers = [s["layer"] for s in self.bundle["tour"]["steps"]]
        self.assertEqual(layers[0], "root")           # entry-first
        self.assertEqual(set(layers), {"root", "api", "db"})

    def test_write_bundle(self):
        with tempfile.TemporaryDirectory() as out:
            paths = understand.write_bundle(self.bundle, out)
            for key in ("graph", "overview", "tour"):
                p = pathlib.Path(paths[key])
                self.assertTrue(p.exists())
                json.loads(p.read_text(encoding="utf-8"))  # valid JSON

    def test_pure_as_is(self):
        # comprehension is terminal here: nothing in the bundle elects a to_be or opens an interview
        blob = json.dumps(self.bundle)
        for forbidden in ("to_be", "interview", "remediation", "ledger"):
            self.assertNotIn(forbidden, blob)


if __name__ == "__main__":
    unittest.main()
