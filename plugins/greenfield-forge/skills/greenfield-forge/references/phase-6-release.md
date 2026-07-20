# Phase 6 — Release (ship the slice safely)

Take a validated slice to production **safely**. This is the **codebase-facing slice** of release
engineering — the decisions and artifacts that live in the repo — NOT the CD platform. The line:
migration scripts, version, changelog, feature-flag code, rollback procedure are **in**;
provisioning clusters, the CD runner, and cloud infra are **out** (platform/team).

Prerequisite: the release decisions elected in the interview (deploy strategy, migration
strategy, versioning, rollback), from the decision-catalog's Delivery cluster. If they were not
elected, that is an `open_decision` to resolve first — never release on an unmade decision.

## Steps

1. **Migration safety (the dangerous part — it is code).** Schema changes follow **expand /
   contract**: add the new nullable column / table → backfill → switch reads → drop the old, each
   step reversible and tested on a copy first. Never a destructive migration in one shot. This is
   what makes the release zero-downtime *by construction*, not by luck.
2. **Version & changelog from the ledger.** Cut a version (semver), and generate the changelog
   **from the ledger's `DecisionEvent`s and `BuildItem`s** — the ledger already records what
   changed and why, so the changelog is a projection, not hand-written prose. Read it from the
   carrier, never from memory of the session:

   ```bash
   python scripts/runtime/ledger.py summary ledger.json
   ```

   The `decision_log` is what a changelog entry *is*: each `DecisionEvent` carries the elected
   option and its rationale. Writing the changelog from recollection instead is how a release note
   and the decision it describes drift apart — the exact divergence this package exists to prevent,
   committed at the moment it becomes public.
3. **Feature-flag if not ready for all.** Ship behind a flag when the slice isn't ready for every
   user. The flag is code + a decision (with a `flip_criteria`: "remove the flag when adoption /
   error-rate crosses X").
4. **Execute the deploy strategy.** Run the elected strategy (canary / blue-green / rolling) as
   **config + a runbook**, not infra provisioning. A canary is a routing decision expressed in
   the repo's deploy config, watched by the Operate phase's signals.
5. **Rollback ready and tested.** The reversible path exists and has been exercised: migration
   down-path, flag off, previous version redeployable. A release without a tested rollback is not
   ready.

## Guardrail

Never release without the migration **expand/contract** plan and the **rollback** decided and
tested. The paved road (Phase 3) scaffolded these mechanics; this phase executes them per slice.
Everything here traces to a decision — no ad-hoc "just push it".

## Output

A released slice, a cut version, a changelog entry projected from the ledger, and a tested
rollback. The ledger records the release; the deploy config and migration scripts are committed
artifacts. Hand off to Phase 7, which watches how the release behaves in production.
