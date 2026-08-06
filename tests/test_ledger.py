"""Tests for runtime/ledger.py — each test pins one load-bearing rule of
core/decisions-ledger-spec.md (v0.18). Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

from ledger import SCHEMA_VERSION, Ledger, LedgerError  # noqa: E402


#: The greenfield catalog, for the one test that has to reach the OTHER unasked door.
_CATALOG = os.path.join(os.path.dirname(__file__), "..", "src", "skills", "greenfield-forge",
                        "assets", "decision-catalog.json")


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
            add_simple_pin(led, question={"prompt": "x", "allow_freeform": True,
                                          "options": [{"label": "no id"}]})

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

    def test_one_call_decides_one_pin_and_cannot_fan_out(self):
        """v0.14. `decide` took `apply_to_cluster`, and one call then wrote the same outcome — and
        the same `human_answer` — onto every pin sharing the `cluster_id`, past the offered-options
        rule, past the severity threshold, from an elicitation that named one pin. It is not gated,
        it is gone: a fan-out is a `Policy` (there is no rung for one that is not), and `apply_policy`
        does it with a preview and two held-back buckets. Asserted on the signature too, because the
        parameter coming back is exactly how this regresses."""
        import inspect
        led = make_ledger()
        a = add_simple_pin(led, cluster_id="cl_sqli", severity="medium")
        b = add_simple_pin(led, cluster_id="cl_sqli", severity="medium")
        self.assertNotIn("apply_to_cluster", inspect.signature(led.decide).parameters,
                         "a cluster fan-out that carries no Policy can name neither the rule it "
                         "applied nor the radius the human was shown")
        event = led.decide(a["id"], "parametrize", "one class, one decision", "new sqli class")
        self.assertEqual(event["pin_id"], a["id"])
        self.assertEqual(len(led.data["decision_log"]), 1)
        self.assertEqual(b["state"], "needs_input")   # the sibling stays open and gets asked

    def test_accept_is_design_concern_only(self):
        led = make_ledger()
        concern = add_simple_pin(led, kind="design_concern",
                                 as_is={"current_design": "monolith", "concern": "coupling"})
        fork = add_simple_pin(led, kind="open_decision", as_is={"givens": [], "built": None})
        led.accept(concern["id"], "fine for v1 scale", "if a module needs independent scaling")
        self.assertEqual(concern["state"], "accepted")
        with self.assertRaises(LedgerError):
            led.accept(fork["id"], "n/a", "n/a")


class TestEvidenceIsReachable(unittest.TestCase):
    """v0.10 `evidence`: stored on the event, read by the surfaces a human looks at.

    The rung was written by `decide()` and consumed by nothing for a version, which made the spec's
    own justification for allowing the weak rung — *it is made visible* — false as shipped. These
    pin the two things a surface needs: the count an agent reads before acting, and the path the map
    walks to state the rung on a decision card.
    """

    def test_summary_counts_the_rungs_apart(self):
        led = make_ledger()
        a, b, c = add_simple_pin(led), add_simple_pin(led), add_simple_pin(led)
        led.decide(a["id"], "opt_a", "r", "flip", evidence="elicited")
        led.decide(b["id"], "opt_a", "r", "flip", evidence="transcribed", human_answer="opt A")
        led.decide(c["id"], "opt_a", "r", "flip", evidence="brief")
        # counts, never a blended score: three failure modes kept apart is the design
        self.assertEqual(led.summary()["decisions_by_evidence"],
                         {"elicited": 1, "transcribed": 1, "brief": 1})

    def test_summary_counts_how_each_POLICY_was_elected_too(self):
        """v0.15. A policy is an election over a whole cluster, and every `cascaded` count above
        rests on one — so a summary that weighs the cascade and says nothing about the election it
        derives from weighs the wrong end. It also has to be counted when the policy cascaded over
        nothing: `policies: 1` and no event anywhere was the state that showed up on no surface."""
        led = make_ledger()
        led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="DB wins",
                       default_outcome="opt_a", evidence="transcribed", human_answer="db wins")
        led.data["policies"].append({"id": "pol_0002", "applies_to": {}, "rule": "older file",
                                     "default_outcome": "opt_a", "exceptions": []})
        summary = led.summary()
        self.assertEqual(summary["decisions_by_evidence"], {}, "neither cascaded over any pin")
        self.assertEqual(summary["policies"], 2)
        self.assertEqual(summary["policies_by_evidence"], {"transcribed": 1, "unrecorded": 1},
                         "a policy elected before the rung existed is unknown, never weak")

    def test_summary_counts_only_decisions_not_every_event(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "flip", evidence="elicited")
        led.challenge(pin["id"], target="to_be", challenge_class="unstated_assumption",
                      argument="assumes single-tenant", severity="high", upheld=True)
        led.label_failure(pin["id"], failure_class="environment", detail="toolchain missing",
                          phase="build")
        self.assertEqual(led.summary()["decisions_by_evidence"], {"elicited": 1})

    def test_the_map_can_reach_the_rung_from_the_pin(self):
        """`pin.decision` carries only `{event_id, outcome}`, so every surface that states the rung
        resolves it in `decision_log` by that id. If either half of that join stops holding, the
        map's decision card silently loses the rung again — with nothing else failing."""
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "flip",
                   evidence="transcribed", human_answer="option A, the DB is truth")
        event_id = pin["decision"]["event_id"]
        event = next((e for e in led.data["decision_log"] if e["id"] == event_id), None)
        self.assertIsNotNone(event, "pin.decision.event_id resolves to no event")
        self.assertEqual(event["evidence"], "transcribed")
        self.assertEqual(event["human_answer"], "option A, the DB is truth")

    def test_a_cascade_is_not_recorded_as_a_relay(self):
        """v0.11. The cascade used to take the `transcribed` default, so every surface said an agent
        had relayed what the user said about a decision nobody relayed — the map warned about a
        missing quote, the summary counted it as weak, the AGENTS.md line stated it in prose."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="low")
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="DB wins",
                             default_outcome="opt_a", evidence="transcribed",
                             human_answer="the DB wins unless I say otherwise")
        led.apply_policy(pol)
        event = led.data["decision_log"][-1]
        self.assertEqual(event["evidence"], "cascaded")
        self.assertEqual(event["policy_id"], pol["id"],
                         "a cascaded event must name the election it derives from, by field — a "
                         "surface should not have to parse `source` to find the policy")
        self.assertNotIn("human_answer", event,
                         "the quote belongs to the policy election, not restated on each pin")
        self.assertEqual(led.summary()["decisions_by_evidence"], {"cascaded": 1})
        self.assertEqual((pol["evidence"], pol["human_answer"]),
                         ("transcribed", "the DB wins unless I say otherwise"))

    def test_the_rung_and_the_source_imply_each_other(self):
        """Both directions, because both are ways of lying about who answered."""
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):   # a direct answer claiming a cascade
            led.decide(pin["id"], "opt_a", "r", "flip", evidence="cascaded", policy_id="pol_0001")
        with self.assertRaises(LedgerError):   # a cascade claiming a relay
            led.decide(pin["id"], "opt_a", "r", "flip", source="policy:pol_0001",
                       evidence="transcribed", human_answer="x")
        with self.assertRaises(LedgerError):   # a cascade naming no policy
            led.decide(pin["id"], "opt_a", "r", "flip", source="policy:pol_0001",
                       evidence="cascaded")
        with self.assertRaises(LedgerError):   # a direct answer pointing at a policy
            led.decide(pin["id"], "opt_a", "r", "flip", human_answer="x", policy_id="pol_0001")
        with self.assertRaises(LedgerError):   # a policy is elected, never derived from a policy
            led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="r",
                           default_outcome="opt_a", evidence="cascaded")


class TestThresholdAndPolicies(unittest.TestCase):
    """v0.3: 200 findings are not 200 decisions — but blocker|high never defaults silently."""

    def test_policy_resolves_medium_low_only(self):
        led = make_ledger()
        low = add_simple_pin(led, severity="medium")
        high = add_simple_pin(led, severity="blocker")
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"},
                             rule="DB is source of truth by default",
                             default_outcome="opt_a")
        self.assertEqual(led.apply_policy(pol)["would_decide"], [low["id"]])
        self.assertEqual(low["state"], "decided")
        self.assertEqual(low["resolution_mode"], "policy_default")
        self.assertEqual(high["state"], "needs_input")            # never silent
        self.assertEqual(high["resolution_mode"], "asked")

    def test_policy_event_names_the_policy(self):
        led = make_ledger()
        add_simple_pin(led, severity="low")
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"},
                             rule="DB wins", default_outcome="opt_a")
        led.apply_policy(pol)
        event = led.data["decision_log"][-1]
        self.assertEqual(event["source"], f"policy:{pol['id']}")   # user-originated, amplified

    def test_the_preview_is_the_cascade(self):
        """What a user is shown before electing a policy must be what the cascade then does. One
        matcher, two callers — the preview is not a second implementation that can drift."""
        led = make_ledger()
        low = add_simple_pin(led, severity="low")
        med = add_simple_pin(led, severity="medium")
        high = add_simple_pin(led, severity="blocker")
        skip = add_simple_pin(led, severity="low")
        preview = led.policy_preview({"kind": "contract_mismatch"}, "opt_a",
                                     exceptions=[skip["id"]])
        self.assertEqual(preview["would_decide"], [low["id"], med["id"]])
        self.assertEqual(preview["held_back"], [high["id"]])
        self.assertEqual(preview["excepted"], [skip["id"]])
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="DB wins",
                             default_outcome="opt_a", exceptions=[skip["id"]],
                             human_answer="db wins")
        self.assertEqual(led.apply_policy(pol)["would_decide"], preview["would_decide"])

    def test_policy_exceptions_stay_asked(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="low")
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="DB wins",
                             default_outcome="opt_a", exceptions=[pin["id"]])
        self.assertEqual(led.apply_policy(pol)["would_decide"], [])
        self.assertEqual(pin["state"], "needs_input")

    def test_a_policy_may_not_write_an_outcome_the_pin_never_offered(self):
        """v0.12, the blocker. `record_decision` has always refused an outcome the pin's own
        `question` does not offer; the cascade did not, so a policy — which decides MANY pins —
        was governed less than a single decision. Reproduced by two independent reviewers over
        real stdio and through the pure layer: an agent-authored sentence landed as the outcome of
        pins whose question offered a closed set that did not contain it."""
        led = make_ledger()
        offers = add_simple_pin(led, severity="low")
        other = add_simple_pin(led, severity="low",
                               question={"prompt": "Which datastore?",
                                         "options": [{"id": "postgres", "label": "Postgres"},
                                                     {"id": "mysql", "label": "MySQL"}],
                                         "allow_freeform": True})
        mute = add_simple_pin(led, severity="low", question=None)

        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="the DB is truth",
                             default_outcome="opt_a", human_answer="the DB wins")
        radius = led.apply_policy(pol)
        self.assertEqual(radius["would_decide"], [offers["id"]])
        self.assertEqual(radius["not_offered"], [other["id"], mute["id"]],
                         "a pin whose own question does not offer the outcome — or poses no "
                         "question at all — must be held back, not decided on a value nobody "
                         "offered it")
        self.assertEqual(other["state"], "needs_input")
        # v0.18: held back, and NOT marked. `not_offered` is a fact about this rule's fit, and the
        # mark is permanent — see TestAMarkThatCannotBeClearedIsWrittenOnlyForAStandingReason.
        self.assertNotIn("resolution_mode", other)
        self.assertEqual(mute["state"], "detected")
        self.assertEqual([e["pin_id"] for e in led.data["decision_log"]], [offers["id"]])

    def test_freeform_does_not_widen_what_a_policy_may_write(self):
        """`allow_freeform` legitimizes an unlisted outcome on the single-pin path because there
        the human's own words ARE the outcome. A policy outcome is one sentence elected over a
        cluster and is nobody's words on this pin, so reading the flag as 'anything may cascade
        here' would reopen the hole on every pin that carries a freeform escape — which is every
        pin the greenfield catalog creates."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="low")            # allow_freeform: True
        self.assertTrue(pin["question"]["allow_freeform"])
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"},
                             rule="mongo everywhere", default_outcome="mongodb",
                             human_answer="mongo everywhere")
        self.assertEqual(led.apply_policy(pol)["not_offered"], [pin["id"]])
        self.assertEqual(led.data["decision_log"], [])

    def test_a_policy_outcome_is_an_option_id_not_a_payload(self):
        """It was `Any`, and the cascade JSON-encoded anything else into the event's `outcome` — a
        blob no question can offer, so it would now hold back every pin it was meant to decide.
        Refused at the door, where the message can say so."""
        led = make_ledger()
        add_simple_pin(led, severity="low")
        for bad in ({"canonical_layer": "db"}, "", "   ", None):
            with self.subTest(default_outcome=bad), self.assertRaises(LedgerError):
                led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="r",
                               default_outcome=bad, human_answer="x")

    def test_a_policy_cascades_once_over_the_radius_its_elector_saw(self):
        """v0.12. `apply_policies()` re-ran EVERY policy on every call. Settled pins are skipped,
        so the only pins a re-run could touch were pins added since an election — precisely the ones
        that policy's elector was never shown. It also made the report false: recording pol_0002
        returned the pins pol_0001 had just decided as its own."""
        led = make_ledger()
        first = add_simple_pin(led, severity="low", cluster_id="cl_one")
        pol1 = led.add_policy(applies_to={"cluster_id": "cl_one"}, rule="A",
                              default_outcome="opt_a", human_answer="A")
        self.assertEqual(led.apply_policy(pol1)["would_decide"], [first["id"]])

        later = add_simple_pin(led, severity="low", cluster_id="cl_one")   # found AFTER the election
        second = add_simple_pin(led, severity="low", cluster_id="cl_two")
        pol2 = led.add_policy(applies_to={"cluster_id": "cl_two"}, rule="B",
                              default_outcome="opt_b", human_answer="B")
        radius = led.apply_policy(pol2)

        self.assertEqual(radius["would_decide"], [second["id"]],
                         "a policy must report what IT decided — not what an earlier one did")
        self.assertEqual(later["state"], "needs_input",
                         "a pin created after an election was not in the radius the user accepted; "
                         "deciding it here would cascade a rule over pins nobody was shown")
        self.assertEqual([(e["pin_id"], e["outcome"]) for e in led.data["decision_log"]],
                         [(first["id"], "opt_a"), (second["id"], "opt_b")])

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

    def test_sequence_lives_on_the_pin_and_only_there(self):
        """An item takes no `depends_on`, and the pin's is the one the scheduler levels.

        Both halves matter. The item field used to exist and was inert three ways — ids allocated
        per-pin (`rem_0001` on every pin, so a cross-pin reference was ambiguous by construction),
        no validation, and no reader anywhere in the runtime. It read as a capability, which is how
        it got planned around. `scripts/check_schema_fields.py` guards the class, but it matches on
        the field NAME and so cannot tell a pin's `depends_on` from an item's; this is the instance.
        """
        led = make_ledger()
        defect = led.add_pin(kind="defect", title="sqli", severity="blocker", confidence="extracted",
                             provenance=[{"source": "semgrep", "detail": "r"}], as_is={"description": "x"})
        with self.assertRaises(TypeError, msg="an item must not accept ordering of its own"):
            led.add_remediation(defect["id"], action="refactor", ladder_rung=1,
                                depends_on=["rem_0001"])
        item = led.add_remediation(defect["id"], action="refactor", ladder_rung=1)
        self.assertNotIn("depends_on", item)

        # ...and the surviving channel is real: validated on write, and levelled into waves.
        with self.assertRaises(LedgerError, msg="the pin DAG is real, not aspirational"):
            led.add_pin(kind="defect", title="downstream", severity="low", confidence="extracted",
                        provenance=[{"source": "s", "detail": "d"}], as_is={"description": "y"},
                        depends_on=["pin_9999"])
        later = led.add_pin(kind="defect", title="downstream", severity="low", confidence="extracted",
                            provenance=[{"source": "s", "detail": "d"}], as_is={"description": "y"},
                            depends_on=[defect["id"]])
        import buildloop
        waves = buildloop.waves(led)
        self.assertLess(next(i for i, w in enumerate(waves) if defect["id"] in w),
                        next(i for i, w in enumerate(waves) if later["id"] in w))

    def test_resolve_gated_on_done_items(self):
        """Every call here states the observation, so the only thing under test is the remediation
        gate — a refusal that could be either rule proves neither."""
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "flip")
        obs = dict(evidence="ran it; the drift is gone", rung="observed")
        with self.assertRaises(LedgerError) as ctx:                # no silent close
            led.resolve(pin["id"], **obs)
        self.assertIn("remediation", str(ctx.exception))
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2,
                                   canonical_target="db")
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], **obs)
        self.assertIn("remediation", str(ctx.exception))
        led.set_remediation_status(pin["id"], item["id"], "done")
        self.assertEqual(led.resolve(pin["id"], **obs)["state"], "resolved")


