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

What the budget bought and what it refused: `evidence` (v0.10, v0.11)
---------------------------------------------------------------------
Each decision records the rung its answer travelled on — `elicited` / `transcribed` / `brief` /
`cascaded`. Two ways to project that, and only one earns its bytes:

- **Per decision, refused.** The `Elected` list is the section most likely to be clipped already, and
  a ` (transcribed)` suffix on every entry costs bytes on every line to restate a fact that is
  identical for nearly all of them — the elicitation rung only fires on hosts that declare the
  capability. Paying per line for a mostly-constant value is what pushes the *user's* prose past
  Codex's byte cap.
- **One header line, taken** — and only when a rung worth weighing is actually present: some
  decision `transcribed` (an agent's relay), or `cascaded` (one policy election deciding a whole
  cluster), or written with no rung recorded at all. A project with none pays nothing, and the line
  says what the agent should DO rather than merely reporting a number. The full per-decision detail
  is one `ledger_summary` call away (`decisions_by_evidence`) and is stated in full on the map,
  which is where a human looks.

  The line reports only rungs that were *recorded*. It used to read a missing `evidence` as
  `transcribed`, which was a claim about pre-v0.10 events nobody had evidenced — and after v0.11 it
  would have been wrong in a second way, since a policy cascade is the one case where a missing rung
  is most likely. Unrecorded is now its own clause, which is what the map and `ledger_summary`
  already do.

  And the rung is READ, not copied (`ledger.decision_rung`, v0.13). A cascade written before v0.11
  records `transcribed`, so this line told the user that N of their decisions had been relayed by an
  agent when a policy they elected themselves had decided them. The clauses are only worth their
  bytes if each one is true of the ledger it is generated from.

  v0.15 adds one sentence for the **standing rules** the region already lists, and v0.16 makes the
  rule behind it `ledger.policy_weakness` — the SAME predicate the map's badge reads. It was
  re-stated here as "no rung, or a relay with no quote" while the map badged every weak rung, so
  two surfaces counted one ledger and printed different totals (two, and one, on the repo's own
  preview fixture). A number a reader cannot reconcile is worse than no number. A `Policy` is an
  election over a whole cluster and is what every `cascaded` decision derives from, so weighing the
  cascade while saying nothing about the election behind it weighs the wrong end. It is also the one
  clause that can fire with an empty `decision_log`: a rule that cascaded over no pin still governs
  what gets written next, and that state was visible on no surface at all.

