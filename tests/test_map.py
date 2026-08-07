"""Tests for runtime/map.py — the visual map artifact.

The map is a user-facing deliverable and its correctness is a DOM, so it is verified rendered in a
browser — repeatably, via `python scripts/preview_map.py`, whose docstring lists what to look at.
That pass covers the pin list, the `as_is`/`to_be` projection over every shape the spec allows, the
three-column contract-diff with the disagreeing layer flagged, the linked interview question, the
traffic-light, the `evidence` states of a decision card (elicited / brief / transcribed with a
quote / transcribed with none / cascaded, which also shows the policy and how it was elected)
reading as *different strengths* before the words are read, and
hostile content rendering as text rather than executing — in light and dark.

These tests pin only what CI can guard without a browser: the output is one self-contained file
(data inlined, no external fetch), it is script-safe, and every pin's data reaches the page.
Deliberately NOT here: assertions that the template *contains* the strings a correct renderer would
emit. Matching source text against expected content is the heuristic this package refuses
everywhere else; it would pass on a renderer that never runs.
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import map as mapmod  # noqa: E402
from ledger import Ledger  # noqa: E402


#: Where a JS `/` may begin a regex literal rather than a division — the lexical rule an engine
#: uses, not a guess about the text: a regex may only start where a VALUE may start.
_REGEX_MAY_FOLLOW = set("(=,:[!&|?{};+-*<>~^%")


def code_only(template: str) -> str:
    """The template with every comment blanked, so a REFERENCE can be told from a mention.

    `TestTheWholeEnvelopeHasAReader` asserted `p.<field>` against the raw template and called it
    "not a word search" — but a comment naming the field satisfied it exactly as a word does.
    Proved by planting, both ways, in `test_the_reference_check_is_not_satisfied_by_a_comment`.

    It is a scanner and not a `re.sub`, because this template carries every construct a naive strip
    gets wrong: three regex literals (one holding both quote characters), CSS block comments,
    division (`100*done/pins.length`), and — the one that decided the shape — **nested** tagged
    templates, `h`…${…h`…`…}`…``. Matching backticks pairwise gets that exactly backwards on every
    odd nesting, and the first draft did: it read three of this file's own comment blocks as string
    content and left 30 `//` markers standing. So the state is a STACK of frames, `code` and `tmpl`,
    and `${` pushes a code frame that `}` pops.

    Comments are replaced by spaces rather than deleted, so every offset in the result still names
    the same place in the template.

    Its limit, stated: a `//` inside a string it failed to enter would eat the rest of that line.
    That is what `test_the_strip_leaves_no_comment_marker_and_no_landmark_behind` is for — a
    mis-tracked string leaves a marker standing, which is how the nesting bug above was found.
    """
    out = list(template)
    frames = [["code", 0]]          # [kind, brace depth] — `${` pushes, its `}` pops
    i, n = 0, len(template)
    prev = ""                       # last non-space character seen in code
    while i < n:
        ch = template[i]
        if frames[-1][0] == "tmpl":
            if ch == "\\":
                i += 2
            elif ch == "`":
                frames.pop()
                prev, i = "`", i + 1
            elif ch == "$" and template[i + 1:i + 2] == "{":
                frames.append(["code", 0])
                prev, i = "{", i + 2
            else:
                i += 1
            continue
        if ch == "`":
            frames.append(["tmpl", 0])
            i += 1
            continue
        if ch in "'\"":             # a plain string: skip to its unescaped close
            j = i + 1
            while j < n and template[j] != ch:
                j += 2 if template[j] == "\\" else 1
            i, prev = j + 1, ch
            continue
        if ch == "/" and template[i + 1:i + 2] == "/":
            j = template.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
            continue
        if ch == "/" and template[i + 1:i + 2] == "*":
            j = template.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out[i:j] = [" " if c != "\n" else "\n" for c in template[i:j]]
            i = j
            continue
        if ch == "/" and (prev in _REGEX_MAY_FOLLOW or prev == ""):
            j = i + 1               # a regex literal — it cannot span a line
            while j < n and template[j] not in "/\n":
                j += 2 if template[j] == "\\" else 1
            i, prev = j + 1, "/"
            continue
        if ch == "{":
            frames[-1][1] += 1
        elif ch == "}":
            if frames[-1][1] == 0 and len(frames) > 1:
                frames.pop()        # closes a `${…}` hole; the template literal resumes
                prev, i = "}", i + 1
                continue
            frames[-1][1] -= 1
        if not ch.isspace():
            prev = ch
        i += 1
    return "".join(out)


def demo_ledger() -> Ledger:
    led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
    led.add_pin(
        kind="contract_mismatch", title="role enum drift", severity="blocker",
        confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
        anchors=[{"node_id": None, "layer": "db", "role": "src", "loc": "m.sql:12"}],
        as_is={"db": "ENUM('admin','user')", "frontend": "'superadmin'",
               "disagreeing_layers": ["frontend"]},
        question={"prompt": "Intended role set?",
                  "options": [{"id": "a", "label": "DB is truth", "implication": "drop FE check"}],
                  "allow_freeform": True})
    return led


class TestSelfContained(unittest.TestCase):
    def setUp(self):
        self.html = mapmod.render(demo_ledger().data, title="demo")

    def test_is_a_full_html_document(self):
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn("</html>", self.html)

    def test_no_external_resources(self):
        # a self-contained artifact opens offline: no external scripts/styles/fetch/img
        for pattern in (r'src\s*=\s*["\']https?:', r'href\s*=\s*["\']https?:',
                        r'@import', r'fetch\(["\']https?:'):
            self.assertIsNone(re.search(pattern, self.html),
                              f"external resource matched {pattern!r}")

    def test_ledger_data_is_inlined(self):
        self.assertIn("const LEDGER =", self.html)
        self.assertIn("role enum drift", self.html)          # pin title reached the page
        self.assertIn("disagreeing_layers", self.html)       # contract-diff data inlined

    def test_script_safe_closing_tags_escaped(self):
        # no raw </script> from data could break out of the inline script
        script_body = self.html.split("const LEDGER =", 1)[1]
        data_line = script_body.split("\n", 1)[0]
        self.assertNotIn("</script", data_line.lower())

    def test_the_derived_payload_is_script_safe_too(self):
        """A second inlined payload is a second way out of the inline script, and it carries values
        taken from the same agent-written file — a `source` is as attacker-reachable as a title. The
        rule that governs `const LEDGER` governs this one; asserted at it, not assumed from it."""
        hostile = {"version": "0.9", "pins": [],
                   "decision_log": [{"id": "ev_0001", "evidence": "transcribed",
                                     "source": "policy:</script><img src=x onerror=alert(1)>"}],
                   "policies": []}
        line = mapmod.render(hostile).split("const DERIVED = ", 1)[1].split("\n", 1)[0]
        self.assertIn("policy_id", line)          # the value did reach the page...
        self.assertNotIn("</script", line.lower())  # ...and cannot close the script it rides in

    def test_inlined_content_is_never_rewritten_by_a_later_substitution(self):
        """The page was assembled by chained `.replace()`, so every substitution after `__DATA__`
        ran over the ledger it had just inlined. A pin titled `evil __DERIVED__ title` came out as
        `evil {} title` — or as the whole derived-rungs JSON — and `__LIVE_SCRIPT__` in a title
        injected the self-reload loop into the frozen artifact that is meant to be safe to hand to
        anyone. `esc` cannot reach this: it happens in Python, to the JSON literal, before the page
        exists. Asserted on the value that comes back out of the inlined JSON, which is the only
        thing that proves the title survived intact."""
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        titles = ["evil __DERIVED__ title", "__DATA__ and __TITLE__",
                  "__LIVE_SCRIPT__ __LIVE_STYLE__ __LIVE_BADGE__"]
        for t in titles:
            led.add_pin(kind="defect", title=t, severity="low", confidence="extracted",
                        provenance=[{"source": "recon", "detail": "x"}], as_is={"description": "d"})
        # a non-empty DERIVED payload, so the second substitution has something to inject
        led.data["decision_log"].append({"id": "ev_0001", "pin_id": "pin_0001", "outcome": "x",
                                         "source": "policy:pol_0001", "evidence": "transcribed"})
        html = mapmod.render(led.data, title="hostile")
        payload = json.loads(html.split("const LEDGER =", 1)[1]
                             .split(";\n", 1)[0].replace("<\\/", "</"))
        self.assertEqual([p["title"] for p in payload["pins"]], titles)
        # and the frozen page stays frozen: content cannot switch live mode on
        self.assertNotIn("location.reload", html)
        self.assertNotIn("livebadge", html)

    def test_empty_ledger_renders(self):
        empty = Ledger(os.path.join(tempfile.mkdtemp(), "l.json"))
        out = mapmod.render(empty.data)
        self.assertIn("<!doctype html>", out.lower())

    def test_render_file_writes_html(self):
        led = demo_ledger()
        led.save()
        out_path = os.path.join(tempfile.mkdtemp(), "map.html")
        result = mapmod.render_file(led.path, out_path)
        self.assertTrue(os.path.exists(result))
        self.assertIn("role enum drift", result.read_text(encoding="utf-8"))


class TestGraphAnchoredRendering(unittest.TestCase):
    """Anchors enriched by runtime/graph.py (node_id + blast_radius) reach the page — the map
    stays a self-contained projection: the graph is needed at anchor time, never at view time."""

    def test_node_id_and_blast_radius_inlined(self):
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(
            kind="contract_mismatch", title="role enum drift", severity="blocker",
            confidence="extracted", provenance=[{"source": "recon", "detail": "x"}],
            anchors=[{"node_id": "table_users", "layer": "db", "role": "src",
                      "loc": "packages/db/schema/users.ts:12",
                      "blast_radius": {"count": 3, "depth": 2, "edges": "structural/extracted",
                                       "sample": ["backend/models.py:30", "frontend/types.ts:5"]}}],
            as_is={"db": "x", "frontend": "y", "disagreeing_layers": ["frontend"]})
        html = mapmod.render(led.data, title="anchored")
        self.assertIn("table_users", html)          # node_id inlined
        self.assertIn("impact:", html)               # blast-radius line present
        self.assertIn("backend/models.py:30", html)  # sample dependent inlined
        # still self-contained: no external fetch introduced
        self.assertNotIn("fetch(", html.split("const LEDGER =", 1)[1].split("\n", 1)[0])


class TestDecisionEvidenceIsInlined(unittest.TestCase):
    """The decision card states the rung, which lives on the DecisionEvent — so the page must carry
    `decision_log`, not just `pins`.

    This is the only part of that feature CI can hold without a browser, and it is worth holding:
    trimming the inlined payload to `pins` is an obvious "optimization" that would turn the lookup
    into a dangling id and silently drop the rung — with the page still rendering, still
    self-contained, and every other test still green. Asserting that the *template* contains the
    words a correct card would print is the heuristic this file refuses; asserting the data the
    lookup needs is a fact about the artifact."""

    def test_the_event_the_pin_points_at_reaches_the_page(self):
        led = demo_ledger()
        pin = led.data["pins"][0]
        led.decide(pin["id"], "a", "the DB enum is narrowest", "a fourth role appears",
                   evidence="transcribed", human_answer="option a — the DB is truth")
        html = mapmod.render(led.data, title="decided")
        event_id = pin["decision"]["event_id"]
        payload = json.loads(html.split("const LEDGER =", 1)[1]
                             .split(";\n", 1)[0].replace("<\\/", "</"))
        event = next((e for e in payload.get("decision_log", []) if e["id"] == event_id), None)
        self.assertIsNotNone(event, "the map cannot resolve pin.decision.event_id — the rung is "
                                    "unreachable from the page, whatever the card says")
        self.assertEqual(event["evidence"], "transcribed")
        self.assertEqual(event["human_answer"], "option a — the DB is truth")

    def test_a_cascaded_card_can_reach_the_policy_that_decided_it(self):
        """The `cascaded` card states the rule the user elected and how they elected it, so the
        second join — event.policy_id -> policies[] — has to land on the page too. It is a join on a
        field, not on `source`'s `policy:<id>` prefix: a surface that parses a string to find its
        record is one refactor away from silently finding nothing."""
        led = demo_ledger()
        pin = led.data["pins"][0]
        pin["severity"] = "low"                      # blocker|high is held back by the threshold
        pol = led.add_policy(applies_to={"kind": "contract_mismatch"}, rule="the DB is truth",
                             default_outcome="a",   # the id this pin's own question offers (v0.12)
                             human_answer="db wins unless I flag one")
        led.apply_policy(pol)
        payload = json.loads(mapmod.render(led.data, title="cascaded").split("const LEDGER =", 1)[1]
                             .split(";\n", 1)[0].replace("<\\/", "</"))
        event = next(e for e in payload["decision_log"] if e["id"] == pin["decision"]["event_id"])
        self.assertEqual(event["evidence"], "cascaded")
        policy = next((p for p in payload.get("policies", []) if p["id"] == event["policy_id"]), None)
        self.assertIsNotNone(policy, "the map cannot resolve event.policy_id — the card would have "
                                     "to say a policy decided this and be unable to say which")
        self.assertEqual((policy["rule"], policy["evidence"], policy["human_answer"]),
                         ("the DB is truth", "transcribed", "db wins unless I flag one"))


class TestARungTheTableDoesNotKnow(unittest.TestCase):
    """The spec says it outright — *"a rung one of the three surfaces does not know is the same bug
    wearing a new name, so adding one means teaching all three"* — and nothing held the map to it.
    `cascaded` was added to `DECISION_EVIDENCE` and to this table by hand, in the same commit, by
    someone who remembered; the next one would be added by someone who did not, and the card would
    fall through to the `weak` default and call it unrecorded.

    The carrier is the object literal, read as keys, not a search for the word in the file."""

    def test_the_cards_rung_table_covers_every_rung_the_schema_names(self):
        from ledger import DECISION_EVIDENCE
        block = re.search(r"const RUNG=\{(.*?)\}\};", mapmod._TEMPLATE, re.S)
        self.assertIsNotNone(block, "the RUNG table's shape changed — this guard just went vacuous")
        keys = set(re.findall(r"^\s+(\w+):\{", block.group(1), re.M))
        self.assertEqual(keys, set(DECISION_EVIDENCE))


class TestALedgerWrittenBeforeTheRungExisted(unittest.TestCase):
    """v0.13. `cascaded` binds the write, so a pre-v0.11 ledger carries `transcribed` on its
    cascades and this surface printed *"an agent relayed what the user said"* + *"⚠ relayed with no
    quote — nothing here separates it from an invention"* over the user's own elected policy.

    The rule is applied in Python (`map.derived_rungs` → `ledger.decision_rung`) and its RESULT
    crosses into the page, which is what makes it assertable here at all: a second implementation in
    the page's JavaScript would be reachable by no test without a browser, and would drift."""

    @staticmethod
    def _legacy() -> dict:
        return {"version": "0.9",
                "pins": [{"id": "pin_0001", "state": "decided",
                          "decision": {"event_id": "ev_0001", "outcome": "db"}}],
                "decision_log": [{"id": "ev_0001", "pin_id": "pin_0001", "outcome": "db",
                                  "source": "policy:pol_0001", "evidence": "transcribed"}],
                "policies": [{"id": "pol_0001", "rule": "the DB is truth", "default_outcome": "db"}]}

    def test_the_page_is_told_to_read_the_rung_it_cannot_take_off_the_field(self):
        derived = mapmod.derived_rungs(self._legacy())
        self.assertEqual(derived, {"ev_0001": {"rung": "cascaded", "policy_id": "pol_0001",
                                               "as_recorded": "transcribed"}})

    def test_the_derivation_reaches_the_rendered_page(self):
        html = mapmod.render(self._legacy(), title="legacy")
        inlined = json.loads(html.split("const DERIVED = ", 1)[1]
                             .split(";\n", 1)[0].replace("<\\/", "</"))
        self.assertEqual(inlined["ev_0001"]["rung"], "cascaded")
        # the policy the card must join to is named, though the event carries no `policy_id`
        self.assertEqual(inlined["ev_0001"]["policy_id"], "pol_0001")
        # and what the file actually records travels with it, so the card states the disagreement
        # instead of quietly winning it
        self.assertEqual(inlined["ev_0001"]["as_recorded"], "transcribed")

    def test_a_ledger_this_runtime_wrote_derives_nothing(self):
        """Empty is the normal case, and it has to be: the branch it feeds is the exception, and an
        index that grew entries for ordinary events would be a second copy of the rung."""
        led = demo_ledger()
        pin = led.data["pins"][0]
        pin["severity"] = "low"
        led.apply_policy(led.add_policy(applies_to={"kind": "contract_mismatch"},
                                        rule="the DB is truth", default_outcome="a",
                                        human_answer="db wins"))
        led.decide(pin["id"], "a", "r", "flip", evidence="elicited")
        self.assertEqual(mapmod.derived_rungs(led.data), {})


