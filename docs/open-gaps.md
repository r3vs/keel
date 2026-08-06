# Open gaps — the standing record of what this package knows is wrong with itself

This file started as four things left open after v0.5.0 (`22809f0`). It is no longer that. It is the
**standing register**: every defect this repo has found in itself and has not closed, kept in one
place, in one shape, so that a cold session can pick any of them up without re-deriving the evidence
— and so that nothing gets closed twice or forgotten once.

Every section, open or closed, is stated the same way: **what was verified**, **why it matters**,
**what done looks like**, **how to prove it**, and the **traps** — because in this repo a change is
not finished when the tests pass, it is finished when the behaviour was observed. Closed sections
keep their original text under a closing note; they are kept, not deleted, because *why it was
wrong* is the part that stops it coming back.

> **STATUS 2026-08-06 (third pass).** §1–§14 and §16 are **closed**, and §17a, §17b, §17d, §17e,
> §17f, §17g with them. **Only §15 and §17c are open.**
>
> | # | Open gap | One line |
> |---|---|---|
> | ~~5~~ | ~~reopen arcs unreachable~~ | **CLOSED** — both arcs, `set_question` and `add_proposals` now have doors |
> | ~~6~~ | ~~map palette contrast~~ | **CLOSED** — measured before/after in a browser; three hues needed a paired foreground, not one darker hue |
> | ~~7~~ | ~~`resolution_mode` has no reader on the map~~ | **CLOSED** — one line under the sub-line, and only `proposed_default` is a countdown |
> | ~~8~~ | ~~the `verification` envelope has no reader~~ | **CLOSED** — a verification card says *this pin cannot close: …*; the funnel carries `blocked_by` |
> | ~~9~~ | ~~a null-valued scope key is a universal selector~~ | **CLOSED** — `scope_note` says what the matcher matched, on the elicited message |
> | ~~10~~ | ~~no door gives an existing pin a question~~ | **CLOSED** — `mcp:ledger_set_question`, write-if-absent, freeform required |
> | ~~11~~ | ~~the `correctness_unknown` fork offers an outcome it cannot produce~~ | **CLOSED** — the implication is computed from `settlement_verdict` |
> | ~~12~~ | ~~`resolution_mode: "asked"` is permanent~~ | **CLOSED** — only a STANDING refusal writes it, at both unasked doors |
> | ~~13~~ | ~~`ensure_ascii=False` emits raw U+2028/U+2029~~ | **CLOSED** — one table of holes, and `_inline` proved by AST to be the only path |
> | ~~14~~ | ~~five more pin fields, and four of five log kinds, reach the map nowhere~~ | **CLOSED** — one stack of cards plus a trail, decided once |
> | 15 | two gates check less than their names claim | an AST gate that only sees constants; a name-match gate |
> | ~~16~~ | ~~an unknown `settles_as` renders as a bare label~~ | **CLOSED** — one `unknownNote` sentence, six callers, tables kept apart |
> | 17 | **17c only** — two phase-4 playbooks still say `resolved` needs two things | 17a/b/d/e/f/g closed |
>
> §6 and §7 were found by opening the page in a browser, which is the only way either could have
> been. §9–§16 came from two adversarial reviews of the v0.16 settlement work and are recorded here
> rather than fixed, under the rule that governed that round: **a round that only removes defects
> cannot introduce a new surface's holes**, and most of these need a new door, a new reader or a
> widened gate.
>
> | Gap | Closed by | The answer now lives in |
> |---|---|---|
> | 1. `evidence` stored and shown nowhere | `294535a` | `src/runtime/map.py`, `ledger.summary()`, `instructions.py::_evidence_note` |
> | 2. tools named by no phase | `eb9c24c` | both `phase-2-interview.md`, both `modules.json`, gate `scripts/check_tool_carriers.py` |
> | 3. elicitation had never met a real host | `3a0be05` | `docs/packaging.md` → *Elicitation — does the host ask the human, or does the agent relay?* |
> | 4. 21 tree-sitter skips | `92d2e17` | `tests/test_treesitter.py::TestASkipIsAClaimAboutOneInterpreter` |
> | 5. + 10. + 17b. five transitions no host could make | ledger v0.17 | `mcp:ledger_reopen` · `ledger_challenge` · `ledger_set_question` · `ledger_add_proposals`; `Ledger.reopen_verdict` + `_reopen_minimal`; `tests/test_ledger.py::TestComingBackIntoTheOpenSetIsGovernedToo`; `test_invariants.py::…::test_an_INTERNAL_mutator_is_actually_reached` |
> | 9. + 11. + 12. + 17f. + 17g. five rules false of what they were printed on | ledger v0.18 | `Ledger.policy_preview` → `scope_note` (and `server.py`'s elicited message); `ledger.STANDING_REFUSALS`, read by `apply_policy` and `interview.expand_catalog`; `Ledger._accept_implication`; `Ledger.defer`'s signature; `ledger.LOG_ENTRY_PREFIXES` + `nonconforming`'s `log_entry_kind`; gates `tests/test_ledger.py::TestARuleIsTrueOfTheThingItIsPrintedOn` and `test_invariants.py::TestAMarkWithNoClearingDoorIsWrittenForAStandingReason` |
> | 6. + 7. + 8. + 13. + 14. + 16. + 17a. + 17d. + 17e. the reading surfaces never grew | ledger v0.19 | `src/runtime/map.py` — the palette block's three foreground pairs, `unknownNote`, and the card stack `verificationCard` · `brainstormCard` · `modeLine` · `readinessCard` · `remediationCard` · `premortemCard` · `trailCard`; `_SCRIPT_UNSAFE` + `_inline`; `interview.funnel`'s `blocked_by`; `instructions._pin_line`'s dispute clause and the two settled sections; `ledger.LEAVE_AS_IS_STATES` + `ledger.REOPENED_SUBSTATES`; gates `tests/test_map.py::TestThePaletteCarriesTheWarningItIsUsedFor` · `TestTheOnlyWayDataEntersThePage` · `TestEveryClosedTableThePageReadsIsTheSchemas` · `TestTheWholeEnvelopeHasAReader`, `tests/test_instructions.py::TestNoStateNameIsKeptInThisFile`, `tests/test_ledger.py::TestTheDistinctionsASurfaceSortsAndTITLESBy` |
>
> Two residuals of gap 3 are recorded rather than fixed, and both are named in `docs/packaging.md`:
> a Claude Code hook can answer an elicitation *for* the human, so `elicited` means "the agent did
> not hold the value", not "a human was looked in the eye"; and headless `codex exec` declares the
> capability then auto-cancels, so `ledger_record_decision` errors there instead of falling back to
> the transcribed rung. Neither is a bug in what is written down — they are the limits of what the
> strong rung buys, which is the sort of thing this file exists to keep honest.
>
> **The pattern the register makes visible, stated once so each section does not have to.** Most of
> the open gaps were one shape: *a field, a state or an arc that something WRITES and nothing
> READS.* §5, §7, §8, §10, §14 and half of §11 were all that — **all of them are now closed**, and the first two
> turned out to be the harsher variant of it: an arc nothing could **write** either. It is the repo's signature class
> (`MEMORY.md` → *"the claiming-vs-doing failure"*) at the surface layer rather than the path layer,
> and the reason it keeps recurring is structural: adding a writer is a change inside one module, and
> giving it a reader is a change on somebody else's surface. So the question to ask of any new field
> is not "is it stored" but **"name the surface a human reads it on, and open that surface."**
>
> **The second shape, which §9, §11, §12, §17f and §17g turned out to share.** Not a missing reader:
> *a sentence, a default or a mark that is true of some object and is printed on the ones it is
> false of.* An option promising a state its own door refuses; a scope reading as a filter and
> matching by absence; a permanent mark recording a fact about the last rule; a parameter naming a
> path that does not exist. Each had a tool, ran, and passed every gate — because a gate asserts the
> rule, and what was wrong was the rule's claim about the thing in front of it. The question that
> catches it: **read the sentence the surface prints and ask what happens if a human believes it,
> on the object it is printed on.**

Two of the original four (§1 and §2) were introduced *by the same session that closed four older bugs
of the identical class*, and the same thing has happened in every round since — §5 and §8 were opened
by the round that closed §1–§4's successors, §9–§16 by the round after that. That is the point of
writing them down rather than remembering them: this failure mode is not rare here and it is not
careless — it is what happens when you add state and stop at the layer that stores it.

**Before starting anything below:** read `CLAUDE.md`, then the playbook for whatever you touch.
Work on a branch, one scope per commit, and **run every gate — the list is the Commands block in
`CLAUDE.md`, and it is complete against `.github/workflows/ci.yml`.** This line used to enumerate the
gates itself, and the copy was already short by two — `check_tool_carriers.py` and
`run_evals.py --validate`: a second list of the same fact, drifting, in the file that tells a cold
session what "every gate" means. `src/` is authored, `plugins/` is generated — never edit under
`plugins/`, run `python scripts/build.py`.

The original suggested order was **1 → 2 → 4 → 3**, and it was followed; 3 landed in between the two
outcomes it anticipated — two hosts yes, two no. §1–§4 below are that report, kept verbatim under
their closing notes. §5 onwards were opened later and each says where it came from.

**Suggested order for what is left.** §5 was done first, then §9, §11, §12, §17f and §17g — the
rules that mis-fired rather than the surfaces that were missing — then the reader cluster **§6, §7,
§8, §13, §14, §16, §17a, §17d, §17e** as **one** change to the two reading surfaces, which is what
§14 asked for and is why they closed together. **What is left is §15 and §17c.**

§17c is prose: two phase-4 playbooks and rescue's `SKILL.md` still say `resolved` requires two
things when it now requires three, and the refusal text happens to name the fix. §15 is the harder
one and is the right next scope, because it is the class every round keeps finding: *a gate that has
been asked and answered stops anyone asking again.* The round that closed the reader cluster nearly
added a fourth instance and caught it in the DOM rather than in CI — a new test named *"a badge is
readable against its own foreground"* that listed the two tokens the finding named and would have
skipped the two more that were failing (see §6). Read that before starting §15: the shape is always
a gate whose name quantifies over more than its body does.

---

## 1. `evidence` is stored and shown nowhere — **CLOSED 2026-08-05** (`294535a`)

Three surfaces now carry the rung, chosen by what each is for. The **map**'s decision card states it
and shows the quote, looked up in `decision_log` by `event_id` (the ledger is inlined whole, so it is
a join, not a fetch, and the page stays one offline file); weak reads as weaker — amber on a tinted
card against green for elicited. **`Ledger.summary()`** returns `decisions_by_evidence`, so the count
an agent reads before acting says "17 decided, 15 on an agent's say-so". **`instructions.py`** made
the budgeted call deliberately and recorded it: no per-decision rung in the projection, one
`_evidence_note` line when a weak rung is present, with the reasoning in the module docstring —
an omission with a reason, which is the standard this section set.

### Verified

`DecisionEvent.evidence` (`elicited | transcribed | brief`) and `human_answer` were added in v0.10
(`src/core/decisions-ledger-spec.md`, the "`evidence` — how the human's answer reached the log"
section). Written by `Ledger.decide()` in `src/runtime/ledger.py`. Then:

```
grep -c evidence src/runtime/map.py          -> 0
grep -c evidence src/runtime/instructions.py -> 0
Ledger.summary()                             -> does not count it
```

The map renders the decision at `src/runtime/map.py:202` and shows the outcome only:

```js
if(p.decision) body+=`<div class="card"><div class="kv"><b>decided</b><span>${esc(p.decision.outcome)}</span></div></div>`;
```

### Why it matters

The spec's own justification for allowing the weak rung at all is that it is **made visible**:

> the weak path is not forbidden, it is made **visible**, so a reader can weigh it and the
> challenger can attack it.

Nobody reads `ledger.json` by hand — they read the map, the summary, and `AGENTS.md`. A decision
recorded as `transcribed` (an agent's word that the human said so) is today indistinguishable from
one the server elicited directly. So the sentence above is, as shipped, false. This is not a missing
nicety; it is the design's load-bearing claim with no carrier.

### Done looks like

- **Map** — the decision card states the rung, and a `transcribed` one shows the quoted
  `human_answer`. Weak evidence should read as weaker at a glance, not merely be present in a
  tooltip. `pin.decision` currently carries only `{event_id, outcome}`; the rung lives on the event
  in `decision_log`, so the map must look it up by `event_id` (the ledger is inlined whole, so this
  is a lookup, not a new fetch).
- **`Ledger.summary()`** — a `decisions_by_evidence` count beside `failures_by_class`. The summary
  is what an agent reads *before acting*; "17 decided, 15 of them on an agent's say-so" changes what
  a reviewer does next.
- **`instructions.py`** — decide deliberately, and record the decision either way. The projection is
  budgeted (Codex truncates by bytes; adherence drops past ~200 lines) so a per-decision rung may not
  earn its bytes; a single line in the header ("N of M decisions were transcribed, not elicited")
  probably does. If you conclude it does not belong, say so in the module docstring — an omission
  with a reason is fine, an omission by oversight is this bug again.
- The challenger can act on it: `src/runtime/challenger.py` already refutes elected oracles. A
  decision resting on an unquoted relay is a legitimate thing to challenge. Optional, but it is the
  other half of "so the challenger can attack it".

### Prove it

Render a map from a ledger holding one elicited and one transcribed decision, open it in a browser,
and look. `scripts/preview_map.py` exists for exactly this and its docstring lists the procedure —
extend its fixture with both rungs. A test asserting the string is in the HTML proves nothing about
whether a human can see it.

### Traps

- Do not add a `set_evidence`-style tool. The rung is a fact about how the write happened; only the
  writer can state it, and it is already recorded there.
- Do not let this become a confidence score. Three named rungs with different failure modes, kept
  apart, is the design — averaging them into a number is what the spec explicitly refuses.

---

## 2. The tools the phases need are named by no phase — **CLOSED 2026-08-05** (`eb9c24c`)

> **And it opened one, closed 2026-08-06.** Two adversarial reviewers found it independently. The
> fix exposed the READ half of the policy step (`interview_seed_policies`) and left the WRITE half
> doorless: nothing created a `Policy` or ran `apply_policies` on any host, while the same commit
> ADDED four passages telling an agent the user elects a policy and that it then cascades. Exactly
> the class this section is about, in the commit that closed the class. The door is now
> `mcp:ledger_record_policy` (+ read-only `mcp:policy_preview`), built on `record_decision`'s shape.
> The second finding was its consequence: the cascade called `decide()` with no `evidence`, so
> a user's own cascaded policy rendered as *"an agent relayed what the user said — ⚠ relayed with no
> quote"* on all three of gap 1's surfaces. A cascade now has its own rung (`cascaded`, spec v0.11)
> and names its policy by `policy_id`. Lesson worth keeping: **a new tool is not the deliverable —
> the reachable state transition is.** `check_tool_carriers.py` would have caught the unnamed tool;
> it cannot catch a tool that was never written, so the question to ask of any prose is not "does a
> tool exist for this" but "name the tool that performs it, and run it".
>
> **And THAT opened one, closed 2026-08-06 (spec v0.12).** Both reviewers found it independently,
> each by running the new door rather than reading it. The door governed *who* answered — quote,
> offer taken verbatim, elicitation, rung — and not *what could be written*: `record_decision`
> refuses an outcome the pin's own `question` never offered, and the policy path wrote the caller's
> own sentence onto every pin in the cluster, on the strongest rung, with the outcome absent from
> the message the human accepted. The same shape a third time: **a new surface arrived without the
> invariant that governed the old one.** Now an outcome lands on a pin only if that pin's question
> offers it (`not_offered` holds the rest back), `default_outcome` is an option id, the elicitation
> names the outcome, and the cascade runs once over the radius its elector saw. The question to ask
> of any new write door is not "is it guarded" but "name every invariant the OLD door enforced, and
> check each at this one".
>
> **And THAT left one, closed 2026-08-06 (spec v0.13) — the same lineage, one step sideways.** Both
> v0.11 and v0.12 were enforced *at the write*, so neither governed a single ledger that already
> existed. A reviewer built the file the pre-v0.11 cascade wrote (`source: "policy:pol_0001"`,
> `evidence: "transcribed"`, no `policy_id`) and ran all three of gap 1's surfaces: `{"transcribed":
> 1}`, *"1 relayed by an agent"*, and the map's unquoted-relay warning — the exact sentence v0.11 was
> written to delete, still shipping. Worse, a bare load+save restamped that file with the runtime's
> own version, so it then *claimed* invariants it does not satisfy. Both are refused now: the rung is
> **read** from the carrier its writer left (`ledger.decision_rung` — the log is immutable, so
> nothing is rewritten and the map states what the file records), and `version` is a **floor** that
> rises only when `ledger.nonconforming` is empty, reported as `pre_rule_events`. Restated for the
> next time, since this is the fourth turn of it: **a new rule arrives with a writer and no reader.**
> The question is not "is the rule enforced" but *"name every artifact this rule is now false of,
> and say what reads them."*
>
> **And the whole lineage rested on two tools that could not run at all — closed 2026-08-06.** Found
> by the final reviewer, at the only place it was ever visible: the SHIPPED tree. `interview.py`
> reads a **data** file, and `build.py` vendored only `*.py`, so `interview_expand` and
> `interview_seed_policies` raised `FileNotFoundError` on every host, on every call. Installed, that
> module is `keel-core/mcp/runtime/interview.py`, so its authoring-relative constant pointed at
> `keel-core/mcp/skills/greenfield-forge/…` — while the catalog ships inside a **different plugin**,
> which this one may not read. Nothing saw it because every test hands `load_catalog` an explicit
> path (`tests/test_interview.py:21`), so 704 tests exercised the parser and none the default. The
> build now ships the catalog to `mcp/runtime/assets/`, resolution happens at call time against both
> candidate trees, the failure names both paths it looked in, and
> `test_installed_package.py::test_the_two_catalog_tools_run_on_the_installed_tree` calls **the two
> tools** from a foreign cwd on a copied plugin — verified to fail when the asset is removed. This is
> the repo's oldest bug class (`python runtime/ledger.py`), and the honest lesson is narrower than
> "check the install": **a gate that tests a function's parameter never tests its default**, and the
> default is the only form a tool caller can use.
>
> One more from the same round, worth its own line because it is the failure mode of a *gate*:
> `tests/test_tool_roster.py::test_every_served_tool_is_documented_and_nothing_else_is` filtered its
> entries through the served set before comparing (`if n in known`), so the "nothing else is" half
> could not fire — a planted `ledger_delete_everything` row passed green, twice over, because the
> count balanced too. Both filters are gone and the plant was re-run to confirm it fails. A test
> named for an invariant it does not check is worse than no test: the absence would at least be
> visible.

The class was closed, not just the instance. Rescue's phase-2 names `mcp:ledger_record_decision` as
the commit step with the four things it enforces; greenfield's phase-2 says what actually happens as
three tools, and `phase-1-frame.md` / `decision-catalog.md` name `interview_expand` where the
expansion is described. Both interview modules declare their engine and stay `type: judgment` — the
outcome is the human's, the write has exactly one carrier. **The decision the section demanded was
made:** `interview_seed_policies` is its own tool rather than a step inside `interview_expand`,
because a silent write behind a tool named "expand" is the thing this package refuses. And
`scripts/check_tool_carriers.py` (in CI) fails the build when a **write** tool — derived from each
`@mcp.tool` annotation's own `readOnlyHint`, by AST, not by grep — is named by no shipped playbook.
It found two instances beyond the three reported here.

### Verified

```
ledger_record_decision -> src/skills/using-the-ledger/SKILL.md, src/core/decisions-ledger-spec.md
interview_expand       -> src/skills/using-the-ledger/SKILL.md
propose_correspondence -> src/skills/codebase-rescue/references/contract-reconciliation.md
```

No `modules.json` declares any of them as an `engine`. The modules that *elect* are
`codebase-rescue: interview-generator` and `greenfield-forge: interview-generator` /
`decision-frame` — all `type: judgment`, `engine: None`.

And the electing playbooks describe the act without naming the tool that performs it:

- `src/skills/codebase-rescue/references/phase-2-interview.md:69` — *"the user's committed answer
  here (and only here) sets `state: decided` and emits the `DecisionEvent` (with `flip_criteria`)"*.
  True, and it never says how.
- `src/skills/greenfield-forge/references/phase-2-interview.md:26` — *"The `interview_next` tool
  expands the decision catalog into `open_decision` / `acceptance_criterion` pins and seeds the
  per-cluster default policies"*. **Both halves are false.** `interview_next` calls
  `interview.funnel()`, which reads. Expanding is `interview.expand_catalog` (now exposed as
  `interview_expand`); seeding is `interview.default_policies`, which **has no tool at all** —
  verified: neither name appears anywhere in `interview.py` outside its own definition, nor in
  `mcp/tools.py` except the new `interview_expand`.

### Why it matters

This is instance 2 of the repo's signature class, recorded in `MEMORY.md`: *twelve playbooks invoked
the runtime zero times* — the prose described each activity in English while the code implemented it
and nothing joined them. A tool no playbook names does not get called, whatever the tool list says.
It is why the MCP server exists (discovery), and it was reintroduced the same day four instances of
the class were closed.

The greenfield line is worse than silence: it tells the agent a mechanism exists that does not, so
the agent believes the catalog was expanded and the policies seeded when neither happened.

### Done looks like

- Rescue `phase-2-interview.md`: the commit step names `mcp:ledger_record_decision`, states that the
  outcome must be one the pin's question offered, that `flip_criteria` is required, and that on a
  host without elicitation the agent must quote the user verbatim.
- Greenfield `phase-2-interview.md`: the false sentence corrected to name `interview_expand` for the
  catalog, and to say honestly what happens to the default policies — see the decision below.
- `modules.json` for both skills: the electing module declares its engine. Note the type rule in
  `greenfield-forge/modules.json`'s own header — *"an `agent:<how>` engine is legitimate and still
  declared, but it is never deterministic"*. The interview stays `type: judgment`; the engine is
  declared as the honest statement of what produces the output. `check_consistency.py` enforces
  type↔engine coherence, so read that rule before choosing the value.
- **A decision you must actually make:** `default_policies` has no surface. Either expose it
  (`interview_seed_policies`, or fold it into `interview_expand` since they are always used
  together at frame time) or delete the claim from the playbook. Do not leave the prose describing
  it while nothing performs it — that is the whole bug.

### Prove it

`scripts/verify_commands.py` and `check_consistency.py` will pass either way; they check that named
things resolve, not that necessary things are named. So the proof is a reading: open each phase
playbook and ask *"if I were an agent with only this file, would I call the tool?"* If the answer
needs the tool list, the prose is not done.

Consider closing the class rather than the instance: a linter that fails when a **write** tool
exposed by the server is named by no shipped playbook would have caught both this and the 2026-07-16
original. Scope it to write tools — a read tool that only `using-the-ledger` names is defensible.

---

## 3. Elicitation has never met a real host — **CLOSED 2026-08-06**

**It has now met all four, and the answer is split 2–2.** The per-host record lives in
`docs/packaging.md` → *"Elicitation — does the host ask the human, or does the agent relay?"*, with
every claim cited at the function that consumes the value. In short: **Claude Code** (2.1.221, read
out of the binary that actually spawned our server) and **Codex** (`openai/codex`) both declare
`elicitation: {}` unconditionally and both render our enum as a **picker**, so the free-text worry
below does not arise on either. **opencode** does not — the line is commented out, `elicitation`
support landed in PR #35064 and was reverted 67 minutes later by #35080 — and registers no handler.
**Pi** does not, and that negative is **ours**: Pi has no MCP client at all, our own
`mcp-bridge.ts::McpStdioClient.connect()` hardcodes `capabilities: {}`, and the file names the work
that would close it (`ctx.ui.select`, declared only when `ctx.hasUI`).

The keel-side link both positive rows depend on — what `ctx.elicit(message, choices)` actually puts
on the wire — was the one thing no audit had, so it was **executed** under the pinned
`fastmcp==3.4.4`: one flat string property carrying an `enum`, passed verbatim as `requestedSchema`.
That is recorded too, since both rendering claims rest on it.

**What was deliberately not upgraded to fact.** All four rows are `read_source`; **no handshake was
captured on the wire**, so option 1 of "Prove it" below stays unexecuted and the honest verb is
"read", not "observed". Codex was read at `main` with no tag pinned. Two Claude Code sub-claims are
marked `UNVERIFIED` in `packaging.md` rather than resolved: whether the interactive handler is
registered in non-interactive/`stream-json` runs, and whether an elicitation from a subagent reaches
the REPL queue. The trap the section warns about is the one that would swallow these.

**The rung stays on the two hosts that cannot use it**, exactly as this section instructed — it costs
one session lookup and arms itself the day support lands.

### Verified

`ledger_record_decision`'s strong rung asks the client through the host. It is verified end to end
in `tests/test_mcp_server.py::TestRecordingAnElectionByElicitation` — against a **fake client
written in that same file**, which declares `{"elicitation": {}}` and answers the request.

That proves the protocol path works. It proves nothing about whether **any real host declares the
capability**. If none does, `_client_can_elicit` always returns False and the strong rung is dead
code; the design degrades correctly to relaying, but "it degrades correctly" and "it is ever used"
are different claims and only the first has evidence.

### Why it matters

The whole reason the strong rung exists is that a transcribed decision cannot be distinguished from
a fabricated one. If it never fires, every decision in the wild is `transcribed` and the ledger's
strongest guarantee is theoretical.

### Done looks like

A verified per-host answer to: *does this host's MCP client declare `elicitation` in its
`initialize` capabilities, and does it render the prompt?* Recorded where the other host facts live
(`docs/packaging.md` and the memory file `host-claims-audit-2026-07-17.md`), with the citation being
**the function that consumes the value**, never the type that holds it.

Hosts: Claude Code, Codex (`openai/codex`), opencode (`anomalyco/opencode`), Pi
(`earendil-works/pi` — note it has no native MCP; its bridge extension is the surface).

### Prove it

Two independent ways, and prefer the first:

1. **Observe it.** Add temporary stderr logging in `server.py` that dumps the client's declared
   capabilities on `initialize`, install the plugin the way a user does, and read what each host
   actually sends. This is the consumer. Remove the logging before committing.
2. **Read the source**, following the value to whatever consumes or replaces it. Do not stop at a
   type or a constant.

If a host declares it: also check what it *renders*. `ctx.elicit(message, choices)` builds an enum
schema; a host that ignores the enum and shows a free-text box would let a user answer outside the
offered menu, which the pure layer would then reject with a confusing error.

### Traps

- This repo has been wrong about host facts by reasoning from memory more than once; see
  `MEMORY.md` → "Host claims, audited at the consumer". Assert nothing you did not watch or read.
- `anomalyco/opencode` is the current name; older citations use a stale one.
- A negative result is a real deliverable. Record it and keep the rung — it costs nothing and arms
  itself the day a host gains support, which is exactly why the capability is asked and not assumed.

---

## 4. The local suite skips 21 tree-sitter tests and nobody knows why — **CLOSED 2026-08-05**

**Cause: two interpreters, not one behaviour.** The gap's premise ("the same interpreter") was
false. An unrelated tool's virtualenv (`…\hermes-agent\venv\Scripts`, python 3.11.9, no
`tree_sitter`) sat on the **User PATH ahead of the real install**, so every PATH-resolving shell —
PowerShell, cmd, and any subprocess any tool spawns — got it. Git Bash escaped only via
`~/.bashrc:31`, an `alias python=…Python314\python` that rewrites what bash execs and is invisible
to PATH lookup in any child process. So the passing `python -c "import tree_sitter"` ran under the
alias (3.14, backend present) and the skipping `discover` ran under PATH resolution (3.11, backend
absent). Same-shell control, only the interpreter varied: `OK (skipped=29)` vs `OK (skipped=4)`.

That is also why every hypothesis below was ruled out — there was nothing to find inside the
process. `sys.path` was not corrupted and nothing shadowed the import; the interpreter simply never
had the package, and the "unrelated venv's site-packages" was not a symptom but literally the
running interpreter's own.

**Why the existing detector missed it.** `TestCIExercisesTheShippedBackend` probes
`subprocess.run([sys.executable, …])` — it asks the possibly-broken interpreter about *itself*, so
it can only catch an **intra**-interpreter discrepancy. The real condition was **inter**-interpreter,
so the probe agreed with itself, honestly, and degraded to its skip exactly as designed.

**The check that closes it** — `tests/test_treesitter.py::TestASkipIsAClaimAboutOneInterpreter`.
When this interpreter lacks the backend, it asks **every python PATH can reach** (executing each and
reading its exit code — the carrier, not the path's spelling; zero-byte Windows App Execution Alias
stubs are excluded because they cannot be executables and running one opens the Store). If any has
it, the test **fails** and names both interpreters plus what bare `python` resolves to. It counts
the silenced assertions off `__unittest_skip__`, the same attribute the runner reads, rather than
hardcoding 21. Verified at the consumer on all three branches: hermes 3.11 → RED naming both
interpreters; Python 3.14 → 29 tests, `OK`, no skips; PATH stripped of any capable python →
`OK (skipped=22)`, the honest absence, no false failure. The skip *reason* now names the interpreter
too, so the 21 skips can no longer read as a fact about the machine.

**Left to the operator** (outside any repo, so not done here): take the foreign venv off the global
PATH, or invoke the interpreter you mean by its full path. `CLAUDE.md`'s "on Windows use `python`
(present)" — the instruction that produced this — was corrected.

### Verified (the original report, kept as the record)

In CI this is **closed**: the workflow now installs the backend pinned to what the server ships, and
the same commit went from `Ran 565 tests, OK (skipped=28)` to `OK (skipped=4)` — the four remaining
are the release-tag assertions, which is their correct state.

On the machine this was written on, `python -m unittest discover -s tests` still skips the 21
`skipUnless(HAVE_TS)` tests, while `python -c "import tree_sitter"` succeeds with the same
interpreter. What was ruled out:

- `sys.path` loses nothing across discovery (`before - after` is empty)
- no test module assigns to `sys.path` or pokes `sys.modules`
- `src/runtime` first on the path does not shadow the import
- importing `agentready` / `challenger` / `ledger` directly does not break it
- importing `test_agentready` as a module does not break it either

Yet inside a real `discover()` run, `importlib.util.find_spec("tree_sitter")` returns `None` and the
only `site-packages` on `sys.path` is an unrelated venv's. The interpreter reports the base prefix,
not a virtualenv.

> Two claims in that last sentence were wrong, and both point at the cause. The venv's site-packages
> is not "an unrelated venv's" — it is the running interpreter's own. And `sys.prefix !=
> sys.base_prefix` there, i.e. it *is* a virtualenv; the reading that said otherwise came from the
> other interpreter. Measured, both: hermes → `prefix=…\hermes-agent\venv`,
> `base_prefix=…\Python311`; Python314 → equal.

`tests/test_treesitter.py::TestCIExercisesTheShippedBackend` now fails loudly if a plain subprocess
can import the backend while the suite cannot — but in the failing runs the subprocess *also* cannot,
so it skips honestly instead of catching it.

### Why it matters

Low severity, high annoyance: it makes local runs untrustworthy for the extraction backend, which is
the component most likely to regress silently. It is also the same shape as everything else in this
file — a green summary that is not coverage.

### Done looks like

Either a named cause and a fix, or a documented environmental condition with a check that detects
it. "It works in CI" is not an answer, it is where we already are.

### Prove it

Start from the divergence, not from the code: run the failing `discover()` and the passing single
module with `python -X importtime` and compare, and print the full `sys.path` plus `os.environ`
snapshot at the top of both. The env is the remaining suspect — the subprocess probe inheriting a
different environment than the shell is consistent with everything ruled out above.

> Superseded, and worth keeping as a lesson in where to start. No `importtime` diff was needed or
> possible: the module is absent from the interpreter, so there is no import event to compare. The
> instruction "start from the divergence" was right; the divergence was just one level further out
> than "the env" — it was **which binary the word `python` names**, which every command in this file
> spells the same way and no gate had ever pinned down.

---

## 5. Both reopen arcs are reachable by nobody — **CLOSED 2026-08-06** (ledger v0.17)

**Both arcs have doors, and so do the two states that turned out to be in the same condition.**
`mcp:ledger_reopen` and `mcp:ledger_challenge` are served, named by shipped playbooks
(`core/feedback-loop.md` + greenfield's phase-7; both phase-2 interviews), and verified end to end
over real `uv run --script` stdio against the **shipped plugin tree from a foreign cwd**: decide →
resolve → `mark_correctness_unknown` refused `already_closed` → `ledger_reopen` → the same call
succeeds. `tools/list` carries all four names, which is the carrier this section named.

**The shape got a predicate, not a fourth ad-hoc rule.** `Ledger.reopen_verdict(pin, arc)` answers
*would this arc move this pin*, `_reopen_minimal` is the single writer of the reopened state
(`_settle`'s twin), and `REOPEN_ARCS` ↔ `_SUBSTATE_BY_ARC` are held equal —
`TestComingBackIntoTheOpenSetIsGovernedToo` asserts the caller set from the AST, the mirror of
`test_every_door_reaches_the_single_writer`. `nothing_settled` is deliberately **not** a refusal:
both arcs append their event either way and report `reopened`, the shape `cross_derive` was
corrected to in v0.16 for the identical condition — dropping the event would lose the signal
`learning.divergences` and `premortem_required` both read.

**Both package predicates were checked at this surface, and the answer is recorded rather than
assumed.** `unasked_verdict` governs what outcome may land on an unasked pin; neither arc writes an
outcome — no `outcome`, `settles_as`, `option_id` or `default_outcome` parameter on any of the four
library methods or their four tools, and none of them calls `decide`/`_settle`/`accept`/`defer`,
asserted by signature and by AST. `settlement_verdict` governs leaving the open set; these enter it.
What each arc owes instead is stated in carriers: `reason` non-blank + `fired` ∈ `REOPEN_TRIGGERS` +
`source` ∈ `feedback:<FLIP_SIGNAL_SOURCES>` downstream; a non-blank `argument` upstream.

**Who owns `upheld` — the challenger, and the tool says so.** "Read-only" in the roster means *about
decisions*: reopening is the challenger's mandate, electing is what it may never do. What that buys
is checkability, so a blank `argument` is refused at the runtime, for the reason a relayed decision
with no quote is.

**The inverse gate this section asked for exists**:
`test_invariants.py::…::test_an_INTERNAL_mutator_is_actually_reached` computes the transitive call
graph over `src/runtime` + `src/mcp`, rooted at the `@mcp.tool` functions, and fails when an
exemption names a mutator nothing an agent can reach. It would have caught all four at once. Its
declared limit: names are matched by final component (the same rule `TestEveryPathToDecideIsGated`
uses), so a mutator sharing a name with something reachable (`run`) would pass — verified by
planting `_warm_grammars_async` and `nonconforming`, both of which it fails on.

**Two residuals, recorded rather than fixed:**

- `_reopen_minimal` cascades over `("decided", "resolved", "accepted")` — three states where
  `SETTLED_STATES` has four. Whether a `deferred` dependent rested on the falsified truth is a real
  question and nothing here settles it, so the tuple is unchanged and the divergence is named in a
  comment at the site. Inventing a rationale for someone else's tuple is how a hardcoded list
  acquires the authority of a decision (and it is §17e's class one file over).
- **`add_proposals` auto-id'd every proposal identically** — `f"prop_{len(proposals)}"` is the
  list's length, constant across the loop, so two proposals both came back `prop_2`. Fixed here
  rather than registered, because this commit is what made the method callable at all and the id is
  a carrier (`DecisionEvent.proposal_ref` points at it, and the funnel entry now lists it). Found by
  running the tool over stdio, not by reading it — unreachable code cannot be wrong in a way anybody
  notices, which is the whole subject of this section.

### The original report, kept as the record

Found while closing the v0.16 settlement predicate, and deliberately **not** fixed in that scope:
it is a missing door, not a missing rule, and the round that found it was a rule round. It is the
repo's signature class (`MEMORY.md` → *"the claiming-vs-doing failure"*), instance N.

### Verified

`Ledger.challenge()` and `Ledger.reopen()` are the two arcs the doctrine calls load-bearing — the
upstream refutation and the downstream production signal — and **neither has an MCP tool**. MCP is
the only runtime channel on all four hosts, so neither can be written by anybody, on any host:

```
grep -n "def .*reopen\|\.reopen(\|\.challenge(" src/mcp/tools.py src/mcp/server.py  -> 0 call sites
tools.challenge_oracle -> {"proposed": challenger.scan(_open_existing(ledger))}      -> READ-ONLY
```

`challenger.scan` proposes; it applies nothing. So an upheld `ChallengeEvent` and a fired
`flip_signal` `ReopenEvent` are states the runtime can produce and the product cannot.

Worse, the gate that exists to catch exactly this **asserts the opposite**.
`tests/test_invariants.py::TestEveryWritePassesAGovernedChannel.INTERNAL` exempts `challenge` with
the reason *"exposed as challenge_oracle, which applies upheld ChallengeEvents"* — which is false of
that function — and exempts `reopen` as *"the feedback loop's downstream arc, driven by a fired
flip_signal"*, which describes when it should run and never says what runs it. An exemption whose
stated reason is wrong is worse than no exemption: it is the check having been asked and answered.

### Why it matters

Three shipped claims rest on it, and v0.16 added a fourth:

- `core/feedback-loop.md` and the spec's v0.5/v0.6 sections both say the loop closes by reopening.
- `agentready.py` and `challenger.py` both read `chl_` events, so their inputs can only ever be
  empty.
- **v0.16 made it load-bearing.** A CLOSED pin (`resolved` · `accepted` · `deferred`) may no longer
  be settled again by any door, and the spec now says *"the way back is `reopen`, which records
  why."* That sentence is true of the runtime and reachable by no agent — so the correct handling of
  a finished pin that turns out to be wrong is, today, to hand-edit `ledger.json`, which every
  playbook forbids. The tightening is right; it made an existing hole load-bearing, and saying so is
  the point of this file.
- **2026-08-06 makes it load-bearing twice.** The `CLOSED_STATES` check now runs before every door,
  the mirror door included, so `mark_correctness_unknown` on a finished pin refuses with *"Reopen it
  first"* — a refusal that names, verbatim, the one arc no host can reach. Every refusal in this
  package is written to be actionable; this one is actionable only from a Python shell. That does
  not argue for loosening the door, it raises this gap's priority: a wall is what a gate becomes
  when its opening move does not exist, which is the same sentence the `rung` fix was written under.

### Done looks like

- A door for the downstream arc: `mcp:ledger_reopen(ledger, pin_id, reason, fired, source)`. It is
  **not** an election — reopening never decides — so it needs no quote and no offered option, which
  is exactly why it is safe to expose and why its absence is hard to justify.
- A door for the upstream arc: either `mcp:ledger_challenge(...)` writing one `ChallengeEvent`, or
  an `apply` mode on `challenge_oracle` — but read the neutrality rule first: the challenger is
  read-only *about decisions*, and `upheld` is a judgment somebody must own. Decide whose, and say
  so at the tool, not in prose.
- The two `INTERNAL` exemptions corrected to name what actually reaches the method, or moved out of
  `INTERNAL` entirely once a tool exists.
- `check_tool_carriers.py` covers write tools that exist and are named by no playbook; it cannot see
  a tool that was never written. Consider the inverse gate — a `Ledger` mutator classified
  `INTERNAL` whose stated entry point does not call it, asserted over the AST the way
  `TestEveryPathToDecideIsGated` already does for `decide`. That is the check that would have caught
  this one, and it is the same shape as the two gates that closed rounds 4 and 5.

### Prove it

Over real `uv run --script` stdio, with no human: decide a pin, resolve it, then try to reopen it.
There must be a tool call that does it. `tools/list` is the carrier — if the name is not in that
listing, the capability does not exist on any host, whatever the runtime can do.

### Traps

- Do not close it by making `cross_derive` the general-purpose reopener. It already reopens on
  provider disagreement and v0.16 deliberately narrowed it (it may not un-close finished work, and
  may not rewrite `question.options`). Widening it back would undo that in a different shape.
- Do not let `reopen` grow an outcome parameter. Both arcs **reopen and never decide**; a reopen
  that can also set a state is the fan-out flag returning under a new name.

---

## 6. The map's palette fails contrast where it carries the warning — **CLOSED 2026-08-06** (ledger v0.19)

**The answer lives in `src/runtime/map.py`'s `:root` block and the comment above it, and in
`tests/test_map.py::TestThePaletteCarriesTheWarningItIsUsedFor`.** Re-measured before and after, in
Chrome, from the elements' own computed colours, in **both** themes — because the section's own note
said its numbers were not re-verified since the day they were filed, and one of them was wrong.

| | light before | light after | dark before | dark after |
|---|---|---|---|---|
| `.warn` text on `--warnbg` (the tinted relay card) | **2.33** | **4.65** | 6.14 | 6.14 |
| `.rung.weak` badge (the amber pill) | **2.48** | **4.95** | **2.48** | **6.61** |
| `.sev` badge, `high` | **2.48** | **4.95** | **2.48** | **6.61** |
| `.sev` badge, `low` | **3.32** | **4.69** | **3.32** | **4.69** |

Two corrections to the filing, both material. **`--low` measured 3.32:1, not 2.48:1** — the three
numbers in the original were the same number written three times, and only two of them were right.
And **dark mode WAS affected**: the section says it is not, which is true of the amber as *text* and
false of the amber as a *badge*, because a badge's contrast is with its own foreground and does not
change with the theme. The `--high` pill was 2.48:1 in dark too.

That is also why the fix is not "a darker amber". One token cannot serve both uses: as text it must
contrast with the surface (dark on light, light on dark), as a fill it must contrast with its
foreground (dark, always). **So the hue stays one hue and the FOREGROUND splits** — `--onhigh`,
white in light and near-black in dark. The trap said not to add a fifth colour, and none was added.

**Scope grew by two tokens, deliberately, and the reason is §15.** A DOM sweep of every badge and
every text node over all 32 fixture pins and all 4 policies found two more below the bar that the
filing never measured: `--ok` (the *strong* rung pill, 3.45:1; and the live badge's green text,
3.33:1) and `--accent` (the `policy` pill — 4.32:1 in light and **2.97:1 in dark** — and the same
token is the link colour, 4.32:1 as text). Stopping at the two named tokens would have shipped a
gate called *"a badge is readable against its own foreground"* that skipped the two badges it would
have failed on, which is exactly what §15 is about. Both took the identical fix, and at three
instances it stopped being three fixes: **a hue that is both a badge fill and a text colour needs a
paired foreground, and the pair — not the hue — is what switches by theme.** `--blocker`,
`--medium` and `--low` need no pair because they are only ever fills. The unknown-severity fallback
(`#888`, 3.54:1 under white — the badge a *hostile* severity lands on) was fixed with them and is
held by its own test, read off the object literal that supplies it.

**Final state, measured in the DOM over every pin and policy in both themes: worst text 4.65:1
(light) / 5.46:1 (dark); worst badge 4.51:1 in both** — which is `blocker`, unchanged, and was
already passing. Every text node and every badge on the page clears 4.5:1.

The gate computes WCAG ratios from the `:root` block and states its limit rather than overselling
it: that is a fact about the declared palette, not a claim about a DOM. It was verified
non-vacuously by planting the old values (5 subtests fail, and they are exactly the right 5) and
again by planting the old `--ok`. The original text is kept below.

### The original finding, kept verbatim

Found while walking the rendering surface in a browser, and deliberately **not** fixed in that
scope: it is one palette decision affecting every badge and every warning on the page, and the round
that found it was fixing what the page *says*, not what it looks like. Changing `--high` touches
every state at once, which is a change that has to be looked at in both themes on purpose rather
than as a side effect.

### Verified

Measured in Chrome on the light path of `.preview/map.html` (`scripts/preview_map.py`), computing
WCAG contrast from the elements' own computed colours — not from the stylesheet:

- `.warn` amber text (`--high` = `#f08c00`) on the card it sits on: **2.48:1**. WCAG AA wants 4.5:1
  for body text.
- `.rung.weak` badge (white on `#f08c00`): **2.48:1**. AA wants 3:1 for a UI component or large
  text; this is 11px bold.
- `.sev` badge for `low` (white on `--low` = `#868e96`): **2.48:1**. `blocker` is 4.51:1 and
  `medium` 5.02:1, so the palette is not uniformly weak — these two tokens are.

Dark mode is not affected in the same way (the same hues sit on `#1f1f23`), so this is a light-mode
finding specifically, which is why looking at only one theme would have missed it.

### Why it matters

The amber is not decoration: it is the entire mechanism by which *"⚠ relayed with no quote — nothing
here separates it from an invention"* reads as weaker than a green elicited card. The spec permits
the weak rung **on the grounds that it is made visible**, and this is the surface where "visible"
is cashed. A warning nobody can read at a glance is the same failure as a warning nobody prints,
arriving by a different route — and the preview checklist's item 6 says so outright: *"if they look
alike, the fix did not land — presence is not visibility."*

### Done looks like

- `--high` and `--low` given light-mode values that clear 4.5:1 for text and 3:1 for a badge, with
  the dark-mode overrides kept separate (they already are: `@media(prefers-color-scheme:dark)`
  re-declares the palette).
- The ratios asserted where they can be: the colours are constants in `map._TEMPLATE`, so a test can
  parse the `:root` block and compute the ratio without a browser. That is a fact about the
  stylesheet, not a claim about a DOM — state the limit rather than overselling it.

### Prove it

`python scripts/preview_map.py`, open the file in a browser **in light mode**, select the
`Background jobs` pin (transcribed, no quote) and the `Retries` pin (legacy cascade). The amber
warning must read as a warning at a glance, next to the green `role enum drift` card. Chrome's
"auto dark mode for web contents" force-darkens light pages in a dark-themed browser — check
`matchMedia('(prefers-color-scheme: dark)').matches` before trusting a screenshot of either theme.

### Traps

- Do not "fix" it by making the warning bigger or bolder. The finding is contrast, and a heavier
  weight at 2.5:1 is still 2.5:1.
- Do not collapse `--high` and `--blocker`. The severity badge and the rung badge share the token
  today; if a fix has to split them, split them deliberately — the page's whole colour vocabulary is
  four severities plus one warning, and a fifth colour costs the reader more than it buys.

---

## 7. The map renders no `resolution_mode` — **CLOSED 2026-08-06** (ledger v0.19)

**The answer lives in `map.py`'s `MODE` table and `modeLine`, and in the preview fixture's closing
`assign_resolution_modes()` call.** One line, directly under the sub-line, in the page's existing
vocabulary — and the trap was obeyed: only `proposed_default` takes a colour, and it takes it as a
left border rather than as accent-coloured text (`--accent` measured 4.32:1 as text in light mode,
so a new 12px text element in it would have re-committed §6 while closing it).

- `proposed_default` → *⏳ if you say nothing, the interview settles this with the proposed answer —
  here, silence IS the answer.*
- `asked` → *this one must be ASKED: no standing rule and no proposed default may settle it for you.*
- `policy_default` → *a standing rule may settle this one on your behalf — the rule, and how you
  elected it, are on its own card.*

The line is suppressed on a settled pin, because there the mode is history and *"a rule may settle
this without you"* over an answered question is v0.18's own finding one surface over.

**The fixture gap the section named is closed twice over.** Nothing in it called
`assign_resolution_modes`, so `proposed_default` existed on no pin and the state could not be seen in
a browser; it is now called last, so it fills only what the blocks above left absent. And a second
gap the section did not name: with the settled-pin suppression, `policy_default` became unreachable
too — `apply_policy` writes that mode in the same breath as the decision, so on a ledger this runtime
wrote it only ever sits on a settled pin. That clause fires only on a file we did not write, which is
stated at the site, and the fixture carries a hand-composed pin in exactly that shape so the sentence
is looked at rather than assumed. `test_the_fixture_carries_all_three_resolution_modes` asserts all
three on OPEN pins for that reason.

Verified in a browser, light and dark: `Config: files or flags` shows the countdown, `Secrets: env
vars or a manager` says it must be asked, `Cache eviction policy` shows the standing-rule sentence,
and `Validation lives in the handler` (decided, `policy_default`) shows nothing at all.

### The original finding, kept verbatim

### Verified

`resolution_mode` (`asked` · `policy_default` · `proposed_default`) is written by six sites, read by
`interview_view` and `unasked_verdict`, projected into `AGENTS.md` nowhere and rendered by
`src/runtime/map.py` nowhere. Confirmed by reading the template: the string does not occur in it.

> **Amended 2026-08-06 by §12's close, which is the half of this that was about the write.** The
> writers of `"asked"` are now enumerated by AST set equality with a declared reason each
> (`test_invariants.py::TestAMarkWithNoClearingDoorIsWrittenForAStandingReason`) — **seven**, and
> the seventh is `interview.expand_catalog`, which this count missed because it is not in
> `ledger.py`. Nothing about the missing reader changed: still projected nowhere, still rendered
> nowhere, and the fixture still carries no `proposed_default` pin. Read that list before building
> the sub-line — it is the vocabulary a reader would be shown.

Two of its three values are the reader-facing ones. `proposed_default` means *this pin will be
settled with the proposed answer unless you object* — the funnel's whole compression argument — and
on the map that pin is a row saying `needs_input`, identical to one nobody will settle without
asking. `asked` means the opposite: *this one may not be defaulted by anybody*, which is what v0.16
added `must_be_asked` for.

### Why it matters

It is the same shape as the gap this round closed one level up: a state the ledger tracks, that
changes what a reader should do, on a surface that shows every neighbouring field. The map already
renders `state`, `substate`, `severity`, `kind` and the whole decision card — `resolution_mode` is
the one field of the envelope that a human reading the page cannot see, and it is the field that
says whether their silence will be taken as an answer.

### Done looks like

- The sub-line (or the row) distinguishes the three, in the page's existing vocabulary — a
  proposed default is not a warning, it is a countdown.
- The preview fixture carries one of each: today it carries none with `proposed_default`, because
  nothing in it calls `assign_resolution_modes`, which is also why the browser walk could not see
  this state at all. A fixture that cannot show a state cannot check it.

### Prove it

Build a fixture pin through `interview.funnel` (which calls `assign_resolution_modes`), render, and
read the row without opening the JSON: it must say whether an unanswered question will be defaulted.

### Traps

- Do not badge all three. Only `proposed_default` changes what a reader must do *now*; badging
  `policy_default` duplicates the decision card, and badging `asked` decorates the common case.

---

## 8. The `verification` envelope reaches no surface — **CLOSED 2026-08-06** (ledger v0.19)

**The answer lives in `map.py`'s `verificationCard` (with `VRUNG` / `vrungInfo`) and in
`interview.funnel`'s `blocked_by` key.** Closed as one instance of §14's class rather than on its
own, which is what that section asked for.

The card reuses the rung vocabulary and its colours rather than inventing a second, exactly as the
section's trap demands — but the *values* are their own closed set, because `VERIFICATION_RUNGS`
answers *how hard was the work checked* and `DECISION_EVIDENCE` answers *how did the human's answer
travel*. Two tests hold it: the keys against `ledger.VERIFICATION_RUNGS`, and the ones the page
colours `strong` against `ledger._CLOSING_RUNGS` — so the two rungs a pin may close on cannot drift
from the two this page shows as solid.

Both halves of *why will this pin not close* are now on the page, in the two carriers the predicate
actually reads: `⚠ this pin cannot close: <blocked_by>` from the envelope, and `⚠ N of M done — this
pin cannot be resolved until every item is` from `remediation`. Absence is rendered as the weakest
rung and says so, matching what `settlement_verdict` now does with it.

No field was added and the overwrite was not restored in a softer form: `blocked_by` travels to the
funnel as **its own key beside the prompt**, so the human's `question.options[].id` is untouched.

Verified in a browser (light and dark) on `.preview/map.html`: the `Webhook signature` pin states
what blocked verification and that 0 of 1 remediation items are done; `The rate limiter counted
retries` states the observation that earned `resolved`; `Export streams the whole table` states 0 of
2. Three cards, one vocabulary.

### The original finding, kept verbatim

Found while removing `mark_correctness_unknown`'s question overwrite, and deliberately not fixed in
that scope: the fix was a deletion, and this is a missing reader. Recorded rather than bundled,
because bundling a reader into a deletion round is how the last six rounds each ended with one more
surface than they started with.

> **Its twin was closed 2026-08-06, and the shape of that fix is the template for this one.**
> `cross_derivations` — written by the same round, by the door one method over, and argued for in a
> comment that said *"the human sees what disagreed"* — had one writer and zero readers in exactly
> the same way. `src/runtime/map.py` now renders it as a card immediately above the pin's question,
> in the colour vocabulary the page already has for how hard a claim was checked (agreement green
> like an elicited decision, disagreement amber on `--warnbg` like an unquoted relay), and the spec
> section was corrected where it still claimed both derivations become the pin's options. Verified in
> a browser on `.preview/map.html`, fixture item 18. **When this gap is closed, reuse that card's
> vocabulary rather than inventing a second one** — that is the trap this section already names, and
> the twin is now the worked example of obeying it.
>
> One thing that fix deliberately did **not** do, and this one should not either: it added no gate.
> `scripts/check_schema_fields.py` passed both fields the whole time — see §15.
>
> **2026-08-06 raises its priority: the envelope is now read on every resolve, not only a weak one.**
> `settlement_verdict` used to consult it `if verification is not None`, so a pin with no envelope
> closed green — including one whose state declared its own correctness unestablishable. Absence now
> reads as the weakest rung, which means `verification` is the field that decides whether ANY pin may
> close. A field with that much authority, written by three doors, gated on by the predicate, and
> rendered on no surface, is this section's claim with a bigger number attached: the reader who has to
> ask *why will this pin not close* has nowhere to look but the JSON.

### Verified

`verification` — `determinism`, `rung`, `attempted`, `blocked_by` — is written by `resolve`,
`mark_correctness_unknown` and `cross_derive`, read by `settlement_verdict` (it is what decides
whether a pin may close), and rendered by nothing. `grep -rn "blocked_by" src/` outside
`ledger.py` and the spec returns only the two MCP signatures that *accept* it;
`src/runtime/map.py` does not contain the string `verification` at all, and `interview.funnel`
builds each entry from `title` / `severity` / `question.prompt` / `downstream`.

Until this commit `blocked_by` did reach two surfaces — the funnel's `prompt` and the map's
*Interview question* card — but only by being pasted into `pin["question"]`, i.e. **by deleting the
human's own fork**, which is the defect that was just removed. So the reach was never the envelope's;
it was borrowed from the field it was overwriting.

### Why it matters

`correctness_unknown` exists to say *the work was done and nobody could establish it was right*, and
the one sentence that makes such a pin actionable is **what blocked verification**. A reader of the
map sees the state and the original question; the reason sits in the JSON. `attempted` is the same
shape one field over: it is the evidence that the state was earned rather than shrugged, and it is
the exact thing a reviewer would check.

### Done looks like

- The map's pin body renders the envelope where it exists: the rung (it already has a rung
  vocabulary and colour for decisions — reuse it, do not invent a second), what was attempted, and
  `blocked_by` in full.
