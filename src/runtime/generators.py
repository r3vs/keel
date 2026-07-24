"""Generator-level false-positive discipline — the layer above `FpGate`.

`findings.FpGate` judges one finding at a time: is *this* one reachable, corroborated, a framework
pattern, a duplicate. That is necessary and it is blind to the pattern that actually poisons a
findings stream — **a generator that is wrong over and over**. Each of its findings can look
individually plausible while the rule itself has been refuted eleven times this month.

Without this layer every new signal is a potential flooder, which is a real risk the moment
co-change and scope-check start emitting. A stream nobody trusts gets ignored wholesale, and then
the one true finding in it is ignored too. Precision is not a nicety here; it is the thing that
keeps the channel usable at all.

Four mechanisms, in order of how much they assume:

    precision bar        confirmed / (confirmed + refuted), from RECORDED outcomes    D0 ratio
    minimum sample       below it, no verdict at all — 1 of 1 is not 100%             declared
    cooldown             a rule refuted recently does not re-fire immediately         declared
    near-duplicate       the same root cause under a different rule id                D0 fingerprint

**Muting is loud.** A generator below the bar is muted, and its findings still appear — in a
`muted` list, with the precision that muted them. A signal that vanishes silently is worse than a
noisy one, because the noise at least tells you it is there. Muting is also reversible by its own
carrier: one confirmed finding moves the ratio back.

The determinism split, as everywhere: the **ratio** is `D0` — a count of outcomes somebody actually
recorded. The **verdict** built from a bar and a cooldown nobody measured is `D1`, reproducible from
the pinned policy and no further. They are reported apart.

Stdlib-only.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterable, Optional

#: Declared hypotheses, pinned in the artifact they grade (see `doccatalog` for the same pattern):
#: nobody measured these, and hiding them as module constants would let them read as findings.
DEFAULT_POLICY = {
    "hypothesis": True,
    "why": "no measurement backs these; tune them against observed refutation rates",
    # below this precision a generator is muted...
    "precision_bar": 0.5,
    # ...but never before this many judged findings. 1-of-1 is not 100%, it is one data point.
    "min_sample": 4,
    # a refuted rule sits out this many runs before it may fire again
    "cooldown_runs": 2,
}

OUTCOMES = ("confirmed", "refuted", "pending")


def new_registry(policy: Optional[dict] = None) -> dict:
    return {"version": "1", "policy": dict(policy or DEFAULT_POLICY), "runs": 0, "generators": {}}


def load(path: str | pathlib.Path) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        return new_registry()
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("policy", dict(DEFAULT_POLICY))
    data.setdefault("generators", {})
    data.setdefault("runs", 0)
    return data


def save(registry: dict, path: str | pathlib.Path) -> None:
    pathlib.Path(path).write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def _rec(registry: dict, generator: str) -> dict:
    return registry["generators"].setdefault(generator, {
        "surfaced": 0, "confirmed": 0, "refuted": 0, "last_refuted_run": None, "muted": False,
    })


def observe(registry: dict, generator: str, outcome: str) -> dict:
    """Record what a human (or the reviewer) concluded about one of this generator's findings.

    `refuted` is the honest word and it matters: a finding the operator looked at and rejected is
    evidence about the *rule*, not about that one file. This is the only input the precision ratio
    has, which is why it is recorded explicitly rather than inferred from silence — treating
    "nobody complained" as confirmation is exactly the self-certifying loop this package rejects.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    rec = _rec(registry, generator)
    rec["surfaced"] += 1
    if outcome == "confirmed":
        rec["confirmed"] += 1
    elif outcome == "refuted":
        rec["refuted"] += 1
        rec["last_refuted_run"] = registry.get("runs", 0)
    rec["muted"] = _verdict(registry, generator)["verdict"] == "muted"
    return rec


