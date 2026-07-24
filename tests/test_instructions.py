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
                  "rule": "the DB is the canonical layer", "default_outcome": "canonicalize on db",
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
