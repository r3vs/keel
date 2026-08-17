"""The run register (v0.32): a module was applied, and to what.

The gap it closes is one the dispatch gate cannot reach. A gate proves a step is **reachable**; for
a `type: judgment` module nothing observed that it was ever **taken**, because its engine is an agent
and agents leave no report on disk. `design-taste` finding nothing and `design-taste` never running
produced byte-identical ledgers.

So what is asserted here is mostly what the record **refuses**, because that is where the design is.
A flag saying `applied: true` would satisfy any test that only checked round-tripping, and it would
be worthless: an agent that skipped the work writes it just as happily, and nothing can contradict
it. The refusals are what make the record contradictable — named targets, the call that produced
them, and a commit to re-run against.

The last leg is the one the register exists for and the easiest to leave out: the **empty** run.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "runtime"))

import coverage  # noqa: E402
import ledger  # noqa: E402


def _ledger() -> ledger.Ledger:
    return ledger.Ledger(str(Path(tempfile.mkdtemp()) / "ledger.json"))


BASE = dict(module="design-taste", skill="codebase-rescue",
            derived_from="mcp:render_agreement", targets=["http://localhost:3000"],
            at_commit="abc1234")


class TestTheRecordCarriesAScopeAndNoVerdict(unittest.TestCase):
    def test_a_run_records_what_was_looked_at(self):
        led = _ledger()
        record = led.record_run(**BASE)
        self.assertEqual(["http://localhost:3000"], record["scope"]["targets"])
        self.assertEqual("abc1234", record["at_commit"])
        self.assertEqual([], record["findings"])
        self.assertNotIn("outcome", record, "a run records scope, never a verdict")
        self.assertNotIn("clean", record)

    def test_the_empty_run_is_the_case_it_exists_for(self):
        """Recording only the runs that found something rebuilds the original failure one layer up."""
        led = _ledger()
        led.record_run(**BASE)
        view = led.runs_view(at_commit="abc1234")
        self.assertEqual(1, view["count"])
        self.assertEqual(0, view["modules"]["codebase-rescue:design-taste"]["findings"])

    def test_a_run_at_another_commit_does_not_answer_for_this_one(self):
        led = _ledger()
        led.record_run(**BASE)
        self.assertEqual(0, led.runs_view(at_commit="deadbee")["count"])
        self.assertEqual(1, led.runs_view()["count"], "unfiltered answers the weaker question")

    def test_findings_must_be_pins_this_ledger_holds(self):
        led = _ledger()
        with self.assertRaises(ledger.LedgerError):
            led.record_run(**BASE, findings=["pin_9999"])
        pin = led.add_pin(kind="design_concern", title="templated hero", severity="low",
                          confidence="inferred",
                          provenance=[{"source": "design-taste", "detail": "tell catalog"}])
        record = led.record_run(**BASE, findings=[pin["id"]])
        self.assertEqual([pin["id"]], record["findings"])

    def test_what_the_door_refuses_is_the_design(self):
        """Each refusal removes one way of writing an unfalsifiable claim."""
        led = _ledger()
        for label, override in (
            ("no targets — 'I looked at it'", {"targets": []}),
            ("no anchor — a claim that cannot go stale", {"at_commit": "  "}),
            ("no derivation — a scope nobody can reproduce", {"derived_from": ""}),
            ("no module — a claim about nothing", {"module": ""}),
            ("no skill — two catalogs carry this id", {"skill": ""}),
        ):
            with self.subTest(refusal=label), self.assertRaises(ledger.LedgerError):
                led.record_run(**{**BASE, **override})

    def test_an_older_file_without_the_collection_is_not_nonconforming(self):
        """`analysis_runs` arrived here, so its absence means an older file — not a broken one."""
        data = {"version": "0.31", "pins": [], "decision_log": [], "policies": [], "fog": []}
        self.assertNotIn("collection_shape", ledger.nonconforming(data))

    def test_a_malformed_run_is_reported_by_id(self):
        data = {"version": ledger.SCHEMA_VERSION, "pins": [], "decision_log": [], "policies": [],
                "fog": [], "analysis_runs": [{"id": "run_0001", "module": "", "skill": "s",
                                     "scope": {"derived_from": "t", "targets": []},
                                     "at_commit": "c", "findings": [], "ran_at": "now"}]}
        report = ledger.nonconforming(data)
        self.assertIn("run_module", report)
        self.assertIn("run_scope_targets", report)
        self.assertEqual(["run_0001"], report["run_module"])


class TestTheJoinThatMakesItBite(unittest.TestCase):
    """The record alone is inert: what closes the gap is that an ABSENCE becomes a pin."""

    def test_a_dispatched_module_with_no_run_is_a_gap(self):
        led = _ledger()
        led.record_run(**BASE)
        ran = led.runs_view(at_commit="abc1234")["modules"]
        report = coverage.module_report("codebase-rescue", ran, "abc1234", phases=[1])
        ids = {g["module"] for g in report["gaps"]}
        self.assertNotIn("design-taste", ids, "the module with a run is not a gap")
        self.assertIn("fp-check", ids, "a phase-1 module with no run is")
        self.assertEqual(report["expected"], report["applied"] + len(report["gaps"]))

    def test_the_gap_says_unchecked_and_never_clean(self):
        """The one sentence that must not invert: not looked at ≠ nothing found."""
        report = coverage.module_report("codebase-rescue", {}, "abc1234", phases=[1])
        pin = report["gaps"][0]["pin"]
        self.assertEqual("module-unrun", pin["kind_detail"])
        self.assertEqual("extracted", pin["confidence"],
                         "the ABSENCE of a record is a fact about the file, not a judgment")
        self.assertIn("unchecked", pin["as_is"]["description"])
        self.assertIn("never have been applied", pin["as_is"]["description"])

    def test_phases_narrow_the_expectation(self):
        """A mode that runs Phase 1 alone is not missing Phase 5."""
        one = coverage.module_report("codebase-rescue", {}, "c", phases=[1])
        every = coverage.module_report("codebase-rescue", {}, "c")
        self.assertLess(one["expected"], every["expected"])

    def test_both_catalogs_resolve_from_the_repo_and_from_the_vendored_copy(self):
        """The build vendors these beside the runtime because a skill ships as another plugin.

        Asserted for both, because the join has no left-hand side without them and the failure is
        silent in the worst way: no catalog reads exactly like no gaps.
        """
        for skill in ("codebase-rescue", "greenfield-forge"):
            with self.subTest(skill=skill):
                self.assertTrue(coverage.load_modules(skill))
        with self.assertRaises(FileNotFoundError):
            coverage.load_modules("no-such-skill")


if __name__ == "__main__":
    unittest.main()
