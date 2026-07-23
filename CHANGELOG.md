# Changelog

All notable changes to this project are documented here. The design is complete and the runtime
spine has started; versions track design + packaging + runtime together.

## [Unreleased]

### Removed
- **The root `.claude-plugin/plugin.json` is gone.** It declared the repository itself to be a
  plugin — which it stopped being on 2026-07-16, when the architecture became four plugins under
  `plugins/`, each with its own generated manifest. The file survived that change because **nothing
  read it**: not `build.py`, not a test, not CI. Verified at the docs rather than assumed — a
  marketplace entry's relative `source` *"resolve[s] relative to the marketplace root, which is the
  directory containing `.claude-plugin/`"*, ours are all `./plugins/<name>`, and a root manifest sits
  on no documented path. Unread **and** hand-written is this repo's worst pair: it had drifted to the
  old brand and the old repo URL, and only an eyeball caught it, which is not a mechanism.
  `tests/test_mcp_declaration.py::test_the_root_is_a_marketplace_not_a_plugin` now gates it — and was
  confirmed to fail with the file restored, rather than merely passing without it.

### Changed
- **The project is named `Keel`, and for the first time every surface agrees on it.** There used to
  be three answers to "what is this called": the repo was `codebase-rescue`, the marketplace was
  `codebase-alignment`, and the infrastructure plugins were `alignment-core` / `alignment-helpers` —
  so the install line read `codebase-rescue@codebase-alignment` and the flagship plugin shared a name
  with the repo that contained all four. Three names, no two agreeing: the exact drift this package
  exists to find, sitting in its own front door. Now: repo `r3vs/keel`, marketplace `keel`, MCP
  server `keel`, plugins `keel-core` + `keel-kit`.
- **`codebase-rescue` and `greenfield-forge` deliberately keep their names.** A skill self-activates
  off its `description`, and those two words are load-bearing there — `keel-rescue` would trade
  trigger accuracy for brand symmetry. The brand carries the infrastructure; the methodology carries
  the meaning.
- **README rewritten for a reader who has never heard of any of this.** It now opens on the failure
  it detects rather than on the architecture that detects it, and proves the claim with **real
  output** from `tests/fixtures/slop-repo` plus the one-line command to reproduce it. The old hero
  described the repository's own file layout in paragraph three.
  - One line of that rewrite was cut on the house rule: the draft's hero ran `keel contract-diff`,
    a CLI that has not existed since it was removed in favour of the MCP-only runtime. A fabricated
    command in the first code block of the README is the claiming-vs-doing bug in its purest form.

## [0.1.0] — unreleased

### Removed
- **The root's host config — `.mcp.json`, `opencode.json`, `.codex/config.toml` — is gone**, and
  with it the assumption underneath it: that a user might be working *here*. They install into their
  own project, so root config reached nobody. The docs sold it as the install path anyway (`README`
  told Cursor and Codex users to *"open the repo (or add it to your workspace root)"*; `install.sh`
  printed *"copy the mcpServers block into your opencode.json"*), which meant two of four hosts had
  no install path at all — only an invitation to clone a demo. And the three copies of that one fact
  had already drifted: deepwiki declared for Claude but missing for Codex, cognee `enabled: true` in
  two of them (which the doctrine forbids *because* it cannot connect without a container), context7
  over `npx` in one and http in the others.

### Added
- **MCP delivery is now the install itself, on every host that can take it** — generated from the
  one table in `src/core/knowledge-sources.md`, so a server cannot be ordered in prose and absent
  from the product:
  - **Claude Code** reads the plugin's own `.mcp.json`; **Codex** reaches the same file through its
    manifest's `mcpServers: ".mcp.json"` (verified in `openai/codex`: `PluginManifestMcpServers::Path`).
  - **opencode** has no manifest slot for servers, but a plugin's `config(cfg)` hook receives the
    live merged config and may mutate it (verified in `sst/opencode`) — so the generated
    `adapters/opencode/plugin/mcp.ts` declares them, and `scripts/install.sh` places it. Two shape
    facts there are verified rather than inferred, and neither follows from Claude's: opencode's
    discriminator is `local`/`remote`, not `stdio`/`http`, and a local `command` is an **array**.
    Emitting Claude's shape would be valid JSON that silently declares nothing. `${CLAUDE_PLUGIN_ROOT}`
    is likewise a Claude-ism no other host expands, so the plugin resolves our server from its own
    location and degrades gracefully when it cannot.
  - The user's own config wins on every key — this fills gaps, it never overwrites a choice.
