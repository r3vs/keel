"""Tests for runtime/instructions.py — the ledger → AGENTS.md carrier.

Offline/stdlib. Pins the properties the design rests on: the region is a stable projection (an
unchanged ledger round-trips to zero drift, like generate.py's layers), everything OUTSIDE the
markers survives byte for byte, a hand-edited region is distinguished from a merely stale one (the
whole reason the marker carries a fingerprint), truncation is always declared, and the Claude Code
bridge is idempotent and parseable by Claude Code's own import rules.
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import instructions as ins  # noqa: E402


def _pin(pid, kind, title, state, severity="medium", outcome=None):
    p = {"id": pid, "kind": kind, "title": title, "state": state, "severity": severity}
    if outcome:
        p["decision"] = {"event_id": "ev_0001", "outcome": outcome}
    return p


LEDGER = {
    "version": "0.6",
    "pins": [
        _pin("p_0002", "contract_mismatch", "role enum disagrees DB vs API", "decided",
             "high", "canonicalize on the DB enum"),
        _pin("p_0001", "open_decision", "persistence: Postgres or SQLite", "needs_input", "blocker"),
        _pin("p_0003", "design_concern", "auth helper duplicated", "accepted", "low", "keep"),
        _pin("p_0004", "defect", "off-by-one in pagination", "detected", "medium"),
    ],
    "decision_log": [],
    "policies": [{"id": "pol_0001", "applies_to": {"kind": "contract_mismatch"},
                  # v0.12: an option id, since that is the only thing a cascade may write
                  "rule": "the DB is the canonical layer", "default_outcome": "db",
                  # v0.15: a properly elected rule, so the evidence note in the tests below stays
                  # about the decisions they are each written to check
                  "evidence": "transcribed", "human_answer": "the DB wins unless I flag one",
                  "set_by": "interview", "exceptions": []}],
}


class TestRender(unittest.TestCase):
    def test_sections_and_ordering(self):
        body = ins.render(LEDGER)
        self.assertIn("### Standing rules", body)
        self.assertIn("the DB is the canonical layer", body)
        # elected = decided + accepted, each carrying its outcome
        self.assertIn("`p_0002`", body)
        self.assertIn("**canonicalize on the DB enum**", body)
        self.assertIn("`p_0003`", body)
        # open pins are listed as open
        self.assertIn("### Open — not settled; do not decide one yourself", body)
        self.assertIn("`p_0001`", body)
        # blocker sorts above medium within its section
        self.assertLess(body.index("`p_0001`"), body.index("`p_0004`"))

    def test_open_pin_never_shown_as_elected(self):
        """The anti-slop property: an undecided fork must not read as settled."""
        body = ins.render(LEDGER)
        elected = body.split("### Open —")[0]
        self.assertNotIn("`p_0001`", elected)

    def test_empty_ledger_says_so(self):
        body = ins.render({"pins": [], "policies": []})
        self.assertIn("No decisions elected yet", body)

    def test_generated_files_are_passed_in_not_invented(self):
        body = ins.render(LEDGER, generated=["src/types.ts", "db/001_initial.sql"])
        self.assertIn("### Generated — never hand-edit", body)
        self.assertIn("`src/types.ts`", body)

    def test_truncation_is_declared_and_budget_holds(self):
        many = {"pins": [_pin(f"p_{i:04d}", "defect", f"bug {i}", "decided", "low", "fix")
                         for i in range(200)], "policies": []}
        body = ins.render(many, max_lines=30)
        self.assertLessEqual(len(body.splitlines()), 30)
        self.assertRegex(body, r"\(\+\d+ more")

    def test_an_unhonourable_budget_is_refused_not_silently_overrun(self):
        """A cap that reports success while exceeding itself is the failure the cap exists to
        prevent — so a budget below the header is a ValueError, not a best effort."""
        for n in (0, 5, ins._MIN_LINES - 1):
            with self.subTest(max_lines=n):
                with self.assertRaises(ValueError):
                    ins.render(LEDGER, max_lines=n)
        self.assertLessEqual(len(ins.render(LEDGER, max_lines=ins._MIN_LINES).splitlines()),
                             ins._MIN_LINES)

    def test_render_is_stable(self):
        self.assertEqual(ins.render(LEDGER), ins.render(LEDGER))


class TestEveryStateReachesTheRegion(unittest.TestCase):
    """The projection kept its OWN pair of state lists — six of the schema's eight — so a `deferred`
    pin and a `correctness_unknown` pin reached a fresh agent's always-on context in NO section.

    Same bug `map.py` carried until its `SETTLED` set was sourced from `ledger.SETTLED_STATES`, one
    surface over, and the same fix: a set the schema owns cannot be kept here, because a state added
    there does not come here. So these assert the partition at the schema, and the behaviour at the
    projection — a private list re-added later fails the second even if it satisfies the first.
    """

    def test_the_two_sets_partition_the_schema(self):
        from ledger import OPEN_STATES, SETTLED_STATES, STATES
        self.assertEqual(set(SETTLED_STATES) & set(OPEN_STATES), set(),
                         "a state in both buckets would be listed twice, saying two things")
        self.assertEqual(sorted(set(SETTLED_STATES) | set(OPEN_STATES)), sorted(STATES),
                         "a state in neither bucket reaches the agent in no section at all — "
                         "which is exactly how `deferred` and `correctness_unknown` went missing")

    def test_a_pin_in_every_state_is_listed(self):
        from ledger import STATES
        data = {"pins": [_pin(f"p_{i:04d}", "defect", f"pin in {s}", s) for i, s in
                         enumerate(STATES)], "policies": [], "decision_log": []}
        body = ins.render(data, max_lines=200)
        missing = [p["id"] for p in data["pins"] if p["id"] not in body]
        self.assertEqual(missing, [], f"listed in no section: {missing}")

    def test_the_two_states_that_went_missing(self):
        """The reproduction, verbatim: two blockers, and the region said no decisions existed."""
        data = {"pins": [
            _pin("p_0001", "open_decision", "Multi-tenant isolation is unimplemented", "deferred",
                 "blocker", outcome="defer"),
            _pin("p_0002", "defect", "Webhook replay", "correctness_unknown", "blocker"),
        ], "policies": [], "decision_log": []}
        body = ins.render(data)
        self.assertNotIn("No decisions elected yet", body)
        self.assertIn("Multi-tenant isolation is unimplemented", body)
        self.assertIn("Webhook replay", body)
        # and on the right side of the divide: deferring is an election, correctness_unknown is not
        settled, openp = body.split("### Open —")
        self.assertIn("`p_0001`", settled)
        self.assertIn("`p_0002`", openp)


class TestArrivingInASectionThatInvertsTheMeaning(unittest.TestCase):
    """Landing the two rescued states somewhere was not the fix finished — the section a pin lands
    in is an instruction, and for these two it was the wrong one.

    Both reproduced against the shipped renderer before the fix, and both are about the ONE thing
    this file is: bytes an agent reads before it writes anything.
    """

    def test_a_leave_as_is_pin_does_not_clip_the_decisions_that_say_what_to_build(self):
        """Six do-not-build blockers + six decided mediums at `max_lines=22`: severity-then-id put
        all six FIRST and clipped two elected decisions to `(+2 more)`, in the file an agent reads
        before writing anything.

        Three of the six are `accepted` and three `deferred`, because the first fix at this line
        named only `deferred` and an `accepted` blocker went on outranking an elected medium under
        exactly the same clip. What survives the budget is now decided by which SECTION a pin is in,
        not by a boolean in a sort key."""
        pins = [_pin(f"p_{i:04d}", "design_concern", f"left as it is {i}", "accepted",
                     "blocker", outcome="keep") for i in range(3)]
        pins += [_pin(f"p_{i:04d}", "incompleteness", f"deferred blocker {i}", "deferred",
                      "blocker", outcome="defer") for i in range(3, 6)]
        pins += [_pin(f"p_{i:04d}", "open_decision", f"elected medium {i}", "decided",
                      "medium", outcome=f"choice_{i}") for i in range(6, 12)]
        log = [{"id": f"ev_{i:04d}", "pin_id": p["id"], "evidence": "transcribed",
                "human_answer": "yes"} for i, p in enumerate(pins)]
        # `+ _NONCONF_LINES`: this fixture's events carry no `flip_criteria`, so from v0.25 the
        # header also says the file holds something the schema does not describe. Written as the
        # constant rather than as 24, because the budget arithmetic is what the assertion below is
        # about — a literal here would silently change what "clips" means the next time a
        # conditional line is added.
        body = ins.render({"pins": pins, "decision_log": log, "policies": []},
                          max_lines=22 + ins._NONCONF_LINES)
        self.assertRegex(body, r"\(\+4 more")               # the budget clips, and says so
        clipped = [p["id"] for p in pins if f"`{p['id']}`" not in body]
        elected = {p["id"] for p in pins if p["state"] == "decided"}
        self.assertEqual(elected & set(clipped), set(),
                         f"an elected decision was clipped while a do-not-build pin survived: "
                         f"{clipped}")
        lines = [ln for ln in body.splitlines() if ln.startswith("- `p_")]
        last_elected = max(i for i, ln in enumerate(lines) if "**choice_" in ln)
        first_leave = min((i for i, ln in enumerate(lines)
                           if "**defer**" in ln or "**keep**" in ln), default=len(lines))
        self.assertLess(last_elected, first_leave,
                        "the do-not-build section must come after the one that says what to build, "
                        "so the budget reaches it last")

    def test_each_settled_heading_is_true_of_every_pin_under_it(self):
        """A `deferred` pin listed under a bare *build on these* reads as the opposite of itself,
        and so does an `accepted` one — which the first version of this heading did not say, because
        it named `defer` and stopped. The states are read out of `ledger.LEAVE_AS_IS_STATES`, so the
        heading cannot fall behind the set it describes."""
        from ledger import LEAVE_AS_IS_STATES
        pins = [_pin("p_0001", "open_decision", "multi-tenant isolation", "deferred", "blocker",
                     outcome="defer"),
                _pin("p_0002", "design_concern", "duplicated parser", "accepted", "high",
                     outcome="keep"),
                _pin("p_0003", "open_decision", "persistence", "decided", "high", outcome="pg")]
        body = ins.render({"pins": pins, "decision_log": [], "policies": []}, max_lines=200)
        build_on, leave = body.split("### Settled — elected NOT to be built")
        self.assertIn("`p_0003`", build_on)
        for state in LEAVE_AS_IS_STATES:
            self.assertIn(f"`{state}`", leave.splitlines()[0],
                          f"the heading does not name {state}, so a pin in it reads as buildable")
        self.assertIn("`p_0001`", leave)
        self.assertIn("`p_0002`", leave)
        self.assertNotIn("`p_0002`", build_on)

    def test_an_outcome_under_dispute_is_not_printed_as_a_build_instruction(self):
        """A pin reopened by the feedback arc, by an upheld challenge or by a cross-derivation
        disagreement still carries the outcome it was elected with. Printing it bare formats a
        contradicted answer exactly like an elected one — and the heading above forbids *deciding*,
        not *building on*. Every substate the schema names is walked, not the one that was found."""
        from ledger import REOPENED_SUBSTATES
        for substate in REOPENED_SUBSTATES:
            with self.subTest(substate=substate):
                pin = _pin("p_0001", "ambiguity", "outbox flush order", "needs_input", "high",
                           outcome="after")
                pin["substate"] = substate
                body = ins.render({"pins": [pin], "decision_log": [], "policies": []})
                line = [ln for ln in body.splitlines() if ln.startswith("- `p_0001`")][0]
                self.assertIn("**after**", line)
                self.assertIn(substate, line, "the outcome is printed with no sign it is disputed")
                self.assertIn("do not build on this answer", line)

    def test_an_undisputed_outcome_pays_nothing_for_that_clause(self):
        """The mark is bought on the pins that carry the substate and on no others — which is what
        separates it from the per-pin state token this file refuses on byte grounds."""
        pin = _pin("p_0001", "open_decision", "persistence", "decided", "high", outcome="pg")
        line = [ln for ln in ins.render({"pins": [pin], "decision_log": [], "policies": []})
                .splitlines() if ln.startswith("- `p_0001`")][0]
        self.assertTrue(line.endswith("**pg**"), line)


class TestTheProjectionIsNotWhereAProjectionShouldDie(unittest.TestCase):
    """v0.23 — this module writes the one file every host loads unprompted, and five ordinary
    malformations took it down over real stdio against the shipped server:

        severity is a list          -> unhashable type: 'list'          (used as a dict key)
        title is not a string       -> 'dict' object has no attribute 'strip'
        decision is a string        -> 'str' object has no attribute 'get'
        a policy scope is a string  -> 'str' object has no attribute 'items'
        a policy rule is a list     -> 'list' object has no attribute 'strip'

    Every one of them is a field the reading surfaces index, on a file `ledger_summary` reads and
    reports the nonconformance of. `render` never dies here now, and the fields come through
    `pin_read` / `policy_read` so the substitutions are the schema's rather than this module's."""

    BROKEN = {
        "severity is a list": {"pins": [{"id": "pin_0001", "kind": "defect", "state": "decided",
                                         "title": "t", "severity": ["high"]}]},
        "title is not a string": {"pins": [{"id": "pin_0001", "kind": "defect", "state": "decided",
                                            "title": {"text": "nope"}, "severity": "high"}]},
        "decision is a string": {"pins": [{"id": "pin_0001", "kind": "defect", "state": "decided",
                                           "title": "t", "severity": "high",
                                           "decision": "ev_0001"}]},
        "a policy scope is a string": {"policies": [{"id": "pol_0001", "rule": "prefer X",
                                                     "applies_to": "everything",
                                                     "default_outcome": "opt_a"}]},
        "a policy rule is a list": {"policies": [{"id": "pol_0001", "rule": ["prefer", "X"],
                                                  "applies_to": {},
                                                  "default_outcome": "opt_a"}]},
        "a pin is null": {"pins": [None]},
        "pins is not a list": {"pins": "everything is fine"},
        "policies is not a list": {"policies": None},
    }

    def test_render_answers_on_every_shape_instead_of_raising(self):
        for name, data in self.BROKEN.items():
            with self.subTest(shape=name):
                ins.render(dict({"version": "0.23", "pins": [], "decision_log": [],
                                 "policies": []}, **data))

    def test_a_severity_the_file_states_outranks_one_it_does_not(self):
        """The finding itself. `_SEVERITY_RANK` read a MISSING severity as `low`, so `pin_0001` —
        whose file says nothing about how bad it is — led the section, ahead of a pin that states
        `low` and of one that states a severity outside the set. Reproduced over stdio; this is the
        order the region carries now, and it is `ledger.severity_rank`'s."""
        data = {"version": "0.23", "decision_log": [], "policies": [], "pins": [
            {"id": "pin_0001", "kind": "defect", "title": "no severity stated at all",
             "state": "decided", "decision": {"event_id": "ev_0001", "outcome": "fix"}},
            {"id": "pin_0002", "kind": "defect", "title": "a severity outside the set",
             "severity": "catastrophic", "state": "decided",
             "decision": {"event_id": "ev_0002", "outcome": "fix"}},
            {"id": "pin_0003", "kind": "defect", "title": "a stated low", "severity": "low",
             "state": "decided", "decision": {"event_id": "ev_0003", "outcome": "fix"}},
        ]}
        listed = [ln.split("`")[1] for ln in ins.render(data).splitlines()
                  if ln.startswith("- `pin_")]
        self.assertEqual(listed, ["pin_0003", "pin_0001", "pin_0002"],
                         "a pin whose file states no severity is ahead of one that states a "
                         "severity — the projection is reading a claim the file does not make")