class TestTheSafePathIsTheOnlyPath(unittest.TestCase):
    """`esc` at every site is a rule every site must remember, and this file got it wrong twice:
    once `esc` was a String() cast that escaped nothing, and then `severity` — alone among the
    fields — went into the list row, the detail sub-line and a `style` attribute raw, so a ledger
    carrying `severity: "<img src=x onerror=…>"` put a live img node in the DOM.

    Fixing the field would leave the next field to whoever writes it. What CI can hold without a
    browser is the *shape* of the mechanism, and it is worth holding precisely because it is the
    thing that makes the field-level bug unwritable: markup reaches the document through ONE sink,
    the sink escapes anything that is not an assembled fragment, and the tagged template is the only
    thing that assembles one. The behaviour itself is verified rendered — `scripts/preview_map.py`,
    check 4 — because a DOM is what it is about.

    The honest limit: this reads our own template as text. It cannot tell a sink in code from the
    word in a comment, which is why the assertion is an exact count and the message says so."""

    #: Every DOM API that writes markup rather than text. A closed list of names with exact
    #: meanings — not a guess about what some code does.
    SINKS = ("outerHTML", "insertAdjacentHTML", "document.write", "createContextualFragment")

    def test_markup_reaches_the_document_through_exactly_one_sink(self):
        body = mapmod._TEMPLATE
        self.assertEqual(body.count("innerHTML"), 1,
                         "the page writes markup in more than one place (or a comment says the "
                         "word). Every write goes through `mount`, which escapes anything that is "
                         "not an assembled fragment — a second sink is a second escaping rule.")
        sink_line = next(i for i, ln in enumerate(body.splitlines()) if "innerHTML" in ln)
        opener = next(i for i, ln in enumerate(body.splitlines()) if "function mount(" in ln)
        self.assertLess(opener, sink_line, "the one write is outside `mount`")
        self.assertLess(sink_line - opener, 8, "the one write is not in `mount`'s own body")
        for sink in self.SINKS:
            self.assertNotIn(sink, body, f"{sink} bypasses `mount` and its escaping")

    #: `mount(` appears once as its own definition; every other occurrence is a call.
    def test_every_call_to_the_sink_hands_it_a_thunk_and_not_a_node(self):
        """v0.23 — the sink is also the page's one failure boundary, and that only works if the
        node is built INSIDE it.

        `mount(id, node)` evaluated its argument at the call site, so anything that threw while
        building one threw before the sink was reached: the pane was never written and the page said
        nothing. Reproduced in Chromium on a pin whose `brainstorm.proposals` was a string — the
        list rendered, the row showed as selected, and the detail pane stayed empty.

        A call that passes an already-built node is that bug again, one card later, so it is not a
        thing you can write here. Same limit as the class above: this reads our own template as
        text; the rendered half is the preview walk and the browser run recorded in
        `docs/open-gaps.md` §22."""
        body = mapmod._TEMPLATE
        sites = [seg for seg in body.split("mount(")[1:]
                 if not seg.startswith("id,build,subject")]      # the definition is not a call
        self.assertGreaterEqual(len(sites), 5,
                                "the mount call sites vanished — this guard is vacuous")
        # The second argument, up to the first comma or paren that follows it. Two legitimate
        # shapes and no others: an arrow that builds nothing until `mount` calls it, or the bare
        # name of a function. A value expression is the bug.
        offenders = [s[:60] for s in sites
                     if not re.match(r"[^,]+,\s*(\(\)\s*=>|[A-Za-z_$][\w$]*\s*[,)])", s)]
        self.assertEqual(offenders, [],
                         f"a mount call evaluates its node at the call site: {offenders} — "
                         "anything that throws there throws outside the one boundary this page has")

    def test_only_the_tagged_template_can_produce_an_unescaped_fragment(self):
        """`frag` escapes everything that is not an `H`, so `new H(` IS the escape hatch. There is
        exactly one, inside `h`, and it exists to let fragments nest. A `raw()` helper added later
        would show up here — which is the point: an opt-out you can reach for is an opt-out someone
        reaches for with a pin title in their hand."""
        self.assertEqual(mapmod._TEMPLATE.count("new H("), 1)
        self.assertEqual(mapmod._TEMPLATE.count("function H("), 1)


