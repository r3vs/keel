/**
 * opencode adapter for the ledger gate — rule #1: no code edits before the interview elects the to-be.
 *
 * This file deliberately contains NO rule logic. The decision lives once, in `ledger-gate.py`
 * (15 tests), and every host feeds it the same JSON contract: Claude Code and Codex natively via
 * hooks.json, opencode and Pi through a thin adapter like this one. Reimplementing the rule in
 * TypeScript would give three copies to keep in sync — the exact divergence this package exists to
 * cure, committed by the package itself.
 *
 * Install: link/copy into `.opencode/plugin/` (or `~/.config/opencode/plugin/`) together with
 * `ledger-gate.py`. No package.json needed — only Node built-ins are used.
 *
 * Three traps this navigates, none of which are visible from the type system:
 *
 * 1. `apply_patch`. opencode swaps the toolset by model: on gpt-* models `edit` and `write` are
 *    REMOVED and replaced by `apply_patch` (tool/registry.ts). Guarding only edit/write leaves a
 *    hole that opens silently the day a user switches model.
 * 2. `permission.ask` looks purpose-built for denying a call — and is declared in the Hooks type
 *    but never triggered anywhere in the codebase. It would typecheck, install, and never fire.
 *    `tool.execute.before` + throw is the mechanism that actually runs.
 * 3. `$` is typed as a non-optional BunShell but is `undefined` under Node (their own source marks
 *    it `@ts-expect-error`). Hence `node:child_process`, not `$`.
 *
 * Every export in a legacy-shape plugin file must be a function — opencode iterates Object.values()
 * and throws on a non-function. That is why the constants below are not exported.
 */
import type { Plugin } from "@opencode-ai/plugin"
import { spawnSync } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

// `edit`/`write` are the normal path; `apply_patch` is what GPT models get instead. Miss it and
// the guard is model-dependent.
const WRITE_TOOLS = new Set(["edit", "write", "apply_patch"])

const GATE = resolve(dirname(fileURLToPath(import.meta.url)), "ledger-gate.py")

function decide(tool: string, filePath: string, cwd: string): string | null {
  const event = JSON.stringify({
    hook_event_name: "PreToolUse",
    tool_name: tool === "apply_patch" ? "Edit" : tool === "write" ? "Write" : "Edit",
    tool_input: { file_path: filePath },
    cwd,
  })

  const r = spawnSync("python", [GATE], { input: event, encoding: "utf8", timeout: 10_000 })
  // Fail open on every failure mode: no python, timeout, crash, garbage. A missed block costs one
  // edit the reviewer catches; a false block costs the whole session.
  if (r.error || r.status !== 0 || !r.stdout?.trim()) return null
  try {
    const out = JSON.parse(r.stdout).hookSpecificOutput
    return out?.permissionDecision === "deny" ? (out.permissionDecisionReason ?? "blocked") : null
  } catch {
    return null
  }
}

export const LedgerGate: Plugin = async ({ directory, worktree }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (!WRITE_TOOLS.has(input.tool)) return

      // args is `any` at the type level — validate rather than trust.
      const filePath: unknown = output.args?.filePath
      if (typeof filePath !== "string" || filePath.length === 0) return

      const base = worktree ?? directory
      const reason = decide(input.tool, resolve(base, filePath), base)
      // Throwing is how opencode blocks: the hook loop aborts before the tool executes, and the
      // message comes back to the model as a tool error.
      if (reason) throw new Error(reason)
    },
  }
}
