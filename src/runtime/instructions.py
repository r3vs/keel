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

What the budget refused, deliberately: **no per-pin state token.** A ` (deferred)` suffix would cost
bytes on every line of the section most likely to be clipped. The exact state of any pin is one
`ledger_summary` call away and is in the map's sub-line, where a human looks.

One per-pin clause is bought rather than refused, and the test is the one this section applies to
everything: does the default reading of the line without it say something FALSE? A `substate` in
`ledger.REOPENED_SUBSTATES` means the printed outcome is under dispute, so the bare line asserts an
elected answer that is currently contradicted — see `_pin_line`. It fires on the pins that carry the
substate and on no others, which is what separates it from a token every line pays for.

That refusal used to rest on a claim that was false of two states, and the claim is what was wrong,
not the refusal. It read: *the bucket already carries the only instruction that differs between
these pins, and that instruction is identical for all four states inside each bucket.* It is not.
`deferred` is a settled state whose instruction is **do not build this**, and it was landing
first inside *"build on these"* — severity-ordered, so six deferred blockers clipped two elected
decisions off the end of the section. And a `correctness_unknown` pin — *elected, and we could not
establish that it worked* — reached the region as an unanswered question, because the open section
suppressed the outcome. Both are fixed where they broke, at zero bytes per line: the elected outcome
is printed in **either** section wherever a pin has one, and the open heading says *not settled; do
not decide one yourself*, which is true of a pin carrying an answer and of one carrying none. The
headings are what must be true of every member — `resolved` and `deferred` are settled without being
"elected" in the narrow sense, and `correctness_unknown` is open without anyone having failed to
decide it, which is why neither says "decided".

Which is exactly where the first attempt at that fix was still wrong, and v0.19 says so
--------------------------------------------------------------------------------------
*"`deferred` is the ONE settled state whose instruction is do not build this"* was a claim about two
states made about one. `accept` is defined in `settlement_verdict` as leaving the concern exactly as
it is — the same instruction — so an `accepted` blocker still outranked an elected `decided` medium
under the clip, inside a section headed *build on these*, under a parenthetical that named only
`defer`. And the sort that put deferrals last did it by comparing `state == "deferred"`, a literal
state name in the file whose own test class asserts *a set the schema owns cannot be kept here*.

So the set is the schema's (`ledger.LEAVE_AS_IS_STATES`) and the settled half is **two sections**,
not one section with an ordering trick and a parenthetical. Three consequences, and the middle one
is the reason this shape was chosen over a cheaper true heading:

- the heading is true of every member of the section it heads, which is this file's stated standard
  and is not achievable by any single heading over both groups;
- a reader can tell WHICH pins are the do-not-build ones without a per-pin state token — the very
  thing the budget refused. Membership is carried by the heading, which costs 2 lines **once**
  instead of a suffix on every line;
- the clip now falls on the do-not-build pins first, which is strictly better than the ordering hack
  it replaces: the section that survives a tight budget is the one that says what to build.

It costs 2 lines only when both groups are non-empty (`_section` drops an empty section whole), so a
project with nothing deferred or accepted pays nothing — the same bargain `_evidence_note` makes.
And no state name is written in this module any more, which is what makes a fifth settled state with
leave-as-is semantics arrive here rather than silently inherit today's placement.
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
#: The nonconformance note (blank line + one line), emitted only when the file holds something the
#: schema does not describe. Counted in the floor for exactly the reason above, and it is counted
#: because the first draft was not: at the floor it displaced `### Standing rules` — the rules an
#: agent must obey — which is the one thing this budget promises survives.
_NONCONF_LINES = 2

#: Header + both conditional notes + a heading + one item + its clip note. Below this a budget
#: cannot be honoured at all, and overrunning it silently is the exact failure the budget exists to
#: prevent — so it is refused.
_MIN_LINES = len(_HEAD_TEMPLATE) + _NOTE_LINES + _NONCONF_LINES + 4

def _fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def _order(pin: dict) -> tuple:
    """Severity then id, through the schema's own ordering — and the table this module used to keep
    is gone (v0.23).

    It read a MISSING severity as `low` and an unrecognised one as 9, so a pin whose file says
    nothing about how bad it is sorted AHEAD of a pin that states a severity outside the set — in
    the section a tight budget clips first. `ledger.severity_rank` says the opposite, with an
    argument (`pin_read`): an unrankable severity is not evidence of anything, and *missing* and
    *unrecognised* are the same amount of nothing. Two surfaces ordering the same pins by two
    tables, the newer one contradicting the older's argued direction; one of them had to go, and it
    is the one that carried no argument.

    Both fields come through `pin_read`, which is also what stops `severity` being used as a dict
    key: a list severity is unhashable, and that is how the whole projection died on one pin.
    """
    from ledger import pin_read, severity_rank
    read = pin_read(pin)
    return (severity_rank(read["severity"]), read["id"])


