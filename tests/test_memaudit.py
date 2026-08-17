"""Tests for runtime/memaudit.py — the ledger audited as a MEMORY.

Two properties matter more than any single check and are held first: the module never writes to what
it audits, and it never reports a clean sheet on the two modes it cannot decide. A store-health gate
that quietly skips half the taxonomy is the `coverage.py` failure one layer up — `0 findings` from a
check that ran and `0 findings` from a check that did not are the same sentence, and the second is
the one that gets believed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import memaudit  # noqa: E402
from ledger import Ledger, policy_selects  # noqa: E402


def _pin(pid, title="A pin", state="detected", **extra):
    base = {"id": pid, "title": title, "state": state, "severity": "medium", "kind": "design_concern"}
    base.update(extra)
    return base


def _observed(ref):
    return {"determinism": "D0", "rung": "observed",
            "evidence": [{"kind": "test", "ref": ref, "outcome": "pass"}]}


def _data(pins=(), policies=(), log=()):
    return {"version": "0.31", "pins": list(pins), "policies": list(policies),
            "decision_log": list(log)}


class TestTheTaxonomyIsDeclaredNotApproximated(unittest.TestCase):
    """The eight modes are the published edge, and two of them are honestly out of reach."""

    def test_all_eight_modes_are_carried(self):
        self.assertEqual(len(memaudit.MEMORY_MODES), 8)
        self.assertEqual(len(memaudit.DECIDABLE) + len(memaudit.UNDECIDABLE), 8)

    def test_the_two_undecidable_modes_name_why(self):
        self.assertEqual(set(memaudit.UNDECIDABLE), {"missed_write", "missed_read"})
        for mode in memaudit.MEMORY_MODES:
            if mode["carrier"] is None:
                self.assertTrue(mode["why_not"].strip(),
                                f"{mode['id']} is undecidable and says nothing about why")

    def test_a_clean_audit_still_reports_what_it_could_not_check(self):
        """The property this module exists for: a green result is not silence."""
        report = memaudit.audit(_data())
        self.assertEqual(report["finding_count"], 0)
        self.assertEqual({u["mode"] for u in report["undecidable"]}, {"missed_write", "missed_read"})
        self.assertEqual(list(report["checked"]), list(memaudit.DECIDABLE))

    def test_decidable_is_derived_from_the_table_not_a_second_list(self):
        for mode in memaudit.MEMORY_MODES:
            self.assertEqual(mode["id"] in memaudit.DECIDABLE, bool(mode["carrier"]))


class TestStateStaleness(unittest.TestCase):
    def test_closed_at_observed_with_no_ref_is_unfalsifiable(self):
        found = memaudit.state_staleness([
            _pin("p1", state="resolved", verification=_observed("")),
        ])
        self.assertEqual([f["mode"] for f in found], ["state_staleness"])
        self.assertEqual(found[0]["severity"], "high")

    def test_a_ref_is_the_whole_defence(self):
        self.assertEqual(memaudit.state_staleness([
            _pin("p1", state="resolved", verification=_observed("pytest -k payments")),
        ]), [])

    def test_an_open_pin_is_not_a_stale_claim(self):
        self.assertEqual(memaudit.state_staleness([
            _pin("p1", state="detected", verification=_observed("")),
        ]), [])

    def test_a_weak_rung_is_not_this_finding(self):
        """A pin that never claimed to close is a different problem, and `resolve` already refuses
        it. Reporting it here would double-count the one gate that already holds."""
        weak = _pin("p1", state="resolved",
                    verification={"determinism": "D2", "rung": "self_check", "evidence": []})
        self.assertEqual(memaudit.state_staleness([weak]), [])


class TestOvergeneralization(unittest.TestCase):
    def test_an_empty_scope_is_a_universal_default(self):
        found = memaudit.overgeneralization(
            [{"id": "pol1", "rule": "deny", "applies_to": {}}],
            [_pin("p1"), _pin("p2")])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "high")
        self.assertIn("every pin written after it", found[0]["detail"])

    def test_a_scope_selecting_one_pin_is_a_record_not_a_law(self):
        self.assertEqual(memaudit.overgeneralization(
            [{"id": "pol1", "rule": "deny", "applies_to": {"id": "p1"}}],
            [_pin("p1"), _pin("p2")]), [])

    def test_a_scope_selecting_several_is_reported(self):
        found = memaudit.overgeneralization(
            [{"id": "pol1", "rule": "deny", "applies_to": {"severity": "medium"}}],
            [_pin("p1"), _pin("p2"), _pin("p3")])
        self.assertEqual([f["mode"] for f in found], ["overgeneralization"])


class TestRationaleErosion(unittest.TestCase):
    def test_a_policy_with_no_rung_lost_its_reason(self):
        found = memaudit.rationale_erosion([{"id": "pol1", "rule": "deny", "applies_to": {}}], [])
        self.assertEqual([f["mode"] for f in found], ["rationale_erosion"])

    def test_the_weakness_cascades_into_every_decision_it_defaulted(self):
        policies = [{"id": "pol1", "rule": "deny", "applies_to": {}}]
        log = [{"id": "ev_1", "pin_id": "p1", "outcome": "deny",
                "evidence": "cascaded", "source": "policy:pol1", "policy_id": "pol1"}]
        found = memaudit.rationale_erosion(policies, log)
        subjects = [f["subject"] for f in found]
        self.assertIn("ev_1", subjects)

    def test_a_sound_policy_cascades_nothing(self):
        policies = [{"id": "pol1", "rule": "deny", "applies_to": {}, "evidence": "elicited"}]
        log = [{"id": "ev_1", "pin_id": "p1", "outcome": "deny",
                "evidence": "cascaded", "source": "policy:pol1", "policy_id": "pol1"}]
        self.assertEqual(memaudit.rationale_erosion(policies, log), [])


class TestPollution(unittest.TestCase):
    def test_a_traceback_in_a_durable_field(self):
        found = memaudit.pollution(
            [_pin("p1", as_is={"description": "Traceback (most recent call last)\nboom"})], "pin")
        self.assertEqual([f["mode"] for f in found], ["pollution"])

    def test_a_stack_frame_line_counts_even_without_the_header(self):
        found = memaudit.pollution(
            [_pin("p1", as_is={"description": 'x\n  File "app/main.py", line 42\n    return'})], "pin")
        self.assertEqual(len(found), 1)

    def test_an_ansi_escape_is_terminal_output(self):
        found = memaudit.pollution([_pin("p1", title="\x1b[31mFAILED\x1b[0m")], "pin")
        self.assertEqual(len(found), 1)

    def test_size_alone_is_the_weaker_finding(self):
        found = memaudit.pollution([_pin("p1", title="x" * 3000)], "pin")
        self.assertEqual(found[0]["severity"], "low")

    def test_ordinary_prose_is_left_alone(self):
        self.assertEqual(memaudit.pollution(
            [_pin("p1", as_is={"description": "The retry path drops the idempotency key."})],
            "pin"), [])


class TestRedundancy(unittest.TestCase):
    def test_normalization_catches_the_same_sentence_written_twice(self):
        found = memaudit.redundancy(
            [_pin("p1", title="Payments must retry"), _pin("p2", title="payments  must   retry.")],
            "title", "pin")
        self.assertEqual(len(found), 1)
        self.assertIn("p1,p2", found[0]["subject"])

    def test_one_finding_per_group_not_per_member(self):
        pins = [_pin(f"p{i}", title="Same thing") for i in range(4)]
        self.assertEqual(len(memaudit.redundancy(pins, "title", "pin")), 1)

    def test_different_words_for_one_meaning_are_NOT_caught(self):
        """Deliberate. Judging that two sentences mean the same thing is a model's call, and a
        duplicate reported on a model's say-so is exactly what this package refuses elsewhere."""
        self.assertEqual(memaudit.redundancy(
            [_pin("p1", title="Payments must retry"), _pin("p2", title="Retry the payment path")],
            "title", "pin"), [])


