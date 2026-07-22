#!/usr/bin/env python3
"""PreToolUse gate: no code edits before the interview elects the to-be.

This is rule #1 of the whole package, and until now it was enforced by *asking nicely* — a
paragraph in a SessionStart banner. A rule with no gate rots; this repo proved that on itself
(its own MEMORY.md drifted, its own read-only agents shipped able to write). So the rule becomes
a mechanism.

What it decides
---------------
- **No ledger in the project** -> allow, silently. The user is not in a rescue/forge; this must not
  interfere with ordinary work. Being invisible when it does not apply is what earns the right to
  block when it does.
- **Ledger with unresolved `blocker`/`high` pins in `needs_input`** -> **deny** edits to product
  code. Those are precisely the pins the spec forbids from silent default: the to-be for that area
  is not knowable yet, so anything built on it is a guess wearing a decision's clothes.
- **Otherwise** -> allow. Once the load-bearing questions are elected, Phase 4 is exactly what
  should be writing code.

What it never blocks
--------------------
Tests (Track A writes the failing test *first* — blocking that would break the very TDD this
enforces), the ledger and its artifacts, and prose. The gate exists to stop premature *product*
code, not to stop work.

Not a target, only an observation
---------------------------------
The gate observes one fact — is the to-be for this area elected yet — and blocks an edit that
presumes "yes" when the ledger says "no". It is deliberately not a score to optimize against. Put
optimization pressure on a monitor and a model does not stop the behavior, it learns to *hide* it;
here that would mean reclassifying product code as prose or dropping it under a `tests/` marker to
slip past ``_is_exempt``. Those exemptions are load-bearing trust, not a checklist to route around.
The honest response to a block is the honest exit the deny message names — elect the to-be, or record
the impasse in the ledger — never a relabeled file that satisfies the gate's letter and defeats it.

Fails open, always. A crash here must never wedge a user's session — the cost of a missed block is
one bad edit the reviewer catches; the cost of a false block is an agent that cannot work at all.

Contract: stdin = PreToolUse JSON; stdout = a permission decision; exit 0 either way.
"""
import json
import sys
from pathlib import Path

# Where a run keeps its ledger. `.audit/` is the rescue/forge convention; the bare name covers a
# user who put it at the root.
LEDGER_LOCATIONS = (".audit/ledger.json", "ledger.json")

# Editing these is how the workflow makes progress — never stand in their way.
ALLOWED_SUFFIXES = (".md", ".txt", ".rst")
ALLOWED_PARTS = (".audit", "ledger.json", "graph.json")
TEST_MARKERS = ("test_", "_test.", "/tests/", "\\tests\\", ".test.", ".spec.", "__tests__")


def _allow():
    sys.exit(0)  # exit 0 with no output = "no decision"; the normal permission flow applies


def _deny(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def _find_ledger(cwd: str):
    base = Path(cwd or ".")
    for rel in LEDGER_LOCATIONS:
        p = base / rel
        if p.is_file():
            return p
    return None


def _is_exempt(path: str) -> bool:
    low = path.replace("\\", "/").lower()
    if any(low.endswith(s) for s in ALLOWED_SUFFIXES):
        return True
    if any(part in low for part in ALLOWED_PARTS):
        return True
    return any(m in low for m in TEST_MARKERS)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        _allow()

    if event.get("tool_name") not in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        _allow()

    path = (event.get("tool_input") or {}).get("file_path") or ""
    if _is_exempt(path):
        _allow()

    ledger_path = _find_ledger(event.get("cwd") or "")
    if ledger_path is None:
        _allow()

    try:
        with open(ledger_path, encoding="utf-8") as fh:
            pins = json.load(fh).get("pins") or []
    except (OSError, json.JSONDecodeError, ValueError, AttributeError):
        _allow()

    blocking = [p for p in pins
                if p.get("state") == "needs_input" and p.get("severity") in ("blocker", "high")]
    if not blocking:
        _allow()

    titles = "\n".join(f"  - [{p.get('severity')}] {p.get('title', p.get('id', '?'))}"
                       for p in blocking[:5])
    more = f"\n  … and {len(blocking) - 5} more" if len(blocking) > 5 else ""
    _deny(
        f"Blocked by the decisions ledger: {len(blocking)} blocker/high pin(s) are still awaiting "
        f"the user's decision, so the to-be for this area is not elected yet.\n{titles}{more}\n\n"
        f"Editing product code now builds on a guess. Run the interview first "
        f"(the `interview_next` MCP tool) and let the user elect the truth — only their committed "
        f"answer decides.\n"
        f"Tests, prose, and the ledger itself are never blocked; write the failing Track-A test if "
        f"you have an elected `to_be` to encode. If you cannot proceed honestly, record the impasse "
        f"in the ledger — never relabel this file to slip past the gate."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # fail open — never wedge a session
        sys.exit(0)
