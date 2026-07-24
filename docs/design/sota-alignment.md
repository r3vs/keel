# SOTA alignment — piano di build

> **Stato: COSTRUITO INTEGRALMENTE (2026-07-24).** Tutti i blocchi 0–5 sono in `sota-alignment`,
> sette commit, 551 test verdi e cinque gate puliti. Le deviazioni dal piano originale sono marcate
> **[deviazione]** dove sono avvenute, con il motivo — non riscritte via.
>
> **Stato originale: ELETTO in sessione (2026-07-24).** L'input è lo studio del corpus PRD di VibraFlow
> (`docs/prd/*`, 11 file, commit `95ff71c`) più l'analisi di `affaan-m/ECC continuous-learning-v2`.
> Branch: `sota-alignment` off `main`.
>
> Le forche che **non** ho potuto risolvere da solo sono in §9, marcate come assunzioni vetoabili
> (`agent_assumption`, `core/assumptions.md`). Tutto il resto è deciso e costruibile.

## 0. Il principio che ordina il piano

Una sola regola, e corregge quella che c'era prima.

> **Il determinismo è un dial per-step, non una proprietà del modulo.**
> Non "no heuristics", ma: **niente giudizio travestito da calcolo, e niente calcolo dove c'è già
> un carrier.**

Il motivo per cui la formulazione vecchia era pericolosa: un check finto-deterministico è **peggio**
di un check a giudizio, perché porta un'autorità che il secondo non rivendica. Un modulo
`type: deterministic` che grepa prosa asserisce *"questo è provato"*. Un agente che dice *"credo che"*
no. Il badge verde è il danno, non il giudizio.

Il repo aveva già questo bug **su di sé**: 4 moduli di `greenfield-forge` dichiaravano
`type: deterministic` con `engine: agent:*` (§1). Il gate esistente li accettava perché verificava
solo che *un* engine fosse nominato, mai la **coerenza** fra il tipo dichiarato e ciò che l'engine è.

### I tre test per decidere il livello di uno step

1. **Esiste già un carrier che codifica la risposta?** (AST, symbol table, schema, storia git, hash)
   → deterministico, e chiamare un modello sarebbe spreco.
2. **L'implementazione deterministica sarebbe un'imitazione a regex del giudizio?** → agente,
   etichettato `D2`. Il grep sulla prosa è il caso da manuale.
3. **La versione deterministica è più economica *e* ugualmente corretta?** Se è più economica ma
   meno corretta non è una vittoria: è un downgrade con un badge verde.

## 1. Cosa esiste già (verificato in questa sessione, non a memoria)

| Pezzo | Stato reale | Dove |
|---|---|---|
| Gate engine sui moduli | `type: deterministic` **deve** nominare un `engine`, validato contro l'inventario tool del server MCP. **Non** verifica la coerenza tipo↔engine. | [scripts/check_consistency.py](../../scripts/check_consistency.py) |
| Moduli mislabeled | rescue 29 moduli: 24 `mcp:` + 1 `external:` + 4 judgment — puliti. greenfield 16: **4 `deterministic` con `engine: agent:*`** (`paved-road`, `architecture-fitness`, `release`, `operate`). | `src/skills/*/modules.json` |
| Degrado non silenzioso | Già dottrina **per i tool statici**: `coverage_gaps` emette un pin `incompleteness` per ogni capacità attesa e non coperta. *"Unchecked non deve mai leggersi come clean."* Manca la generalizzazione a un seam qualsiasi. | [src/core/static-analysis.md](../../src/core/static-analysis.md) |
| Formulazione controllabile | Già dottrina: *"non solo controllare col segnale più forte, ma **autorare la spec perché il segnale più forte si applichi**"*. È il seme della graduazione-a-carrier (§7). | static-analysis.md |
| Osservazione ≠ verifica | Già dottrina in prosa: *"se non riesci a osservarlo, dillo — un claim non verificabile riportato come verificato è peggio di uno aperto."* **Ma non esiste uno stato** che lo renda esigibile. | [verification-before-completion](../../src/skills/verification-before-completion/SKILL.md) |
| Blast radius | Reverse-reachability sul grafo, `max_depth`, filtro per tipo di edge. **Nessun** co-change, nessun confronto dichiarato↔effettivo. | [src/runtime/graph.py](../../src/runtime/graph.py) |
| Scheduler | `ready()` = **sola chiusura delle dipendenze**. Nessun cancello di limitatezza sull'item. | [src/runtime/buildloop.py](../../src/runtime/buildloop.py) |
| Docs come claim | `docs_claims.py` risolve i riferimenti dei doc *trovati* contro il grafo → pin candidati. **Una direzione sola**: nessun gate su ciò che il pacchetto *scrive*. | [src/runtime/docs_claims.py](../../src/runtime/docs_claims.py) |
| Arco upstream | `challenger` + `ChallengeEvent` (spec v0.6), 6 classi di refutazione. Il premortem è una **modalità mancante**, non un ruolo mancante. | [decisions-ledger-spec.md](../../src/core/decisions-ledger-spec.md) |
| Cross-provider | Profilo D (mixed cross-provider) cablato e verde, **mai usato come segnale di sicurezza**. | [src/core/model-tiers.md](../../src/core/model-tiers.md) |
| GitHub | Zero. Tre menzioni di passaggio nei playbook, `github` MCP opt-in, niente che governi issue/PR. | — |

