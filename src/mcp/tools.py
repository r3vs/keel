"""The MCP tool bodies — stdlib only, importable without FastMCP, testable in plain CI.

The split here is the repo's own pattern, the one `treesitter_extract.py` already follows: **the
engine stays pure, the adapter carries the dependency.** `server.py` is the FastMCP adapter and
pulls a ~77-package tree; this module is the part that is actually ours, so it holds no MCP
concepts at all and its tests need nothing installed.

It also survives the thing that killed the first attempt: MCP's 2026-07-28 revision drops the
`initialize` handshake, mandates `server/discover`, and requires `resultType` on every result. Not
one line in this file knows or cares — the protocol churn lands entirely on the adapter, where a
version bump absorbs it.

Every function calls the runtime's *library* API — never a subprocess or a printing entry point
(the modules no longer have a `main()` at all). Under stdio transport stdout is the wire, so a stray
print would corrupt the session.
"""
import json
import sys
from pathlib import Path

# The runtime sits beside this file once vendored into a plugin (mcp/runtime/), and one level up in
# the authoring tree (src/runtime/). Accept both so dev and shipped layouts behave identically.
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE / "runtime", _HERE.parent / "runtime"):
    if _candidate.is_dir():
        sys.path.insert(0, str(_candidate))
        break


def _open_existing(path: str):
    """Load a ledger that must already exist.

    `Ledger(path)` deliberately creates a fresh empty ledger when the file is absent — correct for
    the write path, but a trap for a read tool: a mistyped path would answer "no pins", and the
    agent would conclude there is nothing to do. That is a confident wrong answer, the exact failure
    this package exists to prevent. Reads refuse instead.
    """
    from ledger import Ledger
    if not Path(path).is_file():
        raise FileNotFoundError(
            f"no ledger at {path!r}. Not creating one: an empty summary would read as "
            f"'nothing to do'. Check the path, or run the skill's Phase 1 to build it."
        )
    return Ledger(path)


def ledger_summary(ledger: str) -> dict:
    return _open_existing(ledger).summary()


def interview_next(ledger: str) -> dict:
    import interview
    return interview.funnel(_open_existing(ledger))


# -- the ledger as a READ SURFACE (what the MCP resources project) --------------------------------
# These have no `@mcp.tool` of their own and are not meant to: an agent that wants pins calls
# `ledger_summary` / `interview_next` / `ledger_frontier`, each of which answers a question. What a
# *resource* is for is the other consumer — a human typing `@keel:ledger://…` — and the rule that
# makes it safe is that it reads through `_open_existing` and `pin_read` like every tool does.
# A second parser over ledger.json is the divergence this package exists to find, so there is none.

def ledger_pins(ledger: str) -> dict:
    """The pin index: id, kind, state, severity, title — through the guarded read.

    Deliberately not the whole pin. A ledger is routinely hundreds of pins and a resource is
    *attached to a prompt*, not summarized into one, so the full payload would spend the context it
    was fetched to inform. `ledger_pin` is the drill-down.
    """
    from ledger import pin_read
    led = _open_existing(ledger)
    pins = [pin_read(p) for p in led.readable_pins()]
    return {"source": ledger, "count": len(pins),
            "pins": [{k: p[k] for k in ("id", "kind", "state", "severity", "title") if k in p}
                     for p in pins]}


def ledger_pin(ledger: str, pin_id: str) -> dict:
    """One pin, whole, through the same guarded read the write doors use.

    `Ledger.pin` raises `LedgerError` on an unknown id rather than returning an empty record — the
    read path's standing refusal, and the right one here too: a resource that answered `{}` for a
    mistyped id would read as "that pin has nothing on it".
    """
    from ledger import pin_read
    return {"source": ledger, "pin": pin_read(_open_existing(ledger).pin(pin_id))}


# -- ledger writes (non-electing only; electing an outcome is the human interview's job) ----------

def _open_or_create(path: str):
    """Load a ledger for a WRITE. Unlike the read path, a missing file is created here — this is how
    the first pin lands. Reads refuse a missing path; writes bootstrap it.

    Also stamps the governance record when one is absent. This used to be an agent-facing tool, and
    that was wrong twice: it rented ~250 tokens of description in every session to expose a button no
    playbook ever pressed, and it made the trail's completeness depend on an agent remembering to
    press it. The server already knows its own root and version, so it can answer "under which rules"
    without being asked. A fact the machine can establish should never be a question put to a model.
    """
    from ledger import Ledger
    led = Ledger(path)
    if not led.data.get("governance"):
        led.set_governance(_governance_record())
    return led


def _saved(ledger: str, led) -> None:
    """THE write-commit of this module: persist the ledger, then re-project every live map on it.

    One function because the pairing was a convention, and a convention is a thing eighteen doors
    remember and the nineteenth does not. Measured by AST over this file: 18 functions called
    `led.save()`, 17 of them then called `_refresh_live_maps`, and `ledger_label_failure` did not —
    while `_livemap_marker`'s own docstring states the rule it was breaking (*"'live' is the MCP
    layer re-projecting the file on every ledger write"*). Verified over stdio: with a live map
    registered, `ledger_label_failure` left the page on disk byte-identical, so a `FailureEvent` the
    measurer had just recorded was absent from the surface a human was watching, and the next
    unrelated write made it appear — which is worse than never showing it, because the page's
    freshness badge said live throughout.

    The fix is not the eighteenth call. It is that there is now exactly one place where a ledger
    write is finished, and `tests/test_mcp_tools.py::TestOneCommitPointForEveryLedgerWrite` fails on
    any function in this module that reaches `save()` without coming through here — quantified over
    the callers, so the nineteenth door inherits the rule instead of remembering it.

    **And it is the LAST thing a door does (v0.28).** Four doors computed their answer *after* this
    call — `ledger_reopen`, `ledger_challenge` and `ledger_cross_derive` re-read the pin and the
    cascade radius, `ledger_label_failure` ran `foresight` — so a read that raised there left the
    write on disk and handed the caller `isError`. Reproduced over stdio: two `resolved` pins, one
    `ledger_reopen`, one hand-written log entry naming a `via` and no `pin_id` — the root pin came
    back `needs_input` in the file and the tool reported `KeyError: 'pin_id'`. An agent that reads
    that error retries, and the retry is a second reopen.

    So the shape of every door here is *compute the answer, then commit*: whatever a door returns
    describes what happened, and a door that raises has changed nothing.
    `TestADoorThatReportsFailureCommittedNothing` holds both halves — the position of this call by
    AST over every function that makes it, and the file byte-identical after every raise the derived
    corpora can provoke.
    """
    led.save()
    _refresh_live_maps(ledger)


def _require_quote(human_answer: str, evidence: str = "transcribed", *,
                   freeform: bool = False, writes: str = "decision", because: str = "") -> None:
    """Refuse an agent-relayed election that quotes nobody — the one carrier of that rule (v0.24).

    It was four hand-written enforcement points that happened to agree: two in `record_decision`
    (the `transcribed` rung, and the freeform path where the human's words ARE the outcome), one in
    `record_policy`, one in `ledger_defer`. Four sentences, one rule, and the branch this was found
    on has spent itself on exactly that shape — a rule spelled out at each door is a rule the next
    door is written without.

    Which rungs owe a quote is `ledger.QUOTED_RUNGS`, so the membership question lives with the
    schema and this is only the refusal. The freeform path owes it whatever the rung says: there the
    words are not evidence FOR the outcome, they are the outcome.

    `writes` and `because` exist so the sentence can say what this particular call would have
    written — a policy that decides forty pins and a defer that stops a question being asked are
    different consequences of one missing quote, and a refusal an agent cannot act on is a wall.
    """
    from ledger import QUOTED_RUNGS
    if not freeform and evidence not in QUOTED_RUNGS:
        return
    if str(human_answer or "").strip():
        return
    lead = ("a freeform election IS the human's words, so human_answer is required"
            if freeform else
            f"a {evidence} {writes} must carry the human's answer verbatim in human_answer — "
            f"without it, an honest relay and a fabricated one are indistinguishable in the ledger")
    raise ValueError(lead + (f"; {because}" if because else ""))


def _governance_record() -> dict:
    """The policy fingerprint from what this process can see: the vendored roster and the spec
    version it ships with. Unresolvable inputs land in `missing` rather than being dropped."""
    import governance
    from ledger import SCHEMA_VERSION
    roster = next((str(c) for c in (_HERE / "core" / "agents.md",
                                    _HERE.parent / "core" / "agents.md") if c.is_file()), "")
    version = ""
    for manifest in (_HERE.parent / ".claude-plugin" / "plugin.json",
                     _HERE.parent.parent / ".claude-plugin" / "plugin.json"):
        if manifest.is_file():
            try:
                version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
            except (OSError, ValueError):
                version = ""
            break
    return governance.record(roster=roster, spec_version=SCHEMA_VERSION, skill_version=version)


