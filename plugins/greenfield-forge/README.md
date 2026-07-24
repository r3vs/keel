<!-- GENERATED FILE - do not edit. Source: src/readme/greenfield-forge.md at the repo root; regenerate with: python scripts/build.py -->

# greenfield-forge

**The preventive half of Keel.** Start a new project the right way: elect the design in a compressed
decision interview **before any code exists**, define the cross-layer contract once, then *generate*
every layer from it so they cannot drift. The goal is a codebase that never needs rescuing.

```bash
/plugin install greenfield-forge@keel
```
```text
> I want to build a multi-tenant SaaS for invoicing. Set it up properly from day one.
```

`keel-core` follows automatically (the MCP server, the agent roster, the hooks). On **Codex**,
install it explicitly — Codex has no dependency resolution.

---

## The one idea

```
gap = diff(to-be, as-is)
```

Rescue runs that diff backward. Forge runs it **forward**: elect the **to-be** first, start from an
**empty as-is**, and build until the two meet — `gap → 0`.

That inversion is the whole product. Nothing is reverse-engineered from code, because there is no
code yet to be wrong.

---

## Why not just talk to your agent about it

An open-ended *"tell me about your app"* chat **is the slop seed.** It lets the model fill unmade
decisions with silent assumptions, and you never find out which ones until something breaks three
weeks later.

Phase 1 does the opposite: it turns a vague brief into **concrete, answerable forks**, each a pin
with options, downstream implications, and its dependencies wired.

---

## Modes — pick the scope up front

| Mode | What runs | Use when |
|---|---|---|
| **`forge`** *(default)* | Phases 1–6 | idea → aligned scaffold → first vertical slice → first release |
| **`spec`** | Phases 1–3 only | you want the design, contract and backlog; you'll build it yourself |
| **`slice`** | Phases 3–5 on a subset | extend a forged project with ONE vertical feature — how it continues after v1 |
| **`decide`** | the interview alone | *"help me make these architecture decisions properly"* — no scaffolding |
| **`evolve`** | Phase 7's feedback loop | a live project: evaluate `flip_signal`s against telemetry and reopen what fired |

```text
> /forge spec
> /forge decide
```

---

## The seven phases

Each phase is a **separate invocation with a fresh context**, communicating only through artifacts
on disk. Phases 1–5 build v1; 6–7 ship it and feed production back into the ledger, closing the loop.

### Phase 1 — Frame (materialize the open decisions)
1. Intake the brief and classify the project type to **prune** the decision catalog — a CLI skips
   rendering and client concerns; a static site skips persistence.
2. Expand the catalog against the brief into one `open_decision` pin per fork, each with options,
   downstream implications and `depends_on` wired. Related forks are clustered.
3. Record **givens** as pre-committed decisions. If the brief already says *"must run on-prem"* or
   *"the team knows Postgres"*, that is logged as a decision with `flip_criteria` — it is never
   re-asked.
4. Seed the skeletal **to-be map**: domain entities and layer lanes as ghost nodes, all `planned`,
   decision pins attached. The completeness traffic-light starts **all red by design**.

Phase 1 also pins the **acceptance criteria** that root the entire dependency DAG, and runs the
**threat-model** pass — so security is *designed in*, not scanned for later.

### Phase 2 — Interview (elect the to-be)
The same compression funnel rescue uses. **Policy questions first** — architectural defaults like
*"prefer boring/proven tech"*, *"server-render unless interactivity demands a SPA"*, *"one datastore
until proven otherwise"*, *"no service split in v1"*. Then the genuine forks, ordered by
**information gain**: domain model and persistence first (they fan out to everything), delivery and
observability last.

Every committed answer emits a decision with **`flip_criteria`** — essential here, because you are
deciding *before* you know the app. Then a **challenger** pass red-teams what you elected: an
`acceptance_criterion` with no testable `verify`, two forks that cannot both hold, a `to_be`
unsatisfiable from the givens, a decision resting on an undeclared assumption. A sustained
refutation reopens the pin **before** Phase 3 turns it into contract and backlog. It challenges; it
never decides.

You can open a **brainstorm** on any hard fork: 2–3 designs with tradeoffs, cited, disciplined by
the ponytail ladder. It writes proposals; only the interview commits.

### Phase 3 — Contract & roadmap (derive the build)

**1. Define the cross-layer contract ONCE and propagate it.** From the decided data model and API
decisions, author the shared contract — a shared-types package, or OpenAPI / JSON-schema / protobuf
for a polyglot stack — as the single source of truth. Then **generate** aligned scaffolds for every
layer from it: DB schema, ORM model, API DTOs and route stubs, client types.

Drift becomes impossible by construction, and the same shape-diff is installed as a **CI check** so
no future hand-edit can quietly break alignment. This is rescue's contract-reconciliation, run
forward.

Where a UI is rendered, the **design contract** rides the same rails: elect a **W3C DTCG** token set
(captured or imported, never invented), project it into CSS / Tailwind / `DESIGN.md`, and guard it
in CI. Design drift becomes a build failure rather than a matter of taste.

