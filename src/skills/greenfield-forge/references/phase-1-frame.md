# Phase 1 — Frame (materialize the open decisions)

Produce the greenfield equivalent of rescue's as-is map: a set of concrete, answerable **forks**
and a skeletal **to-be map** to hang them on. Where rescue reads code to find problems, greenfield
reads the **brief** against the **decision-catalog** to find decisions. Attention scales with the
number of real forks, not with how big the eventual app will be.

The cardinal rule: **this is not an open-ended "tell me about your app" chat.** An open chat is
the slop seed — it lets the model quietly fill unmade decisions with assumptions, which is exactly
the failure mode both skills exist to prevent. The catalog replaces the chat with a bounded,
pruned, information-gain-ordered set of forks.

## Step 1 — Intake & classify

Take the brief (a paragraph or two from the user). Classify the project type (CLI · library ·
static site · API service · web SaaS · …) and use it to **prune** the decision-catalog
(`references/decision-catalog.md`) — a whole cluster absent from the type is never asked. Do not
expand the pruning into a design; classification only decides which forks are live.

## Step 2 — Separate givens from decisions

Read the brief for choices already made ("must run on-prem", "team knows Postgres", "React
frontend"). Each is a **given**, recorded as a pre-committed `DecisionEvent` (`source: brief`)
with a `flip_criteria` — NOT re-asked. Re-asking what the user already told you is the fastest way
to make the interview feel like a form. Everything the brief leaves open becomes a fork.

## Step 3 — Frame the testable outcomes (acceptance criteria)

Before the architecture forks, pin the **outcomes**: what a user must be able to do, in testable
form. Each becomes an `acceptance_criterion` pin (`references/core/ledger.md`) — a Given/When/Then (or
equivalent) statement with a `verify` hook, scoped bounded to v1 (`in scope` / `deferred`). These
are the **roots of the `depends_on` DAG**: architecture `open_decision`s depend on the criteria
they must satisfy, and the Phase-4 Track-A tests trace back to them, completing the chain
`outcome → decision → contract → test`.

This is the **engineering half** of requirements (problem statement + acceptance criteria); the
product half (user research, personas, market) stays out — pulling it in reopens the "tell me
about your app" chat. Discipline: elicit outcomes as a **bounded** set (the core use case, not
"everything"); an outcome the brief doesn't state is asked or deferred, never silently assumed.
YAGNI applies to outcomes first — a deferred outcome is future backlog, not scaffolding.

## Step 4 — Expand the catalog into `open_decision` pins

For each live, undecided fork, materialize one `open_decision` pin (schema: `references/core/ledger.md`):
- `question` = the fork, with the catalog's **options** (candidate to-be's — never one asserted
  as correct) and each option's downstream **implication**.
- `depends_on` = wired from the catalog (e.g. the API/contract fork `depends_on` the data-model
  fork; the client fork `depends_on` the API contract). This DAG is what later sequences the build.
- `cluster_id` = grouping related forks so the interview asks once (e.g. all persistence sub-forks).
- `severity` = set by **fan-out**: clusters the catalog marks high-fan-out (domain, persistence,
  API, identity) tend to `high`/`blocker`; leaf clusters (delivery, observability) tend to
  `medium`. This drives the severity threshold in Phase 2.
- `as_is` = the givens that constrain this fork; `built: null`. `to_be` stays null until elected.

**Materialize them — do not write them out by hand:** call `interview_expand` over `ledger.json`.
It reads the machine form of the catalog, prunes by the `project_type` from Step 1, creates one pin
per surviving fork with the catalog's options, implications, `cluster_id`, `severity` and
`depends_on` already wired to the freshly-created pin ids, and takes the Step-2 givens as
`brief_decisions` (cluster id → the outcome the brief already settled), which it commits as
pre-decided with `evidence: "brief"` instead of asking again. It returns `created` / `pruned` /
`pre_decided`, which is the audit of what Steps 1–2 actually did.

Then call `interview_seed_policies` for the catalog's per-cluster default policies. They are
**offers**, not writes — Phase 2 opens with them and the user elects; nothing lands in the ledger
until it does. Each offer arrives with `would_decide` / `held_back`: the pins accepting it would
settle, and the blocker/high ones the threshold rule keeps as real questions. Carry that to Phase 2
and put it in front of the user with the rule — what they accept is the radius. When they accept,
`ledger_record_policy` is what writes the `Policy` and cascades it; there is no other way for one to
enter the ledger, so an offer agreed to in conversation compresses nothing.

Also run the **threat-model** pass here (`references/threat-model.md`): STRIDE over the decided
elements materializes security `open_decision`s, so security is designed in from Phase 1, not
scanned for later.

## Step 5 — Seed the skeletal to-be map

Build the design canvas (the `to-be-map` module): domain entities and layer lanes (DB / API /
client) as **ghost/planned** nodes, every decision pin attached to the nodes it governs. The
completeness traffic-light starts **all-red by design** — nothing is built, and that is the
correct starting state, not an error (the exact inverse of rescue, where red means broken). As the
build loop resolves items, these nodes flip ghost→solid and the map converges toward all-green.

**Render it — do not draw it by hand:** call the `render_map` tool over `ledger.json`.

The same renderer rescue uses, with a built-in as-is/to-be toggle: your `open_decision` and
`acceptance_criterion` pins render their `to_be` (the design), where rescue's render their `as_is`
(the extracted mess). The map holds **no state of its own** — it is a view over `ledger.json`, so
re-running it after any pin changes is how it stays true. Nothing here is hand-maintained.

## Output

`ledger.json` populated with `acceptance_criterion` pins (the DAG roots), `open_decision` pins
(architecture + security, state `detected` → `needs_input` once the questions are surfaced) plus
any brief-given `DecisionEvent`s, and the skeletal to-be map. These are what Phase 2 reads —
Phase 1 carries no conversational state forward.

## Guardrail

Never fill an unmade decision with a silent assumption. If the brief is silent on a high-fan-out
fork, it becomes an `asked` question, never a proposed default — the severity threshold
(`references/core/interview-funnel.md`) makes this a hard rule. Silent defaults are only ever for the
low-severity long tail.
