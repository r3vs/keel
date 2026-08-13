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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

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

    def test_contract_tables_requires_explicit_table(self):
        # a table name is a decision — contract_tables errors rather than pluralize the entity name
        import json
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"entities": {"User": {"fields": []}}}, fh)   # no "table"
        with self.assertRaises(ValueError):
            shapes.contract_tables(p)

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

    def test_ddl_real_world_postgres_forms(self):
        # the shapes real Supabase/Postgres DDL uses (validated on plastital_lca): CREATE TABLE IF
        # NOT EXISTS, a `public.` schema prefix, multi-word types, `numeric`, quoted refs.
        sql = """
        CREATE TABLE IF NOT EXISTS public.db_impatti (
            id numeric PRIMARY KEY DEFAULT nextval('db_impatti_id_seq'),
            codice text NOT NULL,
            gwp_t numeric,
            created_at timestamp with time zone DEFAULT (now() AT TIME ZONE 'Europe/Rome'),
            descrizione character varying(255),
            owner_id bigint REFERENCES public."profiles"(id),
            UNIQUE NULLS NOT DISTINCT (codice)
        );
        """
        fd, p = tempfile.mkstemp(suffix=".sql")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(sql)
        out = extract_ddl(p)
        t = out["db_impatti"]                                   # IF NOT EXISTS + public. handled
        self.assertEqual(t["id"]["type"], "float")             # numeric -> float
        self.assertEqual(t["gwp_t"]["type"], "float")
        self.assertEqual(t["created_at"]["type"], "datetime")  # timestamp with time zone (multi-word)
        self.assertEqual(t["descrizione"]["type"], "string")   # character varying(255)
        self.assertEqual(t["descrizione"]["constraints"]["max_length"], 255)
        self.assertFalse(t["codice"]["nullable"])              # NOT NULL
        self.assertTrue(t["gwp_t"]["nullable"])
        self.assertEqual(t["owner_id"]["constraints"]["foreign_key"], "profiles.id")  # quoted ref
        self.assertNotIn("UNIQUE", t)                          # table constraint, not a column


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

    def test_int_float_equivalent_across_js_layer(self):
        # JS/TS has one `number` — int↔float across that boundary is not drift (the client can
        # neither express nor get wrong the distinction). Real repos hit this on every float field.
        flt = {"x": {"name": "x", "type": "float", "nullable": False, "confidence": "extracted"}}
        i = {"x": {"name": "x", "type": "int", "nullable": False, "confidence": "extracted"}}
        self.assertEqual(diff_shapes(flt, i, "api", "client", "E"), [])
        self.assertEqual(diff_shapes(i, flt, "typescript", "api", "E"), [])      # symmetric
        # but int↔float between two server layers (which DO distinguish) IS drift
        self.assertEqual(diff_shapes(flt, i, "contract", "orm", "E")[0]["kind"], "type_mismatch")


if __name__ == "__main__":
    unittest.main()


class TestElectedCorrespondence(unittest.TestCase):
    """The third way, for a repo with no carrier AND no shared naming between its layers.

    `reconcile_layers` matching on the name is right and, on a real codebase, can leave you with
    nothing usable: 74 tables named `cert_lotti_registrati` against models named `LottoRegistrato`
    report as 74 missing and 377 extra. Honest, useless, and it pushes the operator into doing the
    comparison by hand outside the tool. So the comparison comes inside — as a PROPOSAL, which is
    the only form a similarity score is allowed to take here.
    """

    DDL = pathlib.Path(__file__).parent / "fixtures" / "step0" / "001_initial.sql"
    PRISMA = pathlib.Path(__file__).parent / "fixtures" / "stacks" / "schema.prisma"

    def test_pairs_are_proposed_by_field_overlap_not_by_name(self):
        cands = shapes.propose_correspondence("ddl", str(self.DDL), "prisma", str(self.PRISMA))
        pairs = {(c["a"], c["b"]) for c in cands}
        self.assertIn(("users", "User"), pairs,
                      "identical field sets under different names must still be proposable")
        for c in cands:
            self.assertEqual(c["status"], "proposed",
                             "a similarity score may propose; it may never be a finding")
            self.assertTrue(c["shared_fields"], "a candidate must carry the evidence it rests on")

    def test_one_pairing_per_entity(self):
        cands = shapes.propose_correspondence("ddl", str(self.DDL), "prisma", str(self.PRISMA))
        self.assertEqual(len({c["a"] for c in cands}), len(cands))
        self.assertEqual(len({c["b"] for c in cands}), len(cands))

    def test_nothing_is_proposed_below_the_floor(self):
        self.assertEqual(
            shapes.propose_correspondence("ddl", str(self.DDL), "prisma", str(self.PRISMA),
                                          min_overlap=1.01), [])

    def test_an_elected_pairing_makes_the_diff_deterministic_again(self):
        before = shapes.reconcile_layers("ddl", str(self.DDL), "prisma", str(self.PRISMA))
        self.assertIn("users", {f["entity"] for f in before if f["kind"] == "missing_entity"})

        after = shapes.reconcile_layers("ddl", str(self.DDL), "prisma", str(self.PRISMA),
                                        correspondence={"users": "User"})
        kinds = {(f["entity"], f["kind"]) for f in after}
        self.assertNotIn(("users", "missing_entity"), kinds,
                         "a declared pairing must beat the name match")
        self.assertNotIn(("User", "extra_entity"), kinds, "and must consume the other side too")
        # every other entity is left exactly as it was: the map declares pairs, it does not fold names
        self.assertIn("projects", {f["entity"] for f in after if f["kind"] == "missing_entity"})


