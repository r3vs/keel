/**
 * opencode adapter — `opencode run`, headless.
 *
 * VERIFIED flags (deepwiki, 2026-07-22): `opencode run "<prompt>" --model <id> --agent <name>
 * --format json`; the prompt is an argv arg (not stdin); `opencode serve` + `--attach <url>` gives a
 * warm server (later slice).
 *
 * VERIFIED event schema (real probe, opencode in WSL, 2026-07-22): `--format json` emits JSONL, one
 * event per line:
 *   { "type":"step_start",  "part":{ "type":"step-start", … } }
 *   { "type":"text",        "part":{ "type":"text", "text":"…" } }
 *   { "type":"step_finish", "part":{ "reason":"stop", "tokens":{ "total":N, "input":…, "output":… }, "cost":<usd> } }
 * So opencode exposes BOTH cost and token count (unlike the Claude SDK, which gives cost only).
 */
import type { SpawnAdapter, SpawnOpts, SpawnResult } from '../adapter.ts';
import type { ExecFn } from '../exec.ts';
import { spawnExec } from '../exec.ts';

function parseJsonl(stdout: string): any[] {
  const lines = stdout.split('\n').map((l) => l.trim()).filter(Boolean);
  const out: any[] = [];
  for (const l of lines) {
    try {
      out.push(JSON.parse(l));
    } catch {
      /* not every line is JSON */
    }
  }
  if (out.length) return out;
  const trimmed = stdout.trim();
  if (!trimmed) return [];
  try {
    const one = JSON.parse(trimmed);
    return Array.isArray(one) ? one : [one];
  } catch {
    return [];
  }
}

export function parseOpencodeJson(stdout: string, opts?: SpawnOpts): SpawnResult {
  const events = parseJsonl(stdout);
  const textParts: string[] = [];
  let cost: number | undefined;
  let tokens: number | undefined;
  for (const ev of events) {
    if (ev?.type === 'text' && typeof ev?.part?.text === 'string') {
      textParts.push(ev.part.text);
    }
    if (ev?.type === 'step_finish') {
      if (typeof ev?.part?.cost === 'number') cost = ev.part.cost;
      const t = ev?.part?.tokens?.total;
      if (typeof t === 'number') tokens = t;
    }
  }
  const text = textParts.join('');
  let result: string | Record<string, unknown> = text;
  if (opts?.schema && text) {
    try {
      result = JSON.parse(text) as Record<string, unknown>;
    } catch {
      /* leave as text */
    }
  }
  return { result, cost, tokens };
}

export class OpencodeCliAdapter implements SpawnAdapter {
  host = 'opencode';
  exec: ExecFn;
  defaultModel?: string;
  defaultAgent?: string;
  bin: string;

  constructor(opts?: { exec?: ExecFn; model?: string; agent?: string; bin?: string }) {
    this.exec = opts?.exec ?? spawnExec;
    this.defaultModel = opts?.model;
    this.defaultAgent = opts?.agent;
    this.bin = opts?.bin ?? 'opencode';
  }

  buildArgs(prompt: string, opts?: SpawnOpts): string[] {
    const args = ['run', prompt, '--format', 'json'];
    const model = opts?.model ?? this.defaultModel;
    if (model) args.push('--model', model);
    const agent = opts?.agentType ?? this.defaultAgent;
    if (agent) args.push('--agent', agent);
    return args;
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    const { stdout } = await this.exec(this.bin, this.buildArgs(prompt, opts), undefined, opts?.cwd);
    return parseOpencodeJson(stdout, opts);
  }
}
