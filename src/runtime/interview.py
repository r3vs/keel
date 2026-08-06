"""Decision-frame + interview funnel — greenfield's Phase-1 catalog expansion as code.

`references/decision-catalog.md` is a *frame, not a script*: Phase 1 loads the machine-usable
catalog, prunes it by project type, skips the forks the brief already decided, and materializes
one ledger pin per surviving fork. The shared interview funnel
(`references/core/interview-funnel.md`) then compresses those pins — cluster → policy → exception →
proposed-default — and orders the real questions by information gain. This module is that pipeline
over `runtime/ledger.py`; it adds no state of its own (the ledger stays the single source of truth).

Both disciplines from the catalog playbook are enforced here:
1. **Prune by project type** before asking anything (a CLI has no rendering fork).
2. **Skip what the brief already decided** — recorded as pre-committed `DecisionEvent`s (source
   `interview`, so neutrality holds), never re-asked. Skipping is a *write*, so it passes the one
   predicate every unasked write passes (`Ledger.unasked_verdict`): the brief settles a fork only
   with one of that fork's own options, and never a `blocker`/`high` one. See `expand_catalog`.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

_HERE = pathlib.Path(__file__).resolve().parent

#: Where the catalog is, in each of the two trees this module lives in. The authoring path was the
#: only one for a while, and it cannot resolve after install: shipped, this module is
#: `keel-core/mcp/runtime/interview.py`, so `parent.parent` is `keel-core/mcp` — and the catalog is
#: in a DIFFERENT plugin (`greenfield-forge/skills/...`), which no plugin may read. So
#: `interview_expand` and `interview_seed_policies` raised FileNotFoundError on every host while 704
#: tests passed, because every test hands `load_catalog` an explicit path. `build.py` vendors the
#: file beside the runtime for exactly this; the candidate order puts the shipped location first,
#: since that is the one a user actually runs.
_CATALOG_CANDIDATES = (
    _HERE / "assets" / "decision-catalog.json",
    _HERE.parent / "skills" / "greenfield-forge" / "assets" / "decision-catalog.json",
)
CATALOG_PATH = next((p for p in _CATALOG_CANDIDATES if p.is_file()), _CATALOG_CANDIDATES[0])


def load_catalog(path: str | pathlib.Path = None) -> dict:
    """The machine-usable catalog. Resolved at CALL time, never at import time.

    A module-level constant is evaluated once, when the server starts, and this file is imported by
    a server whose install layout differs from the repo's — so a stale constant would freeze the
    wrong answer for the process's whole life. The failure also has to name both places it looked:
    a bare `FileNotFoundError` on a path the reader has never seen is how this stayed invisible.
    """
    if path is None:
        path = next((p for p in _CATALOG_CANDIDATES if p.is_file()), None)
        if path is None:
            looked = "\n  ".join(str(p) for p in _CATALOG_CANDIDATES)
            raise FileNotFoundError(
                "the decision catalog is not beside this runtime. Looked in:\n  " + looked +
                "\nShipped, it is vendored to mcp/runtime/assets/ by scripts/build.py.")
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fork_question(cluster: dict) -> Optional[dict]:
    opts = cluster.get("options", [])
    if not opts:
        # an outcomes/elicitation cluster: a bounded elicitation, not an options-fork
        if cluster.get("elicit"):
            return {"prompt": f"{cluster['title']}: {cluster['elicit']}. In scope for v1?",
                    "options": [{"id": "in", "label": "In v1 scope"},
                                {"id": "defer", "label": "Defer (deferred)"}],
                    "allow_freeform": True}
        return None
    return {
        "prompt": cluster["title"] + "?",
        "options": [{"id": o["id"], "label": o["label"],
                     **({"implication": o["implication"]} if o.get("implication") else {})}
                    for o in opts],
        "allow_freeform": True,
    }


def expand_catalog(ledger, catalog: dict, project_type: str = "web-saas",
                   brief_decisions: Optional[dict] = None) -> dict:
    """Materialize open_decision / acceptance_criterion pins from the catalog into the ledger.

    - `project_type` prunes whole clusters (a fork absent from the type is not a question).
    - `brief_decisions` maps cluster_id → an already-decided outcome; those pins are created and
      immediately committed (pre-decided by the brief), never left as open questions.

    **`brief` is a rung, not a hole (v0.14).** It means *answered from the project brief, without
    asking* — which is exactly why it is held to `Ledger.unasked_verdict`, the same predicate the
    policy cascade passes: nobody was asked here either. So the outcome must be an option id the
    pin's own question offers, and a `blocker`/`high` fork is never settled this way. Before that,
    this was the third door onto `decide`, and the weakest: an agent-supplied dict wrote any string
    onto any cluster at any severity, so `{"persistence": "mongodb", "identity": "roll our own
    crypto"}` committed `high` pins to outcomes their questions never offered, with `evidence:
    brief` claiming a document that was never quoted. A brief that really did settle the persistence
    fork settles it with one of the fork's own options; anything else is a fork the brief left open,
    and the funnel exists to ask those.

    A held-back cluster is NOT dropped: its pin is created open, named in the return so an agent
    reading the result knows the brief did not carry it rather than assuming it did, and marked
    `resolution_mode: asked` when — and only when — the refusal is a standing property of the pin
    (`ledger.STANDING_REFUSALS`, v0.18). A `blocker` fork demands to be asked whatever any rule
    says; a fork whose menu did not contain the brief's word does not, and that mark had no
    clearing door.

    **Nor is a key that matched no cluster** (v0.16). `brief_decisions` is agent-supplied, and a key
    naming no cluster of this catalog — or one pruned for this `project_type` — used to fall through
    every branch: it landed in neither `pre_decided` nor `brief_held_back`, and the caller was told
    to check a list that would never mention it. Silently dropping an input while reporting on the
    inputs beside it is the same class this module's own gate exists to close, one layer up. They
    come back in `brief_unmatched` with which of the two it was.

    depends_on is wired from catalog cluster ids to the freshly-created pin ids. Returns
    {created, pruned, pre_decided, brief_held_back, brief_unmatched, id_map}.
    """
    brief_decisions = brief_decisions or {}
    id_map: dict[str, str] = {}       # catalog cluster id -> ledger pin id
    created, pruned, pre_decided, held_back = [], [], [], []

    for cluster in sorted(catalog["clusters"], key=lambda c: c["order"]):
        cid = cluster["id"]
        if project_type in cluster.get("prune_for", []):
            pruned.append(cid)
            continue
        deps = [id_map[d] for d in cluster.get("depends_on", []) if d in id_map]
        question = _fork_question(cluster)
        as_is = ({"built": None} if cluster["kind"] == "acceptance_criterion"
                 else {"givens": [], "built": None})
        pin = ledger.add_pin(
            kind=cluster["kind"],
            title=cluster["title"],
            severity=cluster["severity"],
            confidence="inferred",
            provenance=[{"source": "decision-catalog", "detail": f"cluster:{cid}"}],
            as_is=as_is,
            question=question,
            depends_on=deps,
            cluster_id=f"cl_{cid}",
        )
        id_map[cid] = pin["id"]
        if cid not in brief_decisions:
            created.append(pin["id"])
            continue
        outcome = brief_decisions[cid]
        verdict = ledger.unasked_verdict(pin, outcome)
        if verdict != "would_decide":
            # Held back for the reason the predicate gives, and the pin joins the questions to ask.
            #
            # The mark is written only for a refusal that is a standing property of the PIN
            # (v0.18). This door had the identical defect `apply_policy` had, for the identical
            # reason — `verdict != "would_decide"` includes `not_offered`, which says the BRIEF's
            # answer is not on this fork's menu, and stamping that on the pin made it permanent:
            # nothing clears `resolution_mode`, so a later policy that fits the pin exactly would
            # be refused for ever by a sentence somebody typed into a brief. Reading the shared
            # tuple rather than repeating the rule is the point; a rule spelled out at two doors is
            # a rule one of them will be fixed without.
            from ledger import STANDING_REFUSALS
            if verdict in STANDING_REFUSALS:
                pin["resolution_mode"] = "asked"
            created.append(pin["id"])
            held_back.append({"cluster_id": cid, "pin_id": pin["id"], "outcome": outcome,
                              "reason": verdict, "severity": pin["severity"],
                              "offers": [o["id"] for o in (question or {}).get("options", [])]})
            continue
        ledger.decide(pin["id"], outcome=outcome,
                      rationale="pre-decided by the brief",
                      flip_criteria=f"if the brief's {cid} choice is contradicted downstream",
                      evidence="brief")
        pre_decided.append(cid)
    # Sorted, not in the caller's dict order: this is a report about a set, and a report whose order
    # depends on how the argument was typed is one two runs can disagree about.
    unmatched = [{"cluster_id": cid, "outcome": brief_decisions[cid],
                  "reason": "pruned_for_project_type" if cid in pruned else "no_such_cluster"}
                 for cid in sorted(brief_decisions) if cid not in id_map]
    return {"created": created, "pruned": pruned, "pre_decided": pre_decided,
            "brief_held_back": held_back, "brief_unmatched": unmatched, "id_map": id_map}


def default_policies(catalog: dict, ledger, project_type: str = "web-saas") -> dict:
    """The catalog's per-cluster default policies become the interview's opening policy offers.
    Each, if the user accepts it, auto-resolves the low-severity tail of that cluster (the funnel's
    policy step). Not applied here — offered; the user elects (`mcp:ledger_record_policy`).

    `default_outcome` is stated on the offer, not derived downstream, and for a catalog offer it is
    the cluster's `default_policy_outcome`: **one of that cluster's own option ids**, so the value
    the offer promises is a value the pins it would decide actually offer. It used to be the
    `default_policy` sentence itself, which meant accepting the persistence offer wrote *"one
    relational datastore until a concrete need proves otherwise; schema-first"* as the outcome of a
    pin whose question offered `relational | document | kv | none` — prose no downstream reader can
    consume, and an outcome nobody was ever offered.

    Returns both halves, because the second is not an empty set (v0.12):

      * `offers` — clusters whose stated default IS one of their options. Electable, cascadable.
      * `no_default_outcome` — clusters that state a default no single option carries: `nfrs` names
        four at once, `delivery`'s is conditional on the topology fork, `outcomes` has no options to
        name. They are returned rather than dropped, so a reader can tell "this default must be
        asked" from "this cluster has no default", and so the catalog doc and this function cannot
        quietly disagree about which clusters state one.
    """
    offers, no_outcome = [], []
    for cluster in catalog["clusters"]:
        if project_type in cluster.get("prune_for", []):
            continue
        if not cluster.get("default_policy"):
            continue
        cid = f"cl_{cluster['id']}"
        outcome = cluster.get("default_policy_outcome")
        if outcome:
            offers.append({"cluster_id": cid,
                           "rule": cluster["default_policy"],
                           "default_outcome": outcome,
                           "applies_to": {"cluster_id": cid}})
        else:
            no_outcome.append({"cluster_id": cid,
                               "rule": cluster["default_policy"],
                               "reason": "no single option of this cluster carries that default, "
                                         "and a cascade may only write an outcome the pin's own "
                                         "question offers — ask this one"})
    return {"offers": offers, "no_default_outcome": no_outcome}


def funnel(ledger) -> dict:
    """Run the compression over the current ledger and return the interview view.

    200 pins → clusters → policies → the few real questions (asked), the rest skimmable as
    proposed_default. Order the asked questions by information gain (the ledger's interview_view
    already sorts by transitive downstream fan-out). Returns a structured, renderable view.

    An entry carries `proposals` when the brainstorm has written any (v0.17). `core/brainstorm.md`
    states the arc — *"its proposals surface back as options on that pin's interview question, so
    the user's exploration flows straight into their answer"* — and this is the surface where that
    sentence is either true or decoration: the pin only just became reachable here at all, and
    arriving at the top of the funnel with the options it was opened for invisible would waste the
    fix. Neutrality is unchanged: a proposal is not an option id, `record_decision` still admits
    only what `question.options[].id` offers or a freeform answer the question permits, and
    `recommended` is carried as the brainstorm's own mark rather than as a default.

    An entry carries `blocked_by` when the pin's `verification` envelope records one (v0.19). A
    `correctness_unknown` pin is sorted to the FRONT of this funnel by `interview_view`, and the one
    sentence that makes it answerable is what stopped verification — which used to arrive here only
    because `mark_correctness_unknown` pasted it into the human's own `question.prompt`, i.e. by
    deleting their fork. v0.16 rightly stopped doing that and the reach went with it: the pin
    arrived first, and blank. So the reason travels as its own key, beside the prompt rather than
    inside it, and the fork stays exactly where its author left it."""
    ledger.assign_resolution_modes()
    view = ledger.interview_view()

    def transitive_downstream(pin_id: str, seen: frozenset = frozenset()) -> int:
        total = 0
        for p in ledger.data["pins"]:
            if pin_id in p.get("depends_on", []) and p["id"] not in seen:
                total += 1 + transitive_downstream(p["id"], seen | {p["id"]})
        return total

    asked, tail = [], []
    for pin in view:
        entry = {"pin_id": pin["id"], "title": pin["title"], "severity": pin["severity"],
                 "prompt": (pin.get("question") or {}).get("prompt", ""),
                 "downstream": transitive_downstream(pin["id"])}
        blocked_by = (pin.get("verification") or {}).get("blocked_by")
        if blocked_by:
            entry["blocked_by"] = blocked_by
        proposals = (pin.get("brainstorm") or {}).get("proposals") or []
        if proposals:
            entry["proposals"] = [{"id": p.get("id"), "summary": p.get("summary"),
                                   "effort": p.get("effort"),
                                   "recommended": bool(p.get("recommended"))}
                                  for p in proposals]
        if pin.get("resolution_mode") == "proposed_default":
            tail.append(entry)
        else:
            asked.append(entry)
    return {"asked": asked, "proposed_default": tail,
            "asked_count": len(asked), "tail_count": len(tail),
            "total_open": len(view)}
