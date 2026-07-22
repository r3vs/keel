/**
 * Flagship topology #2 — the challenger's perspective-diverse adversarial verify (design §6.2).
 *
 * The upstream twin of the reviewer: for each ELECTED oracle (an acceptance_criterion / to_be /
 * policy), N red-teamers each try to REFUTE it under a DISTINCT lens. A fatal refutation (≥ minFatal
 * lenses) yields a `ChallengeEvent` that REOPENS the pin — it challenges, it never decides. Read-only:
 * it RETURNS the events; the calling agent records/surfaces them and the human re-elects.
 *
 * Distinct lenses, not N identical skeptics: redundancy catches one failure mode many times;
 * diversity catches many failure modes once.
 */
import type { WorkflowCtx } from '../engine.ts';

export const CHALLENGE_LENSES = [
  'unfalsifiable', // no observation could show it false
  'inconsistente', // contradicts another elected oracle
  'unsatisfiable', // nothing could satisfy it
  'assunzione-non-detta', // rests on an unstated assumption
  'ignora-fan-out', // ignores its own blast radius
];

export const REFUTATION_SCHEMA = {
  type: 'object',
  properties: { fatal: { type: 'boolean' }, reason: { type: 'string' } },
  required: ['fatal'],
};

export type Oracle = { id: string; kind?: string; statement: string };
export type ChallengeEvent = {
  event: 'ChallengeEvent';
  reopen: string;
  refutations: Array<{ lens: string; fatal: boolean; reason?: string }>;
};

export async function challengerVerify(
  wf: WorkflowCtx,
  args?: { oracles?: Oracle[]; lenses?: string[]; minFatal?: number },
): Promise<ChallengeEvent[]> {
  const oracles = args?.oracles ?? [];
  const lenses = args?.lenses ?? CHALLENGE_LENSES;
  const minFatal = args?.minFatal ?? 1; // any fatal lens reopens — a challenge flags, it does not decide

  wf.phase('Challenge');
  const events = await wf.pipeline(
    oracles,
    // stage 1: one red-teamer per lens, each trying to refute the oracle under that lens
    (o) =>
      wf.parallel(
        lenses.map((lens) => () =>
          wf
            .agent(
              `Red-team dell'oracolo eletto sotto la lente "${lens}". Oracolo: ${JSON.stringify(o)}. ` +
                `Cerca un difetto FATALE di tipo "${lens}"; se non ne trovi, fatal=false. Usa i tool ` +
                `deterministici per i FATTI, non indovinare.`,
              { schema: REFUTATION_SCHEMA, label: `challenge:${(o as Oracle).id}:${lens}` },
            )
            .then((r) => ({ lens, ...(r as Record<string, unknown>) })),
        ),
      ),
    // stage 2: enough fatal refutations → a ChallengeEvent that reopens the pin (never decides)
    (refs, o) => {
      const fatal = (refs as Array<{ lens: string; fatal?: boolean; reason?: string }>).filter(
        (r) => r && r.fatal === true,
      );
      if (fatal.length < minFatal) return null; // oracle survives → no event
      return {
        event: 'ChallengeEvent',
        reopen: (o as Oracle).id,
        refutations: fatal.map((r) => ({ lens: r.lens, fatal: true, reason: r.reason })),
      };
    },
  );
  return events.filter(Boolean) as ChallengeEvent[];
}
