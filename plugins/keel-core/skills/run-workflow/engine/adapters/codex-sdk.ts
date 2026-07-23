/**
 * Codex WARM adapter — the TypeScript SDK (`@openai/codex-sdk`).
 *
 * VERIFIED against the installed 0.145.0 `dist/index.d.ts`:
 *   new Codex(options?: CodexOptions)
 *   codex.startThread(options?: ThreadOptions): Thread      // ThreadOptions has `model?`
 *   thread.run(input: string, turnOptions?: TurnOptions): Promise<Turn>   // TurnOptions has `outputSchema?`
 *   Turn = { items: ThreadItem[]; finalResponse: string }   // finalResponse IS the result — no parsing
 * The SDK wraps the `codex` cli, so it honours the same auth/quota (a failed turn rejects here).
 *
 * OPT-IN: needs `npm i @openai/codex-sdk`; absent → fails loud. NOT live-verified (needs codex auth);
 * option-construction + result extraction are mock-tested via the injectable `loadSdk`.
 */
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';
import type { SdkLoader } from './claude-sdk.ts';

const MODULE = '@openai/codex-sdk';

export class CodexSdkAdapter implements SpawnAdapter {
  host = 'codex-sdk';
  defaultModel?: string;
  loadSdk: SdkLoader;

  constructor(opts?: { model?: string; loadSdk?: SdkLoader }) {
    this.defaultModel = opts?.model;
    this.loadSdk =
      opts?.loadSdk ??
      (async () => {
        try {
          return await import(MODULE);
        } catch {
          throw new Error(`CodexSdkAdapter needs ${MODULE} — install it (npm i ${MODULE}) or use CodexCliAdapter.`);
        }
      });
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    const sdk = await this.loadSdk();
    const codex = new sdk.Codex();
    const model = opts?.model ?? this.defaultModel;
    const thread = codex.startThread(model ? { model } : undefined);
    const turn = await thread.run(prompt, opts?.schema ? { outputSchema: opts.schema } : undefined);

    let result: string | Record<string, unknown> = turn?.finalResponse ?? '';
    if (opts?.schema && typeof result === 'string' && result) {
      try {
        result = JSON.parse(result) as Record<string, unknown>;
      } catch {
        /* leave as text */
      }
    }
    // Usage lives on the thread/turn events; best-effort until a live turn is observed.
    const usage = turn?.usage as { total_tokens?: number; cost_usd?: number } | undefined;
    return { result, tokens: usage?.total_tokens, cost: usage?.cost_usd };
  }
}
