#!/usr/bin/env python3
"""Eval harness for the skills' evals/evals.json.

Three modes, and the whole point of the file is that each one is honest about what it proves.

  --validate (default; runs in CI, blocking)
      Structural gate: every evals.json parses, has the required fields, unique ids, non-empty
      assertions, and a skill_name matching its directory. It also checks that every entry in
      `CHECKS` below still names an assertion that exists — a machine check keyed to prose that
      has since been reworded is a check that silently stops running, which is the class this
      repo's gates exist to catch. Proves the specs are well-formed — NOT that the skill behaves.

  --execute (advisory in CI; needs a runner with credentials)
      Behavioral execution against Claude Code in headless mode, with the built plugin loaded
      (`--plugin-dir plugins/<plugin>`), the transcript captured as `stream-json`, and each
      assertion resolved against the ARTIFACTS the run produced — the `ledger.json` it wrote and
      the tool calls it made — not against an opinion about the transcript. Assertions with no
      machine check are reported `manual`, never as a pass and never skipped in silence.

  --run --runner "<cmd>"  (legacy, host-agnostic)
      The original mode, kept because it is the only one that works against a runner that is not
      Claude Code: it pipes the prompt to an arbitrary command and judges each assertion with an
      LLM-as-judge call through that same command. It proves nothing about artifacts, because it
      never looks at any — which is exactly why `--execute` exists beside it rather than replacing
      it. `--execute --judge` reuses this file's judge for its `manual` assertions, as ADVISORY
      evidence that cannot move the exit code.

Exit codes are distinct on purpose, because "the assertions failed" and "this machine cannot host
a run" are different facts and CI must be able to tell them apart:

    0  every machine-checked assertion passed (manual ones reported)
    1  at least one machine-checked assertion FAILED, or a case errored
    2  usage error (bad flags, unknown skill, missing fixture)
    3  the runner is unavailable — no `claude` on PATH, no credentials, or the plugin is not
       built. The report says which, in the runner's own words.

Stdlib-only, like every other check in this repo.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED_CASE_FIELDS = ("id", "prompt", "expected_output", "assertions")

#: Exit codes, named rather than typed at three call sites (see the docstring for what each means).
EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_NO_RUNNER = 0, 1, 2, 3

#: How a `keel` MCP tool call NAMES ITSELF in the transcript — a regex fragment, not a constant,
#: because the host rewrites the name and there are two forms.
#:
#: Verified by running it, after the constant `"mcp__keel__"` reported a clean FAIL on a run that
#: had plainly called the tool. Every plugin's `.mcp.json` declares the server as `keel`, and a
#: server reached that way IS `mcp__keel__<tool>` — but a plugin loaded with `--plugin-dir` has its
#: servers namespaced by the plugin: `system/init` lists them as `plugin:keel-core:keel` and the
#: tools arrive as `mcp__plugin_keel-core_keel__<tool>`. The eval harness loads the plugin, so it
#: sees the second form; a developer with the server in their own settings sees the first. Both
#: match below, and the alternation is the record of which is which.
MCP_PREFIX = r"mcp__(?:plugin_[\w-]+_)?keel__"

JUDGE_PROMPT = """You are a strict eval judge. Below is the full transcript of an agent \
working on a task, followed by ONE assertion about the required behavior.

Answer with a single JSON object, nothing else: {{"verdict": "PASS" | "FAIL", "reason": "<one sentence>"}}
Judge only what the transcript shows; unsupported claims FAIL.

