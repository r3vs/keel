"""Spend telemetry — attribute tokens (and, given a price sheet, cost) across a coding session.

Deterministic by construction: it reads the session transcript the host already writes and sums the
`usage` the model itself reported. No estimation, no sampling. This is the `measurer`'s cost surface
— what makes the model-orchestration tiers *measured* rather than asserted (`core/model-tiers.md`),
and what turns "which MCP servers are loaded but never used" into a fact instead of a guess.

Two rules keep it honest:

- **Tokens are the carrier and are always exact. Cost is not baked in.** Prices are volatile external
  facts, not carrier facts, so cost is computed only against a price sheet the caller supplies (see
  ``PRICING_EXAMPLE`` for the shape). A model with no entry degrades to tokens-only and is listed
  under `unpriced_models`, rather than carrying a number that silently goes stale. That is
  verify-don't-assume applied to our own telemetry.
- **A host whose logs are absent is `unchecked`, never `zero`** (the coverage-gap doctrine). Claude
  Code writes `~/.claude/projects/<slug>/<session>.jsonl` plus a `<session>/subagents/*.jsonl` dir —
  one file per subagent, which is the per-role carrier. Other hosts write elsewhere in other shapes;
  each is a separate adapter, added the same way, and silence from a missing adapter is reported, not
  counted as free.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterable, Optional

# The billable token buckets Anthropic reports, and the human-facing price-sheet key for each. Kept
# 1:1 so a sheet reads `{"input": ..., "output": ..., "cache_write": ..., "cache_read": ...}`.
_TOKEN_BUCKETS = ("input_tokens", "output_tokens",
                  "cache_creation_input_tokens", "cache_read_input_tokens")
_PRICE_KEY = {"input_tokens": "input", "output_tokens": "output",
              "cache_creation_input_tokens": "cache_write", "cache_read_input_tokens": "cache_read"}

# The price-sheet shape: model -> USD per 1,000,000 tokens, per bucket. Supplied by the caller (a
# path or dict), NEVER baked in — prices are external and volatile. This is a SHAPE template only;
# fill real, dated numbers. Any bucket left out is treated as unpriced for that bucket (0 added),
# and a model absent from the sheet degrades the whole row to tokens-only.
PRICING_EXAMPLE = {
    "<model-id, e.g. claude-opus-4-8>": {
        "input": 0.0, "output": 0.0, "cache_write": 0.0, "cache_read": 0.0,
    },
}


def _iter_records(path: str | pathlib.Path) -> Iterable[dict]:
    """One JSON object per line; a malformed line is skipped, never fatal (a truncated tail is normal
    for a session still being written)."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _blank() -> dict:
    return {b: 0 for b in _TOKEN_BUCKETS}


def parse_file(path: str | pathlib.Path, agent: str | None = None) -> tuple[list, set]:
    """Usage rows and the set of MCP servers seen, from one transcript file (a main session or a
    subagent). `agent` overrides the per-row agent label (the subagent files carry their own id)."""
    rows: list = []
    mcp: set = set()
    for r in _iter_records(path):
        srv = r.get("attributionMcpServer")
        if srv:
            mcp.add(srv)
        if r.get("type") != "assistant":
            continue
        m = r.get("message") or {}
        u = m.get("usage")
        if not isinstance(u, dict):
            continue
        rows.append({
            "model": m.get("model") or "unknown",
            "day": (r.get("timestamp") or "")[:10],
            "agent": agent or r.get("agentId") or "main",
            "tokens": {b: int(u.get(b) or 0) for b in _TOKEN_BUCKETS},
        })
    return rows, mcp


def parse_session(session_file: str | pathlib.Path) -> tuple[list, set]:
    """One session: the main transcript plus every subagent transcript beside it (Claude Code puts
    them at `<session-stem>/subagents/*.jsonl`). Each subagent file is a distinct agent invocation,
    so its rows keep their own `agentId` — the per-role carrier, without inventing a mapping."""
    session_file = pathlib.Path(session_file)
    rows, mcp = parse_file(session_file, agent="main")
    subdir = session_file.parent / session_file.stem / "subagents"
    if subdir.is_dir():
        for f in sorted(subdir.glob("*.jsonl")):
            r2, m2 = parse_file(f)
            rows += r2
            mcp |= m2
    return rows, mcp


def _load_pricing(pricing) -> Optional[dict]:
    if pricing is None:
        return None
    if isinstance(pricing, dict):
        return pricing
    return json.loads(pathlib.Path(pricing).read_text(encoding="utf-8"))


