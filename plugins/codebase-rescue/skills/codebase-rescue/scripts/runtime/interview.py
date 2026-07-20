# GENERATED FILE - do not edit. Source: src/runtime/interview.py at the repo root;
# regenerate with: python scripts/build.py
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
   `interview`, so neutrality holds), never re-asked.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

CATALOG_PATH = (pathlib.Path(__file__).resolve().parent.parent
                / "skills" / "greenfield-forge" / "assets" / "decision-catalog.json")


def load_catalog(path: str | pathlib.Path = CATALOG_PATH) -> dict:
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

    depends_on is wired from catalog cluster ids to the freshly-created pin ids. Returns
    {created: [pin_ids], pruned: [cluster_ids], pre_decided: [cluster_ids]}.
    """
    brief_decisions = brief_decisions or {}
    id_map: dict[str, str] = {}       # catalog cluster id -> ledger pin id
    created, pruned, pre_decided = [], [], []

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
        if cid in brief_decisions:
            ledger.decide(pin["id"], outcome=brief_decisions[cid],
                          rationale="pre-decided by the brief",
                          flip_criteria=f"if the brief's {cid} choice is contradicted downstream")
            pre_decided.append(cid)
        else:
            created.append(pin["id"])
    return {"created": created, "pruned": pruned, "pre_decided": pre_decided,
            "id_map": id_map}


def default_policies(catalog: dict, ledger, project_type: str = "web-saas") -> list[dict]:
    """The catalog's per-cluster default policies become the interview's opening policy offers.
    Each, if the user accepts it, auto-resolves the low-severity tail of that cluster (the funnel's
    policy step). Not applied here — offered; the user elects."""
    offers = []
    for cluster in catalog["clusters"]:
        if project_type in cluster.get("prune_for", []):
            continue
        if cluster.get("default_policy"):
            offers.append({"cluster_id": f"cl_{cluster['id']}",
                           "rule": cluster["default_policy"],
                           "applies_to": {"cluster_id": f"cl_{cluster['id']}"}})
    return offers


def funnel(ledger) -> dict:
    """Run the compression over the current ledger and return the interview view.

    200 pins → clusters → policies → the few real questions (asked), the rest skimmable as
    proposed_default. Order the asked questions by information gain (the ledger's interview_view
    already sorts by transitive downstream fan-out). Returns a structured, renderable view."""
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
        if pin.get("resolution_mode") == "proposed_default":
            tail.append(entry)
        else:
            asked.append(entry)
    return {"asked": asked, "proposed_default": tail,
            "asked_count": len(asked), "tail_count": len(tail),
            "total_open": len(view)}


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Expand the decision catalog into a ledger and print the funnel view")
    parser.add_argument("ledger", help="path to a ledger.json (created if absent)")
    parser.add_argument("--project-type", default="web-saas",
                        help="cli | library | static-site | api-service | web-saas")
    parser.add_argument("--catalog", default=str(CATALOG_PATH))
    args = parser.parse_args(argv)

    from ledger import Ledger
    led = Ledger(args.ledger)
    catalog = load_catalog(args.catalog)
    result = expand_catalog(led, catalog, args.project_type)
    view = funnel(led)
    led.save()
    print(f"expanded catalog for project-type={args.project_type}: "
          f"{len(result['created'])} open decisions, {len(result['pruned'])} clusters pruned")
    print(f"funnel: {view['asked_count']} asked, {view['tail_count']} proposed_default\n")
    for q in view["asked"]:
        print(f"  [{q['severity']:>7}] (+{q['downstream']} downstream) {q['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