=== TRANSCRIPT ===
{transcript}
=== ASSERTION ===
{assertion}
"""


def find_eval_files() -> list[pathlib.Path]:
    return sorted(ROOT.glob("src/skills/*/evals/evals.json"))


# ---------------------------------------------------------------------------
# the checks — what an assertion can be resolved against, deterministically
# ---------------------------------------------------------------------------
#
# A check reads the RUN, never the transcript's prose. `Run` below is everything one execution
# left behind: the ordered tool calls, the ledger(s) it wrote, the files under its working
# directory, and the host's own `system/init` (which is how "was the plugin actually loaded?"
# becomes a fact rather than an assumption).
#
# The honesty rule this file runs on: a check either resolves against an artifact or it does not
# exist. There is no "the transcript said it did" check, because an agent claiming to have opened
# a pin and an agent opening a pin are the two states the whole package is about telling apart.


class Run:
    """One executed case: the artifacts, indexed for the checks."""

    def __init__(self, workdir: pathlib.Path, events: list[dict], result: dict,
                 wall_seconds: float):
        self.workdir = workdir
        self.events = events
        self.result = result
        self.wall_seconds = wall_seconds
        self.init = next((e for e in events
                          if e.get("type") == "system" and e.get("subtype") == "init"), {})
        self.tools: list[dict] = []
        texts: list[str] = []
        self.tool_errors: list[str] = []
        for ev in events:
            message = ev.get("message")
            blocks = message.get("content") if isinstance(message, dict) else None
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    self.tools.append({"seq": len(self.tools), "name": block.get("name", ""),
                                       "input": block.get("input") or {}})
                elif block.get("type") == "tool_result" and block.get("is_error"):
                    # A tool that was CALLED and FAILED reads, in every check above, exactly like a
                    # tool that was never called — and the two are different findings. Recorded so
                    # the report can tell an operator which one they are looking at.
                    self.tool_errors.append(str(block.get("content"))[:200])
                elif block.get("type") == "text" and ev.get("type") == "assistant":
                    texts.append(str(block.get("text") or ""))
        self.text = "\n".join(texts)
        # Every ledger the run produced. Searched under the working directory AND at every path the
        # run NAMED, because the `ledger` argument is the agent's to choose
        # (`mcp:ledger_add_pin(ledger=…)`) and it is free to name an absolute path outside the copy.
        # A harness that only globs the workdir reports "0 pins" for a run that wrote a full ledger
        # somewhere else — a false FAIL, which is worse than a manual. Found by running it: the
        # first green case called `ledger_add_pin` and left the workdir empty.
        named = {pathlib.Path(str(t["input"]["ledger"])).expanduser()
                 for t in self.tools if isinstance(t["input"].get("ledger"), str)}
        self.ledgers: list[dict] = []
        for path in sorted(set(workdir.rglob("ledger.json")) | named):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                try:
                    label = str(path.relative_to(workdir))
                except ValueError:
                    label = str(path)          # outside the copy; reported as the absolute path
                self.ledgers.append({"path": label, "data": data})

    def pins(self) -> list[dict]:
        out = []
        for led in self.ledgers:
            pins = led["data"].get("pins")
            if isinstance(pins, list):
                out += [p for p in pins if isinstance(p, dict)]
        return out

    def log(self) -> list[dict]:
        out = []
        for led in self.ledgers:
            entries = led["data"].get("decision_log")
            if isinstance(entries, list):
                out += [e for e in entries if isinstance(e, dict)]
        return out

    def digest(self) -> dict:
        """What the report carries about the run itself, so a FAIL is diagnosable without a rerun."""
        return {
            "wall_seconds": round(self.wall_seconds, 1),
            "num_turns": self.result.get("num_turns"),
            "cost_usd": self.result.get("total_cost_usd"),
            "is_error": self.result.get("is_error"),
            "stop_reason": self.result.get("stop_reason"),
            "tools_called": [t["name"] for t in self.tools],
            "tool_errors": self.tool_errors,
            "mcp_servers": self.init.get("mcp_servers"),
            "ledgers_written": [led["path"] for led in self.ledgers],
            "pins_written": len(self.pins()),
            "log_entries": len(self.log()),
        }


def _check(describe: str):
    """Decorator-free helper: attach the human-readable predicate to the callable."""
    def wrap(fn):
        fn.describe = describe
        return fn
    return wrap


def pin(min_count: int = 1, **want) -> object:
    """At least `min_count` pins match every `want` key. `provenance` matches any element's
    `source`; every other key matches the pin field exactly. `confidence` may be a tuple, because
    two of the assertions below say "inferred/ambiguous" and narrowing that to one value would be
    the harness inventing a requirement the eval did not state."""
    def matches(p: dict) -> bool:
        for key, value in want.items():
            if key == "provenance":
                sources = [s.get("source") for s in p.get("provenance") or []
                           if isinstance(s, dict)]
                if value not in sources:
                    return False
            else:
                found = p.get(key)
                if isinstance(value, tuple):
                    if found not in value:
                        return False
                elif found != value:
                    return False
        return True

    @_check(f"≥{min_count} pin(s) with " + ", ".join(f"{k}={v!r}" for k, v in want.items()))
    def run_check(run: Run) -> tuple[bool, str]:
        hits = [p for p in run.pins() if matches(p)]
        seen = [{"kind": p.get("kind"), "state": p.get("state"),
                 "confidence": p.get("confidence")} for p in run.pins()]
        return (len(hits) >= min_count,
                f"{len(hits)} matching of {len(run.pins())} pin(s); saw {seen[:8]}")
    return run_check


def no_pin(**want) -> object:
    """No pin matches — the mirror of `pin`, for the assertions that forbid a state."""
    inner = pin(min_count=1, **want)

    @_check("NO pin with " + ", ".join(f"{k}={v!r}" for k, v in want.items()))
    def run_check(run: Run) -> tuple[bool, str]:
        ok, detail = inner(run)
        return (not ok, detail)
    return run_check


def log_entry(prefix: str, min_count: int = 1) -> object:
    """At least `min_count` append-only `decision_log` entries carry this id prefix. The prefixes
    are the ledger's own closed vocabulary (`ledger.LOG_ENTRY_PREFIXES`): `ev_` DecisionEvent,
    `chl_` ChallengeEvent, `stl_` settlement, `cas_` cascade, `rev_`/`xdr_`/`fal_` the arcs."""
    @_check(f"≥{min_count} decision_log entr(y/ies) with id prefix {prefix!r}")
    def run_check(run: Run) -> tuple[bool, str]:
        hits = [e for e in run.log() if str(e.get("id", "")).startswith(prefix)]
        ids = [str(e.get("id", "")) for e in run.log()]
        return len(hits) >= min_count, f"{len(hits)} matching of {len(ids)} entr(y/ies); saw {ids[:8]}"
    return run_check


def no_log_entry(prefix: str) -> object:
    @_check(f"NO decision_log entry with id prefix {prefix!r}")
    def run_check(run: Run) -> tuple[bool, str]:
        hits = [e for e in run.log() if str(e.get("id", "")).startswith(prefix)]
        return not hits, f"{len(hits)} entr(y/ies) with prefix {prefix!r}"
    return run_check


def tool_used(pattern: str) -> object:
    """A tool whose name matches `pattern` was called. Matched against the name the HOST reports,
    so an MCP tool is `mcp__keel__ledger_add_pin` and a built-in is `Edit`."""
    rx = re.compile(pattern)

    @_check(f"a tool matching /{pattern}/ was called")
    def run_check(run: Run) -> tuple[bool, str]:
        hits = [t["name"] for t in run.tools if rx.search(t["name"])]
        return bool(hits), f"matched {sorted(set(hits))} of {sorted(set(t['name'] for t in run.tools))}"
    return run_check


def tool_absent(pattern: str) -> object:
    rx = re.compile(pattern)

    @_check(f"NO tool matching /{pattern}/ was called")
    def run_check(run: Run) -> tuple[bool, str]:
        hits = [t["name"] for t in run.tools if rx.search(t["name"])]
        return not hits, f"matched {sorted(set(hits))}"
    return run_check


def tool_before(earlier: str, later: str) -> object:
    """The first call matching `earlier` precedes the first matching `later`. The `earlier` tool
    must actually have been called: an assertion that A comes before B is not satisfied by never
    doing A, which is the reading that would let "pins problems before proposing any fix" pass on
    a run that pinned nothing."""
    rx_a, rx_b = re.compile(earlier), re.compile(later)

    @_check(f"first /{earlier}/ call precedes first /{later}/ call (and /{earlier}/ happened)")
    def run_check(run: Run) -> tuple[bool, str]:
        first_a = next((t["seq"] for t in run.tools if rx_a.search(t["name"])), None)
        first_b = next((t["seq"] for t in run.tools if rx_b.search(t["name"])), None)
        if first_a is None:
            return False, f"/{earlier}/ was never called"
        if first_b is None:
            return True, f"/{earlier}/ at #{first_a}; /{later}/ never called"
        return first_a < first_b, f"/{earlier}/ at #{first_a}, /{later}/ at #{first_b}"
    return run_check


def file_untouched(pattern: str) -> object:
    """No write tool was pointed at a path matching `pattern`. Reads the tool INPUT, not the name,
    which is the only way "never hand-edits ledger.json" becomes a fact: the forbidden thing is not
    calling `Edit`, it is calling `Edit` on that file."""
    rx = re.compile(pattern)
    writers = re.compile(r"^(Edit|Write|NotebookEdit)$")

    @_check(f"no Edit/Write/NotebookEdit aimed at a path matching /{pattern}/")
    def run_check(run: Run) -> tuple[bool, str]:
        hits = [t["input"].get("file_path") for t in run.tools
                if writers.match(t["name"]) and rx.search(str(t["input"].get("file_path") or ""))]
        return not hits, f"write tools aimed at {hits}"
    return run_check


def all_of(*checks) -> object:
    """Every sub-check holds. For an assertion that states two things — "operates through the MCP
    tools AND never hand-edits the file" — because splitting it into two report lines would make
    the report disagree with the eval about how many assertions there are."""
    @_check(" AND ".join(c.describe for c in checks))
    def run_check(run: Run) -> tuple[bool, str]:
        details, ok = [], True
        for check in checks:
            passed, detail = check(run)
            ok = ok and passed
            details.append(f"[{'ok' if passed else 'NO'}] {detail}")
        return ok, " · ".join(details)
    return run_check


def artifact(*names: str) -> object:
    """A file matching any of these globs exists under the working directory after the run."""
    @_check("an artifact matching " + " or ".join(names) + " exists")
    def run_check(run: Run) -> tuple[bool, str]:
        found = [str(p.relative_to(run.workdir))
                 for name in names for p in run.workdir.rglob(name)]
        return bool(found), f"found {found[:6]}"
    return run_check


#: Machine checks, keyed by `(skill, case id, the assertion VERBATIM)`.
#:
#: Keyed on the prose rather than on an index, and the key is checked by `--validate`, because the
#: two ways this table can rot are opposite and both silent. An index key survives a reworded
#: assertion and starts checking the wrong sentence; a prose key that nobody validates stops
#: matching and the assertion quietly becomes `manual`. Keying on the prose AND gating the keys
#: makes the second failure loud and the first impossible.
#:
#: What is deliberately NOT here: every assertion about compression, phrasing, refusal-with-a-
#: reason, or "names X as the failure". Those are real requirements and no artifact carries them,
#: so they report `manual` — the honest answer — rather than a regex over the transcript pretending
#: to be a check. The split is roughly the package's own: what the ledger records is checkable,
#: what the agent *said* is not.
CHECKS: dict[tuple[str, int, str], object] = {
    # --- codebase-rescue: the as-is is built and pinned before anything is edited --------------
    ("codebase-rescue", 1, "builds the as-is map/graph and pins problems before proposing any fix"):
        tool_before(r"graph|understand|ledger_add_pin", r"^(Edit|Write|NotebookEdit)$"),
    ("codebase-rescue", 1,
     "runs contract-reconciliation and surfaces DB<->API<->frontend shape mismatches as "
     "contract_mismatch pins"):
        pin(kind="contract_mismatch"),
    ("codebase-rescue", 1, "marks intentional stubs as incompleteness work items, not defects"):
        pin(kind="incompleteness"),
    ("codebase-rescue", 1, "does not edit code before the interview elects the to-be"):
        tool_absent(r"^(Edit|Write|NotebookEdit)$"),
    ("codebase-rescue", 4,
     "materializes a forced assumption as a pin with confidence inferred/ambiguous and provenance "
     "source: agent_assumption"):
        pin(confidence=("inferred", "ambiguous"), provenance="agent_assumption"),
    ("codebase-rescue", 4, "does not edit code before the elected to-be exists"):
        tool_absent(r"^(Edit|Write|NotebookEdit)$"),
    ("codebase-rescue", 5,
     "emits a ChallengeEvent and reopens the pin (challenged) rather than proceeding to "
     "remediation"):
        log_entry("chl_"),
    ("codebase-rescue", 5,
     "the challenger only reopens — it never writes a DecisionEvent or edits code"):
        no_log_entry("ev_"),

    # --- greenfield-forge: the fork is a pin before it is a file ------------------------------
    ("greenfield-forge", 1,
     "frames testable acceptance criteria and open_decision pins from the decision-catalog "
     "(pruned to a web SaaS) before scaffolding"):
        pin(kind="acceptance_criterion"),
    ("greenfield-forge", 2,
     "elects tenancy model, datastore, API style, and contract location as open_decisions"):
        pin(kind="open_decision", min_count=4),
    ("greenfield-forge", 4, "commits each choice as a DecisionEvent with a flip_criteria"):
        log_entry("ev_"),
    ("greenfield-forge", 5,
     "emits a ChallengeEvent and reopens the pin (challenged) instead of building the contract "
     "on it"):
        log_entry("chl_"),
    ("greenfield-forge", 6, "materializes the load-bearing forks as open_decision pins from the catalog"):
        pin(kind="open_decision"),
    ("greenfield-forge", 6,
     "where forced to assume, surfaces it as a pin with provenance source: agent_assumption and "
     "confidence inferred/ambiguous"):
        pin(confidence=("inferred", "ambiguous"), provenance="agent_assumption"),

    # --- systematic-debugging: the root cause lands in the pin, not the commit message ---------
    ("systematic-debugging", 1,
     "opens a defect pin (ledger_add_pin) whose as_is carries the observed wrong behavior and the "
     "Phase 1 command as its reproduction"):
        pin(kind="defect"),
    ("systematic-debugging", 2,
     "does not call ledger_resolve; if pressed, reaches for ledger_mark_correctness_unknown with "
     "what was attempted and what blocked it"):
        tool_absent(rf"{MCP_PREFIX}ledger_resolve$"),
    ("systematic-debugging", 2, "refuses to close the defect pin while it cannot say why the code was wrong"):
        no_pin(kind="defect", state="resolved"),

    # --- test-driven-development: the red step IS the pin --------------------------------------
    ("test-driven-development", 1,
     "reads the existing acceptance_criterion pin (ledger_summary) before writing any code"):
        tool_before(rf"{MCP_PREFIX}ledger_summary", r"^(Edit|Write|NotebookEdit)$"),
    ("test-driven-development", 2,
     "does NOT self-elect an acceptance_criterion to justify existing code; surfaces it via "
     "ledger_add_pin as an open_decision with confidence inferred"):
        pin(kind="open_decision", confidence="inferred"),
    ("test-driven-development", 3,
     "the acceptance_criterion pin still exists before the code — no build without an elected "
     "outcome"):
        pin(kind="acceptance_criterion"),
    ("test-driven-development", 4,
     "does not write code for the feature before a testable acceptance_criterion exists"):
        tool_before(rf"{MCP_PREFIX}ledger_add_pin", r"^(Edit|Write|NotebookEdit)$"),

    # --- verification-before-completion: resolved means observed ------------------------------
    ("verification-before-completion", 1,
     "calls ledger_resolve only after observing, passing the observation as evidence and "
     'rung="observed"'):
        tool_used(rf"{MCP_PREFIX}ledger_resolve$"),
    ("verification-before-completion", 2, "does not move the pin to resolved; it stays needs_input"):
        no_pin(state="resolved"),
    ("verification-before-completion", 2,
     "surfaces the unverified remainder as an incompleteness pin instead of dropping it"):
        pin(kind="incompleteness"),
    ("verification-before-completion", 3,
     "calls ledger_mark_correctness_unknown carrying what was attempted and what blocked it, not "
     "ledger_resolve"):
        tool_used(rf"{MCP_PREFIX}ledger_mark_correctness_unknown"),

    # --- using-the-ledger: the tools are the only door ----------------------------------------
    ("using-the-ledger", 1,
     "operates through the ledger_* MCP tools (ledger_add_pin, ledger_summary) and never "
     "hand-edits ledger.json"):
        all_of(tool_used(rf"{MCP_PREFIX}ledger_"), file_untouched(r"ledger\.json$")),
    ("using-the-ledger", 2,
     "records only after the human accepted, with ledger_record_policy, quoting the user verbatim "
     "(or letting the server elicit)"):
        tool_used(rf"{MCP_PREFIX}ledger_record_policy"),
    ("using-the-ledger", 3, "uses ledger_record_decision to write the DecisionEvent and move the pin to decided"):
        log_entry("ev_"),
    ("using-the-ledger", 4, "reads through ledger_summary rather than opening files directly"):
        tool_used(rf"{MCP_PREFIX}ledger_summary"),
}


# ---------------------------------------------------------------------------
# --validate
# ---------------------------------------------------------------------------


def validate(paths: list[pathlib.Path]) -> int:
    problems: list[str] = []
    total_cases = 0
    #: every (skill, id, assertion) the corpus actually contains, so the CHECKS keys can be held
    #: to it. A check keyed to a sentence nobody wrote runs on nothing and reports nothing.
    corpus: set[tuple[str, object, str]] = set()
    for path in paths:
        rel = path.relative_to(ROOT)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel}: invalid JSON ({exc})")
            continue
        skill_dir = path.parent.parent.name
        if data.get("skill_name") != skill_dir:
            problems.append(f"{rel}: skill_name {data.get('skill_name')!r} != dir {skill_dir!r}")
        cases = data.get("evals", [])
        if not cases:
            problems.append(f"{rel}: no eval cases")
        seen_ids = set()
        for case in cases:
            cid = case.get("id")
            label = f"{rel}#'{cid}'"
            for field in REQUIRED_CASE_FIELDS:
                if not case.get(field):
                    problems.append(f"{label}: missing/empty {field}")
            if cid in seen_ids:
                problems.append(f"{label}: duplicate id")
            seen_ids.add(cid)
            for fixture in case.get("files", []):
                if not (path.parent / fixture).exists():
                    problems.append(f"{label}: listed file {fixture!r} does not exist")
            for assertion in case.get("assertions", []):
                corpus.add((skill_dir, cid, assertion))
        total_cases += len(cases)

    # The CHECKS table is validated only over the eval files actually in scope, so `--skill X
    # --validate` does not report every other skill's checks as orphans.
    in_scope = {skill for skill, _, _ in corpus}
    orphans = sorted(key for key in CHECKS if key[0] in in_scope and key not in corpus)
    for skill, cid, assertion in orphans:
        problems.append(f"CHECKS[{skill!r}, {cid}]: no such assertion — {assertion!r}. The eval was "
                        f"reworded and this machine check stopped running; re-key it or drop it.")

    for line in problems:
        print(f"INVALID  {line}")
    checked = sum(1 for key in CHECKS if key in corpus)
    print(f"\nrun_evals --validate: {len(paths)} eval file(s), {total_cases} case(s), "
          f"{len(corpus)} assertion(s) of which {checked} carry a machine check, "
          f"{len(problems)} problem(s)")
    return EXIT_FAILED if problems else EXIT_OK


# ---------------------------------------------------------------------------
# --run (legacy, host-agnostic): the LLM judge
# ---------------------------------------------------------------------------


def call_runner(runner: str, prompt: str, cwd: pathlib.Path, timeout: int) -> str:
    cmd = shlex.split(runner) + [prompt]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"runner exited {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout


def judge(runner: str, transcript: str, assertion: str, cwd: pathlib.Path,
          timeout: int) -> dict:
    raw = call_runner(runner, JUDGE_PROMPT.format(transcript=transcript, assertion=assertion),
                      cwd, timeout)
    # the judge is told to emit a lone JSON object; tolerate surrounding prose
    start, end = raw.find("{"), raw.rfind("}")
    try:
        verdict = json.loads(raw[start:end + 1])
        assert verdict.get("verdict") in ("PASS", "FAIL")
        return verdict
    except Exception:
        return {"verdict": "FAIL", "reason": f"unparseable judge output: {raw[:200]!r}"}


def run(paths: list[pathlib.Path], runner: str, fixture: pathlib.Path,
        report_path: pathlib.Path, timeout: int) -> int:
    report: dict = {"mode": "run", "runner": runner, "fixture": str(fixture), "skills": {}}
    failed = 0
    for path in paths:
        skill = path.parent.parent.name
        data = json.loads(path.read_text(encoding="utf-8"))
        results = []
        for case in data.get("evals", []):
            print(f"[{skill}] case {case['id']}: running…", flush=True)
            try:
                transcript = call_runner(runner, case["prompt"], fixture, timeout)
            except Exception as exc:
                results.append({"id": case["id"], "error": str(exc)})
                failed += 1
                continue
            verdicts = []
            for assertion in case["assertions"]:
                verdict = judge(runner, transcript, assertion, fixture, timeout)
                verdicts.append({"assertion": assertion, **verdict})
                mark = "PASS" if verdict["verdict"] == "PASS" else "FAIL"
                print(f"    {mark} {assertion}")
                if verdict["verdict"] != "PASS":
                    failed += 1
            results.append({"id": case["id"], "assertions": verdicts})
        report["skills"][skill] = results

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nrun_evals --run: report written to {report_path} — "
          f"{failed} failing assertion(s)/case error(s)")
    return EXIT_FAILED if failed else EXIT_OK


# ---------------------------------------------------------------------------
# --execute: the real run, against the built plugin, checked against artifacts
# ---------------------------------------------------------------------------


def plugin_for(skill: str) -> pathlib.Path | None:
    """The BUILT plugin directory that carries this skill. Read off `plugins/` rather than kept in
    a table here: which plugin a skill lands in is `scripts/build.py`'s decision, and a second copy
    of that mapping is the drift this repo's gates exist to catch."""
    for candidate in sorted((ROOT / "plugins").glob("*/skills/*")):
        if candidate.name == skill and candidate.is_dir():
            return candidate.parent.parent
    return None


