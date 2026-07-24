# Agent Roster (shared core) — neutral source of truth

The agent roles both skills run on, defined **once, platform-neutrally**. This file is the source in
the strong sense: the build **derives** each host's adapter from it — Claude Code's
`agents/<role>.md` (via `disallowedTools`, the only deny it has) and opencode's
`agent/<role>.md` (via `permission: {edit: …}`). There is nothing to keep in sync, because there is
no second copy to drift.

That is deliberate, and it is the second attempt. The roster used to be hand-written into each
adapter with a linter checking they matched — and they had already diverged in prose, which
name-and-verb parity could never see. A parity linter is a smell: it says two things should be one
thing, generated. Change a permission **here**, and both hosts change together or the build fails.

## The discipline: serialized writing, parallel reading

Only **one** role writes code — the `executor`, one closed scope at a time. Every other role is
**read-only** and may fan out in parallel. This is the anti-divergence property applied at the
agent level, exactly as the single `ledger.json` applies it at the state level: many readers can
diverge harmlessly (they only propose/verify), one writer cannot. Each role runs in a **fresh
context** and communicates only through the ledger + artifacts on disk — never a shared session.

And the hard rule both skills already enforce: **only the human's committed answer in the
interview elects a decision.** No agent commits. Agents find, propose, build, and verify; the
person decides.

## The roles

| Role | Writes? | Job | Phases |
|------|---------|-----|--------|
| **researcher** | no (read-only) | Comprehension & finding; catalog/threat research; grounding per the knowledge-sources doctrine. Fans out. | rescue P1 · greenfield P1 (frame, threat-model) |
| **brainstorm** | no (proposals only) | Proposes 2–3 options with tradeoffs to `pin.brainstorm.proposals[]`, grounded and cited; never decides. | on-demand · greenfield P2 hard forks |
| **executor** | **yes (the one writer)** | Implements ONE closed scope (a `RemediationItem`/`BuildItem`) via two-track TDD in fresh context; opens a PR; **never merges**. Serialized. | rescue P4 · greenfield P4 build, P6 release |
| **measurer** | no (read-only) | Data/evidence verdict, and the **first** gate on a finished item: kind-specific proof that the gap closed (re-diff to zero drift, mutants killed, behavior reachable, static signal green). Deterministic and cheap. Also evaluates `flip_signal`s in the feedback loop. Never guesses, never writes. | rescue P4 gate → P5 · greenfield P4 gate → P5, P7 evolve |
| **reviewer** | no (read-only) | Adversarial pre-merge **judgment** gate, running *after* the measurer — it reads the recorded evidence and never re-derives it. Two stages: (1) is the oracle satisfied **honestly** — no test-gaming, no special-casing, no criterion met by its letter (the thing evidence cannot see) → (2) code quality. Verdict `MERGE`/`ADJUST`/`REJECT`; ADJUST/REJECT restart the item. A rejection **teaches** (see below). | rescue P4 · greenfield P4 |
| **challenger** | no (challenges only) | Adversarial red-team of the elected **oracle** — the reviewer's upstream twin. The reviewer enforces the `to_be`; the challenger doubts it. Refutes `acceptance_criterion`/`to_be`/`Policy` as unfalsifiable / inconsistent / unsatisfiable / falsely infeasible / resting on an unstated assumption / ignoring fan-out; emits a `ChallengeEvent` that reopens the pin (`challenged`). **The one reopen path at the wave checkpoint.** Neutral: challenges, never decides. | rescue P2→P4 · greenfield P2→P4 |

### Why the gates run in that order, and why each owns one object

The three read-only gates used to overlap enough that two of them ran the same commands on the same
item back to back, and three of them could reopen a pin. Two rules remove the overlap without
removing a gate.

**Deterministic evidence before model judgment.** This is the `static-analysis` doctrine turned on
the roster itself: the `measurer` is T0 and runs a parse, a diff and a test suite; the `reviewer` is
T2 and runs a mind. Spending T2 on a change that does not even close the gap is the same waste as
asking a model what a type-checker already knows. So the measurer gates first, and a failing
evidence gate returns the item to the executor **before** any judgment is spent.

