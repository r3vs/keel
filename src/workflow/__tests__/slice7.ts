/**
 * Slice-7 tests — author-on-the-fly: an agent writes a workflow as SOURCE and runs it via the cli's
 * `--script` path (→ runWorkflowSource in the vm sandbox). This is the "dynamic" in dynamic workflows.
 * Run:  node --experimental-strip-types src/workflow/__tests__/slice7.ts
 */
import assert from 'node:assert/strict';
import { runCli, parseArgs } from '../cli.ts';
import { MockAdapter } from '../adapter.ts';

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

const base = {
  host: 'mock',
  topology: 'phase1-finding',
  argsStdin: false,
  scriptStdin: false,
  worktree: false,
  json: true,
} as const;

// 1 — an ad-hoc source workflow runs against the chosen host, driving agent() to the adapter.
await test('runCli: ad-hoc --script source runs (agent → adapter)', async () => {
  const mock = new MockAdapter((p) => `R:${p}`);
  const result = await runCli(
    { ...base },
    { adapters: { mock: () => mock }, source: `phase('adhoc'); const a = await agent('hi'); return a;` },
  );
  assert.equal(result, 'R:hi');
  assert.equal(mock.calls.length, 1);
});

// 2 — the vm globals now include checkpoint (the Slice-5 primitive), usable ad-hoc.
await test('runCli: ad-hoc script can use checkpoint', async () => {
  const result = await runCli(
    { ...base },
    { adapters: { mock: () => new MockAdapter() }, source: `const c = await checkpoint('ok?', { default: 42 }); return c;` },
  );
  assert.deepEqual(result, { approved: true, value: 42 });
});

// 3 — the full DSL is available ad-hoc (parallel preserves order).
await test('runCli: ad-hoc script uses parallel()', async () => {
  const mock = new MockAdapter((p) => p);
  const result = await runCli(
    { ...base },
    { adapters: { mock: () => mock }, source: `return await parallel(['a','b','c'].map(x => () => agent(x)));` },
  );
  assert.deepEqual(result, ['a', 'b', 'c']);
});

// 4 — the determinism guard applies to ad-hoc scripts too.
await test('runCli: ad-hoc script is determinism-guarded (Math.random banned)', async () => {
  await assert.rejects(
    () => runCli({ ...base }, { adapters: { mock: () => new MockAdapter() }, source: `return Math.random();` }),
    /banned/,
  );
});

// 5 — args reach the ad-hoc script as the `args` global.
await test('runCli: ad-hoc script receives args', async () => {
  const result = await runCli(
    { ...base },
    { adapters: { mock: () => new MockAdapter() }, source: `return args.n * 2;`, args: { n: 21 } },
  );
  assert.equal(result, 42);
});

// 6 — parseArgs: --script / --script-stdin / --script -
await test('parseArgs: --script, --script-stdin, --script -', () => {
  const p = parseArgs(['--script', 'w.js']);
  assert.equal(p.script, 'w.js');
  assert.equal(p.scriptStdin, false);

  const p2 = parseArgs(['--script', '-']);
  assert.equal(p2.script, undefined);
  assert.equal(p2.scriptStdin, true);

  assert.equal(parseArgs(['--script-stdin']).scriptStdin, true);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
