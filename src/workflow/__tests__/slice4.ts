/**
 * Slice-4 tests — the CLI entry (arg parsing, adapter/topology selection, dry-run discovery).
 * Run:  node --experimental-strip-types src/workflow/__tests__/slice4.ts
 */
import assert from 'node:assert/strict';
import { parseArgs, runCli, ADAPTERS, TOPOLOGIES } from '../cli.ts';
import { MockAdapter } from '../adapter.ts';
import type { Pin } from '../topologies/phase1-finding.ts';

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

// 1 — defaults + overrides.
await test('parseArgs: defaults and overrides', () => {
  const d = parseArgs([]);
  assert.equal(d.host, 'claude');
  assert.equal(d.topology, 'phase1-finding');
  assert.equal(d.json, true);
  const o = parseArgs(['--host', 'opencode', '--topology', 'phase1-finding', '--model', 'x', '--text']);
  assert.equal(o.host, 'opencode');
  assert.equal(o.model, 'x');
  assert.equal(o.json, false);
});

// 2 — the dependency-free CLI hosts are registered (the warm *-sdk/pi hosts are added in slice6).
await test('ADAPTERS: claude/codex/opencode registered (no npm dep)', () => {
  for (const h of ['claude', 'codex', 'opencode']) assert.ok(h in ADAPTERS, `${h} should be registered`);
  assert.ok(TOPOLOGIES['phase1-finding']);
});

// 3 — unknown host / topology fail loud.
await test('runCli: unknown host and topology throw', async () => {
  await assert.rejects(() => runCli({ host: 'nope', topology: 'phase1-finding', json: true }), /unknown --host/);
  await assert.rejects(() => runCli({ host: 'claude', topology: 'nope', json: true }, {
    adapters: { claude: () => new MockAdapter() },
  }), /unknown --topology/);
});

// 4 — end-to-end via injected mock adapter: the CLI runs the real phase1 topology and returns pins.
await test('runCli: dry-run discovery returns surviving pins', async () => {
  const A = { file: 'a.ts', line: 1, kind: 'contract_mismatch', summary: 'real' };
  const B = { file: 'b.ts', line: 2, kind: 'dead', summary: 'false' };
  const mock = new MockAdapter((prompt) => {
    if (prompt.startsWith('Round')) return prompt.includes('per-layer') || prompt.includes('per-entity') ? A : B;
    if (prompt.startsWith('Verifica')) return { real: prompt.includes('a.ts') };
    return 'x';
  });
  const result = await runCli(
    { host: 'mock', topology: 'phase1-finding', json: true },
    { adapters: { mock: () => mock }, topologies: TOPOLOGIES },
  );
  const pins = result as Pin[];
  assert.equal(pins.length, 1);
  assert.equal(pins[0].file, 'a.ts');
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
