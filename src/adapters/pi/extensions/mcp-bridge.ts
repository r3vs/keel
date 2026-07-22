/**
 * Pi adapter — MCP bridge. Pi has no native MCP; this makes the codebase-alignment MCP server
 * reachable from Pi, so MCP is the channel on all four hosts and no CLI is needed anywhere.
 *
 * DEPENDENCY-FREE ON PURPOSE. It is a loose `.ts` (Node built-ins + Pi's aliased `typebox` only) with
 * a hand-rolled newline-delimited JSON-RPC client over stdio — NOT `@modelcontextprotocol/sdk`. The
 * SDK is not in Pi's jiti allowlist, so using it would force this into an npm sub-package inside Pi's
 * shared dependency tree and reintroduce the exact `ERESOLVE` that makes `nicobailon/pi-mcp-adapter`
 * unusable (its open issue #176). A loose `.ts` sidesteps that entirely.
 *
 * ONE proxy tool `alignment` is registered — synchronously, so the "does registerTool after an await
 * get collected?" question (unverified on Pi) never arises. `{describe:true}` lists the server's
 * tools; `{tool, args}` calls one. The server connection is LAZY (spawned on first use) and the whole
 * thing FAILS OPEN: if `uv` is missing or the server cannot start, the tool returns a readable error
 * instead of crashing the extension — the same posture as `ledger-gate.ts`.
 *
 * Install: `scripts/install.sh` symlinks this into `~/.pi/agent/extensions/`, keeping the relative
 * link to `../../../mcp/server.py` (the vendored server) intact — the same trick opencode's `mcp.ts`
 * uses. A plain copy severs that link; then the tool reports the server as unreachable, gracefully.
 *
 * The protocol here mirrors `tests/test_mcp_server.py` exactly: initialize -> notifications/initialized
 * -> tools/list / tools/call, newline-delimited JSON-RPC, replies matched by id.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { Type } from "typebox"
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

// The vendored MCP server sits at the plugin root; from adapters/pi/extensions/ that is three up.
const SERVER = resolve(dirname(fileURLToPath(import.meta.url)), "../../../mcp/server.py")
const REQUEST_TIMEOUT_MS = 60_000 // first `uv run` resolves FastMCP (~7s cold); generous ceiling.

type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void; timer: NodeJS.Timeout }

class McpStdioClient {
  private proc: ChildProcessWithoutNullStreams | null = null
  private buf = ""
  private id = 0
  private readonly pending = new Map<number, Pending>()
  private connecting: Promise<void> | null = null

  private async ensure(): Promise<void> {
    if (this.proc) return
    if (this.connecting) return this.connecting
    this.connecting = (async () => {
      const p = spawn("uv", ["run", "--script", SERVER], { stdio: ["pipe", "pipe", "pipe"] })
      this.proc = p
      p.stdout.setEncoding("utf8")
      p.stdout.on("data", (chunk: string) => this.onData(chunk))
      p.on("error", (e) => this.fail(e))
      p.on("exit", () => this.fail(new Error("MCP server exited")))
      await this.request("initialize", {
        protocolVersion: "2025-11-25",
        capabilities: {},
        clientInfo: { name: "codebase-alignment-pi", version: "0.1.0" },
      })
      this.notify("notifications/initialized")
    })()
    try {
      await this.connecting
    } finally {
      this.connecting = null
    }
  }

  private fail(err: Error): void {
    this.proc = null
    for (const { reject, timer } of this.pending.values()) {
      clearTimeout(timer)
      reject(err)
    }
    this.pending.clear()
  }

  private onData(chunk: string): void {
    this.buf += chunk
    let nl: number
    while ((nl = this.buf.indexOf("\n")) >= 0) {
      const line = this.buf.slice(0, nl).trim()
      this.buf = this.buf.slice(nl + 1)
      if (!line) continue
      let msg: { id?: number; result?: unknown; error?: { message?: string } }
      try {
        msg = JSON.parse(line)
      } catch {
        continue // partial/garbage line — wait for more
      }
      if (typeof msg.id === "number" && this.pending.has(msg.id)) {
        const { resolve, reject, timer } = this.pending.get(msg.id)!
        clearTimeout(timer)
        this.pending.delete(msg.id)
        if (msg.error) reject(new Error(msg.error.message ?? "MCP error"))
        else resolve(msg.result)
      }
      // messages without a matching id (server notifications) are ignored by design
    }
  }

  private send(obj: unknown): void {
    this.proc!.stdin.write(JSON.stringify(obj) + "\n")
  }

  private notify(method: string, params: unknown = {}): void {
    this.send({ jsonrpc: "2.0", method, params })
  }

  private request(method: string, params: unknown): Promise<unknown> {
    const id = ++this.id
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`MCP request '${method}' timed out`))
      }, REQUEST_TIMEOUT_MS)
      this.pending.set(id, { resolve, reject, timer })
      this.send({ jsonrpc: "2.0", id, method, params })
    })
  }

  async listTools(): Promise<Array<{ name: string; description?: string }>> {
    await this.ensure()
    const r = (await this.request("tools/list", {})) as { tools?: Array<{ name: string; description?: string }> }
    return r.tools ?? []
  }

  async callTool(name: string, args: unknown): Promise<{ content?: unknown[] }> {
    await this.ensure()
    return (await this.request("tools/call", { name, arguments: args ?? {} })) as { content?: unknown[] }
  }

  close(): void {
    try {
      this.proc?.stdin.end()
      this.proc?.kill()
    } catch {
      /* fail open */
    }
    this.proc = null
  }
}

export default function mcpBridge(pi: ExtensionAPI): void {
  const client = new McpStdioClient()

  // Registered SYNCHRONOUSLY (a single proxy tool), so there is no registerTool-after-await timing
  // question. The connection is lazy: nothing is spawned until the first call.
  ;(pi.registerTool as (tool: unknown) => unknown)({
    name: "alignment",
    label: "Codebase Alignment (MCP)",
    description:
      "The codebase-alignment MCP tools (the decisions ledger, cross-layer contract diff, findings + " +
      "fp-check, coverage manifest, and the understand-mode graph family). Pass {describe:true} to list " +
      "the tools and their schemas; pass {tool:'<name>', args:{...}} to call one.",
    promptSnippet:
      "codebase-alignment MCP: ledger / contract-diff / findings / coverage / graph tools — " +
      "{describe:true} to list, {tool,args} to call",
    parameters: Type.Object({
      tool: Type.Optional(Type.String({ description: "tool to call, e.g. ledger_summary, contract_diff" })),
      args: Type.Optional(Type.Any({ description: "arguments object for the chosen tool" })),
      describe: Type.Optional(Type.Boolean({ description: "list available tools instead of calling one" })),
    }),
    async execute(_id: string, params: { tool?: string; args?: unknown; describe?: boolean }) {
      try {
        if (params?.describe || !params?.tool) {
          const tools = await client.listTools()
          const listing = tools.map((t) => ({ name: t.name, description: t.description }))
          return {
            content: [{ type: "text", text: JSON.stringify(listing, null, 2) }],
            details: { tools: listing },
          }
        }
        const result = await client.callTool(params.tool, params.args)
        return {
          content: result.content ?? [{ type: "text", text: JSON.stringify(result) }],
          details: result,
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e)
        // Fail open: surface the error to the model as a tool result, never throw out of the extension.
        return {
          content: [{ type: "text", text: `alignment MCP unavailable: ${message}` }],
          details: { error: message },
        }
      }
    },
  })

  pi.on("session_shutdown", () => client.close())
}
