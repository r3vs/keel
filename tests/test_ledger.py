"""Tests for runtime/ledger.py — each test pins one load-bearing rule of
core/decisions-ledger-spec.md (v0.18). Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # `shape_corpus`, the derived corpus

from ledger import SCHEMA_VERSION, Ledger, LedgerError, refuted_claim  # noqa: E402


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


def walk_every_pin_writer() -> tuple:
    """Drive every door that writes onto ONE pin; return `(keys written, a snapshot per door)`.

    Snapshots and not a final state, for the reason the key accumulation below already gives one
    level up: three doors REPLACE `pin["verification"]` wholesale, so `cross_derived_by` is written
    by `cross_derive` and correctly gone by the time `resolve` returns. A gate reading the last pin
    would call that path unwritten, which is a claim about the snapshot rather than about the
    writers.

    Extracted in v0.25 because two declarations are now held to the writers rather than trusted —
    `PIN_FIELDS` (which fields a policy scope may name) and `PIN_SHAPES` (what shape each one is) —
    and a second copy of this walk would be the second answer to "what does this runtime write",
    which is the thing both declarations exist to prevent.

    A defect, so the walk can end at `resolved`: the door's kind escape is what admits a pin that is
    no longer in `decided`, and the order is the settlement rules' rather than a convenience.
    `correctness_unknown` takes a pin out of `decided` and NOT out of `resolved` (the way back from
    finished work is `reopen`), and the disagreement that writes `substate` may only touch a pin
    that is not closed — so: decided -> unknown -> contested -> resolved on a later observation.

    The keys are ACCUMULATED across the walk rather than read off the final pin (v0.22): `_settle`
    clears `substate` on every door that lands the pin in `SETTLED_STATES`, so the field is written,
    read and then correctly gone by the time `resolve` returns. "A field no writer writes" is a
    question about the writers, and a snapshot of the last state answers a different one.
    """
    import copy
    led = make_ledger()
    pin = add_simple_pin(led, kind="defect", severity="medium", cluster_id="cl_x",
                         depends_on=[], anchors=[{"node_id": "n_1", "loc": "a.py:1"}],
                         to_be={"db": "ENUM('admin','user','auditor')"})
    written: set = set(pin)
    shots: list = [copy.deepcopy(pin)]

    def door(fn, *args, **kw):
        fn(*args, **kw)
        written.update(pin)
        shots.append(copy.deepcopy(pin))

    door(led.add_proposals, pin["id"], [{"summary": "s"}])
    door(led.set_readiness, pin["id"], "ready", zone={"files": ["a.py"]}, evidence={})
    door(led.premortem, pin["id"], [{"class": "environment", "description": "d"}],
         guardrails=["g"], abort_criteria=["a"],
         paper_tigers=[{"risk": "r", "evidence": "already mitigated by X"}])
    door(led.cross_derive, pin["id"], claim="c", agreement="agree", derivations=[
        {"provider": "anthropic", "model": "m", "result": "a"},
        {"provider": "openai", "model": "n", "result": "a"}])
    door(led.decide, pin["id"], "opt_a", "r", "f")
    item = led.add_remediation(pin["id"], action="align", ladder_rung=1)
    door(led.set_remediation_status, pin["id"], item["id"], "done")
    door(led.mark_correctness_unknown, pin["id"], blocked_by="b", attempted=["tests"])
    door(led.cross_derive, pin["id"], claim="c2", agreement="disagree", derivations=[
        {"provider": "anthropic", "model": "m", "result": "a"},
        {"provider": "openai", "model": "n", "result": "b"}])       # writes `substate`
    door(led.resolve, pin["id"], evidence="observed it on staging", rung="observed")
    led.data["pins"][0]["kind_detail"] = "x"      # only `other` writes it, and it is scopeable
    written |= set(led.data["pins"][0])
    shots.append(copy.deepcopy(led.data["pins"][0]))
    return written, shots


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
        led.decide(c["id"], "opt_a", "r", "flip", evidence="brief",
                   brief_quote="one relational datastore until a need proves otherwise")
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
            # v0.24. The second rule in this table with a retroactive edge, and it is deliberate:
            # a `brief` event written before the field existed carries no passage and none can be
            # reconstructed, so the file is held below its floor and says which rule it is held by.
            "brief_quote": {"evidence": "brief"},
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
        written, _shots = walk_every_pin_writer()
        self.assertIn("substate", written, "the disagreement is what writes it")
        self.assertEqual(sorted(written - set(ledger_mod.PIN_FIELDS)), [],
                         "a Pin field no policy scope can name")
        self.assertEqual(sorted(set(ledger_mod.PIN_FIELDS) - written), [],
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


class TestTheWayBackOwesTheDoorsTheirCarriers(unittest.TestCase):
    """v0.22 — the carriers a settlement door DECIDES on, and what the reopen leaves standing.

    v0.20 gave the arcs the settlement half's events; v0.21 gave the pins the log half's guarded
    read. This is the same question one layer further in: `settlement_verdict` decides from what the
    pin says about itself, and `_reopen_minimal` rewrote the state and left every other one of those
    carriers exactly as the closed pin had it. Reproduced over real stdio before it was fixed here.

    The structural test is the one that generalizes: the carriers are read off the predicate's own
    AST and compared to the declared table, so a door gating on a fifth one fails until the arcs are
    told what it is owed. `_validate_question` / `question_offers` are the shape — one function,
    several callers, asserted by AST — and this is that shape applied to a set of FIELDS rather than
    to a call.
    """

    def _closed_defect(self, led, title="double charge on retry"):
        pin = led.add_pin(kind="defect", title=title, severity="high", confidence="extracted",
                          provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="p95 measured at 180ms in staging", rung="observed")
        return pin

    # -- the structural half ---------------------------------------------------------------------

    @staticmethod
    def _pin_keys(node):
        """Every key read OFF the local named `pin` under `node`, in the two shapes a read takes
        here — `pin["x"]` in a Load context and `pin.get("x")`. Items inside `pin["remediation"]`
        are a different object and are deliberately not collected: the question is what the DOOR
        decides from, and the arc's obligation is to the pin."""
        import ast
        keys = set()
        for n in ast.walk(node):
            if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                    and n.value.id == "pin" and isinstance(n.ctx, ast.Load)
                    and isinstance(n.slice, ast.Constant)
                    and isinstance(n.slice.value, str)):
                keys.add(n.slice.value)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "get" and isinstance(n.func.value, ast.Name)
                  and n.func.value.id == "pin" and n.args
                  and isinstance(n.args[0], ast.Constant)):
                keys.add(n.args[0].value)
        return keys

    @classmethod
    def _carriers_the_doors_gate_on(cls):
        """Every carrier a settlement DOOR decides from — the predicate's whole body, plus every
        `_require` CONDITION in the five doors themselves.

        **The table says DOOR and this used to ask one FUNCTION (v0.26).** It read
        `settlement_verdict` alone, so *"every carrier a settlement door decides on"* was proved of
        the predicate and asserted of the doors — and `resolve` gated on a fifth the table does not
        name (`pin.get("evidence")`, the observation the LAST resolve rested on). A `_require` is
        this runtime's one refusal, so a pin field read inside one is a field the settlement is
        decided by; anything else a door reads it is merely writing to or reporting.
        """
        import ast
        import ledger as mod
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        doors = {"settlement_verdict"} | {
            "mark_correctness_unknown" if d == "correctness_unknown" else d
            for d in mod.SETTLEMENT_DOORS}
        seen, keys = set(), set()
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or fn.name not in doors:
                continue
            seen.add(fn.name)
            if fn.name == "settlement_verdict":
                keys |= cls._pin_keys(fn)
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "_require" and node.args):
                    keys |= cls._pin_keys(node.args[0])
        assert seen == doors, f"a settlement door this gate never found: {sorted(doors - seen)}"
        return keys

    def test_every_carrier_a_settlement_door_reads_has_a_declared_disposition(self):
        """The load-bearing half. A door that starts gating on a new carrier fails here until
        `SETTLEMENT_CARRIERS` says what the way back owes it — which is the only arrangement in
        which "every carrier" is a claim about the code rather than about two functions remembering
        each other."""
        import ledger as ledger_mod
        self.assertEqual(self._carriers_the_doors_gate_on(),
                         set(ledger_mod.SETTLEMENT_CARRIERS),
                         "a carrier a settlement DOOR decides from, with nothing said about "
                         "what a reopen does to it — declare it in `SETTLEMENT_CARRIERS`")
        self.assertEqual(set(ledger_mod.SETTLEMENT_CARRIERS.values())
                         - set(ledger_mod.REOPEN_DISPOSITIONS), set())

    def test_the_arc_pays_every_carrier_the_table_calls_invalidated(self):
        """And the behavioural half of the same table: each `invalidated` carrier must stop reading
        as permission once the arc has run, on the pin itself."""
        import ledger as ledger_mod
        checks = {
            "verification": lambda p: (p.get("verification") or {}).get("rung")
            not in ledger_mod._CLOSING_RUNGS,
        }
        self.assertEqual(
            sorted(checks),
            sorted(k for k, v in ledger_mod.SETTLEMENT_CARRIERS.items() if v == "invalidated"),
            "an `invalidated` carrier with no assertion here is a promise nothing keeps")
        # One branch per arc, dispatched by name and asserted to be exhaustive. It used to be an
        # `if reopen / else challenge`, so the third arc added in v0.24 ran the challenge branch
        # twice and was never exercised by a loop written over the tuple it had just joined — the
        # register's third recurring shape, inside the gate for its second.
        def run(arc, led, pin):
            if arc == "reopen":
                # `cross_derive` acts on a pin that is not FINISHED, so its fixture stops one call
                # short of `resolve` — the closing rung is the one `cross_derive(agree)` wrote.
                led.reopen(pin["id"], reason="p95 blew the threshold", fired="incident")
            elif arc == "challenge":
                led.challenge(pin["id"], target="to_be", challenge_class="unfalsifiable",
                              argument="the oracle it closed on cannot fail", severity="high",
                              upheld=True)
            elif arc == "cross_derive":
                led.cross_derive(pin["id"], claim="the retry path is idempotent",
                                 derivations=[{"provider": "anthropic", "model": "o",
                                               "result": "idempotent"},
                                              {"provider": "openai", "model": "g",
                                               "result": "NOT idempotent"}],
                                 agreement="disagree")
            else:
                self.fail(f"no branch exercises the arc {arc!r}")

        for arc in ledger_mod.REOPEN_ARCS:
            led = make_ledger()
            if arc == "cross_derive":
                pin = led.add_pin(kind="defect", title="double charge", severity="high",
                                  confidence="extracted",
                                  provenance=[{"source": "recon", "detail": "x"}],
                                  as_is={"description": "d"})
                led.cross_derive(pin["id"], claim="the retry path is idempotent",
                                 derivations=[{"provider": "anthropic", "model": "o",
                                               "result": "idempotent"},
                                              {"provider": "openai", "model": "g",
                                               "result": "idempotent"}],
                                 agreement="agree")
                self.assertEqual(pin["verification"]["rung"], "cross_derived")
            else:
                pin = self._closed_defect(led)
            run(arc, led, pin)
            for carrier, holds in checks.items():
                self.assertTrue(holds(pin), f"{arc} left `{carrier}` standing")

    # -- the reproduction, verbatim --------------------------------------------------------------

    def test_a_pin_reopened_by_an_incident_no_longer_claims_it_was_observed(self):
        """The whole finding in one walk: `add_pin -> add_remediation -> done ->
        resolve(rung="observed") -> reopen(fired="incident")` came back open still carrying the
        verification that says its behaviour was OBSERVED — on the evidence the incident had just
        refuted — so it re-closed through the gate that exists to stop exactly that."""
        led = make_ledger()
        pin = self._closed_defect(led)
        self.assertEqual(pin["verification"]["rung"], "observed")
        event = led.reopen(pin["id"], reason="p95 blew the threshold", fired="incident")

        self.assertEqual(pin["state"], "needs_input")
        self.assertIsNone(pin["verification"]["rung"], "the refuted claim is taken back")
        self.assertIn(event["id"], pin["verification"]["blocked_by"])
        self.assertEqual(led.settlement_verdict(pin, "resolve"), "unverified",
                         "the door that means OBSERVED may not reopen on refuted evidence")
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], evidence="no new observation — the same staging run")
        self.assertIn("unverified", str(ctx.exception))

    def test_a_fresh_observation_is_still_the_way_out(self):
        """A gate with no gate-opening move is a wall, and people route around walls: the pin closes
        again the moment somebody states a rung they actually reached."""
        led = make_ledger()
        pin = self._closed_defect(led)
        led.reopen(pin["id"], reason="p95 blew the threshold", fired="incident")
        item = led.add_remediation(pin["id"], action="align", ladder_rung=3)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="re-measured on prod for 24h: p95 190ms", rung="observed")
        self.assertEqual((pin["state"], pin["verification"]["rung"]), ("resolved", "observed"))
        self.assertIn("refuted by", pin["verification"]["blocked_by"],
                      "demoted, never deleted — `it was blocked, then it was observed` is history")

    def test_a_pin_that_claimed_nothing_has_nothing_taken_back(self):
        """Writing an envelope onto a pin that carries none would manufacture a statement the file
        never made — the overwrite v0.16 removed from `cross_derive` and `mark_correctness_unknown`
        twice."""
        led = make_ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "f")
        led.reopen(pin["id"], reason="the elected enum is rejected by 4% of writes")
        self.assertIsNone(pin.get("verification"))

    def test_the_cascade_pays_the_dependents_too(self):
        """`_reopen_minimal` is the one place either arc moves anything, so the closure it sweeps up
        gets the same treatment as the pin the arc names — the v0.20 lesson, on the carriers."""
        led = make_ledger()
        root = self._closed_defect(led, title="root")
        dep = led.add_pin(kind="defect", title="dependent", severity="medium",
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"}, depends_on=[root["id"]])
        item = led.add_remediation(dep["id"], action="align", ladder_rung=2)
        led.set_remediation_status(dep["id"], item["id"], "done")
        led.resolve(dep["id"], evidence="observed on staging", rung="observed")
        led.reopen(root["id"], reason="both blew the threshold", fired="incident")
        self.assertIsNone(dep["verification"]["rung"])
        self.assertEqual(led.settlement_verdict(dep, "resolve"), "unverified")

    # -- the dispute mark: one writer, not one door ----------------------------------------------

    def test_the_dispute_mark_is_cleared_by_the_writer_and_not_by_one_door(self):
        """`pin.pop("substate", …)` lived in `decide`, so the three election doors cleared it and
        `resolve` did not: the fully honest path — reopen, fresh remediation, fresh evidence, an
        explicit `rung="observed"` — ended `state=resolved substate=reopened`, which
        `REOPENED_SUBSTATES` defines as *disputed and not re-answered*."""
        led = make_ledger()
        pin = self._closed_defect(led)
        led.reopen(pin["id"], reason="loop is back on mobile", fired="incident")
        self.assertEqual(pin["substate"], "reopened")
        item = led.add_remediation(pin["id"], action="align", ladder_rung=3)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="re-observed on a real mobile client, 50 refreshes",
                    rung="observed")
        self.assertEqual(pin["state"], "resolved")
        self.assertIsNone(pin.get("substate"),
                          "finished work may not also be disputed-and-not-re-answered")

    def test_every_door_that_lands_in_a_settled_state_clears_it_and_the_fifth_does_not(self):
        """Derived from `_STATE_BY_DOOR` rather than listed, so the distinction survives a door
        being added. `correctness_unknown` keeps the mark on purpose: it hands the pin back to the
        human still carrying the outcome that was disputed."""
        import ledger as ledger_mod
        for door in ledger_mod.SETTLEMENT_DOORS:
            led = make_ledger()
            pin = add_simple_pin(led, kind="design_concern", severity="medium")
            led.decide(pin["id"], "opt_a", "r", "f")
            pin["substate"] = "contested"          # as `cross_derive` leaves it
            if door == "decide":
                led.decide(pin["id"], "opt_b", "r2", "f2")
            elif door == "accept":
                led.accept(pin["id"], rationale="r", flip_criteria="f")
            elif door == "defer":
                led.defer(pin["id"], rationale="r", flip_criteria="f")
            elif door == "correctness_unknown":
                led.mark_correctness_unknown(pin["id"], blocked_by="no oracle",
                                             attempted=["tests"])
            else:
                item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
                led.set_remediation_status(pin["id"], item["id"], "done")
                led.resolve(pin["id"], evidence="observed on staging", rung="observed")
            settled = ledger_mod._STATE_BY_DOOR[door] in ledger_mod.SETTLED_STATES
            self.assertEqual(pin.get("substate") is None, settled, f"{door}: {pin['state']}")

    # -- reading a ledger is never the operation that fails on it, at the THIRD reader -----------

    #: The pin shapes v0.21 hardened `summary` and `interview_view` against. The same list, because
    #: the principle carries no qualifier and the third reader is under it too.
    BROKEN_PINS = (
        {"id": "pin_0002", "kind": "contract_mismatch", "state": "needs_input"},   # no severity
        {"id": "pin_0003", "kind": "contract_mismatch", "state": "needs_input", "severity": None},
        {"id": "pin_0004", "kind": "contract_mismatch", "state": "needs_input", "severity": "huge"},
        {"id": "pin_0005", "kind": "contract_mismatch", "severity": "medium"},     # no state
        {"kind": "contract_mismatch", "state": "needs_input", "severity": "medium"},  # no id
        {"id": "pin_0007", "kind": "contract_mismatch", "state": "needs_input",
         "severity": "medium", "question": "which side wins?"},                   # fork not an object
    )

    def test_the_read_only_preview_survives_every_pin_shape_its_siblings_do(self):
        """Reproduced over stdio: on a two-pin ledger whose second pin carries no `severity`,
        `ledger_summary` and `interview_next` both answered and `policy_preview` — *"Read-only"* in
        its own first line — came back `isError: true` with the body `'severity'`."""
        for broken in self.BROKEN_PINS:
            with self.subTest(pin=broken):
                led = make_ledger()
                add_simple_pin(led, severity="medium")
                led.data["pins"].append(dict(broken))
                led.summary(), led.interview_view()          # the two v0.21 hardened
                radius = led.policy_preview({"kind": "contract_mismatch"}, "opt_a")
                self.assertEqual(radius["would_decide"], ["pin_0001"])

    def test_a_severity_this_runtime_cannot_rank_is_held_back_not_defaulted(self):
        """The direction the substitution goes, and it is the only safe one: the mark exists because
        `blocker|high` are never silently defaulted, and a severity nobody can read is not evidence
        that silence is safe. `_MAY_BE_SILENT`, the same complement `assign_resolution_modes` asks
        of the closed set."""
        led = make_ledger()
        add_simple_pin(led, severity="medium")
        led.data["pins"].append({"id": "pin_0002", "kind": "contract_mismatch",
                                 "state": "needs_input", "severity": "catastrophic",
                                 "question": {"options": [{"id": "opt_a", "label": "A"}]}})
        radius = led.policy_preview({"kind": "contract_mismatch"}, "opt_a")
        self.assertEqual((radius["would_decide"], radius["held_back"]),
                         (["pin_0001"], ["pin_0002"]))

    def test_the_exception_list_still_matches_on_a_pin_that_carries_an_id(self):
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        radius = led.policy_preview({"kind": "contract_mismatch"}, "opt_a",
                                    exceptions=[pin["id"]])
        self.assertEqual(radius["excepted"], [pin["id"]])

    # -- the other funnel door's other end ------------------------------------------------------

    def test_proposals_are_refused_on_a_pin_that_poses_no_fork(self):
        """v0.20 gave this door the `CLOSED_STATES` refusal from one end of the range. At the other
        end a `detected` pin was accepted in silence, and there the write is unreachable by
        construction: this moves `needs_input -> brainstorming`, so a `detected` pin keeps the state
        it has, outside `INTERVIEW_STATES`, and its proposals reach no surface on any host."""
        import ledger as ledger_mod
        led = make_ledger()
        pin = led.add_pin(kind="design_concern", title="no rate limiting anywhere",
                          severity="medium", confidence="inferred",
                          provenance=[{"source": "recon", "detail": "route scan"}])
        self.assertEqual(pin["state"], "detected")
        with self.assertRaises(LedgerError) as ctx:
            led.add_proposals(pin["id"], [{"summary": "token bucket at the edge"}])
        self.assertIn("set_question", str(ctx.exception))
        self.assertIsNone(pin["brainstorm"])
        self.assertEqual(pin["state"], "detected")
        # and the door that answers it makes the write legal
        led.set_question(pin["id"], {"prompt": "Where do limits live?",
                                     "options": [{"id": "edge", "label": "at the edge"},
                                                 {"id": "app", "label": "per route"}],
                                     "allow_freeform": True})
        led.add_proposals(pin["id"], [{"summary": "token bucket at the edge"}])
        self.assertEqual(pin["state"], "brainstorming")
        self.assertIn(pin["state"], ledger_mod.INTERVIEW_STATES)
        self.assertEqual([p["id"] for p in led.interview_view()], [pin["id"]])

    def test_no_state_this_door_admits_leaves_the_pin_out_of_reach(self):
        """The general form, over the closed vocabulary: for every state a pin can be in, either
        `add_proposals` refuses it, or the pin ends up somewhere the interview actually looks. That
        is the property `detected` broke, and it is decidable for all of them."""
        import ledger as ledger_mod
        for state in ledger_mod.STATES:
            with self.subTest(state=state):
                led = make_ledger()
                pin = add_simple_pin(led, severity="medium")
                pin["state"] = state
                try:
                    led.add_proposals(pin["id"], [{"summary": "an option for the fork"}])
                except LedgerError:
                    continue
                self.assertIn(pin["state"], ledger_mod.INTERVIEW_STATES + ("decided",),
                              "proposals written where no surface will show them")


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
        ("ledger.py", "add_proposals"): "`needs_input`/`detected` -> `brainstorming`. Still open, "
                                        "still in "
                                        "`interview_view` since v0.17 — a pin being thought about "
                                        "has not been answered.",
        # `cross_derive` was here until v0.24, writing `needs_input` itself on provider
        # disagreement. That is what made it a third way back into the open set with none of the
        # arcs' obligations — it is `REOPEN_ARCS`' third member now, and the writer below is the one
        # that moves it.
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
        """AST over every assignment to `pin["substate"]`, in both shapes it can come in.

        **v0.24 removed the shape this test was written for, and that is the finding rather than a
        regression.** It used to hold two writers: `cross_derive` assigned the literal `"contested"`,
        `_reopen_minimal` assigned a lookup in `_SUBSTATE_BY_ARC` — and the literal was the whole of
        why `contested` had to be spelled out beside a table it was not in. There is one writer now,
        so `assertTrue(literals)` would fail on the fixed tree; what replaces it is the assertion
        that made it worth having: **every mark reaches the pin through the arc table the readers'
        set is composed from.** A literal is still allowed and still checked — a fifth arc that
        writes its own mark by hand fails on the membership line, not on a count.
        """
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
            brief_decisions={"client": {"outcome": "carrier-pigeon",
                                        "quote": "the brief says carrier pigeon"},
                             "domain": {"outcome": "elicit_entities",
                                        "quote": "the brief lists the entities"}})
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
        # v0.23 — every one of these was reproduced over stdio against the SHIPPED server, on the
        # two surfaces this class's own `test_no_reading_surface_dies_on_any_of_them` walks and
        # never caught: they are the PROJECTIONS, and neither builds a `Ledger`.
        "a pin is null": lambda d: d["pins"].append(None),
        "pins is not a list": lambda d: d.update(pins="everything is fine"),
        "decision_log is not a list": lambda d: d.update(decision_log={"ev_0001": "happened"}),
        "policies is not a list": lambda d: d.update(policies=None),
        "a log entry is a string": lambda d: d["decision_log"].append("ev_0001 happened"),
        "a policy is a string": lambda d: d["policies"].append("always prefer X"),
        "severity is a list": lambda d: d["pins"][0].update(severity=["high"]),
        "title is not a string": lambda d: d["pins"][0].update(title={"text": "nope"}),
        "decision is a string": lambda d: d["pins"][0].update(state="decided",
                                                              decision="ev_0001"),
        "a policy rule is not a string": lambda d: d["policies"].append(
            {"id": "pol_0001", "rule": ["prefer", "X"], "applies_to": {},
             "default_outcome": "opt_a"}),
        "a policy scope is a string": lambda d: d["policies"].append(
            {"id": "pol_0002", "rule": "prefer X", "applies_to": "everything",
             "default_outcome": "opt_a"}),
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
            "a pin is null": "entry_shape",
            "pins is not a list": "collection_shape",
            "a log entry is a string": "entry_shape",
            "a policy is a string": "entry_shape",
            "severity is a list": "pin_severity",
            "title is not a string": "pin_title",
            "decision is a string": "pin_decision",
            "a policy rule is not a string": "policy_rule",
            "a policy scope is a string": "policy_applies_to",
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
        """The inverted half, and the one that keeps this honest: a field the read path substitutes
        with no `PIN_RULES` entry is a silent substitution, which is the failure this class fixed.

        Held against `PIN_SHAPES` from v0.25 rather than against `set(pin_read({}))`. The old
        equality was true and weak: `pin_read` returned exactly the seven keys it materialises, so
        the two sets agreed *because both were the same hand-written seven*. The table is the
        carrier now, both are derived from it, and the equality says what it always meant to."""
        from ledger import PIN_RULES, PIN_SHAPES
        self.assertEqual({name.removeprefix("pin_") for name, _h, _m in PIN_RULES},
                         {path.replace(".", "_") for path in PIN_SHAPES},
                         "a guarded read and a reported rule are two halves of one mechanism")

    def test_the_read_actually_delivers_every_shape_it_declares(self):
        """The claim `pin_read` makes, asked of every declared path over the DERIVED corpus rather
        than of the seven somebody wrote down. This is the assertion the round turns on: whatever
        the file carries at a declared path, a reader gets that path's declared shape."""
        from ledger import PIN_SHAPES, SHAPE_HOLDS, _at, pin_read
        from shape_corpus import broken_pins
        cases = broken_pins()
        self.assertGreater(len(cases), 60, "the derivation went vacuous")
        for label, pin in cases:
            with self.subTest(shape=label):
                read = pin_read(pin)
                for path, shape in PIN_SHAPES.items():
                    value = _at(read, path)
                    if value is None:
                        continue          # absent stays absent unless it is one of the guaranteed
                    self.assertTrue(SHAPE_HOLDS[shape](value),
                                    f"`{path}` reached a reader as {type(value).__name__} on "
                                    f"{label!r} — the read path guarantees {shape}")

    def test_every_declared_shape_has_a_probe_that_refuses_it(self):
        """The corpus's own floor. A shape token no probe violates would give that path an EMPTY
        corpus — a gate that runs zero cases and passes, which is precisely the failure the derived
        corpus was built to end. So the probe set is held to the shape vocabulary, not to the
        paths."""
        from ledger import SHAPE_HOLDS
        from shape_corpus import PROBES
        for shape, holds in SHAPE_HOLDS.items():
            with self.subTest(shape=shape):
                self.assertTrue(any(not holds(v) for _label, v in PROBES),
                                f"no probe violates {shape!r}, so every path declaring it is "
                                f"tested by nothing")

    def test_every_derived_violation_is_reported_by_its_own_rule(self):
        """Nothing is substituted in silence, over the whole derived corpus — the pin half of the
        promise `nonconforming` makes, asked of every path instead of the five it was written for."""
        from ledger import nonconforming
        from shape_corpus import GOOD_PIN, broken_pins
        base = {"version": SCHEMA_VERSION, "pins": [], "decision_log": [], "policies": []}
        self.assertEqual(nonconforming({**base, "pins": [dict(GOOD_PIN)]}), {},
                         "the corpus's own control pin is not conforming, so every case below "
                         "would report a rule it did not mean to")
        for label, pin in broken_pins():
            with self.subTest(shape=label):
                report = nonconforming({**base, "pins": [pin]})
                self.assertTrue(report, f"{label!r} is substituted by the read path and reported "
                                        f"by nobody")

    def test_a_ledger_whose_top_level_is_not_an_object_is_refused_not_crashed(self):
        """v0.25 — `Ledger.__init__` called `self.data.get("version")` before any guard ran, so a
        file holding a bare list or string killed every surface at once with an `AttributeError`.
        The constructor serves the WRITE path, so it refuses; the two projections build no `Ledger`
        and must answer instead."""
        import instructions
        import map as mapmod
        from ledger import nonconforming, readable_ledger
        for raw in (["nope"], "nope", 7):
            with self.subTest(top=type(raw).__name__):
                path = os.path.join(tempfile.mkdtemp(), "ledger.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(raw, fh)
                with self.assertRaises(LedgerError) as ctx:
                    Ledger(path)
                self.assertIn("top level", str(ctx.exception))
                self.assertEqual(nonconforming(raw), {"ledger_shape": [type(raw).__name__]})
                self.assertEqual(readable_ledger(raw)["pins"], [])
                mapmod.render(raw, title="t")          # a projection answers about it
                instructions.render(raw)

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


class TestTheShapeTableIsTheWritersOwnShapes(unittest.TestCase):
    """`PIN_SHAPES` is the carrier every other part of the read path is derived from, so it is the
    one thing that cannot itself be a declaration nobody checks.

    Its membership rule is stated on the table and is what is asserted here, in both directions:
    **a path is declared iff a reader can INDEX INTO its value** — every object and every list this
    runtime writes into a pin, plus the top-level scalars a reader coerces. A nested scalar is
    deliberately absent, because nothing indexes into a string.

    Driven by `walk_every_pin_writer`, the same walk `PIN_FIELDS` is held to — one answer to "what
    does this runtime write", asked by both declarations."""

    def test_every_container_a_writer_writes_is_declared_with_the_shape_it_wrote(self):
        import ledger as ledger_mod
        _written, shots = walk_every_pin_writer()
        undeclared, wrong = set(), set()
        for pin in shots:
            for field, value in pin.items():
                pairs = [(field, value)]
                if isinstance(value, dict):
                    pairs += [(f"{field}.{k}", v) for k, v in value.items()]
                for path, val in pairs:
                    if not isinstance(val, (dict, list)):
                        continue
                    if path not in ledger_mod.PIN_SHAPES:
                        undeclared.add(path)
                    elif not ledger_mod.SHAPE_HOLDS[ledger_mod.PIN_SHAPES[path]](val):
                        wrong.add(f"{path}: declared {ledger_mod.PIN_SHAPES[path]}, wrote "
                                  f"{type(val).__name__}")
        self.assertEqual(sorted(undeclared), [],
                         "a container this runtime writes into a pin that no shape declares — a "
                         "reader indexes into it, so it is exactly the class the corpus is derived "
                         "from")
        self.assertEqual(sorted(wrong), [],
                         "the table declares a shape its own writer does not write")

    def test_every_declared_path_is_one_a_writer_can_reach(self):
        """The inverse, and the one that stops the table growing paths nothing produces: a declared
        path that no door writes is a rule that reports on nothing and a corpus of dead cases."""
        import ledger as ledger_mod
        from ledger import _at
        _written, shots = walk_every_pin_writer()
        unreachable = [p for p in ledger_mod.PIN_SHAPES
                       if all(_at(pin, p) is None for pin in shots)]
        self.assertEqual(sorted(unreachable), [],
                         "a declared path no writer in this package writes")

    def test_every_scalar_a_settlement_door_decides_on_has_a_membership_rule(self):
        """v0.26 — `kind` was the third closed vocabulary a pin carries and the only one with no
        rule, so a wrong-typed or out-of-set `kind` was invisible to `nonconforming` on every
        surface while `state` and `severity` were reported on all of them.

        Derived from `SETTLEMENT_CARRIERS` rather than listed: a carrier a door decides from, whose
        value is a SCALAR, picks a branch — `settlement_verdict` sends a `defect` and a
        `design_concern` down different ones — so a value outside the set silently takes the pin
        somewhere nobody elected. The container carriers are excluded because a rule about their
        MEMBERS is a different question, and `PIN_SHAPES` answers it.
        """
        import ledger as ledger_mod
        scalars = [c for c in ledger_mod.SETTLEMENT_CARRIERS
                   if ledger_mod.PIN_SHAPES.get(c) == "str"]
        self.assertEqual(sorted(scalars), ["kind", "state"], "the derivation went vacuous")
        for path in scalars:
            with self.subTest(carrier=path):
                self.assertIn(path, ledger_mod.PIN_STRONGER,
                              f"`{path}` decides a settlement branch and its only rule is that it "
                              f"is a string — every value outside the closed set reads as a valid "
                              f"one on every surface")

    def test_a_stronger_rule_implies_the_shape_it_replaces(self):
        """`PIN_STRONGER` replaces a path's shape rule with a membership one, under one name. That
        is only sound while the stronger predicate is actually stronger — a membership rule that
        admitted a non-string would leave the shape unreported under a name that claims to cover
        it."""
        import ledger as ledger_mod
        for table, shapes in ((ledger_mod.PIN_STRONGER, ledger_mod.PIN_SHAPES),
                              (ledger_mod.POLICY_STRONGER, ledger_mod.POLICY_SHAPES)):
            for path, (holds, _msg) in table.items():
                with self.subTest(path=path):
                    shape = shapes[path]
                    for _label, probe in __import__("shape_corpus").PROBES:
                        if holds(probe):
                            self.assertTrue(ledger_mod.SHAPE_HOLDS[shape](probe),
                                            f"the stronger rule on `{path}` admits a "
                                            f"{type(probe).__name__}, which its shape refuses")


class TestReadingAPolicyIsNeverTheOperationThatFails(unittest.TestCase):
    """v0.23 — `pin_read`'s twin, and it exists because the pin half was fixed alone.

    `instructions.render` called `.strip()` on `policy["rule"]` and `.items()` on
    `policy["applies_to"]`, on the collection whose CONTAINER the same function had already learned
    to guard one line above. Reproduced over stdio against the shipped server: a policy whose scope
    is a string returned `'str' object has no attribute 'items'` from `generate_instructions`, which
    writes the one file every host loads unprompted.

    Same three assertions the pin half carries, because it is the same mechanism: the read
    substitutes, a rule reports that it did, and the write cannot produce a record either refuses.
    """

    def test_every_field_the_policy_read_substitutes_has_a_rule_that_reports_it(self):
        from ledger import POLICY_RULES, POLICY_SHAPES
        self.assertEqual({name.removeprefix("policy_") for name, _h, _m in POLICY_RULES},
                         {path.replace(".", "_") for path in POLICY_SHAPES},
                         "a guarded read and a reported rule are two halves of one mechanism")

    def test_the_policy_read_delivers_every_shape_it_declares(self):
        """`pin_read`'s gate, one collection over, over the same derived corpus."""
        from ledger import POLICY_SHAPES, SHAPE_HOLDS, _at, policy_read
        from shape_corpus import broken_policies
        cases = broken_policies()
        self.assertGreaterEqual(len(cases), 9, "the derivation went vacuous")
        for label, policy in cases:
            with self.subTest(shape=label):
                read = policy_read(policy)
                for path, shape in POLICY_SHAPES.items():
                    value = _at(read, path)
                    if value is None:
                        continue
                    self.assertTrue(SHAPE_HOLDS[shape](value), f"`{path}` on {label!r}")

    def test_no_policy_this_runtime_writes_can_break_one_of_these_rules(self):
        """The claim the one-caller table rests on, asserted rather than argued — `set_policy`'s
        twin of `add_pin`'s."""
        from ledger import POLICY_EVIDENCE, policy_violations
        led = make_ledger()
        for evidence in POLICY_EVIDENCE:
            for scope in ({"kind": "contract_mismatch"}, {}):
                policy = led.add_policy(rule="the DB wins on nullability", applies_to=scope,
                                        default_outcome="opt_a", evidence=evidence,
                                        human_answer="the DB is the source of truth")
                self.assertEqual(policy_violations(policy), [],
                                 f"set_policy composed a {evidence} policy the read path cannot "
                                 f"index")

    def test_an_unreadable_scope_is_read_as_the_widest_one_and_not_the_narrowest(self):
        """The substitution has a direction and it is the honest one. `{}` as a scope is the
        UNIVERSAL selector, so a rule whose radius cannot be read is shown at its widest — the
        alternative is a surface quietly telling a human that a rule they are about to elect binds
        less than it might."""
        from ledger import policy_read
        self.assertEqual(policy_read({"id": "pol_0001", "rule": "x",
                                      "applies_to": "everything"})["applies_to"], {})


class TestOneSeverityOrderingForTheWholePackage(unittest.TestCase):
    """`instructions._SEVERITY_RANK` read a MISSING severity as `low` and an unrecognised one as 9,
    so a pin whose file says nothing about how bad it is sorted AHEAD of a pin that states a
    severity outside the set — in the section a tight line budget clips first. `severity_rank` says
    the opposite and carries the argument for it. Two surfaces, two tables, and the newer one
    contradicted the older's argued direction.

    Three copies existed (`instructions`, `readiness`, `findings`). The gate is derived from
    `SEVERITIES` itself, so a fourth fails on the day it is written rather than on the day someone
    reads for it."""

    def test_the_direction_is_the_one_pin_read_argues_for(self):
        from ledger import pin_read, severity_rank
        stated = severity_rank(pin_read({"severity": "low"})["severity"])
        missing = severity_rank(pin_read({})["severity"])
        unknown = severity_rank(pin_read({"severity": "catastrophic"})["severity"])
        self.assertLess(stated, missing,
                        "a severity the file states must sort ahead of one it does not")
        self.assertEqual(missing, unknown,
                         "missing and unrecognised are the same amount of nothing — reading one of "
                         "them as `low` is reading a claim the file does not make")

    def test_no_module_but_the_schema_carries_a_severity_ordering(self):
        """A dict literal mapping severity names to numbers, anywhere in the runtime or the MCP
        layer, IS a second ordering. Membership is `SEVERITIES`, so the gate cannot fall behind the
        vocabulary; two names is the threshold because one pair is not an ordering."""
        import ast
        import pathlib
        from ledger import SEVERITIES
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        offenders = []
        for path in sorted(list((root / "runtime").glob("*.py"))
                           + list((root / "mcp").glob("*.py"))):
            if path.name == "ledger.py":
                continue                     # the one home of the table
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                keys = {k.value for k in node.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                ranked = all(isinstance(v, ast.Constant) and isinstance(v.value, int)
                             for v in node.values) and bool(node.values)
                if ranked and len(keys & set(SEVERITIES)) >= 2:
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [],
                         f"a second severity ordering lives at {offenders} — `severity_rank` is "
                         "the one table, and the last copy of it disagreed with it")


class TestEveryReaderOfACollectionGoesThroughTheCarrier(unittest.TestCase):
    """The gate for the class this whole round is: **a rule paid at a class's methods is unpaid for
    every caller that holds the class's DATA instead of the class.**

    `Ledger.readable` guarded the three collections in v0.21. `map.render` and
    `instructions.render` read a ledger as JSON and never build a `Ledger`, so both walked
    `data.get("policies") or []` and called `.get` on whatever came out — four reproductions over
    stdio, all `'str' object has no attribute 'get'`, on files `ledger_summary` reported the
    nonconformance of in the same session. Two rounds of hardening the read path went straight past
    them because nothing asked *who else names these collections*.

    So: naming one of `LEDGER_COLLECTIONS` as a subscript or a `.get` key, outside the module that
    owns the schema, is what this forbids. The names come from the tuple, so a fourth collection is
    covered the day it is declared. `ledger.py` is excluded because it is the carrier's home AND the
    WRITE path, which deliberately keeps `self.data[…]` — a write onto a file this runtime cannot
    read is a different question, and the answer there is to refuse."""

    def test_no_module_but_the_schema_indexes_a_collection_directly(self):
        import ast
        import pathlib
        from ledger import LEDGER_COLLECTIONS
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        names = set(LEDGER_COLLECTIONS)
        offenders = []
        for path in sorted(list((root / "runtime").glob("*.py"))
                           + list((root / "mcp").glob("*.py"))):
            if path.name == "ledger.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                        and node.slice.value in names and isinstance(node.ctx, ast.Load)):
                    offenders.append(f"{path.name}:{node.lineno} [{node.slice.value!r}]")
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value in names):
                    offenders.append(f"{path.name}:{node.lineno} .get({node.args[0].value!r})")
        self.assertEqual(offenders, [],
                         f"a collection is read outside the guarded path at {offenders} — "
                         "`read_collection` / `readable_ledger` / `Ledger.readable` is the one "
                         "door, and every reader that skipped it died on a shape the same file's "
                         "`ledger_summary` reported")

