# Dynamic Workflows — design/build spec (cross-host)

> **Status: PROPOSAL — `open_decision`, NOT elected.** No code until the to-be is elected.
> Suggested branch: `dynamic-workflows` off `main` (one worktree per scope, `branch-lifecycle`).
> This spec is the interview's input: elect the forks in §7, and then the build in §9 is mechanical.

> **Translated from Italian on 2026-08-13.** It was the last Italian file in the repo — the design
> authority for the TS workflow engine, written in a language most of the agents and contributors
> expected to execute it do not read. Structure, section numbering and every verified claim are
> preserved; only the language changed. The ledger spec took the same trip on 2026-07-14.

> **§7 and §8 are unelected pins living in prose.** Their home is a ledger — §7's forks are
> `open_decision` pins and §8's assumptions are `provenance: agent_assumption` pins, vetoable — and
> until they are recorded there, a fresh agent reading only the ledger cannot see them at all. They
> are kept here because that is where they were written, not because a design document is the right
> register for a decision nobody has made yet.

## 0. Principle

The "dynamic workflow" is **not a new concept for this package**: it is the *runtime* of the roster
rule **"serialized writing, parallel reading"**
([src/core/agents.md](../../src/core/agents.md)). The read-only roles (researcher · brainstorm ·
challenger · reviewer · measurer) **are** the fan-out; the executor is the single serialized write
track. A workflow engine makes that roster *executable*.

The constraint that decides everything: the workflow is **a projection of the ledger**, not a new
store — like the map, the interview and the brainstorm. Read-only fan-out; ledger writes always
serialized. `gap = diff(to-be, as-is)`: the workflow **closes** the gap after the election, it does
not decide it.

## 1. What already exists (verified, not from memory)

| Piece | What it is | Where |
|---|---|---|
| **`buildloop.py`** | A pure DAG scheduler over the ledger's `depends_on`: `waves()` (topological leveling + cycle detection), `ready()`, `next_item()`, `checkpoint(wave)`, `plan()`. **It does not spawn agents — on purpose.** Stdlib. | [src/runtime/buildloop.py](../../src/runtime/buildloop.py) |
| **pi-dynamic-workflows** | An MIT fork (v3.4.0) of an original by *michaelliv*; **it replicates Claude Code's contract**. A DSL (`agent/parallel/pipeline/phase/verify/loopUntilDry/checkpoint/workflow/judgePanel/gate/retry`), a journal keyed by positional index, a deterministic `vm` sandbox, and the `WorkflowAgentRunner` seam. | `QuintinShaw/pi-dynamic-workflows@main` |
| **Claude Code Workflow** | The same lineage, but **not drivable from a plugin or SDK** (main loop / `ultracode` keyword only). The *programmatic* ceiling on Claude is the Agent SDK. | — |

**Conclusion:** the "what to execute next" half is already ours (`buildloop.py`). What is missing is
the "how to execute it" half: a **runner** (concurrency + journal + resume) behind a **spawn seam**,
plus the **4 adapters**. pi-dw is the complete reference for that half, and its seam is exactly ours.

## 2. Architecture — floor / ceiling (post-"Totale": the floor is an MCP tool, not a CLI)