class TestMemoryFollowingFailure(unittest.TestCase):
    def test_two_policies_selecting_one_pin_is_ambiguous_dispatch(self):
        found = memaudit.memory_following_failure(
            [{"id": "pol1", "applies_to": {}}, {"id": "pol2", "applies_to": {"severity": "medium"}}],
            [_pin("p1")])
        self.assertEqual([f["mode"] for f in found], ["memory_following_failure"])
        self.assertEqual(found[0]["severity"], "high")

    def test_one_policy_per_pin_is_the_healthy_case(self):
        self.assertEqual(memaudit.memory_following_failure(
            [{"id": "pol1", "applies_to": {"severity": "high"}}], [_pin("p1")]), [])


class TestTheScopePredicateHasOneHome(unittest.TestCase):
    """`policy_selects` moved into `ledger` precisely so the auditor and `policy_preview` cannot
    drift. If a future edit copies it back into this module, this test is what says so."""

    def test_memaudit_does_not_define_its_own(self):
        self.assertFalse(hasattr(memaudit, "policy_selects"),
                         "memaudit must import the scope predicate, never redefine it")

    def test_the_predicate_is_equality_on_declared_keys(self):
        self.assertTrue(policy_selects({"severity": "high"}, {"severity": "high", "id": "p1"}))
        self.assertFalse(policy_selects({"severity": "high"}, {"severity": "low"}))
        self.assertTrue(policy_selects({}, {"id": "p1"}))

    def test_it_never_raises_on_a_malformed_scope_or_pin(self):
        self.assertFalse(policy_selects("high", {"id": "p1"}))
        self.assertFalse(policy_selects({"severity": "high"}, "not a pin"))


class TestTheAuditIsReadOnly(unittest.TestCase):
    def test_auditing_does_not_mutate_the_data_it_was_given(self):
        import copy
        data = _data(
            pins=[_pin("p1", state="resolved", verification=_observed(""))],
            policies=[{"id": "pol1", "rule": "deny", "applies_to": {}}])
        before = copy.deepcopy(data)
        memaudit.audit(data)
        self.assertEqual(data, before)

    def test_it_survives_a_ledger_whose_collections_are_wrong_shapes(self):
        """A store-health check that dies on an unhealthy store is the joke this package keeps
        catching itself telling."""
        for broken in ({"pins": "nope"}, {"policies": [42]}, {"pins": [{"title": 7}]},
                       {"decision_log": "nope"}, {}):
            with self.subTest(broken=broken):
                report = memaudit.audit(broken)
                self.assertIsInstance(report["findings"], list)

    def test_writing_findings_is_the_callers_move_through_their_own_ledger(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "ledger.json")
        led = Ledger(path)
        led.add_pin(kind="defect", title="a real defect", severity="high", confidence="extracted",
                    provenance=[{"source": "test", "detail": "seed"}])
        findings = [{"mode": "redundancy", "subject": "pin:p1,p2", "detail": "twice", "severity": "low"}]
        written = memaudit.to_pins(led, findings)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["kind_detail"], "memory-redundancy")
        self.assertEqual(written[0]["confidence"], "extracted")


if __name__ == "__main__":
    unittest.main()