class TestTheThirdArcPaysWhatTheOtherTwoPay(unittest.TestCase):
    """v0.24 — `cross_derive(agreement="disagree")` was a reopen arc with no membership.

    It wrote `"reopened": true` on its own event and moved the pin with its own three lines of
    state, so every obligation v0.20 and v0.22 attached to `REOPEN_ARCS` and to `_reopen_minimal`
    went past it: no `cas_` record for anything it swept up, no carrier invalidation, and its
    closed-state question spelled out inline where nothing else could ask it.

    Reproduced over real `uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd:
    `add_pin(defect) -> add_remediation -> done -> cross_derive(agree)` (the envelope reaches the
    `cross_derived` rung) `-> cross_derive(disagree)` came back `state: "needs_input"` with
    `verification.rung` still `cross_derived`, and `ledger_resolve` with
    `evidence="no new observation of any kind"` then answered `{"state": "resolved"}`.
    """

    def _closed_defect(self, led):
        pin = led.add_pin(kind="defect", title="double charge on retry", severity="high",
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        return pin

    AGREE = ({"provider": "anthropic", "model": "opus", "result": "the retry is idempotent"},
             {"provider": "openai", "model": "gpt", "result": "the retry is idempotent"})
    DIFFER = ({"provider": "anthropic", "model": "opus", "result": "idempotent"},
              {"provider": "openai", "model": "gpt", "result": "NOT idempotent"})

    # -- the structural half: the arc table IS the callers of the one writer --------------------

    def test_the_arc_that_moves_a_pin_is_on_the_table_that_charges_the_tolls(self):
        """`TestComingBackIntoTheOpenSetIsGovernedToo` already asserts callers == `REOPEN_ARCS`;
        this states the consequence that made the third arc worth finding. Every axis on which the
        arcs differ is a table, so being different costs an entry rather than a second writer."""
        import ledger as mod
        self.assertEqual(sorted(mod.REOPEN_ARCS), sorted(mod.ARC_MOVES))
        self.assertEqual(sorted(mod.REOPEN_ARCS), sorted(mod.ARC_CASCADES))
        self.assertEqual(sorted(mod.REOPEN_ARCS), sorted(mod._SUBSTATE_BY_ARC))
        self.assertEqual(set(mod.REOPENED_SUBSTATES), set(mod._SUBSTATE_BY_ARC.values()),
                         "a mark composed from anything but the arc table is a second list")
        for arc, states in mod.ARC_MOVES.items():
            self.assertLessEqual(set(states), set(mod.STATES), f"{arc} moves a state that is not one")

    def test_the_disagreement_arc_takes_back_the_claim_a_settlement_door_reads(self):
        """The reproduction, in the library. The pin comes back open and no longer tells the next
        `resolve` that its behaviour was observed — which is `SETTLEMENT_CARRIERS`' `invalidated`
        disposition, paid by the arc it was not a member of."""
        led = make_ledger()
        pin = self._closed_defect(led)
        led.cross_derive(pin["id"], claim="the retry path is idempotent",
                         derivations=list(self.AGREE), agreement="agree")
        self.assertEqual(pin["verification"]["rung"], "cross_derived")
        led.cross_derive(pin["id"], claim="the retry path is idempotent",
                         derivations=list(self.DIFFER), agreement="disagree")
        self.assertEqual((pin["state"], pin["substate"]), ("needs_input", "contested"))
        self.assertIsNone(pin["verification"]["rung"], "the refuted claim is taken back")
        self.assertEqual(led.settlement_verdict(pin, "resolve"), "unverified")
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], evidence="no new observation of any kind")
        self.assertIn("unverified", str(ctx.exception))

    def test_it_still_cascades_nothing_and_the_table_is_where_that_is_said(self):
        """The decision this arc has always made, kept verbatim and now declared: nobody yet knows
        which side is wrong, so the neighbourhood is not reopened. Held against the two arcs that
        DO cascade, on the same fixture, so the assertion is a difference rather than a zero."""
        import ledger as mod
        self.assertEqual(mod.ARC_CASCADES["cross_derive"], False)
        for arc in ("cross_derive", "reopen"):
            led = make_ledger()
            root = self._closed_defect(led)
            led.resolve(root["id"], evidence="observed on staging", rung="observed")
            dep = led.add_pin(kind="defect", title="dependent", severity="medium",
                              confidence="extracted",
                              provenance=[{"source": "recon", "detail": "x"}],
                              as_is={"description": "d"}, depends_on=[root["id"]])
            item = led.add_remediation(dep["id"], action="align", ladder_rung=2)
            led.set_remediation_status(dep["id"], item["id"], "done")
            led.resolve(dep["id"], evidence="observed on staging", rung="observed")
            if arc == "reopen":
                event = led.reopen(root["id"], reason="both blew the threshold", fired="incident")
                self.assertEqual(led.cascaded_by(event["id"]), [dep["id"]])
                self.assertEqual(dep["state"], "needs_input")
            else:
                # a disagreement may not un-close finished work at all, which is `ARC_MOVES`
                record = led.cross_derive(root["id"], claim="the retry path is idempotent",
                                          derivations=list(self.DIFFER), agreement="disagree")
                self.assertEqual(led.reopen_verdict(root, "cross_derive"), "already_closed")
                self.assertEqual(led.cascaded_by(record["event_id"]), [])
                self.assertEqual((root["state"], dep["state"]), ("resolved", "resolved"))

    def test_every_bucket_the_verdict_can_answer_is_reachable(self):
        """A bucket no arc/state pair produces is a word in a tuple. Derived over the product of
        the two closed sets rather than asserted for the three cases somebody had in mind."""
        import ledger as mod
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        seen = set()
        for arc in mod.REOPEN_ARCS:
            for state in mod.STATES:
                pin["state"] = state
                seen.add(led.reopen_verdict(pin, arc))
        self.assertEqual(seen, set(mod.REOPEN_BUCKETS))

    def test_an_arc_this_runtime_does_not_have_is_refused(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led.reopen_verdict(pin, "cross_derivation")   # the arc's old name


class TestOnlyAFreshObservationRaisesARefutedClaim(unittest.TestCase):
    """v0.24 — `cross_derive(agreement="agree")` laundered the demotion the reopen had just written.

    Reproduced over real stdio, four calls apart: `resolve(rung="observed")` closed the pin,
    `ledger_reopen(fired="incident")` demoted the envelope and wrote `blocked_by`, `ledger_resolve`
    correctly refused as `unverified` — and one agent-authored `ledger_cross_derive(agreement=
    "agree")` merged `rung: "cross_derived"` back onto that same envelope, `blocked_by` untouched,
    after which the pin closed.

    The structural half is the general form: *who may write a closing rung* had as many answers as
    there were writers, and the writers rest on different things. So they are enumerated from the
    AST and each one declares what fresh thing it stands on.
    """

    @staticmethod
    def _rung_writers():
        """Every function that writes a `rung` into a `verification` envelope, both shapes it takes:
        `<x>["rung"] = …`, and a dict literal carrying a `"rung"` key assigned to `<x>
        ["verification"]`. Anchored on the assignment, never on a grep for the word."""
        import ast
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        found = set()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not (isinstance(target, ast.Subscript)
                            and isinstance(target.slice, ast.Constant)):
                        continue
                    if target.slice.value == "rung":
                        found.add(fn.name)
                    elif (target.slice.value == "verification"
                          and isinstance(node.value, ast.Dict)
                          and any(isinstance(k, ast.Constant) and k.value == "rung"
                                  for k in node.value.keys)):
                        found.add(fn.name)
        return found

    def test_every_writer_of_a_rung_declares_what_it_rests_on(self):
        import ledger as mod
        self.assertEqual(self._rung_writers(), set(mod.VERIFICATION_RUNG_WRITERS),
                         "a function that writes the rung a settlement gate opens on, with nothing "
                         "saying what fresh thing it stands on — declare it in "
                         "`VERIFICATION_RUNG_WRITERS`")
        self.assertLessEqual(set(mod.VERIFICATION_RUNG_WRITERS.values()),
                             set(mod.RUNG_WRITER_KINDS))
        self.assertEqual({k for k, v in mod.VERIFICATION_RUNG_WRITERS.items()
                          if v == "re_derivation"}, {"cross_derive"},
                         "the behavioural half below covers exactly this kind; a second member "
                         "would be uncovered")

    def test_a_re_derivation_does_not_answer_a_refutation(self):
        """The reproduction. The agreement is still recorded — an arc that drops the observation
        because it changed nothing is the shape v0.16 removed from this very function — and
        `rung_raised` is the carrier that says which happened."""
        led = make_ledger()
        pin = led.add_pin(kind="defect", title="p95 regression", severity="high",
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="p95 measured at 180ms in staging", rung="observed")
        led.reopen(pin["id"], reason="p95 blew the threshold in prod", fired="incident",
                   source="feedback:incident")
        self.assertTrue(refuted_claim(pin))

        record = led.cross_derive(pin["id"], claim="the hot path is O(1)",
                                  derivations=[{"provider": "anthropic", "model": "opus",
                                                "result": "yes"},
                                               {"provider": "openai", "model": "gpt",
                                                "result": "yes"}],
                                  agreement="agree")
        self.assertFalse(record["rung_raised"])
        self.assertEqual(record["refuted_claim"], pin["verification"]["blocked_by"])
        self.assertIsNone(pin["verification"]["rung"], "a re-derivation is not an observation")
        self.assertEqual(led.settlement_verdict(pin, "resolve"), "unverified")
        event = next(e for e in led.data["decision_log"] if e["id"] == record["event_id"])
        self.assertEqual((event["agreement"], event["rung_raised"], event["reopened"]),
                         ("agree", False, False))

    def test_the_way_out_is_still_open_and_it_is_the_one_that_states_an_observation(self):
        """A gate with no gate-opening move is a wall. `resolve` rests on `fresh_observation` and
        demands the evidence, so it re-raises the rung where a re-derivation may not."""
        led = make_ledger()
        pin = led.add_pin(kind="defect", title="p95 regression", severity="high",
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="p95 measured at 180ms", rung="observed")
        led.reopen(pin["id"], reason="p95 blew the threshold", fired="incident")
        item2 = led.add_remediation(pin["id"], action="align", ladder_rung=3)
        led.set_remediation_status(pin["id"], item2["id"], "done")
        led.resolve(pin["id"], evidence="re-measured on prod for 24h: p95 190ms", rung="observed")
        self.assertEqual(pin["state"], "resolved")
        self.assertEqual(refuted_claim(pin), "", "a closing rung answers the refutation")

    def test_an_unrefuted_pin_is_still_strengthened_by_agreement(self):
        """The rung is not withdrawn from the case it exists for — that would be the wall in the
        other direction, and `cross_derived` is a member of `_CLOSING_RUNGS` on purpose."""
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        record = led.cross_derive(pin["id"], claim="the export is unpaginated",
                                  derivations=[{"provider": "anthropic", "model": "o", "result": "y"},
                                               {"provider": "openai", "model": "g", "result": "y"}],
                                  agreement="agree")
        self.assertTrue(record["rung_raised"])
        self.assertEqual(pin["verification"]["rung"], "cross_derived")
        self.assertNotIn("refuted_claim", record)

    def test_reading_a_refutation_never_fails_on_the_shape_of_the_envelope(self):
        """`refuted_claim` is on the read path's own rule, because it is asked of a pin a file
        supplied: absence, a non-object envelope and a non-object pin all answer rather than raise."""
        for shape in (None, {}, {"verification": None}, {"verification": "blocked"},
                      {"verification": {"rung": None}}, "not a pin"):
            with self.subTest(pin=shape):
                self.assertEqual(refuted_claim(shape), "")
        self.assertEqual(refuted_claim({"verification": {"rung": None, "blocked_by": "why"}}),
                         "why")

    # -- v0.26: the table's THIRD column stops being prose ----------------------------------------

    def test_every_rung_writer_goes_through_the_one_refusal_with_its_own_name(self):
        """`VERIFICATION_RUNG_WRITERS` declared four KINDS of writer and enforced none of them.

        The kind that mattered is the one whose description asserted the enforcement:
        `records_absence` reads *"writes a rung BELOW the closing ones, or none at all… so it is
        asked nothing"*, and `mark_correctness_unknown` checked `rung in VERIFICATION_RUNGS` — the
        whole vocabulary. So the AST half is the load-bearing one: every writer must pay
        `_writable_rung`, and pay it under its own name, or a fifth writer inherits the same prose.
        """
        import ast

        import ledger as mod
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        paid = {}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "_writable_rung" and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    paid.setdefault(fn.name, set()).add(node.args[0].value)
        self.assertEqual(set(paid), set(mod.VERIFICATION_RUNG_WRITERS),
                         "a writer of the rung a settlement gate opens on that does not go through "
                         "`_writable_rung` — the kind it declares is then a sentence nothing checks")
        for name, named in sorted(paid.items()):
            self.assertEqual(named, {name},
                             f"{name} pays the carrier under somebody else's name, so it is judged "
                             f"by somebody else's kind")
        self.assertEqual(set(mod.RUNG_WRITER_RUNGS), set(mod.RUNG_WRITER_KINDS),
                         "a declared kind with no rungs is a column with no rule")

    def test_the_door_that_records_an_absence_may_not_claim_an_observation(self):
        """The reproduction, over the library. Derived: every writer whose kind is
        `records_absence` is exercised with every closing rung, and every one must refuse."""
        import ledger as mod
        absence = [n for n, kind in mod.VERIFICATION_RUNG_WRITERS.items()
                   if kind == "records_absence"]
        self.assertEqual(absence, ["mark_correctness_unknown"],
                         "the behavioural half below covers exactly this writer; a second member "
                         "would be uncovered")
        for rung in mod._CLOSING_RUNGS:
            with self.subTest(rung=rung):
                led = make_ledger()
                pin = add_simple_pin(led, kind="defect", severity="high")
                with self.assertRaises(LedgerError) as ctx:
                    led.mark_correctness_unknown(pin["id"], blocked_by="no oracle exists",
                                                 attempted=["tests"], rung=rung)
                self.assertIn("records_absence", str(ctx.exception))
                self.assertIsNone(pin.get("verification"),
                                  "the envelope was written before the rung was judged")

    def test_the_rungs_it_does_record_still_land(self):
        """The other direction: refusing the two closing rungs is not refusing the door."""
        import ledger as mod
        for rung in mod.RUNG_WRITER_RUNGS["records_absence"]:
            with self.subTest(rung=rung):
                led = make_ledger()
                pin = add_simple_pin(led, kind="defect", severity="high")
                led.mark_correctness_unknown(pin["id"], blocked_by="no oracle exists",
                                             attempted=["tests"], rung=rung)
                self.assertEqual(pin["verification"]["rung"], rung)
                self.assertEqual(pin["state"], "correctness_unknown")

    def test_the_laundering_route_the_reproduction_walked_is_closed(self):
        """Five calls, no human: resolve at `observed` -> reopen on an incident -> the correct
        `unverified` refusal -> `mark_correctness_unknown(rung="observed")` -> resolve, green."""
        led = make_ledger()
        pin = led.add_pin(kind="defect", title="double charge on retry", severity="high",
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="replayed on staging; one charge", rung="observed")
        led.reopen(pin["id"], reason="p95 blew the threshold", fired="incident")
        self.assertTrue(refuted_claim(pin))
        with self.assertRaises(LedgerError):
            led.mark_correctness_unknown(pin["id"], blocked_by="no oracle exists for this",
                                         attempted=["tests"], rung="observed")
        self.assertTrue(refuted_claim(pin), "the refutation is still standing")
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], evidence="I looked")
        self.assertIn("unverified", str(ctx.exception))

    def test_a_claimed_rung_rests_on_the_observation_this_call_states(self):
        """`SETTLEMENT_CARRIERS`' fifth carrier, removed rather than declared. `resolve` demanded
        *the observation it rests on* and accepted the `evidence` already ON the pin — which is the
        one the LAST resolve rested on, and after a reopen names exactly what production refuted."""
        led = make_ledger()
        pin = led.add_pin(kind="defect", title="double charge", severity="high",
                          confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
                          as_is={"description": "d"})
        item = led.add_remediation(pin["id"], action="align", ladder_rung=2)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="replayed on staging; one charge", rung="observed")
        led.reopen(pin["id"], reason="it came back", fired="incident")
        self.assertEqual(pin.get("evidence"), "replayed on staging; one charge")
        with self.assertRaises(LedgerError) as ctx:
            led.resolve(pin["id"], rung="observed")
        self.assertIn("observation it rests on", str(ctx.exception))


