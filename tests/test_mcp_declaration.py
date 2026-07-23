"""If the doctrine orders a server, the **install** must deliver it.

`core/knowledge-sources.md` is vendored into five skills and *orders* the agent to ground claims via
Context7 and DeepWiki. Those servers were declared in this repo's own root `.mcp.json`,
`opencode.json` and `.codex/config.toml` — and the fix that "shipped" them only covered Claude Code.

The root files were the whole bug, in two layers:

1. **A user installing a plugin never works in this repo — they work in their own.** So root host
   config reaches nobody. The docs papered over that by telling users to *"open the repo (or add it
   to your workspace root)"* and copy servers out of `.mcp.json`. That is not installing a plugin;
   it is cloning a demo. `scripts/install.sh` said the same thing out loud, in a heredoc: *copy the
   mcpServers block into your opencode.json*.
2. **Three hand-written copies of one fact drift, and had already drifted**: deepwiki was in
   `.mcp.json` but missing from Codex; `opencode.json` and `.codex/config.toml` both declared cognee
   `enabled: true`, which the doctrine forbids precisely because it cannot connect without a
   container; Codex pulled context7 over `npx` while the others used http.

Delivery is now the install itself, generated from the doctrine's one table, on every host that can
take it — verified in each host's source, not assumed: Claude Code reads the plugin's own
`.mcp.json`; Codex's manifest points at the same file (`resolve_manifest_mcp_servers`); opencode has
no manifest slot but a plugin's `config(cfg)` hook may mutate the live merged config.

That Codex citation used to read `PluginManifestMcpServers::Path` — the type that HOLDS the value
rather than the function that CONSUMES it. The type accepts any `String`; the resolver accepts only
a `./`-prefixed one, and drops the rest with a `tracing::warn`. So this suite asserted, for months,
that Codex reached a file Codex never opened. `test_codex_manifest.py` holds that shut now; the
lesson it carries is the general one: **cite consumers, never types.**

These assert against the doctrine's table, never a hardcoded list — a new required server fails here
until every host's delivery carries it, which is the point.
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
    with open(PLUGINS / "keel-core" / ".mcp.json", encoding="utf-8") as fh:
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
        self.assertIn("keel", declared())

    def test_the_playwright_capability_server_is_declared(self):
        # Browser verification (references/browser-verification.md) is a CAPABILITY, not a knowledge
        # source — so Playwright's MCP is declared beside keel, NOT via the doctrine
        # table. It earns a default declaration because it CONNECTS with zero setup (stdio via npx, no
        # container/key, unlike the opt-in cognee); it only degrades on a browser action without
        # `npx playwright install`. That is the real declared-vs-opt-in line.
        d = declared()
        self.assertIn("playwright", d)
        self.assertEqual(d["playwright"]["type"], "stdio")
        self.assertNotIn("playwright", mandated(), "it is a capability, not a knowledge-table server")
        self.assertNotIn("playwright", opt_in(), "it connects with zero setup — it is not opt-in")

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
                self.assertIn("keel-core", m.get("dependencies", []),
                              "this plugin's skills cite the doctrine's servers but nothing "
                              "guarantees the plugin that declares them is installed")


class TestTheRootDeclaresNoHostConfig(unittest.TestCase):
    """The root is for developing this repo. Delivery is the install, or it does not exist."""

    # Each of these was a real file, and each looked like product because the docs used it as
    # product. Re-adding one is how the bug comes back: it works here, on the one machine where
    # nothing is installed, and reaches no user anywhere.
    FORBIDDEN = (".mcp.json", "opencode.json", ".codex/config.toml")

    def test_no_root_file_declares_mcp_servers(self):
        for f in self.FORBIDDEN:
            with self.subTest(file=f):
                self.assertFalse(
                    (ROOT / f).exists(),
                    f"{f} is host config for THIS repo; a user installing a plugin works in their "
                    "own project and never sees it. Declare servers where the install delivers "
                    "them: plugins/*/.mcp.json (Claude + Codex) and the opencode plugin's config() "
                    "hook — both generated from src/core/knowledge-sources.md",
                )

    # NOT here, deliberately: a check that no doc still says "open the repo" / "point it at the
    # repo" — the sentences that made root config look like a delivery mechanism for two whole
    # hosts. It was written, and it failed on the very prose that RETIRES those sentences by
    # quoting them. Prose-matching cannot tell use from mention, so it can only false-positive or
    # be watered down until it proves nothing. That is a heuristic, and this package does not
    # guess. The deterministic carrier is above: the files are gone, so no doc can send a user to
    # them and be right.


class TestEveryHostGetsThemFromItsInstall(unittest.TestCase):
    """Same table, three hosts, zero user action. The shapes differ; the fact does not."""

    def opencode_plugin(self) -> str:
        p = PLUGINS / "keel-core" / "adapters" / "opencode" / "plugin" / "mcp.ts"
        self.assertTrue(p.is_file(), "opencode's MCP delivery is a generated plugin file")
        return p.read_text(encoding="utf-8")

    def test_the_opencode_plugin_carries_every_mandated_server(self):
        ts = self.opencode_plugin()
        for name, url in sorted(mandated().items()):
            with self.subTest(server=name):
                self.assertIn(url, ts, "the doctrine mandates this server but opencode never gets it")

    def test_the_opencode_plugin_carries_the_playwright_capability(self):
        # the capability server reaches opencode too, in opencode's local/array shape
        ts = self.opencode_plugin()
        self.assertIn("@playwright/mcp", ts)
        self.assertIn('playwright:', ts)

    def test_the_opencode_plugin_speaks_opencodes_schema_not_claudes(self):
        # Verified in anomalyco/opencode, and not guessable from Claude's shape: the discriminator is
        # `remote`/`local`, and a local server's `command` is an ARRAY. Emitting Claude's `http`
        # would typecheck as JSON and silently declare nothing.
        ts = self.opencode_plugin()
        self.assertIn('"type": "remote"', ts)
        self.assertNotIn('"type": "http"', ts)
        self.assertIn("cfg.mcp", ts, "config(cfg) mutating cfg.mcp is the delivery mechanism")

    def test_the_opencode_plugin_resolves_our_server_at_runtime(self):
        # `${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code and by nothing else; left in an
        # opencode config it is a literal path that cannot resolve. So the path is computed from
        # the plugin's own location instead.
        #
        # This asserts that mechanism POSITIVELY rather than asserting the variable's absence,
        # and the difference is not cosmetic: the absence check was written first and failed on
        # the comment that explains why the variable is not used. A string-match cannot tell use
        # from mention. An identifier that must appear for the code to work can only be there on
        # purpose.
        self.assertIn("fileURLToPath(import.meta.url)", self.opencode_plugin())

    def test_the_users_own_config_wins(self):
        # An installer that overwrites a user's explicit choice is a worse bug than the one fixed.
        self.assertRegex(self.opencode_plugin(), r"\.\.\.ours,\s*\.\.\.\(cfg\.mcp")

    def test_codex_reaches_the_same_file_claude_does(self):
        # One file, two hosts — but only because the path is `./`-prefixed. This assertion read
        # `".mcp.json"` for months, which is the value Codex silently drops: the test did not merely
        # miss the bug, it pinned it as correct. The syntax rule and the invariant that enforces it
        # across every path-valued field live in test_codex_manifest.py; this one asserts only the
        # fact this suite is about — that Codex is pointed at the same declaration Claude reads.
        with open(PLUGINS / "keel-core" / ".codex-plugin" / "plugin.json", encoding="utf-8") as fh:
            self.assertEqual(json.load(fh).get("mcpServers"), "./.mcp.json")

    def test_install_sh_does_not_ask_the_user_to_copy_servers(self):
        text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("copy the mcpServers block", text,
                         "opencode plugins can declare servers themselves — install, don't instruct")


class TestDeclarationsResolveAfterInstall(unittest.TestCase):
    def test_the_stdio_server_is_plugin_root_anchored(self):
        # The whole bug class in one assertion: a repo-relative path resolves into the USER'S
        # project, because that is what the working directory is at runtime.
        args = " ".join(declared()["keel"]["args"])
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