What is left for the reviewer is not a weaker version of the same check — it is the part evidence
structurally cannot reach. The measurer proves *the oracle passes*; the reviewer judges *whether it
passes for the right reason*. A Track-A test satisfied by special-casing its own input, a criterion
met in letter and defeated in spirit, a fix that moves the symptom: all of these are green. That is
a judgment job, and it is why the reviewer is T2.

Consequently **`resolved` needs both**: recorded evidence *and* a `MERGE`. Neither alone is
sufficient, and neither gate re-runs the other's work.

This does not weaken the anti-cheat property it looks adjacent to. The rule that matters is
**independence from the author**: an `acceptance_criterion` the `executor` both writes and codes
against is a target it can build *to*, so the behavior must be re-exercised by a role that did not
write the code, and the executor's self-report is never accepted in its place. The `measurer` is
that role. A `reviewer` reading the measurer's record is reading an *independent* re-execution, not
the author's claim — and running a deterministic check a second time buys nothing, since determinism
means the second run cannot disagree with the first. Deduplicate the mechanical proof; never
deduplicate the judgment.

**One object each, so the reopen path is single.** The `measurer` owns evidence, the `reviewer` owns
the code, the `challenger` owns the oracle. A reviewer that suspects the *decision* rather than the
change does not reopen it — it hands the build evidence to the `challenger`, which already runs at
every wave checkpoint. That is not bureaucracy: refuting an oracle is the **T3** job, and a reviewer
reopening directly would silently perform T3 work at T2 — the half-applied config this repo gates
against everywhere else. It also gives the reopen a record: the challenger's `ChallengeEvent`
carries the `argument`, and an append-only ledger whose reopens have no *why* is a ledger that has
stopped doing the one thing it is for.

## Permissions — **the source of truth; the build reads this table**

These two lines are parsed by `build.py`. Editing them changes every host at once; nothing else
states a write permission anywhere.

- `researcher`, `brainstorm`, `reviewer`, `challenger`, `measurer` → **edit: deny** (read-only; may read, search, run read-only tools, fetch grounded sources). The `challenger` additionally writes **only** `ChallengeEvent`s and may set a challenged pin back to `needs_input` — never a `DecisionEvent`, never code.
- `executor` → **edit: allow** (the single writer; still gated by the reviewer and the Phase-5 evidence gate).

**The residual no adapter can close: `Bash`.** A subagent with `Bash` can `echo > file` whatever its
`disallowedTools` says, so `edit: deny` is enforced *statically* only as far as the write **tools**
go, and the rest is closed at **runtime** by the ledger gate. A read-only role's `Bash` is a read
channel by discipline, not by mechanism — which is why each role's prompt says so out loud.

State the platform limit precisely, because the obvious phrasing is false: **Claude Code restricts
`Bash` fine** — `Bash(rm *)`-style matchers exist, with `deny → ask → allow` precedence. What no
adapter can do is narrower: **a plugin cannot ship a selective `Bash` rule, nor scope one to a single
agent.** Agent frontmatter takes tool *names* only, `permissionMode` is ignored for plugin subagents,
and the plugin manifest has no property for permission rules — selective matchers live only in the
user's own `settings.json`, session-wide, which a plugin cannot write. And blunt denial is not
available either, because the read-only roles genuinely need `Bash` for static analysis. That is the
gap the ledger gate exists to close, and it is smaller than "cannot restrict" implied.

And it closes that gap by *observing*, not by becoming a target. The ledger gate — like the
`reviewer`, `challenger` and `measurer` — blocks an unelected edit or an unverified claim, never a
suspect *thought*; the reasoning stays legible so the shortcut is visible in it. This is a **design
principle for whoever extends these gates**, not a runtime instruction — there is no optimizer here to
obey it: put optimization pressure on a monitor and a model learns to hide the intent rather than drop
it, so a read-only gate must never be turned into a score to beat. A monitor you optimize against
stops seeing.

## Model tier per role — **the build reads this too**

