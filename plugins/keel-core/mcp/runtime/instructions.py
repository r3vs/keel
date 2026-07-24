"""Agent instruction-file carrier — project the elected to-be into the file every host actually reads.

The gap this closes
-------------------
The ledger is the single source of truth, and **no coding agent loads it**. Every host loads exactly
one thing without being asked: a markdown instruction file next to the code. So a project could have
a fully elected design and still hand a fresh agent — the executor in a new worktree, a teammate's
Codex, a reviewer on another host — a blank slate. The skills' own doctrine travels inside the skill;
*this project's decisions* had no carrier at all.

So the ledger gets projected into `AGENTS.md`, the way `generate.py` projects a data contract into
DB/ORM/API layers and `design_tokens.py` projects a DTCG contract into CSS. Same rule as both: the
projection is **generated, never authored**, and a drift-check proves it still matches its source.

Why `AGENTS.md` and a two-line `CLAUDE.md`, verified at each host's own loader
-----------------------------------------------------------------------------
- **Codex** — `read_agents_md` collects every `AGENTS.md` from the project root (found via
  `project_root_markers`, default `.git`) down to the cwd and concatenates them. `AGENTS.override.md`
  wins locally. Truncates past `config.project_doc_max_bytes`.
- **opencode** — `InstructionContext.observe` walks up for `AGENTS.md`, falling back to `CLAUDE.md`,
  then the global `~/.config/opencode/AGENTS.md`, then `~/.claude/CLAUDE.md`. First match per category.
- **Pi** — `loadProjectContextFiles` loads `~/.pi/agent/AGENTS.md`, then every ancestor's
  `AGENTS.md`/`CLAUDE.md` (case-insensitive), then the cwd's. Concatenated.
- **Claude Code** — reads `CLAUDE.md`, **not** `AGENTS.md`; its own docs prescribe the bridge
  (`@AGENTS.md` at the top of `CLAUDE.md`). Files from root down to cwd concatenate; subdirectory
  files load lazily when a file there is read.

**No import syntax is portable.** Only Claude Code parses `@path` (depth 4, skipping code spans and
fenced blocks). Codex, opencode and Pi concatenate plain text — an `@` line there is a literal string.
That single fact decides the whole design: **anything that must be always-on is inlined here, never
imported.** It is also what refutes the old `project-memory` claim that a root `MEMORY.md` is
"always-on context via AGENTS.md" — it is not, on any of the four (see `core/instruction-files.md`).

A symlink `CLAUDE.md -> AGENTS.md` also works and is what the docs offer first, but it needs
Administrator or Developer Mode on Windows, so the bridge file is what this module writes.

Why a *managed region*, not a generated file
--------------------------------------------
`AGENTS.md` is the user's — hand-written prose about their project, and on their machine it may
predate us. Owning the whole file would either destroy that or force us to merge prose, which is
exactly the model-judgment step this repo forbids. So we own a fenced region and nothing else:
everything outside `<!-- keel:begin -->` / `<!-- keel:end -->` is untouched, byte for byte.

The markers are HTML comments for a reason beyond convention: **Claude Code strips block-level HTML
comments before injecting the file into context**, so the fence costs zero tokens where the budget is
tightest, while staying visible to a human reading the file. On the other three they are inert text.

The begin marker carries a `sha256` of the body it fenced. That is what lets the drift-check
distinguish two failures a re-render alone cannot tell apart: the region **hand-edited** (body no
longer hashes to the recorded value — someone wrote a decision into the projection instead of into
the ledger, the divergence this package exists to find) versus merely **stale** (body still matches
its recording, but the ledger has moved on). Different causes, different fixes.

Budget is a correctness constraint, not a style preference
-----------------------------------------------------------
Codex truncates at `project_doc_max_bytes`; Claude Code loads the file whole but its own guidance is
under 200 lines, past which adherence measurably drops. A ledger with 300 decided pins dumped here
would silently push the *user's own* instructions past a byte limit on one host and dilute everything
on another. So the region is an **index with a hard line budget**, and truncation is always
**declared** (`+N more — read the ledger`), never silent: a shortened list that looks complete is the
same lie as a clean bill of health from a scanner that did not run.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

BEGIN_RE = re.compile(r"<!--\s*keel:begin(?:\s+v(?P<v>\d+))?(?:\s+sha256=(?P<sha>[0-9a-f]{12}))?\s*-->")
END = "<!-- keel:end -->"
_END_RE = re.compile(r"<!--\s*keel:end\s*-->")
VERSION = 1

#: default line budget for the managed region (see module docstring — this is a host limit, not taste)
MAX_LINES = 60

#: The region's header. Always emitted: a block of rules in someone's file with no statement of where
#: it came from, who may change it, and what to do when it does not answer the question is worse than
#: no block at all. `{ledger}` is the only substitution.
_HEAD_TEMPLATE = (
    "## Elected design — generated from the decisions ledger by Keel",
    "",
    "This project's decisions live in `{ledger}`, the single source of truth; each one",
    "carries a `flip_criteria` saying when to reopen it. Read it with the `ledger_summary` MCP",
    "tool before changing anything below. **Only the human's interview elects a decision.** If",
    "this section does not answer your question, do not decide it silently — surface a vetoable",
    "assumption pin (`ledger_surface_assumption`) and keep going.",
)
#: Header + a heading + one item + its clip note. Below this a budget cannot be honoured at all, and
#: overrunning it silently is the exact failure the budget exists to prevent — so it is refused.
_MIN_LINES = len(_HEAD_TEMPLATE) + 4

_SEVERITY_RANK = {"blocker": 0, "high": 1, "medium": 2, "low": 3}
#: states in which the human has committed something — these are the elected truth
_ELECTED = ("decided", "accepted", "resolved")
#: states in which nothing is elected yet — an agent must NOT answer these on its own
_OPEN = ("detected", "needs_input", "brainstorming")


def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def _order(pin: dict) -> tuple:
    return (_SEVERITY_RANK.get(pin.get("severity", "low"), 9), str(pin.get("id", "")))


def _pin_line(pin: dict, with_outcome: bool) -> str:
    kind = pin.get("kind", "other")
    if kind == "other" and pin.get("kind_detail"):
        kind = f"other:{pin['kind_detail']}"
    line = f"- `{pin.get('id', '?')}` [{kind}] {pin.get('title', '').strip()}"
    outcome = (pin.get("decision") or {}).get("outcome") if with_outcome else None
    if outcome:
        line += f" — **{outcome}**"
    return line


def _section(title: str, lines: list, remaining: int, more_hint: str) -> list:
    """A titled list fitted into `remaining` lines, with any clip DECLARED (never silent).

    Costs 2 lines of chrome (a blank line and the heading) before any content, so a section that
    cannot fit its heading plus one item is dropped whole rather than emitted as a bare title.
    """
    if not lines or remaining < 4:
        return []
    out = ["", f"### {title}"]
    room = remaining - len(out)
    if len(lines) <= room:
        return out + lines
    kept = lines[: max(room - 1, 1)]
    return out + kept + [f"- *(+{len(lines) - len(kept)} more — {more_hint})*"]


def render(data: dict, max_lines: int = MAX_LINES, ledger_path: str = "ledger.json",
           generated: Optional[list] = None) -> str:
    """The managed region's body: the ledger's elected state as instructions, markers excluded.

    Four sections, in the order an agent needs them: the standing rules it must obey, the decisions
    already elected, the forks NOT yet elected (so it surfaces an assumption instead of inventing an
    answer), and the generated files it must never hand-edit. Ordering is severity then id — stable,
    so an unchanged ledger re-renders byte-identically and the drift-check has no false positives.

    `max_lines` bounds the WHOLE region, not each section: the budget exists because two hosts
    penalize length (one truncates by bytes, one loses adherence), and a per-section cap would let
    four sections quietly sum past it. Sections are filled in the order above and each declares what
    it dropped, so the first thing to survive a tight budget is the rules an agent must obey.

    `generated` is passed in rather than read from the ledger: the paths come from what
    `generate_layers` / `generate_tokens` reported writing. A file list is a fact about a write that
    happened, not a decision, so it does not belong in the ledger schema. It is recovered across runs
    from the previous region (`extract_generated`), so a regeneration that does not re-state it does
    not silently drop it — see the note there.
    """
    if max_lines < _MIN_LINES:
        raise ValueError(
            f"max_lines={max_lines} cannot be honoured: the header alone is {len(_HEAD_TEMPLATE)} "
            f"lines and a region without it would be an unattributed block of rules in someone's "
            f"file. Minimum {_MIN_LINES}. Refusing rather than silently overrunning the budget — an "
            f"exceeded cap that reports success is the failure this budget exists to prevent."
        )
    pins = list(data.get("pins") or [])
    policies = list(data.get("policies") or [])

    head = [line.format(ledger=ledger_path) for line in _HEAD_TEMPLATE]

    elected = sorted((p for p in pins if p.get("state") in _ELECTED), key=_order)
    openp = sorted((p for p in pins if p.get("state") in _OPEN), key=_order)
    sections = [
        ("Standing rules",
         [f"- {p.get('rule', '').strip()} *(applies to "
          f"{', '.join(f'{k}={v}' for k, v in (p.get('applies_to') or {}).items()) or 'all pins'}; "
          f"default: {p.get('default_outcome')})*" for p in policies],
         "see `policies` in the ledger"),
        ("Elected", [_pin_line(p, True) for p in elected], "run `ledger_summary`"),
        ("NOT decided — do not encode an answer", [_pin_line(p, False) for p in openp],
         "run `interview_next`"),
        ("Generated — never hand-edit", [f"- `{g}`" for g in sorted(str(x) for x in (generated or []))],
         "see the contract"),
    ]

    body: list = []
    for title, lines, hint in sections:
        chunk = _section(title, lines, max_lines - len(head) - len(body), hint)
        body += chunk

    if not body:
        body = ["", "*No decisions elected yet — run the skill's interview before writing code.*"]
    return "\n".join(head + body).rstrip() + "\n"


def wrap(body: str) -> str:
    """Body → the fenced region, begin marker carrying the body's fingerprint."""
    return f"<!-- keel:begin v{VERSION} sha256={_fingerprint(body)} -->\n{body}{END}\n"


