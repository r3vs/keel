# Module: Maintainability (deterministic)

## Tools → signals
- **jscpd** — copy-paste / clone detection (the vibecode duplication symptom).
- **lizard** + **scc** — cyclomatic complexity, function length, nesting.
- **dead-code** (language-gated: vulture/knip/deadcode/cargo-udeps) — unreferenced symbols.
- **git** (+ optional code-maat) — churn, churn×complexity hotspots, co-change coupling, bus
  factor.

## Run it

```bash
jscpd --reporters sarif --output .audit/ .
vulture . > .audit/vulture.txt        # or: knip / deadcode / cargo-udeps, per stack
```

Whatever emits SARIF goes straight through the `findings_gate` tool (pass it the
`.audit/jscpd-sarif.json` report) — the same ingester + fp-check gate the security module uses, so a
duplication finding and an SQLi finding are gated by one implementation and land as pins the same
way. Tools that emit their own text format (lizard, scc, vulture, `git
log`) are read as **inputs to the pin mapping below**, not as verdicts.

**One asymmetry to respect, and it is the reason dead-code is not just another SARIF source:**
every dead-code detector guesses. Dynamic dispatch, reflection, framework entrypoints, `__all__`,
and test-only usage all read as "unreferenced". So a dead-code hit is never a `defect` on its own
— it is a *candidate* that the pin mapping below must corroborate. `findings_gate` marks proven
diagnostics (a type error, a compiler message) to skip fp-check; a dead-code hit is the opposite
and must go through it.

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
