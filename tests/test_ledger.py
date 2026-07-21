"""Tests for runtime/ledger.py — each test pins one load-bearing rule of
core/decisions-ledger-spec.md (v0.6). Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

from ledger import Ledger, LedgerError  # noqa: E402


def make_ledger() -> Ledger:
    tmp = tempfile.mkdtemp()
    return Ledger(os.path.join(tmp, "ledger.json"))


def add_simple_pin(led: Ledger, **overrides) -> dict:
    defaults = dict(
        kind="contract_mismatch",
        title="role enum drift",
        severity="high",
        confidence="extracted",
        provenance=[{"source": "contract_recon", "detail": "db↔api shape diff"}],
        as_is={"db": "ENUM('admin','user')", "api": "string", "disagreeing_layers": ["api"]},
        question={
            "prompt": "Which role set is intended?",
            "options": [{"id": "opt_a", "label": "DB is truth"},
                        {"id": "opt_b", "label": "Widen the enum"}],
            "allow_freeform": True,
        },
    )
    defaults.update(overrides)
    return led.add_pin(**defaults)


class TestEnvelope(unittest.TestCase):
    def test_unknown_kind_rejected(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            add_simple_pin(led, kind="vibe_issue")

    def test_other_requires_kind_detail(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            add_simple_pin(led, kind="other")
        pin = add_simple_pin(led, kind="other", kind_detail="license drift")
        self.assertEqual(pin["kind_detail"], "license drift")

    def test_enums_validated(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            add_simple_pin(led, severity="catastrophic")
        with self.assertRaises(LedgerError):
            add_simple_pin(led, confidence="vibes")

    def test_provenance_required(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            add_simple_pin(led, provenance=[])

    def test_question_shape_validated(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            add_simple_pin(led, question={"options": []})  # no prompt
        with self.assertRaises(LedgerError):
            add_simple_pin(led, question={"prompt": "x", "options": [{"label": "no id"}]})

    def test_depends_on_must_exist(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            add_simple_pin(led, depends_on=["pin_9999"])

    def test_question_makes_needs_input(self):
        led = make_ledger()
        self.assertEqual(add_simple_pin(led)["state"], "needs_input")
        self.assertEqual(add_simple_pin(led, question=None)["state"], "detected")


class TestNeutrality(unittest.TestCase):
    """Decision 4 + v0.6: brainstorm proposes, challenger refutes — neither decides."""

    def test_brainstorm_cannot_carry_decision(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.add_proposals(pin["id"], [{"summary": "x", "decision": "opt_a"}])

    def test_brainstorm_writes_proposals_not_state(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.add_proposals(pin["id"], [{"summary": "consolidate on db", "effort": "S"}])
        self.assertEqual(pin["state"], "brainstorming")
        self.assertIsNone(pin["decision"])

    def test_only_interview_or_policy_commits(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        for bad_source in ("brainstorm", "challenge:challenger", "feedback:metrics", "agent"):
            with self.assertRaises(LedgerError):
                led.decide(pin["id"], "opt_a", "r", "flip", source=bad_source)

    def test_challenge_never_writes_decision(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "db is truth", "if superadmin appears, reopen")
        led.challenge(pin["id"], target="to_be", challenge_class="unstated_assumption",
                      argument="assumes single-tenant", severity="high", upheld=True)
        events = [e["id"] for e in led.data["decision_log"]]
        self.assertEqual(len([e for e in events if e.startswith("ev_")]), 1)  # still one decision
        self.assertEqual(len([e for e in events if e.startswith("chl_")]), 1)


class TestDecisions(unittest.TestCase):
    def test_flip_criteria_required(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.decide(pin["id"], "opt_a", "rationale", flip_criteria="")

    def test_append_only_last_wins(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "first", "flip-1")
        led.decide(pin["id"], "opt_b", "changed our mind", "flip-2")
        self.assertEqual(pin["decision"]["outcome"], "opt_b")     # last committed wins
        self.assertEqual(len(led.data["decision_log"]), 2)        # history preserved

    def test_flip_signal_source_validated(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.decide(pin["id"], "opt_a", "r", "flip",
                       flip_signal={"signal": "p95", "source": "astrology"})
        led.decide(pin["id"], "opt_a", "r", "flip",
                   flip_signal={"signal": "orders p95", "comparator": ">",
                                "threshold": "200ms", "window": "7d", "source": "metrics"})

    def test_cluster_decide_applies_to_group_with_per_pin_events(self):
        led = make_ledger()
        a = add_simple_pin(led, cluster_id="cl_sqli", severity="medium")
        b = add_simple_pin(led, cluster_id="cl_sqli", severity="medium")
        c = add_simple_pin(led, cluster_id="cl_other", severity="medium")
        events = led.decide(a["id"], "parametrize", "one class, one decision", "new sqli class",
                            apply_to_cluster=True)
        self.assertEqual(len(events), 2)
        self.assertEqual(b["state"], "decided")
        self.assertEqual(c["state"], "needs_input")   # other cluster untouched

    def test_accept_is_design_concern_only(self):
        led = make_ledger()
        concern = add_simple_pin(led, kind="design_concern",
                                 as_is={"current_design": "monolith", "concern": "coupling"})
        fork = add_simple_pin(led, kind="open_decision", as_is={"givens": [], "built": None})
        led.accept(concern["id"], "fine for v1 scale", "if a module needs independent scaling")
        self.assertEqual(concern["state"], "accepted")
        with self.assertRaises(LedgerError):
            led.accept(fork["id"], "n/a", "n/a")


class TestThresholdAndPolicies(unittest.TestCase):
    """v0.3: 200 findings are not 200 decisions — but blocker|high never defaults silently."""

    def test_policy_resolves_medium_low_only(self):
        led = make_ledger()
        low = add_simple_pin(led, severity="medium")
        high = add_simple_pin(led, severity="blocker")
        led.add_policy(applies_to={"kind": "contract_mismatch"},
                       rule="DB is source of truth by default",
                       default_outcome={"canonical_layer": "db"})
        decided = led.apply_policies()
        self.assertEqual([p["id"] for p in decided], [low["id"]])
        self.assertEqual(low["state"], "decided")
        self.assertEqual(low["resolution_mode"], "policy_default")
        self.assertEqual(high["state"], "needs_input")            # never silent
        self.assertEqual(high["resolution_mode"], "asked")

    def test_policy_event_names_the_policy(self):
        led = make_ledger()
        add_simple_pin(led, severity="low")
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"},
                             rule="DB wins", default_outcome="db")
        led.apply_policies()
        event = led.data["decision_log"][-1]
        self.assertEqual(event["source"], f"policy:{pol['id']}")   # user-originated, amplified

    def test_policy_exceptions_stay_asked(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="low")
        led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="DB wins",
                       default_outcome="db", exceptions=[pin["id"]])
        self.assertEqual(led.apply_policies(), [])
        self.assertEqual(pin["state"], "needs_input")

    def test_resolution_mode_threshold(self):
        led = make_ledger()
        high = add_simple_pin(led, severity="high")
        low = add_simple_pin(led, severity="low")
        led.assign_resolution_modes()
        self.assertEqual(high["resolution_mode"], "asked")
        self.assertEqual(low["resolution_mode"], "proposed_default")


class TestAssumptionSurfacing(unittest.TestCase):
    """v0.6: a forced assumption is a vetoable pin, never a silent default."""

    def test_assumption_pin_shape(self):
        led = make_ledger()
        pin = led.surface_assumption("assumed single-tenant",
                                     "brief never says multi-tenant; schema has no tenant_id")
        self.assertEqual(pin["provenance"][0]["source"], "agent_assumption")
        self.assertEqual(pin["state"], "needs_input")              # visible + vetoable
        self.assertIn(pin["confidence"], ("inferred", "ambiguous"))

    def test_assumption_cannot_claim_extracted(self):
        led = make_ledger()
        with self.assertRaises(LedgerError):
            led.surface_assumption("t", "d", confidence="extracted")

    def test_high_severity_assumption_always_asked(self):
        led = make_ledger()
        pin = led.surface_assumption("auth model assumed", "JWT assumed", severity="blocker")
        self.assertEqual(pin["resolution_mode"], "asked")


class TestReopenArcs(unittest.TestCase):
    """v0.5 downstream + v0.6 upstream: both arcs reopen, neither decides."""

    def _decided_chain(self, led):
        root = add_simple_pin(led, kind="acceptance_criterion", severity="high",
                              as_is={"built": None},
                              to_be={"statement": "user books a slot", "verify": "e2e 201"})
        mid = add_simple_pin(led, kind="open_decision", depends_on=[root["id"]],
                             as_is={"givens": ["on-prem"], "built": None})
        leaf = add_simple_pin(led, kind="open_decision", depends_on=[mid["id"]],
                              as_is={"givens": [], "built": None})
        unrelated = add_simple_pin(led)
        for p in (root, mid, leaf, unrelated):
            led.decide(p["id"], "opt_a", "r", "flip")
        return root, mid, leaf, unrelated

    def test_upheld_challenge_reopens_minimal_transitively(self):
        led = make_ledger()
        root, mid, leaf, unrelated = self._decided_chain(led)
        led.challenge(root["id"], target="acceptance_criterion",
                      challenge_class="unfalsifiable",
                      argument="'the app is fast' has no failing test", severity="high",
                      upheld=True)
        for p in (root, mid, leaf):
            self.assertEqual(p["state"], "needs_input")
            self.assertEqual(p["substate"], "challenged")
            self.assertEqual(p["resolution_mode"], "asked")        # never re-defaulted
        self.assertEqual(unrelated["state"], "decided")            # minimal reopen

    def test_not_upheld_challenge_changes_nothing(self):
        led = make_ledger()
        root, mid, leaf, _ = self._decided_chain(led)
        led.challenge(root["id"], target="to_be", challenge_class="inconsistent",
                      argument="weak claim", severity="medium", upheld=False)
        self.assertEqual(root["state"], "decided")

    def test_reopen_event_downstream(self):
        led = make_ledger()
        root, mid, leaf, unrelated = self._decided_chain(led)
        event = led.reopen(mid["id"], reason="orders p95 340ms > 200ms for 9d")
        self.assertTrue(event["id"].startswith("rev_"))
        self.assertEqual(mid["substate"], "reopened")
        self.assertEqual(leaf["state"], "needs_input")             # dependent reopened
        self.assertEqual(root["state"], "decided")                 # upstream untouched
        self.assertEqual(unrelated["state"], "decided")

    def test_challenge_class_validated(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.challenge(pin["id"], target="to_be", challenge_class="i_disagree",
                          argument="x", severity="high", upheld=False)

    def test_unfounded_infeasibility_reopens_like_any_challenge(self):
        """v0.6+: the mirror of `unsatisfiable` — an oracle that gives up a reachable outcome as
        falsely impossible is challengeable, and an upheld challenge reopens the pin."""
        led = make_ledger()
        root, mid, leaf, unrelated = self._decided_chain(led)
        led.challenge(root["id"], target="to_be", challenge_class="unfounded_infeasibility",
                      argument="'SSO cannot be done here' — but the elected library supports it",
                      severity="high", upheld=True)
        self.assertEqual(root["state"], "needs_input")
        self.assertEqual(root["substate"], "challenged")
        self.assertEqual(unrelated["state"], "decided")               # still minimal reopen


class TestRemediation(unittest.TestCase):
    def test_remediation_requires_decision(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.add_remediation(pin["id"], action="align", ladder_rung=2)

    def test_defect_goes_straight_to_plan(self):
        led = make_ledger()
        defect = led.add_pin(kind="defect", title="sqli", severity="blocker",
                             confidence="extracted",
                             provenance=[{"source": "semgrep", "detail": "python.sqli.raw"}],
                             as_is={"description": "string concat query"})
        item = led.add_remediation(defect["id"], action="refactor", ladder_rung=1)
        self.assertEqual(item["status"], "todo")

    def test_build_item_verbs_and_track(self):
        led = make_ledger()
        fork = add_simple_pin(led, kind="open_decision", as_is={"givens": [], "built": None})
        led.decide(fork["id"], "opt_pg", "team knows postgres", "if doc-model needs emerge")
        item = led.add_remediation(fork["id"], action="scaffold", ladder_rung=7,
                                   build_track="A", contract_carrier="shared-types")
        self.assertTrue(item["id"].startswith("bld_"))
        with self.assertRaises(LedgerError):                       # rescue verb on a BuildItem
            led.add_remediation(fork["id"], action="consolidate", ladder_rung=2,
                                build_track="A")
        with self.assertRaises(LedgerError):                       # build verb on RemediationItem
            led.add_remediation(fork["id"], action="scaffold", ladder_rung=2)

    def test_resolve_gated_on_done_items(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "flip")
        with self.assertRaises(LedgerError):                       # no silent close
            led.resolve(pin["id"])
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2,
                                   canonical_target="db")
        with self.assertRaises(LedgerError):
            led.resolve(pin["id"])
        led.set_remediation_status(pin["id"], item["id"], "done")
        self.assertEqual(led.resolve(pin["id"])["state"], "resolved")


class TestViewsAndPersistence(unittest.TestCase):
    def test_interview_orders_by_information_gain(self):
        led = make_ledger()
        root = add_simple_pin(led, severity="low", title="high fan-out root")
        add_simple_pin(led, question=None, depends_on=[root["id"]])
        add_simple_pin(led, question=None, depends_on=[root["id"]])
        lone_blocker = add_simple_pin(led, severity="blocker", title="lone blocker")
        view = led.interview_view()
        # the low-severity root collapses 2 downstream pins → outranks the lone blocker
        self.assertEqual(view[0]["id"], root["id"])
        self.assertEqual(view[1]["id"], lone_blocker["id"])

    def test_round_trip(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "flip")
        led.save()
        reloaded = Ledger(led.path)
        self.assertEqual(reloaded.summary()["pins"], 1)
        self.assertEqual(reloaded.summary()["events"], 1)
        self.assertEqual(reloaded.pin(pin["id"])["state"], "decided")

    def test_save_is_valid_json_utf8(self):
        led = make_ledger()
        add_simple_pin(led, title="ruolo però — non-ASCII")
        led.save()
        with open(led.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["version"], "0.6")
        self.assertIn("però", data["pins"][0]["title"])

    def test_version_mismatch_rejected(self):
        led = make_ledger()
        led.save()
        with open(led.path, "r+", encoding="utf-8") as fh:
            data = json.load(fh)
            data["version"] = "0.1"
            fh.seek(0)
            json.dump(data, fh)
            fh.truncate()
        with self.assertRaises(LedgerError):
            Ledger(led.path)


if __name__ == "__main__":
    unittest.main()
