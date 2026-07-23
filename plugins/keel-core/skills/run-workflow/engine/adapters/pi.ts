/**
 * Pi native adapter — `@earendil-works/pi-coding-agent`.
 *
 * Modeled on pi-dynamic-workflows' WorkflowAgent + the package's exported helpers (verified present
 * in 0.81.1's `index.d.ts`: createAgentSession / resolveCliModel / createCodingTools / SessionManager):
 *   resolve the model, build coding tools, create a FRESH in-memory session that EXCLUDES the
 *   `workflow`/`workflow_control` tools (anti-recursive-fanout), prompt it, read the final assistant
 *   text + usage, dispose in finally.
 *
 * ⚠️ NOT live-verified: the exact createAgentSession wiring (model runtime construction) may have
 * drifted across Pi minor versions, and there is no live Pi runtime here to test against. Pi's OWN
 * native workflow path is pi-dynamic-workflows; this adapter is for running THIS engine's topologies
 * on Pi. OPT-IN (needs the peer dep); absent → fails loud. The control flow is mock-tested.
 */
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';
import type { SdkLoader } from './claude-sdk.ts';

const MODULE = '@earendil-works/pi-coding-agent';

export class PiAdapter implements SpawnAdapter {
  host = 'pi';
  defaultModel?: string;
  cwd: string;
  loadSdk: SdkLoader;

  constructor(opts?: { model?: string; cwd?: string; loadSdk?: SdkLoader }) {
    this.defaultModel = opts?.model;
    this.cwd = opts?.cwd ?? '.';
    this.loadSdk =
      opts?.loadSdk ??
      (async () => {
        try {
          return await import(MODULE);
        } catch {
          throw new Error(`PiAdapter needs ${MODULE} (>=0.81) — install it, or use pi-dynamic-workflows natively on Pi.`);
        }
      });
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    const sdk = await this.loadSdk();
    const cwd = opts?.cwd ?? this.cwd;
    const modelId = opts?.model ?? this.defaultModel;

    const resolved = modelId && sdk.resolveCliModel ? await sdk.resolveCliModel(modelId) : undefined;
    const model = resolved?.model ?? resolved;
    const sessionManager = sdk.SessionManager?.inMemory ? sdk.SessionManager.inMemory() : undefined;
    const customTools = sdk.createCodingTools ? sdk.createCodingTools(cwd) : undefined;

    const created = await sdk.createAgentSession({
      cwd,
      model,
      sessionManager,
      customTools,
      excludeTools: ['workflow', 'workflow_control'], // anti-recursive-fanout, as pi-dw does
    });
    const session = created?.session ?? created;
    try {
      await session.prompt(prompt);
      let text = '';
      for (const m of session.messages ?? []) {
        const t = m?.text ?? m?.content;
        if ((m?.role === 'assistant' || m?.type === 'assistant') && typeof t === 'string') text = t;
      }
      const stats = session.getSessionStats?.();
      return { result: text, cost: stats?.costUsd, tokens: stats?.totalTokens };
    } finally {
      session.dispose?.();
    }
  }
}
