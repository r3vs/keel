# Module: Completeness (core, judgment)

The module that makes the skill usable on **in-progress** codebases. Its whole job is to
tell apart, for anything that looks unfinished:

- **intentional stub / not-yet-built** — a work item, NOT a defect. Renders neutral.
- **missing** — something is referenced but does not exist. A real gap.
- **broken** — exists but contradicts a consumer. A defect (hand to contract-recon / logic).

Getting this wrong in either direction is fatal: flag every stub as an error and the tool is
unusable noise on a half-built repo; miss the broken ones and you shipped slop. So this
module is deliberately conservative and always routes its output through `fp-check`.

## Signals (gather first, classify second)

Collect candidate signals from ast-grep/ripgrep + the graph:

- **Trivial body**: `pass`, `return None/null`, `throw NotImplementedError`, empty function,
  empty React component, handler that returns hardcoded/mock data, `// TODO` as the body.
- **Orphan (declared, no inbound edge)**: entity exists in the graph with no caller/importer
  from any entry point. Could be dead OR half-built — do not decide yet.
- **Dangling (referenced, no definition)**: a call/import/fetch/query targets a symbol,
  endpoint, or table that does not exist. This is `missing`.
- **Cross-layer half-wiring**: DB table with no ORM model; API route with no frontend caller;
  frontend calling an endpoint the backend never defines. (Overlaps contract-reconciliation —
  here it is the "one side entirely absent" case.)

## Classification (the judgment)

For each candidate, decide `kind` + `is_intentional_stub` using corroborating evidence, not a
single signal:

- **Pattern consistency → intentional stub.** A trivial body that fits an obvious scaffold
  (e.g. 3 of 4 CRUD verbs implemented, the 4th is `pass`) is almost certainly
  unfinished-on-purpose → `incompleteness`, `is_intentional_stub: true`.
- **Contradiction → defect.** If the stub's expected shape conflicts with an actual consumer
  (a caller relies on a return the stub can't give), that is not mere incompleteness — emit a
  `defect` or hand to contract-reconciliation.
- **Git recency.** Recently-added trivial code (high churn, new file) = active WIP → lean
  `incompleteness`. Long-untouched orphan with no inbound edge = lean dead → `defect` (delete),
  but still confirm via fp-check.
- **Dangling reference** always → `incompleteness` with sub-type `missing` (or `defect` if the
  reference is on a live path and will crash).

## Output

Mostly `incompleteness` pins with `is_intentional_stub` set, so the map renders them as neutral
work items (traffic-light "stub"/"missing"), never as errors. Each carries a Phase-2 scope
question with three options: **implement now / defer / drop (YAGNI)** — the "drop" option is
the ponytail rung-1 decision surfaced to the user. A minority promote to `defect` (broken) or
feed contract-reconciliation (cross-layer half-wiring).

Cluster by feature: dangling pieces that look like the same unfinished feature share a
`cluster_id`, so Phase 2 asks "is feature X in scope for v1?" once, not per symbol.

## Hard rule
Never render an intentional stub as an error by default. On slop this is THE noise that makes
an auditor unusable. When unsure between stub and broken, emit `incompleteness` (neutral) and
let the scope question resolve it — do not assert a defect on ambiguous evidence.
