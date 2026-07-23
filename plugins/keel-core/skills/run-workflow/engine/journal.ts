/**
 * The journal — deterministic replay by positional call index.
 *
 * Faithful to pi-dynamic-workflows (MIT), which itself replicates Claude Code's Workflow contract:
 *   - each `agent()`/`checkpoint()` gets a `callIndex` assigned in lexical call order (BEFORE the
 *     concurrency limiter), so a fixed script replays identically regardless of which parallel agent
 *     finishes first;
 *   - the entry key is `${runId}:${callIndex}` (a nested workflow restarts its own index and gets a
 *     suffixed runId, so child index-0 does not collide with parent index-0 — later slice);
 *   - a call is served from cache only if its identity `hash` matches AND its index is before the
 *     first miss ("longest-unchanged-prefix"): editing a call invalidates itself and everything
 *     downstream, the prefix before it stays cached.
 *
 * See `docs/design/dynamic-workflows.md` §4.
 */
import { createHash } from 'node:crypto';

export type JournalEntry = {
  index: number;
  runId: string;
  hash: string;
  result: unknown;
};

/** sha256 over the call's identity — the fields that, if changed, must invalidate the cached result. */
export function callHash(kind: string, identity: Record<string, unknown>): string {
  return createHash('sha256').update(JSON.stringify({ kind, ...identity })).digest('hex');
}

export class Journal {
  entries: Map<string, JournalEntry> = new Map();
  firstMiss = Number.POSITIVE_INFINITY;

  constructor(resume?: JournalEntry[]) {
    if (resume) for (const e of resume) this.entries.set(`${e.runId}:${e.index}`, e);
  }

  /** Return the cached entry iff its hash matches and it sits in the unchanged prefix; else null. */
  lookup(runId: string, index: number, hash: string): JournalEntry | null {
    const cached = this.entries.get(`${runId}:${index}`);
    if (cached && cached.hash === hash && index < this.firstMiss) return cached;
    return null;
  }

  /** Record that index `index` ran live — everything from here on must run live too. */
  miss(index: number): void {
    if (index < this.firstMiss) this.firstMiss = index;
  }

  put(entry: JournalEntry): void {
    this.entries.set(`${entry.runId}:${entry.index}`, entry);
  }

  /** The journal to persist / hand to the next run, ordered by call index. */
  dump(): JournalEntry[] {
    return [...this.entries.values()].sort((a, b) => a.index - b.index);
  }
}