class TestAWriteOntoAPinThisRuntimeCannotReadIsRefused(unittest.TestCase):
    """v0.26 — the read path was hardened twice and the write doors read the same pins.

    Reproduced over real stdio against the shipped plugin: 42 crash sites across all fourteen
    per-pin write doors, over shapes the derived corpus already describes. The carrier is
    `Ledger.writable_pin`; this holds the two declarations it rests on.
    """

    def test_the_required_set_is_the_writers_own_output(self):
        """`PIN_REQUIRED` is not a list somebody typed: it is every declared path `add_pin`
        composes, which is exactly the set a write door may index unconditionally. A field added to
        the envelope joins it iff the writer writes it."""
        import ledger as mod
        from ledger import _at
        led = make_ledger()
        # The MINIMAL call, because the rule is "every declared path `add_pin` writes
        # UNCONDITIONALLY": a path that arrives only when a caller supplies the optional argument
        # for it is exactly the path a write door may not assume.
        minimal = led.add_pin(kind="defect", title="t", severity="low", confidence="extracted",
                              provenance=[{"source": "recon", "detail": "x"}])
        derived = {p for p in mod.PIN_SHAPES if _at(minimal, p) is not None}
        self.assertEqual(set(mod.PIN_REQUIRED), derived,
                         "`PIN_REQUIRED` and what `add_pin` actually writes have diverged — one of "
                         "them is a claim about the other")
        for pin in (minimal, add_simple_pin(led)):
            self.assertEqual(mod.pin_violations(pin), [],
                             "add_pin composed a pin its own rules refuse")

    def test_reading_still_substitutes_where_writing_refuses(self):
        """The split, asserted rather than argued: the same record is readable and unwritable.

        Materialising on the write path is not available and the reason is concrete — `question`
        and `decision` are `PIN_GUARANTEED` and `add_pin` writes both as an explicit `None`, so a
        fill would put `{}` on every pin in the file, and `{}` is falsy in Python and TRUTHY in
        JavaScript."""
        import ledger as mod
        led = make_ledger()
        pin = add_simple_pin(led)
        pin.pop("depends_on")
        led.save()
        self.assertEqual(mod.pin_read(pin)["depends_on"], [])
        with self.assertRaises(LedgerError) as ctx:
            led.writable_pin(pin["id"])
        self.assertIn("pin_depends_on", str(ctx.exception))
        self.assertIn("pre_rule_events", str(ctx.exception),
                      "a refusal an agent cannot act on is a wall")

    def test_every_shape_the_corpus_describes_is_refused_and_never_crashed(self):
        """Over the DERIVED corpus, at the one carrier. A shape the schema can describe is a
        refusal with a sentence, never an `AttributeError` naming a line of ours."""
        import ledger as mod
        from shape_corpus import broken_pins
        cases = broken_pins()
        self.assertGreaterEqual(len(cases), 100, "the derivation went vacuous")
        for label, broken in cases:
            with self.subTest(shape=label):
                tmp = tempfile.mkdtemp()
                path = os.path.join(tmp, "ledger.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"version": SCHEMA_VERSION, "pins": [broken],
                               "decision_log": [], "policies": []}, fh)
                led = Ledger(path)
                pin_id = mod.pin_read(broken)["id"]
                try:
                    led.writable_pin(pin_id)
                except LedgerError as exc:
                    self.assertIn("cannot be written to", str(exc))
                    continue
                except Exception as exc:                      # noqa: BLE001 — that IS the finding
                    self.fail(f"the write lookup crashed on {label!r}: "
                              f"{type(exc).__name__}: {exc}")
                self.fail(f"{label!r} passed the write lookup, so every door indexes it raw")