> ✅ **Reconciled** (see §10). The original "CLI-floor" framing was stale after the "Totale"
> decision (PR #5): there is no longer a runtime CLI. The floor is now the scheduler **exposed as
> the MCP tool `build_waves`**; `buildloop.py` remains a stdlib *library* invoked by the MCP server.

```
        run-workflow SKILL.md  (binder: invokes the engine; no Node → degrade to sequential)
                    │
        ┌───────────┴─────────────┐
   FLOOR (guaranteed parity)        CEILING (parallel, journal, resume)
   scheduler `build_waves` (MCP)    workflow engine ──seam──► spawn(prompt,{model,schema,isolation,agentType})
   buildloop.py = library via MCP                               │
   uv only, no Node                 Node required   ┌───────┬───┼────┬────────┐
                                                  Claude  Codex opencode Pi   (4 adapters)
```

- **FLOOR** = the DAG scheduler **exposed as the MCP tool `build_waves`** (`buildloop.py` stays a
  stdlib *library*, invoked by the MCP server — after "Totale" there is no runtime CLI left to run).
  It needs **only uv**, no Node. This is *literal* parity: same topology, order straight from the
  DAG; execution is done by the agent item by item, calling the MCP tools.
- **CEILING** = **one single** TS engine with the `spawn(...)` seam, invoked **by the agent inside
  the host session** (`engine/cli.ts`). It takes the DAG and the facts (`build_waves`,
  `contract_diff`, `blast_radius`) **via MCP tools** — the agent calls them and bridges the values in
  (`--args-stdin`); the engine does not speak MCP. Determinism (the journal) lives in the engine, so
  replay is reproducible **even** on the model-driven hosts (opencode/Codex), because the host is
  used only as a spawn primitive.
- **BINDER** = the `run-workflow` `SKILL.md`. It invokes `engine/cli.ts` (Node + the host's CLI); if
  Node is missing it **degrades**: run the topology's steps sequentially / by hand — **not** "run
  `buildloop.py`", which is no longer an executable.
- **Node prerequisite (decided, §10):** the ceiling requires Node; the MCP floor does not. Node is
  therefore a prerequisite **scoped to the `run-workflow` skill**, not to the whole package (which
  runs on uv + MCP).

### The spawn seam (from pi-dw's real `WorkflowAgentRunner.run`)

```
interface SpawnAdapter {
  run(prompt: string, opts: { model?, schema?, isolation?, timeoutMs?, agentType? })
    : Promise<{ result: string | object, cost?: number, tokens?: number }>
}
```

**Model policy (reuses `src/core/model-tiers.md`, does not reinvent it):** the model binds to the
**role** (`agentType`), resolved **per host at install time** in the native per-agent config
(Profiles A–D). The engine **does not** resolve models. Where the host's headless CLI can select an
installed role (opencode `--agent`), the role's model applies by itself; where it cannot (Claude
`-p` and `codex exec` have no installed-role selector), it **degrades to the session model** — the
same degradation model-tiers already prescribes for a missing row and for Pi. `model` is an
**explicit override** (e.g. the executor's escalation target), never a resolved tier. That is why
`tier` is **no longer** a field of the seam.

Per-host signatures **verified** (research pass 2026-07-22):

| Host | Warm adapter (SDK) | Cold adapter (headless CLI) | model | schema | cost | tokens |
|---|---|---|---|---|---|---|
| **Claude Code** | `@anthropic-ai/claude-agent-sdk` `query({prompt, options:{model, allowedTools, systemPrompt, maxTurns}})` → iterate to `ResultMessage` (`.result`, `.total_cost_usd`) | `claude -p "…" --output-format json --model X --json-schema '…' --max-budget-usd` | ✓ | ✓ | ✓ (SDK only) | ✗ |
| **Codex** | TS/Python SDK `Codex().run(…, {model, outputSchema, sandboxMode})`; app-server JSON-RPC | `codex exec --json --skip-git-repo-check --model X --output-schema f --output-last-message m` (prompt from stdin; **rc=0 even on error** → fail loud on the envelope) | ✓ | ✓ (`--output-schema`) | best-effort² | best-effort² |
| **opencode** | `@opencode-ai/sdk` `client.session.create()` + `client.session.prompt({agent, model, parts})`; `serve --attach` = warm | `opencode run "…" --model X --agent A --format json` | ✓ | validated in-engine | ✓ **verified** (`step_finish.part.cost`) | ✓ **verified** (`part.tokens.total`) |
| **Pi** | `createAgentSession(...)` from `@earendil-works/pi-coding-agent` (pi-dw's `WorkflowAgent`) | — | ✓ | ✓ (`structured_output` tool) | ✓ | ✓ (`getSessionStats`) |

An honest note: **token count is not exposed uniformly** — the Claude SDK gives cost only;
**opencode gives both** (verified with a real probe, opencode **v1.18.4**, WSL: JSONL,
`type:"text"`→`part.text`, `type:"step_finish"`→`part.cost`/`part.tokens.total`; reconfirmed after an
update). The engine's cost tracking keys on cost where there is cost, tokens where there are tokens,
and **degrades** — never hard-fails.

² **Codex** (real probe, codex-cli **0.137.0**, WSL): JSONL envelope verified — `thread.started` →
`turn.started` → `item.completed{item}` → `turn.completed` | `error{message}` | `turn.failed{error}`.
Two grounded facts: (a) codex **exits 0 even when the turn fails** (observed: a ChatGPT usage-limit
with rc=0) → the adapter detects `error`/`turn.failed` and **fails loud** rather than silently
returning `''` (the `item.completed` entries with `item.type:"error"` are non-fatal warnings, e.g.
the skills-budget notice); (b) the result is read from `--output-last-message <file>` (flag
verified), not from the schema item — which the exhausted quota prevented me from observing on a
success. So codex `cost`/`tokens` stay best-effort until a successful turn is seen.

**LIVE end-to-end verification (2026-07-22, opencode v1.18.4 via WSL):** the real engine drove real
opencode — a-function topology → `"4"`; **replay from the journal → 0 calls to the host**
(deterministic replay against a real host); vm-source path → `"4"`. Opt-in harness in
`src/workflow/__tests__/live-smoke.ts` (outside `npm test`: it costs tokens and requires WSL).

## 3. Topology = a projection of the ledger's DAG

The topology is **not hardcoded**: it falls out of `depends_on`, exactly the way "contracts before
logic" (rescue) and "contract → paved road → slice" (greenfield) fall out of the DAG today in
`buildloop.waves()`.

- `buildloop.waves(ledger)` → the levels → `pipeline`/`parallel` per wave.
- each `acceptance_criterion` / `RemediationItem` / `BuildItem` → one `agent()`.
- a `verify` / challenge gate → `verify()` (perspective-diverse) or the `challenger` role.
- It is the **4th surface** beside map/interview/brainstorm; **it holds no state of its own**.

## 4. The engine: what to reuse from pi-dw (MIT) and what to change

**Reuse (it is mature, tested, and replicates Claude Code's contract):**
- Journal: key `${runId}:${callIndex}` (the positional index is assigned **before** the limiter →
  deterministic); `hash` = sha256 of the call's identity (`prompt, model, tier, phase, agentType,
  schema`); replay only if `hash == cached && callIndex < firstMiss` = **longest-unchanged-prefix**.
- Persistence: atomic tmp+rename writes with `.bak` recovery; `initialTokenUsage` reseeds the
  counters on resume.
- `vm` sandbox + `DETERMINISM_PRELUDE` (neutralizes `Date.now`/`Math.random`/argless `Date()`).
  **It is not a security sandbox** — it holds only for *trusted* scripts (the user's, or an LLM's
  under supervision).
- Subagents: fresh session, `noExtensions`, **excluding `workflow`/`workflow_control`** (anti
  recursive fan-out), `dispose()` in `finally`.
- Caps: `MAX_CONCURRENCY=16`, `MAX_AGENTS_PER_RUN=1000`, `retries=3`.

**Change (this is the only substantive work):**
- Replace the Pi-specific `WorkflowAgent` with the `SpawnAdapter` seam and its 4 implementations (§2).
- Hook the topology to `buildloop.waves()` instead of a hand-written script.
- Land the output as **pins** (§5.4), not as a free-form return value.

**MIT attribution (mandatory):** reproduce **both** copyright lines from the `LICENSE` verbatim plus
the full MIT text:
```
Copyright (c) 2026 QuintinShaw
Copyright (c) Michael Livs (original pi-dynamic-workflows)
```
⚠️ Discrepancy to resolve before committing: the `LICENSE` says "Michael Livs", while `package.json`
contributors says "michaelliv". When in doubt, reproduce the `LICENSE` notice exactly as it stands.

## 5. Invariants (the guardrails — break one and you have built the forgetting twin)

1. **Pure orchestration; the ledger's only writer is the executor subagent** (via the MCP floor). The
   engine never touches `ledger.json`. This is the roster rule made runtime.
2. **Elect before fan-out.** The interview elects the to-be first, then the workflow works. The
   workflow **never** elects an `open_decision`.
3. **Agents for judgment, deterministic tools for facts.** Do not spawn an agent to approximate what
   `contract_diff`/`blast_radius`/`findings_gate` give exactly (the no-heuristics rule). The engine
   *calls* the tool inside the agent and fans out the interpretation.
4. **The output lands as a pin, not as a report.** Read-only fan-out → structured results → the write
   as a pin stays serialized. That is what makes the workflow a projection rather than a twin.
5. **Self-containment.** Do **not** depend on `npm:@quintinshaw/pi-dynamic-workflows` — it is an MIT
   fork vendored and adapted into `src/`. The `test_no_source_leaves_this_repo` gate enforces it
   regardless.
6. **Engine-side determinism.** The journal lives in the engine → replay parity even on the
   model-driven hosts (opencode/Codex), where *in-session* orchestration would not be reproducible.

## 6. Flagship topologies (pseudocode, in the DSL style to fork)

> **Status: all three implemented and tested** in `src/workflow/topologies/` (`phase1-finding`,
> `challenger-verify`, `build-waves`), registered in `cli.ts`. `build-waves` uses the `checkpoint`
> primitive (a journaled gate, auto-approving when headless) + `WorktreeAdapter` (**real** git
> isolation, one worktree+branch per executor). The pseudocode below is the reference; the code is
> the truth.

### 6.1 Phase-1 finding (rescue) — multi-modal sweep + loop-until-dry  ⟵ highest value
```js
export const meta = { name: 'rescue-phase1-finding',
  description: 'Extract as-is + find drift/dead/contradictions → pins', phases:[{title:'Sweep'},{title:'Verify'}] }

phase('Sweep')
const found = await loopUntilDry({
  round: (i) => parallel(  // finders blind to one another
    ['per-layer DB↔ORM↔API↔FE','per-entity','per-contract','dead-code','contradictions']
    .map(lens => () => agent(
      `Round ${i}. Find pins through the "${lens}" lens. Call the deterministic tools (contract_diff, blast_radius) for the FACTS; return judgment only.`,
      { tier:'medium', schema: PIN_SCHEMA }))),
  key: p => `${p.file}:${p.line}:${p.kind}`, consecutiveEmpty: 2 })

phase('Verify')  // perspective-diverse: reopens, does not decide
const kept = await parallel(found.map(pin => () =>
  verify(pin, { reviewers:3, lens:['correctness','fan-out/blast-radius','reproducibility'], threshold:0.5 })
    .then(v => v.real ? pin : null)))
return kept.filter(Boolean)   // ← the executor writes them as pins (serialized write, outside the orchestration)
```

### 6.2 challenger verify — perspective-diverse (the reviewer's upstream twin)
```js
await pipeline(args.oracles,   // elected acceptance_criteria / to_be, from the ledger
  o => verify(o, { reviewers:3, lens:['unfalsifiable','inconsistent','unsatisfiable','unstated-assumption','ignores-fan-out'] }),
  (v, o) => v.real ? null : { reopen: o.id, event:'ChallengeEvent', votes: v.votes })  // reopens the pin, does not decide
```

### 6.3 build waves — a pipeline over the DAG + worktree isolation (already `buildloop`)
```js
for (const wave of args.waves) {                 // args.waves = buildloop.waves(ledger)
  phase(`wave ${wave.index}`)
  await parallel(wave.items.map(item => () => agent(
    `Implement ${item.id} in TDD (red = an acceptance_criterion pin). Open a PR, do not merge.`,
    { isolation:'worktree', agentType:'executor', model:'big' })))
  await checkpoint(`Wave ${wave.index} complete? reviewer's verdict.`, { kind:'confirm' })  // gate before the next wave
}
```

## 7. Open decisions to elect (this proposal's pins)

*Each of these is an `open_decision` pin that has never been recorded as one. Elect them in the
interview and write them to the ledger; the "recommended" tag below is a proposal, not an election —
no agent may commit a decision the human did not make.*

- **OD-1 — Engine substrate.** (A) An MIT fork of pi-dw in TS, with a 4-adapter seam [recommended:
  mature engine, journal/vm/verify already done, all 4 hosts have a TS SDK]; (B) rewrite in Python,
  extending `buildloop.py` [consistent with the stdlib floor, but you reinvent determinism and the
  journal]; (C) no new engine, only a generator targeting each host's native primitive [less
  control, no real parity on opencode/Codex].
- **OD-2 — Execution model** (depends on OD-1). Hybrid [recommended]: a sequential `buildloop.py`
  floor plus a ceiling engine driving the hosts through the **warm SDK** · vs uniform-external
  (headless subprocess, cold, maximum parity) · vs native-per-host (warmest, 4 integrations).
- **OD-3 — First slice.** Phase-1 finding [recommended] · build-wave (extends `buildloop`) ·
  challenger-verify.

## 8. Assumptions (`agent_assumption`, vetoable)

*These are forced assumptions surfaced deliberately rather than encoded silently
(`src/core/assumptions.md`). Their home is a pin with `provenance: agent_assumption`, which a human
can veto; while they live only here, nobody can.*

- **A-1 → DECIDED (§10):** the TS ceiling requires **Node** on the user's machine; the **MCP floor
  (`build_waves`, via uv) stays Node-free**. No longer a tacit assumption: Node is a **hard
  prerequisite scoped to the `run-workflow` skill** (the whole package runs on uv + MCP without it).
  Defensible — all 4 hosts are Node/TS-SDK ecosystems — and now explicit, with a documented
  degradation to sequential.
- **A-2**: token count is not uniformly available → tracking is **cost-first**, degrading to tokens
  or to n/a. No gate depends on the token count.
- **A-3**: the pi-dw fork stays API-compatible with the peer
  `@earendil-works/pi-coding-agent >=0.80.8`; on a major bump, the Pi adapter is the first to break.

## 9. Build plan (slices, each one an `acceptance_criterion` pin, TDD)

- **Slice 0 — ✅ DONE (verified, 5/5 tests in `src/workflow/__tests__/run.ts`)** — branch
  `dynamic-workflows`; `SpawnAdapter` + `MockAdapter` + `ClaudeCliAdapter` (skeleton); the
  deterministic core `runWorkflow` (agent/parallel/pipeline/verify/loopUntilDry/phase/log) + a
  journal keyed by positional index with longest-unchanged-prefix replay. Runs on Node 22
  `--experimental-strip-types` (no deps). `src/workflow/`.
- **Slice 1 — partial** — the §6.1 topology (`phase1Finding`) runs end-to-end **against mocks** (dedup
  + dry-out + adversarial verify, tested). Missing: the `vm` sandbox + determinism guard; and
  **output→pin in the real ledger** (today the topology returns the pins as data — the serialized
  write is still to be hooked up).
- **Slice 2 — partial (7/7 tests)** — host adapters in `src/workflow/adapters/` (Codex + opencode:
  **argv/flags verified and tested** through an injectable `ExecFn` seam; Claude Agent SDK + Pi:
  *guarded* skeletons that fail loud when the dependency is missing). The `ledger_add_pin`/
  `build_waves` ports in `ports.ts` are **typed against the real MCP signatures**
  (`src/mcp/server.py`). `launch.ts` runs the topology and writes the survivors through `PinSink`
  (a **serialized** write, outside the engine). opencode **verified end-to-end live**; codex
  **envelope + fail-loud verified** (the success item was not observed: quota/auth).
  **The warm SDK adapters (`claude-sdk`/`codex-sdk`) + Pi-native are DONE** (Slice 7): written
  against the real APIs in the installed `.d.ts` files, mock-tested through an injectable `loadSdk`,
  **opt-in** (`npm i`, not shipped).
- **Slice 3 — ✅ DONE (verified, 7/7 tests)** — `vm` sandbox + determinism guard in `sandbox.ts`:
  `runWorkflowSource` (a script as source, with the primitives injected as globals), a parse-time
  blocklist + the runtime `DETERMINISM_PRELUDE` (blocks `Date.now`/`Math.random`/argless `Date()`,
  leaves `new Date(arg)` alone), `stripLeadingExportMeta`. Refactored `createWorkflowContext` to be
  shared between the a-function and a-source paths.
- **Slice 3** — bind the topology ↔ `buildloop.waves()`; the §6.3 build wave with worktrees.
- **Slice 4 — ✅ DONE** — the **`run-workflow`** skill (in keel-core) with the engine vendored
  **inside the skill** (`engine/`, a **skill-relative** path that every host injects → portable; the
  plugin root would have required `${CLAUDE_PLUGIN_ROOT}`, which is Claude-only, or a `../` that does
  not travel). `build.py` copies `src/workflow/`→`skills/run-workflow/engine/` (`__tests__`
  excluded), gated by `build --check` + `tests/test_workflow_vendored.py`. The `SKILL.md` carries the
  protocol: run `engine/cli.ts` (Node + the host CLI, **zero npm deps**) → pins as JSON → **the
  agent** writes them through `ledger_add_pin`.
- **Slice 7 — ✅ DONE** — warm SDK adapters (`claude-sdk`/`codex-sdk`) + Pi-native, verified against
  the real APIs (SDKs installed, `node_modules` gitignored and not shipped), guarded + an injectable
  `loadSdk`, mock-tested (35/36 → 41 tests total), opt-in via `optionalDependencies`. **Live
  `build_waves` solved WITHOUT an MCP client** (a fair objection from the user): the agent — which
  already has the MCP client — calls `build_waves` and bridges the result in through `--args-stdin`
  (`--args-file -`); the engine stays pure and dependency-free. What remains is only the **live**
  execution of the SDKs (needs provider auth) and the shape of a codex success item (quota).

## 10. Reconciliation with recent decisions — ✅ DONE

Two recent elections intersected this design and corrected its frame; they are now **integrated**
(the "CLI-floor" framing in §1–§2 was stale and has been rewritten):

- ✅ **The "CLI floor" no longer exists** (the "Totale" decision, 2026-07-22, PR #5). MCP is the
  **only** runtime channel on all 4 hosts (Pi via `mcp-bridge.ts`), and uv is a **hard**
  prerequisite. The floor here is **not** "run `buildloop.py` as a CLI": it is the **scheduler
  exposed as the MCP tool `build_waves`** (`buildloop.py` stays a library, invoked over MCP). The TS
  ceiling takes the DAG and the facts (`build_waves`, `contract_diff`, `blast_radius`) **via MCP
  tools** — the agent calls them and bridges (`--args-stdin`); the engine does not speak MCP.
  **§2 rewritten accordingly.**
- ✅ **Node elected as a prerequisite, scoped.** The TS ceiling adds **Node**; the MCP floor does
  not. Decided explicitly (no longer a tacit assumption — see §8 A-1): Node is **hard but scoped to
  the `run-workflow` skill**, not a second global prerequisite beside uv — the rest of the package
  runs on uv + MCP without Node, and the skill degrades to sequential when Node is missing. Note:
  the host adapters (`claude -p`, `codex exec`) are the *coding agents'* CLIs, not the old runtime
  CLI — no conflict there.
- ✅ **`tier` reuses `model-orchestration-profiles`, it does not reinvent it.** The `tier` dial was
  removed from the seam (it was `task→model`, the forbidden heuristic). The carrier is now the
  **role** (`agentType`): finder→`researcher`, verify→`reviewer`, challenger→`challenger`,
  executor→`executor`. The model resolves **per host at install** from the native per-agent config
  (`model-tiers.md` Profiles A–D); opencode applies it through `--agent`, the others degrade to the
  session model. The engine does not resolve models.

Slice 0 was untouched by any of this (the engine is agnostic about how the DAG, the role and the
facts arrive); the later slices now start from this reconciled frame rather than from the original
§1–§2.

**Resolution (Slice 4), without a controversial fork:** the engine **does not speak MCP**. A
skill/command inside the host session invokes `workflow/cli.ts` (Node + the *same* host's CLI, zero
npm deps); the engine drives sub-invocations of that CLI and **prints the pins as JSON**; the calling
agent writes them with `ledger_add_pin` — the MCP tool it already has. So `build_waves` (through
`args`) and the ledger write both stay with the agent rather than moving into the engine. That
dissolves the "how does it reach MCP" question without choosing anything contestable: the vendored
engine is invocable immediately (discovery/dry-run), and the write belongs to the agent.

---
*Grounding research (2026-07-22): pi-dw v3.4.0 source read in full; the Claude Code Agent SDK and
headless CLI via the docs; Codex `codex exec`/app-server and opencode `run`/`serve` via deepwiki;
`buildloop.py` read in the repo. The signatures and flags cited are verified, not from memory.*
