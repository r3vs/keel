# The Decision Catalog (core asset)

This is greenfield's crown jewel and the analog of rescue's finding modules. Rescue sources its
pins from **code analysis**; greenfield sources its pins from **this catalog** — the canonical
space of forks that (almost) every project must resolve before it is built. Phase 1 expands the
catalog against the brief and materializes one `open_decision` pin per unresolved fork.

It is a **frame, not a script**. Two disciplines keep it from becoming an open-ended
questionnaire:

1. **Prune by project type** before asking anything (a CLI tool has no rendering fork).
2. **Skip what the brief already decided** — record those as pre-committed `DecisionEvent`s, not
   questions.

It is also **open**: domain-specific forks (data residency, compliance, offline-first, …) are
added as needed via the ledger's `other`/open-taxonomy discipline. This list is the common core,
not a ceiling.

## The clusters, in information-gain order

Order matters: the earlier a cluster, the more downstream forks depend on it. Ask domain and
persistence first — they fan out to everything; delivery and observability are leaves. This
ordering *is* the information-gain order the interview funnel (`references/core/interview-funnel.md`) uses.

Each fork below lists **options** (candidate to-be's, never one asserted as correct), the
**downstream** forks it feeds (`depends_on` runs the other way), and a **default policy**
candidate the interview can offer to auto-resolve the long tail.

### 0. Outcomes / acceptance criteria  ·  roots of the DAG
The testable results v1 must deliver — the **engineering half** of requirements. Not forks with
options but **assertions of desired outcome**, elicited as a bounded set and pinned as
`acceptance_criterion`s (`references/phase-1-frame.md`, Step 3). Everything else `depends_on` them:
an architecture decision exists to satisfy an outcome, and a Track-A test traces to one.
- **Elicit:** the core use case as Given/When/Then statements with a `verify` hook; each `in scope
  v1` or `deferred`.
- **Downstream:** every decision and every slice.
- **Default policy:** "smallest set of outcomes that delivers the core use case; the rest deferred."

### 1. Product scope & domain model  ·  fan-out: everything
The entities, their relationships, and — critically — **what is in v1 vs later**. This is the
YAGNI forcing function: every entity and feature not scoped in is a `deferred` pin, not silent
scaffolding.
- **Options:** the core entity set and the v1 feature list (elicited, then confirmed as a bounded
  set, not an open "anything else?").
- **Downstream:** persistence, API, boundaries, every slice.
- **Default policy:** "smallest domain that delivers the core use case; everything else deferred."

### 2. Persistence & data  ·  depends_on: domain
- **Options:** relational (Postgres/SQLite) · document · key-value · none (stateless/static).
- **Downstream:** the contract carrier, the ORM layer, migrations.
- **Default policy:** "one relational datastore until a concrete need proves otherwise;
  schema-first (the DB schema is a source the contract derives from)."

### 3. Identity & access  ·  depends_on: domain
- **Options:** none · session cookie · JWT · third-party (OAuth/OIDC, Auth provider). Plus the
  **multitenancy** sub-fork: single-tenant · shared-schema multi-tenant · schema/DB-per-tenant.
- **Downstream:** authz checks in every API route, tenant scoping in every query.
- **Default policy:** "third-party identity unless there's a reason to own it; single-tenant
  until a second tenant is real."

### 4. API & contract  ·  depends_on: domain, persistence
The most load-bearing greenfield fork, because it decides **where the cross-layer contract
lives** — the thing contract-propagation generates from.
- **Options (style):** REST · RPC (tRPC/gRPC) · GraphQL · none (server-rendered, no API layer).
- **Options (contract carrier):** a shared-types package (TS monorepo) · OpenAPI · JSON-schema ·
  protobuf. This is the single source every layer is generated from (`references/contract-propagation.md`).
- **Downstream:** client types, DTOs, the drift-check.
- **Default policy:** "the lightest contract carrier that spans the languages in play; a
  shared-types package when the stack is TS end-to-end."

### 5. Client & rendering  ·  depends_on: API & contract
- **Options:** server-rendered (SSR/MPA) · SPA · mobile · none (headless/API-only). Plus state
  management if SPA.
- **Downstream:** the client slice of every vertical feature.
- **Default policy:** "server-render unless interactivity genuinely demands a SPA — reach for the
  client-heavy option by exception, not default."

### 5b. Design system (DTCG tokens)  ·  depends_on: client
Applies wherever a UI is rendered (pruned for CLI / library / API-only, but a **static site has a
UI** and keeps it). This is the presentation-layer contract — the thing greenfield's
`design-propagation` generates from and rescue's `design-alignment` diffs against. The machine
contract is a **W3C DTCG** token set (the stable, multi-vendor standard); `DESIGN.md` and the CSS /
Tailwind layers are *generated* from it, never hand-authored (an agent that only reads text cannot
invent a tasteful palette — the tokens are **captured or imported**, not invented).
- **Options:** capture a **DTCG token set** from an approved visual direction (a visual tool, opt-in)
  · import tokens (an existing brand · a Figma Variables export, DTCG-native · a component library) ·
  no formal system in v1 (only universal a11y/slop checks run).
- **Downstream:** the DTCG carrier → generated CSS / Tailwind / DESIGN.md, the CI drift-check
  (`tokens_diff` + `impeccable detect`), Wave 1; every UI slice's styling.
- **Default policy:** "elect a minimal DTCG token set from day one, so design drift is a build failure
  a CI check catches — not a matter of taste discovered in review." A token set is an `enum`; the
  same shape engine that guards the data contract guards the design one (`references/core/shape-engine.md`).

### 6. Sync & time  ·  depends_on: domain, API
- **Options:** pure request/response · background jobs/queue · event-driven · realtime
  (websockets/SSE).
- **Downstream:** infrastructure, the delivery target, testing strategy.
- **Default policy:** "synchronous request/response until a concrete latency or decoupling need
  justifies a queue; no event bus in v1."

### 7. Boundaries & topology  ·  depends_on: domain
- **Options:** single deployable (monolith) · **modular monolith** · services.
- **Downstream:** delivery, CI, the contract's transport (in-process vs network).
- **Default policy:** "modular monolith — clear internal module boundaries, one deployable. Split
  to services only when a module has a proven independent scaling or ownership need"
  (a textbook `flip_criteria`).

### 8. Cross-cutting NFRs  ·  depends_on: most of the above
Elected once as **policies**, applied everywhere (this is where the funnel's policy questions pay
off most): validation strategy (where input is validated — at the contract boundary by default),
error taxonomy, observability (logs/metrics/traces), testing strategy (what gets Track-A tests),
security posture (secrets handling, authz default-deny).
- **Default policy:** "validate at the contract boundary; structured errors from one taxonomy;
  Track-A tests on every decision-bearing slice; default-deny authz."

### 9. Delivery & release  ·  depends_on: topology, sync
- **Options:** deploy target (serverless · container · VM · static host) · CI provider · env/
  secrets management · **deploy strategy** (canary · blue-green · rolling) · **migration strategy**
  (expand/contract, zero-downtime) · **versioning/changelog** (semver, projected from the ledger) ·
  **rollback** procedure · feature-flag rollout.
- **Downstream:** the paved-road scaffolding and Phase 6 Release (`references/phase-6-release.md`).
- **Default policy:** "the platform's boring default for the chosen topology; migrations versioned
  and expand/contract from commit one; every release rollback-ready."

### 10. Operability  ·  depends_on: delivery, most
What the running system must expose to be observed and evolved — the **codebase-facing slice** of
operations (not the SRE practice).
- **Options:** observability (structured logs · metrics · traces · health/readiness) · SLO targets
  · the **signal manifest** (which telemetry each `flip_signal` watches).
- **Downstream:** Phase 7 Operate & Evolve (`references/phase-7-operate-evolve.md`) — the signal
  manifest is the physical anchor of the feedback loop.
- **Default policy:** "structured logs + the few metrics the SLOs need; a signal manifest for every
  decision that carries a `flip_signal`."

## Cross-cutting: threat model
Security is not a cluster but a **pass** over the decided elements: STRIDE per entry point / data
store / trust boundary materializes security `open_decision`s (`references/threat-model.md`), run
in Phase 1 alongside the catalog expansion. Designed in, not scanned for later.

## Grounding the options (don't reason in a vacuum)

The catalog's options are candidates, not gospel. Ground the hard forks in real sources
(`references/core/knowledge-sources.md`): DeepWiki on exemplar repos ("how does a well-run system in this
space decide this?"), Context7 for whether a candidate library's *current* API actually supports
the option, the registries for its maintenance/health. Cite what you find and carry its confidence
onto the pin — the interview still decides; grounding only sharpens the options.

## Project-type presets (pruning)

Apply before materializing pins — a whole cluster absent from the type is not a question:

| Project type   | Prune (skip these clusters)                    |
|----------------|------------------------------------------------|
| CLI tool       | 4 API, 5 client/rendering, 3 identity (usually)|
| Library / SDK  | 2 persistence, 3 identity, 4 API, 5 client, 9 delivery (partly) |
| Static site    | 2 persistence, 3 identity, 6 sync              |
| API service    | 5 client/rendering                             |
| Web SaaS       | none — the full catalog applies                |

## How Phase 1 uses this

For each surviving fork not decided by the brief: emit an `open_decision` pin (schema:
`references/core/ledger.md`) with the fork as its `question`, the options above, the downstream links as
`depends_on`, a `cluster_id` grouping related forks, and `severity` set by fan-out (clusters 1–4
tend to `high`/`blocker`; 9–10 tend to `medium`). Cluster 0's outcomes become `acceptance_criterion`
pins that root the DAG; the threat-model pass adds security `open_decision`s. The default policies
become the interview's opening policy questions. See `references/phase-1-frame.md`.

## Runtime

The machine-usable form of this catalog is `assets/decision-catalog.json` (this doc stays the
authoring source — keep them in step). The `interview_next` tool loads it and runs Phase 1:
`expand_catalog(ledger, catalog, project_type, brief_decisions)` prunes by project type, skips the
forks the brief already decided (pre-committed, never re-asked), materializes one pin per surviving
fork, and wires `depends_on` to the created pin ids; `funnel(ledger)` compresses to the asked
questions ordered by transitive information gain with the tail as `proposed_default`;
`default_policies()` offers the per-cluster defaults. The `challenge_oracle` tool then red-teams the
elected oracles (deterministic classes). `interview_next` takes the project type (e.g. `web-saas`).
Both are covered by the runtime's own test suite.
