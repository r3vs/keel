# Dynamic Workflows — spec di design/build (cross-host)

> **Stato: PROPOSAL — `open_decision`, NON eletto.** Nessun codice finché la to-be non è eletta.
> Branch consigliato: `dynamic-workflows` off `main` (una worktree per scope, `branch-lifecycle`).
> Questa spec è l'input dell'interview: elegge le forche in §7, poi il build in §9 è meccanico.

## 0. Principio

Il "dynamic workflow" **non è un concetto nuovo per questo package**: è il *runtime* della regola di
roster **"serialized writing, parallel reading"** ([src/core/agents.md](../../src/core/agents.md)).
I ruoli read-only (researcher · brainstorm · challenger · reviewer · measurer) **sono** il fan-out;
l'executor è l'unica traccia serializzata in scrittura. Un motore di workflow rende quel roster
*eseguibile*.

Vincolo che decide tutto: il workflow è **una proiezione del ledger**, non un nuovo store — come la
mappa, l'interview e il brainstorm. Fan-out read-only; scrittura del ledger sempre serializzata.
`gap = diff(to-be, as-is)`: il workflow **chiude** il gap dopo l'elezione, non lo decide.

## 1. Cosa esiste già (verificato, non a memoria)

| Pezzo | Cos'è | Dove |
|---|---|---|
| **`buildloop.py`** | Scheduler DAG puro sul `depends_on` del ledger: `waves()` (leveling topologico + rilevamento cicli), `ready()`, `next_item()`, `checkpoint(wave)`, `plan()`. **Non spawna agenti — di proposito.** Stdlib. | [src/runtime/buildloop.py](../../src/runtime/buildloop.py) |
| **pi-dynamic-workflows** | Fork MIT (v3.4.0) di un originale di *michaelliv*; **replica il contract di Claude Code**. DSL (`agent/parallel/pipeline/phase/verify/loopUntilDry/checkpoint/workflow/judgePanel/gate/retry`), journal per indice posizionale, sandbox `vm` deterministica, e il seam `WorkflowAgentRunner`. | `QuintinShaw/pi-dynamic-workflows@main` |
| **Claude Code Workflow** | Stessa stirpe, ma **NON pilotabile da plugin/SDK** (solo main-loop / keyword `ultracode`). Il ceiling *programmatico* su Claude è l'Agent SDK. | — |

**Conclusione:** la metà "cosa eseguire dopo" è già nostra (`buildloop.py`). Manca la metà "come
eseguirlo": un **runner** (concorrenza + journal + resume) dietro un **seam di spawn**, più i
**4 adapter**. pi-dw è la referenza completa di quella metà, e il suo seam è esattamente il nostro.

## 2. Architettura — floor / ceiling (lo stesso pattern di MCP-ceiling / CLI-floor)

```
                 SKILL.md  (unico universale: "usa il motore se il runtime c'è; se no, buildloop.py")
                    │
        ┌───────────┴────────────┐
   FLOOR (parità garantita)   CEILING (parallelo, journal, resume)
   buildloop.py sequenziale    Motore workflow  ──seam──►  spawn(prompt,{model,schema,isolation})
   stdlib, zero deps,                                         │
   degrada senza parallelo                    ┌───────┬───────┼────────┬────────┐
                                            Claude   Codex  opencode   Pi     (4 adapter)
```

- **FLOOR** = `buildloop.py` in modalità sequenziale. Gira ovunque, zero dipendenze, nessun Node.
  È la parità *letterale*: stessa topologia, esecuzione seriale. Già esiste.
- **CEILING** = **un solo motore** con il seam `spawn(...)`. Il determinismo (journal) vive nel
  motore → replay riproducibile **anche** sugli host model-driven (opencode/Codex), perché l'host è
  colto solo come primitiva di spawn.
- **BINDER** = `SKILL.md`. Nomina topologia + gate e dice: *"usa il primitivo di orchestrazione che
  questo host espone; se nessuno, esegui `buildloop.py`"*.

### Il seam di spawn (dal `WorkflowAgentRunner.run` reale di pi-dw)