class TestHonestVerification(unittest.TestCase):
    """v0.7: `resolved` means observed, so a claim that could not be observed needs somewhere
    honest to land. Without `correctness_unknown` every pressure pointed at a false `resolved`."""

    def _done(self, led):
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "flip")
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2, canonical_target="db")
        led.set_remediation_status(pin["id"], item["id"], "done")
        return pin

    def test_self_check_rung_cannot_resolve(self):
        led = make_ledger()
        pin = self._done(led)
        pin["verification"] = {"rung": "self_check"}
        with self.assertRaises(LedgerError):
            led.resolve(pin["id"])
        pin["verification"]["rung"] = "observed"
        self.assertEqual(led.resolve(pin["id"])["state"], "resolved")

    def test_cross_derived_also_resolves(self):
        led = make_ledger()
        pin = self._done(led)
        pin["verification"] = {"rung": "cross_derived"}
        self.assertEqual(led.resolve(pin["id"])["state"], "resolved")

    def test_unknown_records_what_was_tried_and_what_blocked(self):
        led = make_ledger()
        pin = self._done(led)
        out = led.mark_correctness_unknown(
            pin["id"], blocked_by="no runnable env for the payments path",
            attempted=["tests", "typecheck", "smoke_probe"], determinism="D1", rung="re_read")
        self.assertEqual(out["state"], "correctness_unknown")
        self.assertEqual(out["verification"]["attempted"], ["tests", "typecheck", "smoke_probe"])

    def test_unknown_refuses_a_shrug(self):
        led = make_ledger()
        pin = self._done(led)
        with self.assertRaises(LedgerError):                       # nothing was attempted
            led.mark_correctness_unknown(pin["id"], blocked_by="dunno", attempted=[])
        with self.assertRaises(LedgerError):                       # no reason given
            led.mark_correctness_unknown(pin["id"], blocked_by="  ", attempted=["tests"])

    def test_unknown_is_not_a_black_hole(self):
        """It blocks closure, so it must reach someone. A state on no surface is lost work — and
        what puts the pin on the surface is its STATE (`interview_view` selects
        `correctness_unknown`), not a question written over whatever was there."""
        led = make_ledger()
        pin = self._done(led)
        led.mark_correctness_unknown(pin["id"], blocked_by="no env", attempted=["tests"])
        view = [p["id"] for p in led.interview_view()]
        self.assertIn(pin["id"], view)

    def test_the_unknown_fork_never_replaces_a_fork_that_exists(self):
        """The overwrite v0.16 removed from `cross_derive`, still in place on the door beside it.
        Reproduced on a pin the human had DECIDED: their own `s3|gcs` fork was simply gone, replaced
        by an agent-authored `retry|add_check|takeover|narrow|accept`. `question.options[].id` is
        the carrier the offered-options rule anchors on at both doors, so rewriting it is deciding
        what the human is allowed to choose next."""
        led = make_ledger()
        pin = self._done(led)
        theirs = json.loads(json.dumps(pin["question"]))
        led.mark_correctness_unknown(pin["id"], blocked_by="no env", attempted=["tests"])
        self.assertEqual(pin["question"], theirs)
        # and a pin with no fork still gains one — the state has to ask somebody something
        bare = add_simple_pin(led, kind="defect", question=None)
        led.mark_correctness_unknown(bare["id"], blocked_by="no env", attempted=["tests"])
        self.assertIn("What now?", bare["question"]["prompt"])

    def test_unverifiable_blocker_outranks_information_gain(self):
        led = make_ledger()
        hub = add_simple_pin(led, title="hub", severity="medium")           # high fan-out
        for _ in range(3):
            add_simple_pin(led, severity="low")["depends_on"].append(hub["id"])
        pin = self._done(led)
        led.mark_correctness_unknown(pin["id"], blocked_by="no env", attempted=["tests"])
        self.assertEqual(led.interview_view()[0]["id"], pin["id"])

    def test_unknown_does_not_satisfy_a_dependent(self):
        """A dependent may not build on work whose correctness was never established."""
        import buildloop
        led = make_ledger()
        upstream = self._done(led)
        led.mark_correctness_unknown(upstream["id"], blocked_by="no env", attempted=["tests"])
        downstream = add_simple_pin(led)
        downstream["depends_on"].append(upstream["id"])
        led.decide(downstream["id"], "opt_a", "r", "flip")
        self.assertNotIn(downstream["id"], [p["id"] for p in buildloop.ready(led)])

    def test_older_ledger_is_readable_not_stranded(self):
        """An additive schema that rejects its own older files strands the one durable artifact."""
        led = make_ledger()
        led.save()
        with open(led.path, "r+", encoding="utf-8") as fh:
            data = json.load(fh)
            data["version"] = "0.5"
            fh.seek(0)
            json.dump(data, fh)
            fh.truncate()
        self.assertEqual(Ledger(led.path).data["version"], SCHEMA_VERSION)  # upgraded on read


def legacy_cascade_ledger(version: str = "0.9") -> str:
    """A ledger exactly as the pre-v0.11 cascade wrote one, written as BYTES rather than through
    this runtime — which now refuses that shape, so nothing else could produce it.

    `source` names the policy, `evidence` is `decide()`'s old parameter default, and neither
    `policy_id` nor a quote exists. Every ledger written before v0.11 holds this.
    """
    path = os.path.join(tempfile.mkdtemp(), "ledger.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({
            "version": version,
            "pins": [{"id": "pin_0001", "kind": "contract_mismatch", "title": "role enum drift",
                      "severity": "medium", "confidence": "extracted",
                      "provenance": [{"source": "contract_recon", "detail": "d"}],
                      "state": "decided", "resolution_mode": "policy_default", "anchors": [],
                      "as_is": {}, "to_be": None, "question": None, "brainstorm": None,
                      "decision": {"event_id": "ev_0001", "outcome": "db"},
                      "depends_on": [], "remediation": []}],
            "decision_log": [{"id": "ev_0001", "pin_id": "pin_0001", "timestamp": "2026-01-01T00:00:00+00:00",
                              "outcome": "db", "rationale": "keep the DB as the source of truth",
                              "flip_criteria": "an exception to policy pol_0001 surfaces",
                              "source": "policy:pol_0001", "evidence": "transcribed"}],
            "policies": [{"id": "pol_0001", "applies_to": {"kind": "contract_mismatch"},
                          "rule": "keep the DB as the source of truth", "default_outcome": "db",
                          "exceptions": []}],
        }, fh)
    return path


