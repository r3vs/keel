<!-- GENERATED FILE - do not edit. Source: src/core/interview-funnel.md at the repo root; regenerate with: python scripts/build.py -->

# The Interview Compression Funnel (shared core)

The interview mechanism is **shared by both skills**. It is the same machine in both:
a filtered, compressed view over the pins in state `needs_input`, that resolves them into
committed decisions **without drowning the user in questions**. What differs is only the
*source* of the pins — and that lives in each skill's Phase-2 playbook, not here:

- `codebase-rescue` — pins are **code findings** (`skills/codebase-rescue/references/phase-2-interview.md`).
- `greenfield-forge` — pins are **open decisions** (`skills/greenfield-forge/references/phase-2-interview.md`).

This file is the authority for the *mechanism*. Read it before writing either skill's interview.

## The core reframe

The enemy is not the number of pins — it is the number of **decisions**. In rescue, 200
SQL-injection findings are ONE decision ("parameterize everywhere?"). In greenfield, twelve
forks about API shape may collapse to ONE policy ("the shared-types package is the contract").
The interview's first job is not to ask — it is to **collapse pins into decisions**.

Neither skill's interview is an open-ended "tell me about your app / your code" script. It is
always driven by concrete pins with 2–3 options each. (In greenfield, "tell me about your app"
is the exact failure mode to avoid: an open chat lets the model fill unmade decisions with
silent assumptions — which is how slop is born. The decision-catalog replaces the open chat.)

## The funnel (mandatory)

```
pins  →  clusters  →  policies  →  real questions (asked)  →  proposed defaults (bulk skim)
```

1. **Cluster.** Group pins sharing one decision under a `cluster_id`; ask ONCE per cluster and
   apply to the group. Typically 200 → ~20.
2. **Policy questions first** (4–5, highest leverage). Category-level rules that auto-resolve
   whole clusters by default. Each becomes a `Policy`; cascading it emits `DecisionEvent`s with
   `source: "policy:<id>"` and `evidence: cascaded` — still user-originated, just amplified.
   ~20 clusters → ~5 policies.

   **One tool sets a policy and cascades it: `mcp:ledger_record_policy`.** Nothing else creates a
   `Policy`, so a policy you only agreed to in conversation cascades over nothing and the whole
   compression step silently does not happen. Put the rule to the user *with the outcome it writes
   and the pins it would decide*: `mcp:policy_preview` answers that without writing, and
   greenfield's opening offers arrive with it already attached from `mcp:interview_seed_policies`.
   It cannot be used to elect: a catalog
   offer is taken verbatim by `offer_id`, any other policy must state its rule, scope and outcome
   and quote the user, and where the host can elicit, the server asks and writes only on acceptance.

   **Read `scope_note` out too, whenever it is non-empty.** A scope value of `null` is a legal,
   sometimes intended filter — it matches the pins carrying no value for that field — and it is
   indistinguishable from a wildcard by reading the scope. `{"cluster_id": null}` says *the pins in
   no cluster* and behaves as *nearly everything* wherever little is clustered. The note says which,
   and how many of how many; the radius alone does not.

   **Two rules hold a pin back, and both leave it open.** `blocker`/`high` pins by the severity
   threshold below; and any pin whose own `question` does not offer the policy's outcome
   (`not_offered`) — a policy decides more pins than a single decision does, so it is not allowed to
   write what a single decision could not. Only the first is recorded on the pin as
   `resolution_mode: "asked"`: severity is a standing property, while `not_offered` is a fact about
   *that policy's* fit, and the mark is permanent, so recording it would put the pin beyond the
   later policy written for it (v0.18). A `default_outcome` is therefore an **option id**, not a
   sentence: `"relational"`, not *"one relational datastore until a concrete need proves
   otherwise"*. The second rule is why a cluster can state a default and still make no offer — if no
   one of its options carries that default, it is advice, and advice is asked.
3. **Exception questions** — only what a policy doesn't cover: pins that contradict a policy,
   plus the genuine forks (rescue: `ambiguity` / `design_concern`; greenfield: high-fan-out
   `open_decision`). Few, and the valuable ones.
4. **Proposed defaults** — the long tail. Attach a low-confidence proposed resolution (marked
   as a guess), presented in bulk by type. The user skims, overrides by exception, accepts the
   rest. Review by exception, not by enumeration.
5. **Severity threshold (hard rule).** `blocker`/`high` → **never** silent default (always
   `asked`, or at minimum top of the review batch). `medium`/`low` → may be `proposed_default`.
6. **Order `asked` questions by information gain** — those that collapse the most downstream
   pins once answered go first. The first ~10 do ~90% of the work.

