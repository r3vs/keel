/**
 * The deterministic workflow runner — the ceiling engine.
 *
 * Design adapted from pi-dynamic-workflows (MIT): positional-index journal, longest-unchanged-prefix
 * replay, concurrency cap, and the read-only fan-out primitives. The Pi-specific spawn is replaced by
 * a pluggable `SpawnAdapter` (see `adapter.ts`).
 *   Copyright (c) 2026 QuintinShaw
 *   Copyright (c) Michael Livs (original pi-dynamic-workflows)
 *
 * SLICE 0 deliberate simplifications (see `docs/design/dynamic-workflows.md` §9):
 *   - no `vm` sandbox yet — the topology is a trusted function receiving the ctx, not globals
 *     injected into a realm; the determinism guard (blocking Date.now/Math.random) is a later slice;
 *   - no worktree isolation yet;
 *   - cost-only accounting; no per-phase budget.
 *
 * Invariants held now (design §5): orchestration is pure — the engine never writes the ledger;
 * fan-out is read-only; results are returned as data for the executor to land as pins.
 */
import type { SpawnAdapter, SpawnOpts } from './adapter.ts';
import { Journal, callHash } from './journal.ts';
import type { JournalEntry } from './journal.ts';

export type VerifyOpts = {
  reviewers?: number;
  lens?: string | string[];
  threshold?: number;
  /** Roster role the reviewers run as (model-tiers picks their model per host). Defaults to host default. */
  agentType?: string;
};
export type VerifyResult = { real: boolean; realCount: number; total: number; votes: unknown[] };

export type LoopOpts = {
  round: (i: number) => unknown[] | Promise<unknown[]>;
  key?: (x: any) => string;
  consecutiveEmpty?: number;
  maxRounds?: number;
};

export type CheckpointOpts = {
  default?: unknown;
  kind?: 'confirm' | 'input' | 'select';
  headless?: 'default' | 'abort';
  choices?: string[];
};

export interface WorkflowCtx {
  readonly runId: string;
  /** Spawn one read-only sub-agent. Journaled by positional call index. */
  agent(prompt: string, opts?: SpawnOpts): Promise<unknown>;
  /** Run thunks concurrently; preserves input order; a failing thunk becomes `null`. */
  parallel<T>(thunks: Array<() => Promise<T>>): Promise<Array<T | null>>;
  /** Run each item through the stages independently (no barrier between stages). */
  pipeline(
    items: unknown[],
    ...stages: Array<(prev: any, item: any, i: number) => unknown>
  ): Promise<unknown[]>;
  /** Perspective-diverse adversarial verify: N reviewers (distinct lenses) vote; majority decides. */
  verify(item: unknown, opts?: VerifyOpts): Promise<VerifyResult>;
  /** Repeat discovery rounds until `consecutiveEmpty` rounds surface nothing new (deduped by `key`). */
  loopUntilDry(opts: LoopOpts): Promise<unknown[]>;
  /** A journaled approval gate. Headless (no human) returns `{approved:true, value:default}`, or
   * `{approved:false, aborted:true}` when `headless:'abort'`. Journaled like agent() so replay is stable. */
  checkpoint(prompt: string, opts?: CheckpointOpts): Promise<unknown>;
  phase(title: string): void;
  log(msg: string): void;
}

export type RunOpts = {
  adapter: SpawnAdapter;
  resume?: JournalEntry[];
  runId?: string;
  concurrency?: number;
  onLog?: (msg: string) => void;
  onJournal?: (j: JournalEntry[]) => void;
};

const MAX_CONCURRENCY = 16; // matches pi-dw / Claude Code

class Semaphore {
  max: number;
  active = 0;
  queue: Array<() => void> = [];

  constructor(max: number) {
    this.max = max;
  }

  async run<T>(fn: () => Promise<T>): Promise<T> {
    if (this.active >= this.max) await new Promise<void>((res) => this.queue.push(res));
    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
      const next = this.queue.shift();
      if (next) next();
    }
  }
}

/**
 * Build the primitives + journal for a run, WITHOUT executing a script. Shared by `runWorkflow`
 * (topology-as-function) and `runWorkflowSource` (topology-as-vm-source, see `sandbox.ts`), so both
 * paths use identical semantics — one implementation, two front doors.
 */
