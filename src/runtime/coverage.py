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


def report(present_langs: Iterable[str], report_paths: Iterable[str]) -> dict:
    """The full manifest: what ran, what is missing. The honest answer to 'was this analysed?'."""
    ran = ran_tools(report_paths)
    g = gaps(present_langs, ran)
    return {"ran": sorted(ran), "gaps": g, "gap_count": len(g)}