- `interview.funnel` carries `blocked_by` on the entry for a `correctness_unknown` pin, so the
  question an agent is told to ask arrives with the reason attached. The pin is already sorted to
  the top when it is a `blocker`/`high`; arriving at the top with no reason is what wastes that.

### Prove it

Render `scripts/preview_map.py` and read the `correctness_unknown` pin without opening the JSON: the
page must say what blocked verification. Then do the same for a pin that carried its own fork — the
one this commit stopped overwriting — and check that both the human's question and the reason are
there.

### Traps

- Do not restore the overwrite in a softer form (appending options, editing the prompt).
  `question.options[].id` is the carrier the offered-options rule anchors on at both doors; a
  surface problem is fixed in the surface.
- Do not add a field. `blocked_by` is already stored, already required, and already refused when
  blank — what is missing is a reader, and the last six rounds are a record of what happens when a
  missing reader is answered with a new writer.

---

## 9. A policy scope naming a null-valued optional field is still a universal selector — **CLOSED 2026-08-06** (ledger v0.18)

**The preview says what the matcher did: `policy_preview` returns `scope_note`.** Non-empty exactly
when a scope value is `null` — *"this scope selects by ABSENCE: it matches every pin that carries no
value for `cluster_id` — 3 of 4"* — and empty otherwise, so the common message is unchanged. Built
in the matcher's own function, counted with the matcher's own comparison (`== None`, which is what
admits the pin; `to_be` and `question` are explicit nulls, so a key-presence check would have been a
second implementation that disagrees on exactly those fields), and therefore returned by
`apply_policy` too, since that is the same call.

