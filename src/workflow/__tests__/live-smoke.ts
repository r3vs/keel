/**
 * LIVE end-to-end smoke — drives a REAL host (opencode) through the real adapter + engine.
 *
 * NOT part of `npm test`: it spends real tokens and needs opencode reachable. Manual:
 *   node --experimental-strip-types src/workflow/__tests__/live-smoke.ts
 * Here it routes opencode through WSL (`wsl.exe -- <linux-bin> …`). Proves: (1) the engine drives a
 * real host, (2) journal replay against a real host is free (0 new host calls), (3) the vm-sandbox
 * source path also drives a real host.
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import type { ExecFn } from '../exec.ts';
import { runWorkflow } from '../engine.ts';
import { runWorkflowSource } from '../sandbox.ts';
import { OpencodeCliAdapter } from '../adapters/opencode.ts';

const OPENCODE = '/home/pietr/.opencode/bin/opencode';

// Route the adapter's process boundary through WSL, counting real invocations.
function wslExec(counter: { n: number }): ExecFn {
  return (cmd, args, input) =>
    new Promise((resolve, reject) => {
      counter.n += 1;
      const cp = spawn('wsl.exe', ['--', cmd, ...args], { windowsHide: true });
      let stdout = '';
      let stderr = '';
      cp.stdout.on('data', (d) => (stdout += d.toString()));
      cp.stderr.on('data', (d) => (stderr += d.toString()));
      cp.on('error', reject);
      cp.on('close', (code) => resolve({ stdout, stderr, code: code ?? 0 }));
      if (input != null) cp.stdin.write(input);
      cp.stdin.end();
    });
}

const counter = { n: 0 };
const oc = new OpencodeCliAdapter({ bin: OPENCODE, exec: wslExec(counter) });
const PROMPT = 'Reply with exactly the digit 4 and nothing else.';

// 1 — function topology, one real call.
const r1 = await runWorkflow(
  async (wf) => {
    wf.phase('smoke');
    return wf.agent(PROMPT);
  },
  { adapter: oc, onLog: (m) => console.log('   ', m) },
);
console.log('1) live result:', JSON.stringify(r1.result), '| host calls so far:', counter.n);
assert.ok(String(r1.result).includes('4'), 'expected the model to reply 4');

// 2 — replay from journal: must not touch the host again.
const before = counter.n;
const r2 = await runWorkflow(
  async (wf) => {
    wf.phase('smoke');
    return wf.agent(PROMPT);
  },
  { adapter: oc, resume: r1.journal },
);
console.log('2) replay result:', JSON.stringify(r2.result), '| new host calls:', counter.n - before);
assert.equal(counter.n - before, 0, 'replay must be free (served from journal)');
assert.equal(r2.result, r1.result, 'replay must reproduce the result');

// 3 — vm-sandbox source path drives a real host too.
const r3 = await runWorkflowSource(`phase('smoke'); return await agent(args.p);`, {
  adapter: oc,
  args: { p: PROMPT },
});
console.log('3) vm-source live result:', JSON.stringify(r3.result));
assert.ok(String(r3.result).includes('4'), 'vm path should also reach the host');

console.log(`\nLIVE SMOKE OK — ${counter.n} real opencode call(s) total.`);
