"""Tests for runtime/shapes.py — the field-shape engine over the step-0 fixtures.

The fixtures under tests/fixtures/step0/ are the REAL artifacts of greenfield's gating
experiment (contract carrier + four generated layers, machine-validated). The green case
asserts the whole stack diffs clean against the carrier; the drift cases inject the classic
mismatches rescue exists to find and assert the engine catches each one."""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import shapes  # noqa: E402
from shapes import (  # noqa: E402
    diff_shapes,
    drift_check,
    extract_contract,
    extract_ddl,
    extract_pydantic,
    extract_sqlalchemy,
    extract_typescript,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "step0"


def mutated_copy(source: pathlib.Path, old: str, new: str) -> str:
    text = source.read_text(encoding="utf-8")
    assert old in text, f"fixture drifted: {old!r} not found in {source.name}"
    fd, path = tempfile.mkstemp(suffix=source.suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    return path


class TestExtractors(unittest.TestCase):
    def test_contract(self):
        shapes = extract_contract(FIXTURES / "contract.json")
        self.assertEqual(sorted(shapes), ["Comment", "Project", "Task", "User"])
        role = shapes["User"]["role"]
        self.assertEqual((role["type"], role["enum"]), ("enum", ["admin", "member"]))

    def test_sqlalchemy_reserved_word_column(self):
        shapes = extract_sqlalchemy(FIXTURES / "models.py")
        # attribute is metadata_ but the COLUMN is "metadata" — the reserved-word escape
        self.assertIn("metadata", shapes["tasks"])
        self.assertNotIn("metadata_", shapes["tasks"])
        self.assertEqual(shapes["tasks"]["metadata"]["type"], "json")
        self.assertTrue(shapes["tasks"]["metadata"]["nullable"])

    def test_sqlalchemy_enum_and_fk(self):
        shapes = extract_sqlalchemy(FIXTURES / "models.py")
        self.assertEqual(shapes["users"]["role"]["enum"], ["admin", "member"])
        self.assertEqual(shapes["projects"]["owner_id"]["constraints"]["foreign_key"],
                         "users.id")
        self.assertNotIn("projects", shapes["users"])       # relationships are not columns

    def test_pydantic_read_vs_create(self):
        classes = extract_pydantic(FIXTURES / "schemas.py")
        self.assertIn("id", classes["UserRead"])
        self.assertNotIn("id", classes["UserCreate"])       # partial projection by design
        self.assertEqual(classes["TaskRead"]["status"]["enum"],
                         ["todo", "in_progress", "done"])

    def test_typescript_unions_and_types(self):
        shapes = extract_typescript(FIXTURES / "types.ts")
        self.assertEqual(shapes["User"]["role"]["type"], "enum")        # named string-literal union
        # TS has no uuid/datetime type: a `string` stays `string` (no comment sniffing). The
        # uuid/datetime↔string equivalence is applied at diff time (see TestHonestyRules below).
        self.assertEqual(shapes["User"]["id"]["type"], "string")
        self.assertEqual(shapes["User"]["created_at"]["type"], "string")
        self.assertTrue(shapes["Task"]["due_date"]["nullable"])         # `| null`

    def test_ddl_enums_nullability_fk(self):
        shapes = extract_ddl(FIXTURES / "001_initial.sql")
        self.assertEqual(shapes["users"]["role"]["enum"], ["admin", "member"])
        self.assertFalse(shapes["users"]["email"]["nullable"])
        self.assertTrue(shapes["tasks"]["due_date"]["nullable"])
        self.assertEqual(shapes["comments"]["task_id"]["constraints"]["foreign_key"],
                         "tasks.id")


class TestGreenCase(unittest.TestCase):
    def test_aligned_stack_diffs_clean(self):
        """The preventive payload: generated layers agree with the carrier — zero drift."""
        findings = drift_check(
            str(FIXTURES / "contract.json"),
            sqlalchemy=str(FIXTURES / "models.py"),
            pydantic=str(FIXTURES / "schemas.py"),
            typescript=str(FIXTURES / "types.ts"),
            ddl=str(FIXTURES / "001_initial.sql"),
        )
        self.assertEqual(findings, [])


class TestInjectedDrift(unittest.TestCase):
    """Each mutation is a real vibecoding failure mode; the engine must catch it."""

    def test_frontend_invents_enum_value(self):
        # the classic: frontend checks a role the schema never defined
        path = mutated_copy(FIXTURES / "types.ts",
                            'export type UserRole = "admin" | "member";',
                            'export type UserRole = "admin" | "member" | "superadmin";')
        findings = drift_check(str(FIXTURES / "contract.json"), typescript=path)
        kinds = {(f["field"], f["kind"]) for f in findings}
        self.assertIn(("role", "enum_mismatch"), kinds)

    def test_ddl_nullability_flip(self):
        path = mutated_copy(FIXTURES / "001_initial.sql",
                            "display_name varchar(80)  NOT NULL,",
                            "display_name varchar(80),")
        findings = drift_check(str(FIXTURES / "contract.json"), ddl=path)
        self.assertIn(("display_name", "nullability_mismatch"),
                      {(f["field"], f["kind"]) for f in findings})

    def test_orm_drops_a_column(self):
        path = mutated_copy(FIXTURES / "models.py",
                            '    is_archived: Mapped[bool] = mapped_column(default=False)\n',
                            "")
        findings = drift_check(str(FIXTURES / "contract.json"), sqlalchemy=path)
        self.assertIn(("is_archived", "missing_field"),
                      {(f["field"], f["kind"]) for f in findings})

    def test_dto_type_change(self):
        path = mutated_copy(FIXTURES / "schemas.py",
                            "    priority: int\n",
                            "    priority: str\n")
        findings = drift_check(str(FIXTURES / "contract.json"), pydantic=path)
        self.assertIn(("priority", "type_mismatch"),
                      {(f["field"], f["kind"]) for f in findings})

    def test_extra_field_is_a_finding_not_papered_over(self):
        path = mutated_copy(FIXTURES / "001_initial.sql",
                            "    created_at   timestamptz  NOT NULL DEFAULT now()\n);",
                            "    created_at   timestamptz  NOT NULL DEFAULT now(),\n"
                            "    legacy_flag  boolean      NOT NULL DEFAULT false\n);")
        findings = drift_check(str(FIXTURES / "contract.json"), ddl=path)
        self.assertIn(("legacy_flag", "extra_field"),
                      {(f["field"], f["kind"]) for f in findings})


class TestCarrierlessReconcile(unittest.TestCase):
    """rescue's path when a repo has no shared-types carrier: diff two layers directly."""

    def test_aligned_layers_reconcile_clean(self):
        # step-0 DDL and ORM both match the contract, so they match each other
        findings = shapes.reconcile_layers(
            "ddl", str(FIXTURES / "001_initial.sql"),
            "sqlalchemy", str(FIXTURES / "models.py"))
        hard = [f for f in findings if f["confidence"] != "ambiguous"]
        self.assertEqual(hard, [])

    def test_symmetric_missing_and_extra_entities(self):
        slop = pathlib.Path(__file__).parent / "fixtures" / "slop-repo" / "schema.sql"
        stacks = pathlib.Path(__file__).parent / "fixtures" / "stacks" / "schema.drizzle.ts"
        findings = shapes.reconcile_layers("ddl", str(slop), "drizzle", str(stacks))
        kinds = {(f["entity"], f["kind"]) for f in findings}
        # slop DDL has only users; drizzle has users+tasks → tasks is an extra_entity on side b
        self.assertIn(("tasks", "extra_entity"), kinds)
        # and users still field-diffs: the slop DDL's planted drift shows up
        self.assertIn(("users", "nullability_mismatch"),
                      {(f["entity"], f["kind"]) for f in findings})

    def test_no_pluralization_guess_across_naming_conventions(self):
        # a `users` table and a `User` model do NOT auto-correspond: pluralization is a guess
        # (English-specific, irregular plurals). The deterministic path for that correspondence is
        # the carrier (drift_check maps table→entity explicitly), never a name fold here.
        ddl = pathlib.Path(__file__).parent / "fixtures" / "step0" / "001_initial.sql"
        prisma = pathlib.Path(__file__).parent / "fixtures" / "stacks" / "schema.prisma"
        findings = shapes.reconcile_layers("ddl", str(ddl), "prisma", str(prisma))
        missing = {f["entity"] for f in findings if f["kind"] == "missing_entity"}
        self.assertIn("users", missing)        # honestly unmatched, not folded to User

    def test_same_name_layers_still_reconcile(self):
        # the deterministic case: two layers that share the table name line up exactly
        ddl = pathlib.Path(__file__).parent / "fixtures" / "step0" / "001_initial.sql"
        sqla = pathlib.Path(__file__).parent / "fixtures" / "step0" / "models.py"
        findings = shapes.reconcile_layers("ddl", str(ddl), "sqlalchemy", str(sqla))
        missing = {f["entity"] for f in findings if f["kind"] in ("missing_entity", "extra_entity")}
        self.assertNotIn("users", missing)     # users↔users: exact match, no guessing needed


class TestHonestyRules(unittest.TestCase):
    def test_unknown_type_downgrades_to_ambiguous_note(self):
        ref = {"f": {"name": "f", "type": "string", "nullable": False,
                     "confidence": "extracted"}}
        cand = {"f": {"name": "f", "type": "unknown", "nullable": False,
                      "confidence": "ambiguous"}}
        findings = diff_shapes(ref, cand, "contract", "orm", "X")
        self.assertEqual(findings[0]["kind"], "unresolved")
        self.assertEqual(findings[0]["confidence"], "ambiguous")   # a note, never asserted

    def test_partial_projection_missing_fields_are_not_drift(self):
        ref = extract_contract(FIXTURES / "contract.json")["User"]
        create = extract_pydantic(FIXTURES / "schemas.py")["UserCreate"]
        findings = diff_shapes(ref, create, "contract", "api:create", "User", partial=True)
        self.assertEqual([f for f in findings if f["kind"] == "missing_field"], [])

    def test_client_projection_of_uuid_and_datetime_is_not_drift(self):
        # equivalence table: on a stringly-typed layer, uuid/datetime carry as `string`
        ref = {"id": {"name": "id", "type": "uuid", "nullable": False,
                      "confidence": "extracted"}}
        cand = {"id": {"name": "id", "type": "string", "nullable": False,
                       "confidence": "extracted"}}
        self.assertEqual(diff_shapes(ref, cand, "contract", "client", "X"), [])
        # symmetric: the stringly-typed side may be the reference too (e.g. a TS-vs-DDL reconcile)
        self.assertEqual(diff_shapes(cand, ref, "typescript", "db", "X"), [])
        # …but the same pair on the ORM layer (which HAS a uuid type) IS drift
        self.assertEqual(diff_shapes(ref, cand, "contract", "orm", "X")[0]["kind"],
                         "type_mismatch")


if __name__ == "__main__":
    unittest.main()
