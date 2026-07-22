/**
 * Claude Code WARM adapter — the Agent SDK (`@anthropic-ai/claude-agent-sdk`).
 *
 * VERIFIED (claude-code-guide, 2026-07-22): `query({prompt, options:{model, allowedTools, systemPrompt,
 * maxTurns}})` yields messages until a `ResultMessage` with `.result` (text) and `.total_cost_usd`
 * (cost). Token count is NOT exposed. The native `Workflow` primitive is NOT plugin/SDK-pilotable, so
 * the SDK is the warm ceiling on Claude Code. Requires the dep (Node) — if absent, `run()` throws a
 * clear install hint. UNVERIFIED end-to-end here (dep not installed); the error path IS tested.
 */
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';

const SDK_MODULE = '@anthropic-ai/claude-agent-sdk';

export class ClaudeSdkAdapter implements SpawnAdapter {
  host = 'claude';
  defaultModel?: string;
  allowedTools?: string[];

  constructor(opts?: { model?: string; allowedTools?: string[] }) {
    this.defaultModel = opts?.model;
    this.allowedTools = opts?.allowedTools;
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    let sdk: any;
    try {
      sdk = await import(SDK_MODULE);
    } catch {
      throw new Error(
        `ClaudeSdkAdapter needs ${SDK_MODULE} — install it (npm i ${SDK_MODULE}) or use ClaudeCliAdapter.`,
      );
    }
    let result: string | Record<string, unknown> = '';
    let cost: number | undefined;
    for await (const msg of sdk.query({
      prompt,
      options: {
        model: opts?.model ?? this.defaultModel,
        allowedTools: this.allowedTools,
      },
    })) {
      if (msg && typeof msg === 'object' && 'result' in msg) {
        result = (msg as any).result;
        cost = (msg as any).total_cost_usd;
        break;
      }
    }
    return { result, cost }; // tokens intentionally omitted — not exposed by the SDK
  }
}
