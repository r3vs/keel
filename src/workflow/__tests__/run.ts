/**
 * Slice-0 tests — run with:  node --experimental-strip-types src/workflow/__tests__/run.ts
 * No test framework / no deps: a tiny hand-rolled harness so the strip-types flag applies to one
 * process. Verifies the parts that MUST be correct now: adapter wiring, parallel order, and the
 * determinism/replay contract (the whole reason the engine exists).
 */
import assert from 'node:assert/strict';
import { runWorkflow } from '../engine.ts';
import type { WorkflowCtx } from '../engine.ts';
import { MockAdapter } from '../adapter.ts';
import { phase1Finding } from '../topologies/phase1-finding.ts';
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

// 1 — agent() calls the adapter and returns its result.
await test('agent() returns the adapter result', async () => {
  const mock = new MockAdapter((p) => `R:${p}`);
  const { result } = await runWorkflow((wf) => wf.agent('hello'), { adapter: mock });
  assert.equal(result, 'R:hello');
  assert.equal(mock.calls.length, 1);
});

// 2 — parallel() preserves INPUT order even when later items resolve first.
await test('parallel() preserves input order under out-of-order completion', async () => {
  const mock = new MockAdapter(
    (p) => p,
    (p) => (p === 'a' ? 30 : p === 'b' ? 10 : 0), // 'a' slowest, 'c' fastest
  );
  const { result } = await runWorkflow(
    (wf) => wf.parallel(['a', 'b', 'c'].map((x) => () => wf.agent(x))),
    { adapter: mock },
  );
  assert.deepEqual(result, ['a', 'b', 'c']);
});

// 3 — a clean re-run replays entirely from the journal; the adapter is never touched.
await test('journal replay: unchanged script serves 100% from cache', async () => {
  const script = async (wf: WorkflowCtx) => {
    const a = await wf.agent('x');
    const b = await wf.agent('y');
    return `${a as string}|${b as string}`;
  };
  const m1 = new MockAdapter((p) => `v:${p}`);
  const run1 = await runWorkflow(script, { adapter: m1 });
  assert.equal(run1.result, 'v:x|v:y');
  assert.equal(m1.calls.length, 2);

  const m2 = new MockAdapter(() => 'SHOULD_NOT_BE_CALLED');
  const run2 = await runWorkflow(script, { adapter: m2, resume: run1.journal });
  assert.equal(run2.result, 'v:x|v:y'); // identical result, from cache
  assert.equal(m2.calls.length, 0); // adapter never invoked on a clean replay
});

// 4 — longest-unchanged-prefix: edit call #1 → only #1.. re-run live, #0 stays cached.
await test('journal: edited call + downstream re-run, prefix stays cached', async () => {
  const m1 = new MockAdapter((p) => `v:${p}`);
  const run1 = await runWorkflow(
    async (wf: WorkflowCtx) => {
      await wf.agent('keep');
      await wf.agent('old');
      return 'done';
    },
    { adapter: m1 },
  );
  assert.equal(m1.calls.length, 2);

  const m2 = new MockAdapter((p) => `v:${p}`);
  await runWorkflow(
    async (wf: WorkflowCtx) => {
      await wf.agent('keep'); // #0 unchanged → cached
      await wf.agent('NEW'); // #1 changed → live
      return 'done';
    },
    { adapter: m2, resume: run1.journal },
  );
  assert.equal(m2.calls.length, 1);
  assert.equal(m2.calls[0].prompt, 'NEW');
});

// 5 — the elected flagship end-to-end against a mock: dedup across lenses, loop-until-dry
//     termination, and the adversarial verify filter — all in one run.
await test('phase1Finding: dedup + dry-out + adversarial verify filter', async () => {
  const A: Pin = { file: 'a.ts', line: 1, kind: 'drift', summary: 'real' };
  const B: Pin = { file: 'b.ts', line: 2, kind: 'dead', summary: 'false' };
  const mock = new MockAdapter((prompt) => {
    if (prompt.startsWith('Round')) {
      // two lenses report A, three report B → 5 raw, deduped to {A, B}; identical every round → dry-out
      return prompt.includes('per-layer') || prompt.includes('per-entity') ? A : B;
    }
    if (prompt.startsWith('Verifica')) {
      // A is real, B is not
      return { real: prompt.includes('a.ts') };
    }
    return 'unexpected';
  });

  const { result } = await runWorkflow((wf) => phase1Finding(wf), { adapter: mock });
  const kept = result as Pin[];
  assert.equal(kept.length, 1, `expected 1 survivor, got ${kept.length}`);
  assert.equal(kept[0].file, 'a.ts');

  // sanity: 3 rounds × 5 finders = 15 finder calls; 2 pins × 3 reviewers = 6 verify calls = 21
  const finders = mock.calls.filter((c) => c.prompt.startsWith('Round')).length;
  const verifies = mock.calls.filter((c) => c.prompt.startsWith('Verifica')).length;
  assert.equal(finders, 15, `finders=${finders}`);
  assert.equal(verifies, 6, `verifies=${verifies}`);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
