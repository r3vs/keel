#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""The human's own door onto the two electing writes — run BY the person deciding, never by an agent.

Why this file exists
--------------------
`mcp:ledger_record_decision` picks its path from a capability the client DECLARES: `_client_can_elicit`
asks `check_client_capability(ElicitationCapability())` on a connection whose negotiated era still
has a back-channel, and on yes it sends `ctx.elicit` and treats
anything but `AcceptedElicitation` as "no answer" — correctly, because declined and cancelled are not
outcomes. There is a third situation neither of those covers, and `server.py::_ask` is what separates
it: a door that never opened at all. A refusal arrives as a *value* and keeps its hard refusal here;
a missing door arrives as a *raise*, and since nobody was asked there is no answer to invert, so that
one degrades to the relay rung instead. A client that declares the capability and then declines every request reaches neither rung:
the strong one raises, and the relay below it is unreachable, because the `if` short-circuits it.
On such a host no pin can reach `decided` and no policy can be set — the whole electing surface is
gone, which is the state that removing the CLI floor left behind and that this file finally closes.

Why not just fall back to the relay after a decline
---------------------------------------------------
Because `Declined` flattens two opposite situations onto one value: *no prompt was ever drawn* and
*the human saw the fork and refused*. Nothing downstream can tell them apart. So degrading to
`transcribed` on a decline would, on a CONFORMING host, convert a human's "no" into an outcome the
agent wrote — an inversion, not a weakening. `_require_quote` does not stand in the way either: it
demands a verbatim `human_answer` and an offered `option_id`, and an agent can supply both.

This door does not ask the protocol to distinguish "can you?" from "will you?". It removes the
question: the person deciding runs this file, reads the fork as the pin poses it, and types the
answer into a process no agent mediates.

Why it may state the `elicited` rung (spec v0.29)
-------------------------------------------------
`decide()` holds that the rung is a fact about WHICH PATH RAN, so only the code that ran it may
state it. This is such a path, and it states its own. What `elicited` claims is one property — *the
agent never held the value, so it could not have invented it* — and v0.29 names the two carriers
that establish it instead of the one mechanism that used to: the server asking through the host, and
this door, where the property holds by construction rather than by capability. Two carriers, one
claim, no fifth rung: a new member of `DECISION_EVIDENCE` would be a new concept on every surface
that reads one, and the honest widening costs nothing but the sentence.

The guard that makes that a mechanism and not a promise
-------------------------------------------------------
It refuses to run without a TTY on stdin. Piped or redirected input is how an agent would answer
these prompts and mint an `elicited` write, and that would rebuild the agent-run CLI this repo
deliberately removed — the same bytes, the wrong hand on them. No flag carries an answer either:
the option, the words, the rationale and the flip criteria are typed here, or nothing is written.
`tests/test_human_door.py` holds both halves, and quantifies the rung over its callers so a third
one cannot appear by being written.

(One environment note, observed rather than assumed: under msys/Git Bash `< /dev/null` reports a
TTY, so the guard does not fire there. It cannot mint anything — the first `input()` takes EOF and
the run cancels — but the guard is not the only thing standing between a pipe and a write.)

How the human learns the path to this file
------------------------------------------
From something that knows its own location, never from prose. `verify_commands.py` exists because a
runnable path written into a shipped file resolves against the USER'S project after install; that is
what killed the CLI. So no playbook names this file. The server, whose own location the host
resolved, prints the absolute path in the refusal the agent will show — see `_human_door` in
`server.py`. The agent relays a path it did not compute and cannot execute.

Usage (both forms print what they will write and ask before writing):
    <this file> pin    <path/to/ledger.json> <pin_id>
    <this file> policy <path/to/ledger.json> <offer_id> [--project-type web-saas]
