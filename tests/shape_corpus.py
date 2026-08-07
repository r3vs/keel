"""The broken-record corpus, DERIVED from the schema rather than remembered.

**Why this file exists, in one sentence: when the gate is a corpus, the corpus is the weak link.**

The read path had three parts held to each other by construction — `PIN_RULES` ↔ `pin_read` by set
equality, `LEDGER_COLLECTIONS` driving an AST gate, `nonconforming` replaying the rule table — and
all three ran against a HAND-WRITTEN list of seven broken pins, copied into two test modules with a
comment saying the principle was one. A reviewer extended that list in a scratch copy of HEAD with
eleven more shapes, every one of them naming a field `PIN_FIELDS` already declared, and the
unchanged gates went red: `verification: "observed"` and `brainstorm: {"proposals": "opt_a"}` both
killed `interview_next` over real stdio. **The gates proved what somebody had thought to write
down**, which is a strictly weaker claim than the one they were making.

So nothing here is a list of shapes. `ledger.PIN_SHAPES` and `ledger.POLICY_SHAPES` declare what
each path must be; this module turns each declaration into every way it can be violated, by probing
the declared shape against a fixed set of values and keeping the ones it refuses. A path added to
the schema tomorrow arrives in every gate that imports this, with no one remembering.

Not a `test_*.py` module on purpose — `unittest discover` collects those, and this holds no tests.
"""
from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

from ledger import (LEDGER_COLLECTIONS, LOG_ENTRY_PREFIXES, PIN_SHAPES,  # noqa: E402
                    POLICY_SHAPES, SHAPE_HOLDS, PIN_STRONGER, POLICY_STRONGER)

#: The values every declared path is probed with. One per JSON type a hand-edited ledger can put
#: there, plus the two list flavours, so that for any shape in the vocabulary at least one probe is
#: refused — asserted in `tests/test_ledger.py`, because a probe set that happens to satisfy a new
#: shape would make that path's corpus silently empty, which is this file's own subject.
PROBES = (
    ("a string", "observed"),
    ("a number", 7),
    ("a bare list", ["a", "b"]),
    ("a list of objects", [{"id": "x"}]),
    ("an object", {"rung": "observed"}),
    ("a boolean", True),
)

#: A pin every rule accepts, as the thing each malformation is a mutation OF. Written out rather
#: than built with `add_pin`, because the corpus is about files this runtime did NOT write.
GOOD_PIN = {
    "id": "pin_0009", "kind": "contract_mismatch", "title": "the corpus pin",
    "severity": "medium", "confidence": "extracted", "state": "needs_input",
    "provenance": [{"source": "recon", "detail": "x"}], "anchors": [],
    "as_is": None, "to_be": None,
    "question": {"prompt": "which side wins?",
                 "options": [{"id": "db", "label": "the DB"}, {"id": "api", "label": "the API"}]},
    "brainstorm": None, "decision": None, "depends_on": [], "remediation": [],
}

GOOD_POLICY = {"id": "pol_0009", "rule": "the DB wins on nullability",
               "applies_to": {"kind": "contract_mismatch"}, "default_outcome": "db",
               "evidence": "transcribed", "human_answer": "the DB wins"}


def _set_at(record: dict, path: str, value) -> None:
    node = record
    steps = path.split(".")
    for step in steps[:-1]:
        if not isinstance(node.get(step), dict):
            node[step] = {}
        node = node[step]
    node[steps[-1]] = value


def _drop_at(record: dict, path: str) -> None:
    node = record
    steps = path.split(".")
    for step in steps[:-1]:
        node = node.get(step)
        if not isinstance(node, dict):
            return
    node.pop(steps[-1], None)


def _corpus(shapes: dict, stronger: dict, good: dict, kindname: str) -> list:
    """`(label, record)` for every way a declared path of `shapes` can be violated."""
    out = []
    for path, shape in shapes.items():
        for probe_label, probe in PROBES:
            if SHAPE_HOLDS[shape](probe):
                continue                      # not a violation of THIS path; a different one's job
            record = copy.deepcopy(good)
            _set_at(record, path, probe)
            out.append((f"{kindname}.{path} is {probe_label} (declared {shape})", record))
        # A path whose rule is STRONGER than its shape is also violated by absence — `id`, `state`
        # and `severity` are required, and "missing" is exactly how the first six reproductions of
        # this class arrived.
        if path in stronger:
            record = copy.deepcopy(good)
            _drop_at(record, path)
            out.append((f"{kindname}.{path} is absent (required)", record))
            record = copy.deepcopy(good)
            _set_at(record, path, None)
            out.append((f"{kindname}.{path} is null (required)", record))
    return out


def broken_pins() -> list:
    """`(label, pin)` for every violation `PIN_SHAPES` can describe. ~100 shapes, none listed."""
    return _corpus(PIN_SHAPES, PIN_STRONGER, GOOD_PIN, "pin")


