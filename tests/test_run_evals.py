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

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
import unittest.mock

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

    def test_shell_absent_reads_the_command_because_every_shell_search_is_named_Bash(self):
        """The search doctrine's carrier is the command string; the tool name cannot carry it.

        `tool_absent("^Bash$")` would fail any run that used a shell at all, so it would grade the
        agent for opening a terminal rather than for which search it reached for.
        """
        recursive = r"(^|[|&;])\s*grep\s+-[A-Za-z]*[rR]"
        innocent = make_run(self.tmp, tools=[("Bash", {"command": "rg -t py 'def is_'"})])
        self.assertTrue(run_evals.shell_absent(recursive)(innocent)[0])
        guilty = make_run(self.tmp, tools=[("Bash", {"command": "grep -rn TODO ."})])
        self.assertFalse(run_evals.shell_absent(recursive)(guilty)[0])
        # A pipe filter reads as a search to a careless regex; it is not one, and the doctrine's
        # own hook stays out of it. Anchoring on a command boundary is what keeps them apart.
        piped = make_run(self.tmp, tools=[("Bash", {"command": "gh pr list | grep open"})])
        self.assertTrue(run_evals.shell_absent(recursive)(piped)[0])

    def test_shell_absent_sees_past_the_first_line(self):
        """A multi-line Bash call is the ordinary shape, and this predicate asserts ABSENCE — so a
        pattern anchored at `^` without `MULTILINE` misses the violation and grades the run a PASS.
        A check that cannot fail is worse than no check, because it is counted as a pass."""
        for pattern, command in (
            (r"(^|[|&;])\s*grep\s+-[A-Za-z]*[rR]", "cd fixture\ngrep -rn 'authorize' ."),
            (r"(^|[|&;])\s*find\s", "cd fixture\nfind . -name '*.py'"),
        ):
            guilty = make_run(self.tmp, tools=[("Bash", {"command": command})])
            self.assertFalse(run_evals.shell_absent(pattern)(guilty)[0], command)

    def test_searched_with_accepts_the_native_tool_and_the_shell_spelling(self):
        """Grep-the-tool and `rg`-in-a-shell are the same answer; an assertion naming one would
        grade the host's tool surface instead of the agent's choice."""
        pattern = r"^(Grep|Glob)$|\b(rg|ast-grep|sg|fd)\b"
        native = make_run(self.tmp, tools=[("Grep", {"pattern": "is_admin"})])
        self.assertTrue(run_evals.searched_with(pattern)(native)[0])
        shelled = make_run(self.tmp, tools=[("Bash", {"command": "ast-grep -p 'f($$$A)'"})])
        self.assertTrue(run_evals.searched_with(pattern)(shelled)[0])
        neither = make_run(self.tmp, tools=[("Bash", {"command": "grep -rn x ."})])
        self.assertFalse(run_evals.searched_with(pattern)(neither)[0])

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