def preflight(executable: str, skills: list[str], probe_timeout: int) -> tuple[bool, str, dict]:
    """Can this machine host a behavioral run? Returns (ok, reason, detail).

    Three questions, asked in the order that makes the answer cheapest and the reason precise. CI
    fails the third and only the third, and the message it prints is the runner's own — the point
    of a distinct exit code is wasted if the operator still has to guess which of the three it was.
    """
    path = shutil.which(executable)
    if not path:
        return False, (f"no {executable!r} on PATH — a behavioral eval executes a real agent; "
                       f"there is no pretend mode"), {"executable": executable}

    missing = [s for s in skills if plugin_for(s) is None]
    if missing:
        return False, (f"no built plugin carries {missing} — run `python scripts/build.py` first. "
                       f"Executing without the plugin would test the host's own defaults and "
                       f"report the result as this package's behavior"), {"missing_plugins": missing}

    # Credentials. This is the one CI cannot hold, and it is why the CI job is advisory: the probe
    # is a real API call, so a machine without a key or with an expired session fails HERE, loudly,
    # instead of failing every case with an error that reads like a skill regression.
    #
    # The prompt goes over STDIN, not argv, and that is a fix rather than a style: `--tools` and
    # `--allowedTools` are VARIADIC in this CLI (`<tools...>`), so a trailing positional prompt is
    # swallowed as another tool name and the run dies with "Input must be provided either through
    # stdin or as a prompt argument" — an argv bug that reads exactly like a credentials failure,
    # which is the one thing this function exists to distinguish.
    probe = [executable, "-p", "--output-format", "json", "--no-session-persistence", "--tools", ""]
    try:
        proc = subprocess.run(probe, input="reply with exactly: OK", capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=probe_timeout,
                              cwd=str(ROOT))
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{executable} could not be probed: {exc}", {"probe": probe}
    if proc.returncode != 0:
        head = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, (f"{executable} exited {proc.returncode} on a trivial prompt — most often "
                       f"absent or expired credentials: {head[:1]}"), {"probe": probe}
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False, f"{executable} returned unparseable JSON on the probe", {"probe": probe}
    if answer.get("is_error"):
        return False, f"{executable} reported is_error on the probe: {answer.get('result')!r}", {}
    return True, "", {"executable": path, "model": answer.get("modelUsage") and
                      sorted(answer["modelUsage"]) or None}