def extract(text: str) -> Optional[dict]:
    """The managed region found in `text`, or None. `{'body', 'recorded', 'start', 'end'}`.

    `recorded` is the fingerprint the begin marker claims; comparing it to the body's actual hash is
    what separates a hand-edited region from a stale one.
    """
    begin = BEGIN_RE.search(text or "")
    if not begin:
        return None
    end = _END_RE.search(text, begin.end())
    if not end:
        return None
    body = text[begin.end():end.start()].lstrip("\n")
    return {"body": body, "recorded": begin.group("sha"), "start": begin.start(), "end": end.end()}


_GENERATED_HEADING = "### Generated — never hand-edit"
_BULLET_PATH_RE = re.compile(r"^- `([^`]+)`\s*$")


def extract_generated(text: Optional[str]) -> list:
    """The generated-file list recorded in an existing region, so a regeneration can carry it forward.

    Without this the list is transient input, and a caller that regenerates for any other reason —
    a pin was decided, a policy changed — silently drops the "never hand-edit" section while the
    Claude-only rule file keeps asserting it. Two carriers of one fact, disagreeing, with the
    drift-check reporting `in_sync` because it was asked the same incomplete question. That is the
    precise failure this whole module exists to prevent, so the region stores its own answer.

    Clearing stays possible and stays explicit: pass `[]`, not "omit the argument".

    One honest limit: if the section was clipped by the line budget, only the listed paths come back
    — the clip note is not a path and is skipped. The clip is declared in the region either way, so
    this loses nothing that was not already declared missing, but a caller holding the full list
    should pass it rather than rely on recovery.
    """
    found = extract(text or "")
    if not found:
        return []
    out, inside = [], False
    for line in found["body"].splitlines():
        if line.startswith("### "):
            inside = line.strip() == _GENERATED_HEADING
            continue
        if inside and (m := _BULLET_PATH_RE.match(line.strip())):
            out.append(m.group(1))
    return out


