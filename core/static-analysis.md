# Using Static Analysis Well (shared core)

Shared doctrine for using static signal **in the best way**, not just which tools exist. Static
signal is cheap, deterministic, and high-confidence — so the rule is: **use the strongest static
signal available before model judgment, and use it in-loop, not only as a batch scan.** Both
skills read this; the concrete tool list lives in `skills/codebase-rescue/references/toolchain.md`.

## The underused SOTA signals (make these first-class)

The finder toolchain already covers SAST, secrets, deps, complexity, duplication, dead code, and
mutation. Three high-value static signals are commonly under-used:

- **Type-checkers / compilers as analyzers** — `tsc --noEmit`, `mypy` / `pyright`,
  `cargo check` / `rust-analyzer`, `go vet`. This is the **highest-value static signal** and the
  one most directly tied to contracts and logic: a type error is a *fact*, not an AI guess. Run it
  as a first-class finding at `extracted` confidence. In greenfield, the generated types + the
  type-checker make whole classes of contract drift impossible before a test ever runs.
- **LSP / SCIP indexes** — precise definitions, references, call hierarchy, and safe
  rename/refactor. More reliable than the LLM-inferred graph edges for navigation and blast-radius
  (see the Phase-0 verdict: the graph's cross-layer edges are weak). **Prefer LSP/SCIP where a
  language server exists**; keep the graph for community structure and cross-tree spans an LSP
  can't give. LSP is the SOTA navigation primitive; the graph is the complement.
- **Architecture-fitness / dependency-constraint checks** — `import-linter`, `dependency-cruiser`,
  `ArchUnit`, `ts-arch`. These encode the **elected boundaries** (modular monolith, layer rules,
  allowed dependencies) as executable constraints. In rescue, a violation is a `design_concern`
  against the elected to-be. In greenfield, the constraints are **generated from the topology
  decision and enforced in CI**, so boundaries can't silently erode — the preventive mirror.

## Using them well (the "best way" part)

- **In-loop / incremental, not just batch.** Run static tools **on the diff while editing**
  (Phase-4 build/remediation), via the language server where possible — not only in the Phase-1
  batch scan. Fast local feedback catches a regression the moment it's introduced.
- **Confidence from determinism.** A deterministic static finding (type error, failed constraint,
  dead symbol) is high-confidence — feed the ledger's `confidence` tags accordingly, and it can
  **skip the heavy `fp-check`** (it is not an AI over-report). Reserve fp-check budget for the
  judgment findings that actually need it.
- **Right tool per phase:**
  - **Comprehension / finding** (rescue Phase 1): type-check + LSP/SCIP index + architecture-fitness
    alongside the existing finders; type errors and constraint violations become high-confidence pins.
  - **Build / remediation** (Phase 4): type-check + LSP in-loop on the diff; `ast-grep` for
    mechanical rewrites.
  - **Validate** (Phase 5): type-check passes and architecture-fitness is green — as evidence, not
    just a green build.
  - **greenfield paved road** (Phase 3): scaffold the type-checker and the architecture-fitness /
    dependency-constraint checks into CI, so the elected boundaries are enforced from commit one.
- **Degrade gracefully.** No language server or checker for a language → fall back to the graph /
  grep and note the gap. Never hard-fail (same posture as the rest of the toolchain).

## Output

High-confidence static findings feeding pins (rescue) or standing CI checks (greenfield), used
in-loop — with the deterministic ones bypassing fp-check and carrying `extracted` confidence.
