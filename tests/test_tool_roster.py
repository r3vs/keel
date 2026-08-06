"""The documented tool roster is the served tool roster — counts included.

Third instance of the same class on one branch, and the first two were caught by a human reading:
`src/readme/keel-core.md` headed its ledger table *"the single source of truth (14)"* over 14 rows
that omitted `ledger_record_decision`, `ledger_record_policy`, `policy_preview`, `interview_expand`,
`interview_seed_policies` and `propose_correspondence`; two of its section counts were already off by
one in opposite directions, which is why the wrong total still summed; and the root `README.md`
repeated the wrong total in four more places. A count in a heading is a claim about the artifact, and
nothing derived or verified it.

What is checked, and on what carrier — never a semantic read of the prose:

  * **served** — the `@mcp.tool` decorations in `src/mcp/server.py`, by AST. The same authority
    `scripts/check_tool_carriers.py` uses, for the same reason: a hand-kept second list drifts the
    first time somebody adds a tool.
  * **documented** — an entry in a roster section. In `keel-core.md` the carrier is a table row
    (`| `tool` | … |`); in `README.md` it is a backticked name inside the `<details>` block.
  * **claimed** — the integer in a section marker (`### … (N)` / `**… (N)**`), in the roster's own
    heading, and in every `<int> MCP tools` phrase in either file.

Both scans are bounded by structure, not by looking for prose that seems roster-ish: `keel-core.md`
from its `## The N MCP tools` heading to the next `##`, `README.md` between `<summary>` and
`</details>`.

**An entry is compared as it is written, never filtered through the served set.** It used to be
`[n for n in names if n in known]`, in both assertions — which dropped an undocumented name *before*
comparing, so the set matched and the count still balanced. A planted `| `ledger_delete_everything` |
wipes the ledger |` row passed green: a test named for "and nothing else is" that checked only the
first half, which is worse than not having it, because it is read as coverage. Removing the filter is
the whole fix, and it makes both rosters assert the same rule — *inside the roster block, a name in
entry position is a claim that the server serves it*. That rule is why `README.md` writes the ledger
states it glosses (`in_sync`, `stale`, …) without backticks inside that block and with them
everywhere else: the block is a tool list, so the carrier has to mean one thing there.

The honest limit: a count written in some other phrasing — "roughly fifty tools", "48 of them" — is
not covered, because catching that would mean reading prose for meaning. The fix for that is to
write the number in one of the three shapes above, which is what both files now do.
"""
from __future__ import annotations

import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "src" / "mcp" / "server.py"

#: Each roster: the file, the delimiters that bound it, the marker that states the total, the marker
#: that opens a section, and how a documented tool is spelled inside one.
ROSTERS = (
    {
        "path": "src/readme/keel-core.md",
        "start": re.compile(r"^## The (\d+) MCP tools\s*$", re.M),
        "stop": re.compile(r"^## ", re.M),
        "section": re.compile(r"^### .*?\((\d+)\)\s*$", re.M),
        "entry": re.compile(r"^\|\s*`(\w+)`\s*\|", re.M),
    },
    {
        "path": "README.md",
        "start": re.compile(r"^<summary><b>All (\d+) tools</b></summary>\s*$", re.M),
        "stop": re.compile(r"^</details>\s*$", re.M),
        "section": re.compile(r"^\*\*.*?\((\d+)\)\*\*", re.M),
        "entry": re.compile(r"`(\w+)`"),
    },
)

#: Every free-prose restatement of the total, matched on literal adjacency (an integer immediately
#: followed by the words "MCP tools"). A lexical fact, not an inference about what a sentence means.
TOTAL_PHRASE = re.compile(r"\b(\d+)\s+(?:typed\s+)?MCP tools\b")


def served() -> set:
    """Tool names the server exposes, from the decorations that ship."""
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    out = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            func = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(func, ast.Attribute) and func.attr == "tool":
                out.add(node.name)
    return out


def roster_body(spec: dict) -> tuple:
    """(claimed total, the roster's text) — bounded by the file's own structure."""
    text = (ROOT / spec["path"]).read_text(encoding="utf-8")
    head = spec["start"].search(text)
    assert head, f"{spec['path']}: no roster heading matching {spec['start'].pattern}"
    tail = spec["stop"].search(text, head.end())
    return int(head.group(1)), text[head.end(): tail.start() if tail else len(text)]


def sections(spec: dict, body: str) -> list:
    """[(claimed, [tool names documented in that section])] — each section bounded by the next."""
    marks = list(spec["section"].finditer(body))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((int(m.group(1)), spec["entry"].findall(body[m.end(): end])))
    return out


class TestTheDocumentedRosterIsTheServedRoster(unittest.TestCase):
    def test_the_server_exposes_tools_at_all(self):
        """If the decorator shape changes this gate goes vacuous, so it says so instead."""
        self.assertGreater(len(served()), 20)

    def test_every_served_tool_is_documented_and_nothing_else_is(self):
        known = served()
        for spec in ROSTERS:
            with self.subTest(spec["path"]):
                _, body = roster_body(spec)
                listed = [n for _, names in sections(spec, body) for n in names]
                self.assertEqual(sorted(set(listed)), sorted(known),
                                 f"{spec['path']} documents a different set than the server serves. "
                                 f"Documented and not served: {sorted(set(listed) - known)} — inside "
                                 f"the roster block an entry is a claim that the server serves it, "
                                 f"so a name that is not a tool does not belong in entry position. "
                                 f"Served and not documented: {sorted(known - set(listed))}.")
                self.assertEqual(len(listed), len(set(listed)),
                                 f"{spec['path']} lists a tool in two sections")

    def test_every_section_count_equals_what_the_section_holds(self):
        for spec in ROSTERS:
            for claimed, names in sections(spec, roster_body(spec)[1]):
                found = set(names)
                with self.subTest(path=spec["path"], claimed=claimed):
                    self.assertEqual(claimed, len(found),
                                     f"{spec['path']}: a section claims {claimed} tools and holds "
                                     f"{len(found)} — {sorted(found)}")

    def test_every_stated_total_equals_the_number_served(self):
        total = len(served())
        for spec in ROSTERS:
            claimed, _ = roster_body(spec)
            with self.subTest(spec["path"]):
                self.assertEqual(claimed, total)
        for path in ("src/readme/keel-core.md", "README.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            for stated in TOTAL_PHRASE.findall(text):
                with self.subTest(path=path, stated=stated):
                    self.assertEqual(int(stated), total,
                                     f"{path} says '{stated} MCP tools'; the server serves {total}")


if __name__ == "__main__":
    unittest.main()