def apply(text: Optional[str], body: str) -> str:
    """`text` with the managed region set to `body`; everything outside it is preserved byte for byte.

    An absent region is appended (never prepended: the user's own opening prose stays the first thing
    a host reads, and every host concatenates rather than truncates, so position is not a priority
    signal). An absent file becomes a file with a heading and the region.
    """
    region = wrap(body)
    if not text:
        return "# AGENTS.md\n\n" + region
    found = extract(text)
    if found:
        return text[: found["start"]] + region.rstrip("\n") + text[found["end"]:]
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + region


def drift_check(text: Optional[str], body: str) -> dict:
    """Is the file's managed region what the ledger currently projects?

    `status` is one of:
      - `absent`      — no region in the file (or no file): the carrier was never written.
      - `hand_edited` — the body no longer hashes to what the begin marker recorded. Someone wrote
                        into the projection. The fix is to write it into the LEDGER; regenerating
                        would silently discard it, so this is reported, never auto-healed.
      - `stale`       — the region is intact but the ledger has moved: regenerate.
      - `in_sync`     — nothing to do.
    """
    found = extract(text or "")
    if not found:
        return {"status": "absent", "in_sync": False,
                "detail": "no keel managed region — run generate_instructions"}
    actual = _fingerprint(found["body"])
    if found["recorded"] and found["recorded"] != actual:
        return {"status": "hand_edited", "in_sync": False, "recorded": found["recorded"],
                "actual": actual,
                "detail": "the managed region was edited by hand. Its content is a projection: put "
                          "the change in the ledger (a pin/decision), then regenerate — regenerating "
                          "now would discard it."}
    if found["body"].rstrip("\n") != body.rstrip("\n"):
        return {"status": "stale", "in_sync": False,
                "detail": "the ledger has moved since this region was written — regenerate"}
    return {"status": "in_sync", "in_sync": True, "detail": ""}


