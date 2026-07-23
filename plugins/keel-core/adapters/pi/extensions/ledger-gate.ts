/**
 * Pi adapter for the ledger gate — rule #1: no code edits before the interview elects the to-be.
 *
 * Like the opencode adapter, this holds NO rule logic. The decision lives once in `ledger-gate.py`
 * (15 tests); Claude Code and Codex call it natively through hooks.json, opencode and Pi through a
 * thin adapter. One rule, four hosts — because three hand-kept copies of a rule is the divergence
 * this package exists to cure.
 *
 * Install: copy into `~/.pi/agent/extensions/` together with `ledger-gate.py`.
 * Prefer the GLOBAL location over project-local `.pi/extensions/`: project-local extensions load
 * only after the project is trusted, and a guard that is absent until trust is granted is absent
 * exactly when an unfamiliar codebase is being opened.
 *
 * Two Pi-specific details worth stating, both opposite to opencode:
 *   - the file path field is `path`, not `filePath`;
 *   - blocking is `return { block: true, reason }` — the sanctioned path (throwing also blocks, but
 *     produces a messier result). The model receives `reason` as an error tool result and the tool
 *     never runs.
 *
 * No package.json or manifest needed: Pi loads extensions through jiti, so TypeScript runs
 * uncompiled, and Node built-ins are available.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { isToolCallEventType } from "@earendil-works/pi-coding-agent"
import { spawnSync } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const GATE = resolve(dirname(fileURLToPath(import.meta.url)), "ledger-gate.py")

function decide(toolName: string, filePath: string, cwd: string): string | null {
  const event = JSON.stringify({
    hook_event_name: "PreToolUse",
    tool_name: toolName === "write" ? "Write" : "Edit",
    tool_input: { file_path: filePath },
    cwd,
  })

  const r = spawnSync("python", [GATE], { input: event, encoding: "utf8", timeout: 10_000 })
  // Fail open on every failure mode — no python, timeout, crash, garbage.
  if (r.error || r.status !== 0 || !r.stdout?.trim()) return null
  try {
    const out = JSON.parse(r.stdout).hookSpecificOutput
    return out?.permissionDecision === "deny" ? (out.permissionDecisionReason ?? "blocked") : null
  } catch {
    return null
  }
}

export default function ledgerGate(pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    let target: string | undefined
    if (isToolCallEventType("write", event)) target = event.input.path
    else if (isToolCallEventType("edit", event)) target = event.input.path
    else return

    if (typeof target !== "string" || target.length === 0) return

    // ctx.cwd, not process.cwd(): it is what Pi's own tools resolve paths against.
    const reason = decide(event.toolName, resolve(ctx.cwd, target), ctx.cwd)
    if (reason) return { block: true, reason }
  })
}
