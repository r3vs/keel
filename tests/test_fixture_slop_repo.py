"""The slop-repo fixture is a valid rescue target — the runtime finds its planted problems.

This is the end-to-end check that the pieces (shape engine, ast-grep markers, findings gate)
actually detect real issues on a small realistic multi-layer repo, not just unit fixtures. It is
also the target `scripts/run_evals.py --run` points an agent at.
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import shapes  # noqa: E402

REPO = pathlib.Path(__file__).parent / "fixtures" / "slop-repo"


class TestPlantedContractDrift(unittest.TestCase):
    def test_shape_engine_finds_the_two_planted_mismatches(self):
        findings = shapes.drift_check(str(REPO / "contract.json"), ddl=str(REPO / "schema.sql"))
        kinds = {(f["field"], f["kind"]) for f in findings}
        # planted drift 1: enum missing 'member'
        self.assertIn(("role", "enum_mismatch"), kinds)
        # planted drift 2: display_name nullable in DB, NOT NULL in contract
        self.assertIn(("display_name", "nullability_mismatch"), kinds)

    def test_no_spurious_drift_on_aligned_fields(self):
        findings = shapes.drift_check(str(REPO / "contract.json"), ddl=str(REPO / "schema.sql"))
        drifted_fields = {f["field"] for f in findings}
        self.assertNotIn("email", drifted_fields)      # email is aligned — must not be flagged
        self.assertNotIn("id", drifted_fields)


class TestPlantedCodeIssues(unittest.TestCase):
    def setUp(self):
        self.src = (REPO / "handlers.py").read_text(encoding="utf-8")

    def test_intentional_stub_present(self):
        # the completeness module classifies this as incompleteness, not a defect
        self.assertIn("raise NotImplementedError", self.src)

    def test_sqli_shape_present(self):
        # raw SQL by string concatenation — the ast-grep pack + findings gate confirm it
        self.assertIn('"SELECT * FROM users WHERE email LIKE', self.src)
        self.assertIn('" + q + "', self.src)


class TestBriefFixtures(unittest.TestCase):
    def test_three_briefs_exist_and_name_their_project_type(self):
        briefs = pathlib.Path(__file__).parent / "fixtures" / "briefs"
        found = {p.stem for p in briefs.glob("*.md")}
        self.assertEqual(found, {"crud-saas", "cli-tool", "api-service"})
        for p in briefs.glob("*.md"):
            self.assertIn("Project type:", p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