def ledger_add_pin(ledger: str, kind: str, title: str, severity: str, confidence: str,
                   provenance: list, as_is: dict | None = None, to_be: dict | None = None,
                   question: dict | None = None, depends_on: list | None = None,
                   kind_detail: str | None = None, cluster_id: str | None = None) -> dict:
    led = _open_or_create(ledger)
    pin = led.add_pin(kind=kind, title=title, severity=severity, confidence=confidence,
                      provenance=provenance, as_is=as_is, to_be=to_be, question=question,
                      depends_on=depends_on, kind_detail=kind_detail, cluster_id=cluster_id)
    out = {"pin_id": pin["id"], "kind": pin["kind"], "state": pin["state"]}
    _saved(ledger, led)
    return out


def ledger_surface_assumption(ledger: str, title: str, detail: str, severity: str = "medium",
                              confidence: str = "inferred") -> dict:
    led = _open_or_create(ledger)
    pin = led.surface_assumption(title=title, detail=detail, severity=severity, confidence=confidence)
    out = {"pin_id": pin["id"], "state": pin["state"]}
    _saved(ledger, led)
    return out


def decision_prompt(ledger: str, pin_id: str) -> dict:
    """The fork exactly as the pin poses it — what to put in front of the human, nothing invented.

    Read-only, and separate from recording on purpose: the thing that ASKS must be able to run
    without the power to write.
    """
    return _prompt_from_pin(_open_existing(ledger).pin(pin_id))


def _prompt_from_pin(pin: dict) -> dict:
    """The prompt over an already-loaded pin. Split out so `record_decision` can check the pin it is
    about to write against the ledger it is about to write to — one open, one object, no window in
    which the fork it showed and the fork it enforces could be different files."""
    pin_id = pin["id"]
    question = pin.get("question")
    if not question:
        raise ValueError(
            f"{pin_id} poses no question, so there is nothing to elect. A pin reaches "
            f"`decided` only through the fork the interview put to the user; a `defect` needs no "
            f"election and goes straight to remediation."
        )
    return {
        "pin_id": pin_id,
        "title": pin["title"],
        "kind": pin["kind"],
        "severity": pin["severity"],
        "prompt": question["prompt"],
        "options": [{"id": o["id"], "label": o["label"], "implication": o.get("implication", "")}
                    for o in question.get("options", [])],
        "allow_freeform": bool(question.get("allow_freeform")),
        "can_accept_as_is": pin["kind"] == "design_concern",
    }


def record_decision(ledger: str, pin_id: str, option_id: str, rationale: str, flip_criteria: str,
                    human_answer: str = "", evidence: str = "transcribed",
                    accept_as_is: bool = False) -> dict:
    """Record an election the HUMAN made. This tool does not elect; it writes down what was elected.

    That distinction is the package's central invariant, and until now it was implemented by having
    no tool at all — which stopped an agent from choosing and also stopped the human from being
    recorded, so after the CLI was removed no pin on any host could reach `decided`. The whole
    downstream chain rests on that state: `DecisionEvent`, `flip_criteria`, the reopen loop, and
    `roadmap = diff(to_be, as_is)`. Only `defect` pins moved, because they need no election.

    What replaces "there is no tool" is a tool that cannot be used to choose:

      * `option_id` must name an option the pin's own `question` offers — checked with
        `Ledger.question_offers`, the *same function* the unasked doors reach through
        `unasked_verdict`, so "what this pin may be decided to" has one answer and not two that
        happen to agree. An agent cannot elect an outcome the interview never put to the user: the
        menu is the ledger's, not the caller's.
      * freeform is allowed only where the question says `allow_freeform`, and then the human's
        words ARE the outcome.
      * `flip_criteria` is required, so no decision fossilizes out of reach of the reopen loop.
      * a `transcribed` decision must quote the human. An agent asserting "the user chose B" with
        nothing quoted is exactly the claim `evidence` exists to make checkable — and this is the
        boundary where that claim gets made, which is why the rule lives here and not in `ledger.py`.
      * a pin whose work is FINISHED (`resolved` / `accepted` / `deferred`) is refused, by
        `Ledger.settlement_verdict` inside `decide` (v0.16). This door had no settled check of any
        kind, so it re-decided a resolved pin back to `decided` while `unasked_verdict` refused the
        same pin as `already_settled` — two doors, two answers, one question. A `decided` pin is
        still re-electable here and only here: that is the human correcting themselves, the log
        keeps both events, and no unasked write can do it.

    **One pin.** This door took `apply_to_cluster`, which fanned the same outcome — and the same
    quote — across every pin sharing the `cluster_id`, past all three rules above: a pin offering a
    different option set, a pin with no question, a `blocker`. The elicitation the human answered
    named ONE pin. Cluster-wide is `record_policy`: it shows the radius before the write, holds back
    what may not be settled, and leaves a `Policy` for each cascaded event to point at. The funnel's
    "200 findings → one decision" is that tool, and it is the only shape of it that can say, on each
    pin, whose answer this was.

    `evidence="elicited"` is reserved for the two paths that actually ask a human and so may say so:
    the adapter's elicitation branch (`mcp/server.py`, the server asks through the host) and
    `mcp/decide.py` (the deciding human runs it, and it refuses a non-terminal stdin). The agent
    carries the value on neither. v0.29 widened the rung from the first mechanism to the property
    both establish; a caller that is neither has not earned it.
    """
    from ledger import FREEFORM_OUTCOME, Ledger
    led = _open_existing(ledger)
    pin = led.writable_pin(pin_id)
    prompt = _prompt_from_pin(pin)
    offered = {o["id"] for o in prompt["options"]}

    if accept_as_is:
        if not prompt["can_accept_as_is"]:
            raise ValueError(
                f"{pin_id} is a {prompt['kind']}; leaving-as-is is the legitimate resolution of a "
                f"design_concern only — an open_decision has nothing to keep."
            )
    elif option_id == FREEFORM_OUTCOME:
        if FREEFORM_OUTCOME in offered:
            # `_validate_question` refuses this menu at every door that composes one, so a pin that
            # carries it was hand-written or predates that gate. Refusing is the only honest answer
            # left: the token means two things here, and picking either one is this door deciding
            # which fork was answered. Same shape as the duplicate-row refusal in
            # `server.py::_decision_choices` — a fork whose branches a caller cannot tell apart is
            # not a fork, and resolving it by precedence would just hide which of the two ran.
            raise ValueError(
                f"{pin_id} offers an option whose id is {FREEFORM_OUTCOME!r}, which is also the "
                f"token that selects a free-text answer — so this call names two different "
                f"outcomes and the pin stays open. Rename that option with `ledger_set_question` "
                f"(the fork is unanswerable as written), then elect it."
            )
        if not prompt["allow_freeform"]:
            raise ValueError(f"{pin_id} does not allow a freeform answer; choose one of {sorted(offered)}")
        _require_quote(human_answer, evidence, freeform=True,
                       because="the words are not evidence for the outcome here, they ARE it")
    elif not Ledger.question_offers(pin, option_id):
        raise ValueError(
            f"{option_id!r} is not an option this pin offers ({sorted(offered) or 'none'}). An "
            f"agent may record an election, never invent one: the menu belongs to the question the "
            f"interview asked. Use option_id='freeform' if the question allows it."
        )

    _require_quote(human_answer, evidence, writes="decision")

    if accept_as_is:
        led.accept(pin_id, rationale=rationale, flip_criteria=flip_criteria,
                   evidence=evidence, human_answer=human_answer)
        outcome, state = "keep", "accepted"
    else:
        outcome = human_answer if option_id == FREEFORM_OUTCOME else option_id
        led.decide(pin_id, outcome=outcome, rationale=rationale, flip_criteria=flip_criteria,
                   evidence=evidence, human_answer=human_answer)
        state = "decided"
    out = {"pin_id": pin_id, "state": state, "outcome": outcome, "evidence": evidence}
    _saved(ledger, led)
    return out