```
interface SpawnAdapter {
  run(prompt: string, opts: { model?, tier?, schema?, isolation?, timeoutMs?, agentType? })
    : Promise<{ result: string | object, cost?: number, tokens?: number }>
}
```

Firme per-host **verificate** (§ricerca 2026-07-22):

| Host | Adapter caldo (SDK) | Adapter freddo (CLI headless) | model | schema | cost | token |
|---|---|---|---|---|---|---|
| **Claude Code** | `@anthropic-ai/claude-agent-sdk` `query({prompt, options:{model, allowedTools, systemPrompt, maxTurns}})` → itera fino a `ResultMessage` (`.result`, `.total_cost_usd`) | `claude -p "…" --output-format json --model X --json-schema '…' --max-budget-usd` | ✓ | ✓ | ✓ (solo SDK) | ✗ |
| **Codex** | TS/Python SDK `Codex().run(…, {model, outputSchema, sandboxMode})`; app-server JSON-RPC | `codex exec --json --skip-git-repo-check --model X --output-schema f --output-last-message m` (prompt da stdin; **rc=0 anche in errore** → fail-loud sull'envelope) | ✓ | ✓ (`--output-schema`) | best-effort² | best-effort² |
| **opencode** | `@opencode-ai/sdk` `client.session.create()` + `client.session.prompt({agent, model, parts})`; `serve --attach` = caldo | `opencode run "…" --model X --agent A --format json` | ✓ | valida in-engine | ✓ **verif.** (`step_finish.part.cost`) | ✓ **verif.** (`part.tokens.total`) |
| **Pi** | `createAgentSession(...)` da `@earendil-works/pi-coding-agent` (il `WorkflowAgent` di pi-dw) | — | ✓ | ✓ (`structured_output` tool) | ✓ | ✓ (`getSessionStats`) |

Nota onesta: **token count non è esposto uniformemente** — Claude SDK dà solo cost; **opencode dà
entrambi** (verificato con probe reale, opencode **v1.18.4**, WSL: JSONL, `type:"text"`→`part.text`,
`type:"step_finish"`→`part.cost`/`part.tokens.total`; riconfermato dopo un update). Il cost-tracking
del motore keya su cost dove c'è, token dove c'è, e **degrada** — mai hard-fail.

² **Codex** (probe reale, codex-cli **0.137.0**, WSL): envelope JSONL verificato — `thread.started` →
`turn.started` → `item.completed{item}` → `turn.completed` | `error{message}` | `turn.failed{error}`.
Due fatti fondati: (a) codex **esce 0 anche quando il turn fallisce** (visto: usage-limit ChatGPT con
rc=0) → l'adapter rileva `error`/`turn.failed` e **fallisce forte**, non ritorna `''` in silenzio (gli
`item.completed` con `item.type:"error"` sono warning non-fatali, es. lo skills-budget notice); (b) il
risultato si legge da `--output-last-message <file>` (flag verificato), non dallo schema-item — che la
quota esaurita mi ha impedito di osservare in caso di successo. Perciò `cost`/`tokens` codex restano
best-effort finché non vedo un turn riuscito.

**Verifica end-to-end LIVE (2026-07-22, opencode v1.18.4 via WSL):** il motore reale ha pilotato
opencode reale — topologia a-funzione → `"4"`; **replay dal journal → 0 chiamate all'host** (replay
deterministico contro host reale); path vm-sorgente → `"4"`. Harness opt-in in
`src/workflow/__tests__/live-smoke.ts` (fuori da `npm test`: costa token, richiede WSL).

## 3. Topologia = proiezione del DAG del ledger

La topologia **non è hardcoded**: cade dal `depends_on`, esattamente come oggi "contracts before
logic" (rescue) e "contract → paved road → slice" (greenfield) cadono dal DAG in `buildloop.waves()`.

- `buildloop.waves(ledger)` → i livelli → `pipeline`/`parallel` per wave.
- ogni `acceptance_criterion` / `RemediationItem` / `BuildItem` → un `agent()`.
- gate `verify` / challenge → `verify()` (perspective-diverse) o il ruolo `challenger`.
- È la **4ª superficie** accanto a map/interview/brainstorm; **nessuno stato proprio**.