def write(suffix: str, text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class TestRefusesToDiffNothing(unittest.TestCase):
    """`[]` used to mean both "these layers agree" and "I parsed neither".

    Measured, not imagined (`docs/measurements.md`, `Netflix/dispatch`): 65 model files, 0 entities
    off the ORM side, 0 findings, and the only reason that run could be told apart from a clean bill
    of health is that the measurement script happened to print the entity counts beside it. An empty
    diff over an empty extraction is the failure mode most easily read as success, so the engine
    refuses it — the way `_treesitter_only` refuses rather than returning `{}`.
    """

    EMPTY_SQL = "-- a migration that creates nothing\nSELECT 1;\n"

    def test_an_empty_side_refuses_instead_of_reporting_agreement(self):
        empty = write(".sql", self.EMPTY_SQL)
        with self.assertRaises(shapes.EmptyExtraction) as caught:
            shapes.reconcile_layers("ddl", empty, "sqlalchemy", str(FIXTURES / "models.py"))
        self.assertEqual([s["layer"] for s in caught.exception.sides], ["ddl"])
        self.assertIn("CREATE TABLE", caught.exception.sides[0]["expects"])
        self.assertIn(empty, str(caught.exception))

    def test_both_sides_empty_names_both(self):
        a, b = write(".sql", self.EMPTY_SQL), write(".sql", self.EMPTY_SQL)
        with self.assertRaises(shapes.EmptyExtraction) as caught:
            shapes.reconcile_layers("ddl", a, "ddl", b)
        self.assertEqual(len(caught.exception.sides), 2, "a refusal must name every empty side")

    def test_a_real_clean_diff_still_returns_no_findings(self):
        """The distinction is the point: refusing must not swallow the case it exists to separate
        from. Two aligned layers with entities on both sides still report zero drift."""
        findings = shapes.reconcile_layers(
            "ddl", str(FIXTURES / "001_initial.sql"), "sqlalchemy", str(FIXTURES / "models.py"))
        self.assertEqual([f for f in findings if f["confidence"] != "ambiguous"], [])

    def test_propose_correspondence_refuses_on_the_same_ground(self):
        # zero candidates from zero entities is the same lie as zero findings from zero entities
        with self.assertRaises(shapes.EmptyExtraction):
            shapes.propose_correspondence("ddl", write(".sql", self.EMPTY_SQL),
                                          "sqlalchemy", str(FIXTURES / "models.py"))

    def test_an_empty_carrier_refuses_too(self):
        # drift_check's carrier IS the reference; "no drift against nothing" is not a green build
        carrier = write(".json", '{"entities": {}}')
        with self.assertRaises(shapes.EmptyExtraction):
            shapes.drift_check(carrier, ddl=str(FIXTURES / "001_initial.sql"))

    def test_a_layer_that_read_nothing_refuses_even_with_a_good_carrier(self):
        """The half that was missing, and it was the half the playbooks reach for FIRST.

        `drift_check` refused an empty CARRIER and nothing else, while every layer below it is
        matched by `if table in shapes` / `if entity in shapes` — a membership test that fails
        closed and silently over an extractor that returned `{}`. So the carrier-anchored tool
        answered `[]`, and `mcp:contract_diff` answered `{"findings": []}` under a description that
        calls an empty list the evidence of zero drift, over a layer nothing had read: the measured
        `Netflix/dispatch` failure arriving through the other door.
        """
        carrier = str(FIXTURES / "contract.json")
        unreadable = {
            "sqlalchemy": write(".py", "# no models here\nX = 1\n"),
            "pydantic": write(".py", "# no DTOs here\nX = 1\n"),
            "typescript": write(".ts", "// only a comment\n"),
            "graphql": write(".graphql", "input UserWhereInput { id: ID }\n"),
            "drizzle": write(".ts", "// no pgTable here\n"),
        }
        for layer, path in unreadable.items():
            with self.subTest(layer=layer):
                with self.assertRaises(shapes.EmptyExtraction) as caught:
                    shapes.drift_check(carrier, **{layer: path})
                sides = [s["layer"] for s in caught.exception.sides]
                self.assertEqual(sides, [layer], f"the refusal must name {layer}, not the carrier")
                self.assertIn(path, str(caught.exception))

    def test_one_refusal_names_every_empty_layer_it_was_handed(self):
        """Extraction happens up front for exactly this: an operator fixing extraction wants the
        whole list, not whichever branch happened to run first."""
        with self.assertRaises(shapes.EmptyExtraction) as caught:
            shapes.drift_check(str(FIXTURES / "contract.json"),
                               sqlalchemy=write(".py", "X = 1\n"),
                               typescript=write(".ts", "// nothing\n"))
        self.assertEqual(sorted(s["layer"] for s in caught.exception.sides),
                         ["sqlalchemy", "typescript"])

    def test_a_populated_layer_still_diffs(self):
        """The refusal must not swallow the case it exists to separate from — the carrier door's
        own version of `test_a_real_clean_diff_still_returns_no_findings`."""
        findings = shapes.drift_check(str(FIXTURES / "contract.json"),
                                      ddl=str(FIXTURES / "001_initial.sql"))
        self.assertIsInstance(findings, list)

    def test_a_file_that_does_not_parse_is_not_an_idiom_we_do_not_read(self):
        """`_ModuleBatch` degrades over a NEIGHBOUR, and that guarantee used to cover the file the
        caller named too — so an unparsable models.py surfaced as `0 entities (expected: declarative
        classes with a __tablename__ …)`, which is a true sentence about the wrong problem. Same
        flattening as an empty diff read as agreement, one level down."""
        garbage = write(".py", "this is ((( not python\n")
        for extractor in (shapes.extract_sqlalchemy, shapes.extract_pydantic):
            with self.subTest(extractor=extractor.__name__):
                with self.assertRaises(SyntaxError):
                    extractor(garbage)

    def test_a_neighbour_that_does_not_parse_still_degrades(self):
        """The other side of the same line: somebody else's syntax error one import hop away must
        not take down the file the operator actually asked about."""
        root = pathlib.Path(write(".py", "")).parent / f"nb_{os.getpid()}"
        root.mkdir(exist_ok=True)
        (root / "__init__.py").write_text("", encoding="utf-8")
        (root / "broken.py").write_text("not ((( python\n", encoding="utf-8")
        main = root / "dto.py"
        main.write_text("from pydantic import BaseModel\nfrom .broken import Missing\n\n"
                        "class UserRead(BaseModel):\n    id: str\n", encoding="utf-8")
        self.assertEqual(list(shapes.extract_pydantic(main)), ["UserRead"])

    def test_an_absolute_import_does_not_reach_past_the_project_root(self):
        """The ancestor walk used to run to the filesystem root, so `from dispatch.models import
        DispatchBase` matched the FIRST `dispatch/models.py` any ancestor happened to hold —
        a sibling checkout under a shared `~/src`, a container's `/app` beside site-packages. The
        cost is not a missing extraction but a wrong one: somebody else's base class is grafted in
        and its fields are reported with `confidence: extracted`, the one label that means *read*.
        """
        outer = pathlib.Path(tempfile.mkdtemp())
        foreign = outer / "dispatch"
        foreign.mkdir()
        (foreign / "__init__.py").write_text("", encoding="utf-8")
        (foreign / "models.py").write_text(
            "from pydantic import BaseModel\n\n\n"
            "class DispatchBase(BaseModel):\n    leaked: str\n", encoding="utf-8")

        project = outer / "project"
        (project / "app").mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname = 'p'\n", encoding="utf-8")
        dto = project / "app" / "dto.py"
        dto.write_text("from dispatch.models import DispatchBase\n\n\n"
                       "class UserRead(DispatchBase):\n    id: str\n", encoding="utf-8")

        out = shapes.extract_pydantic(str(dto))
        self.assertNotIn("leaked", out.get("UserRead", {}),
                         "a base class from OUTSIDE the project was resolved and its fields "
                         "reported as extracted from this file")

        # ...and the bound did not cost the case it exists inside: the same absolute import, with
        # the module where the project actually keeps it, still resolves.
        local = project / "dispatch"
        local.mkdir()
        (local / "__init__.py").write_text("", encoding="utf-8")
        (local / "models.py").write_text(
            "from pydantic import BaseModel\n\n\n"
            "class DispatchBase(BaseModel):\n    tenant_id: str\n", encoding="utf-8")
        out = shapes.extract_pydantic(str(dto))
        self.assertIn("tenant_id", out["UserRead"],
                      "the project's own absolute import stopped resolving")

    def test_with_no_project_marker_anywhere_the_reach_is_unchanged(self):
        """Degrade gracefully: a loose file under no project must resolve exactly as far as it did
        before, or a first-time user pointing the engine at a scratch directory silently extracts
        less — a bound that turns *no project here* into *resolve nothing*."""
        loose = pathlib.Path(tempfile.mkdtemp()) / "a" / "b" / "c.py"
        loose.parent.mkdir(parents=True)
        loose.write_text("", encoding="utf-8")
        self.assertEqual(shapes._project_ancestors(loose), list(loose.parents))

    def test_the_marker_directory_itself_stays_in_the_walk(self):
        """A src-layout project imports its top package by the name of a directory sitting BESIDE
        `pyproject.toml`, so an exclusive bound would break the common case it was written for."""
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "pyproject.toml").write_text("", encoding="utf-8")
        (root / "pkg").mkdir()
        leaf = root / "pkg" / "mod.py"
        leaf.write_text("", encoding="utf-8")
        self.assertEqual(shapes._project_ancestors(leaf), [root / "pkg", root])

    def test_every_extractor_states_its_preconditions(self):
        """An enumeration that asserts a completeness it does not have is this repo's signature
        defect. A stack in EXTRACTORS with no `_EXTRACTOR_EXPECTS` entry refuses with a generic
        sentence, which tells the operator nothing about why their file read empty."""
        missing = sorted(set(shapes.EXTRACTORS) - set(shapes._EXTRACTOR_EXPECTS))
        self.assertEqual(missing, [], f"no stated preconditions for: {missing}")