def _failed_in_production(data: dict) -> dict:
    """`pin_id -> the failure class`, for every pin a `production` FailureEvent was labelled on.

    `ledger_label_failure` is a write door that reaches finished work on purpose — labelling an
    incident on a `resolved` pin is the move that PRECEDES a reopen, which is why the closed-work
    gate lets it through. The map's trail card shows the event and `learning_report` counts it; this
    projection listed the pin under *"Settled — build on these"* with nothing said, so the one file
    every host loads unprompted told a fresh agent to build on work that had already failed in front
    of users.

    Scoped to `production` deliberately, not to every phase: a failure labelled at `plan`, `build`,
    `evidence` or `review` is the loop working — it happened before anything shipped, and marking it
    here would spend bytes on the ordinary case, which is the bargain this whole region is under. A
    production failure is the one that contradicts the heading above the line.
    """
    from ledger import read_collection
    out: dict = {}
    for event in read_collection(data, "decision_log"):
        if not str(event.get("id") or "").startswith("fal_"):
            continue
        if event.get("phase") != "production":
            continue
        pin_id = str(event.get("pin_id") or "")
        if pin_id:
            out[pin_id] = str(event.get("class") or "failure")
    return out


def _pin_line(pin: dict, failed: dict | None = None) -> str:
    """One pin, with its elected outcome wherever it has one — in EITHER section.

    The outcome used to be suppressed for open pins, which was right for the three open states that
    have none and wrong for the fourth: `correctness_unknown` means *elected, and we could not
    establish that it worked*. A pin decided `request_id` and then marked unverifiable reached a
    fresh agent's always-on context as an unanswered question, so the agent could answer again what
    the human had already answered. A pin with no decision prints no outcome, so the honest line
    costs nothing where there is nothing to say — which is why this is one rule, not a per-section
    flag.

    **And an outcome under dispute is marked as one** (v0.19). That same deletion inverted one state
    over: a pin reopened by `cross_derive(agreement="disagree")`, by the feedback arc or by an upheld
    challenge still carries the outcome it was elected with, and printing it bare formats a
    contradicted answer exactly like a build instruction. The heading above it forbids *deciding*,
    not *building on* — and this is the surface with nobody to ask. The map has said it loudly since
    v0.16 (an amber CROSS-DERIVATION — DISAGREE card); `grep -c substate` over this file returned 0.

    The mark costs bytes only on the pins that carry the substate, which is the same bargain
    `_evidence_note` and the leave-as-is section make: nothing on the common case, a clause where the
    default reading would be false. The substate is not compared to a name — `ledger.REOPENED_SUBSTATES`
    owns that set, for the reason the module docstring gives about every set the schema owns.

    Every field it indexes comes through `pin_read` (v0.23). Two of them killed this function over
    real stdio on ordinary malformations — `.strip()` on a title that was an object, `.get()` on a
    `decision` that was a string — and the file it kills is `AGENTS.md`, the one thing every host
    loads unprompted. `kind` stays a plain `.get`: it is only interpolated, never indexed, so
    substituting it would be inventing a claim about the pin rather than avoiding a crash.
    """
    from ledger import REOPENED_SUBSTATES, pin_read
    read = pin_read(pin)
    kind = pin.get("kind", "other")
    if kind == "other" and pin.get("kind_detail"):
        kind = f"other:{pin['kind_detail']}"
    line = f"- `{read['id'] or '?'}` [{kind}] {read['title'].strip()}"
    outcome = read["decision"].get("outcome")
    if outcome:
        line += f" — **{outcome}**"
        substate = pin.get("substate")
        if substate in REOPENED_SUBSTATES:
            line += f" *({substate} — do not build on this answer)*"
    # v0.28 — and a production failure is marked wherever the pin lands, for the reason the
    # reopened substate is: the default reading of this line is *build on this*, and on a pin that
    # already failed in front of users that reading is false. See `_failed_in_production`.
    failure = (failed or {}).get(read["id"])
    if failure:
        line += f" *(failed in production — {failure})*"
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