## 4. Motore: cosa riusare da pi-dw (MIT) e cosa cambiare

**Riusare (è maturo, testato, replica il contract di Claude Code):**
- Journal: chiave `${runId}:${callIndex}` (indice posizionale assegnato **prima** del limiter →
  deterministico); `hash` = sha256 dell'identità della call (`prompt, model, tier, phase, agentType,
  schema`); replay solo se `hash == cached && callIndex < firstMiss` = **longest-unchanged-prefix**.
- Persistenza: scrittura atomica tmp+rename con recovery `.bak`; `initialTokenUsage` risemina i
  contatori sul resume.
- Sandbox `vm` + `DETERMINISM_PRELUDE` (neutralizza `Date.now`/`Math.random`/`Date()` argless).
  **Non è una sandbox di sicurezza** — vale solo per script *fidati* (utente / LLM guidato).
- Subagenti: sessione fresca, `noExtensions`, **escludono `workflow`/`workflow_control`**
  (anti-fanout ricorsivo), `dispose()` in `finally`.
- Cap: `MAX_CONCURRENCY=16`, `MAX_AGENTS_PER_RUN=1000`, `retries=3`.

**Cambiare (è l'unico lavoro di sostanza):**
- Sostituire il `WorkflowAgent` Pi-specifico con il seam `SpawnAdapter` a 4 implementazioni (§2).
- Agganciare la topologia a `buildloop.waves()` invece di uno script scritto a mano.
- Far atterrare l'output come **pin** (§5.4), non come valore di ritorno libero.

**Attribuzione MIT (obbligatoria):** riprodurre **entrambe** le righe di copyright del `LICENSE`
verbatim + il testo MIT integrale:
```
Copyright (c) 2026 QuintinShaw
Copyright (c) Michael Livs (original pi-dynamic-workflows)
```
⚠️ Discrepanza da risolvere prima del commit: `LICENSE` dice "Michael Livs", `package.json`
contributors dice "michaelliv". In dubbio si riproduce la notice del `LICENSE` così com'è.

## 5. Invarianti (i guardrail — rompine uno e hai costruito il forgetting-twin)

1. **Orchestrazione pura; unico writer del ledger = l'executor-subagent** (via floor MCP/CLI). Il
   motore non tocca `ledger.json`. È la regola di roster resa runtime.
2. **Elect-before-fanout.** Prima l'interview elegge la to-be, poi il workflow lavora. Il workflow
   **non** eleva mai un `open_decision`.
3. **Agent per il giudizio, tool deterministici per i fatti.** Non spawnare un agent per approssimare
   ciò che `contract_diff`/`blast_radius`/`findings_gate` danno esatto (regola no-heuristics). Il
   motore *chiama* il tool dentro l'agent e fana-out l'interpretazione.
4. **L'output atterra come pin, non come report.** Fan-out read-only → risultati strutturati → la
   scrittura come pin resta serializzata. Così il workflow è proiezione, non twin.
5. **Self-containment.** **NON** dipendere da `npm:@quintinshaw/pi-dynamic-workflows` — è un fork MIT
   vendorizzato/adattato in `src/`. Il gate `test_no_source_leaves_this_repo` lo impone comunque.
6. **Determinismo engine-side.** Il journal vive nel motore → parità di replay anche sugli host
   model-driven (opencode/Codex), dove l'orchestrazione *in-sessione* non sarebbe riproducibile.

## 6. Topologie flagship (pseudocodice, stile DSL da forkare)

### 6.1 Phase-1 finding (rescue) — multi-modal sweep + loop-until-dry  ⟵ valore massimo
```js
export const meta = { name: 'rescue-phase1-finding',
  description: 'Estrai as-is + trova drift/dead/contradictions → pin', phases:[{title:'Sweep'},{title:'Verify'}] }

phase('Sweep')
const found = await loopUntilDry({
  round: (i) => parallel(  // finder ciechi l'uno all'altro
    ['per-layer DB↔ORM↔API↔FE','per-entity','per-contract','dead-code','contraddizioni']
    .map(lens => () => agent(
      `Round ${i}. Trova pin via lente "${lens}". Chiama i tool deterministici (contract_diff, blast_radius) per i FATTI; ritorna solo il giudizio.`,
      { tier:'medium', schema: PIN_SCHEMA }))),
  key: p => `${p.file}:${p.line}:${p.kind}`, consecutiveEmpty: 2 })