- **`scripts/install.sh` places the opencode plugin and the Pi extension** instead of printing them
  as homework, and `tests/test_mcp_declaration.py` grew the gate that keeps the root clean.
- **`README`, `docs/packaging.md`, `AGENTS.md`, `CONTRIBUTING.md` and `MEMORY.md` rewritten** — all
  predated the `src/`↔`plugins/` split and still described `scripts/sync_core.py` and
  `scripts/install-opencode.sh` (both deleted), `skills/`+`core/` at the root, and — in the very
  "try it" section — `python runtime/ledger.py`, this repo's signature bug, still on its front page.

### Added
- **Runtime** — the executable layer both skills bind to (core stdlib-only, tested in CI;
  **~170 tests** across `tests/`):
  - `runtime/ledger.py` — the shared decisions-ledger runtime (spec v0.6): kind-discriminated pin
    validation, append-only Decision/Reopen/Challenge events, enforced brainstorm/challenger/
    feedback **neutrality**, the severity threshold (blocker/high never silently defaulted), policy
    cascade, `agent_assumption` surfacing, minimal transitive reopen on both arcs, RemediationItem/
    BuildItem verbs, an information-gain-ordered interview view, a read-only CLI.
  - `runtime/shapes.py` — the field-shape engine (`core/shape-engine.md`): extractors for
    **Postgres DDL, SQLAlchemy 2, Pydantic v2, TypeScript, Drizzle, Prisma, Django, GraphQL**
    (new stacks are additive), the cross-type-system diff with both honesty rules (unresolved →
    `ambiguous` note; absence is the finding), and the **CI drift-check CLI** (exit 1 on drift) —
    rescue's contract-reconciliation core and greenfield's guardrail.
  - `runtime/generate.py` — greenfield's **contract generators**: one descriptor → DDL / SQLAlchemy
    / Pydantic / TS, aligned by construction. Proven by a **round-trip test** (generate → drift-check
    == zero drift), turning the step-0 STRONG verdict into an executable invariant; `choose_carrier`
    picks shared-types / OpenAPI / protobuf.
  - `runtime/findings.py` — the mandatory **false-positive gate** (`module-fp-check.md`): normalize
    SARIF + OSV to one stream, the CONFIRM/DOWNGRADE/DROP gate (five ordered checks, injected
    reachability + stub oracles defaulting to keep, deterministic diagnostics skip the gate),
    root-cause clustering to one pin with N anchors, a showable DROP audit trail.
  - `runtime/interview.py` + `skills/greenfield-forge/assets/decision-catalog.json` — the
    **decision-frame + funnel**: the 11-cluster catalog as machine-usable data; `expand_catalog`
    prunes by project type and skips brief-decided forks; `funnel` compresses to the asked questions
    ordered by transitive information gain with the tail as `proposed_default`.
  - `runtime/challenger.py` — the deterministic slice of the v0.6 oracle red-team (`unfalsifiable`,
    `ignored_fanout`), emitting upheld `ChallengeEvent`s that reopen via the ledger; judgment classes
    stay agent-driven. Neutrality tested (never writes a DecisionEvent).
  - `runtime/buildloop.py` — the shared **Phase-4 wave scheduler**: levels the BuildItem/pin DAG
    topologically (cycle-detecting), yields ready pins, gates each wave checkpoint; restart-safe
    because the ledger is the state.
  - `runtime/map.py` — the **visual map** as one self-contained HTML file (no build step, no
    external fetch): clickable pins, three-column contract-diff, linked interview questions,
    completeness traffic-light, as-is/to-be toggle; shared by both skills. Now renders a pin
    anchor's `node_id` and a **blast-radius impact line** when the graph enriched it.
  - `runtime/graph.py` — **deterministic graph anchoring + blast-radius** over graphify's NetworkX
    `graph.json`, with **no heuristics**: resolves a pin anchor to a stable `node_id` **only by its
    `file:line`** (exact, or a node's declared line-range — no name-matching, no plural folding, no
    basename/nearest guessing); computes blast-radius by **reverse reachability over the graph's own
    EXTRACTED edges** (its deterministic confidence tag — never the INFERRED cross-layer edges, and
    no editorial edge-type filter); enforces the `built_at_commit == HEAD` staleness gate (**refuses
    to write on a stale graph** — worse than none); enriches the ledger's `anchors[]` in place so
    the map stays self-contained. Exactly the two things the Phase-0 verdict leaves the graph —
    anchoring + impact — and nothing it is not (no field-level correspondence). `tests/test_graph.py`.
  - `runtime/treesitter_extract.py` — the **primary extraction backend** (`shapes.py` defaults to
    `backend="auto"`): a real grammar parses the whole language, so real-world **TypeScript,
    GraphQL, and SQL** just work — none of the per-repo regex patches the stdlib parsers needed. It
    is one **generic engine driven by declarative per-grammar DATA** (a `STACKS` entry = a
    tree-sitter query + type/​node maps; **no per-stack code, no heuristics, no comment-sniffing**),
    plus a small custom walk where a grammar's shape differs (SQL columns are positional). Ships
    verified specs for **TS interfaces**, **GraphQL SDL**, **Postgres/SQL DDL**, and the backend
    struct/class stacks **Go, Java, Rust, C#** (each language's nullability convention — Go `*T`,
    Rust `Option<T>`, C# `T?`, Java primitives-vs-boxed — is spec DATA, not code); adding a stack is
    a data entry, not a parser. Not a *hard* dependency: it **degrades to the stdlib parsers**
    when tree-sitter is absent (a stdlib-only environment still runs; the ledger/core stay
    stdlib-only). Every spec is a verified **byte-identical drop-in** with the stdlib extractor on
    the fixtures (so the drift-check is identical) and strictly more robust on real code.
    `tests/test_treesitter.py` (skips cleanly without the backend; the full suite is green both with
    tree-sitter and with it simulated absent).
  - `scripts/run_evals.py` — eval harness: `--validate` (CI structural gate) and `--run` (behavioral
    execution against a real agent runner + fixture, LLM-judge per assertion; no pretend mode).
  - `skills/codebase-rescue/assets/ast-grep/` — the placeholder/stub rule pack: 8 python+typescript
    rules + `sgconfig.yml` + ripgrep markers, fixture-validated (18 findings, 0 false positives).
  - Fixtures: `tests/fixtures/slop-repo/` (a misaligned mini-repo whose planted drift/stub/SQLi the
    runtime detects) and `tests/fixtures/briefs/` (crud-saas, cli-tool, api-service).
