/**
 * Slice-6 tests — the opt-in WARM SDK adapters (claude-sdk / codex-sdk / pi). Each takes an
 * injectable `loadSdk`, so the option-construction, result-extraction, and fail-loud paths are
 * tested against a FAKE module — no real dep, no auth. (Live execution needs provider auth and is
 * out of scope here; the CLI adapters are the live-verified default.)
 * Run:  node --experimental-strip-types src/workflow/__tests__/slice6.ts
 */
import assert from 'node:assert/strict';
import { ClaudeSdkAdapter } from '../adapters/claude-sdk.ts';
import { CodexSdkAdapter } from '../adapters/codex-sdk.ts';
import { PiAdapter } from '../adapters/pi.ts';
import { ADAPTERS, parseArgs } from '../cli.ts';

let passed = 0;
let failed = 0;

async function test(name: string, fn: () => Promise<void> | void): Promise<void> {
  try {
    await fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    failed++;
    console.log(`  ✗ ${name}\n      ${e instanceof Error ? e.message : String(e)}`);
  }
}

// --- Claude Agent SDK ---
await test('ClaudeSdkAdapter: query() result message → result + cost; error → throw', async () => {
  const okSdk = {
    query: () =>
      (async function* () {
        yield { type: 'assistant' };
        yield { type: 'result', is_error: false, subtype: 'success', result: 'R:hi', total_cost_usd: 0.02 };
      })(),
  };
  const r = await new ClaudeSdkAdapter({ loadSdk: async () => okSdk }).run('hi');
  assert.equal(r.result, 'R:hi');
  assert.equal(r.cost, 0.02);

  const errSdk = {
    query: () => (async function* () { yield { type: 'result', is_error: true, subtype: 'error_max_turns' }; })(),
  };
  await assert.rejects(() => new ClaudeSdkAdapter({ loadSdk: async () => errSdk }).run('hi'), /turn failed/);
});

await test('ClaudeSdkAdapter: fails loud when the SDK cannot load', async () => {
  await assert.rejects(
    () => new ClaudeSdkAdapter({ loadSdk: () => Promise.reject(new Error('MODULE_NOT_FOUND')) }).run('hi'),
    /MODULE_NOT_FOUND/,
  );
});

// --- Codex SDK ---
await test('CodexSdkAdapter: startThread→run→finalResponse; schema parses JSON', async () => {
  class FakeThread {
    async run(input: string, turnOpts?: { outputSchema?: unknown }) {
      return {
        items: [],
        finalResponse: turnOpts?.outputSchema ? '{"real":true}' : `C:${input}`,
        usage: { total_tokens: 5, cost_usd: 0.001 },
      };
    }
  }
  const codexSdk = { Codex: class { startThread() { return new FakeThread(); } } };

  const r = await new CodexSdkAdapter({ loadSdk: async () => codexSdk }).run('hi');
  assert.equal(r.result, 'C:hi');
  assert.equal(r.tokens, 5);
  assert.equal(r.cost, 0.001);

  const r2 = await new CodexSdkAdapter({ loadSdk: async () => codexSdk }).run('hi', { schema: { type: 'object' } });
  assert.deepEqual(r2.result, { real: true });
});

await test('CodexSdkAdapter: fails loud when the SDK cannot load', async () => {
  await assert.rejects(
    () => new CodexSdkAdapter({ loadSdk: () => Promise.reject(new Error('no codex-sdk')) }).run('hi'),
    /no codex-sdk/,
  );
});

// --- Pi native ---
await test('PiAdapter: createAgentSession → prompt → final assistant text; disposes', async () => {
  let disposed = false;
  const piSdk = {
    resolveCliModel: async (m: string) => ({ model: { id: m } }),
    SessionManager: { inMemory: () => ({}) },
    createCodingTools: () => [],
    createAgentSession: async () => ({
      session: {
        prompt: async () => {},
        messages: [
          { role: 'user', text: 'q' },
          { role: 'assistant', text: 'A' },
        ],
        getSessionStats: () => ({ costUsd: 0.003, totalTokens: 7 }),
        dispose: () => {
          disposed = true;
        },
      },
    }),
  };
  const r = await new PiAdapter({ loadSdk: async () => piSdk }).run('hi', { model: 'x' });
  assert.equal(r.result, 'A');
  assert.equal(r.cost, 0.003);
  assert.equal(r.tokens, 7);
  assert.equal(disposed, true, 'session must be disposed in finally');
});

await test('PiAdapter: fails loud when the SDK cannot load', async () => {
  await assert.rejects(
    () => new PiAdapter({ loadSdk: () => Promise.reject(new Error('no pi')) }).run('hi'),
    /no pi/,
  );
});

// --- CLI registration + stdin args ---
await test('cli: warm hosts registered; --args-stdin / --args-file - parse', () => {
  for (const h of ['claude', 'codex', 'opencode', 'claude-sdk', 'codex-sdk', 'pi']) {
    assert.ok(h in ADAPTERS, `host ${h} should be registered`);
  }
  assert.equal(parseArgs(['--args-stdin']).argsStdin, true);
  const p = parseArgs(['--args-file', '-']);
  assert.equal(p.argsStdin, true);
  assert.equal(p.argsFile, undefined);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