phase('Verify')  // perspective-diverse: riapre, non decide
const kept = await parallel(found.map(pin => () =>
  verify(pin, { reviewers:3, lens:['correttezza','fan-out/blast-radius','riproducibilità'], threshold:0.5 })
    .then(v => v.real ? pin : null)))
return kept.filter(Boolean)   // ← l'executor li scrive come pin (scrittura serializzata, fuori dall'orchestrazione)
```

### 6.2 challenger verify — perspective-diverse (upstream twin del reviewer)
```js
await pipeline(args.oracles,   // acceptance_criteria / to_be eletti, dal ledger
  o => verify(o, { reviewers:3, lens:['unfalsifiable','inconsistente','unsatisfiable','assunzione-non-detta','ignora-fan-out'] }),
  (v, o) => v.real ? null : { reopen: o.id, event:'ChallengeEvent', votes: v.votes })  // riapre il pin, non decide
```

### 6.3 build waves — pipeline sul DAG + worktree isolation (già `buildloop`)
```js
for (const wave of args.waves) {                 // args.waves = buildloop.waves(ledger)
  phase(`wave ${wave.index}`)
  await parallel(wave.items.map(item => () => agent(
    `Implementa ${item.id} in TDD (red = acceptance_criterion pin). Apri PR, non fare merge.`,
    { isolation:'worktree', agentType:'executor', model:'big' })))
  await checkpoint(`Wave ${wave.index} completa? verdetto reviewer.`, { kind:'confirm' })  // gate prima della wave successiva
}
```

## 7. Open decisions da eleggere (i pin di questa proposta)

- **OD-1 — Substrato del motore.** (A) Fork MIT di pi-dw in TS, seam a 4 adapter [consigliato:
  motore maturo, journal/vm/verify già fatti, tutti e 4 gli host hanno TS SDK]; (B) riscrivi in
  Python estendendo `buildloop.py` [coerente col floor stdlib, ma reinventi determinismo/journal];
  (C) nessun motore nuovo, solo generatore verso il primitivo nativo di ogni host [meno controllo,
  niente parità reale su opencode/Codex].
- **OD-2 — Modello d'esecuzione** (dipende da OD-1). Ibrido [consigliato]: floor `buildloop.py`
  sequenziale + ceiling motore che guida gli host via **SDK caldo** · vs esterno-uniforme (subprocess
  headless, freddo, parità massima) · vs nativo-per-host (più caldo, 4 integrazioni).
- **OD-3 — Prima slice.** Phase-1 finding [consigliato] · build-wave (estende `buildloop`) ·
  challenger-verify.

## 8. Assumptions (`agent_assumption`, vetoabili)

- **A-1**: il ceiling TS richiede Node sulla macchina dell'utente; il **floor Python resta senza
  Node**. (Tutti e 4 gli host sono ecosistemi Node/TS-SDK → assunzione debole ma esplicita.)
- **A-2**: token-count non è disponibile uniformemente → tracking **cost-first**, degrada a token o a
  n/d. Nessun gate dipende dal token-count.
- **A-3**: il fork di pi-dw resta API-compatibile col peer `@earendil-works/pi-coding-agent >=0.80.8`;
  su bump maggiore, l'adapter Pi è il primo a rompersi.

## 9. Build plan (slice, ognuna = `acceptance_criterion` pin, TDD)

- **Slice 0 — ✅ FATTO (verificato, 5/5 test in `src/workflow/__tests__/run.ts`)** — branch
  `dynamic-workflows`; `SpawnAdapter` + `MockAdapter` + `ClaudeCliAdapter` (skeleton); core
  deterministico `runWorkflow` (agent/parallel/pipeline/verify/loopUntilDry/phase/log) + journal per
  indice posizionale con replay longest-unchanged-prefix. Gira su Node 22 `--experimental-strip-types`
  (nessuna dep). `src/workflow/`.
- **Slice 1 — parziale** — topologia §6.1 (`phase1Finding`) gira end-to-end **contro mock** (dedup +
  dry-out + verify avversariale, testata). Manca: sandbox `vm` + determinism guard; e **output→pin nel
  ledger reale** (oggi la topologia ritorna i pin come dati — la scrittura serializzata è da agganciare).
- **Slice 2 — parziale (7/7 test)** — adapter host in `src/workflow/adapters/` (Codex + opencode:
  **argv/flag verificati e testati** via seam `ExecFn` iniettabile; Claude Agent SDK + Pi: skeleton
  *guarded* che falliscono forte se manca la dep). Ports `ledger_add_pin`/`build_waves` in `ports.ts`
  **tipizzati sulle firme MCP reali** (`src/mcp/server.py`). `launch.ts` esegue la topologia e scrive
  i sopravvissuti via `PinSink` (scrittura **serializzata**, fuori dal motore). Manca (serve host
  reale): opencode **verificato end-to-end live**; codex **envelope + fail-loud verificati**, ma la
  forma dell'item di successo + usage resta da vedere (quota ChatGPT esaurita); path SDK caldo
  eseguito; wiring nativo Pi (`createAgentSession`); bind live di `build_waves` via MCP.
- **Slice 3 — ✅ FATTO (verificato, 7/7 test)** — sandbox `vm` + determinism guard in `sandbox.ts`:
  `runWorkflowSource` (script come sorgente, primitive iniettate come global), blocklist parse-time +
  `DETERMINISM_PRELUDE` runtime (blocca `Date.now`/`Math.random`/`Date()` argless, lascia `new Date(arg)`),
  `stripLeadingExportMeta`. Refactor `createWorkflowContext` condiviso tra path a-funzione e a-sorgente.
- **Slice 3** — bind topologia ↔ `buildloop.waves()`; wave build §6.3 con worktree.
- **Slice 4** — `build.py` genera i binder per-host + il fallback `SKILL.md`→`buildloop.py`; gate di
  self-containment.

## 10. Riconciliazione con decisioni recenti (⚠️ da integrare prima delle slice 2+)

Due elezioni recenti intersecano questo design e ne correggono la cornice — il framing "CLI-floor" in
§1-§2 è **stale**:

- **Il "CLI floor" non esiste più** (decisione "Totale", 2026-07-22, PR #5). MCP è l'**unico** canale
  runtime su tutti e 4 gli host (Pi via `mcp-bridge.ts`), uv è prerequisito **hard**. Quindi il floor
  qui **non** è "eseguire `buildloop.py` come CLI": è lo **scheduler esposto come MCP tool
  `build_waves`** (buildloop.py resta library, invocato via MCP). Il ceiling TS prende il DAG e i fatti
  (`contract_diff`, `blast_radius`) **via MCP tool**, non shellando `.py`. Riscrivere §2 di conseguenza.
- **Conseguenza da eleggere esplicitamente:** il ceiling TS aggiunge **Node come SECONDO prerequisito
  hard** accanto a uv. Difendibile (i 4 host sono ecosistemi Node/TS-SDK), ma va deciso con la stessa
  cognizione con cui è stato rimosso il CLI. Nota: gli adapter host (`claude -p`, `codex exec`) sono i
  CLI dei *coding agent*, non il vecchio CLI runtime del repo — lì nessun conflitto.
- **`tier` deve riusare** il lavoro `model-orchestration-profiles` (tier→profilo→host, branch
  `feat/model-orchestration-profiles`), non reinventare la risoluzione modello.

Slice 0 non è toccata da nulla di questo (il motore è agnostico su come arrivano DAG/tier/fatti —
sono slice successive). Ma le slice 2-4 devono partire da questa cornice, non da §1-§2 originali.

---
*Ricerca a fondamento (2026-07-22): sorgente pi-dw v3.4.0 letto integralmente; Claude Code Agent SDK
+ CLI headless via docs; Codex `codex exec`/app-server + opencode `run`/`serve` via deepwiki;
`buildloop.py` letto in repo. Firme e flag citati sono verificati, non a memoria.*