def interview_expand(ledger: str, project_type: str = "web-saas",
                     brief_decisions: dict | None = None) -> dict:
    """Materialize the decision catalog as pins — greenfield's Phase-1 frame step.

    Exposed because the funnel had no pins to funnel: `interview_next` reads, and the thing that
    CREATES the forks lived in `interview.expand_catalog` with no surface at all, so Phase 2 could
    not start through the only runtime channel there is.

    `brief_decisions` is a WRITE — it commits DecisionEvents — and it is the one this tool has to be
    read for (v0.14). It is gated by `Ledger.unasked_verdict`, the same predicate the policy cascade
    passes, because the `brief` rung means precisely *nobody was asked*: a cluster the brief settles
    with an outcome its own fork does not offer, or a `blocker`/`high` fork, comes back under
    `brief_held_back` with the reason and stays an open question. Un-gated, this door wrote any
    string onto any cluster at any severity — the third way into `decide` and the quietest.

    **Each entry carries the brief (v0.24):** `{"outcome": "<option id>", "quote": "<the brief's own
    words>"}`. The gate above governs *what may be written*; nothing governed *what the claim rested
    on*, and `brief` was the one member of `DECISION_EVIDENCE` in that position — `transcribed`
    demands `human_answer` at every door, `cascaded` demands a `policy_id` on both sides of a
    biconditional, `elicited` cannot be claimed over MCP at all. So this tool moved pins to `decided`
    on the caller's word that a document said so. A bare outcome string is refused, naming the shape.

    A key naming no cluster of this catalog, or one pruned for this `project_type`, comes back under
    `brief_unmatched` (v0.16). It used to come back nowhere: the docstring told the caller to check
    `brief_held_back`, and a typo'd or obsolete cluster id appeared on no list at all, so a fork the
    brief believed it had settled was reported as neither settled nor held.

    **Calling it twice adds nothing (v0.27).** It projects a fixed catalog into the ledger, and it
    used to re-materialise the whole of it: two calls left 24 pins for 12 clusters — the funnel
    asking every question twice, with the first copy of each (which may already carry a decision)
    orphaned. A cluster already in the file comes back under `already_present` with its pin and
    state, and a `brief_decisions` key naming one is reported ignored there. This is the door an
    agent re-runs after a context reset, so re-running it had to be the cheap answer.
    """
    import interview
    led = _open_or_create(ledger)
    result = interview.expand_catalog(led, interview.load_catalog(), project_type=project_type,
                                      brief_decisions=brief_decisions or {})
    _saved(ledger, led)
    return result


def interview_seed_policies(ledger: str, project_type: str = "web-saas") -> dict:
    """The catalog's per-cluster default policies, as the interview's opening OFFERS.

    Its own tool rather than a step inside `interview_expand`, even though the two are used together
    at frame time: a policy offer is not a consequence of expanding a catalog, and folding it in
    would make it a side effect nobody reading the call could see. The tool that offers the policies
    says it offers the policies.

    It READS. That is not an oversight to be fixed later — `interview.default_policies` deliberately
    writes nothing, and could not: a `Policy` in the ledger carries a `default_outcome` that the
    cascade then writes into DecisionEvents over the whole medium/low tail, so writing one
    the human never elected would be an agent deciding at scale, through the one door this package
    holds shut. It seeds the *interview*, never the ledger. What the user elects is written by
    `record_policy`, and that door does exist — for one version it did not, and this docstring told
    an agent to "record what they elect" through a surface nothing implemented.

    Each offer carries what accepting it WOULD decide, from `Ledger.policy_preview` — the same
    matcher the cascade itself runs. That is what the `ledger` argument is for: an offer put to a
    user without its blast radius is a rule with the interesting part missing, and a policy decides
    more pins than any single question does.

    The second key, `no_default_outcome`, is the honest half (v0.12). A cascade may only write an
    outcome the pin's own question offers, so a cluster whose stated default is not carried by any
    of its own options cannot be offered as a policy — `nfrs` names four options at once, and
    `delivery`'s default is conditional on the topology fork. Those clusters are returned here
    rather than dropped: the catalog still states a default for them, and an agent that saw only
    `offers` would read the silence as "this cluster has no default" instead of "this default has
    to be asked".
    """
    import interview
    led = _open_existing(ledger)
    seeded = interview.default_policies(interview.load_catalog(), led, project_type=project_type)
    offers = [{**offer, **led.policy_preview(offer["applies_to"], offer["default_outcome"])}
              for offer in seeded["offers"]]
    return {"offers": offers, "no_default_outcome": seeded["no_default_outcome"]}


def policy_prompt(ledger: str, offer_id: str = "", rule: str = "", applies_to: dict | None = None,
                  default_outcome: str = "", exceptions: list | None = None,
                  project_type: str = "web-saas") -> dict:
    """The policy exactly as it would be set, and exactly what it would decide. Read-only.

    The twin of `decision_prompt`, and separate from recording for the same reason: the thing that
    ASKS must be able to run without the power to write. It resolves the two legitimate origins of a
    policy and refuses everything else:

      * `offer_id` — the `cluster_id` of an offer `interview_seed_policies` returned. The rule, the
        scope and the default outcome are then taken FROM the offer; passing your own is refused,
        because the offer is the mandate the user was shown and restating it is rewriting it.
      * no `offer_id` — a policy the catalog never offered (every rescue policy is one: its clusters
        come from findings, not from a catalog). Then `rule`, `applies_to` and `default_outcome` are
        the caller's, and `record_policy` demands the user's words verbatim, because those words are
        the only thing the policy rests on.

    Either way `default_outcome` is an **option id**, and the returned radius splits on whether each
    matching pin's own question offers it (`not_offered`, v0.12). That is the half that used to be
    missing on the freeform path: the caller's own sentence became the outcome of every pin in the
    cluster, including pins whose question offered a closed set that did not contain it.

    The radius also carries `scope_note` (v0.18), non-empty exactly when a scope key's value is
    `null`: the matcher is a flat equality test, so a null selects the pins that carry no value for
    that field — legitimate, and indistinguishable from a wildcard by reading the scope alone. Put
    it in front of the user with the pin lists.
    """
    led = _open_existing(ledger)
    exceptions = [str(x) for x in (exceptions or [])]
    for pin_id in exceptions:
        led.pin(pin_id)      # an exception naming no pin excepts nothing; fail rather than pretend

    if offer_id:
        import interview
        seeded = interview.default_policies(interview.load_catalog(), led,
                                            project_type=project_type)
        offers = {o["cluster_id"]: o for o in seeded["offers"]}
        offer = offers.get(offer_id)
        if offer is None:
            stated = {o["cluster_id"] for o in seeded["no_default_outcome"]}
            raise ValueError(
                f"{offer_id!r} is not an offer this catalog makes for project_type={project_type!r} "
                f"({sorted(offers) or 'none'}). Read them with interview_seed_policies; a policy the "
                f"user was never offered is one you invented."
                + (f" That cluster does state a default, but no single one of its options carries "
                   f"it, so it cannot be cascaded — ask it as a question." if offer_id in stated
                   else "")
            )
        if rule or applies_to or default_outcome:
            raise ValueError(
                "an offer carries its own rule, scope and default outcome — pass offer_id alone. "
                "Restating them here would let the recorded policy differ from the one the user "
                "was shown, which is the whole thing this refuses."
            )
        rule, applies_to = offer["rule"], offer["applies_to"]
        default_outcome = offer["default_outcome"]
    else:
        if not rule or not applies_to or not default_outcome:
            raise ValueError(
                "a policy the offers did not contain needs all three of rule, applies_to and "
                "default_outcome: what the user decided, which pins it covers, and the outcome "
                "every one of them gets. Or pass offer_id to take a catalog offer verbatim."
            )

    if not isinstance(default_outcome, str) or not default_outcome.strip():
        raise ValueError(
            "default_outcome must be the option id every cascaded pin gets — a non-empty string. "
            "It is what lands in each DecisionEvent, and each pin's own question has to offer it; "
            "a structured value is offered by no question, so it would decide nothing anywhere."
        )

    return {"offer_id": offer_id, "rule": rule, "applies_to": applies_to,
            "default_outcome": default_outcome, "exceptions": exceptions,
            **led.policy_preview(applies_to, default_outcome, exceptions)}


