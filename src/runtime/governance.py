"""Governance fingerprint — which rules were in force when a decision was taken.

An append-only decision log answers *what* was decided and *why*. It has never answered a third
question that matters just as much when something goes wrong: **under which rules?** Between two
decisions the agent roster can change, a permission can widen, the ledger schema can gain a state,
and the skill's own prose can be edited. A trail that cannot show that is a trail that will one day
be read wrongly with total confidence.

So every event carries a `policy_hash` over the governing inputs, stamped **before the outcome takes
effect** — and a permission change becomes a visible hash delta in the log rather than an invisible
change of meaning. The hash is not a security device; it is a *join key*. Its job is to make "these
two decisions were taken under different rules" answerable at all.

**Absence is recorded, not implied.** A ledger with no governance record stamps `policy_hash: null`
explicitly, so ungoverned reads as ungoverned. A missing field would read as fine.

Second job, same carrier: **stale-skill detection at runtime.** `build.py --check` verifies the
shipped bytes at *build* time; once installed, nobody checks anything, and a hand-edited `SKILL.md`
diverges from the doctrine it claims to implement with no signal at all. `verify_skills` recomputes
the hashes and reports drift — it warns and downgrades confidence rather than refusing, because a
user editing their own installed copy is legitimate and blocking them would be worse than telling
them.

Stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Iterable, Optional


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _hash_file(path: str | pathlib.Path) -> Optional[str]:
    try:
        return _hash_bytes(pathlib.Path(path).read_bytes())
    except OSError:
        return None


def fingerprint(inputs: dict) -> dict:
    """A stable hash over the governing inputs, plus the per-input hashes that produced it.

    The components are stored beside the hash on purpose. A bare digest tells you two decisions
    differ; the components tell you *which rule* changed, which is the only form of the answer
    anybody can act on.
    """
    parts = {}
    for name in sorted(inputs):
        value = inputs[name]
        if value is None:
            parts[name] = None
        elif isinstance(value, (str, int, float)) and not str(value).endswith(".md"):
            parts[name] = _hash_bytes(str(value).encode("utf-8"))
        else:
            parts[name] = _hash_file(str(value))
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"policy_hash": _hash_bytes(payload), "components": parts,
            "missing": sorted(k for k, v in parts.items() if v is None)}


def record(roster: str = "", spec_version: str = "", skill_version: str = "",
           permissions: str = "", extra: Optional[dict] = None) -> dict:
    """Build the governance record a ledger stamps onto every event.

    `roster` and `permissions` are paths (typically the same `core/agents.md`, which is the single
    source of truth for both); `spec_version` and `skill_version` are literals. Anything unresolvable
    lands in `missing` rather than being dropped — a fingerprint over three of four inputs is not a
    smaller fingerprint, it is a misleading one.
    """
    inputs = {
        "roster": roster or None,
        "permissions": permissions or roster or None,
        "spec_version": spec_version or None,
        "skill_version": skill_version or None,
    }
    inputs.update(extra or {})
    return fingerprint(inputs)


def pin_skills(skill_dirs: Iterable[str]) -> dict:
    """Pin the current hash of every `SKILL.md` — the baseline `verify_skills` compares against."""
    pinned = {}
    for d in skill_dirs:
        p = pathlib.Path(d) / "SKILL.md"
        h = _hash_file(p)
        if h:
            pinned[pathlib.Path(d).name] = h
    return pinned


def verify_skills(pinned: dict, skill_dirs: Iterable[str]) -> dict:
    """Recompute and compare. Reports `drifted` / `missing` / `unpinned`; never raises.

    Deliberately a warning, not a refusal. `build.py --check` is the hard gate for *our* bytes at
    build time; this runs on an *installed* copy, where a user editing their own skill is legitimate.
    What is not legitimate is a skill quietly claiming a doctrine it no longer contains — so the
    result downgrades confidence in that skill's output and says which file to look at.
    """
    current = pin_skills(skill_dirs)
    drifted = sorted(k for k, v in current.items() if k in pinned and pinned[k] != v)
    missing = sorted(k for k in pinned if k not in current)
    unpinned = sorted(k for k in current if k not in pinned)
    return {
        "ok": not (drifted or missing),
        "drifted": drifted,
        "missing": missing,
        "unpinned": unpinned,
        "confidence": "downgraded" if drifted else "unchanged",
        "note": ("A drifted SKILL.md no longer matches the doctrine it was built from. Treat that "
                 "skill's output as inferred rather than extracted until it is rebuilt or "
                 "re-pinned." if drifted else "every pinned skill matches its shipped bytes"),
    }