**Conclusione:** metà delle fondamenta esiste già come *prosa*. Quello che manca quasi ovunque è la
**forma dato** che la rende esigibile — uno stato, un campo, un check. Il piano è in larga parte
"dare i denti a regole che il repo già dichiara", non aggiungere dottrina nuova.

---

## Blocco 0 — Fondamenta di onestà · **COSTRUITO in questo passaggio**

### 0.1 I tre assi di fiducia (`core/trust-axes.md`, nuovo)

Un output governato porta **tre assi ortogonali, mai fusi in un punteggio unico**:

| Asse | Domanda | Valori |
|---|---|---|
| **Determinismo** | come si riproduce il risultato? | `D0` calcolo su carrier · `D1` ricostruibile da artefatto pinnato · `D2` giudizio sul percorso |
| **Rung di verifica** | quanto duramente è stato controllato il claim? | `self_check` · `re_read` · `observed` · `cross_derived` |
| **Burden di review** | che revisione esige il rischio? | già esistente: `severity` × blast radius |

Regola di composizione: **la postura mostrata è la congiunzione dei tre, mai l'asse più lusinghiero.**
Un output `D2` può raggiungere `observed`; un calcolo `D0` può esigere revisione umana perché il suo
raggio è alto. E: **il determinismo non è un obiettivo da massimizzare.** Non si de-agenta mai uno
step che ha bisogno di giudizio solo per guadagnare un badge più verde.

### 0.2 Coerenza tipo↔engine, esigita dal linter

`check_consistency.py` guadagna un check: un modulo `type: deterministic` **non può** nominare
`engine: agent:*`. I 4 moduli greenfield mislabeled diventano `type: judgment`, che è ciò che sono —
generano da decisioni elette, ed è un lavoro di giudizio.

### 0.3 `correctness_unknown` — spec ledger v0.7

Terzo esito di prima classe fra `decided` e `resolved`: il lavoro è stato fatto, la correttezza
**non è stabilibile** con l'evidenza disponibile. Blocca la chiusura e forza una mossa esplicita.
Senza questo stato la dottrina *"resolved = osservato"* genera pressione verso un `resolved` falso.

### 0.4 Degradare è permesso, fingere no — generalizzato

La regola esiste per i tool statici; sale a regola di seam: **quando un seam qualsiasi è
irraggiungibile, l'assenza diventa un fatto nel ledger.** Uno scanner mancante non è mai una
scansione pulita; un MCP che non risponde non è mai un'assenza di findings.

### 0.5 Divieto del loop `scrivi docs → re-ingerisci docs`

I doc generati da agente sono artefatti **derivati**: possono alimentare il retrieval *dopo*, mai
essere il percorso di bootstrap della verità. La modalità `understand` è strutturalmente esposta.

---

## Blocco 1 — Architettura