class TestFinishedWorkIsRefusedAtEveryDoorThatWritesToAPin(unittest.TestCase):
    """v0.24 — the rule that was PROSE at the two doors this branch added it to.

    Reproduced over real stdio on one `resolved` defect: `ledger_set_question` and
    `ledger_add_proposals` refused it in near-identical sentences, and `ledger_add_remediation`,
    `ledger_set_remediation_status`, `ledger_premortem` and `ledger_set_readiness` all wrote to it.

    The roster half is `tests/test_mcp_tools.py`, where the doors an agent can reach are derived.
    This is the library half: the table's dispositions must each be true of the code.
    """

    def test_every_disposition_is_declared_and_none_is_invented(self):
        import ledger as mod
        self.assertLessEqual(set(mod.PIN_WRITE_DOORS.values()),
                             set(mod.CLOSED_WORK_DISPOSITIONS))
        for name in mod.PIN_WRITE_DOORS:
            self.assertTrue(callable(getattr(mod.Ledger, name, None)),
                            f"{name} is on the table and is not a method of this class")

    def test_each_disposition_is_true_of_the_code_that_carries_it(self):
        """AST, per disposition: `refuse` asks `_gate_closed`, `settlement` reaches
        `_gate_settlement` (`decide` does it through `_settle`, and both are on the table),
        `arc` reaches `_reopen_minimal`. `records_only` is asked nothing, which is what it means."""
        import ast

        import ledger as mod
        path = os.path.join(os.path.dirname(__file__), "..", "src", "runtime", "ledger.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        calls = {name: {c.func.attr for c in ast.walk(fn)
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
                 for name, fn in fns.items()}

        def reaches(name, target, seen=()):
            if name in seen or name not in calls:
                return False
            if target in calls[name]:
                return True
            return any(reaches(c, target, seen + (name,)) for c in calls[name] if c in fns)

        required = {"refuse": "_gate_closed", "settlement": "_gate_settlement",
                    "arc": "_reopen_minimal"}
        self.assertEqual(set(required) | {"records_only"}, set(mod.CLOSED_WORK_DISPOSITIONS),
                         "a disposition with no assertion here is a promise nothing keeps")
        for door, disposition in sorted(mod.PIN_WRITE_DOORS.items()):
            if disposition == "records_only":
                continue
            with self.subTest(door=door, disposition=disposition):
                self.assertTrue(reaches(door, required[disposition]),
                                f"{door} is declared `{disposition}` and never reaches "
                                f"{required[disposition]}")

    def test_the_refusal_names_the_move_that_undoes_it(self):
        """A refusal an agent cannot act on is a wall, and this one has an opening move on every
        host. Asserted over every `refuse` door rather than the one that was written first."""
        import ledger as mod
        for door, disposition in sorted(mod.PIN_WRITE_DOORS.items()):
            if disposition != "refuse":
                continue
            with self.subTest(door=door):
                led = make_ledger()
                pin = add_simple_pin(led, severity="medium")
                pin["state"] = "resolved"
                with self.assertRaises(LedgerError) as ctx:
                    led._gate_closed(pin, door)
                self.assertIn("reopen", str(ctx.exception))
                self.assertIn(door, str(ctx.exception))

    def test_a_door_this_runtime_does_not_have_is_refused_by_the_gate(self):
        led = make_ledger()
        pin = add_simple_pin(led)
        with self.assertRaises(LedgerError):
            led._gate_closed(pin, "delete_everything")

    def test_the_gate_says_nothing_about_a_pin_that_is_merely_decided(self):
        """`CLOSED_STATES` and not `SETTLED_STATES`, which is the line `set_question` drew first:
        a `decided` pin is re-electable by the human, and everything downstream of an election is
        still legitimately being planned."""
        import ledger as mod
        led = make_ledger()
        pin = add_simple_pin(led, severity="medium")
        led.decide(pin["id"], "opt_a", "r", "f")
        for door, disposition in mod.PIN_WRITE_DOORS.items():
            if disposition == "refuse":
                led._gate_closed(pin, door)      # must not raise
        led.add_remediation(pin["id"], action="align", ladder_rung=2)