class TestEveryRunCanReachTheToolsItIsMeasuredOn(unittest.TestCase):
    """`--plugin-dir` loads a directory; it resolves no `dependencies`.

    Verified at the consumer on this CLI: `--plugin-dir plugins/keel-kit` alone answers
    `mcp_servers: []` in its `init` event, while adding `--plugin-dir plugins/keel-core` brings up
    `plugin:keel-core:keel` and makes `mcp__plugin_keel-core_keel__ledger_summary` callable from a
    keel-kit skill's session. Only `keel-core` carries a plugin-root `.mcp.json`; the other three
    name it in `dependencies`, which is what a MARKETPLACE resolves and a directory load does not.

    So five of the six eval skills used to run with no `ledger_*` tool at all: every `pin(...)` and
    `log_entry(...)` check read a ledger the agent had no door to write, `tool_used(…ledger_resolve)`
    could not match on any run, and `tool_absent(…)` passed for the one reason that proves nothing.
    `docs/measurements.md` never saw it because the only case it drove end to end was a `keel-core`
    one. CI runs `--execute --checked-only`, so those cases ran and spent budget.
    """

    def test_the_command_carries_every_plugin_that_declares_an_mcp_server(self):
        carriers = run_evals.mcp_plugins()
        self.assertTrue(carriers, "no built plugin declares MCP servers — run scripts/build.py")
        for path in run_evals.find_eval_files():
            skill = path.parent.parent.name
            with self.subTest(skill=skill):
                names = [p.name for p in run_evals.plugin_dirs_for(skill)]
                self.assertEqual(names[0], run_evals.plugin_for(skill).name,
                                 "the skill's own plugin must stay first")
                for carrier in carriers:
                    self.assertIn(carrier.name, names)
                self.assertEqual(len(names), len(set(names)), "a plugin dir was passed twice")

    def test_the_flag_is_repeated_rather_than_joined(self):
        """`--plugin-dir <path>`, *"repeatable: --plugin-dir A --plugin-dir B.zip"* — one flag per
        directory. A comma-joined pair is a path that does not exist, and the CLI would load
        nothing while the command still looked right."""
        class _Args:
            model = permission_mode = allowed_tools = ""
            max_budget_usd = 5.0
        dirs = run_evals.plugin_dirs_for("test-driven-development")
        cmd = run_evals.build_command("claude", dirs, _Args())
        self.assertEqual(cmd.count("--plugin-dir"), len(dirs))
        for path in dirs:
            self.assertIn(str(path), cmd)


class TestARelativeLedgerBelongsToTheRunAndNotToTheHarness(unittest.TestCase):
    """`ledger.json` is the natural spelling for an agent standing in the project.

    The MCP server resolves it against ITS cwd, which is the workdir the harness handed the run.
    The harness resolved it against its own — the repo root, which is where `--execute` is
    documented to be run from and where anyone who has dogfooded Keel has a `ledger.json`. So a run
    that wrote nothing was credited with somebody else's pins, and the report listed the label
    `ledger.json` twice with no way to tell which was which. Latent in CI only because that file is
    gitignored and absent from a fresh checkout.
    """

    def setUp(self):
        self.harness_cwd = pathlib.Path(tempfile.mkdtemp())
        self.workdir = pathlib.Path(tempfile.mkdtemp())
        self._old = os.getcwd()
        os.chdir(self.harness_cwd)

    def tearDown(self):
        os.chdir(self._old)

    def test_a_stray_ledger_beside_the_harness_is_not_an_artifact_of_the_run(self):
        (self.harness_cwd / "ledger.json").write_text(json.dumps({"version": "0.31", "pins": [
            {"id": f"pin_{i}", "kind": "open_decision", "state": "needs_input"}
            for i in range(4)]}), encoding="utf-8")
        (self.workdir / "ledger.json").write_text(
            json.dumps({"version": "0.31", "pins": []}), encoding="utf-8")
        run = make_run(self.workdir, tools=[
            ("mcp__plugin_keel-core_keel__ledger_add_pin", {"ledger": "ledger.json"})])
        self.assertEqual([led["path"] for led in run.ledgers], ["ledger.json"])
        self.assertEqual(run.pins(), [],
                         "the run's empty ledger was topped up from the harness's cwd")
        self.assertFalse(run_evals.pin(kind="open_decision", min_count=4)(run)[0])

    def test_an_absolute_ledger_outside_the_copy_is_still_the_runs(self):
        """The property the relative fix must not cost: naming an absolute path is legitimate, and
        a harness that only globs its copy reports `0 pins` for a run that wrote a full ledger.

        The tempdir is `.resolve()`d because the harness labels ledgers by RESOLVED path (its
        stated symlink rationale) and macOS mounts tempdirs behind one: `/var` -> `/private/var`.
        Compared unresolved, this assertion is green on Linux and red on the macOS CI leg only."""
        elsewhere = pathlib.Path(tempfile.mkdtemp()).resolve() / "out.json"
        elsewhere.write_text(json.dumps({"version": "0.31", "pins": [
            {"id": "pin_1", "kind": "defect", "state": "detected"}]}), encoding="utf-8")
        run = make_run(self.workdir, tools=[("mcp__keel__ledger_add_pin",
                                             {"ledger": str(elsewhere)})])
        self.assertTrue(run_evals.pin(kind="defect")(run)[0])
        self.assertIn(str(elsewhere), [led["path"] for led in run.ledgers],
                      "a ledger outside the copy must be labelled by its absolute path")

    def test_the_report_default_is_a_gitignored_path(self):
        """`--execute` writes it into the cwd even on the runner-unavailable path, and the
        documented invocation is from the repo root. Every other artifact this repo generates is
        ignored; this one escaped, and a release commit's `git add -A` would have carried it."""
        proc = subprocess.run(["git", "check-ignore", run_evals.DEFAULT_REPORT], cwd=str(ROOT),
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         f"{run_evals.DEFAULT_REPORT!r} is not gitignored — see .gitignore")


