"""Smoke-test the FastMCP adapter the way a host actually reaches it: `uv run --script`.

Scope is deliberately narrow. The protocol is FastMCP's job — testing its handshake would just
re-test a dependency, and the first cut of this server proved the cost of owning that: it hand-
rolled `initialize`/`ping`, which the 2026-07-28 revision deletes outright. What is ours, and what
this asserts, is: the PEP 723 block resolves, the server starts, and every tool we registered is
actually advertised. Tool *behaviour* is tested in test_mcp_tools.py with no dependencies at all.

Skips when uv is absent — which is the real deployment risk, so the skip message names it: without
uv the host cannot spawn the server and the tools go missing with no error surfaced to the agent.
uv is a hard prerequisite now (the CLI floor was removed; bootstrap.sh aborts without it), so this
skip marks an environment that must be fixed, not a soft fallback.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

SERVER = os.path.join(os.path.dirname(__file__), "..", "src", "mcp", "server.py")

# The COMPLETE inventory of what the adapter advertises. If a tool silently stops being registered,
# the capability becomes invisible to the agent again — which is the whole gap this server exists to
# close.
#
# Asserted as set EQUALITY, not containment, and that is the load-bearing part. As a subset this list
# guarded only the tools someone remembered to add: five (`spend_report`, `design_scan`,
# `generate_tokens`, `tokens_diff`, `extract_tokens`) were advertised by the server for months with no
# guard at all, because nothing forced the list to grow. Equality makes adding a tool here part of
# adding a tool — the small friction is the mechanism, not a side effect of it.
#
# Safe to assert because registration is unconditional: every `@mcp.tool` decoration sits at module
# level in server.py, so `tools/list` is deterministic. A tool registered behind an `if` would have to
# be handled explicitly rather than by loosening this back to a subset. (This line used to state the
# count — "all 34" against a server that then served 54. A number written beside a list that already
# states it is a second carrier for one fact, and it drifted the first time the list grew, silently,
# because nothing reads a comment. `len(EXPECTED_TOOLS)` is the count, and it cannot be wrong.)
EXPECTED_TOOLS = {
    "ledger_summary", "interview_next", "contract_diff", "reconcile_layers", "blast_radius",
    "propose_correspondence",
    "generate_layers", "findings_gate", "build_waves", "challenge_oracle", "render_map",
    "coverage_gaps",
    # non-electing ledger writes; decide/accept stay human-only and are deliberately NOT here
    "ledger_add_pin", "ledger_surface_assumption", "ledger_add_remediation",
    "ledger_set_remediation_status", "ledger_resolve", "ledger_defer",
    "ledger_mark_correctness_unknown", "ledger_set_readiness",
    # comprehension / understand-mode (the structural-graph family)
    "build_graph", "understand_codebase", "explain_node", "graph_query", "guided_tour",
    "domain_view", "fingerprint_scan", "graph_map", "impact_overlay", "docs_claims",
    # the instruction-file carrier — the ledger projected into the file every host actually loads
    "generate_instructions", "instructions_diff",
    # the election: creating the forks, offering the opening policies, and recording the human's
    # answer to one. `interview_seed_policies` is its own tool and not a step inside
    # `interview_expand` — the two run together at frame time, but a tool named "expand" must not
    # also do a thing its name does not say.
    "interview_expand", "interview_seed_policies", "ledger_record_decision",
    # the policy step of the same funnel: what a rule would decide (read), and the election that
    # sets it and cascades it (write). `add_policy`/`apply_policies` had no surface at all, while
    # the playbooks told an agent the user elects a policy and that it then cascades.
    "policy_preview", "ledger_record_policy",
    # design contract (DTCG) + the frontend/design scanner
    "generate_tokens", "tokens_diff", "extract_tokens", "design_scan",
    # cost & token telemetry — the measurer's surface
    "spend_report",
    # landing-zone readiness: D0 evidence (read-only) + the D2 verdict (write)
    "readiness_assess",
    # v0.9 — the agent-ready gate (D0 presence) and the challenger's premortem queue
    "agent_ready", "ledger_premortem", "ledger_label_failure",
    # new carriers: git history as an independent signal, and the cross_derived rung
    "cochange_omissions", "scope_check", "ledger_cross_derive",
    # docs as a governed surface: the publication direction + the catalog
    "doc_register", "doc_freshness",
    # hygiene: which rules were in force, whether a skill drifted, whether a rule keeps being wrong
    "generator_observe", "generator_screen",
    # learning that only ever produces checks, never stored beliefs
    "learning_report",
}
WRITE_TOOLS = {
    "generate_layers", "render_map", "generate_instructions", "generate_tokens",
    "ledger_add_pin", "ledger_surface_assumption", "ledger_add_remediation",
    "ledger_set_remediation_status", "ledger_resolve", "ledger_defer",
    "ledger_mark_correctness_unknown", "ledger_set_readiness",
    "ledger_premortem", "ledger_label_failure", "ledger_cross_derive", "doc_register",
    "generator_observe", "interview_expand", "ledger_record_decision", "ledger_record_policy",
    "build_graph", "understand_codebase", "fingerprint_scan", "graph_map",
}
READ_ONLY = EXPECTED_TOOLS - WRITE_TOOLS


NEEDS_UV = unittest.skipIf(
    shutil.which("uv") is None,
    "uv not on PATH — the host cannot spawn the MCP server, and its tools would be silently "
    "absent. uv is a hard prerequisite; bootstrap.sh installs it and aborts if it cannot.")


class _Session(unittest.TestCase):
    """One server session over real stdio, reused across a class's assertions (cold uv is ~7s).

    Subclasses vary `CAPABILITIES`, because what this fake client declares in `initialize` is what
    the server reads to decide whether it may ask the user directly. That makes both rungs of
    `ledger_record_decision` testable here, with no host in the loop.
    """

    #: What this fake client declares in `initialize`. The server reads it to decide whether it may
    #: ask the user directly, so declaring nothing here is what exercises the relay path.
    CAPABILITIES: dict = {}
    #: Reply to a server->client `elicitation/create`, or None to fail loudly on one.
    ELICIT_REPLY: dict | None = None

    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen(
            ["uv", "run", "--script", SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
            # Don't let the server's best-effort grammar warm-up fetch in the background here — it
            # would race test_treesitter's `available()` probes and flake the suite. Prod still warms.
            env={**os.environ, "CODEBASE_ALIGNMENT_SKIP_WARM": "1"},
        )
        cls._id = 0
        cls.elicited = []
        # Drain stderr continuously. It used to be read only when the stream closed, which is fine
        # until a tool raises: FastMCP logs the traceback, a few KB fills the OS pipe buffer, and
        # the server BLOCKS on its own stderr write — so it never answers, and `readline()` below
        # waits forever with no timeout to save it. The first test to exercise a refusal hung the
        # whole suite. Kept, not discarded: the text is still what the failure messages quote.
        cls._stderr = []
        cls._drain = threading.Thread(target=cls._pump_stderr, daemon=True)
        cls._drain.start()
        try:
            cls._request("initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": cls.CAPABILITIES,
                "clientInfo": {"name": "keel-tests", "version": "1"},
            })
            cls._notify("notifications/initialized")
            listing = cls._request("tools/list", {})
        except Exception:
            cls.tearDownClass()
            raise
        cls.tools = {t["name"]: t for t in listing["result"]["tools"]}

    @classmethod
    def tearDownClass(cls):
        if cls.proc.poll() is None:
            cls.proc.stdin.close()
            try:
                cls.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                cls.proc.kill()

    @classmethod
    def _pump_stderr(cls):
        for line in cls.proc.stderr:
            cls._stderr.append(line)

    @classmethod
    def _stderr_text(cls) -> str:
        return "".join(cls._stderr[-40:])

    @classmethod
    def _send(cls, payload):
        cls.proc.stdin.write(json.dumps(payload) + "\n")
        cls.proc.stdin.flush()

    @classmethod
    def _notify(cls, method, params=None):
        cls._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    @classmethod
    def _request(cls, method, params):
        cls._id += 1
        cls._send({"jsonrpc": "2.0", "id": cls._id, "method": method, "params": params})
        while True:
            line = cls.proc.stdout.readline()
            if not line:
                raise AssertionError(
                    "server closed the stream — the PEP 723 block failed to resolve, or the "
                    f"server crashed. stderr:\n{cls.proc.stderr.read()}"
                )
            msg = json.loads(line)
            if msg.get("method") == "elicitation/create" and "id" in msg:
                # The server is asking the USER something, mid-call. A client that declares the
                # capability and then ignores the request would deadlock the tool, so answering it
                # is part of being this client — and it is what lets the strong rung be tested
                # end to end with no host involved.
                cls.elicited.append(msg["params"])
                if cls.ELICIT_REPLY is None:
                    raise AssertionError(
                        "the server elicited from a client that declared no elicitation capability")
                cls._send({"jsonrpc": "2.0", "id": msg["id"], "result": cls.ELICIT_REPLY})
                continue
            if msg.get("id") == cls._id:   # skip any notifications interleaved on the wire
                return msg


@NEEDS_UV
class TestServerAdvertisesItsTools(_Session):
    """The relay rung: a client that declares nothing, so the server must not try to ask."""

    def test_the_advertised_set_is_exactly_the_inventory(self):
        """Both directions, because they are different bugs.

        Missing = a capability went invisible to the agent (the regression this file exists for).
        Extra = a tool was added and the inventory was not, so it silently has no guard — which is
        how five of them went unguarded until someone read this comment against the server.
        """
        advertised = set(self.tools)
        self.assertEqual(EXPECTED_TOOLS - advertised, set(),
                         "registered tools missing from tools/list — the agent can no longer see them")
        self.assertEqual(advertised - EXPECTED_TOOLS, set(),
                         "server.py advertises tools this inventory does not list. Add them to "
                         "EXPECTED_TOOLS (and to WRITE_TOOLS if they write), so they are guarded too")

    def test_every_tool_carries_a_description_and_object_schema(self):
        for name in sorted(EXPECTED_TOOLS):
            with self.subTest(tool=name):
                t = self.tools[name]
                self.assertTrue((t.get("description") or "").strip(),
                                "a tool with no description is undiscoverable — the agent picks by it")
                self.assertEqual(t["inputSchema"]["type"], "object")

    def test_read_write_split_is_visible_to_the_host(self):
        # "Serialized writing, parallel reading" is the roster's central property. Annotations are
        # where a host can see it, instead of it living only in prose.
        for name in sorted(READ_ONLY):
            with self.subTest(tool=name):
                self.assertTrue(self.tools[name]["annotations"]["readOnlyHint"])
        for name in sorted(WRITE_TOOLS):
            with self.subTest(tool=name):
                self.assertFalse(self.tools[name]["annotations"]["readOnlyHint"],
                                 "a write tool must not claim to be read-only")

    def test_no_tool_elects_on_its_own_authority(self):
        # Electing stays the human's job. What the surface offers is a way to RECORD an election —
        # `ledger_record_decision`, which can only write an outcome the pin's own question offered.
        self.assertNotIn("ledger_decide", self.tools)
        self.assertNotIn("ledger_accept", self.tools)

    def test_the_cross_layer_core_answers_over_the_wire(self):
        """The regression that costs the most to miss, exercised where it actually broke.

        `contract_diff` and `reconcile_layers` are the cross-layer core, and both were unreachable
        over MCP for months: annotated `-> dict`, returning `shapes`' bare `list[dict]`, so FastMCP's
        derived output_schema rejected every payload — the empty one too. Nothing caught it, because
        the behaviour tests call `tools.contract_diff(...)` in-process (a list is fine there) and
        this file only ever read `inputSchema`. A declared output type is only true on the wire, so
        it gets asserted on the wire. `test_mcp_output_contracts.py` guards the whole class
        statically; this proves the instance end to end.
        """
        step0 = os.path.join(os.path.dirname(__file__), "fixtures", "step0")
        for name, args in (
            ("contract_diff", {"contract": os.path.join(step0, "contract.json"),
                               "ddl": os.path.join(step0, "001_initial.sql")}),
            ("reconcile_layers", {"layer_a": "ddl", "path_a": os.path.join(step0, "001_initial.sql"),
                                  "layer_b": "sqlalchemy", "path_b": os.path.join(step0, "models.py")}),
        ):
            with self.subTest(tool=name):
                res = self._request("tools/call", {"name": name, "arguments": args})
                self.assertNotIn("error", res, f"{name} failed at the JSON-RPC layer: {res.get('error')}")
                result = res["result"]
                self.assertFalse(
                    result.get("isError"),
                    f"{name} returned a tool error over the wire: "
                    f"{[c.get('text') for c in result.get('content', [])]}")
                structured = result.get("structuredContent")
                self.assertIsInstance(structured, dict,
                                      "structuredContent must be a JSON object — a bare list is "
                                      "rejected by the host before the agent sees any of it")
                self.assertIn("findings", structured)
                self.assertEqual(structured["findings"], [],
                                 "the step-0 fixtures are aligned: zero drift is the expected answer, "
                                 f"got {structured['findings']}")

    def test_schemas_are_derived_from_the_signatures(self):
        diff = self.tools["contract_diff"]["inputSchema"]
        self.assertIn("contract", diff["properties"])
        self.assertIn("contract", diff.get("required", []))
        for optional in ("ddl", "sqlalchemy", "typescript", "drizzle", "graphql"):
            self.assertIn(optional, diff["properties"])
            self.assertNotIn(optional, diff.get("required", []),
                             "a layer that may be absent must not be required")


if __name__ == "__main__":
    unittest.main()


DESIGN_CONCERN = {
    "kind": "design_concern", "title": "three near-identical blocks", "severity": "low",
    "confidence": "inferred", "provenance": [{"source": "recon", "detail": "clones"}],
    "as_is": {"current_design": "copy-paste", "concern": "they drift"},
    "question": {"prompt": "Consolidate them?",
                 "options": [{"id": "keep", "label": "leave it", "implication": "drift stays possible"},
                             {"id": "extract", "label": "extract a helper", "implication": "one call shape"}],
                 "allow_freeform": False},
}


def _seeded_ledger(session, tmp):
    """A pin with a real fork on it, created over the wire like an agent would."""
    path = os.path.join(tmp, "ledger.json")
    res = session._request("tools/call", {"name": "ledger_add_pin",
                                          "arguments": {"ledger": path, **DESIGN_CONCERN}})
    return path, res["result"]["structuredContent"]["pin_id"]


@NEEDS_UV
class TestRecordingAnElectionByRelay(_Session):
    """No elicitation capability declared, so the agent must relay — and be held to it.

    `ELICIT_REPLY` stays None: if the server tried to ask this client anyway, the harness fails
    loudly rather than deadlocking on a request that would never be answered.
    """

    def test_the_outcome_must_come_from_the_pins_own_question(self):
        tmp = tempfile.mkdtemp()
        path, pin_id = _seeded_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_decision", "arguments": {
            "ledger": path, "pin_id": pin_id, "option_id": "rewrite_in_rust",
            "rationale": "r", "flip_criteria": "f", "human_answer": "do that"}})
        self.assertTrue(res["result"].get("isError"),
                        "an agent must not be able to write an outcome the interview never offered")

    def test_a_relayed_decision_is_recorded_with_the_words_it_rests_on(self):
        tmp = tempfile.mkdtemp()
        path, pin_id = _seeded_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_decision", "arguments": {
            "ledger": path, "pin_id": pin_id, "option_id": "extract",
            "rationale": "one call shape beats three", "human_answer": "yes, pull the helper out",
            "flip_criteria": "if a second caller shape appears"}})
        self.assertFalse(res["result"].get("isError"), res["result"].get("content"))
        out = res["result"]["structuredContent"]
        self.assertEqual((out["state"], out["outcome"], out["evidence"]),
                         ("decided", "extract", "transcribed"))
        self.assertEqual(self.elicited, [], "the server must not ask a client that cannot answer")
        with open(path, encoding="utf-8") as fh:
            event = json.load(fh)["decision_log"][-1]
        self.assertEqual(event["human_answer"], "yes, pull the helper out")


@NEEDS_UV
class TestReadingALedgerWrittenBeforeTheRuleExisted(_Session):
    """v0.13, over the wire because that is where the agent reads it.

    The rung was enforced in `decide()` and nowhere else, so every ledger written before v0.11
    still carries `transcribed` on its cascades — `decide()`'s old parameter default — and this
    tool answered `{"transcribed": 1}` about decisions the user's own elected policy made. Asserted
    on `structuredContent`, not on the in-process return: the summary grew a key, and a key that
    does not survive the declared output schema reaches no agent at all.
    """

    def test_a_pre_v0_11_cascade_is_not_reported_as_a_relay(self):
        path = os.path.join(tempfile.mkdtemp(), "ledger.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"version": "0.9", "pins": [], "policies": [],
                       "decision_log": [{"id": "ev_0001", "pin_id": "pin_0001", "outcome": "db",
                                         "source": "policy:pol_0001", "evidence": "transcribed"}]}, fh)
        res = self._request("tools/call", {"name": "ledger_summary", "arguments": {"ledger": path}})
        self.assertFalse(res["result"].get("isError"), res["result"].get("content"))
        out = res["result"]["structuredContent"]
        self.assertEqual(out["decisions_by_evidence"], {"cascaded": 1})
        # and the file is not restamped into claiming a version its content does not satisfy
        self.assertEqual((out["version"], out["pre_rule_events"]), ("0.9", {"cascade_rung": 1}))


CLUSTERED = {
    "kind": "contract_mismatch", "title": "role enum drift", "severity": "low",
    "confidence": "extracted", "provenance": [{"source": "recon", "detail": "shape diff"}],
    "cluster_id": "cl_shape", "as_is": {"db": "enum", "api": "string"},
    # The fork the policy answers. A cascade may only write an outcome the pin's OWN question
    # offers (v0.12), so these pins have to pose one — a cluster of question-less pins is not one
    # decision, and no policy cascades over it.
    "question": {"prompt": "Which layer is truth?",
                 "options": [{"id": "db", "label": "the DB"},
                             {"id": "api", "label": "the API"}]},
}


def _clustered_ledger(session, tmp):
    """Two pins under one cluster_id — the population a policy elects over."""
    path = os.path.join(tmp, "ledger.json")
    for i in range(2):
        session._request("tools/call", {"name": "ledger_add_pin", "arguments": {
            "ledger": path, **CLUSTERED, "title": f"role enum drift {i}"}})
    return path


@NEEDS_UV
class TestRecordingAPolicyByRelay(_Session):
    """The write half of the funnel's policy step, over the wire. It had no door at all: nothing
    created a `Policy` or ran the cascade on any host, while four shipped passages said the user
    elects one and it cascades."""

    def test_a_policy_relayed_without_a_quote_is_refused(self):
        tmp = tempfile.mkdtemp()
        path = _clustered_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_policy", "arguments": {
            "ledger": path, "rule": "the DB is truth", "default_outcome": "db",
            "applies_to": {"cluster_id": "cl_shape"}}})
        self.assertTrue(res["result"].get("isError"),
                        "one unquoted claim here would carry a whole cluster")

    def test_the_cascade_records_itself_as_a_cascade(self):
        tmp = tempfile.mkdtemp()
        path = _clustered_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_policy", "arguments": {
            "ledger": path, "rule": "the DB is truth", "default_outcome": "db",
            "applies_to": {"cluster_id": "cl_shape"},
            "human_answer": "the DB wins unless I flag one"}})
        self.assertFalse(res["result"].get("isError"), res["result"].get("content"))
        out = res["result"]["structuredContent"]
        self.assertEqual(len(out["cascaded"]), 2)
        self.assertEqual(self.elicited, [], "the server must not ask a client that cannot answer")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        event = data["decision_log"][-1]
        self.assertEqual(event["evidence"], "cascaded")
        self.assertEqual(event["policy_id"], out["policy_id"])
        self.assertEqual(data["policies"][-1]["human_answer"], "the DB wins unless I flag one")


@NEEDS_UV
class TestSettingAPolicyByElicitation(_Session):
    """The strong rung for a policy — and the refusal that matters more: a declined offer writes
    nothing. A policy nobody accepted, cascaded anyway, would settle a whole cluster on silence."""

    CAPABILITIES = {"elicitation": {}}
    ELICIT_REPLY = {"action": "accept",
                    "content": {"value": "do not set it — keep asking pin by pin"}}

    def test_a_declined_policy_writes_nothing_and_shows_the_radius(self):
        tmp = tempfile.mkdtemp()
        path = _clustered_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_policy", "arguments": {
            "ledger": path, "rule": "the DB is truth", "default_outcome": "db",
            "applies_to": {"cluster_id": "cl_shape"}, "human_answer": "the caller's own words"}})
        self.assertTrue(res["result"].get("isError"), "a declined offer is not an election")
        self.assertTrue(self.elicited, "the server never asked")
        asked = json.dumps(self.elicited[0])
        self.assertIn("pin_0001", asked,
                      "the user must be shown WHICH pins the rule would decide — the radius is "
                      "what they are electing")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["policies"], [], "a declined policy must not exist")

    def test_the_message_shows_the_outcome_it_would_write(self):
        """The blocker's other half. The message named the rule and the pin count and NOT the
        `default_outcome` — the string stamped on every one of those pins — while the user answered
        a two-value accept/decline and the write claimed the strongest rung there is. What a message
        omits was not elected, whatever the write then claims."""
        tmp = tempfile.mkdtemp()
        path = _clustered_ledger(self, tmp)
        self._request("tools/call", {"name": "ledger_record_policy", "arguments": {
            "ledger": path, "rule": "keep the DB as the source of truth", "default_outcome": "db",
            "applies_to": {"cluster_id": "cl_shape"}}})
        message = self.elicited[-1]["message"]
        self.assertIn("keep the DB as the source of truth", message)
        self.assertIn("db", message.split("Outcome written on every pin it decides:", 1)[1],
                      "the value that lands on every cascaded pin must be in front of the human")


@NEEDS_UV
class TestAcceptingAPolicyByElicitation(_Session):
    """Accepted through the host: the policy records the strong rung, and the caller's own
    `human_answer` is discarded — it never carried the answer."""

    CAPABILITIES = {"elicitation": {}}
    ELICIT_REPLY = {"action": "accept",
                    "content": {"value": "set this policy — decide the whole cluster this way"}}

    def test_the_policy_records_the_rung_the_server_earned(self):
        tmp = tempfile.mkdtemp()
        path = _clustered_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_policy", "arguments": {
            "ledger": path, "rule": "the DB is truth", "default_outcome": "db",
            "applies_to": {"cluster_id": "cl_shape"}, "human_answer": "the caller's own words"}})
        self.assertFalse(res["result"].get("isError"), res["result"].get("content"))
        self.assertEqual(res["result"]["structuredContent"]["evidence"], "elicited")
        with open(path, encoding="utf-8") as fh:
            policy = json.load(fh)["policies"][-1]
        self.assertEqual(policy["evidence"], "elicited")
        self.assertNotEqual(policy["human_answer"], "the caller's own words",
                            "the elicited answer must win over what the caller passed — otherwise "
                            "the strong rung is decoration")

    def test_an_accepted_policy_still_cannot_decide_a_pin_that_never_offered_the_outcome(self):
        """The blocker, over the wire, on the strongest rung — where it was found. The user accepts,
        so `elicited` is earned; what it does not license is the OUTCOME, which the caller composed
        and the pins never offered. Held back, not written."""
        tmp = tempfile.mkdtemp()
        path = _clustered_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_policy", "arguments": {
            "ledger": path, "rule": "keep the DB as the source of truth",
            "default_outcome": "DROP the api layer and regenerate from scratch",
            "applies_to": {"cluster_id": "cl_shape"}}})
        self.assertFalse(res["result"].get("isError"), res["result"].get("content"))
        out = res["result"]["structuredContent"]
        self.assertEqual(out["cascaded"], [])
        self.assertEqual(out["not_offered"], ["pin_0001", "pin_0002"])
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["decision_log"], [],
                         "an accepted RULE is not an accepted outcome for a pin that never "
                         "offered it — the pins stay open and get asked")
        self.assertEqual([p["state"] for p in data["pins"]], ["needs_input", "needs_input"])


@NEEDS_UV
class TestRecordingAnElectionByElicitation(_Session):
    """The strong rung, end to end: the SERVER asks, this client answers, the server writes.

    The point is what does not happen — the answer never passes through the caller. So the call
    below sends a deliberately wrong `option_id`, and the recorded outcome must be the one this
    client picked, not the one the caller asked for.
    """

    CAPABILITIES = {"elicitation": {}}
    ELICIT_REPLY = {"action": "accept", "content": {"value": "extract — extract a helper (→ one call shape)"}}

    def test_the_server_asks_the_user_and_ignores_what_the_caller_proposed(self):
        tmp = tempfile.mkdtemp()
        path, pin_id = _seeded_ledger(self, tmp)
        res = self._request("tools/call", {"name": "ledger_record_decision", "arguments": {
            "ledger": path, "pin_id": pin_id, "option_id": "keep",
            "rationale": "whatever the user says", "human_answer": "the caller's own words",
            "flip_criteria": "if a second caller shape appears"}})
        self.assertFalse(res["result"].get("isError"), res["result"].get("content"))
        out = res["result"]["structuredContent"]
        self.assertEqual(out["evidence"], "elicited")
        self.assertEqual(out["outcome"], "extract",
                         "the elicited answer must win over the caller's proposed option_id — "
                         "otherwise the strong rung is decoration")
        self.assertTrue(self.elicited, "the server never asked")
        asked = json.dumps(self.elicited[0])
        self.assertIn("extract a helper", asked, "the user was not shown the pin's real options")