class TestNoStateNameIsKeptInThisFile(unittest.TestCase):
    """`TestEveryStateReachesTheRegion` states the rule — *a set the schema owns cannot be kept
    here, because a state added there does not come here* — and this module went on comparing
    `pin.get("state") == "deferred"` inside `_settled_order`, which is the same rule broken by one
    literal. No gate forbade it, so a fifth settled state with leave-as-is semantics would have
    silently inherited today's placement.

    Asserted over the AST rather than over the text, and with docstrings excluded, because the
    words are legitimately in the prose of this file — what must not exist is a state name used as a
    VALUE. The honest limit: a state name assembled at runtime (`"defer" + "red"`) would not be
    seen. That is not a limit worth closing; it is a limit worth stating."""

    @staticmethod
    def _docstring_nodes(tree) -> set:
        out = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                first = node.body[0] if node.body else None
                if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    out.add(id(first.value))
        return out

    def test_no_schema_state_is_written_as_a_literal(self):
        from ledger import STATES
        tree = ast.parse(pathlib.Path(ins.__file__).read_text(encoding="utf-8"))
        docstrings = self._docstring_nodes(tree)
        found = [node.value for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)
                 and id(node) not in docstrings and node.value in STATES]
        self.assertEqual(found, [], f"a state name is a value in this module: {found}. The sets are "
                                    "the schema's — read them, do not name their members.")

    def test_the_guard_sees_a_planted_one(self):
        """Non-vacuous by construction: the same walk over a module that DOES name a state finds it,
        so a green run above means the names are gone rather than that the walk is looking wrong."""
        from ledger import STATES
        tree = ast.parse('def f(p):\n    """docstring naming deferred"""\n'
                         '    return p["state"] == "deferred"\n')
        docstrings = self._docstring_nodes(tree)
        found = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and id(n) not in docstrings and n.value in STATES]
        self.assertEqual(found, ["deferred"])

    def test_a_correctness_unknown_pin_does_not_reach_the_agent_as_an_unanswered_question(self):
        """The state means *elected, and we could not establish that it worked*. Its outcome was
        suppressed because the pin is in `OPEN_STATES`, so a decision the human made arrived as a
        fork — and an agent may answer it again."""
        pin = _pin("p_0001", "open_decision", "idempotency key source", "correctness_unknown",
                   "high", outcome="request_id")
        body = ins.render({"pins": [pin], "decision_log": [], "policies": []})
        openp = body.split("### Open —")[1]
        self.assertIn("**request_id**", openp,
                      "the elected outcome must be visible where the pin is listed")
        self.assertIn("do not decide one yourself", body.split("### Open —")[1].splitlines()[0],
                      "and the heading must still forbid deciding it")

    def test_a_pin_with_no_decision_still_prints_no_outcome(self):
        """The rule is one rule, not a per-section flag: nothing to say costs nothing."""
        body = ins.render({"pins": [_pin("p_0001", "ambiguity", "which cache", "needs_input")],
                           "decision_log": [], "policies": []})
        self.assertIn("- `p_0001` [ambiguity] which cache\n", body)


