"""The eval harness's own gates — `scripts/run_evals.py`.

Two things are tested here and they are not the same thing:

  * **`--validate`'s new half.** The `CHECKS` table is keyed on the assertion's PROSE, so a
    reworded eval silently detaches its machine check and the assertion quietly becomes `manual`.
    `--validate` now fails on that, and this suite proves the failure fires — a drift gate nobody
    has watched fail is a drift gate nobody knows works.

  * **The check predicates.** Each one resolves an assertion against the artifacts a run left
    behind, and they run against a REAL agent only when a credential exists, which CI does not
    hold. So they are exercised here against a synthetic `Run` instead: a ledger on disk and a
    tool list, which is exactly what the predicates read. This is the difference between "the
    harness executed" and "the harness would have noticed", and only the second is testable
    without spending money.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run_evals.py")
run_evals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_evals)


def make_run(tmp: pathlib.Path, *, tools=(), ledger=None, text="") -> run_evals.Run:
    """A `Run` without an agent: the artifacts the predicates actually read, placed by hand.

    The tool calls are wrapped back into the host's own `stream-json` message shape rather than
    poked into `Run.tools`, so this exercises the parser too — the layer where a host format
    change would break everything downstream of it.
    """
    events = []
    for name, tool_input in tools:
        events.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": tool_input}]}})
    if text:
        events.append({"type": "assistant",
                       "message": {"content": [{"type": "text", "text": text}]}})
    if ledger is not None:
        (tmp / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    return run_evals.Run(tmp, events, {"num_turns": len(events)}, 1.0)


class TestTheChecksTableIsHeldToTheCorpus(unittest.TestCase):
    """A machine check keyed to prose nobody wrote runs on nothing and reports nothing."""

    def test_every_checks_key_names_a_real_assertion(self):
        self.assertEqual(0, run_evals.validate(run_evals.find_eval_files()),
                         "the shipped corpus and the CHECKS table disagree — see the INVALID lines")

    def test_a_reworded_assertion_is_reported_not_silently_dropped(self):
        key = next(iter(run_evals.CHECKS))
        original = run_evals.CHECKS.pop(key)
        try:
            run_evals.CHECKS[(key[0], key[1], key[2] + " (reworded)")] = original
            self.assertEqual(run_evals.EXIT_FAILED,
                             run_evals.validate(run_evals.find_eval_files()),
                             "a CHECKS key naming no assertion must fail --validate")
        finally:
            run_evals.CHECKS.pop((key[0], key[1], key[2] + " (reworded)"), None)
            run_evals.CHECKS[key] = original

    def test_every_check_carries_its_predicate_in_words(self):
        for key, check in run_evals.CHECKS.items():
            self.assertTrue(getattr(check, "describe", ""),
                            f"{key} has no describe — a FAIL with no stated predicate is not "
                            f"diagnosable")


class TestThePredicatesReadArtifacts(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_pin_matches_kind_confidence_and_provenance(self):
        led = {"version": "0.31", "pins": [
            {"id": "pin_1", "kind": "open_decision", "confidence": "inferred",
             "provenance": [{"source": "agent_assumption"}], "state": "needs_input"}]}
        run = make_run(self.tmp, ledger=led)
        ok, _ = run_evals.pin(kind="open_decision", confidence=("inferred", "ambiguous"),
                              provenance="agent_assumption")(run)
        self.assertTrue(ok)
        wrong, _ = run_evals.pin(kind="defect")(run)
        self.assertFalse(wrong)

    def test_no_pin_is_not_satisfied_by_a_matching_pin(self):
        led = {"version": "0.31", "pins": [{"id": "pin_1", "kind": "defect", "state": "resolved"}]}
        run = make_run(self.tmp, ledger=led)
        ok, _ = run_evals.no_pin(kind="defect", state="resolved")(run)
        self.assertFalse(ok)

    def test_log_entry_dispatches_on_the_ledgers_own_id_prefixes(self):
        led = {"version": "0.31", "pins": [],
               "decision_log": [{"id": "chl_1", "pin_id": "pin_1"}]}
        run = make_run(self.tmp, ledger=led)
        self.assertTrue(run_evals.log_entry("chl_")(run)[0])
        self.assertTrue(run_evals.no_log_entry("ev_")(run)[0])
        self.assertFalse(run_evals.log_entry("ev_")(run)[0])

    def test_a_ledger_written_outside_the_workdir_is_still_found(self):
        """The `ledger` argument is the agent's to choose. A harness that only globs its own copy
        reports `0 pins` for a run that wrote a full ledger elsewhere — a false FAIL."""
        elsewhere = pathlib.Path(tempfile.mkdtemp()) / "out.json"
        elsewhere.write_text(json.dumps({"version": "0.31", "pins": [
            {"id": "pin_1", "kind": "defect", "state": "detected"}]}), encoding="utf-8")
        run = make_run(self.tmp, tools=[("mcp__plugin_keel-core_keel__ledger_add_pin",
                                         {"ledger": str(elsewhere)})])
        self.assertTrue(run_evals.pin(kind="defect")(run)[0])

    def test_the_mcp_prefix_matches_both_namespacings_the_host_uses(self):
        """Verified against a real run: a plugin loaded with `--plugin-dir` has its MCP server
        namespaced (`mcp__plugin_keel-core_keel__…`); the same server reached from a user's own
        settings is `mcp__keel__…`. A constant for one of them FAILS a run that used the other."""
        check = run_evals.tool_used(rf"{run_evals.MCP_PREFIX}ledger_add_pin")
        for name in ("mcp__keel__ledger_add_pin", "mcp__plugin_keel-core_keel__ledger_add_pin"):
            run = make_run(self.tmp, tools=[(name, {})])
            self.assertTrue(check(run)[0], f"{name} must match MCP_PREFIX")

    def test_tool_before_is_not_satisfied_by_never_doing_the_first_thing(self):
        """"pins before it edits" must not pass on a run that pinned nothing."""
        run = make_run(self.tmp, tools=[("Edit", {"file_path": "a.py"})])
        ok, why = run_evals.tool_before(r"ledger_add_pin", r"^Edit$")(run)
        self.assertFalse(ok)
        self.assertIn("never called", why)
        ordered = make_run(self.tmp, tools=[("mcp__keel__ledger_add_pin", {}),
                                            ("Edit", {"file_path": "a.py"})])
        self.assertTrue(run_evals.tool_before(r"ledger_add_pin", r"^Edit$")(ordered)[0])

    def test_file_untouched_reads_the_tool_input_not_the_tool_name(self):
        """The forbidden thing is not calling Edit, it is calling Edit ON that file."""
        innocent = make_run(self.tmp, tools=[("Edit", {"file_path": "src/app.py"})])
        self.assertTrue(run_evals.file_untouched(r"ledger\.json$")(innocent)[0])
        guilty = make_run(self.tmp, tools=[("Edit", {"file_path": "/x/ledger.json"})])
        self.assertFalse(run_evals.file_untouched(r"ledger\.json$")(guilty)[0])

    def test_a_failed_tool_call_is_distinguished_from_an_absent_one(self):
        run = run_evals.Run(self.tmp, [{"type": "user", "message": {"content": [
            {"type": "tool_result", "is_error": True, "content": "boom"}]}}], {}, 1.0)
        self.assertEqual(["boom"], run.tool_errors)


class TestAnUnavailableRunnerIsItsOwnAnswer(unittest.TestCase):
    def test_exit_codes_are_distinct(self):
        codes = {run_evals.EXIT_OK, run_evals.EXIT_FAILED,
                 run_evals.EXIT_USAGE, run_evals.EXIT_NO_RUNNER}
        self.assertEqual(4, len(codes), "'assertions failed' and 'cannot host a run' must differ")

    def test_a_missing_binary_says_so_before_spending_anything(self):
        ok, reason, _ = run_evals.preflight("claude-no-such-binary", ["using-the-ledger"], 5)
        self.assertFalse(ok)
        self.assertIn("PATH", reason)

    def test_every_shipped_skill_with_evals_resolves_to_a_built_plugin(self):
        """`--execute` loads `plugins/<p>` so the run measures Keel rather than the host's
        defaults. A skill with evals and no built plugin cannot be executed at all."""
        for path in run_evals.find_eval_files():
            skill = path.parent.parent.name
            with self.subTest(skill=skill):
                self.assertIsNotNone(run_evals.plugin_for(skill),
                                     f"no plugins/*/skills/{skill} — run scripts/build.py")


if __name__ == "__main__":
    unittest.main()
