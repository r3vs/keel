"""Design-alignment — the presentation layer's drift, bound to the ledger.

The detection is NOT reinvented. It shells the **Impeccable** detector (pbakaus/impeccable,
Apache-2.0): a no-LLM scanner for AI-slop tells and design-quality / accessibility issues across
HTML / CSS / JSX / TSX / Vue / Svelte, and — when the project carries a `DESIGN.md` — for drift away
from that declared design system. What is ours is the **binding**: each detector hit becomes a
ledger pin — a `design_concern`, or a `contract_mismatch` when the hit is a violation of the elected
`DESIGN.md` contract — so a frontend design finding flows through the same interview → remediation →
resolve-when-observed machinery as every DB / ORM / API / logic pin, in the one source of truth.
Impeccable's output is a lint report; the ledger is where a decision lives. That difference is the
whole reason we bind rather than install it as a sibling skill (which the self-contained rule forbids
anyway): a design finding that lived only in Impeccable's report would be a stateless twin beside the
single source of truth — the exact divergence this package exists to find.

**Two pin kinds, split by a deterministic carrier — not by judgment.** Impeccable's own antipattern
id is the carrier. A hit whose `antipattern` begins `design-system-` (`design-system-font` /
`-color` / `-radius` / `-font-size`) is a **token-membership violation against the project's
elected `DESIGN.md`** — a used font/color/radius/size that the declared design system does not
contain. That is exactly a `contract_mismatch` (as_is = the code's token, to_be = the DESIGN.md's
declared token), the presentation-layer analog of the DB↔ORM↔API shape diff, and it only appears
when a `DESIGN.md` actually governs the files (impeccable resolves it by walking up to the project
root), so it is never fabricated. Every other hit — universal a11y/slop tells that hold with or
without a project design system (low contrast, overused font, …) — is a `design_concern`.

**Deterministic by construction.** The detector runs no model — WCAG contrast is a computed ratio, an
off-palette color is a set-membership fact against the DESIGN.md — so its hits are FACTS and carry
`confidence: extracted`, which lets them skip the false-positive gate, exactly like a type error. The
*taste* half (Impeccable's LLM critique, shipped as its own *skill*, not a CLI command) is
deliberately NOT run here; it belongs to the reviewer / challenger lens, adapted with attribution, as
judgment pins that DO pass fp-check.

**Advisory findings are carried, never dropped, but flagged.** Impeccable marks some rules
`advisory` (e.g. off-palette color, em-dash overuse): detected, but never counted as a failure and
never changing its exit code. We surface them as low-severity pins with `advisory: true` so the
interview can see the whole design picture, while the severity threshold keeps them out of the
blocker path — the coverage doctrine (surface everything) without letting a soft signal block.

**Degrades, never hard-fails.** If `impeccable` (Node ≥ 22.12) is not runnable, the module reports
`unchecked` rather than a clean bill — a design finder that could not run is not "no slop", it is "not
looked at" (the coverage-gap doctrine). This is how the toolchain already treats semgrep or knip.

**Attribution.** The detector, its rule catalog, the `design-system-*` DESIGN.md checks, and the
`DESIGN.md` (Google Stitch) convention are Impeccable's (Paul Bakaus, Apache-2.0). We consume its
`detect --json` like any toolchain scanner and add the ledger binding; we ship none of its code.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

# Impeccable severity → our severity ladder. Its detector emits error / warning / info / advisory
# (and stamps an `advisory: true` flag on some rules); advisory is a real-but-soft signal, so it
# floors at low and is flagged, never dropped.
_SEV = {"error": "high", "warning": "medium", "info": "low", "advisory": "low"}
# Impeccable category → pin kind for the NON-contract hits. 'slop' = an AI-slop tell, 'quality' =
# general design / a11y. Both are deterministic facts here (the split we enforce — fact vs taste — is
# detector vs critique, and we run only the detector), so each is a design_concern. The
# `design-system-*` antipatterns are the exception, routed to contract_mismatch in `_kind_for` by
# their id prefix — the carrier, not a guess.
_KIND = {"slop": "design_concern", "quality": "design_concern"}
# The id prefix impeccable stamps on a DESIGN.md token-membership violation. Its presence is proof a
# DESIGN.md governed the file, so routing on it never invents a contract that is not on disk.
_CONTRACT_PREFIX = "design-system-"


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


def _is_advisory(r: dict) -> bool:
    return r.get("advisory") is True or r.get("severity") == "advisory"


def _kind_for(r: dict) -> str:
    """The pin kind, decided by the detector's own antipattern id (the deterministic carrier).

    A `design-system-*` hit is a violation of the elected DESIGN.md contract → `contract_mismatch`;
    everything else is a universal a11y/slop tell → `design_concern` (via category). No judgment: the
    id, which impeccable only emits when a DESIGN.md governed the file, decides it."""
    ap = r.get("antipattern") or ""
    if ap.startswith(_CONTRACT_PREFIX):
        return "contract_mismatch"
    return _KIND.get(r.get("category"), "design_concern")


def normalize(raw: list) -> list:
    """Impeccable `detect --json` array → the package's finding shape. Every hit is deterministic (no
    model ran), so `confidence: extracted` — the fp-gate lets extracted findings through as facts."""
    findings = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        ap = r.get("antipattern") or "design"
        advisory = _is_advisory(r)
        f = {
            "check_id": f"impeccable/{ap}",
            "kind": _kind_for(r),
            "title": r.get("name") or ap,
            "detail": r.get("snippet") or r.get("description") or "",
            # advisory is non-blocking by definition (never changes impeccable's exit code), so it
            # floors at low regardless of the raw severity string; otherwise the ladder maps directly.
            "severity": "low" if advisory else _SEV.get(r.get("severity"), "low"),
            "confidence": "extracted",     # deterministic detector → fact → skips fp-check
            "file": r.get("file") or "",
            "line": r.get("line") or 0,
            "category": r.get("category") or "design",
            "source": "impeccable",
        }
        if advisory:
            f["advisory"] = True           # soft signal: surfaced + floored at low, never blocks
        findings.append(f)
    return findings


def scan(paths, timeout: int = 300, scope=None, viewport: str = "", no_advisory: bool = False) -> dict:
    """Run the detector over `paths` (files, directories, or URLs) and normalize. Returns
    `{"findings": [...]}`, or `{"unchecked": True, "reason": ...}` when the detector cannot run —
    never raises for a missing tool. The exit code is a gate signal (non-zero when issues are found),
    not a failure, so it is ignored: what we read is stdout.

    - `scope`: restrict to a design domain (`"type"`, `"layout"`, or a list) — impeccable's `--scope`.
    - `viewport`: `"WxH"` for a URL render pass (e.g. `"390x844"` for a mobile-width check) — only
      meaningful for URL targets, which impeccable renders in a real browser.
    - `no_advisory`: drop advisory rules at the source (impeccable's `--no-advisory`). Default keeps
      them (we surface everything and flag the soft ones); pass True for a blocker-only pass.

    The DESIGN.md contract is loaded by impeccable automatically when one governs the target — no
    flag needed; that is what makes a `design-system-*` hit a real `contract_mismatch`."""
    paths = [str(p) for p in (paths if isinstance(paths, (list, tuple)) else [paths])]
    cmd = _detect_cmd()
    if cmd is None:
        return {"unchecked": True,
                "reason": "impeccable detector not runnable (needs Node ≥22.12 + npx, or a global "
                          "`impeccable`) — install it or accept the design layer as unchecked"}
    argv = cmd + ["detect", "--json"]
    if scope:
        scope = ",".join(scope) if isinstance(scope, (list, tuple)) else str(scope)
        argv += ["--scope", scope]
    if viewport:
        argv += ["--viewport", str(viewport)]
    if no_advisory:
        argv += ["--no-advisory"]
    argv += paths
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
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
