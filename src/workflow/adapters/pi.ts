/**
 * Pi native adapter — the pi-dynamic-workflows path (`createAgentSession` from
 * `@earendil-works/pi-coding-agent`), which is exactly this seam already.
 *
 * VERIFIED (pi-dw v3.4.0 source, 2026-07-22): `createAgentSession({cwd, agentDir, sessionManager,
 * modelRuntime, model, customTools, resourceLoader:{noExtensions:true}, excludeTools:['workflow',
 * 'workflow_control']})` → `{session}`; `await session.prompt(text)`; read `session.messages`
 * (final assistant text after the last toolResult), or the `structured_output` tool call when a
 * schema is given; `session.getSessionStats()` for usage; `session.dispose()` in finally.
 *
 * SLICE 2: guarded skeleton. Wiring the real `createAgentSession` (fresh session per call, anti-
 * recursive-fanout, structured-output retries) lands with the vendored pi-dw fork. Requires the peer
 * `@earendil-works/pi-coding-agent >=0.80.8`; if absent, `run()` throws a clear hint. Error path tested.
 */
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';

const PI_MODULE = '@earendil-works/pi-coding-agent';

export class PiAdapter implements SpawnAdapter {
  host = 'pi';
  defaultModel?: string;
  cwd: string;

  constructor(opts?: { model?: string; cwd?: string }) {
    this.defaultModel = opts?.model;
    this.cwd = opts?.cwd ?? '.';
  }

  async run(_prompt: string, _opts?: SpawnOpts): Promise<SpawnResult> {
    let pi: any;
    try {
      pi = await import(PI_MODULE);
    } catch {
      throw new Error(
        `PiAdapter needs ${PI_MODULE} (>=0.80.8) — install it, or run the vendored pi-dw fork.`,
      );
    }
    // Guard: the real session wiring is deferred to the vendored fork slice. Fail loud, not silent.
    void pi;
    throw new Error('PiAdapter: createAgentSession wiring not implemented yet (Slice 2 skeleton).');
  }
}