class TestARuleEnforcedAtTheWriteGovernsNoExistingFile(unittest.TestCase):
    """v0.13. `cascaded` (v0.11) was checked in `decide()` and nowhere else, so every ledger already
    on disk still said `transcribed` — the parameter default the old cascade fell through to — and
    all three surfaces read it literally: `{"transcribed": 1}`, *"1 relayed by an agent"*, and a map
    card warning that nothing separated it from an invention. Three faithful readings of a field,
    all three false about the user's own elected policy."""

    def test_a_pre_v0_11_cascade_is_not_read_as_a_relay(self):
        led = Ledger(legacy_cascade_ledger())
        self.assertEqual(led.summary()["decisions_by_evidence"], {"cascaded": 1})

    def test_the_version_stamp_is_not_raised_over_content_that_does_not_satisfy_it(self):
        """A bare load+save used to restamp that file to the runtime's own version, so it CLAIMED
        invariants it does not satisfy. The stamp is a floor now, and the refusal is reported."""
        path = legacy_cascade_ledger()
        led = Ledger(path)
        self.assertEqual(led.data["version"], "0.9")
        self.assertEqual(led.summary()["pre_rule_events"], {"cascade_rung": 1})
        led.save()
        with open(path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk["version"], "0.9")

    def test_nothing_in_the_append_only_log_is_rewritten(self):
        """The alternative shape — migrate the events — is refused on the entity's own terms. The
        reading is corrected where reading happens; the bytes stay the writer's."""
        path = legacy_cascade_ledger()
        led = Ledger(path)
        led.save()
        with open(path, encoding="utf-8") as fh:
            event = json.load(fh)["decision_log"][0]
        self.assertEqual(event["evidence"], "transcribed")
        self.assertNotIn("policy_id", event)

    def test_a_conforming_older_ledger_still_gets_the_stamp(self):
        """The floor is about content, not about age: an old file this runtime could have written
        is raised exactly as before, or the rule would strand every ledger that is merely old."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.decide(pin["id"], "opt_a", "r", "flip")
        led.save()
        with open(led.path, "r+", encoding="utf-8") as fh:
            data = json.load(fh)
            data["version"] = "0.9"
            fh.seek(0)
            json.dump(data, fh)
            fh.truncate()
        reloaded = Ledger(led.path)
        self.assertEqual(reloaded.data["version"], SCHEMA_VERSION)
        self.assertEqual(reloaded.summary()["pre_rule_events"], {})

    def test_the_rung_is_read_off_the_carrier_the_writer_left(self):
        """`policy:` in `source` is what says "this is a cascade" at every version of the schema —
        `decide()` has never accepted any other source for one — so it is what the read uses when
        the explicit v0.11 field is absent."""
        import ledger as ledger_mod
        old = {"id": "ev_0001", "source": "policy:pol_0001", "evidence": "transcribed"}
        self.assertEqual(ledger_mod.decision_rung(old), "cascaded")
        self.assertEqual(ledger_mod.cascaded_from(old), "pol_0001")
        relay = {"id": "ev_0002", "source": "interview", "evidence": "transcribed"}
        self.assertEqual(ledger_mod.decision_rung(relay), "transcribed")
        self.assertIsNone(ledger_mod.cascaded_from(relay))
        self.assertEqual(ledger_mod.decision_rung({"id": "ev_0003", "source": "interview"}), "")

    def test_the_floor_only_holds_what_one_event_alone_decides(self):
        """The v0.12 offered-options rule needs the pin's `question`, which is mutable — an option
        absent today does not prove it was absent then. A file is not held below its floor on
        evidence that weak, and the narrowness is asserted rather than left to be assumed."""
        import ledger as ledger_mod
        path = legacy_cascade_ledger()
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["decision_log"][0].update(evidence="cascaded", policy_id="pol_0001")
        data["pins"][0]["question"] = {"prompt": "?", "options": [{"id": "api", "label": "api"}]}
        self.assertEqual(ledger_mod.nonconforming(data), {})   # outcome "db" is not offered

    def test_the_floor_replays_the_writers_own_rules_rather_than_one_it_remembered(self):
        """v0.15. The reader knew ONE write-time rule, hand-copied, and nothing forced the next one
        to gain a reader — the v0.13 lesson, shipping inside v0.13's own fix.

        The declaration below is the gate: every rule in the writer's table must carry an event
        that violates it, asserted by set EQUALITY, so a rule added to `EVENT_RULES` without a
        reachable failure fails here instead of being trusted."""
        import ledger as ledger_mod
        ok = {"id": "ev_0001", "pin_id": "pin_0001", "outcome": "db", "rationale": "r",
              "flip_criteria": "an exception surfaces", "source": "interview",
              "evidence": "transcribed"}
        self.assertEqual(ledger_mod.event_violations(ok), [])
        breaks = {
            "committing_source": {"source": "brainstorm"},
            "evidence_rung": {"evidence": None},          # written before the field existed
            "cascade_rung": {"source": "policy:pol_0001"},
            "cascade_policy_id": {"evidence": "cascaded", "source": "policy:pol_0001",
                                  "policy_id": ""},
            "flip_criteria": {"flip_criteria": ""},
            "flip_signal_source": {"flip_signal": {"source": "vibes"}},
            # v0.16. Absence conforms (every pre-v0.16 event produced `decided`, which is what the
            # absence means); a value naming a state no election can produce does not.
            "settled_state": {"settles_as": "resolved"},
        }
        self.assertEqual(set(breaks), {name for name, _, _ in ledger_mod.EVENT_RULES},
                         "a rule in the writer's table with no sample here is a rule nobody proved "
                         "the floor can report")
        for rule, mutation in breaks.items():
            with self.subTest(rule=rule):
                event = dict(ok, **mutation)
                self.assertIn(rule, ledger_mod.event_violations(event))
                self.assertEqual(ledger_mod.nonconforming({"decision_log": [event]}).get(rule),
                                 ["ev_0001"], "the floor must NAME the rule, not merely refuse")
                # and the same rule refuses the write, from the same table — one implementation
                led = make_ledger()
                pin = add_simple_pin(led, severity="medium")
                kwargs = {"source": event["source"], "evidence": event["evidence"],
                          "flip_criteria": event["flip_criteria"],
                          "policy_id": event.get("policy_id") or None}
                if "flip_signal" in event:
                    kwargs["flip_signal"] = event["flip_signal"]
                if "settles_as" in event:
                    kwargs["settles_as"] = event["settles_as"]
                with self.assertRaises(LedgerError):
                    led.decide(pin["id"], "opt_a", "r", **kwargs)

    def test_nothing_is_appended_when_a_rule_refuses_the_write(self):
        """The event is now built before it is checked, so 'built' must not mean 'written'."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        with self.assertRaises(LedgerError):
            led.decide(pin["id"], "opt_a", "r", "flip", source="brainstorm")
        self.assertEqual(led.data["decision_log"], [])
        self.assertEqual(pin["state"], "needs_input")

    def test_the_spec_version_and_the_runtime_agree(self):
        """`SCHEMA_VERSION` is stamped into `policy_hash` as `spec_version`, so a spec that has moved
        past it makes the trail cite a rule set by the wrong name. Two carriers, one fact."""
        spec = os.path.join(os.path.dirname(__file__), "..", "src", "core",
                            "decisions-ledger-spec.md")
        with open(spec, encoding="utf-8") as fh:
            heading = fh.readline().strip()
        self.assertEqual(heading, f"# Decisions Ledger — Spec v{SCHEMA_VERSION}")


class TestWhyAStandingRuleMustBeWeighed(unittest.TestCase):
    """One classification, because two surfaces had one each and printed different totals for one
    ledger: the map badged every weak rung, the projected `AGENTS.md` counted every missing quote.
    Neither was wrong on its own terms, which is why a reader could act on neither.

    Here rather than on either surface for the reason `decision_rung` is here: the module that owns
    the schema answers questions about the schema, and a rule with two implementations has already
    begun to drift."""

    BASE = {"id": "pol_0001", "applies_to": {}, "rule": "r", "default_outcome": "x"}

    def test_the_reasons_are_the_declared_ones(self):
        from ledger import POLICY_WEAKNESS, policy_weakness
        cases = {
            "no_rung": dict(self.BASE),
            "unknown_rung": dict(self.BASE, evidence="oracle"),
            "unquoted_relay": dict(self.BASE, evidence="transcribed"),
        }
        for expected, policy in cases.items():
            self.assertEqual(policy_weakness(policy), expected)
        self.assertEqual(set(cases), set(POLICY_WEAKNESS),
                         "a weakness code with no case here is one no surface has been shown")

    def test_a_properly_elected_rule_is_not_weak(self):
        """A relay WITH the words is the rung the spec permits — permitted *because* the quote is
        there to be weighed. Badging it as missing something would say the opposite."""
        from ledger import policy_weakness
        self.assertEqual(policy_weakness(dict(self.BASE, evidence="elicited")), "")
        self.assertEqual(policy_weakness(dict(self.BASE, evidence="brief")), "")
        self.assertEqual(policy_weakness(dict(self.BASE, evidence="transcribed",
                                              human_answer="take it for all of these")), "")

    def test_the_rung_a_policy_may_carry_is_the_schemas(self):
        """`unknown_rung` is defined against `POLICY_EVIDENCE`, so a rung added there stops being
        unknown on the day it is added — not on the day someone remembers this function."""
        from ledger import POLICY_EVIDENCE, policy_weakness
        for rung in POLICY_EVIDENCE:
            self.assertNotEqual(policy_weakness(dict(self.BASE, evidence=rung, human_answer="q")),
                                "unknown_rung")


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
        self.assertEqual(data["version"], SCHEMA_VERSION)
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