# ── the Claude Code bridge ──────────────────────────────────────────────────

BRIDGE_LINE = "@AGENTS.md"
_BRIDGE_RE = re.compile(r"^\s*@AGENTS\.md\s*$", re.MULTILINE)


def claude_bridge(text: Optional[str]) -> Optional[str]:
    """`CLAUDE.md` content that makes Claude Code read the same `AGENTS.md` as the other three hosts.

    Returns None when the file already imports it — the bridge is idempotent and never rewrites a
    file the user has built on. When adding it to an existing `CLAUDE.md` the import goes **first**:
    Claude Code expands imports in place, and a project's own instructions should be able to override
    the shared ones, so the shared file must be read before them.

    The import must sit outside backticks and outside fenced blocks to be parsed at all — the same
    rule that quietly made this repo's own ``MEMORY.md`` mention a no-op.
    """
    if text and _BRIDGE_RE.search(text):
        return None
    if not text:
        return (f"{BRIDGE_LINE}\n\nClaude Code reads `CLAUDE.md`, not `AGENTS.md`; the import above is the\n"
                "bridge, so this host and every other one read the same instructions.\n")
    return f"{BRIDGE_LINE}\n\n{text.lstrip()}"


# ── the Claude-only path-scoped layer ───────────────────────────────────────

def rule_generated_files(paths: list, source: str, tool: str) -> str:
    """A `.claude/rules/*.md` file scoping "these are generated" to the exact paths that were written.

    Claude Code is the **only** one of the four hosts with conditional, path-scoped instructions
    (`paths:` frontmatter, matched when it reads a file). opencode's `instructions` globs choose which
    instruction files to concatenate, always-on; Codex and Pi have nothing. So this is an additive
    optimization for one host and must never be the only carrier — the same fact is inlined in the
    portable `AGENTS.md` region ("Generated — never hand-edit"), which is what the other three read.

    The globs are the paths `generate_layers` / `generate_tokens` actually wrote, passed straight
    through. Not a pattern guessed from a convention: the writer reported them.
    """
    listed = "\n".join(f'  - "{p}"' for p in sorted(paths))
    return (
        "---\n"
        f"{'paths:' if paths else 'paths: []'}\n"
        f"{listed + chr(10) if paths else ''}"
        "---\n\n"
        "# Generated files — do not hand-edit\n\n"
        f"These files are generated from `{source}` by the `{tool}` tool. A change made here is\n"
        "erased on the next generation, and until then the layers disagree — which is precisely the\n"
        "drift this project is set up to prevent.\n\n"
        f"To change what they contain, edit `{source}` and re-run `{tool}`. If the contract itself is\n"
        "wrong, that is a decision: open a pin (`ledger_add_pin`) and let the interview elect it.\n"
    )
