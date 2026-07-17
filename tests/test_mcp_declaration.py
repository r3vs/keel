"""If the doctrine orders a server, the product must ship it.

The bug this locks shut: `core/knowledge-sources.md` is vendored into five skills and *orders* the
agent to ground claims via Context7 and DeepWiki — while those servers were declared only in this
repo's own root `.mcp.json`, which no user ever receives. So the package commanded a capability it
never provided. That is worse than the runtime nothing invoked: there the tool existed and went
unused; here the prose demanded a tool that was simply absent.

These assert the invariant against the doctrine's own table, not against a hardcoded list — a new
required server fails here until it is declared, which is the point.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"

# The doctrine's table is the carrier. Reading it — rather than grepping its prose for server names
# — is the whole point: "GitHub" appears in that doc twice as ordinary English (DeepWiki indexes
# *public GitHub repos*; *GitHub Advisory* is a registry), so a word-match "finds" a server nobody
# declared. That is a heuristic, and this package does not guess: correspondence comes from a
# declared fact or not at all.
REQUIRED = re.compile(r"^- `([\w-]+)` → \*\*http\*\* `(\S+)`", re.M)
OPT_IN = re.compile(r"^- `([\w-]+)` → \*\*opt-in\*\*", re.M)


def declared() -> dict:
    with open(PLUGINS / "alignment-core" / ".mcp.json", encoding="utf-8") as fh:
        return json.load(fh)["mcpServers"]


def doctrine() -> str:
    """The SHIPPED copy — what the user actually reads is what must be satisfied."""
    shipped = sorted(PLUGINS.rglob("references/core/knowledge-sources.md"))
    assert shipped, "the doctrine is not vendored into any shipped skill"
    return shipped[0].read_text(encoding="utf-8")


def mandated() -> dict:
    return dict(REQUIRED.findall(doctrine()))


def opt_in() -> set:
    return set(OPT_IN.findall(doctrine()))


class TestTheProductShipsWhatItOrders(unittest.TestCase):
    def test_the_doctrine_declares_what_it_requires(self):
        self.assertTrue(mandated(),
                        "knowledge-sources.md orders the agent to ground claims somewhere; its "
                        "table must name the servers — build.py generates .mcp.json from it")

    def test_every_mandated_server_is_declared_with_its_url(self):
        for name, url in sorted(mandated().items()):
            with self.subTest(server=name):
                self.assertIn(name, declared(),
                              "the shipped doctrine orders this server but no plugin declares it — "
                              "the package would command a capability the user does not have")
                self.assertEqual(declared()[name]["url"], url,
                                 "the declaration must match the doctrine's own table")

    def test_our_own_server_is_declared(self):
        self.assertIn("codebase-alignment", declared())

    def test_opt_in_servers_are_named_but_not_declared(self):
        # Each needs external setup (cognee a container + key, github a token). A declared-but-
        # unreachable server is a broken entry in every user's session, which is the opposite of
        # "degrade gracefully, never hard-fail".
        self.assertTrue(opt_in(), "the table should still name the opt-in servers it excludes")
        for s in sorted(opt_in() & set(declared())):
            self.fail(f"{s} needs external setup; declaring it fails to connect for everyone")

    def test_every_plugin_reaches_the_declaration(self):
        # MCP servers are session-global — but only if the plugin declaring them is installed.
        # `dependencies` is the only thing that guarantees it; there is no cross-plugin file access
        # to fall back on.
        for p in sorted(x for x in PLUGINS.iterdir() if x.is_dir()):
            with open(p / ".claude-plugin" / "plugin.json", encoding="utf-8") as fh:
                m = json.load(fh)
            with self.subTest(plugin=p.name):
                if (p / ".mcp.json").exists():
                    continue  # it declares them itself
                self.assertIn("alignment-core", m.get("dependencies", []),
                              "this plugin's skills cite the doctrine's servers but nothing "
                              "guarantees the plugin that declares them is installed")


class TestDeclarationsResolveAfterInstall(unittest.TestCase):
    def test_the_stdio_server_is_plugin_root_anchored(self):
        # The whole bug class in one assertion: a repo-relative path resolves into the USER'S
        # project, because that is what the working directory is at runtime.
        args = " ".join(declared()["codebase-alignment"]["args"])
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", args)
        self.assertNotIn("src/", args, "src/ is authoring source and never ships")

    def test_every_server_declares_a_type(self):
        # A `url` entry with no `type` is a documented config error in Claude Code.
        for name, entry in declared().items():
            with self.subTest(server=name):
                self.assertIn("type", entry)


class TestOptInIsDocumentedWhereItIsClaimed(unittest.TestCase):
    def test_project_memory_does_not_claim_cognee_is_wired(self):
        # It used to say cognee was "wired in .mcp.json / opencode.json / .codex/config.toml" —
        # naming this repo's own files, which an installed user never has.
        shipped = sorted(PLUGINS.rglob("skills/project-memory/SKILL.md"))
        self.assertTrue(shipped)
        for p in shipped:
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertNotIn("wired in `.mcp.json`", text)
                self.assertIn("docker run", text.lower(),
                              "an opt-in server must tell the reader how to turn it on")


if __name__ == "__main__":
    unittest.main()