Not refused, and the section's own two branches decided it: a refusal would have had to say how to
express *the pins in no cluster*, and there is no other way to express it — that is the wall the
section's Prove-it warned against. Not given an operator either (`{"$exists": false}`), for the
reason its Traps give. Its readers are named rather than assumed: `policy_prompt` and `record_policy`
spread the radius, and `mcp/server.py::ledger_record_policy` puts the note in the **elicited
message**, above the pin counts, because that is the surface a human reads before electing.

Verified over real `uv run --script` stdio against `plugins/keel-core/mcp/server.py` from a foreign
cwd: `{"cluster_id": null}` → `would_decide` the 3 unclustered pins with the note; `{"cluster_id":
"cl_one"}` → 1 pin, note `""`; `{"nope": null}` → v0.16's refusal, untouched. Tests:
`test_ledger.py::TestARuleIsTrueOfTheThingItIsPrintedOn`, first four.

<details><summary>The original report, kept verbatim</summary>

v0.16 closed the **typo** case (`applies_to={"nope": null}` matched every pin, because
`pin.get("nope") == None` is true of all of them) by requiring every scope key to be a member of
`ledger.PIN_FIELDS`. That closed one instance. The class is wider: most `Pin` fields are **optional**,
so a scope naming a real one with a `null` value still selects every pin that does not carry it.

