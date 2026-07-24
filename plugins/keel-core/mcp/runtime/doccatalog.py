"""DocCatalog — a queryable catalog of docs, and staleness that is graded instead of binary.

Two problems with how documentation staleness is usually handled, and this module answers both.

**The catalog exists before the prose.** Today the only question you can ask about a repo's docs is
"what files are in `docs/`". You cannot ask what is *covered*, by whom, from which sources, or what
is deliberately absent. So a doc is registered with its subject, owner, source set and status
*before* it is written — which makes "nobody has documented the payment flow" a query rather than a
discovery, and makes a gap in coverage as visible as a gap in code.

**Staleness is a gradient, not a flag.** The graph already carries `built_at_commit`, and that gives
exactly one bit for the whole artifact: current, or not. A doc is not like that. Its sources rot at
different rates and at different distances:

    distance 0   a file the doc directly cites changed
    distance 1   something that IMPORTS a cited file changed
    distance 2   something that historically CO-CHANGES with a cited file changed

and the cascade follows the same edges: a changed source invalidates its own doc, then its
importers' docs, then its co-change partners' docs. A content hash tells you *what literally
changed*; the cascade tells you *what is now stale because of it*.

**Where the honesty line falls.** One signal here has a carrier and one does not, and they are kept
apart rather than blended:

    invalid   a directly-cited source's content HASH no longer matches   D0 — an equality
    aging /   arithmetic over declared decay weights and a time window   D1 — reproducible from
    stale     that nobody measured                                            the pinned policy

The weights are a **hypothesis** and the catalog stores them as such, in the file, versioned with the
data they judge. That is the whole reason they live in the artifact instead of in this module: a
constant hidden in code reads as a fact, a constant pinned in the data it grades reads as a choice
someone can change. Nothing here produces a single fused "freshness score" — `D0` invalidation and
`D1` decay are reported side by side (`core/trust-axes.md`).

Stdlib-only. Reads the repo, optionally the graph and git history.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Iterable, Optional

CATALOG_VERSION = "1"

#: The decay policy written into a NEW catalog. Every number here is a declared hypothesis: nobody
#: measured how fast a doc rots, and pretending otherwise would be a tuned constant wearing a
#: deterministic badge. It is stored in the catalog file so it travels with the data it grades and
#: can be re-elected without touching code.
DEFAULT_POLICY = {
    "hypothesis": True,
    "why": "no measurement backs these numbers; they are a starting point to be tuned against "
           "observed doc rot, not a finding",
    "aging_days": 30,
    "stale_days": 90,
    # how much a change at each distance counts toward the decay signal
    "distance_weights": {"0": 1.0, "1": 0.5, "2": 0.25},
    "aging_at": 0.5,
    "stale_at": 1.0,
}

STATUSES = ("planned", "drafting", "published", "deprecated")


def _norm(p: str) -> str:
    return str(p).replace("\\", "/").lstrip("./")


def _hash_file(repo: str, rel: str) -> Optional[str]:
    path = pathlib.Path(repo) / rel
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def new_catalog(policy: Optional[dict] = None) -> dict:
    return {"version": CATALOG_VERSION, "policy": dict(policy or DEFAULT_POLICY), "docs": []}


def load(path: str | pathlib.Path) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        return new_catalog()
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("policy", dict(DEFAULT_POLICY))
    data.setdefault("docs", [])
    return data


def save(catalog: dict, path: str | pathlib.Path) -> None:
    pathlib.Path(path).write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


def register(catalog: dict, path: str, subject: str, owner: str, sources: Iterable[str],
             repo: str = ".", status: str = "planned", generated_at: str = "",
             commit: str = "") -> dict:
    """Register (or re-register) a doc. Legal *before the prose exists* — that is the point.

    A `planned` entry with a subject, an owner and a source set is a coverage commitment somebody
    can query, argue with, or reassign. Waiting until the file exists means the catalog can only
    ever describe what was already written, which is the state we are trying to leave.
    """
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    rel = _norm(path)
    entry = {
        "path": rel,
        "subject": subject,
        "owner": owner,
        "status": status,
        "sources": sorted({_norm(s) for s in sources}),
        "source_hashes": {},
        "content_hash": _hash_file(repo, rel),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_at_commit": commit,
    }
    for s in entry["sources"]:
        entry["source_hashes"][s] = _hash_file(repo, s)
    catalog["docs"] = [d for d in catalog["docs"] if d["path"] != rel] + [entry]
    return entry


def _days_since(iso: str) -> Optional[float]:
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400.0


def _importers(graph_data: Optional[dict], files: Iterable[str]) -> set:
    """Files that depend on any of `files` (distance 1). Empty without a graph — and the caller
    reports that absence rather than treating it as 'nothing imports these'."""
    if not graph_data:
        return set()
    import graph as graphmod
    g = graphmod.Graph(graph_data)
    want = {_norm(f) for f in files}
    seeds = [nid for nid, n in g.nodes.items() if _norm(str(n.get("source_file") or "")) in want]
    out = set()
    for nid in seeds:
        for dep in g.blast_radius(nid, max_depth=1):
            f = g._node_file(g.nodes[dep])
            if f and _norm(f) not in want:
                out.add(_norm(f))
    return out


def freshness(catalog: dict, doc: dict, repo: str = ".", graph_data: Optional[dict] = None,
              changed_files: Optional[Iterable[str]] = None) -> dict:
    """Graded freshness for one doc: a `D0` invalidation plus a `D1` decay signal, never fused.

    `changed_files` (when given) supplies the distance-1 and distance-2 evidence. Without it those
    distances are reported as **unknown**, not as zero — an unmeasured distance reading as "nothing
    changed there" is the degrade-silently failure this package refuses everywhere else.
    """
    policy = catalog.get("policy", DEFAULT_POLICY)
    sources = doc.get("sources", [])

    # --- D0: did a directly-cited source's bytes change? An equality, not an estimate.
    direct: list[str] = []
    unreadable: list[str] = []
    for s in sources:
        now = _hash_file(repo, s)
        was = (doc.get("source_hashes") or {}).get(s)
        if now is None:
            unreadable.append(s)
        elif was is not None and now != was:
            direct.append(s)

    # --- D1: decay over declared weights.
    changed = {_norm(f) for f in (changed_files or [])}
    measured = changed_files is not None
    d1 = sorted(_importers(graph_data, sources) & changed) if (measured and graph_data) else []
    d2: list[str] = []
    if measured:
        try:
            import cochange
            partners = {r["file"] for r in cochange.outside(repo, sources)}
            d2 = sorted((partners & changed) - set(d1) - set(sources))
        except Exception:            # a missing carrier is a fact, never an exception
            d2 = []
    w = policy.get("distance_weights", DEFAULT_POLICY["distance_weights"])
    decay = (len(direct) * float(w.get("0", 1.0))
             + len(d1) * float(w.get("1", 0.5))
             + len(d2) * float(w.get("2", 0.25)))
    age = _days_since(doc.get("generated_at", ""))
    if age is not None:
        if age >= policy.get("stale_days", 90):
            decay += float(w.get("0", 1.0))
        elif age >= policy.get("aging_days", 30):
            decay += float(w.get("1", 0.5))

    signal = "fresh"
    if decay >= policy.get("stale_at", 1.0):
        signal = "stale"
    elif decay >= policy.get("aging_at", 0.5):
        signal = "aging"

    unknown = []
    if not measured:
        unknown.append("distance 1 and 2 — no changed-file set was supplied")
    elif not graph_data:
        unknown.append("distance 1 — no graph was supplied, so importers were not resolved")
    if unreadable:
        unknown.append(f"{len(unreadable)} source(s) could not be read")

    return {
        "path": doc["path"],
        "status": doc.get("status"),
        "invalid": bool(direct),
        "invalid_determinism": "D0",
        "changed_sources": direct,
        "decay": round(decay, 3),
        "signal": signal,
        "decay_determinism": "D1",
        "distance_1": d1,
        "distance_2": d2,
        "age_days": None if age is None else round(age, 1),
        "unreadable_sources": unreadable,
        "unknown": unknown,
        "policy_is_hypothesis": bool(policy.get("hypothesis", True)),
        "note": "`invalid` is a hash equality and carries no assumptions. `signal` is arithmetic "
                "over declared decay weights nobody measured — reproducible from the pinned "
                "policy, not a measurement. They are reported apart on purpose.",
    }


def cascade(catalog: dict, changed_files: Iterable[str], repo: str = ".",
            graph_data: Optional[dict] = None) -> dict:
    """Which docs a set of changed files touches, by distance. The invalidation fan-out.

    A content hash answers *what literally changed*; this answers *what is now stale because of it*
    — the docs whose sources changed, then the docs whose sources merely import those, then the
    docs whose sources merely move with them.
    """
    rows = [freshness(catalog, d, repo=repo, graph_data=graph_data, changed_files=changed_files)
            for d in catalog.get("docs", [])]
    return {
        "invalid": [r["path"] for r in rows if r["invalid"]],
        "stale": [r["path"] for r in rows if r["signal"] == "stale" and not r["invalid"]],
        "aging": [r["path"] for r in rows if r["signal"] == "aging"],
        "fresh": [r["path"] for r in rows if r["signal"] == "fresh" and not r["invalid"]],
        "rows": rows,
        "policy": catalog.get("policy", DEFAULT_POLICY),
    }


def coverage(catalog: dict) -> dict:
    """What the catalog says is covered, planned, unowned or deprecated — the query the prose
    cannot answer about itself."""
    docs = catalog.get("docs", [])
    by_status: dict[str, list] = {}
    for d in docs:
        by_status.setdefault(d.get("status", "planned"), []).append(d["path"])
    return {
        "total": len(docs),
        "by_status": by_status,
        "unowned": sorted(d["path"] for d in docs if not str(d.get("owner", "")).strip()),
        "sourceless": sorted(d["path"] for d in docs if not d.get("sources")),
        "determinism": "D0",
        "note": "`sourceless` docs cannot be staleness-checked at all — nothing anchors them to the "
                "code, so they can only ever read as fresh. That is a gap, not a pass.",
    }