Result: **200 pins → ~20 clusters → ~5 policies → ~10 real questions → the rest as skimmable
proposed defaults.**

## Question shape (both skills)

Keep each question short: `prompt` + 2–3 `options` (+ freeform escape). All detail — divergent
shapes and evidence (rescue), or option implications and downstream `depends_on` (greenfield) —
lives behind the pin on the map, pulled up on demand. **The question is not detailed; the map
is.** Options are derived, not invented: from the divergent layer shapes (rescue) or from the
decision-catalog's option set (greenfield).

## What only the interview may do

Only the interview commits a decision: it sets `state: decided` and emits the `DecisionEvent`
(with `flip_criteria`). The brainstorm (its own doctrine doc) only writes `proposals[]` and
never decides. This separation is what keeps the interview neutral in both skills.

Two tools carry that commit and no third one exists: `mcp:ledger_record_decision` for one pin,
`mcp:ledger_record_policy` for a whole cluster. Both **record** an election and neither can make
one — the outcome must come from the pin's own question, or from an offer the user was shown. The
rung each answer travelled on is recorded (`evidence`), so a relay reads as weaker than an
elicitation and a cascade reads as what it is: one answer, amplified.

That sentence is a rule, not a summary, and it is enforced per pin at the write: every outcome
written — by either door, on either rung — is an id from the `question.options` of the pin it lands
on, and a pin that does not offer it is held back rather than decided on a value nobody offered it.
For one version it was true only of the single-pin door. The policy door showed the user a rule,
took a two-value accept, and stamped a `default_outcome` the caller had composed onto every pin in
the cluster — the strong `elicited` rung on a value the human was never shown. What the message
omits was not elected, whatever rung the write claims; so the elicitation names the outcome, and the
outcome has to be one the pin offers.

**And it is one predicate, not a rule each door remembers.** Guarding the policy door was not
enough: the same violation went through two others nobody had looked at — a cluster fan-out flag on
the single-pin door, and the project brief's `brief_decisions`, which wrote any string onto any
cluster at any severity, `blocker` included. A rule that lives in a door has to be re-implemented by
every new caller, and one of them always is not. So there is exactly one question, asked in one
place (`Ledger.unasked_verdict`): *may this outcome land on this pin, given that this pin's own
question was never put to the human?* The severity threshold and the offered-options rule are its
two halves. The policy cascade asks it, the brief asks it, and anything added later must ask it —
the callers are enumerated from the source itself, so a new one that skips it fails the gate.
The single-pin door does not ask it, for the one reason that holds: there the human WAS shown this
pin, so the threshold does not apply — and the offered-options half is literally the same function.

**And there is a second predicate, for the question next to it.** The one above governs *what may be
written onto a pin nobody was asked about*. It says nothing about whether a pin may **leave the open
set at all** — and for four versions nothing did, so `mcp:ledger_defer` settled a `blocker` fork on a
single state check with no election, no quote and nothing in the log, and a pin that had just
recorded that its correctness could not be established closed green. `Ledger.settlement_verdict(pin,
door)` is that second question, asked at all five doors. Two consequences for the funnel:

- **Deferring is an answer, so it is recorded as one.** `mcp:ledger_defer` is the third electing
  door and is held to the first one's discipline — the user's verbatim words for a relay, and
  `flip_criteria` saying what brings the pin back. A deferral with no return condition is a deletion
  with better manners. It is *not* held to the offered-options rule: `defer` is a meta-answer about
  scope, not a branch of this pin's fork.
- **`resolution_mode: "asked"` binds.** A pin that was reopened, contested, surfaced as an
  assumption, or left unverifiable carries that mark, and no unasked write may settle it — it comes
  back as `must_be_asked`, beside `held_back` and `not_offered`. The mark was written by six places
  and read by none, which made "never re-defaulted silently" a comment rather than a rule.
- **And it is written only for a standing property of the pin** (v0.18). Every item in the list
  above is one: being reopened, contested, assumed or unverifiable is a fact about *this* pin that
  no later rule can undo. Being `not_offered` is not — it says the last policy's outcome was not on
  this pin's menu, which is a fact about that policy — and stamping it made the pin permanently
  un-cascadable, so an early badly-scoped rule quietly switched the long-tail compression off for
  every pin it touched. Nothing clears the mark and no door should: a door that unsets *this must be
  asked* can silence the threshold rule. The fix is at the writer, and both writers read one tuple.

Which is why there is no third door and no fan-out flag. A fan-out **is** a policy: one answer
covering pins nobody was shown individually is exactly what a `Policy` records — the rule, the
quote, and the radius — and `cascaded` is the only rung that describes it honestly. "200 findings →
one decision" is real and it runs there, with the radius in front of the user before the write.