class TestLeavingTheOpenSetIsGovernedToo(unittest.TestCase):
    """v0.16 — the SECOND predicate.

    `unasked_verdict` governs what may be written onto a pin nobody was asked about. Nothing
    governed whether a pin may leave the open set **at all**, so four doors answered that question
    independently and one of them answered it with nothing. Each test below is one of the four,
    written from the reproduction that found it rather than from the fix.
    """

    def _decided_defect(self, led, severity="blocker"):
        pin = led.add_pin(kind="defect", title="race in the payment retry", severity=severity,
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "double charge under retry"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        return pin

    # -- 1. correctness_unknown blocks closure, and `rung: None` is a claim ---------------------

    def test_a_pin_that_cannot_establish_its_correctness_does_not_resolve(self):
        """The reported chain: add_pin(defect, blocker) -> add_remediation -> status done ->
        mark_correctness_unknown(no rung) -> resolve. The last call used to succeed, because the
        v0.7 rung check ran only `if rung is not None` and this door writes None by default."""
        led = make_ledger()
        pin = self._decided_defect(led)
        led.mark_correctness_unknown(pin["id"], blocked_by="no runnable payments environment",
                                     attempted=["tests", "typecheck", "smoke_probe"])
        self.assertIsNone(pin["verification"]["rung"])
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], evidence="the retry path looks right now")
        self.assertIn("unverified", str(ctx.exception))
        self.assertEqual(pin["state"], "correctness_unknown")

    def test_a_weak_envelope_keeps_blocking_after_the_state_is_answered(self):
        """The same hole one step later: answering the correctness fork returns the pin to
        `decided`, and the verification envelope it left behind still says nothing was observed."""
        led = make_ledger()
        pin = self._decided_defect(led, severity="medium")
        led.mark_correctness_unknown(pin["id"], blocked_by="no env", attempted=["tests"])
        led.decide(pin["id"], "retry", "r", "if the env appears")
        self.assertEqual(pin["state"], "decided")
        with self.assertRaises(LedgerError):
            led.resolve(pin["id"], evidence="looks fine")
        pin_state = led.resolve(pin["id"], evidence="ran it against staging; no double charge",
                                rung="observed")
        self.assertEqual(pin_state["state"], "resolved")
        self.assertEqual(pin["verification"]["blocked_by"], "no env",
                         "what blocked verification is history, not something a close erases")

    def test_a_claimed_rung_needs_the_observation_it_rests_on(self):
        led = make_ledger()
        pin = self._decided_defect(led, severity="medium")
        led.mark_correctness_unknown(pin["id"], blocked_by="no env", attempted=["tests"])
        led.decide(pin["id"], "retry", "r", "f")
        with self.assertRaises(LedgerError):
            led.resolve(pin["id"], rung="observed")               # no evidence
        with self.assertRaises(LedgerError):
            led.resolve(pin["id"], evidence="e", rung="re_read")  # not a closing rung

    def test_the_rung_opens_the_gate_it_is_the_key_to(self):
        """`rung` was added as the way out of `correctness_unknown` and could not open it. The
        refusal was returned on the STATE, before anything read `verification.rung`: `resolve`
        writes the rung and calls `_settle`, `_settle` re-asks the predicate, and the state has not
        moved — so the door raised the very refusal whose text (and whose shipped playbook) told the
        caller to pass `rung`. A gate with no gate-opening move is a wall."""
        led = make_ledger()
        pin = self._decided_defect(led, severity="blocker")
        led.mark_correctness_unknown(pin["id"], blocked_by="no runnable payments environment",
                                     attempted=["tests", "typecheck", "smoke_probe"])
        with self.assertRaises(LedgerError):                 # still no observation: still refused
            led.resolve(pin["id"], evidence="the retry path looks right now")
        out = led.resolve(pin["id"], evidence="replayed the retry against staging; one charge",
                          rung="observed")
        self.assertEqual(out["state"], "resolved")
        self.assertEqual(pin["verification"]["blocked_by"], "no runnable payments environment",
                         "what blocked verification is history, not something the close erases")

    def test_a_missing_envelope_is_the_weakest_reading_not_permission(self):
        """The other half of the same carrier, and the half 691 tests missed.

        Deleting the `state == "correctness_unknown"` refusal was right; reading the envelope as
        `if verification is not None` was the hole it left. A `ledger.json` whose pin is
        `state: "correctness_unknown"` with its remediation done and NO `verification` key returned
        `would_settle`, and `resolve(evidence="I looked")` closed it green — the exact defect the
        state exists to prevent, entered from the other side. Written as the file it was reproduced
        on, because that file class is the one thing a rule enforced at the write never governs.
        """
        led = make_ledger()
        pin = self._decided_defect(led, severity="blocker")
        pin["state"] = "correctness_unknown"                 # a file that already exists
        pin.pop("verification", None)
        self.assertEqual(led.settlement_verdict(pin, "resolve"), "unverified")
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], evidence="I looked")
        self.assertIn("unverified", str(ctx.exception))
        self.assertEqual(pin["state"], "correctness_unknown")
        # and the gate still has its opening move
        self.assertEqual(led.resolve(pin["id"], evidence="replayed it on staging; one charge",
                                     rung="observed")["state"], "resolved")

    def test_no_envelope_at_all_is_not_weaker_only_where_the_state_says_so(self):
        """Absence is read the same way on every pin, not only on the one whose state confesses.
        A `decided` pin with its remediation done and nothing recorded about verification has
        observed nothing either, and `resolved` means observed."""
        led = make_ledger()
        pin = self._decided_defect(led, severity="medium")
        self.assertIsNone(pin.get("verification"))
        self.assertEqual(led.settlement_verdict(pin, "resolve"), "unverified")
        with self.assertRaises(LedgerError):
            led.resolve(pin["id"], evidence="the code is written")
        self.assertEqual(led.resolve(pin["id"], evidence="ran it; no double charge",
                                     rung="observed")["state"], "resolved")

    def test_the_closed_check_runs_before_every_door_including_the_mirror_one(self):
        """The mirror door was evaluated BEFORE the `CLOSED_STATES` check, so `resolved` was an
        ACCEPTING condition for it: resolve -> mark_correctness_unknown took a pin out of the closed
        set and back into it with four agent-only calls, no `reopen`, and nothing recording why
        finished work had been un-finished. The rule this table introduced, falsified by the
        table's own ordering."""
        led = make_ledger()
        pin = self._decided_defect(led, severity="blocker")
        led.resolve(pin["id"], evidence="observed: no longer reproduces", rung="observed")
        self.assertEqual(led.settlement_verdict(pin, "correctness_unknown"), "already_closed")
        with self.assertRaises(LedgerError) as ctx:
            led.mark_correctness_unknown(pin["id"], blocked_by="no oracle after all",
                                         attempted=["tests"])
        self.assertIn("Reopen it first", str(ctx.exception))
        self.assertEqual(pin["state"], "resolved")
        # and the way back is the arc that records why — after which the door is open again
        led.reopen(pin["id"], reason="the double charge came back in production")
        self.assertEqual(led.mark_correctness_unknown(
            pin["id"], blocked_by="no oracle after all", attempted=["tests"])["state"],
            "correctness_unknown")

    def test_a_refusal_does_not_call_an_election_the_absence_of_one(self):
        """`not_decided` read 'nothing has been elected on this pin yet (state accepted)'. It is a
        refusal a caller is meant to act on, and it described an elected pin as an unelected one."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="low")
        self.assertEqual(led.settlement_verdict(pin, "correctness_unknown"), "not_decided")
        with self.assertRaises(LedgerError) as ctx:
            led.mark_correctness_unknown(pin["id"], blocked_by="b", attempted=["tests"])
        self.assertNotIn("nothing has been elected", str(ctx.exception))
        self.assertIn("needs_input", str(ctx.exception))

    def test_reading_a_ledger_is_never_the_operation_that_fails_on_it(self):
        """One event whose `settles_as` names a state this runtime does not know made `summary()`
        raise — over the wire, `ledger_summary` came back `isError` — on exactly the file class
        `nonconforming()` exists to describe. The summary is what an agent reads BEFORE acting, so
        a file it cannot read is a file it acts on blind. The event is not lost: the same rule table
        reports it under `pre_rule_events`."""
        led = make_ledger()
        add_simple_pin(led, severity="low")
        led.decide("pin_0001", "opt_a", "r", "f")
        led.data["decision_log"][-1]["settles_as"] = "archived"    # a state no door produces
        led.save()
        reread = Ledger(led.path)
        summary = reread.summary()
        self.assertEqual(summary["settlements_by_door"], {})
        self.assertEqual(summary["pre_rule_events"], {"settled_state": 1},
                         "skipped in the count, named in the surface that exists to name it")

    # -- 2. deferring is an election ------------------------------------------------------------

    def test_deferring_is_recorded_as_the_election_it_is(self):
        """`defer` moved a pin into SETTLED_STATES on ONE check — no threshold, no election, no
        quote, nothing appended. It had zero test coverage anywhere, which is why it survived."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="blocker", kind="open_decision",
                             as_is=None, to_be=None,
                             question={"prompt": "Session or JWT?",
                                       "options": [{"id": "session", "label": "server sessions"},
                                                   {"id": "jwt", "label": "stateless JWT"}],
                                       "allow_freeform": True})
        before = len(led.data["decision_log"])
        led.defer(pin["id"], rationale="auth is out of the v1 slice",
                  flip_criteria="a second client appears that cannot hold a cookie",
                  human_answer="not now — v1 is one web client")
        self.assertEqual(pin["state"], "deferred")
        events = led.data["decision_log"][before:]
        self.assertEqual(len(events), 1, "one settlement, one entry — never two carriers")
        self.assertEqual((events[0]["outcome"], events[0]["settles_as"]), ("defer", "deferred"))
        self.assertEqual(events[0]["human_answer"], "not now — v1 is one web client",
                         "a deferral is an answer, and an answer nobody can read is a claim")
        self.assertTrue(events[0]["flip_criteria"],
                        "a deferral with no return condition is a deletion with better manners")

    def test_a_deferral_needs_a_return_condition(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        with self.assertRaises(LedgerError):
            led.defer(pin["id"], rationale="later", flip_criteria="", human_answer="not now")

    def test_no_door_settles_a_pin_whose_work_is_finished(self):
        """The LOW finding, generalized: `record_decision` had no settled check while
        `unasked_verdict` refused the same pin as `already_settled`. One question, one answer."""
        led = make_ledger()
        pin = self._decided_defect(led, severity="medium")
        led.resolve(pin["id"], evidence="observed: the double charge no longer reproduces",
                    rung="observed")
        for door in ("decide", "accept", "defer", "resolve"):
            with self.subTest(door=door):
                self.assertEqual(led.settlement_verdict(pin, door), "already_closed")
        with self.assertRaises(LedgerError):
            led.decide(pin["id"], "opt_a", "r", "f")
        with self.assertRaises(LedgerError):
            led.defer(pin["id"], rationale="r", flip_criteria="f", human_answer="not now")

    def test_a_decided_pin_is_still_re_electable_and_a_closed_one_is_not(self):
        """The asymmetry is the fix, not an exception to it: correcting yourself is not a second
        close, and the append-only log keeps both events."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.decide(pin["id"], "opt_a", "r", "f")
        self.assertEqual(led.settlement_verdict(pin, "decide"), "would_settle")
        self.assertEqual(led.unasked_verdict(pin, "opt_a"), "already_settled",
                         "an UNASKED write may not touch it either way")
        led.decide(pin["id"], "opt_b", "r", "f")
        self.assertEqual(pin["decision"]["outcome"], "opt_b")
        self.assertEqual(len([e for e in led.data["decision_log"]
                              if e["id"].startswith("ev_")]), 2)

    def test_accept_applies_to_a_design_concern_and_the_rule_lives_in_the_predicate(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")            # a contract_mismatch
        self.assertEqual(led.settlement_verdict(pin, "accept"), "wrong_kind")
        with self.assertRaises(LedgerError):
            led.accept(pin["id"], rationale="r", flip_criteria="f", human_answer="leave it")

    # -- 3. `resolution_mode: "asked"` binds ----------------------------------------------------

    def test_a_reopened_pin_is_never_re_defaulted_silently(self):
        """The comment at the reopen site asserted this for four versions. Nothing read the field:
        both readers compared against `proposed_default` only, so a policy cascade re-decided a
        truth an upheld challenge had just reopened."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.decide(pin["id"], "opt_a", "r", "f")
        led.challenge(pin["id"], target="decision", challenge_class="unstated_assumption",
                      argument="the enum widened upstream", severity="medium", upheld=True)
        self.assertEqual(pin["resolution_mode"], "asked")
        self.assertEqual(led.unasked_verdict(pin, "opt_a"), "must_be_asked")
        radius = led.policy_preview({"severity": "medium"}, "opt_a")
        self.assertEqual(radius["must_be_asked"], [pin["id"]])
        self.assertEqual(radius["would_decide"], [])

    def test_a_contested_claim_is_never_re_defaulted_silently(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.cross_derive(pin["id"], claim="the enum is closed", agreement="disagree", derivations=[
            {"provider": "anthropic", "model": "m", "result": "closed"},
            {"provider": "openai", "model": "n", "result": "open"}])
        self.assertEqual(led.unasked_verdict(pin, "opt_a"), "must_be_asked")

    # -- 4. the cross-derivation arc reopens the way the other two arcs do -----------------------

    def test_a_disagreement_is_appended_before_anything_moves(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.decide(pin["id"], "opt_a", "r", "f")
        offered = [o["id"] for o in pin["question"]["options"]]
        record = led.cross_derive(pin["id"], claim="the enum is closed", agreement="disagree",
                                  derivations=[
                                      {"provider": "anthropic", "model": "m", "result": "closed"},
                                      {"provider": "openai", "model": "n", "result": "open"}])
        event = led.data["decision_log"][-1]
        self.assertTrue(event["id"].startswith("xdr_"))
        self.assertEqual((event["pin_id"], event["agreement"], event["reopened"]),
                         (pin["id"], "disagree", True))
        self.assertEqual(record["event_id"], event["id"])
        self.assertEqual([o["id"] for o in pin["question"]["options"]], offered,
                         "question.options[].id is the carrier the offered-options rule anchors "
                         "on — an agent that rewrites it decides what the human may choose next")
        self.assertEqual(pin["state"], "needs_input")

    def test_a_disagreement_does_not_un_close_finished_work(self):
        led = make_ledger()
        pin = self._decided_defect(led, severity="medium")
        led.resolve(pin["id"], evidence="observed: no longer reproduces", rung="observed")
        led.cross_derive(pin["id"], claim="the retry is idempotent", agreement="disagree",
                         derivations=[{"provider": "anthropic", "model": "m", "result": "yes"},
                                      {"provider": "openai", "model": "n", "result": "no"}])
        event = led.data["decision_log"][-1]
        self.assertEqual((event["id"][:4], event["reopened"]), ("xdr_", False))
        self.assertEqual(pin["state"], "resolved", "un-closing finished work has its own arc")

    def test_a_decided_pin_is_on_the_reopened_side_of_the_closed_line(self):
        """The spec said "an **open** pin moves to needs_input", as though open and closed
        exhausted the states. The predicate is `state not in CLOSED_STATES`, and `decided` is in
        `SETTLED_STATES` but not in `CLOSED_STATES` — which is the whole reason the two sets were
        split: a human election is correctable, finished work is not un-finished from the side."""
        from ledger import CLOSED_STATES, SETTLED_STATES
        self.assertIn("decided", SETTLED_STATES)
        self.assertNotIn("decided", CLOSED_STATES)
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.decide(pin["id"], "opt_a", "r", "f")
        led.cross_derive(pin["id"], claim="c", agreement="disagree", derivations=[
            {"provider": "anthropic", "model": "m", "result": "a"},
            {"provider": "openai", "model": "n", "result": "b"}])
        self.assertTrue(led.data["decision_log"][-1]["reopened"])
        self.assertEqual((pin["state"], pin["substate"]), ("needs_input", "contested"))

    def test_a_pin_with_no_fork_gains_one_rather_than_having_one_replaced(self):
        led = make_ledger()
        pin = led.add_pin(kind="defect", title="d", severity="medium", confidence="extracted",
                          provenance=[{"source": "x", "detail": "y"}], as_is={"description": "d"})
        led.cross_derive(pin["id"], claim="c", agreement="disagree", derivations=[
            {"provider": "anthropic", "model": "m", "result": "a"},
            {"provider": "openai", "model": "n", "result": "b"}])
        self.assertEqual([o["id"] for o in pin["question"]["options"]], ["d0", "d1", "neither"])

    # -- 5. a policy scope names real fields -----------------------------------------------------

    def test_a_scope_key_that_is_not_a_pin_field_is_refused(self):
        """`pin.get("nope") == None` is True of every pin, so this matched the whole ledger — and
        the radius is exactly what a human elects a policy from."""
        led = make_ledger()
        add_simple_pin(led, severity="medium")
        with self.assertRaises(LedgerError) as ctx:
            led.policy_preview({"nope": None}, "opt_a")
        self.assertIn("not a Pin field", str(ctx.exception))
        self.assertEqual(led.policy_preview({"severity": "medium"}, "opt_a")["would_decide"],
                         ["pin_0001"], "a real key still selects")

    def test_the_scopeable_fields_are_the_fields_the_writers_write(self):
        """`PIN_FIELDS` is a declaration, so it is held to the envelope rather than trusted: a
        field a writer adds without becoming scopeable would silently be unmatchable, and a field
        listed here that nobody writes would be a scope key that selects nothing."""
        import ledger as ledger_mod
        led = make_ledger()
        # A defect, so the walk below can end at `resolved`: the door's kind escape is what admits a
        # pin that is no longer in `decided`, and the order here is the settlement rules' rather
        # than a convenience. `correctness_unknown` takes a pin out of `decided` and NOT out of
        # `resolved` (the way back from finished work is `reopen`), and the disagreement that writes
        # `substate` may only touch a pin that is not closed — so: decided -> unknown -> contested
        # -> resolved on a later observation.
        pin = add_simple_pin(led, kind="defect", severity="medium", cluster_id="cl_x",
                             depends_on=[], anchors=[{"node_id": "n_1", "loc": "a.py:1"}])
        led.add_proposals(pin["id"], [{"summary": "s"}])
        led.set_readiness(pin["id"], "ready", zone={"files": ["a.py"]}, evidence={})
        led.premortem(pin["id"], [{"class": "environment", "description": "d"}], guardrails=["g"])
        led.cross_derive(pin["id"], claim="c", agreement="agree", derivations=[
            {"provider": "anthropic", "model": "m", "result": "a"},
            {"provider": "openai", "model": "n", "result": "a"}])
        led.decide(pin["id"], "opt_a", "r", "f")
        item = led.add_remediation(pin["id"], action="align", ladder_rung=1)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.mark_correctness_unknown(pin["id"], blocked_by="b", attempted=["tests"])
        led.cross_derive(pin["id"], claim="c2", agreement="disagree", derivations=[
            {"provider": "anthropic", "model": "m", "result": "a"},
            {"provider": "openai", "model": "n", "result": "b"}])       # writes `substate`
        led.resolve(pin["id"], evidence="observed it on staging", rung="observed")
        led.data["pins"][0]["kind_detail"] = "x"      # only `other` writes it, and it is scopeable
        self.assertEqual(sorted(set(pin) - set(ledger_mod.PIN_FIELDS)), [],
                         "a Pin field no policy scope can name")
        self.assertEqual(sorted(set(ledger_mod.PIN_FIELDS) - set(pin)), [],
                         "a scopeable field no writer writes")


class TestComingBackIntoTheOpenSetIsGovernedToo(unittest.TestCase):
    """v0.17 — the mirror of `TestLeavingTheOpenSetIsGovernedToo`.

    v0.16 gave the five doors that settle a pin one predicate, one writer and one event. The two
    arcs that un-settle one had none of the three — and, invisibly from inside this module, no MCP
    tool either, so `settlement_verdict`'s own refusal (*"Reopen it first"*) named an arc no host
    could run. Each test below is written from that condition rather than from the fix.
    """

    def _resolved(self, led, severity="medium"):
        pin = led.add_pin(kind="defect", title="double charge on retry", severity=severity,
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="replayed it on staging; one charge", rung="observed")
        return pin

    # -- the arc the settlement table pointed at ------------------------------------------------

    def test_the_way_back_out_of_finished_work_exists_and_is_recorded(self):
        led = make_ledger()
        pin = self._resolved(led)
        with self.assertRaises(LedgerError) as ctx:
            led.mark_correctness_unknown(pin["id"], blocked_by="no oracle", attempted=["tests"])
        self.assertIn("Reopen it first", str(ctx.exception))
        event = led.reopen(pin["id"], reason="the double charge came back: 3 in 24h on prod")
        self.assertTrue(event["reopened"])
        self.assertEqual((pin["state"], pin["substate"], pin["resolution_mode"]),
                         ("needs_input", "reopened", "asked"))
        self.assertEqual(event["reason"], "the double charge came back: 3 in 24h on prod")

    def test_an_observation_about_an_unsettled_pin_is_recorded_and_moves_nothing(self):
        """`nothing_settled` is deliberately not a refusal. `cross_derive` was corrected to exactly
        this shape in v0.16, and dropping the event would lose the one signal `learning.divergences`
        and `challenger.premortem_required` both read."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        self.assertEqual(led.reopen_verdict(pin, "reopen"), "nothing_settled")
        event = led.reopen(pin["id"], reason="p95 blew the threshold again")
        self.assertFalse(event["reopened"])
        self.assertEqual(pin["state"], "needs_input")
        self.assertIsNone(pin.get("substate"))
        self.assertEqual([e["id"] for e in led.data["decision_log"]], ["rev_0001"])

    def test_upheld_and_reopened_are_two_facts_and_the_event_records_both(self):
        """Reading the move back off `substate` is the two-carriers bug v0.16 found one arc over:
        the substate is written by whichever arc moved the pin and is never cleared."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        event = led.challenge(pin["id"], target="to_be", challenge_class="unfalsifiable",
                              argument="the elected to_be has no verify that could fail",
                              severity="high", upheld=True)
        self.assertEqual((event["upheld"], event["reopened"]), (True, False))
        self.assertIsNone(pin.get("substate"))

    def test_a_reopen_states_what_was_observed_and_where_it_came_from(self):
        led = make_ledger()
        pin = self._resolved(led)
        for bad in ("", "   "):
            with self.assertRaises(LedgerError):
                led.reopen(pin["id"], reason=bad)
        with self.assertRaises(LedgerError):
            led.reopen(pin["id"], reason="r", fired="i felt like it")
        with self.assertRaises(LedgerError):
            led.reopen(pin["id"], reason="r", source="agent")
        self.assertEqual(led.data["decision_log"][-1]["id"], "stl_0001",
                         "a refused reopen appends nothing")

    def test_an_upheld_challenge_with_no_argument_is_an_assertion(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "f")
        with self.assertRaises(LedgerError) as ctx:
            led.challenge(pin["id"], target="decision", challenge_class="unstated_assumption",
                          argument="   ", severity="high", upheld=True)
        self.assertIn("argument", str(ctx.exception))

    # -- v0.20: what the settlement half does, the reopen half must do too ----------------------

    def _settled_chain(self, led):
        """Three pins, each closed the long way, each depending on the one before it."""
        chain = []
        for i, dep in enumerate(("", "chain")):
            pin = led.add_pin(kind="defect", title=f"link {i}", severity="medium",
                              confidence="extracted",
                              provenance=[{"source": "recon", "detail": "x"}],
                              as_is={"description": "d"},
                              depends_on=[chain[-1]["id"]] if chain else [])
            item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
            led.set_remediation_status(pin["id"], item["id"], "done")
            led.resolve(pin["id"], evidence="observed on staging", rung="observed")
            chain.append(pin)
        root = self._resolved(led)
        chain[0]["depends_on"] = [root["id"]]
        return [root] + chain

    def test_every_pin_the_cascade_moves_gets_the_record_a_settlement_gets(self):
        """`_settle` appends one `stl_` per pin it settles; `_reopen_minimal` appended nothing for
        any pin it moved. One `reopen` on the root took three `resolved` pins back into the open
        set and the log named one — finished work un-finished with no trail, which is the exact
        asymmetry the settlement work removed in the other direction."""
        led = make_ledger()
        root, dep, dep2 = self._settled_chain(led)
        event = led.reopen(root["id"], reason="the double charge came back: 3 in 24h on prod")

        moved = {p["id"] for p in (root, dep, dep2)}
        self.assertEqual({p["id"] for p in led.data["pins"] if p["state"] == "needs_input"}, moved)
        cascades = [e for e in led.data["decision_log"] if e["id"].startswith("cas_")]
        self.assertEqual([e["pin_id"] for e in cascades], [dep["id"], dep2["id"]],
                         "every pin the closure swept up owes a record; the origin already has one")
        for entry in cascades:
            self.assertEqual((entry["arc"], entry["via"], entry["from_state"], entry["to_state"],
                              entry["substate"]),
                             ("reopen", event["id"], "resolved", "needs_input", "reopened"))

    def test_the_origin_pin_gets_no_second_record_because_its_own_arc_event_carries_it(self):
        """`_settle`'s rule, in `_settle`'s words: the event is appended only where something is not
        already carrying it. The `rev_`/`chl_` event is about the origin pin and records `reopened`,
        so a `cas_` beside it would be two carriers for one fact."""
        led = make_ledger()
        root, _, _ = self._settled_chain(led)
        led.reopen(root["id"], reason="observed again in production")
        self.assertEqual([e["pin_id"] for e in led.data["decision_log"]
                          if e["id"].startswith("cas_") and e["pin_id"] == root["id"]], [])

    def test_the_radius_is_read_off_the_records_and_not_off_a_substate_nothing_clears(self):
        """Reproduced over real stdio at the tool: after a legitimate cascade, an unrelated reopen
        reported the earlier cascade's pins as its own — because the radius was every pin whose
        `substate` is `reopened`, and nothing anywhere clears that substate. The tool-level
        assertion is `test_mcp_tools`; this is the carrier it now reads."""
        led = make_ledger()
        root, dep, dep2 = self._settled_chain(led)
        first = led.reopen(root["id"], reason="p95 has been 1.4s for six days")
        self.assertEqual(led.cascaded_by(first["id"]), [dep["id"], dep2["id"]])

        alone = self._resolved(led)
        second = led.reopen(alone["id"], reason="a second, unrelated incident")
        self.assertEqual(led.cascaded_by(second["id"]), [],
                         "a pin nothing depends on has no radius, whatever the older pins carry")

    def test_both_arcs_hold_their_source_to_a_closed_vocabulary(self):
        """`reopen` always did; `challenge` took any string, so `source="interview"` — the value
        that means *a human elected this* — was accepted onto an event that then reopened a human's
        `decided` pin. An arc whose safety argument is that it never elects may not sign itself with
        the door that does."""
        import ledger as ledger_mod
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "f")
        with self.assertRaises(LedgerError) as ctx:
            led.challenge(pin["id"], target="decision", challenge_class="inconsistent",
                          argument="contradicts the pin one over", severity="high", upheld=True,
                          source="interview")
        self.assertIn("source must be one of", str(ctx.exception))
        self.assertEqual(pin["state"], "decided", "a refused challenge moves nothing")
        self.assertEqual([e for e in led.data["decision_log"] if e["id"].startswith("chl_")], [],
                         "a refused challenge appends nothing")
        self.assertEqual(ledger_mod._CHALLENGE_SOURCES,
                         tuple(f"challenge:{o}" for o in ledger_mod.CHALLENGE_ORIGINS),
                         "composed from the origins, never a second list beside them")
        # and the arc it is the twin of still refuses its own out-of-vocabulary source
        with self.assertRaises(LedgerError):
            led.reopen(pin["id"], reason="r", source="challenge:challenger")

    def test_the_challengers_other_mode_answers_the_same_way(self):
        """One role, two modes, one parameter, one default. Fixing the vocabulary at the mode that
        reopens and leaving it open at the mode that does not would teach the next reader that the
        rule is about consequences rather than about who is speaking."""
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError) as ctx:
            led.premortem(pin["id"], failure_modes=[{"class": "untested_path",
                                                     "description": "the nightly export breaks"}],
                          guardrails=["a fixture before any refactor"], source="interview")
        self.assertIn("source must be one of", str(ctx.exception))
        self.assertIsNone(pin.get("premortem"))

    def test_both_funnel_doors_refuse_finished_work(self):
        """`set_question` and `add_proposals` were added in one commit for the two halves of one
        funnel, and only one checked the state: `add_proposals` wrote `brainstorm.proposals` onto an
        `accepted` pin and onto a `deferred` one. `CLOSED_STATES` and not `SETTLED_STATES` at both,
        because `decided` is re-electable and exploring a live election is what a brainstorm is
        for."""
        import ledger as ledger_mod
        for state in ledger_mod.CLOSED_STATES:
            led = make_ledger()
            pin = self._resolved(led)
            pin["state"] = state          # the three closed states, whichever door produced it
            with self.assertRaises(LedgerError, msg=state) as ctx:
                led.add_proposals(pin["id"], [{"summary": "written onto finished work"}])
            self.assertIn("reopen", str(ctx.exception))
            self.assertIsNone(pin["brainstorm"])
            with self.assertRaises(LedgerError, msg=state):
                led.set_question(pin["id"], {"prompt": "p", "options": [],
                                             "allow_freeform": True})
        # `decided` is the state both doors deliberately still admit
        led = make_ledger()
        live = add_simple_pin(led)
        led.decide(live["id"], "opt_a", "r", "f")
        led.add_proposals(live["id"], [{"summary": "the alternative to what was elected"}])
        self.assertEqual(live["state"], "decided")

    def test_both_doors_that_compose_a_fork_require_the_way_out(self):
        """The byte-identical dict, at both doors. §10 introduced the rule at `set_question` and
        left it off `add_pin` — the older door, the busier one, composing the identical object."""
        led = make_ledger()
        closed = {"prompt": "closed menu the agent wrote",
                  "options": [{"id": "a", "label": "A"}]}
        with self.assertRaises(LedgerError) as at_add:
            led.add_pin(kind="ambiguity", title="t", severity="low", confidence="inferred",
                        provenance=[{"source": "recon", "detail": "x"}], question=dict(closed))
        bare = led.add_pin(kind="ambiguity", title="t2", severity="low", confidence="inferred",
                           provenance=[{"source": "recon", "detail": "x"}])
        with self.assertRaises(LedgerError) as at_set:
            led.set_question(bare["id"], dict(closed))
        self.assertEqual(str(at_add.exception), str(at_set.exception),
                         "one rule, one message: two doors onto one object may not answer "
                         "differently, and may not answer the same thing in two voices")
        self.assertEqual(led.data["pins"], [bare], "a refused fork creates no pin")

    # -- the structural half: one writer, and neither arc can decide ----------------------------

    @staticmethod
    def _tree():
        import ast
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read(), filename=path), ast

    def test_every_arc_reaches_the_single_writer_and_these_are_all_the_arcs(self):
        import ledger as ledger_mod
        tree, ast = self._tree()
        fns = {n.name: n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        callers = {name for name, fn in fns.items()
                   if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                          and c.func.attr == "_reopen_minimal" for c in ast.walk(fn))}
        self.assertEqual(callers, set(ledger_mod.REOPEN_ARCS),
                         "an arc that reopens a pin outside `_reopen_minimal` is a reopen with no "
                         "predicate and no minimality — which is how both of these shipped")
        self.assertEqual(sorted(ledger_mod.REOPEN_ARCS),
                         sorted(ledger_mod._SUBSTATE_BY_ARC),
                         "an arc with no substate, or a substate no arc leaves")

    def test_neither_arc_can_decide_anything(self):
        """The claim that makes these safe to expose where `decide` is not, asserted from the
        source: a reopen that can also set a state is the cluster fan-out flag under a new name."""
        import inspect

        import ledger as ledger_mod
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp"))
        import tools as mcp_tools
        for fn in (ledger_mod.Ledger.reopen, ledger_mod.Ledger.challenge,
                   ledger_mod.Ledger.set_question, ledger_mod.Ledger.add_proposals,
                   mcp_tools.ledger_reopen, mcp_tools.ledger_challenge,
                   mcp_tools.ledger_set_question, mcp_tools.ledger_add_proposals):
            params = set(inspect.signature(fn).parameters)
            self.assertEqual(params & {"outcome", "settles_as", "option_id", "default_outcome"},
                             set(), f"{fn.__qualname__} can elect")
        tree, ast = self._tree()
        fns = {n.name: n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in ("reopen", "challenge", "_reopen_minimal", "set_question", "add_proposals"):
            called = {c.func.attr for c in ast.walk(fns[name])
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
            self.assertEqual(called & {"decide", "_settle", "accept", "defer"}, set(),
                             f"{name} reaches a settlement door")

    # -- the two forks nobody could pose (§10, §17b) --------------------------------------------

    def test_a_pin_recorded_without_a_fork_can_be_given_one(self):
        led = make_ledger()
        pin = led.add_pin(kind="ambiguity", title="two auth flows", severity="high",
                          confidence="ambiguous", provenance=[{"source": "recon", "detail": "x"}])
        self.assertEqual((pin["state"], pin["question"]), ("detected", None))
        self.assertEqual(led.interview_view(), [])
        led.set_question(pin["id"], {"prompt": "Which flow is intended?",
                                     "options": [{"id": "session", "label": "server sessions"},
                                                 {"id": "jwt", "label": "stateless JWT"}],
                                     "allow_freeform": True})
        self.assertEqual(pin["state"], "needs_input")
        self.assertEqual([p["id"] for p in led.interview_view()], [pin["id"]])

    def test_a_fork_composed_after_the_fact_may_not_bound_the_human(self):
        led = make_ledger()
        pin = led.add_pin(kind="ambiguity", title="t", severity="low", confidence="inferred",
                          provenance=[{"source": "recon", "detail": "x"}])
        with self.assertRaises(LedgerError) as ctx:
            led.set_question(pin["id"], {"prompt": "p", "options": [{"id": "a", "label": "A"}]})
        self.assertIn("allow_freeform", str(ctx.exception))
        self.assertEqual(pin["state"], "detected")

    def test_it_will_not_replace_a_fork_that_already_exists(self):
        """`question.options[].id` is the carrier the offered-options rule anchors on at both
        election doors, so a general-purpose setter dismantles it from the side — which is exactly
        what `cross_derive` and `mark_correctness_unknown` were caught doing in v0.16."""
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.set_question(pin["id"], {"prompt": "p", "options": [{"id": "z", "label": "Z"}],
                                         "allow_freeform": True})
        self.assertEqual([o["id"] for o in pin["question"]["options"]], ["opt_a", "opt_b"])

    def test_posing_a_question_to_finished_work_is_the_reopen_arc(self):
        led = make_ledger()
        pin = self._resolved(led)
        with self.assertRaises(LedgerError) as ctx:
            led.set_question(pin["id"], {"prompt": "p", "options": [], "allow_freeform": True})
        self.assertIn("reopen", str(ctx.exception))

    def test_asking_the_brainstorm_no_longer_takes_the_fork_off_the_agenda(self):
        """`add_proposals` moves a pin out of `needs_input`, the view selected two states, and
        nothing moved it back — while `summary()` went on counting it under `open_questions`."""
        led = make_ledger()
        pin = add_simple_pin(led)
        led.add_proposals(pin["id"], [{"summary": "keep the DB enum", "effort": "S"},
                                      {"summary": "widen it", "effort": "M",
                                       "recommended": True}])
        self.assertEqual(pin["state"], "brainstorming")
        self.assertEqual([p["id"] for p in led.interview_view()], [pin["id"]])
        self.assertEqual(led.summary()["open_questions"], 1)

    def test_two_proposals_do_not_share_one_id(self):
        """Found by running the new tool over real stdio, not by reading it: the auto-id was
        `f"prop_{len(proposals)}"` — the LIST's length, constant across the loop — so two proposals
        both came back `prop_2`. Unreachable code cannot be wrong in a way anybody notices."""
        led = make_ledger()
        pin = add_simple_pin(led)
        led.add_proposals(pin["id"], [{"summary": "keep it"}, {"summary": "widen it"}])
        self.assertEqual([p["id"] for p in pin["brainstorm"]["proposals"]], ["prop_1", "prop_2"])
        with self.assertRaises(LedgerError):
            led.add_proposals(pin["id"], [{"id": "a", "summary": "x"}, {"id": "a", "summary": "y"}])

    def test_the_proposals_ride_along_on_the_funnel_entry(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))
        import interview
        led = make_ledger()
        pin = add_simple_pin(led)
        led.add_proposals(pin["id"], [{"summary": "widen it", "effort": "M", "recommended": True}])
        entry = interview.funnel(led)["asked"][0]
        self.assertEqual(entry["pin_id"], pin["id"])
        self.assertEqual(entry["proposals"], [{"id": "prop_1", "summary": "widen it",
                                               "effort": "M", "recommended": True}])


class TestOneWriterForTheSettledStates(unittest.TestCase):
    """The structural half, and the reason this round is not a fifth one: the rule cannot live in
    the doors, because a door added later will not know it.

    Asserted over the AST of everything that ships and can write: no function may assign a settled
    state to a pin except `_settle`, which is where the gate and the record are.
    `TestEveryPathToDecideIsGated` does the same for the first predicate; this is the same move for
    the second — and since 2026-08-06 it is the same SHAPE, which is what §15 of `docs/open-gaps.md` was
    about.

    **Why the shape changed.** The old walk collected `pin["state"] = <literal>` and asked whether
    the literal was a settled state. Everything else was invisible: `pin["state"] = target`,
    `pin["state"] = _STATE_BY_DOOR[door]` — which is the line `_settle` itself is made of, so the
    one write the class is named for was the one write it could not see. Verified by planting that
    exact line into `cross_derive`: the gate passed, green, twice. A gate that quantifies over
    *every function* in its docstring and over *literal assignments only* in its body is this
    repo's most-repeated finding turned on its own tooling.

    So the question is inverted, the way `TestEveryPathToDecideIsGated` inverted it: not "is this
    value a settled state" — which needs the value to be readable — but **"which functions assign
    `pin["state"]` at all"**, which is decidable from the target alone. That set is small and
    stable, every member is declared here with the transition it makes, and a computed value
    outside `_settle` is refused OUTRIGHT rather than inspected, because a gate that cannot read a
    value must not pass it.
    """

    ROOTS = ("runtime", "mcp")

    #: Every function that assigns a pin's `state`, module-qualified, with the transition it makes
    #: and why that transition needs no settlement gate. Set equality against the source, so a
    #: sixth writer fails on the day it is added rather than on the day someone reads for it.
    STATE_WRITERS = {
        ("ledger.py", "_settle"): "THE writer. Assigns `_STATE_BY_DOOR[door]` after "
                                  "`settlement_verdict` has answered and after the event is "
                                  "appended — the gate and the record are both here, which is what "
                                  "makes every other writer's job to not be this one.",
        ("ledger.py", "set_question"): "`detected` -> `needs_input` only. Posing a fork decides "
                                       "nothing; it puts the pin ON the agenda, which is the "
                                       "opposite direction to a settlement.",
        ("ledger.py", "add_proposals"): "`needs_input` -> `brainstorming`. Still open, still in "
                                        "`interview_view` since v0.17 — a pin being thought about "
                                        "has not been answered.",
        ("ledger.py", "cross_derive"): "-> `needs_input` on provider disagreement. The upstream "
                                       "half of the reopen pair; it may not un-close finished work "
                                       "(v0.16) and is checked at `reopen_verdict`.",
        ("ledger.py", "_reopen_minimal"): "-> `needs_input` on every dependent of a falsified "
                                          "truth. The single writer of the reopened state, "
                                          "`_settle`'s twin, held by "
                                          "`TestComingBackIntoTheOpenSetIsGovernedToo`.",
    }

    @classmethod
    def _modules(cls):
        import ast
        base = os.path.join(os.path.dirname(__file__), "..", "src")
        out = {}
        for root in cls.ROOTS:
            for name in sorted(os.listdir(os.path.join(base, root))):
                if name.endswith(".py"):
                    full = os.path.join(base, root, name)
                    with open(full, encoding="utf-8") as fh:
                        out[name] = ast.parse(fh.read(), filename=full)
        return out, ast

    @classmethod
    def _state_writes(cls):
        """(module, function) -> [assigned value node], for every `<x>["state"] = …` that ships.

        Anchored on the assignment TARGET, which is a constant subscript in every shape the value
        can take — that is the whole point of the inversion.
        """
        modules, ast = cls._modules()
        out = {}
        for module, tree in modules.items():
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    if not isinstance(node, ast.Assign):
                        continue
                    for target in node.targets:
                        if (isinstance(target, ast.Subscript)
                                and isinstance(target.slice, ast.Constant)
                                and target.slice.value == "state"):
                            out.setdefault((module, fn.name), []).append(node.value)
        return out, ast

    def test_the_enumeration_of_state_writers_is_complete(self):
        """The load-bearing half: these are ALL the functions that move a pin's state."""
        writes, _ = self._state_writes()
        self.assertEqual(set(writes), set(self.STATE_WRITERS),
                         "a function that assigns a pin's state was added or removed. Declare it "
                         "here with the transition it makes — that is what stops the next one from "
                         "being a settlement nobody looked at")

    def test_only_settle_writes_a_settled_state(self):
        """And the value half, which now refuses what it cannot read instead of skipping it."""
        import ledger as ledger_mod
        writes, ast = self._state_writes()
        governed = set(ledger_mod.SETTLED_STATES) | {"correctness_unknown"}
        for (module, fn), values in sorted(writes.items()):
            if (module, fn) == ("ledger.py", "_settle"):
                continue
            for value in values:
                with self.subTest(writer=f"{module}::{fn}"):
                    self.assertIsInstance(
                        value, ast.Constant,
                        f"{fn} assigns a pin's state from a computed value. Only `_settle` may do "
                        f"that: everywhere else the state must be a literal this gate can read, "
                        f"because a value it cannot read is a value it cannot clear")
                    self.assertNotIn(
                        value.value, governed,
                        "a settled state written outside `_settle` is a settlement with no gate "
                        "and no record — which is exactly how `defer` shipped")

    def test_every_door_reaches_the_single_writer(self):
        import ledger as ledger_mod
        modules, ast = self._modules()
        tree = modules["ledger.py"]
        fns = {n.name: n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        callers = {name for name, fn in fns.items()
                   if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                          and c.func.attr == "_settle" for c in ast.walk(fn))}
        self.assertEqual(callers, {"decide", "resolve", "mark_correctness_unknown"},
                         "these are all the ways a pin becomes settled: `accept` and `defer` reach "
                         "it through `decide`, which is what makes them elections")
        self.assertEqual(sorted(ledger_mod.SETTLEMENT_DOORS),
                         sorted(ledger_mod._STATE_BY_DOOR),
                         "a door with no target state, or a state no door produces")



class TestTheDistinctionsASurfaceSortsAndTITLESBy(unittest.TestCase):
    """v0.19 — two sets a projection was answering with literals.

    `instructions.py` sorted on `state == "deferred"` and headed the section *build on these
    (`defer` = elected NOT to build)*, while `settlement_verdict` defines `accept` as leaving the
    concern exactly as it is — the same instruction, one state over, unnamed. And `_pin_line`
    printed a reopened pin's disputed outcome with no marker at all, because nothing in that file
    read `substate`: `grep -c substate` returned 0.

    Both sets belong to the schema for the reason every set in that block does — a state added here
    must arrive at the surfaces that sort and title by it — so both are asserted against the
    carriers rather than against a second copy of the list."""

    @staticmethod
    def _tree():
        import ast
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read(), filename=path), ast

    def test_the_leave_as_is_states_are_settled_states_and_not_all_of_them(self):
        import ledger as mod
        self.assertLess(set(mod.LEAVE_AS_IS_STATES), set(mod.SETTLED_STATES),
                        "a leave-as-is state that is not settled, or a set covering every settled "
                        "state — either way the split it exists to make has stopped being a split")

    def test_the_two_doors_whose_outcome_is_leave_it_alone_produce_exactly_these(self):
        """Anchored on `_STATE_BY_DOOR`, which is what the doors actually write, so the membership
        question is answered by the table and not by remembering which two doors those were."""
        import ledger as mod
        self.assertEqual(set(mod.LEAVE_AS_IS_STATES),
                         {mod._STATE_BY_DOOR["accept"], mod._STATE_BY_DOOR["defer"]})
        self.assertEqual(set(mod.SETTLED_STATES) - set(mod.LEAVE_AS_IS_STATES),
                         {mod._STATE_BY_DOOR["decide"], mod._STATE_BY_DOOR["resolve"]},
                         "the complement must be exactly the two doors that DO produce work")

    def test_every_substate_a_writer_writes_is_one_a_reader_knows(self):
        """AST over every assignment to `pin["substate"]`, in both shapes it comes in.

        Two writers, two shapes, and the test has to hold both or it holds nothing: `cross_derive`
        assigns the literal `"contested"`, `_reopen_minimal` assigns a lookup in `_SUBSTATE_BY_ARC`.
        So every literal must be a member of the set, every non-literal must come out of the one
        table the set is COMPOSED from, and the literals must not be an empty set — a fourth arc
        introducing a fourth mark, or reading a second table, fails here rather than printing a
        disputed outcome as an elected one on a surface that never heard of it."""
        import ledger as mod
        tree, ast = self._tree()
        literals, tables = set(), set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not (isinstance(target, ast.Subscript)
                        and isinstance(target.slice, ast.Constant)
                        and target.slice.value == "substate"):
                    continue
                if isinstance(node.value, ast.Constant):
                    literals.add(node.value.value)
                elif isinstance(node.value, ast.Name):
                    tables.add(node.value.id)      # the local the table lookup was bound to
                elif (isinstance(node.value, ast.Subscript)
                      and isinstance(node.value.value, ast.Name)):
                    tables.add(node.value.value.id)
                else:
                    self.fail(f"a substate written by an expression this guard cannot follow: "
                              f"{ast.dump(node.value)[:80]}")
        self.assertTrue(literals, "no substate literal anywhere — this guard just went vacuous")
        self.assertLessEqual(literals, set(mod.REOPENED_SUBSTATES),
                             "a mark written by a writer and known to no reader")
        self.assertEqual(tables, {"substate"},
                         "the table-driven writer stopped being the one this set is composed from")
        arc_local = next(fn for fn in ast.walk(tree)
                         if isinstance(fn, ast.FunctionDef) and fn.name == "_reopen_minimal")
        source = ast.dump(arc_local)
        self.assertIn("_SUBSTATE_BY_ARC", source,
                      "`_reopen_minimal` no longer reads the arc table `REOPENED_SUBSTATES` is "
                      "built from, so the two have begun to drift")
        self.assertEqual(set(mod.REOPENED_SUBSTATES),
                         literals | set(mod._SUBSTATE_BY_ARC.values()))

    def test_a_re_election_clears_the_mark(self):
        """The mark means *disputed and not re-answered*, not *was disputed once* — otherwise a pin
        the human answered again would keep telling every reader not to build on it."""
        led = make_ledger()
        pin = led.add_pin(kind="ambiguity", title="outbox order", severity="high",
                          confidence="ambiguous", provenance=[{"source": "r", "detail": "d"}],
                          as_is={"claim": "after"},
                          question={"prompt": "when?",
                                    "options": [{"id": "after", "label": "after commit"},
                                                {"id": "inside", "label": "inside"}],
                                    "allow_freeform": True})
        led.decide(pin["id"], outcome="after", rationale="documented", flip_criteria="a duplicate",
                   evidence="transcribed", human_answer="after commit")
        led.cross_derive(pin["id"], claim="the flush runs after commit",
                         derivations=[{"provider": "anthropic", "model": "opus", "result": "no"},
                                      {"provider": "openai", "model": "gpt-5", "result": "yes"}],
                         agreement="disagree")
        self.assertEqual(pin["substate"], "contested")
        led.decide(pin["id"], outcome="inside", rationale="the code is the contract",
                   flip_criteria="the comment is corrected", evidence="transcribed",
                   human_answer="inside — the code wins")
        self.assertIsNone(pin.get("substate"))


