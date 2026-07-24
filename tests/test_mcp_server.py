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
# Safe to assert because registration is unconditional: all 34 `@mcp.tool` decorations sit at module
# level in server.py, so `tools/list` is deterministic. A tool registered behind an `if` would have to
# be handled explicitly rather than by loosening this back to a subset.
EXPECTED_TOOLS = {
    "ledger_summary", "interview_next", "contract_diff", "reconcile_layers", "blast_radius",
    "generate_layers", "findings_gate", "build_waves", "challenge_oracle", "render_map",
    "coverage_gaps",
    # non-electing ledger writes; decide/accept stay human-only and are deliberately NOT here
    "ledger_add_pin", "ledger_surface_assumption", "ledger_add_remediation",
    "ledger_set_remediation_status", "ledger_resolve", "ledger_defer",
    # comprehension / understand-mode (the structural-graph family)
    "build_graph", "understand_codebase", "explain_node", "graph_query", "guided_tour",
    "domain_view", "fingerprint_scan", "graph_map", "impact_overlay", "docs_claims",
    # the instruction-file carrier — the ledger projected into the file every host actually loads
    "generate_instructions", "instructions_diff",
    # design contract (DTCG) + the frontend/design scanner
    "generate_tokens", "tokens_diff", "extract_tokens", "design_scan",
    # cost & token telemetry — the measurer's surface
    "spend_report",
}
WRITE_TOOLS = {
    "generate_layers", "render_map", "generate_instructions", "generate_tokens",
    "ledger_add_pin", "ledger_surface_assumption", "ledger_add_remediation",
    "ledger_set_remediation_status", "ledger_resolve", "ledger_defer",
    "build_graph", "understand_codebase", "fingerprint_scan", "graph_map",
}
READ_ONLY = EXPECTED_TOOLS - WRITE_TOOLS


@unittest.skipIf(shutil.which("uv") is None,
                 "uv not on PATH — the host cannot spawn the MCP server, and its tools would be "
                 "silently absent. uv is a hard prerequisite; bootstrap.sh installs it and aborts if it cannot.")
class TestServerAdvertisesItsTools(unittest.TestCase):
    """One session, driven over real stdio, reused across assertions (a cold uv resolve is ~7s)."""

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
        try:
            cls._request("initialize", {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
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
            if msg.get("id") == cls._id:   # skip any notifications interleaved on the wire
                return msg

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

    def test_decide_is_not_advertised(self):
        # Electing an outcome stays the human interview's job — no MCP tool may commit a decision.
        self.assertNotIn("ledger_decide", self.tools)
        self.assertNotIn("ledger_accept", self.tools)

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
