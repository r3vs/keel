# mattpocock/skills — cosa copiare in Keel, e come

> **TL;DR.** Quella repo risolve un problema che Keel non ha ancora affrontato: **come si scrive
> la prosa** che è il deliverable, e **come un umano trova la skill giusta** in un pacchetto che ne
> contiene sedici. Keel è nettamente più avanti su tutto ciò che è *stato* (ledger, evidenza,
> verifica, build multi-host, gate CI); mattpocock è più avanti su tutto ciò che è *superficie*
> (doctrine di scrittura, asse di invocazione, router, pagine per umani). I due assi non si
> sovrappongono quasi mai — ed è per questo che vale la pena prendere.
>
> **Le tre prese che valgono più di tutte le altre messe insieme:** ① la doctrine
> `writing-for-agents` (context pointer, i due carichi, gerarchia informativa, criteri di
> completamento, *leading words*, potatura) dentro `writing-skills`, che oggi in Keel parla solo
> di gate e non dice **una riga** su come si scrive; ② l'asse **user-invoked / model-invoked**, che
> Keel non nomina da nessuna parte e che oggi gli costa ~5,5 KB di `description` sempre in
> contesto; ③ un **router** (`ask-matt`), perché Keel ha 16 skill su 4 plugin e nessuna mappa.
>
> Tutto letto file per file dal clone (`mattpocock/skills`, MIT), non citato a memoria.

---

## 0. Stato di attuazione — aggiornato dopo l'implementazione

Questo studio è stato scritto come analisi, poi eseguito. Quanto segue è ciò che è **atterrato**,
perché un documento che continua a proporre ciò che è già fatto è esattamente la sedimentazione di
cui parla la §6 ①.

| Presa | Stato | Dove |
|---|---|---|
| ① `writing-for-agents` | **fatto** | `src/core/writing-for-agents.md`; `writing-skills` e `documentation-lifecycle` lo puntano |
| ② asse di invocazione | **fatto** | frontmatter autorale; `build.py` deriva il sidecar Codex; `tests/test_invocation_axis.py` |
| ③ router | **fatto** | `src/skills/which-skill/` (in `keel-core`), con `tests/test_router_completeness.py` |
| ④ pagine per umani | **non fatto** | vedi la nota qui sotto |
| ⑤ Fase 1 di debugging | **fatto** | `src/skills/systematic-debugging/SKILL.md`, riscritta attorno al loop rosso |
| ⑥ fog of war | **fatto** (secondo giro) | ledger **v0.31** — collezione `fog` top-level, forma 1 eletta; `docs/open-gaps.md` §30 CHIUSA |
| ⑦ reclamo sulla frontiera | **fatto** (secondo giro) | ledger **v0.30** — `claimed_by`/`claimed_at`, frontiera, TTL; `docs/open-gaps.md` §29 CHIUSA |
| ⑧ vocabolario dei moduli profondi | **fatto** | `src/core/module-design.md` |
| ⑨ le prese piccole | **tutte fatte** | l'ultima, `wizard`, è `src/skills/wizard/` |

**Due correzioni a ciò che questo studio affermava**, entrambe scoperte verificando invece di
ricordare:

- **Sull'asse di invocazione, l'argomento dei token era il più debole dei due.** Il costo di ~5,5 KB
  è reale, ma quasi tutte queste skill *devono* restare model-invoked: è il design. Ciò che l'asse
  compra davvero è che la scelta smetta di essere un'omissione — e ha due costi che lo studio non
  conosceva perché non li aveva verificati: una skill user-invoked **non è raggiungibile da un'altra
  skill**, e su Claude Code **non viene precaricata in un subagent**, cosa che qui conta perché il
  roster ne ha sei. In pratica una sola skill lo merita: il router.
- **Il meccanismo è più economico del previsto.** Lo studio, seguendo mattpocock, lo trattava come un
  fatto Claude+Codex. **Pi legge la stessa chiave di Claude Code** — `dist/core/skills.js` la parsa e
  `formatSkillsForPrompt` filtra via quelle skill dal prompt — quindi una riga autorale serve due
  host, il build ne genera uno, e opencode è un residuo dichiarato (la sua unica porta è il tool
  `skill` del modello, quindi negare il permesso toglie la skill anche all'umano: è disattivazione,
  non user-invocation).
- **Una presa della §6 ⑨ era un buco inventato.** *"Riferisci per nome, mai per id"* è già vero qui:
  `map.py` rende `p.title` sulle card e nell'intestazione del pin. Verificato, non corretto.