def record_policy(ledger: str, offer_id: str = "", rule: str = "", applies_to: dict | None = None,
                  default_outcome: str = "", exceptions: list | None = None, human_answer: str = "",
                  evidence: str = "transcribed", project_type: str = "web-saas") -> dict:
    """Record a POLICY the human elected, and cascade it. This tool does not elect; it writes down
    what was elected — the same invariant `record_decision` holds, one level up.

    One level up is the point. A policy is an election over a whole cluster: it decides more than
    one pin, so it earns at least the discipline a single decision gets, not less. Until now it got
    less on the one axis that matters most — `record_decision` refuses an outcome the pin's own
    question never offered, and this door wrote the caller's own sentence onto every pin in the
    cluster regardless of what those pins offered.

    What is refused, so that this cannot be used to choose:

      * an `offer_id` the catalog does not make for this project type;
      * an offer restated in the caller's own words (see `policy_prompt`);
      * a policy with no rule, scope or outcome;
      * an outcome that is not a non-empty string — it is an option id, not a payload;
      * an exception naming a pin that does not exist;
      * a `transcribed` policy with no quote — the same rule as a transcribed decision, and it bites
        harder here, since one unquoted claim would carry a whole cluster;
      * and, per pin, the write itself: a pin whose own `question` does not offer this outcome is
        HELD BACK (`not_offered`) and stays open, exactly as a blocker/high pin is. That is the
        offered-options rule of `record_decision`, applied where it was missing.

    `evidence="elicited"` is reserved for the two paths that actually ask a human — the adapter's
    elicitation branch (`mcp/server.py`) and `mcp/decide.py`, run by the human — each of which shows
    the rule, the OUTCOME it writes, and the pins it would decide, and neither of which lets the
    agent carry the answer. The door takes a CATALOG `offer_id` only: there the rule, the scope and
    the outcome come from shipped data, so nothing on screen was agent-authored. A rule an agent
    composed is elected on the rung that says an agent relayed it.
    """
    prompt = policy_prompt(ledger, offer_id, rule, applies_to, default_outcome, exceptions,
                           project_type)

    _require_quote(human_answer, evidence, writes="policy",
                   because=f"and it bites harder here — this one decides "
                           f"{len(prompt['would_decide'])} pin(s) at once")

    led = _open_existing(ledger)
    policy = led.add_policy(applies_to=prompt["applies_to"], rule=prompt["rule"],
                            default_outcome=prompt["default_outcome"],
                            exceptions=prompt["exceptions"],
                            evidence=evidence, human_answer=human_answer)
    # Exactly this policy, once, over the radius its elector was shown. It used to call
    # `apply_policies()`, which re-ran every policy in the ledger: the returned `cascaded` then
    # listed pins an OLDER policy had just decided, and accepting one policy silently cascaded a
    # previous one over pins added since it was elected — pins nobody was shown when they elected it.
    radius = led.apply_policy(policy)
    # What THIS policy decided on THIS call. Every event it wrote carries evidence `cascaded` and
    # points back at this policy by `policy_id` — none of them claims a relay nobody made, and none
    # of them is another policy's work reported as this one's. The refusal buckets are spread from
    # the radius rather than named one by one: they used to be hardcoded here while `policy_preview`
    # built its shape from `UNASKED_BUCKETS`, so the constant's own comment ("adding a bucket cannot
    # leave one surface reporting four and another five") was false of this surface. The spread
    # also carries `scope_note` (v0.18), which is not a bucket: what a null-valued scope key
    # selected is part of the radius this call reports, and a caller handed the pin lists without
    # it has been handed a narrow-looking rule that matched by absence.
    out = {"policy_id": policy["id"], "rule": policy["rule"],
           "default_outcome": policy["default_outcome"], "evidence": evidence,
           "cascaded": radius["would_decide"]}
    out.update({bucket: radius[bucket] for bucket in radius if bucket != "would_decide"})
    _saved(ledger, led)
    return out


def ledger_add_remediation(ledger: str, pin_id: str, action: str, ladder_rung: int,
                           canonical_target: str | None = None, build_track: str | None = None,
                           contract_carrier: str | None = None) -> dict:
    led = _open_existing(ledger)
    item = led.add_remediation(pin_id, action=action, ladder_rung=ladder_rung,
                               canonical_target=canonical_target, build_track=build_track,
                               contract_carrier=contract_carrier)
    out = {"item_id": item["id"], "pin_id": pin_id, "status": item["status"]}
    _saved(ledger, led)
    return out


def ledger_set_remediation_status(ledger: str, pin_id: str, item_id: str, status: str) -> dict:
    led = _open_existing(ledger)
    item = led.set_remediation_status(pin_id, item_id, status)
    out = {"item_id": item["id"], "status": item["status"]}
    _saved(ledger, led)
    return out


def ledger_resolve(ledger: str, pin_id: str, evidence: str, rung: str = "") -> dict:
    led = _open_existing(ledger)
    pin = led.resolve(pin_id, evidence=evidence, rung=rung or None)
    out = {"pin_id": pin["id"], "state": pin["state"],
           "verification": pin.get("verification")}
    _saved(ledger, led)
    return out


def readiness_assess(ledger: str, pin_id: str, graph_path: str, repo: str = ".",
                     max_depth: int = 2, head: str = "") -> dict:
    """The D0 evidence bundle for one pin's landing zone. Read-only; states no verdict.

    The pin comes through `pin_read` (v0.28), and that is the fix rather than a nicety: this is a
    READ-ONLY tool taking a `pin_id`, which is exactly the class every derived roster on this branch
    excluded — the read-tool roster was *required == ["ledger"]*, the write-door rosters are *takes a
    `pin_id` and commits*, and a read that takes a pin falls between them. It handed
    `readiness.zone_of` whatever `anchors` the file held, so a number there was `TypeError: 'int'
    object is not iterable` and a list of strings was `'str' object has no attribute 'get'`.
    """
    import readiness
    from ledger import pin_read
    led = _open_existing(ledger)
    pin = pin_read(led.pin(pin_id))
    head = head or _git_head()
    if not head:
        raise RuntimeError(
            "cannot resolve HEAD (not a git repo, or git unavailable) — pass `head` explicitly; "
            "without it the staleness gate cannot run, and a zone from a stale graph describes "
            "ground that has since moved"
        )
    # `.get` and not `pin["anchors"]`: `anchors` is not one of the paths `pin_read` MATERIALISES
    # (`PIN_GUARANTEED`), so a file that simply omits it must read as no anchors, not as a KeyError.
    return readiness.assess(graph_path, led.data, pin.get("anchors", []),
                            repo=repo, max_depth=max_depth, head=head)


def ledger_set_readiness(ledger: str, pin_id: str, verdict: str, zone: dict, evidence: dict,
                         hardens: list | None = None, rationale: str = "") -> dict:
    led = _open_existing(ledger)
    pin = led.set_readiness(pin_id, verdict, zone, evidence,
                            hardens=hardens, rationale=rationale)
    out = {"pin_id": pin["id"], "readiness": pin["readiness"],
           "depends_on": pin["depends_on"]}
    _saved(ledger, led)
    return out


def ledger_mark_correctness_unknown(
    ledger: str,
    pin_id: str,
    blocked_by: str,
    attempted: list,
    determinism: str | None = None,
    rung: str | None = None,
) -> dict:
    led = _open_existing(ledger)
    pin = led.mark_correctness_unknown(
        pin_id, blocked_by=blocked_by, attempted=attempted,
        determinism=determinism, rung=rung)
    out = {"pin_id": pin["id"], "state": pin["state"],
           "verification": pin["verification"]}
    _saved(ledger, led)
    return out


def ledger_premortem(ledger: str, pin_id: str, failure_modes: list,
                     guardrails: list | None = None, abort_criteria: list | None = None,
                     paper_tigers: list | None = None) -> dict:
    led = _open_existing(ledger)
    pm = led.premortem(pin_id, failure_modes, guardrails=guardrails,
                       abort_criteria=abort_criteria, paper_tigers=paper_tigers)
    out = {"pin_id": pin_id, "premortem": pm}
    _saved(ledger, led)
    return out


def ledger_label_failure(ledger: str, pin_id: str, failure_class: str, detail: str,
                         phase: str, source: str = "measurer") -> dict:
    led = _open_existing(ledger)
    event = led.label_failure(pin_id, failure_class, detail, phase, source=source)
    out = {"event": event, "foresight": led.foresight(pin_id)}
    _saved(ledger, led)
    return out


def learning_report(ledger: str, min_cluster: int = 2, candidates: list | None = None) -> dict:
    import learning
    return learning.report(_open_existing(ledger), min_cluster=min_cluster, candidates=candidates)


def generator_observe(registry: str, generator: str, outcome: str) -> dict:
    import generators
    reg = generators.load(registry)
    rec = generators.observe(reg, generator, outcome)
    generators.save(reg, registry)
    return {"generator": generator, "record": rec,
            "verdict": generators.health(reg)}


def generator_screen(registry: str, findings: list, bump_run: bool = False) -> dict:
    import generators
    reg = generators.load(registry)
    if bump_run:
        reg["runs"] = reg.get("runs", 0) + 1
        generators.save(reg, registry)
    return generators.screen(reg, findings)


def doc_register(catalog: str, path: str, subject: str, owner: str, sources: list,
                 repo: str = ".", status: str = "planned", commit: str = "") -> dict:
    import doccatalog
    cat = doccatalog.load(catalog)
    entry = doccatalog.register(cat, path, subject, owner, sources, repo=repo,
                                status=status, commit=commit)
    doccatalog.save(cat, catalog)
    return {"registered": entry, "total": len(cat["docs"])}


def doc_freshness(catalog: str, repo: str = ".", graph_path: str = "",
                  changed: list | None = None, git_base: str = "") -> dict:
    import doccatalog
    import impact
    cat = doccatalog.load(catalog)
    graph_data = impact.load(graph_path) if graph_path else None
    files = list(changed) if changed is not None else (
        impact.changed_files_from_git(repo, git_base) if git_base else None)
    out = doccatalog.cascade(cat, files or [], repo=repo, graph_data=graph_data) \
        if files is not None else {
            "rows": [doccatalog.freshness(cat, d, repo=repo, graph_data=graph_data)
                     for d in cat.get("docs", [])],
            "policy": cat.get("policy"),
        }
    out["coverage"] = doccatalog.coverage(cat)
    return out


