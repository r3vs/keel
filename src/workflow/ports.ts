/**
 * Ports — the seams through which the PURE engine touches the ledger and the DAG, without ever
 * calling MCP itself (invariant §5.1). In production these are backed by the real MCP tools:
 *   - PinSink.addPin   → `ledger_add_pin(ledger, kind, title, severity, confidence, provenance, as_is?, …)`
 *   - SchedulerPort    → `build_waves(ledger) -> dict`
 * verified against `src/mcp/server.py`. The engine receives waves as `args` and RETURNS pins; the
 * PinSink (an executor sub-agent, or the host harness) performs the one serialized write.
 */
import type { Pin } from './topologies/phase1-finding.ts';

// ---- PinSink: the output→pin seam (ledger_add_pin) -------------------------

export type LedgerKind =
  | 'contract_mismatch'
  | 'internal_contradiction'
  | 'ambiguity'
  | 'incompleteness'
  | 'design_concern'
  | 'defect'
  | 'open_decision'
  | 'acceptance_criterion'
  | 'other';

const LEDGER_KINDS = new Set<string>([
  'contract_mismatch', 'internal_contradiction', 'ambiguity', 'incompleteness',
  'design_concern', 'defect', 'open_decision', 'acceptance_criterion', 'other',
]);

export type AddPinArgs = {
  kind: LedgerKind;
  title: string;
  severity: 'blocker' | 'high' | 'medium' | 'low';
  confidence: 'extracted' | 'inferred' | 'ambiguous';
  provenance: Array<{ source: string; detail: string }>;
  as_is?: Record<string, unknown>;
  to_be?: Record<string, unknown>;
  depends_on?: string[];
  kind_detail?: string;
  cluster_id?: string;
};

export interface PinSink {
  addPin(args: AddPinArgs): Promise<{ id: string }>;
}

/**
 * Map a topology-returned Pin to `ledger_add_pin` args. NO invented taxonomy: a valid ledger `kind`
 * passes through; anything else lands as `other` + `kind_detail` (never silently reclassified). A
 * later refinement should tighten the topology's PIN_SCHEMA to emit the ledger enum directly.
 */
export function pinToAddArgs(
  pin: Pin,
  opts?: { source?: string; severity?: AddPinArgs['severity'] },
): AddPinArgs {
  const known = LEDGER_KINDS.has(pin.kind);
  return {
    kind: (known ? pin.kind : 'other') as LedgerKind,
    kind_detail: known ? undefined : pin.kind,
    title: pin.summary ?? `${pin.kind} @ ${pin.file}:${pin.line}`,
    severity: opts?.severity ?? 'medium',
    confidence: 'inferred', // a workflow finding is never `extracted` (that is for deterministic tools)
    provenance: [{ source: opts?.source ?? 'workflow:phase1-finding', detail: `${pin.file}:${pin.line}` }],
    as_is: { file: pin.file, line: pin.line, kind: pin.kind, summary: pin.summary },
  };
}

// ---- SchedulerPort: the DAG seam (build_waves) -----------------------------

export type Waves = {
  waves: string[][];
  wave_count?: number;
  ready_now?: string[];
  open?: number;
};

export interface SchedulerPort {
  buildWaves(ledger: string): Promise<Waves>;
}

// ---- Mocks for tests / buildloop-only dry runs -----------------------------

export class MockPinSink implements PinSink {
  added: AddPinArgs[] = [];
  private n = 0;
  async addPin(args: AddPinArgs): Promise<{ id: string }> {
    this.added.push(args);
    this.n += 1;
    return { id: `pin-${this.n}` };
  }
}

export class MockScheduler implements SchedulerPort {
  waves: Waves;
  constructor(waves?: Waves) {
    this.waves = waves ?? { waves: [], wave_count: 0, ready_now: [], open: 0 };
  }
  async buildWaves(): Promise<Waves> {
    return this.waves;
  }
}