### Verified

Three `design_concern` pins, one of them given a `cluster_id`, and one preview:

```
policy_preview(applies_to={"cluster_id": None}, default_outcome="keep")
  -> would_decide: ["pin_0002", "pin_0003"]        # every pin WITHOUT a cluster_id
```

`cluster_id` is in `PIN_FIELDS`, so the v0.16 check passes it. The matcher is
`all(pin.get(k) == v for k, v in applies_to.items())` (`ledger.py`, `policy_preview`), and `None` is
what `.get` returns for an absent key — so "scope this rule to the pins in no cluster" and "scope
this rule to everything" are the same expression.

### Why it matters

The radius is what a human is shown before electing a standing rule, and a policy cascades an
outcome onto every pin in it. The v0.16 note in `ledger.py` states the danger in its own words —
*"a universal selector wearing a filter's clothes, and the preview a human elects a policy from
showed the whole ledger as its radius"*. That sentence is still true of this case; only the spelling
of the key changed.

Not urgent in the way §12 is: the human sees the radius in `policy_preview` before electing, so this
is a foot-gun rather than a silent write. It matters because the preview is exactly what makes the
election legitimate, and a scope that reads as narrow while selecting broadly is the one input to
that preview a reader cannot check by looking at it.

### Done looks like

- A scope key with a `null` value is either **refused** at `add_policy`/`policy_preview` — with a
  message that says how to express "the pins with no cluster" if that is genuinely wanted — or it is
  accepted and the preview **says so in words**: *"this scope matches every pin that does not carry
  `cluster_id` — N of M."*