def ledger_cross_derive(ledger: str, pin_id: str, claim: str, derivations: list,
                        agreement: str, notes: str = "") -> dict:
    led = _open_existing(ledger)
    record = led.cross_derive(pin_id, claim, derivations, agreement, notes)
    pin = led.writable_pin(pin_id)
    # v0.16: what the disagreement DID, said rather than inferred from the state. A closed pin is
    # recorded and not reopened — un-closing finished work has its own arc — and a caller that
    # cannot tell the two apart would read "recorded" as "handled".
    #
    # Read off the event THIS call appended, not re-derived from the pin. Re-derived it was
    # `substate == "contested"`, which is a different fact wearing the same name: `substate` is set
    # by the reopen and never cleared, so a second, AGREEING derivation over the same pin reported
    # `reopened: true` while its own event recorded `false`. Two carriers for one fact, disagreeing —
    # in the return shape of the tool whose whole subject is two derivations disagreeing.
    #
    # `rung_raised` joins it in v0.24 and is the same kind of fact: an AGREEING derivation strengthens
    # the pin's `verification` — unless an arc has a standing refutation on that envelope, in which
    # case the agreement is recorded and the rung is not raised. Reported rather than left to be
    # inferred from `verification`, because "the rung was already `cross_derived`" and "this call
    # raised it" are two different histories that leave the same field.
    event = next(e for e in led.readable("decision_log") if e.get("id") == record["event_id"])
    out = {"pin_id": pin_id, "cross_derivation": record, "state": pin["state"],
           "event_id": event["id"],
           "reopened": event["reopened"],
           "rung_raised": event["rung_raised"],
           "verification": pin.get("verification")}
    _saved(ledger, led)
    return out


def cochange_omissions(changed: list | None = None, repo: str = ".", git_base: str = "",
                       min_commits: int = 3, window: int = 500) -> dict:
    import cochange
    import impact
    files = list(changed or [])
    if not files and git_base:
        files = impact.changed_files_from_git(repo, git_base)
    if not files:
        raise RuntimeError(
            "no changed files — pass `changed` explicitly or a `git_base` to diff against; "
            "an empty diff would report zero omissions, and that would read as clean"
        )
    return cochange.omissions(repo, files, min_commits=min_commits, limit=window)


def scope_check(ledger: str, pin_id: str, changed: list | None = None, repo: str = ".",
                git_base: str = "") -> dict:
    """Did the change stay inside the boundary the pin declared? Read-only.

    The pin comes through `pin_read` for `readiness_assess`'s reason and it is the same class: a
    read-only tool taking a `pin_id`, on no derived roster, dying on the pin's own declared shapes.
    `declared_vs_actual` reaches `(pin.get("readiness") or {}).get("zone")` and iterates
    `pin.get("anchors")` — a `readiness` that is a string and an `anchors` that is a number are both
    in `shape_corpus.broken_pins()`, and both took this tool down with a stack trace.
    """
    import impact
    from ledger import pin_read
    led = _open_existing(ledger)
    files = list(changed or [])
    if not files and git_base:
        files = impact.changed_files_from_git(repo, git_base)
    return impact.declared_vs_actual(pin_read(led.pin(pin_id)), files)


def agent_ready(ledger: str, pin_id: str = "") -> dict:
    import agentready
    led = _open_existing(ledger)
    return agentready.card(led, pin_id) if pin_id else agentready.gate(led)


def ledger_fog(ledger: str) -> dict:
    """The fog register: decisions you can tell are coming and cannot yet phrase.

    `oldest_days` is the number to read, not the count. A register bounded by the elected scope
    graduates or clears as the scope firms up; one whose oldest patch keeps getting older is a
    backlog wearing a doctrine's name.
    """
    return _open_existing(ledger).fog_view()


def ledger_add_fog(ledger: str, area: str, sensed: str, provenance: list,
                   cluster_hint: str = "") -> dict:
    """Record an unphrasable decision without inventing a question for it."""
    led = _open_or_create(ledger)
    patch = led.add_fog(area, sensed, provenance, cluster_hint or None)
    out = {"fog_id": patch["id"], "area": patch["area"]}
    _saved(ledger, led)
    return out


def ledger_graduate_fog(ledger: str, fog_id: str, question: dict, human_answer: str,
                        kind: str = "open_decision", title: str = "", severity: str = "medium",
                        confidence: str = "inferred") -> dict:
    """The human phrased it: the patch becomes a pin and leaves the register.

    The quote is unconditional and is not the usual relay rule wearing a new hat. Phrasing the
    question IS framing the decision — an agent that writes the fork writes which answers are
    thinkable — so this door records a phrasing the human elected and can record no other kind.
    """
    led = _open_existing(ledger)
    _require_quote(human_answer, "transcribed", writes="graduate_fog",
                   because="phrasing the fork is framing the decision, and a fork an agent framed "
                           "is a decision an agent has already half-made")
    pin = led.graduate_fog(fog_id, question=question, human_answer=human_answer, kind=kind,
                           title=title, severity=severity, confidence=confidence)
    out = {"fog_id": fog_id, "pin_id": pin["id"], "state": pin["state"]}
    _saved(ledger, led)
    return out


def ledger_clear_fog(ledger: str, fog_id: str, rationale: str, human_answer: str) -> dict:
    """There was no fork here after all, or the scope moved past it. The patch is deleted."""
    led = _open_existing(ledger)
    _require_quote(human_answer, "transcribed", writes="clear_fog",
                   because="clearing stops the register asking about this, which settles it — and "
                           "an agent settling it alone is an agent deciding not to decide")
    out = led.clear_fog(fog_id, rationale=rationale, human_answer=human_answer)
    _saved(ledger, led)
    return out


def ledger_claim(ledger: str, pin_id: str, holder: str) -> dict:
    """Take a pin before working it. Compare-and-set; writes nothing else.

    It writes nothing else on purpose. The property being bought is that the claim lands BEFORE the
    work, so a door that also recorded something is a door somebody calls second, and a claim taken
    afterwards is a receipt rather than a reservation.

    The refusal is not an error, and the return shape says so: `claimed: false` with the holder
    named is the normal, expected answer when a peer is on it. An exception there would make every
    caller wrap the one outcome that is neither a bug nor a surprise.
    """
    led = _open_existing(ledger)
    out = led.claim(pin_id, holder)
    if out.get("claimed"):
        _saved(ledger, led)
    return out


def ledger_release(ledger: str, pin_id: str, holder: str = "") -> dict:
    """Put a pin back on the frontier without settling it. The other way a claim ends.

    A settlement releases too, so this is for the session that stops without finishing — and for the
    human cleaning up after one that died, which is why `holder` is optional: passing it releases
    only your own claim, omitting it releases whatever is there.
    """
    led = _open_existing(ledger)
    out = led.release(pin_id, holder)
    if out.get("released"):
        _saved(ledger, led)
    return out


def ledger_frontier(ledger: str) -> dict:
    """What is takeable right now — open, unblocked, unclaimed — and what your peers are holding.

    Both halves, never one. A list that silently omits the claimed pins reads as *there is less
    work*, and the difference between that and *somebody else has it* is the whole reason anyone is
    looking.
    """
    from ledger import pin_read
    led = _open_existing(ledger)
    return {
        "frontier": [{"pin_id": pin_read(p)["id"], "title": pin_read(p)["title"],
                      "state": pin_read(p)["state"]} for p in led.frontier()],
        "claimed": led.claims(),
    }


