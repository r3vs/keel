# Decisions Ledger — Spec v0.3

Il ledger è la **singola fonte di verità** che le tre superfici della skill (mappa/wiki, intervista, brainstorm) leggono e scrivono. Nessuna delle tre tiene stato proprio: tutte proiettano una vista sul ledger. Questo è ciò che impedisce a tre agenti che parlano dello stesso problema di divergere — cioè lo stesso failure mode che la skill cura nelle codebase.

Forma su disco: un `ledger.json` nella cartella di output dell'audit (portabile, versionabile in git). Mappa 1:1 su tabelle Postgres se serve persistenza applicativa.

**Novità v0.2:** l'oggetto `Pin` è ora un'**unione discriminata stretta su `kind`** (envelope condiviso + payload `as_is`/`to_be`/`question` specifico per kind), con una variante `other` aperta come escape hatch. `DecisionEvent` guadagna `flip_criteria`.

---

## Entità

- **`Pin`** — l'unità atomica: un delta tra `as_is` (com'è ora) e `to_be` (come dovrebbe essere), o un'ambiguità da risolvere prima di poter definire il to-be. È l'oggetto appuntato sulla mappa e il perno di una domanda d'intervista.
- **`Question`** — vive SUL pin. L'intervista non è una lista separata: è la vista filtrata dei pin in stato `needs_input`.
- **`Proposal`** — output del brainstorm; scrive proposte con tradeoff, non decide mai.
- **`DecisionEvent`** — log append-only, immutabile, del *perché*; ora con `flip_criteria`.
- **`RemediationItem`** — ponte verso la fase 4; registra il gradino della ladder ponytail.

---

## Le 9 decisioni di design che portano il peso

1. **`anchors` è una LISTA cross-layer**, non un puntatore singolo. Un mismatch è multi-nodo (colonna DB *e* campo API *e* uso frontend). Poggia sugli ID nodo del knowledge graph; ogni anchor porta un `role` che dice alla UI come renderizzare.
2. **`kind` è un discriminatore** che vincola la forma di `as_is`/`to_be`/`question`. Unione stretta per i kind noti + `other` aperto.
3. **La domanda vive sul pin; l'intervista è una vista** (`state == needs_input`).
4. **Il brainstorm scrive `proposals[]`, mai `decision`.** Neutralità imposta dallo schema.
5. **`decision_log` immutabile, `pin.state` materializzato.** Regola di riconciliazione: last committed decision wins sullo stato, storia preservata.
6. **`depends_on` genera la roadmap sequenziata.** "Contratti prima della logica" cade fuori dal grafo delle dipendenze, non è hardcoded.
7. **`to_be` è DERIVATO dalle decisioni, non scritto a mano.** Roadmap = diff(to_be, as_is).
8. **Il gradino ponytail è registrato su proposte E remediation.** Minimalismo auditabile.
9. **Ogni decisione porta un `flip_criteria`** (idea da agentic-engineering): la condizione osservabile sotto cui la verità eletta va riaperta. Impedisce che una decisione presa su info incomplete si fossilizzi.

---

## Envelope condiviso (tutti i kind)

```jsonc
{
  "id": "pin_0001",
  "kind": "contract_mismatch",   // discriminatore — vedi varianti sotto
  "title": "string",             // corto, per il pannello
  "severity": "blocker",         // blocker | high | medium | low
  "confidence": "extracted",     // extracted | inferred | ambiguous
  "provenance": [{ "source": "contract_recon", "detail": "db↔api shape diff" }],
  "anchors": [                   // DECISIONE 1 — lista cross-layer
    { "node_id": "n_412", "layer": "db", "role": "db_source", "loc": "migrations/003.sql:12" }
  ],
  "state": "needs_input",        // detected | needs_input | brainstorming | decided | deferred | resolved | accepted
  "as_is": { },                  // DISCRIMINATO per kind ↓
  "to_be": null,                 // DISCRIMINATO per kind ↓ — derivato (Decisione 7)
  "question": null,              // Question | null — forma delle opzioni discriminata per kind
  "brainstorm": null,            // { proposals: [...], notes } | null
  "decision": null,              // { event_id, outcome } | null — solo da intervista
  "depends_on": [],              // DECISIONE 6
  "remediation": []              // [ RemediationItem ]
}
```

---

## Varianti discriminate per `kind`