The write permission is not the only per-role property the build derives. Each role also carries a
**tier**: a classification by cognitive demand, from which `model-tiers.md` resolves a concrete model
and reasoning effort **per profile** (Anthropic / OpenAI / OpenCode-Go / mixed), and `build.py`
emits it into each host's adapter. The tier is a property of the **role**, known deterministically —
never a guess about how hard a given task is, which is the heuristic this package forbids. These
lines are parsed; editing them re-tiers every host at once.

- `challenger` → **tier: T3** (deepest reasoning — refute the oracle; rare, highest stakes)
- `reviewer`, `brainstorm` → **tier: T2** (judgment — find real bugs, propose options)
- `executor` → **tier: T1** (bounded implementation — the one writer, high volume)
- `researcher`, `measurer` → **tier: T0** (read / verify at fan-out — cheap, parallel)

The **orchestrator** (the main loop) is not a roster subagent and has no tier: on Claude Code a
plugin cannot set the main-loop model (it stays the human's `/model`), so there it is guidance; on
opencode/Pi it is the configurable primary agent. Escalation (`executor` → a higher tier) fires only
on a ledger signal — a `reviewer` `REJECT` twice or an unmet `acceptance_criterion` — so it is a
runtime decision on evidence, never baked into an adapter. Full policy + the four profiles:
`model-tiers.md`.

## Mapping notes

- The two-stage review the phase playbooks describe **is** the `reviewer`; the "data decides"
  evidence gate **is** the `measurer`; the brainstorm agent **is** `brainstorm`; the
  comprehension/finding pass **is** the `researcher`; the remediation/build loop **is** the
  `executor`. This roster names what the phases already imply, and adds the explicit
  single-writer/parallel-reader orchestration.
- Grounding for `researcher` and `brainstorm` follows the knowledge-sources doctrine (Context7 /
  DeepWiki / registry / web), cited and confidence-tagged, treated as untrusted input.
- Every role inherits the self-model / effort-calibration doctrine (self-model.md): execute rather
  than defer or advise, and size work in steps/tool-calls, never in human wall-clock. The `executor`
  carries it most sharply (it is the one writer, the one tempted to hand back a plan); the `measurer`
  rests its verdict on observed behavior, never on the agent's own sense of how hard the work was.
- The `challenger` is the **upstream** twin of the feedback loop (the feedback-loop doctrine): the
  feedback loop reopens a decision when *production* falsifies it (downstream), the challenger
  reopens it when the *oracle itself* is unsound (upstream, before build). Both **reopen and never
  decide** — same schema-enforced neutrality as the brainstorm. Its `ChallengeEvent` schema and the
  `unstated_assumption` precondition live in the ledger spec (decisions-ledger-spec, v0.6) and the
  assumptions doctrine. It runs right after the interview commits (Phase 2) and again at each wave
  checkpoint (Phase 4), so an unsound oracle is caught before, not after, code rests on it. This is
also the package's runtime guard against **evasive fabrication**: an agent handed an oracle it
*cannot* satisfy — mutually exclusive criteria, an unreachable `to_be` — tends not to down tools but
to invent a plausible external reason it is blocked and present it as fact. Refuting an
`unsatisfiable` oracle before build is the joint-satisfiability check that keeps the agent out of that
corner, and running it early is essential: once fabrication starts it self-reinforces, and later
evidence no longer dislodges it.

## Teach on rejection (a gate that blocks must also teach)

Every read-only gate here can **block** — the reviewer REJECTs, the challenger reopens, the measurer
withholds `resolved`. A gate that only blocks maximizes today's output and freezes tomorrow's skill;
a gate that *teaches* raises the operator too. So a blocking verdict is never a bare code: it names
the **class** that was violated and **how to recognize it next time** (e.g. "REJECT — this is a
TOCTOU race: the check and the use straddle an `await`", not "REJECT — concurrency bug"). The class,
not the instance; the pattern gets a name. This costs one sentence, is emitted whether or not anyone
reads it (passive, opt-out), and is what the `learning-layer` skill consumes to close the operator
gap. Enforce the oracle *and* explain the enforcement.