def ledger_defer(ledger: str, pin_id: str, rationale: str, flip_criteria: str,
                 human_answer: str = "") -> dict:
    """Record the human's election to put this pin out of scope for now. It does not elect.

    Deferring is an answer — the spec's own `incompleteness` fork offers it as an option — and it
    settles the pin exactly as `decided` does: the question stops being asked, `interview_next` loses
    it, `open_questions` goes down. Until v0.16 it was the one settlement with no election behind it:
    one state check, no severity threshold, no quote, nothing in the append-only log. An agent alone
    deferred a `blocker` `open_decision` posing a session|jwt fork, and the only trace was a question
    that had stopped being asked.

    So it is held to `record_decision`'s discipline, for the same reason and in the same words: a
    `transcribed` defer must carry the human's answer verbatim, `flip_criteria` says what brings the
    pin back (a defer with no return condition is a deletion with better manners), and a pin whose
    work is already finished is refused rather than closed twice.

    It is NOT held to the offered-options rule: `defer` is a meta-answer about scope, not a branch of
    the pin's fork, and requiring every question to list a defer option would make punting depend on
    whoever authored the pin. What holds it instead is that the human was shown THIS pin.

    **The rung is not a parameter, because the caller cannot know it.** v0.16 made deferring an
    election and then let the agent state its own provenance: one keyword, `evidence="elicited"`,
    settled a `blocker` fork on the rung whose entire claim is that the agent never carried the
    value — reproduced against a client declaring no elicitation capability, so nobody was asked by
    anybody. `record_decision` has never allowed this and the shape it uses is the fix: the rung is
    decided by WHICH PATH RAN. There is one path here — the agent relays — so the rung is
    `transcribed` and the human's words are always required. If deferral ever gains an elicitation
    path, that path sets the rung, exactly as `mcp/server.py::ledger_record_decision` does.

    v0.18 finished that one layer down. `Ledger.defer` kept `evidence="transcribed"` as a parameter
    for two versions after this door dropped it, so the rule was held by the door and not by the
    thing the door protects: the next caller of the library writes a rung nobody earned, and every
    sentence above still says it cannot. A default is not a refusal.
    """
    led = _open_existing(ledger)
    # There is exactly one path here — the agent relays — so the rung is `transcribed` and is not the
    # caller's to state (see above); the same fact is what makes the quote unconditional, which is
    # why this passes the rung rather than a boolean.
    _require_quote(human_answer, "transcribed", writes="defer",
                   because="deferring settles the pin and stops the question being asked, so an "
                           "unquoted one is an agent deciding not to decide, which is the one "
                           "thing no tool here may do")
    pin = led.defer(pin_id, rationale=rationale, flip_criteria=flip_criteria,
                    human_answer=human_answer)
    # Read off the event this call appended, not restated here (v0.18). It used to be a local
    # `evidence = "transcribed"` that was passed down AND reported back — one fact with two
    # carriers, and the parameter it was passed into is the one that has just been removed. The
    # rung the caller is told about is now the rung the log actually holds.
    event = next(e for e in led.readable("decision_log")
                 if e.get("id") == pin["decision"]["event_id"])
    out = {"pin_id": pin["id"], "state": pin["state"], "outcome": "defer",
           "evidence": event["evidence"]}
    _saved(ledger, led)
    return out


# -- the two reopen arcs, and the two doors that put a pin back in front of a human ---------------
#
# Everything above moves a pin forward. Nothing here elects: these four record that something is
# owed a human's attention again — a signal fired, an oracle was refuted, a finding has no fork yet,
# the brainstorm has options. That is why they are exposed at all while `decide` is not, and the
# distinction is enforced structurally rather than promised: no function in this block passes an
# `outcome` anywhere, and `tests/test_ledger.py::TestComingBackIntoTheOpenSetIsGovernedToo` asserts
# it from the AST.

def ledger_reopen(ledger: str, pin_id: str, reason: str, fired: str = "flip_signal",
                  source: str = "feedback:metrics") -> dict:
    """Record that production falsified an elected decision, and hand the pin back. Never decides.

    The downstream arc of the feedback loop, and for four versions it existed in the runtime and on
    no host: `settlement_verdict` refuses to close finished work twice with the words *"Reopen it
    first"*, and nothing could. So the only way to correct a wrongly-closed pin was to hand-edit
    `ledger.json`, which every playbook forbids.

    It writes no outcome, which is what makes it safe to expose — there is no quote to demand and no
    offered option to check, because nothing is being chosen. What it does demand is the observation:
    `reason` must say what was seen, `fired` names the kind of tripwire, `source` names where the
    reading came from. `reopened` in the return says whether the pin actually moved: an observation
    about a pin nobody had settled is still recorded, and reporting it as a move would be a second
    carrier for a fact the event already holds.

    `also_reopened` is the settled dependents the cascade swept up with it — **read off the `cas_`
    records this call appended** (`Ledger.cascaded_by`), not derived from the pins. It used to be
    every pin carrying `substate == "reopened"` and `state == "needs_input"`, and nothing anywhere
    clears that substate: after one legitimate cascade, a later reopen of an unrelated pin reported
    the earlier cascade's pins as its own radius. Same bug, same fix, as `reopened` one field over.
    """
    led = _open_existing(ledger)
    event = led.reopen(pin_id, reason=reason, fired=fired, source=source)
    pin = led.writable_pin(pin_id)
    out = {"pin_id": pin_id, "event_id": event["id"], "reopened": event["reopened"],
           "state": pin["state"], "substate": pin.get("substate"),
           "also_reopened": led.cascaded_by(event["id"])}
    _saved(ledger, led)
    return out


def ledger_challenge(ledger: str, pin_id: str, target: str, challenge_class: str, argument: str,
                     severity: str, upheld: bool, source: str = "challenge:challenger") -> dict:
    """Record a ChallengeEvent against an elected oracle, and — if upheld — hand the pin back.

    The upstream arc: the oracle may be wrong *from the start*, before anything is built on it. Its
    read-only twin `challenge_oracle` proposes the deterministic classes and applies none of them;
    this is where one lands. The judgment classes (`inconsistent`, `unsatisfiable`,
    `unstated_assumption`, `unfounded_infeasibility`) never had a surface at all.

    **Who owns `upheld`: the challenger.** "Read-only" in the roster means *about decisions* —
    reopening is the challenger's whole mandate and electing is what it may never do, so upholding
    belongs to it and the re-answer belongs to the human. What the arc owes in exchange is the
    `argument`: an upheld challenge with nothing stated reopens a human's election on an assertion,
    which is the unquoted relay one arc over, and the runtime refuses it.

    `upheld` and `reopened` are different facts and both come back: a refutation of a pin nobody
    settled is true and moves nothing.

    **`also_reopened` is here for the same reason it is on `ledger_reopen` (v0.20): the two arcs run
    the same cascade.** An upheld challenge reopens the pin *and its settled dependents*, and this
    tool reported none of them — observed, a `resolved` pin was taken back into the open set by a
    challenge on the pin it depends on and appeared in no key of the response. Two arcs, one
    predicate, one writer, added in one commit, and their radius reporting was one over. Read off the
    `cas_` records this call appended, exactly as the downstream arc reads its own.

    `source` is a closed vocabulary (`challenge:challenger`): the arc's safety argument is that it
    never elects, so it may not sign itself with the door that does.
    """
    led = _open_existing(ledger)
    event = led.challenge(pin_id, target=target, challenge_class=challenge_class,
                          argument=argument, severity=severity, upheld=bool(upheld), source=source)
    pin = led.writable_pin(pin_id)
    out = {"pin_id": pin_id, "event_id": event["id"], "upheld": event["upheld"],
           "reopened": event["reopened"], "state": pin["state"],
           "substate": pin.get("substate"),
           "also_reopened": led.cascaded_by(event["id"])}
    _saved(ledger, led)
    return out


def ledger_set_question(ledger: str, pin_id: str, question: dict) -> dict:
    """Give a pin that poses NO fork the fork it needs to reach the interview. Never decides.

    `ledger_add_pin`'s `question` is optional — a finder is not always the one who knows what the
    choice is — and nothing could supply it afterwards, so such a pin stayed `detected` for ever and
    appeared in `interview_next` on no host.

    Write-if-absent, and refused on a pin that already poses one: `question.options[].id` is the
    carrier the offered-options rule anchors on at both election doors, so replacing a fork is an
    agent deciding what the human may choose from. `allow_freeform` is required, because a menu an
    agent composed must leave the human a way to answer outside it.
    """
    led = _open_existing(ledger)
    pin = led.set_question(pin_id, question)
    out = {"pin_id": pin["id"], "state": pin["state"],
           "options": [o["id"] for o in (pin["question"].get("options") or [])],
           "allow_freeform": bool(pin["question"].get("allow_freeform"))}
    _saved(ledger, led)
    return out


def ledger_add_proposals(ledger: str, pin_id: str, proposals: list, notes: str = "") -> dict:
    """Write the brainstorm's options onto ONE pin. Proposes; never decides, by schema.

    The brainstorm agent's own write path, and it had none: `Ledger.add_proposals` is the only
    writer of the `brainstorming` state and no tool reached it, so on every host the brainstorm
    could think and could not record. A proposal carrying a `decision` or an `outcome` is refused —
    neutrality is enforced by the schema, not by good intentions — and at most one may be
    `recommended`, because the gap between what was recommended and what the human elected is the
    single best learning signal in the ledger and two marks make it uncomputable.

    The pin stays in the interview funnel while it is in `brainstorming` (v0.17); its proposals ride
    along on the funnel entry, so the exploration flows into the answer instead of replacing it.
    """
    led = _open_existing(ledger)
    pin = led.add_proposals(pin_id, list(proposals or []), notes=notes)
    out = {"pin_id": pin["id"], "state": pin["state"],
           "proposals": [p["id"] for p in pin["brainstorm"]["proposals"]],
           "recommended": next((p["id"] for p in pin["brainstorm"]["proposals"]
                                if p.get("recommended")), "")}
    _saved(ledger, led)
    return out


