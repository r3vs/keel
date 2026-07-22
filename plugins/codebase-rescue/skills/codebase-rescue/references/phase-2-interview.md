# Phase 2 — Interview (elect the to-be)

Goal: resolve the pins that need human judgment into a validated `to-be` spec **without
drowning the user in questions**. The interview is a filtered view over pins in state
`needs_input`, generated entirely from Phase 1. It is never an open-ended "tell me about
your app" script.

## The core reframe

The enemy is not the number of problems — it is the number of **decisions**. 200 SQL-i
findings are ONE decision ("parameterize everywhere?"). 15 divergent copies of an auth
helper are ONE decision ("consolidate onto which copy?"). The interview's first job is not
to ask, it is to **collapse pins into decisions**.

## The compression funnel (mandatory)

The funnel mechanism — cluster → policy → exception → proposed-default, the severity threshold,
and information-gain ordering — is **shared with the `greenfield-forge` sibling and authoritative
in `references/core/interview-funnel.md`. Read it first.** How *rescue* sources it:

- **Cluster:** the contract-reconciliation and duplication modules already assign `cluster_id`;
  extend by decision-similarity. 200 findings typically collapse to ~20 clusters.
- **Policy questions first** (4–5, highest leverage): category rules that auto-resolve whole
  clusters — "DB is source of truth for schema mismatches unless noted", "dead code with no
  inbound reference → remove", "duplication → consolidate onto the most-tested copy". Each becomes
  a `Policy`; cascading it emits `DecisionEvent`s with `source: "policy:<id>"`. ~20 → ~5 policies.
- **Exception questions:** pins a policy doesn't cover, plus genuine `ambiguity` and
  `design_concern` pins — the true forks where intent changes what would be built.
- **Proposed defaults + severity threshold + information-gain order:** exactly as in the shared
  funnel. `blocker`/`high` never go to silent default; order `asked` questions by how many
  downstream pins they collapse.

Result: **200 findings → ~20 clusters → ~5 policies → ~10 real questions → the rest skimmable.**

> **Run the funnel — do not re-derive it.** It is implemented, not merely specified: the
> `interview_next` tool returns the compressed view straight from the ledger — clusters collapsed,
> policies cascaded, the severity threshold already enforced, `asked` questions already ordered by
> information gain. Re-deriving that order in your head is exactly how the threshold gets quietly
> skipped and a `blocker` slips into a silent default.

## Question shape

Keep each question short: `prompt` + 2–3 `options` (+ freeform escape). All detail — the
divergent shapes, anchors, evidence — lives behind the pin on the map, pulled up on demand.
The question is not detailed; the map is. Options are usually derived directly from the
mismatch (each divergent layer shape becomes a candidate truth).

**Example (contract_mismatch):**
Prompt: "The frontend checks a `superadmin` role the DB doesn't define. What is the intended
set of roles?"
Options: `{admin,user} — DB is truth` · `add superadmin to schema` · (freeform)

## Kind-specific handling

- `design_concern` → OPTIONS, not findings. "Leave as-is" (`state: accepted`) is a valid
  answer; `to_be` stays null until the user chooses. Never phrase it as a defect.
- `ambiguity` (blocker) → must be resolved before the to-be for that area is knowable; put
  high in the order.
- `defect` → usually `question: null`; goes to remediation. Promote to `needs_input` only
  when there's a genuine scope question (e.g. "is this dead code residue, or a half-built
  feature you want completed?").
- `incompleteness` → question is typically scope: implement now / defer / drop (YAGNI).

## Parallelism with the map and brainstorm

Every question carries a reference to the pin(s) it came from, so the UI can cross-link:
click the question → the map highlights the involved nodes; click a pin → its question
surfaces. If the user opens a brainstorm on a pin, the brainstorm writes
`proposals[]`; the user's committed answer here (and only here) sets `state: decided` and
emits the `DecisionEvent` (with `flip_criteria`). The interview commits; the brainstorm
never does.

> **Composability (optional):** a coaching layer — the `learning-layer` skill — can wrap this
> surface non-invasively: capture the user's own spec attempt *before* the derived `to_be` is
> revealed, then teach the 1–2 highest-leverage misses (the delta). It never blocks or alters the
> interview; if it is not active, this section runs exactly as written.

## Challenge the oracle (before Phase 3 builds on it)

Electing a `to_be` is not the end of the interview — a wrong oracle elected confidently is worse
than an open question, because Phase 3/4 will build on it as if it were true. So once answers are
committed, the `challenger` (`references/core/agents.md`, the reviewer's upstream twin) red-teams the
freshly derived `to_be`s and any `Policy` cascade, trying to **refute** each
(`references/core/decisions-ledger-spec.md` v0.6):

- **unfalsifiable** — the `to_be` has no observable check that could fail (a policy stated so
  loosely nothing violates it). Send it back to get a testable form.
- **inconsistent** — two committed answers (or a policy and an exception) that cannot both hold.
- **unsatisfiable** — the elected truth contradicts a hard `as_is` constraint the code can't shed.
- **unstated_assumption** — the answer silently rests on an assumption never surfaced
  (`references/core/assumptions.md`); reopen it with the assumption made explicit.
- **ignored_fanout** — a high-`depends_on` pin resolved by silent default where the severity
  threshold demanded `asked`.

A sustained challenge emits an immutable `ChallengeEvent` and returns the pin to `needs_input`
(`challenged`) — reopening the **minimum** (the pin + genuine dependents), handed straight back to
this interview. The challenger **challenges, never decides**; only the user's re-answer commits.
This is cheap here and ruinous later: catching an unsound criterion now costs one question; catching
it after Wave 1 remediation costs the wave.

> **Run the deterministic classes first.** The `challenge_oracle` tool mechanizes the classes above
> that are decidable without judgment — an `acceptance_criterion` with no `verify` is unfalsifiable
> as a matter of fact, not opinion. It returns proposals and never writes, so its output is where
> the `challenger` agent *starts*, not what it reports: spend the agent's judgment on the classes a
> checker cannot reach (unsatisfiable-against-the-code, unstated_assumption).

## Output

Updated ledger: `Policy` entities, `Question` objects on pins, `DecisionEvent`s for every committed
answer (direct or policy-cascaded), and any `ChallengeEvent`s from the challenge pass. Decided pins
now carry a derived `to_be`; challenged pins are back in `needs_input`. Phase 3 diffs `to_be`
against `as_is` only for pins that survived the challenge.
