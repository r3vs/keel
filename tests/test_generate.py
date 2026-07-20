"""Tests for runtime/generate.py — greenfield's contract-propagation payload.

The central test is the ROUND-TRIP: generate all four layers from a contract, then run
runtime/shapes.drift_check over them. A correct generator produces layers that are aligned by
construction, so the diff must be empty. This is greenfield's step-0 STRONG verdict turned into
an executable invariant — if a future edit to a generator breaks alignment, this test fails.

(Syntactic validity of the generated Python/TS — ORM builds, DTOs validate, tsc --strict passes —
was checked once by hand during step-0; here we assert the structural alignment, which is what a
generator can regress on without anyone noticing.)
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import generate  # noqa: E402
import shapes  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "step0"


class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self.contract_path = str(FIXTURES / "contract.json")
        self.contract = generate.Contract.load(self.contract_path)

    def _write(self, outputs) -> dict:
        import tempfile
        d = pathlib.Path(tempfile.mkdtemp())
        paths = {}
        for layer, text in outputs.items():
            p = d / generate._FILENAMES[layer]
            p.write_text(text, encoding="utf-8", newline="\n")
            paths[layer] = str(p)
        return paths

    def test_generate_all_layers_round_trips_clean(self):
        paths = self._write(generate.generate_all(self.contract))
        findings = shapes.drift_check(
            self.contract_path,
            ddl=paths["ddl"], sqlalchemy=paths["sqlalchemy"],
            pydantic=paths["pydantic"], typescript=paths["typescript"],
        )
        self.assertEqual(findings, [], f"generated layers drifted from the contract: {findings}")

    def test_each_layer_round_trips_independently(self):
        outputs = generate.generate_all(self.contract)
        paths = self._write(outputs)
        for layer in ("ddl", "sqlalchemy", "pydantic", "typescript"):
            findings = shapes.drift_check(self.contract_path, **{layer: paths[layer]})
            self.assertEqual(findings, [], f"{layer} drifted: {findings}")

    def test_generated_ddl_has_enums_and_fks(self):
        ddl = generate.generate_ddl(self.contract)
        self.assertIn("CREATE TYPE user_role AS ENUM ('admin', 'member');", ddl)
        self.assertIn("CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done');", ddl)
        self.assertIn("REFERENCES users(id) ON DELETE CASCADE", ddl)
        self.assertIn("gen_random_uuid()", ddl)

    def test_generated_orm_handles_reserved_word_column(self):
        orm = generate.generate_sqlalchemy(self.contract)
        # `metadata` is reserved on the Declarative Base → aliased attribute + explicit column
        self.assertIn('metadata_: Mapped', orm)
        self.assertIn('mapped_column("metadata"', orm)
        # enum stored by value, not member name (friction #2)
        self.assertIn("values_callable", orm)

    def test_generated_pydantic_create_omits_pk_and_server_defaults(self):
        dto = generate.generate_pydantic(self.contract)
        # UserCreate must not contain id or created_at
        create_block = dto.split("class UserCreate")[1].split("class UserRead")[0]
        self.assertNotIn("id:", create_block)
        self.assertNotIn("created_at", create_block)
        self.assertIn("email", create_block)

    def test_generated_ts_uses_string_literal_unions_and_brands(self):
        ts = generate.generate_typescript(self.contract)
        self.assertIn('export type UserRole = "admin" | "member";', ts)
        self.assertIn("id: string; // uuid", ts)
        self.assertIn("created_at: string; // ISO datetime", ts)

    def test_generated_matches_committed_step0_fixtures_semantically(self):
        # not byte-identical (formatting differs), but must extract to the same shapes as the
        # hand-written, machine-validated step-0 fixtures
        gen = self._write(generate.generate_all(self.contract))
        gen_ddl = shapes.extract_ddl(gen["ddl"])
        fix_ddl = shapes.extract_ddl(str(FIXTURES / "001_initial.sql"))
        for table in fix_ddl:
            self.assertIn(table, gen_ddl)
            for field, shape in fix_ddl[table].items():
                self.assertEqual(gen_ddl[table][field]["type"], shape["type"],
                                 f"{table}.{field} type differs from the step-0 fixture")


class TestCarrierChooser(unittest.TestCase):
    def test_ts_monorepo_picks_shared_types(self):
        self.assertEqual(
            generate.choose_carrier({"api": "ts-express", "client": "typescript-react"}),
            "shared-types")

    def test_polyglot_picks_openapi(self):
        self.assertEqual(
            generate.choose_carrier({"api": "fastapi-python", "client": "typescript"}),
            "openapi")

    def test_rpc_decision_picks_protobuf(self):
        self.assertEqual(
            generate.choose_carrier({"api": "go-grpc", "client": "protobuf-ts"}),
            "protobuf")


class TestExplicitTable(unittest.TestCase):
    def test_generation_requires_explicit_table(self):
        # the table name is a decision the contract declares — generation errors rather than
        # guess it by pluralizing the entity name (the symmetric twin of contract_tables).
        import json
        import tempfile
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"entities": {"User": {"fields": [
                {"name": "id", "type": "uuid", "nullable": False}]}}}, fh)   # no "table"
        contract = generate.Contract.load(p)
        with self.assertRaises(ValueError):
            generate.generate_ddl(contract)


if __name__ == "__main__":
    unittest.main()