"""
import sys
from pathlib import Path

# `tools.py` is a sibling in BOTH layouts — `src/mcp/` here, `mcp/` in a built plugin — and it
# bootstraps the runtime onto the path itself. So one entry covers both, and no `../` appears.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools  # noqa: E402  — after the path bootstrap above
from ledger import FREEFORM_OUTCOME  # noqa: E402  — `tools` put the runtime on the path

#: Menu rows that are not an option id. Objects, not strings: an option id is authored by an agent
#: through `ledger_add_pin`, so any sentinel STRING could be collided with on purpose — the reason
#: `server.py::_ACCEPT_AS_IS_ROW` maps to `None` rather than to a word.
_FREEFORM = object()
_AS_IS = object()

_ACCEPT = "set this policy — decide the whole cluster this way"
_DECLINE = "do not set it — keep asking pin by pin"


def _guard() -> None:
    """The one precondition of the `elicited` rung, checked before anything is read or shown."""
    if sys.stdin.isatty():
        return
    sys.exit(
        "refusing: stdin is not a terminal.\n"
        "This door writes the `elicited` rung, whose whole claim is that no agent held the value.\n"
        "Answering it through a pipe would make that claim false while keeping it unfalsifiable.\n"
        "Run it yourself in a terminal — or, if you are relaying an answer a human already gave,\n"
        "use `ledger_record_decision` / `ledger_record_policy` and quote them verbatim in\n"
        "`human_answer`. That is the `transcribed` rung, and it is the honest one for a relay."
    )


def _ask(label: str, *, required: bool = True) -> str:
    while True:
        value = input(f"{label}\n> ").strip()
        if value or not required:
            return value
        print("  (required)")


def _pick(rows: list) -> object:
    while True:
        raw = input("\nNumber> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1][1]
        print(f"  pick 1-{len(rows)}")


def _confirm(what: str) -> bool:
    print(f"\n--- about to write\n{what}")
    return input("\nWrite it? [y/N] ").strip().lower() in ("y", "yes")


def decide_pin(ledger: str, pin_id: str) -> int:
    prompt = tools.decision_prompt(ledger, pin_id)      # read-only; raises on a bad path or pin

    print(f"\n{prompt['pin_id']}  [{prompt['severity']}/{prompt['kind']}]  {prompt['title']}")
    print(f"\n{prompt['prompt']}\n")

    # Numbered, so the id never round-trips through display text. `server.py::_decision_choices`
    # needs an injectivity check because the elicitation protocol carries a string back; an index
    # cannot collide with another index, so that whole class is absent here, not defended against.
    rows = [(f"{o['id']} — {o['label']}" + (f"  (→ {o['implication']})" if o["implication"] else ""),
             o["id"]) for o in prompt["options"]]
    if prompt["allow_freeform"]:
        rows.append(("freeform — answer in your own words", _FREEFORM))
    if prompt["can_accept_as_is"]:
        rows.append(("accept_as_is — leave it as it is", _AS_IS))
    if not rows:
        sys.exit(f"{pin_id} offers no option and no freeform answer; there is nothing to elect.")
    for i, (row, _) in enumerate(rows, 1):
        print(f"  {i}. {row}")

    picked = _pick(rows)
    accept_as_is = picked is _AS_IS
    if picked is _FREEFORM:
        option_id = FREEFORM_OUTCOME
        human_answer = _ask("\nYour answer, in your own words (here the words ARE the outcome):")
    else:
        option_id = "" if accept_as_is else picked
        human_answer = next(row for row, val in rows if val is picked)

    rationale = _ask("\nWhy this outcome — the reasoning, not a restatement:")
    flip_criteria = _ask("\nWhat would reopen this decision:")

    if not _confirm(f"  ledger   {ledger}\n"
                    f"  pin      {pin_id}\n"
                    f"  outcome  {human_answer if option_id == 'freeform' else (option_id or 'leave as is')}\n"
                    f"  state    {'accepted' if accept_as_is else 'decided'}\n"
                    f"  rung     elicited (you typed it; no agent carried it)\n"
                    f"  reopens  {flip_criteria}"):
        print("nothing written; the pin stays open.")
        return 1

    out = tools.record_decision(ledger, pin_id, option_id, rationale, flip_criteria,
                                human_answer=human_answer, evidence="elicited",
                                accept_as_is=accept_as_is)
    print(f"\n{out['pin_id']} → {out['state']}  outcome={out['outcome']!r}  rung={out['evidence']}")
    return 0


def set_policy(ledger: str, offer_id: str, project_type: str) -> int:
    """A CATALOG offer only, and that restriction is what keeps the rung true.

    `policy_prompt` takes the rule, the scope and the outcome FROM the offer and refuses a caller
    that restates them, so on this path nothing shown to the human was authored by an agent — the
    catalog is shipped data and the radius is computed by the same matcher the cascade runs. A
    policy the catalog never offered has a rule somebody had to write; if that somebody is an agent,
    the honest rung is `transcribed` through the MCP tool, quoting the human. This door will not
    launder it into `elicited`, so it does not accept one.
    """
    p = tools.policy_prompt(ledger, offer_id=offer_id, project_type=project_type)
    would, held, unoffered = p["would_decide"], p["held_back"], p["not_offered"]

    print(f"\npolicy offer: {offer_id}\n\n  rule     {p['rule']}\n"
          f"  outcome  {p['default_outcome']}   ← written onto every pin below\n"
          f"  scope    {p['applies_to']}")
    if p.get("scope_note"):
        print(f"  note     {p['scope_note']}")
    print(f"\ndecides {len(would)} pin(s)" + (f": {', '.join(would)}" if would else ""))
    if held:
        print(f"holds back {len(held)} blocker/high pin(s), still asked: {', '.join(held)}")
    if unoffered:
        print(f"holds back {len(unoffered)} pin(s) whose question does not offer "
              f"{p['default_outcome']!r}: {', '.join(unoffered)}")

    for i, row in enumerate((_ACCEPT, _DECLINE), 1):
        print(f"  {i}. {row}")
    if _pick([(_ACCEPT, _ACCEPT), (_DECLINE, _DECLINE)]) is _DECLINE:
        print("nothing written; those pins stay open, which is the correct outcome.")
        return 1

    if not _confirm(f"  ledger   {ledger}\n  policy   {p['rule']}\n"
                    f"  outcome  {p['default_outcome']} on {len(would)} pin(s)\n"
                    f"  rung     elicited (you typed it; no agent carried it)"):
        print("nothing written; those pins stay open.")
        return 1

    out = tools.record_policy(ledger, offer_id=offer_id, human_answer=_ACCEPT,
                              evidence="elicited", project_type=project_type)
    print(f"\npolicy set — cascaded onto {len(out.get('cascaded') or [])} pin(s)")
    return 0


def main(argv: list) -> int:
    _guard()
    if len(argv) >= 3 and argv[0] == "pin":
        return decide_pin(argv[1], argv[2])
    if len(argv) >= 3 and argv[0] == "policy":
        pt = argv[argv.index("--project-type") + 1] if "--project-type" in argv else "web-saas"
        return set_policy(argv[1], argv[2], pt)
    print("\n".join(__doc__.strip().splitlines()[-3:]))
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, FileNotFoundError, KeyError) as exc:
        sys.exit(f"\nrefused: {exc}")            # the ledger is unchanged — every door commits last
    except (KeyboardInterrupt, EOFError):
        sys.exit("\ncancelled; nothing was written.")