- Whichever is chosen, one implementation, in the module that owns the matcher. Both surfaces that
  show a radius (`policy_preview` and `apply_policy`, which returns the same shape by construction)
  must agree, and by construction they will if the rule lives in the matcher.

### Prove it

Build a ledger where most pins lack the field, elect a policy scoped to it with `null`, and read the
radius as a human would: it must not be possible to believe the rule is narrow. Then do the same for
a scope where `null` is the intended meaning, and check the message is not a wall.

### Traps

- Do not "fix" it by adding a sentinel for "absent" (`"__missing__"`, `{"$exists": false}`). That is
  a query language arriving one operator at a time, and the scope is deliberately a flat equality
  match so that a human can read it.
- Do not widen `PIN_FIELDS` into an allowlist of *required* fields. Optionality is correct; the
  problem is that equality against `None` conflates two questions.

</details>

---

## 10. Nothing can give an existing pin a question — **CLOSED 2026-08-06** (ledger v0.17)

**The door is `mcp:ledger_set_question`, and the section's own warning decided its shape.** It is
write-if-absent — a pin that already poses a fork is refused, because `question.options[].id` is the
carrier the offered-options rule anchors on at both election doors and replacing it is an agent
deciding what the human may choose from. Verified over stdio on the shipped tree: `ledger_add_pin`
with no question → `detected`, absent from `interview_next`; `ledger_set_question` → `needs_input`,
present in the funnel; a second call → refused.

**The trap got a carrier rather than a docstring.** "Do not solve it by having the agent compose the
fork silently" is enforced by requiring `allow_freeform: true` on any fork composed after the fact:
the options become a suggestion and the human's own words stay a legal outcome
(`record_decision(option_id="freeform")`). A closed menu written by an agent is refused.

**One thing deliberately not done:** it does **not** append `provenance: agent_assumption`, which
this section suggested. `add_pin` couples that source to the pin's `confidence`
(`inferred|ambiguous` required), so appending it afterwards would manufacture exactly the
combination that door refuses — one rule, two doors, two answers, the shape v0.14–v0.16 were spent
removing. `confidence` describes how the pin's `as_is` was established; composing a fork later says
nothing about that.

**The state move is scoped to where it was blocking:** `detected` → `needs_input`, and nothing else.
The old body forced `needs_input` unconditionally, which this section flagged as wrong for a
`correctness_unknown` pin (already in the view on its state alone, and the envelope is what says
why). A `CLOSED_STATES` pin is refused outright and pointed at `reopen`.

**The alternative was considered and rejected**, since the section asked for a decision rather than
both options left open: making `question` *required* on the kinds that must reach the interview
would refuse the honest case this exists for — a Phase-1 finder who knows there is a fork and not
yet what it is. A required field there produces an invented fork, which is worse than a late one.

### The original report, kept as the record

### Verified

`question` is settable only at creation (`ledger_add_pin(question=…)`). No MCP tool assigns
`pin["question"]` afterwards — `grep 'pin\["question"\]' src/mcp/tools.py` is empty. Reproduced:

```
add_pin(kind="ambiguity", severity="high", …)   with no question
  -> state "detected", question None
  -> interview_view(): []
```

So a finding recorded without a fork is `detected` for ever and reaches the interview on no host.
The only way out is to hand-edit `ledger.json`, which every playbook forbids, or to add a second pin
and abandon the first.

**Inside the runtime there are four writers, not three, and the fourth is the interesting one.**
This section said "exactly three writers, all of them side effects of something else" and named
`surface_assumption` (creating a pin), `mark_correctness_unknown` and `cross_derive` (both now
write-if-absent). The fourth is **`Ledger.set_question`** (`src/runtime/ledger.py:582`) — not a side
effect of anything: it takes a pin id and a question, validates it, assigns it and moves the pin to
`needs_input`. It has **zero callers** in shipped code (`grep -rn set_question src/ plugins/` returns
its own definition and the vendored copy), and it was exempted in `tests/test_invariants.py` as
*"the interview funnel writes it (interview_next drives the surface)"* — false; `interview.funnel`
reads. The exemption is corrected to say what is true, in the same commit as this line: a gate that
has been asked and answered wrongly is §15's class, and a register carrying a miscount is that class
applied to the register.