class TestNothingInTheDataCanEndTheDocument(unittest.TestCase):
    """A `</script>` was escaped; `<!--` was not, and it was the worse of the two. HTML's script-data
    tokenizer treats `<!--` followed later by `<script` as a double-escaped span in which `</script>`
    closes nothing, so a pin titled ``A <!--<script> double escape`` swallowed the rest of the
    document: `LEDGER` undefined, both panes empty, **no error anywhere**. A map that silently shows
    nothing reads as "no findings", which is the worst thing this surface can say.

    So the rule is not a longer list of sequences but the character all of them need."""

    HOSTILE = "A <!--<script> double escape"

    def _rendered(self) -> str:
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(kind="other", kind_detail="renderer", title=self.HOSTILE, severity="low",
                    confidence="inferred", provenance=[{"source": "recon", "detail": "x"}],
                    as_is={"payload": "<!-- <script> -->"})
        led.data["policies"].append({"id": "pol_x", "rule": "<b>r</b>", "default_outcome": "x",
                                     "applies_to": {}, "exceptions": []})
        return mapmod.render(led.data, title="hostile")

    @staticmethod
    def _payload(html: str, name: str) -> str:
        return html.split(name, 1)[1].split(";\n", 1)[0]

    def test_no_inlined_payload_carries_an_angle_bracket(self):
        html = self._rendered()
        for name in ("const LEDGER =", "const DERIVED =", "const WEAK_POL =", "const SETTLED ="):
            self.assertNotIn("<", self._payload(html, name),
                             f"{name} can still start an HTML token inside the script it rides in")

    def test_the_data_survives_the_escape_intact(self):
        """An escape that loses the data is not an escape. `\\u003c` is JSON's own encoding of the
        character, so the payload stays valid JSON and reads back byte-identical."""
        payload = json.loads(self._payload(self._rendered(), "const LEDGER ="))
        self.assertEqual(payload["pins"][0]["title"], self.HOSTILE)
        self.assertEqual(payload["pins"][0]["as_is"]["payload"], "<!-- <script> -->")

    def test_the_document_still_closes_after_the_script(self):
        html = self._rendered()
        self.assertIn("</script></body></html>", html.replace("\n", ""))