class TestTheBriefOwesTheBrief(unittest.TestCase):
    """v0.24 — `brief` was the one member of `DECISION_EVIDENCE` whose claim had no carrier.

    `elicited` is unreachable over MCP (the server computes it), `transcribed` demands
    `human_answer` at every door, `cascaded` demands `policy_id` on both sides of a biconditional.
    Reproduced over stdio with three clusters: one `ev_` event on disk carrying `evidence: "brief"`,
    `rationale: "pre-decided by the brief"`, and no reference of any kind to a brief.
    """

    def test_every_rung_owes_something_and_the_test_is_derived_from_the_vocabulary(self):
        """The finding's own shape, asserted rather than restated: for each rung, the FIELD its
        claim rests on and the CARRIER that refuses the write without it. A rung added to
        `DECISION_EVIDENCE` with no entry fails here — which is how this one would have been caught
        the day it was added.

        Two carriers and not one, because the two rules answer different questions and the split is
        `decide`'s own, stated in `decide`: `EVENT_RULES` holds what is decidable from the stored
        event alone (so `nonconforming` can replay it over a file this runtime did not write), and
        the quote rule is about the boundary an AGENT reaches, which the event does not record.
        """
        import ledger as mod
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp"))
        import tools as mcp_tools
        owed = {
            "elicited": (None, "the adapter computes it; no agent ever holds the value"),
            "transcribed": ("human_answer", "tools._require_quote"),
            "brief": ("brief_quote", "ledger.EVENT_RULES"),
            "cascaded": ("policy_id", "ledger.EVENT_RULES"),
        }
        self.assertEqual(set(owed), set(mod.DECISION_EVIDENCE),
                         "a rung whose evidence nothing carries is a claim an honest agent and a "
                         "fabricating one make identically")
        base = {"id": "ev_0001", "pin_id": "pin_0001", "outcome": "opt_a", "rationale": "r",
                "flip_criteria": "f", "source": "interview"}
        for rung, (field, carrier) in sorted(owed.items()):
            if field is None:
                continue
            with self.subTest(rung=rung, carrier=carrier):
                if carrier == "ledger.EVENT_RULES":
                    # `cascaded` also needs its `policy:` source; either rule firing is the refusal
                    self.assertNotEqual(mod.event_violations(dict(base, evidence=rung)), [],
                                        f"`{rung}` conforms with nothing backing it")
                else:
                    with self.assertRaises(ValueError):
                        mcp_tools._require_quote("", rung)
        self.assertEqual({r for r, (f, _) in owed.items() if f} | {"elicited"},
                         set(mod.DECISION_EVIDENCE))

    def test_only_a_brief_event_may_carry_the_passage(self):
        import ledger as mod
        base = {"id": "ev_0001", "pin_id": "pin_0001", "outcome": "opt_a", "rationale": "r",
                "flip_criteria": "f", "source": "interview"}
        self.assertEqual(mod.event_violations(dict(base, evidence="brief",
                                                   brief_quote="one relational store")), [])
        self.assertIn("brief_quote",
                      mod.event_violations(dict(base, evidence="transcribed",
                                                human_answer="q", brief_quote="a passage")))
        self.assertIn("brief_quote",
                      mod.event_violations(dict(base, evidence="brief", brief_quote="   ")))

    def test_the_door_refuses_a_bare_outcome_and_names_the_shape(self):
        import interview
        led = make_ledger()
        catalog = {"clusters": [{"id": "sync", "order": 1, "kind": "open_decision",
                                 "severity": "medium", "title": "Sync",
                                 "options": [{"id": "reqresp", "label": "request/response"}]}]}
        with self.assertRaises(ValueError) as ctx:
            interview.expand_catalog(led, catalog, brief_decisions={"sync": "reqresp"})
        self.assertIn("quote", str(ctx.exception))
        self.assertEqual(led.data["decision_log"], [])

    #: The rule `_brief_entry` carries, as its own two halves: an entry needs BOTH the outcome and
    #: the passage. Derived from the product rather than listed, so neither half can be deleted
    #: without a failure — which is what happened: the class above asserted only the bare-string
    #: form, so `quote` was covered and `outcome` was covered by nothing. Planted and confirmed —
    #: rewriting the condition to `if not quote:` left the whole suite green.
    HALVES = (("", ""), ("reqresp", ""), ("", "v1 is request/response; no streaming."))

    def _one_cluster(self):
        return {"clusters": [{"id": "sync", "order": 1, "kind": "open_decision",
                              "severity": "medium", "title": "Sync",
                              "options": [{"id": "reqresp", "label": "request/response"}]}]}

    def test_the_door_refuses_a_half_pair_whichever_half_is_missing(self):
        import interview
        for outcome, quote in self.HALVES:
            with self.subTest(outcome=outcome, quote=quote):
                with self.assertRaises(ValueError) as ctx:
                    interview._brief_entry("sync", {"outcome": outcome, "quote": quote})
                self.assertIn("quote", str(ctx.exception))
                self.assertIn("outcome", str(ctx.exception))
        self.assertEqual(interview._brief_entry("sync", {"outcome": "reqresp", "quote": "q"}),
                         {"outcome": "reqresp", "quote": "q"},
                         "the both-present case must pass, or the three refusals above prove "
                         "nothing but that the door refuses everything")

    def test_whitespace_is_not_a_passage_and_not_an_outcome(self):
        """`human_answer`'s rule, at this door: what makes the rung checkable is the passage, and
        whitespace is not one. Both halves, because both are `.strip()`ed by the same line."""
        import interview
        for entry in ({"outcome": "reqresp", "quote": "   "},
                      {"outcome": " \t ", "quote": "v1 is request/response"},
                      {"outcome": None, "quote": None}):
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError):
                    interview._brief_entry("sync", entry)

    def test_the_refusal_reaches_the_caller_through_the_tool_that_takes_the_dict(self):
        """The door-level half. `_brief_entry` runs before anything is created, so a half-pair
        anywhere in the mapping leaves the ledger untouched — no pins, no events."""
        import interview
        for value in ("reqresp", {"outcome": "reqresp"}, {"quote": "v1 is request/response"}):
            with self.subTest(value=value):
                led = make_ledger()
                with self.assertRaises(ValueError):
                    interview.expand_catalog(led, self._one_cluster(),
                                             brief_decisions={"sync": value})
                self.assertEqual(led.data["pins"], [])
                self.assertEqual(led.data["decision_log"], [])

    def test_a_quoted_brief_settles_the_fork_and_the_passage_is_on_the_event(self):
        import interview
        led = make_ledger()
        catalog = {"clusters": [{"id": "sync", "order": 1, "kind": "open_decision",
                                 "severity": "medium", "title": "Sync",
                                 "options": [{"id": "reqresp", "label": "request/response"}]}]}
        out = interview.expand_catalog(led, catalog, brief_decisions={
            "sync": {"outcome": "reqresp", "quote": "v1 is request/response; no streaming."}})
        self.assertEqual(out["pre_decided"], ["sync"])
        event = led.data["decision_log"][-1]
        self.assertEqual((event["evidence"], event["brief_quote"]),
                         ("brief", "v1 is request/response; no streaming."))


