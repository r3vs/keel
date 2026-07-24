# keel-core

**The spine.** Every other Keel plugin declares this one as a dependency, so you normally get it
without asking for it. It ships the parts that must exist *exactly once*: the MCP server, the agent
roster, the enforcement hooks, and the shared doctrine both methodology skills read.

```bash
/plugin install keel-core@keel
```
> Only needed if you want the spine on its own. `codebase-rescue`, `greenfield-forge` and
> `keel-kit` pull it in automatically on Claude Code. **Codex has no dependency resolution** —
> there, install it explicitly.

**Requires [`uv`](https://docs.astral.sh/uv/)** on `PATH`. The MCP server is a PEP-723 script;
`uv run --script` resolves its dependencies on first launch. There is no `pip install` step, no
virtualenv to manage, and no CLI — MCP is the only runtime channel.

---

## What's in the box

| | Count | |
|---|---|---|
| MCP tools | **34** | the deterministic engine, typed and discoverable |
| Sub-agents | **6** | `researcher · brainstorm · executor · reviewer · challenger · measurer` |
| Hooks | **2** | a session banner and the pre-edit ledger gate |
| Skills | **2** | `using-the-ledger`, `run-workflow` |
| Shared doctrine | **14 docs** | the ledger spec, the interview funnel, the shape engine, … |
| MCP servers declared | **4** | `keel` · `context7` · `deepwiki` · `playwright` |

---

## The 34 MCP tools

Your agent *discovers* these — it never needs to be told a file path. Everything below is a parse,
a graph traversal or a set difference. **No LLM is in the loop**, which is why a finding can be
labelled `confidence: extracted` and skip the false-positive gate.

### Ledger — the single source of truth (8)

The append-only decisions ledger. Every other surface (the map, the interview, the brainstorm)
holds no state of its own; it projects this file.

| Tool | Does | Writes |
|---|---|---|
| `ledger_summary` | counts of pins by state, kind and severity | — |
| `interview_next` | the open questions, best-first by information gain | — |
| `ledger_add_pin` | record a finding / defect / `open_decision` | ✎ |
| `ledger_surface_assumption` | turn a *forced agent assumption* into a vetoable pin | ✎ |
| `ledger_add_remediation` | attach a `RemediationItem` (rescue) or `BuildItem` (forge) to a decided pin | ✎ |
| `ledger_set_remediation_status` | `todo → in_progress → done` | ✎ |
| `ledger_resolve` | close a pin **with the observed evidence** — refuses while any item is open | ✎ |
| `ledger_defer` | out of scope for now; stays as backlog, never silently dropped | ✎ |

**None of these elect anything.** A `DecisionEvent` comes only from a human's committed interview
answer. The write tools record; they do not decide.

### Cross-layer contract (2)

| Tool | Does |
|---|---|
| `contract_diff` | field-shape drift of every layer against the contract carrier — **the core engine** |
| `reconcile_layers` | diff two layers directly, when there is no contract to sit between them |

Eight stacks reduce to one field descriptor and are then diffed: **Postgres DDL · Drizzle · Prisma ·
Django · SQLAlchemy · GraphQL · TypeScript · Pydantic**. What comes back is `nullability_mismatch`,
`enum_mismatch`, `type_mismatch`, missing/extra fields — per entity, per field, with the layers named.

### Generation (3)

| Tool | Does |
|---|---|
| `generate_layers` | one contract → DB + ORM + API + client, round-tripping to zero drift |
| `generate_tokens` | one W3C **DTCG** token contract → CSS / Tailwind / `DESIGN.md` |
| `extract_tokens` | harvest the *de-facto* tokens a codebase already declares → candidate DTCG |

Generating the layers is how `greenfield-forge` makes drift structurally impossible instead of
merely detectable.

### Instruction carrier (2)

| Tool | Does |
|---|---|
| `generate_instructions` | project the ledger into a managed region of `AGENTS.md` (+ the `CLAUDE.md` bridge) |
| `instructions_diff` | is that region still what the ledger projects — `in_sync` / `stale` / `hand_edited` / `absent` |

The ledger is the single source of truth and **no coding agent loads it**. Every host loads one thing
unprompted: `AGENTS.md` (Claude Code via a `CLAUDE.md` that imports it). Without this pair, a project
can have a fully elected design and still hand every fresh executor a blank slate. It writes **only**
between its own markers, so the file stays yours; `hand_edited` is reported and never auto-healed,
because a decision written into the projection belongs in the ledger.

### Comprehension graph (9)

A **tree-sitter native** structural graph — a real grammar per language, not regex. Files, symbols
and tables are nodes; imports and calls are edges.

| Tool | Does |
|---|---|
| `build_graph` | build the structural graph |
| `understand_codebase` | the whole `understand`-mode bundle: graph + layered overview + tour + map |
| `explain_node` | one node's neighborhood, edges and owning layer |
| `graph_query` | *"which parts handle auth?"*, *"what depends on X?"* — over **extracted** edges only |
| `guided_tour` | a dependency-ordered walkthrough from the top entry point outward |
| `domain_view` | framework-agnostic entry points: HTTP routes, CLI, tasks, events, cron |
| `graph_map` | the graph as a self-contained navigable HTML map |
| `blast_radius` | what breaks if this node changes — reverse reachability, **staleness-gated** |
| `impact_overlay` | the blast radius of a concrete diff (`git_base` or an explicit file list) |

Staleness-gated means: if the graph was built at a different commit than `HEAD`, it says so instead
of answering confidently from a stale index.

### Findings, quality & spend (5)

| Tool | Does |
|---|---|
| `findings_gate` | normalize SARIF/OSV into one stream, then run the false-positive gate |
| `coverage_gaps` | which expected analyses **did not run** for the stacks present |
| `design_scan` | frontend AI-slop tells, design quality, a11y, drift from the design contract |
| `tokens_diff` | a CSS layer's `--variables` vs the DTCG contract |
| `docs_claims` | treat docs as **claims** about the code and flag the dangling ones |

`coverage_gaps` is the anti-overclaim tool: a report that doesn't say what it *couldn't* check is a
report that reads as clean.

### Workflow & interview (5)

| Tool | Does |
|---|---|
| `challenge_oracle` | red-team each elected `to_be` / `acceptance_criterion` / policy **before** code rests on it |
| `build_waves` | level the roadmap's `depends_on` DAG into waves; report what's actionable now |
| `render_map` | the ledger as a self-contained HTML map (`live: true` keeps it refreshing) |
| `fingerprint_scan` | signature-level per-file fingerprints — the resume / incremental baseline |
| `spend_report` | token and (with a price sheet) cost telemetry over the host's session transcript |

---

## The agent roster

**One rule: serialized writing, parallel reading.**

| Agent | Writes? | Tier | Role |
|---|---|---|---|
| `researcher` | ✗ read-only | T0 | comprehension, finding, grounded research — fans out wide |
| `measurer` | ✗ read-only | T0 | the **evidence** gate — deterministic proof the gap closed; also `flip_signal` evaluation |
| `executor` | ✎ **the single writer** | T1 | one closed scope, two-track TDD, fresh context, opens a PR — never merges |
| `brainstorm` | ✗ read-only | T2 | 2–3 options with tradeoffs for ONE pinned fork, cited |
| `reviewer` | ✗ read-only | T2 | the **judgment** gate — is the oracle satisfied honestly, then code quality |
| `challenger` | ✗ read-only | T3 | refutes the elected **oracle**; the one reopen path at a wave checkpoint |

**One object each, and evidence before judgment.** The measurer owns evidence, the reviewer owns the
code, the challenger owns the oracle. The cheap deterministic gate runs first, so review judgment is
never spent on a change that doesn't close the gap — the package's own static-first doctrine applied
to its own roster. The reviewer reads the measurer's record instead of re-running it (a
deterministic check cannot disagree with itself on a second run) and adds what evidence structurally
cannot see: a criterion can be green and still met for the wrong reason. `resolved` needs both.