**The conclusion survives, and gets cheaper.** The section's claim is about the *product*, not the
runtime: MCP is the only runtime channel on all four hosts, no tool reaches this method, so no
agent on any host can give an existing pin a question. That is unchanged. What changes is the size
of the fix — the runtime half already exists and is written the way this section asks (it refuses a
`resolved` pin, and `_validate_question` already guards the shape), so closing §10 is exposing a
method rather than writing one. Two things about it still have to be decided rather than inherited:
it **replaces** an existing question, which "Done looks like" below forbids, and the state it forces
(`needs_input`) is wrong for a `correctness_unknown` pin. Both are one-line answers at the door.

### Why it matters

`ledger_add_pin` is the tool every Phase-1 finding goes through, and its `question` argument is
optional — reasonably, since a finder is not always the person who knows what the fork is. The whole
funnel then runs on `question`: `interview_view` selects on it, `interview.funnel` builds its entries
from `question.prompt`, and `record_decision` refuses an outcome the question does not offer. A pin
with no question is therefore invisible to the machinery whose entire job is to put it to a human.

It is the same shape as §5 one level down: a state the runtime can produce and the product cannot
leave.

### Done looks like

- A door that gives an existing pin its fork. It is **not** an election — posing a question decides
  nothing — so it needs no quote and no offered option, which is what makes it safe to expose.
- It must refuse to **replace** an existing question. That is the invariant v0.16 spent two fixes
  building (`question.options[].id` is what the offered-options rule anchors on at both doors), and a
  general-purpose question setter is exactly the way to dismantle it from the side. Write-if-absent,
  the same rule `mark_correctness_unknown` and `cross_derive` were both corrected to.
- Alternatively, and cheaper: make `question` **required** on the kinds that must reach the
  interview. That trades a door for a stricter write, and it is a legitimate answer — but decide it,
  do not leave both open.

### Prove it

Over real `uv run --script` stdio: `ledger_add_pin` with no question, then `interview_next`. The pin
must appear. If it does not, name the tool call that makes it appear; if there is none, the
capability does not exist on any host, whatever the runtime can do.

### Traps

- Do not let the new door take an `outcome`, a `default`, or anything that reads as an answer.
- Do not solve it by having the agent compose the fork silently. The menu is what the human is
  allowed to choose from; an agent authoring one without saying so is `provenance:
  agent_assumption` territory (`src/core/assumptions.md`), and it should be recorded as such.

---

## 11. The `correctness_unknown` fork offers an outcome it cannot produce — **CLOSED 2026-08-06** (ledger v0.18)

**The wording is corrected, and it is corrected by being computed.** `Ledger._accept_implication(pin)`
asks `settlement_verdict(pin, "accept")` — the authority the section named, one call away — so the
sentence cannot drift from the door a second time. On a kind the door refuses it reads *"the risk
becomes the recorded decision and the pin becomes `decided` — leaving-as-is closes a design_concern
and nothing else, so a defect cannot reach `accepted` from here"*; where the door opens it says
`accepted`, and names `accept_as_is` as what gets it there. That is the section's own preferred
branch (*correct the wording*) and its own parenthetical (*choosing it records a decision; the pin
becomes `decided`*), not a third answer.

Neither trap was taken: `accept`'s kind rule is untouched, and the fork is still generated
write-if-absent, so v0.16's rule that an agent may not replace a human's menu holds.

Verified over stdio on the shipped tree: a defect walked `add_pin → add_remediation → done →
mark_correctness_unknown` carries the refusing implication, and `ledger_record_decision(option_id=
"accept")` on it returns `state: "decided"` — the sentence and the state now agree. The
`design_concern` half was measured on the same session and confirms v0.16's other rule instead: it
reached the state from `decided`, so it kept its own `['keep']` fork and no menu was generated over
it, which is the second half of what the section verified.

<details><summary>The original report, kept verbatim</summary>

### Verified

`mark_correctness_unknown` writes a five-option fork whose last option is

```json
{"id": "accept", "label": "Accept the risk, unknown named",
 "implication": "state becomes accepted, with the unverified remainder recorded"}
```

The implication is false wherever the option is offered, and the two halves of that were measured
separately:

- **On a `defect`** — the kind that reaches `correctness_unknown` without a decision, and therefore
  the kind that most often carries this generated fork — `settlement_verdict(pin, "accept")` returns
  **`wrong_kind`**: leaving-as-is is the resolution of a `design_concern` and of nothing else.
  Measured on a defect that had just been marked: its options are exactly
  `['retry','add_check','takeover','narrow','accept']`, and `accept` is refused.
- **On a `design_concern`**, `accept` *is* allowed (`would_settle`, measured). But a non-defect
  reaches `correctness_unknown` only from `decided`, and a pin that was decided already carried the
  human's fork — which v0.16 stopped overwriting. Measured: its options are `['keep']`. So the
  generated menu was never written on the pin where its promise holds.

Both directions verified in one run. The option is offered **exactly on the pins where its stated
outcome is refused**, and absent from the pins where it would work.

### Why it matters

Low severity and easy to under-rate, which is why it is written down. The offered-options rule is the
package's strongest single invariant: an agent may record only an outcome the pin's own question
offered. That makes the option list a **promise about what can happen**, not a list of suggestions —
and an option whose implication the machinery refuses turns the promise into decoration on the one
pin kind where the reader is already told "we could not establish this is right".

### Done looks like

- Either the option's implication says what actually happens (choosing it records a decision; the
  pin becomes `decided`, and `accept`'s kind rule still governs whether it can then be closed), or
  the option is dropped from the generated fork for kinds that cannot take it.
- Prefer correcting the wording: the option itself is a reasonable thing for a human to want.
- Whichever, the sentence must be true of the pin it is printed on — `settlement_verdict` is the
  authority and it is one call away.

### Prove it

Mark a defect `correctness_unknown` over real stdio, record the `accept` outcome, and read the pin's
state. Then do the same on a `design_concern` that had no prior fork. The implication printed must
match both.

### Traps

- Do not loosen `accept`'s kind rule to make the sentence true. That rule is load-bearing and was
  moved into `settlement_verdict` precisely so it could stop being re-litigated at the door.
- Do not delete the whole generated fork. It is what makes the state actionable at all, and the
  write-if-absent guard already keeps it away from the human's own menu.

</details>

---

## 12. `resolution_mode: "asked"` is permanent, and any policy can set it — **CLOSED 2026-08-06** (ledger v0.18)

**The cheapest correct version, taken as written: the `not_offered` branch no longer writes the
mark.** `STANDING_REFUSALS = ("held_back", "must_be_asked")` declares which unasked refusals are a
standing property of the **pin**, and both writes that settle a pin nobody was shown read it —
`Ledger.apply_policy` and `interview.expand_catalog`. The second is the part the section did not
report: the brief door had the identical defect for the identical reason, its `verdict !=
"would_decide"` sweeping `not_offered` in with the threshold, so one word in a project brief that a
fork did not offer marked that fork permanently un-cascadable. Closing one and not the other would
have left the rule false at the door next to it, which is this register's own recurring finding.

Both traps held. **No door clears `resolution_mode`** — the fix is entirely at the writer — and
§7 is untouched. The enumeration is now enforced rather than described:
`test_invariants.py::TestAMarkWithNoClearingDoorIsWrittenForAStandingReason` asserts by AST **set
equality** that the seven writers of `"asked"` are exactly the seven declared, each with the reason
it is a standing property, and a second test asserts that nothing anywhere `del`s or `pop`s the
field. Both were verified by planting: an eighth writer and a clearing door each fail the gate.
The two remaining readers of `STANDING_REFUSALS` are asserted to be exactly the two doors.

Verified over stdio on the shipped tree: `ledger_record_policy(default_outcome="zzz")` cascades
nothing and returns all four pins in `not_offered`; the next policy — `default_outcome="db"`, which
their forks do offer — cascades all four, with `must_be_asked` empty. Before v0.18 the second call
returned all four as `must_be_asked`, for ever.

**The residual, stated rather than repaired.** A ledger written by v0.12–v0.17 may carry `asked` on
a pin marked only for this reason, and **nothing can tell it from a standing demand**: the stamp
recorded no reason, so no reader can recover one, and reconstructing it from the policies still in
the file would be the heuristic this repo forbids. Those pins stay open and stay in the funnel; what
they have lost is the chance of being cascaded, which is the behaviour they were written under. The
version floor is deliberately not raised against them either — `nonconforming` replays rules
decidable **from the event alone**, and this one is decidable from nothing.

<details><summary>The original report, kept verbatim</summary>

### Verified

`apply_policy` marks every pin it did **not** decide:

```python
for pin_id in radius["held_back"] + radius["must_be_asked"] + radius["not_offered"]:
    self.pin(pin_id)["resolution_mode"] = "asked"
```

`not_offered` is in that list — i.e. a pin is marked "must be asked" because *some other rule's*
outcome was not on its menu. Nothing clears it: seven writers of `resolution_mode` in `ledger.py`,
six of which write `"asked"`, and `assign_resolution_modes` only fills the field where it is
**absent**. Reproduced end to end:

```
medium open_decision, options {a, b}
apply_policy(rule with default_outcome "zzz")   -> not_offered -> resolution_mode "asked"
apply_policy(rule with default_outcome "a")     -> must_be_asked      # refused for ever
```

The second policy is the *correct* one for that pin, its outcome is on the menu, and the pin's
severity (`medium`) is below the never-silent threshold. It is still refused, because an unrelated
rule touched it once.

### Why it matters

`must_be_asked` is a real and good invariant — v0.16 added it because two writers of `"asked"` were
carrying the assertion *"a reopened truth is never re-defaulted silently"* as a comment while a
cascade re-defaulted them anyway. The problem is that the mark is now applied for a **fourth**
reason that carries no such assertion. `not_offered` says "this rule does not fit this pin", which
is a fact about the rule; recording it on the pin makes it a permanent property of the pin.

The compounding cost is the funnel's whole reason for existing: the medium/low long tail is what
`proposed_default` compresses. A ledger where an early, badly-scoped policy touched many pins is a
ledger where the compression quietly stopped working, and nothing reports it — see §7, which is why
nobody would notice.

### Done looks like

- Separate "this pin demands to be asked" (reopened, contested, surfaced assumption, above the
  threshold — all standing properties) from "the last policy did not fit" (a fact about that policy).
  The cheapest correct version is to stop writing `"asked"` on the `not_offered` branch: the pin is
  already un-decided and already open, so the mark adds nothing except permanence.
- If a clearing path is wanted instead, it belongs where the reason ends — but note the trap below.

### Prove it

The reproduction above, over real stdio: elect a policy whose outcome one pin does not offer, then
elect the policy that fits it. The second must decide it (or must refuse it for a reason that is
about *that* pin).

### Traps

- Do not add a tool that clears `resolution_mode`. A door that unsets "this must be asked" is a door
  that can silence the threshold rule, and it would be reachable by an agent. Fix the writer.
- Do not merge this with §7. §7 is that the field reaches no reader; this is that the field is
  written wrongly. Fixing either alone leaves the other, and fixing §7 first would at least make
  this one visible.

</details>

---

## 13. The map inlines raw U+2028 / U+2029 into its own script — **CLOSED 2026-08-06** (ledger v0.19)

**The answer lives in `map._SCRIPT_UNSAFE` and in
`tests/test_map.py::TestTheOnlyWayDataEntersThePage`.** They are escaped — the section allowed
either escaping or a stated omission, and escaping costs nothing (an escaped U+2028 inside a JSON
string is the same character, so the existing round-trip assertion covers them for free).

The fix is deliberately **structural, not a third `.replace()` at the site**, because this file has
been wrong about escaping twice and both times the bug was a site that did not go through the
mechanism. `_inline`'s claim — *"not a longer list of dangerous sequences, it is the character all
of them need"* — was true of the HTML hole and silent about the JavaScript one, so the table now
names **one character per hole** and says which hole each closes. What makes that enumeration worth
anything is the other half: two AST tests assert that `json.dumps` is called in exactly one function
in the module, and that **every** substitution in `render`'s dict except the three declared
non-payloads is produced by `_inline`. The previous shape of that second test named the four
payloads that existed when it was written; it is an exclusion list now, which is why adding
`__REOPENED__` in this same change was covered by default instead of when someone remembered.

Recorded at the strength the section set: this is a stated discipline being made whole, not an
observed breakage. A page carrying both raw was opened in Chromium and there was no failure, because
ES2019's JSON-superset proposal made them legal in string literals. `ensure_ascii=True` was not
taken, for the reason the trap gives.