- **Greenfield step-0 gating experiment run** (2026-07-14): verdict **STRONG** — one 4-entity
  contract carrier generated all four layers (DDL, SQLAlchemy 2 ORM, Pydantic-v2/FastAPI DTOs +
  routes, TS client), each machine-validated; full generation is Plan A for that stack family,
  with four recorded frictions keeping the CI drift-check mandatory
  (`skills/greenfield-forge/references/contract-propagation.md`).
- **Activation contract**: the SessionStart hook upgraded from a nudge to a mandatory-workflow
  bootstrap (entry rule + 8-skill inventory + the three non-negotiable disciplines).
- **Cursor install steps** (README + `docs/packaging.md`) and a README note on the
  repo-vs-package naming split (`codebase-rescue` repo, `codebase-alignment` package).
- **Two sibling skills on a shared core**: `codebase-rescue` (curative) and `greenfield-forge`
  (preventive), unified by `gap = diff(to-be, as-is)` and one append-only decisions ledger.
- **Full lifecycle loop** for greenfield (7 phases): frame (acceptance criteria + threat model) →
  interview → contract & roadmap → build → validate → release → operate & evolve, closing back via
  observable `flip_criteria` + `ReopenEvent` (ledger v0.5).
- **Shared core doctrines**: decisions-ledger spec, interview funnel, brainstorm, field-shape
  engine, contract-testing, feedback-loop, static-analysis, knowledge-sources, and the agent roster.
- **Agent-agnostic packaging**: Agent-Skills-spec `skills/<name>/`, root `AGENTS.md`, a Claude Code
  plugin (`.claude-plugin/`, `agents/`, `hooks/`, `commands/`) and an opencode adapter
  (`opencode.json` + `opencode-skills` + `.opencode/command/` + `scripts/install-opencode.sh`).
- **Agent roster** (`core/agents.md`): researcher · brainstorm · executor · reviewer · challenger ·
  measurer, under serialized-writing / parallel-reading.