A reviewer that suspects the *decision* rather than the change does not reopen it — refuting an
oracle is the T3 job, and it must leave a `ChallengeEvent` carrying the argument. An append-only
ledger whose reopens have no *why* has stopped doing the one thing it is for.

Three roles may only ever **reopen** a decision, never make one — `brainstorm` proposes,
`challenger` refutes, and the feedback loop reopens on production signal. Read-only is enforced by
the `tools:` allowlist with `disallowedTools` as a backstop, not by a paragraph asking nicely.

Each role carries a **tier**, resolved to a concrete model + reasoning effort per profile — Profile
A (Anthropic / Claude Code), B (OpenAI / Codex), C (open-weight / opencode + Pi), D (mixed). Nothing
hardcodes a model; the build reads the policy doc.

---

## Hooks

| Event | Hook | What it does |
|---|---|---|
| `SessionStart` (startup / clear / compact) | `session-start.sh` | prints the mandatory workflow check — which skill applies, and the three non-negotiables |
| `PreToolUse` on `Edit\|Write\|NotebookEdit\|MultiEdit` | `ledger-gate.py` | **denies product-code edits while `blocker`/`high` pins sit in `needs_input`** |

The gate is what turns rule #1 from prose into a mechanism. Its behavior, precisely:

- **No ledger in the project** → allow, silently. If you're not in a rescue or a forge, it is
  invisible. Being invisible when it doesn't apply is what earns it the right to block when it does.
