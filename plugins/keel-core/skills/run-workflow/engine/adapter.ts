/**
 * The spawn seam — the ONE host dependency the workflow engine has.
 *
 * Design adapted from pi-dynamic-workflows (MIT), whose `WorkflowAgentRunner { run(...) }` interface
 * is exactly this seam; there the runner is hard-wired to Pi's `createAgentSession`, here it is a
 * pluggable per-host adapter so the same engine drives all four hosts. See
 * `docs/design/dynamic-workflows.md` §2.
 *
 *   Copyright (c) 2026 QuintinShaw
 *   Copyright (c) Michael Livs (original pi-dynamic-workflows)
 *   MIT — see the full NOTICE that must ship with any vendored copy of the engine.
 *
 * Invariant (design §5.1): an adapter's `run()` executes a READ-ONLY fan-out agent by default; the
 * only writer of the ledger is the executor sub-agent, via the floor MCP/CLI — never the engine.
 */
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const pExecFile = promisify(execFile);

/**
 * Options for a single spawned agent.
 *
 * Model policy — reuses `src/core/model-tiers.md`, it does NOT reinvent it. The MODEL binds to the
 * ROLE, resolved per-host at install time into that host's own per-agent config (Profile A–D). So the
 * engine carries `agentType` (the role) and never resolves a model itself. Where a host's headless CLI
 * can select an installed role (opencode `--agent`), the role's model applies automatically; where it
 * cannot (Claude `-p`, `codex exec` have no installed-role selector), it degrades to the host's
 * session/default model — the same graceful degradation model-tiers.md already specifies for a missing
 * row and for Pi. `model` is an explicit OVERRIDE (e.g. the executor's escalation target), never a
 * resolved tier: the engine must not carry a `task → model` table, which would be the exact heuristic
 * both the roster and this package forbid.
 */
export type SpawnOpts = {
  model?: string; // explicit override ONLY; the steady-state model comes from the host's per-role config
  schema?: object;
  isolation?: 'worktree';
  cwd?: string; // working directory for this agent (set by WorktreeAdapter when isolation is on)
  timeoutMs?: number | null;
  agentType?: string; // the roster role (researcher/reviewer/challenger/executor/…) — the model carrier
  label?: string;
  phase?: string;
};

/** Cost/tokens are best-effort: no host exposes token count uniformly (design §2, assumption A-2). */
export type SpawnResult = {
  result: string | Record<string, unknown>;
  cost?: number;
  tokens?: number;
};

export interface SpawnAdapter {
  readonly host: string;
  run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult>;
}

// ---------------------------------------------------------------------------
// MockAdapter — deterministic, for tests and for `buildloop.py`-only dry runs.
// ---------------------------------------------------------------------------

export type MockResponder = (prompt: string, opts?: SpawnOpts) => string | Record<string, unknown>;

export class MockAdapter implements SpawnAdapter {
  host = 'mock';
  calls: Array<{ prompt: string; opts?: SpawnOpts }> = [];
  responder: MockResponder;
  delays?: (prompt: string) => number;

  constructor(responder?: MockResponder, delays?: (prompt: string) => number) {
    this.responder = responder ?? ((p) => `echo:${p}`);
    this.delays = delays;
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    this.calls.push({ prompt, opts });
    const d = this.delays ? this.delays(prompt) : 0;
    if (d > 0) await new Promise((r) => setTimeout(r, d));
    return { result: this.responder(prompt, opts), cost: 0, tokens: 0 };
  }
}

// ---------------------------------------------------------------------------
// ClaudeCliAdapter — headless `claude -p`. Present but UNVERIFIED at runtime:
// the JSON shape of `-p --output-format json` is not documented for cost/token
// (design §2 table). The warm path is the Agent SDK (`query()` → ResultMessage
// .total_cost_usd); it lands in a later slice once we take the SDK dependency.
// ---------------------------------------------------------------------------

export class ClaudeCliAdapter implements SpawnAdapter {
  host = 'claude';
  defaultModel?: string;

  constructor(opts?: { model?: string }) {
    this.defaultModel = opts?.model;
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    const args = ['-p', prompt, '--output-format', 'json'];
    const model = opts?.model ?? this.defaultModel;
    if (model) args.push('--model', model);
    if (opts?.schema) args.push('--json-schema', JSON.stringify(opts.schema));
    const { stdout } = await pExecFile('claude', args, { maxBuffer: 64 * 1024 * 1024 });
    const parsed = JSON.parse(stdout) as Record<string, unknown>;
    // NOTE: shape unverified — `result` is a best-effort read; `total_cost_usd` is what the SDK
    // exposes and MAY be present here. Do not gate on either until verified against a real install.
    const result = (parsed.result ?? parsed) as string | Record<string, unknown>;
    return { result, cost: parsed.total_cost_usd as number | undefined };
  }
}
