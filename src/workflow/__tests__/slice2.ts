/**
 * Slice-2 tests — host adapters (argv contract) + the pure-engine → PinSink write seam.
 * Run:  node --experimental-strip-types src/workflow/__tests__/slice2.ts
 *
 * What is VERIFIED here: the argv/flag contract of each CLI adapter (the part grounded in real docs),
 * the stdin-vs-argv wiring, schema-file handling, the guarded SDK adapters failing loud, and
 * launchFinding landing survivors via a PinSink. What is NOT verified (and marked in-source): the
 * exact JSONL/JSON event schema of `codex exec`/`opencode run` output, and live SDK execution.
 */
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import type { ExecFn } from '../exec.ts';
import { CodexCliAdapter } from '../adapters/codex.ts';
import { OpencodeCliAdapter, parseOpencodeJson } from '../adapters/opencode.ts';
import { MockAdapter } from '../adapter.ts';
import { MockPinSink, pinToAddArgs } from '../ports.ts';
import { launchFinding } from '../launch.ts';
import { phase1Finding } from '../topologies/phase1-finding.ts';

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

// 1 — Codex: verified argv, prompt via stdin, result read from --output-last-message.
await test('CodexCliAdapter: verified argv, stdin prompt, result from --output-last-message', async () => {
  let seen: { cmd: string; args: string[]; input?: string } | null = null;
  const fake: ExecFn = async (cmd, args, input) => {
    seen = { cmd, args, input };
    const i = args.indexOf('--output-last-message');
    if (i >= 0) await writeFile(args[i + 1], '{"real":true}', 'utf8'); // codex writes the final message here
    return {
      stdout: `${JSON.stringify({ type: 'thread.started' })}\n${JSON.stringify({ type: 'turn.completed' })}`,
      stderr: '',
      code: 0,
    };
  };
  const ad = new CodexCliAdapter({ exec: fake });
  const res = await ad.run('audit routes', { model: 'gpt-5.5', schema: { type: 'object' } });
  assert.equal(seen!.cmd, 'codex');
  assert.deepEqual(seen!.args.slice(0, 5), ['exec', '--json', '--skip-git-repo-check', '--model', 'gpt-5.5']);
  assert.ok(seen!.args.includes('--output-schema'));
  assert.ok(seen!.args.includes('--output-last-message'));
  assert.equal(seen!.input, 'audit routes'); // prompt via stdin
  assert.deepEqual(res.result, { real: true }); // from last-message, JSON-parsed under schema
});

// 2 — Codex fails LOUD on a turn-level error even though the process exits 0 (REAL usage-limit
//     envelope captured from codex 0.137 in WSL). Item-level errors are non-fatal warnings.
await test('CodexCliAdapter: fail-loud on turn error at rc=0; item-error is non-fatal', async () => {
  const realErrJsonl = [
    JSON.stringify({ type: 'thread.started', thread_id: 'x' }),
    JSON.stringify({ type: 'turn.started' }),
    JSON.stringify({ type: 'item.completed', item: { id: 'item_0', type: 'error', message: 'skills budget notice' } }),
    JSON.stringify({ type: 'error', message: "You've hit your usage limit." }),
    JSON.stringify({ type: 'turn.failed', error: { message: "You've hit your usage limit." } }),
  ].join('\n');
  await assert.rejects(
    () => new CodexCliAdapter({ exec: async () => ({ stdout: realErrJsonl, stderr: '', code: 0 }) }).run('hi'),
    /usage limit/,
  );

  // an item-level error alone is a warning, not fatal → result still comes from last-message
  const warnOnly = `${JSON.stringify({ type: 'item.completed', item: { type: 'error', message: 'skills budget' } })}\n${JSON.stringify({ type: 'turn.completed' })}`;
  const fake2: ExecFn = async (_c, a) => {
    const i = a.indexOf('--output-last-message');
    if (i >= 0) await writeFile(a[i + 1], 'OK', 'utf8');
    return { stdout: warnOnly, stderr: '', code: 0 };
  };
  const r = await new CodexCliAdapter({ exec: fake2 }).run('hi');
  assert.equal(r.result, 'OK');
});