class TestEvidenceNote(unittest.TestCase):
    """v0.10: the region is byte-budgeted, so `evidence` gets one conditional header line — and the
    condition is what makes it affordable. It must appear when some decision rests on a relay,
    disappear when none does, and never eat a section's room."""

    @staticmethod
    def _with(log):
        return {**LEDGER, "decision_log": log}

    def test_absent_when_every_decision_was_elicited(self):
        body = ins.render(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "elicited"},
            {"id": "ev_0002", "pin_id": "p_0003", "evidence": "brief"}]))
        self.assertNotIn("transcribed", body)

    def test_present_and_counted_when_a_decision_was_relayed(self):
        body = ins.render(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "transcribed",
             "human_answer": "the DB is truth"},
            {"id": "ev_0002", "pin_id": "p_0003", "evidence": "elicited"}]))
        self.assertIn("of 2 recorded decisions, 1 relayed by an agent", body)

    def test_a_cascade_is_reported_as_a_cascade(self):
        """v0.11. The clauses are kept apart because they fail differently: a relay may be an
        invention, a cascade may simply not fit this pin. Summing them into "N weak" would put the
        user's own elected policy in the same sentence as an agent's unquoted say-so — and reading a
        missing rung as `transcribed`, which this used to do, said it outright."""
        body = ins.render(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "cascaded", "policy_id": "pol_0001"},
            {"id": "ev_0002", "pin_id": "p_0003", "evidence": "elicited"}]))
        self.assertIn("1 cascaded from a policy the user elected once", body)
        self.assertNotIn("relayed by an agent", body)

    def test_a_cascade_written_before_the_rung_existed_is_still_not_a_relay(self):
        """v0.13, and the reason the clause above was not enough: the rung binds the WRITE, so every
        ledger written before v0.11 carries `transcribed` on its cascades — `decide()`'s old
        parameter default — and this line, reading the field literally, told the user in their own
        `AGENTS.md` that an agent had relayed a decision their elected policy made."""
        body = ins.render(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "source": "policy:pol_0001",
             "evidence": "transcribed"},
            {"id": "ev_0002", "pin_id": "p_0003", "evidence": "elicited"}]))
        self.assertIn("1 cascaded from a policy the user elected once", body)
        self.assertNotIn("relayed by an agent", body)

    def test_an_unrecorded_rung_is_not_reported_as_a_relay(self):
        body = ins.render(self._with([{"id": "ev_0001", "pin_id": "p_0002"}]))
        self.assertIn("1 with no rung recorded at all", body)
        self.assertNotIn("relayed by an agent", body)

    def test_a_rung_this_projection_does_not_know_is_counted_as_that(self):
        """It used to fall through all three clauses and be reported as nothing — while the map
        badged it weak. Unrecorded is not the same as unrecognised: one says nobody wrote how the
        answer travelled, the other says the file did and this projection cannot read the road."""
        body = ins.render(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "oracle"},
            {"id": "ev_0002", "pin_id": "p_0003", "evidence": "elicited"}]))
        self.assertIn("1 on a rung this projection does not know", body)
        self.assertNotIn("with no rung recorded at all", body)

    def test_only_decision_events_are_counted(self):
        """`decision_log` also holds challenges, reopens and failures. Counting those would report a
        rung for events that never carried a human's answer at all."""
        body = ins.render(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "transcribed", "human_answer": "x"},
            {"id": "chl_0001", "pin_id": "p_0002", "class": "unfalsifiable"},
            {"id": "fal_0001", "pin_id": "p_0002", "class": "environment"}]))
        self.assertIn("of 1 recorded decisions", body)

    def test_the_declared_note_length_is_the_length_it_emits(self):
        """`_NOTE_LINES` is budget arithmetic, so it must be measured off the note, not asserted
        about it: if the note grows a line and the floor does not, a tight budget starts overrunning
        itself — which is the one failure the budget exists to prevent."""
        note = ins._evidence_note(self._with([
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "transcribed", "human_answer": "x"}]))
        self.assertEqual(len(note), ins._NOTE_LINES)

    def test_the_declared_nonconformance_note_length_is_the_length_it_emits(self):
        """`_NONCONF_LINES` is budget arithmetic and is measured off the note, for the reason the
        assertion above gives — and because the first draft of this note was NOT counted and
        displaced `### Standing rules` at the floor, which is the one section this budget promises
        survives."""
        note = ins._nonconformance_note({"pins": ["a bare string where a pin goes"],
                                         "decision_log": [], "policies": []})
        self.assertEqual(len(note), ins._NONCONF_LINES)
        self.assertEqual(ins._nonconformance_note(
            {"pins": [], "decision_log": [], "policies": []}), [],
            "the note costs bytes on a conforming file")

    def test_the_note_never_costs_a_section_its_room(self):
        noted = self._with([{"id": "ev_0001", "pin_id": "p_0002", "evidence": "transcribed",
                             "human_answer": "x"}])
        floor = ins.render(noted, max_lines=ins._MIN_LINES)
        self.assertLessEqual(len(floor.splitlines()), ins._MIN_LINES)
        self.assertIn("relayed by an agent", floor)
        # at the floor exactly one section survives, and it is still the rules an agent must obey —
        # the note is budgeted for, so it displaces nothing that fitted before it existed
        self.assertIn("### Standing rules", floor)
        # at the default budget the note is additive: every section it shares the region with stays
        self.assertIn("`p_0002`", ins.render(noted))