- **Three-gap harness** (the definitive-harness pass): the package now closes three gaps with one
  anti-divergence machine, not one.
  - *Oracle gap* — a new read-only **`challenger`** role + `ChallengeEvent` (ledger **v0.6**) that
    red-teams an elected oracle **upstream** (unfalsifiable / inconsistent / unsatisfiable / unstated
    assumption / ignored fan-out) and reopens the pin before code rests on it — the feedback loop's
    upstream twin. Both **reopen, never decide**.
  - *Silent-assumption gap* — `core/assumptions.md` doctrine + `provenance: agent_assumption`: a
    forced assumption is materialized as a vetoable, challengeable pin, never encoded silently.
  - *Operator gap* — a composable **`learning-layer`** skill: senior-grade output *while the user
    learns*, via one-mode (default-on, opt-out) micro-retrieval, teach-from-the-delta ranked to 1–2
    items, teach-the-class, and a **learner-model** gradebook (the operator-gap twin of the ledger)
    that measures mastery, fades scaffolds on evidence, and detects cargo-cult.
  - *Teach-on-rejection* — a blocking gate (reviewer / challenger / feedback loop) now names the
    class and the recognition cue, not a bare verdict — raising the operator, not just the code.
  - *Prefer-the-checkable-formulation* — a selection heuristic in `core/static-analysis.md`: author
    the spec so the strongest static signal applies, not only run it in-loop.
- **Engineering hygiene**: drift-linter + pointer verifier, CI (`.github/workflows/ci.yml`), a
  version-pinning mechanism in `bootstrap.sh`, MIT `LICENSE`, `CONTRIBUTING.md`.

- **Complete-package layer** (composed, not cloned): six composable skills — `using-the-ledger`,
  `grounded-research`, `static-first-analysis`, `project-memory`, `learning-layer`, `writing-skills`
  (meta); a
  **memory** subsystem (ledger + `MEMORY.md` + cognee MCP); **MCP** servers wired across platforms
  (`context7`, `deepwiki`, `cognee`; `github` opt-in) via `.mcp.json`, `opencode.json`, and
  `.codex/config.toml`; **Codex** + any AGENTS.md-aware agent supported; and `superpowers` referenced
  in the marketplace for the generic engineering skills instead of reinventing them.

### Changed
- **No-heuristics pass on the shape engine + graph** (design directive: deterministic, tech-stack
  agnostic). Extraction now reads only a stack's own type system — the guessing came out:
  - **comment-branding removed** — a TS `// uuid` / `// ISO datetime` no longer coerces a `string`
    to uuid/datetime. The uuid/datetime↔string equivalence is instead a **deterministic, symmetric
    diff-time rule** for stringly-typed layers (`diff_shapes` / `_STRINGLY_LAYERS`) — where it
    belongs, per the equivalence table — so the drift-check stays clean without sniffing comments.
  - **Drizzle enum name-guess removed** — a column whose enum const is unresolved is honestly
    `unknown`/ambiguous, never guessed to be an enum from a `…Enum` name.
  - **pluralization guess removed** from carrier-less `reconcile_layers` (it was English-specific):
    entity matching is now **case-insensitive exact**. Cross-convention correspondence (`users`
    table ↔ `User` model) comes from the **carrier** (`drift_check`), the Phase-0 verdict's
    strongest anchor — not from folding names.
  - **`runtime/graph.py` anchors by `file:line` only** (exact/containment), and blast-radius is
    reverse reachability over the graph's own **EXTRACTED** edges — no `_LAYER_TYPES` name matching,
    no basename/nearest guessing, no editorial edge-type lists.
- **Real-repo end-to-end validation** (`plastital_lca`, a polyglot Supabase + FastAPI + React LCA
  app) drove two deterministic extractor improvements: `extract_ddl` **hardened for real Postgres/
  Supabase DDL** (`CREATE TABLE IF NOT EXISTS`, `public.` schema prefixes, quoted identifiers,
  multi-word types like `timestamp with time zone`, `numeric`/`decimal`) — it went from **0 → 17
  tables / 290 fields** on that schema; and an **int ⟷ float equivalence** for JS/TS-family layers
  (a client's single `number` cannot express, nor get wrong, the distinction), which removed ~109
  false type mismatches. The run produced a real **102-pin** ledger + map across 40 corresponded
  API↔client entities (genuine missing/extra-field and nullability drift, e.g. a `last_checked` vs
  `last_check` rename), found **0** DB↔code name correspondence (no carrier, divergent vocabularies),
  and surfaced 3 name collisions — confirming the Phase-0 thesis that the carrier is the strongest
  anchor. Both improvements are covered by tests (`test_ddl_real_world_postgres_forms`,
  `test_int_float_equivalent_across_js_layer`).
- **Tree-sitter promoted to the primary extraction path** (the durable answer to the DDL fragility
  above: a real grammar, not per-repo regex patches). `shapes.py` now defaults to `backend="auto"`,
  and **SQL DDL** joined TS/GraphQL on tree-sitter — a byte-identical drop-in with the (hardened)
  regex parser on the fixtures, but it eats plastital's real Postgres (`IF NOT EXISTS`, `public.`
  prefixes, `numeric`, `timestamp with time zone`) with **zero targeted patches**. The regex/line
  parsers stay as the always-available fallback; the Python `ast` extractors (SQLAlchemy/Pydantic/
  Django) are already real parsers and are unchanged. The full suite is green both with tree-sitter
  installed and with it simulated absent (regex fallback).