### 1.1 Landing-Zone Readiness Gate + edge `hardens` — **COSTRUITO** (spec v0.8, `345b0e0`)

Costruito senza aggiungere un tipo di edge: i prerequisiti di hardening sono normali voci di
`depends_on`, quindi lo scheduler a onde li ordina senza meccanismo nuovo e la regola esistente
(*solo `resolved`/`accepted` chiude un edge*) significa già che il cambiamento non parte finché il
terreno non è davvero riparato. `runtime/readiness.py` calcola la zona e i quattro carrier `D0`;
il verdetto è `D2` e l'oggetto registra **entrambi i livelli** invece di fonderli. Due rifiuti invece
di due degradi (grafo stale, anchor irrisolvibile) e due discipline di cui **una è meccanica**
(change-justified: un pin ancorato fuori zona viene rifiutato dal ledger).

Dottrina: [src/core/landing-zone.md](../../src/core/landing-zone.md).

<details><summary>Il piano originale, per confronto</summary>

Prima di pianificare un cambiamento su una zona esistente: audit **scopato al solo blast radius di
quel cambiamento** → verdict `ready` / `harden_first` / `redesign`. Se `harden_first`, la remediation
diventa **prerequisito bloccante** espresso come edge `hardens` nel DAG.

Due discipline lo tengono chiuso, o diventa una riscrittura aperta:
- **blast-radius-scoped** — un hotspot fuori dalla zona toccata non entra nel verdict;
- **change-justified** — si ripara solo ciò che riduce il rischio di *questo* cambiamento, mai
  perché il codice è imperfetto.

Livelli onesti: la zona e le sue metriche sono `D0` (dal grafo); **il verdict è `D2`** — è giudizio
su quelle metriche, e va etichettato così.

Perché conta: è il **ponte mancante fra `codebase-rescue` e `greenfield-forge`**. Oggi due skill
separate; con questo un solo DAG in cui i pin di rescue sono prerequisiti dei BuildItem di forge.
È l'unico item che cambia la *forma* del pacchetto invece di aggiungerci sopra.

</details>

### Difetto trovato e chiuso mentre costruivo 1.1

`correctness_unknown` (Blocco 0) era **un buco nero**: non compariva né in `interview_view()` né in
`buildloop.ready()`. Uno stato che blocca la chiusura e non appare su nessuna superficie non è un
gate, è lavoro perso. Ora porta la forcella a cinque opzioni ed entra nell'interview, dove un
blocker non verificabile ordina **sopra** l'information gain: il fan-out ordina domande ancora
aperte, un blocker non verificabile non è una domanda da sequenziare bene, è una da non saltare.

Lezione per gli item rimanenti: **ogni stato nuovo va cercato su tutte le superfici prima del
commit**, non solo testato in isolamento.

### 1.2 Agent-Ready Gate — due strati, tenuti distinti · **COSTRUITO** (`bf53ec2`)

`buildloop.ready()` oggi controlla solo la chiusura delle dipendenze: un item vago passa senza attrito.

| Strato | Cosa | Livello | Chi |
|---|---|---|---|
| **Precondizioni** | comandi di validazione dichiarati? file o strategia di discovery? blast radius calcolato? rollback? stop conditions? | `D0` presenza | runtime |
| **Qualità** | il criterio è davvero *falsificabile*? lo scope è davvero *chiuso*? | `D2` giudizio | `challenger` (mestiere già suo) |

I due strati restano **separati nella card**, mai fusi in un verdict unico. Instrada indietro invece
di bloccare: `needs_interview` / `needs_research` / `needs_hardening` / `human_only`.

**[deviazione — una rotta in più]** Il piano ne nominava quattro e poi introduceva uno strato di
qualità di proprietà del `challenger` **senza un posto dove mandarlo**. Era un buco: infilarlo in
`needs_research` (un ruolo diverso) lo avrebbe nascosto invece di chiuderlo. Quindi `needs_challenge`.

