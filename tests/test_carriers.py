"""Tests for the new deterministic carriers (Block 2 of docs/design/sota-alignment.md):
co-change from git history, declared-vs-actual blast radius, and the cross_derived rung.
Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import cochange  # noqa: E402
import impact  # noqa: E402
from ledger import Ledger, LedgerError  # noqa: E402


def git(repo: str, *args: str) -> None:
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   capture_output=True, text=True)


def write(repo: str, rel: str, body: str) -> None:
    path = os.path.join(repo, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def make_repo() -> str:
    """A repo where api/handler.ts and client/types.ts have always moved together."""
    repo = tempfile.mkdtemp()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t.t")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "commit.gpgsign", "false")
    for i in range(4):
        write(repo, "api/handler.ts", f"// v{i}")
        write(repo, "client/types.ts", f"// v{i}")
        write(repo, "README.md", f"# v{i}")          # ubiquitous: rides along with everything
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", f"c{i}")
    write(repo, "docs/unrelated.md", "x")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "unrelated")
    return repo


class TestCoChange(unittest.TestCase):
    def test_the_other_half_of_the_edit_is_reported(self):
        repo = make_repo()
        out = cochange.omissions(repo, ["api/handler.ts"], min_commits=3)
        files = [c["file"] for c in out["candidates"]]
        self.assertIn("client/types.ts", files)
        self.assertNotIn("docs/unrelated.md", files)

    def test_ubiquity_travels_with_the_row_instead_of_being_filtered_away(self):
        """A lockfile that changes in every commit means nothing — the reader discounts it, not a
        hidden rule."""
        repo = make_repo()
        rows = {r["file"]: r for r in cochange.outside(repo, ["api/handler.ts"], min_commits=3)}
        self.assertIn("README.md", rows)
        self.assertGreater(rows["README.md"]["ubiquity"], rows["client/types.ts"]["ubiquity"] - 1e-9)

    def test_confidence_is_a_conditional_frequency_not_a_weight(self):
        repo = make_repo()
        rows = {r["file"]: r for r in cochange.outside(repo, ["api/handler.ts"], min_commits=3)}
        self.assertEqual(rows["client/types.ts"]["confidence"], 1.0)   # 4 of 4 zone commits

    def test_no_history_is_a_fact_not_an_exception(self):
        empty = tempfile.mkdtemp()
        self.assertEqual(cochange.outside(empty, ["a.ts"]), [])

    def test_one_implementation_serves_both_consumers(self):
        """readiness delegates; two implementations of 'what moves together' would drift."""
        import readiness
        repo = make_repo()
        self.assertEqual(readiness.cochanged_outside(repo, ["api/handler.ts"], min_commits=3),
                         cochange.outside(repo, ["api/handler.ts"], min_commits=3))


class TestDeclaredVsActual(unittest.TestCase):
    def _pin(self, **over) -> dict:
        pin = {"id": "pin_0001", "anchors": [], "readiness": None}
        pin.update(over)
        return pin

    def test_files_outside_the_declared_boundary_are_candidate_scope_creep(self):
        pin = self._pin(readiness={"zone": {"files": ["src/pay/charge.ts"]}})
        out = impact.declared_vs_actual(pin, ["src/pay/charge.ts", "src/admin/panel.ts"])
        self.assertEqual(out["outside_declared"], ["src/admin/panel.ts"])
        self.assertEqual(out["candidates"][0]["failure_class"], "scope_creep")

    def test_touching_less_than_the_zone_is_not_a_finding(self):
        """A blast radius is what COULD be affected; the ladder aims below it on purpose."""
        pin = self._pin(readiness={"zone": {"files": ["a.ts", "b.ts"]}})
        out = impact.declared_vs_actual(pin, ["a.ts"])
        self.assertEqual(out["candidates"], [])
        self.assertEqual(out["declared_untouched"], ["b.ts"])

    def test_anchors_are_the_fallback_boundary(self):
        pin = self._pin(anchors=[{"loc": "src/pay/charge.ts:5"}])
        out = impact.declared_vs_actual(pin, ["src/pay/charge.ts"])
        self.assertEqual(out["declared_from"], "anchors")
        self.assertEqual(out["outside_declared"], [])

    def test_no_declared_boundary_says_so_rather_than_reading_clean(self):
        out = impact.declared_vs_actual(self._pin(), ["anything.ts"])
        self.assertFalse(out["checked"])
        self.assertIn("Unchecked is not clean", out["why"])


class TestCrossDerivation(unittest.TestCase):
    def _led(self) -> tuple:
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        pin = led.add_pin(kind="design_concern", title="use lib X", severity="high",
                          confidence="inferred",
                          provenance=[{"source": "researcher", "detail": "docs"}],
                          as_is={"description": "d"})
        return led, pin

    def test_same_provider_twice_is_repetition_not_independence(self):
        led, pin = self._led()
        with self.assertRaises(LedgerError):
            led.cross_derive(pin["id"], "lib X supports streaming", [
                {"provider": "anthropic", "model": "a", "result": "yes"},
                {"provider": "anthropic", "model": "b", "result": "yes"},
            ], agreement="agree")

    def test_one_derivation_is_just_the_original_claim(self):
        led, pin = self._led()
        with self.assertRaises(LedgerError):
            led.cross_derive(pin["id"], "c", [
                {"provider": "anthropic", "model": "a", "result": "yes"}], agreement="agree")

    def test_agreement_earns_the_cross_derived_rung(self):
        led, pin = self._led()
        led.cross_derive(pin["id"], "lib X supports streaming", [
            {"provider": "anthropic", "model": "a", "result": "yes"},
            {"provider": "openai", "model": "b", "result": "yes"},
        ], agreement="agree")
        self.assertEqual(led.pin(pin["id"])["verification"]["rung"], "cross_derived")

    def test_disagreement_contests_the_pin_and_asks_a_human(self):
        led, pin = self._led()
        led.cross_derive(pin["id"], "lib X supports streaming", [
            {"provider": "anthropic", "model": "a", "result": "yes"},
            {"provider": "openai", "model": "b", "result": "no, removed in v4"},
        ], agreement="disagree")
        got = led.pin(pin["id"])
        self.assertEqual(got["state"], "needs_input")
        self.assertEqual(got["substate"], "contested")
        self.assertIn(got["id"], [p["id"] for p in led.interview_view()])

    def test_disagreement_does_not_cascade_to_dependents(self):
        """Nobody knows which side is wrong yet — reopening the neighbourhood would be churn."""
        led, pin = self._led()
        dependent = led.add_pin(kind="defect", title="d", severity="low", confidence="extracted",
                                provenance=[{"source": "x", "detail": "y"}],
                                as_is={"description": "d"}, depends_on=[pin["id"]])
        led.decide(dependent["id"], "o", "r", "f")
        led.cross_derive(pin["id"], "c", [
            {"provider": "anthropic", "model": "a", "result": "yes"},
            {"provider": "openai", "model": "b", "result": "no"},
        ], agreement="disagree")
        self.assertEqual(led.pin(dependent["id"])["state"], "decided")

    def test_the_two_determinism_levels_are_kept_apart(self):
        led, pin = self._led()
        rec = led.cross_derive(pin["id"], "c", [
            {"provider": "anthropic", "model": "a", "result": "yes"},
            {"provider": "openai", "model": "b", "result": "yes"},
        ], agreement="agree")
        self.assertEqual(rec["independence_determinism"], "D0")   # distinct providers: checked
        self.assertEqual(rec["agreement_determinism"], "D2")      # 'same meaning': judged


if __name__ == "__main__":
    unittest.main()