def precision(registry: dict, generator: str) -> Optional[float]:
    """confirmed / judged, or None below the minimum sample. `None` is the honest answer to
    "how good is this rule" after two findings — not a provisional number that will be quoted."""
    rec = _rec(registry, generator)
    judged = rec["confirmed"] + rec["refuted"]
    if judged < registry.get("policy", DEFAULT_POLICY).get("min_sample", 4):
        return None
    return round(rec["confirmed"] / judged, 3)


def _verdict(registry: dict, generator: str) -> dict:
    policy = registry.get("policy", DEFAULT_POLICY)
    rec = _rec(registry, generator)
    p = precision(registry, generator)
    if p is None:
        return {"verdict": "unproven", "precision": None,
                "why": f"fewer than {policy.get('min_sample', 4)} judged findings — no verdict"}
    if p < policy.get("precision_bar", 0.5):
        return {"verdict": "muted", "precision": p,
                "why": f"precision {p} is below the declared bar "
                       f"{policy.get('precision_bar', 0.5)} over {rec['confirmed'] + rec['refuted']} "
                       "judged findings"}
    return {"verdict": "trusted", "precision": p, "why": "at or above the declared bar"}


def cooling_down(registry: dict, generator: str) -> bool:
    policy = registry.get("policy", DEFAULT_POLICY)
    rec = _rec(registry, generator)
    last = rec.get("last_refuted_run")
    if last is None:
        return False
    return (registry.get("runs", 0) - last) < policy.get("cooldown_runs", 2)


def _root_fingerprint(f: dict) -> str:
    """The same root cause under a different rule id. Deliberately coarse — file plus message shape,
    not rule id — because near-duplicates across rules are exactly what a rule-keyed merge misses."""
    msg = " ".join(str(f.get("message", "")).split())[:60].lower()
    return f"{f.get('file', '')}|{msg}"


def screen(registry: dict, findings: Iterable[dict]) -> dict:
    """Route a gated findings stream by generator health. Nothing is deleted, only routed.

    Returns `surfaced` (report normally), `muted` (report quietly, with the precision that muted
    them), `cooling` (a recently-refuted rule sitting out), and `near_duplicates` (a root cause
    already represented under another rule id this run).
    """
    surfaced, muted, cooling, dupes = [], [], [], []
    seen: dict[str, str] = {}
    for f in findings:
        gen = f.get("generator") or f"{f.get('tool', '?')}:{f.get('rule_id', '?')}"
        fp = _root_fingerprint(f)
        if fp in seen and seen[fp] != gen:
            dupes.append({**f, "generator": gen, "duplicate_of_generator": seen[fp]})
            continue
        seen.setdefault(fp, gen)
        v = _verdict(registry, gen)
        if v["verdict"] == "muted":
            muted.append({**f, "generator": gen, **v})
        elif cooling_down(registry, gen):
            cooling.append({**f, "generator": gen,
                            "why": "this rule was refuted recently and is in cooldown"})
        else:
            surfaced.append({**f, "generator": gen, **v})
    return {
        "surfaced": surfaced,
        "muted": muted,
        "cooling": cooling,
        "near_duplicates": dupes,
        "ratio_determinism": "D0",
        "verdict_determinism": "D1",
        "policy": registry.get("policy", DEFAULT_POLICY),
        "note": ("Nothing was deleted. A muted generator's findings are still listed, with the "
                 "precision that muted them — a signal that vanishes silently is worse than a "
                 "noisy one. Muting reverses itself: one confirmed finding moves the ratio."),
    }


def health(registry: dict) -> dict:
    """Every generator's standing — the report that makes muting arguable instead of mysterious."""
    rows = []
    for gen in sorted(registry.get("generators", {})):
        rec = registry["generators"][gen]
        rows.append({"generator": gen, **_verdict(registry, gen),
                     "surfaced": rec["surfaced"], "confirmed": rec["confirmed"],
                     "refuted": rec["refuted"], "cooling_down": cooling_down(registry, gen)})
    return {"runs": registry.get("runs", 0), "generators": rows,
            "policy_is_hypothesis": bool(registry.get("policy", {}).get("hypothesis", True))}