- **Unresolved blocker/high pins in `needs_input`** → **deny** edits to product code. The to-be for
  that area isn't knowable yet; anything built on it is a guess wearing a decision's clothes.
- **Otherwise** → allow. Once the load-bearing questions are elected, writing code is the point.

It **never** blocks tests (TDD writes the failing test first), the ledger and its artifacts, or
prose. And it **fails open** — a crash in the gate must never wedge your session.

---

## Skills

### `using-the-ledger`
How to read and write the ledger from *any* task: read pins, add a finding, run the compressed
interview, record a decision with its `flip_criteria`, and never let an agent commit a decision you
did not elect. This is the spine both methodology skills run on, usable on its own.

### `run-workflow`
A deterministic, journaled orchestration engine (a TypeScript fork of `pi-dynamic-workflows`, MIT)
that fans a task out across isolated sub-agents and returns findings. Three flagship topologies:

- **`phase1-finding`** (read-only, default) — multi-modal sweep → loop-until-dry → adversarial
  verify. Returns surviving pins.
- **`challenger-verify`** (read-only) — red-teams each elected oracle under distinct lenses
  (unfalsifiable / inconsistent / unsatisfiable / unstated-assumption / ignores-fan-out).
- **`build-waves`** (WRITE) — drives the DAG's waves; one `executor` per item, each in its **own git
  worktree**, with a checkpoint between waves.

Agents can also **compose a workflow on the fly** (`--script` / `--script-stdin` into a sandboxed
VM) rather than picking from the three. The engine is **pure and never writes the ledger** — it
returns JSON, and the invoking agent writes each pin with `ledger_add_pin`. Fan-out is read; the
write stays serialized. Needs **Node** (a prerequisite scoped to this one skill); without it, the
skill degrades to running the steps sequentially by hand.

---

## MCP servers this plugin declares

You never hand-copy a server block. Claude Code auto-discovers the plugin's own `.mcp.json`; Codex's
manifest points at the same file; opencode gets the same table from a `config()` hook.

| Server | Transport | Why |
|---|---|---|
| `keel` | stdio (`uv run --script`) | the 34 tools above |
| `context7` | http | **current** library docs — beats the model's training cutoff |
| `deepwiki` | http | how a real repo actually solved it |
| `playwright` | stdio (`npx`) | rendered-DOM extraction for the design/frontend layer |

`cognee` (durable graph memory) is named in the doctrine but deliberately **left undeclared** — it
needs a container and a key, so it stays opt-in.

---

## Shared doctrine

`core/*.md` at the plugin root, read by the agents: the decisions-ledger spec (v0.6), the interview
funnel, the brainstorm protocol, the field-shape engine, contract testing, the feedback loop, the
static-analysis and knowledge-source doctrines, the assumption-surfacing rule, the agent roster, the
model tiers, and the self-model.

---

Repo, architecture and per-host packaging detail:
[github.com/r3vs/keel](https://github.com/r3vs/keel) ·
[`docs/packaging.md`](https://github.com/r3vs/keel/blob/main/docs/packaging.md) · MIT.
