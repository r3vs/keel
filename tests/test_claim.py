"""The claim (ledger v0.30) — `docs/open-gaps.md` §29, and the proof it asked for.

The assertion that matters is **not** a unit test of the setter. It is two sessions: open the same
`ledger.json` twice, have both take the same pin, and observe exactly one success and one refusal
naming the holder. That is `TestTwoSessionsCannotBothTakeIt`, and it is the whole reason `claim`
compares against the FILE rather than against its own in-memory copy — a check against the copy
answers *did I claim this*, which is true of nobody else and therefore always passes.

Everything else here holds one of the four traps the register recorded, in the register's own words:
the claim is not a state, it does not reuse `depends_on`/`conflicts_with`, it does not gate a write,
and it expires so a dead session parks nothing.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledger import (CLAIM_CARRIERS, CLAIM_STATES, CLAIM_TTL_SECONDS, Ledger,  # noqa: E402
                    LedgerError, claim_state, pin_read)
from test_ledger import add_simple_pin  # noqa: E402


def _ledger() -> Ledger:
    return Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))


def _stale() -> datetime:
    """A moment far enough in the past that a claim stamped then has expired."""
    return datetime.now(timezone.utc) - timedelta(seconds=CLAIM_TTL_SECONDS + 60)


class TestTwoSessionsCannotBothTakeIt(unittest.TestCase):
    """The reproduction from the register, and the only test here that would have caught it."""

    def test_exactly_one_succeeds_and_the_other_is_told_who_holds_it(self):
        first = _ledger()
        pin = add_simple_pin(first)
        first.save()

        second = Ledger(first.path)          # a second session, its own in-memory copy
        took = first.claim(pin["id"], "sess_a")
        first.save()
        refused = second.claim(pin["id"], "sess_b")

        self.assertTrue(took["claimed"])
        self.assertFalse(refused["claimed"],
                         "both sessions took the pin — which is the duplication the field exists "
                         "to remove, and the in-memory check is how it passes unnoticed")
        self.assertEqual(refused["holder"], "sess_a",
                         "a refusal that does not name the holder tells the loser nothing they can "
                         "act on")
        self.assertIn("sess_a", refused["why"])

    def test_the_loser_writing_anyway_is_not_blocked(self):
        """Trap 3: the claim is advisory. It prevents duplicated WORK, not concurrent ACCESS."""
        led = _ledger()
        pin = add_simple_pin(led)
        led.save()
        led.claim(pin["id"], "sess_a")
        led.save()

        other = Ledger(led.path)
        self.assertFalse(other.claim(pin["id"], "sess_b")["claimed"])
        # ...and the write goes through anyway, because the human said so.
        other.add_proposals(pin["id"], [{"summary": "token bucket at the edge"}])
        self.assertEqual(pin_read(other.pin(pin["id"]))["state"], "brainstorming")

    def test_a_pin_nobody_holds_is_taken_by_the_first_asker(self):
        led = _ledger()
        pin = add_simple_pin(led)
        out = led.claim(pin["id"], "sess_a")
        self.assertEqual((out["claimed"], out["holder"], out["reclaimed"]),
                         (True, "sess_a", None))


class TestAClaimExpires(unittest.TestCase):
    """An agent that dies holding one must not park a pin forever, and there is no daemon here."""

    def test_a_stale_claim_is_reclaimable_and_the_reclaim_says_so(self):
        led = _ledger()
        pin = add_simple_pin(led)
        led.claim(pin["id"], "sess_dead", now=_stale())
        led.save()

        out = Ledger(led.path).claim(pin["id"], "sess_b")
        self.assertTrue(out["claimed"])
        self.assertEqual(out["reclaimed"], "sess_dead",
                         "taking a stale claim silently is how two sessions come to believe the "
                         "same thing about different work")

    def test_a_claim_this_runtime_cannot_date_is_stale_not_live(self):
        """The conservative reading in the one direction that matters: a claim nobody can date must
        not park a pin behind a timestamp nobody can fix."""
        for stamp in ("not-a-timestamp", "", 17, None):
            with self.subTest(claimed_at=stamp):
                self.assertEqual(claim_state({"claimed_by": "sess_a", "claimed_at": stamp}),
                                 "stale")

    def test_renewing_is_how_a_long_session_says_it_is_alive(self):
        led = _ledger()
        pin = add_simple_pin(led)
        led.claim(pin["id"], "sess_a", now=_stale())
        led.save()
        again = Ledger(led.path)
        out = again.claim(pin["id"], "sess_a")
        self.assertTrue(out["claimed"])
        self.assertTrue(out["renewed"])
        self.assertIsNone(out["reclaimed"], "you did not reclaim it from yourself")
        self.assertEqual(claim_state(pin_read(again.pin(pin["id"]))), "live")

    def test_the_three_readings_are_the_declared_vocabulary(self):
        self.assertEqual(set(CLAIM_STATES), {"unclaimed", "live", "stale"})
        led = _ledger()
        pin = add_simple_pin(led)
        self.assertEqual(claim_state(pin_read(led.pin(pin["id"]))), "unclaimed")
        led.claim(pin["id"], "sess_a")
        self.assertEqual(claim_state(pin_read(led.pin(pin["id"]))), "live")


class TestTheClaimIsNotAState(unittest.TestCase):
    """Trap 1. It is orthogonal to the lifecycle, and the whole transition table depends on that."""

    def test_a_pin_can_be_claimed_in_more_than_one_state(self):
        led = _ledger()
        pin = add_simple_pin(led)
        for state in ("needs_input", "brainstorming"):
            with self.subTest(state=state):
                led.claim(pin["id"], "sess_a")
                self.assertEqual(pin_read(led.pin(pin["id"]))["state"], state)
                self.assertEqual(claim_state(pin_read(led.pin(pin["id"]))), "live")
            led.add_proposals(pin["id"], [{"summary": "s"}])

    def test_settling_releases_it_because_a_settled_pin_is_not_held(self):
        led = _ledger()
        pin = add_simple_pin(led, kind="defect", question=None)
        led.claim(pin["id"], "sess_a")
        item = led.add_remediation(pin["id"], action="align", ladder_rung=1)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="watched it on staging", rung="observed")
        read = pin_read(led.pin(pin["id"]))
        self.assertEqual(read["state"], "resolved")
        self.assertEqual(claim_state(read), "unclaimed")
        for carrier in CLAIM_CARRIERS:
            self.assertNotIn(carrier, led.pin(pin["id"]))

    def test_correctness_unknown_does_not_release(self):
        """The one door that hands the pin back still open — and the session that could not verify
        it is the one most likely to still be on it."""
        led = _ledger()
        pin = add_simple_pin(led)
        led.decide(pin["id"], "opt_a", "r", "f", human_answer="opt A")
        led.claim(pin["id"], "sess_a")
        led.mark_correctness_unknown(pin["id"], blocked_by="no oracle", attempted=["tests"])
        read = pin_read(led.pin(pin["id"]))
        self.assertEqual(read["state"], "correctness_unknown")
        self.assertEqual(claim_state(read), "live")

    def test_finished_work_is_not_claimable(self):
        led = _ledger()
        pin = add_simple_pin(led, kind="defect", question=None)
        item = led.add_remediation(pin["id"], action="align", ladder_rung=1)
        led.set_remediation_status(pin["id"], item["id"], "done")
        led.resolve(pin["id"], evidence="watched it", rung="observed")
        with self.assertRaises(LedgerError) as ctx:
            led.claim(pin["id"], "sess_a")
        self.assertIn("finished", str(ctx.exception))


class TestReleasing(unittest.TestCase):
    def test_releasing_someone_elses_claim_needs_you_to_not_name_yourself(self):
        led = _ledger()
        pin = add_simple_pin(led)
        led.claim(pin["id"], "sess_a")
        refused = led.release(pin["id"], "sess_b")
        self.assertFalse(refused["released"])
        self.assertEqual(refused["holder"], "sess_a")
        self.assertEqual(claim_state(pin_read(led.pin(pin["id"]))), "live")

        cleaned = led.release(pin["id"])          # the human, clearing up after a dead session
        self.assertTrue(cleaned["released"])
        self.assertEqual(claim_state(pin_read(led.pin(pin["id"]))), "unclaimed")

    def test_releasing_an_unheld_pin_is_not_an_error(self):
        """The post-condition a caller wants is *nobody holds this*. Refusing when it is already
        true would make cleanup a thing you have to check before doing."""
        led = _ledger()
        pin = add_simple_pin(led)
        out = led.release(pin["id"], "sess_a")
        self.assertEqual((out["released"], out["holder"]), (False, ""))

    def test_an_anonymous_claim_is_refused(self):
        led = _ledger()
        pin = add_simple_pin(led)
        for holder in ("", "   ", None):
            with self.subTest(holder=holder):
                with self.assertRaises(LedgerError):
                    led.claim(pin["id"], holder)


class TestTheFrontierIsWhatMakesItWorthHaving(unittest.TestCase):
    """A claim nothing reads is a decoration — and `check_schema_fields` would say so."""

    def _three(self):
        led = _ledger()
        first = add_simple_pin(led, title="one")
        second = add_simple_pin(led, title="two")
        blocked = add_simple_pin(led, title="three", depends_on=[first["id"]])
        return led, first, second, blocked

    def test_it_is_open_unblocked_and_unclaimed(self):
        led, first, second, blocked = self._three()
        self.assertEqual([pin_read(p)["id"] for p in led.frontier()],
                         [first["id"], second["id"]],
                         "a pin whose dependency is still open is not takeable")
        led.claim(first["id"], "sess_a")
        self.assertEqual([pin_read(p)["id"] for p in led.frontier()], [second["id"]])

    def test_a_stale_claim_does_not_hide_a_pin(self):
        """The failure the fix could itself become: a frontier that hid pins behind dead sessions
        would be the outage this field was added to prevent, wearing its name."""
        led, first, _second, _blocked = self._three()
        led.claim(first["id"], "sess_dead", now=_stale())
        self.assertIn(first["id"], [pin_read(p)["id"] for p in led.frontier()])

    def test_what_the_frontier_dropped_is_always_nameable(self):
        led, first, _second, _blocked = self._three()
        led.claim(first["id"], "sess_a")
        held = led.claims()
        self.assertEqual([(c["pin_id"], c["holder"], c["claim_state"]) for c in held],
                         [(first["id"], "sess_a", "live")])

    def test_the_summary_reports_both_halves_and_never_one(self):
        led, first, second, _blocked = self._three()
        led.claim(first["id"], "sess_a")
        summary = led.summary()
        self.assertEqual(summary["frontier"], 1)
        self.assertEqual(summary["claimed"], {first["id"]: "sess_a"})
        self.assertEqual(summary["open_questions"], 3,
                         "the interview still shows every open question — a claim schedules work, "
                         "it does not hide a fork from the human")
        self.assertEqual(pin_read(led.pin(second["id"]))["state"], "needs_input")


class TestTheWaveSchedulerSelectsOverIt(unittest.TestCase):
    def _built(self):
        import buildloop
        led = _ledger()
        one = add_simple_pin(led, kind="defect", title="a", question=None)
        two = add_simple_pin(led, kind="defect", title="b", question=None)
        return buildloop, led, one, two

    def test_a_held_item_leaves_ready_now_and_appears_under_held_by_peers(self):
        buildloop, led, one, two = self._built()
        self.assertEqual(len(buildloop.ready(led)), 2)
        led.claim(one["id"], "sess_a")
        plan = buildloop.plan(led)
        self.assertEqual(plan["ready_now"], ["b"])
        self.assertEqual(plan["held_by_peers"], [{"pin": "a", "holder": "sess_a"}],
                         "a queue that shrinks silently reads as a finished one")
        self.assertEqual(len(buildloop.ready(led)), 2,
                         "`ready` keeps answering the dependency question; the claim filter is "
                         "`frontier`, and fusing them would give the scheduler one answer to two "
                         "questions")

    def test_next_item_does_not_hand_back_what_a_peer_holds(self):
        buildloop, led, one, _two = self._built()
        led.claim(one["id"], "sess_a")
        pin, _item = buildloop.next_item(led)
        self.assertEqual(pin["title"], "b")


class TestTheTunedNumberIsDeclared(unittest.TestCase):
    def test_the_ttl_is_a_hypothesis_and_says_so(self):
        """`check_hypotheses.py` enforces this in CI; asserting it here is what makes the failure
        legible when the constant moves without its reason."""
        import pathlib
        src = pathlib.Path(__file__).resolve().parent.parent / "src" / "runtime" / "ledger.py"
        lines = src.read_text(encoding="utf-8").splitlines()
        at = next(i for i, line in enumerate(lines) if line.startswith("CLAIM_TTL_SECONDS"))
        above = []
        for line in reversed(lines[:at]):
            if not line.startswith("#"):
                break
            above.append(line)
        self.assertTrue(any("HYPOTHESIS" in line for line in above),
                        "a constant with no carrier is a hypothesis, and a hypothesis that hides "
                        "inside code reads as a finding")
        self.assertGreater(CLAIM_TTL_SECONDS, 0)


if __name__ == "__main__":
    unittest.main()
