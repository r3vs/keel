"""Tests for runtime/instructions.py — the ledger → AGENTS.md carrier.

Offline/stdlib. Pins the properties the design rests on: the region is a stable projection (an
unchanged ledger round-trips to zero drift, like generate.py's layers), everything OUTSIDE the
markers survives byte for byte, a hand-edited region is distinguished from a merely stale one (the
whole reason the marker carries a fingerprint), truncation is always declared, and the Claude Code
bridge is idempotent and parseable by Claude Code's own import rules.
"""
from __future__ import annotations

import os
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
        # open pins are listed as NOT decided, and carry no outcome
        self.assertIn("### NOT decided — do not encode an answer", body)
        self.assertIn("`p_0001`", body)
        # blocker sorts above medium within its section
        self.assertLess(body.index("`p_0001`"), body.index("`p_0004`"))

    def test_open_pin_never_shown_as_elected(self):
        """The anti-slop property: an undecided fork must not read as settled."""
        body = ins.render(LEDGER)
        elected = body.split("### NOT decided")[0]
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


if __name__ == "__main__":
    unittest.main()