**[deviazione — nessun campo nuovo]** «rollback? stop conditions?» sembravano precondizioni separate
da un oggetto `preflight` da inventare. Sono esattamente i `guardrails` e gli `abort_criteria` che il
premortem già produce: **il premortem È il preflight**. Precondizioni finali: `oracle` · `scope` ·
`terrain` · `premortem`, ognuna su un carrier che esiste già. Il gate è **advisory**: non toglie
niente da `ready()`, perché un item che sparisce senza destinatario è lo stesso buco nero di uno
stato che non compare da nessuna parte.

### 1.3 Premortem come seconda modalità del `challenger` · **COSTRUITO** (`bf53ec2`)

Il challenger refuta **l'oracolo** (il criterio è sano?); il premortem assume che **il piano** sia già
fallito e lavora a ritroso verso guardrail, precheck e criteri di abort. Stesso ruolo read-only,
seconda modalità — **il roster resta a sei**. Obbligatorio sopra blast radius medio, su tool con
side-effect, sui retry. Il campo `paper_tigers[]` (rischi che sembravano gravi ma sono già mitigati,
**con evidenza**) è il meccanismo anti-rumore. `D2` puro, ed è giusto così.

**[deviazione — obbligatorietà senza numero nuovo]** «sopra blast radius medio» avrebbe richiesto una
soglia inventata. `premortem_required()` la deriva invece da quattro carrier che il ledger ha già:
severità `blocker|high`, un verdetto landing-zone debole, una storia registrata di riaperture, e il
`_FANOUT_THRESHOLD` che `ignored_fanout` usa già — dichiarato una volta e riusato, non inventato due
volte.

### 1.4 Tassonomia chiusa dei fallimenti · **COSTRUITO** (`bf53ec2`)

Vocabolario unico che premortem, labeling post-run e recovery condividono, invece di tre. Il
vocabolario è `D0` (è una enum); **la classificazione è `D2`** e va detto, non nascosto.

---

## Blocco 2 — Carrier nuovi · **COSTRUITO** (`5f397dd`)

Qui il determinismo è una vittoria vera: il carrier esiste già e nessuno lo legge.

### 2.1 Co-change dalla storia git (`D0`)

Se un file modificato ha edge di co-change forti (insieme in ≥3 commit passati) verso file **assenti
dal diff**, segnala l'omissione. È la tesi del pacchetto — la deriva cross-layer — derivata da un
**carrier indipendente**: la storia git invece delle field shape. Due carrier che concordano su un
finding valgono molto più di uno; **due che discordano sono essi stessi il segnale.**

**[nota]** `readiness.cochanged_outside` ora **delega** a `cochange.outside`: due implementazioni di
«cosa si muove insieme» sarebbero divergenti, e un pacchetto che caccia la divergenza non può
spedirne una propria.

### 2.2 Blast radius dichiarato vs effettivo (`D0`)

Post-esecuzione: se il diff reale supera il raggio dichiarato dall'item, emetti un finding. Prende lo
scope creep dell'executor senza chiedere niente a nessuno.

**[deviazione — una direzione sola è un finding]** Il confine è la landing zone che il pin ha **già
registrato**, cioè qualcosa che un umano ha visto e accettato, mai una linea tracciata dopo. Toccare
*meno* della zona non è un finding: un blast radius è ciò che *potrebbe* essere colpito e la scala
minima punta sotto per costruzione. Zero confine dichiarato → `checked: false`, perché non
controllato non deve mai leggersi come pulito.

### 2.3 Ri-derivazione cross-provider sui claim ad alto rischio (`D2` × 2)

Per pin irreversibili o ad alta severità, il claim va **ri-derivato indipendentemente da un modello di
un provider diverso**: l'accordo è il pass, **la divergenza forza review umana**. Un'allucinazione
single-provider difficilmente si riproduce cross-provider, quindi il disaccordo *è* il segnale.
L'infrastruttura c'è già (profilo D) e non è mai stata usata per questo. È il rung `cross_derived`
di §0.1.

---

## Blocco 3 — Superfici nuove · **COSTRUITO** (`c2651b0`)

### 3.1 Docs: grounding gate in direzione di pubblicazione (`D0`)

`docs_claims.py` audita i doc *trovati*; farlo girare su ciò che il pacchetto *scrive* costa quasi
nulla. Regola assoluta: un simbolo che non risolve viene **droppato o marcato `unknown`, mai
pubblicato**. Il symbol lookup è il carrier perfetto — caso 1 dei tre test.

