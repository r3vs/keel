# Module: False-Positive Gate (mandatory)

Every candidate finding from every module passes through this gate BEFORE it becomes a pin the
user sees. Non-negotiable: AI-generated analysis over-reports (empirically ~45% OWASP-intro
rates, high noise), and the entire value proposition dies if the user drowns in false
positives — that is exactly what makes people distrust AI auditors. Adapted from Trail of Bits
`fp-check`: mandatory gate reviews with an explicit verdict per finding.

## Verdict per finding: CONFIRM / DOWNGRADE / DROP

Assign one, with evidence, using these checks (in order — cheapest first):

1. **Intentional-stub exclusion.** Route through the completeness module first. Unfinished
   work is never a defect. If it's an intentional stub → DROP as a defect (it stays an
   `incompleteness` pin instead).
2. **Reachability (this is where the graph earns its keep).** Is the flagged path reachable
   from an entry point? Query the graph for an inbound edge chain. No path from any entry
   point → DOWNGRADE (dead/unreachable) or DROP. A "vulnerability" in unreachable code is not
   a live risk.
3. **Framework/context suppression.** Known-safe patterns are FPs: an ORM that already
   parameterizes queries (so a raw-SQLi flag on ORM-built SQL is spurious), auto-escaping
   template engines, a validator upstream of the flagged sink. Maintain a per-framework
   safe-pattern list; matching → DROP or DOWNGRADE.
4. **Corroboration.** Does a second independent signal agree (tool + graph + shape)? Single
   low-confidence source → DOWNGRADE to `proposed_default` (don't interrupt the user), never
   straight to an `asked` question. Confidence from the graph's EXTRACTED/INFERRED/AMBIGUOUS
   tag propagates here.
5. **Duplicate/variant merge.** N instances of one root cause collapse to one pin via
   `cluster_id`. 200 SQLi findings = one confirmed pin with 200 anchors, not 200 pins.

## Output

- **CONFIRM** → becomes a surfaced pin; the verdict + evidence is written to `pin.provenance`.
- **DOWNGRADE** → surfaced but with lowered `confidence`/`severity`, which (via the severity
  threshold) sends `medium`/`low` to `proposed_default` instead of `asked`.
- **DROP** → logged in an audit trail (auditable: you can show what was suppressed and why) but
  NOT surfaced to the user.

## Discipline
No finding reaches the map or interview without a verdict here. The gate runs at the end of
Phase 1, after all analysis modules, on the single normalized findings stream — so reachability
and corroboration can use the full graph and all other findings at once.
