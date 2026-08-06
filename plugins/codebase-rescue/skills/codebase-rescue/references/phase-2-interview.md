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
  **Record each accepted rule with `mcp:ledger_record_policy`** — it creates the `Policy` and runs
  the cascade in one call, and nothing else does either. Rescue's policies come from the findings,
  not from a catalog, so pass `rule` + `applies_to` (e.g. `{"cluster_id": "cl_dupe_auth"}`) +
  `default_outcome`, and quote the user verbatim in `human_answer`: one unquoted claim here carries
  a whole cluster, which is why the tool refuses it. `exceptions` names the pins the rule must not
  touch; `blocker`/`high` matches are held back by the threshold rule and stay `asked`. Ask
  `mcp:policy_preview` **first**, with the same arguments: it writes nothing and answers with the
  pins the rule would decide. Put that list to the user, because what they are electing is the blast
  radius, not the sentence.

  **`default_outcome` is an option id those pins already offer** — `"db"`, the id on their
  `question`, not *"the DB is the source of truth"*. A matching pin whose own question does not
  offer it comes back in `not_offered`, held back and still `asked`, exactly like a blocker: the
  single-pin door has always refused an outcome the pin never offered, and a policy decides more
  pins, so it is not allowed to write what one decision could not. If a cluster's pins carry no
  question, or carry questions with different option sets, that is the finding: they are not one
  decision, and no policy will cascade over them.
- **Exception questions:** pins a policy doesn't cover, plus genuine `ambiguity` and
  `design_concern` pins — the true forks where intent changes what would be built.
- **Proposed defaults + severity threshold + information-gain order:** exactly as in the shared
  funnel. `blocker`/`high` never go to silent default; order `asked` questions by how many
  downstream pins they collapse.

Result: **200 findings → ~20 clusters → ~5 policies → ~10 real questions → the rest skimmable.**

> **Run the funnel — do not re-derive it.** It is implemented, not merely specified: the
> `interview_next` tool returns the compressed view straight from the ledger — clusters collapsed,
> the severity threshold already enforced, `asked` questions already ordered by information gain.
> Re-deriving that order in your head is exactly how the threshold gets quietly skipped and a
> `blocker` slips into a silent default.
>
> It **reads**, and the cascade is not one of the things it does: pins already settled by a policy
> are simply absent from the view because they are `decided`. Cascading is `ledger_record_policy`,
> and only when the user elects one. Reading "the funnel is implemented" as "the policies have been
> applied" is how a whole cluster stays open while the view looks compressed.

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

> **A pin with no question reaches this interview on no host — give it one with
> `mcp:ledger_set_question`.** `ledger_add_pin`'s `question` is optional, which is right (whoever
> finds a thing is not always whoever knows what the choice is), and the consequence is that a
> Phase-1 finding recorded without a fork sits in `detected` for ever: `interview_next` selects on
> the question, so the pin is invisible to the exact machinery whose job is to put it to the user.
> Two things the tool will not let you do, both deliberate. It will not **replace** an existing
> fork — the option ids are what the user is allowed to choose from, and rewriting them is you
> deciding for them. And the question you compose must set `allow_freeform: true`, because you wrote
> this menu: leaving the way out open is what keeps a fork of your own authorship from bounding
> their answer.
- `incompleteness` → question is typically scope: implement now / defer / drop (YAGNI). "Defer" is
  `mcp:ledger_defer`, not silence: the pin stays on the ledger as backlog, which is the whole
  difference between scoping something out and forgetting it. **It is an election, so it is recorded
  like one** — deferring settles the pin and takes the question off the interview, so the tool wants
  the user's words verbatim and a `flip_criteria` saying what brings it back. Never defer on your own
  judgement: a deferral nobody elected is the question quietly disappearing.

## Parallelism with the map and brainstorm

Every question carries a reference to the pin(s) it came from, so the UI can cross-link:
click the question → the map highlights the involved nodes; click a pin → its question
surfaces. If the user opens a brainstorm on a pin, the brainstorm writes
`proposals[]` with `mcp:ledger_add_proposals` — one pin per call, and the schema refuses a proposal
carrying a `decision` or an `outcome`; the user's committed answer here (and only here) sets
`state: decided` and emits the `DecisionEvent` (with `flip_criteria`). The interview commits; the
brainstorm never does. The pin stays in `interview_next` while it is being brainstormed, with those
proposals on its entry — exploring a hard fork must not be what takes it off the list.

