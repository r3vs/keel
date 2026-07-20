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

_DONE_STATES = ("resolved", "accepted")


def _actionable(pin: dict) -> bool:
    """A pin carries Phase-4 work if it is decided (or a defect) and not yet resolved."""
    if pin["state"] in _DONE_STATES:
        return False
    return pin["state"] == "decided" or pin["kind"] == "defect"


def _items_done(pin: dict) -> bool:
    items = pin.get("remediation", [])
    return bool(items) and all(i["status"] == "done" for i in items)


def waves(ledger) -> list[list[str]]:
    """Topologically level every pin by `depends_on`: wave 0 has no unmet deps, wave N depends only
    on ≤N-1. Raises ValueError on a dependency cycle (the DAG invariant the roadmap rests on)."""
    pins = {p["id"]: p for p in ledger.data["pins"]}
    level: dict[str, int] = {}

    def depth(pid: str, stack: frozenset) -> int:
        if pid in level:
            return level[pid]
        if pid in stack:
            raise ValueError(f"dependency cycle through {pid}")
        deps = [d for d in pins[pid].get("depends_on", []) if d in pins]
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
    by_id = {p["id"]: p for p in ledger.data["pins"]}
    return all(by_id[d]["state"] in _DONE_STATES
               for d in pin.get("depends_on", []) if d in by_id)


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
        for item in pin.get("remediation", []):
            if item["status"] != "done":
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
            if seen_blocked > len(ledger.data["pins"]):
                return   # caller isn't closing anything — stop rather than spin
        else:
            seen_blocked = 0


def _open_count(ledger) -> int:
    return sum(1 for p in ledger.data["pins"] if _actionable(p))


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


def plan(ledger) -> dict:
    """A renderable summary of the Phase-4 plan: the waves, and what is ready right now."""
    wv = waves(ledger)
    return {"waves": [[ledger.pin(pid)["title"] for pid in w] for w in wv],
            "wave_count": len(wv),
            "ready_now": [p["title"] for p in ready(ledger)],
            "open": _open_count(ledger)}


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Show the Phase-4 wave plan for a ledger")
    parser.add_argument("ledger")
    args = parser.parse_args(argv)
    from ledger import Ledger
    led = Ledger(args.ledger)
    p = plan(led)
    print(f"{p['wave_count']} wave(s), {p['open']} open item(s)")
    for i, w in enumerate(p["waves"]):
        print(f"  wave {i}: " + ", ".join(w))
    print("ready now: " + (", ".join(p["ready_now"]) or "—"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