Verified in a browser: the preview fixture carries a pin titled `line ␤ sep ␤ para`, the characters
round-trip into `LEDGER` intact (code points `2028` / `2029` read back off the parsed payload), the
raw characters appear nowhere inside the `<script>` element, and the console is empty.

### The original finding, kept verbatim

### Verified

`map._inline` is `json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")`. The `<` escape is
deliberate and documented at length; U+2028 (LINE SEPARATOR) and U+2029 (PARAGRAPH SEPARATOR) are
not escaped, and they are **statement terminators in pre-ES2019 JavaScript** while being legal
inside a JSON string — the classic JSON-is-not-a-JS-subset hole.

Measured, both halves:

- A pin titled `"line <U+2028> sep <U+2029> para"` renders with **both characters raw** in the page.
- The resulting page was **opened in Chromium**: `LEDGER` is defined, the title round-trips
  intact, the list renders, and the console is empty. So on a current engine — the ES2019
  JSON-superset proposal made both characters legal in string literals — there is no failure.

Recorded at that strength deliberately: this is a **stated discipline with a hole in it**, not an
observed breakage. The file's own docstring says the escape *"is not a longer list of dangerous
sequences — it is the character all of them need"*, and that sentence is true of `<` and not of
these two.

### Why it matters

The map is handed to people and opened in whatever they have. The consequence is bounded and the
likelihood is low, and both are stated here so nobody re-derives them at higher cost later. What
makes it worth writing down at all is the reasoning, not the risk: the module argues that one
character covers the class, and the class has two more members that the argument does not reach.

### Done looks like

- Two more `.replace()` calls, or a note in `_inline`'s docstring saying these two are knowingly left
  raw and why. Either is fine. An unstated omission is not.
- If they are escaped, the round-trip assertion that already exists for `<`
  (`test_the_data_survives_the_escape_intact`) covers them for free — an escaped U+2028 in a JSON string is
  the same character.

### Prove it

Render a pin whose title carries both characters and `json.loads` the inlined literal back: the
value must be unchanged. Then open the page — that is the half that says whether it ever mattered.

### Traps

- Do not turn `ensure_ascii=False` on its head and escape everything. The ledger is full of
  non-ASCII prose (the preview fixture is largely Italian) and `ensure_ascii=True` would triple the
  page for no reader.

---

## 14. Five more pin fields, and four of five log kinds, reach the map nowhere — **CLOSED 2026-08-06** (ledger v0.19)

**The answer lives in `map.py`'s card stack and its `TRAIL` table, and the architecture is stated
once in a comment above them.** The section asked for *one change, not five*, and the choice made —
recorded here because it is the part worth arguing with — is: **the detail pane is a fixed stack of
cards in the order a reader asks the questions, each answering `''` when its field is absent.**

```
what is it        as-is / to-be         how it may die    premortem
how hard checked  verification (§8)     how it got here   the trail
who else checked  cross_derivations     what is asked     question + resolution (§7)
what was proposed brainstorm            where it lives    anchors
what was elected  decision              can it land       readiness
what will be done remediation
```

`premortem` and `readiness` are rendered rather than omitted, and the section explicitly allowed
either. They earn the page because each answers a question a reader of a pin actually has — *can the
ground bear this* and *what did we already decide would kill it* — with a closed verdict vocabulary
the page can colour honestly. Nothing is dumped: the trap is obeyed, `sideCard`'s `raw` already
exists for the free-form payloads, and everything else is projected because a projection is a claim
about what matters.

**The trail was built, and only because §5 is closed.** The section says a timeline is worth
resisting until three of the event kinds are producible on a host; they now are, and the preview
fixture produces all six (`ev_` `stl_` `chl_` `xdr_` `fal_` `rev_`) through the real doors rather
than by hand. `TRAIL`'s keys are held against `ledger.LOG_ENTRY_PREFIXES`, so a seventh kind arrives
rather than being dropped, and an unrecognised entry gets §16's sentence. No schema gate was added —
the section forbids it and §15 says why.

**One defect was found by looking at the rendered page, which is the whole argument for this
procedure.** The trail's decision row read the rung off `e.evidence` while the decision card three
cards up read it through `derived`, so on the pre-v0.11 cascade one page printed *"cascaded from a
policy"* and *"transcribed"* about one event. That is `derived_rungs`' own reason for existing,
re-introduced by a second reader on the same page, within the change that added the reader. Fixed;
the row now goes through `derived` too.

**A second one, in the same spirit:** the decision card describes an *event*, which is a historical
fact, so on a pin since handed back it read `decided → request_id` while the sub-line said
`needs_input (challenged)`. That is §17a's finding on the surface §17a says gets it right. The card
now carries `⚠ this answer is under dispute (<substate>)`, read from `REOPENED` — inlined from
`ledger.REOPENED_SUBSTATES`, not a hand-kept list.

Verified in a browser, light and dark, over every fixture state; `tests/test_map.py::TestTheWholeEnvelopeHasAReader`
holds both halves in CI — the template must reference each field, and the fixture must carry it,
because either alone is vacuous.

### The original finding, kept verbatim

§8 is one instance; this is the rest of the class, listed so a fix can be scoped once instead of
five times.

### Verified

Against `map._TEMPLATE`, by reference (`p.<field>`), not by word search:

```
p.cross_derivations   True    (closed 2026-08-06 — see §8's note)
p.verification        False   (§8)
p.brainstorm          False
p.remediation         False
p.premortem           False
p.readiness           False
p.resolution_mode     False   (§7)
p.evidence            False
```

And on the log: the page reads only entries whose id starts with `ev_`. The four other event kinds
the runtime appends — `stl_` (SettlementEvent), `xdr_` (cross-derivation), `rev_` (reopen), `chl_`
(challenge), `flr_` (failure) — appear in the template nowhere. The whole ledger is inlined, so every
one of them is *in* the page and none of them is *on* it.

### Why it matters

The map is the surface this repo names whenever it asks "where does a human see this" — §1's fix,
§8's, and the twin closed alongside it all landed there. A field the map does not render is a field
whose only reader is `ledger.json`, and the register's opening note is that this is the shape nine of
twelve open gaps share.

Two of these are load-bearing beyond decoration. `remediation` is what `resolve` gates on — a reader
looking at a pin cannot see why it will not close. And the missing `stl_` / `rev_` entries mean the
page can show that a pin is settled but never **how it stopped being open, or that it was ever
un-closed**, which is the exact question v0.16's `SETTLEMENT_DOORS` table was built to answer.

### Done looks like

- One change to the map, not five. Decide the page's information architecture once — the detail pane
  is already a stack of cards and adding five more independently is how a surface acquires five
  vocabularies.
- A timeline for the log is the obvious shape and is worth resisting until §5 is closed: three of the
  four event kinds cannot be produced on any host today, so a timeline built now would be verified
  against fixtures only.
- `premortem` and `readiness` may honestly not belong on this page. Say so in the module docstring if
  that is the conclusion — this file's standard since §1 is that an omission with a reason is fine.

### Prove it

Extend `scripts/preview_map.py` with one pin carrying each, render, and read the page without opening
the JSON. Anything you cannot answer from the page is still on this list.

### Traps

- Do not add a generic "raw pin" dump. `sideCard` already offers `raw` for `as_is`/`to_be`, and the
  reason the rest is projected rather than dumped is that a projection is a claim about what matters.
- Do not add a schema gate for this (see §15). The gate that would catch it is the one that already
  says it cannot.

---

## 15. Two gates check less than their names claim — **OPEN, found 2026-08-06**

The instances differ; the class is one, and it is the worst kind of finding in this repo, because a
gate that has been asked and answered stops anyone asking again. §2's closing note records a third
instance (`test_every_served_tool_is_documented_and_nothing_else_is` filtered its own input, so the
"nothing else is" half could not fire, and a planted row passed green twice).

### Verified

**`tests/test_ledger.py::TestOneWriterForTheSettledStates::test_only_settle_writes_a_settled_state`.**
The class docstring says *"no function may assign a settled state to a pin except `_settle`"*. The
walk collects `ast.Assign` nodes whose target is `pin["state"]` and then requires

```python
if (isinstance(node.value, ast.Constant) and node.value.value in governed):
```

so only a **literal** counts. `pin["state"] = target_state`, `pin["state"] = _STATE_BY_DOOR[door]`,
or any computed value assigns a settled state and is invisible to the gate. Note the same walk is
the model `TestEveryPathToDecideIsGated` follows, so whatever is decided here should be checked
there too.

**`scripts/check_schema_fields.py`.** It concatenates every shipped file into one string and asks
`re.search(rf"\b{name}\b", corpus)`. Its docstring already declares one limit honestly (it cannot
tell a pin's `depends_on` from an item's). The limit it does **not** declare is the one that
matters here: **the writer is in the corpus.** `cross_derivations` and `verification` are named in
`ledger.py` by the methods that write them, so both passed this gate for their entire lives as
write-only fields — the gate whose first line is *"Every field the ledger spec declares must be read
by something that ships."*

### Why it matters

`check_schema_fields.py` is the gate that exists **for** the class that nine of the twelve open gaps
belong to, and it cannot see any of them. That is worth more than the sum of the gaps: as long as it
is green, the register above looks like bad luck rather than an unguarded class.

### Done looks like

- The AST gate: match on the assigned **value's reachable constants** rather than requiring the node
  to be one, or invert it — assert the set of functions that assign `pin["state"]` at all, which is
  small, stable and does not depend on how the value is spelled.
- `check_schema_fields.py`: distinguish a reader from a writer. The cheapest honest version is to
  exclude assignment sites (`pin["x"] = `, `record["x"] = `, `"x":` inside a dict literal being
  built) from the corpus for that field, and to keep declaring whatever it still cannot do — the
  file's existing "honest limit" paragraph is the right precedent and should grow, not shrink.
- If neither is affordable, **weaken the docstrings to what the code checks.** A gate that overstates
  itself is worse than no gate; this is the one change that is never wrong.

### Prove it

Plant the failure and watch it fail — the method that caught §2's third instance. For the AST gate,
add `pin["state"] = _STATE_BY_DOOR[door]` to a method that is not `_settle` and run the test. For the
schema gate, add a field to the spec whose only mention is a write in `ledger.py` and run it.

### Traps

- Do not delete either gate. Both catch real things; they just claim more than they catch.
- Do not answer the schema gate by requiring every field to be named in a playbook. The two-audience
  rule in its docstring (code **or** doctrine) is correct and was arrived at by it failing on two
  correct fields.

---

## 16. An unknown `settles_as` renders as a bare label, while an unknown `rung` gets a warning — **CLOSED 2026-08-06** (ledger v0.19)

**The answer lives in `map.py`'s `unknownNote` and `settlesInfo`.** The trap is obeyed exactly: the
tables are **not** merged — they answer different questions off one event — and what is shared is the
*sentence*. `unknownNote(what, value, consequence)` is the one place the page says it does not know
something, and it now has six callers: the decision rung, the settled state, the verification rung,
the resolution mode, the readiness verdict, and a log entry whose id matches no prefix. Every reader
added in this round was written against it, so §16 closed as a rule rather than as an instance.

The card's `cls` is deliberately untouched by an unknown `settles_as`: the colour is the rung's
answer, and letting a second axis recolour it would be the merge the trap forbids, arriving through
the back.

The gate the section named exists: `SETTLES`' keys are held against `ledger._ELECTION_STATES`, and
the fixture carries an event with `settles_as: "quarantined"` so the browser walk has it to look at.
Verified rendered: *"⚠ this map does not know the settled state `quarantined` — it was most likely
added to the schema after this page was generated, so nothing here says what this election produced
— the pin's own state, in the line under the title, is what the file records."*

### The original finding, kept verbatim

### Verified

The map's decision card carries two closed tables read off the same event. They disagree about what
to do with a value they do not know:

```js
const SETTLES={decided:'decided', accepted:'accepted (left as it is)', deferred:'deferred (not now)'};
… has(SETTLES,settles)?SETTLES[settles]:settles          // bare label, no note
```

versus `rungInfo`, which for an unrecognised rung returns `cls:'weak'` plus *"this map does not know
the rung `x` — it was most likely added to the schema after this page was generated"*. That wording
and that third state were added deliberately (§ the `oracle` fixture pin, preview checklist item 14),
for a condition that is identical here: a schema that grew after the artifact was written.

### Why it matters

Small, and it is here because it is the *residue of a fix*. The rung case was thought through
carefully — three states, not two, because "a rung this page does not know" and "no rung recorded"
cannot both be true of one card. The settlement case, added in the same version, took the older
two-state shape. One page, one condition, two behaviours, and the newer of the two is the
under-considered one.

### Done looks like

- An unknown `settles_as` says it is unknown, in the vocabulary the rung case already uses. Reuse
  `rungInfo`'s wording pattern rather than writing a second sentence for the same idea.