class TestARunOfAUserInvokedSkillHasToLoadIt(unittest.TestCase):
    """The 2026-08-13 live run measured an agent that never loaded the skill under test.

    All four transcripts carry the host's own refusal — *"Skill using-the-ledger cannot be used with
    Skill tool due to disable-model-invocation. Ask the user to run /using-the-ledger themselves"* —
    because `execute_case` piped the bare prompt and **fifteen of the nineteen shipped skills** are
    user-invoked. Every assertion about the skill's steering was then resolved against a run the
    skill did not steer: a pass proved the MCP tools were discoverable, a fail proved nothing.

    So the prompt now carries the invocation the refusal itself names. Asserted here at the level
    this machine can reach — the string that is piped — because the level above it needs a
    credentialed runner. `docs/measurements.md` carries that residual explicitly rather than
    letting a green suite imply an observed run.
    """

    def test_a_user_invoked_skill_is_typed_by_name(self):
        self.assertTrue(run_evals.is_user_invoked("using-the-ledger"),
                        "the built SKILL.md no longer sets disable-model-invocation")
        prompt = run_evals.case_prompt("using-the-ledger", {"prompt": "what is open?"})
        self.assertEqual(prompt, "/using-the-ledger what is open?")

    def test_a_model_invoked_skill_is_left_to_fire_off_its_description(self):
        """`codebase-rescue` triggers on a situation nobody names, so typing the name would test a
        door no cold user uses — the trigger IS what the case measures."""
        self.assertFalse(run_evals.is_user_invoked("codebase-rescue"))
        self.assertEqual(run_evals.case_prompt("codebase-rescue", {"prompt": "this repo is a mess"}),
                         "this repo is a mess")

    def test_the_answer_is_read_off_the_built_skill_and_not_a_list_here(self):
        """A second copy of *which skills are user-invoked* is the drift every gate here exists to
        catch, so the predicate is checked against the frontmatter rather than against a roster."""
        source = (ROOT / "src" / "skills" / "using-the-ledger" / "SKILL.md").read_text("utf-8")
        self.assertEqual(run_evals.is_user_invoked("using-the-ledger"),
                         run_evals.declares_user_invoked(source))

    def test_the_key_is_read_in_the_frontmatter_and_nowhere_else(self):
        """The host parses the YAML block; a body is prose to it. This package's own bodies quote
        the key — `which-skill` tabulates which skills set it, `writing-skills` documents setting
        it — so a whole-file match would classify a MODEL-invoked skill as user-invoked and make the
        runner type `/codebase-rescue`, testing a door no cold user uses on the one skill whose
        entire case is the cold trigger."""
        body_only = (
            "---\nname: codebase-rescue\ndescription: rescue a misaligned codebase\n---\n\n"
            "# Codebase Rescue\n\nFifteen of the nineteen shipped skills set\n"
            "disable-model-invocation: true\nand are reached by typing the name.\n"
        )
        self.assertFalse(run_evals.declares_user_invoked(body_only),
                         "the key was matched in the body — this skill fires off its description")
        in_frontmatter = (
            "---\nname: using-the-ledger\ndisable-model-invocation: true\n---\n\n# body\n"
        )
        self.assertTrue(run_evals.declares_user_invoked(in_frontmatter))
        self.assertFalse(run_evals.declares_user_invoked("disable-model-invocation: true\n"),
                         "a file with no frontmatter block at all declares nothing")