class TestSQLAlchemyOneDotX(unittest.TestCase):
    """The 1.x idiom, and the missing `__tablename__` — both measured on `Netflix/dispatch`:
    653 `= Column(` occurrences, 0 `mapped_column(`, 0 `__tablename__`, and 0 entities extracted."""

    SOURCE = """
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Enum
from .base import Base


class TimeStampMixin(object):
    created_at = Column(DateTime)


class Legacy(Base, TimeStampMixin):
    id = Column(Integer, primary_key=True)
    title = Column(String(80), nullable=False)
    note = Column(String)
    owner_id = Column(Integer, ForeignKey("owner.id"))
    rank = Column(Integer, nullable=True)
    tags = relationship("Tag", backref="legacy")


class Declared(Base):
    __tablename__ = "declared_table"
    id = Column(Integer, primary_key=True)


class NotATable(object):
    __abstract__ = True
    ghost = Column(String)


class JustADTO(SomethingElse):
    title: str
    count: int
"""

    def setUp(self):
        self.out = shapes.extract_sqlalchemy(write(".py", self.SOURCE))

    def test_plain_assign_columns_are_read(self):
        legacy = self.out["Legacy"]
        self.assertEqual(legacy["id"]["type"], "int")
        self.assertTrue(legacy["id"]["constraints"]["primary_key"])
        self.assertFalse(legacy["id"]["nullable"])                  # a primary key is never null
        self.assertEqual(legacy["title"]["constraints"]["max_length"], 80)
        self.assertFalse(legacy["title"]["nullable"])               # nullable=False
        self.assertTrue(legacy["note"]["nullable"])                 # 1.x default: nullable
        self.assertEqual(legacy["owner_id"]["constraints"]["foreign_key"], "owner.id")
        self.assertNotIn("tags", legacy)                            # a relationship is not a column

    def test_a_missing_tablename_keys_by_class_name_and_says_so(self):
        self.assertIn("Legacy", self.out)
        meta = self.out.entity_meta["Legacy"]
        self.assertEqual(meta["key_source"], "class_name")
        self.assertIn("__tablename__", meta["why"])
        # and a DECLARED name is still the key, with no provenance note attached to it
        self.assertIn("declared_table", self.out)
        self.assertNotIn("declared_table", self.out.entity_meta)

    def test_no_table_name_is_ever_derived_from_the_class_name(self):
        """`Legacy` → `legacy`/`legacies` is the pluralization guess `reconcile_layers` refuses
        elsewhere, and the rule differs per project. The key is the class name AS WRITTEN."""
        self.assertNotIn("legacy", self.out)
        self.assertNotIn("legacies", self.out)

    def test_mixin_columns_belong_to_the_table(self):
        # SQLAlchemy's own semantics: a declarative mixin's columns ARE the mapped table's columns
        self.assertIn("created_at", self.out["Legacy"])

    def test_annotated_classes_that_are_not_mapped_are_not_tables(self):
        """The fallback's precondition. In dispatch the ORM model and its DTOs share one FILE, so a
        rule of "has annotated fields" would turn every DTO into a table."""
        self.assertNotIn("JustADTO", self.out)
        self.assertNotIn("NotATable", self.out)                     # __abstract__ = True

    def test_a_computed_tablename_is_not_a_declared_one(self):
        """`__tablename__ = PREFIX + "users"` is an expression, and `ast.unparse(...).strip("'\\"")`
        turned it into the entity key `PREFIX + 'users` — mangled by the strip, carrying no
        `entity_meta`, i.e. presented as a name this extractor READ. It also made the extraction
        non-empty, so a models file whose classes all compute their table name defeated the
        `EmptyExtraction` refusal with one fabricated entity per class."""
        out = shapes.extract_sqlalchemy(write(".py", """
from sqlalchemy import Column, String
PREFIX = "app_"
TABLES = {"thing": "things"}


class User(Base):
    __tablename__ = PREFIX + "users"
    name = Column(String)


class Order(Base):
    __tablename__ = f"{PREFIX}orders"
    ref = Column(String)


class Thing(Base):
    __tablename__ = TABLES["thing"]
    label = Column(String)
"""))
        self.assertEqual(sorted(out), ["Order", "Thing", "User"], "keyed by class name, not by the "
                                                                  "text of an expression")
        for entity in out:
            with self.subTest(entity=entity):
                self.assertEqual(out.entity_meta[entity]["key_source"], "class_name")
                self.assertIn("EXPRESSION", out.entity_meta[entity]["why"])
        self.assertFalse([k for k in out if "+" in k or "'" in k or "{" in k],
                         "an unparsed expression reached the caller as an entity name")

    def test_a_file_of_only_computed_tablenames_does_not_defeat_the_refusal(self):
        models = write(".py", "class User(Base):\n    __tablename__ = PREFIX + 'users'\n")
        with self.assertRaises(shapes.EmptyExtraction):
            shapes.reconcile_layers("sqlalchemy", models, "ddl", str(FIXTURES / "001_initial.sql"))

    def test_the_leftmost_base_wins_a_column_two_of_them_declare(self):
        """Python resolves `Thing(TimestampMixin, SoftDeleteMixin)` by MRO and MRO is leftmost-first;
        merging the bases left-to-right with `dict.update` let the LAST one win, so the diff was
        keyed on the type SQLAlchemy does not use. If mixin columns are the table's columns because
        that is SQLAlchemy's own semantics, the order is part of the semantics."""
        out = shapes.extract_sqlalchemy(write(".py", """
from sqlalchemy import Column, Integer, String


class TimestampMixin:
    tag = Column(String)


class SoftDeleteMixin:
    tag = Column(Integer)


class Thing(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "things"
    id = Column(Integer, primary_key=True)
"""))
        self.assertEqual(out["things"]["tag"]["type"], "string")

    def test_the_two_idioms_agree_on_the_same_schema(self):
        """A 1.x model and its 2.0 rewrite must extract to the same shapes, or the new path is a
        second engine rather than a second spelling."""
        old = shapes.extract_sqlalchemy(write(".py", """
from sqlalchemy import Column, Integer, String
class Thing(Base):
    __tablename__ = "things"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    note = Column(String)
"""))
        new = shapes.extract_sqlalchemy(write(".py", """
from sqlalchemy.orm import Mapped, mapped_column
class Thing(Base):
    __tablename__ = "things"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    note: Mapped[Optional[str]] = mapped_column(String)
"""))
        self.assertEqual(old, new)


