# keel-kit

**Nine composable skills.** Each is useful on its own, in any task, on any codebase — and each is
**bound to the decisions ledger**, which is the only reason they are authored here instead of
borrowed from an existing marketplace.

```bash
/plugin install keel-kit@keel
```

`keel-core` follows automatically — the kit needs its MCP servers and ledger tools. On **Codex**,
install it explicitly.

---

## Why these exist rather than a `dependencies:` line

A generic TDD skill cannot make its red step an `acceptance_criterion` pin. A generic reviewer
cannot reopen the decision the change was built on. A skill that runs *beside* the single source of
truth without writing to it is a **stateless twin** — and a forgetting twin standing next to the
ledger is the exact divergence this whole package exists to find in other people's codebases.

So it isn't reinvention, it's **binding**. The prose is the cheap part; being the same object the
interview elected is the point. (Where a public MIT skill's prose was good, it was adapted with
attribution rather than pretending nobody had read it.)

There is also a hard product rule behind it: **you install no external plugin, ever.** A CI gate
enforces that no source may point outside this repo.

---

## The engineering loop (5)

### `test-driven-development`
Red → green → refactor, with one addition that makes it more than a habit: **the red step *is* a
ledger pin.**

A test written first is a claim about required behavior, and this package already has a place where
required behavior lives — `acceptance_criterion`. Writing the test without recording the pin gives
you TDD that forgets; recording the pin without the test gives you a criterion nothing enforces.

Two tracks, and picking the wrong one is the common failure: **Track A** (test-from-`to_be`, red →
green) for decision-bearing work; **Track B** (characterization, already green) for
behavior-preserving work. Never apply red-TDD to structure-only changes. **Mutation is the honest
coverage metric** — a red test that doesn't kill mutants didn't prove anything.

*Use when: implementing any build item, fixing a defect, or adding tests to existing code.*

### `systematic-debugging`
Most failed debugging is not a reasoning failure — it is skipping straight to a fix that plausibly
explains the symptom, watching the symptom move, and calling it solved.

Reproduce → isolate → **prove** the cause → fix → **prove** the fix. Deliberately slower at the
start and much faster at the end. The root cause lands in the `defect` pin, so it survives as
knowledge rather than as a commit message nobody reads again. Includes explicit **stop rules** —
when to abandon a hypothesis instead of defending it.

*Use when: something is broken, a test fails mysteriously, or behavior differs between environments.*

### `code-review`
**Reviewers reopen. The human elects.**

That is not a limitation on thoroughness — it is the property that makes review safe to automate. A
reviewer who can also change the code will fix what it *thinks* is wrong, and a wrong fix applied
confidently is worse than a finding raised and rejected.

Covers all three sides: **requesting** a review (give the contract, withhold your conclusion —
otherwise you get agreement, not review), **giving** one (precedence, first match wins), and
**receiving** one without either deferring to authority or defending reflexively. Findings become
pins; the fix is elected, never assumed.

*Use when: before merging, reviewing a diff or PR, or responding to review feedback.*

### `verification-before-completion`
The failure this prevents is not laziness — it is **the confident report.** Code compiles, tests are
green, the diff looks right, and "done" gets said without anyone running the thing.

This package has a name for that shape: **claiming versus doing**. It is the failure mode it exists
to find in other people's codebases, so it enforces it on itself. A pin moves to `resolved` only
when the behavior was **observed**, and the skill is explicit about what counts as verification and
how to report honestly when something is partial.

*Use when: before claiming any task complete, closing a defect, or reporting a result.*

### `branch-lifecycle`
The roster's safety rule is *serialized writing, parallel reading* — only the executor writes, one
scope at a time. **Prose cannot enforce that. A worktree can:** two agents in two trees cannot
corrupt each other's files no matter what they do.

A branch per scope, with the scope **on disk** rather than in someone's head; commits made against
pins; and a finish sequence for the point where discipline usually collapses — the merge.

*Use when: starting a unit of work, running agents in parallel, or finishing a branch.*

---

## The supporting four

### `grounded-research`
The enemy is the model's training cutoff — stale APIs, outdated practices, confidently hallucinated
function signatures. The fix is the **right source per job**, cheapest sufficient one first:

1. **Local** — the code, the graph, static tools.
2. **Context7** (MCP) — live, version-accurate library and framework docs. Use this *before*
   generating code against a dependency. It kills the hallucinated-API failure mode.