### `contract_mismatch` — disaccordo cross-layer (verificabile)
```jsonc
"as_is": {                       // mappa layer → forma osservata
  "db": "role ENUM('admin','user')",
  "api": "role: string",
  "frontend": "role === 'superadmin'",
  "disagreeing_layers": ["frontend"]
},
"to_be": { "shape": "ENUM('admin','user')", "canonical_layer": "db" },
"question": {
  "prompt": "Il frontend usa 'superadmin', assente nel DB. Qual è l'insieme ruoli inteso?",
  "options": [                   // candidate-truth derivate dalle forme divergenti
    { "id": "opt_a", "label": "Solo {admin,user} — DB è verità", "implication": "rimuovere check FE" },
    { "id": "opt_b", "label": "Aggiungere superadmin allo schema", "implication": "migration + enum ovunque" }
  ],
  "allow_freeform": true
}
```

### `internal_contradiction` — disaccordo dentro UN layer (es. due flussi auth)
```jsonc
"as_is": {
  "variants": [
    { "desc": "JWT su /api/v1", "anchor_ref": "n_501" },
    { "desc": "cookie sessione su /api/v2", "anchor_ref": "n_777" }
  ]
},
"to_be": { "elected": "n_501", "rationale_ref": "ev_..." },
"question": { "prompt": "...", "options": [ /* le varianti come candidate */ ], "allow_freeform": true }
```

### `ambiguity` — verità multiple, va eletta PRIMA di poter definire il to-be
```jsonc
"severity": "blocker",           // tipicamente blocca la definizione del to-be
"as_is": {
  "candidates": [                // nessun "corrente": genuinamente indeciso
    { "interpretation": "orders è in scope v1", "evidence_ref": "n_...", "confidence": "inferred" },
    { "interpretation": "orders è feature futura", "evidence_ref": "n_..." }
  ]
},
"to_be": { "elected_interpretation": "string" },
"question": { "prompt": "...", "options": [ /* le interpretazioni */ ], "allow_freeform": true }
```

### `incompleteness` — stub/non-finito: è un WORK ITEM, non un difetto
```jsonc
"as_is": {
  "present": "route POST /orders definita",
  "missing": "corpo handler è `pass` / stub",
  "is_intentional_stub": true    // distingue da difetto — non renderizzare come errore
},
"to_be": { "behavior_spec": "string (cosa deve fare una volta completo)" },
"question": {
  "prompt": "orders è in scope per la v1?",
  "options": [
    { "id": "impl", "label": "Implementare ora" },
    { "id": "defer", "label": "Rimandare (deferred)" },
    { "id": "drop", "label": "Non serve — rimuovere (YAGNI)" }
  ],
  "allow_freeform": true
}
```

### `design_concern` — scelta migliorabile: GIUDIZIO, non finding
```jsonc
"as_is": {
  "current_design": "string (descrizione)",
  "concern": "string (perché è subottimale)"
},
"to_be": null,                   // resta null finché non deciso — è un'OPZIONE, non un difetto
"question": {
  "prompt": "...",
  "options": [                   // spesso alimentate dalle proposte del brainstorm
    { "id": "keep", "label": "Lasciare com'è (accepted)" },
    { "id": "prop_1", "label": "Alternativa A", "proposal_ref": "prop_1" }
  ],
  "allow_freeform": true
}
// risoluzione di default legittima: state = "accepted"
```

### `defect` — bug/security/dead-code/duplicazione: verificabile, spesso senza intervista
```jsonc
"as_is": {
  "description": "SQL injection via string concat",
  "evidence": { "tool": "semgrep", "rule_id": "python.sqli.raw", "loc": "..." }
},
"to_be": { "corrected": "usare query parametrizzata" },
"question": null,                // di norma nessuna domanda: va dritto in remediation (comunque gated dal piano)
```

### `other` — escape hatch aperto (onora "non solo pochi tipi")
```jsonc
"kind_detail": "string (che cos'è)",
"as_is": { },                    // forma libera
"to_be": null
```

---

## `Proposal`, `DecisionEvent`, `RemediationItem`

```jsonc
// Proposal (dentro pin.brainstorm.proposals[]) — DECISIONE 4
{ "id": "prop_1", "summary": "string",
  "tradeoffs": { "pros": ["..."], "cons": ["..."] },
  "ladder_rung": 3, "references": ["..."], "effort": "S" }   // S | M | L

// DecisionEvent (dentro decision_log[]) — DECISIONI 5 e 9, immutabile
{ "id": "ev_0007", "pin_id": "pin_0001", "timestamp": "ISO-8601",
  "outcome": "opt_a",            // option id | freeform
  "rationale": "string",
  "flip_criteria": "se compaiono utenti con permessi oltre admin, riaprire",  // DECISIONE 9
  "source": "interview" }        // solo "interview" committa

// RemediationItem (dentro pin.remediation[]) — DECISIONE 8
{ "id": "rem_0001",
  "action": "align",             // consolidate | implement | refactor | delete | align
  "ladder_rung": 2,
  "canonical_target": "db",      // per consolidate/align: chi è la verità
  "status": "todo" }             // todo | in_progress | done
```