- **Stack coverage broadened** toward "the vast majority of cases". Extraction now covers, per
  layer: **DB** — Postgres/SQL DDL (tree-sitter); **ORM/model** — SQLAlchemy · Django (Python `ast`),
  Drizzle · Prisma (regex); **API/DTO** — Pydantic (`ast`), GraphQL SDL (tree-sitter); **client** —
  TypeScript (tree-sitter); and the **backend struct/class stacks Go · Java · Rust · C#**
  (tree-sitter), each added as a declarative spec (query + type map + nullability convention as
  DATA — Go `*T`, Rust `Option<T>`, C# `T?`, Java primitive-vs-boxed), verified on fixtures. Still
  open: migrate Drizzle/Prisma off regex, and add more stacks (Kotlin, PHP, Ruby, protobuf, …) —
  the same one-spec-per-stack pattern, each hardened on a real repo when one is available.
- **Self-contained skills (Model B)**: the shared `core/` is now a single **authoring source**,
  vendored into each skill under `references/core/` by `scripts/sync_core.py` (following the
  `core→core` dependency closure). No skill points at `core/` directly, so every skill directory
  ships complete on any platform. CI gained `sync_core.py --check` (keeps each copy identical to its
  source), and `check_consistency.py` now errors on a bare `` `core/x.md` `` pointer under `skills/`.
- **Model B slimmed** (after review feedback that the vendoring surface was confusing): see-also
  cross-links inside `core/*.md` demoted to plain text so the dependency closure only follows
  load-bearing pointers — vendored copies drop **65 → 39** and each helper skill now carries only
  the doc(s) that are its actual subject; every vendored copy is stamped with a
  `GENERATED FILE — do not edit` banner by `sync_core.py`; `check_consistency.py` gained
  **command parity** (`commands/` ↔ `.opencode/command/`); and `docs/packaging.md` now answers
  "why not write the text directly in each skill?" explicitly.
- **Graph-memory backend: `@modelcontextprotocol/server-memory` → `cognee` (`cognee/cognee-mcp`)**
  across `.mcp.json`, `opencode.json`, `.codex/config.toml`, the `project-memory` skill, and the
  docs. Cognee is Apache-2.0, ships an official MCP server, runs on a single Postgres or fully
  embedded (no Neo4j), self-edits (re-weights rather than append-only-grow), and supports
  **deliberate writes** (`cognee.remember(...)`) that match the skill's "one crisp line" discipline.
  Trade-off, documented: unlike the zero-config `server-memory`, cognee needs its Docker container
  running on `:8000` and an `LLM_API_KEY` — so it stays **opt-in**; the ledger + `MEMORY.md` cover
  durable memory without it. (The layer was flagged as the weakest/most-optional; this makes it a
  genuine upgrade when a project's scale earns it, or a clean drop when it doesn't.)

### Notes
- **Both step-0 gating verdicts are recorded on trustworthy data.** Greenfield (FastAPI+SQLAlchemy
  +TS): STRONG → full four-layer generation is Plan A. Rescue's VibraFlow verdict was challenged
  (its graph was stale — 37 commits behind HEAD) and then **re-run on a fresh graph (2026-07-14)**:
  `graphify update` rebuilt it to current (`built_at_commit` == HEAD), and the verdict is **WEAK**
  cross-layer correspondence → standalone extraction is Plan A — 75 INFERRED / 0 semantic edges,
  and DB-schema nodes that exist but carry no field-level correspondence (correcting the stale
  verdict's wrong "0 DB nodes" claim). Confirmed positively: `runtime/shapes.py` extracts 113
  tables / 1290 fields from VibraFlow's real Drizzle schema.
- What remains is agent-orchestrated at runtime (the per-item TDD loop); evals execute via
  `scripts/run_evals.py --run` against a live agent runner. See each skill's `TODO.md`.
- Generic skills are **composed** from `superpowers` (MIT), not authored here.
- The vendored `references/core/` copies are generated — edit `core/*.md`, then run `sync_core.py`.