### 3.2 `DocCatalog` + staleness graduata

Catalogo interrogabile *prima* che la prosa esista (soggetto, owner, freshness, source set, status).
Freshness **graduata**, non flag: decadimento temporale × distanza-di-cambiamento — una fonte citata
direttamente decade in fretta, un importer a 1 hop meno, un partner di co-change meno ancora. Più il
cascade: una fonte cambiata invalida il proprio doc *e* i suoi importer *e* i partner di co-change.

> l'hash del contenuto prende *cosa è letteralmente cambiato*; il cascade prende *cosa è ora stale
> a causa di quello*.

Oggi c'è solo `built_at_commit`: staleness binaria e globale. I pesi del decadimento sono
un'**ipotesi tarabile** e vanno dichiarati tali, mai nascosti come costanti.

Approvazione **per-file**, quattro esiti: approvato / rifiutato / **emendato-poi-approvato** /
selezione parziale. Commit timbrato con l'id della run di rigenerazione.

### 3.3 GitHub `maintainer_assist`, e si ferma lì

Triage, label, commento, review, request-changes, report di merge-readiness. **Nessun auto-close,
nessun merge.** Lo stato resta di GitHub, la policy resta del pacchetto — il ledger non specchia mai
lo stato dell'host, ci si collega.

Due regole rendono onesta l'intera cosa:
- **Un contenuto in arrivo è non fidato per costruzione.** Una issue è testo scritto da uno
  sconosciuto: può influenzare sommario, citazione ed evidenza per review umana, **mai** policy,
  gate, elezione o istruzioni. È l'unico posto dove il reticolo dei trust tier è *portante*.
- **I modi di auto-close non si implementano finché non c'è un tasso di falsi positivi misurato.**
  Il permesso si guadagna con i dati — che è anche il modo onesto di non implementarli adesso.

---

## Blocco 4 — Igiene · **COSTRUITO** (`4501520`)

- **`policy_hash` su ogni decisione**, persistito *prima* che l'esito abbia effetto: hash di roster
  agenti + permessi + versione spec ledger + versione skill. Un cambio di permessi diventa **un delta
  di hash nel trail**.
- **Stale-skill detection a runtime.** `SKILL.md` con hash pinnato: al load si ricalcola, se diverge
  → warn + downgrade della fiducia. `build.py --check` fa questo **al build**; installato, nessuno.
- **Due test comportamentali sugli invarianti**, non unit test: *"un'azione su protected path fa
  scattare il gate"* (asserire che è **scattato**, non che il task è finito) e *"tutte le scritture
  passano dal canale governato"* — l'invariante MCP-unico-canale, asserito invece che convenuto.
- **Tag di stato sulle affermazioni**: `normative | derived | deferred | hypothesis`, lintabile.
  Regola annessa: **un trend senza finestra di misura e senza soglia di falsificazione è uno slogan.**
  Una costante magica senza carrier è un'ipotesi: si etichetta, non si nasconde né si evita.
- **Disciplina anti-falsi-positivi sul *generatore*.** `findings_gate` filtra il singolo finding;
  manca il livello sopra: barra di precisione per generatore, cooldown per tipo, soppressione dei
  quasi-duplicati — e **un generatore che inciampa ripetutamente viene demolito**. Senza questo, ogni
  segnale nuovo del Blocco 2 è un potenziale flooder.

---

## Blocco 5 — Apprendimento con carrier · **COSTRUITO** (`6f194e4`), e ultimo di proposito