---

## Ciclo di vita

```
detected ──(genera question)──▶ needs_input ──(apre brainstorm)──▶ brainstorming
                                     │                                   │
                                     │◀────────(proposte scritte)────────┘
                                     │
                          (utente committa in intervista)
                                     ▼
                                  decided ──(spawn remediation)──▶ resolved
                                     │
                              (oppure deferred / accepted)
```

`brainstorming` transitorio/opzionale. `deferred` = fuori scope ora (YAGNI a livello spec). `accepted` = riconosciuto, lasciato intenzionalmente (esito legittimo di `design_concern`).

---

## Amendamento ponytail per lo slop (gradino 2)

> **2. Già nella codebase (magari duplicato)? → consolida su UNA copia canonica, non aggiungerne una (N+1)-esima.**

Per questo `RemediationItem` ha `action: "consolidate"` e `canonical_target`: il fix registra quale copia diventa verità e che le altre convergono.

---

## v0.3 — Clustering, Policy, resolution_mode (compressione delle domande)

Il problema: **200 finding non sono 200 decisioni.** 200 SQL-injection sono UNA decisione; 15 copie divergenti di un helper sono UNA decisione. v0.3 aggiunge il funnel che comprime le domande.

### `cluster_id` sul `Pin`
Pin che condividono una decisione (stesso tipo di mismatch, stesso helper duplicato, stessa classe di vuln) portano lo stesso `cluster_id`. L'intervista chiede **una volta per cluster** e applica al gruppo. È variant-analysis usato per deduplicare le *domande*, non solo i pattern.

### `resolution_mode` sul `Pin`
- `asked` — domanda vera (ambiguity, design_concern, blocker)
- `policy_default` — risolto da una Policy impostata dall'utente (revisione passiva)
- `proposed_default` — ipotesi bassa-confidenza della coda lunga (skim in blocco, override per eccezione)

### Nuova entità `Policy`
Regola di categoria impostata dall'utente in intervista che auto-risolve i pin che matchano.
```jsonc
{ "id": "pol_schema_truth",
  "applies_to": { "kind": "contract_mismatch" },
  "rule": "DB è fonte di verità di default",
  "default_outcome": { "canonical_layer": "db" },
  "set_by": "interview",
  "exceptions": ["pin_0042"] }        // pin esclusi che restano `asked`
```
Quando una Policy cascata su un pin genera un `DecisionEvent` con `source: "policy:<id>"` che punta alla scelta dell'utente: resta una decisione **originata dall'utente**, solo amplificata. La neutralità regge (il brainstorm continua a non committare nulla).

### Regola di soglia (confermata)
Cosa può finire in default silenzioso senza disturbare:
- `severity: blocker | high` → **mai** silenzioso. Sempre `asked`, o almeno in cima al batch da rivedere.
- `severity: medium | low` → può andare in `proposed_default`.

Il volume crolla ma nulla di importante scivola via passivamente.

### Il funnel completo
```
200 pin → ~20 cluster → ~5 policy → ~10 domande vere (asked)
        → il resto in proposed_default, skimmabile in blocco
```
Ordina le domande `asked` per **information gain**: prima quelle che, una volta risposte, collassano più pin a valle. Le prime ~10 fanno il 90% del lavoro.

---

## v0.4 — Estensione greenfield (skill gemella `greenfield-forge`)

Il ledger è **condiviso** dalle due skill sorelle del repo. `codebase-rescue` è curativo (parte dall'as-is, deriva il to-be a ritroso); `greenfield-forge` è preventivo (elegge il to-be *prima*, l'as-is cresce fino a coincidere). Stesso schema, stessa proprietà anti-divergenza. Un progetto forgiato si porta dietro il suo `ledger.json`: è la **baseline di audit** che rescue potrà poi diffare contro il codice reale — chiudendo il cerchio che rescue non può chiudere sullo slop (i cui doc sono stale/aspirazionali; un ledger forgiato no).

