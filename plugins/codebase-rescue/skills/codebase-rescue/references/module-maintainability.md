# Module: Maintainability (deterministic)

## Tools → signals
- **jscpd** — copy-paste / clone detection (the vibecode duplication symptom).
- **lizard** + **scc** — cyclomatic complexity, function length, nesting.
- **dead-code** (language-gated: vulture/knip/deadcode/cargo-udeps) — unreferenced symbols.
- **git** (+ optional code-maat) — churn, churn×complexity hotspots, co-change coupling, bus
  factor.

## Pin mapping
- **Duplication** → feeds `consolidate` remediation. Pick `canonical_target` = the most-tested
  / most-referenced copy (use graph inbound-edge count + coverage). Clustered so all copies of
  one thing are one decision.
- **Complexity + churn** → hotspot heatmap on the map. A hot, complex, high-coupling unit is a
  `design_concern` (an OPTION to refactor, not a defect) — `to_be` stays null until the user
  chooses.
- **Dead code on slop is ambiguous.** Cross-check the completeness module: orphan + recent
  churn → likely a half-built feature → `incompleteness` scope question; orphan + long-dead →
  `defect` (delete). Never blindly delete on a slop repo.
- **Co-change coupling** → hidden coupling surfaced as `design_concern` (files that always
  change together but aren't structurally linked).

## Note
Complexity and duplication numbers are inputs to judgment, not verdicts. Present them; let the
user decide what to consolidate or refactor via the interview.