class TestASeedNobodyCopiesIsACaseWithNoPrecondition(unittest.TestCase):
    """`files` was in the eval schema and validated by `--validate` from the beginning, and nothing
    ever copied it — a declared mechanism with no carrier, inside the harness written to catch that.

    It is load-bearing now: two relay cases record against pins they did not create, and the seed
    cannot live in the shared fixture for two independent reasons — `ledger.json` is a gitignored
    runtime artifact, and case 4 asserts that a MISSING ledger is reported as missing.
    """

    def test_a_seed_lands_under_the_name_the_case_declared(self):
        evals_dir = pathlib.Path(tempfile.mkdtemp())
        (evals_dir / "seeds").mkdir()
        (evals_dir / "seeds" / "fork.json").write_text('{"version": "0.31", "pins": []}', "utf-8")
        workdir = pathlib.Path(tempfile.mkdtemp())
        landed = run_evals.seed_files(
            {"files": [{"from": "seeds/fork.json", "to": "ledger.json"}]}, evals_dir, workdir)
        self.assertEqual(landed, ["ledger.json"])
        self.assertTrue((workdir / "ledger.json").is_file())

    def test_a_plain_path_keeps_its_own_name(self):
        evals_dir = pathlib.Path(tempfile.mkdtemp())
        (evals_dir / "notes.md").write_text("x", encoding="utf-8")
        workdir = pathlib.Path(tempfile.mkdtemp())
        run_evals.seed_files({"files": ["notes.md"]}, evals_dir, workdir)
        self.assertTrue((workdir / "notes.md").is_file())

    def test_every_declared_seed_exists_and_parses_as_a_ledger(self):
        """`--validate` proves the file is there. This proves it is the thing the case needs: a
        seed that does not parse is a case that runs against a ledger no tool can open, and the
        failure would read as an adherence miss."""
        for path in run_evals.find_eval_files():
            data = json.loads(path.read_text(encoding="utf-8"))
            for case in data.get("evals", []):
                for entry in case.get("files", []):
                    if not (isinstance(entry, dict) and entry.get("to") == "ledger.json"):
                        continue
                    with self.subTest(skill=path.parent.parent.name, case=case["id"]):
                        seed = json.loads((path.parent / entry["from"]).read_text("utf-8"))
                        self.assertTrue(seed.get("pins"),
                                        "a seeded ledger with no pins seeds nothing")