class TestThePageIsRenderedFromWhatAReaderCanIndex(unittest.TestCase):
    """v0.23 — the map was the last surface still projecting a ledger it had not read through the
    guarded path, and it failed in both directions at once.

    A `null` entry in `pins`, or a `pins` that is not a list, threw inside the page's own
    `trafficLight` — which runs before anything is mounted, so the document rendered its header and
    NOTHING, under a full green bar, while `render_map` returned `{"written": …}` with
    `isError: false`. Observed in Chromium. One collection over, a non-object entry in
    `decision_log` or `policies` made `render` itself raise in Python.

    Both halves have one answer and it is the schema's: `readable_ledger` is what this module
    renders. What that DROPPED is the second half — `nonconforming` reaches the page as a banner,
    which it had never done on any file, though `ledger_summary` reported it in the same session."""

    #: Every malformation reproduced over stdio against the shipped server, as raw ledger data.
    BROKEN = {
        "a null pin": {"pins": [None]},
        "pins is not a list": {"pins": "everything is fine"},
        "a log entry is a string": {"decision_log": ["ev_0001 happened"]},
        "decision_log is not a list": {"decision_log": {"ev_0001": "happened"}},
        "a policy is a string": {"policies": ["always prefer X"]},
        "policies is not a list": {"policies": None},
    }

    @staticmethod
    def _base() -> dict:
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        led.add_pin(kind="defect", title="an ordinary pin", severity="high",
                    confidence="extracted", provenance=[{"source": "recon", "detail": "x"}])
        return led.data

    def test_render_answers_on_every_shape_instead_of_raising(self):
        for name, override in self.BROKEN.items():
            with self.subTest(shape=name):
                data = dict(self._base())
                data.update(override)
                mapmod.render(data, title=name)

    def test_the_page_is_handed_no_entry_the_schema_does_not_describe(self):
        """The property that makes the page's own JavaScript safe without a second guard written in
        a second language: whatever the file holds, `LEDGER.pins` is a list of objects."""
        for name, override in self.BROKEN.items():
            with self.subTest(shape=name):
                data = dict(self._base())
                data.update(override)
                html = mapmod.render(data, title=name)
                payload = json.loads(html.split("const LEDGER =", 1)[1].split(";\n", 1)[0]
                                     .replace("\\u003c", "<"))
                for collection in ("pins", "decision_log", "policies"):
                    self.assertIsInstance(payload[collection], list, collection)
                    for entry in payload[collection]:
                        self.assertIsInstance(entry, dict,
                                              f"{collection} carries a non-object into the page")

    def test_what_the_guard_dropped_is_on_the_page_and_not_merely_absent(self):
        """A count that silently shrinks is the map telling a human there is less here than there
        is — the same claim a blank page makes, made quietly."""
        from ledger import nonconforming
        for name, override in self.BROKEN.items():
            with self.subTest(shape=name):
                data = dict(self._base())
                data.update(override)
                html = mapmod.render(data, title=name)
                inlined = json.loads(html.split("const NONCONF =", 1)[1].split(";\n", 1)[0]
                                     .replace("\\u003c", "<"))
                self.assertEqual(inlined, nonconforming(data),
                                 "the page's report is not the file's own report")
                self.assertTrue(inlined, f"{name} reaches the page as nothing at all")

    def test_every_rule_the_report_can_name_has_a_sentence_on_the_page(self):
        """`NONCONF_WHY` is a closed table over the rule names the schema can produce, held to them
        the way every other closed table this page reads is held to its tuple — so a rule added to
        any of the three arrives here instead of printing as a bare token.

        **Its first draft quantified over two of the three tuples and the browser walk caught it**:
        the hostile ledger put `committing_source` and `flip_criteria` on the page reading *"no
        sentence here describes this rule"*. `EVENT_RULES` is the log half and is exactly as
        reportable as the other two."""
        import ledger as ledger_mod
        table = mapmod._TEMPLATE.split("const NONCONF_WHY={", 1)[1].split("};", 1)[0]
        keys = set(re.findall(r"^\s*(\w+):", table, re.MULTILINE))
        # v0.25 — the two shape tables now DERIVE their rules, so the page derives their sentences
        # too (`__SHAPE_WHY__`, inlined from `ledger.shape_notes`). Hand-writing thirty-one
        # sentences beside thirty-one derived rules is the drift this gate exists to catch, one
        # table over. The hand-written entries stay for the rules whose prose was argued, and they
        # win the lookup; what this asserts is that between the two there is no rule with nothing.
        derived = ledger_mod.shape_notes()
        self.assertTrue(all(derived.values()), "a derived rule name got an empty sentence")
        produced = ({n for n, _h, _m in ledger_mod.PIN_RULES}
                    | {n for n, _h, _m in ledger_mod.POLICY_RULES}
                    | {n for n, _h, _m in ledger_mod.EVENT_RULES}
                    | {"ledger_shape", "collection_shape", "entry_shape", "log_entry_kind"})
        self.assertEqual(produced - keys - set(derived), set(),
                         "a rule `nonconforming` can report has no sentence on the page")

    def test_the_page_can_join_the_report_to_the_record_it_is_about(self):
        """v0.25 — the banner is a fact about the FILE, and a reader looking at one card was never
        told that this card's own record was in it. A pin carrying `verification: "observed"`
        rendered *"no rung recorded"* — true of the guarded reading — over a file that records one,
        and nothing contradicted it.

        The join is by id, so it only works while there is ONE answer to what a record's id is.
        There were two: `nonconforming` labelled by `str(pin.get("id") or "")` and every surface
        read `pin_read`, so a pin carrying `id: 7` was reported as `7` and rendered as `""`. Both
        now go through the carrier, and a record this runtime cannot name is named by position on
        both sides — which the card says, rather than showing a clean one."""
        from ledger import nonconforming, pin_read
        from shape_corpus import worst_ledger
        data = worst_ledger()
        report = nonconforming(data)
        labelled = {i for ids in report.values() for i in ids}
        joinable = [pin_read(p)["id"] for p in data["pins"] if isinstance(p, dict)
                    and pin_read(p)["id"]]
        hit = [i for i in joinable if i in labelled]
        self.assertGreater(len(hit), 20,
                           "no broken pin in the worst file the corpus can build is reachable from "
                           "the report by its own id — the per-record card would never fire")
        self.assertIn("nonconfCard", mapmod._TEMPLATE, "the card was removed from the page")
        for anchor in ("${nonconfCard(p.id)}", "${nonconfCard(P.id)}"):
            self.assertIn(anchor, mapmod._TEMPLATE,
                          f"a detail view stopped asking the report about its own record ({anchor})")

    def test_the_derived_sentences_actually_reach_the_page(self):
        """`__SHAPE_WHY__` is inlined, so the claim above is only worth what the substitution is:
        a placeholder that stopped being filled would leave the fallback table empty and every
        derived rule would print as `no sentence here describes this rule` — which is exactly what
        the browser walk found the last time this page quantified over less than the report
        produces."""
        import json as _json
        import ledger as ledger_mod
        html = mapmod.render(self._base(), title="t")
        inlined = _json.loads(html.split("const SHAPE_WHY =", 1)[1].split(";\n", 1)[0]
                              .replace("\\u003c", "<"))
        self.assertEqual(inlined, ledger_mod.shape_notes())
        self.assertIn("pin_verification", inlined)

    def test_the_map_counts_what_ledger_summary_counts(self):
        """They used to be the raw array lengths, so the map and the tool an agent calls before
        acting reported two different totals for one file."""
        for name, override in self.BROKEN.items():
            with self.subTest(shape=name):
                tmp = os.path.join(tempfile.mkdtemp(), "ledger.json")
                data = dict(self._base())
                data.update(override)
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                html = mapmod.render(data, title=name)
                payload = json.loads(html.split("const LEDGER =", 1)[1].split(";\n", 1)[0]
                                     .replace("\\u003c", "<"))
                self.assertEqual(len(payload["pins"]), Ledger(tmp).summary()["pins"],
                                 "the map and `ledger_summary` disagree about one file")


class TestTheSurfacesAgreeAboutOneLedger(unittest.TestCase):
    """Two surfaces counted the same standing rules and printed different numbers — the map badged
    two on the repo's own preview fixture, the projected `AGENTS.md` said one — because the map
    asked *is the rung weak* and the projection asked *is the quote missing*. Neither was wrong on
    its own terms, which is exactly why a reader could act on neither.

    The classification is `ledger.policy_weakness` now, in the module that owns the schema, and the
    map gets its RESULT inlined the way it already gets `derived_rungs`. Asserted over the preview
    fixture because that is the ledger a human actually looks at."""

    @staticmethod
    def _fixture() -> dict:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import preview_map
        return preview_map.build().data

    def test_the_map_and_the_projection_weigh_the_same_rules(self):
        import instructions
        data = self._fixture()
        weak = mapmod.weak_policies(data)
        self.assertTrue(weak, "the fixture no longer carries a weak rule — this guard went vacuous")
        self.assertIn(f"{len(weak)} of the standing rules below", instructions.render(data))

    def test_the_reasons_reach_the_page(self):
        data = self._fixture()
        inlined = json.loads(mapmod.render(data).split("const WEAK_POL = ", 1)[1]
                             .split(";\n", 1)[0])
        self.assertEqual(inlined, mapmod.weak_policies(data))

    def test_the_pages_settled_states_are_the_schemas(self):
        """v0.16 made `deferred` a settled state and the page kept its own hand-written list, so a
        deferred blocker was counted as an OPEN blocker in the loudest colour the page has."""
        from ledger import SETTLED_STATES
        html = mapmod.render(demo_ledger().data)
        inlined = json.loads(html.split("const SETTLED = new Set(", 1)[1].split(");", 1)[0])
        self.assertEqual(inlined, list(SETTLED_STATES))

    def test_the_pages_askable_states_are_the_interviews_own(self):
        """Same rule, one set over, and this one arrived because the page did NOT have it: reach
        was re-derived from `SETTLED` alone, so the funnel's countdown printed on `detected` pins
        the funnel never carries. The set the page reads must be the set `interview_view` selects,
        so both halves of the same statement cannot be answered differently."""
        from ledger import INTERVIEW_STATES
        html = mapmod.render(demo_ledger().data)
        inlined = json.loads(html.split("const ASKABLE = new Set(", 1)[1].split(");", 1)[0])
        self.assertEqual(inlined, list(INTERVIEW_STATES))