class TestPydanticBaseChain(unittest.TestCase):
    """`131 classes inherit DispatchBase, 4 inherit BaseModel directly` — the old check saw 3%."""

    def test_a_project_local_base_counts(self):
        out = shapes.extract_pydantic(write(".py", """
from pydantic import BaseModel


class ProjectBase(BaseModel):
    id: int


class UserRead(ProjectBase):
    email: str
"""))
        self.assertIn("UserRead", out)
        self.assertEqual(out["UserRead"]["email"]["type"], "string")
        self.assertIn("id", out["UserRead"], "an inherited field is still a field")

    def test_a_base_one_import_hop_away_resolves(self):
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "pkg" / "api").mkdir(parents=True)
        (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (root / "pkg" / "base.py").write_text(
            "from pydantic import BaseModel\n\n\nclass ProjectBase(BaseModel):\n"
            "    created_at: datetime\n", encoding="utf-8")
        dto = root / "pkg" / "api" / "models.py"
        dto.write_text("from pkg.base import ProjectBase\n\n\nclass UserRead(ProjectBase):\n"
                       "    email: str\n", encoding="utf-8")
        out = shapes.extract_pydantic(dto)
        self.assertIn("UserRead", out)
        self.assertEqual(out["UserRead"]["created_at"]["type"], "datetime",
                         "fields inherited across the hop come with it")

    def test_a_chain_that_leaves_the_batch_is_not_guessed_at(self):
        """The limit is stated and enforced: a base this extractor could not READ is not accepted
        for being named like one. `SomethingBase` looks exactly like a DTO base and is not."""
        out = shapes.extract_pydantic(write(".py", """
from somewhere.far.away import SomethingBase


class UserRead(SomethingBase):
    email: str
"""))
        self.assertEqual(dict(out), {})

    def test_a_field_argument_that_is_not_a_literal_does_not_kill_the_file(self):
        """`Field(validation_alias=AliasChoices(...))` is what pydantic's own docs write and
        `Field(max_length=MAX_LEN)` is what a project with a constants module writes. Both are
        non-literal nodes, and `ast.literal_eval` raises `ValueError` on every one of them — so
        reading a constraint used to take the whole file down, from a message naming no file and a
        line number in a module the caller never passed. An unreadable constraint is simply not
        reported; the field still is."""
        out = shapes.extract_pydantic(write(".py", """
from pydantic import AliasChoices, BaseModel, Field

MAX_LEN = 40


class UserRead(BaseModel):
    email: str = Field(validation_alias=AliasChoices("email", "emailAddress"))
    name: str = Field(max_length=MAX_LEN)
    slug: str = Field(max_length=12)
"""))
        self.assertEqual(sorted(out["UserRead"]), ["email", "name", "slug"])
        self.assertEqual(out["UserRead"]["slug"]["constraints"], {"max_length": 12},
                         "a literal one is still read")
        self.assertIsNone(out["UserRead"]["name"].get("constraints"))

    def test_an_unreadable_constraint_in_a_BASE_does_not_kill_the_file_either(self):
        """The base-chain resolver made this reachable from a neighbour the operator never named:
        the crash came out of a file that is not the one on the command line."""
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "app").mkdir()
        (root / "app" / "__init__.py").write_text("", encoding="utf-8")
        (root / "app" / "base.py").write_text(
            "from pydantic import AliasChoices, BaseModel, Field\n\n\n"
            "class ProjectBase(BaseModel):\n"
            '    email: str = Field(validation_alias=AliasChoices("email", "emailAddress"))\n',
            encoding="utf-8")
        dto = root / "app" / "schemas.py"
        dto.write_text("from app.base import ProjectBase\n\n\nclass UserRead(ProjectBase):\n"
                       "    id: str\n", encoding="utf-8")
        out = shapes.extract_pydantic(dto)
        self.assertEqual(sorted(out["UserRead"]), ["email", "id"])

    def test_the_leftmost_base_wins_a_field_two_of_them_declare(self):
        """`typing.get_type_hints` on the equivalent classes answers `Left`'s annotation, because
        pydantic builds its fields off the MRO. Merging bases left-to-right answered `Right`'s."""
        out = shapes.extract_pydantic(write(".py", """
from pydantic import BaseModel


class Left(BaseModel):
    status: int


class Right(BaseModel):
    status: str


class Child(Left, Right):
    pass
"""))
        self.assertEqual(out["Child"]["status"]["type"], "int")

    def test_a_collection_field_is_undecided_rather_than_a_sentinel(self):
        """`relationship` is an internal marker, not one of CANONICAL. It used to reach the diff as
        `sqlalchemy=json vs pydantic=relationship` — a sentinel printed to an operator as a type."""
        out = shapes.extract_pydantic(write(".py", """
from pydantic import BaseModel
from typing import List


class UserRead(BaseModel):
    tags: List[str]
"""))
        self.assertEqual(out["UserRead"]["tags"]["type"], "unknown")
        self.assertEqual(out["UserRead"]["tags"]["confidence"], "ambiguous")