Which pins reach the region, and what the budget refused there too
------------------------------------------------------------------
The two lists are `ledger.SETTLED_STATES` and `ledger.OPEN_STATES` — read, never re-listed. This
module used to keep its own pair (`("decided","accepted","resolved")` and
`("detected","needs_input","brainstorming")`), which covered six of the schema's eight states, so a
`deferred` pin and a `correctness_unknown` pin reached a fresh agent's always-on context **in no
section at all**. Reproduced on a two-pin ledger — one deferred `blocker` ("Multi-tenant isolation
is unimplemented"), one `correctness_unknown` `blocker` ("Webhook replay") — where the region
rendered the header, the evidence note, and then *"No decisions elected yet — run the skill's
interview before writing code."* Two blockers, and the sentence said none existed. That is the same
bug `map.py` carried until its `SETTLED` set was sourced from `ledger.SETTLED_STATES`, in this file,
one surface over: **a set the schema owns cannot be kept here, because a state added there will not
come here.** The two ledger tuples are complements over `ledger.STATES`, so every state now has
exactly one home, and `tests/test_instructions.py` holds that rather than trusting it.

What the budget refused, deliberately: **no per-pin state token.** The bucket already carries the
only instruction that differs between these pins — *build on this* versus *do not answer this
yourself* — and that instruction is identical for all four states inside each bucket. A ` (deferred)`
suffix would cost bytes on every line of the section most likely to be clipped, to restate what its
heading says. The headings are worded to be true of every member instead: `resolved` and `deferred`
are settled without being "elected" in the narrow sense, and `correctness_unknown` is open without
anyone having failed to decide it — which is why neither heading says "decided" any more. The exact
state of any pin is one `ledger_summary` call away and is in the map's sub-line, where a human looks.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

BEGIN_RE = re.compile(r"<!--\s*keel:begin(?:\s+v(?P<v>\d+))?(?:\s+sha256=(?P<sha>[0-9a-f]{12}))?\s*-->")
END = "<!-- keel:end -->"
_END_RE = re.compile(r"<!--\s*keel:end\s*-->")
VERSION = 1

#: HYPOTHESIS, tunable — the default line budget for the managed region. Split the claim honestly:
#: that a budget must EXIST has a carrier (Codex truncates by bytes, Claude Code loses adherence past
#: ~200 lines — see the module docstring), but the value 60 does not. It is a conservative choice
#: well under the known ceilings, not a measurement.
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
#: The evidence note (blank line + one line), emitted only when a weak rung is present. Counted in
#: the floor below so a tight budget can never squeeze every section out and fall back to "nothing
#: elected yet" on a ledger that has decisions — the note must cost the sections nothing.
_NOTE_LINES = 2

#: Header + the evidence note + a heading + one item + its clip note. Below this a budget cannot be
#: honoured at all, and overrunning it silently is the exact failure the budget exists to prevent —
#: so it is refused.
_MIN_LINES = len(_HEAD_TEMPLATE) + _NOTE_LINES + 4

_SEVERITY_RANK = {"blocker": 0, "high": 1, "medium": 2, "low": 3}


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


#: One clause per `ledger.POLICY_WEAKNESS` code, in the order a reader weighs them. The
#: classification is the ledger's (one rule, one implementation); only the wording is this
#: surface's, because a badge on a map and a line in an agent's always-on context address different
#: readers. A code with no clause here would surface as a bare token, so the mapping is total and
#: `tests/test_instructions.py` holds it to the tuple.
_POLICY_WEAKNESS_CLAUSE = {
    "no_rung": "elected with no rung recorded",
    "unknown_rung": "elected on a rung this projection does not know",
    "unquoted_relay": "relayed with no quote",
}


def _evidence_note(data: dict) -> list:
    """One line naming which decisions are worth weighing before building on them — or nothing.

    Reads the `decision_log`, not the pins: the rung is a property of the write, and `pin.decision`
    carries only `{event_id, outcome}`. Emitted only when there is something to weigh, because a
    line that always says "0 of N" is bytes spent to report the absence of a problem.

    Four clauses, at most one line, composed from what is present. They are kept apart rather than
    summed into "N weak" because they fail differently: a relay may be an invention, a cascade may
    simply not fit this pin, an unrecorded rung is not weak — it is unknown — and a rung the schema
    does not name is a road this projection cannot describe.

    A second sentence covers the STANDING RULES the section below lists (v0.15). Those are elections
    too — over a whole cluster — and their rung is the thing every `cascaded` decision rests on, so
    a projection that weighs the cascade and not the election it derives from weighs the wrong end.
    It costs bytes only when a rule is actually weak, and it earns them where the leverage is: a
    policy elected on an agent's unquoted relay governs pins this file may not even list. Which
    rules those are is `ledger.policy_weakness`'s answer and not this module's (v0.16) — the two
    surfaces that report it must not be able to disagree about the count.
    """
    events = [e for e in (data.get("decision_log") or []) if str(e.get("id", "")).startswith("ev_")]
    policies = list(data.get("policies") or [])
    sentences = []
    if events:
        # `ledger.decision_rung`, never `e["evidence"]`: a pre-v0.11 cascade records `transcribed`,
        # and reading it literally put "N relayed by an agent" into the user's own AGENTS.md about
        # decisions their elected policy made. One reader for that, in the module owning the schema.
        from ledger import DECISION_EVIDENCE, decision_rung
        rungs = [decision_rung(e) for e in events]
        clauses = []
        relayed = rungs.count("transcribed")
        cascaded = rungs.count("cascaded")
        unrecorded = sum(1 for r in rungs if not r)
        # A rung the schema does not name is not the same as none: the file states how the answer
        # travelled and this projection does not know that road. Counted apart for the same reason
        # the other three are, and counted AT ALL because the map badges it weak — a rung nobody
        # here recognises used to fall through every clause and be reported by this surface as
        # nothing, while the map called it out. One ledger, two numbers.
        unknown = sum(1 for r in rungs if r and r not in DECISION_EVIDENCE)
        if relayed:
            clauses.append(f"{relayed} relayed by an agent (`transcribed`), not elicited from the user")
        if cascaded:
            clauses.append(f"{cascaded} cascaded from a policy the user elected once for the cluster")
        if unrecorded:
            clauses.append(f"{unrecorded} with no rung recorded at all")
        if unknown:
            clauses.append(f"{unknown} on a rung this projection does not know")
        if clauses:
            sentences.append(f"of {len(events)} recorded decisions, " + "; ".join(clauses))
    # A rule is weak on the counts `ledger.policy_weakness` names — the SAME predicate the map's
    # badge reads (v0.16). It used to be re-stated here as "no rung, or a relay with no quote",
    # which is a narrower rule than the map's, so the two surfaces counted one ledger and reported
    # different numbers: the fixture in `scripts/preview_map.py` badged two and this line said one.
    # Reported even when the log is empty: a policy that cascaded over nothing still governs what
    # gets written next, and that is exactly the state no surface used to show.
    from ledger import policy_weakness
    reasons = [policy_weakness(p) for p in policies]
    weak = sum(1 for r in reasons if r)
    if weak:
        why = ", or ".join(clause for code, clause in _POLICY_WEAKNESS_CLAUSE.items()
                           if code in reasons)
        sentences.append(f"{weak} of the standing rules below "
                         f"{'was' if weak == 1 else 'were'} {why}")
    if not sentences:
        return []
    return ["", "*Evidence: " + ". ".join(sentences) + " — weigh those before building on one.*"]


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

    Four sections, in the order an agent needs them: the standing rules it must obey, the pins that
    have stopped being open (`ledger.SETTLED_STATES` — build on these), the pins still awaiting
    something (`ledger.OPEN_STATES` — surface an assumption instead of inventing an answer), and the
    generated files it must never hand-edit. Ordering is severity then id — stable, so an unchanged
    ledger re-renders byte-identically and the drift-check has no false positives.

    The two state sets come from the ledger and are complements over `ledger.STATES`, so no pin can
    fall between them; the module docstring records why they are not listed here and why no per-pin
    state token is projected.

    Above them, the header carries one conditional line when some decision rests on an agent's relay
    (`_evidence_note`) — see the module docstring for why that is the only shape of `evidence` this
    projection can afford.

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

    head = ([line.format(ledger=ledger_path) for line in _HEAD_TEMPLATE]
            + _evidence_note(data))

    # The two sets are the ledger's, not this module's (see the module docstring). Imported here
    # rather than at module scope for the same reason `_evidence_note` imports what it needs: the
    # rule has one implementation, in the module that owns the schema.
    from ledger import OPEN_STATES, SETTLED_STATES
    settled = sorted((p for p in pins if p.get("state") in SETTLED_STATES), key=_order)
    openp = sorted((p for p in pins if p.get("state") in OPEN_STATES), key=_order)
    sections = [
        ("Standing rules",
         [f"- {p.get('rule', '').strip()} *(applies to "
          f"{', '.join(f'{k}={v}' for k, v in (p.get('applies_to') or {}).items()) or 'all pins'}; "
          f"default: {p.get('default_outcome')})*" for p in policies],
         "see `policies` in the ledger"),
        ("Settled — build on these", [_pin_line(p, True) for p in settled], "run `ledger_summary`"),
        ("Open — do not encode an answer", [_pin_line(p, False) for p in openp],
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