def _nonconformance_note(data: dict) -> list:
    """One line saying what this file holds that the schema does not describe — or nothing.

    **v0.25, and it was the last surface with no such line.** The map has carried a banner since
    v0.23 and `ledger_summary` has reported `pre_rule_events` since v0.21; this projection called
    `nonconforming` nowhere at all. On one hostile ledger the three surfaces gave three accounts of
    one file: `ledger_summary` said 8 pins and 24 nonconformances across 15 rules, the map showed a
    banner, and the region every fresh agent loads listed 6 pins and said nothing — the shortest
    list, in the one file no host loads on request. A projection that silently drops what it could
    not read is telling an agent there is less here than there is, which is the same claim a blank
    map makes, made where it is hardest to notice.

    Counts and rule names, not ids: the region is a budgeted index and the ids are on the map and in
    `ledger_summary`, both of which this line names. It costs bytes only when there is something to
    say, exactly as `_evidence_note` does.
    """
    from ledger import nonconforming
    report = nonconforming(data)
    if not report:
        return []
    total = sum(len(ids) for ids in report.values())
    rules = ", ".join(f"`{r}`" for r in sorted(report))
    return ["", f"*This ledger holds {total} thing(s) the schema does not describe ({rules}), so "
                f"what is listed below is what a reader can index — not all the file contains. "
                f"`ledger_summary` reports the same list under `pre_rule_events`; the map shows it "
                f"as a banner. Nothing was rewritten, and a file in this state does not get its "
                f"`version` raised.*"]


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
    from ledger import read_collection
    events = [e for e in read_collection(data, "decision_log")
              if str(e.get("id", "")).startswith("ev_")]
    policies = read_collection(data, "policies")
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

    Five sections, in the order an agent needs them: the standing rules it must obey, the settled
    pins it should build on, the settled pins it must **not** build (`ledger.LEAVE_AS_IS_STATES`),
    the pins still awaiting something (`ledger.OPEN_STATES` — surface an assumption instead of
    inventing an answer), and the generated files it must never hand-edit. Ordering is severity then
    id — stable, so an unchanged ledger re-renders byte-identically and the drift-check has no false
    positives.

    The state sets come from the ledger, `SETTLED_STATES`/`OPEN_STATES` are complements over
    `ledger.STATES` so no pin can fall between them, and `LEAVE_AS_IS_STATES` partitions the settled
    half; the module docstring records why none of them is listed here and why no per-pin state
    token is projected.

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
    # v0.21 filtered the two collections here, inline; v0.23 asks the carrier, because a rule with a
    # copy in every reader is the thing this file's own module docstring keeps finding one surface
    # over. `read_collection` is `Ledger.readable`'s body — this function holds no `Ledger`, which is
    # exactly why the guard on the method never reached it. What is dropped is reported by
    # `nonconforming` under `entry_shape` / `collection_shape` — and from v0.25 it is reported HERE
    # too, in the region's own header, rather than only on the two surfaces that already said it.
    from ledger import read_collection
    pins = read_collection(data, "pins")
    policies = read_collection(data, "policies")

    head = ([line.format(ledger=ledger_path) for line in _HEAD_TEMPLATE]
            + _nonconformance_note(data)
            + _evidence_note(data))

    # The two sets are the ledger's, not this module's (see the module docstring). Imported here
    # rather than at module scope for the same reason `_evidence_note` imports what it needs: the
    # rule has one implementation, in the module that owns the schema.
    from ledger import LEAVE_AS_IS_STATES, OPEN_STATES, SETTLED_STATES, policy_read
    settled = sorted((p for p in pins if p.get("state") in SETTLED_STATES), key=_order)
    build_on = [p for p in settled if p.get("state") not in LEAVE_AS_IS_STATES]
    leave_as_is = [p for p in settled if p.get("state") in LEAVE_AS_IS_STATES]
    openp = sorted((p for p in pins if p.get("state") in OPEN_STATES), key=_order)
    # `policy_read` for the two fields this line INDEXES — `.strip()` on the rule and `.items()` on
    # the scope, both of which killed the whole projection on a hand-written policy (v0.23).
    # `default_outcome` is interpolated and not indexed, so it stays a plain `.get` for the reason
    # `_pin_line` gives about `kind`.
    reads = [(policy_read(p), p) for p in policies]
    failed = _failed_in_production(data)
    sections = [
        ("Standing rules",
         [f"- {r['rule'].strip()} *(applies to "
          f"{', '.join(f'{k}={v}' for k, v in r['applies_to'].items()) or 'all pins'}; "
          f"default: {p.get('default_outcome')})*" for r, p in reads],
         "see `policies` in the ledger"),
        ("Settled — build on these", [_pin_line(p, failed) for p in build_on], "run `ledger_summary`"),
        ("Settled — elected NOT to be built ("
         + ", ".join(f"`{s}`" for s in LEAVE_AS_IS_STATES) + ")",
         [_pin_line(p, failed) for p in leave_as_is], "run `ledger_summary`"),
        ("Open — not settled; do not decide one yourself", [_pin_line(p, failed) for p in openp],
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