class TestGraphQLIdIsOpaque(unittest.TestCase):
    """117 of keystone's 130 `type_mismatch` findings — 90% of the class — were a Prisma
    `String @id`/`Int @id` under a GraphQL `ID!`."""

    def test_an_id_does_not_assert_against_string_int_or_uuid(self):
        gql = {"id": {"name": "id", "type": "uuid", "nullable": False, "confidence": "extracted"}}
        for other in ("string", "int", "uuid"):
            db = {"id": {"name": "id", "type": other, "nullable": False,
                         "confidence": "extracted"}}
            self.assertEqual(diff_shapes(db, gql, "prisma", "graphql", "User"), [],
                             f"prisma={other} under a GraphQL ID is not drift")
            self.assertEqual(diff_shapes(gql, db, "graphql", "prisma", "User"), [],
                             "and the rule is symmetric")

    def test_it_still_asserts_against_everything_else(self):
        gql = {"id": {"name": "id", "type": "uuid", "nullable": False, "confidence": "extracted"}}
        for other in ("bool", "json", "datetime"):
            db = {"id": {"name": "id", "type": other, "nullable": False,
                         "confidence": "extracted"}}
            self.assertEqual(diff_shapes(db, gql, "prisma", "graphql", "User")[0]["kind"],
                             "type_mismatch", f"{other} vs ID is still drift")

    def test_the_rule_rests_on_id_being_the_only_uuid_in_the_graphql_map(self):
        """The rule reads `uuid on the GraphQL side` and means `an ID field`. That equivalence is
        exact only while `ID` is the sole GraphQL type either backend canonicalizes to `uuid` — so
        this fails the day a second one is added, rather than silently widening the rule."""
        self.assertEqual([k for k, v in shapes._GQL_TYPES.items() if v == "uuid"], ["ID"])
        # Removed again on the way out. A test that widens `sys.path` and leaves it widened decides
        # what every test after it imports, and the ordering that exposes it is unittest's, not
        # anybody's intent — which makes the failure land somewhere else entirely.
        runtime = os.path.join(os.path.dirname(__file__), "..", "src", "runtime")
        sys.path.insert(0, runtime)
        self.addCleanup(lambda: sys.path.remove(runtime) if runtime in sys.path else None)
        import treesitter_extract
        ts_map = treesitter_extract.STACKS["graphql"]["type_map"]
        self.assertEqual([k for k, v in ts_map.items() if v == "uuid"], ["ID"],
                         "the tree-sitter backend is the PRIMARY path; it must agree")

    def test_graphql_does_not_inherit_the_js_number_equivalence(self):
        """GraphQL has `Int` and `Float`. The equivalence table used to be one tuple, so adding
        graphql to it for `ID` would have bought a numeric equivalence GraphQL does not have."""
        i = {"n": {"name": "n", "type": "int", "nullable": False, "confidence": "extracted"}}
        f = {"n": {"name": "n", "type": "float", "nullable": False, "confidence": "extracted"}}
        self.assertEqual(diff_shapes(i, f, "prisma", "graphql", "E")[0]["kind"], "type_mismatch")
        self.assertEqual(diff_shapes(i, f, "prisma", "client", "E"), [],
                         "…while the JS client, which has one `number`, still gets it")

    def test_a_string_timestamp_over_the_graphql_boundary_is_not_drift(self):
        """The half of the table entry that IS the usual string projection: an SDL has no native
        datetime either, so a timestamp typed `String` carries the same as `uuid`/`datetime` do to
        a TS client."""
        db = {"at": {"name": "at", "type": "datetime", "nullable": False,
                     "confidence": "extracted"}}
        sdl = {"at": {"name": "at", "type": "string", "nullable": False,
                      "confidence": "extracted"}}
        self.assertEqual(diff_shapes(db, sdl, "prisma", "graphql", "E"), [])


