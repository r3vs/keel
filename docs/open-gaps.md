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

> **STATUS 2026-08-06.** §1–§4 are **closed**. **§5–§16 are open.**
>
> | # | Open gap | One line |
> |---|---|---|
> | 5 | reopen arcs unreachable | `reopen` and `challenge` have no MCP tool, so no host can un-close a pin |
> | 6 | map palette contrast | `--high` is 2.48:1 in light mode, on the badge that carries the warning |
> | 7 | `resolution_mode` has no reader on the map | the field that says whether silence counts as an answer |
> | 8 | the `verification` envelope has no reader | `blocked_by` / `attempted` are written, gated on, rendered nowhere |
> | 9 | a policy scope on a null-valued optional field is a universal selector | v0.16 closed the typo case, not the class |
> | 10 | no door gives an existing pin a question | a pin created without one is `detected` for ever |
> | 11 | the `correctness_unknown` fork offers an outcome it cannot produce | offered exactly where it is refused |
> | 12 | `resolution_mode: "asked"` is permanent | one unrelated policy puts a pin beyond every later one |
> | 13 | `ensure_ascii=False` emits raw U+2028/U+2029 | a stated escape discipline with a hole in it |
> | 14 | five more pin fields, and four of five log kinds, reach the map nowhere | the class §8 is one instance of |
> | 15 | two gates check less than their names claim | an AST gate that only sees constants; a name-match gate |
> | 16 | an unknown `settles_as` renders as a bare label | its sibling `rung` gets a warning for the same condition |
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
>
> Two residuals of gap 3 are recorded rather than fixed, and both are named in `docs/packaging.md`:
> a Claude Code hook can answer an elicitation *for* the human, so `elicited` means "the agent did
> not hold the value", not "a human was looked in the eye"; and headless `codex exec` declares the
> capability then auto-cancels, so `ledger_record_decision` errors there instead of falling back to
> the transcribed rung. Neither is a bug in what is written down — they are the limits of what the
> strong rung buys, which is the sort of thing this file exists to keep honest.
>
> **The pattern the register makes visible, stated once so each section does not have to.** Nine of
> the twelve open gaps are one shape: *a field, a state or an arc that something WRITES and nothing
> READS.* §5, §7, §8, §10, §14 and half of §11 are all that. It is the repo's signature class
> (`MEMORY.md` → *"the claiming-vs-doing failure"*) at the surface layer rather than the path layer,
> and the reason it keeps recurring is structural: adding a writer is a change inside one module, and
> giving it a reader is a change on somebody else's surface. So the question to ask of any new field
> is not "is it stored" but **"name the surface a human reads it on, and open that surface."**

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

**Suggested order for what is open.** §5 first: it is a missing door, three shipped claims rest on
it, and two other sections (§8's "reopen it first", §12's stuck `asked`) currently point at an arc
nobody can reach. Then §9 and §12, which are rules that mis-fire rather than surfaces that are
missing — they can decide a user's pins wrongly today. Then the reader cluster §7, §8, §14, which is
one afternoon on one file and should be done as **one** change to the map rather than four, because
four separate additions to one surface is how a page acquires four vocabularies. §15 and §16 are
small. §6 is one palette decision that has to be looked at in both themes on purpose. §10, §11 and
§13 are the least urgent and say so in their own sections.

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

## 5. Both reopen arcs are reachable by nobody — **OPEN, found 2026-08-06**

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

## 6. The map's palette fails contrast where it carries the warning — **OPEN, found 2026-08-06**

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

## 7. The map renders no `resolution_mode` — **OPEN, found 2026-08-06**

### Verified

`resolution_mode` (`asked` · `policy_default` · `proposed_default`) is written by six sites, read by
`interview_view` and `unasked_verdict`, projected into `AGENTS.md` nowhere and rendered by
`src/runtime/map.py` nowhere. Confirmed by reading the template: the string does not occur in it.

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

## 8. The `verification` envelope reaches no surface — **OPEN, found 2026-08-06**

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

## 9. A policy scope naming a null-valued optional field is still a universal selector — **OPEN, found 2026-08-06**

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

---

## 10. Nothing can give an existing pin a question — **OPEN, found 2026-08-06**

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

## 11. The `correctness_unknown` fork offers an outcome it cannot produce — **OPEN, found 2026-08-06**

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

---

## 12. `resolution_mode: "asked"` is permanent, and any policy can set it — **OPEN, found 2026-08-06**

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

---

## 13. The map inlines raw U+2028 / U+2029 into its own script — **OPEN, found 2026-08-06**

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

## 14. Five more pin fields, and four of five log kinds, reach the map nowhere — **OPEN, found 2026-08-06**

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

## 16. An unknown `settles_as` renders as a bare label, while an unknown `rung` gets a warning — **OPEN, found 2026-08-06**

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