class TestACrossDerivationHasAReader(unittest.TestCase):
    """`cross_derivations` had ONE writer — `Ledger.cross_derive` — and zero readers: not this page,
    not `ledger_summary`, not the projected `AGENTS.md`. The writer's own comment asserted the
    opposite (*"the derivations are on the pin either way, so the human sees what disagreed"*),
    which made it a claim with no carrier written in the commit that closed a claim with no carrier.

    It matters most in the branch that comment defends: `cross_derive` stopped rewriting an existing
    question, rightly, so a disagreement reopened the pin to `needs_input (contested)` with the
    human's original menu and no account anywhere of why it was back.

    Verified rendered, in a browser, on `.preview/map.html`: the contested pin's card sits above the
    question, names both providers and both results, and reads amber on `--warnbg` with the ⚠ line,
    while the agreeing pin's card is green-bordered on the plain card background with no warning at
    all (`border-left-color` `rgb(240,140,0)` vs `rgb(47,158,68)` — measured off the elements, in
    light mode). What is asserted below is what CI can hold without a browser."""

    @staticmethod
    def _fixture() -> dict:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import preview_map
        return preview_map.build().data

    def test_the_preview_fixture_carries_a_disagreement_and_an_agreement(self):
        """Without both, the manual pass has nothing to look at and item 18 goes vacuous — the same
        guard `test_the_map_and_the_projection_weigh_the_same_rules` puts on its fixture."""
        found = {x["agreement"] for p in self._fixture()["pins"]
                 for x in (p.get("cross_derivations") or [])}
        self.assertLessEqual({"agree", "disagree"}, found)

    def test_the_page_knows_no_agreement_the_ledger_refuses(self):
        """The table is read as keys, like `RUNG`, and each key is EXECUTED against the writer
        rather than compared to a second copy of its vocabulary kept here — a hand-kept list beside
        the schema's is the bug one surface over. The reverse direction is not asserted because it
        does not have to be: an agreement this table does not carry falls through to a DEFINED
        `weak` case that shows the value and the ⚠, so an unknown value degrades to "weigh this",
        never to a card that says nothing."""
        block = re.search(r"const AGREE=\{(.*?)\}\};", mapmod._TEMPLATE, re.S)
        self.assertIsNotNone(block, "the AGREE table's shape changed — this guard just went vacuous")
        keys = set(re.findall(r"^\s*(\w+):\{", block.group(1), re.M))
        self.assertTrue(keys, "no agreement values at all — the reader is gone")
        derivations = [{"provider": "anthropic", "model": "m", "result": "yes"},
                       {"provider": "openai", "model": "n", "result": "no"}]
        for key in sorted(keys):
            with self.subTest(agreement=key):
                led = demo_ledger()
                led.cross_derive(led.data["pins"][0]["id"], claim="c",
                                 derivations=derivations, agreement=key)

    def test_the_derivations_reach_the_rendered_page(self):
        led = demo_ledger()
        led.cross_derive(led.data["pins"][0]["id"],
                         claim="the scheduler re-delivers on consumer timeout",
                         derivations=[{"provider": "anthropic", "model": "opus",
                                       "result": "yes — the ack deadline expires"},
                                      {"provider": "openai", "model": "gpt-5",
                                       "result": "no — the row is marked taken first"}],
                         agreement="disagree")
        inlined = json.loads(mapmod.render(led.data).split("const LEDGER = ", 1)[1]
                             .split(";\n", 1)[0].replace("\\u003c", "<"))
        record = inlined["pins"][0]["cross_derivations"][0]
        self.assertEqual(record["agreement"], "disagree")
        self.assertEqual([d["result"] for d in record["derivations"]],
                         ["yes — the ack deadline expires", "no — the row is marked taken first"])


