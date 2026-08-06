"""Wave scheduler for the Phase-4 loop — the mechanizable half of the remediation/build harness.

Both skills run a restartable, per-item Phase-4 loop: rescue closes `RemediationItem`s, greenfield
builds `BuildItem`s, each in a fresh agent invocation doing two-track TDD, with wave checkpoints
between dependency levels (`references/phase-4-remediation.md`, `references/phase-4-build.md`). The
*agent* part (write the code, run the tests, review) cannot be a script. The *harness* part — what
order to work in, what is ready now, when a wave is complete — is pure DAG scheduling over the
ledger's `depends_on`, and that is this module.

"Contracts before logic" (rescue) and "contract & data model → paved road → slice → polish"
(greenfield) are not hardcoded orders: they fall out of the dependency graph. `waves()` levels the
DAG topologically; `ready()` yields the pins whose dependencies are all closed and whose own work
is unfinished; `checkpoint()` reports whether a wave is fully done (the gate before the next wave).
Restartability is free because the ledger is the state: re-run after a crash and `ready()` returns
exactly what is left. Stdlib-only.
"""
from __future__ import annotations

from typing import Iterator, Optional

from ledger import pin_read

_DONE_STATES = ("resolved", "accepted")


def _actionable(pin: dict) -> bool:
    """A pin carries Phase-4 work if it is decided (or a defect) and not yet resolved.

    Through `pin_read` (v0.22): `mcp:build_waves` is a READ-ONLY tool taking nothing but a ledger
    path, so it is under the same rule `summary` and `policy_preview` are — reading a ledger is
    never the operation that fails on it. It was one of three the derived gate caught
    (`tests/test_mcp_tools.py::TestNoReadOnlyLedgerToolDiesOnAPinShape`), and it was the registered
    §20 residual: *these are not among the four reading surfaces, but it is the same class*.
    """
    read = pin_read(pin)
    if read["state"] in _DONE_STATES:
        return False
    return read["state"] == "decided" or pin.get("kind") == "defect"


def _items_done(pin: dict) -> bool:
    items = pin.get("remediation")
    items = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    return bool(items) and all(i.get("status") == "done" for i in items)


def waves(ledger) -> list[list[str]]:
    """Topologically level every pin by `depends_on`: wave 0 has no unmet deps, wave N depends only
    on ≤N-1. Raises ValueError on a dependency cycle (the DAG invariant the roadmap rests on)."""
    pins = {pin_read(p)["id"]: p for p in ledger.readable_pins()}
    level: dict[str, int] = {}

    def depth(pid: str, stack: frozenset) -> int:
        if pid in level:
            return level[pid]
        if pid in stack:
            raise ValueError(f"dependency cycle through {pid}")
        deps = [d for d in pin_read(pins[pid])["depends_on"] if d in pins]
        d = 0 if not deps else 1 + max(depth(x, stack | {pid}) for x in deps)
        level[pid] = d
        return d

    for pid in pins:
        depth(pid, frozenset())
    out: list[list[str]] = [[] for _ in range(max(level.values(), default=-1) + 1)]
    for pid, lv in sorted(level.items()):
        out[lv].append(pid)
    return out


def _deps_closed(ledger, pin: dict) -> bool:
    by_id = {pin_read(p)["id"]: p for p in ledger.readable_pins()}
    return all(pin_read(by_id[d])["state"] in _DONE_STATES
               for d in pin_read(pin)["depends_on"] if d in by_id)


def ready(ledger) -> list[dict]:
    """Pins actionable now: their dependencies are all closed and their own work is unfinished.
    This is what a fresh Phase-4 invocation pulls from — order stable, restart-safe."""
    out = []
    for wave in waves(ledger):
        for pid in wave:
            pin = ledger.pin(pid)
            if _actionable(pin) and _deps_closed(ledger, pin) and not _items_done(pin):
                out.append(pin)
    return out


def next_item(ledger) -> Optional[tuple]:
    """The single next (pin, remediation_item) to work — the first todo item on the first ready
    pin. Returns None when nothing is ready (loop done, or blocked on upstream waves)."""
    for pin in ready(ledger):
        for item in (pin.get("remediation") or []):
            if not isinstance(item, dict) or item.get("status") != "done":
                return pin, item
        # a ready pin with no items yet is itself the next unit of work (needs items planned)
        return pin, None
    return None


def iter_ready(ledger) -> Iterator[dict]:
    """Yield ready pins until none remain — re-evaluated each step so newly-unblocked pins appear
    as their dependencies close. Caller must actually resolve items or this never terminates."""
    seen_blocked = 0
    while True:
        r = ready(ledger)
        if not r:
            return
        before = _open_count(ledger)
        yield r[0]
        if _open_count(ledger) == before:
            seen_blocked += 1
            if seen_blocked > len(ledger.readable_pins()):
                return   # caller isn't closing anything — stop rather than spin
        else:
            seen_blocked = 0


def _open_count(ledger) -> int:
    return sum(1 for p in ledger.readable_pins() if _actionable(p))


def checkpoint(ledger, wave_index: int) -> dict:
    """Wave-checkpoint gate: is every actionable pin in wave `wave_index` resolved? The loop does
    not advance to wave N+1 until wave N passes (where the challenger + reviewer also run)."""
    wv = waves(ledger)
    if wave_index >= len(wv):
        return {"wave": wave_index, "exists": False, "complete": True, "pending": []}
    pending = [pid for pid in wv[wave_index]
               if _actionable(ledger.pin(pid)) and not _items_done(ledger.pin(pid))]
    return {"wave": wave_index, "exists": True, "complete": not pending,
            "pending": pending, "size": len(wv[wave_index])}


def _label(pin: dict) -> str:
    return str(pin.get("title") or pin_read(pin)["id"])


def plan(ledger) -> dict:
    """A renderable summary of the Phase-4 plan: the waves, and what is ready right now."""
    wv = waves(ledger)
    # `title` is prose for a human and is not one of `pin_read`'s five, so absence falls back to
    # the id: a wave listing with a blank row names nothing, which is worse than naming the pin.
    return {"waves": [[_label(ledger.pin(pid)) for pid in w] for w in wv],
            "wave_count": len(wv),
            "ready_now": [_label(p) for p in ready(ledger)],
            "open": _open_count(ledger)}