> **Committing is one tool: `mcp:ledger_record_decision`.** Nothing else moves a pin to `decided`,
> so an answer you only wrote down in prose leaves the pin open — and an open pin blocks its own
> remediation, its dependents, and the reopen loop. Four things it enforces — meet them
> deliberately rather than meeting them as errors:
> - **`option_id` must be one the pin's own `question` offered** (`"freeform"` only where that
>   question sets `allow_freeform`, and then the user's words *are* the outcome). An outcome from
>   anywhere else is you electing, which is the one thing no agent here may do.
> - **`flip_criteria` is required** — a decision with no reopen condition fossilizes, and the
>   feedback loop has nothing to fire against. Name the observable that would make you revisit it.
> - **If the host's client declares elicitation, the server asks the user itself** and ignores
>   whatever you passed; the answer never travels through you (`evidence: elicited`). Otherwise you
>   are relaying, and must **quote the user verbatim in `human_answer`** — that lands as
>   `evidence: transcribed`, the weaker rung, which a reader and the `challenger` can then weigh.
>   Relaying with nothing quoted is refused: an honest relay and an invented one would be
>   indistinguishable in the log.
> - **`accept_as_is: true`** is how "leave it as it is" is recorded, and only for a `design_concern`
>   — an `ambiguity` or a `contract_mismatch` has nothing to keep.
>
> **It decides ONE pin.** "200 findings → one decision" is real, and it is the tool above:
> `mcp:ledger_record_policy`, which shows the user the pins the rule would decide *before* writing,
> holds back the ones it may not settle, and leaves a `Policy` every cascaded decision points back
> at. This door briefly took an `apply_to_cluster` flag instead, and that flag is exactly the shape
> of the mistake this playbook warns about everywhere else: one answer, about one pin, stamped onto
> every pin sharing the `cluster_id` — past the offered-options rule, past the severity threshold,
> with the same quote copied onto pins the user was never shown. A fan-out has to name the rule it
> applies and the radius it covers, and the thing that does that **is** a policy.

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

A sustained challenge is recorded with **`mcp:ledger_challenge`**: it appends the immutable
`ChallengeEvent` and, when `upheld`, returns the pin to `needs_input` (`challenged`) — reopening the
**minimum** (the pin + genuine dependents), handed straight back to this interview. The challenger
**challenges, never decides**; only the user's re-answer commits. This is cheap here and ruinous
later: catching an unsound criterion now costs one question; catching it after Wave 1 remediation
costs the wave.

> **State the argument.** The tool refuses a blank one, and the reason is the same one that makes a
> relayed decision carry the user's words verbatim: an upheld challenge un-does an election on your
> say-so, so what refutes the oracle has to be in the ledger and not only in your reasoning. Read
> `reopened` in the result — `upheld` says the refutation stands, `reopened` says whether this pin
> had anything to un-settle; a refutation of a pin nobody elected is recorded and moves nothing.

> **Run the deterministic classes first.** The `challenge_oracle` tool mechanizes the classes above
> that are decidable without judgment — an `acceptance_criterion` with no `verify` is unfalsifiable
> as a matter of fact, not opinion. It returns proposals and never writes, so its output is where
> the `challenger` agent *starts*, not what it reports: spend the agent's judgment on the classes a
> checker cannot reach (unsatisfiable-against-the-code, unstated_assumption). Applying one of its
> proposals means calling `ledger_challenge` with it — the scan is a proposal, never a write.

## Output

Updated ledger: `Policy` entities, `Question` objects on pins, `DecisionEvent`s for every committed
answer (direct or policy-cascaded), and any `ChallengeEvent`s from the challenge pass. Decided pins
now carry a derived `to_be`; challenged pins are back in `needs_input`. Phase 3 diffs `to_be`
against `as_is` only for pins that survived the challenge.
