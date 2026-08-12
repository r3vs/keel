"""The fog register (ledger v0.31) — `docs/open-gaps.md` §30, and the proof it asked for.

The register named the assertion: *a fixture where resolving one pin makes a fog patch phrasable —
the graduation produces a pin, the patch disappears from the fog, and `ledger_summary` reports it in
neither place twice. Plus the negative: a patch that is still fog after the round is still fog, and
nothing invented a question for it.* That is `TestGraduationIsTheLoadBearingHalf`.

The other three classes hold the three traps, in the register's own words: an agent may not graduate
fog on its own, a patch is not sized like a ticket, and the register must not become a backlog.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools  # noqa: E402
from ledger import (FOG_SHAPES, LEDGER_COLLECTIONS, OPTIONAL_COLLECTIONS,  # noqa: E402
                    SCHEMA_VERSION, Ledger, LedgerError, fog_read, nonconforming)

_QUESTION = {"prompt": "Do trials get their own plan, or a flag on the paid one?",
             "options": [{"id": "plan", "label": "their own plan"},
                         {"id": "flag", "label": "a flag"}],
             "allow_freeform": True}


def _ledger() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


def _sense(led: Ledger, area="billing", sensed="three call sites already special-case trials"):
    return led.add_fog(area=area, sensed=sensed,
                       provenance=[{"source": "interview", "detail": "phase 2"}])


class TestGraduationIsTheLoadBearingHalf(unittest.TestCase):
    """Without the deletion the register is a second home for what already lives on a pin — the
    divergence this package exists to find, built by the feature meant to prevent it."""

    def test_the_patch_becomes_a_pin_and_is_gone_from_the_register(self):
        led = _ledger()
        patch = _sense(led)
        self.assertEqual(led.summary()["fog"], 1)

        pin = led.graduate_fog(patch["id"], question=_QUESTION,
                               human_answer="ask it as plan versus flag")

        self.assertEqual(led.summary()["fog"], 0, "the patch is still in the register")
        self.assertEqual(led.summary()["pins"], 1)
        self.assertEqual(pin["state"], "needs_input")
        self.assertEqual([p["area"] for p in led.fog_view()["patches"]], [])
        with self.assertRaises(LedgerError):
            led.fog(patch["id"])

    def test_the_trail_survives_on_the_pin_that_replaced_it(self):
        """Deleting the patch must not delete the fact that it existed — the pin carries where it
        came from, what was sensed, and the words the human phrased it with."""
        led = _ledger()
        patch = _sense(led)
        pin = led.graduate_fog(patch["id"], question=_QUESTION,
                               human_answer="ask it as plan versus flag")
        source = pin["provenance"][0]
        self.assertEqual(source["source"], "fog_graduation")
        self.assertIn(patch["id"], source["detail"])
        self.assertIn("special-case trials", source["detail"])
        self.assertEqual(source["human_answer"], "ask it as plan versus flag")

    def test_the_negative_a_patch_that_is_still_fog_stays_fog(self):
        """And nothing invented a question for it: there is nowhere on the record to put one."""
        led = _ledger()
        patch = _sense(led)
        led.add_pin(kind="defect", title="unrelated", severity="low", confidence="extracted",
                    provenance=[{"source": "recon", "detail": "x"}])
        self.assertEqual(led.summary()["fog"], 1)
        stored = fog_read(led.fog(patch["id"]))
        self.assertNotIn("question", stored)
        self.assertNotIn("question", FOG_SHAPES,
                         "a fog record with somewhere to put a fork is a pin with a worse schema")

    def test_it_is_reported_in_neither_place_twice(self):
        led = _ledger()
        patch = _sense(led)
        led.graduate_fog(patch["id"], question=_QUESTION, human_answer="plan versus flag")
        summary = led.summary()
        self.assertEqual((summary["fog"], summary["pins"], summary["open_questions"]), (0, 1, 1))


class TestOnlyTheHumanPhrasesIt(unittest.TestCase):
    """Trap 1. Phrasing the question IS framing the decision, and framing is where the answer gets
    smuggled in — so the agent proposes and the human elects, like any other fork."""

    def test_graduating_without_the_words_is_refused(self):
        led = _ledger()
        patch = _sense(led)
        for words in ("", "   ", None):
            with self.subTest(human_answer=words):
                with self.assertRaises(LedgerError):
                    led.graduate_fog(patch["id"], question=_QUESTION, human_answer=words)
        self.assertEqual(led.summary()["fog"], 1, "a refused graduation consumed the patch")

    def test_the_door_asks_the_one_refusal_for_the_quote(self):
        """Over the MCP door, which is the surface an agent actually reaches."""
        path = os.path.join(tempfile.mkdtemp(), "ledger.json")
        fog_id = tools.ledger_add_fog(path, area="billing", sensed="trials are special-cased",
                                      provenance=[{"source": "interview",
                                                   "detail": "phase 2"}])["fog_id"]
        with self.assertRaises(ValueError) as ctx:
            tools.ledger_graduate_fog(path, fog_id, question=_QUESTION, human_answer="")
        self.assertIn("human_answer", str(ctx.exception))

    def test_graduating_with_no_fork_is_not_a_graduation(self):
        led = _ledger()
        patch = _sense(led)
        with self.assertRaises(LedgerError):
            led.graduate_fog(patch["id"], question={}, human_answer="just move it across")


class TestTheOtherExit(unittest.TestCase):
    def test_clearing_deletes_it_and_needs_the_words(self):
        led = _ledger()
        patch = _sense(led)
        with self.assertRaises(LedgerError):
            led.clear_fog(patch["id"], rationale="no trials in v1", human_answer="")
        with self.assertRaises(LedgerError):
            led.clear_fog(patch["id"], rationale="", human_answer="drop it")
        out = led.clear_fog(patch["id"], rationale="trials were cut from v1",
                            human_answer="drop it, no trials in v1")
        self.assertTrue(out["cleared"])
        self.assertEqual(led.summary()["fog"], 0)

    def test_a_patch_must_name_an_area_and_what_was_sensed(self):
        """A patch with neither is a note, and the register is not a notebook."""
        led = _ledger()
        with self.assertRaises(LedgerError):
            led.add_fog(area="", sensed="s", provenance=[{"source": "x", "detail": "y"}])
        with self.assertRaises(LedgerError):
            led.add_fog(area="a", sensed="  ", provenance=[{"source": "x", "detail": "y"}])
        with self.assertRaises(LedgerError):
            led.add_fog(area="a", sensed="s", provenance=[])


class TestTheBacklogTrapIsVisibleRatherThanForbidden(unittest.TestCase):
    """Trap 3. A cap would just move the dishonesty, so the age is reported on the call an agent
    makes before acting."""

    def test_the_age_of_the_oldest_patch_is_what_says_it_became_a_backlog(self):
        led = _ledger()
        _sense(led, area="billing")
        old = _sense(led, area="tenancy")
        old["noticed_at"] = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(
            timespec="seconds")
        view = led.fog_view()
        self.assertEqual(view["count"], 2)
        self.assertEqual(view["oldest_days"], 90)
        self.assertEqual(led.summary()["fog_oldest_days"], 90)

    def test_an_undateable_patch_does_not_take_the_surface_down(self):
        led = _ledger()
        patch = _sense(led)
        patch["noticed_at"] = 17
        self.assertEqual(led.fog_view()["oldest_days"], 0)
        self.assertEqual(led.summary()["fog"], 1)      # must not raise
        self.assertIn("fog_noticed_at", nonconforming(led.data),
                      "a substitution nobody can see is worse than the crash it replaced")


class TestAnOlderFileHasNoRegister(unittest.TestCase):
    """The distinction `OPTIONAL_COLLECTIONS` draws, and why it had to be drawn."""

    def test_absence_is_not_a_nonconformance_but_a_wrong_shape_still_is(self):
        base = {"version": "0.29", "pins": [], "decision_log": [], "policies": []}
        self.assertEqual(nonconforming(base), {},
                         "every ledger written before v0.31 would be permanently nonconforming, "
                         "and its version stamp frozen, on a rule about a collection it could not "
                         "have carried")
        self.assertIn("collection_shape", nonconforming({**base, "fog": "nope"}))
        for required in ("pins", "decision_log", "policies"):
            with self.subTest(collection=required):
                missing = {k: v for k, v in base.items() if k != required}
                self.assertIn("collection_shape", nonconforming(missing),
                              "the three original collections have been in every file since v0.3, "
                              "so an absent one means a broken file")

    def test_an_older_file_can_be_written_to_and_comes_out_current(self):
        path = os.path.join(tempfile.mkdtemp(), "ledger.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"version": "0.29", "pins": [], "decision_log": [], "policies": []}, fh)
        led = Ledger(path)
        _sense(led)
        led.save()
        with open(path, encoding="utf-8") as fh:
            written = json.load(fh)
        self.assertEqual(written["version"], SCHEMA_VERSION)
        self.assertEqual(len(written["fog"]), 1)

    def test_the_optional_set_is_a_subset_of_the_collections(self):
        self.assertTrue(set(OPTIONAL_COLLECTIONS) < set(LEDGER_COLLECTIONS))


if __name__ == "__main__":
    unittest.main()
