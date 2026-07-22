"""Design-alignment — the presentation layer's drift, bound to the ledger.

The detection is NOT reinvented. It shells the **Impeccable** detector (pbakaus/impeccable,
Apache-2.0): a no-LLM scanner for AI-slop tells and design-quality / accessibility issues across
HTML / CSS / JSX / TSX / Vue / Svelte. What is ours is the **binding**: each detector hit becomes a
ledger pin — a `design_concern` (or, once a `DESIGN.md` contract is elected, a `contract_mismatch`
against it) — so a frontend design finding flows through the same interview → remediation →
resolve-when-observed machinery as every DB / ORM / API / logic pin, in the one source of truth.
Impeccable's output is a lint report; the ledger is where a decision lives. That difference is the
whole reason we bind rather than install it as a sibling skill (which the self-contained rule forbids
anyway): a design finding that lived only in Impeccable's report would be a stateless twin beside the
single source of truth — the exact divergence this package exists to find.

**Deterministic by construction.** The detector runs no model — WCAG contrast is a computed ratio, an
overused font is a set-membership fact — so its hits are FACTS and carry `confidence: extracted`,
which lets them skip the false-positive gate, exactly like a type error. The *taste* half (Impeccable's
LLM critique) is deliberately NOT run here; it belongs to the reviewer / challenger lens, adapted with
attribution, as judgment pins that DO pass fp-check.

**Degrades, never hard-fails.** If `impeccable` (Node ≥ 22.12) is not runnable, the module reports
`unchecked` rather than a clean bill — a design finder that could not run is not "no slop", it is "not
looked at" (the coverage-gap doctrine). This is how the toolchain already treats semgrep or knip.

**Attribution.** The detector, its rule catalog, and the `DESIGN.md` (Google Stitch) convention are
Impeccable's (Paul Bakaus, Apache-2.0). We consume its `detect --json` like any toolchain scanner and
add the ledger binding; we ship none of its code.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

# Impeccable severity → our severity ladder. Its detector emits warning/error/info.
_SEV = {"error": "high", "warning": "medium", "info": "low"}
# Impeccable category → pin kind. 'slop' = an AI-slop tell, 'quality' = general design / a11y. Both
# are deterministic facts here (the split we enforce — fact vs taste — is detector vs critique, and we
# run only the detector), so every hit is a design_concern that skips fp-check. A hit that is literally
# a token-membership violation becomes a contract_mismatch once a DESIGN.md is elected — that
# refinement is the agent's, at pin-creation time, against the elected contract.
_KIND = {"slop": "design_concern", "quality": "design_concern"}


def _detect_cmd() -> Optional[list]:
    """How to invoke the detector: a global `impeccable` if present, else `npx impeccable` (resolves
    the latest published CLI on demand). None when neither Node/npx nor a global binary exists.

    The **full resolved path** is returned, not the bare name — on Windows the npm shim is
    `impeccable.CMD`, and `subprocess` (no shell) fails on the bare name (`WinError 2`) but runs the
    resolved `.CMD` path fine. `shutil.which` supplies the extension on Windows and the plain binary on
    POSIX, so one code path works on both without `shell=True` (no arg-injection surface)."""
    exe = shutil.which("impeccable")
    if exe:
        return [exe]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "impeccable"]
    return None


def available() -> bool:
    """True when the detector can run at all. Absence → the module reports unchecked, not clean."""
    return _detect_cmd() is not None


def normalize(raw: list) -> list:
    """Impeccable `detect --json` array → the package's finding shape. Every hit is deterministic (no
    model ran), so `confidence: extracted` — the fp-gate lets extracted findings through as facts."""
    findings = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        ap = r.get("antipattern") or "design"
        findings.append({
            "check_id": f"impeccable/{ap}",
            "kind": _KIND.get(r.get("category"), "design_concern"),
            "title": r.get("name") or ap,
            "detail": r.get("snippet") or r.get("description") or "",
            "severity": _SEV.get(r.get("severity"), "low"),
            "confidence": "extracted",     # deterministic detector → fact → skips fp-check
            "file": r.get("file") or "",
            "line": r.get("line") or 0,
            "category": r.get("category") or "design",
            "source": "impeccable",
        })
    return findings


def scan(paths, timeout: int = 300) -> dict:
    """Run the detector over `paths` and normalize. Returns `{"findings": [...]}`, or
    `{"unchecked": True, "reason": ...}` when the detector cannot run — never raises for a missing
    tool. The exit code is a gate signal (non-zero when issues are found), not a failure, so it is
    ignored: what we read is stdout."""
    paths = [str(p) for p in (paths if isinstance(paths, (list, tuple)) else [paths])]
    cmd = _detect_cmd()
    if cmd is None:
        return {"unchecked": True,
                "reason": "impeccable detector not runnable (needs Node ≥22.12 + npx, or a global "
                          "`impeccable`) — install it or accept the design layer as unchecked"}
    try:
        proc = subprocess.run(cmd + ["detect", "--json", *paths],
                              capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return {"unchecked": True, "reason": f"impeccable detect could not run: {e}"}
    out = (proc.stdout or "").strip()
    if not out:
        return {"findings": []}
    try:
        raw = json.loads(out)
    except ValueError:
        return {"unchecked": True,
                "reason": "impeccable detect returned non-JSON on stdout (version mismatch?)"}
    return {"findings": normalize(raw)}
