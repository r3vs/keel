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
- **Degrade gracefully — but never silently.** No checker for a *present* language → the run
  continues, but the gap becomes a **fact in the ledger, not a silent zero**.
  The `coverage_gaps` tool compares the capabilities expected for the stacks tokei found against
  the tools that actually produced a report, and surfaces each uncovered one as an `incompleteness`
  **`coverage-gap`** pin (`confidence: extracted` — the absence is a fact). "Unchecked" must never
  read as "clean": a deterministic module that could not run its engine did not find zero problems, it
  found *nothing*. The gap then flows through the interview like any pin — closed (install the tool +
  re-run) or accepted (out of scope) — never defaulted away. **Never hard-fail; never hide the hole
  either** — that silent fallback is the package's own "claiming vs doing" failure turned inward.

## Prefer the checkable formulation (a selection heuristic)

Verification is usually strictly cheaper than generation — checking a passing test, a type, or a
failed constraint costs far less than producing correct code, and the gap is widest exactly where
the static signal is strong. So when a `to_be` or an `acceptance_criterion` can be expressed more
than one way, **prefer the formulation whose correctness a machine can check** — because that moves
the property out of "someone has to notice" and into "the build fails". Concretely: state an outcome
with a mechanical `verify` (an e2e assertion) over a prose intent; encode an elected boundary as an
architecture-fitness rule over a comment; make an invariant a runtime assert or a property test over
a hope. This is the design-time companion to running the tools in-loop: don't only *check* with the
strongest signal, **author the spec so the strongest signal applies.** A `to_be` with no possible
failing test is a smell — it is precisely what the `challenger` refutes as `unfalsifiable`
(agents doctrine; ledger spec v0.6).

## Output

High-confidence static findings feeding pins (rescue) or standing CI checks (greenfield), used
in-loop — with the deterministic ones bypassing fp-check and carrying `extracted` confidence.
