# codebase-rescue

A Claude skill that rescues large, misaligned, often AI-generated ("vibecoded") codebases —
reconciling backend, frontend, and database into an aligned, state-of-the-art state. It works
on unfinished codebases and treats "not built yet" as a work item, not a defect.

Its center of gravity is architectural: wrong design choices, wrong logic, contradictory or
improvable specs, and layers that drifted apart — not just bugs and vulnerabilities.

## How it works
Two artifacts, diffed: **as-is** (what the code is now) and **to-be** (what it should be,
derived from decisions the user elects in a targeted interview). Everything found is a delta:
`gap = diff(to-be, as-is)`. A single append-only decisions ledger is the source of truth for
the three surfaces (map/wiki, interview, brainstorm).

Five phases: comprehension → interview → diff/roadmap → TDD-driven remediation loop → validate.

## Start here
- `SKILL.md` — the orchestrator (entry point).
- `decisions-ledger-spec.md` — the ledger schema (v0.3).
- `references/` — per-phase and per-module playbooks.
- `TODO.md` — the build checklist. **Do step 0 (the Graphify experiment) first.**
- `scripts/bootstrap.sh` — install the deterministic toolchain.
- `scripts/check_consistency.py` — drift-linter (run in CI).

## Status
Design complete and internally coherent. What remains is implementation — see `TODO.md`.

## License
TBD (MIT recommended — the graph backbone Graphify is MIT; GitNexus is excluded from
commercial use).