class TestThePaletteCarriesTheWarningItIsUsedFor(unittest.TestCase):
    """The amber is not decoration: it is the entire mechanism by which *"⚠ relayed with no quote"*
    reads as weaker than a green elicited card, and the spec permits the weak rung **on the grounds
    that it is made visible**. At `#f08c00` it measured 2.48:1 as text on the light card and 2.33:1
    on the tinted warn card — a warning nobody can read at a glance is the same failure as a warning
    nobody prints, arriving by a different route.

    The honest limit, stated rather than oversold: this computes WCAG ratios from the `:root` block
    of our own stylesheet. It is a fact about the declared palette, NOT a claim about any DOM — the
    cascade, an override, a force-dark browser and a user stylesheet all sit between the two. The
    DOM half is `scripts/preview_map.py`, item 19, in a browser, in light mode on purpose.

    Both themes are computed, because the badge case is theme-independent (white on amber is white
    on amber wherever the card sits) and the text case is not — which is exactly why one token could
    not serve both and the foreground had to split.
    """

    #: WCAG 2.x: 4.5:1 for body text, 3:1 for a UI component or large text. The badge is 11px bold,
    #: which is neither, so it is held to the text bar wherever the palette can reach it — and where
    #: it cannot, the number is in the stylesheet comment rather than absent.
    TEXT, UI = 4.5, 3.0

    @staticmethod
    def _luminance(value: str) -> float:
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        parts = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    @classmethod
    def _ratio(cls, a: str, b: str) -> float:
        la, lb = cls._luminance(a), cls._luminance(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    @classmethod
    def _palettes(cls) -> tuple[dict, dict]:
        light = dict(re.findall(r"--([a-z]+):(#[0-9a-f]{3,6})",
                                re.search(r":root\{(.*?)\}", mapmod._TEMPLATE, re.S).group(1)))
        dark = dict(light)
        dark.update(re.findall(
            r"--([a-z]+):(#[0-9a-f]{3,6})",
            re.search(r"prefers-color-scheme:dark\)\{:root\{(.*?)\}",
                      mapmod._TEMPLATE, re.S).group(1)))
        return light, dark

    def test_the_palette_block_is_still_readable_here(self):
        """A guard on the guard: if the stylesheet stops matching, every assertion below passes on
        an empty dict and this class silently stops measuring anything."""
        for name, palette in zip(("light", "dark"), self._palettes()):
            with self.subTest(theme=name):
                for token in ("high", "low", "card", "warnbg", "bg", "onhigh", "blocker"):
                    self.assertIn(token, palette, f"--{token} vanished from the {name} palette")

    def test_the_warning_text_is_readable_on_both_surfaces_it_lands_on(self):
        """`.warn` sits on `.card`, and inside `.dec.weak` it sits on `--warnbg` — the tinted card
        that marks an unquoted relay, i.e. the exact place the warning matters most."""
        for name, p in zip(("light", "dark"), self._palettes()):
            for surface in ("card", "warnbg"):
                with self.subTest(theme=name, surface=surface):
                    self.assertGreaterEqual(self._ratio(p["high"], p[surface]), self.TEXT,
                                            f"--high on --{surface} ({name}) is unreadable as text")

    #: Every badge fill on this page, with the foreground it is actually printed in. A pair, not a
    #: colour: `--onhigh` and `--onok` exist because no single hue can be both dark enough for white
    #: text and light enough to read AS text on a dark card, and both hues are used both ways.
    #: EVERY badge is here — including `--ok`, which the finding did not name and which a DOM sweep
    #: of every pin found at 3.45:1. A list that skipped it would be a gate checking less than its
    #: name claims, which is another open entry in the same register.
    BADGES = (("high", "onhigh"), ("ok", "onok"), ("accent", "onaccent"), ("low", None),
              ("blocker", None), ("medium", None))

    def test_a_badge_is_readable_against_its_own_foreground(self):
        """Every `.sev` and `.rung` badge is a filled pill with text on it, so the pair matters and
        not the surface under it — which is why these numbers are the same in both themes for the
        tokens whose foreground does not switch, and why the two that do switch have their own."""
        for name, p in zip(("light", "dark"), self._palettes()):
            for token, fg_token in self.BADGES:
                fg = p[fg_token] if fg_token else "#ffffff"
                with self.subTest(theme=name, badge=token):
                    self.assertGreaterEqual(self._ratio(p[token], fg), self.TEXT,
                                            f"{fg} on --{token} ({name}) is an unreadable badge")

    def test_the_fallback_badge_is_a_badge_too(self):
        """The pair a severity this page does not know lands on lives in the script, not in `:root`,
        so a gate that read only the palette skipped the badge a HOSTILE value is printed in — and a
        DOM sweep found it at 3.54:1 while every named token passed. Read off the object literal
        that supplies it, so it cannot be changed without this seeing it."""
        pair = re.search(r"const SEV_UNKNOWN=\{bg:'(#[0-9a-f]{3,6})',fg:'(#[0-9a-f]{3,6})'\}",
                         mapmod._TEMPLATE)
        self.assertIsNotNone(pair, "the unknown-severity pair changed shape — this guard is vacuous")
        self.assertGreaterEqual(self._ratio(pair.group(1), pair.group(2)), self.TEXT)
        light, _ = self._palettes()
        self.assertGreater(self._ratio(pair.group(1), light["low"]), 1.4,
                           "an unrecognised severity reads as `low`, which is a claim about it")

    def test_the_colours_used_as_text_are_readable_as_text(self):
        """`--ok` is `.livebadge`'s text colour in live mode and `--high` is `.warn`'s everywhere.
        Held on `--bg` because that is where the live badge sits, in both themes."""
        for name, p in zip(("light", "dark"), self._palettes()):
            for token in ("high", "ok", "accent", "mut", "fg"):
                with self.subTest(theme=name, text=token):
                    self.assertGreaterEqual(self._ratio(p[token], p["bg"]), self.TEXT,
                                            f"--{token} ({name}) is unreadable as text on --bg")

    def test_a_hue_used_both_ways_carries_a_paired_foreground(self):
        """The rule the third instance made visible, asserted rather than described: every token
        that is BOTH a badge fill and a text colour has an `--on<token>` beside it in both themes,
        and every `--on<token>` names a token that exists. Three of the six badge fills need one and
        three do not, which is the whole content of the design."""
        paired = {token: fg for token, fg in self.BADGES if fg}
        self.assertEqual(set(paired.values()), {f"on{t}" for t in paired},
                         "an `--on<x>` that does not name the token it is the foreground of")
        for name, p in zip(("light", "dark"), self._palettes()):
            for token, fg in paired.items():
                with self.subTest(theme=name, pair=token):
                    self.assertIn(fg, p, f"--{fg} is missing from the {name} palette, so the badge "
                                         f"falls back to whatever the cascade supplies")

    def test_the_warning_hue_is_not_the_blocker_hue(self):
        """The page's colour vocabulary is four severities plus one warning. Darkening the amber far
        enough drags it toward `--blocker`, and a warning that reads as a blocker is a different lie
        from a warning nobody can read.

        Measured as HUE and not as a contrast ratio, deliberately: the two are 1.10:1 apart in
        luminance because they were darkened to similar lightness on purpose, and a luminance test
        here would fail on a palette that is perfectly distinguishable. What separates them is the
        angle, and that is what is asserted."""
        for name, p in zip(("light", "dark"), self._palettes()):
            with self.subTest(theme=name):
                gap = abs(self._hue(p["high"]) - self._hue(p["blocker"]))
                self.assertGreaterEqual(min(gap, 360 - gap), 20,
                                        "--high and --blocker have collapsed into one hue")

    @staticmethod
    def _hue(value: str) -> float:
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hi, lo = max(r, g, b), min(r, g, b)
        if hi == lo:
            return 0.0
        if hi == r:
            return (60 * ((g - b) / (hi - lo))) % 360
        if hi == g:
            return 60 * ((b - r) / (hi - lo)) + 120
        return 60 * ((r - g) / (hi - lo)) + 240


class TestTheOnlyWayDataEntersThePage(unittest.TestCase):
    """`_inline` says the escape *"is not a longer list of dangerous sequences — it is the character
    all of them need"*, and that sentence was true of `<` and of nothing else. U+2028 and U+2029 are
    legal inside a JSON string and were statement terminators inside a pre-ES2019 JavaScript string
    literal, and `ensure_ascii=False` emitted them raw into the inline script.

    This file has been wrong about escaping twice, and both times the bug was a SITE that did not go
    through the mechanism — `esc` that escaped nothing, then `severity` interpolated raw. So the fix
    is not the two `.replace` calls: it is that `_inline` is provably the only way a payload reaches
    the page, asserted by AST rather than by reading the four lines that happen to call it today."""

    @staticmethod
    def _module() -> ast.Module:
        return ast.parse(pathlib.Path(mapmod.__file__).read_text(encoding="utf-8"))

    def test_json_is_serialized_in_exactly_one_function(self):
        tree = self._module()
        sites = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for inner in ast.walk(node):
                    if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                            and inner.func.attr == "dumps"):
                        sites.append(node.name)
        self.assertEqual(sites, ["_inline"],
                         f"a payload is serialized outside `_inline` ({sites}) — the escaping is "
                         "whatever that site remembered, which is how both previous holes got in")

    #: The three substitutions that are NOT data: a title (HTML-escaped, and it lands in an element
    #: rather than in script text) and the live-mode fragments (this module's own constants, not
    #: content). Everything else in `render`'s dict is agent-written and must be inlined — stated as
    #: an exclusion list rather than an inclusion one, so a payload added later is covered by
    #: default instead of being covered when someone remembers to add it here.
    NOT_DATA = {"__TITLE__", "__LIVE_STYLE__", "__LIVE_BADGE__", "__LIVE_SCRIPT__"}

    def test_every_inlined_placeholder_is_produced_by_that_one_function(self):
        """Checked at the assignment rather than at the reader, and by exclusion: the previous
        version of this test named the four payloads that existed when it was written, so a fifth
        added by hand would have been a fifth escaping rule that no gate asked about."""
        tree = self._module()
        render = next(n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == "render")
        values = next(node for node in ast.walk(render) if isinstance(node, ast.Dict))
        inlined = {}
        for key, value in zip(values.keys, values.values):
            if isinstance(key, ast.Constant):
                inlined[key.value] = (isinstance(value, ast.Call)
                                      and isinstance(value.func, ast.Name)
                                      and value.func.id == "_inline")
        self.assertTrue(inlined, "render's substitution dict changed shape — this guard is vacuous")
        payloads = set(inlined) - self.NOT_DATA
        self.assertIn("__DATA__", payloads, "the ledger payload vanished — the guard went vacuous")
        not_inlined = sorted(k for k in payloads if not inlined[k])
        self.assertEqual(not_inlined, [], f"{not_inlined} reaches the script without `_inline`")

    def test_every_placeholder_the_template_carries_is_substituted(self):
        """The other direction, and it is not decoration: `render` raises `KeyError` on an unknown
        placeholder, so a `__FOO__` added to the template and not to the dict does not survive into
        the page as text — it takes the whole render down. Held here so the failure is a named test
        rather than a stack trace in someone's MCP call."""
        placeholders = set(re.findall(r"__[A-Z_]+__", mapmod._TEMPLATE))
        tree = self._module()
        render = next(n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == "render")
        values = next(node for node in ast.walk(render) if isinstance(node, ast.Dict))
        keys = {k.value for k in values.keys if isinstance(k, ast.Constant)}
        self.assertEqual(placeholders - keys, set(),
                         "a placeholder in the template that `render` does not substitute")

    def test_the_two_javascript_line_terminators_do_not_reach_the_script_raw(self):
        led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))
        title = "line \u2028 sep \u2029 para"
        led.add_pin(kind="other", kind_detail="renderer", title=title, severity="low",
                    confidence="inferred", provenance=[{"source": "recon", "detail": "x"}],
                    as_is={"payload": "\u2029 leading"})
        html = mapmod.render(led.data, title="separators")
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        for char in ("\u2028", "\u2029"):
            self.assertNotIn(char, script,
                             "a raw JS line terminator is inside the inline script")
        # ...and the escape did not lose the data, which is what makes it an escape
        payload = json.loads(html.split("const LEDGER =", 1)[1].split(";\n", 1)[0]
                             .replace("\\u003c", "<"))
        self.assertEqual(payload["pins"][0]["title"], title)
        self.assertEqual(payload["pins"][0]["as_is"]["payload"], "\u2029 leading")