def build_command(executable: str, plugin: pathlib.Path, args) -> list[str]:
    """The headless invocation, verified at the consumer (`claude --help`, CLI 2.x) rather than
    remembered. Each flag is here for a stated reason:

      -p / --output-format stream-json / --verbose
          `-p` is headless; `stream-json` is the ONLY format that carries tool_use blocks, and the
          tool calls are half of what the checks read. `--verbose` is required alongside it.
      --plugin-dir plugins/<plugin>
          loads the BUILT plugin for this session only — skills, hooks and the plugin-root
          `.mcp.json` (so the `keel` MCP server, hence the `ledger_*` tools). Without it the run
          measures Claude Code, not Keel.
      --setting-sources ''
          the developer's own user/project settings are not part of what a user installs, and a
          personal skill or permission rule leaking in makes the result unreproducible.
      --no-session-persistence
          an eval is not a conversation anyone resumes.
      --max-budget-usd
          a runaway case is a cost, not a finding. The cap is per case and declared in the report.

    `--max-turns` is deliberately absent: this CLI has no such flag (checked, not assumed), so the
    bound is the budget and the timeout.

    The PROMPT is not here. It goes over stdin, because `--allowedTools` is variadic and would eat
    a trailing positional — see `preflight` for the failure that taught this.
    """
    cmd = [executable, "-p", "--output-format", "stream-json", "--verbose",
           "--plugin-dir", str(plugin), "--no-session-persistence",
           "--setting-sources", "", "--max-budget-usd", str(args.max_budget_usd)]
    if args.model:
        cmd += ["--model", args.model]
    if args.permission_mode:
        cmd += ["--permission-mode", args.permission_mode]
    if args.allowed_tools:                       # variadic: kept LAST, and the prompt is on stdin
        cmd += ["--allowedTools"] + shlex.split(args.allowed_tools)
    return cmd