class TestThisRuntimeReadsWhatItWrites(unittest.TestCase):
    """v0.27 — the stamp and the accept-list are one fact, and the bump raised one of them.

    `SCHEMA_VERSION` went to `0.27`; `READABLE_VERSIONS` was a literal tuple ending at `0.26`. So
    this runtime wrote a file and then refused to open it: `LedgerError: ledger schema '0.27' is not
    readable by this runtime`, from `Ledger.__init__`, on every second call through
    `_open_existing`/`_open_or_create`. Nothing named the rule — the constructor is the tuple's only
    consumer — and it surfaced only because an unrelated gate's plant happened to reopen a ledger.
    The tuple now ends in `SCHEMA_VERSION`; this asserts the property rather than the spelling.
    """

    def test_the_version_this_runtime_stamps_is_one_it_accepts(self):
        import ledger as mod
        self.assertIn(mod.SCHEMA_VERSION, mod.READABLE_VERSIONS)

    def test_a_ledger_this_runtime_wrote_reopens(self):
        """The behavioural half, and the one that reproduces the failure: write, then open."""
        led = make_ledger()
        add_simple_pin(led)
        led.save()
        reopened = Ledger(led.path)
        self.assertEqual(reopened.data["version"], SCHEMA_VERSION)
        self.assertEqual(len(reopened.readable_pins()), 1)