- `tests/test_map.py::TestARungTheTableDoesNotKnow` reads the `RUNG` table's keys and holds them
  against `DECISION_EVIDENCE`. There is no equivalent for `SETTLES`; `ledger._ELECTION_STATES` is the
  tuple it should be held against, and it is the same three values.

### Prove it

Add a fixture pin whose `DecisionEvent` carries a `settles_as` this page does not know (the `oracle`
pin is the worked example one field over), render, and read the card: it must say the value is one
this map cannot describe, not print it as though it were understood.

### Traps

- Do not merge `SETTLES` into `RUNG`. They answer different questions off the same event; the
  vocabulary for *not knowing* is what should be shared, not the tables.

---

## 17. Seven residuals of the final review — **only 17c is OPEN**

Two adversarial reviewers closed the seventh round. Their findings are here rather than fixed,
because the round's rule was that only defects it had *introduced* could be fixed in it — and
because a report dies with its session while this file does not. The four still open are not triaged: each states what
was verified and why it matters, and stops there.

**17a — CLOSED 2026-08-06 (ledger v0.19), and it was three substates rather than one.**
`instructions._pin_line` now appends `*(<substate> — do not build on this answer)*` to a pin whose
outcome is under dispute. Read from **`ledger.REOPENED_SUBSTATES`** and not from the word
`contested`, because fixing only the substate the reviewer happened to see would be §17e's defect
in the same file at the same time: the feedback arc leaves `reopened` and an upheld challenge leaves
`challenged`, and both keep the outcome exactly as `cross_derive` does. The set is composed from
`_SUBSTATE_BY_ARC` rather than re-listed, `decide` clears the substate (so the mark means *disputed
and not re-answered*), and an AST test holds every `pin["substate"]` write in `ledger.py` to it in
both shapes it comes in.

The byte argument, since the region is budgeted: the clause fires on the pins that carry the
substate and on no others, which is what separates it from the per-pin state token the module
refuses. The test it must pass — stated in the module docstring so the next clause has to pass it
too — is *does the default reading of the line without it say something FALSE?* Here it does: the
line asserts an elected answer that is currently contradicted.

The same finding turned out to be true of the MAP, which this section credits with getting it right:
the decision card describes the *event*, so it read `decided → request_id` on a pin whose sub-line
said `needs_input (challenged)`. Fixed there too — see §14. The original finding is kept verbatim.

**17a. `AGENTS.md` prints a `contested` pin's disputed outcome with no marker.** Round 7 deleted
`_pin_line`'s `with_outcome` flag so a `correctness_unknown` pin would stop reaching a fresh agent
as an unanswered question. The same deletion applies to `contested`, where it inverts: a pin put in
`needs_input`/`contested` by `cross_derive(agreement="disagree")` — i.e. because two providers gave
opposite answers — now renders as ``- `pin_0010` [ambiguity] … — **at_least_once**``, formatted
identically to the Settled section's build instruction. `grep -c substate src/runtime/instructions.py`
→ 0. The map distinguishes the two loudly (an amber CROSS-DERIVATION — DISAGREE card, confirmed in a
browser); the one file every host loads unprompted does not. **Why it matters:** the heading forbids
*deciding*, not *building on*, and this is the surface with no reader to ask.

**17b — CLOSED 2026-08-06 (ledger v0.17), and it was worse than reported.** `interview_view` now
selects `brainstorming` too, and each funnel entry carries the proposals, so `core/brainstorm.md`'s
*"its proposals surface back as options on that pin's interview question"* describes the machine for
the first time. But the exit was only half of it: **`add_proposals` is the only writer of the
`brainstorming` state and no MCP tool reached it either**, so the brainstorm could think and could
not write on any host — this section described the way out of a room nobody could enter. The door is
`mcp:ledger_add_proposals`, neutrality unchanged (a proposal carrying a `decision`/`outcome` is
refused; at most one `recommended`). The spec's lifecycle diagram drew a
`brainstorming ──(proposals written)──▶ needs_input` return arrow that nothing implemented; it is
corrected rather than deleted, because the arrow is *why* nobody noticed. The finding below is kept
verbatim.

**17b. A pin in `brainstorming` reaches the interview on no host.** `Ledger.interview_view` selects
only `("needs_input", "correctness_unknown")` (`src/runtime/ledger.py:1699`), so `add_proposals` —
which moves a pin from `needs_input` to `brainstorming` — removes it from the funnel. Verified at the
MCP door on the all-states fixture: `interview_next` omits the brainstorming pin entirely while
`ledger_summary` reports `by_state.brainstorming: 1` and counts it in `open_questions: 5`. Nothing
moves it back — `decide` goes forward, only `cross_derive(disagree)` returns it, and the one method
that would is §10's unreachable `set_question`. **Why it matters:** asking the brainstorm agent for
options is how a hard fork gets help, and doing so is what takes the fork off the agenda.

**17c. Two phase-4 playbooks and rescue's `SKILL.md` still say `resolved` needs two things.** It now
needs three. `src/skills/codebase-rescue/references/phase-4-remediation.md:123`,
`src/skills/greenfield-forge/references/phase-4-build.md:111` and
`src/skills/codebase-rescue/SKILL.md:221` state *"requires BOTH the evidence and a MERGE"*; round 7
made `rung` mandatory on every close (verified over stdio against the shipped server: the same call
is `isError` without it and `{"state":"resolved"}` with `rung="observed"`). Round 7 updated three
other playbooks and missed the two that specify the loop which actually closes pins. **Why it
matters:** it is the signature class — a door tightened, the prose describing it left on the old
rule — and it is recoverable only because the refusal text happens to name the fix. Note while
fixing: `rung` now means two different things inside the same eight-step loop (the ladder rung at
step 4, the verification rung at step 7).

**17d + 17e — CLOSED 2026-08-06 (ledger v0.19), together, because they are one bug seen from two
ends.** The heading was false because the sort key was a literal, and the sort key was a literal
because the schema had no name for the distinction. So the schema got one —
**`ledger.LEAVE_AS_IS_STATES = ("accepted", "deferred")`**, anchored on `_STATE_BY_DOOR` so
membership is the doors' answer — and `_settled_order` is **gone**.

The settled half is now **two sections**, not one section with an ordering trick and a
parenthetical. That is more than the minimum, and the argument is written into the module docstring
rather than left implicit: a single heading cannot be true of both groups, which is this file's own
stated standard for a heading; a reader can then tell WHICH pins are the do-not-build ones without
the per-pin state token the budget refuses, because membership is carried by a heading that costs 2
lines **once** instead of a suffix on every line; and the clip now falls on the do-not-build pins
first, which is strictly better than the ordering hack it replaces. It costs nothing when either
group is empty, since `_section` drops an empty section whole.

17e is closed structurally rather than by a docstring note:
`tests/test_instructions.py::TestNoStateNameIsKeptInThisFile` walks the module's AST and fails on
any string constant equal to a member of `ledger.STATES`, excluding docstrings — with a companion
test that plants one to prove the walk is not looking in the wrong place. Its limit is stated: a
name assembled at runtime would not be seen. Both findings are kept verbatim below.

**17d. The settled heading claims `defer` is the only "do not build" state.** `### Settled — build on
these (`defer` = elected NOT to build, not now)` is followed, in the rendered region, by
``- `pin_0006` [design_concern] ACCEPTED: … — **keep**``. `accept` is defined in
`settlement_verdict` as leaving the concern exactly as it is — the same instruction the parenthetical
claims is unique to `defer` — and `_settled_order` sorts only on `state == "deferred"`, so a
blocker-severity `accepted` pin still outranks an elected `decided` medium under the byte clip. The
argument that moved `deferred` last was not applied one state over.

**17e. `instructions.py` hardcodes the state name `deferred`.** `_settled_order` names it directly,
against the rule the file's own test class asserts
(`tests/test_instructions.py::TestEveryStateReachesTheRegion`: *a set the schema owns cannot be kept
here, because a state added there does not come here*). No gate forbids it, so a fifth settled state
with "do not build" semantics silently gets today's placement. Declared in the function's docstring;
this is the entry that makes it survive the branch.

**17f — CLOSED 2026-08-06 (ledger v0.18).** The parameter is gone; `defer` passes `"transcribed"` to
`decide` itself. The argument is the section's own: there is one path here and it is the relay, so a
default was not a refusal — the next caller passes `elicited` and the library writes it, which is
exactly the write `mcp:ledger_defer` refuses, and the door was the only thing stopping it. `decide`
keeps the parameter, and the test asserts that asymmetry rather than describing it
(`inspect.signature` on both). The tool also stopped restating the rung it passed in: it reads it
back off the event it just appended, so one fact has one carrier. Verified over stdio: `ledger_defer`
advertises five properties and none is `evidence`, and the call returns `evidence: "transcribed"`
from the log. The finding below is kept verbatim.

**17f. `Ledger.defer` still takes `evidence: str = "transcribed"`.** The MCP door refuses a
caller-stated rung (round 6 removed the parameter there, and the advertised schema proves it); the
library layer still accepts one for a path that has no elicitation. Unreachable from any agent today
— `tools.ledger_defer` is the only caller and hardcodes the value — so this is about the next caller,
not this one. Compare `decide`, where the same parameter is legitimate because two paths exist.

**17g — CLOSED 2026-08-06 (ledger v0.18).** Every read in that loop is a `.get`, the dispatch key
included. Skipping in silence was not an option, because the branch directly below it already states
why (*"nothing is hidden by skipping: the same event is already reported by `pre_rule_events`"*), so
`LOG_ENTRY_PREFIXES` declares the six prefixes a log entry may carry and `nonconforming` reports an
entry matching none under **`log_entry_kind`**, named by position because the thing wrong with it is
that it has no name. It is not an `EVENT_RULES` entry and the reason is that table's own membership
question: the rule is about every entry rather than about a DecisionEvent, and `decide` cannot
violate it because `_next_id` composes the id — there is nothing for the writer half to check, and
what it buys is the reader. A recognised entry missing the field its own kind is counted by lands in
`unrecorded`, the answer `decision_rung` already gives one line down. A test holds
`LOG_ENTRY_PREFIXES` to the `_next_id` calls by AST, so a seventh event kind cannot be reported as
corruption by the check that exists to report corruption. The pre-fix crash was **observed, not
assumed**: `git show HEAD:src/runtime/ledger.py` on that file raises `KeyError: 'id'`; the shipped
tree now returns the summary with `pre_rule_events: {"log_entry_kind": 1}` and
`failures_by_class: {"unrecorded": 1}`, and `interview_next` still answers on the same file. The
finding below is kept verbatim.

**17g. A `decision_log` entry with no `id` makes `ledger_summary` die with a bare `KeyError`.**
`Ledger.summary` dispatches on `e["id"].startswith(...)` (`src/runtime/ledger.py`, ~:1742).
Reproduced over stdio on both trees. No version of this package ever wrote that shape, so it is
hand-corruption rather than a legacy file — but round 6 established the principle without that
qualification (*reading a ledger must never be the operation that fails on it*), and `summary` is
what an agent calls **before** acting, on a file it did not write.

**One more, not a defect:** §6 (the 2.48:1 `--high` palette) was **not re-verified** in the final
round. It is the one open gap whose evidence only a browser can produce, and no browser was opened
for it. Treat its measurement as of the day it was filed.

> **Re-verified 2026-08-06, and the caution was right.** A browser was opened, the before/after
> numbers are in §6's closing note, and one of the three filed figures was wrong (`--low` was
> 3.32:1, not 2.48:1) while one whole half was missing (the badge failed in dark mode too). The
> lesson generalises past the palette: **a number nobody re-ran is a claim, and this file's own
> standard applies to its own contents.**

---

## Do not re-litigate

Settled with evidence; re-opening these costs a session and lands where it started.

- **No `ledger_decide`.** An agent may record an election, never make one. The tool refuses an
  outcome the pin's question did not offer, refuses freeform where the question forbids it, and
  refuses a transcribed decision with no quote. That is the invariant now — not the absence of a
  tool, which is what left the human with no door for months. The same holds for
  `ledger_record_policy` one level up: it refuses an offer the catalog never made, an offer restated
  in the caller's words, and a relayed policy with no quote. Removing either door does not restore
  the invariant, it only removes the human.
- **No item-level `depends_on`.** Sequence lives on the pin: global ids, validated on write, levelled
  by `buildloop.waves()`. Removed rather than repaired, and the spec says why.
- **Field-overlap similarity may propose, never decide.** `propose_correspondence` returns
  `status: "proposed"`; only what the human elects goes into
  `reconcile_layers(correspondence=...)`, and from there the diff is deterministic again.
- **No CLI floor.** MCP is the one runtime channel on all four hosts; `uv` is a hard prerequisite.
- **Vendoring stays** — the reason is distribution atomicity, not path resolution. The old
  `relative_escape` / `external_directory` argument was refuted at the consuming functions.
