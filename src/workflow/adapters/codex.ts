/**
 * Codex adapter — `codex exec`, headless.
 *
 * VERIFIED against a real probe (codex-cli 0.137.0 in WSL, 2026-07-22):
 *   - flags: prompt via STDIN (or argv); `-m/--model`; `--output-schema <file>` (JSON schema);
 *     `--output-last-message <file>` (writes the FINAL message — we read the result from here, so we
 *     don't depend on the per-item event shape); `--json` (JSONL events); `--skip-git-repo-check`
 *     (needed when cwd is not a git repo).
 *   - event envelope: `{type:'thread.started'}` `{type:'turn.started'}`
 *     `{type:'item.completed', item:{…}}` `{type:'turn.completed', …}` and, on failure,
 *     `{type:'error', message}` / `{type:'turn.failed', error:{message}}`.
 *   - CORRECTNESS: codex exits **0 even when the turn fails** (observed: a ChatGPT usage-limit error
 *     returned rc=0). So exit code is NOT a success signal — we detect turn-level errors in the JSONL
 *     and FAIL LOUD (mirrors pi-dw's non-recoverable PROVIDER_USAGE_LIMIT), never return '' silently.
 * NOT yet seen (quota-limited probe): the exact success `item`/usage shape — `codexUsage` is best-effort.
 */
import { writeFile, readFile, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';
import type { ExecFn } from '../exec.ts';
import { spawnExec } from '../exec.ts';

let tmpCounter = 0;
function tmpPath(tag: string): string {
  tmpCounter += 1;
  return join(tmpdir(), `codex-${tag}-${process.pid}-${tmpCounter}`);
}

/** Return the message of the first FATAL (turn-level) error event, or null. Item-level errors are
 * non-fatal warnings (e.g. the skills-budget notice) and are ignored — verified in the real probe. */
export function firstCodexError(stdout: string): string | null {
  for (const line of stdout.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    let ev: any;
    try {
      ev = JSON.parse(t);
    } catch {
      continue;
    }
    if (ev?.type === 'error') return String(ev.message ?? 'unknown error');
    if (ev?.type === 'turn.failed') return String(ev?.error?.message ?? 'turn failed');
  }
  return null;
}

/** Best-effort usage scan (success/usage event shape NOT yet observed — quota-limited probe). */
export function codexUsage(stdout: string): { cost?: number; tokens?: number } {
  let cost: number | undefined;
  let tokens: number | undefined;
  for (const line of stdout.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    let ev: any;
    try {
      ev = JSON.parse(t);
    } catch {
      continue;
    }
    const u = ev?.usage ?? ev?.turn?.usage ?? (ev?.type === 'turn.completed' ? ev?.usage : undefined);
    if (u) {
      tokens = u.total_tokens ?? u.total ?? tokens;
      cost = u.cost_usd ?? u.cost ?? cost;
    }
  }
  return { cost, tokens };
}

export class CodexCliAdapter implements SpawnAdapter {
  host = 'codex';
  exec: ExecFn;
  defaultModel?: string;
  bin: string;

  constructor(opts?: { exec?: ExecFn; model?: string; bin?: string }) {
    this.exec = opts?.exec ?? spawnExec;
    this.defaultModel = opts?.model;
    this.bin = opts?.bin ?? 'codex';
  }

  buildArgs(opts: SpawnOpts | undefined, lastFile: string, schemaFile?: string): string[] {
    const args = ['exec', '--json', '--skip-git-repo-check'];
    const model = opts?.model ?? this.defaultModel;
    if (model) args.push('--model', model);
    if (schemaFile) args.push('--output-schema', schemaFile);
    args.push('--output-last-message', lastFile);
    return args;
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    const lastFile = tmpPath('last');
    const schemaFile = opts?.schema ? tmpPath('schema') : undefined;
    if (schemaFile) await writeFile(schemaFile, JSON.stringify(opts!.schema), 'utf8');
    try {
      const { stdout } = await this.exec(this.bin, this.buildArgs(opts, lastFile, schemaFile), prompt);

      // codex exits 0 even on failure — detect turn-level errors and fail loud.
      const err = firstCodexError(stdout);
      if (err) throw new Error(`codex turn failed: ${err}`);

      let last = '';
      try {
        last = (await readFile(lastFile, 'utf8')).trim();
      } catch {
        /* no last-message file written */
      }
      let result: string | Record<string, unknown> = last;
      if (opts?.schema && last) {
        try {
          result = JSON.parse(last) as Record<string, unknown>;
        } catch {
          /* leave as text */
        }
      }
      const usage = codexUsage(stdout);
      return { result, cost: usage.cost, tokens: usage.tokens };
    } finally {
      if (schemaFile) await unlink(schemaFile).catch(() => {});
      await unlink(lastFile).catch(() => {});
    }
  }
}