def execute_case(executable: str, skill: str, plugin: pathlib.Path, case: dict,
                 fixture: pathlib.Path | None, workroot: pathlib.Path, args) -> Run:
    """One case, in its own copy of the fixture (or its own empty directory when none is declared).

    The copy is not hygiene, it is the measurement: the checks read the `ledger.json` the run
    WROTE, so a shared directory would let case 2 pass on case 1's pins. It also keeps the
    fixture in `tests/` unmodified, which `tests/test_fixture_slop_repo.py` depends on.
    """
    # Namespaced by SKILL as well as case id: nine eval files each number their cases from 1, so a
    # bare `case-1` would have nine skills sharing one directory — and sharing one ledger, which is
    # the exact cross-contamination the per-case copy exists to prevent.
    workdir = workroot / f"{skill}-case-{case['id']}"
    if fixture is None:
        workdir.mkdir(parents=True)
    else:
        shutil.copytree(fixture, workdir)
    cmd = build_command(executable, plugin, args)
    started = time.monotonic()
    proc = subprocess.run(cmd, input=case["prompt"], cwd=str(workdir), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=args.timeout)
    wall = time.monotonic() - started
    events, result = [], {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        if event.get("type") == "result":
            result = event
    if not events and proc.returncode != 0:
        raise RuntimeError(f"{executable} exited {proc.returncode}: "
                           f"{(proc.stderr or '').strip()[:400]}")
    return Run(workdir, events, result, wall)


def resolve_assertions(skill: str, case: dict, run_obj: Run) -> list[dict]:
    """Every assertion of one case, resolved. Three outcomes and no fourth: `pass`, `fail`, or
    `manual` — a machine check exists and held, a machine check exists and did not, or none
    exists. `manual` is a report, never a silence and never a pass."""
    out = []
    for assertion in case["assertions"]:
        check = CHECKS.get((skill, case["id"], assertion))
        if check is None:
            out.append({"assertion": assertion, "verdict": "manual",
                        "reason": "no machine check declared for this assertion — a human reads "
                                  "the transcript, or nobody does"})
            continue
        try:
            ok, detail = check(run_obj)
        except Exception as exc:                                   # a broken check is a FAIL here
            ok, detail = False, f"check raised {type(exc).__name__}: {exc}"
        out.append({"assertion": assertion, "verdict": "pass" if ok else "fail",
                    "checked": check.describe, "evidence": detail})
    return out


def execute(paths: list[pathlib.Path], fixture_override: str, report_path: pathlib.Path,
            args) -> int:
    import tempfile

    skills = [p.parent.parent.name for p in paths]
    ok, reason, detail = preflight(args.executable, skills, args.probe_timeout)
    report: dict = {"mode": "execute", "executable": args.executable,
                    "model": args.model or "(host default)", "skills": {}}
    if not ok:
        report["runner_unavailable"] = reason
        report["detail"] = detail
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"run_evals --execute: RUNNER UNAVAILABLE — {reason}", file=sys.stderr)
        print(f"  (report written to {report_path}; exit {EXIT_NO_RUNNER} means 'this machine "
              f"cannot host a run', NOT 'the skills failed')", file=sys.stderr)
        return EXIT_NO_RUNNER

    failed = passed = manual = 0
    workroot = pathlib.Path(tempfile.mkdtemp(prefix="keel-evals-"))
    print(f"run_evals --execute: workdirs under {workroot}", flush=True)
    for path in paths:
        skill = path.parent.parent.name
        data = json.loads(path.read_text(encoding="utf-8"))
        plugin = plugin_for(skill)
        # An eval file with no `fixture` gets an EMPTY directory, and for the two that declare none
        # that is the correct fixture rather than a fallback: greenfield-forge's as-is starts empty
        # by definition, and screenshot-to-code builds from an image, not from a tree. What is NOT
        # correct is what the obvious `ROOT / (data.get("fixture") or "")` does — it resolves to the
        # repo root, so every case would copy all of Keel and run the agent inside a copy of the
        # package under test.
        declared = fixture_override or data.get("fixture")
        fixture = (pathlib.Path(declared) if pathlib.Path(declared).is_absolute()
                   else ROOT / declared).resolve() if declared else None
        results = []
        for case in data.get("evals", []):
            if args.case and case["id"] != args.case:
                continue
            if args.checked_only and not any((skill, case["id"], a) in CHECKS
                                             for a in case["assertions"]):
                continue
            if fixture is not None and not fixture.is_dir():
                results.append({"id": case["id"],
                                "error": f"fixture {fixture} does not exist"})
                failed += 1
                continue
            print(f"[{skill}] case {case['id']} (plugin {plugin.name}, "
                  f"fixture {fixture.name if fixture else '(empty dir)'})…", flush=True)
            try:
                run_obj = execute_case(args.executable, skill, plugin, case, fixture,
                                       workroot, args)
            except Exception as exc:
                print(f"    ERROR {exc}")
                results.append({"id": case["id"], "error": str(exc)})
                failed += 1
                continue
            verdicts = resolve_assertions(skill, case, run_obj)
            if args.judge:
                transcript = _transcript_text(run_obj)
                for entry in verdicts:
                    if entry["verdict"] != "manual":
                        continue
                    advisory = judge(f"{args.executable} -p", transcript, entry["assertion"],
                                     run_obj.workdir, args.timeout)
                    entry["advisory_judge"] = advisory   # evidence; never moves the exit code
            for entry in verdicts:
                mark = {"pass": "PASS", "fail": "FAIL", "manual": "MANL"}[entry["verdict"]]
                print(f"    {mark} {entry['assertion']}")
                if entry["verdict"] != "manual":
                    print(f"         checked: {entry['checked']}\n"
                          f"         evidence: {entry['evidence']}")
                failed += entry["verdict"] == "fail"
                passed += entry["verdict"] == "pass"
                manual += entry["verdict"] == "manual"
            results.append({"id": case["id"], "run": run_obj.digest(), "assertions": verdicts})
        report["skills"][skill] = results

    report["totals"] = {"passed": passed, "failed": failed, "manual": manual}
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nrun_evals --execute: {passed} passed · {failed} failed · {manual} manual "
          f"(no machine check declared) — report at {report_path}")
    if manual:
        print(f"  {manual} assertion(s) are NOT evidence of anything until a human reads them. "
              f"That is the honest state of the corpus, not a pass.")
    return EXIT_FAILED if failed else EXIT_OK


