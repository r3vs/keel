"""Coverage manifest — which analysis capabilities were EXPECTED, and which actually ran.

The finder toolchain degrades gracefully: a missing tool falls back to model judgment and the run
continues. That is the right posture — a user analysing a Python repo should not be blocked because
they lack a Rust toolchain. But the degrade must never be **silent**, because
`security-sast: 0 defects` from a clean scan and `0 defects` from *semgrep never ran* are the same
output — and the second is this package's own signature failure: it *looks* analysed when it was not.
"A rule with no gate rots" applies to the toolchain's own coverage.

This module closes that gap. From the languages present (tokei) it derives the analysis
**capabilities** expected for those stacks, compares them against the tools that actually emitted a
report, and turns each gap into an `incompleteness` pin (`kind_detail: coverage-gap`) — a visible
fact, not a silent zero. A deterministic module that could not run its engine is not *clean*; it is
*unchecked*, and the ledger says so. The pin then flows through the interview like any other: the
human elects to close it (install the tool, re-run) or accept it (out of scope) — never a default
that hides it.

Design choices, stated:
- **Capabilities, not tools.** "type-check Python" is satisfied by mypy OR pyright; tracking the
  capability avoids a false gap when the user ran the other one.
- **Only REQUIRED finders are tracked.** Opt-in / costly tools (mutation testing, licensed graph
  engines) are deliberately absent — their absence is a *choice*, not a coverage gap.
- **`present_langs` is passed in** (from tokei), not shelled out, so this module stays stdlib-only
  and pure — the same discipline as `findings.py`.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterable, Optional

_ANY = "*"  # language-agnostic: expected whenever there is any code at all

# capability -> (stacks it applies to, tools that satisfy it, severity of a gap).
# A gap is surfaced when the capability applies to a present stack and NONE of its tools ran.
# Security + type signal are `high` (a silent hole there is the costly one); the rest are `medium`.
CAPABILITIES = (
    {"id": "sast",              "stacks": _ANY,                        "tools": ("semgrep", "opengrep"),        "severity": "high"},
    {"id": "secrets",           "stacks": _ANY,                        "tools": ("gitleaks",),                  "severity": "high"},
    {"id": "dependency-vulns",  "stacks": _ANY,                        "tools": ("osv-scanner", "trivy"),       "severity": "high"},
    {"id": "complexity",        "stacks": _ANY,                        "tools": ("lizard", "scc"),              "severity": "medium"},
    {"id": "duplication",       "stacks": _ANY,                        "tools": ("jscpd",),                     "severity": "medium"},
    {"id": "type-check",        "stacks": ("Python",),                 "tools": ("mypy", "pyright"),            "severity": "high"},
    {"id": "type-check",        "stacks": ("TypeScript",),             "tools": ("tsc", "typescript"),          "severity": "high"},
    {"id": "type-check",        "stacks": ("Rust",),                   "tools": ("cargo-check", "cargo", "clippy"), "severity": "high"},
    {"id": "type-check",        "stacks": ("Go",),                     "tools": ("go-vet", "govet", "go"),      "severity": "high"},
    {"id": "dead-code",         "stacks": ("Python",),                 "tools": ("vulture",),                   "severity": "medium"},
    {"id": "dead-code",         "stacks": ("JavaScript", "TypeScript"),"tools": ("knip",),                     "severity": "medium"},
    {"id": "dead-code",         "stacks": ("Go",),                     "tools": ("deadcode",),                  "severity": "medium"},
    {"id": "dead-code",         "stacks": ("Rust",),                   "tools": ("cargo-udeps",),               "severity": "medium"},
    {"id": "architecture-fitness", "stacks": ("Python",),             "tools": ("import-linter", "lint-imports"), "severity": "medium"},
    {"id": "architecture-fitness", "stacks": ("JavaScript", "TypeScript"), "tools": ("dependency-cruiser", "depcruise", "ts-arch"), "severity": "medium"},
)


def ran_tools(report_paths: Iterable[str]) -> set[str]:
    """The set of tool names that actually produced a report (lowercased).

    SARIF names the tool in run.tool.driver.name; OSV-scanner JSON has no driver, so a `results`-only
    file is attributed to osv-scanner. A malformed/absent file contributes nothing — it did not run.
    """
    tools: set[str] = set()
    for p in report_paths:
        try:
            data = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        runs = data.get("runs")
        if isinstance(runs, list):
            for run in runs:
                name = (run.get("tool", {}) or {}).get("driver", {}).get("name")
                if name:
                    tools.add(name.strip().lower())
        elif "results" in data:                         # OSV-scanner shape
            tools.add("osv-scanner")
    return tools


def gaps(present_langs: Iterable[str], ran: Iterable[str]) -> list[dict]:
    """Capabilities that apply to a present stack but which NO tool covered.

    Returns [{capability, stacks, tools, severity}], one per uncovered (capability, applicable-stack)
    — deterministic, no guessing: it is presence of a report or its absence, nothing in between.
    """
    present = {l.strip() for l in present_langs if l and l.strip()}
    have = {t.strip().lower() for t in ran}
    out: list[dict] = []
    for cap in CAPABILITIES:
        stacks = cap["stacks"]
        applicable = present if stacks == _ANY else (set(stacks) & present)
        if stacks != _ANY and not applicable:
            continue                                    # capability's language isn't in the repo
        if any(t in have for t in cap["tools"]):
            continue                                    # covered
        out.append({
            "capability": cap["id"],
            "stacks": "any" if stacks == _ANY else sorted(applicable),
            "tools": list(cap["tools"]),
            "severity": cap["severity"],
        })
    return out


def to_pins(ledger, gap_list: list[dict]) -> list[dict]:
    """One `incompleteness` pin per gap. confidence=extracted: the tool's ABSENCE is a fact, not a
    guess. These are `coverage-gap`, not intentional stubs — the map must not render them neutral."""
    pins = []
    for g in gap_list:
        stacks = g["stacks"] if isinstance(g["stacks"], str) else ", ".join(g["stacks"])
        pin = ledger.add_pin(
            kind="incompleteness",
            title=f"coverage gap: {g['capability']} not run ({stacks})",
            severity=g["severity"],
            confidence="extracted",
            provenance=[{"source": "coverage",
                         "detail": f"no report from any of {g['tools']} — "
                                   f"{g['capability']} is UNCHECKED for {stacks}, not clean"}],
            as_is={"description": f"{g['capability']} was not executed for {stacks}: none of "
                                  f"{g['tools']} produced a report. Treat as 'unchecked', not 'clean'.",
                   "coverage_gap": True},
            kind_detail="coverage-gap",
        )
        pins.append(pin)
    return pins


# The module catalogs, vendored beside this runtime by the build (a skill ships as a different
# plugin, so the bytes have to travel). Repo layout is the fallback, exactly as `interview.py`
# resolves its decision catalog — and both are resolved at CALL time, never at import.
_HERE = pathlib.Path(__file__).resolve().parent
_CATALOG_DIRS = (_HERE / "assets" / "modules", _HERE.parent / "skills")


def load_modules(skill: str) -> list[dict]:
    """The modules a skill's catalog declares. Raises with BOTH paths it looked at, never a bare
    `FileNotFoundError` on a path the reader has never seen."""
    for base in _CATALOG_DIRS:
        for candidate in (base / f"{skill}.json", base / skill / "modules.json"):
            if candidate.is_file():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return [m for m in data.get("modules", []) if isinstance(m, dict)]
    looked = ", ".join(str(b) for b in _CATALOG_DIRS)
    raise FileNotFoundError(f"no module catalog for {skill!r}; looked in: {looked}")


def _unrun_pin(module: dict, skill: str, at_commit: str) -> dict:
    """The `ledger_add_pin` payload for an un-run module, composed HERE rather than by the caller.

    The wording is deterministic for the reason every coverage message is: the pin must say the
    module was *not looked at*, never that it *found nothing*, and a payload an agent writes from
    memory is where that distinction quietly inverts. `confidence: extracted` because the absence of
    a run record is a fact about the file; `severity: medium` uniformly, because an unchecked
    surface is not a defect and ranking absences against each other is the trap `memory_audit`
    refuses one register over.
    """
    mid = module.get("module")
    return {
        "kind": "incompleteness",
        "title": f"module not applied: {mid} ({skill}, phase {module.get('phase')})",
        "severity": "medium",
        "confidence": "extracted",
        "kind_detail": "module-unrun",
        "provenance": [{"source": "coverage",
                        "detail": f"no run recorded for {mid} at {at_commit}"}],
        "as_is": {"description": f"{mid} is dispatched by {skill} and no run of it is recorded at "
                                 f"{at_commit}. Treat as 'unchecked', not 'clean': it may have "
                                 f"found nothing and it may never have been applied, and nothing "
                                 f"in the file tells those two apart.",
                  "coverage_gap": True},
    }


def module_gaps(modules: Iterable[dict], ran: dict, *, phases: Optional[Iterable] = None,
                skill: str = "", at_commit: str = "") -> list:
    """Dispatched modules with **no run recorded at this commit** — the empty case, made visible.

    The tool-level check above answers "did the engine run?" for a deterministic module, because a
    report is on disk or it is not. A `type: judgment` module has an agent for an engine and leaves
    no artifact, so its silence was indistinguishable from a clean result — and *guessing* which one
    it was from the absence of findings is precisely the inference this package refuses everywhere
    else. `Ledger.record_run` supplies the missing half; this is the join.

    `phases` narrows the expectation to what was actually in scope (a mode that runs Phase 1 alone
    is not missing Phase 5), and narrowing is the caller's job because the ledger does not know
    which phases a run covered. Pass nothing and every module in the catalog is expected.
    """
    wanted = None if phases is None else {str(p) for p in phases}
    out = []
    for m in modules:
        phase = m.get("phase", m.get("step"))
        if wanted is not None and str(phase) not in wanted:
            continue
        if any(e.get("module") == m.get("id") for e in ran.values()):
            continue
        gap = {"module": m.get("id"), "phase": phase, "type": m.get("type"),
               "reference": m.get("reference"), "engine": m.get("engine")}
        gap["pin"] = _unrun_pin(gap, skill, at_commit)
        out.append(gap)
    return out


def module_report(skill: str, ran: dict, at_commit: str, phases: Optional[Iterable] = None) -> dict:
    """Expected vs applied, for one skill's catalog at one commit — the run register's read side.

    Read-only, like every report in this file: the `pin` payload on each gap is composed here and
    written by whoever holds the ledger, so nothing about "which modules were skipped" is decided by
    a door that could also hide it.
    """
    modules = load_modules(skill)
    considered = [m for m in modules
                  if phases is None or str(m.get("phase", m.get("step"))) in {str(p) for p in phases}]
    gap_list = module_gaps(modules, ran, phases=phases, skill=skill, at_commit=at_commit)
    return {"skill": skill, "at_commit": at_commit,
            "phases": None if phases is None else [str(p) for p in phases],
            "expected": len(considered), "applied": len(considered) - len(gap_list),
            "gaps": gap_list}


def report(present_langs: Iterable[str], report_paths: Iterable[str]) -> dict:
    """The full manifest: what ran, what is missing. The honest answer to 'was this analysed?'."""
    ran = ran_tools(report_paths)
    g = gaps(present_langs, ran)
    return {"ran": sorted(ran), "gaps": g, "gap_count": len(g)}
