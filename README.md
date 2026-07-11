# codebase-rescue & greenfield-forge

Two sibling Claude Code skills that keep a codebase aligned across its whole lifecycle — one
**curative**, one **preventive** — sharing a single decisions-ledger spine.

- **`codebase-rescue`** — rescue a large, misaligned, often AI-generated ("vibecoded") codebase,
  reconciling backend, frontend, and database into an aligned, state-of-the-art state. Works on
  unfinished codebases and treats "not built yet" as a work item, not a defect.
- **`greenfield-forge`** (`greenfield-forge/`) — build a NEW project aligned from the first commit,
  so it never needs rescuing. Elects the design in a compressed decision interview *before* any
  code exists, defines the cross-layer contract once and generates aligned layers from it, then
  builds thin vertical slices test-first.

Both center on architecture — design choices, logic, specs, and layers that agree — not just bugs
and vulnerabilities.

## The shared idea
Two artifacts, diffed: **as-is** (what the code is now) and **to-be** (what it should be, derived
from decisions the user elects in a targeted interview). Everything is a delta:
`gap = diff(to-be, as-is)`. Rescue runs it backward (as-is exists → derive to-be → close the gap);
greenfield runs it forward (elect to-be → build until as-is meets it → gap → 0). A single
append-only decisions ledger is the source of truth for the three surfaces (map/wiki, interview,
brainstorm) — and a forged project's ledger is the audit baseline rescue can later diff against.

Five phases each. Rescue: comprehension → interview → diff/roadmap → TDD remediation loop →
validate. Greenfield: frame → interview → contract & roadmap → TDD build loop → validate.

## Layout
- `SKILL.md` + `references/` + `modules.json` — the `codebase-rescue` skill (repo root).
- `greenfield-forge/` — the `greenfield-forge` skill (same layout, its own dir).
- `core/` — the shared spine: `decisions-ledger-spec.md` (schema, v0.4, Italian), `ledger.md`
  (English pointer), `interview-funnel.md`, `brainstorm.md`, `shape-engine.md`.
- each skill's `TODO.md` — its build checklist. **Do step 0 (the gating experiment) first.**
- `scripts/bootstrap.sh` — install the deterministic toolchain (shared).
- `scripts/check_consistency.py` — drift-linter for both skills + core (run in CI).

## Status
Both skills are design-complete and internally coherent; the drift-linter is green. What remains
is implementation — see each `TODO.md`.

## License
TBD (MIT recommended — the graph backbone Graphify is MIT; GitNexus is excluded from
commercial use).
