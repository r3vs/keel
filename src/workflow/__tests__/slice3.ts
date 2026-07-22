/**
 * Slice-3 tests — vm sandbox + determinism guard (fully verifiable here, no host needed).
 * Run:  node --experimental-strip-types src/workflow/__tests__/slice3.ts
 */
import assert from 'node:assert/strict';
import { runWorkflowSource, stripLeadingExportMeta } from '../sandbox.ts';
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

// 1 — a source-string workflow runs with the primitives injected as globals.
await test('runWorkflowSource: globals injected, returns value', async () => {
  const src = `phase('P'); const a = await agent('hi'); log('done'); return a;`;
  const { result } = await runWorkflowSource(src, { adapter: new MockAdapter((p) => `R:${p}`) });
  assert.equal(result, 'R:hi');
});

// 2 — parse-time blocklist rejects the obvious non-deterministic calls.
await test('determinism: parse-time blocklist rejects Math.random / Date.now', async () => {
  await assert.rejects(() => runWorkflowSource('return Math.random();', { adapter: new MockAdapter() }), /banned/);
  await assert.rejects(() => runWorkflowSource('return Date.now();', { adapter: new MockAdapter() }), /banned/);
});

// 3 — runtime prelude catches what the regex misses (computed access bypasses the blocklist).
await test('determinism: runtime prelude catches Date["now"]() the regex misses', async () => {
  await assert.rejects(
    () => runWorkflowSource(`const f = Date['now']; return f();`, { adapter: new MockAdapter() }),
    /Date\.now|banned/,
  );
});

// 4 — new Date(arg) still works; only the non-deterministic forms are banned.
await test('determinism: new Date(arg) is allowed', async () => {
  const src = `const d = new Date('2020-06-15T00:00:00Z'); return d.getUTCFullYear();`;
  const { result } = await runWorkflowSource(src, { adapter: new MockAdapter() });
  assert.equal(result, 2020);
});

// 5 — the journal/replay contract holds through the vm path too.
await test('runWorkflowSource: unchanged source replays 100% from cache', async () => {
  const src = `const a = await agent('x'); const b = await agent('y'); return a + '|' + b;`;
  const m1 = new MockAdapter((p) => `v:${p}`);
  const r1 = await runWorkflowSource(src, { adapter: m1 });
  assert.equal(r1.result, 'v:x|v:y');
  assert.equal(m1.calls.length, 2);

  const m2 = new MockAdapter(() => 'SHOULD_NOT_BE_CALLED');
  const r2 = await runWorkflowSource(src, { adapter: m2, resume: r1.journal });
  assert.equal(r2.result, 'v:x|v:y');
  assert.equal(m2.calls.length, 0);
});

// 6 — `args` is injected as a global for parameterized workflows.
await test('runWorkflowSource: args injected as a global', async () => {
  const { result } = await runWorkflowSource('return args.x + 1;', {
    adapter: new MockAdapter(),
    args: { x: 41 },
  });
  assert.equal(result, 42);
});

// 7 — meta stripping handles nested braces and keeps the body.
await test('stripLeadingExportMeta: removes nested-brace meta, keeps body', () => {
  const src = `export const meta = { name: 'x', phases: [{ title: 'a' }, { title: 'b' }] };\nreturn 5;`;
  const stripped = stripLeadingExportMeta(src);
  assert.ok(!stripped.includes('export const meta'), 'meta not removed');
  assert.ok(stripped.includes('return 5'), 'body lost');
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
