#!/usr/bin/env python3
"""The tool surface `docs/packaging.md` measures, re-measured on the wire it was measured on.

**Why this exists, in the doc's own words.** The section *"The tool surface is a budget, and it is
the host's to spend"* states five numbers — the whole `tools/list` payload, its token estimate, the
median tool object, the longest single description, the server `instructions` — and then wrote down
the method to re-derive them *and* the admission that nothing runs it: *"these four have **no
gate**, unlike the tool count, which `check_stated_facts.py` checks against the `@mcp.tool`
decorations themselves."* A measurement published with its method and no runner is a number that was
true on one afternoon; every argument the section makes rests on it (*"roughly a fifth of a 128 k
window before the conversation starts"*, *"about 640 of headroom"*), and every docstring anyone
edits moves it. This is the runner.

**Why it is not a row in `check_stated_facts.py`, which is the obvious home.** The two gates split
on **exactness and cost**, not on subject:

  * That gate compares `match.group(1) == str(truth)` — exact equality, deliberately, because the
    facts it holds are counts (tests, tools, modules) where a tolerance would be a licence to drift.
    These claims are **rounded by construction**: the prose writes `~98 k` and `≈24 k`, and it is
    right to, because nobody should restate a payload to the character.
  * Its carriers are an AST walk and a JSON read, under a second. This one's carrier is a
    subprocess that resolves a PEP 723 environment and completes an MCP handshake (~3 s warm, ~7 s
    cold). Importing it there would make every run of the cheapest gate pay for the most expensive
    measurement.

So the tolerance lives here, declared, and the exact gate stays exact.

**What is measured, and where.** At the consumer — the bytes a host receives — not at the source
that produces them. The doc already records why that distinction bites: FastMCP splits a tool's
docstring, sending the prose before ``Args:`` as ``description`` and moving each ``Args:`` entry
into the matching property inside ``inputSchema``, so **counting docstrings sees about half the
truth** (~51 k of docstring against ~98 k on the wire). Both halves are measured here, because the
doc states both and the *gap* between them is the finding.

**One check here is not about prose at all**, and it is the reason this gate earns a CI slot beyond
keeping a table honest: Claude Code *"truncates tool descriptions and server instructions at 2KB
each"*, silently — the agent picks a tool by its description, so a clipped one degrades selection
with nothing reporting it. That ceiling is enforced below in **bytes**, because the host states it
in KB while the doc's figures are characters, and this repo's prose is full of em dashes: the
longest description is 1,405 characters and 1,413 bytes. The unit that matters is the one the host
truncates by, and reading a KB limit as characters is the same class of error `open-gaps.md` §31
residual 1 records against the skill-listing budget.

**The declared limit, because a gate that hides one is worse than none.** A number is checked where
the prose spells it in a shape registered below; a restatement in an unregistered phrasing ("roughly
a hundred thousand characters") is invisible, exactly as `check_stated_facts.py` declares for
itself. The answer is the same: write the number in one of these shapes. A pattern that matches
nothing is an error rather than silence, for the reason that gate learned the hard way — a dead
pattern reads as coverage and is not.

Run in CI: `python scripts/check_packaging_wire.py` (exit 1 on drift, on a description over the
host's ceiling, or on a pattern that covers nothing).
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "src" / "mcp" / "server.py"
DOC = ROOT / "docs" / "packaging.md"

# HYPOTHESIS: 5%. The tolerance is on the ARGUMENT the numbers carry, not on the numbers — the
# section's claims are "roughly a fifth of a 128 k window" and "about 640 of headroom", and neither
# turns on a hundred characters. 5% of the payload is ~4.9 k characters, about three and a half
# median tool objects: below that the prose stays true and re-rounding it would be churn; above it,
# somebody added tools or rewrote docstrings at a scale the section is making an argument about, and
# the argument needs re-reading rather than the number re-typing. Two facts below opt out with 0.0
# because they are counts and definitions, not measurements.
TOLERANCE = 0.05

# HYPOTHESIS: 4 characters per token, which is the divisor the prose itself names ("at ~4
# chars/token") and a conventional English-text approximation, not a measurement of any tokenizer.
# It is registered as a fact below so the doc and this gate cannot disagree about it: if the prose
# changes the divisor, the check on the token figure changes with it, which is the only way an
# estimate and its stated method stay one claim.
CHARS_PER_TOKEN = 4

#: Claude Code's published ceiling, quoted rather than chosen: *"truncates tool descriptions and
#: server instructions at 2KB each"* (`https://code.claude.com/docs/en/mcp`). Bytes, because KB is
#: bytes — see the module docstring. Not ours to tune; a different number here does not buy headroom,
#: it just stops predicting where the host will cut.
TRUNCATION_LIMIT_BYTES = 2048

# HYPOTHESIS: 180 s. A watchdog, not a performance budget: the doc measures cold start at ~7 s and
# this gate is ~3 s warm, so anything near this ceiling is a server that never answered. The value
# only decides how long CI waits before saying so — the harness in tests/test_mcp_server.py blocks
# forever on `readline()`, which is fine in a test runner with its own timeout and not fine here.
SPAWN_TIMEOUT_S = 180


class _Wire:
    """One server session over real stdio — the same client shape as `tests/test_mcp_server.py`.

    Deliberately a second implementation of that handshake rather than an import: the tests are not
    a library, and a gate that fails because a test file was refactored is a gate that reports on
    the wrong thing. What is shared is the protocol, which is FastMCP's to keep stable.
    """

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            ["uv", "run", "--script", str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
            # Same reason the test harness sets it: the background grammar warm-up fetches, and
            # this gate has nothing to do with tree-sitter.
            env={**os.environ, "CODEBASE_ALIGNMENT_SKIP_WARM": "1"},
        )
        self._id = 0
        self._stderr: list[str] = []
        threading.Thread(target=self._pump, daemon=True).start()
        # The watchdog. Without it a server that starts and never answers hangs CI, because the
        # read below has no timeout of its own.
        self._timer = threading.Timer(SPAWN_TIMEOUT_S, self.proc.kill)
        self._timer.daemon = True
        self._timer.start()

    def _pump(self) -> None:
        for line in self.proc.stderr:
            self._stderr.append(line)

    def _send(self, payload: dict) -> None:
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise SystemExit(
                    f"ERROR the server closed the stream before answering `{method}` — the PEP 723 "
                    f"block failed to resolve, or it crashed. Its stderr:\n"
                    + "".join(self._stderr[-40:]))
            msg = json.loads(line)
            if msg.get("id") == self._id:
                return msg

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": {}})

    def close(self) -> None:
        self._timer.cancel()
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def docstring_chars() -> int:
    """The `@mcp.tool` docstrings, summed — the *source* half of the doc's docstring-vs-wire pair.

    Read off the same decorations `check_tool_carriers.py` and `check_stated_facts.py` read, so the
    three gates cannot disagree about what a tool is.
    """
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    total = 0
    seen = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            func = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(func, ast.Attribute) and func.attr == "tool":
                seen += 1
                total += len(ast.get_docstring(node) or "")
    if not seen:
        raise SystemExit("ERROR no @mcp.tool decorations found — the decorator shape changed and "
                         "this gate just went vacuous")
    return total


def measure() -> dict:
    """Everything the section claims, taken off one handshake."""
    wire = _Wire()
    try:
        handshake = wire.request("initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "keel-packaging-wire", "version": "1"},
        })
        wire.notify("notifications/initialized")
        listing = wire.request("tools/list", {})
    finally:
        wire.close()

    result = listing.get("result") or {}
    tools = result.get("tools") or []
    if not tools:
        raise SystemExit("ERROR tools/list advertised nothing — every number below would be 0 and "
                         "this gate would pass by measuring an empty server")
    objects = [len(json.dumps(t, ensure_ascii=False)) for t in tools]
    descriptions = [(t["name"], t.get("description") or "") for t in tools]
    desc_chars = [len(d) for _, d in descriptions]
    instructions = (handshake.get("result") or {}).get("instructions") or ""
    wire_chars = len(json.dumps(result, ensure_ascii=False))

    return {
        "tools": len(tools),
        "wire_chars": wire_chars,
        "tokens": wire_chars / CHARS_PER_TOKEN,
        "chars_per_token": CHARS_PER_TOKEN,
        "median_tool_chars": statistics.median(objects),
        "longest_desc_chars": max(desc_chars),
        "median_desc_chars": statistics.median(desc_chars),
        "instructions_chars": len(instructions),
        "docstring_chars": docstring_chars(),
        "headroom_chars": TRUNCATION_LIMIT_BYTES - max(desc_chars),
        # The ceiling check reads these two, and they are BYTES on purpose — see the docstring.
        "_descriptions": descriptions,
        "_instructions": instructions,
    }


#: Each fact: what the section claims, the key that knows the answer, the multiplier the prose's own
#: spelling implies (`~98 k` is written in thousands), and the patterns — each annotated with the
#: sentence it was written for, so a pattern nobody matches is visible as dead coverage rather than
#: as a green run.
FACTS = (
    {
        "label": "the tools the server advertises on the wire",
        "key": "tools",
        "scale": 1,
        # A count, not a measurement: 66 tools is not 67 within any tolerance. `check_stated_facts.py`
        # already holds the prose count against the DECORATIONS; this holds the table cell against
        # what actually arrives, which is a different carrier and the one this section is about — a
        # tool registered behind a condition would satisfy the first and fail here.
        "tolerance": 0.0,
        "patterns": (
            re.compile(r"^\|\s*tools advertised\s*\|\s*\*\*(\d+)\*\*", re.M),
        ),
    },
    {
        "label": "the characters of JSON the whole tools/list result costs",
        "key": "wire_chars",
        "scale": 1_000,
        "patterns": (
            re.compile(r"~([\d,]+) k characters of JSON"),      # the cost table
            re.compile(r"against ~([\d,]+) k on the wire"),     # the docstring-vs-wire correction
        ),
    },
    {
        "label": "the token estimate for that payload",
        "key": "tokens",
        "scale": 1_000,
        "patterns": (
            re.compile(r"≈([\d,]+) k tokens"),   # the cost table AND the Claude Code `auto` row
        ),
    },
    {
        "label": "the divisor the token estimate uses",
        "key": "chars_per_token",
        "scale": 1,
        # A definition the prose and this file must share, not a measured quantity — so exact.
        "tolerance": 0.0,
        "patterns": (
            re.compile(r"at ~(\d+) chars/token"),
        ),
    },
    {
        "label": "the median tool object on the wire",
        "key": "median_tool_chars",
        "scale": 1,
        "patterns": (
            re.compile(r"^\|\s*median tool object\s*\|\s*~([\d,]+) characters", re.M),
            re.compile(r"median tool object of ~([\d,]+)"),   # "the schema is most of the cost"
        ),
    },
    {
        "label": "the longest single tool description",
        "key": "longest_desc_chars",
        "scale": 1,
        "patterns": (
            re.compile(r"^\|\s*longest single description\s*\|\s*([\d,]+) characters", re.M),
            re.compile(r"longest description is ([\d,]+) characters"),   # the 2 KB paragraph
        ),
    },
    {
        "label": "the median tool description",
        "key": "median_desc_chars",
        "scale": 1,
        "patterns": (
            re.compile(r"median description ([\d,]+) characters"),
        ),
    },
    {
        "label": "the server's own instructions string",
        "key": "instructions_chars",
        "scale": 1,
        "patterns": (
            re.compile(r"^\|\s*server `instructions`\s*\|\s*([\d,]+) characters", re.M),
        ),
    },
    {
        "label": "the docstring characters the wire figure is contrasted with",
        "key": "docstring_chars",
        "scale": 1_000,
        "patterns": (
            re.compile(r"~([\d,]+) k characters of docstring"),
        ),
    },
    {
        "label": "the headroom under the host's 2 KB description ceiling",
        "key": "headroom_chars",
        "scale": 1,
        "patterns": (
            re.compile(r"about ([\d,]+) of headroom"),
        ),
    },
)


def _num(raw: str, scale: int) -> float:
    return int(raw.replace(",", "")) * scale


def _show(value: float) -> str:
    return f"{value:,.0f}"


def audit(text: str, truth: dict) -> tuple[list[str], int, dict[tuple[str, str], int]]:
    """The prose half, as a pure function of (document, measurement).

    Split out from `main` so a test can drive it with a doctored document and a fake measurement —
    a gate whose only proof is that it passes on today's tree has never been shown to fail, which is
    the same "green means nothing" problem this repo keeps finding in other people's suites.
    """
    errors: list[str] = []
    checked = 0
    hits: dict[tuple[str, str], int] = {}
    for fact in FACTS:
        measured = truth[fact["key"]]
        tol = fact.get("tolerance", TOLERANCE)
        for pattern in fact["patterns"]:
            hits.setdefault((fact["label"], pattern.pattern), 0)
            for match in pattern.finditer(text):
                checked += 1
                hits[(fact["label"], pattern.pattern)] += 1
                stated = _num(match.group(1), fact["scale"])
                drift = abs(stated - measured) / measured if measured else 1.0
                if drift <= tol:
                    continue
                line = text[: match.start()].count("\n") + 1
                errors.append(
                    f"ERROR {DOC.relative_to(ROOT).as_posix()}:{line}: says "
                    f"`{match.group(0).strip()}` — {fact['label']} measures {_show(measured)} on "
                    f"the wire today ({drift:.1%} off, tolerance {tol:.0%}). Re-measure and restate "
                    f"it, or say why the argument the number carries still holds.")

    for (label, pattern), n in sorted(hits.items()):
        if n:
            continue
        errors.append(
            f"ERROR pattern `{pattern}` ({label}) matched nothing in "
            f"{DOC.relative_to(ROOT).as_posix()}. Each pattern is annotated with the sentence it "
            f"was written for, so either that sentence was rewritten — restate it or repoint the "
            f"pattern — or the measurement was dropped from the doc and this gate now covers less "
            f"than it claims.")
    return errors, checked, hits


def main() -> int:
    if shutil.which("uv") is None:
        # Not a skip. uv is a hard prerequisite of this package — without it a host cannot spawn the
        # server at all and the tools go silently missing — and a gate that exits 0 having measured
        # nothing is the failure this file's whole subject warns about. `bash src/tools/bootstrap.sh`
        # installs it; CI provisions it with `astral-sh/setup-uv`.
        print("ERROR uv is not on PATH, so the server cannot be spawned and nothing here was "
              "measured. Install it (src/tools/bootstrap.sh) rather than treating this as a skip: "
              "uv's absence is exactly the failure that is silent at runtime.")
        return 1

    truth = measure()
    text = DOC.read_text(encoding="utf-8")
    rel = DOC.relative_to(ROOT).as_posix()
    messages, checked, hits = audit(text, truth)
    for message in messages:
        print(message)
    errors = len(messages)

    # The half that is not about prose: the host's ceiling, in the unit the host cuts by.
    for name, desc in sorted(truth["_descriptions"]):
        size = len(desc.encode("utf-8"))
        if size <= TRUNCATION_LIMIT_BYTES:
            continue
        errors += 1
        print(f"ERROR the `{name}` tool's description is {size:,} bytes, over the "
              f"{TRUNCATION_LIMIT_BYTES:,}-byte ceiling Claude Code truncates at. Truncation is "
              f"SILENT and the agent selects tools by that text: shorten the docstring, do not "
              f"accept the clip.")
    instr_bytes = len(truth["_instructions"].encode("utf-8"))
    if instr_bytes > TRUNCATION_LIMIT_BYTES:
        errors += 1
        print(f"ERROR the server `instructions` string is {instr_bytes:,} bytes, over the same "
              f"{TRUNCATION_LIMIT_BYTES:,}-byte ceiling — and it is the one string that loads on "
              f"every session even where tools are deferred.")

    widest = max(len(d.encode("utf-8")) for _, d in truth["_descriptions"])
    print(f"\n{truth['tools']} tools measured on the wire: {_show(truth['wire_chars'])} characters "
          f"(≈{truth['tokens'] / 1000:.1f} k tokens at {CHARS_PER_TOKEN} chars/token), median tool "
          f"object {_show(truth['median_tool_chars'])}, longest description "
          f"{_show(truth['longest_desc_chars'])} chars / {widest:,} bytes "
          f"({TRUNCATION_LIMIT_BYTES - widest:,} under the ceiling), instructions "
          f"{_show(truth['instructions_chars'])}.")
    print(f"{len(FACTS)} measured fact(s), {checked} restatement(s) across "
          f"{sum(1 for n in hits.values() if n)}/{len(hits)} pattern(s) in {rel} — {errors} stale")
    if not checked:
        print("ERROR no restatement matched any pattern at all — the section was rewritten, or this "
              "gate is now checking nothing.")
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
