# Open gaps — a plan any session can pick up

> **STATUS 2026-08-06: the original four are closed; four are OPEN** — §5 (both reopen arcs are
> reachable by no host), §6 (the map's amber fails contrast in light mode, which is where the weak
> rung is made visible), §7 (`resolution_mode` reaches no reader) and §8 (the `verification`
> envelope reaches no reader either — its `blocked_by` had been borrowing the surface of the
> question it overwrote). §6 and §7 were found by opening the page in a browser, which is the only
> way either could have been. The file stays
> because its value is the record — what was wrong, where the answer now lives, and which sub-claims
> were deliberately left `UNVERIFIED` rather than rounded up. Each section keeps its original text
> and carries a closing note at the top.
>
> | Gap | Closed by | The answer now lives in |
> |---|---|---|
> | 1. `evidence` stored and shown nowhere | `294535a` | `src/runtime/map.py`, `ledger.summary()`, `instructions.py::_evidence_note` |
> | 2. tools named by no phase | `eb9c24c` | both `phase-2-interview.md`, both `modules.json`, gate `scripts/check_tool_carriers.py` |
> | 3. elicitation had never met a real host | this commit | `docs/packaging.md` → *Elicitation — does the host ask the human, or does the agent relay?* |
> | 4. 21 tree-sitter skips | `92d2e17` | `tests/test_treesitter.py::TestASkipIsAClaimAboutOneInterpreter` |
>
> Two residuals are recorded rather than fixed, and both are named in `docs/packaging.md`: a Claude
> Code hook can answer an elicitation *for* the human, so `elicited` means "the agent did not hold
> the value", not "a human was looked in the eye"; and headless `codex exec` declares the capability
> then auto-cancels, so `ledger_record_decision` errors there instead of falling back to the
> transcribed rung. Neither is a bug in what is written down — they are the limits of what the strong
> rung buys, which is the sort of thing this file exists to keep honest.

Four things left open after v0.5.0 (`22809f0`). Each is stated as: **what was verified**, **why it
matters**, **what done looks like**, and **how to prove it** — because in this repo a change is not
finished when the tests pass, it is finished when the behaviour was observed.

Two of these (1 and 2) were introduced *by the same session that closed four older bugs of the
identical class*. That is the point of writing them down rather than remembering them: this failure
mode is not rare here and it is not careless — it is what happens when you add state and stop at
the layer that stores it.

**Before starting anything below:** read `CLAUDE.md`, then the playbook for whatever you touch.
Work on a branch, one scope per commit, and **run every gate — the list is the Commands block in
`CLAUDE.md`, and it is complete against `.github/workflows/ci.yml`.** This line used to enumerate the
gates itself, and the copy was already short by two — `check_tool_carriers.py` and
`run_evals.py --validate`: a second list of the same fact, drifting, in the file that tells a cold
session what "every gate" means. `src/` is authored, `plugins/` is generated — never edit under
`plugins/`, run `python scripts/build.py`.

Suggested order: **1 → 2 → 4 → 3**. 1 and 2 are small and self-contained. 4 unblocks trusting the
local suite while doing 3. 3 is research-shaped and may end in "no host supports it", which is a
finding, not a failure.

> That order was followed, and 3 landed in between the two outcomes it anticipated — two hosts yes,
> two no. Everything from here down is the original report, kept verbatim under its closing note.

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