# -- coverage manifest -------------------------------------------------------------------------

def coverage_gaps(langs: list, reports: list | None = None) -> dict:
    """Which expected analysis capabilities ran vs are missing, for the present stacks."""
    import coverage
    return coverage.report(langs, reports or [])


def contract_diff(contract: str, backend: str = "auto", **layers) -> dict:
    # Wrapped under a key, not returned bare: MCP's `structuredContent` is an object, so a tool that
    # hands back the engine's `list[dict]` is rejected on the wire before the agent sees a thing —
    # even at zero drift, where the list is empty. `findings_gate` already answers under that key,
    # and a named key leaves room to say more later without breaking a caller that reads
    # `["findings"]`.
    import shapes
    findings = shapes.drift_check(contract, backend=backend, **{k: v for k, v in layers.items() if v})
    return {"findings": findings}


def reconcile_layers(layer_a: str, path_a: str, layer_b: str, path_b: str,
                     correspondence: dict | None = None) -> dict:
    import shapes
    return {"findings": shapes.reconcile_layers(layer_a, path_a, layer_b, path_b,
                                                correspondence=correspondence)}


def propose_correspondence(layer_a: str, path_a: str, layer_b: str, path_b: str,
                           min_overlap: float = 0.5) -> dict:
    import shapes
    return {"candidates": shapes.propose_correspondence(layer_a, path_a, layer_b, path_b,
                                                        min_overlap=min_overlap)}


def _git_head(cwd: str | None = None) -> str:
    """HEAD of the repository the agent is working in. Resolved here rather than asked of the
    caller: an agent cannot reliably know the sha, and a wrong one silently defeats the staleness
    gate — which is the one thing making the graph's answers trustworthy."""
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def blast_radius(graph_path: str, node_id: str, head: str = "", depth: int = 2) -> dict:
    import graph as G
    g = G.load(graph_path)
    head = head or _git_head()
    if not head:
        raise RuntimeError(
            "cannot resolve HEAD (not a git repo, or git unavailable) — pass `head` explicitly; "
            "without it the staleness gate cannot run, and an ungated blast radius is worse than none"
        )
    if not g.is_current(head):
        # A stale blast radius reports impact for code that has since moved. Refuse, don't degrade.
        raise RuntimeError(
            f"graph is stale (built_at_commit={g.built_at_commit!r} != HEAD {head!r}) — rebuild it; "
            "a blast radius computed on a stale graph is worse than none"
        )
    return {"node_id": node_id, "head": head,
            "impacted": sorted(g.blast_radius(node_id, max_depth=depth))}


def generate_layers(contract: str, out: str, layers: list | None = None) -> dict:
    import generate as GEN
    c = GEN.Contract.load(contract)
    produced = GEN.generate_all(c, tuple(layers) if layers else GEN.LAYERS)
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    written = {}
    for layer, text in produced.items():
        p = outdir / GEN._FILENAMES[layer]
        p.write_text(text, encoding="utf-8", newline="\n")
        written[layer] = str(p)
    return {"written": written}


def findings_gate(reports: list) -> dict:
    import findings as F
    gated = F.FpGate().run(F.load_and_normalize(reports))
    return {"findings": gated, "audit": F.audit_log(gated)}


def build_waves(ledger: str) -> dict:
    import buildloop
    return buildloop.plan(_open_existing(ledger))


def challenge_oracle(ledger: str) -> dict:
    import challenger
    return {"proposed": challenger.scan(_open_existing(ledger))}


def _livemap_marker(ledger: str) -> Path:
    """Sidecar that records which map file(s) are tracking this ledger live. A file:// page cannot
    poll a sibling JSON (opaque origin), so 'live' is the MCP layer re-projecting the file on every
    ledger write; this marker is how a write knows a live map exists and where it is. It is a runtime
    artifact next to ledger.json (same gitignore class), created only when live=True is requested."""
    return Path(str(ledger) + ".livemap")


def _register_live_map(ledger: str, out: str) -> None:
    m = _livemap_marker(ledger)
    outs: list = []
    if m.is_file():
        try:
            outs = json.loads(m.read_text(encoding="utf-8")).get("outs", [])
        except (OSError, ValueError):
            outs = []
    ap = str(Path(out).resolve())
    if ap not in outs:
        outs.append(ap)
    m.write_text(json.dumps({"outs": outs}), encoding="utf-8", newline="\n")


def _unregister_live_map(ledger: str, out: str) -> None:
    m = _livemap_marker(ledger)
    if not m.is_file():
        return
    try:
        outs = json.loads(m.read_text(encoding="utf-8")).get("outs", [])
    except (OSError, ValueError):
        return
    outs = [o for o in outs if o != str(Path(out).resolve())]
    if outs:
        m.write_text(json.dumps({"outs": outs}), encoding="utf-8", newline="\n")
    else:
        try:
            m.unlink()
        except OSError:
            pass


def _refresh_live_maps(ledger: str) -> None:
    """Re-project every live map registered for this ledger. Best-effort by design: a render failure
    must never break the ledger write that triggered it, and a ledger with no live map pays nothing
    (the marker check returns immediately).

    **`Exception`, and the narrow tuple that was here is the finding (v0.25).** The docstring said
    *never* and the handler caught `(OSError, ValueError)` — not `AttributeError`, `TypeError` or
    `KeyError`, which are precisely the failure classes this whole round is about. A ledger the
    renderer chokes on would therefore have taken down the WRITE that had already succeeded and been
    persisted: the pin is on disk, the tool returns `isError`, and the agent is told its write
    failed. The rule is the docstring's own, so the handler is the rule's: anything the projection
    raises is the projection's problem, and the marker is read the same way for the same reason (a
    marker file holding a JSON list met `.get`).

    Nothing is swallowed that a caller needed: `render_map` is the door that RENDERS, and it does
    not go through here — a failure there is reported to the caller who asked for a render.
    """
    m = _livemap_marker(ledger)
    if not m.is_file():
        return
    try:
        outs = json.loads(m.read_text(encoding="utf-8")).get("outs", [])
    except Exception:
        return
    if not isinstance(outs, list) or not outs:
        return
    import map as M
    for out in outs:
        try:
            M.render_file(ledger, out, live=True)
        except Exception:
            continue


def render_map(ledger: str, out: str, live: bool = False) -> dict:
    import map as M
    _open_existing(ledger)  # refuse to render a map of a ledger that isn't there
    M.render_file(ledger, out, live=live)
    # live=True registers the file so every later ledger write re-projects it; live=False (the
    # shareable frozen artifact) clears any prior registration so it stops auto-refreshing.
    (_register_live_map if live else _unregister_live_map)(ledger, out)
    return {"written": out, "live": live}


def spend_report(project: str = "", session: str = "", pricing: str = "",
                 declared_mcp: list | None = None) -> dict:
    import spend
    price = pricing or None
    if session:
        return spend.report_session(session, pricing=price, declared_mcp=declared_mcp)
    if project:
        return spend.report_project(project, pricing=price, declared_mcp=declared_mcp)
    raise ValueError(
        "spend_report needs `session` (a transcript .jsonl) or `project` (a repo dir, to discover "
        "this host's session store)")


def design_scan(paths: list, scope: str = "", viewport: str = "", no_advisory: bool = False) -> dict:
    import design
    return design.scan(paths, scope=scope or None, viewport=viewport, no_advisory=no_advisory)


def generate_tokens(contract: str, out: str) -> dict:
    import design_tokens as DT
    ts = DT.TokenSet.load(contract)
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    files = {"tokens.css": DT.to_css_vars(ts), "theme.css": DT.to_tailwind(ts),
             "DESIGN.md": DT.to_design_md(ts)}
    written = {}
    for name, text in files.items():
        p = outdir / name
        p.write_text(text, encoding="utf-8", newline="\n")
        written[name] = str(p)
    return {"written": written}


def tokens_diff(contract: str, css: str) -> dict:
    import design_tokens as DT
    ts = DT.TokenSet.load(contract)
    p = Path(css)
    text = p.read_text(encoding="utf-8") if p.exists() else css
    return DT.drift_check(ts, text)


def extract_tokens(css: str) -> dict:
    import design_tokens as DT
    p = Path(css)
    text = p.read_text(encoding="utf-8") if p.exists() else css
    return {"candidate": DT.harvest_tokens(text)}


# -- reference-image evidence (the deterministic half of "build me this screenshot") -----------
# Read-only over an image the user supplied. The split these two tools exist to hold open: what is
# computed from pixels is D0, what a model says about the picture is D2, and only the first one is
# allowed to refute the second.

