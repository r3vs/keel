/**
 * LIVE end-to-end smoke — drives REAL hosts through the real adapters + engine.
 *
 * NOT part of `npm test`: spends real tokens, needs the hosts reachable (here via WSL). Manual:
 *   node --experimental-strip-types src/workflow/__tests__/live-smoke.ts            # all hosts
 *   SMOKE_ONLY=opencode node --experimental-strip-types …/live-smoke.ts             # one host
 *   SMOKE_ONLY=codex    node --experimental-strip-types …/live-smoke.ts
 * Proves: (1) the engine drives a real host, (2) journal replay against a real host is free
 * (0 new host calls), (3) the vm-sandbox source path also drives a real host, (4) a real host
 * failure (e.g. codex usage-limit at rc=0) surfaces as a thrown error, not a silent ''.
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import type { ExecFn } from '../exec.ts';
import { runWorkflow } from '../engine.ts';
import { runWorkflowSource } from '../sandbox.ts';
import { OpencodeCliAdapter } from '../adapters/opencode.ts';
import { CodexCliAdapter } from '../adapters/codex.ts';

const OPENCODE = '/home/pietr/.opencode/bin/opencode';
const CODEX = '/home/pietr/.local/bin/codex';
const PROMPT = 'Reply with exactly the digit 4 and nothing else.';

const only = process.env.SMOKE_ONLY;
const runOpencode = !only || only === 'opencode';
const runCodex = !only || only === 'codex';

// Route an adapter's process boundary through WSL, counting real invocations.
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

const topo = async (wf: { phase(t: string): void; agent(p: string): Promise<unknown> }) => {
  wf.phase('smoke');
  return wf.agent(PROMPT);
};

if (runOpencode) {
  const counter = { n: 0 };
  const oc = new OpencodeCliAdapter({ bin: OPENCODE, exec: wslExec(counter) });

  const r1 = await runWorkflow(topo, { adapter: oc, onLog: (m) => console.log('   ', m) });
  console.log('opencode 1) live result:', JSON.stringify(r1.result), '| host calls:', counter.n);
  assert.ok(String(r1.result).includes('4'), 'opencode should reply 4');

  const before = counter.n;
  const r2 = await runWorkflow(topo, { adapter: oc, resume: r1.journal });
  console.log('opencode 2) replay:', JSON.stringify(r2.result), '| new host calls:', counter.n - before);
  assert.equal(counter.n - before, 0, 'replay must be free (served from journal)');
  assert.equal(r2.result, r1.result, 'replay must reproduce the result');

  const r3 = await runWorkflowSource(`phase('smoke'); return await agent(args.p);`, {
    adapter: oc,
    args: { p: PROMPT },
  });
  console.log('opencode 3) vm-source result:', JSON.stringify(r3.result));
  assert.ok(String(r3.result).includes('4'), 'vm path should also reach the host');
  console.log(`opencode END-TO-END OK — ${counter.n} real call(s).`);
}

if (runCodex) {
  const counter = { n: 0 };
  const cx = new CodexCliAdapter({ bin: CODEX, exec: wslExec(counter) });
  try {
    const rc = await runWorkflow(topo, { adapter: cx });
    console.log('codex) live result:', JSON.stringify(rc.result));
    assert.ok(String(rc.result).includes('4'), 'codex should reply 4');
    console.log('codex END-TO-END OK (success path).');
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    // A real host failure (e.g. usage-limit at rc=0) must surface as a throw, not a silent ''.
    if (/usage limit|turn failed/i.test(msg)) {
      console.log('codex) fail-loud verified against REAL host:', msg.replace(/\s+/g, ' ').slice(0, 90));
    } else {
      throw e;
    }
  }
}