**2. Sequence the backlog.** Emit `BuildItem`s from decided pins, ordered by `depends_on`. The waves
fall out of the DAG — contract & data model → paved road → core slices → secondary features →
polish — rather than being hardcoded. Build thin **vertical slices** (one feature end-to-end through
every layer), never horizontal layers, so there is always a running system.

### Phase 4 — Build loop (TDD-driven, restartable)
A loop over the **backlog**, not "build everything you can think of." Each item runs in a fresh
invocation loading only that item, its pin, the contract and its tests. All state is on the
append-only ledger, so an interrupted loop resumes at the first unresolved item.

**Track A (test-from-`to_be`, red → green) is the primary track here**: every feature's behavior is
a red test derived from the decision, written before any implementation. Track B (characterization)
applies only when extending an already-built slice.

The **ponytail ladder** enforces YAGNI *by construction*: build only the minimum a decision
committed to — never speculative scaffolding, which is exactly how slop is born.

**Wave checkpoints**: it pauses at each wave boundary — especially after Wave 1, the contract — runs
the generated layers, confirms the contract holds end to end, and if building revealed a decision
was wrong, **reopens the dependent pins** instead of building on a bad foundation. It never runs
fully autonomous end-to-end.

### Phase 5 — Validate (data decides)
A slice is not done because the build is green. Re-extract the shapes across the generated layers
and confirm **zero drift**; confirm the Track-A test kills mutants; confirm the behavior is
reachable from a real entry point; confirm the paved road actually runs. Read-only verdict — a pin
becomes `resolved` only on evidence. The convergence check is the completeness traffic-light:
resolved slices flip ghost → solid and the gap shrinks toward zero.

### Phase 6 — Release (ship the slice safely)
The **codebase-facing** slice of release, not the CD platform: migration scripts, version,
changelog, feature-flag code, rollback. Migrations follow **expand/contract**, so zero-downtime is
structural rather than careful. The changelog is projected from the ledger. A tested **rollback** is
mandatory. Never release on an unmade decision.

### Phase 7 — Operate & Evolve (run, observe, feed back)
**Operate** emits the instrumentation (logs, metrics, traces, health), the SLO definitions, and the
**signal manifest** that maps each `flip_signal` to real telemetry — the physical anchor of the
feedback loop.

**Evolve** runs that loop: when a signal fires, it emits a reopen event and moves the affected pins
back to `needs_input`, handing them to the interview via `slice` mode. The arc **reopens, never
decides.**

This is what makes a forged project never "done" — and what makes its `ledger.json` the audit
baseline a `codebase-rescue` can diff against years later.

---

## The 15 modules

| Phase | Modules |
|---|---|
| **1 — Frame** | `decision-frame` *(judgment)* · `acceptance-framing` *(judgment)* · `threat-model` *(judgment)* · `to-be-map` |
| **2 — Interview** | `interview-generator` *(judgment)* |
| **3 — Contract** | `contract-propagation` (one contract → every layer) · `design-propagation` (DTCG → CSS/Tailwind/DESIGN.md) · `roadmap-sequencer` (the DAG → waves) · `paved-road` (scaffold from the elected decisions) · `architecture-fitness` (boundaries as CI constraints) |
| **4–5 — Build** | `build-loop` *(judgment)* · `validate` *(judgment)* |
| **6–7 — Ship** | `release` · `operate` · `evolve` *(judgment)* |

Everything not marked *judgment* is **deterministic** — and that is a promise, not a label: each one
names the engine that produces its output.

---

## The guardrails, stated plainly

- **No scaffolding before the interview elects the decisions.** Enforced by a `PreToolUse` hook from
  `keel-core`, not by a paragraph asking nicely.
- **No agent commits a decision.** Only your committed interview answer elects anything.
- **Forced to assume?** The agent surfaces it as a **vetoable pin** instead of encoding it silently.
- **Every decision carries `flip_criteria`** — doubly important here, since you decide before you
  know the app.
- **Vertical slices, never horizontal layers.** There is always a running system.
- **YAGNI by construction** — the ladder logs which rung was used, so speculative scaffolding has
  nowhere to hide.
- **`resolved` means observed**, not "the code was written".

---

## What it produces

| Artifact | What it is |
|---|---|
| `ledger.json` | the append-only single source of truth — decisions, criteria, build items, events |
| the contract carrier | shared types / OpenAPI / JSON-schema / protobuf — the one place shape is defined |
| the generated layers | DB + ORM + API + client, plus CSS/Tailwind tokens, all round-tripping to zero drift |
| the to-be map | ghost → solid as slices land; the completeness traffic-light |
| the roadmap | `BuildItem`s levelled into waves by the dependency DAG |
| the signal manifest | each `flip_signal` mapped to real telemetry |

---

Sibling: [`codebase-rescue`](https://github.com/r3vs/keel/tree/main/plugins/codebase-rescue) — the
same machinery run backward, for the codebase you already have.

Repo and architecture: [github.com/r3vs/keel](https://github.com/r3vs/keel) · MIT.
