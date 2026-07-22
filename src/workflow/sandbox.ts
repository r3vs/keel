/**
 * Slice 3 — vm sandbox + determinism guard, for running a workflow authored as a SOURCE STRING
 * (the general `.claude/workflows/*.js` authoring experience), as opposed to a trusted TS function.
 *
 * Faithful to pi-dynamic-workflows (MIT), and for the SAME reason: a re-run must reproduce the
 * journal, so the orchestration script may not observe wall-clock time or randomness — otherwise a
 * cached call at index N could diverge from a live call and replay would be unsound.
 *   Copyright (c) 2026 QuintinShaw
 *   Copyright (c) Michael Livs (original pi-dynamic-workflows)
 *
 * Two layers, exactly as pi-dw:
 *   1. parse-time BLOCKLIST — a fast hint to the author (regex, best-effort);
 *   2. runtime PRELUDE — the real enforcement, executed in the vm realm before the user script,
 *      neutralizing Math.random / Date.now / argless Date() while keeping new Date(arg), Date.UTC,
 *      Date.parse. This is NOT a security sandbox (a determined script can escape); it guards against
 *      ACCIDENTAL nondeterminism in trusted (author / guided-LLM) scripts.
 */
import vm from 'node:vm';
import { createWorkflowContext } from './engine.ts';
import type { RunOpts, WorkflowCtx } from './engine.ts';
import type { JournalEntry } from './journal.ts';

export const DETERMINISM_BLOCKLIST = /\bDate\s*\.\s*now\b|\bMath\s*\.\s*random\b|\bnew\s+Date\s*\(\s*\)/;

export const DETERMINISM_PRELUDE = `
(function () {
  Math.random = function () {
    throw new Error('Math.random() is banned in a workflow script (non-deterministic — breaks journal replay)');
  };
  var _Date = Date;
  function SafeDate() {
    if (arguments.length === 0) {
      throw new Error('Date()/new Date() with no argument is banned in a workflow (non-deterministic); pass an explicit value');
    }
    return new _Date(...arguments);
  }
  SafeDate.UTC = _Date.UTC;
  SafeDate.parse = _Date.parse;
  SafeDate.prototype = _Date.prototype;
  SafeDate.now = function () {
    throw new Error('Date.now() is banned in a workflow script (non-deterministic — breaks journal replay)');
  };
  globalThis.Date = SafeDate;
}());
`;

/** Remove a leading `export const meta = { … }` literal (brace-matched) — vm scripts are not modules. */
export function stripLeadingExportMeta(src: string): string {
  const m = src.match(/export\s+const\s+meta\s*=\s*\{/);
  if (!m || m.index == null) return src;
  let i = m.index + m[0].length - 1; // position of the opening brace
  let depth = 0;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') {
      depth--;
      if (depth === 0) {
        i++;
        break;
      }
    }
  }
  while (i < src.length && (src[i] === ';' || src[i] === '\n' || src[i] === '\r' || src[i] === ' ' || src[i] === '\t')) i++;
  return src.slice(0, m.index) + src.slice(i);
}

export type SourceRunOpts = RunOpts & { args?: unknown; filename?: string };

export async function runWorkflowSource(
  source: string,
  opts: SourceRunOpts,
): Promise<{ result: unknown; journal: JournalEntry[] }> {
  if (DETERMINISM_BLOCKLIST.test(source)) {
    throw new Error(
      'workflow script uses a banned non-deterministic API (Date.now / Math.random / new Date()) — it would break replay',
    );
  }
  const { ctx, journal } = createWorkflowContext(opts);
  const bind = <K extends keyof WorkflowCtx>(k: K) => (ctx[k] as any).bind(ctx);

  const sandbox: Record<string, unknown> = {
    agent: bind('agent'),
    parallel: bind('parallel'),
    pipeline: bind('pipeline'),
    verify: bind('verify'),
    loopUntilDry: bind('loopUntilDry'),
    checkpoint: bind('checkpoint'),
    phase: bind('phase'),
    log: bind('log'),
    args: opts.args,
    console: { log: (...a: unknown[]) => ctx.log(a.map((x) => String(x)).join(' ')) },
  };

  const context = vm.createContext(sandbox);
  const body = stripLeadingExportMeta(source);
  const wrapped = `${DETERMINISM_PRELUDE}\n(async () => {\n${body}\n})()`;
  const result = await new vm.Script(wrapped, { filename: opts.filename ?? 'workflow.js' }).runInContext(context);
  return { result, journal: journal.dump() };
}