class TestTheStandingRulesAreWeighedToo(unittest.TestCase):
    """v0.15. This region already LISTED the policies; what it never said is how the human elected
    them — while saying exactly that about every decision. A `Policy` decides a whole cluster and is
    what each `cascaded` line above derives from, so weighing the cascade and not the election
    behind it weighs the wrong end. It is also the only clause here that can fire with an empty
    `decision_log`: a rule that cascaded over no pin still governs what gets written next."""

    @staticmethod
    def _with(policy):
        return {**LEDGER, "decision_log": [], "policies": [policy]}

    BASE = {"id": "pol_0001", "applies_to": {"kind": "contract_mismatch"},
            "rule": "the DB is the canonical layer", "default_outcome": "db", "exceptions": []}

    def test_an_elected_rule_that_decided_nothing_is_still_weighed(self):
        body = ins.render(self._with(dict(self.BASE)))          # no rung recorded at all
        self.assertIn("1 of the standing rules below was elected with no rung recorded", body)
        self.assertIn("the DB is the canonical layer", body)

    def test_an_unquoted_relay_of_a_whole_cluster_says_so(self):
        body = ins.render(self._with(dict(self.BASE, evidence="transcribed")))
        self.assertIn("relayed with no quote", body)

    def test_a_properly_elected_rule_costs_nothing(self):
        body = ins.render(self._with(dict(self.BASE, evidence="transcribed",
                                          human_answer="the DB wins unless I flag one")))
        self.assertNotIn("standing rules below was elected", body)
        body = ins.render(self._with(dict(self.BASE, evidence="elicited")))
        self.assertNotIn("standing rules below was elected", body)

    def test_the_count_is_the_ledgers_and_not_this_modules(self):
        """The map badged two standing rules on the preview fixture and this line said one, because
        each surface had its own rule for "weak". `ledger.policy_weakness` is the single answer now;
        what stays here is the wording, and every code it can return must have some."""
        from ledger import POLICY_WEAKNESS
        self.assertEqual(set(ins._POLICY_WEAKNESS_CLAUSE), set(POLICY_WEAKNESS),
                         "a weakness code with no clause here surfaces as a bare token")

    def test_a_rung_the_schema_does_not_name_is_reported_as_its_own_thing(self):
        body = ins.render(self._with(dict(self.BASE, evidence="oracle")))
        self.assertIn("elected on a rung this projection does not know", body)
        self.assertNotIn("with no rung recorded", body)

    def test_the_note_is_still_one_line_with_both_halves(self):
        """`_NOTE_LINES` is budget arithmetic: a second sentence must not become a second line."""
        note = ins._evidence_note({**LEDGER, "policies": [dict(self.BASE)], "decision_log": [
            {"id": "ev_0001", "pin_id": "p_0002", "evidence": "transcribed"}]})
        self.assertEqual(len(note), ins._NOTE_LINES)
        self.assertIn("relayed by an agent", note[1])
        self.assertIn("standing rules below", note[1])