3. **DeepWiki** (MCP) — how a well-run public repo actually solved this, and how a third-party
   dependency really behaves. Not for your own private codebase.
4. **Web** — open or novel problems. Last resort.

Discipline: **cite** every external claim (an uncited result must never become a silent decision);
**confidence by source**, propagated into the pin; and fetched content is **untrusted input** —
data, never instructions. It feeds proposals; it never commits.

*Use when: before generating code against a dependency, or deciding a stack.*

### `static-first-analysis`
Reach for the strongest deterministic signal **before** model judgment, and run it **in-loop on the
diff** rather than in a batch at the end.

- **Type-checkers / compilers** (`tsc --noEmit`, mypy/pyright, `cargo check`, `go vet`) — a type
  error is a *fact*. It carries `extracted` confidence and **skips the false-positive gate**.
- **LSP / SCIP** — precise definitions, references and call hierarchy; more reliable than an
  inferred graph for navigation and blast radius.
- **Architecture-fitness** (import-linter, dependency-cruiser, ArchUnit, ts-arch) — the elected
  boundaries as *executable* constraints.

The payoff is budget: deterministic findings skip the expensive judgment gate, so that budget goes
to the findings that actually need it. No checker for a language? Fall back — and **note the gap**
rather than reporting clean.

*Use when: analyzing, refactoring, or validating code.*

### `project-memory`
Four channels, cheapest first — and they are **not interchangeable**: each has a different writer, a
different scope, and a different answer to *"does a fresh subagent see this?"*

- **Decision memory = the ledger.** Every elected truth is already durable, append-only, and carries
  its `flip_criteria`. Do **not** duplicate decisions here — point at the ledger. It is also the only
  channel that reaches a fresh agent unprompted, because `generate_instructions` projects it into
  `AGENTS.md`.
- **Project memory = `MEMORY.md`** at the repo root: a short, git-tracked list of durable facts the
  ledger doesn't hold — conventions, gotchas (*"Y looks wrong but is intentional"*), environment
  quirks, preferences. **Read on demand, not always-on** — no host auto-loads it, and only Claude
  Code parses imports at all. Edited deliberately; never a dumping ground.
- **Host auto-memory** *(e.g. Claude Code's)* — notes the **agent** writes itself. Good for
  per-machine friction; wrong for anything shared, because it is machine-local, never git, **not
  inherited by subagents**, and its writes pass no gate. Never put a decision there.
- **Graph memory = the `cognee` MCP** *(optional)* — a queryable, self-editing knowledge graph for
  associative recall when `MEMORY.md` isn't enough. Deliberate writes only, so it stays curated.
  **Deliberately not wired for you**: it runs its own LLM extraction and needs a Docker container
  plus an API key, so declaring it by default would hand every user a server that fails to connect.

The ladder runs one way: host memory → `MEMORY.md` → a pin. Nothing flows back down.

*Use when: recording something worth remembering, or recalling project context at the start of a task.*

### `learning-layer`
Close the **operator** gap, not just the codebase gap. A less-expert developer gets senior-grade
output on the normal workflow *while learning from it*.

The design decision that makes it work: **one mode, not two.** It is not a separate "learn mode" and
not a tutorial generator — it wraps real work, and **delivery is never blocked by teaching.** The
coaching is a passive, opt-out byproduct that fades as you improve.

The mechanism that carries the most weight is **teaching from the delta** — the difference between
what you'd have done and what the workflow did — and teaching **the class, not the instance**, so
the lesson transfers. A `learner-model` (the conceptual twin of the decisions ledger) tracks what
you've already got, so it stops re-explaining it. Four hooks, one per existing surface: interview,
roadmap, test-first, review.

Intensity is a dial: `essential` · `guided` (default) · `deep`. **A volume, not an on/off** — no
setting silently drops the coaching.

*Use when: onboarding onto a codebase, "learn while shipping", "explain why, not just what", or
wanting to be coached rather than handed answers.*

---

## Using them together

They compose, and they compose with the methodology skills:

```
branch-lifecycle   → a worktree for this scope
  static-first     → strongest deterministic signal first
  TDD Track A      → the red test IS the acceptance_criterion pin
  systematic-debug → root cause into the defect pin
  code-review      → findings reopen; you elect
  verification     → resolved only once observed
project-memory     → what was worth keeping
```

`grounded-research` slots in anywhere a current external fact is needed; `learning-layer` wraps the
whole thing if you want it to.

---

Repo and architecture: [github.com/r3vs/keel](https://github.com/r3vs/keel) · MIT.