def broken_policies() -> list:
    """`(label, policy)` for every violation `POLICY_SHAPES` can describe."""
    return _corpus(POLICY_SHAPES, POLICY_STRONGER, GOOD_POLICY, "policy")


#: The fields a reader dispatches on AFTER the kind — every branch of `summary`'s log loop and of
#: `learning.divergences` indexes one of these. Not a shape table: the rule about a log entry is
#: that **every read of it is a `.get`, the dispatch key most of all** (v0.18), so what the corpus
#: has to produce is an entry MISSING each of them, per kind.
EVENT_DISPATCH_FIELDS = ("id", "pin_id", "class", "upheld", "fired", "reason", "phase", "detail",
                         "door", "settles_as", "evidence")


def broken_events() -> list:
    """`(label, decision_log entry)` for every kind of log entry, stripped to nothing.

    DERIVED from `LOG_ENTRY_PREFIXES`, which is the schema the dispatch rule is about — a reader
    branches on the prefix and then indexes. The corpus that caught the pin half could not see this
    one at all: it built well-formed logs, so `learning.divergences`' `e["id"].startswith(...)` —
    the exact expression v0.18 removed from `summary()` — survived a plant of its own reversal.

    `upheld: True` on the `chl_` entries because that branch is guarded by it, and an entry the
    branch never enters proves nothing about what the branch does.
    """
    out = [("a log entry with no id at all", {"pin_id": "pin_0001", "outcome": "db"}),
           ("a log entry whose id is a number", {"id": 7, "pin_id": "pin_0001"}),
           ("a log entry whose id is a list", {"id": ["ev_0001"], "pin_id": "pin_0001"})]
    for prefix in LOG_ENTRY_PREFIXES:
        out.append((f"a bare `{prefix}` entry, every other field absent", {"id": f"{prefix}0001"}))
        out.append((f"a bare `{prefix}` entry that a guarded branch enters",
                    {"id": f"{prefix}0001", "upheld": True}))
        for field in EVENT_DISPATCH_FIELDS:
            if field == "id":
                continue
            entry = {"id": f"{prefix}0001", "upheld": True, field: ["not a scalar"]}
            out.append((f"`{prefix}` entry whose `{field}` is a list", entry))
    return out


def broken_ledgers(base: dict) -> list:
    """`(label, ledger data)` for the malformations that are about the FILE rather than a record.

    The container half, derived from `LEDGER_COLLECTIONS` the way the record half is derived from
    the shape tables — plus the top level itself, which is the one nothing covered: a ledger whose
    root is a list or a string killed all four surfaces with a raw `AttributeError`, because
    `Ledger.__init__` reached `self.data.get("version")` before any guard ran.
    """
    out = [("the whole file is a list", ["nope"]),
           ("the whole file is a string", "nope"),
           ("the whole file is a number", 7)]
    for name in LEDGER_COLLECTIONS:
        for probe_label, probe in PROBES:
            if isinstance(probe, list):
                continue                      # a list is what the collection is supposed to be
            data = copy.deepcopy(base)
            data[name] = probe
            out.append((f"{name} is {probe_label}", data))
        data = copy.deepcopy(base)
        data.pop(name, None)
        out.append((f"{name} is absent", data))
        data = copy.deepcopy(base)
        data.setdefault(name, []).append("a bare string where a record goes")
        out.append((f"{name} carries a non-object entry", data))
    return out


def worst_ledger() -> dict:
    """Every malformation this module can describe, in ONE file.

    What a reviewer builds to open in a browser: each declared path broken on its own pin, so the
    per-record report on the map has something to say about every card, and the file-level report
    has every rule in it.
    """
    def renumber(record, path, prefix, index):
        """A unique id, EXCEPT where the case is about the id — found in the browser: assigning one
        unconditionally repaired the six `pin.id` malformations, so the worst file was quietly less
        bad than the corpus it was built from, and the map's per-record report had nothing to say
        about the pins whose fault is that they cannot be named."""
        if SHAPE_HOLDS["str"](record.get(path)) and record.get(path):
            record[path] = f"{prefix}{index:04d}"
        return record

    pins = []
    for index, (label, pin) in enumerate(broken_pins(), start=1):
        pin = renumber(copy.deepcopy(pin), "id", "pin_", index)
        if SHAPE_HOLDS["str"](pin.get("title")):
            pin["title"] = label
        pins.append(pin)
    policies = []
    for index, (label, policy) in enumerate(broken_policies(), start=1):
        policies.append(renumber(copy.deepcopy(policy), "id", "pol_", index))
    pins.append("a bare string where a pin goes")
    policies.append("a bare string where a policy goes")
    return {
        "version": "0.24",
        "pins": pins,
        "decision_log": [
            {"pin_id": "pin_0001", "outcome": "db"},               # no id: dispatched by nothing
            {"id": "ev_0001", "pin_id": "pin_0001", "outcome": "db", "source": "interview",
             "evidence": "transcribed"},                           # no flip_criteria, no quote
            "a bare string where an event goes",
        ],
        "policies": policies,
    }
