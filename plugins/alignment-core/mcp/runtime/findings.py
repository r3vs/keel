"""Findings pipeline + false-positive gate — the mandatory Phase-1 gate as code.

`references/module-fp-check.md` states the rule: no finding reaches the map or the interview
without an explicit CONFIRM / DOWNGRADE / DROP verdict, because AI-assisted analysis over-reports
and the whole value proposition dies if the user drowns in false positives. This module:

1. **Normalizes** heterogeneous tool output to one finding stream — SARIF (semgrep, gitleaks,
   trivy, and any SARIF-emitting tool) and OSV-scanner JSON, reduced to
   `{tool, rule_id, message, severity, file, line, fingerprint}`.
2. **Gates** each finding through the five ordered checks (cheapest first): intentional-stub
   exclusion → reachability → framework/context suppression → corroboration → duplicate merge.
   Deterministic findings (a type error, a compiler diagnostic) are marked so they skip the gate
   entirely (`core/static-analysis.md`: a proven diagnostic needs no fp-check).
3. **Maps** survivors to ledger pins — `defect` (confirmed live) or `incompleteness` (intentional
   stub) — clustering N instances of one root cause into a single pin with many anchors.

The two oracles the gate needs from outside are injected, never faked: a `reachable(file)`
predicate (from the graph; default unknown→keep, so a missing graph never silently drops a real
bug) and an `intentional_stub(file, line)` predicate (from the completeness module). Stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Callable, Iterable, Optional

# SARIF level → our severity; tools that emit `security-severity` refine it further.
_SARIF_LEVEL = {"error": "high", "warning": "medium", "note": "low", "none": "low"}
_SEVERITY_RANK = {"blocker": 0, "high": 1, "medium": 2, "low": 3}

# Deterministic rule-id prefixes: a proven diagnostic, not a heuristic guess — skips fp-check
# (still clustered + surfaced, but never DROPPED as a suspected false positive).
_DETERMINISTIC_PREFIXES = ("mypy", "tsc", "pyright", "typecheck", "compile", "syntax")


def _fingerprint(tool: str, rule_id: str, file: str, line: int) -> str:
    return hashlib.sha1(f"{tool}:{rule_id}:{file}:{line}".encode()).hexdigest()[:12]


def finding(tool: str, rule_id: str, message: str, severity: str,
            file: str, line: int, deterministic: bool = False,
            security_severity: Optional[float] = None) -> dict:
    if security_severity is not None:      # SARIF security-severity 0-10 → our bands
        severity = ("blocker" if security_severity >= 9 else "high" if security_severity >= 7
                    else "medium" if security_severity >= 4 else "low")
    return {"tool": tool, "rule_id": rule_id, "message": message,
            "severity": severity if severity in _SEVERITY_RANK else "medium",
            "file": file, "line": line,
            "deterministic": deterministic or rule_id.split(".")[0].split("-")[0].lower()
            in _DETERMINISTIC_PREFIXES,
            "fingerprint": _fingerprint(tool, rule_id, file, line)}


# ── normalizers ──────────────────────────────────────────────────────────────

def normalize_sarif(sarif: dict, tool_hint: str = "") -> list[dict]:
    """SARIF 2.1.0 → finding stream. Handles multi-run files (trivy) and rule metadata."""
    out: list[dict] = []
    for run in sarif.get("runs", []):
        tool = (run.get("tool", {}).get("driver", {}).get("name") or tool_hint or "sarif").lower()
        # rule_id → security-severity from rule metadata, if present
        sev_by_rule: dict[str, float] = {}
        for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
            props = rule.get("properties", {})
            if "security-severity" in props:
                try:
                    sev_by_rule[rule.get("id", "")] = float(props["security-severity"])
                except (TypeError, ValueError):
                    pass
        for res in run.get("results", []):
            rule_id = res.get("ruleId") or res.get("rule", {}).get("id") or "unknown"
            level = res.get("level", "warning")
            msg = (res.get("message", {}) or {}).get("text", "")
            locs = res.get("locations", []) or [{}]
            for loc in locs:
                phys = loc.get("physicalLocation", {})
                uri = phys.get("artifactLocation", {}).get("uri", "")
                line = phys.get("region", {}).get("startLine", 0)
                out.append(finding(tool, rule_id, msg, _SARIF_LEVEL.get(level, "medium"),
                                   uri, line, security_severity=sev_by_rule.get(rule_id)))
    return out


def normalize_osv(osv: dict) -> list[dict]:
    """OSV-scanner JSON → finding stream (one per vulnerable package)."""
    out: list[dict] = []
    for res in osv.get("results", []):
        source = res.get("source", {}).get("path", "")
        for pkg in res.get("packages", []):
            name = pkg.get("package", {}).get("name", "?")
            for vuln in pkg.get("vulnerabilities", []):
                vid = vuln.get("id", "OSV")
                summary = vuln.get("summary", "") or vid
                sev = "high"
                for s in vuln.get("severity", []):
                    if s.get("type") == "CVSS_V3":
                        sev = "high"       # keep conservative; CVSS parsing is out of scope
                out.append(finding("osv", vid, f"{name}: {summary}", sev, source, 0))
    return out


def load_and_normalize(paths: Iterable[str]) -> list[dict]:
    """Auto-detect SARIF vs OSV by shape and merge every file into one stream."""
    stream: list[dict] = []
    for p in paths:
        data = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        if "runs" in data:
            stream += normalize_sarif(data)
        elif "results" in data:
            stream += normalize_osv(data)
    return stream


# ── the false-positive gate ──────────────────────────────────────────────────

# Per-framework safe patterns: (tool-or-rule substring, path substring) that are known-safe.
DEFAULT_SAFE_PATTERNS = [
    ("sqlalchemy", ""),      # ORM-built SQL flagged as raw SQLi is spurious
    ("django.orm", ""),
    ("", "/migrations/"),    # a raw-SQL flag inside a migration is expected, not a live sink
]


class FpGate:
    """The mandatory gate. `reachable` and `intentional_stub` are injected oracles; both default
    to the safe direction (keep) when the caller has no graph / completeness data, so a missing
    input never silently drops a real finding."""

    def __init__(self,
                 reachable: Optional[Callable[[str], Optional[bool]]] = None,
                 intentional_stub: Optional[Callable[[str, int], bool]] = None,
                 safe_patterns: Optional[list] = None):
        self.reachable = reachable or (lambda f: None)          # None = unknown → keep
        self.intentional_stub = intentional_stub or (lambda f, l: False)
        self.safe_patterns = safe_patterns if safe_patterns is not None else DEFAULT_SAFE_PATTERNS

    def _safe_pattern_hit(self, f: dict) -> bool:
        hay = f"{f['tool']} {f['rule_id']}".lower()
        for needle, path_sub in self.safe_patterns:
            if (not needle or needle in hay) and (not path_sub or path_sub in f["file"]):
                return True
        return False

    def _corroborated(self, f: dict, all_findings: list[dict]) -> bool:
        """A second *independent* signal agrees: a different tool flags the same file, or the
        finding is a deterministic diagnostic. (Many hits of one rule from one tool are the same
        signal, not corroboration — that is the duplicate-merge case, not this one.)"""
        if f["deterministic"]:
            return True
        return any(g["file"] == f["file"] and g["tool"] != f["tool"] for g in all_findings)

    def verdict(self, f: dict, corroborated: bool) -> tuple[str, str]:
        """Per-finding verdict (CONFIRM|DOWNGRADE|DROP), checks 1-4 in cheapest-first order.
        The duplicate merge (check 5) happens after, in run()."""
        # deterministic diagnostics skip the gate: proven, not suspected
        if f["deterministic"]:
            return "CONFIRM", "deterministic diagnostic — skips fp-check"
        # 1. intentional-stub exclusion → it belongs to completeness, not defects
        if self.intentional_stub(f["file"], f["line"]):
            return "DROP", "intentional stub — surfaces as incompleteness, not a defect"
        # 2. reachability
        if self.reachable(f["file"]) is False:
            return "DOWNGRADE", "no path from any entry point — dead/unreachable"
        # 3. framework/context suppression
        if self._safe_pattern_hit(f):
            return "DROP", "framework safe-pattern (e.g. ORM-parameterized / migration)"
        # 4. corroboration
        if not corroborated and f["severity"] in ("medium", "low"):
            return "DOWNGRADE", "single low-confidence signal — proposed_default, not asked"
        return "CONFIRM", "reachable, corroborated or high-severity"

    def run(self, findings: list[dict]) -> dict:
        """Gate the whole stream: checks 1-4 per finding, then check 5 (duplicate merge) collapses
        surviving instances of one root cause into a single cluster with many anchors."""
        graded = [(f, *self.verdict(f, self._corroborated(f, findings))) for f in findings]

        # check 5: merge non-DROP survivors by (tool, rule_id); a cluster CONFIRMs if any
        # instance confirmed (the strongest verdict wins), keeping every instance as an anchor.
        surviving: dict[str, dict] = {}
        dropped: list[dict] = []
        for f, v, reason in graded:
            if v == "DROP":
                dropped.append({"cluster_id": f"{f['tool']}:{f['rule_id']}", "reason": reason,
                                "count": 1, "lead": f, "verdict": v, "anchors": [f]})
                continue
            cid = f"{f['tool']}:{f['rule_id']}"
            rec = surviving.setdefault(cid, {"cluster_id": cid, "verdict": v, "reason": reason,
                                             "anchors": [], "lead": f})
            rec["anchors"].append(f)
            if v == "CONFIRM":          # strongest verdict wins the cluster
                rec["verdict"], rec["reason"] = "CONFIRM", reason
            if _SEVERITY_RANK[f["severity"]] < _SEVERITY_RANK[rec["lead"]["severity"]]:
                rec["lead"] = f
        for rec in surviving.values():
            rec["count"] = len(rec["anchors"])

        confirmed = [r for r in surviving.values() if r["verdict"] == "CONFIRM"]
        downgraded = [r for r in surviving.values() if r["verdict"] == "DOWNGRADE"]
        return {"confirmed": confirmed, "downgraded": downgraded, "dropped": dropped,
                "clusters": len(surviving), "findings_in": len(findings)}


# ── mapping survivors to ledger pins ─────────────────────────────────────────

def to_pins(ledger, gated: dict) -> list[dict]:
    """Add a pin per surviving cluster. CONFIRM → defect; DOWNGRADE → defect with lowered
    severity+confidence (the threshold then routes medium/low to proposed_default). DROP is
    logged, never surfaced. N instances collapse to one pin with many anchors (`cluster_id`)."""
    pins = []
    for record in gated["confirmed"] + gated["downgraded"]:
        lead = record["lead"]
        downgraded = record in gated["downgraded"]
        severity = lead["severity"]
        if downgraded and severity in ("high",):
            severity = "medium"
        anchors = [{"node_id": None, "layer": "code", "role": "sink",
                    "loc": f"{a['file']}:{a['line']}"} for a in record["anchors"]]
        pin = ledger.add_pin(
            kind="defect",
            title=f"{lead['rule_id']}: {lead['message'][:80]}" if lead["message"]
            else lead["rule_id"],
            severity=severity,
            confidence="inferred" if downgraded else "extracted",
            provenance=[{"source": f"fp-check:{record['verdict']}", "detail": record["reason"]},
                        {"source": lead["tool"], "detail": lead["rule_id"]}],
            anchors=anchors,
            as_is={"description": lead["message"], "evidence": {
                "tool": lead["tool"], "rule_id": lead["rule_id"],
                "loc": f"{lead['file']}:{lead['line']}", "instances": record["count"]}},
            cluster_id=f"cl_{lead['tool']}_{lead['rule_id']}".replace(".", "_")[:60],
        )
        pins.append(pin)
    return pins


def audit_log(gated: dict) -> list[dict]:
    """The DROP audit trail — what was suppressed and why (fp-check must be showable)."""
    return [{"cluster_id": r["cluster_id"], "reason": r["reason"], "count": r["count"],
             "example": f"{r['lead']['file']}:{r['lead']['line']}"} for r in gated["dropped"]]
