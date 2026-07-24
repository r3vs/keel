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

The one place it **asks** instead of allowing or denying
--------------------------------------------------------
A write into the host's **auto-memory** directory, while blocker/high pins are still awaiting the
user. That channel is the package's one unguarded write path: the agent decides on its own what to
persist, the store is machine-local and never reviewed in a PR, and *no host emits a memory-specific
hook event*. So an elected-looking claim can be written there by the agent and read back next session
as if it were settled — a decision with no `flip_criteria` and no interview behind it.

Three facts make this branch necessary, and all three were **observed**, not assumed (2026-07-24):
the write really does travel as an ordinary `Write`/`Edit` tool call (27/27 memory files in this
project correlate to one); Claude Code really does emit `PreToolUse` for it, with no path exemption
at the harness level; and this gate nonetheless let it through, because every memory file ends in
`.md` and the prose exemption above swallowed it.

It **asks** rather than denies, and the asymmetry is the whole point. Denying would put this gate in
the business of blocking prose, which the paragraph above promises it never does — and most memory
writes are perfectly legitimate even mid-interview (a build command, an environment quirk). Asking
costs one prompt and converts a silent write into a visible one, which is all that was actually
missing. Only the human's answer decides — same rule as everywhere else here.

Where auto-memory lives is read from the **carrier**, never guessed: the `autoMemoryDirectory`
setting when one is configured, else the documented default `~/.claude/projects/<project>/memory/`.
An unreadable settings file degrades to the default rather than failing.

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

# The documented default auto-memory store: ~/.claude/projects/<project>/memory/. Matched as an
# ordered pair of path segments so a project directory of any name sits between them.
MEMORY_DEFAULT_PARTS = ("/.claude/projects/", "/memory/")
# Settings files that may relocate it via `autoMemoryDirectory` (user scope first, then project).
SETTINGS_FILES = ("~/.claude/settings.json", ".claude/settings.json", ".claude/settings.local.json")


def _allow():
    sys.exit(0)  # exit 0 with no output = "no decision"; the normal permission flow applies


def _decide(decision: str, reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
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


def _configured_memory_dirs(cwd: str) -> list:
    """Auto-memory locations declared by `autoMemoryDirectory`, read from the settings files that
    can set it. The setting is the carrier for "where memory lives"; reading it is what keeps this
    from being a guess about someone's layout. Unreadable or absent → nothing, and the caller falls
    back to the documented default."""
    out = []
    for rel in SETTINGS_FILES:
        try:
            p = Path(rel).expanduser() if rel.startswith("~") else Path(cwd or ".") / rel
            if not p.is_file():
                continue
            value = json.loads(p.read_text(encoding="utf-8")).get("autoMemoryDirectory")
            if isinstance(value, str) and value:
                out.append(str(Path(value).expanduser()).replace("\\", "/").lower().rstrip("/") + "/")
        except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
            continue          # a broken settings file must never wedge the gate
    return out


def _is_host_memory(path: str, cwd: str) -> bool:
    """Is this write landing in the host's agent-written memory store?

    Deterministic: either it sits under a configured `autoMemoryDirectory`, or it matches the
    documented default layout `~/.claude/projects/<project>/memory/` — the two ordered segments,
    so any project directory name fits between them without pattern-guessing.
    """
    low = path.replace("\\", "/").lower()
    if any(low.startswith(d) for d in _configured_memory_dirs(cwd)):
        return True
    head, tail = MEMORY_DEFAULT_PARTS
    i = low.find(head)
    return i != -1 and low.find(tail, i + len(head)) != -1


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        _allow()

    if event.get("tool_name") not in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        _allow()

    cwd = event.get("cwd") or ""
    path = (event.get("tool_input") or {}).get("file_path") or ""
    # The memory check runs BEFORE the exemptions on purpose: every memory file is `.md`, so the
    # prose exemption would swallow this branch entirely (observed — that is exactly why the rule
    # was a recommendation and not a mechanism until now).
    memory = _is_host_memory(path, cwd)
    if not memory and _is_exempt(path):
        _allow()

    ledger_path = _find_ledger(cwd)
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

    if memory:
        _decide("ask",
            f"This writes to the host's agent-written memory while {len(blocking)} blocker/high "
            f"pin(s) are still awaiting the user's decision:\n{titles}{more}\n\n"
            f"Asking, not blocking — most memory notes are fine mid-interview. But that store is "
            f"machine-local, never reviewed in a PR, and read back next session as settled fact, so "
            f"a decision written there becomes a second source of truth with no `flip_criteria` and "
            f"no interview behind it.\n"
            f"If this is a durable FACT (a build command, an environment quirk), say yes. If it is "
            f"really a CHOICE about how this project should be, put it in the ledger instead — "
            f"`ledger_add_pin`, or `ledger_surface_assumption` if you were forced to assume it. "
            f"Only the user's committed interview answer elects anything.")

    _decide("deny",
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