export function createWorkflowContext(opts: RunOpts): { ctx: WorkflowCtx; journal: Journal } {
  const runId = opts.runId ?? 'wf';
  const journal = new Journal(opts.resume);
  const sem = new Semaphore(Math.min(MAX_CONCURRENCY, opts.concurrency ?? MAX_CONCURRENCY));
  const log = opts.onLog ?? (() => {});
  let seq = 0;
  let currentPhase = '';

  const ctx: WorkflowCtx = {
    runId,

    phase(title) {
      currentPhase = title;
      log(`▸ phase: ${title}`);
    },

    log(msg) {
      log(msg);
    },

    async agent(prompt, aopts) {
      // callIndex assigned synchronously, in lexical order, BEFORE the limiter — the property the
      // whole determinism story rests on.
      const index = seq++;
      const phase = aopts?.phase ?? currentPhase;
      const hash = callHash('agent', {
        prompt,
        model: aopts?.model ?? null,
        phase,
        agentType: aopts?.agentType ?? null,
        schema: aopts?.schema ?? null,
      });
      const cached = journal.lookup(runId, index, hash);
      if (cached) {
        log(`· replay #${index} (${aopts?.label ?? 'agent'})`);
        return cached.result;
      }
      journal.miss(index);
      const res = await sem.run(() => opts.adapter.run(prompt, { ...aopts, phase }));
      journal.put({ index, runId, hash, result: res.result });
      opts.onJournal?.(journal.dump());
      return res.result;
    },

    async parallel(thunks) {
      return Promise.all(
        thunks.map(async (t) => {
          try {
            return await t();
          } catch (e) {
            log(`× parallel item failed: ${String(e)}`);
            return null;
          }
        }),
      );
    },

    async pipeline(items, ...stages) {
      return Promise.all(
        items.map(async (item, i) => {
          let cur: unknown = item;
          for (const stage of stages) {
            try {
              cur = await stage(cur, item, i);
            } catch (e) {
              log(`× pipeline item ${i} failed: ${String(e)}`);
              return null;
            }
          }
          return cur;
        }),
      );
    },

    async verify(item, vopts) {
      const lensArr = Array.isArray(vopts?.lens) ? vopts?.lens : vopts?.lens ? [vopts.lens] : [];
      const n = lensArr.length || (vopts?.reviewers ?? 2);
      const threshold = vopts?.threshold ?? 0.5;
      const votes = await ctx.parallel(
        Array.from({ length: n }, (_x, i) => async () => {
          const lens = lensArr[i];
          return ctx.agent(
            `Verifica avversariale${lens ? ` (lente: ${lens})` : ''}. Item: ${JSON.stringify(item)}. È REALE?`,
            {
              schema: { type: 'object', properties: { real: { type: 'boolean' } }, required: ['real'] },
              label: `verify:${i}`,
              agentType: vopts?.agentType,
            },
          );
        }),
      );
      const realCount = votes.filter((v) => v != null && (v as any).real === true).length;
      const total = votes.length;
      return { real: total > 0 && realCount / total >= threshold, realCount, total, votes };
    },

    async loopUntilDry(lopts) {
      const consecutiveEmpty = lopts.consecutiveEmpty ?? 2;
      const maxRounds = lopts.maxRounds ?? 50;
      const key = lopts.key ?? ((x: unknown) => JSON.stringify(x));
      const seen = new Set<string>();
      const all: unknown[] = [];
      let dry = 0;
      let i = 0;
      while (dry < consecutiveEmpty && i < maxRounds) {
        const batch = await lopts.round(i);
        const flat = (Array.isArray(batch) ? batch : [batch]).flat().filter((x) => x != null);
        const fresh = flat.filter((x) => {
          const k = key(x);
          if (seen.has(k)) return false;
          seen.add(k);
          return true;
        });
        if (fresh.length === 0) {
          dry++;
        } else {
          dry = 0;
          all.push(...fresh);
        }
        i++;
      }
      return all;
    },

    async checkpoint(prompt, copts) {
      // callIndex before any work, like agent() — so the gate replays deterministically.
      const index = seq++;
      const hash = callHash('checkpoint', {
        prompt,
        kind: copts?.kind ?? 'confirm',
        default: copts?.default ?? null,
        headless: copts?.headless ?? 'default',
      });
      const cached = journal.lookup(runId, index, hash);
      if (cached) {
        log(`· replay checkpoint #${index}`);
        return cached.result;
      }
      journal.miss(index);
      // Non-interactive: no human to prompt. Auto-approve (or abort), journaled so replay reproduces it.
      const result =
        copts?.headless === 'abort'
          ? { approved: false, aborted: true }
          : { approved: true, value: copts?.default ?? null };
      log(`◆ checkpoint #${index} — ${copts?.headless === 'abort' ? 'ABORT' : 'auto-approve'}: ${prompt}`);
      journal.put({ index, runId, hash, result });
      opts.onJournal?.(journal.dump());
      return result;
    },
  };

  return { ctx, journal };
}

export async function runWorkflow(
  script: (wf: WorkflowCtx) => Promise<unknown>,
  opts: RunOpts,
): Promise<{ result: unknown; journal: JournalEntry[] }> {
  const { ctx, journal } = createWorkflowContext(opts);
  const result = await script(ctx);
  return { result, journal: journal.dump() };
}
