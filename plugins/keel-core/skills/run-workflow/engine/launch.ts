/**
 * Launcher — the thin harness that runs a finding topology and lands its survivors as ledger pins.
 *
 * This is where the ONE serialized write lives (invariant §5.1/§5.4): the pure engine RETURNS pins;
 * the launcher hands each to a `PinSink` (in production an executor sub-agent invoking `ledger_add_pin`;
 * in tests a mock), one at a time. The engine never touches the ledger; MCP calls (`build_waves` for
 * `args`, `contract_diff`/`ledger_add_pin` inside sub-agents) happen at the seams, not in the engine.
 */
import { runWorkflow } from './engine.ts';
import type { WorkflowCtx, RunOpts } from './engine.ts';
import type { JournalEntry } from './journal.ts';
import type { PinSink } from './ports.ts';
import { pinToAddArgs } from './ports.ts';
import type { Pin } from './topologies/phase1-finding.ts';

export type LaunchOpts = RunOpts & {
  sink?: PinSink;
  commit?: boolean; // land survivors as pins (default: true when a sink is given)
  source?: string; // provenance source for the written pins
  args?: unknown; // e.g. the `build_waves` result, resolved by the caller
};

export async function launchFinding(
  topology: (wf: WorkflowCtx, args?: unknown) => Promise<Pin[]>,
  opts: LaunchOpts,
): Promise<{ pins: Pin[]; committed: string[]; journal: JournalEntry[] }> {
  const { result, journal } = await runWorkflow((wf) => topology(wf, opts.args), opts);
  const pins = (result ?? []) as Pin[];

  const committed: string[] = [];
  if (opts.sink && opts.commit !== false) {
    // serialized write — one pin at a time, never a parallel fan-out of ledger writes
    for (const pin of pins) {
      const { id } = await opts.sink.addPin(pinToAddArgs(pin, { source: opts.source }));
      committed.push(id);
    }
  }
  return { pins, committed, journal };
}