class TestARuleIsTrueOfTheThingItIsPrintedOn(unittest.TestCase):
    """v0.18 — four rules whose writer and whose reader disagreed about what they meant.

    None of these is a missing surface: every one had a tool, ran, and printed a sentence that was
    not true of what it did. They are grouped because that is the shape, and the shape is what the
    next round has to look for.
    """

    # -- 1. a scope key with a null value selects by ABSENCE, and the preview says so -------------

    def test_a_null_scope_value_is_reported_as_the_absence_selector_it_is(self):
        """v0.16 refused a scope key naming no pin field. Most pin fields are OPTIONAL, so a scope
        naming a REAL one with a null value still selects every pin carrying no value for it — the
        same universal-looking radius, past the same check. The radius is what makes an election
        legitimate, so the matcher says what it did."""
        led = make_ledger()
        clustered = add_simple_pin(led, severity="low", cluster_id="cl_one")
        loose_a = add_simple_pin(led, severity="low")
        loose_b = add_simple_pin(led, severity="low")

        radius = led.policy_preview({"cluster_id": None}, "opt_a")
        self.assertEqual(radius["would_decide"], [loose_a["id"], loose_b["id"]],
                         "the matcher is unchanged — a null still selects by absence")
        self.assertNotIn(clustered["id"], radius["would_decide"])
        self.assertIn("selects by ABSENCE", radius["scope_note"])
        self.assertIn("`cluster_id`", radius["scope_note"])
        self.assertIn("2 of 3", radius["scope_note"],
                      "the count is the whole point: a reader has to be able to see that a scope "
                      "reading as narrow covers most of the ledger")

    def test_a_scope_on_a_value_the_pins_carry_says_nothing(self):
        """The note is not a wall and not a warning banner: it appears only where the ambiguity is
        real, so the common message is the one it was before."""
        led = make_ledger()
        add_simple_pin(led, severity="low", cluster_id="cl_one")
        self.assertEqual(led.policy_preview({"cluster_id": "cl_one"}, "opt_a")["scope_note"], "")
        self.assertEqual(led.policy_preview({"severity": "low"}, "opt_a")["scope_note"], "")
        self.assertEqual(led.policy_preview({}, "opt_a")["scope_note"], "")

    def test_the_note_counts_what_the_matcher_matches_and_not_what_a_key_check_would(self):
        """`to_be`, `question` and `decision` are written as explicit nulls, so "does not have the
        key" and "carries no value" disagree on exactly the fields where a second implementation
        would drift. The note is counted with the matcher's own comparison."""
        led = make_ledger()
        add_simple_pin(led, severity="low")            # to_be is an explicit null
        add_simple_pin(led, severity="low")
        radius = led.policy_preview({"to_be": None}, "opt_a")
        self.assertEqual(len(radius["would_decide"]), 2)
        self.assertIn("2 of 2", radius["scope_note"])

    def test_the_cascade_reports_the_same_note_because_it_is_the_same_call(self):
        led = make_ledger()
        add_simple_pin(led, severity="low")
        pol = led.add_policy(applies_to={"cluster_id": None}, rule="the loose ones",
                             default_outcome="opt_a", human_answer="yes")
        self.assertEqual(led.apply_policy(pol)["scope_note"],
                         led.policy_preview({"cluster_id": None}, "opt_a")["scope_note"])

    # -- 2. the mark that cannot be cleared is written only for a standing reason -----------------

    def test_one_ill_fitting_policy_no_longer_puts_a_pin_beyond_every_later_one(self):
        """The reproduction from the register, end to end. `not_offered` says *this rule's outcome
        is not on this pin's menu* — a fact about the rule — and it was recorded on the pin as
        `resolution_mode: "asked"`, which nothing clears and which `unasked_verdict` reads as the
        pin's own standing demand. So the SECOND policy, whose outcome the fork does offer and whose
        severity is under the threshold, was refused for ever by an unrelated first one."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        misfit = led.add_policy(applies_to={"severity": "medium"}, rule="unrelated",
                                default_outcome="zzz", human_answer="whatever")
        self.assertEqual(led.apply_policy(misfit)["not_offered"], [pin["id"]])
        self.assertNotIn("resolution_mode", pin,
                         "a fact about the rule is reported in the radius, not stamped on the pin")

        fitting = led.add_policy(applies_to={"severity": "medium"}, rule="DB wins",
                                 default_outcome="opt_a", human_answer="the DB wins")
        self.assertEqual(led.apply_policy(fitting)["would_decide"], [pin["id"]])
        self.assertEqual((pin["state"], pin["resolution_mode"]), ("decided", "policy_default"))

    def test_the_standing_reasons_still_mark_and_still_bind(self):
        """The mark is not weakened where it means something. Severity is a standing property, and
        so is a pin that already carries the demand — both keep it, and `unasked_verdict` keeps
        refusing them."""
        led = make_ledger()
        blocker = add_simple_pin(led, severity="blocker")
        reopened = add_simple_pin(led, severity="medium")
        led.decide(reopened["id"], "opt_a", "r", "f")
        led.challenge(reopened["id"], target="decision", challenge_class="unstated_assumption",
                      argument="the enum widened upstream", severity="medium", upheld=True)

        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="DB wins",
                             default_outcome="opt_a", human_answer="db wins")
        radius = led.apply_policy(pol)
        self.assertEqual(radius["held_back"], [blocker["id"]])
        self.assertEqual(radius["must_be_asked"], [reopened["id"]])
        self.assertEqual(blocker["resolution_mode"], "asked")
        self.assertEqual(reopened["resolution_mode"], "asked")

    def test_the_brief_door_had_the_identical_defect_and_reads_the_same_tuple(self):
        """`interview.expand_catalog`'s `verdict != "would_decide"` swept `not_offered` in with the
        threshold, so one word in a project brief that no fork offered marked that fork permanently
        un-cascadable. Same rule, second door — which is the thing v0.14 exists to stop — so both
        read `STANDING_REFUSALS` rather than spelling it out twice.

        The two verdicts are produced deliberately, in one call: `client` is a `medium` fork given a
        word it does not offer (`not_offered`), `domain` is a `blocker` given one of its own option
        ids (`held_back`). Nothing here depends on guessing which branch the catalog happens to take.
        """
        import interview
        from ledger import STANDING_REFUSALS
        self.assertNotIn("not_offered", STANDING_REFUSALS)
        led = make_ledger()
        out = interview.expand_catalog(
            led, interview.load_catalog(_CATALOG), project_type="web-saas",
            brief_decisions={"client": "carrier-pigeon", "domain": "elicit_entities"})
        held = {h["cluster_id"]: h for h in out["brief_held_back"]}
        self.assertEqual(held["client"]["reason"], "not_offered")
        self.assertEqual(held["domain"]["reason"], "held_back")

        misfit, threshold = led.pin(held["client"]["pin_id"]), led.pin(held["domain"]["pin_id"])
        self.assertNotIn("resolution_mode", misfit,
                         "the brief's word was not on this fork's menu — a fact about the brief, "
                         "and the mark it used to leave had no clearing door")
        self.assertEqual(threshold["resolution_mode"], "asked")
        for pin in (misfit, threshold):
            self.assertIn(pin["id"], out["created"], "held back is never dropped")

    # -- 3. an offered option states what actually happens on the pin it is printed on ------------

    def _unverifiable_defect(self, led):
        pin = led.add_pin(kind="defect", title="flaky retry", severity="medium",
                          confidence="extracted",
                          provenance=[{"source": "test", "detail": "d"}],
                          as_is={"description": "retries twice"})
        led.add_remediation(pin["id"], action="refactor", ladder_rung=3)
        led.set_remediation_status(pin["id"], pin["remediation"][0]["id"], "done")
        led.mark_correctness_unknown(pin["id"], blocked_by="no staging queue",
                                     attempted=["tests", "typecheck"])
        return pin

    def test_the_accept_option_on_a_defect_no_longer_promises_a_state_the_door_refuses(self):
        """Measured both ways in one run, as the register did. On a `defect` — the kind that reaches
        this state without a decision, so the kind that most often carries the generated fork —
        `settlement_verdict(pin, "accept")` is `wrong_kind`, and the option promised `accepted`
        anyway."""
        led = make_ledger()
        pin = self._unverifiable_defect(led)
        option = next(o for o in pin["question"]["options"] if o["id"] == "accept")
        self.assertEqual(led.settlement_verdict(pin, "accept"), "wrong_kind")
        self.assertNotIn("becomes `accepted`", option["implication"])
        self.assertIn("`decided`", option["implication"])
        self.assertIn("defect", option["implication"])

    def test_the_implication_is_what_recording_that_outcome_actually_does(self):
        """The proof the register asked for: record the offered outcome and read the state."""
        led = make_ledger()
        pin = self._unverifiable_defect(led)
        led.decide(pin["id"], outcome="accept", rationale="risk named",
                   flip_criteria="a staging queue exists", human_answer="live with it")
        self.assertEqual(pin["state"], "decided")

    def test_the_option_says_accepted_where_accepted_is_reachable(self):
        """The other half: a `design_concern` with no prior fork. The door does open there, and the
        sentence is computed from the same predicate, so it says so."""
        led = make_ledger()
        pin = led.add_pin(kind="design_concern", title="one service does two jobs",
                          severity="medium", confidence="inferred",
                          provenance=[{"source": "review", "detail": "d"}],
                          as_is={"concern": "coupling"})
        led.decide(pin["id"], outcome="keep", rationale="fine for v1",
                   flip_criteria="a module needs independent scaling", human_answer="leave it")
        led.mark_correctness_unknown(pin["id"], blocked_by="no load profile",
                                     attempted=["diff_review"])
        option = next(o for o in pin["question"]["options"] if o["id"] == "accept")
        self.assertEqual(led.settlement_verdict(pin, "accept"), "would_settle")
        self.assertIn("`accepted`", option["implication"])

    def test_computing_the_sentence_did_not_make_this_a_writer_of_forks(self):
        """v0.16's rule is untouched: a pin that already poses a fork keeps it, whatever the
        implication would have said."""
        led = make_ledger()
        pin = self._unverifiable_defect(led)
        offered = [o["id"] for o in pin["question"]["options"]]
        led.decide(pin["id"], outcome="retry", rationale="try again", flip_criteria="f",
                   human_answer="retry it")
        led.mark_correctness_unknown(pin["id"], blocked_by="still no queue", attempted=["tests"])
        self.assertEqual([o["id"] for o in pin["question"]["options"]], offered)

    # -- 4. `defer` states no rung, because only the code that ran a path may name it -------------

    def test_defer_takes_no_caller_stated_rung_at_the_library_either(self):
        """The MCP door dropped the parameter in v0.16 and the library kept it, so the rule was held
        by the door rather than by the thing the door protects. A default is not a refusal: the next
        caller passes `elicited` and the library writes it."""
        import inspect
        self.assertNotIn("evidence", inspect.signature(Ledger.defer).parameters)
        self.assertIn("evidence", inspect.signature(Ledger.decide).parameters,
                      "`decide` keeps it legitimately — two paths reach it and the rung is a fact "
                      "about which one ran")
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.defer(pin["id"], rationale="v2", flip_criteria="a customer asks",
                  human_answer="not now")
        self.assertEqual(led.data["decision_log"][-1]["evidence"], "transcribed")

    # -- 5. reading a ledger is never the operation that fails on it ------------------------------

    def _hand_corrupted(self, entry: dict) -> Ledger:
        led = make_ledger()
        add_simple_pin(led, severity="medium")
        led.save()
        with open(led.path, encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["decision_log"].append(entry)
        with open(led.path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
        return Ledger(led.path)

    def test_a_log_entry_with_no_id_does_not_kill_the_call_an_agent_makes_first(self):
        """`summary` dispatched on `e["id"]`. No version of this package wrote an entry without one,
        so it is hand-editing — but `summary` is what an agent calls BEFORE acting, on a file it did
        not write, and the principle carries no such qualification."""
        reloaded = self._hand_corrupted({"pin_id": "pin_0001", "outcome": "opt_a"})
        summary = reloaded.summary()                      # must not raise
        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["pre_rule_events"], {"log_entry_kind": 1},
                         "skipped in the counts, reported by name — the same rule the settles_as "
                         "skip one branch down already follows")
        self.assertEqual(reloaded.pre_rule["log_entry_kind"], ["decision_log[0]"],
                         "named by position, because the thing wrong with it is that it has no name")

    def test_a_recognised_entry_missing_its_own_field_is_counted_as_unrecorded(self):
        self.assertEqual(self._hand_corrupted({"id": "fal_0001", "pin_id": "pin_0001"})
                         .summary()["failures_by_class"], {"unrecorded": 1})
        self.assertEqual(self._hand_corrupted({"id": "stl_0001", "pin_id": "pin_0001"})
                         .summary()["settlements_by_door"], {"unrecorded": 1})

    def test_every_prefix_a_writer_writes_is_a_prefix_a_reader_knows(self):
        """`LOG_ENTRY_PREFIXES` is a declaration, so it is held to the writers rather than trusted:
        a new event kind whose prefix is not here would be reported as corruption by the very check
        that exists to report corruption, and its events would vanish from every count."""
        import ast
        import ledger as ledger_mod
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        written = set()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_next_id" and len(node.args) > 1):
                continue
            target = node.args[1]
            if not (isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "decision_log"):
                continue
            prefix = node.args[0]
            self.assertIsInstance(prefix, ast.Constant, "a computed log id prefix has no reader")
            written.add(prefix.value)
        self.assertEqual(written, set(ledger_mod.LOG_ENTRY_PREFIXES))

class TestEveryForkThisRuntimeComposes(unittest.TestCase):
    """`_validate_question` holds the rule for everything that passes a door. This is what does not.

    `surface_assumption` and `interview._fork_question` compose a fork and hand it to `add_pin`, so
    the validator sees theirs. `cross_derive` assigns one straight onto the pin — installing a fork
    the human answers from without passing any door — and it happens to set `allow_freeform`.
    "Happens to" is the state this repo keeps finding, so the bypass is asserted from the AST.

    The predicate is a carrier and not a resemblance: **a dict literal assigned to a `["question"]`
    subscript.** The first draft asked "does the literal have a `prompt` key", which flagged
    `interview.funnel`'s entry and `tools._prompt_from_pin`'s return — two PROJECTIONS of a fork
    that already exists, neither of which writes one. A rule that cannot tell a reader from a writer
    is the exact defect `scripts/check_schema_fields.py` was inverted for.
    """

    ROOTS = ("runtime", "mcp")

    #: The functions allowed to install a fork without passing `_validate_question`, with the reason.
    #: Declared, so a fourth bypass fails here rather than inheriting this exemption.
    #:
    #: Both write-if-absent, which is the rule `set_question` is built on and the reason neither is
    #: a hole: the menu each composes replaces nobody's. `mark_correctness_unknown` was found by
    #: this test rather than remembered — it was not in the first draft of this dict, which is
    #: exactly what an inverted gate is for.
    BYPASSES = {
        "cross_derive": "install-if-absent: two providers disagreeing pose 'which derivation "
                        "holds', and the derivations reach the map either way",
        "mark_correctness_unknown": "install-if-absent: the state forces an explicit next move, so "
                                    "it carries a fork asking for one; `blocked_by` is on the pin "
                                    "either way",
    }

    def _question_literals(self):
        import ast
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        for sub in self.ROOTS:
            for path in sorted((root / sub).glob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                enclosing = {}
                for fn in ast.walk(tree):
                    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for child in ast.walk(fn):
                            enclosing.setdefault(id(child), fn.name)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                        continue
                    for target in node.targets:
                        if (isinstance(target, ast.Subscript)
                                and isinstance(target.slice, ast.Constant)
                                and target.slice.value == "question"):
                            yield (path.name, node.lineno, enclosing.get(id(node), "<module>"),
                                   node.value)

    def test_no_fork_installed_past_the_validator_bounds_the_human(self):
        import ast
        closed = []
        for name, lineno, _fn, literal in self._question_literals():
            keys = [k.value for k in literal.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            value = dict(zip(keys, literal.values)).get("allow_freeform")
            if not (isinstance(value, ast.Constant) and value.value is True):
                closed.append(f"{name}:{lineno}")
        self.assertEqual(closed, [],
                         "a fork installed here bounds what the human may answer, and it reaches "
                         "`_validate_question` on no path")

    def test_the_composers_that_reach_no_door_are_the_declared_ones(self):
        found = {fn for _n, _l, fn, _lit in self._question_literals()}
        self.assertEqual(found, set(self.BYPASSES),
                         "a function installing a fork without passing a door is a menu nothing "
                         "validated — declare it here with the reason, or route it through "
                         "`set_question`")


class TestReadingAPinIsNeverTheOperationThatFails(unittest.TestCase):
    """v0.18 made every read in `summary`'s LOG loop a `.get`, under a principle stated with no
    qualifier. It was applied to one of the two collections: `summary` and `interview_view` went on
    indexing `pin["state"]`, `pin["severity"]` and `pin["id"]`, and six pin shapes made both die
    with a bare `KeyError` — on files `map.render` and `instructions.render` read start to finish
    without complaint.

    Every shape below was reproduced against the shipped tree before it was a test. They are fixed
    as ONE guarded path — `Ledger.readable` for the container, `pin_read` for the fields — and not
    as six guards, because six sites that agree today are what the rounds before this one have
    spent themselves untangling.
    """

    #: Each shape, as a mutation of a written ledger's first pin. The last three are the container
    #: and the entry, which are the same failure one level up.
    SHAPES = {
        "severity outside the set": lambda d: d["pins"][0].update(severity="critical"),
        "severity missing": lambda d: d["pins"][0].pop("severity"),
        "severity null": lambda d: d["pins"][0].update(severity=None),
        "state missing": lambda d: d["pins"][0].pop("state"),
        "id missing": lambda d: d["pins"][0].pop("id"),
        "depends_on is a bare string": lambda d: d["pins"][0].update(depends_on="pin_0002"),
        "question is not an object": lambda d: d["pins"][0].update(question="which?"),
        "a pin is not an object": lambda d: d["pins"].__setitem__(0, "pin_0001"),
        "pins is absent": lambda d: d.pop("pins"),
        "decision_log is absent": lambda d: d.pop("decision_log"),
        "policies is absent": lambda d: d.pop("policies"),
    }

    def _broken(self, mutate) -> tuple:
        led = make_ledger()
        add_simple_pin(led, severity="medium")
        add_simple_pin(led, severity="low", title="second")
        led.save()
        with open(led.path, encoding="utf-8") as fh:
            raw = json.load(fh)
        mutate(raw)
        with open(led.path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
        return Ledger(led.path), raw

    def test_no_reading_surface_dies_on_any_of_them(self):
        """All four surfaces the reviewer swept, on every shape — because the finding was that two
        of the four answered and two did not, on the same file."""
        import instructions
        import map as mapmod
        from interview import funnel
        for name, mutate in self.SHAPES.items():
            with self.subTest(shape=name):
                led, raw = self._broken(mutate)
                led.summary()
                led.interview_view()
                funnel(led)
                mapmod.render(raw, title="t")
                instructions.render(raw)

    def test_what_the_read_substitutes_is_reported_by_name(self):
        """Nothing is skipped in silence: the same answer the log half gives one collection over.
        `pre_rule_events` is returned by `summary()` itself, so the agent that reads the counts
        reads why they are short in the same call."""
        expected = {
            "severity outside the set": "pin_severity",
            "state missing": "pin_state",
            "id missing": "pin_id",
            "depends_on is a bare string": "pin_depends_on",
            "question is not an object": "pin_question",
            "a pin is not an object": "entry_shape",
            "pins is absent": "collection_shape",
            "decision_log is absent": "collection_shape",
        }
        for name, rule in expected.items():
            with self.subTest(shape=name):
                led, _raw = self._broken(self.SHAPES[name])
                self.assertIn(rule, led.summary()["pre_rule_events"],
                              f"{name!r} is substituted by the read path and reported by nobody")

    def test_a_file_with_an_unreadable_pin_does_not_get_its_version_raised(self):
        """The stamp is a claim of conformance — the rule `nonconforming` has always enforced for
        the log, now true of the pins for the same reason."""
        def older_and_broken(raw):
            raw["version"] = "0.19"
            self.SHAPES["state missing"](raw)

        led, _raw = self._broken(older_and_broken)
        self.assertIn("pin_state", led.pre_rule)
        self.assertEqual(led.summary()["version"], "0.19",
                         "the floor rose on a file this runtime cannot read start to finish")
        conforming, _ = self._broken(lambda raw: raw.__setitem__("version", "0.19"))
        self.assertEqual(conforming.summary()["version"], SCHEMA_VERSION,
                         "the control: the same file with readable pins does rise")

    def test_an_unrankable_severity_sorts_last_and_the_pin_stays_in_the_view(self):
        """The substitution has a direction and it is declared: not `low` (reading a claim the file
        does not make) and not `blocker` (inventing urgency out of a broken field). The pin is
        still in the interview, because dropping it would hide a question."""
        led, _raw = self._broken(self.SHAPES["severity outside the set"])
        view = [p.get("id") for p in led.interview_view()]
        self.assertIn("pin_0001", view, "the unreadable pin was dropped from the interview")
        self.assertEqual(view[-1], "pin_0001", "an unrankable severity must sort last")

    def test_every_field_the_read_path_substitutes_has_a_rule_that_reports_it(self):
        """The inverted half, and the one that keeps this honest: a field added to `pin_read` with
        no `PIN_RULES` entry is a silent substitution, which is the failure this class fixed."""
        from ledger import PIN_RULES, pin_read
        self.assertEqual({name.removeprefix("pin_") for name, _h, _m in PIN_RULES},
                         set(pin_read({})),
                         "a guarded read and a reported rule are two halves of one mechanism")

    def test_no_pin_this_runtime_writes_can_break_one_of_these_rules(self):
        """`PIN_RULES` has one caller where `EVENT_RULES` has two, and this is the claim that
        difference rests on: the write path already settles every one of them, so a writer half
        would be a second refusal for one fact. Asserted over every kind and every severity rather
        than argued — if `add_pin` ever composes a pin this table refuses, the membership argument
        above is wrong and the table needs `_check_event`'s twin."""
        from ledger import KINDS, SEVERITIES, pin_violations
        led = make_ledger()
        for kind in sorted(KINDS):
            for severity in SEVERITIES:
                for fork in ({"prompt": "which?",
                              "options": [{"id": "a", "label": "A"}],
                              "allow_freeform": True}, None):
                    pin = add_simple_pin(
                        led, kind=kind, severity=severity, question=fork,
                        kind_detail="an escape hatch" if kind == "other" else None)
                    self.assertEqual(pin_violations(pin), [],
                                     f"add_pin composed a {kind}/{severity} pin (fork="
                                     f"{fork is not None}) that the read path cannot index")
        # ...and one carrying the DAG, since `depends_on` is the fifth rule
        dependent = add_simple_pin(led, depends_on=[led.data["pins"][0]["id"]])
        self.assertEqual(pin_violations(dependent), [])

    def test_the_interviews_states_are_the_ones_its_own_view_selects(self):
        """`INTERVIEW_STATES` exists because the map re-derived this set and got it wrong. A
        constant nothing is held to would let the two drift apart again, so the tuple is read out of
        `interview_view`'s own AST rather than trusted."""
        import ast
        import ledger as ledger_mod
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "interview_view")
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        self.assertIn("INTERVIEW_STATES", names,
                      "interview_view selects its states from a literal again — the map reads the "
                      "constant, so the two would answer differently")
        self.assertEqual(set(ledger_mod.INTERVIEW_STATES),
                         set(ledger_mod.OPEN_STATES) - {"detected"},
                         "the interview reads every open state but the one that poses no fork")


if __name__ == "__main__":
    unittest.main()