class TestClassificationNotSuppression(unittest.TestCase):
    """Two noise classes get a marker, not a filter: the raw counts stay derivable."""

    PRISMA = """
model User {
  id       String @id @default(uuid())
  email    String
  authorId String
}
"""
    SDL = """
type User {
  id: ID!
  email: String!
  author: Author!
}

type Query {
  users: [User]
}

type Mutation {
  createUser: User
}
"""

    def setUp(self):
        self.findings = shapes.reconcile_layers(
            "prisma", write(".prisma", self.PRISMA), "graphql", write(".graphql", self.SDL))

    def test_the_operation_roots_are_tagged_and_still_reported(self):
        tagged = {f["entity"] for f in self.findings if f.get("structural_tier")}
        self.assertEqual(tagged, {"Query", "Mutation"})
        for f in self.findings:
            if f["entity"] in ("Query", "Mutation"):
                self.assertEqual(f["kind"], "extra_entity",
                                 "classification must not change or drop the finding")
                self.assertEqual(f["structural_tier"], "operation_root")

    def test_nothing_else_is_tagged_structural(self):
        """The vendor tier (keystone's 1,098 `Keystone*Meta` types) is equally structural and is
        deliberately NOT encoded: only the GraphQL spec's own root names are."""
        self.assertIsNone(next((f for f in self.findings
                                if f["entity"] == "User" and f.get("structural_tier")), None))

    def test_the_fk_scalar_and_its_relation_object_carry_one_stem(self):
        pairs = {(f["field"], f.get("relation_role")) for f in self.findings
                 if f.get("relation_pair") == "author"}
        self.assertEqual(pairs, {("authorId", "fk_scalar"), ("author", "relation_object")})
        kinds = {f["field"]: f["kind"] for f in self.findings if f.get("relation_pair")}
        self.assertEqual(kinds, {"authorId": "missing_field", "author": "extra_field"},
                         "both survive, in their own kinds — folding is the reader's decision")

    def test_the_pairing_is_symmetric_over_the_snake_spelling(self):
        ref = {"banner_id": {"name": "banner_id", "type": "uuid", "nullable": True,
                             "confidence": "extracted"}}
        cand = {"banner": {"name": "banner", "type": "json", "nullable": True,
                           "confidence": "extracted"}}
        for a, b in ((ref, cand), (cand, ref)):
            tagged = {f["field"]: f["relation_pair"]
                      for f in diff_shapes(a, b, "db", "api", "Post") if "relation_pair" in f}
            self.assertEqual(tagged, {"banner_id": "banner", "banner": "banner"})

    def test_an_unrelated_absence_is_left_alone(self):
        ref = {"legacy_flag": {"name": "legacy_flag", "type": "bool", "nullable": True,
                               "confidence": "extracted"}}
        findings = diff_shapes(ref, {}, "db", "api", "Post")
        self.assertNotIn("relation_pair", findings[0])


class TestDerivedEntityKeysTravelWithTheFinding(unittest.TestCase):
    def test_a_finding_says_when_the_entity_name_was_derived(self):
        orm = write(".py", """
from sqlalchemy import Column, Integer, String


class Widget(Base):
    id = Column(Integer, primary_key=True)
    label = Column(String)
""")
        dto = write(".py", """
from pydantic import BaseModel


class Widget(BaseModel):
    id: int
    label: str
    extra: str
""")
        findings = shapes.reconcile_layers("sqlalchemy", orm, "pydantic", dto)
        self.assertTrue(findings, "the two agree on the NAME, so the fields get diffed")
        for f in findings:
            self.assertEqual(f["entity_key_source"], {"sqlalchemy": "class_name"},
                             "a diff keyed on a derived name says so, on every finding it emits")
