# Phase 3 — Contract & Roadmap (derive the build)

Turn decided pins into (a) the aligned contract everything is generated from, and (b) a
dependency-sequenced build backlog. Nothing here is authored by hand beyond the contract itself:
the backlog is the mechanical expansion of the elected `to_be` into `BuildItem`s, ordered by the
`depends_on` DAG. This is rescue's Phase 3 run forward — build items instead of remediation items.

## Job 1 — Define the contract once, propagate it

Run the **contract-propagation** module (`references/contract-propagation.md`): author the
cross-layer contract from the decided data-model + API pins, pick the lightest carrier that spans
the stack (a shared-types package when TS end-to-end; OpenAPI/JSON-schema/protobuf when polyglot),
generate the aligned layer scaffolds from it, and **install the CI drift-check**. Each generated
layer is a `BuildItem` (`action: scaffold`, `contract_carrier` set) that `depends_on` the carrier.
Because everything else depends on the contract, this is Wave 1 — which falls out of the DAG, not
a hardcoded rule.

## Job 2 — Scaffold the paved road

From the decided NFR/delivery pins, run the **paved-road** module: scaffold the baseline the
project rides on — test harness, linters/formatters, CI pipeline, env/secrets config, error
taxonomy, and a **SessionStart hook** (see the `session-start-hook` skill) so future sessions can
run tests and linters immediately. These are `BuildItem`s (`action: scaffold`/`configure`) in Wave
1 alongside the contract: they carry no product decision but everything is built on top of them.

## Job 3 — Sequence the backlog

Expand each remaining decided pin into `BuildItem`s (`action: implement`/`wire`), then:

1. **Build the DAG** from `pin.depends_on` / item `depends_on`. "Contract before API before
   client" is not hardcoded — it falls out (a client type `depends_on` the DTO `depends_on` the
   carrier).
2. **Topologically sort.** Within a level, order by `severity`, then effort (cheap wins first).
3. **Detect cycles** (e.g. two entities each referencing the other as source of truth) — surface
   as a blocker pin for the user to break; never auto-resolve.
4. **Emit `roadmap.ordered_item_ids`** plus a human-facing plan.

### Build vertical slices, not horizontal layers
This is the load-bearing greenfield discipline. A `BuildItem` for a feature cuts **end-to-end
through all layers** (DB → API → client) for one thin capability, so there is always a **running
system** and every wave produces something demonstrable. Never build all of one layer before
starting the next — that defers integration risk to the end, which is how greenfield projects
stall.

## The waves (emergent, not hardcoded)

The topology almost always produces:

- **Wave 1 — Contract & paved road.** The carrier, the generated aligned scaffolds, the drift-
  check, the test/CI baseline. Everything depends on this.
- **Wave 2 — Core vertical slices.** The handful of features that deliver the core use case, each
  end-to-end and test-first.
- **Wave 3 — Secondary features.** The rest of the in-scope `to_be`.
- **Wave 4 — Polish.** Hardening, observability wiring, edge cases.

## Guardrail

Only **decided** pins yield `BuildItem`s. `deferred` and undecided pins produce nothing — no
speculative scaffolding, ever. A backlog that contains anything the user did not decide is how
greenfield regenerates the slop rescue exists to clean. The Phase-4 ladder enforces the same rule
per item.
