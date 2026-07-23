/**
 * Worktree isolation — real `git worktree` per parallel writer, so build-waves executors never
 * collide. Kept OUT of the pure engine (the engine never touches git/fs): a composable decorator
 * adapter that only acts when `isolation:'worktree'` is set, otherwise delegates untouched.
 *
 * This is the `branch-lifecycle` "a worktree per scope" rule made runnable: one executor, one tree,
 * one branch — left in place after the run so its PR can be opened; only the worktree checkout is
 * removed. Matches pi-dw's `isolation:'worktree'`, minus its Pi-session specifics.
 */
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import type { SpawnAdapter, SpawnOpts, SpawnResult } from './adapter.ts';

function git(cwd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const cp = spawn('git', args, { cwd, windowsHide: true });
    let out = '';
    let err = '';
    cp.stdout.on('data', (d) => (out += d.toString()));
    cp.stderr.on('data', (d) => (err += d.toString()));
    cp.on('error', reject);
    cp.on('close', (code) =>
      code === 0 ? resolve(out.trim()) : reject(new Error(`git ${args.join(' ')} failed: ${err.trim()}`)),
    );
  });
}

/** Sanitize a label into a safe branch/path component. */
export function safeName(s: string): string {
  return (s || 'item').toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'item';
}

/**
 * Create a git worktree with a fresh branch, run `fn` against its path, then remove the worktree
 * (keeping the branch). Best-effort cleanup in `finally` — never leaks a checkout even if `fn` throws.
 */
export async function withWorktree<T>(
  repoRoot: string,
  branch: string,
  fn: (worktreePath: string) => Promise<T>,
): Promise<T> {
  const path = join(repoRoot, '.workflow-worktrees', safeName(branch));
  await git(repoRoot, ['worktree', 'add', '-b', branch, path, 'HEAD']);
  try {
    return await fn(path);
  } finally {
    await git(repoRoot, ['worktree', 'remove', '--force', path]).catch(() => {});
  }
}

/**
 * Decorator adapter: for `isolation:'worktree'` runs, spawn the inner adapter with a fresh worktree
 * as its cwd; otherwise delegate unchanged. `Date`/`Math.random` are unavailable inside the vm engine,
 * but this runs OUTSIDE it — a pid+counter keeps branch names unique without them.
 */
export class WorktreeAdapter implements SpawnAdapter {
  host: string;
  inner: SpawnAdapter;
  repoRoot: string;
  branchPrefix: string;
  n = 0;

  constructor(inner: SpawnAdapter, opts: { repoRoot: string; branchPrefix?: string }) {
    this.inner = inner;
    this.host = inner.host;
    this.repoRoot = opts.repoRoot;
    this.branchPrefix = opts.branchPrefix ?? 'wf';
  }

  async run(prompt: string, opts?: SpawnOpts): Promise<SpawnResult> {
    if (opts?.isolation !== 'worktree') return this.inner.run(prompt, opts);
    this.n += 1;
    const branch = `${this.branchPrefix}/${safeName(opts?.label ?? 'item')}-${process.pid}-${this.n}`;
    return withWorktree(this.repoRoot, branch, (wt) => this.inner.run(prompt, { ...opts, cwd: wt }));
  }
}
