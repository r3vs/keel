# Open gaps — a plan any session can pick up

Four things left open after v0.5.0 (`22809f0`). Each is stated as: **what was verified**, **why it
matters**, **what done looks like**, and **how to prove it** — because in this repo a change is not
finished when the tests pass, it is finished when the behaviour was observed.

Two of these (1 and 2) were introduced *by the same session that closed four older bugs of the
identical class*. That is the point of writing them down rather than remembering them: this failure
mode is not rare here and it is not careless — it is what happens when you add state and stop at
the layer that stores it.

**Before starting anything below:** read `CLAUDE.md`, then the playbook for whatever you touch.
Work on a branch, one scope per commit, run every gate (`scripts/build.py --check`,
`check_consistency.py`, `verify_pointers.py`, `check_hypotheses.py`, `verify_commands.py`,
`check_schema_fields.py`, `python -m unittest discover -s tests`). `src/` is authored, `plugins/` is
generated — never edit under `plugins/`, run `python scripts/build.py`.

Suggested order: **1 → 2 → 4 → 3**. 1 and 2 are small and self-contained. 4 unblocks trusting the
local suite while doing 3. 3 is research-shaped and may end in "no host supports it", which is a
finding, not a failure.

---

## 1. `evidence` is stored and shown nowhere

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

## 2. The tools the phases need are named by no phase

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

## 3. Elicitation has never met a real host

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

## Do not re-litigate

Settled with evidence; re-opening these costs a session and lands where it started.

- **No `ledger_decide`.** An agent may record an election, never make one. The tool refuses an
  outcome the pin's question did not offer, refuses freeform where the question forbids it, and
  refuses a transcribed decision with no quote. That is the invariant now — not the absence of a
  tool, which is what left the human with no door for months.
- **No item-level `depends_on`.** Sequence lives on the pin: global ids, validated on write, levelled
  by `buildloop.waves()`. Removed rather than repaired, and the spec says why.
- **Field-overlap similarity may propose, never decide.** `propose_correspondence` returns
  `status: "proposed"`; only what the human elects goes into
  `reconcile_layers(correspondence=...)`, and from there the diff is deterministic again.
- **No CLI floor.** MCP is the one runtime channel on all four hosts; `uv` is a hard prerequisite.
- **Vendoring stays** — the reason is distribution atomicity, not path resolution. The old
  `relative_escape` / `external_directory` argument was refuted at the consuming functions.
