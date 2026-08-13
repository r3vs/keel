"""A number this repo computes, restated in this repo's prose, checked against what computes it.

**Why this gate exists, in the register's own words.** Three consecutive rounds of `docs/open-gaps.md`
ended with the same paragraph in their report: a stale count was corrected *"rather than registered,
and I name it for scope honesty… Neither is covered by any gate, and that gap in the gate is not
fixed."* The instances were `README.md`'s "592 → 720 → 738 → 770 tests green in CI", `src/readme/
keel-core.md`'s "MCP tools | **37**" while the server served 54, and `CLAUDE.md`'s ledger-spec
version, which sat at v0.6 while the spec was at v0.16 and then v0.19. Nobody was careless: each was
found by a human who happened to edit an adjacent line, which means the ones nobody edited beside
are still wrong. That is the class — **a claim in prose with no carrier** — and this is the subset of
it that is decidable, because for these claims the carrier exists and is one call away.

The rule, and it is the same rule `check_tool_carriers.py` and `check_schema_fields.py` run on:
**the number is computed here, never kept here.** Nothing below holds a copy of the answer; each
fact names the thing that knows it — `unittest`'s own discovery for the suite size, the `@mcp.tool`
decorations for the roster, `ledger.SCHEMA_VERSION` for the schema. A gate holding its own copy of
the number it checks is the drift it exists to catch, one file over.

**What it is scanned over, and the two deliberate exclusions.** Every markdown that describes the
repo *as it now stands*. `docs/open-gaps.md` and `CHANGELOG.md` are excluded and the reason is
structural rather than convenient, and it is the same reason twice: both are **historical registers
by construction**. `open-gaps.md` keeps its closed sections verbatim on purpose, so it quotes
`Ran 565 tests, OK (skipped=28)` and "617 tests and eight green linters" as records of what was
true on a past day; a changelog entry for 0.1.0 restates the ~170-test suite and the v0.6 ledger
spec of the day 0.1.0 shipped, and rewriting those to today's numbers would be falsifying the
record, not fixing it. Checking either against today would make the file un-writable in its own
declared shape. Every other doc in scope is making a present-tense claim.

**`MEMORY.md` is in scope as of 2026-08-13, and it is the instance this gate was written for.**
It sat outside `SCOPE` while claiming "**179 tests** in CI" against a suite of 1017, and while
asserting that cognee was among the declared MCP servers when the build declares only the rows its
own table marks `→ **http**`. That is exactly the shape the docstring above describes — a claim in
prose with a carrier one call away, wrong because nobody happened to edit the line beside it — and
the file was invisible to the gate for the whole time. An unlisted file reads as an oversight in one
shape and as a decision in the other, which is why both lists below are explicit.

**The honest limit, stated because a gate that hides one is worse than none.** A restatement in a
phrasing nobody registered below is not checked — "roughly fifty tools", "about eight hundred
tests". That is the same limit `tests/test_tool_roster.py` declares for the same reason, and the
same answer applies: the fix is to write the number in one of the shapes here, which is what the
files in scope now do. What this gate adds over that one is coverage of the OTHER word orders and
the OTHER files — `test_tool_roster.TOTAL_PHRASE` matches `<int> MCP tools` in two files, so the
table cell `| MCP tools | **58** |` and every claim outside those two files were invisible to it,
which is precisely how the "37" shipped.

**The version claim needed a convention, and finding that out is why this gate was built by
running it.** A spec version in prose means one of two incompatible things: *this feature arrived
in v0.7* (history — true for ever) or *the spec is at v0.7* (currency — must be bumped). The first
draft matched `(spec v0.X)` and immediately reported
`verification-before-completion/SKILL.md`'s `` `correctness_unknown` (spec v0.7) `` as stale, which
it is not. Deciding which one a sentence means by reading around it is precisely the heuristic this
repo forbids its own linters, so the phrasing carries it instead: **a currency claim says
`currently v0.X`**, a historical one does not, and the four sites that make one now say so. The
limit that leaves is real and is stated rather than papered over: a NEW currency claim written
without the word is not checked.

**One check was built, run, and removed — recorded here so nobody rebuilds it.** *"No document may
name a spec version higher than the runtime's, because history cannot be in the future"* needs no
convention at all and looked free. Run, it reported `docs/packaging.md`'s
`@earendil-works/pi-coding-agent v0.81.1` as a spec version from the future. The premise was the
bug: a `v0.X` in prose belongs to **whatever the sentence is about**, and this repo's prose
legitimately names other projects' versions — Pi's, `fastmcp`'s, the plugin's. Nothing lexical says
which project a version token belongs to, and deciding it from the words around it is the same
heuristic the currency/history split above already refused. So it is gone, and the equality half —
which knows what it is matching because each pattern was written for a named site — is the whole
gate.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "runtime"))

#: Present-tense descriptions of the repo. Anything not here is not scanned, which is why the list
#: is paths and globs rather than "every .md" minus exceptions — an unlisted file reads as an
#: oversight in one shape and as a decision in the other.
SCOPE = ("README.md", "CLAUDE.md", "AGENTS.md", "MEMORY.md",
         "src/readme/*.md", "src/core/*.md", "src/skills/*/SKILL.md",
         "src/skills/*/references/*.md", "docs/packaging.md")

#: Kept out, with the reason. Both are historical registers by construction, so their numbers are
#: records of a past day rather than claims about this one:
#:  - `open-gaps.md` keeps its closed sections verbatim — that is the point of the file.
#:  - `CHANGELOG.md` restates, per released version, the suite size and ledger-spec version that
#:    were true when that version shipped (0.1.0's "~170 tests", "spec v0.6"). Holding those to
#:    today's carrier would demand rewriting history to keep a linter quiet, which inverts what the
#:    file is for. Present-tense claims about the package belong in README/CLAUDE/MEMORY, which are
#:    all in SCOPE — so nothing is lost by excluding this one, and the exclusion is recorded here
#:    rather than left as an unlisted-file silence.
EXCLUDED = {"docs/open-gaps.md", "CHANGELOG.md"}


def suite_size() -> int:
    """How many tests `python -m unittest discover -s tests` runs — asked of the loader itself.

    Discovery imports the test modules and builds the suite; it runs nothing, so this costs about a
    fifth of a second. A module that fails to import becomes a `_FailedTest` case, which would still
    be *counted* — so that is checked rather than assumed, because a gate that silently counts its
    own breakage as coverage is this file's whole subject.
    """
    # No `top_level_dir`: `tests/` is not a package, and passing the repo root as one is the
    # difference between this and `python -m unittest discover -s tests`, which is the command whose
    # number the prose quotes. Absolute start dir, so the answer does not depend on the cwd.
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                yield from walk(item)
            else:
                yield item

    broken = [c for c in walk(suite) if type(c).__name__ == "_FailedTest"]
    if broken:
        raise SystemExit(f"ERROR {len(broken)} test module(s) failed to import, so the suite size "
                         f"below would be counting the breakage: {sorted(str(c) for c in broken)}")
    total = suite.countTestCases()
    if total < 100:
        raise SystemExit(f"ERROR discovery found only {total} tests — the layout changed and this "
                         f"gate just went vacuous")
    return total


def served_tools() -> int:
    """The `@mcp.tool` decorations in `src/mcp/server.py` — the same authority
    `scripts/check_tool_carriers.py` and `tests/test_tool_roster.py` both use."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_tool_carriers
    tree = ast.parse(check_tool_carriers.SERVER.read_text(encoding="utf-8"))
    total = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            func = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(func, ast.Attribute) and func.attr == "tool":
                total += 1
    if total == 0:
        raise SystemExit("ERROR no @mcp.tool decorations found — the decorator shape changed and "
                         "this gate just went vacuous")
    return total