class TestEveryClosedTableThePageReadsIsTheSchemas(unittest.TestCase):
    """`TestARungTheTableDoesNotKnow` holds ONE of the page's tables to the schema tuple it mirrors.
    Six more arrived with the envelope reader, and a hand-kept list beside the schema's is the bug
    this repo keeps finding one surface over — so they are held the same way, as keys read off the
    object literal rather than as a search for the words in the file.

    The limit is the same one that class carries: this reads our own template as text, so it proves
    the table's KEYS, not that the card renders. The rendering is the preview walk."""

    @staticmethod
    def _keys(name: str) -> set:
        """The table's TOP-LEVEL keys, by tracking brace depth rather than by indentation.

        Depth, because two of these tables hold objects and two hold strings, and a pattern tuned to
        one shape reads the other's inner keys as if they were entries — which is a guard that
        passes on the wrong set, i.e. the thing this file exists not to do.

        Comments are removed by `code_only` rather than by a branch here (2026-08-06): this walk
        carried its own `//`-skip, so two scanners in one file answered *is this a comment* their
        own way — and when the weaker of the two turned out to be wrong about nested tagged
        templates, only one of them would have been fixed. `code_only` blanks rather than deletes,
        so every offset below still names the same place in the template."""
        source = code_only(mapmod._TEMPLATE)
        start = source.index(f"const {name}={{") + len(f"const {name}=")
        depth, keys, at_key = 0, set(), False
        i = start
        while i < len(source):
            ch = source[i]
            if ch in "'\"`":
                # a string literal is not structure: a value reading "…on the path, not a
                # computation" put `not` in the key set, which is a guard passing on the wrong set
                end = source.index(ch, i + 1)
                i = end + 1
                continue
            if ch in "{[":
                depth += 1
                at_key = depth == 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1 and ch == ",":
                at_key = True
            elif depth == 1 and at_key and (ch.isalpha() or ch == "_"):
                match = re.match(r"\w+", source[i:])
                keys.add(match.group(0))
                at_key = False
                i += match.end() - 1
            i += 1
        assert depth == 0 and keys, f"the {name} table's shape changed — this guard went vacuous"
        return keys

    def test_the_verification_rungs_are_the_schemas(self):
        from ledger import VERIFICATION_RUNGS
        self.assertEqual(self._keys("VRUNG"), set(VERIFICATION_RUNGS))

    def test_the_rungs_this_page_shows_as_strong_are_the_rungs_a_pin_may_close_on(self):
        """The card's colour is a claim about whether the work is done, and `settlement_verdict`
        answers that from `_CLOSING_RUNGS`. Two lists, one question — so they are one list."""
        from ledger import _CLOSING_RUNGS
        block = re.search(r"const VRUNG=\{(.*?)\}\};", mapmod._TEMPLATE, re.S).group(1)
        strong = {m.group(1) for m in re.finditer(r"(\w+):\{[^}]*?cls:'strong'", block, re.S)}
        self.assertEqual(strong, set(_CLOSING_RUNGS))

    def test_the_settlement_table_is_the_states_an_election_produces(self):
        from ledger import _ELECTION_STATES
        self.assertEqual(self._keys("SETTLES"), set(_ELECTION_STATES))

    def test_the_resolution_modes_are_the_schemas(self):
        from ledger import RESOLUTION_MODES
        self.assertEqual(self._keys("MODE"), set(RESOLUTION_MODES))

    def test_the_readiness_verdicts_are_the_schemas(self):
        from ledger import READINESS_VERDICTS
        self.assertEqual(self._keys("READY"), set(READINESS_VERDICTS))

    def test_the_determinism_levels_are_the_schemas(self):
        from ledger import DETERMINISM
        self.assertEqual(self._keys("DET"), set(DETERMINISM))

    def test_the_trail_knows_every_kind_of_entry_the_runtime_appends(self):
        """The page read `ev_` and dropped the other five in silence. `LOG_ENTRY_PREFIXES` is the
        schema's own answer to *what may a log entry be*, and it is what a seventh kind will be
        added to — so a seventh kind arrives here rather than being skipped."""
        from ledger import LOG_ENTRY_PREFIXES
        self.assertEqual(self._keys("TRAIL"), set(LOG_ENTRY_PREFIXES))

    def test_not_knowing_is_said_in_one_sentence_and_not_two(self):
        """§16's finding was a residue: the rung case got three states and a sentence about a schema
        that grew after the page was written; the settlement case, added in the same version, took
        the older two-state shape and printed a bare token in the card's key position. What is
        shared is the SENTENCE — `unknownNote` — and deliberately not the tables, which answer
        different questions off one event."""
        body = mapmod._TEMPLATE
        self.assertEqual(body.count("function unknownNote("), 1)
        callers = set(re.findall(r"unknownNote\('([a-z ]+)'", body))
        self.assertLessEqual({"rung", "settled state", "verification rung", "resolution mode",
                              "readiness verdict", "log entry",
                              # 2026-08-06: the verification card printed an unrecognised determinism
                              # level BARE — §16's exact finding, still live one field over, and it
                              # went through `detRow` the moment five more determinism rows needed
                              # the same sentence.
                              "determinism level"}, callers)


class TestTheWholeEnvelopeHasAReader(unittest.TestCase):
    """Eight fields and five of the six log kinds were WRITTEN by the runtime and read by nothing.
    Two were load-bearing rather than decorative: `verification` is what `settlement_verdict` reads
    to decide whether ANY pin may close, and `remediation` is the other half of the same gate — so
    the reader who asks *why will this pin not close* had nowhere to look but the JSON.

    Two halves, because either alone is vacuous: the template must REFERENCE the field (§14's own
    method — `p.<field>`, not a word search), and the preview fixture must CARRY it, or the browser
    walk that verifies the rendering has nothing to look at.

    **The reference half was itself a word search until 2026-08-06**, which is the third instance of
    §18's own class — a gate whose name quantifies over more than its body does. It asserted
    `p.<field>` against the RAW template, and a comment naming the field satisfies that exactly as
    a reader does: the check passed on a page with no reader at all. It now runs over `code_only`,
    and both halves of that claim are planted below rather than argued."""

    FIELDS = ("verification", "resolution_mode", "brainstorm", "remediation", "premortem",
              "readiness", "evidence", "cross_derivations")

    @staticmethod
    def _fixture() -> dict:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import preview_map
        return preview_map.build().data

    def test_every_envelope_field_is_read_by_the_page(self):
        code = code_only(mapmod._TEMPLATE)
        for field in self.FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"p.{field}", code,
                              f"`{field}` is stored, gated on, and on this page nowhere")

    def test_the_strip_leaves_no_comment_marker_and_no_landmark_behind(self):
        """The scanner's own premise, checked rather than trusted — the house rule for a guard that
        parses something. A mis-tracked string swallows a comment and leaves its `//` standing (the
        nested-template bug did exactly that, 30 times), and an over-eager strip eats code, so both
        directions are asserted: no marker survives, and the landmarks that must do, do."""
        code = code_only(mapmod._TEMPLATE)
        for marker in ("//", "/*", "*/"):
            self.assertNotIn(marker, code,
                             f"`{marker}` survived the strip — a string was mis-tracked, so some "
                             f"comment is still being read as code by every check below")
        for landmark in ("function modeLine(p){", "const MODE={", "const ASKABLE = new Set(",
                         "function detail(p){"):
            self.assertIn(landmark, code, f"the strip ate {landmark!r} — it is removing code")
        self.assertEqual(len(code.splitlines()), len(mapmod._TEMPLATE.splitlines()),
                         "comments are blanked, never deleted: every offset must still name the "
                         "same place in the template")

    def test_the_reference_check_is_not_satisfied_by_a_comment(self):
        """Planted both ways, because either alone proves nothing.

        1. Break the only reader (`p.premortem` -> `p['premortem']`) — the check must catch it.
        2. Then add a COMMENT naming the field — the raw-template check goes green again on a page
           that still has no reader, and this one must not.
        """
        broken = mapmod._TEMPLATE.replace("p.premortem", "p['premortem']")
        self.assertNotIn("p.premortem", code_only(broken),
                         "the planted break was not caught — this gate is vacuous")
        commented = broken.replace("function premortemCard(p){",
                                   "// p.premortem is read below\nfunction premortemCard(p){")
        self.assertIn("p.premortem", commented,
                      "the plant did not reproduce the old body's failure mode")
        self.assertNotIn("p.premortem", code_only(commented),
                         "a comment naming the field satisfied the check — which is the finding")

    #: 2026-08-06 — the six the schema gate found write-only on the day it learned to tell a reader from
    #: a writer (§15). Nested rather than pin-level, so the template reference is `<obj>.<field>`
    #: and the fixture probe is the KEY, wherever in the pin it sits. Two of them are one half of a
    #: determinism pair the spec says is "never merged into one score" — a rule about a surface,
    #: kept by no surface: this page printed `verification.determinism` and dropped all five others,
    #: which is merging by omission.
    NESTED = {"independence_determinism": "x.independence_determinism",
              "agreement_determinism": "x.agreement_determinism",
              "evidence_determinism": "r.evidence_determinism",
              "open_pins_in_zone": "ev.open_pins_in_zone",
              "untested_files": "ev.untested_files",
              "coupled_outside_zone": "ev.coupled_outside_zone"}

    @staticmethod
    def _keys(obj) -> set:
        """Every key anywhere inside a stored object — the carrier, not a rendering of it."""
        found = set()
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                found |= set(cur)
                stack += list(cur.values())
            elif isinstance(cur, list):
                stack += cur
        return found

    def test_the_preview_fixture_carries_each_of_them(self):
        pins = self._fixture()["pins"]
        for field in self.FIELDS:
            with self.subTest(field=field):
                self.assertTrue(any(not _is_blank(p.get(field)) for p in pins),
                                f"no fixture pin carries `{field}` — the browser walk cannot see it")

    def test_every_nested_field_the_gate_found_is_read_and_carried(self):
        pins = self._fixture()["pins"]
        code = code_only(mapmod._TEMPLATE)
        carried = set().union(*(self._keys(p) for p in pins)) if pins else set()
        for field, reference in sorted(self.NESTED.items()):
            with self.subTest(field=field):
                self.assertIn(reference, code,
                              f"`{field}` is written by the runtime and read by this page nowhere")
                self.assertIn(field, carried,
                              f"no fixture pin carries `{field}` — the row is verified by nobody")

    def test_the_preview_fixture_carries_every_kind_of_log_entry(self):
        from ledger import LOG_ENTRY_PREFIXES
        ids = [str(e.get("id", "")) for e in self._fixture()["decision_log"]]
        missing = [p for p in LOG_ENTRY_PREFIXES if not any(i.startswith(p) for i in ids)]
        self.assertEqual(missing, [], f"no fixture entry of kind {missing} — the trail card's rows "
                                      "for those kinds are verified by nobody")

    def test_the_fixture_carries_all_three_resolution_modes(self):
        """`proposed_default` is the one that changes what a reader must do NOW, and until this
        fixture called `assign_resolution_modes` nothing in it carried that mode at all — which is
        why the state could not be seen in a browser and the gap went unfound for a version.

        The second assertion used to say *on an OPEN pin*, which was the page's old condition and
        the page's old condition was wrong: it printed the funnel's countdown on six `detected`
        pins, none of which the interview reads and none of which poses a fork. So the fixture is
        held to the condition the page now uses — `ledger.INTERVIEW_STATES` plus a fork — because a
        fixture that satisfies a weaker predicate than the surface proves nothing about it."""
        from ledger import INTERVIEW_STATES, RESOLUTION_MODES
        pins = self._fixture()["pins"]
        self.assertLessEqual(set(RESOLUTION_MODES), {p.get("resolution_mode") for p in pins})
        reachable = {p.get("resolution_mode") for p in pins
                     if p.get("state") in INTERVIEW_STATES
                     and ((p.get("question") or {}).get("options") or [])}
        self.assertLessEqual(set(RESOLUTION_MODES), reachable,
                             "a resolution mode whose sentence the browser walk cannot reach")

    def test_the_fixture_carries_a_pin_the_interview_cannot_reach(self):
        """The other half of the same line, and the one that was being lied to: a pin carrying a
        mode that no interview will ever act on. It must be in the fixture, or the sentence that
        replaced the countdown is verified by nobody."""
        from ledger import INTERVIEW_STATES, SETTLED_STATES
        stuck = [p for p in self._fixture()["pins"]
                 if p.get("resolution_mode")
                 and p.get("state") not in SETTLED_STATES
                 and (p.get("state") not in INTERVIEW_STATES
                      or not ((p.get("question") or {}).get("options") or []))]
        self.assertTrue(stuck, "no fixture pin carries a mode the interview cannot act on — the "
                               "browser walk cannot see the sentence that says so")

    def test_the_fixture_carries_a_settled_state_the_page_cannot_describe(self):
        """§16's worked example, the same shape as the `oracle` rung one field over."""
        from ledger import _ELECTION_STATES
        settles = {e.get("settles_as") for e in self._fixture()["decision_log"]
                   if str(e.get("id", "")).startswith("ev_")}
        self.assertTrue(settles - set(_ELECTION_STATES) - {None},
                        "no fixture event carries an unknown `settles_as` — the fix is unlookable-at")