Valutazione di `continuous-learning-v2` (ECC): **la metà osservativa è giusta, la metà inferenziale è
quella che questo repo ha già demolito due volte** (`learner.json` declassato nel red-team,
`self_assessment` rimosso dopo l'adversariale).

Giusto: **hook invece di skill per osservare** — un hook è eseguito dall'harness, l'attivazione di una
skill è mediata dal giudizio del modello. Differenza categorica, non quantitativa. È l'applicazione
corretta del dial: cattura `D0`, interpretazione `D2`.

Rotto: la confidenza non ha carrier (`0.7` da *"5 istanze osservate"*, e sale quando *"l'utente non
corregge"* — **l'assenza di correzione trattata come evidenza di correttezza**); la soglia è una scala
di autonomia senza prova (`0.7` = auto-applicato); il loop si auto-certifica (gli instinct sono
validati da sessioni che girano *sotto quegli instinct*); `/evolve` genera harness senza gate di
regressione; e le osservazioni catturano contenuto non fidato che poi **influenza il comportamento**.

### La forma che invece regge

Il ledger ha già il collegamento agli esiti che a quel design manca:
`pin → decisione → BuildItem → verdetto measurer → verdetto reviewer → resolved | riaperto`.
E il segnale migliore è già lì, non catturato da nessuno:

> **il delta fra l'opzione che il brainstorm ha raccomandato e quella che l'umano ha eletto.**

Più i `ChallengeEvent` che hanno retto, i verdetti reviewer negativi, i `flip_criteria` scattati.
Eventi rari, umani, avversarialmente verificati, già persistiti — l'opposto di *"5 istanze osservate"*.

| Passo | Chi | Livello |
|---|---|---|
| Cattura degli eventi di divergenza | hook | `D0` — già nel ledger, va solo letto |
| Proposta di una regola da un cluster | agente | `D2`, **dichiarato** |
| **Graduazione a carrier** | deterministico | `D0` |
| Elezione | umano, interview | l'unica autorità |

**La graduazione è il pezzo che nessuno di questi sistemi fa.** Una regola candidata è promossa
**solo se esprimibile come qualcosa di controllabile**: un matcher ast-grep, una regola di shape, un
lint, un predicato `flip_criteria`, un test. Cioè:

> **non memorizzi la credenza, memorizzi il check che la credenza implica.**

Una regola che non gradua resta una proposta senza autorità: visibile sulla mappa, mai applicata. E
la demozione diventa onesta a sua volta — una regola graduata a check si demolisce con il **proprio
tasso di falsi positivi misurato**, non con un contatore che scende.

Costo onesto: **si impara molto meno.** È il trade giusto — l'alternativa impara di più e impara cose
sbagliate con sicurezza.

Ultimo di proposito: i segnali che gli servono (divergenza brainstorm↔umano, reject del reviewer,
flip scattati) esistono solo **dopo** che dei cicli hanno girato. Costruirlo prima significa scrivere
un osservatore che osserva il vuoto.

---

## 6. Cosa il piano rifiuta esplicitamente

- **Ladder di autonomia a sei gate e livelli A0–A5.** Il pacchetto ha una regola più semplice e
  corretta: solo la risposta committata dell'umano elegge, i ruoli read-only riaprono. Sei gate
  sarebbero cerimonia importata da un prodotto ospitato con telemetria che qui non esiste.
- **Scoring di memoria con pesi tarati, decay contract, posterior bayesiani.** Nessun substrato
  telemetrico multi-run: sarebbero costanti magiche senza carrier.
- **Un sesto e settimo ruolo nel roster.** Il premortem entra nel `challenger`, la readiness si
  divide fra runtime e `challenger`. Il roster a sei è un asset.
- **Instinct auto-applicati per frequenza.** Vedi Blocco 5.

## 7. Ordine di build

```
Blocco 0  fondamenta            ← COSTRUITO in questo passaggio
Blocco 1  1.1 landing-zone (la leva) → 1.2 agent-ready → 1.3/1.4
Blocco 2  2.1+2.2 (costo basso, carrier già presente) → 2.3 (infra già c'è)
Blocco 3  3.1 (quasi gratis) → 3.2 → 3.3
Blocco 4  a spizzichi, ogni volta che si tocca l'area interessata
Blocco 5  ultimo, dopo che esistono esiti da cui imparare
```

## 8. Origine di ogni item (per non riderivare l'argomento)

| Item | Fonte | Cosa ho cambiato rispetto alla fonte |
|---|---|---|
| Tre assi di fiducia | VibraFlow `04` §G2 | invariato — è già la formulazione onesta |
| `correctness_unknown` | VibraFlow `03` §221 | portato a **stato del pin**, non solo esito di review |
| Landing-zone + `hardens` | VibraFlow `02` §543 | il verdict marcato `D2`, non venduto come calcolo |
| Agent-Ready Gate | VibraFlow `02` §494 | **spezzato in due strati** — la fonte li fonde in un verdict, e metà sono giudizi |
| Premortem | VibraFlow `02` §527 | modalità del `challenger`, **non** un ruolo nuovo |
| Co-change mancante | VibraFlow `03` §173 | invariato |
| Cross-provider | VibraFlow `04` §G:200 | legato al profilo D già esistente |
| Docs: no-fabricated-API | VibraFlow `07` §E | il motore c'è già, manca la direzione |
| Staleness graduata | VibraFlow `07` §E2 | pesi dichiarati come ipotesi, non come costanti |
| GitHub `maintainer_assist` | VibraFlow `09` §132 | invariato, inclusa la regola "il permesso si misura" |
| Osservazione via hook | ECC `continuous-learning-v2` | tenuta la cattura, **buttata l'inferenza** |
| Graduazione a carrier | studio Pi (P1) + static-analysis.md | è la sintesi delle due |

## 9. Assunzioni vetoabili

Marcate come `agent_assumption` — se una è sbagliata, l'item che dipende da lei si riapre.

1. **`correctness_unknown` è uno stato del pin, non un campo su `RemediationItem`.** Assunto perché è
   il pin ad avere un ciclo di vita e a essere l'unità dell'interview. Se l'esito dovesse invece
   vivere per-item, cambia la forma di §0.3.
2. **I 4 moduli greenfield mislabeled sono `judgment`, non deterministici da riparare.** Generano
   artefatti da decisioni elette — è giudizio. L'alternativa (renderli davvero `D0` con un generatore
   templatico) sarebbe un lavoro molto più grande e probabilmente peggiore.
3. **Il rung `cross_derived` non è obbligatorio in nessuna severità, per ora.** Renderlo obbligatorio
   sopra una soglia raddoppia il costo dei pin ad alta severità; va deciso con un numero in mano.
4. **`maintainer_assist` è una skill nuova, non un'estensione di `code-review`.** Direzione opposta:
   `code-review` guarda un diff che il pacchetto ha prodotto, `maintainer_assist` guarda contenuto in
   arrivo da terzi. Fonderli farebbe entrare contenuto non fidato in un percorso che oggi è fidato.

---

## 10. Consuntivo — cosa è cambiato rispetto al piano

Sette commit su `sota-alignment`, tutti i blocchi chiusi. Le deviazioni sono marcate in loco;
qui restano le tre che hanno cambiato una *decisione*, non un dettaglio.

| Deviazione | Perché |
|---|---|
| `FAILURE_CLASSES` è un **superset** di `CHALLENGE_CLASSES`, non una lista accanto | una challenge *è* un modo di fallire dell'oracolo previsto prima del lavoro. Due vocabolari per un concetto è la divergenza che il pacchetto caccia — spedirla nel nostro schema sarebbe stata la versione dal portone d'ingresso |
| il gate agent-ready ha **cinque** rotte, non quattro | il piano introduceva uno strato di qualità di proprietà del `challenger` e non gli dava dove atterrare. `needs_challenge` chiude il buco invece di nasconderlo dentro `needs_research` |
| `maintainer-assist` gira su **`gh`**, non sull'MCP `github` | richiesta di Pietro a metà build, ed è giusta: `gh` è già autenticato, e soprattutto la superficie permessa diventa **nominabile** — i comandi di lettura, quelli di scrittura, e quelli rifiutati, uno per uno. Una capacità che puoi enumerare è una che puoi verificare |

### Difetti trovati mentre costruivo, non prima

Uno per blocco, e sono la parte che il piano non poteva contenere.

1. **`correctness_unknown` era un buco nero** (Blocco 0, trovato costruendo 1.1) — bloccava la
   chiusura senza comparire su nessuna superficie. Da lì la regola operativa applicata a ogni
   aggiunta successiva: *uno stato nuovo va cercato su tutte le superfici prima del commit.*
2. **Il gate delle ipotesi ha trovato il proprio bug** (Blocco 4) — `2 in {2.0}` è `True` in Python,
   quindi un'esenzione strutturale scritta come float esentava in silenzio **ogni** intero 2 del
   runtime, incluso un vero fan-out threshold. Il linter ha trovato 7 costanti non dichiarate solo
   dopo che il linter è stato aggiustato.
3. **4 moduli greenfield erano `type: deterministic` con `engine: agent:*`** (Blocco 0) — il gate
   esistente verificava che *un* engine fosse nominato, mai la coerenza fra tipo ed engine.

### Cosa resta aperto, di proposito

- **Il Blocco 5 non produce nulla finché non girano dei cicli.** È corretto: un osservatore
  costruito prima che esistano esiti osserva il vuoto. Il meccanismo c'è, i segnali arrivano dopo.
- **`cross_derived` non è obbligatorio a nessuna severità** (assunzione 3, invariata). Renderlo tale
  raddoppia il costo dei pin più cari e va eletto con un numero in mano.
- **Nessun auto-close in `maintainer-assist`.** Il permesso si guadagna con un tasso di falsi
  positivi misurato — e ora la macchina per misurarlo esiste (`generator_observe`), quindi
  l'obiezione è diventata una condizione verificabile invece che un rinvio.
- **Il gate delle ipotesi guarda solo il livello modulo.** Un default tarato in una firma di funzione
  non viene preso. È un buco reale, dichiarato nel docstring dello script: meglio di un gate che
  copre in silenzio meno di quanto il nome promette.

---

## 11. La potatura — perché il piano finisce con meno tool di quanti ne aggiunge

Obiezione di Pietro a lavoro finito: *"tutti questi tool mcp servono tutti?"*. La misura ha dato
ragione a lui: **8.761 token caricati in ogni sessione** solo per le descrizioni dei tool, pagati
anche quando nessuna skill si attiva.

> **La descrizione di un tool è affitto pagato a ogni sessione; il suo valore si incassa solo quando
> il tool viene chiamato.** La soglia per un tool non è "è utile", è "è utile abbastanza spesso da
> battere ~600 token di affitto permanente".

Il check che lo ha reso decidibile è quello che il repo già sa fare su sé stesso — *"twelve playbooks
invoke the runtime zero times"*, puntato sulla lista dei tool: **6 tool che nessun playbook, skill o
agente nominava**.

| Tolto | Dove è finito | Perché non doveva essere un tool |
|---|---|---|
| `ledger_set_governance` | automatico in `_open_or_create` | il server conosce la propria root e versione. Affittava 250 token per un bottone che nessuno premeva **e** faceva dipendere la completezza del trail dalla memoria di un agente. *Un fatto che la macchina può stabilire non è mai una domanda da porre a un modello.* |
| `docs_publication_gate` | un `mode` di `docs_claims` | stesso motore girato dall'altra parte: due tool = due descrizioni per un'idea |
| `premortem_gaps` | dentro `agent_ready` | quella lista `agent_ready` la calcolava già |
| `skill_integrity` | **cancellato**, con `verify_skills`/`pin_skills` | `build.py --check` copre i nostri byte al build; l'unico valore residuo è post-install e nessun host offre un posto economico dove girare. *Una funzione senza chiamante non è copertura, è decorazione che si legge come copertura.* Il motivo sta in `governance.py` perché nessuno la ricostruisca |

Più 19 descrizioni tagliate alla parte che serve a **decidere se chiamare** il tool. La regola:
la descrizione risponde a *quando lo chiamo e con cosa*; il *perché* vive nel playbook che lo nomina,
letto una volta.

**52 → 48 tool · 8.761 → 6.741 token/sessione (−23%) · zero tool non nominati da nessun playbook.**

La distinzione che rende la regola applicabile e che mi era sfuggita: i docstring dei moduli in
`src/runtime/*.py` **non entrano mai** nel contesto di un agente — li legge un umano nel codice, e lì
la prosa densa è giusta. I docstring in `src/mcp/server.py` **sono** le descrizioni inviate al
modello. Stessa scrittura, costo opposto.
