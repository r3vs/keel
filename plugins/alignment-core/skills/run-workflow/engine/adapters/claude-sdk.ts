/**
 * Claude Code WARM adapter — the Agent SDK (`@anthropic-ai/claude-agent-sdk`).
 *
 * VERIFIED against the installed 0.3.217 `sdk.d.ts`:
 *   query({ prompt, options?: Options }): Query   // Query is an async-iterable of SDKMessage
 *   the final message has `type: 'result'`; SDKResultSuccess has `result: string` + `total_cost_usd`,
 *   SDKResultError has `is_error: true` (no `result`). Token count is NOT exposed.
 * The native `Workflow` primitive is NOT plugin/SDK-pilotable, so the SDK is the warm ceiling here.
 *
 * OPT-IN: needs the dep (`npm i @anthropic-ai/claude-agent-sdk`) + its peers; absent → fails loud.
 * NOT live-verified (needs auth); the option-construction + result/error paths are mock-tested.
 * `loadSdk` is injectable so those paths are testable without the real module.
 */
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';

const MODULE = '@anthropic-ai/claude-agent-sdk';

export type SdkLoader = () => Promise<any>;

export class ClaudeSdkAdapter implements SpawnAdapter {
  host = 'claude-sdk';
  defaultModel?: string;
  allowedTools?: string[];
  loadSdk: SdkLoader;

  constructor(opts?: { model?: string; allowedTools?: string[]; loadSdk?: SdkLoader }) {
    this.defaultModel = opts?.model;
    this.allowedTools = opts?.allowedTools;
    this.loadSdk =
      opts?.loadSdk ??
      (async () => {
        try {
          return await import(MODULE);
        } catch {
          throw new Error(`ClaudeSdkAdapter needs ${MODULE} — install it (npm i ${MODULE}) or use ClaudeCliAdapter.`);
        }
      });
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    const sdk = await this.loadSdk();
    let result: string | Record<string, unknown> = '';
    let cost: number | undefined;
    for await (const msg of sdk.query({
      prompt,
      options: { model: opts?.model ?? this.defaultModel, allowedTools: this.allowedTools },
    })) {
      if (msg && msg.type === 'result') {
        // codex-style fail-loud: a turn error surfaces as a throw, never a silent ''.
        if (msg.is_error) throw new Error(`claude-sdk turn failed${msg.subtype ? `: ${msg.subtype}` : ''}`);
        result = msg.result;
        cost = msg.total_cost_usd;
        break;
      }
    }
    return { result, cost }; // tokens intentionally omitted — not exposed by the SDK
  }
}