def spec_version() -> str:
    import ledger
    return ledger.SCHEMA_VERSION


def _budget():
    """`check_description_budget.py`'s own numbers, asked of the gate rather than recomputed here.

    Two copies of "how long are the model-invoked descriptions" would be the duplication this file
    exists to catch, committed by the file that catches it.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cdb", pathlib.Path(__file__).resolve().parent / "check_description_budget.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    total = sum(len(mod.description_of(s)) for s in mod.model_invoked())
    return total, mod.LISTING_BUDGET_CHARS - total


def listing_chars() -> str:
    """Returned already comma-grouped, because the comparison is against `str(truth)`.

    `render` is display-only — `main()` compares `match.group(1) == str(truth)` — so a carrier whose
    prose spelling is `1,178` has to *be* `1,178`, or the gate reports a number as stale against
    itself.
    """
    return f"{_budget()[0]:,}"


def listing_headroom() -> int:
    return _budget()[1]


#: Each fact: what it is, how the prose spells it, and the function that knows the answer. The
#: patterns capture exactly one group, and each is annotated with the site it was written for, so a
#: pattern that stops matching anything is visible as a pattern nobody uses rather than as coverage.
FACTS = (
    {
        "label": "the size of the test suite",
        "carrier": suite_size,
        "render": str,
        "patterns": (
            re.compile(r"\*?\*?(\d+) tests? green"),            # README.md's status line
            re.compile(r"(\d+) tests? passing in CI"),
            # README.md's shields.io BADGE, added in 2026-08-06. It said `tests-592 passing` while
            # the status line 314 lines below it said 828 — two claims about one number, in one
            # file, disagreeing by 236. This gate was built for exactly that instance and its own
            # docstring names "592" three times; what it did not do was quantify over the shape the
            # number is written in when it is a badge, where the space is `%20` and the word is
            # `passing` rather than `green`. A gate that covers the prose and not the picture of
            # the prose is the corpus problem in miniature.
            re.compile(r"tests-(\d+)%20passing"),
        ),
    },
    {
        "label": "the number of tools the MCP server serves",
        "carrier": served_tools,
        "render": str,
        "patterns": (
            re.compile(r"\b(\d+)\s+(?:typed\s+)?MCP tools\b"),  # README.md, keel-core.md prose
            re.compile(r"^\|\s*MCP tools\s*\|\s*\*\*(\d+)\*\*", re.M),   # keel-core.md's table cell
            re.compile(r"[Aa]ll (\d+) tools"),                  # README.md's <details> summary
        ),
    },
    {
        "label": "the version of the decisions-ledger spec",
        "carrier": spec_version,
        "render": lambda v: f"v{v}",
        "patterns": (
            re.compile(r"currently v(0\.\d+)"),                     # the canonical currency phrase
            re.compile(r"\(shared, v(0\.\d+)\)"),                   # CLAUDE.md's architecture list
            re.compile(r"\(v(0\.\d+)\) is authoritative"),          # CLAUDE.md's conventions list
            re.compile(r"decisions-ledger spec \(v(0\.\d+)\)"),     # keel-core.md's core listing
        ),
    },
    # Added 2026-08-13, at the merge that proved the need. `screenshot-to-code` arrived from a
    # parallel branch still model-invoked with a 748-character description, and the total jumped to
    # 1,809 against a 1,200 budget. `check_description_budget.py` caught that, because it gates the
    # *ceiling*. What had no gate was the number once CLAUDE.md restated it — and this one drifts
    # more easily than the others, because the budget is a SHARED POOL: editing any one skill's
    # description moves a number written in a file that skill has nothing to do with.
    #
    # Only CLAUDE.md is covered, and deliberately so. `docs/open-gaps.md` §31 states the same two
    # numbers and is in EXCLUDED — it is a dated register whose entries record what was true on the
    # day of a round, exactly like CHANGELOG.md. Patterns aimed at it would match nothing here, which
    # is the fake coverage the note above the FACTS table warns about.
    {
        "label": "the listing characters Keel's model-invoked descriptions occupy",
        "carrier": listing_chars,
        "render": str,
        "patterns": (
            re.compile(r"([\d,]+) / 1,200"),          # CLAUDE.md's invocation-axis bullet
        ),
    },
    {
        "label": "the characters left in Keel's share of the listing budget",
        "carrier": listing_headroom,
        "render": str,
        "patterns": (
            re.compile(r"~(\d+) to spare"),           # CLAUDE.md's invocation-axis bullet
        ),
    },
)

def in_scope() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for pattern in SCOPE:
        if any(ch in pattern for ch in "*?"):
            paths += sorted(ROOT.glob(pattern))
        else:
            candidate = ROOT / pattern
            if candidate.exists():
                paths.append(candidate)
    return [p for p in paths if p.relative_to(ROOT).as_posix() not in EXCLUDED]


def main() -> int:
    errors = 0
    checked = 0
    files = in_scope()
    for fact in FACTS:
        truth = fact["carrier"]()
        shown = fact["render"](truth)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for pattern in fact["patterns"]:
                for match in pattern.finditer(text):
                    checked += 1
                    if match.group(1) == str(truth):
                        continue
                    errors += 1
                    line = text[: match.start()].count("\n") + 1
                    print(f"ERROR {path.relative_to(ROOT).as_posix()}:{line}: says "
                          f"`{match.group(0).strip()}` — {fact['label']} is {shown}. The number is "
                          f"computed, not remembered; restate it or delete the claim.")
    print(f"\n{len(files)} file(s) scanned, {len(FACTS)} computed fact(s), "
          f"{checked} restatement(s) found — {errors} stale")
    if not checked:
        print("ERROR no restatement matched any pattern at all — either the prose was rewritten or "
              "this gate is checking nothing")
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
