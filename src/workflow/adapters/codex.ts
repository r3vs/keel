/**
 * Codex adapter — `codex exec`, headless.
 *
 * VERIFIED flags (deepwiki, 2026-07-22): prompt read from STDIN; `--model <id>`;
 * `--output-schema <file>` for JSON-schema structured output; `--json` emits JSONL events.
 * UNVERIFIED here: the exact JSONL event schema — `parseCodexJsonl` is best-effort and MUST be
 * re-checked against a real `codex exec --json` sample. The argv contract below is what is tested.
 */
import { writeFile, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';
import type { ExecFn } from '../exec.ts';
import { spawnExec } from '../exec.ts';

let tmpCounter = 0;

export function parseCodexJsonl(stdout: string, opts?: SpawnOpts): SpawnResult {
  const lines = stdout.split('\n').map((l) => l.trim()).filter(Boolean);
  let lastText: string | undefined;
  let cost: number | undefined;
  let tokens: number | undefined;
  for (const line of lines) {
    let ev: any;
    try {
      ev = JSON.parse(line);
    } catch {
      continue; // not every line is JSON
    }
    const text = ev?.msg?.text ?? ev?.text ?? ev?.message?.content ?? ev?.item?.text;
    if (typeof text === 'string') lastText = text;
    const usage = ev?.usage ?? ev?.msg?.usage;
    if (usage) {
      tokens = usage.total_tokens ?? tokens;
      cost = usage.cost_usd ?? usage.total_cost_usd ?? cost;
    }
  }
  let result: string | Record<string, unknown> = lastText ?? '';
  if (opts?.schema && typeof lastText === 'string') {
    try {
      result = JSON.parse(lastText) as Record<string, unknown>;
    } catch {
      /* leave as text */
    }
  }
  return { result, cost, tokens };
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

  buildArgs(opts?: SpawnOpts, schemaFile?: string): string[] {
    const args = ['exec', '--json'];
    const model = opts?.model ?? this.defaultModel;
    if (model) args.push('--model', model);
    if (schemaFile) args.push('--output-schema', schemaFile);
    return args;
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    let schemaFile: string | undefined;
    if (opts?.schema) {
      tmpCounter += 1;
      schemaFile = join(tmpdir(), `codex-schema-${process.pid}-${tmpCounter}.json`);
      await writeFile(schemaFile, JSON.stringify(opts.schema), 'utf8');
    }
    try {
      const { stdout } = await this.exec(this.bin, this.buildArgs(opts, schemaFile), prompt);
      return parseCodexJsonl(stdout, opts);
    } finally {
      if (schemaFile) await unlink(schemaFile).catch(() => {});
    }
  }
}