def _is_blank(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


class TestARefutationIsShownWhileItStandsAndNotAfter(unittest.TestCase):
    """The card had the field and not the rule.

    `blocked_by` is HISTORY by design — `resolve` keeps it verbatim so *"it was blocked, then it was
    observed"* survives as the sequence it is — and the page printed it as a present-tense verdict on
    any pin that carried it. On the most ordinary lifecycle in the package (work blocked, blocker
    lifted, work observed, pin closed) a reader was told `resolved` and *"⚠ this pin cannot close"*
    in the same card, and after the incident arc *"nothing has been observed since"* sat directly
    under the observation that closed the pin.

    `ledger.refuted_claim` is the predicate that answers it, it already existed, and this surface was
    not among its callers. So the assertion is on the DERIVATION, in Python, for the reason
    `derived_rungs` gives: one implementation of the rule, reachable without a browser. The browser
    check is `scripts/preview_map.py` item 20 and it is not a substitute for this — nor this for it.
    """

    def _pin(self, state, rung, blocked_by):
        return {"id": "pin_0001", "kind": "defect", "title": "t", "severity": "high",
                "state": state, "verification": {"rung": rung, "blocked_by": blocked_by}}

    def test_a_standing_refutation_is_reported(self):
        data = {"pins": [self._pin("correctness_unknown", None, "no way to replay a signed webhook")]}
        self.assertEqual(mapmod.refuted_claims(data),
                         {"pin_0001": "no way to replay a signed webhook"})

    def test_an_answered_one_is_not(self):
        # the rung above it is what answered it; the words stay on the pin as history
        data = {"pins": [self._pin("resolved", "observed", "no way to replay a signed webhook")]}
        self.assertEqual(mapmod.refuted_claims(data), {},
                         "a resolved pin was told it cannot close, by the field that says it once "
                         "could not")

    def test_the_page_reads_the_derivation_and_does_not_re_derive_it(self):
        """The other half of the same rule: a page that asks `v.blocked_by` directly has re-derived
        the fact from one of its two carriers, which is exactly how this bug was written."""
        code = code_only(mapmod._TEMPLATE)
        self.assertIn("REFUTED", code, "the page must read the computed derivation")
        self.assertNotIn("cannot close: ${v.blocked_by}", code,
                         "the warning may not be driven by `blocked_by` alone — it is history")

    def test_the_fixture_carries_both_so_the_browser_walk_has_something_to_look_at(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import preview_map
        data = preview_map.build().data
        standing = mapmod.refuted_claims(data)
        answered = [p for p in data["pins"]
                    if isinstance(p.get("verification"), dict)
                    and p["verification"].get("blocked_by")
                    and p["id"] not in standing]
        self.assertTrue(standing, "no pin in the preview fixture carries a standing refutation")
        self.assertTrue(answered, "no pin in the preview fixture carries an ANSWERED one — the "
                                  "case this test exists for renders nowhere")


class TestLiveMode(unittest.TestCase):
    """live=True turns the map into a self-reloading dev monitor; live=False (the default) stays the
    frozen single-file artifact. The self-contained invariant must survive live mode."""

    def test_default_is_frozen(self):
        html = mapmod.render(demo_ledger().data, title="demo")
        self.assertNotIn("livebadge", html)
        self.assertNotIn("location.reload", html)

    def test_live_adds_self_reload_and_badge(self):
        html = mapmod.render(demo_ledger().data, title="demo", live=True)
        self.assertIn("livebadge", html)        # the LIVE badge
        self.assertIn("location.reload", html)  # the self-reload loop
        self.assertIn("decmap.live", html)      # selection/view/state persisted across reload

    def test_live_stays_self_contained(self):
        # the whole point of the map: even live, one offline file with no external fetch
        html = mapmod.render(demo_ledger().data, title="demo", live=True)
        for pattern in (r'src\s*=\s*["\']https?:', r'href\s*=\s*["\']https?:', r'@import', r'fetch\('):
            self.assertIsNone(re.search(pattern, html),
                              f"live mode introduced an external resource: {pattern!r}")
        self.assertTrue(html.lstrip().lower().startswith("<!doctype html>"))

    def test_render_file_live_flag(self):
        led = demo_ledger(); led.save()
        out_path = os.path.join(tempfile.mkdtemp(), "map.html")
        mapmod.render_file(led.path, out_path, live=True)
        with open(out_path, encoding="utf-8") as fh:
            self.assertIn("livebadge", fh.read())


if __name__ == "__main__":
    unittest.main()
