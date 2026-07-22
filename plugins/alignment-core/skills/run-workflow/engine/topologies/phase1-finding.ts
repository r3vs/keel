/**
 * Flagship topology #1 — rescue Phase-1 finding (design §6.1, the highest-value fan-out).
 *
 * Multi-modal sweep (finders blind to each other, one per lens) + loop-until-dry, then a
 * perspective-diverse adversarial verify. The whole thing is READ-ONLY: it RETURNS the surviving
 * pins; the executor lands them in the ledger (serialized write — invariant §5.1/§5.4). Finders are
 * instructed to call the deterministic tools (`contract_diff`, `blast_radius`) for FACTS and only
 * fan out the JUDGEMENT — never approximate a deterministic result with an agent (invariant §5.3).
 */
import type { WorkflowCtx } from '../engine.ts';

export const PIN_SCHEMA = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    line: { type: 'number' },
    kind: { type: 'string' },
    summary: { type: 'string' },
  },
  required: ['file', 'line', 'kind'],
};

export const LENSES = [
  'per-layer DB↔ORM↔API↔FE',
  'per-entity',
  'per-contract',
  'dead-code',
  'contraddizioni',
];

export type Pin = { file: string; line: number; kind: string; summary?: string };

export async function phase1Finding(
  wf: WorkflowCtx,
  cfg?: { lenses?: string[]; consecutiveEmpty?: number },
): Promise<Pin[]> {
  const lenses = cfg?.lenses ?? LENSES;

  wf.phase('Sweep');
  const found = (await wf.loopUntilDry({
    round: (i) =>
      wf.parallel(
        lenses.map((lens) => () =>
          wf.agent(
            `Round ${i}. Trova pin via lente "${lens}". Usa i tool deterministici (contract_diff, blast_radius) per i FATTI; ritorna solo il giudizio come pin.`,
            { agentType: 'researcher', schema: PIN_SCHEMA, label: `find:${lens}` },
          ),
        ),
      ),
    key: (p: Pin) => `${p.file}:${p.line}:${p.kind}`,
    consecutiveEmpty: cfg?.consecutiveEmpty ?? 2,
  })) as Pin[];

  wf.log(`sweep: ${found.length} pin candidati (deduped)`);

  wf.phase('Verify');
  const kept = await wf.parallel(
    found.map((pin) => () =>
      wf
        .verify(pin, {
          reviewers: 3,
          lens: ['correttezza', 'fan-out/blast-radius', 'riproducibilità'],
          threshold: 0.5,
          agentType: 'reviewer',
        })
        .then((v) => (v.real ? pin : null)),
    ),
  );

  const survivors = kept.filter((p): p is Pin => p != null);
  wf.log(`verify: ${survivors.length}/${found.length} pin sopravvissuti`);
  return survivors;
}