class TestRegion(unittest.TestCase):
    def test_apply_into_empty_creates_file_body(self):
        out = ins.apply(None, ins.render(LEDGER))
        self.assertTrue(out.startswith("# AGENTS.md"))
        self.assertIn(ins.END, out)

    def test_user_prose_survives_byte_for_byte(self):
        original = "# My project\n\nRun `make dev`.\n\n## Notes\n\nDon't touch vendor/.\n"
        once = ins.apply(original, ins.render(LEDGER))
        self.assertIn("Run `make dev`.", once)
        self.assertIn("Don't touch vendor/.", once)
        # a second generation replaces only the region — prose still intact, region not duplicated
        twice = ins.apply(once, ins.render(LEDGER, generated=["a.ts"]))
        self.assertEqual(twice.count(ins.END), 1)
        self.assertIn("`a.ts`", twice)
        # first insertion appends after a single separating blank line; every later regeneration
        # leaves everything outside the markers identical — that is the byte-for-byte guarantee.
        self.assertEqual(once.split("<!-- keel:begin")[0], original + "\n")
        self.assertEqual(twice.split("<!-- keel:begin")[0], once.split("<!-- keel:begin")[0])

    def test_prose_after_the_region_survives_too(self):
        text = ins.apply("# P\n\nbefore\n", ins.render(LEDGER)) + "\nafter the region\n"
        out = ins.apply(text, ins.render(LEDGER, generated=["x.py"]))
        self.assertIn("before", out)
        self.assertIn("after the region", out)
        self.assertEqual(out.count(ins.END), 1)


