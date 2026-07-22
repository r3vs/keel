/**
 * Slice-5 tests — the two remaining flagship topologies (challenger-verify, build-waves) and the
 * engine features they need (checkpoint gate, real git-worktree isolation).
 * Run:  node --experimental-strip-types src/workflow/__tests__/slice5.ts
 */
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { runWorkflow } from '../engine.ts';
import { MockAdapter } from '../adapter.ts';
import { challengerVerify } from '../topologies/challenger-verify.ts';
import { buildWaves } from '../topologies/build-waves.ts';
import { withWorktree, WorktreeAdapter, safeName } from '../worktree.ts';
import { runCli, TOPOLOGIES, parseArgs } from '../cli.ts';

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

function tempGitRepo(): string {
  const dir = mkdtempSync(join(tmpdir(), 'wf-wt-'));
  const g = (args: string[]) => execFileSync('git', args, { cwd: dir, stdio: 'pipe' });
  g(['init', '-q']);
  g(['config', 'user.email', 't@t.dev']);
  g(['config', 'user.name', 'tester']);
  writeFileSync(join(dir, 'README.md'), 'x\n');
  g(['add', '.']);
  g(['commit', '-q', '-m', 'init']);
  return dir;
}

// 1 — challenger-verify: refuted oracle → ChallengeEvent (reopen), sound oracle → none.
await test('challengerVerify: fatal refutation reopens, survivor does not', async () => {
  const oracles = [
    { id: 'AC-1', statement: 'sound' },
    { id: 'AC-2', statement: 'weak' },
  ];
  const mock = new MockAdapter((prompt) =>
    prompt.includes('"id":"AC-2"') && prompt.includes('unfalsifiable') ? { fatal: true, reason: 'no test' } : { fatal: false },
  );
  const { result } = await runWorkflow((wf) => challengerVerify(wf, { oracles }), { adapter: mock });
  const events = result as Array<{ event: string; reopen: string }>;
  assert.equal(events.length, 1);
  assert.equal(events[0].event, 'ChallengeEvent');
  assert.equal(events[0].reopen, 'AC-2');
});

// 2 — checkpoint gate: auto-approve headless, abort on demand, and journaled replay.
await test('checkpoint: auto-approve / abort / journaled replay', async () => {
  const { result: ok } = await runWorkflow((wf) => wf.checkpoint('go?', { default: 'X' }), {
    adapter: new MockAdapter(),
  });
  assert.deepEqual(ok, { approved: true, value: 'X' });

  const { result: stop } = await runWorkflow((wf) => wf.checkpoint('halt?', { headless: 'abort' }), {
    adapter: new MockAdapter(),
  });
  assert.deepEqual(stop, { approved: false, aborted: true });

  const script = async (wf: any) => {
    const a = await wf.agent('x');
    return wf.checkpoint('ok?', { default: a });
  };
  const m1 = new MockAdapter(() => 'A');
  const run1 = await runWorkflow(script, { adapter: m1 });
  assert.deepEqual(run1.result, { approved: true, value: 'A' });
  const m2 = new MockAdapter(() => 'SHOULD_NOT_BE_CALLED');
  const run2 = await runWorkflow(script, { adapter: m2, resume: run1.journal });
  assert.deepEqual(run2.result, { approved: true, value: 'A' });
  assert.equal(m2.calls.length, 0); // agent + checkpoint both replayed from journal
});

// 3 — withWorktree: real git worktree created, fn sees repo content, cleaned up after.
await test('withWorktree: creates an isolated checkout and removes it', async () => {
  const repo = tempGitRepo();
  try {
    let seen = '';
    const r = await withWorktree(repo, 'wf/test-1', async (wt) => {
      seen = wt;
      assert.ok(existsSync(wt), 'worktree should exist during fn');
      assert.ok(existsSync(join(wt, 'README.md')), 'worktree carries the repo content');
      return 42;
    });
    assert.equal(r, 42);
    assert.ok(!existsSync(seen), 'worktree checkout removed after');
    assert.equal(safeName('wf/test-1'), 'wf-test-1');
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

// 4 — WorktreeAdapter: isolates only when asked, passing the worktree as cwd to the inner adapter.
await test('WorktreeAdapter: isolation:worktree sets cwd; plain run delegates untouched', async () => {
  const repo = tempGitRepo();
  try {
    const mock = new MockAdapter(() => 'ok');
    const wt = new WorktreeAdapter(mock, { repoRoot: repo });

    await wt.run('do', { isolation: 'worktree', label: 'item A' });
    const cwd = mock.calls[0].opts?.cwd;
    assert.ok(cwd && cwd.includes('.workflow-worktrees'), 'isolated run gets a worktree cwd');
    assert.ok(!existsSync(cwd as string), 'worktree cleaned up after the run');

    await wt.run('plain', {});
    assert.equal(mock.calls[1].opts?.cwd, undefined, 'non-isolated run gets no cwd');
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

// 5 — build-waves: one executor per item, isolation + executor agentType, checkpoint per wave.
await test('buildWaves: executor-per-item, worktree isolation, wave checkpoints', async () => {
  const waves = [
    { index: 0, items: [{ id: 'B-1' }, { id: 'B-2' }] },
    { index: 1, items: [{ id: 'B-3' }] },
  ];
  const mock = new MockAdapter(() => 'done');
  const { result } = await runWorkflow((wf) => buildWaves(wf, { waves }), { adapter: mock });
  const summary = result as Array<{ wave: number; items: string[]; checkpoint: unknown }>;

  assert.equal(summary.length, 2);
  assert.deepEqual(summary[0].items, ['B-1', 'B-2']);
  assert.deepEqual(summary[1].items, ['B-3']);
  assert.deepEqual(summary[0].checkpoint, { approved: true, value: null });

  assert.equal(mock.calls.length, 3); // one executor per item
  for (const c of mock.calls) {
    assert.equal(c.opts?.isolation, 'worktree');
    assert.equal(c.opts?.agentType, 'executor');
  }
});

// 6 — CLI: all three topologies registered; runCli routes with injected args.
await test('cli: three topologies registered; runCli routes challenger-verify', async () => {
  assert.deepEqual(Object.keys(TOPOLOGIES).sort(), ['build-waves', 'challenger-verify', 'phase1-finding']);
  const p = parseArgs(['--topology', 'build-waves', '--args-file', 'w.json', '--worktree']);
  assert.equal(p.topology, 'build-waves');
  assert.equal(p.argsFile, 'w.json');
  assert.equal(p.worktree, true);

  const mock = new MockAdapter((prompt) => (prompt.includes('unfalsifiable') ? { fatal: true } : { fatal: false }));
  const events = await runCli(
    { host: 'mock', topology: 'challenger-verify', worktree: false, json: true },
    { adapters: { mock: () => mock }, args: { oracles: [{ id: 'AC-2', statement: 'weak' }] } },
  );
  assert.equal((events as unknown[]).length, 1);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
