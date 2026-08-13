#!/usr/bin/env python3
"""Render the two MCP Apps' SERVED documents to a directory, for `mcp-apps.ts` beside this file.

Why a Python file inside a `__tests__/` directory full of TypeScript
--------------------------------------------------------------------
The documents are Python's to produce and JavaScript's to check, and the split has to happen
somewhere. It happens here rather than inside the node file as an embedded here-doc, because a
program pasted into a string literal is a program no linter reads: `ruff check .` covers this file
and covers nothing that lives inside a template literal. `build.py` excludes `__tests__` from the
vendored engine copy (`"__tests__" in parts` → skip), so nothing here reaches `plugins/`.

Why RENDER rather than extract the JS from `apps.py` and `map.py` directly
--------------------------------------------------------------------------
A node-side extractor reading `_INTERVIEW_JS = r\"\"\"…\"\"\"` out of the Python source would be dumb
in the wrong way: rename the constant, add a third one, and the gate silently checks less while
still reporting green — the vacuous-guard shape this repo keeps finding elsewhere. Rendering
produces exactly the bytes a host receives, so the node side can extract every `<script>` block
there is and a new one is covered the moment it exists rather than the moment someone remembers.

The map goes through `map.render` and `apps.map_app`, which is what `tools.map_app_html` does
either side of its guarded read (`_open_existing`); the read itself is not re-implemented here,
because a missing ledger is `tests/test_mcp_server.py`'s subject, not this gate's.

The hostile ledger
------------------
Not invented: these are the two payloads `tests/test_map.py` already carries, at the classes that
found them — `</script><img src=x onerror=alert(1)>` (`test_the_derived_payload_is_script_safe_too`)
and `A <!--<script> double escape` (`TestNothingInTheDataCanEndTheDocument`, the double-escaped span
that swallowed the rest of the document and rendered nothing, with no error anywhere). Those tests
assert the property on the page as TEXT. This file exists so the same payloads can be asserted on
the page as it RUNS, which is the half `tests/test_map.py`'s own docstring hands to a human at
`scripts/preview_map.py`.

The hostile `severity` is written straight into `led.data` and not through `add_pin`, deliberately:
`add_pin` rejects a severity outside `SEVERITIES`, and the file a rescue run reads was written by
some other agent, not by this constructor. That is the same reachability `map.py`'s `SEV_UNKNOWN`
fallback exists for.

Usage:  python3 render-app-documents.py <out-dir>
Writes: interview.html, map-wellformed.html, map-hostile.html, manifest.json
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[3]  # src/workflow/__tests__/<this> -> repo root

sys.path.insert(0, str(ROOT / "src" / "runtime"))
sys.path.insert(0, str(ROOT / "src" / "mcp"))

import apps  # noqa: E402
import map as mapmod  # noqa: E402
from ledger import Ledger  # noqa: E402

#: Content that must render as text and never as structure. Every string here is agent-authored
#: content out of somebody else's repo — a title, a source, a severity — which is the whole reason
#: the two apps carry an escaping mechanism each.
HOSTILE_TITLE = "A <!--<script> double escape"
#: The id `map.render` DERIVES out of the `source` below, and the one the decision card then prints.
#: Split out because the derived value is the payload with the `policy:` prefix eaten, so a check
#: that only knows the source string is looking for bytes the page can never emit — green whether
#: the derivation escapes or not. The two are one constant apart so they cannot drift.
HOSTILE_POLICY_ID = "</script><img src=x onerror=alert(1)>"
HOSTILE_SOURCE = "policy:" + HOSTILE_POLICY_ID
HOSTILE_SEVERITY = "<img src=x onerror=alert(1)>"
HOSTILE_RULE = "<b>bold rule</b>"


def _provenance() -> list[dict]:
    return [{"source": "recon", "detail": "the shape engine found it"}]


def _wellformed(path: pathlib.Path) -> dict:
    """A ledger with the shapes the map actually branches on: a pin with both sides, a pin
    carrying an interview question, and a policy — so `renderList`, `detail` and `trafficLight`
    all take a populated branch rather than the empty one."""
    led = Ledger(str(path))
    led.add_pin(
        kind="contract_mismatch", title="the API returns a string where the DB holds an integer",
        severity="high", confidence="extracted", provenance=_provenance(),
        as_is={"layers": {"db": "integer", "api": "string"}},
        to_be={"description": "one shape across both layers"},
        anchors=[{"layer": "api", "loc": "routes/orders.py:41"}],
    )
    led.add_pin(
        kind="open_decision", title="which store backs the session cache",
        severity="blocker", confidence="inferred", provenance=_provenance(),
        question={
            "prompt": "Where should sessions live?",
            "options": [
                {"id": "redis", "label": "Redis", "implication": "one more service to operate"},
                {"id": "pg", "label": "Postgres", "implication": "no new service, slower reads"},
            ],
            "allow_freeform": True,
        },
    )
    led.data["policies"].append({
        "id": "pol_0001", "rule": "the database is the authority on field shape",
        "default_outcome": "align the caller", "applies_to": {}, "exceptions": [],
    })
    return led.data


def _hostile(path: pathlib.Path) -> dict:
    led = Ledger(str(path))
    led.add_pin(
        kind="other", kind_detail="renderer", title=HOSTILE_TITLE, severity="low",
        confidence="inferred", provenance=_provenance(),
        as_is={"payload": "<!-- <script> -->"},
    )
    # Written past the constructor on purpose — see this module's docstring.
    led.data["pins"][0]["severity"] = HOSTILE_SEVERITY
    led.data["policies"].append({
        "id": "pol_0001", "rule": HOSTILE_RULE, "default_outcome": "x",
        "applies_to": {}, "exceptions": [],
    })
    led.data["decision_log"].append({
        "id": "ev_0001", "pin_id": "pin_0001", "outcome": "left as it is",
        "source": HOSTILE_SOURCE, "evidence": "transcribed",
    })
    # The pin has to POINT at the event, or the page never builds a decision card: `map.py` renders
    # one under `if(p.decision)` and nothing else reads `decision_log` into the detail pane. Without
    # this line the hostile `source` was on disk and on no rendered surface, so the node gate's
    # "this string never reached the markup sink" passed over a sink the string could not reach —
    # a guard green because its subject was absent, which is the vacuous shape this repo keeps
    # finding. `map.render` derives `policy:<id>` out of `source` (pre-v0.11 events carry the id
    # nowhere else), so the card renders that id, and the id is content.
    led.data["pins"][0]["decision"] = {"event_id": "ev_0001", "outcome": "left as it is"}
    return led.data


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {HERE.name} <out-dir>", file=sys.stderr)
        return 2
    out = pathlib.Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)

    (out / "interview.html").write_text(apps.interview_app(), encoding="utf-8")
    (out / "map-wellformed.html").write_text(
        apps.map_app(mapmod.render(_wellformed(out / "wellformed.json"), title="wellformed")),
        encoding="utf-8")
    (out / "map-hostile.html").write_text(
        apps.map_app(mapmod.render(_hostile(out / "hostile.json"), title="hostile")),
        encoding="utf-8")

    (out / "manifest.json").write_text(json.dumps({
        "documents": [
            {"name": "interview app", "file": "interview.html", "app": "interview",
             "hostile": []},
            {"name": "map app (well-formed ledger)", "file": "map-wellformed.html", "app": "map",
             "hostile": []},
            {"name": "map app (hostile ledger)", "file": "map-hostile.html", "app": "map",
             "hostile": [HOSTILE_TITLE, HOSTILE_SOURCE, HOSTILE_POLICY_ID, HOSTILE_SEVERITY,
                         HOSTILE_RULE]},
        ],
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