def _transcript_text(run_obj: Run) -> str:
    """A flat rendering for the advisory judge: the assistant text plus the tool calls, in order.
    The tool calls are included because a judge shown only prose judges only prose."""
    lines = [f"[tool] {t['name']} {json.dumps(t['input'], ensure_ascii=False)[:300]}"
             for t in run_obj.tools]
    return run_obj.text + "\n\n=== TOOL CALLS ===\n" + "\n".join(lines)


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validate", action="store_true",
                        help="structural gate only (default; CI-safe, blocking)")
    parser.add_argument("--execute", action="store_true",
                        help="run each case against Claude Code with the built plugin loaded, and "
                             "check assertions against the artifacts the run produced")
    parser.add_argument("--run", action="store_true",
                        help="legacy host-agnostic execution with --runner (LLM judge only)")
    parser.add_argument("--runner", default="",
                        help='--run only: agent command the prompt is appended to, e.g. "claude -p"')
    parser.add_argument("--executable", default="claude",
                        help="--execute: the Claude Code binary (default: claude)")
    parser.add_argument("--fixture", default="",
                        help="working directory template; --execute defaults to each evals.json's "
                             "own `fixture` field")
    parser.add_argument("--skill", default="", help="only this skill (dir name)")
    parser.add_argument("--case", type=int, default=0, help="--execute: only this case id")
    parser.add_argument("--report", default="eval-report.json", help="report path")
    parser.add_argument("--timeout", type=int, default=1800, help="per-case timeout, seconds")
    parser.add_argument("--probe-timeout", type=int, default=120,
                        help="--execute: timeout for the credential probe, seconds")
    parser.add_argument("--model", default="", help="--execute: model alias passed to --model")
    parser.add_argument("--permission-mode", default="",
                        help="--execute: passed straight to --permission-mode. Left EMPTY by "
                             "default: an eval that needs the agent to write must be granted that "
                             "deliberately by whoever runs it, on a machine where that is safe")
    parser.add_argument("--allowed-tools", default="",
                        help="--execute: passed to --allowedTools (e.g. 'Read Grep Glob')")
    parser.add_argument("--max-budget-usd", type=float, default=5.0,
                        help="--execute: per-case spend cap")
    parser.add_argument("--checked-only", action="store_true",
                        help="--execute: skip cases where no assertion carries a machine check. "
                             "An unattended run of such a case spends real money to print "
                             "`manual` — it is a case for a human at a terminal, not for CI")
    parser.add_argument("--judge", action="store_true",
                        help="--execute: also ask an LLM judge about the `manual` assertions. "
                             "ADVISORY — recorded in the report, never moves the exit code")
    args = parser.parse_args()

    if args.execute and args.run:
        print("--execute and --run are two different modes; pick one", file=sys.stderr)
        return EXIT_USAGE

    paths = find_eval_files()
    if args.skill:
        paths = [p for p in paths if p.parent.parent.name == args.skill]
        if not paths:
            print(f"no evals for skill {args.skill!r}", file=sys.stderr)
            return EXIT_USAGE

    if args.execute:
        return execute(paths, args.fixture, pathlib.Path(args.report), args)

    if args.run:
        if not args.runner or not args.fixture:
            print("--run needs --runner and --fixture: behavioral evals execute a real agent "
                  "on a real repo — there is no pretend mode.", file=sys.stderr)
            return EXIT_USAGE
        fixture = pathlib.Path(args.fixture).resolve()
        if not fixture.is_dir():
            print(f"fixture dir {fixture} does not exist", file=sys.stderr)
            return EXIT_USAGE
        return run(paths, args.runner, fixture, pathlib.Path(args.report), args.timeout)

    return validate(paths)


if __name__ == "__main__":
    raise SystemExit(main())
