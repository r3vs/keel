"""Tests for the additional-stack extractors in runtime/shapes.py (Drizzle, Prisma, Django,
GraphQL). Proves new stacks are additive: each normalizes to the one descriptor, an aligned
fixture diffs clean against the shared step-0 contract, and injected drift is caught.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import shapes  # noqa: E402

STACKS = pathlib.Path(__file__).parent / "fixtures" / "stacks"
CONTRACT = str(pathlib.Path(__file__).parent / "fixtures" / "step0" / "contract.json")


def mutate(source: pathlib.Path, old: str, new: str) -> str:
    text = source.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {source.name}"
    fd, path = tempfile.mkstemp(suffix=source.suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    return path


class TestExtraction(unittest.TestCase):
    def test_drizzle_pg_enum_and_balanced_braces(self):
        out = shapes.extract_drizzle(str(STACKS / "schema.drizzle.ts"))
        # the nested { length: 255 } must not truncate the table body — role comes after it
        self.assertIn("role", out["users"])
        self.assertEqual(out["users"]["role"]["type"], "enum")
        self.assertEqual(out["users"]["role"]["enum"], ["admin", "member"])
        self.assertTrue(out["users"]["email"]["constraints"]["unique"])
        self.assertEqual(out["tasks"]["assignee_id"]["constraints"]["foreign_key"], "users.id")

    def test_prisma_model_enum_and_uuid_mapping(self):
        out = shapes.extract_prisma(str(STACKS / "schema.prisma"))
        self.assertEqual(out["User"]["role"]["type"], "enum")
        self.assertEqual(out["User"]["id"]["type"], "uuid")        # String @default(uuid())
        self.assertNotIn("projects", out["User"])                  # relation, not a scalar

    def test_django_models(self):
        out = shapes.extract_django(str(STACKS / "models_django.py"))
        self.assertEqual(out["User"]["email"]["type"], "string")
        self.assertEqual(out["User"]["email"]["constraints"]["max_length"], 255)
        self.assertEqual(out["User"]["role"]["type"], "enum")      # choices=
        self.assertEqual(out["User"]["role"]["confidence"], "ambiguous")  # values not resolved
        self.assertTrue(out["Project"]["description"]["nullable"])  # null=True

    def test_graphql_sdl(self):
        out = shapes.extract_graphql(str(STACKS / "schema.graphql"))
        self.assertEqual(out["User"]["id"]["type"], "uuid")        # ID!
        self.assertEqual(out["User"]["role"]["type"], "enum")
        self.assertFalse(out["User"]["email"]["nullable"])         # String! → non-null
        self.assertTrue(out["Project"]["description"]["nullable"])  # String (no !)
        self.assertNotIn("projects", out["User"])                  # [Project!]! list → skipped


class TestAlignedFixturesDiffClean(unittest.TestCase):
    def test_all_four_stacks_align_with_the_contract(self):
        for kw in ({"drizzle": str(STACKS / "schema.drizzle.ts")},
                   {"prisma": str(STACKS / "schema.prisma")},
                   {"django": str(STACKS / "models_django.py")},
                   {"graphql": str(STACKS / "schema.graphql")}):
            findings = shapes.drift_check(CONTRACT, **kw)
            hard = [f for f in findings if f["confidence"] != "ambiguous"]
            self.assertEqual(hard, [], f"{list(kw)[0]} drifted: {hard}")


class TestInjectedDrift(unittest.TestCase):
    def test_drizzle_enum_widened_is_caught(self):
        path = mutate(STACKS / "schema.drizzle.ts",
                      'pgEnum("user_role", ["admin", "member"])',
                      'pgEnum("user_role", ["admin", "member", "superadmin"])')
        findings = shapes.drift_check(CONTRACT, drizzle=path)
        self.assertIn(("role", "enum_mismatch"), {(f["field"], f["kind"]) for f in findings})

    def test_prisma_type_change_is_caught(self):
        path = mutate(STACKS / "schema.prisma", "is_archived Boolean", "is_archived String ")
        findings = shapes.drift_check(CONTRACT, prisma=path)
        self.assertIn(("is_archived", "type_mismatch"), {(f["field"], f["kind"]) for f in findings})

    def test_graphql_nullability_flip_is_caught(self):
        path = mutate(STACKS / "schema.graphql", "email: String!", "email: String")
        findings = shapes.drift_check(CONTRACT, graphql=path)
        self.assertIn(("email", "nullability_mismatch"),
                      {(f["field"], f["kind"]) for f in findings})

    def test_django_missing_field_is_caught(self):
        path = mutate(STACKS / "models_django.py",
                      "    display_name = models.CharField(max_length=80)\n", "")
        findings = shapes.drift_check(CONTRACT, django=path)
        self.assertIn(("display_name", "missing_field"),
                      {(f["field"], f["kind"]) for f in findings})


if __name__ == "__main__":
    unittest.main()