def _claimed_colors(claimed, contract: str = ""):
    """Normalize the claim set: a DTCG contract's color group, a list of `{name, value}`, or bare
    hex strings. A contract wins when both are given — checking the artifact that will actually be
    generated from is the stronger question."""
    if contract:
        import design_tokens as DT
        return {t["path"]: t["value"] for t in DT.TokenSet.load(contract).of_type("color")
                if isinstance(t["value"], str)}
    seq = list(claimed or [])
    if any(isinstance(item, dict) for item in seq):
        named = {}
        for i, item in enumerate(seq, 1):
            if isinstance(item, dict):
                value = item.get("value") or item.get("hex") or item.get("color")
                named[item.get("name") or item.get("token") or f"claim_{i}"] = value
            else:
                named[f"claim_{i}"] = item
        return named
    return seq


def image_palette(image: str) -> dict:
    import visual
    return visual.image_facts(image)


def palette_verify(image: str, claimed: list | None = None, contract: str = "",
                   tolerance: float = 0.0, contrast_pairs: list | None = None,
                   coverage_floor: float = 0.0) -> dict:
    """`coverage_floor` reaches the engine now; it accepted the parameter and nothing could pass it.

    Both overrides use `0.0` as "the declared default", matching `tolerance` one line up. That is a
    real (small) loss of range and it is the right one: a floor of exactly zero makes `coverage >=
    floor` true for every claim, which is the vacuous verdict `verify_palette` was just taught to
    refuse — so the one value the sentinel costs is the one value nobody should pass.
    """
    import visual
    out = visual.verify_palette(image, _claimed_colors(claimed, contract),
                                tolerance=tolerance or None,
                                coverage_floor=coverage_floor or None)
    if contract:
        out["contract"] = contract
    if contrast_pairs:
        out["contrast"] = visual.check_contrast(contrast_pairs)
    return out


# -- comprehension / understand-mode (the structural-graph family) ----------------------------
# These read/write the graph.json + its projections on disk. The graph is the foundational
# artifact the rest of the family consumes (phases communicate through disk, never a session).

def build_graph(root: str, out: str, commit: str = "") -> dict:
    import graph_build
    data = graph_build.build_graph(root, commit=commit or None)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return {"written": out, "nodes": len(data.get("nodes", [])), "edges": len(data.get("links", [])),
            "built_at_commit": (data.get("graph") or {}).get("built_at_commit")}


def understand_codebase(root: str, out: str, commit: str = "") -> dict:
    import understand
    bundle = understand.understand(root, commit=commit or None)
    paths = understand.write_bundle(bundle, out)
    return {"written": paths, "overview": bundle.get("overview")}


def explain_node(graph_path: str, target: str, root: str = "") -> dict:
    import explain
    return explain.explain(explain.load(graph_path), target, root=root or None)


def graph_query(graph_path: str, query: str, limit: int = 10, expand: bool = True) -> dict:
    import query as Q
    return Q.search(Q.load(graph_path), query, limit=limit, expand=expand)


def guided_tour(graph_path: str, max_steps: int = 14) -> dict:
    import tours
    return tours.build_tour(tours.load(graph_path), max_steps=max_steps)


def domain_view(root: str) -> dict:
    import domain
    return domain.scan_entry_points(root)


def fingerprint_scan(root: str, out: str, against: str = "", commit: str = "") -> dict:
    import fingerprint as FP
    new = FP.store(root, commit=commit or None)
    result = {"files": len(new.get("files", {})), "built_at_commit": new.get("built_at_commit")}
    if against:
        old = FP.load_store(against)
        result["verdict"] = FP.classify_update(FP.diff_stores(old, new), len(new.get("files", {}))) \
            if old else {"verdict": "FULL", "reason": "no prior fingerprint store"}
    result["wrote"] = FP.save_store(new, out)   # guarded: False rather than clobber a non-empty store
    return result


def graph_map(graph_path: str, out: str, tour_path: str = "", title: str = "") -> dict:
    import graphmap
    graphmap.render_file(graph_path, out, tour_path or None)
    return {"written": out}


def impact_overlay(graph_path: str, changed: list | None = None, git_base: str = "",
                   root: str = ".", depth: int = 1) -> dict:
    import impact
    files = list(changed) if changed else (
        impact.changed_files_from_git(root, git_base) if git_base else None)
    if not files:
        raise ValueError("provide `changed` (a file list) or `git_base` (a git ref) — "
                         "impact needs a change set to compute a blast radius over")
    return impact.overlay(impact.load(graph_path), files, depth=depth)


def docs_claims(graph_path: str, docs: list | None = None, draft: str = "",
                mode: str = "audit") -> dict:
    """Audit docs that exist, or gate a draft before publishing. One engine, two directions —
    two tools would have been two descriptions for one idea."""
    import docs_claims as DC
    data = DC.load(graph_path)
    if mode == "audit":
        return DC.analyze(list(docs or []), data)
    if not draft and docs:
        draft = Path(docs[0]).read_text(encoding="utf-8", errors="replace")
    if not draft:
        raise RuntimeError("publishing modes need `draft` text, or a `docs` path to read it from")
    pub_mode = "prospective" if mode == "publish_prospective" else "descriptive"
    return DC.publication_gate(draft, data, source=(docs or ["<draft>"])[0], mode=pub_mode)


def _agents_md(root: str) -> Path:
    return Path(root) / "AGENTS.md"


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _instructions_render(ledger: str, root: str, max_lines: int, generated: list | None):
    """Shared by the generate/diff pair so the two can never disagree about what the region SHOULD be
    — the same failure mode as a linter that reimplements its formatter. That sharing is also what
    makes the generated-file recovery below correct in both: ask the same question, get the same
    answer.

    `generated=None` means "keep whatever the region already records" — recovered from the region
    itself, so a regeneration triggered by anything else (a pin decided, a policy added) cannot
    silently drop the never-hand-edit list. `[]` clears it, explicitly.
    """
    import instructions as INS
    led = _open_existing(ledger)
    if generated is None:
        generated = INS.extract_generated(_read(_agents_md(root)))
    try:
        rel = str(Path(ledger).resolve().relative_to(Path(root).resolve()))
    except ValueError:                      # ledger outside the project root — name it as given
        rel = ledger
    return INS, INS.render(led.data, max_lines=max_lines or INS.MAX_LINES,
                           ledger_path=rel.replace("\\", "/"), generated=generated), generated


def generate_instructions(ledger: str, root: str = ".", generated: list | None = None,
                          generated_from: str = "", generated_by: str = "",
                          max_lines: int = 0, bridge: bool = True) -> dict:
    INS, body, effective = _instructions_render(ledger, root, max_lines, generated)
    base = Path(root)
    agents = _agents_md(root)
    agents.parent.mkdir(parents=True, exist_ok=True)
    agents.write_text(INS.apply(_read(agents), body), encoding="utf-8", newline="\n")
    written = {"agents_md": str(agents)}

    if bridge:
        claude = base / "CLAUDE.md"
        bridged = INS.claude_bridge(_read(claude))
        if bridged is not None:
            claude.write_text(bridged, encoding="utf-8", newline="\n")
            written["claude_md"] = str(claude)

    # The Claude-only rule is a projection of the SAME list the region carries, so it is rewritten
    # and removed in lockstep with it. Letting it outlive an emptied list would leave two carriers
    # of one fact disagreeing — the drift this module exists to make impossible.
    rule = base / ".claude" / "rules" / "keel-generated-files.md"
    if effective:
        rule.parent.mkdir(parents=True, exist_ok=True)
        rule.write_text(
            INS.rule_generated_files(list(effective), generated_from or "the contract",
                                     generated_by or "generate_layers"),
            encoding="utf-8", newline="\n")
        written["claude_rule"] = str(rule)
    elif rule.is_file():
        rule.unlink()
        written["claude_rule_removed"] = str(rule)

    return {"written": written, "region_lines": len(body.splitlines()),
            "generated": sorted(str(g) for g in effective)}


def instructions_diff(ledger: str, root: str = ".", generated: list | None = None,
                      max_lines: int = 0, bridge: bool = True) -> dict:
    INS, body, effective = _instructions_render(ledger, root, max_lines, generated)
    agents = _agents_md(root)
    out = INS.drift_check(_read(agents), body)
    ctext = _read(Path(root) / "CLAUDE.md")
    if not bridge:
        # The caller opted out of the bridge; reporting it "missing" would describe a deliberate
        # choice as a defect, and a status nobody can ever clear gets ignored on sight.
        out["claude_bridge"] = "not_requested"
    else:
        out["claude_bridge"] = "present" if (ctext and INS.claude_bridge(ctext) is None) else "missing"
    out["path"] = str(agents)
    out["generated"] = sorted(str(g) for g in effective)
    return out