class TestASeedNeitherReadsNorWritesOutsideItsOwnTree(unittest.TestCase):
    """An eval file is DATA — this repo's corpus today, a contributor's PR tomorrow — and
    `--execute` turns it into file copies on the operator's behalf.

    Neither side was confined. `pathlib`'s `/` **discards the left operand** when the right is
    absolute, so `evals_dir / "/etc/id_rsa"` is `/etc/id_rsa` and the seed read whatever the
    operator could read; `to` was never validated at all, so `../../.ssh/authorized_keys` wrote
    wherever they could write. Both are checked in BOTH places on purpose: `execute_case` does not
    call `validate`, so a rule that lived only in the gate governed nothing at execution — which is
    the same claiming-vs-doing shape as the `files` mechanism that was declared and never carried.
    """

    ESCAPES = ("../outside.json", "seeds/../../outside.json", "")

    def setUp(self):
        self.evals_dir = pathlib.Path(tempfile.mkdtemp())
        self.workdir = pathlib.Path(tempfile.mkdtemp())
        (self.evals_dir / "seeds").mkdir()
        (self.evals_dir / "seeds" / "fork.json").write_text('{"pins": [1]}', encoding="utf-8")
        self.outside = pathlib.Path(tempfile.mkdtemp()) / "outside.json"
        self.outside.write_text('{"pins": []}', encoding="utf-8")

    def test_seed_files_refuses_an_absolute_from(self):
        with self.assertRaises(run_evals.UnconfinedSeed):
            run_evals.seed_files({"files": [{"from": str(self.outside), "to": "ledger.json"}]},
                                 self.evals_dir, self.workdir)
        self.assertFalse((self.workdir / "ledger.json").exists())

    def test_seed_files_refuses_an_absolute_to(self):
        target = self.workdir.parent / "escaped.json"
        with self.assertRaises(run_evals.UnconfinedSeed):
            run_evals.seed_files({"files": [{"from": "seeds/fork.json", "to": str(target)}]},
                                 self.evals_dir, self.workdir)
        self.assertFalse(target.exists(), "the copy happened before the path was looked at")

    def test_seed_files_refuses_traversal_on_either_side(self):
        for escape in self.ESCAPES:
            with self.subTest(side="from", path=escape), \
                    self.assertRaises(run_evals.UnconfinedSeed):
                run_evals.seed_files({"files": [{"from": escape, "to": "ledger.json"}]},
                                     self.evals_dir, self.workdir)
            with self.subTest(side="to", path=escape), \
                    self.assertRaises(run_evals.UnconfinedSeed):
                run_evals.seed_files({"files": [{"from": "seeds/fork.json", "to": escape}]},
                                     self.evals_dir, self.workdir)

    def test_a_windows_absolute_path_is_refused_on_a_posix_run_too(self):
        """`PurePosixPath("C:\\\\x").is_absolute()` is False, so a POSIX-only test would pass the
        string through to a join that discards the base the moment the same corpus is validated on
        Windows. The corpus is portable; the refusal has to be."""
        with self.assertRaises(run_evals.UnconfinedSeed):
            run_evals.confined(self.evals_dir, r"C:\Windows\win.ini", "files `from`")

    def test_a_legal_relative_seed_still_lands(self):
        """The point is confinement, not refusal: the shipped corpus's own shape must survive."""
        landed = run_evals.seed_files(
            {"files": [{"from": "seeds/fork.json", "to": "nested/ledger.json"}]},
            self.evals_dir, self.workdir)
        self.assertEqual(landed, ["nested/ledger.json"])
        self.assertTrue((self.workdir / "nested" / "ledger.json").is_file())

    def test_validate_reports_an_unconfined_seed_rather_than_letting_execute_meet_it(self):
        """`--validate` is the gate a PR passes, so an escaping path has to be a `problem` line and
        not an exception out of the linter."""
        evals = self.evals_dir / "skill" / "evals"
        evals.mkdir(parents=True)
        (evals / "evals.json").write_text(json.dumps({
            "skill_name": "skill",
            "evals": [{"id": 1, "prompt": "p", "expected_output": "e", "assertions": ["a"],
                       "files": [{"from": str(self.outside), "to": "../escaped.json"}]}],
        }), encoding="utf-8")
        buffer = io.StringIO()
        # `ROOT` only labels the problem lines, and this corpus is deliberately outside the repo —
        # the point is a contributor's eval file, not one of ours.
        with contextlib.redirect_stdout(buffer), \
                unittest.mock.patch.object(run_evals, "ROOT", self.evals_dir):
            code = run_evals.validate([evals / "evals.json"])
        self.assertEqual(code, run_evals.EXIT_FAILED)
        report = buffer.getvalue()
        self.assertIn("files `from`", report)
        self.assertIn("files `to`", report)


if __name__ == "__main__":
    unittest.main()