class TestOneAnswerForHowMuchAForkCollapses(unittest.TestCase):
    """v0.27 — the interview's information gain was computed twice, identically, and wrongly.

    `Ledger.interview_view` held a nested `transitive` and `interview.funnel` a nested
    `transitive_downstream`: same recursion, same `1 + recurse(...)`, same `seen` carried down one
    branch and never across siblings. That counts simple PATHS. On the smallest diamond a roadmap
    makes — `B` and `C` both depend on `A`, `D` on both — `A` reported **4** downstream pins and has
    three. The number is the one the funnel prints beside every question and the key
    `interview_view` sorts on, so the ordering the whole interview rests on drifts with the density
    of the DAG. Two copies is why it survived: every round that looked at one of the two surfaces
    saw a function that agreed with the other.
    """

    #: The functions allowed to call the carrier. Derived membership is asserted against this, so a
    #: third surface that wants a fan-out number has to be added here — and be looked at.
    CALLERS = {"interview_view", "funnel"}

    #: Every OTHER function in the runtime that walks the pin dependency graph, with the question it
    #: answers — because the two are different questions and neither is "how much does this fork
    #: collapse". Both were reported by the derivation below on its first run, which is what the
    #: declaration is for: a walk added tomorrow fails this until somebody writes down what it
    #: computes, and if the answer is *downstream reach* the answer is `downstream_of`.
    OTHER_WALKS = {
        "buildloop.py::depth":
            "UPSTREAM levelling — a pin's own longest dependency chain, for the wave scheduler. "
            "Memoised per pin (`level`) and cycle-detecting by construction, so it is neither a "
            "path count nor unbounded.",
        "challenger.py::_inbound_fanout":
            "the IMMEDIATE dependants, not the transitive ones — the `ignored_fanout` smell is "
            "about how many decisions rest directly on this one, and its threshold is declared.",
    }

    @staticmethod
    def _sources():
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "src"
        return sorted(list((root / "runtime").glob("*.py")) + list((root / "mcp").glob("*.py")))

    @staticmethod
    def _walks_the_edge(tree, ast):
        """Every function that walks the pin dependency graph, by either of the two shapes the
        removed copies had: it re-enters itself while naming `depends_on` (a transitive walk), or
        it tests membership against a `depends_on` value (the INBOUND edge — which is the only way
        to ask who depends on this pin, since the field records the outbound one).

        Iterating a `depends_on` is not on the list: reading a pin's own dependencies is what the
        field is for, and every writer of it does that.
        """
        def is_edge(node) -> bool:
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                return node.slice.value == "depends_on"
            return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and bool(node.args)
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "depends_on")

        out = []
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = any(isinstance(n, ast.Constant) and n.value == "depends_on"
                        for n in ast.walk(fn))
            recurses = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                           and c.func.id == fn.name for c in ast.walk(fn))
            inbound = any(isinstance(n, ast.Compare)
                          and any(isinstance(op, ast.In) for op in n.ops)
                          and any(is_edge(c) for c in n.comparators)
                          for n in ast.walk(fn))
            if (names and recurses) or inbound:
                out.append(fn.name)
        return out

    def test_the_detector_fires_on_the_code_it_was_written_against(self):
        """The non-vacuity half, and it is not optional: the gate below asserts a set this tree
        does not contain, so a detector that matched nothing would pass for ever. This is the
        removed function, verbatim — and it matches on BOTH shapes."""
        import ast
        removed = (
            "def funnel(ledger):\n"
            "    def transitive_downstream(pin_id, seen=frozenset()):\n"
            "        total = 0\n"
            "        for _, r in reads:\n"
            "            if pin_id in r['depends_on'] and r['id'] not in seen:\n"
            "                total += 1 + transitive_downstream(r['id'], seen | {r['id']})\n"
            "        return total\n"
            "    return transitive_downstream\n")
        self.assertEqual(self._walks_the_edge(ast.parse(removed), ast),
                         ["funnel", "transitive_downstream"],
                         "the ENCLOSING function is reported too, and deliberately: both copies "
                         "were nested defs, so a detector that only saw the inner name would be "
                         "silent about which surface carries the walk")

    def test_every_walk_of_the_dependency_graph_is_the_carrier_or_declared(self):
        import ast
        found = {}
        for path in self._sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for name in self._walks_the_edge(tree, ast):
                found[f"{path.name}::{name}"] = True
        self.assertEqual(set(found), set(self.OTHER_WALKS),
                         f"a walk over the pin dependency graph at {sorted(set(found) - set(self.OTHER_WALKS))} "
                         "answers to nothing — `ledger.downstream_of` is the one answer to *how "
                         "much does this fork collapse*, and the last two copies of it agreed with "
                         "each other and disagreed with the graph")
        self.assertNotIn("ledger.py::downstream_of", found,
                         "the carrier is reachability over a reverse index, not a recursion — if "
                         "it matches this detector it has been rewritten into the shape it replaced")

    def test_every_caller_of_the_carrier_is_declared(self):
        import ast
        found = set()
        for path in self._sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                       and c.func.id == "downstream_of" for c in ast.walk(fn)):
                    found.add(fn.name)
        self.assertEqual(found, self.CALLERS,
                         "a surface that reports how much a fork collapses is a surface a human "
                         "sequences their work by — declare it here so it is read, not counted")

    def _diamond(self):
        """A → (B, C) → D. Three pins downstream of A; two simple paths to D."""
        led = make_ledger()
        ids = {}
        for title, deps in (("A", ()), ("B", ("A",)), ("C", ("A",)), ("D", ("B", "C"))):
            pin = add_simple_pin(led, kind="open_decision", title=title, severity="high",
                                 as_is={"givens": [], "built": None},
                                 depends_on=[ids[d] for d in deps])
            ids[title] = pin["id"]
        led.save()
        return led, ids

    def test_a_diamond_is_three_pins_and_not_four_paths(self):
        from ledger import downstream_of, pin_read
        led, ids = self._diamond()
        reads = [pin_read(p) for p in led.readable_pins()]
        self.assertEqual(downstream_of(ids["A"], reads), {ids["B"], ids["C"], ids["D"]})
        self.assertEqual(downstream_of(ids["D"], reads), set())

    def test_both_surfaces_report_the_carriers_answer(self):
        """The callers, quantified: the number the funnel prints and the key the view sorts on are
        the same number, and it is the carrier's."""
        import interview
        from ledger import downstream_of, pin_read
        led, ids = self._diamond()
        reads = [pin_read(p) for p in led.readable_pins()]
        printed = {e["title"]: e["downstream"]
                   for e in interview.funnel(led)["asked"] + interview.funnel(led)["proposed_default"]}
        self.assertEqual(printed, {"A": 3, "B": 1, "C": 1, "D": 0})
        ordered = [pin_read(p)["id"] for p in led.interview_view()]
        self.assertEqual(ordered, sorted(ordered,
                                         key=lambda i: (-len(downstream_of(i, reads)), i)))

    def test_a_cycle_in_a_hand_edited_file_terminates_and_owns_nobody(self):
        """`depends_on` is a list an agent writes and a human can edit, so it can hold a cycle. A
        pin is never downstream of itself: *this fork collapses itself* is not a fact about
        anything, and the old walk counted it."""
        from ledger import downstream_of, pin_read
        led = make_ledger()
        first = add_simple_pin(led, title="A")
        second = add_simple_pin(led, title="B", depends_on=[first["id"]])
        first["depends_on"] = [second["id"]]
        led.save()
        reads = [pin_read(p) for p in led.readable_pins()]
        self.assertEqual(downstream_of(first["id"], reads), {second["id"]})
        self.assertEqual(downstream_of(second["id"], reads), {first["id"]})


if __name__ == "__main__":
    unittest.main()