def _row_cost(model: str, tokens: dict, pricing: dict) -> Optional[float]:
    """USD for one row under the sheet, or None when the model is unpriced (so the caller can list it
    rather than silently treat missing price as zero)."""
    p = pricing.get(model)
    if not isinstance(p, dict):
        return None
    total = 0.0
    for bucket, tk in tokens.items():
        rate = p.get(_PRICE_KEY[bucket])
        if rate is not None:
            total += (tk / 1_000_000.0) * float(rate)
    return round(total, 6)


def aggregate(rows: list, pricing=None) -> dict:
    """Totals and per-model / per-day / per-agent breakdowns. With a price sheet, a `cost_usd` (None
    if no row's model was priced) and the `unpriced_models` that fell through to tokens-only."""
    pricing = _load_pricing(pricing)
    tot = _blank()
    by_model: dict = {}
    by_day: dict = {}
    by_agent: dict = {}
    cost_total = 0.0
    cost_known = False
    unpriced: set = set()
    for row in rows:
        tk = row["tokens"]
        for b in _TOKEN_BUCKETS:
            tot[b] += tk[b]
            by_model.setdefault(row["model"], _blank())[b] += tk[b]
            by_day.setdefault(row["day"], _blank())[b] += tk[b]
            by_agent.setdefault(row["agent"], _blank())[b] += tk[b]
        if pricing is not None:
            c = _row_cost(row["model"], tk, pricing)
            if c is None:
                unpriced.add(row["model"])
            else:
                cost_total += c
                cost_known = True
    out = {"totals": tot, "by_model": by_model, "by_day": by_day,
           "by_agent": by_agent, "rows": len(rows)}
    if pricing is not None:
        out["cost_usd"] = round(cost_total, 4) if cost_known else None
        out["unpriced_models"] = sorted(unpriced)
    return out


def unused_mcp(seen: Iterable[str], declared: Iterable[str]) -> list:
    """Declared MCP servers that never attributed a single call — loaded every session, paid for in
    context, used never. codeburn's core `optimize` insight, as a deterministic fact."""
    return sorted(set(declared or []) - set(seen or []))


def claude_code_slug(project_dir: str | pathlib.Path) -> str:
    """Claude Code's on-disk project slug: the absolute path with the drive colon and every separator
    folded to '-'. A documented on-disk convention (verified against a real store), not a guess."""
    p = str(pathlib.Path(project_dir).resolve())
    return p.replace(":", "-").replace("\\", "-").replace("/", "-")


def claude_code_sessions(project_dir: str | pathlib.Path, home=None) -> list:
    """Top-level session transcripts Claude Code wrote for this project, newest first. Empty (not an
    error) when the host is not Claude Code or wrote nothing here — the caller reports `unchecked`."""
    home = pathlib.Path(home) if home else pathlib.Path.home()
    base = home / ".claude" / "projects" / claude_code_slug(project_dir)
    if not base.is_dir():
        return []
    return sorted(base.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)


def report_session(session_file: str | pathlib.Path, pricing=None, declared_mcp=None) -> dict:
    """Spend for one session file (+ its subagents)."""
    rows, mcp = parse_session(session_file)
    agg = aggregate(rows, pricing=pricing)
    agg["mcp_servers_seen"] = sorted(mcp)
    if declared_mcp is not None:
        agg["optimize"] = {"unused_mcp_servers": unused_mcp(mcp, declared_mcp)}
    return agg


def report_project(project_dir: str | pathlib.Path, pricing=None, declared_mcp=None, home=None) -> dict:
    """Spend across every Claude Code session for a project (codeburn's per-project view). Reports
    `unchecked` rather than an empty zero when no session store is found for this host."""
    sessions = claude_code_sessions(project_dir, home=home)
    if not sessions:
        return {"unchecked": True,
                "reason": f"no Claude Code session store under ~/.claude for {str(project_dir)!r} "
                          f"(other hosts write elsewhere; add that adapter to count them)"}
    rows: list = []
    mcp: set = set()
    for s in sessions:
        r2, m2 = parse_session(s)
        rows += r2
        mcp |= m2
    agg = aggregate(rows, pricing=pricing)
    agg["sessions"] = len(sessions)
    agg["mcp_servers_seen"] = sorted(mcp)
    if declared_mcp is not None:
        agg["optimize"] = {"unused_mcp_servers": unused_mcp(mcp, declared_mcp)}
    return agg