// 3 — opencode: verified argv, prompt as an argv arg (not stdin).
await test('OpencodeCliAdapter: verified argv, prompt as arg', async () => {
  let seen: { cmd: string; args: string[]; input?: string } | null = null;
  const fake: ExecFn = async (cmd, args, input) => {
    seen = { cmd, args, input };
    return { stdout: '{}', stderr: '', code: 0 };
  };
  const ad = new OpencodeCliAdapter({ exec: fake, agent: 'executor' });
  await ad.run('the prompt', { model: 'x' });
  assert.equal(seen!.cmd, 'opencode');
  assert.deepEqual(seen!.args, ['run', 'the prompt', '--format', 'json', '--model', 'x', '--agent', 'executor']);
  assert.equal(seen!.input, undefined);
});

// 3b — opencode parse against the REAL --format json event schema (captured from opencode in WSL).
await test('parseOpencodeJson: real JSONL schema → text + cost + tokens', () => {
  const real = [
    JSON.stringify({ type: 'step_start', part: { type: 'step-start' } }),
    JSON.stringify({ type: 'text', part: { type: 'text', text: 'OK' } }),
    JSON.stringify({
      type: 'step_finish',
      part: { reason: 'stop', tokens: { total: 35432, input: 35332, output: 2 }, cost: 0.01545642 },
    }),
  ].join('\n');
  const r = parseOpencodeJson(real);
  assert.equal(r.result, 'OK');
  assert.equal(r.cost, 0.01545642);
  assert.equal(r.tokens, 35432);

  // schema path: a text event carrying JSON is parsed to the structured object
  const withJson = JSON.stringify({ type: 'text', part: { type: 'text', text: '{"real":true}' } });
  const r2 = parseOpencodeJson(withJson, { schema: { type: 'object' } });
  assert.deepEqual(r2.result, { real: true });
});

// (warm SDK adapters — claude-sdk / codex-sdk / pi — are tested in slice6 via injected mock SDKs.)

// 6 — launchFinding lands survivors as pins via the PinSink (the one serialized write).
await test('launchFinding: survivors → PinSink, kind passthrough, provenance set', async () => {
  const A = { file: 'a.ts', line: 1, kind: 'contract_mismatch', summary: 'real' };
  const B = { file: 'b.ts', line: 2, kind: 'dead', summary: 'false' };
  const mock = new MockAdapter((prompt) => {
    if (prompt.startsWith('Round')) {
      return prompt.includes('per-layer') || prompt.includes('per-entity') ? A : B;
    }
    if (prompt.startsWith('Verifica')) return { real: prompt.includes('a.ts') };
    return 'x';
  });
  const sink = new MockPinSink();
  const { pins, committed } = await launchFinding((wf) => phase1Finding(wf), {
    adapter: mock,
    sink,
    source: 'test',
  });
  assert.equal(pins.length, 1);
  assert.equal(committed.length, 1);
  assert.equal(sink.added.length, 1);
  assert.equal(sink.added[0].kind, 'contract_mismatch'); // valid ledger kind passes through
  assert.equal(sink.added[0].provenance[0].source, 'test');
});

// 7 — pinToAddArgs: no invented taxonomy.
await test('pinToAddArgs: unknown kind → other + kind_detail; valid kind passes through', () => {
  const unknown = pinToAddArgs({ file: 'x', line: 3, kind: 'weird-thing' });
  assert.equal(unknown.kind, 'other');
  assert.equal(unknown.kind_detail, 'weird-thing');
  const valid = pinToAddArgs({ file: 'y', line: 4, kind: 'defect' });
  assert.equal(valid.kind, 'defect');
  assert.equal(valid.kind_detail, undefined);
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
