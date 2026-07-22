/**
 * Process boundary for the CLI host adapters — injectable so adapters are unit-testable without
 * spawning a real coding-agent CLI. Tests pass a fake `ExecFn`; production uses `spawnExec`.
 */
import { spawn } from 'node:child_process';

export type ExecResult = { stdout: string; stderr: string; code: number };

/** `input`, when present, is written to the child's stdin (e.g. `codex exec` reads the prompt there). */
export type ExecFn = (cmd: string, args: string[], input?: string) => Promise<ExecResult>;

export const spawnExec: ExecFn = (cmd, args, input) =>
  new Promise<ExecResult>((resolve, reject) => {
    const cp = spawn(cmd, args, { windowsHide: true });
    let stdout = '';
    let stderr = '';
    cp.stdout.on('data', (d) => {
      stdout += d.toString();
    });
    cp.stderr.on('data', (d) => {
      stderr += d.toString();
    });
    cp.on('error', reject);
    cp.on('close', (code) => resolve({ stdout, stderr, code: code ?? 0 }));
    if (input != null) cp.stdin.write(input);
    cp.stdin.end();
  });
