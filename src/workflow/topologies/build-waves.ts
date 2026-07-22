/**
 * Flagship topology #3 — build waves (design §6.3): the WRITE path.
 *
 * The order falls out of the dependency DAG (`build_waves`), never hardcoded — "align contracts
 * before fixing logic" is a consequence of the graph. Each wave fans out EXECUTOR sub-agents (one
 * per BuildItem/RemediationItem), each in its OWN git worktree so parallel writers never collide,
 * then a journaled `checkpoint` gates the next wave (where the reviewer/challenger run). The executor
 * writes test-first and opens a PR; it never merges. Serialized-writing is preserved PER SCOPE: one
 * executor owns one worktree.
 *
 * Requires a worktree-capable adapter (see `WorktreeAdapter` in `worktree.ts`) for
 * `isolation:'worktree'` to actually isolate; without it the flag is a harmless no-op (agents share
 * the cwd — safe only when the wave has a single item).
 */
import type { WorkflowCtx } from '../engine.ts';

export type WaveItem = { id: string; title?: string };
export type Wave = { index: number; items: WaveItem[] };
export type WaveResult = { wave: number; items: string[]; checkpoint: unknown };

export async function buildWaves(
  wf: WorkflowCtx,
  // `model` is an OPTIONAL override (e.g. the executor's escalation target); by default the executor's
  // model comes from the host's per-role config (model-tiers.md), carried by `agentType: 'executor'`.
  args?: { waves?: Wave[]; model?: string },
): Promise<WaveResult[]> {
  const waves = args?.waves ?? [];
  const model = args?.model;
  const summary: WaveResult[] = [];

  for (const wave of waves) {
    wf.phase(`wave ${wave.index}`);
    await wf.parallel(
      wave.items.map((item) => () =>
        wf.agent(
          `Implementa "${item.id}"${item.title ? ` (${item.title})` : ''} in TDD: prima il test ROSSO ` +
            `(che È l'acceptance_criterion), poi il codice minimo che lo fa passare. Apri una PR, NON fare merge.`,
          { isolation: 'worktree', agentType: 'executor', model, label: item.id },
        ),
      ),
    );
    // Journaled gate: in a real session the reviewer/challenger verdict lands here; headless it
    // auto-approves (and replay reproduces the decision). `headless:'abort'` would stop the run.
    const checkpoint = await wf.checkpoint(
      `Wave ${wave.index} completa (${wave.items.length} item)? Verdetto reviewer prima della wave successiva.`,
      { kind: 'confirm' },
    );
    summary.push({ wave: wave.index, items: wave.items.map((i) => i.id), checkpoint });
    if ((checkpoint as { aborted?: boolean } | null)?.aborted) break;
  }
  return summary;
}