class TestDriftCheck(unittest.TestCase):
    def test_roundtrip_is_in_sync(self):
        body = ins.render(LEDGER)
        self.assertEqual(ins.drift_check(ins.apply(None, body), body)["status"], "in_sync")

    def test_absent(self):
        self.assertEqual(ins.drift_check("# just prose\n", ins.render(LEDGER))["status"], "absent")
        self.assertEqual(ins.drift_check(None, ins.render(LEDGER))["status"], "absent")

    def test_stale_when_the_ledger_moves(self):
        text = ins.apply(None, ins.render(LEDGER))
        moved = {**LEDGER, "pins": LEDGER["pins"] + [
            _pin("p_0009", "acceptance_criterion", "checkout works", "decided", "high", "ship it")]}
        out = ins.drift_check(text, ins.render(moved))
        self.assertEqual(out["status"], "stale")

    def test_hand_edited_is_distinguished_from_stale(self):
        """The fingerprint's whole job: a human writing INTO the projection is a different failure
        from the ledger moving, and must not be silently overwritten."""
        body = ins.render(LEDGER)
        text = ins.apply(None, body).replace("`p_0002`", "`p_0002` (actually we chose the API enum)")
        out = ins.drift_check(text, body)
        self.assertEqual(out["status"], "hand_edited")
        self.assertIn("ledger", out["detail"])