**Secondo giro (2026-08-11): ⑥ ⑦ ⑨ sono stati chiusi.** Lo studio li aveva lasciati specificati
perché entrambi cambiano cosa *significa* il ledger, e questa repo lo decide in intervista. Sono
stati poi eseguiti su richiesta esplicita, e costruirli ha corretto tre cose che la specifica non
sapeva: il compare-and-set del reclamo deve confrontare **il file** e non la copia in memoria (un
controllo sulla copia risponde *l'ho preso io?*, che è vero di nessun altro); il registro della
nebbia aveva bisogno di **due** uscite e non di una (senza `clear_fog` l'unica via d'uscita è
diventare un pin, che è la trappola del backlog che entra dalla porta marcata *graduazione*); e
aggiungere una collezione al ledger rende non-conforme per sempre ogni file scritto prima —
`OPTIONAL_COLLECTIONS` è la distinzione che serviva. Il dettaglio sta nelle due sezioni chiuse di
`docs/open-gaps.md`.

**Perché ④ non è stato fatto**, dichiarato invece che taciuto: la regola che rende quelle pagine
valide è che `Common questions` sia **cacciata, non inventata**, e che il conteggio resti onesto
rispetto all'evidenza. Questo pacchetto non ha ancora campo — nessun issue tracker con domande
ricorrenti, nessun wiki d'audience. Scrivere diciotto pagine di domande plausibili sarebbe
esattamente il padding che quella regola vieta. La fonte onesta esiste ed è `docs/open-gaps.md`
(diciotto round di ciò che è andato storto), ma trasformarla in pagine è un lavoro a sé, non un
sottoprodotto di questo.

---

## 1. Metodo

Clone completo, lettura integrale di: i tre file di ingresso (`README.md`, `CLAUDE.md`/`AGENTS.md`
— identici a parte l'import, `CONTEXT.md`), tutte le `SKILL.md` di `skills/engineering/` e
`skills/productivity/`, i file di riferimento allegati (`tests.md`, `mocking.md`,
`DESIGN-IT-TWICE.md`, `PHASE-BOUNDARIES.md`, `SKILL-MECHANICS.md`, `AGENT-BRIEF.md`), l'intera
`.agents/` (i due ADR, `invocation.md`, `writing-docs.md`), `docs/engineering/wayfinder.md`, gli
script, i due manifest di plugin e la CI.

Numeri di questa repo misurati durante la sessione, non ricordati: 16 `SKILL.md` sotto `src/skills/`,
~5,5 KB complessivi di `description` in frontmatter (≈1,4k token), 15 delle quali spedite.

---

## 2. Che cos'è quella repo, in una pagina

Non è un framework: è un **set di skill piccole, componibili, dichiaratamente hackerabili**
("Approaches like GSD, BMAD, and Spec-Kit try to help by owning the process. But while doing so,
they take away your control"). Nessuno step di build: `skills/` è insieme sorgente e output, e uno
script di symlink (`scripts/link-skills.sh`) le collega in `~/.claude/skills` e `~/.agents/skills`.

Cinque scelte strutturali che decidono tutto il resto:

| Scelta | Come è espressa | Cosa compra |
|---|---|---|
| **Bucket di promozione** | `engineering/` `productivity/` promossi; `misc/` `in-progress/` `deprecated/` no | ciò che spedisce è un sottoinsieme dichiarato, non tutto ciò che esiste |
| **Asse di invocazione** | `disable-model-invocation: true` (Claude) + `policy.allow_implicit_invocation: false` (Codex, in `agents/openai.yaml`) | ogni skill paga *o* carico di contesto *o* carico cognitivo, mai entrambi per sbaglio |
| **Router** | `ask-matt` — user-invoked, mappa i flussi | l'umano ricorda **una** skill invece di venticinque |
| **Pagine per umani** | `docs/<bucket>/<skill>.md`, quattro sezioni obbligate | l'onboarding non passa dal `SKILL.md` |
| **Dipendenze come prosa** | "Run the `/grilling` skill", mai `../altra-skill/FILE.md` | nessuna skill dipende dal layout di un'altra |

E una regola che Keel riconoscerà: **le dipendenze fra skill non sono link, sono invocazioni**.
`invocation.md` la enuncia esplicitamente — "shared reference docs live inside the skill that owns
them; other skills reach that material by invoking the skill, not by linking across folders". È la
stessa tensione che Keel risolve con `build.py` che vendorizza `src/core/` dentro ogni skill: due
risposte diverse allo stesso problema (l'unità di distribuzione è la cartella skill). La risposta di
Keel è più forte perché sopravvive alla copia della cartella fuori dalla repo; quella di mattpocock
è più leggera perché non ha un build. **Non regredire su questo.**

---

## 3. Wayfinder, smontato

È la skill più densa della repo e quella su cui hai chiesto esplicitamente. Il problema che risolve:
**un lavoro troppo grande per una sessione di agente**, con la strada verso la destinazione ancora
nella nebbia.

### Il meccanismo

- **La mappa** è *una* issue sul tracker, etichettata `wayfinder:map`. I ticket sono sue issue
  figlie. La mappa è un **indice, non uno store**: una decisione vive in esattamente un posto — il
  suo ticket — e la mappa la riassume in una riga e linka. Una sessione carica la mappa a bassa
  risoluzione e fa *zoom* sui singoli ticket a richiesta.
- **Quattro sezioni** sul corpo della mappa: `Destination` (cosa vuol dire arrivare — si nomina
  **prima** di qualsiasi ticket, perché fissa lo scope), `Notes`, `Decisions so far` (una riga per
  ticket chiuso + link), `Not yet specified` (la nebbia), `Out of scope`.
- **Il ticket** è una domanda, dimensionata su una sessione da ~100K token, con una label
  `wayfinder:<type>`.
- **La frontiera** = ticket aperti ∧ sbloccati ∧ non reclamati. Il bloccaggio usa la relazione
  **nativa** del tracker, non una convenzione testuale — perché così la frontiera si **disegna da
  sola nella UI del tracker** e l'umano vede cosa è prendibile senza aprire la mappa.
- **Il reclamo** è l'assegnatario: una sessione si assegna il ticket **prima** di qualsiasi lavoro,
  così le sessioni concorrenti lo saltano. Un ticket aperto e non assegnato è non reclamato.
- **Mai più di un ticket per sessione** (unica eccezione: i `research`).

### I quattro tipi di ticket, e l'asse che li taglia

Ogni ticket è **HITL** (worked *con* un umano che parla per sé) o **AFK** (guidato dall'agente da
solo). La riga che vale: *"un agente di grilling che risponde alle proprie domande ha rotto il
contratto HITL"*.

| Tipo | Modo | Quando | Risolto da |
|---|---|---|---|
| `grilling` | HITL | il caso di default: si risolve parlandone | `/grilling` + `/domain-modeling` |
| `prototype` | HITL | "come dovrebbe apparire / comportarsi" — una domanda che il parlare non chiude | `/prototype`, artefatto linkato come asset |
| `research` | AFK | serve un fatto fuori dalla working directory | subagent `/research`, su ramo `research/<name>` |
| `task` | entrambi | niente da decidere, ma un lavoro manuale blocca una decisione | l'agente da solo, o una checklist precisa per l'umano |

`task` è **l'unico tipo che *fa* invece di decidere**, e si guadagna il posto sbloccando una
decisione — mai consegnando un pezzo della destinazione.

### Le tre idee da rubare (indipendenti dal tracker)

1. **Fog of war.** La mappa è *deliberatamente* incompleta: non si carta ciò che non si vede ancora.
   Il test è affilato e verificabile: **si può enunciare la domanda con precisione *ora*?** — non se
   la si può *rispondere* ora. Sì → ticket, anche se bloccato. No → resta nebbia, in `Not yet
   specified`, scritta grossolanamente. Risolvere un ticket dirada la nebbia davanti a sé e
   **gradua** ciò che è diventato specificabile in ticket nuovi — cancellandolo dalla nebbia, così
   vive in un posto solo.
2. **Out of scope ≠ nebbia.** La nebbia si addensa solo *verso* la destinazione. Ciò che sta oltre
   non è nebbia, è fuori scope: sezione propria, **non gradua mai**, e se un ticket già esistente si
   rivela oltre la destinazione **lo si chiude** (un ticket chiuso è inequivocabilmente fuori dalla
   frontiera) lasciando una riga nella sezione. Fuori scope non entra in `Decisions so far`, che
   registra la rotta effettivamente percorsa — un confine di scope non è un passo su di essa.
3. **Riferisci per nome, mai per id.** "Un muro di `#42, #43, #44` è illeggibile; i nomi si leggono
   a colpo d'occhio." L'id non sparisce — cavalca *dentro* il nome, come link.

### Onestà: la pagina docs elenca i modi in cui fallisce

È la cosa più notevole di tutta la repo, e va imitata *come genere*. `docs/engineering/wayfinder.md`
contiene, sotto `## Common questions`, i fallimenti reali riportati sul campo:

- *"Il mio agente si è messo a scrivere codice di produzione."* Segnalato come **il fallimento più
  riportato**, con la falla nominata: il default "plan, don't do" è sovrascrivibile nelle `Notes`
  **scritte dall'agente** — vincolo ed eccezione vivono nello stesso file di cui il vincolato è
  proprietario. Un utente ha visto un agente scriversi da solo la licenza e rileggersela nelle
  sessioni successive.
- *"Ho cartato 27 ticket e al tredicesimo il resto non aveva più senso."* Verbatim da un field
  report. La risposta non nega il problema: scope la mappa su un epic delimitato, e
  **"prototypemaxxing", non "planmaxxing"**.
- *"Il grilling è estenuante, ogni domanda è tre paragrafi."* — *"la lamentela più viva su
  wayfinder, e non è risolta."*
- *"Posso lavorare più ticket in parallelo?"* La frontiera è costruita per mostrarti cosa è
  prendibile, ma in pratica uno-alla-volta è più sicuro: due sessioni di grilling in parallelo non
  condividono contesto e ti richiedono la stessa cosa due volte.

Confronta con `docs/open-gaps.md` di Keel: stessa disciplina (registro permanente di ciò che è rotto
e non chiuso), **ma rivolto al manutentore**. Quella di mattpocock è rivolta all'utente, ed è quella
che Keel non ha.

---

## 4. Le skill di engineering, una per una

Compattate a ciò che è trasferibile. Le annotazioni `→` dicono dove atterra in Keel.

**`grilling`** — la primitiva. Intervista a **round** su un *design tree*; la **frontiera** è ogni
decisione i cui prerequisiti sono già risolti. Si chiede tutta la frontiera in un round, numerata,
**ciascuna con la propria risposta raccomandata**; poi si aspetta. La regola che conta: *"trovare i
**fatti** è il tuo lavoro, mai quello dell'utente"* — se una domanda di frontiera richiede un fatto
dall'ambiente si spedisce un subagent, senza bloccare: solo le domande a valle di quella
esplorazione aspettano. **Le decisioni sono dell'utente.** → `src/core/interview-funnel.md` copre
già la compressione (pin → cluster → policy) che qui manca del tutto; ciò che manca a Keel è il
*round-based frontier* e la regola fatti/decisioni enunciata così nettamente.

**`tdd`** — buon test = attraverso interfacce pubbliche; **seam** = il confine su cui si testa;
**"nessun test è scritto su un seam non confermato"** (i seam si concordano *prima*, con l'utente).
Tre anti-pattern nominati: *implementation-coupled*, **tautological** (il valore atteso ricalcolato
come lo calcola il codice — "passa per costruzione e non può mai dissentire dal codice"),
*horizontal slicing*. E: *"il refactoring non fa parte del loop, appartiene alla review"*. → Il TDD
di Keel è più forte sul legame (il red step **è** un pin `acceptance_criterion`); più debole sul
**tautological test** e sul **seam pre-concordato**, che non nomina.

**`diagnosing-bugs`** — vedi §6, presa n. 5. È il pezzo di prosa tecnicamente migliore della repo.

**`code-review`** — due assi **paralleli e non fusi**: *Standards* (il repo documenta? più una
**baseline di 12 smell di Fowler** che si applica anche se il repo non documenta nulla) e *Spec* (il
diff implementa fedelmente la issue d'origine?). Due sub-agent separati "so they don't pollute each
other's context", poi aggregazione **senza rerank**: *"non scegliere un vincitore fra i due assi — è
esattamente il rerank che la separazione esiste per impedire"*. Due regole sulla baseline: **il repo
sovrascrive**, e ogni smell è **sempre un giudizio** ("possible Feature Envy"), mai una violazione
dura. → Keel ha precedenza a primo-match e un reviewer read-only (più forte); non ha né la
separazione a due assi né una baseline di fallback.

**`codebase-design`** — glossario di **moduli profondi**: *module, interface, implementation,
depth, seam, adapter, leverage, locality*, con gli *"avoid"* accanto a ciascuno ("non dire
*boundary*: è sovraccarico col bounded context del DDD"). Tre principi che sono test, non slogan:
il **deletion test** (cancella il modulo: la complessità sparisce, o riappare su N chiamanti?),
*"l'interfaccia è la superficie di test"*, **"un adapter è un seam ipotetico, due adapter sono un
seam reale"**. E una sezione **Rejected framings** che rifiuta esplicitamente la definizione di
profondità di Ousterhout ("premia il gonfiare l'implementazione"). → Keel **non ha** un vocabolario
di design condiviso: `module-design-alignment.md` di rescue riguarda i *design token* DTCG, non i
moduli. Buco reale.

**`to-tickets`** — slice verticali *tracer bullet*, ciascuna con i propri archi di bloccaggio; e
soprattutto l'eccezione: **i refactor larghi non si affettano verticalmente**. Un cambio meccanico
il cui *blast radius* investe tutta la codebase va sequenziato **expand–contract** — aggiungi la
forma nuova accanto alla vecchia, migra i call site a lotti dimensionati sul blast radius (un ticket
per lotto, CI verde lotto per lotto perché la forma vecchia esiste ancora), poi cancella. → Il
`buildloop.py` di Keel schedula onde su un DAG: il caso "nessuna slice può atterrare verde" è
esattamente quello che un DAG scheduler gestisce male. Presa piccola e affilata.

**`to-spec`** — *non intervista*: sintetizza ciò che è già stato discusso. Template a sei sezioni,
e una regola sui prototipi: *"se un prototipo ha prodotto uno snippet che codifica una decisione più
precisamente della prosa (macchina a stati, reducer, schema, forma di tipo), inlinialo"*.

**`prototype`** — codice usa-e-getta che risponde a **una** domanda; la domanda decide la forma
(logica → un file HTML condivisibile; UI → più varianti radicalmente diverse su una rotta). Sei
regole, di cui la migliore è la sesta: *usa-e-getta è un vincolo su **come si scrive**, non una
promessa di distruggerlo* — la decisione validata rientra nel codice reale, e **il prototipo si
conserva come fonte primaria** su un ramo fuori da main, puntato dalla issue.

**`triage`** — macchina a stati a due ruoli (categoria + stato), con una KB `.out-of-scope/` delle
richieste **rifiutate**, così la stessa richiesta non si ri-litiga. E due controlli obbligatori
prima di qualsiasi cosa: **ridondanza** (esiste già? cercata per concetto di dominio, non per le
parole della richiesta) e **rifiuto precedente**.

**`resolving-merge-conflicts`**, **`wizard`** (genera uno script bash interattivo per i passi che
**solo un umano** può fare: provisioning, credenziali, dashboard di terzi), **`handoff`**,
**`research`**, **`domain-modeling`**, **`improve-codebase-architecture`** — vedi §6 e §7.

---

## 5. Il confronto onesto

### Dove Keel è già avanti (non toccare)

| Dimensione | Keel | mattpocock |
|---|---|---|
| **Stato condiviso** | ledger tipizzato, v0.29, unione discriminata su `kind`, eventi append-only | issue sul tracker + `CONTEXT.md`, prosa |
| **Evidenza** | `rung="observed"`, `correctness_unknown`, tre assi di fiducia, `measurer` indipendente | "watch it fail / watch it pass", in prosa |
| **Multi-host** | build che deriva 4 forme di manifest da una sorgente | plugin Claude; Codex **deferito** (ADR 0002) |
| **Gate** | 9 gate in CI, inclusi `verify_commands` (risolve *dopo* l'install) e `check_tool_carriers` | `claude plugin validate --strict`, manuale |
| **Anti-drift** | `build.py --check`, linter di consistenza, `check_stated_facts.py` | convenzioni in `CLAUDE.md`, nessun gate |
| **Runtime** | ~32 moduli Python, tree-sitter, SARIF/OSV, grafo, mappa | nessuno (uno script bash generato dal `wizard`) |

Nota non banale: **l'ADR 0002 di mattpocock documenta una sconfitta che Keel ha già vinto.** Il
manifest Codex accetta `skills` solo come *singola stringa di path*, e Codex **droppa i symlink**
quando copia il plugin nella cache — quindi una directory piatta di symlink arriva vuota. Keel
genera cartelle reali per plugin, quindi il problema non si pone. Se mai qualcuno proponesse di
"semplificare" Keel togliendo il build: questo ADR è la controprova già scritta.

### Dove Keel ha un buco

| Buco | Verifica | Costo oggi |
|---|---|---|
| Nessuna doctrine di **scrittura** | `writing-skills` = 43 righe, tutte su gate e invarianti; zero righe su come si scrive la prosa | il deliverable della repo è prosa, e non c'è una regola su come si scrive |
| L'asse **user/model-invoked** non esiste | `grep -rn "disable-model-invocation\|user-invoked" src/ docs/` → **0 hit** | ~5,5 KB di `description` sempre in contesto, per 15 skill, ogni turno |
| Nessun **router** | nessuna skill indicizza le altre; `AGENTS.md` le elenca ma non dà un flusso | 16 skill e nessuna mappa; l'umano è l'indice, senza aiuto |
| Nessuna **pagina per umani** | `docs/` = `design/`, `studies/`, `open-gaps.md`, `packaging.md` — tutto per il manutentore | chi installa Keel non ha una pagina che gli dica quando raggiungere quale skill |
| Nessun registro della **nebbia** | il ledger ha `deferred` (fuori scope *ora*) ma nessun posto per "in scope, non ancora enunciabile" | una decisione non ancora formulabile o diventa un pin prematuro o svanisce |
| Nessun **reclamo** su un pin | `depends_on`/`conflicts_with` + worktree coprono i *file*, non l'*item* | due sessioni possono prendere lo stesso pin |
| Nessun **vocabolario di design** | `codebase-design` non ha equivalente | `improve-codebase-architecture` non ha su cosa poggiare |
| Nessuna **redazione dei segreti** | `grep -rn "redact" src/core src/skills/*/SKILL.md` → 0 hit sul debugging | un loop di debug che mostra output mostra anche le credenziali |
| Nessun **prototipo** come artefatto | nessuna skill copre "codice usa-e-getta che risponde a una domanda" | un `open_decision` su "come si comporta" non ha modo di salire di rung |
| Nessun **wizard umano** | `assumptions.md` copre le assunzioni *dell'agente*, non i passi *solo umani* | il passo che l'agente non può fare non ha forma |

---

## 6. Le prese, in ordine di valore

Ognuna: **cos'è**, **perché per Keel**, **dove atterra**, **la trappola**.

### ① `writing-for-agents` → un nuovo `src/core/writing-for-agents.md`

**Cos'è.** La skill meglio scritta della repo, e l'unica che non riguarda il codice ma **la prosa
che gli agenti consumano**. Sette leve, ciascuna con un test:

- **Context pointer** — un riferimento in contesto che nomina materiale fuori contesto e codifica
  la condizione per raggiungerlo. La `description` di una skill *è* un context pointer; una riga di
  `AGENTS.md` che nomina un doc è lo **stesso oggetto**. È **il wording del pointer, non il suo
  target**, a decidere quando l'agente raggiunge il materiale: *"un target indispensabile dietro un
  pointer formulato debolmente è un bug di varianza — affila prima il wording, e inlinia il
  materiale solo se affilare fallisce."*
- **I due carichi.** **Context load** (materiale sempre caricato: costa token e attenzione ogni
  turno, sparando o no) e **cognitive load** (costa all'umano: sapere quali documenti esistono e
  quando raggiungerli). E la riga che li salva dall'essere una banalità: *"il carico cognitivo non
  è un costo da minimizzare — è il prezzo dell'agency umana; spendilo dove serve il giudizio
  umano, toglilo dove non serve."*
- **Gerarchia informativa** — tre pioli (step in-file → reference in-file → reference *disclosed*
  dietro pointer) e il test più utile: **il branching**. Inlinia ciò che ogni branch usa, spingi
  dietro un pointer ciò che solo alcuni raggiungono. Più **co-locazione** (cosa sta *accanto* a
  cosa, una volta deciso *quanto in basso*) e **sprawl** come modo di fallire (un documento
  semplicemente troppo lungo, anche se ogni riga è viva).
- **Criteri di completamento**, con due proprietà che sono leve distinte: **chiarezza** (l'agente
  distingue fatto da non-fatto? un bound vago invita alla **premature completion**) e **domanda**
  ("ogni modello modificato è reso conto" forza lavoro dove "produci una lista di modifiche" no).
  La difesa è ordinata: **affila prima il bound**; nascondi gli step successivi solo se è
  irriducibilmente sfumato *e* osservi la fretta — e nascondere funziona solo attraverso un
  **vero confine di contesto** (un handoff, un subagent), non una chiamata inline.
- **Leading words** — una parola compatta già presente nel pretraining, ripetuta **come token, mai
  come frase**, che ancora un'intera regione di comportamento. `tight` per "veloce, deterministico,
  a basso overhead". `red` per "un loop di cui ti fidi" — *"un gate sfumato diventa uno stato
  binario osservabile"*. Coniarne di proprie funziona se le definisci, ma **una parola inventata non
  recluta prior**: paghi in token di definizione ciò che una parola del pretraining ti dà gratis.
- **La negazione come modo di fallire** — governare per divieto trascina il comportamento vietato
  *dentro* il contesto e lo rende **più** disponibile: *"non pensare a un elefante"*. Enuncia il
  positivo.
- **Potatura** — singola fonte di verità; **l'ambiente è una fonte di verità** e un documento che
  lo ristata è una *cache* (giustificata solo quando il lookup è costoso: la convenzione non
  scritta, il perché di una scelta, il gotcha che nessun config confessa); rilevanza; **no-op**
  (un'istruzione che il modello già obbedisce di default paga carico per non dire nulla, e il test
  è *relativo al modello*, non al lettore — due persone che discutono se una riga è un no-op stanno
  discutendo del default, e lo risolvono **eseguendo il documento**, non dibattendo); **sediment**
  (strati stantii che si depositano perché aggiungere sembra sicuro e togliere rischioso).

**Perché per Keel.** Keel *pratica* già metà di questa doctrine senza nominarla: la regione a
budget di byte in `instruction-files.md` (Codex tronca a byte, Claude perde aderenza oltre ~200
righe) **è** l'argomento del context load; la regola "solo le dipendenze load-bearing sono pointer
backtickati, così la chiusura resta minima" **è** progressive disclosure; `check_stated_facts.py` è
potatura automatizzata. Ciò che manca è il **vocabolario** — e in una repo dove il deliverable è
prosa, non avere un vocabolario per giudicare la prosa significa che ogni revisione riparte dai
gusti.

**Dove atterra.** `src/core/writing-for-agents.md` (core condiviso, vendorizzato solo nelle skill
che lo eseguono davvero — cioè `writing-skills`), e `src/skills/writing-skills/SKILL.md` che lo
punta. Attenzione alla regola di Keel: un pointer backtickato in un doc core trascina l'intera
chiusura dentro ogni skill che lo vendorizza.

**La trappola.** Keel ha già una posizione su cosa fa quando la prosa altrui è buona: *"superpowers
è MIT: dove la sua prosa è buona, adattala **con attribuzione**, invece di far finta di non averla
letta."* Vale identicamente qui — mattpocock/skills è MIT. Adatta e attribuisci; non vendorizzare
verbatim senza dirlo.

### ② L'asse user-invoked / model-invoked

**Cos'è.** Ogni skill è raggiungibile *solo dall'umano che ne digita il nome*
(`disable-model-invocation: true` + `policy.allow_implicit_invocation: false` in
`agents/openai.yaml`) **oppure** dal modello. Il test: *"il modello potrebbe utilmente raggiungerla
autonomamente?"* — e la nota che chiude la porta all'errore comune: *"il riuso è la ragione per
estrarre una skill, non il test per renderla model-invoked."* Due regole di composizione: una skill
user-invoked può invocarne una model-invoked, **mai** un'altra user-invoked (non ha description, non
c'è niente che possa raggiungerla); e il reference condiviso fra due user-invoked non può vivere in
nessuna delle due — va in un file esterno.

**Perché per Keel.** Oggi Keel spedisce 15 skill tutte model-invoked: ~5,5 KB di description sempre
caricate. Ma non è (solo) un argomento di token — è un argomento di **precisione di trigger**, che
Keel già riconosce: *"una skill si auto-attiva dalla sua `description`, ed è per questo che
`codebase-rescue` / `greenfield-forge` restano quei nomi."* Quindi la presa è **selettiva, non
all'ingrosso**: quelle due devono restare model-invoked. I candidati veri sono le skill che solo un
umano avvia — e Keel ha già l'inizio di una risposta in `src/commands/` (`rescue.md`, `forge.md`),
che è una superficie user-invoked non nominata come tale.

**Dove atterra.** Una colonna nella tabella-roster o un campo in `modules.json` che `build.py`
proietta nelle due forme per host — esattamente il pattern che Keel già usa per `disallowedTools` /
`permission: {edit: …}`. **Non** mantenerlo a mano in due posti: `writing-skills` di Keel già dice
che un linter di parità è un odore che due cose dovrebbero esserne una, generata.

**La trappola.** `disable-model-invocation` non è portabile — Codex droppa tutto il frontmatter
oltre `name` + `description` (è già un fatto verificato in `CLAUDE.md` di Keel). Il file
`agents/openai.yaml` accanto alla `SKILL.md` è la risposta di mattpocock; per Keel deve essere
**generato**, non scritto.

### ③ Un router — `ask-matt` → una skill mappa per Keel

**Cos'è.** Una skill user-invoked che nomina tutte le altre e quando raggiungere ciascuna. Non è un
elenco: è una **topologia** — un *main flow* (`grill-with-docs → [prototype] → to-spec → to-tickets
→ implement → tdd → code-review`), delle *on-ramp* che ci si immettono (triage,
diagnosing-bugs, wayfinder), un livello *vocabolario* che gira sotto (domain-modeling,
codebase-design), e gli *standalone*. Con, a ogni nodo, la **clausola-perché** che lo distingue dal
fratello confondibile ("dove `grill-with-docs` affila un'idea che sta in una sessione, wayfinder è
per l'idea che non ci sta").

**Perché per Keel.** Keel ha 16 skill su 4 plugin, due skill-metodologia enormi, un runtime da 32
moduli e un ledger da 179 KB di spec. `AGENTS.md` le elenca — ma un elenco non dice *quale adesso*.
E la regola in `SKILL-MECHANICS.md` chiude il cerchio con la presa ②: *"quando le skill user-invoked
si moltiplicano oltre ciò che riesci a ricordare, quel carico cognitivo accumulato si cura con un
router"*. Le due prese si tengono per mano: senza asse di invocazione il router è un lusso, con
l'asse è **necessario**.

**Dove atterra.** `src/skills/<router>/SKILL.md`, user-invoked, più un comando in `src/commands/`.
E — nello stile di Keel — un gate: `CLAUDE.md` di mattpocock dice *"una nuova skill che il router
non menziona, o una stantia verso cui ancora instrada, è un router che mente"*. Quello è un
`check_*.py`, non una nota.

### ④ Le pagine per umani, con `Common questions` e `It's working if`

**Cos'è.** Una pagina per skill promossa, quattro sezioni che la rendono degna di lettura: *What it
does* (che si apre col **vincolo definente** — l'unico fatto che fa comportare questa skill
diversamente dal default ovvio — scritto come frase dichiarativa piana, **mai** come apposizione
etichettata tipo "Il vincolo chiave:"), *When to reach for it* (modo di invocazione + confine di
trigger), *Common questions*, *It's working if*.

Due regole valgono da sole tutta la presa:

- **`Common questions` va *cacciata*, non inventata.** Fonti nominate: il wiki dell'audience, le
  issue della repo (*"una domanda posta due volte è una domanda a cui la pagina deve una
  risposta"*), il changelog (ogni rinomina genera un "dove è finito?"). E il conteggio **resta
  onesto rispetto all'evidenza**: *"una skill ben discussa se ne guadagna sei; una oscura una o
  due, o nessuna. Imbottire una skill magra per pareggiare una ricca è come la sezione si riempie
  di domande che nessuno ha."*
- **`It's working if` deve essere verificabile senza aprire `SKILL.md`.** Il test è esplicito:
  *"«il documento si accorcia man mano che migliora» passa; «la sezione libreria è identica byte a
  byte a `template.sh`» è un controllo di conformità sugli interni della skill travestito da questa
  sezione."*

**Perché per Keel.** Queste due regole *sono* la doctrine di Keel applicata alla documentazione. Il
conteggio-onesto-rispetto-all'evidenza è `check_stated_facts.py` in prosa. Il verificabile-senza-
aprire-il-sorgente è `rung="observed"` applicato a una pagina. Keel dovrebbe riconoscerle come
proprie.

**Dove atterra.** `docs/skills/<nome>.md`, più una nota in `CLAUDE.md` che le lega al ciclo di vita
della skill. E, se vuoi il livello Keel: un gate che verifica che ogni skill spedita abbia una
pagina e che ogni pagina punti a una skill che esiste — la stessa forma di `verify_pointers.py`.

**La trappola.** Non far diventare la pagina un secondo `SKILL.md`. La regola di mattpocock è
netta: *"spiega il perché, non il processo; non riproduce mai gli step — un umano che sceglie uno
strumento non ha bisogno del runbook."* In Keel, dove la `SKILL.md` è già la specifica, una pagina
che la ripete sarebbe esattamente il **gemello che dimentica** che la doctrine vieta.

### ⑤ La Fase 1 di `diagnosing-bugs` dentro `systematic-debugging`

**Cos'è.** *"Questa **è** la skill. Tutto il resto è meccanico."* Se hai un segnale pass/fail
stretto che va **rosso su *questo* bug**, troverai la causa; bisezione, test d'ipotesi e
strumentazione lo consumano soltanto. Se non ce l'hai, nessuna quantità di fissare il codice ti
salverà. Poi:

- **Dieci modi di costruirne uno, in ordine** — test fallente al seam giusto, script curl, invocazione
  CLI con fixture diffata contro uno snapshot buono, browser headless, **replay di una traccia
  catturata**, harness usa-e-getta, loop property/fuzz, harness di bisezione per `git bisect run`,
  loop differenziale (vecchia vs nuova versione, stesso input, diff dell'output), e — ultima
  risorsa — uno script bash **HITL** che guida l'umano così che il loop resti strutturato.
- **"Tratta il loop come un prodotto"**: più veloce, segnale più affilato, più deterministico.
  *"Un loop flaky da 30 secondi è appena meglio di nessun loop; uno deterministico da 2 secondi è
  un superpotere."*
- **Bug non deterministici**: l'obiettivo non è un repro pulito ma un **tasso di riproduzione più
  alto**. *"Un bug che flaka al 50% è debuggabile; all'1% no."*
- **Un criterio di completamento vero e proprio**, a checkbox — *red-capable, deterministic, fast,
  agent-runnable* — che richiede di **nominare un comando già eseguito almeno una volta**, mostrando
  invocazione e output. E il gate: *"se ti sorprendi a leggere codice per costruire una teoria prima
  che questo comando esista, **fermati**."*
- **La sezione `Redact`**, in cima: questa skill ti fa mostrare comandi, output e artefatti
  catturati — **redigi prima ogni segreto**, costruisci i loop su variabili d'ambiente così la
  credenziale resti nell'ambiente, e negli artefatti catturati (che portano header di auth) cita
  solo le righe che portano il segnale.
- **Fase 4**: ogni log di debug taggato con un prefisso unico (`[DEBUG-a4f2]`), così la pulizia
  finale è un solo grep. *"I log non taggati sopravvivono; quelli taggati muoiono."*
- **Fase 5**: scrivi il test di regressione prima del fix — **ma solo se esiste un seam corretto**.
  *"Se non esiste un seam corretto, quello **è** il finding."*

**Perché per Keel.** Lo step 1 di `systematic-debugging` è una riga ("Reproduce it
deterministically"). Ma il pin `defect` di Keel non può chiudersi senza `rung="observed"` — e
**quel comando è ciò che produce l'osservazione**. Questa prosa non è un'aggiunta stilistica: è
l'unica cosa che rende ottenibile un gate che Keel già impone. E "nessun seam corretto → quello è il
finding" atterra esattamente su un pin `design_concern`.

**Dove atterra.** `src/skills/systematic-debugging/SKILL.md`, espandendo lo step 1 e aggiungendo la
sezione di redazione. `tight` e `red` come leading word (presa ①).

### ⑥ Fog of war → un registro per l'in-scope-non-ancora-enunciabile

**Cos'è.** Vedi §3. Il test è: *puoi enunciare la domanda con precisione **ora**?*

**Perché per Keel.** Il funnel di intervista di Keel comprime pin in decisioni, ma presuppone che i
pin esistano. Una decisione che *sai che arriverà* ma non sai ancora formulare oggi non ha casa: o
diventa un pin prematuro (un fork mal formulato che l'utente deve comunque risolvere — e Keel sa già
che l'open chat "raccontami della tua app" è il modo esatto in cui nasce lo slop) o svanisce. Il
`deferred` di Keel è "fuori scope **ora**" — un'altra cosa.

**Dove atterra.** Non è una presa a costo zero: la spec del ledger è a v0.29 e 179 KB. Le opzioni,
in ordine di costo: una collezione top-level `fog[]` (voci grossolane, non pin, con la regola di
graduazione che le cancella quando diventano pin — *vive in un posto solo*, che è la doctrine di
Keel); oppure uno stato `unspecifiable`; oppure una sezione della mappa renderizzata da `map.py`.
**Trattala come una domanda di design da portare all'intervista, non come una decisione già presa.**

**La trappola.** La regola che rende utile la nebbia è la **graduazione con cancellazione**: quando
una patch di nebbia diventa ticket, sparisce dalla nebbia. Senza quella metà, hai solo un secondo
posto dove la stessa cosa vive — cioè la divergenza che questo pacchetto esiste per trovare.

### ⑦ La frontiera come protocollo di reclamo

**Cos'è.** Frontiera = aperto ∧ sbloccato ∧ **non reclamato**; il reclamo è l'assegnatario, preso
**prima** di qualsiasi lavoro. E il bloccaggio **nativo** perché *renderizza la frontiera nella UI
del tracker*.

**Perché per Keel.** `branch-lifecycle` protegge i **file** (worktree, glob di scope,
`conflicts_with`); niente protegge l'**item**. Due sessioni possono prendere lo stesso pin, fare lo
stesso lavoro, e scoprirlo al merge. Un campo `claimed_by` + timestamp su `BuildItem`/pin, scritto
da un tool MCP prima di qualsiasi altra scrittura, chiude il buco — e rende finalmente sicura la
riga che il pacchetto già promette ("l'utente può eseguire item sbloccati in parallelo").

### ⑧ Il vocabolario dei moduli profondi

**Cos'è.** Vedi §4. Glossario con gli *avoid*, tre test operativi, la sezione **Rejected framings**,
e `DESIGN-IT-TWICE.md`: 3+ subagent in parallelo che progettano **interfacce radicalmente diverse**
per lo stesso modulo, ciascuno con un vincolo di design diverso ("minimizza l'interfaccia" /
"massimizza la flessibilità" / "ottimizza per il chiamante più comune" / "ports & adapters"), poi
confronto su *depth*, *locality*, *seam placement* — e **una raccomandazione netta, non un menu**.

**Perché per Keel.** `codebase-rescue` ha `module-design-alignment.md` (che è sui design token) e
il motore di forma dei campi; nessuno dei due dà un linguaggio per dire *dove va il seam* o *quanto
è profondo questo modulo*. E design-it-twice è già la forma del `brainstorm` di Keel (read-only,
propone, non elegge) applicata al design di interfaccia — quindi si innesta senza attrito.

**La trappola.** "Un adapter è un seam ipotetico, due sono un seam reale" è in tensione diretta con
l'istinto di un agente a generare astrazioni. Va scritto come test, non come consiglio.

### ⑨ Le prese piccole e affilate

| Presa | Dove | Perché |
|---|---|---|
| ✅ **Test tautologico** come anti-pattern nominato | `test-driven-development` | il valore atteso ricalcolato come lo calcola il codice passa per costruzione — è il difetto più probabile in una suite *generata*, che è esattamente il caso di rescue |
| ✅ **Seam pre-concordato**: nessun test su un seam non confermato | `test-driven-development` | rende il "one criterion, one test, one BuildItem" di Keel verificabile *prima* invece che dopo |
| ✅ **Expand–contract per i refactor larghi** | `branch-lifecycle` | il caso in cui nessuna slice verticale può atterrare verde è quello che uno scheduler a DAG gestisce peggio |
| ✅ **Baseline di 12 smell di Fowler**, col repo che sovrascrive | `code-review` | dà al reviewer qualcosa su cui poggiare quando il repo non documenta standard — cioè sempre, in rescue |
| ✅ **Due assi non fusi, nessun rerank** | `code-review` | il rerank è ciò che fa mascherare un asse dall'altro; Keel ha precedenza a primo-match, che è una scelta diversa e va difesa esplicitamente |
| ✅ **Le richieste rifiutate hanno una casa** — come pin `deferred`, non come file separato | `maintainer-assist` | lega agli stati `deferred`/`accepted`; impedisce di ri-litigare |
| ✅ **Controllo di ridondanza per concetto di dominio**, e dire dove hai cercato | `maintainer-assist` | il "è già implementato?" fatto bene |
| ✅ **`prototype` come fonte primaria** su ramo fuori da main | `src/skills/prototype/` | fa salire di rung un `open_decision` su "come si comporta" |
| ✅ **`wizard`** per i passi solo-umani | `src/skills/wizard/` | l'inverso di `assumptions.md`: non un'assunzione dell'agente, un'azione a gate umano — e il vincolo che la lega al ledger è che *"l'ho fatto"* è `self_check`, non un'osservazione |
| — **Riferisci per nome, mai per id** | *già vero*: `map.py` rende `p.title` | verificato dopo aver scritto la riga; era un buco inventato |
| ✅ **Albero dei confini di fase** (continue / clear / handoff / subagent / compact) | `src/core/phase-boundaries.md` | la tabella fonte-primaria-vs-secondaria è un frame che Keel non ha, e il reset di contesto fra fasi è già la sua architettura |

---

## 7. Cosa **non** copiare

- **I bucket** (`misc/`, `in-progress/`, `deprecated/`). Keel ha ucciso deliberatamente la
  divisione a tre vie "questo è sorgente o output?" con una regola sola. I bucket la
  reintrodurrebbero da un altro lato.
- **`skills/` come sorgente *e* output** (nessun build). È esattamente lo stato da cui Keel è
  uscito. L'ADR 0002 di mattpocock documenta il prezzo che si paga a non avere un build: nessun
  plugin Codex nativo.
- **`CONTEXT.md` come file glossario separato.** L'idea (linguaggio condiviso, meno verbosità,
  naming coerente) è ottima e Keel la vuole — ma il ledger + la proiezione in `AGENTS.md`
  (`instructions.py`) **già possiede** "il design eletto raggiunge un agente fresco". Un secondo
  file glossario accanto alla singola fonte di verità sarebbe un **gemello stateless**: precisamente
  l'argomento con cui Keel ha rifiutato di comporre `superpowers`. Prendi la *disciplina* di
  `domain-modeling` — sfida i termini contro il glossario, affila il linguaggio fumoso, stressa con
  scenari concreti, contro-verifica col codice — e legala al ledger.
- **Il test a tre condizioni per gli ADR** (difficile da invertire ∧ sorprendente senza contesto ∧
  risultato di un vero trade-off) — prendilo, ma **non i file ADR**. In Keel quel test dice quando
  un `design_concern` merita l'elezione invece di essere semplicemente fatto.
- **Il report HTML via CDN** (Tailwind + Mermaid da CDN) di `improve-codebase-architecture`. Il
  `map.py` di Keel è auto-contenuto per scelta. Prendi la **struttura della card** (Files / Problem
  / Solution / Benefits / Before-After / badge di forza della raccomandazione: `Strong` /
  `Worth exploring` / `Speculative`), non il modo di consegnarla.
- **Il tracker come casa dello stato.** La stessa pagina docs di mattpocock è onesta sul prezzo:
  i manutentori open-source vedono i tracker pubblici riempirsi di ticket di planning generati da
  agenti, e ripiegano sul markdown locale. Il `ledger.json` di Keel è già la risposta giusta; ciò
  che vale la pena rubare è il *bloccaggio nativo che disegna la frontiera*, cioè un'affordance di
  visualizzazione — che in Keel è `map.py`, non GitHub.

---

## 8. Licenza e attribuzione

`mattpocock/skills` è **MIT**. Keel ha già una regola scritta per questo caso, coniata su
superpowers: *"dove la sua prosa è buona, adattala con attribuzione invece di far finta di non
averla letta."* Applicala identicamente — un `## Attribution` in fondo a ogni file che adatta
materiale, come già fa `module-design-alignment.md`.

Nota che diversi concetti sotto sono a monte di entrambe le repo e vanno attribuiti alla fonte, non
a mattpocock: **seam** è di Michael Feathers, **deep module** e **design it twice** di Ousterhout,
la **baseline degli smell** di Fowler (*Refactoring*, cap. 3), **expand–contract** e **tracer
bullet** sono patrimonio comune (Thomas & Hunt).

---

## 9. Se fai solo tre cose

1. **`src/core/writing-for-agents.md`** + `writing-skills` che lo punta. È l'unica presa che
   migliora *ogni riga futura* della repo invece di una skill sola.
2. **L'asse di invocazione, generato dal build**, e — nella stessa PR — **il router**, perché
   l'asse senza router sposta il carico dal contesto all'umano senza dargli un indice.
3. **La Fase 1 di `diagnosing-bugs` dentro `systematic-debugging`**, con la sezione di redazione.
   È l'unica presa che rende *ottenibile* un gate che Keel già impone (`rung="observed"` su un pin
   `defect`).

Il resto è reale ma incrementale. Fog of war e reclamo sulla frontiera sono i due candidati
successivi, e sono entrambi decisioni di design da portare all'intervista — non modifiche da fare
di testa propria alla spec del ledger.