v0.4 aggiunge, in modo **additivo** (nessuna modifica alle varianti esistenti):
- un nuovo `kind` di `Pin`: **`open_decision`** — la forcella di design non ancora costruita;
- una nuova entità **`BuildItem`** — il gemello di `RemediationItem` per la costruzione.

### Nuovo `kind`: `open_decision` — forcella di design (greenfield)

A differenza di `design_concern` (codice **esistente** subottimale) e di `incompleteness` (uno stub dentro codice che c'è), `open_decision` riguarda una scelta che **precede** il codice: nulla è ancora costruito. `as_is` è nullo (o porta solo i *vincoli dati* dal brief); `to_be` è derivato dall'elezione in intervista; la `question` è la forcella con opzioni e implicazioni a valle.

```jsonc
"kind": "open_decision",
"severity": "high",              // per fan-out a valle: alto se molte decisioni ne dipendono
"as_is": {
  "givens": ["deve girare on-prem", "il team conosce Postgres"],  // vincoli dal brief, non implementazione
  "built": null                  // niente ancora — non è un difetto, è il punto di partenza
},
"to_be": null,                   // derivato dall'elezione (Decisione 7) — mai scritto a mano
"question": {
  "prompt": "Modello di persistenza per la v1?",
  "options": [
    { "id": "opt_pg",  "label": "Postgres relazionale (unico datastore)", "implication": "schema-first; contratto = shared-types" },
    { "id": "opt_doc", "label": "Document store",                          "implication": "schema flessibile; validazione a runtime" }
  ],
  "allow_freeform": true
},
"depends_on": [],                // cablato dal decision-catalog: es. 'stile API' depends_on 'modello dati'
"cluster_id": "cl_persistence"   // forcelle correlate risolte da una sola policy
```

Ciclo di vita identico agli altri pin: `detected → needs_input → (brainstorming) → decided → resolved`. Una volta `decided`, la Fase 3 non calcola un diff di rientro ma **genera** i `BuildItem` che realizzano il `to_be` eletto (l'as-is cresce fino a coincidere). `deferred` = fuori scope v1 (resta backlog futuro, l'aggancio naturale alla modalità `slice`); `accepted` non si applica (non c'è un design esistente da lasciare com'è).

Regola di soglia invariata: un `open_decision` ad alto fan-out (molti `depends_on` in ingresso) è tipicamente `high`/`blocker` → **sempre `asked`**, mai default silenzioso — è il seme dello slop lasciare che il modello riempisca in silenzio una forcella non decisa. Le forcelle di coda (naming, dettagli di stile) possono andare in `proposed_default`.

### Nuova entità: `BuildItem` — il gemello greenfield di `RemediationItem`

Dove `RemediationItem` chiude un gap su codice esistente, `BuildItem` **costruisce** ciò che una decisione ha committato. Stessa disciplina (gradino ponytail registrato, minimo indispensabile), verbi diversi. Vive nello stesso contenitore `pin.remediation[]`.

```jsonc
{ "id": "bld_0001",
  "action": "scaffold",          // scaffold | implement | wire | configure
  "build_track": "A",            // A = red→green dal to_be eletto (principale) · B = caratterizzazione (solo estendendo)
  "ladder_rung": 7,              // YAGNI per costruzione: mai costruire oltre ciò che la decisione richiede
  "contract_carrier": "shared-types",  // per 'scaffold' del contratto: la fonte unica da cui si generano i layer
  "depends_on": ["bld_0000"],    // il DAG: client depends_on API depends_on contratto
  "status": "todo" }             // todo | in_progress | done
```

`action`:
- **`scaffold`** — generare da una fonte unica: il contratto → DDL/ORM/DTO/tipi client allineati *per costruzione*; oppure la paved road (harness di test, linter, CI, session-start hook).
- **`implement`** — realizzare il comportamento di uno slice verticale (Track A: red test dal `to_be`, poi il minimo che lo fa passare).
- **`wire`** — collegare pezzi già scaffoldati (una rotta al suo handler, un form al suo endpoint).
- **`configure`** — impostazioni deterministiche discese da una decisione (env, secrets, feature flag).

Le waves cadono dal `depends_on` (contratto & modello dati → paved road → slice core → feature secondarie → rifinitura), non sono hardcoded — esattamente come le waves di rientro in rescue. Il diff `gap = diff(to_be, as_is)` resta l'invariante: qui `as_is` parte vuoto e la roadmap è il backlog di costruzione, che a v1 completata tende a zero.
