/**
 * GENERATED FILE - do not edit. Source: the MCP table in src/core/knowledge-sources.md;
 * regenerate with: python scripts/build.py
 *
 * opencode's MCP delivery — the servers `core/knowledge-sources.md` orders the agent to use.
 *
 * opencode has no plugin manifest to declare servers in, but `config(cfg)` hands a plugin the live
 * merged config to mutate. So installing this plugin delivers the servers, the same way installing
 * the Claude/Codex plugin does. The alternative — which this replaced — was telling the user to
 * hand-copy a JSON block out of our repo.
 *
 * The user's own config wins on every key: this fills gaps, it does not overwrite choices.
 */
import type { Plugin } from "@opencode-ai/plugin"
import { existsSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

// opencode's discriminator is `remote`/`local` — NOT Claude's `http`/`stdio`.
const REMOTE = {
  "context7": {
    "type": "remote",
    "url": "https://mcp.context7.com/mcp"
  },
  "deepwiki": {
    "type": "remote",
    "url": "https://mcp.deepwiki.com/mcp"
  }
}

// `${CLAUDE_PLUGIN_ROOT}` is a Claude-ism opencode never expands, so resolve from this file.
// A local `command` is an array here, not command + args.
const SERVER = resolve(dirname(fileURLToPath(import.meta.url)), "../../../mcp/server.py")

export const McpServers: Plugin = async () => ({
  config: (cfg: any) => {
    // Playwright MCP is a capability server (browser verification), delivered like keel.
    // opencode's local `command` is an array; it connects via npx with no container/key (unlike the
    // opt-in servers), degrading only on a browser action without `npx playwright install`.
    const ours: Record<string, unknown> = { ...REMOTE, playwright: { type: "local", command: ["npx", "-y", "@playwright/mcp@latest"] } }
    // Degrade gracefully, never hard-fail: if this plugin was copied out of the built tree rather
    // than linked into it, our server is unreachable — declaring it anyway would hand the user a
    // broken entry. The doctrine's remote servers still land.
    if (existsSync(SERVER)) {
      ours["keel"] = { type: "local", command: ["uv", "run", "--script", SERVER] }
    }
    cfg.mcp = { ...ours, ...(cfg.mcp ?? {}) }
  },
})