class TestGeneratedListSurvivesRegeneration(unittest.TestCase):
    """The region records its own generated-file list, so a regeneration triggered by something else
    cannot silently drop it. Without this, `AGENTS.md` loses the never-hand-edit section while the
    Claude-only rule keeps asserting it — two carriers of one fact, disagreeing."""

    def test_recovered_from_an_existing_region(self):
        text = ins.apply(None, ins.render(LEDGER, generated=["src/types.ts", "db/001.sql"]))
        self.assertEqual(ins.extract_generated(text), ["db/001.sql", "src/types.ts"])

    def test_nothing_to_recover_is_empty_not_an_error(self):
        self.assertEqual(ins.extract_generated(None), [])
        self.assertEqual(ins.extract_generated("# just prose\n"), [])
        self.assertEqual(ins.extract_generated(ins.apply(None, ins.render(LEDGER))), [])

    def test_only_the_generated_section_is_harvested(self):
        """Pin lines are also backticked bullets — a looser reader would harvest pin ids as paths."""
        text = ins.apply(None, ins.render(LEDGER, generated=["a.ts"]))
        self.assertEqual(ins.extract_generated(text), ["a.ts"])


class TestClaudeBridge(unittest.TestCase):
    def test_creates_a_parseable_import(self):
        out = ins.claude_bridge(None)
        self.assertTrue(out.startswith("@AGENTS.md"))
        # Claude Code skips imports inside code spans / fences — ours must be outside both.
        first = out.splitlines()[0]
        self.assertNotIn("`", first)

    def test_idempotent(self):
        first = ins.claude_bridge(None)
        self.assertIsNone(ins.claude_bridge(first))

    def test_prepends_to_an_existing_file(self):
        out = ins.claude_bridge("# Project rules\n\nUse pnpm.\n")
        self.assertTrue(out.startswith("@AGENTS.md"))
        self.assertIn("Use pnpm.", out)

    def test_a_backticked_mention_does_not_count_as_an_import(self):
        """The exact bug this repo shipped in its own docs: `@AGENTS.md` in backticks imports nothing."""
        self.assertIsNotNone(ins.claude_bridge("See `@AGENTS.md` for details.\n"))


