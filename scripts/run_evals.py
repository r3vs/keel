#!/usr/bin/env python3
"""Eval harness for the skills' evals/evals.json.

Two modes, honest about what each proves:

  --validate (default; runs in CI)
      Structural gate: every evals.json parses, has the required fields, unique ids,
      non-empty assertions, and a skill_name matching its directory. Proves the specs
      are well-formed — NOT that the skill behaves.

  --run --runner "<cmd>"
      Behavioral execution: pipes each case's prompt to an agent runner (e.g.
      `claude -p` with this plugin installed, cwd = a fixture repo via --fixture),
      captures the transcript, then judges each assertion against it with an
      LLM-as-judge call through the same runner. Emits a per-assertion PASS/FAIL
      JSON report. Requires a real runner + fixture; refuses to pretend otherwise.

Stdlib-only, like every other check in this repo.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED_CASE_FIELDS = ("id", "prompt", "expected_output", "assertions")

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
    return sorted(ROOT.glob("skills/*/evals/evals.json"))


def validate(paths: list[pathlib.Path]) -> int:
    problems: list[str] = []
    total_cases = 0
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
        total_cases += len(cases)

    for line in problems:
        print(f"INVALID  {line}")
    print(f"\nrun_evals --validate: {len(paths)} eval file(s), {total_cases} case(s), "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


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
    report: dict = {"runner": runner, "fixture": str(fixture), "skills": {}}
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
                mark = "✓" if verdict["verdict"] == "PASS" else "✗"
                print(f"    {mark} {assertion}")
                if verdict["verdict"] != "PASS":
                    failed += 1
            results.append({"id": case["id"], "assertions": verdicts})
        report["skills"][skill] = results

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nrun_evals --run: report written to {report_path} — "
          f"{failed} failing assertion(s)/case error(s)")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validate", action="store_true",
                        help="structural gate only (default; CI-safe)")
    parser.add_argument("--run", action="store_true", help="execute cases with --runner")
    parser.add_argument("--runner", default="",
                        help='agent command the prompt is appended to, e.g. "claude -p"')
    parser.add_argument("--fixture", default="",
                        help="working directory for the runner (a real target repo)")
    parser.add_argument("--skill", default="", help="only this skill (dir name)")
    parser.add_argument("--report", default="eval-report.json", help="report path (--run)")
    parser.add_argument("--timeout", type=int, default=1800, help="per-call timeout, seconds")
    args = parser.parse_args()

    paths = find_eval_files()
    if args.skill:
        paths = [p for p in paths if p.parent.parent.name == args.skill]
        if not paths:
            print(f"no evals for skill {args.skill!r}", file=sys.stderr)
            return 2

    if args.run:
        if not args.runner or not args.fixture:
            print("--run needs --runner and --fixture: behavioral evals execute a real agent "
                  "on a real repo — there is no pretend mode.", file=sys.stderr)
            return 2
        fixture = pathlib.Path(args.fixture).resolve()
        if not fixture.is_dir():
            print(f"fixture dir {fixture} does not exist", file=sys.stderr)
            return 2
        return run(paths, args.runner, fixture, pathlib.Path(args.report), args.timeout)

    return validate(paths)


if __name__ == "__main__":
    raise SystemExit(main())