class TestPathScopedRule(unittest.TestCase):
    def test_frontmatter_lists_the_written_paths(self):
        out = ins.rule_generated_files(["src/types.ts", "db/001_initial.sql"],
                                       "contract.json", "generate_layers")
        self.assertTrue(out.startswith("---\npaths:\n"))
        self.assertIn('  - "src/types.ts"', out)
        self.assertIn("contract.json", out)

    def test_no_paths_is_still_valid_frontmatter(self):
        self.assertIn("paths: []", ins.rule_generated_files([], "c.json", "generate_layers"))


class TestWorkThatFailedInProductionSaysSoHere(unittest.TestCase):
    """`ledger_label_failure` deliberately reaches finished work — labelling an incident on a
    `resolved` pin is the move that PRECEDES a reopen, which is why the closed-work gate lets it
    through. The map's trail card showed the event and `learning_report` counted it; this region
    listed the pin under *"Settled — build on these"* with nothing said, so the one file every host
    loads unprompted told a fresh agent to build on work that had already failed in front of users.

    Scoped to the `production` phase on purpose: a failure at `plan`/`build`/`evidence`/`review` is
    the loop working, and marking those would spend bytes on the ordinary case — the bargain every
    clause in this region is under.
    """

    def _data(self, *events):
        return {"pins": [_pin("pin_0001", "defect", "Refunds double-counted", "resolved",
                              severity="blocker", outcome="fix")],
                "decision_log": list(events)}

    def _line(self, data):
        for line in ins.render(data).splitlines():
            if "Refunds" in line:
                return line
        return ""

    @staticmethod
    def _failure(phase):
        return {"id": "fal_0001", "pin_id": "pin_0001", "class": "untested_path",
                "detail": "a retry credited twice", "phase": phase, "source": "feedback:incident"}

    def test_a_production_failure_is_marked_on_the_line(self):
        self.assertIn("failed in production — untested_path",
                      self._line(self._data(self._failure("production"))))

    def test_an_earlier_phase_costs_no_bytes(self):
        self.assertNotIn("failed in production", self._line(self._data(self._failure("review"))),
                         "a failure caught before release is the loop working, not a warning")

    def test_the_pin_with_no_failure_reads_exactly_as_before(self):
        self.assertNotIn("failed in production", self._line(self._data()))


if __name__ == "__main__":
    unittest.main()
