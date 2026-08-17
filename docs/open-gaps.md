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

---

## What this package guarantees today, and what it does not — **read this first**

Seventeen adversarial rounds are recorded below. This section is the standing answer to *what do I
actually get*, so a cold session neither re-derives it nor over-trusts it. Everything here was
**observed** — over real `uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd,
against the built plugin — not inferred from a green suite.

**Reading a ledger never fails.** Any surface, on any file: a malformed pin, policy, log entry or
collection is read as the *emptiest true value* (`pin_read` / `policy_read` / `read_collection` /
`readable_ledger`), never as a plausible invented one, and every substitution is reported by name
under `ledger_summary`'s `pre_rule_events`. That holds for the tools, for the map, and for the
`AGENTS.md` projection — the last two read a ledger as data and never construct a `Ledger`, which is
why the guard lives in module functions and not on the class. It holds for the read-only tools that
take a **`pin_id`** too, which were on no roster until §27 because every derivation said *only* the
ledger path.

**Writing to a pin this runtime cannot read is refused, not attempted.** `Ledger.writable_pin` is
the write path's only per-pin lookup, and it refuses with the names of every `PIN_RULES` entry the
record breaks. A refusal is the answer; a stack trace naming a line of ours is a defect. The
election door is inside that guarantee, and so are the thirteen others.

**The refusal is about the record being written and the collection it sits in — never about a
bystander.** `Ledger.writable_collection` refuses a `pins` / `decision_log` / `policies` this runtime
cannot read (there is nothing there to append to), and `Ledger.writable_pins` reads every *other*
record through the read path. So one malformed pin does not make a file unwritable: it participates
as the emptiest true value — named by nothing, depended on by nothing, swept up by no cascade.

**Whatever a door returns describes what happened.** The commit is the last thing every write door
does, checked positionally by AST over every function that reaches it. A door that raises has changed
nothing on disk — which matters because an agent that reads an error retries, and until §27 the
retry of a `ledger_reopen` was a second reopen of a pin the first call had already reopened.

**No agent can elect.** Every door that settles a pin either takes the human's own words with a
quote refusal, or records an *absence* of evidence and cannot claim its presence. The four
`DECISION_EVIDENCE` rungs each owe a carrier. The read-only roles reopen; they never decide.

**Coming back into the open set is governed the same way as leaving it.** Three arcs
(`reopen` · `challenge` · `cross_derive`), each declared with what it moves and what it cascades, and
every carrier a settlement door gates on is invalidated on the way back — so a pin reopened by an
incident cannot re-close on the evidence that incident refuted.

**The interview asks its questions in the order it claims to.** The `downstream` a fork carries is
the number of pins that transitively depend on it, computed once (`ledger.downstream_of`) and read by
both surfaces. Until v0.27 it was two copies of a walk that counted simple PATHS, so a diamond in the
roadmap re-ordered the interview.

**Phase 1 is safe to re-run.** `interview_expand` projects the decision catalog into the ledger and a
cluster already there is left alone. Nothing else in the tool layer is idempotent, and nothing else
claims to be — a `creates` door records a fresh act each time, by declaration and by test.

**Every rule has one carrier, and a test that quantifies over its callers.** Where the corpus can be
generated from the schema the rule is about, it is (`tests/shape_corpus.py`); where a roster can be
derived from the source, it is. §18 is the standing list of which classes are gated this way.

### Attacked and it held — do not re-derive these

The adversarial reviews of the last rounds produced explicit "attacked, and it did not break" lists.
They are recorded here because knowing what is already covered is what stops the next session
spending its round on it:

- **The reopen / cross-derive triangle, end to end.** Resolve at `observed` → reopen on an incident →
  every settlement carrier demoted → `resolve` refused as `unverified` → a fresh observation required
  to close again. Walked over stdio in both directions, including the laundering routes through
  `cross_derive` and `mark_correctness_unknown`. Both are blocked at the rung, by name.
- **Every derived read case, zero unstated crashes.** The reviewers reported *2105 derived read cases
  across six surfaces*; that was the matrix as their round found it. **As the tree now stands it is
  3102** — four corpora (155 broken pins, 19 broken policies, 87 broken log entries, 21 broken files)
  × 11 read-only ledger tools, with the roster derived from the server's own `readOnlyHint`, plus
  both projections. The roster grew by the two tools §27 added, which are the ones that take a
  `pin_id`. Whatever the file holds, the answer is a report.
- **Every derived write case, zero crashes.** The reviewers reported *2635 derived write calls over
  fourteen doors*. As the tree now stands the same pin corpus runs at the write doors in **two**
  positions: **2170 calls** with the broken pin as the TARGET (155 shapes × 14 per-pin doors — before
  §25's fix the same matrix gave 42 crash sites) and **2790 calls** with it as a BYSTANDER beside a
  healthy target (155 × 18, both rosters, added by §27). None of these numbers is typed anywhere —
  each is the product of a derived corpus and a derived roster, and each moves when either does.
- **XSS through every agent-written field.** The map has one DOM sink, every call hands it a thunk,
  and the ledger is inlined through one escaping path with a declared table of holes (U+2028/U+2029
  included). Attacked through titles, rationales, quotes, proposals and rule names.
- **The whole malformed-container matrix at the write doors.** Every collection absent, an object, a
  string or a number, at all 18 doors an agent can reach. Refusals naming the collection, never a
  stack trace. Before §27: 8 doors over stdio, 10 at the tool layer.

### What it does NOT guarantee

- **That a stated observation is a real one.** `evidence` on `ledger_resolve` is any string an agent
  types. The rung is checkable; the sentence is judgment, and nothing here has a carrier for it.
- **That a declared table tells the truth.** Every roster gate is *derived roster held to a declared
  claim*. An author who writes the wrong sentence passes — they just have to write it.
- **That prose matches behaviour.** `check_stated_facts.py` gates a number the repo COMPUTES. A
  behaviour the repo IMPLEMENTS, restated in prose, is not gated and §18 argues why.
- **Anything about a host.** Those claims live in somebody else's repository; cite the function that
  consumes the value, and mark what was read rather than observed.
- **Any of the residuals listed below.** They are recorded with an argument, not fixed.

---

> **STATUS 2026-08-07 (eighteenth round — the branch closes here).** **§1–§17 and §19–§28 are all
> closed.** Nothing on this list
> is open. **§18** is not a defect but the standing answer to the question this register exists to
> ask: *after sixteen adversarial rounds, which recurring class still has no gate?* **§19** was the
> ninth round's answer — §5 built a new surface and left four rules its siblings enforce — and
> **§20** is the tenth's, which is that question asked **backwards**: two sections were closed
> correctly and each left the other half of its own claim standing. §7 guarded a true sentence with
> a condition the interview does not use, so the funnel's countdown printed on six pins the funnel
> never carries; §17g fixed *reading a ledger never fails* for the log and left the pins to die on
> six shapes. **§21** is the eleventh's, and it is the same question asked of the CARRIERS a
> predicate decides from: the way back into the open set rewrote the state and left standing every
> other carrier a settlement door reads, so a pin reopened **by an incident** re-closed on the
> evidence the incident had refuted. **§22** is the twelfth's, and it names the class in its
> sharpest form yet: *a rule paid at a class's METHODS is unpaid for every caller that holds the
> class's DATA instead of the class* — both projections read a ledger as JSON and never build a
> `Ledger`, so two rounds of hardening the read path went past them, `render_map` reported success
> over a page that rendered nothing, and `generate_instructions` died on five ordinary
> malformations. **§23** is the thirteenth's, and it is that same question asked of **sets** rather
> than of classes: *a rule paid at a set's MEMBERS is unpaid for whatever satisfies the set's
> definition without joining it.* `cross_derive` reopened pins and was not on `REOPEN_ARCS`; four
> write doors touched pins and were on no closed-work list; `brief` was in `DECISION_EVIDENCE` and
> was the only member nothing asked anything of. **§24** is the fourteenth's, and it is the first
> round whose subject is the GATE rather than the rule: *when the gate is a corpus, the corpus is
> the weak link.* The read path's three parts were held to each other by construction and all three
> ran against a hand-written list of seven broken pins; extending that list with eleven shapes the
> schema already declares made the unchanged gates fail. **§25** is the fifteenth's, and it is §22,
> §23 and §24 all arriving at the one surface nobody had asked: *a rule proved of the READERS is
> unproved for the WRITERS, and a write door is a reader first.* Every per-pin write door reads the
> pin already in the file before it writes anything — 42 crash sites across all fourteen, the
> election door included — while the door whose whole meaning is *correctness could not be
> established* could write the claim that the behaviour WAS observed onto the one carrier the
> `resolve` gate opens on. **§26** is the sixteenth's, and it is the first round since §20 whose
> subject is the surface all of that work exists to feed — the **interview**. It asks two questions
> §25 could not: *is the number a surface prints the number it claims to be* (the funnel's
> `downstream` counted simple PATHS, in two byte-identical copies, so one diamond in the roadmap
> re-ordered the whole compressed interview), and *what is outside a roster BECAUSE of how the
> roster is derived* (every derivation on this branch said "takes a `pin_id`", and
> `interview_expand` writes without naming one — so nothing saw that a second call duplicated every
> fork in the funnel). **§27** is the seventeenth's and the branch's last, and it is §25 and §26
> asked of the same write path one more time each: *what may a door read while writing, and is what
> it reports what it did?* `writable_pin` guarded the pin being written and no other, so a write onto
> a healthy pin died because a DIFFERENT pin lacked an `id`; `Ledger.readable`'s own docstring said
> for two versions that a write onto an unreadable file must be refused and nothing refused, so ten
> doors died on a malformed CONTAINER; the read-tool roster derived itself as *required ==
> ["ledger"]*, which excludes every read-only tool that also takes a `pin_id` — a whole class, and
> it was two tools that both died on the pin's own declared shapes. And the one nothing had asked at
> all: three doors computed their answer AFTER the commit, so a write landed on disk and the caller
> was told it had not. **A closed section is a claim about a class, and the class is where the next
> instance lives.**
>
> | # | Gap | One line |
> |---|---|---|
> | ~~5~~ | ~~reopen arcs unreachable~~ | **CLOSED** — both arcs, `set_question` and `add_proposals` now have doors |
> | ~~6~~ | ~~map palette contrast~~ | **CLOSED** — measured before/after in a browser; three hues needed a paired foreground, not one darker hue |
> | ~~7~~ | ~~`resolution_mode` has no reader on the map~~ | **CLOSED** — one line under the sub-line, and only `proposed_default` is a countdown; **re-closed by §20**, which fixed the condition around it |
> | ~~8~~ | ~~the `verification` envelope has no reader~~ | **CLOSED** — a verification card says *this pin cannot close: …*; the funnel carries `blocked_by` |
> | ~~9~~ | ~~a null-valued scope key is a universal selector~~ | **CLOSED** — `scope_note` says what the matcher matched, on the elicited message |
> | ~~10~~ | ~~no door gives an existing pin a question~~ | **CLOSED** — `mcp:ledger_set_question`, write-if-absent, freeform required |
> | ~~11~~ | ~~the `correctness_unknown` fork offers an outcome it cannot produce~~ | **CLOSED** — the implication is computed from `settlement_verdict` |
> | ~~12~~ | ~~`resolution_mode: "asked"` is permanent~~ | **CLOSED** — only a STANDING refusal writes it, at both unasked doors |
> | ~~13~~ | ~~`ensure_ascii=False` emits raw U+2028/U+2029~~ | **CLOSED** — one table of holes, and `_inline` proved by AST to be the only path |
> | ~~14~~ | ~~five more pin fields, and four of five log kinds, reach the map nowhere~~ | **CLOSED** — one stack of cards plus a trail, decided once |
> | ~~15~~ | ~~two gates check less than their names claim~~ | **CLOSED** — both inverted and re-planted; the schema gate then found **six** write-only fields it had always passed |
> | ~~16~~ | ~~an unknown `settles_as` renders as a bare label~~ | **CLOSED** — one `unknownNote` sentence, seven callers, tables kept apart |
> | ~~17~~ | ~~seven residuals of the final review~~ | **CLOSED** — 17c was the last, and it was eight prose sites rather than three |
> | **18** | **which class still has no gate** | not a defect: the standing answer — two classes gated, one newly gated, two argued as not mechanizable |
> | ~~19~~ | ~~four rules true on one side of a pairing, absent on the other~~ | **CLOSED** — the reopen half held to the settlement half's own rules; one residual registered, not built |
> | ~~20~~ | ~~two closures that held for one half of what they claimed~~ | **CLOSED** — §7's guard reads the interview's own states; §17g's principle reaches the pins; the envelope gate stopped being a word search |
> | ~~21~~ | ~~the reopen leaves the carriers the settlement doors gate on~~ | **CLOSED** — one declared table of carriers, held to the predicate's own AST; the derived read-tool gate then found three more readers |
> | ~~22~~ | ~~the two projections read a ledger nobody had guarded~~ | **CLOSED** — `readable_ledger` is the one door for a caller holding ledger data; `nonconforming` reaches the page; `mount` is the page's one failure boundary; six new gates |
> | ~~23~~ | ~~six rules paid at a set's members~~ | **CLOSED** — `cross_derive` is the third arc; a re-derivation may not launder a refutation; `PIN_WRITE_DOORS`; `brief_quote`; one commit point; one quote refusal |
> | ~~24~~ | ~~the gate was a corpus, and the corpus was hand-written~~ | **CLOSED** — `PIN_SHAPES` is the one carrier the rules, the read and the corpus all derive from; the derived corpus then found three readers nobody had reported |
> | ~~25~~ | ~~a write door reads the pin already in the file~~ | **CLOSED** — `writable_pin` is the write path's lookup and refuses what the read path substitutes; `RUNG_WRITER_RUNGS` makes the rung table's third column a rule; the derived corpus now runs at the derived write doors |
> | ~~26~~ | ~~the interview's information gain, and a door with no `pin_id`~~ | **CLOSED** — `downstream_of` is the one answer and it is a set of pins, not a count of paths; the write-door roster now covers what writes WITHOUT one, and the door that projects the catalog is idempotent |
> | ~~27~~ | ~~what a door may read while writing, and whether its report is true~~ | **CLOSED** — the commit is the last thing a door does; `writable_collection` refuses the container; `writable_pins` reads every other record; the read-tool roster stopped excluding a class |
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
> | 15. + 17c. two gates that overstated themselves, and the prose one door behind | 2026-08-06 (no spec bump — nothing here is a schema rule) | `tests/test_ledger.py::TestOneWriterForTheSettledStates` — inverted to `STATE_WRITERS`, set equality over the assignment TARGET across `src/runtime` + `src/mcp`; `scripts/check_schema_fields.py::mask_writes` — Python write-positions blanked before the search, which found **six** write-only fields the same day; `map.py::detRow` + the readiness evidence rows; the three-requirement `resolved` sentence in eight playbooks and `src/core/agents.md` |
> | 18. a number in prose answered to nobody | 2026-08-06 | `scripts/check_stated_facts.py`, wired into `.github/workflows/ci.yml` and `CLAUDE.md`'s Commands block |
> | 19. four rules true on one side of a pairing | ledger v0.20 | `ledger.LOG_ENTRY_PREFIXES`'s `cas_` + `_reopen_minimal`'s per-pin `CascadeEvent`; `Ledger.cascaded_by`, called by both arcs' tools; `ledger._CHALLENGE_SOURCES` on `challenge` **and** `premortem`; `add_proposals`'s `CLOSED_STATES` refusal; `allow_freeform` inside `_validate_question`; gates `tests/test_ledger.py::TestEveryForkThisRuntimeComposes` and the seven new cases in `TestComingBackIntoTheOpenSetIsGovernedToo` |
> | 21. the reopen leaves the settlement doors' carriers standing | ledger v0.22 | `ledger.SETTLEMENT_CARRIERS` + `REOPEN_DISPOSITIONS`, paid by `_reopen_minimal` -> `Ledger._invalidate_settlement_claims`; the `substate` clear moved into `_settle`; `unasked_verdict` · `question_offers` · `policy_preview` through `pin_read`/`readable_pins`, and `buildloop.py` · `agentready.py` · `challenger.py` with them; `add_proposals`'s fork requirement; gates `tests/test_ledger.py::TestTheWayBackOwesTheDoorsTheirCarriers` and `tests/test_mcp_tools.py::TestNoReadOnlyLedgerToolDiesOnAPinShape` (roster derived from `readOnlyHint`) |
> | 7. + 17g. two closures that held for one half | ledger v0.21 | `ledger.INTERVIEW_STATES`, read by `interview_view` and inlined as the map's `__ASKABLE__`; `map.py`'s `outOfReach` / `forkOptions` around `modeLine`; `Ledger.readable` + `ledger.pin_read` + `severity_rank` + `ledger.PIN_RULES` (with `collection_shape` / `entry_shape` in `nonconforming`); `ledger._MAY_BE_SILENT`; gates `tests/test_ledger.py::TestReadingAPinIsNeverTheOperationThatFails` and `tests/test_map.py::code_only` with its two plants |
> | 23. six rules paid at a set's members, unpaid for what satisfies the set | ledger v0.24 | `ledger.REOPEN_ARCS`'s third member with `ARC_MOVES` / `ARC_CASCADES` (and `REOPENED_SUBSTATES` composed from the arc table alone); `ledger.refuted_claim` + `VERIFICATION_RUNG_WRITERS` + the `xdr_` event's `rung_raised`; `ledger.PIN_WRITE_DOORS` + `Ledger._gate_closed`; `EVENT_RULES`' `brief_quote` with `interview._brief_entry` and the map's decision card; `tools._saved`; `tools._require_quote` + `ledger.QUOTED_RUNGS`; gates `tests/test_ledger.py::TestTheThirdArcPaysWhatTheOtherTwoPay` · `TestOnlyAFreshObservationRaisesARefutedClaim` · `TestFinishedWorkIsRefusedAtEveryDoorThatWritesToAPin` · `TestTheBriefOwesTheBrief`, `tests/test_mcp_tools.py::TestOneCommitPointForEveryLedgerWrite` · `TestOneRefusalForTheQuoteRule` · `TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach` |
> | 25. a write door reads the pin already in the file | ledger v0.26 | `Ledger.writable_pin` + `ledger.PIN_REQUIRED` (and `_rules_from`'s `required`), reached by all 14 per-pin write doors and by the tool layer's own lookups; `ledger.RUNG_WRITER_RUNGS` + `_writable_rung`, paid by all four rung writers; `_validate_question` through `_require_objects`; `resolve`'s observation read off the CALL; `PIN_SHAPES["kind"]` + `PIN_STRONGER["kind"]`; gates `tests/test_mcp_tools.py::TestNoWriteDoorDiesOnThePinAlreadyInTheFile` · `TestNoWriteDoorDiesOnAMemberOfAListArgument._lists_under`, `tests/test_ledger.py::TestAWriteOntoAPinThisRuntimeCannotReadIsRefused` · `TestOnlyAFreshObservationRaisesARefutedClaim`'s four new cases · `TestTheWayBackOwesTheDoorsTheirCarriers._carriers_the_doors_gate_on` · `TestTheShapeTableIsTheWritersOwnShapes::test_every_scalar_a_settlement_door_decides_on_has_a_membership_rule` |
> | 22. the two projections read a ledger nobody had guarded | ledger v0.23 | `ledger.read_collection` + `readable_ledger` (with `Ledger.readable` delegating to them), read by `map.render` · `instructions.render` · `graph` · `readiness` · `learning` · `agentready` · `mcp/tools`; `pin_read`'s `title`/`decision` and `ledger.POLICY_RULES` + `policy_read`; `severity_rank` as the package's ONE ordering; the map's `NONCONF_WHY` banner, its honest traffic light and `mount`'s thunk boundary; `build.py::_debris` + `shipped_files`; gates `tests/test_ledger.py::TestEveryReaderOfACollectionGoesThroughTheCarrier` · `TestOneSeverityOrderingForTheWholePackage` · `TestReadingAPolicyIsNeverTheOperationThatFails`, `tests/test_map.py::TestThePageIsRenderedFromWhatAReaderCanIndex` and the thunk row in `TestTheSafePathIsTheOnlyPath` |
> | 27. what a door reads while writing, and whether its report is true | ledger v0.28 | `tools._saved` moved to the end of every door (the answer computed first, `return <name>` after); `Ledger.writable_collection` + `Ledger.writable_pins`, reached by `add_pin` · `decide` · `_settle` · `add_policy` · `challenge` · `cross_derive` · `label_failure` · `reopen` · `_reopen_minimal` · `set_readiness`; `_next_id`'s `isinstance`; `foresight` + `cascaded_by` + `_invalidate_settlement_claims` through the read path; `tools.scope_check` / `readiness_assess` through `pin_read`; `readiness._churn` + `cochange.outside` short-circuit an empty zone; gates `tests/test_ledger.py::TestAWriteOntoACollectionThisRuntimeCannotReadIsRefused` (AST: `self.data[<collection>]` by subscript OR `.get` lives in one function) · `TestAWriteReadsEveryOtherPinThroughTheReadPath`, `tests/test_mcp_tools.py::TestADoorThatReportsFailureCommittedNothing` (positional AST + a trap derived from each door's own appended events, with a non-vacuity floor derived from who reads a radius) · `TestNoWriteDoorDiesOnAPinItIsNotWritingTo` (the corpus as a BYSTANDER, over both rosters) · `TestNoReadOnlyLedgerToolDiesOnAPinShape`'s widened membership rule + `_call` |
> | 26. the interview's fan-out counted paths, and a write door took no pin | ledger v0.27 | `ledger.downstream_of`, called by `interview_view` and `interview.funnel` and computed by neither; `interview.CATALOG_SOURCE` + `catalog_cluster` + `expand_catalog`'s `already_present`; gates `tests/test_ledger.py::TestOneAnswerForHowMuchAForkCollapses` (derived walk roster held to `OTHER_WALKS`, with its own non-vacuity floor) · `TestTheBriefOwesTheBrief`'s three new cases, `tests/test_mcp_tools.py::TestALedgerWideWriteDoorIsOnARosterToo` (the two rosters' union asserted to be every write door in the module) |
>
> **Closed does not mean nothing remains.** Fifteen residuals are listed here, recorded inside
> closed sections rather than fixed, each with the argument for leaving it — read the section before
> re-finding one. It is a selection, not the total: §23, §24, §26 and §27 carry further ones in their
> own *Residuals* subsections, and every one of those is an argument somebody has already had.
>
> - **§5** — `_reopen_minimal` cascades over `("decided", "resolved", "accepted")`, three states where
>   `SETTLED_STATES` has four (`deferred` excluded). Whether a `deferred` dependent rested on the
>   falsified truth is a real question and nothing has settled it; inventing a rationale for someone
>   else's tuple is how a hardcoded list acquires the authority of a decision. It is §17e's class one
>   file over, and `TestNoStateNameIsKeptInThisFile` covers `instructions.py`, not `ledger.py`, where
>   the states are the schema's own.
> - **§12** — a ledger written by v0.12–v0.17 may carry `resolution_mode: "asked"` stamped by the old
>   `not_offered` branch, and nothing can tell it from a standing demand. The stamp recorded no
>   reason, so no reader can recover one, and reconstructing it from the policies still in the file
>   would be the heuristic this repo forbids.
> - **§19** — `server.py::_decision_choices` builds the elicitation enum strictly from
>   `question.options`, so the **elicited** rung hands the human a closed menu whatever
>   `allow_freeform` says. It predates the round that found it (every fork this runtime composes
>   already sets the flag and already got a closed enum), and closing it is a protocol design
>   question rather than a symmetry fix — a "something else" row needs a second `ctx.elicit` for the
>   words, with its own decline path. The relay rung honours the flag today.
> - **§20** — `proposal_ref` is declared by the spec and read by no code; its only corpus mention is
>   prose in `ledger.py`, which is `check_schema_fields.py`'s declared limit #2 doing what the limit
>   says. Giving it a reader is a behaviour change in `learning.divergences`, not a correction.
> - **§20** — ~~`challenger.scan`, `buildloop.waves`, `learning.divergences` and `agentready.card`
>   still index pin fields directly.~~ **CLOSED by §21**, and not by reading: the derived read-tool
>   gate reported three of the four on its first run, because `build_waves` / `agent_ready` /
>   `challenge_oracle` are read-only MCP tools taking nothing but a ledger path — which is the same
>   class *and* the same exposure. `learning.divergences` passed the gate and is left as it was.
> - **§22** — `learning.divergences` and `agentready._challenges_for` read their COLLECTIONS through
>   the carrier now (§22's AST gate forces that) and still index the fields *inside* a pin or an
>   event directly. Left as it is, with the same argument `_pin_line` makes about `kind`: a field
>   that is only interpolated is not a field that is indexed, and substituting one with no failing
>   case is a change with no carrier.
> - **§25** — a scalar nested inside a declared object is still outside `PIN_SHAPES`, by that
>   table's own membership rule (*nothing indexes into a string*) — which is about what a reader
>   indexes INTO and says nothing about a missing KEY. `resolve`'s `i["status"]` and
>   `set_remediation_status`'s `item["id"]` are `.get` now, under the read path's own v0.18 rule,
>   and **no derived corpus can produce those cases**: the deliverable for gating that class is a
>   schema for the item, not a wider corpus.
> - **§25** — `apply_policy` writes to pins and takes no `pin_id`, so it is outside the derived
>   write-door roster by construction. It reaches `decide`, which now refuses an unreadable pin, so
>   the failure mode is a refusal rather than a crash — but the refusal aborts a cascade partway,
>   and what a half-applied policy owes its radius is a question nothing here settles.
> - **§25** — `confidence` and `resolution_mode` are closed vocabularies a pin carries and neither
>   joined the shape table, because the derivation used is *a carrier a settlement door decides
>   from* and no door branches a pin's fate on either. Widening it to every closed vocabulary is a
>   different rule and needs its own argument.
> - **§26** — a declared table can be told a lie. `OTHER_WALKS` and `WIDE` are *derived roster held
>   to a declared claim*, this repo's standard shape and its standard residual: an author may add a
>   downstream walk and declare it as something else. What the gate buys is that they must write the
>   sentence, and both messages say what the right answer is.
> - **§26** — `record_policy` twice with the same offer records two standing rules, and the second
>   has no radius (the first already settled every pin it reaches). Declared `creates` on the
>   argument that two elections are two acts; whether that is a duplicate is a question about what a
>   `Policy` records, and nothing settles it here.
> - **§26** — the catalog projection is idempotent per CLUSTER, not per catalog: a cluster renamed
>   or removed from `decision-catalog.json` leaves its pin behind with nothing to match and nothing
>   reporting it. Reporting it means deciding what an orphaned catalog pin means, which is the
>   catalog's lifecycle rather than this door's.
> - **§27** — `writable_pins` drops a `pins` entry that is not an object, and the door's return says
>   nothing about it. `nonconforming` reports it under `entry_shape` and `ledger_summary` shows it,
>   so the fact is not lost — but a caller who ran only the write door is not told that a record took
>   no part in the cascade it just triggered. Widening every write door's return shape to carry a
>   per-call nonconformance report is a change to eighteen response schemas, and what it would say is
>   already one read away.
> - **§27** — `readiness._churn` and `cochange.outside` now return early on an empty file set. The
>   argument is that every row either builds is gated on an intersection with that set, so the answer
>   was already `{}` / `[]`; nothing gates it, because a test that asserted "empty in, empty out"
>   would pass on both versions. It was made to keep the widened read-tool roster affordable —
>   `readiness_assess` read the repository's whole `git log` on every call, 1.29s each against 3102
>   derived cases.
> - **§3** — the two below.
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
>
> **The third shape, and it is the one about this file's own tooling — §2's third instance and both
> of §15's.** *A gate whose NAME quantifies over more than its BODY does.* A roster test that
> filtered its own input before comparing, so the "and nothing else is" half could not fire; an AST
> walk that said "no function may" and inspected only literal assignments, so the one line it was
> named for was invisible; a field-reader gate whose corpus contained the writers. All three passed
> green for their whole lives and all three were caught by **planting a violation** — never by
> reading. §18 is the standing entry for this shape: which classes now have a gate, which do not,
> and the argument for each.
>
> **The fourth shape, added by §26, and it is the third one turned on the ROSTER instead of the
> gate.** *A derived roster whose predicate quantifies over less than the danger does.* Three rounds
> derived every write-door roster as *a tool taking a `pin_id`*, which is a true and useful
> predicate and is not the same set as *a tool that writes*. Four tools were outside all of it, and
> nothing could report that, because a derivation reports what satisfies it and is silent about the
> rest — which is exactly what makes a derived roster feel safer than a written one. The same shape
> produced §26's first finding one layer down: two surfaces computed the same number, agreed with
> each other, and both answered a question nobody had stated out loud. The question that catches
> both: **say the predicate in words, then name what does the dangerous thing and does not satisfy
> it.**

Two of the original four (§1 and §2) were introduced *by the same session that closed four older bugs
of the identical class*, and the same thing has happened in every round since — §5 and §8 were opened
by the round that closed §1–§4's successors, §9–§16 by the round after that. That is the point of
writing them down rather than remembering them: this failure mode is not rare here and it is not
careless — it is what happens when you add state and stop at the layer that stores it.

The round that closed §15 kept the streak, and it is worth knowing that it did: fixing the
schema-field gate so it could tell a reader from a writer immediately surfaced **six** fields
written by the runtime and read by nothing, three of them the evidence a landing-zone verdict rests
on. They were closed in the same commit rather than filed here, because a gate's first run is the
one place this register's central rule inverts — *the finding is the gate working*, not a new gap.
The next session should expect the same from any instrument it sharpens.

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

**The order that was followed, and what it taught.** §5 first, then §9, §11, §12, §17f and §17g —
the rules that mis-fired rather than the surfaces that were missing — then the reader cluster **§6,
§7, §8, §13, §14, §16, §17a, §17d, §17e** as **one** change to the two reading surfaces, which is
what §14 asked for and is why they closed together. **§15 and §17c went last, and that ordering was
right for a reason worth keeping: §15 is a gate fix, and a gate fix pays out in findings.** The
moment `check_schema_fields.py` could tell a reader from a writer it reported six write-only fields
that had passed it since the day they were written — three of them the evidence a `harden_first`
verdict rests on. Fixing the instrument last means the instrument immediately measures a tree
somebody has just finished cleaning, and it still found six. Fixing it first would have found more,
and earlier.

**What replaces "what is left".** Nothing on this list is open, so the standing question is no
longer *which gap next* but *which class is still ungated* — that is §18, and it is written to be
the entry a cold session reads first.

**And the second standing question, which §20 added: which CLOSED section is closed for only half of
what it claims.** Two were, and both were closed by rounds that did the work well — §7 wrote the
right sentence and guarded it with the wrong condition, §17g stated a principle with no qualifier
and applied it to one of two collections. Neither is visible from inside the section; both were
visible the moment somebody re-ran the section's own method (open the page; break one field at a
time) against the tree as it now stands.

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

> **Read §19 next.** This section built the doors and built them well; the round after it found
> **four rules that hold on one side of a pairing and were absent on the other** — the cascade with
> no per-pin record, a radius re-derived from a substate nothing clears, an unvalidated `source`,
> and a closed-state check on one funnel door of two. Nothing below is retracted. What it did not
> ask is the question §19 is named for: *for every rule on a door, does the sibling door agree?*

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
  a carrier (`DecisionEvent.proposal_ref` points at it, and the funnel entry now lists it) —
  **[corrected by §20.4: there is no `proposal_ref` on a DecisionEvent. The election records the
  option id in `outcome`, and `learning.divergences` matches that against `proposals[].id`. The
  runtime carried the same false claim in a comment and in a shipped refusal message.]** Found by
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

## 7. The map renders no `resolution_mode` — **REOPENED, then CLOSED again 2026-08-06** (ledger v0.21)

> **This section was closed with the wrong guard, and the guard is the whole of §20.1.** The three
> sentences below are right. The condition around them was `SETTLED_STATES` alone, so the countdown
> printed on **six `detected` pins of this repo's own preview fixture** — pins that pose no fork and
> that `interview_view` does not return, i.e. a mechanism that cannot run, stated on the surface this
> section added to make the mode honest. Reach is now read off `ledger.INTERVIEW_STATES` and the
> pin's own options; a pin failing either half is told so. See **§20**.

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

## 15. Two gates check less than their names claim — **CLOSED 2026-08-06**

**Both were inverted, and both were verified by planting first.** The old shapes were reproduced
before anything was changed, because a gate you narrow without re-testing is worse than the loose
one — that is this section's own instruction and it decided the whole procedure.

**The AST gate — `tests/test_ledger.py::TestOneWriterForTheSettledStates`.** The question is
inverted exactly as the section prescribed: not *is this value a settled state*, which needs the
value to be readable, but **which functions assign `pin["state"]` at all**, which is decidable from
the assignment TARGET in every shape the value can take. `STATE_WRITERS` declares the five, each
with the transition it makes, and set equality against the source is the load-bearing half. Three
things changed beyond the shape:

- **A computed value outside `_settle` is refused outright**, not inspected. A gate that cannot read
  a value must not pass it, and the alternative — evaluating reachable constants — buys a guess.
- **The scope is `src/runtime/*.py` + `src/mcp/*.py`**, the same roots `TestEveryPathToDecideIsGated`
  uses. It used to be `ledger.py` alone, so a state write in `tools.py` was outside the gate named
  for *every* function.
- Three plants, each run: `pin["state"] = _STATE_BY_DOOR["resolve"]` in `cross_derive` (the exact
  blind spot — **passed green** before, fails now), a literal settled state outside `_settle` (the
  one case the old gate did catch), and a sixth writer added to `tools.py` (fails two of the three).

The irony worth recording: the invisible line was `pin["state"] = _STATE_BY_DOOR[door]`, which is
the line `_settle` **itself** is made of. The one write the class is named for was the one write it
could not see.

**The schema gate — `scripts/check_schema_fields.py`.** It now parses every Python source and blanks
the positions in which a name can only be a WRITE — a `Store`/`Del` subscript slice, a key in a dict
literal being built, a keyword argument, a parameter name — before the search runs. What survives is
everything a read can look like, including the JavaScript the map template carries inside a Python
string, which is a real reader and is not parseable as Python. Both directions were planted: a field
whose only mention is one dict-literal key in `ledger.py` fails; the same field given a `.get()`
passes.

**And then it found six.** This is the part that matters more than the fix:

```
evidence_determinism        readiness — the verdict is D2 over D0 evidence, "never merged"
independence_determinism    cross_derivations — were the providers distinct (checked)
agreement_determinism       cross_derivations — do the answers mean the same (judged)
open_pins_in_zone           readiness.evidence — the ledger's own broken ground
untested_files              readiness.evidence — no test reaches it
coupled_outside_zone        readiness.evidence — what historically moves with it
```

Every one had exactly one occurrence in the whole tree: the dict-literal key that writes it. Three
of them are the evidence a `harden_first` verdict rests on, and the spec's own rule for that object
is that the four carriers are *"reported separately and never merged into one score"* — a rule about
a **surface**, kept by no surface. So they were given readers rather than deleted (deleting would
re-litigate the determinism dial, which is a settled decision), on the card that already renders
their unsplit sibling, through **one** shared `detRow` — which incidentally removed a live §16
instance, since `verificationCard` printed an unrecognised determinism level bare. The preview
fixture's readiness evidence was hand-composed prose (`{cochange, coverage}`) rather than the four
keys `readiness.assess` actually writes, so it was corrected too: a fixture that cannot show a field
cannot check it. Verified in a browser, both themes, worst contrast 4.77:1 (dark) / 4.95:1 (light)
over the cards touched.

**What the fix does NOT buy, stated so nobody reads it as more.** A field read only by the module
that writes it still passes — the gate answers *is it read*, not *is it read on a surface a human
opens*. That second question is §14's, and it has no gate; §18 says why. Masking Python docstrings
and comments as well was measured and refused: it fails the tree on correct fields whose runtime
reader is a `**kwargs` spread or a `for k, v in …` loop.

### The original finding, kept verbatim

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

## 17. Seven residuals of the final review — **all CLOSED**

Two adversarial reviewers closed the seventh round. Their findings are here rather than fixed,
because the round's rule was that only defects it had *introduced* could be fixed in it — and
because a report dies with its session while this file does not. Each states what was verified and
why it matters; the closing notes were added as each was taken.

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

**17c — CLOSED 2026-08-06, and it was eight sites rather than three.** Every one now names the third
requirement: a `verification.rung` of `observed` or `cross_derived`, which `mcp:ledger_resolve`
refuses without. The five the finding did not name are the point — rescue's `phase-4-remediation.md`
said it a **second** time forty lines below the loop (*"`resolved` needs both"*), both
`phase-5-validate.md` playbooks said it, greenfield's `SKILL.md` said it, and `src/core/agents.md`
said it in the roster doctrine that gets vendored into **eight** shipped skills. A count taken from
the three sites a reviewer happened to open is the same shape as the defect it was reporting, and it
is the third time in this register a section's own enumeration turned out to be the smaller half
(compare §7's "six writers" and §12's).

The `rung` collision was resolved rather than preserved, and by naming the carriers: step 4 logs the
**`ladder_rung`** (an integer 1–7 on the `RemediationItem`/`BuildItem` — how small the intervention
was) and step 7 records **`verification.rung`** on the pin (how hard the result was checked). Both
names are the schema's own, so the disambiguation is not a gloss invented for the prose. Neither
constrains the other, which is stated because the collision made it look as though one might.

Not gated, and the reason is §18: *"the prose says a door demands two things and the door demands
three"* has no carrier a linter can anchor on — the door's requirement is a control-flow property
and the prose's claim is a sentence. What is gated is the adjacent, decidable half (§18's new
`check_stated_facts.py`), and the boundary between the two is exactly where mechanization stops.
The finding is kept verbatim.

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

> **17g was closed for ONE of the two collections, and the principle it quotes has no such
> qualifier.** `summary` and `interview_view` went on indexing `pin["state"]`, `pin["severity"]` and
> `pin["id"]` directly and died with a bare `KeyError` on six pin shapes — on files `map.render` and
> `instructions.render` read start to finish. Reproduced against this tree at `HEAD`, all six, and
> fixed as one guarded read (`Ledger.readable` + `pin_read`) with every substitution reported by a
> `PIN_RULES` entry. See **§20.2**.

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

## 18. Which recurring class still has no gate — **the standing answer, 2026-08-06**

Not a defect. This is the question the register exists to answer, written down so the next round
starts from it instead of re-deriving it. Five classes recur in the sections above. Two of them are
now gated, one was **newly** gated by the eighth round (`check_stated_facts.py`), and two are argued
below as not mechanizable — with the argument, not the verdict, because a verdict without one is
what gets re-litigated.

**§19 is the ninth round's answer, and it lands squarely in the first class below.** It also names
the sharpest form of that class's residual: the invariant a new door misses is most often one its
**sibling** door already enforces, which is a question a reader can actually ask — *for every rule,
record, refusal or return key on this door, which door does the same kind of thing, and does it
agree?* One row was added to the table for it; the rest of §19 is procedure, for the reason the
residual paragraph below already gives.

**§20 is the tenth's, and it splits across two classes below.** Its first two findings are the
sibling question asked of a **closed section** rather than of a door — *this round stated a
principle; name every place it applies and check the ones the round did not touch* — which is
procedure again, and one more row in the table. Its third finding is an instance of the ungated
class at the bottom of this section, and the count there is now five.

**§21 is the eleventh's, and it adds two rows rather than procedure — which is the first time in
four rounds that the answer was mechanizable.** Its question is narrower than the sibling one and
therefore decidable: *for every predicate that decides, enumerate the carriers it reads, and make
the enumeration a table the opposite arc is held to.* `SETTLEMENT_CARRIERS` is that table and its
gate reads the predicate's own AST. The second row is the one worth copying: a read-tool roster
**derived from the server's own `readOnlyHint`**, exercised against broken pin shapes — and its
first run reported three readers nobody had read for, which is the §20 residual closing itself.

**§22 is the twelfth's, and it adds six rows — the most mechanizable round yet, because its question
is lexical.** Two rounds hardened the ledger read path and neither reached `map.render` or
`instructions.render`. The reason is one sentence and it generalises: **a rule paid at a class's
METHODS is unpaid for every caller that holds the class's DATA instead of the class.** That is
decidable by an AST walk — *who names one of these collections* — where the sibling question is not,
and the answer is set equality against a tuple the schema owns. Its first two rows are that walk and
its severity twin; its last two are the same question asked of a page and of a build script rather
than of the runtime, which is where the class had also been sitting unlooked-at. §22 also produced
this section's cheapest lesson yet, and it did **not** come from a gate: the browser walk showed two
rule names on the map reading *"no sentence here describes this rule"*, because the table's first
draft quantified over two of the schema's three rule tuples. **Look at the thing.**

**§23 is the thirteenth's, and it adds seven rows — because its question is the most mechanizable
form the sibling question has taken.** §21 asked *enumerate the carriers a predicate reads*; §22
asked *who holds this class's data instead of the class*; this one asks **what satisfies a set's
definition without being in the set**, which is decidable wherever the definition is behaviour a
walk can see: a function that moves a pin back into the open set IS an arc, a tool that takes a
`pin_id` and finishes a write IS a per-pin write door, a function that writes a closing rung IS a
rung writer, a rung in `DECISION_EVIDENCE` IS something a caller can claim. Four of the seven rows
below are that walk. The other three are the same move at the tool layer — one commit point, one
refusal, one derived roster — and the round's own cheapest lesson came from the roster: **assert
WHICH refusal fires, not that one did.** The closed-work gate caught `set_question` answering *"already
poses a fork"* on a `resolved` pin, which is a true sentence that sends an agent to the wrong door.

**§25 is the fifteenth's, and it adds one row and one QUESTION about every row.** The row is the
per-pin write-door roster run against the derived corpus. The question is the one §24's clause
implies and nobody had asked of the gates themselves: *this rule was proved of the readers — name
every door that READS the record before it writes it.* All fourteen did, none of them was covered,
and the gate that catches it is not a new class but the read path's own corpus pointed at the write
path's own roster.

**§26 is the sixteenth's, and it adds two rows plus the sharpest question yet about a derived
roster.** Every roster this register has praised is set equality computed from the source, and §26
is the first time that shape *caused* a miss rather than caught one: three consecutive rounds
derived their rosters as *a tool taking a `pin_id`*, so the four tools that write without naming a
pin were outside all of it — by construction, invisibly, while every gate stayed green. The standing
answer therefore gains a second clause to sit beside §24's: **state a derivation's predicate out
loud, then name what does the dangerous thing and does not satisfy it.** Its other row is the one
worth copying for a different reason — the derived-walk gate asserts a set the tree does *not*
contain, and a gate whose expected answer is "nothing" can go silently vacuous in a way a set
equality cannot, so it carries its own floor: run the detector over the removed code and require it
to fire.

**§27 is the seventeenth's and the branch's last, and it adds four rows plus one class that had no
row at all.** Three of the four are the same moves one more time — a derived roster whose predicate
was too narrow (`required == ["ledger"]`), a rule paid at one record and unpaid for its neighbours,
a rule stated in prose and paid by nothing. The new one is **positional**: *the commit is the last
thing a door does*, which is checkable by AST over the statement list and is the only shape in this
section that asserts something about ORDER rather than about membership. It is worth copying because
the class it catches is invisible to every other gate here — a door whose behaviour is entirely
correct and whose REPORT is a claim nothing checked. The round also produced this section's third
instance of its own third shape: the widened read-tool roster passed with the fix reverted, because
its sentinel named the first pin in the file while every corpus loop APPENDS the malformed one. **A
gate is not the rule; a gate is a rule plus the case it runs on, and both have to be aimed.**

**§24 is the fourteenth's, and it does not add a class — it adds a QUESTION TO ASK OF EVERY ROW
ALREADY HERE: what corpus does this gate run against, and who wrote it?** Every family of gates
below is set equality computed from the source, which is exactly right and says nothing about the
*cases*. Three of the read path's gates were computed from the source and run against seven pin
shapes somebody had typed; eleven more shapes, all named by a table the repo already declared, were
enough to make all three fail. So the standing answer gains a clause: **a rule gets one carrier, a
structural test that quantifies over all its callers, and — where the schema can generate them — a
corpus derived rather than listed.** The test of whether a corpus is derived is simple and worth
applying to the rows below: if a field were added to the schema tomorrow, would this gate cover it
without anyone remembering? `tests/shape_corpus.py` is the first answer that says yes, and its own
non-vacuity floor (`test_every_declared_shape_has_a_probe_that_refuses_it`) exists because a derived
corpus can go silently empty in a way a written list cannot.

### Gated

**A new surface arrives without the invariant that governs the old one.** The register's most
repeated finding, and the only class with a *family* of gates rather than one. All of them share one
shape — **set equality computed from the source**, so a door added later fails on the day it is
added rather than on the day someone reads for it:

| The set | Where it is asserted |
|---|---|
| every caller of `Ledger.decide` | `tests/test_invariants.py::TestEveryPathToDecideIsGated::test_the_enumeration_is_complete` |
| every caller of `_settle` | `tests/test_ledger.py::TestOneWriterForTheSettledStates::test_every_door_reaches_the_single_writer` |
| every function that assigns `pin["state"]` | the same class's `test_the_enumeration_of_state_writers_is_complete` (2026-08-06 — §15) |
| every caller of `_reopen_minimal` | `TestComingBackIntoTheOpenSetIsGovernedToo` |
| every function that installs a fork past `_validate_question` | `tests/test_ledger.py::TestEveryForkThisRuntimeComposes` (2026-08-06 — §19) |
| every public mutator, classified | `TestEveryWritePassesAGovernedChannel::test_no_mutator_is_unclassified` |
| every `INTERNAL` mutator, reachable | `…::test_an_INTERNAL_mutator_is_actually_reached` |
| every writer of `resolution_mode: "asked"` | `TestAMarkWithNoClearingDoorIsWrittenForAStandingReason` |
| every write tool, named by a shipped playbook | `scripts/check_tool_carriers.py` |
| every served tool, over the wire | `tests/test_mcp_server.py::EXPECTED_TOOLS` / `WRITE_TOOLS` |
| every closed table the map reads | `tests/test_map.py::TestEveryClosedTableThePageReadsIsTheSchemas` |
| every field the read path substitutes, reported by a rule | `tests/test_ledger.py::TestReadingAPinIsNeverTheOperationThatFails::test_every_field_the_read_path_substitutes_has_a_rule_that_reports_it` (2026-08-06 — §20) |
| every carrier a settlement door reads, with what the reopen owes it | `tests/test_ledger.py::TestTheWayBackOwesTheDoorsTheirCarriers::test_every_carrier_a_settlement_door_reads_has_a_declared_disposition` (2026-08-06 — §21) |
| every read-only ledger tool, against a broken pin | `tests/test_mcp_tools.py::TestNoReadOnlyLedgerToolDiesOnAPinShape` — roster derived from `readOnlyHint` (2026-08-06 — §21) |
| every module that names one of the ledger's collections | `tests/test_ledger.py::TestEveryReaderOfACollectionGoesThroughTheCarrier` — names from `LEDGER_COLLECTIONS`, AST over `src/runtime` + `src/mcp` (2026-08-06 — §22) |
| every severity ordering in the package | `tests/test_ledger.py::TestOneSeverityOrderingForTheWholePackage::test_no_module_but_the_schema_carries_a_severity_ordering` — membership from `SEVERITIES` (2026-08-06 — §22) |
| every field `policy_read` substitutes, reported by a rule | `tests/test_ledger.py::TestReadingAPolicyIsNeverTheOperationThatFails` — `pin_read`'s twin for the third collection (2026-08-06 — §22) |
| every rule `nonconforming` can report, given a sentence on the map | `tests/test_map.py::…::test_every_rule_the_report_can_name_has_a_sentence_on_the_page` — union of `PIN_RULES` + `POLICY_RULES` + `EVENT_RULES` (2026-08-06 — §22) |
| every call to the page's one DOM sink, passing a thunk | `tests/test_map.py::TestTheSafePathIsTheOnlyPath::test_every_call_to_the_sink_hands_it_a_thunk_and_not_a_node` (2026-08-06 — §22) |
| the file count `--check` reports, asking the sweep's own question | `tests/test_roster_generation.py::…::test_the_number_reported_as_evidence_counts_the_tree_the_sweep_keeps` (2026-08-06 — §22) |
| every arc, with the two axes on which arcs differ | `tests/test_ledger.py::TestTheThirdArcPaysWhatTheOtherTwoPay` — `REOPEN_ARCS` ↔ `ARC_MOVES` ↔ `ARC_CASCADES` ↔ `_SUBSTATE_BY_ARC`, and every `REOPEN_BUCKETS` member reachable over the product of the two closed sets (2026-08-06 — §23) |
| every writer of a closing `verification.rung` | `tests/test_ledger.py::TestOnlyAFreshObservationRaisesARefutedClaim::test_every_writer_of_a_rung_declares_what_it_rests_on` — AST over both assignment shapes, set equality against `VERIFICATION_RUNG_WRITERS` (2026-08-06 — §23) |
| every per-pin write door an agent can reach, with what it does to FINISHED work | `tests/test_mcp_tools.py::TestFinishedWorkIsRefusedAtEveryWriteDoorAnAgentCanReach` — roster derived from the tools taking a `pin_id` and reaching `_saved`; expectation per door derived from `PIN_WRITE_DOORS` (2026-08-06 — §23) |
| every disposition in `PIN_WRITE_DOORS`, true of the code that carries it | `tests/test_ledger.py::TestFinishedWorkIsRefusedAtEveryDoorThatWritesToAPin::test_each_disposition_is_true_of_the_code_that_carries_it` — transitive call graph, per disposition (2026-08-06 — §23) |
| every rung in `DECISION_EVIDENCE`, with the field its claim rests on and the carrier that demands it | `tests/test_ledger.py::TestTheBriefOwesTheBrief::test_every_rung_owes_something_and_the_test_is_derived_from_the_vocabulary` (2026-08-06 — §23) |
| every ledger write in `mcp/tools.py`, finishing at one commit point | `tests/test_mcp_tools.py::TestOneCommitPointForEveryLedgerWrite` — names bound from `_open_existing`/`_open_or_create`, so a door that calls its ledger something else is caught too (2026-08-06 — §23) |
| every door that accepts the human's words, asking the one refusal for them | `tests/test_mcp_tools.py::TestOneRefusalForTheQuoteRule` — roster from the `human_answer` parameter; planted with a hand-written check that behaves identically (2026-08-06 — §23) |
| every per-pin write door, against every shape the schema can describe | `tests/test_mcp_tools.py::TestNoWriteDoorDiesOnThePinAlreadyInTheFile` — roster derived, corpus derived (`shape_corpus.broken_pins()`), plus *no write door looks a pin up any other way* (2026-08-07 — §25) |
| every writer of a `verification.rung`, held to its declared KIND | `tests/test_ledger.py::TestOnlyAFreshObservationRaisesARefutedClaim` — `RUNG_WRITER_RUNGS`, each writer paying under its own name (2026-08-07 — §25) |
| every walk of the pin dependency graph, with the question it answers | `tests/test_ledger.py::TestOneAnswerForHowMuchAForkCollapses` — AST over `src/runtime` + `src/mcp` (recurses while naming `depends_on`, or tests membership against one), set equality against `OTHER_WALKS`; carries its own non-vacuity floor (2026-08-07 — §26) |
| every write door in `mcp/tools.py`, on ONE of the two rosters | `tests/test_mcp_tools.py::TestALedgerWideWriteDoorIsOnARosterToo::test_the_two_rosters_together_are_every_write_door_in_this_module` — and each ledger-wide door declares what a second identical call does, exercised in both directions (2026-08-07 — §26) |
| every door that commits, committing LAST | `tests/test_mcp_tools.py::TestADoorThatReportsFailureCommittedNothing::test_the_commit_is_the_last_thing_every_door_does` — positional AST over every function reaching `_saved`; the behavioural half plants a `via` derived from each door's own appended events (2026-08-07 — §27) |
| every function that names a collection off `self.data`, by subscript OR `.get` | `tests/test_ledger.py::TestAWriteOntoACollectionThisRuntimeCannotReadIsRefused::test_nothing_reaches_a_collection_except_the_carrier` — one function may, with two non-vacuity floors (the carrier has callers; it is called with every `LEDGER_COLLECTIONS` name) (2026-08-07 — §27) |
| every write door, against every shape the schema can describe **as a BYSTANDER** | `tests/test_mcp_tools.py::TestNoWriteDoorDiesOnAPinItIsNotWritingTo` — the union of both write rosters × `shape_corpus.broken_pins()`, with a healthy target; the sibling one row up runs the same corpus as the TARGET (2026-08-07 — §27) |
| every read-only ledger tool **that also takes a `pin_id`** | the §21 row's own roster, membership rule corrected to *the FIRST required argument is the ledger* — it excluded a whole class, and both members of it crashed (2026-08-07 — §27) |
| the version this runtime stamps, accepted by the runtime that stamps it | `tests/test_ledger.py::TestThisRuntimeReadsWhatItWrites` — property plus the behavioural write-then-open; `READABLE_VERSIONS` now ends in `SCHEMA_VERSION`, so the failure is unreachable rather than merely tested (2026-08-07 — §26) |

**The residual, and it is not closable.** Each row gates *one* invariant. The class is *"the
invariant nobody thought to check at the new door"*, and no gate can enumerate invariants that do
not exist yet. What replaces it is the procedure the last four rounds ran and this one ran: before
finishing, enumerate every invariant the new surface is subject to and check each **at the
consumer**. That is a discipline, and saying so is more honest than a gate that would only cover the
invariants already known.

**A rule enforced at the write, with no reader.** Gated by `scripts/check_schema_fields.py` — and
only since §15, because until then the gate could not tell a reader from a writer and passed every
instance of the class it was built for. It found six the day it could. Its remaining limit is
declared in its own docstring and is real: it answers *is this field read*, never *is it read on a
surface a human opens*. Nothing answers the second question; see the argument under §14's traps for
why a schema gate is the wrong instrument for it.

### Newly gated by this round — `scripts/check_stated_facts.py`

**A claim in prose with no carrier**, restricted to the subset that is decidable. Three consecutive
rounds ended their report with the same paragraph — a stale number corrected *by hand*, named "for
scope honesty", with the sentence *"neither is covered by any gate, and that gap in the gate is not
fixed."* Three rounds is a class, not bad luck: `README.md`'s "592 → 720 → 738 → 770 tests green in
CI", `src/readme/keel-core.md`'s "MCP tools | **37**" while the server served 54, `CLAUDE.md`'s
ledger-spec version at v0.6 against a v0.16 spec. Every one was found by whoever happened to edit
the adjacent line, which means the ones nobody edited beside were still wrong — and two of them
were, when the gate first ran.

It checks a number the repo **computes** against the thing that computes it: `unittest`'s own
discovery for the suite size, the `@mcp.tool` decorations for the roster, `ledger.SCHEMA_VERSION`
for the schema. It holds no copy of any answer. Its scope excludes **this file**, on purpose and
structurally: a historical register quotes the numbers of the day they were filed.

Three things it taught, all of them by being run rather than reasoned about:

- It catches what `tests/test_tool_roster.py` cannot. That gate matches `<int> MCP tools` in two
  files; the table cell `| MCP tools | **58** |` is a different word order, which is precisely the
  shape the "37" shipped in. Verified by planting: the cell goes stale, the roster test stays green,
  this one fails.
- **A version in prose needed a convention, and the first draft found that out the hard way.** A
  spec version means *this arrived in v0.7* (history, true for ever) or *the spec is at v0.7*
  (currency, must be bumped). The draft matched `(spec v0.X)` and immediately called
  `verification-before-completion/SKILL.md`'s `` `correctness_unknown` (spec v0.7) `` stale, which
  it is not. Deciding which from the surrounding words is the heuristic this repo forbids its own
  linters, so the phrasing carries it: **a currency claim says `currently v0.X`**.
- **One check was built, run, and deleted — recorded so nobody rebuilds it.** *"No document may name
  a spec version higher than the runtime's, because history cannot be in the future"* needs no
  convention and looked free. Run, it reported `docs/packaging.md`'s
  `@earendil-works/pi-coding-agent v0.81.1`. The premise was the bug: a `v0.X` belongs to whatever
  the sentence is about, and this repo legitimately names other projects' versions. There is no
  lexical carrier for *which project a version token belongs to*.

**Where the class stops being decidable, and this boundary IS the deliverable.** §17c is the other
half of the same class and got no gate: *"the playbook says a pin closes on two things, the door
demands three."* The door's requirement is a control-flow property of `settlement_verdict`; the
prose's claim is a sentence. Joining them means reading the sentence for meaning, which is the one
thing that is never allowed here. So the line is: **a number the repo computes is gated; a behaviour
the repo implements is not.** Anything proposed for this class in future should be checked against
that line first.

### Newly gated since — `scripts/check_packaging_wire.py` (2026-08-13)

**A number the repo MEASURED, published with its method, and never ran again.** A third position on
the line above, and it had been sitting in plain sight inside the very document that argues for
carriers: `docs/packaging.md`'s tool-surface section states five figures — ~98 k characters on the
wire, ≈24 k tokens, a ~1,410-character median tool object, a 1,405-character longest description, a
335-character `instructions` string — writes out the exact procedure to re-derive them, and then
**admits in the same paragraph** that *"these four have no gate."* Everything the section argues
rests on them (*"roughly a fifth of a 128 k window before the conversation starts"*, *"about 640 of
headroom"*), and every docstring anybody edits moves them. A published method with nobody executing
it is the carrier-less claim wearing the costume of a measured one, which is why it survived a gate
built specifically for stale numbers.

Three things it settled, and the first is the reason it is a second file rather than seven more rows
in `check_stated_facts.py`:

- **The two gates split on exactness, not on subject.** That one compares `match.group(1) ==
  str(truth)` because its facts are *counts*; these are rounded by construction (`~98 k`, `≈24 k`)
  and rightly so. Loosening the exact gate to admit a tolerance would weaken every count it holds.
  So the tolerance is declared here instead — **5%, on the ARGUMENT the number carries** — and cost
  seals it: an AST walk under a second there, a PEP 723 resolve plus an MCP handshake here.
- **The unit was the soft spot, exactly as §31 residual 1 said it would be.** Claude Code truncates
  descriptions *"at 2KB each"* — bytes — while every figure in the section is characters, and this
  repo's prose is full of three-byte em dashes: the longest description is 1,405 characters and
  **1,413 bytes**. The gate enforces the ceiling in the host's unit and checks the prose in its own.
  Two rounds have now found the same defect shape at two layers; treat a host limit's unit as a
  thing to verify, never to assume.
- **It is not only a prose-checker**, which is what earns it a CI slot: it fails when any tool
  description or the server's `instructions` crosses the 2 KB ceiling, and that truncation is
  **silent** — the agent selects by the text it never sees clipped. `tests/test_packaging_wire.py`
  drives the prose half with a doctored document and a fake measurement, because a gate whose
  failure nobody has watched is a gate nobody has tested.

### Not gated, with the argument

**A test named for an invariant it does not check** (and its consequence, *a gate that has been
asked and answered so nobody asks again*). **Six** instances are on record: §2's roster test
filtering its own input, §15's two, the near-miss the reader-cluster round caught in a DOM rather
than in CI, **§20's** — `TestTheWholeEnvelopeHasAReader`, whose docstring said *"not a word search"*
over a body that was one, so a comment naming the field satisfied it — and **§26's**, which is the
class in its mildest and therefore most likely form: `TestTheBriefOwesTheBrief` reached the door
`interview._brief_entry` with exactly one input, a bare string, which exercises one half of a
two-half condition. Rewriting `if not outcome or not quote` to `if not quote` left the whole suite
green. The fifth and sixth are both in gates this register itself built, which is the sharpest form
of the class: the round that writes the gate is the round least likely to plant against it. It is
the worst class in this repo and it is the one with no gate.

§26's instance also names the cheapest partial answer available, and it is not a gate either: **when
a rule is a conjunction, derive the refusal's cases from its terms** — `HALVES` is three tuples
computed from the two halves of the pair, so deleting either half fails. That works wherever the
rule's structure is visible in one expression, which is a real subset and not the class.

The obvious mechanization was measured and refused. *"Every test method must contain at least one
assertion"* is an AST walk of about fifteen lines; run over `tests/`, it reports **0** today. It is
refused not because it finds nothing but because of what it would claim: every instance on record
**had** assertions — they quantified over less than the docstring did, filtered their own input, or
matched only literals. A gate named *a test named for an invariant it does not check* whose body
checks *a test with no assertion at all* would be a gate whose name quantifies over more than its
body does, which is **this class**, added to the repo under this class's own name. That is the
argument; it is not an affordability argument and it does not get cheaper next round.

What actually catches it is written into every closing note above and is a procedure, not a file:
**plant the violation and watch it fail, before and after.** Every gate this register has fixed or
built was verified that way — §2's roster row, §4's interpreter branches, §12's eighth writer and
its clearing door, §6's old palette, §15's three state-write plants and two schema-field plants,
§18's three stale-number plants, §20's two (break the reader; then add a comment naming it), §25's
six, and §26's five (revert the walk; put the recursion back inside `funnel`; drop the idempotence
guard; remove a door from the roster; delete half the brief condition). The one rule that
generalises: a gate whose failure you have never seen is a gate you have not tested, and a green run
is not evidence about it.

**A classification declared inside a derived roster** (2026-08-07 — §26). Every roster family in
the *Gated* table above is set equality computed from the source, and several now carry a declared
CLAIM per member: what a `PIN_WRITE_DOORS` method does to finished work, what kind of rung writer a
function is, what question a dependency-graph walk answers, whether a ledger-wide door projects or
creates. The derivation is mechanical; the claim is a sentence a human writes, and a wrong sentence
passes. That is not fixable by a wider gate — the whole point of the declaration is to hold the part
that is not decidable — and it is not free either: it converts *nobody noticed* into *somebody wrote
it down*, which is the only reliable step. Where a claim's behaviour IS decidable, assert it
(`TestALedgerWideWriteDoorIsOnARosterToo` runs both dispositions; `PIN_WRITE_DOORS`' dispositions are
asserted against the transitive call graph). Where it is not, the declaration is the deliverable.

**A claim about a HOST.** Named here for completeness because it is the class `MEMORY.md` keeps its
own entry for, and it is ungated by construction: the carrier lives in somebody else's repository.
The discipline is the one §3 and `docs/packaging.md` already state — cite the function that
*consumes* the value, never the type that holds it, and mark what was read rather than observed.

---

## 19. Four rules true on one side of a pairing, absent on the other — **CLOSED 2026-08-06** (ledger v0.20)

§5 added the two reopen arcs, and added them well: no outcome on either signature, their own
predicate, a single writer, `reopened` recorded instead of inferred. This section is what it left.
Every finding below was **observed over real `uv run --script` stdio against the shipped
`plugins/keel-core/mcp/server.py`** before it was a test, and every one of them is the same shape:
*a door that does the same kind of thing as its sibling, and does it differently.* All six passed
772 tests and eight gates.

### Verified — the six, and what each returned

1. **The cascade moved pins with no record.** Three pins each walked
   `add_pin → record_decision → add_remediation → done → resolve`. One `ledger_reopen` on the root
   took all three back into the open set; the log held `ev_ stl_ ev_ stl_ ev_ stl_ rev_` — one
   entry for the arc and **nothing** for the two pins it un-finished. `_settle` appends a per-pin
   `stl_` for every settlement. Finished work was un-finished with no trail, which is the exact
   asymmetry the v0.16 settlement work existed to remove one direction over.
2. **`also_reopened` was re-derived, not reported.** `tools.py` computed it as every pin with
   `substate == "reopened"` and `state == "needs_input"` — and **nothing clears that substate**.
   Observed: after a legitimate cascade `pin_0001 → pin_0002, pin_0003`, a later `ledger_reopen` on
   an unrelated closed pin returned `also_reopened: ["pin_0001","pin_0002","pin_0003"]`, none of
   which that call touched. v0.16 removed this exact read from `cross_derive`'s return shape; the
   tool layer re-introduced it one layer up, against the field the arc writes.
3. **`ledger_challenge` cascaded the same reopen and reported nothing.** `pin_0006` (`resolved`,
   `depends_on: [pin_0005]`) was moved to `needs_input`/`challenged` by a challenge on `pin_0005`
   and appeared in no key of the response. Two arcs, one predicate, one writer, one commit, and
   their radius reporting was one over.
4. **`add_proposals` had no closed-state check** while `set_question` — same commit, same funnel —
   refused `CLOSED_STATES`. Observed: `ledger_add_proposals` succeeded on an `accepted` pin and on a
   `deferred` one, writing `brainstorm.proposals` onto work whose question had stopped being asked.
5. **`allow_freeform` was enforced at one door of two.** `ledger_add_pin(question={prompt,
   options})` with no flag succeeded; `ledger_set_question` with the **byte-identical** dict was
   refused with *"a fork composed after the fact must set allow_freeform"*. §10 wrote that rule to
   stop an agent handing the human a closed menu it wrote itself, at the newer and quieter door.
6. **`Ledger.challenge(source=…)` took any string** while `Ledger.reopen(source=…)` validated
   against `feedback:<FLIP_SIGNAL_SOURCES>`. Observed:
   `ledger_challenge(..., upheld=true, source="interview")` was accepted and stored
   `("chl_0002", "interview")` — a ChallengeEvent signed with the value that means *a human elected
   this*, which then reopened a human's `decided` pin.

### Why it matters

Each one defeats the argument its own arc rests on. The arcs are safe to hand an agent **because
they write no outcome** — and 6 let one sign itself as the door that does. The settlement table's
whole claim is that *"how did this pin stop being open, and on whose authority"* is answerable for
every door — and 1 left the opposite direction unanswerable for every pin but one. 2 is the
package's own no-heuristics rule broken in the tool layer: an uncleared substate is not a carrier
for *what this call did*. 5 is worse than an omission, because `add_pin` is where nearly every fork
in a rescue is born, so the rule was absent exactly where it applies most.

### Done looks like

- `CascadeEvent` (`cas_`, the seventh entry in `LOG_ENTRY_PREFIXES`) — one per pin the closure
  sweeps up, carrying `arc`, `via`, `from_state`, `to_state`, `substate`. The origin pin gets none,
  on `_settle`'s own rule: its `rev_`/`chl_` event already carries `reopened`.
- `Ledger.cascaded_by(event_id)` — one reader, two callers, so the arcs cannot report differently.
  `mcp:ledger_challenge` gained `also_reopened`; `mcp:ledger_reopen`'s stopped being a derivation.
- `ledger._CHALLENGE_SOURCES`, composed from `CHALLENGE_ORIGINS` the way `_FEEDBACK_SOURCES` is
  composed from `FLIP_SIGNAL_SOURCES`. One member, and the singleton is the roster's own answer:
  `core/agents.md` makes the challenger *"the one reopen path at the wave checkpoint"* and says in
  the same paragraph why the reviewer is not one. `premortem` — the same role's second mode, same
  parameter, same default — is held to the same list.
- `add_proposals` refuses `CLOSED_STATES` in `set_question`'s words; `decided` stays open to both,
  because the human may re-elect and laying out the alternatives is what a brainstorm is for.
- `allow_freeform` moved into `_validate_question`, so the rule holds at every door that composes a
  fork, including any added later. Both doors now raise the **same string** — asserted.
- The map's trail card grew a `cas_` row; `scripts/preview_map.py` produces one through the real
  doors, so the row is verified by something rather than by nobody.

### Prove it

`tests/test_ledger.py::TestComingBackIntoTheOpenSetIsGovernedToo` —
`test_every_pin_the_cascade_moves_gets_the_record_a_settlement_gets`,
`test_the_origin_pin_gets_no_second_record_because_its_own_arc_event_carries_it`,
`test_the_radius_is_read_off_the_records_and_not_off_a_substate_nothing_clears`,
`test_both_arcs_hold_their_source_to_a_closed_vocabulary`,
`test_the_challengers_other_mode_answers_the_same_way`, `test_both_funnel_doors_refuse_finished_work`,
`test_both_doors_that_compose_a_fork_require_the_way_out`; plus
`tests/test_ledger.py::TestEveryForkThisRuntimeComposes`, which is inverted the way §15 inverted its
two gates — it enumerates the functions that install a fork **without** passing a validator and holds
that set to a declared dict. It found a composer that was not in the first draft of that dict
(`mark_correctness_unknown`), which is the only kind of evidence an inverted gate can give.
`tests/test_mcp_tools.py::TestSettlingAPinThroughTheAgentsOwnDoors` carries the same five at the
boundary the reproductions used.

### Traps

- **`_reopen_minimal` still cascades over three states, not four.** §5's residual is unchanged and
  deliberately so: whether a `deferred` dependent rested on the falsified truth is a real question
  and nothing has settled it. Do not "fix" it while adding the record.
- **`allow_freeform: false` is no longer writable through any door, and its readers stay.**
  `mcp:record_decision` still refuses a freeform answer the question does not permit, and
  `decision_prompt` still carries the flag, because a rule enforced at the write governs no file
  that already exists. `test_invariants.py` exercises that refusal on a ledger whose flag is flipped
  on disk, which is the only way such a file can now arise. Do not delete the branch as dead.
- **The elicitation path does not honour `allow_freeform`, and this round did not fix it.** Found
  while verifying the rule's consumers rather than assuming them: `server.py::_decision_choices`
  builds the enum strictly from `question.options`, so on the strong rung the human is handed a
  closed menu whatever the flag says. It predates this round — every pin `surface_assumption`,
  `cross_derive` and `interview._fork_question` create already set the flag and already gets a
  closed enum — and closing it is a protocol design question (a "something else" row needs a second
  `ctx.elicit` for the words, with its own decline path), not a symmetry fix. **Registered here,
  not built.** The relay rung honours the flag today; the elicited rung does not.

---

## 20. Two closures that held for one half of what they claimed — **CLOSED 2026-08-06** (ledger v0.21)

§19 asked, of a door, what its sibling does. This section is that question asked **backwards, of
work already finished**: §7 and §17g were closed, correctly, and each left the other half of its own
claim standing. Both were found the way they were found the first time — by opening the page in a
browser, and by sweeping the four reading surfaces one mutation at a time.

### Verified — the four, and what each did

1. **§7's countdown printed on pins no interview reads.** `modeLine` was guarded on `SETTLED_STATES`
   alone. Observed in Chromium on `.preview/map.html`: `pin_0003` *"Two auth flows coexist"* is
   `detected`, carries **no `question` at all**, and rendered *"if you say nothing, the interview
   settles this with the proposed answer — here, silence IS the answer"* verbatim. Six of the
   fixture's pins did. `interview_view` selects three states and `detected` is not one of them, and
   `unasked_verdict` refuses a pin whose own question does not offer the outcome (`not_offered`) —
   so no host can ask such a pin and no policy may take it. The page stated a mechanism that cannot
   run, on the surface §7 added to make the mode honest.
2. **§17g's principle was applied to the log and not to the pins.** Six shapes, each reproduced
   against `HEAD` before the fix: a severity outside `SEVERITIES` (`KeyError: 'critical'`), a
   severity missing, a severity `null` (`KeyError: None`), a state missing, an id missing, and an
   absent `pins` key. Every one killed **both** `Ledger.summary()` and `Ledger.interview_view()`, on
   files `map.render` and `instructions.render` read start to finish without complaint. `summary` is
   what an agent calls BEFORE acting, on a file it did not write.
3. **`TestTheWholeEnvelopeHasAReader` was a word search calling itself otherwise.** Its docstring
   says the template must REFERENCE the field, *"not a word search"*; its body was
   `assertIn(f"p.{field}", _TEMPLATE)`. Proved by planting: replacing the only reader
   (`p.premortem` → `p['premortem']`) is caught, and then **adding a comment naming the field makes
   it pass again** with no reader on the page at all.
4. **A shipped refusal message named a field that does not exist.** `add_proposals` asserted, in a
   comment and in the `LedgerError` an agent reads, that `DecisionEvent.proposal_ref` points at a
   proposal id. Read at the writer (`decide` composes ten keys and that is not one of them) and at
   the reader (`learning.divergences` matches `pin.decision.outcome` against `proposals[].id`
   directly): the spec puts `proposal_ref` on `question.options[]`, where an option points back at
   the proposal it was fed by. The runtime was wrong, not the spec.

### Why it matters

1 and 2 are one failure in two directions, and it is the one this register keeps naming: a closed
section is a **claim about a class**, and the class is where the next instance lives. §17g's own
closing note quotes its principle with no qualifier — *reading a ledger is never the operation that
fails on it* — one collection away from where it was applied. §7 built the sentence a reader acts on
and guarded it with the condition already in the file rather than the one the interview uses. 3 is
§18's ungated class, fifth instance, and the first found in a gate this register itself built. 4 is
small and is corrected anyway, because a refusal message is the one sentence an agent reads at the
moment it is confused.

### Done looks like

- **`ledger.INTERVIEW_STATES`** — `OPEN_STATES` minus `detected`, read by `interview_view` (whose
  literal it replaces) and inlined into the page as `__ASKABLE__`, exactly as `SETTLED_STATES` is.
  `modeLine` asks it plus the pin's own `question.options`, and a pin failing either half gets
  *"nothing will settle this one: … so no interview can ask it and no standing rule may take it"* —
  because silence where a countdown used to be is its own claim, and `mcp:ledger_set_question` is
  the door that answers it.
- **One guarded reading path, not six guards**: `Ledger.readable(name)` for the container (all three
  of `LEDGER_COLLECTIONS`, because `summary` read each as `self.data[…]` and died the same way on
  each), `pin_read(pin)` for the five fields the readers index, `severity_rank` for the ordering.
  Every substitution has a declared direction — an unrankable severity sorts **last** and the pin
  stays in the view, and `assign_resolution_modes` gives it `asked` over `_MAY_BE_SILENT`, the
  threshold rule's own complement.
- **`PIN_RULES`**, which is to a pin what `EVENT_RULES` is to a DecisionEvent: replayed by
  `nonconforming`, reported in `pre_rule_events` — plus `collection_shape` and `entry_shape`,
  reported there without being in a table for `log_entry_kind`'s own reason. Nothing is substituted
  in silence, and a file with an unreadable pin does not get its `version` raised.
- **`tests/test_map.py::code_only`** — the template with its comments blanked, so a reference can be
  told from a mention. A scanner and not a `re.sub`, because this template carries regex literals
  holding both quote characters, CSS block comments, division, and **nested** tagged templates:
  matching backticks pairwise reads three of the file's own comment blocks as string content, which
  the first draft did, leaving 30 markers standing.
- `add_proposals`' comment and refusal now name a carrier that exists.

### Prove it

`tests/test_ledger.py::TestReadingAPinIsNeverTheOperationThatFails` — every shape above against all
four reading surfaces plus `interview.funnel`, the rule each substitution is reported under, the
version floor, the sort position of an unrankable severity, and two inverted checks: every field
`pin_read` substitutes must have a `PIN_RULES` entry (a silent substitution fails there), and
`interview_view` must select from `INTERVIEW_STATES` by AST rather than from a literal.
`tests/test_map.py::…::test_the_reference_check_is_not_satisfied_by_a_comment` plants both variants;
`test_the_strip_leaves_no_comment_marker_and_no_landmark_behind` checks the scanner's own premise in
both directions; `test_the_pages_askable_states_are_the_interviews_own` holds the inlined set to the
schema; `test_the_fixture_carries_a_pin_the_interview_cannot_reach` keeps the new sentence lookable
at in a browser.

Observed, not assumed: the six `KeyError`s were reproduced against `git show HEAD:src/runtime/ledger.py`
and all six now answer; `ledger_summary` was run over real `uv run --script` stdio from a foreign cwd
against the shipped `plugins/keel-core/mcp/server.py` on a file broken four ways and returned
`pre_rule_events: {entry_shape: 1, collection_shape: 1, pin_severity: 1, pin_state: 1}` beside
`by_state: {"needs_input": 1, "": 1}`; and the map was re-opened in Chromium, where the countdown now
renders on exactly one pin (`pin_0017`, `needs_input`, two options) and the six `detected` pins carry
the honest sentence instead.

### Traps

- **`proposal_ref` is declared by the spec and read by no code.** Its only occurrence in
  `check_schema_fields.py`'s corpus is the now-corrected prose in `ledger.py` — that gate's declared
  limit #2 doing exactly what the limit says, on a field the module does not even write. Registered
  rather than fixed: giving it a reader means making `learning.divergences` follow an option's
  `proposal_ref` where the option id differs from the proposal id, which is a behaviour change
  nobody asked for and needs its own doctrine. Do not delete the mention without either giving the
  field a reader or removing it from the spec.
- **The other consumers of a pin still index its fields directly** — `challenger.scan`,
  `buildloop.waves`, `learning.divergences`, `agentready.card`. They are not among the four reading
  surfaces and they run over a ledger the agent has just built, but the class is the same one, and
  the next round should either extend the guarded read to them or write down why not.
  **§21 closed three of the four**, and the way it happened is the point: the derived read-tool gate
  reported them without anybody reading for them, because `build_waves` / `agent_ready` /
  `challenge_oracle` are read-only MCP tools taking nothing but a ledger path. The residual was
  right about the class and wrong that these run only over a ledger the agent just built.
  **§22 closed the fourth's container half and left its field half standing, on purpose.**
  `learning.divergences` and `agentready._challenges_for` read their collections through
  `Ledger.readable` now — that is forced, by §22's own AST gate — and both still index the fields
  *inside* a pin or an event directly. That stays registered rather than fixed: it is the same
  argument `_pin_line` makes about `kind`, one module over. A field only interpolated is not a field
  indexed, and substituting one without a failing case is a change with no carrier.
- **Do not "simplify" `modeLine`'s two guards into one.** `SETTLED` and `ASKABLE` answer different
  questions — *is the mode history* and *can the interview reach this at all* — and the right output
  differs: silence for the first, an explanation for the second.
- **`assign_resolution_modes` still writes a mode onto `detected` pins**, deliberately. The mark is
  anticipatory: `set_question` moves such a pin to `needs_input`, and the mode is already there when
  it arrives. What was wrong was the reader, not the write.

---

## 21. The reopen leaves the carriers the settlement doors gate on — **CLOSED 2026-08-06** (ledger v0.22)

Four findings from an adversarial review that ran every one over real
`uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd. Same class as §19 and
§20, one layer further in: **a rule established at the doors it was written for, on an object whose
other doors kept the old behaviour.**

### Verified

**a. [HIGH] `_reopen_minimal` writes `state`, `substate` and `resolution_mode` and leaves the pin's
own claims exactly as the closed pin had them.** Observed:

```
add_pin(defect) -> add_remediation -> done -> resolve(evidence=…, rung="observed")
   -> ledger_reopen(fired="incident", reason="p95 blew the threshold")
{"reopened": true, "state": "needs_input", "substate": "reopened"}
   pin.verification == {"rung": "observed"}          # the claim the incident just refuted
   -> ledger_resolve(evidence="no new observation — the same staging run")
{"isError": false, "state": "resolved", "verification": {"rung": "observed"}}
```

`settlement_verdict` reads that envelope to decide whether the pin may close, and the envelope is
the **single** carrier of *how hard was this checked* by design (v0.16's "one carrier, read on both
sides"). So the gate whose entire purpose is *`resolved` means OBSERVED* was opened by the evidence
the reopen exists to invalidate.

**b. [MEDIUM] `decide` clears `substate`; `_settle` — documented as "THE only writer of a settled
state … so the gate cannot be a rule each door remembers" — does not.** Observed on the fully honest
path (reopen, fresh remediation, fresh evidence, an explicit `rung="observed"`): the pin ends
`state=resolved substate=reopened`, and `REOPENED_SUBSTATES` defines that mark as *disputed and not
re-answered*. Two consumers then contradict each other about one object.

**c. [MEDIUM] `Ledger.policy_preview` — *"Read-only"* in its own first line, served as the read-only
MCP tool `policy_preview` — indexes `pin["id"]` and, through `unasked_verdict`, `pin["state"]` and
`pin["severity"]`.** Observed on a two-pin ledger whose second pin carries no `severity`:
`ledger_summary` and `interview_next` both answered (v0.21 hardened exactly those two) and
`policy_preview` returned `isError: true` with the body `'severity'`. The principle has no
qualifier, and it had been applied to two readers of three.

**d. [LOW] `add_proposals` refuses `CLOSED_STATES` in `set_question`'s words (v0.20) and silently
accepts a `detected` pin**, where its own output is unreachable by construction: it moves
`needs_input -> brainstorming`, so a `detected` pin keeps the state it has — outside
`INTERVIEW_STATES` — and the proposals reach no surface on any host. Observed: `isError: false`,
`{"state": "detected", "proposals": ["prop_1", "prop_2"]}`, `interview_next` then `total_open: 0`.

### Why it matters

(a) is the settlement table's own invariant falsified from the one direction it does not govern. The
whole v0.16/v0.17 design rests on *`resolved` means observed*, and an incident is the strongest
possible statement that the observation was wrong — so a reopen that leaves the claim standing makes
the incident the one event that changes nothing a gate reads. (b) and (d) are rules living in a door
instead of in a carrier, which is this repo's most-repeated finding. (c) is a read tool that can be
the operation that fails on the file it was asked about, at the moment a human is being shown a
blast radius they are about to elect.

### Done looks like

- `ledger.SETTLEMENT_CARRIERS` — every carrier `settlement_verdict` reads, with what the way back
  owes it (`rewritten` / `invalidated` / `not_a_claim`), and `_reopen_minimal` →
  `_invalidate_settlement_claims` as the one place that pays. `verification` is **demoted, never
  deleted**: the rung comes off, `blocked_by` says what refuted it, and the log keeps both events.
- `_settle` clears the dispute mark on every door whose destination is in `SETTLED_STATES` —
  derived from `_STATE_BY_DOOR`, so `correctness_unknown` keeps it on purpose.
- `unasked_verdict`, `question_offers` and `policy_preview` read through `pin_read` /
  `readable_pins`, and the threshold is asked of `_MAY_BE_SILENT` so an unrankable severity is
  **held back** rather than defaulted.
- `add_proposals` requires the pin to pose a fork, after the closed-state check.

### The gates, and what the first run of one of them found

- `tests/test_ledger.py::TestTheWayBackOwesTheDoorsTheirCarriers` — the structural half reads every
  `pin[…]` / `pin.get(…)` key off `settlement_verdict`'s **own AST** and demands set equality with
  `SETTLEMENT_CARRIERS`, so a door gating on a fifth carrier fails until the arcs are told what it
  is owed. Plus the behavioural half, the reproduction verbatim, the cascade, the dispute mark over
  all five doors, and `add_proposals` over the whole `STATES` vocabulary.
- `tests/test_mcp_tools.py::TestNoReadOnlyLedgerToolDiesOnAPinShape` — the roster is **derived from
  the server's own `readOnlyHint`** (a hand-kept list would have contained exactly the two readers
  already fixed), and the assertion distinguishes a refusal about the CALL from death on the FILE:
  an indexing error escaping to the caller. **Its first run reported three more:** `build_waves`,
  `agent_ready` and `challenge_oracle`, i.e. `buildloop.py`, `agentready.py` and `challenger.py` —
  which is precisely the residual §20 registered (*"not among the four reading surfaces … but it is
  the same class"*). All three were fixed in the same commit, on §15's rule: **a gate's first run is
  the one place this register's rule inverts — the finding is the gate working.**
- **And the first draft of that gate passed a plant, which is §18's third shape happening inside
  the round that was closing its first.** Called with its required argument alone, `policy_preview`
  refuses on *its own* arguments — a policy needs a rule, a scope and an outcome — and never opens a
  pin: so the roster listed the very tool the finding was reproduced on, reverting the fix left the
  gate green, and the gate quantified over more than its body exercised. Caught by planting
  `pin["id"]` back, never by reading. `MINIMAL_CALL` declares the legitimate call per tool, set
  equality holds it to the derived roster, and `test_every_minimal_call_reaches_the_file` asserts
  each call simply answers on a well-formed ledger — which is what makes the broken-ledger run an
  exercise of the body. Every gate this round added was then re-planted: a new `pin.get(…)` inside
  `settlement_verdict`, `_reopen_minimal` no longer paying, the raw `pin["id"]`, and
  `_NEVER_SILENT` back in place of `_MAY_BE_SILENT`. All four fire.

### Prove it

```bash
python -m unittest tests.test_ledger tests.test_mcp_tools     # and the full suite
python scripts/build.py --check && python scripts/check_schema_fields.py
```
Then over real stdio, from a directory that is not this repo: walk a defect to `resolved` at the
`observed` rung, `ledger_reopen(fired="incident")`, and try to close it again with no new rung —
`unverified`. Hand-edit a `severity` out of one pin and call `policy_preview` — it answers.
`ledger_add_proposals` on a `detected` pin — refused, naming `set_question`.

### Traps

- **`verification` is demoted, not deleted.** An envelope that is absent says *less* than one at a
  weak rung (v0.16's own words), so removing it would be the stronger claim in the wrong direction —
  and the pin would stop telling a human why it cannot close.
- **A pin that claimed nothing has nothing taken back.** Writing an envelope onto a pin that carries
  none manufactures a statement the file never made — the overwrite v0.16 removed twice.
- **`remediation` is deliberately `not_a_claim`.** The items record that actions were *taken*, which
  stayed true; what did not survive is the claim they *worked*, and that is `verification`. Marking
  them `todo` again would be a different falsehood.
- **`add_proposals` also moves `detected -> brainstorming` now**, for a hand-edited pin that has a
  fork and says `detected`. The refusal is anchored on the fork, so that shape reaches the state
  move, and leaving it `detected` would be the same unreachable write one shape over.


---

## 22. The two projections read a ledger nobody had guarded — **CLOSED 2026-08-06** (ledger v0.23)

Seven findings from an adversarial review. Every one was reproduced over real
`uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd, and the map half was
then read in Chromium in **both** themes. Same class as §19–§21, and the sharpest statement of it so
far: **a rule paid at a class's methods is unpaid for every caller that holds the class's data
instead of the class.** `map.render` and `instructions.render` read a ledger as JSON and never build
a `Ledger`, which is exactly why two rounds of hardening the read path went straight past them.

### Verified — the seven, and what each did

| | BEFORE | AFTER |
|---|---|---|
| **A** [HIGH] `render_map` on a `null` entry in `pins`, and on `pins` that is not a list | `{"written": …}`, `isError: false` — and the page renders its header and **nothing**: no list, no detail pane, no traffic-light text, under a full green bar. Both throw inside `trafficLight`, which runs before anything is mounted. Observed in Chromium. | the page renders; the traffic light reads `0% settled · 1 unreadable`; a banner names `entry_shape → pins[1]` |
| **B** [HIGH] `render_map` on a non-object entry in `decision_log` / `policies`, and on either not being a list | `isError: true — 'str' object has no attribute 'get'` (four reproductions) | `isError: false`, the entry reported in the banner |
| **C** [HIGH] `generate_instructions` on five ordinary malformations | `unhashable type: 'list'` · `'dict' object has no attribute 'strip'` · `'str' object has no attribute 'get'` · `'str' object has no attribute 'items'` · `'list' object has no attribute 'strip'` | all five `isError: false`; the region is written |
| **D** [HIGH] two surfaces ordering the same pins by two severity tables | the `AGENTS.md` region listed `pin_0001` (no severity stated at all) **ahead of** `pin_0003` (`low`) | `pin_0003`, `pin_0001`, `pin_0002` — a severity the file states outranks one it does not |
| **E** [MEDIUM] the map's totals, and `nonconforming` reaching no surface | full green bar over *"all settled"* on a file whose `pins` is not a list; counts taken off the raw arrays; no nonconformance on the page, ever | `nothing on this file could be read · 1 unreadable`, empty bar, banner; and the map's pin count is `ledger_summary`'s |
| **F** [MEDIUM] clicking a pin whose `brainstorm.proposals` / `cross_derivations` is not a list | the detail pane stays **blank** in a browser with no console reader, while the list shows the row as selected | a card: *this map could not render this — props.map is not a function*, with the record as the file holds it |
| **G** [LOW] `build.py --check`'s reported file count | counted `__pycache__`, which the REMOVE sweep twelve lines above excludes — the number quoted as evidence that the tree is in sync counted files the tree does not have | `_debris` is one predicate and both loops ask it |

### Why it matters

A blank map reads as *no findings*. It is the most expensive wrong answer this surface can give, and
the tool that produced it reported success — the same sentence `_inline` was fixed under one hole
over, now true of the data rather than of the escaping. `generate_instructions` writes the one file
every host loads unprompted, so a pin shape that kills it leaves a fresh agent with a blank slate
about a project that has a fully elected design. And D is worse than a tie broken the wrong way: the
projection has a hard line budget and clips, so the pin whose file says nothing about how bad it is
survived a tight budget at the expense of one that states a severity.

### Done looks like

**One path, and it is the one the schema already had.** `Ledger.readable` becomes the module-level
`read_collection(data, name)`; `readable_ledger(data)` is the whole file with the three collections
guarded and everything else carried through; both projections read it. `pin_read` gains the two
fields that killed the second projection (`title`, `decision`), `policy_read` is its twin for the
third collection, and every substitution has a `PIN_RULES` / `POLICY_RULES` entry so `nonconforming`
reports that it happened — the existing set-equality gate makes that mandatory rather than
remembered. `severity_rank` is the package's one severity ordering; the copies in `instructions`,
`readiness` and `findings` are gone.

**And the surface says what it dropped.** `nonconforming` is inlined and rendered as a banner
between the header and the panes (a fact about the FILE may not live in a pane one selection
replaces); the traffic light never reads green while that report is non-empty; and `mount` takes a
thunk, so the page has exactly one place where a build failure becomes something a reader sees. That
last one is the answer for everything *inside* a record, which is free-form by kind and cannot be
enumerated without guessing — the rule is `a surface that cannot render something says so where a
human reads, never blank and never raised`, not a field table.

### The gates, and the one thing a gate did not catch

Six new rows in §18's table. Eight plants were run and all eight fire — a reader naming a collection
directly, a second severity table, a mount call that builds its node at the call site, a policy field
substituted with no rule reporting it, the map handed the file instead of the guarded view,
`nonconforming` stopped from reaching the page, the file count asking its own question again, and
the old ordering table restored.

What no gate caught, and what closes the loop on this section's own advice: the **browser walk**
found that `NONCONF_WHY`'s first draft quantified over `PIN_RULES` and `POLICY_RULES` and forgot
`EVENT_RULES`, so `committing_source` and `flip_criteria` rendered on the page as *"no sentence here
describes this rule"*. The gate written beside it had the identical hole, because the round that
writes a gate is the round least likely to plant against it (§18's standing argument). Both are
derived from all three tuples now.

### Prove it

```bash
# a ledger holding every malformation above, over the SHIPPED server from a foreign cwd
python scripts/build.py
# render it, then open the file and look — light and dark
#   render_map      -> isError: false, and the page shows a banner naming what it dropped
#   ledger_summary  -> the same list under pre_rule_events, and the version is NOT raised
#   generate_instructions -> isError: false, `low` ahead of a pin that states no severity
python -m unittest tests.test_ledger tests.test_map tests.test_instructions
```

### Traps

- **`readable_ledger` copies, it does not rewrite.** `nonconforming` is asked of the ORIGINAL, so the
  banner describes the file as it stands. A guard that edited the data would be this package
  silently repairing the artifact it exists to audit.
- **`policy_read` substitutes `{}` for an unreadable `applies_to`, and `{}` is the UNIVERSAL scope.**
  That is deliberate and is the widest reading: a scope this runtime cannot read must not quietly
  narrow the radius a human is shown before they elect the rule.
- **`kind`, `kind_detail` and `default_outcome` stay plain `.get`s.** They are interpolated, never
  indexed. Substituting a field that cannot crash is inventing a claim about the record rather than
  avoiding a failure — the line `_pin_line` and the policy line both state.
- **The map's `||[]` fallbacks stay** even though the payload is now guaranteed. They cost nothing
  and the page is a file people copy; what they must not become is the reason someone believes the
  page is safe. The Python side is the guarantee.
- **`ledger.py` is excluded from the collection gate on purpose.** It is the carrier's home AND the
  write path, which deliberately keeps `self.data[…]`: a write onto a file this runtime cannot read
  is a different question, and the answer there is to refuse.

---

## 23. Six rules paid at a set's members, unpaid for what satisfies the set — **CLOSED 2026-08-06** (ledger v0.24)

The thirteenth round, and the question it asked is §22's asked of **sets** instead of of classes:
§20 gave the arcs their events, §21 gave them their carriers, §22 gave the projections the read
path — and every one of those was paid *for the members of a table*. So the round looked for things
that satisfy a table's definition without being in it. Each finding below was **reproduced over real
`uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd** before it was a test,
and every one of them passed 828 tests and eight gates.

### Verified — the six, and what each returned

1. **`cross_derive(agreement="disagree")` was a third way back into the open set.** Its own event
   says `"reopened": true`, and it was on neither `REOPEN_ARCS` nor the code path
   `SETTLEMENT_CARRIERS` is paid at, so it paid none of the tolls v0.22 had just made the other two
   arcs pay. `add_pin(defect) → add_remediation → done → cross_derive(agree)` (the envelope reaches
   the `cross_derived` rung) `→ cross_derive(disagree)` returned `{"state": "needs_input",
   "verification": {"rung": "cross_derived", …}}`, and `ledger_resolve` with
   `evidence="no new observation of any kind"` then answered `{"state": "resolved"}`.

2. **`cross_derive(agreement="agree")` laundered a demoted verification.** Four calls apart:
   `resolve(rung="observed")` → `ledger_reopen(fired="incident")` (rung demoted, `blocked_by`
   written) → `ledger_resolve` correctly refused as `unverified` — and then one agent-authored
   `cross_derive(agree)` merged `rung: "cross_derived"` back onto that same envelope with
   `blocked_by` untouched, after which the pin closed. The reopen arc's whole purpose, undone by the
   door beside it.

3. **"Finished work is refused" was spelled out in prose at the two funnel doors this branch added
   it to, and was absent everywhere else.** On one `resolved` defect: `ledger_set_question` and
   `ledger_add_proposals` refused it in near-identical sentences; `ledger_add_remediation`,
   `ledger_set_remediation_status`, `ledger_premortem` and `ledger_set_readiness` all wrote to it,
   `isError: false`.

4. **One write door of eighteen did not refresh the live map.** AST over `src/mcp/tools.py`: 18
   functions called `.save()`, 17 then called `_refresh_live_maps`, `ledger_label_failure` did not —
   while `_livemap_marker`'s own docstring states the rule. Verified with a live map registered: the
   page on disk stayed byte-identical, so a `FailureEvent` was on no surface until the next
   unrelated write, under a badge that said live throughout.

5. **`brief` was the one member of `DECISION_EVIDENCE` whose claim had no carrier.** `elicited` is
   unreachable over MCP, `transcribed` is refused at every door without `human_answer`, `cascaded`
   demands `policy_id` on both sides of a biconditional. Reproduced with three clusters: one `ev_`
   event on disk carrying `evidence: "brief"`, `rationale: "pre-decided by the brief"`, and no
   reference of any kind to a brief.

6. **"An agent-relayed election must quote the human" had four hand-written enforcement points and
   no carrier** — two in `record_decision`, one in `record_policy`, one in `ledger_defer`. They
   agreed, which is the shape every finding on this branch started as.

### Why it matters

Findings 1 and 2 are a correctness hole in the one gate the verification ladder exists for: two
independent routes by which a pin that production had refuted closed green with nothing observed.
Finding 3 lets an agent plan, re-open remediation on, and re-verdict work a human has finished, with
no record that anything was un-finished. Finding 4 is the register's signature class at the surface
layer — a write that reaches the file and not the human. Findings 5 and 6 are the same sentence in
two places: a rung whose evidence nothing collects is a claim an honest agent and a fabricating one
make identically.

### What closed it

- **`REOPEN_ARCS` has three members**, and the two axes on which they differ are tables:
  `ARC_MOVES` (which states the arc moves — `cross_derive` marks an open pin and may not un-close
  finished work) and `ARC_CASCADES` (whether the settled `depends_on` closure comes with it — false
  for `cross_derive`, which is its own long-standing decision, kept verbatim and now *declared*).
  `_reopen_minimal` is the one writer of all three; `REOPENED_SUBSTATES` carries no literal;
  `REOPEN_BUCKETS` gains `already_closed`.
- **`refuted_claim(pin)` + `VERIFICATION_RUNG_WRITERS`.** A re-derivation is not an observation, so
  it may not raise a rung over a standing refutation; the agreement is still recorded and
  `rung_raised` says which happened. Every writer of a closing rung now declares what fresh thing it
  rests on, held to the AST.
- **`PIN_WRITE_DOORS` + `Ledger._gate_closed`.** One entry per per-pin write door, four
  dispositions, and `records_only` is why it is a table rather than a blanket: `label_failure` is
  exactly what you do to a `resolved` pin before you reopen it.
- **`brief_quote`**, as an `EVENT_RULES` biconditional, collected by `interview_expand`
  (`brief_decisions` is now `{cluster_id: {"outcome", "quote"}}`) and read on the map's decision
  card where `human_answer` is read.
- **`tools._saved` and `tools._require_quote`**, with `ledger.QUOTED_RUNGS` holding the membership
  question — one commit point, one refusal.

### Prove it

Every gate below was verified by **planting its own reversal and watching it go red**, then restored
and re-run green. That is the procedure §18 says is the only thing that catches the class it cannot
gate, and one of the plants earned its keep immediately: the closed-work gate asserts *which*
refusal fires, and it caught `set_question` answering `already poses a fork` on a `resolved` pin —
the weaker of two true reasons, pointing an agent at replacing the fork instead of at `reopen`. The
check on the `_require_quote` roster was planted with a hand-written check that behaves identically,
because a plant that breaks the syntax proves nothing.

### Traps

- **Do not widen `ARC_MOVES["cross_derive"]` to `SETTLED_STATES`.** v0.16 narrowed this arc away
  from un-closing finished work on purpose; the complement against `CLOSED_STATES` is that
  narrowing, written where the other two arcs can be compared to it.
- **Do not make `cross_derive` cascade.** `ARC_CASCADES` is a declaration of an existing decision,
  not an oversight to be tidied. Nobody yet knows which side is wrong.
- **Do not let `refuted_claim` become a gate on `resolve`.** `resolve` demands the observation, and
  it is the declared way out of a refutation — a gate with no gate-opening move is a wall.
- **Do not add a `refuse` entry to `PIN_WRITE_DOORS` for `label_failure`.** Labelling a production
  failure on finished work is the move that precedes a reopen; refusing it would make the honest
  sequence impossible.

### The residual, registered rather than fixed

- **A ledger written before v0.24 whose `brief` decisions carry no passage is held below its floor
  for ever, and correctly.** No quote can be reconstructed from a decision that never recorded one,
  and inventing one would be the claim the field exists to make checkable. `nonconforming` reports
  it under `pre_rule_events` and the map's decision card says so on the pin; the version simply does
  not rise. This is §12's shape with the opposite verdict, and the difference is that here the
  surfaces can *say* what is missing.
- **`_gate_closed` binds `CLOSED_STATES`, not `SETTLED_STATES`** — so every one of the six `refuse`
  doors still writes to a `decided` pin, which is deliberate (a human election is correctable, and
  planning against a live election is what those doors are for) and is the same line `set_question`
  drew first. If a future round wants `decided` covered, it is a different rule and needs its own
  argument, not a wider tuple.

---
## 24. The gate was a corpus, and the corpus was hand-written — **CLOSED 2026-08-06** (ledger v0.25)

The fourteenth round, and the first whose subject is the **gate** rather than the rule it enforces.
§23 closed with the counter-move this branch had converged on — *one carrier per rule, and a
structural test that quantifies over all of its callers* — plus a sharper half a reviewer added in
the same review: **where the corpus can be derived from the schema the rule is about, derive it.**
This round is what happens when the second half is taken seriously about the read path, which is
the one place the first half had already been applied twice.

Every finding was **reproduced over real `uv run --script plugins/keel-core/mcp/server.py` stdio
from a foreign cwd**, or opened in Chromium, before it was a test — and every one of them passed
856 tests and nine green gates.

### Verified — what the hand-written corpus was hiding

`PIN_RULES` and `pin_read` were held together by set equality, `LEDGER_COLLECTIONS` drove an AST
gate, and `nonconforming` replayed the rule table. The corpus all three ran against was **seven pin
shapes, written by hand, copied into two test modules** under a comment saying the principle was
one. A reviewer extended it in a scratch copy of HEAD with eleven more shapes — every one naming a
field `PIN_FIELDS` already declared — and the unchanged gates went red.

1. **`interview_next` died on `verification` / `brainstorm` / `brainstorm.proposals`.** One of the
   four surfaces this branch keeps naming in that phrase. `(pin.get("verification") or {}).get` is
   a guard against absence and no guard at all against a string; a `proposals` that is truthy and
   not a list of objects was walked character by character into `p.get(...)`. Five isolated files
   plus a combined worst case, all `isError` over stdio.
2. **A ledger whose top level is not an object killed all four surfaces** with a raw
   `AttributeError`: `Ledger.__init__` reached `self.data.get("version")` before any guard ran, and
   `nonconforming` — the report that exists to describe an unreadable file — was itself among the
   things that could not open one.
3. **`learning.divergences` did `e["id"].startswith(...)`** — the exact expression v0.18 removed
   from `summary()`, whose comment names it, left standing one module over. `learning_report` died
   with a bare `KeyError: 'id'` where `ledger_summary` answered about the same file.
4. **The projection every fresh agent loads was the one surface with no nonconformance note.**
   `instructions.render` named `nonconforming` in a comment and called it nowhere: on one hostile
   ledger `ledger_summary` reported the pins and the nonconformances, the map showed a banner, and
   the region generated into the user's `AGENTS.md` listed the readable pins and said nothing.
5. **The map stated something false and no surface contradicted it.** A pin carrying
   `verification: "observed"` rendered as *"no rung recorded"*, with the warning that goes with it,
   and the banner never mentioned `verification`.
6. **`_refresh_live_maps` promised more than its handler delivered.** The docstring: *"a render
   failure must never break the ledger write that triggered it"*; the handler:
   `except (OSError, ValueError)` — not the failure classes this whole round is about.
7. **Three write doors refused one malformed argument three ways.** `ledger_premortem` cleanly,
   `ledger_add_proposals` and `add_pin`'s provenance loop with raw `AttributeError`s — on the
   argument an agent composes and therefore gets wrong.
8. **`README.md:8`'s badge said `tests-592 passing` while `:322` said 828 tests green.**
   `check_stated_facts.py` was added on this branch for exactly this claim and its docstring names
   "592" three times; it did not quantify over the shape the number is written in when it is a
   badge.

### What was built

**One carrier — `ledger.PIN_SHAPES` — and the rules, the read, the map's sentence and the test
corpus are all derived from it.** 31 declared paths, dotted where nested, with a stated membership
rule that is held to the writers rather than trusted: *a path is declared iff a reader can INDEX
INTO its value.* `PIN_RULES = _rules_from(PIN_SHAPES, PIN_STRONGER, "pin_")`; `pin_read` is the
whole pin with every declared path guaranteed to hold its shape (`fill` naming the one axis on
which its two callers differ); `shape_notes()` is what the page inlines; `tests/shape_corpus.py`
turns each declaration into every way it can be violated, by probing the declared shape against a
fixed set of values and keeping the ones it refuses.

**The derived corpus then found three readers nobody had reported** — `agent_ready` on a
`readiness` that is a bool and a `remediation` member that is a string, `policy_preview` and
`interview_seed_policies` on `self.data["pins"]` (the write path's deliberate direct index, reached
from a read-only tool) — and **the writer gate found `as_is.disagreeing_layers`**, which the map
builds a `Set` out of and which nothing had declared. Neither class was in anyone's list.

**One answer to what a record's id is.** `nonconforming` labelled by `str(pin.get("id") or "")`
while every surface read `pin_read`, so a pin carrying `id: 7` was reported as `7` and rendered as
`""` — which is why the map's new per-record card could not join the report to the card it is
about. Found in the browser, not in a test.

### Proved

- All eight reproductions re-run verbatim over stdio against the **rebuilt** shipped plugin.
- **The browser pass**, light and dark, on the worst file the corpus can build (149 pins, 20
  policies, 35 rules, 172 instances): every rule on the banner carries a sentence (no *"no sentence
  here describes this rule"*), no console errors on load, the per-record card fires on a pin and on
  a policy, and a record with no readable id says *this record carries no readable id* rather than
  showing a clean card.
- New gates: `tests/test_ledger.py::TestTheShapeTableIsTheWritersOwnShapes` (both directions,
  driven by `walk_every_pin_writer`) plus `test_the_read_actually_delivers_every_shape_it_declares`,
  `test_every_declared_shape_has_a_probe_that_refuses_it` (the corpus's own non-vacuity floor) and
  `test_a_ledger_whose_top_level_is_not_an_object_is_refused_not_crashed`;
  `tests/test_mcp_tools.py::TestNoWriteDoorDiesOnAMemberOfAListArgument`,
  `TestEveryProjectionSaysWhatItCouldNotRead` (roster derived from *answers `written`*) and
  `TestARenderFailureNeverBreaksTheWriteThatTriggeredIt`; `tests/test_map.py`'s join gate and its
  derived-sentence gate.

### Residuals, registered rather than fixed

- **`add_pin`'s `anchors` guard is library-level only.** The MCP tool does not expose `anchors`, so
  the FastMCP schema refuses the argument before `_require_objects` is reached. Both refusals exist
  and agree; the parameter not existing is the stronger statement, exactly as `ledger_defer`'s
  required `human_answer` was left in section 23.
- **A record with no readable id cannot be joined to the report.** The page says so rather than
  guessing, and `nonconforming` names such a record by position on both sides. Making the join
  index-based would require the guarded read to carry a source index, which is a change to what a
  projection returns and needs its own argument.
- **`PIN_SHAPES` declares no nested scalar.** That is the membership rule, and it is right for
  Python readers — nothing indexes into a string — but a page that renders one still renders it
  oddly, and the banner does not name it because no rule is broken.

---

## 25. A write door reads the pin already in the file — **CLOSED 2026-08-07** (ledger v0.26)

The fifteenth round, and it is the previous three rounds' lesson landing on the one surface nobody
had asked. §22 hardened the readers that hold a `Ledger`, §23 hardened the readers that hold ledger
DATA, §24 replaced the corpus all of them run on with one derived from `PIN_SHAPES` — and none of it
reached a **write** door. A per-pin write door READS the record before it writes anything, so every
guarantee built for the readers applies to it, and none of it was applied. It is worse than a
reader's crash, not better: the caller is mid-transaction, so the honest report is *your write may
or may not have happened*.

Every finding was **reproduced over real `uv run --script plugins/keel-core/mcp/server.py` stdio
from a foreign cwd** before it was a test, and every one of them passed 876 tests and nine green
gates.

### Verified

1. **[BLOCKER] `mark_correctness_unknown` accepted `rung="observed"|"cross_derived"`** and wrote it
   into the pin's `verification` envelope — the single carrier `settlement_verdict` opens the
   `resolve` gate on. So the door whose entire meaning is *correctness could not be established*
   handed the pin the claim that its behaviour WAS observed. Five calls with no human in the loop:
   `resolve(rung="observed")` closed the pin, `reopen(fired="incident")` demoted the envelope,
   `ledger_resolve` correctly refused as `unverified` — then
   `ledger_mark_correctness_unknown(blocked_by="no oracle exists for this", rung="observed")` wrote
   the closing rung straight back, and `ledger_resolve(evidence="I looked")` closed it green. This
   is v0.24's laundering finding one door over, and it is exactly what the reviewer of that round
   warned about when the check moved: `cross_derive` was gated on `refuted_claim`, and the door
   beside it could still simply assert the observation. `VERIFICATION_RUNG_WRITERS` even *said* it
   could not — `records_absence` reads *"writes a rung BELOW the closing ones… so it is asked
   nothing"* — which is the register's second recurring shape (a sentence printed on the object it
   is false of) sitting inside the table written to close the first.
2. **[HIGH] Every per-pin write door died on the shape of the pin already in the file** — 42
   distinct crash sites across all 14 doors, the election door `ledger_record_decision` among them.
   `KeyError: 'state'` at every door, from `_gate_closed`; `'str' object has no attribute 'get'` at
   `add_remediation`, `challenge`, `reopen` and `cross_derive` on a `remediation` or `verification`
   this runtime did not write; `KeyError: 'title'` at `record_decision`, three lines before `decide`
   was reached; `KeyError: 'depends_on'` at `set_readiness`; `TypeError: string indices must be
   integers` at `resolve` and `set_remediation_status`.
3. **[HIGH] v0.25's list-member rule was paid only at TOP-LEVEL list arguments.**
   `ledger_add_pin(question={"options": ["a bare string"]})` and `ledger_set_question` with the
   byte-identical dict both returned `'str' object has no attribute 'get'` — the exact finding
   `_require_objects` was written to close, one nesting level down, at the two doors that compose
   the fork the whole funnel runs on.
4. **[MEDIUM] `SETTLEMENT_CARRIERS` said DOOR and its gate asked one FUNCTION.** The structural half
   derived the carrier set from the AST of `settlement_verdict` alone, while `resolve` gated on a
   fifth: `_require(pin.get("evidence") or evidence)` — the pin's own field, which is the
   observation the LAST resolve rested on. After a reopen it names precisely what production
   refuted.
5. **[MEDIUM] `kind` was the third closed vocabulary a pin carries and the only one with no rule**
   in `PIN_SHAPES`/`PIN_STRONGER`, so a wrong-typed or out-of-set `kind` was invisible to
   `nonconforming` on every surface while `state` and `severity` were reported on all of them — and
   `settlement_verdict` sends a `defect` and a `design_concern` down different branches on it.

### The answer now lives in

| | |
|---|---|
| **`Ledger.writable_pin`** | the WRITE path's lookup: `pin()` plus a refusal naming every rule the record breaks. The split is the file's standing rule applied to a record — *reading a ledger is never the operation that fails on it, and a write onto something this runtime cannot read is exactly the operation that must fail*, which is what `Ledger.__init__` already says about the whole file. Substituting here is not open to us: the door writes the pin back, so a guarded read on the write path is a silent repair of somebody's file. |
| **`PIN_REQUIRED`** | what a write door may assume is present, with the membership rule being the writer's own output — every declared path `add_pin` composes — and the gate derives the set from a pin `add_pin` actually writes. `_rules_from` gained `required`, so absence and wrong-type are one rule, one name, one `pre_rule_events` entry. |
| **`RUNG_WRITER_RUNGS` + `_writable_rung`** | the third column of `VERIFICATION_RUNG_WRITERS`, which was prose. One refusal, paid by all four writers under their own names, asserted from the AST. |
| **`_validate_question`** | through `_require_objects`, so the one carrier is paid at the nesting level the finding was at. |
| **`resolve`** | demands the observation THIS call rests on. The carrier was removed rather than declared: an arc cannot owe anything to a claim no door reads. |
| **`PIN_SHAPES["kind"]` + `PIN_STRONGER["kind"]`** | `isinstance` first, because `KINDS` is the one closed vocabulary held as a `set` and `v in KINDS` on an unhashable value RAISES — found by the derived corpus on its own first run, inside `nonconforming`, inside `Ledger.__init__`. |

### The gates, and each one was proved by planting its reversal

- `tests/test_mcp_tools.py::TestNoWriteDoorDiesOnThePinAlreadyInTheFile` — the roster is derived
  (*any tool taking a `pin_id` that reaches the commit point*) and the corpus is derived
  (`shape_corpus.broken_pins()`). Three assertions: no write door looks a pin up any other way (the
  one that catches `record_decision`, which reached the guarded `decide` and died three lines
  earlier on its own `led.pin`), every `PIN_WRITE_DOORS` method reaches the carrier, and no door
  crashes on any shape the schema can describe.
- `TestNoWriteDoorDiesOnAMemberOfAListArgument._lists_under` — recursive, so a third nesting level
  arrives under the gate rather than under the next reviewer.
- `TestTheWayBackOwesTheDoorsTheirCarriers._carriers_the_doors_gate_on` — the predicate's whole body
  plus every `_require` CONDITION in the five doors. A `_require` is this runtime's one refusal, so
  a pin field read inside one is a field the settlement is decided by.
- `TestOnlyAFreshObservationRaisesARefutedClaim` — four new cases: every rung writer pays the
  carrier under its own name (AST), the `records_absence` writer refuses every closing rung and
  still records the ones it may (behavioural, both derived from the table), and the five-call
  laundering route is walked and blocked.
- `TestAWriteOntoAPinThisRuntimeCannotReadIsRefused` — `PIN_REQUIRED` held to `add_pin`'s minimal
  output, the read/write split asserted on one record, and the whole derived corpus at the carrier.
- `TestTheShapeTableIsTheWritersOwnShapes::test_every_scalar_a_settlement_door_decides_on_has_a_membership_rule`
  — derived from `SETTLEMENT_CARRIERS`: a carrier a door decides from, whose value is a scalar,
  picks a branch, so it needs a membership rule.

**Re-run after the fix, verbatim:** 2170 stdio calls (155 derived shapes x 14 derived doors) against
the shipped plugin from a foreign cwd, **zero crashes**; the `mark_correctness_unknown` route
refused with the `records_absence` sentence and the pin stayed `needs_input`; both
`question.options` doors refused naming the argument and the index; the door-derived carrier set
equals the declared table.

### Residuals, recorded rather than fixed

- **A scalar nested inside a declared object is still outside `PIN_SHAPES`**, by that table's own
  membership rule (*nothing indexes into a string*). That rule is about what a reader indexes INTO
  and says nothing about a missing KEY, which is a `KeyError` all the same: `resolve` did
  `i["status"]` and `set_remediation_status` did `item["id"]`. Both are `.get` now, under the read
  path's own v0.18 rule, and **no derived corpus can produce those cases** — extending the corpus
  inside a `list[object]` would need a schema for the item, which does not exist. If a future round
  wants that class gated, the deliverable is the item schema, not a wider corpus.
- **`apply_policy` writes to pins and takes no `pin_id`**, so it is outside the derived roster by
  construction. It reaches `decide`, which now refuses an unreadable pin, so the failure mode is a
  refusal rather than a crash — but the refusal aborts a cascade partway. Left as it is: what a
  half-applied policy owes its radius is a real question and nothing here settles it.
- **`kind` is the only closed vocabulary added.** `confidence` and `resolution_mode` are closed too
  and neither is in the table, because the derivation used is *a carrier a settlement door decides
  from*, and no door branches a pin's fate on either. Widening it to "every closed vocabulary a pin
  field carries" is a different rule and needs its own argument.

### The general shape

§23: *a rule paid at a class's methods is unpaid for every caller that holds the class's data.*
§24: *a gate is only as good as the corpus it runs on.* This one is both, aimed at the half of the
surface nobody had asked: **a rule proved of the readers is unproved for the writers, and a write
door is a reader first.** The question to ask of any read-path hardening is not *which readers are
covered* but **name every door that READS this record before it writes it, and run the same corpus
at that door.**

---

## 26. The number the interview orders by, and the door that ran twice — **CLOSED 2026-08-07** (ledger v0.27)

The sixteenth round, and it is the first since §20 whose subject is not the ledger's own read/write
path but the **interview** — the surface all of that work exists to feed. Three findings plus one
this round introduced and its own plants caught, and two of the three were invisible to every roster
the previous three rounds derived, for one reason worth stating in the register rather than in a
docstring: **every derivation on this branch said "takes a `pin_id`", so what writes without naming
a pin was outside the whole mechanism by construction.**

### Verified

1. **[HIGH] `interview_view.transitive` and `interview.funnel.transitive_downstream` counted simple
   PATHS, not downstream pins** — and the two functions were byte-identical, which is the second half
   of the finding. Both summed `1 + recurse(...)` over the inbound edges with the `seen` set carried
   down one branch and never across siblings. On the smallest diamond a roadmap makes — `B` and `C`
   depend on `A`, `D` on both — `A` reported **4** downstream pins and has three: `D` was counted
   once through `B` and once through `C`. That number is the interview's information gain: the key
   `interview_view` sorts on and the `downstream` the funnel prints beside every question. So the
   ordering of the compressed interview inflates with the density of the DAG — fastest exactly where
   the graph is most entangled and the ordering matters most. The old walk was also exponential in
   the number of diamonds, on a file an agent hands us.
2. **[MEDIUM] `interview_expand` is a write door with no `pin_id`, and it was not idempotent.** Two
   calls on the default catalog left **24 pins for 12 clusters** — every fork in the funnel
   duplicated, the newer copy taking the `depends_on` edges and the older one (which may already
   carry a decision, a brainstorm or a remediation) orphaned beside it. Reproduced in two calls on an
   empty ledger. It is the Phase-1 step an agent re-runs after a crash or a context reset, i.e. the
   door most likely to be called twice by a caller that cannot tell whether it already ran. Four
   tools reach the commit point without a `pin_id` (`ledger_add_pin`, `ledger_surface_assumption`,
   `interview_expand`, `record_policy`); the one hand-written table that named any of them named two.
3. **[LOW] The door-level half of v0.24's brief-quote rule had no test.** Rewriting
   `interview._brief_entry`'s condition from `if not outcome or not quote` to `if not quote` left the
   whole suite green — `TestTheBriefOwesTheBrief` included. The one test that reached the door passed
   a bare string, which exercises the `quote` half and says nothing about the other.
4. **[BLOCKER, introduced and caught inside this round] `SCHEMA_VERSION` and `READABLE_VERSIONS`
   are one fact stated twice, and the bump raised one of them.** The stamp went to `0.27`; the
   accept-list was a literal tuple ending at `0.26`. So this runtime wrote a ledger and then refused
   to open it — `LedgerError: ledger schema '0.27' is not readable by this runtime`, from
   `Ledger.__init__`, on every call through `_open_existing` / `_open_or_create` after the first.
   Nothing named the rule: the constructor is the tuple's only consumer, and no gate asked the
   reflexive question. It surfaced because a plant for finding 2 happened to reopen a ledger, which
   is luck, and luck is what this register exists to replace. The tuple now ends in `SCHEMA_VERSION`
   — the failure is unreachable, not merely tested. This is `MEMORY.md`'s own standing lesson
   (*every new state must be sought on all surfaces before the commit*) arriving as a version rather
   than as a state.

### The answer now lives in

| | |
|---|---|
| **`ledger.downstream_of`** | THE answer to *how much does this fork collapse*: a `set` of pin ids, computed as reachability over a reverse index rather than as arithmetic over paths. A `depends_on` cycle in a hand-edited file terminates, and a pin is never downstream of itself. Both surfaces call it; neither computes it. |
| **`interview.catalog_cluster` + `CATALOG_SOURCE`** | the one reading of *this pin was materialised from that catalog cluster*, off the `provenance` entry `expand_catalog` already wrote. Nothing new is stored — the fact was decidable all along and nothing asked. `cluster_id` is deliberately NOT the carrier: `cl_<id>` is a **scope** (a policy's `applies_to` selects on it, `decide(apply_to_cluster=True)` cascades over it), so a hand-grouped finding carries it too, and reading it as origin would make one look like a catalog fork. |
| **`expand_catalog`'s `already_present`** | a cluster whose pin is in the file is left exactly as it is and named back with its pin id and state, so `depends_on` still wires to the fork that exists. A `brief_decisions` key naming one is reported ignored there rather than applied: settling a pin that exists is `ledger_record_decision`'s door, where the offered-options rule lives. |
| **`READABLE_VERSIONS`** | ends in `SCHEMA_VERSION` rather than repeating it, so the version this runtime stamps is a version it accepts by construction. |
| **`TestTheBriefOwesTheBrief.HALVES`** | the refusal derived from the two halves of the pair, so neither half of the condition can be deleted without a failure. |

### The gates, and each was proved by planting its reversal

- `tests/test_ledger.py::TestOneAnswerForHowMuchAForkCollapses` — six assertions, and the one that
  matters is derived: every function in `src/runtime` + `src/mcp` that walks the pin dependency
  graph (recurses while naming `depends_on`, **or** tests membership against a `depends_on` value)
  is held by set equality to a declared table stating the question it answers. **It reported two on
  its first run** — `buildloop.depth` (upstream levelling, memoised, cycle-detecting) and
  `challenger._inbound_fanout` (the immediate dependants) — and both are declared with their
  question rather than silenced. The gate asserts a set the tree does not contain, so it carries its
  own non-vacuity floor: `test_the_detector_fires_on_the_code_it_was_written_against` runs the
  detector over the removed function verbatim and both names must come back. The callers of the
  carrier are derived and declared too, so a third surface that wants a fan-out number is read
  before it is counted.
- `tests/test_mcp_tools.py::TestALedgerWideWriteDoorIsOnARosterToo` — the hole, closed at the
  derivation. The union of the per-pin roster and the ledger-wide one is asserted to be **every**
  function in `mcp/tools.py` that reaches the commit point, and each ledger-wide door declares what
  a second identical call does: `projects` must add nothing, `creates` must add something. Both
  directions are exercised, so the classification is a claim and not a free pass.
  `TestNoWriteDoorDiesOnAMemberOfAListArgument.CREATE_CALL` is now this roster rather than a second
  table of two doors somebody typed.
- `tests/test_ledger.py::TestTheBriefOwesTheBrief` — three new cases: each half of the pair missing,
  whitespace in either half, and the refusal reaching the caller through `expand_catalog` with
  nothing written to the ledger.
- `tests/test_ledger.py::TestThisRuntimeReadsWhatItWrites` — the reflexive case, asserted as a
  property (`SCHEMA_VERSION in READABLE_VERSIONS`) and reproduced behaviourally (write, then open).

**The plants, run and recorded:**

| plant | what failed |
|---|---|
| `downstream_of` reverted to the old recursion | 4 in `TestOneAnswerForHowMuchAForkCollapses` — the diamond (`A: 4 != 3`), the cycle case, the surface-agreement case, **and the derived-walk gate**, because the reverted carrier is itself a recursion over the edge |
| the recursion put back inside `funnel` | 3 — the derived-walk gate naming `interview.py::funnel` and `interview.py::transitive_downstream`, plus the caller roster and the surface-agreement case |
| the idempotence guard removed from `expand_catalog` | 3 in `TestALedgerWideWriteDoorIsOnARosterToo` — `a second identical call` for `interview_expand`, and both `already_present` cases |
| `interview_expand` removed from `WIDE` | `test_the_two_rosters_together_are_every_write_door_in_this_module` |
| `_brief_entry` back to `if not quote:` | 3 in `TestTheBriefOwesTheBrief`, including `(outcome='', quote='…')` — the case the whole suite was silent about |
| `READABLE_VERSIONS` back to a literal tuple | both halves of `TestThisRuntimeReadsWhatItWrites` |

### Residuals, recorded rather than fixed

- **A declared table can be told a lie.** `OTHER_WALKS` and `WIDE` are both *derived roster held to a
  declared claim*, which is this repo's standard shape and carries this repo's standard residual: an
  author can add a downstream walk and declare it as something else, or classify a projection as
  `creates`. What the gate buys is that they must **write the sentence** — and both tables' messages
  say what the right answer is when the sentence would be *downstream reach*. The behavioural half of
  the `WIDE` gate closes the second case in one direction (a `creates` door that adds nothing fails),
  not the other.
- **`record_policy` called twice with the same offer records two standing rules.** Declared
  `creates`, on the argument that an election is an act and two acts are two records — collapsing
  them would be this runtime deciding that two things a human did are one thing. That argument is not
  obviously right: the second cascade decides nothing (every pin the first reached is already
  settled), so the second policy is a rule with no radius. Whether that is a duplicate or a
  re-election is a question about what a `Policy` records, and nothing here settles it.
- **The catalog projection is idempotent per CLUSTER, not per catalog.** A cluster renamed or removed
  from `decision-catalog.json` leaves its pin in the ledger with no cluster to match, and nothing
  reports it — the mirror of `brief_unmatched` on the other axis. Reporting it means deciding what an
  orphaned catalog pin means (a stale fork? one the user still owes an answer to?), which is a
  decision about the catalog's lifecycle rather than about this door.
- **`apply_policy` is still outside the write-door roster** — see §25's residual, unchanged. It takes
  no `pin_id`, and it does not reach `mcp/tools.py`'s commit point directly either, so the
  ledger-wide derivation above does not cover it. It is reached *through* `record_policy`, which is
  on the roster.

### The general shape

§25 asked *which doors read this record before writing it*. This one asks the two questions that
survive it, and both are about the shape of an answer rather than the shape of a rule:

- **Is the number a surface prints the number it claims to be?** Not *is it computed* — it was,
  twice — but *does the computation answer the question the label asks*. Two identical copies of a
  wrong answer is what let this one survive: every round that reviewed one of the two surfaces saw a
  function that agreed with the other, and agreement between copies reads exactly like correctness.
- **What is outside a roster BECAUSE of how the roster is derived?** A derivation is a claim about a
  class, and a derived roster feels like coverage in a way a hand-written one does not. The question
  to ask of every one of them: *state the predicate out loud, then name what does the dangerous thing
  and does not satisfy it.*

---

## 27. What a door reads while writing, and whether its report is true — **CLOSED 2026-08-07** (ledger v0.28)

The seventeenth round and the branch's last. Four findings, all reproduced over real
`uv run --script plugins/keel-core/mcp/server.py` stdio from a foreign cwd against the built plugin,
and every one of them is a question the previous two rounds asked of a neighbouring surface and did
not ask here: §25 refused the record a door WRITES; this asks what it may READ while writing — the
other pins, and the collection they sit in. §26 asked what a derived roster excludes by construction;
this asks it of the READ-only roster. And one nothing had asked at all: **is what a door reports what
it did?**

### Verified

1. **[HIGH] A write persists and then reports failure.** `ledger_reopen`, `ledger_challenge` and
   `ledger_cross_derive` all ran their reporting AFTER `_saved`, and `Ledger.cascaded_by` indexed
   `e["pin_id"]` raw over `self.data["decision_log"]`. Observed over stdio: two `resolved` pins (one
   depending on the other), one hand-written log entry naming a `via` and carrying no `pin_id`, one
   `ledger_reopen` — and the answer was

   ```
   isError: True    Error calling tool 'ledger_reopen': 'pin_id'
   file changed: True    pin pin_0001 state now: needs_input
   ```

   The write is on disk and the caller is told it failed. `ledger_label_failure` was the fourth: it
   ran `foresight`, which indexed `e["id"]` raw over the same log, one line after committing.
2. **[HIGH] A carrier for the record, none for the container.** `Ledger.readable`'s own docstring
   said, in these words: *"The WRITE path deliberately keeps `self.data[…]`: a write onto a file this
   runtime cannot read is a different question from a read of it, **and the answer there is to
   refuse**."* Nothing refused. **Ten agent-reachable doors across both derived rosters** died with a
   raw `AttributeError`/`KeyError` when the CONTAINER — the collection, not the record — was an
   object, a string, a number or simply absent: `interview_expand`, `ledger_add_pin`,
   `ledger_challenge`, `ledger_cross_derive`, `ledger_defer`, `ledger_label_failure`,
   `ledger_reopen`, `ledger_surface_assumption`, `record_decision`, `record_policy`. Eight of them
   over the wire (`record_decision` and `record_policy` refuse earlier through `server.py`'s own path
   on that fixture), all ten at the tool layer. The prose stated the rule; nothing paid it.
3. **[HIGH] `writable_pin` guards the pin being written and no other.** `set_readiness` built
   `by_id = {p["id"]: p for p in self.data["pins"]}` and `_reopen_minimal` walked `p["id"]` /
   `p["state"]` over the same raw list. Reproduced with a **well-formed target both times**: a write
   onto a healthy pin failed with `KeyError: 'id'` because a DIFFERENT pin in the file carried none.
   Five doors, over stdio — `ledger_set_readiness` and `ledger_cross_derive` on the missing id,
   `ledger_add_pin` / `ledger_surface_assumption` / `interview_expand` on a bare string among the
   pins. The blast radius of one malformed record was the whole file.
4. **[MEDIUM] The roster's membership rule has a hole shaped like two tools.** The read-only roster
   was computed as `required == ["ledger"]`, which reads like *a read-only tool that reads a ledger*
   and is that minus every one which also takes a `pin_id`. `scope_check` and `readiness_assess` were
   in **none** of the three derived rosters on this branch — the two write rosters are *takes a
   `pin_id` and commits*, so a READ that takes a pin falls between all of them — and both died on the
   pin's own declared shapes: `'str' object has no attribute 'get'` out of `declared_vs_actual`'s
   `(pin.get("readiness") or {}).get("zone")`, `'int' object is not iterable` out of `zone_of`'s walk
   over `anchors`. Eight of ten probes crashed.

### What closed it

**One carrier per rule, and a test that quantifies over its callers** — the branch's own method,
applied to the last case nobody had asked it about.

- **`tools._saved` is the last thing a door does.** Every door now computes its answer, commits, and
  returns the name. `TestADoorThatReportsFailureCommittedNothing` holds it positionally by AST over
  every function in the module that reaches the commit point, so the nineteenth door inherits the
  rule instead of being written without it. The behavioural half derives its trap from each door's
  own output — run it once, read back the log ids it appended, re-run it on a copy carrying a `cas_`
  entry that names one of them as its `via` — and its non-vacuity floor is derived too: every door
  that reads a cascade radius must be one the planted `via` actually reaches. Verified by planting:
  moving the commit back to where it was fails the AST half by name, and reverting `cascaded_by`'s
  guarded read fails the behavioural half with *"ledger_reopen reported KeyError: 'pin_id' — and the
  write is on disk. A caller that retries writes twice."*
- **`Ledger.writable_collection` is the container half of the refusal.** `writable_pin`'s twin one
  level out, refusing with the collection's name and pointing at `pre_rule_events`, where
  `nonconforming` already reports it as `collection_shape`. Substituting is not available for
  `writable_pin`'s reason: `save()` writes `self.data` back, so a door that appended to a substituted
  `[]` would lose the append or overwrite what the file holds under that key. The AST gate matches
  the forbidden expression by **subscript or `.get`** — a rule that knew one spelling would be
  satisfied by rewriting it as the other — and carries two non-vacuity floors: the carrier must have
  callers, and it must be called with every name in `LEDGER_COLLECTIONS`.
- **`Ledger.writable_pins` is what a door may do with the pins it is not writing to.** `(record,
  read)` pairs: the cascade decides off `pin_read`'s substitutions and writes onto the record. A pin
  with no readable `id` is named by nothing and depended on by nothing; one with no readable `state`
  is in no settled state, so nothing sweeps it up. It participates as what it is. The roster half
  runs the whole derived corpus as a **bystander** beside a healthy target, at every door in the
  union of both write rosters — 155 shapes × 18 doors, nothing named.
- **The read-tool roster's predicate is now *the FIRST required argument is the ledger*,** with the
  extra arguments declared as payload like every other call. Two sentinels resolve at call time (the
  pin id must name a pin in the fixture under test; the graph must be a file), and the pin sentinel
  resolves to the **last** pin — which is load-bearing, because every corpus loop APPENDS its
  malformed record and naming the first pin made the gate pass with the fix reverted. That was found
  by planting, not by reading.

### Traps this round walked into

- **A gate can be widened and still not reach the thing it was widened for.** Adding `scope_check`
  to the roster changed nothing until the sentinel named the appended pin: the first draft passed
  with `pin_read` removed. §18's third shape, on a gate written to close §27's fourth finding.
- **A gate can be too expensive to run.** `readiness_assess` reads the repository's whole `git log`
  per call — measured at 1.29s — which is roughly 45 minutes against the corpus. `_churn` and
  `cochange.outside`
  now return early on an empty file set, which is a real waste-removal and is recorded as a residual
  because nothing gates it.

### Residuals

- **A dropped `pins` entry is reported by `nonconforming` and by no door's return.** Widening
  eighteen response schemas to carry a per-call nonconformance report is a change to eighteen
  contracts, and what it would say is one `ledger_summary` away.
- **`apply_policy` is unchanged and its §25 residual stands**: it writes to pins, takes no `pin_id`,
  and a pin its cascade cannot write to now aborts the cascade partway. What a half-applied policy
  owes its radius is still unsettled here.
- **`_reopen_minimal`'s three-state cascade tuple is unchanged** (§5's residual). The walk was
  rewritten around it and the tuple was deliberately not touched, for §5's own reason.

### The general shape

§25: *a rule proved of the READERS is unproved for the WRITERS.* §26: *a derived roster is a claim
about a class, so name what does the dangerous thing and does not satisfy the predicate.* This round
is both, aimed at the same two predicates one more time — *the pin being written*, and *required ==
["ledger"]* — plus the one question neither shape asks:

- **Is what the door SAYS it did what it did?** A return value is a claim about the file, and a claim
  computed after the commit is a claim nothing checked. The question to ask of any door: *if the line
  after the write raises, what does the caller believe, and what is on disk?*

---

## 28. What the surfaces TELL a reader — **CLOSED 2026-08-07** (map/interview/instructions, no schema change)

### Verified

The eighteenth round, and the first whose subject is neither the write path nor the read path but
the sentence a human ends up reading. It came from the one review that had never run: install the
plugin the way a user does, drive a whole session through it, and open every surface.

Three findings, each observed rather than reasoned:

1. **The map printed a verdict where the file recorded history.** `verificationCard` rendered
   ``⚠ this pin cannot close: ${v.blocked_by}`` with no condition, and `resolve` deliberately KEEPS
   `blocked_by` so *"it was blocked, then it was observed"* survives as the sequence it is. So on the
   most ordinary lifecycle in the package — work blocked, blocker lifted, work observed, pin closed —
   the card said `resolved` and *"this pin cannot close"* in the same breath; after the incident arc
   it printed *"nothing has been observed since"* directly under the observation that closed the pin.
2. **`interview_next` re-asked a settled question.** A `correctness_unknown` pin is sorted to the
   FRONT of the funnel and arrived carrying its original fork prompt and nothing about the answer the
   human had already given it, so an agent driving the interview asked again.
3. **A production failure reached the projection nowhere.** `ledger_label_failure` reaches finished
   work on purpose — an incident label is the move that precedes a reopen — and the map's trail card
   and `learning_report` both carried it while `AGENTS.md` listed the pin under *"Settled — build on
   these"* with nothing said.

### Why it matters

`ledger.refuted_claim` — the predicate that answers finding 1 exactly — **already existed**, with one
caller, and the surface was not it. That is the shape of the whole section: every fact here was
stored correctly, and the reader drew the wrong sentence from it. Eighteen rounds of work on what the
package *records* had never asked what it *says*, and a person only ever meets the saying.

### Done looks like

- `map.refuted_claims` computes the standing refutations in Python and the page reads them, the same
  arrangement as `derived_rungs` and `weak_policies`: one implementation of the rule, testable without
  a browser. Standing → the warning. Answered → the same words as history, which is what they are.
- The funnel entry carries `already_elected` (outcome + event id) and the pin's `state`, keyed off the
  pin's own `decision` rather than off `correctness_unknown` — a reopened or contested pin has an
  elected answer too, and re-asking blind is the same defect one arc over. The human's fork stays
  exactly where its author left it; v0.16 removed the overwrite deliberately and this does not undo it.
- `instructions._failed_in_production` marks the line wherever the pin lands. Scoped to the
  `production` phase: a failure at `plan`/`build`/`evidence`/`review` is the loop working, and marking
  those would spend bytes on the ordinary case — the bargain every clause in that region is under.

### Prove it

`tests/test_map.py::TestARefutationIsShownWhileItStandsAndNotAfter`,
`tests/test_interview.py::TestAPinWhoseForkWasAnsweredSaysSo`,
`tests/test_instructions.py::TestWorkThatFailedInProductionSaysSoHere`. But the assertion that
matters was made in a browser: `scripts/preview_map.py` grew the *blocked, then answered* lifecycle —
it had no fixture, which is why only a browser found it — and all 38 pins were clicked in Chromium
with zero page errors, the standing refutations still warning and the answered one reading
*"was blocked: … — answered since"*.

### Traps

- Do not drive the map's warning off `blocked_by`. Two carriers make that fact and the page must not
  re-derive it from one of them; `test_the_page_reads_the_derivation_and_does_not_re_derive_it` fails
  if the old expression comes back.
- Do not answer finding 2 by overwriting the prompt with the correctness question. That is what v0.16
  removed, and it deleted the human's own menu to do it.

---

## 29. Two sessions can take the same pin — **CLOSED 2026-08-11** (ledger v0.30)

### Verified

Found by reading another package rather than by an incident here, which is worth saying plainly:
`mattpocock/skills`'s wayfinder gives every unit of work an **assignee taken before any work starts**,
and calls the takeable set the *frontier* — open, unblocked, **unclaimed**. Checking this package for
the third of those three: `grep -n "claim\|lease\|lock" src/core/decisions-ledger-spec.md` returns
nothing about ownership. The only `claim` hits are the English word.

What exists instead protects a different thing. `branch-lifecycle` declares a scope's **file globs**
and distinguishes `depends_on` (B needs A's result — ordering) from `conflicts_with` (B and A touch
the same files — mutual exclusion). Worktrees then make that enforceable: two agents in two trees
cannot corrupt each other's files. All of that is about **files**. None of it is about the **item**.

So the concurrency this package already invites — *"the user may run unblocked items in parallel"* —
is safe against corruption and unprotected against duplication: two sessions read the same
`ledger.json`, both see the same unblocked pin, both take it. Nothing corrupts. They do the same work
twice, in different trees, and discover it at the merge. On a `grilling`-shaped pin the failure is
worse than waste — the second session asks the human a question the first already answered, because
sessions share no context.

### Why it matters

The scope-glob mechanism cannot be stretched to cover this, and it is worth being precise about why:
two sessions resolving the same pin may legitimately touch **disjoint** files (one writes the fix, one
writes the test), so `conflicts_with` correctly reports no conflict. The overlap is in the *work
item*, which is the one thing the ledger owns and the filesystem does not.

It is also the cheapest possible fix for a real failure — an owner and a timestamp — which is exactly
the shape of gap that stays open for a year because nobody thinks it is worth a version bump.

### Done looks like

- A pin carries `claimed_by` (an opaque session/agent identifier) and `claimed_at`. Both `null` by
  default; `pin_read` normalises a malformed value to `null`, never to a plausible invented one, and
  reports the substitution under `pre_rule_events` like every other guarded field.
- **One tool takes the claim, and it writes nothing else** — the whole property is that the claim
  lands *before* the work, so a tool that also does something is a tool somebody will call second.
  It is compare-and-set: claiming a pin that already has a live claim fails and returns the holder,
  rather than overwriting.
- A claim **expires**. An agent that dies holding one must not park a pin forever, and the ledger has
  no daemon to reap it, so staleness is computed at read time from `claimed_at` against a declared
  TTL — a tuned number, therefore declared as a hypothesis where `check_hypotheses.py` can see it.
- The reader that makes it worth having: the frontier — open ∧ unblocked ∧ unclaimed — is what
  `interview_next` and the wave scheduler select over, and what the map renders. `check_schema_fields`
  is the gate that will refuse the field otherwise, and correctly: a claim nothing reads is a
  decoration.
- Releasing is explicit and also the settlement doors' business: resolving, deferring or accepting a
  pin clears its claim, because a settled pin is not held.

### Prove it

The assertion that matters is not a unit test of the setter. It is two processes: open the same
`ledger.json` twice, have both call the claim tool on the same pin, and observe exactly one success
and one refusal naming the holder — the same shape as the two-writer tests the ledger already has.
Then the expiry: a claim stamped past the TTL is selectable again, and the tool says it reclaimed a
stale one rather than silently taking it.

### Traps

- **Do not make the claim a `state`.** It is orthogonal to the lifecycle: a pin can be `needs_input`
  and claimed, or `decided` and claimed. Folding it into the state machine would multiply every
  existing state by two and break every transition table in the spec.
- **Do not reuse `depends_on` or `conflicts_with`.** Those two are already the ordering/exclusion
  pair, deliberately separated, and a third meaning on either is how a schedule deadlocks.
- **Do not let the claim gate a write.** It is advisory scheduling metadata, not a lock: an agent that
  legitimately needs to write a claimed pin (the human said so) must not be stopped by it. The failure
  it prevents is duplicated *work*, not concurrent *access* — the ledger's existing write discipline
  covers the latter, and conflating the two would put a lock in a file nobody can unlock.

### Closed as specified — and the one thing the spec did not know

`claimed_by` + `claimed_at`, `CLAIM_STATES`, `CLAIM_TTL_SECONDS` (declared as a hypothesis),
`Ledger.claim` / `release` / `claims` / `frontier`, `buildloop.frontier` / `held`, three MCP tools,
the map badge, and `tests/test_claim.py` — including the two-session reproduction this section
asked for, which is the only test here that would have caught the gap.

**What the writing found: the compare-and-set has to read the FILE.** "Compare-and-set" was stated
above as if the comparison target were obvious, and the obvious one is wrong: two sessions each hold
their own `self.data`, so a check against the in-memory pin answers *did I claim this* — true of
nobody else, therefore always passing. `_claim_on_disk` re-reads the two carriers for the one pin
and nothing else, because a wholesale reload would discard whatever the caller has in flight. The
residual is named in its docstring rather than papered over: between that read and the caller's
`save()` there is a window, which is the same window every other field on the record already has,
and buying more would mean the lock this design exists to avoid.

Two smaller ones, both from the derived gates rather than from reading. `claim` is a per-pin write
door, so it joins `PIN_WRITE_DOORS` (`refuse` — a reservation on finished work parks a pin a session
will never release) and goes through `writable_pin` + `_gate_closed` like every other one; `release`
is `records_only`, because on finished work `_settle` has already taken the claim and refusing
cleanup would make it a thing you check before doing.

---

## 30. In-scope, but not yet phrasable — the register that does not exist — **CLOSED 2026-08-11** (ledger v0.31)

### Verified

Same source, same method. Wayfinder's map carries a **Not yet specified** section — its *fog of war* —
for decisions you can tell are coming but cannot yet phrase, and the test that separates it from a
ticket is sharp: **can you state the question precisely *now*?** — explicitly not *can you answer it
now*. A sharp-but-unanswerable question is a ticket; a question you cannot yet phrase is fog.

This package has no such register, and the two states that look like it are not:

- `deferred` is **out of scope now** — a decision taken, with a settlement event behind it.
- an unwritten pin is nothing at all.

So a decision the interview can *sense* — the funnel compresses pins into decisions, and an
experienced reader can often tell that a whole area will need one — has two available homes, and both
are wrong. Written as a pin now, it is a badly-phrased fork the human must answer, which is precisely
the *"tell me about your app"* open-chat failure `core/interview-funnel.md` was built to prevent: an
under-specified question invites the model to fill it in. Left unwritten, it is gone.

### Why it matters

The funnel's whole thesis is that the enemy is the number of **decisions**, not the number of pins.
A fog register is the other half of that thesis: some decisions are not yet decisions, and forcing
them into the pin shape early is how the interview grows questions nobody can answer — the exact
fatigue the compression exists to remove.

It is also the honest name for something the package already does implicitly. Greenfield's phases
2→7 discover decisions as they go; rescue's `understand` mode surfaces areas before it surfaces
forks. Both already have fog. Neither can write it down.

### Done looks like — and this is the part to settle first

Three candidate shapes, cheapest first. **Pick one in an interview; do not merge them:**

1. **A top-level `fog` collection** — free-text entries with an area and an optional cluster hint, no
   `kind`, no state machine, deliberately coarser than a pin. Cheapest; adds no state.
2. **A pin state `unspecifiable`** — reuses the pin shape, so the graduation is a transition rather
   than a move. Tempting and probably wrong: the entry has no `question`, and the whole pin schema is
   organised around one.
3. **A map/interview surface only**, no schema — fog lives in the projected region and nowhere else.
   Cheapest of all, and fails the package's own rule: a thing no carrier holds is a claim.

Whichever wins, **graduation is the load-bearing half and must be part of it**: when a fog patch
becomes phrasable it becomes a pin *and is deleted from the fog*, so it lives in exactly one place.
Without that, the register is a second home for the same thing — the divergence this package exists
to find. And fog gathers only *toward* the elected scope: work past it is `deferred`, and never
graduates.

### Prove it

A fixture where resolving one pin makes a fog patch phrasable: the graduation produces a pin, the
patch disappears from the fog, and `ledger_summary` reports it in neither place twice. Plus the
negative: a patch that is still fog after the round is still fog, and nothing invented a question for
it.

### Traps

- **Do not let an agent graduate fog on its own.** Phrasing the question *is* framing the decision,
  and framing is where the answer gets smuggled in. The agent proposes the phrasing; the human
  elects it, like any fork.
- **Do not size fog like a ticket.** One patch may become three pins or none. Pre-slicing it into
  pin-sized pieces is the same premature specification the register exists to avoid.
- **Do not let it become a backlog.** It is bounded by the elected scope. A fog register that grows
  monotonically is a to-do list wearing a doctrine's name.

### Closed — shape 1 elected, and what electing it settled

**A top-level `fog` collection.** The other two are recorded in `core/decisions-ledger-spec.md`
§v0.31 so the argument is not re-run, and both fail on their own terms: a pin state `unspecifiable`
reuses a schema organised around a fork the entry does not have, and a surface-only register is a
claim no carrier holds.

Three things fell out of building it that this section did not know:

1. **The absent `question` is the enforcement.** The sharp test — *can you state the question
   precisely now* — cannot be checked by reading prose without becoming the keyword-guessing this
   repo forbids its own linters. Giving the record nowhere to put a fork is structural, and it is
   the same fact that killed shape 2 rather than a second argument.
2. **The register needs an EXIT as much as a ceiling, and it needed two.** Graduation was already
   named as load-bearing; `clear_fog` was not, and without it the only way out is to become a pin,
   which is the backlog trap arriving through the door marked *graduation*. It is held to `defer`'s
   discipline for `defer`'s reason, and it leaves no trail on purpose — a history of things that
   stopped being fog would be a second collection with the first one's failure mode.
3. **`OPTIONAL_COLLECTIONS`, which is a new distinction and a real one.** Adding `fog` to
   `LEDGER_COLLECTIONS` made every ledger written before v0.31 permanently nonconforming — absent
   collection, `collection_shape`, version stamp frozen forever on a rule about a collection the
   file could not have carried. An absent `pins` means a broken file; an absent `fog` means an older
   one. Present-and-wrong is still reported for all four; the exemption is absence only.

The backlog trap is reported rather than enforced, because a cap would move the dishonesty rather
than remove it: `ledger_summary` carries `fog` beside `fog_oldest_days`, and a count that rises
while the oldest patch keeps getting older is the failure, on the call an agent makes before acting.

`tests/test_fog.py` holds the graduation-with-deletion, the negative (a patch that is still fog is
still fog, and nothing invented a question for it), all three traps, and the older-file case.

---

## 31. The package outbid itself for the one thing it needs to be chosen — **CLOSED 2026-08-12** (no schema change)

### Verified

Claude Code loads a listing of every skill's **name and description** into context on every turn,
and that listing is capped. Read at the page that documents the cap, not at the frontmatter
reference:

> *"Claude Code loads a listing of skill names and descriptions into context so Claude knows what's
> available. The listing always contains every skill name, but if you have many skills, Claude Code
> shortens descriptions to fit the listing's character budget, which can strip the keywords Claude
> needs to match your request. **The budget scales at 1% of the model's context window. When the
> listing overflows, Claude Code drops descriptions starting with the skills you invoke least**, so
> the skills you use most keep their full text."*
> — `https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short`

And the lever that removes an entry from that listing, quoted from the behaviour table that states
the consequence in the column that matters:

> | `disable-model-invocation: true` | You can invoke: **Yes** | Claude can invoke: **No** | **Description not in context**, full skill loads when you invoke |
> — same page, *Control who invokes a skill*

Against those two facts the package as shipped was a **self-reinforcing deadlock**, and the numbers
are the argument: nineteen shipped skills, every one model-invoked but the router, **7,745
characters** of description permanently in context, and the two longest entries were the two
flagships — `codebase-rescue` at 824 and `greenfield-forge` at 845. Now run the drop order against
the user this package exists for. A **cold** user has invoked nothing, so every Keel skill sits at
the front of the least-invoked queue; the two longest are the most expensive characters in it; and a
skill whose description is not in context cannot match a request, so it is never invoked, so it
stays at the front of the queue. Nothing in that loop is broken enough to fail a test, and the whole
of the package's value hangs on the two entries it drops first.

Three further facts were checked at the consumer because each one closes an escape somebody would
otherwise reach for:

- **The user cannot free budget for our skills.** `skillOverrides` is the documented way to list a
  low-priority skill by name only — and *"Plugin skills are not affected by `skillOverrides`. Manage
  those through `/plugin` instead."* Keel ships as a plugin. The only lever on Keel's share is
  Keel's own frontmatter.
- **The authored key is not a Claude-ism.** Pi reads the same `disable-model-invocation` and filters
  the skill out of its prompt (`dist/core/skills.js` → `formatSkillsForPrompt`); Codex takes a
  generated `agents/openai.yaml` sidecar; opencode is the stated residual. That machinery already
  existed for `which-skill` — `tests/test_invocation_axis.py` — so this round added no mechanism,
  only the decision about which skills use it.
- **A skill body is not free after it loads.** *"Once a skill loads, its content stays in context
  across turns, so every line is a recurring token cost"* (same page). That makes a loaded `SKILL.md`
  always-on text for the rest of the session, which is the regime `core/instruction-files.md` rule 3
  already has a number for: *"One host truncates by bytes, another loses adherence past ~200
  lines."* Both flagship bodies were over it — 286 and 277 lines.

### Why it matters

This is the package's own thesis turned on the package. Everything here is built so a decision has a
carrier and the carrier is checked; the skills' **trigger** had a carrier — the `description` — that
nobody had ever measured against the budget it competes in. The result was the worst available
allocation: fifteen composable skills, each of which a human can reach by name, were each paying
permanent rent in the one place where the two skills that *cannot* be reached by name have to win.

The asymmetry is what makes it a defect rather than a preference. `/test-driven-development` is a
name somebody types; *"this codebase is a mess"* is a situation with no name attached, and a package
nobody has heard of cannot be summoned by a user who does not know it is installed.

### What was done

- **Invocation split.** Model-invoked: `codebase-rescue`, `greenfield-forge`, `systematic-debugging`
  and `screenshot-to-code` — the four whose trigger is a *situation* rather than a name. The fourth
  arrived from a different branch mid-flight and is the strongest case of the four: its trigger is
  not even text, since a pasted image is not a command anyone types. Every other shipped skill sets
  `disable-model-invocation: true`; `which-skill` already did, and `writing-skills` is dev-only and
  never travels. Fifteen skills now carry the key and the build derives fifteen Codex sidecars.
- **Descriptions tightened, keeping the verbatim user phrases.** Abstract nouns lose to the words a
  person actually types, so *"this codebase is a mess"*, *"the frontend and backend don't match"*,
  *"pick up where I left off"*, *"make this production-ready"*, *"I want to build X"* and
  *"scaffold a new codebase"* all survived the cut. **7,745 → 1,178 characters**, an 85% reduction,
  with the flagships at 355 and 363. `screenshot-to-code` took the deepest single cut, 748 → 196:
  its description was explaining the *method* (palette fact-checking, vetoable inferences, elicited
  states) inside a listing the host truncates, while its body already carried every one of those
  clauses in more detail. Nothing was lost, only moved to where it is read.
- **Progressive disclosure on the two flagship bodies.** 286 → 197 and 277 → 199 lines. Nothing was
  deleted: the guardrails, the learning-layer composition and the prerequisites moved into a new
  `references/guardrails.md` per skill, and the phase prose was compressed onto detail the phase
  playbooks already carried. The old flat "Reference index" became a **conditional** table — every
  row is a situation (*"the work touches more than one layer"*), not a topic — which is the shape
  the host's own guidance asks for and the shape that makes a pointer actionable from a cold read.

### The gate that now holds it shut

`scripts/check_description_budget.py`, run in CI, checks both halves and prints the counts:

- the total description characters over the skills whose frontmatter does **not** set
  `disable-model-invocation: true`, against a declared `LISTING_BUDGET_CHARS = 1_200`, and
- the line count of each flagship `SKILL.md` against `FLAGSHIP_MAX_LINES = 200`, citing
  `core/instruction-files.md` in the failure message.

The budget's arithmetic is written out in the file rather than asserted: 200,000 tokens (the most
conservative published window for a model Claude Code runs) × 1% = 2,000 characters for the whole
listing, × 60% = 1,200 for Keel — leaving 800 for the bundled skills and whatever the user wrote.
The over-allocation is deliberate and named: Keel's flagships are the entries that must survive on a
repo where nothing has been invoked yet.

### Residuals — five, none of them closed by the gate, and **one closed since** (2026-08-13)

The numbering is a citation — `docs/packaging.md` and `check_packaging_wire.py` both point at
*"§31 residual 1"* — so a closed item keeps its number and says so in place rather than being
deleted and the rest renumbered underneath the pointers.

1. **The budget number is a hypothesis about hosts, and its unit is the soft spot. — CLOSED
   2026-08-17**, by re-reading the page rather than by re-deriving anything; the number does not
   move, because the reading already encoded is the one that was right. The doc calls it
   a *"character budget"* that *"scales at 1% of the model's context window"* — a window measured in
   tokens — and the override `SLASH_COMMAND_TOOL_CHAR_BUDGET` is *"a fixed character count"*. Reading
   1% of 200,000 as 2,000 **characters** is the conservative reading; if it is really 2,000 tokens
   the true ceiling is roughly four times larger and this gate is merely strict. The reverse error
   would be silent, which is why the strict reading is the one encoded. It is also a **Claude Code**
   number applied to a package that ships to four hosts: opencode and Codex publish no equivalent
   budget, so for them the gate is prudence rather than a constraint.

   **What settled it, and what it cost to leave open.** The same page now documents
   `skillListingBudgetFraction` — *"(e.g. `0.02` = 2%)"* — a **fraction** applied to the window that
   yields the character budget, with `SLASH_COMMAND_TOOL_CHAR_BUDGET` given as the same quantity
   spelled as *"a fixed character count"*. A fraction of a token-measured window producing a
   character count is precisely the arithmetic the gate encodes, so 1% of 200,000 is 2,000
   **characters** and the four-times-larger alternative is **refuted**, not merely unlikely. The
   architectural consequence is the one worth stating: the fifteen skills moved to
   `disable-model-invocation: true` were **not** cut against a phantom ceiling. Had the unit gone the
   other way, the original 7,745 characters would have nearly fit and this round would have been
   largely unnecessary — which is why leaving a load-bearing unit unverified for five days was the
   real exposure, not the number itself.

   **Two findings from the same read, both against claims this section makes above.**

   - *"The user cannot free budget for our skills"* (§31 Verified) is **too strong**. `skillOverrides`
     genuinely cannot name a plugin skill — that part holds — but the user has three levers on the
     ceiling itself: `skillListingBudgetFraction`, `SLASH_COMMAND_TOOL_CHAR_BUDGET`, and
     `"name-only"` on **their own** low-priority skills, which frees room Keel's entries then
     compete for. None is ours to ship; all are ours to *tell them about*, and a package that
     stays silent is spending a budget it does not own. Now stated in `docs/packaging.md`.
   - **The listing is observable, three ways**, which this section treated as unknowable: `/doctor`
     estimates *"the listing's context cost and its biggest contributors"*; the Skills row in
     `/context` reports *"the size of the listing after the budget is applied, so it matches what
     the model receives"* (accurate since v2.1.196; before that it could read several times high);
     and an over-budget listing warns in the debug log under `--debug`. **Still open as a
     measurement**: nobody has run them against an installed Keel. A derived 1,200 sitting beside
     three instruments that report the real figure is a derivation waiting to be replaced — and the
     replacement needs a real install on a real host, which is why it is named here rather than
     claimed.
   - Not binding, recorded so it is not rediscovered as a constraint: each entry's combined
     `description` + `when_to_use` is capped at 1,536 characters *"regardless of budget"*
     (`skillListingMaxDescChars`). Keel's longest entry is 363.
2. **`code-review` collides with a bundled skill of the same name, and the namespace saves it —
   partly. — CLOSED 2026-08-13**, by executing the recommendation recorded here rather than
   revisiting it. Claude Code bundles `/code-review` (*"bundled skills, such as `/doctor`,
   `/code-review`, `/batch`, `/debug`, `/loop`, and `/claude-api`"*). Ours ships in `keel-kit`, and
   plugin skills are namespaced: *"Plugin skills use a `plugin-name:skill-name` namespace, so they
   can't conflict with other levels"*, so `/keel-kit:code-review` always resolves. What is lost is
   the **bare** name: *"The bare `/fancy` also invokes the skill unless another command already uses
   that name"* — and `code-review` is already used. So `/code-review` runs Anthropic's, not ours,
   silently. **Nothing was renamed** and nothing should be: the recommendation is to keep the name
   (it is what the skill *is*, and renaming trades trigger accuracy for collision-avoidance the
   namespace already provides) and to teach the qualified command wherever the package tells someone
   to review a change. The one place this bites harder is a user who copies the skill folder into
   their own `.claude/skills/` instead of installing the plugin — the docs name that exact case:
   *"a `code-review` skill in your project's `.claude/skills/` replaces the bundled `/code-review`"*.
   That is an override with no warning, and it is the install path this repo does not document.

   **How it closed, and the one thing re-verifying it added.** The recommendation was executed
   exactly as written — nothing renamed. The precedence rules were re-read at the source before
   acting (`https://code.claude.com/docs/en/skills`, *Skill name conflicts*) and all three quoted
   above still hold verbatim, so the decision needed no re-litigation, only the two carriers it
   asked for:

   - **The undocumented install path is now documented**, in `docs/packaging.md` § *"When the name
     is already taken"* — a three-row table of what actually runs for each way the command is typed.
     Re-verifying turned the residual's *"a user who copies the skill folder"* into something
     sharper and closer to home: **this repo makes the override reachable in one argument.**
     `scripts/install.sh` takes its target directory as `$1` (default `~/.agents/skills`, which
     Claude Code ignores), so `bash scripts/install.sh ~/.claude/skills` places every skill at the
     **personal** level — not the project level the docs' example names, so it replaces the bundled
     `/code-review` in *every* project that user opens. The residual imagined a user improvising;
     the real path is a supported-looking argument to our own installer.
   - **The qualified command now has a gate**, `tests/test_name_collision.py`, and its subject is the
     class rather than the instance: the colliding set is derived as `build.shipped_skills()` ∩ the
     bundled roster, and each member must have `/{plugin}:{skill}` spelled in `which-skill` **and**
     in its plugin README. The prose already said the right thing in both places — what it lacked was
     anything that would notice its deletion, or extend it to the next skill named `debug` or
     `verify`. Its declared limit is the bundled roster: a dated copy of somebody else's list, which
     no gate of ours can keep current.

3. **`disable-model-invocation` is not in the Agent Skills spec, and the failure is hard.** Outside
   Claude Code only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`
   are allowed, and *"If you include any field the spec doesn't allow, packaging or upload fails with
   a hard error instead of ignoring the field."* Claude Code plugin skills — how Keel ships — are
   explicitly exempt, and Pi reads the key, so the four supported install paths are unaffected. What
   is now foreclosed is **claude.ai upload / the Skills API / `package_skill.py`**, for fifteen
   skills instead of one. Nobody has asked for that path; it should be recorded as a cost paid, not
   discovered later as a bug.
4. **A user-invoked skill cannot be reached by the model at all, including from another skill.** The
   docs are explicit: *"If Claude tries anyway, Claude Code blocks the call"*, and the key *"also
   prevents the skill from being preloaded into subagents"*. Today nothing in this package composes
   by invoking a sibling skill — the flagships point at `references/*.md`, and the roster agents
   declare no preloaded skills — so the split costs nothing *now*. It becomes a trap the moment
   somebody writes *"invoke the `test-driven-development` skill"* into a playbook, which would read
   as ordinary composition and be blocked at runtime. There is no gate for that; it is written here
   so the next session recognizes it.
5. **The pool is now full, and that was learned by a merge rather than by a gate.** This round was
   authored on a tree without `screenshot-to-code`; the skill landed from a parallel branch already
   model-invoked and carrying a 748-character description, and the total went to 1,809 against a
   1,200 budget the moment the two were merged. The gate caught it — that is the gate working — but
   note *what* it caught: a budget is a shared pool, so the cost of a new model-invoked skill is paid
   by every existing one, and nothing warns the author of the new skill that they are spending
   somebody else's characters. At **1,178 / 1,200** the headroom is 22 characters. The next skill
   that needs a situation-trigger cannot simply be added: it forces either a real cut elsewhere or a
   re-derivation of `LISTING_BUDGET_CHARS` with the arithmetic in the file's comment updated to match.
   Raising the constant to make a red gate green would discard the only measurement anyone has.

---

## 32. The register asserted a completeness it did not have — **PARTLY CLOSED 2026-08-13** (four defects registered below; three still OPEN)

### Verified

This file's own opening is a claim with a carrier nobody had checked:

> *"the **standing register**: every defect this repo has found in itself and has not closed, kept
> in one place, in one shape, so that a cold session can pick any of them up without re-deriving
> the evidence — and so that nothing gets closed twice or forgotten once."*

At the time of writing, four verified, unclosed defects lived **only** in design docs.
`grep -n "mcp-apps\|MCP App\|ui://\|tracker\|measurements.md\|extractor gap" docs/open-gaps.md`
returned zero matches, and every numbered section that states a defect — all of them except §18,
which says in its first line that it is not one — was marked CLOSED. So a cold session reading the
register concluded that nothing was outstanding. That reading is what `CLAUDE.md` and
`MEMORY.md` both route a cold session to, which is what makes the claim load-bearing rather than
decorative.

The omission was not neglect of the file. The same commit range **edited** it (the
`check_packaging_wire.py` note, §31's residual-2 closure), so the file was open in an editor while
four findings were being written down somewhere else. That is the shape worth naming: a register
fails not by being forgotten but by being **updated for the round that is in progress** while the
findings of a different round land in the document nearest to where they were found.

The four, each with its evidence already written and cited here rather than restated:

**32.1 — `_client_can_elicit` promises a door the 2026-07-28 era removed. STILL OPEN.**
`docs/design/mcp-apps.md:255,261`. Driven end to end against 4.0.0b2:
*"`ctx.elicit` raises before touching the wire on a modern connection"* — SEP-2577 removed the
back-channel — and `ledger_record_decision` *"came back `isError` rather than degrading"*, because
`_client_can_elicit` answers from the client's **declared capability** alone and the code then
commits to a path the era deleted. The doc states the order of work itself: fix this **"first and
independently of any bump"**. It is a correctness bug in the flagship election door the day any
host negotiates that revision, whatever pin we are on. **Done looks like:** the predicate answers
from the negotiated protocol revision as well as the capability, and the tool degrades to the
`relay` rung that is already sitting there instead of erroring. **Prove it:** drive
`ledger_record_decision` over a modern connection and observe a recorded decision on the lower rung,
not an `isError`. **Trap:** this is not the version bump, and doing it as part of one buries a
correctness fix inside a migration nobody has scheduled.

**32.2 — five extractor gaps in `src/runtime/shapes.py`, one of which answers two questions with one
value. STILL OPEN.** `docs/measurements.md`. The sharpest: `reconcile_layers` returns `[]` both for
*"these layers agree"* and for *"I parsed neither"* — a clean report from a scan that did not run,
which is the exact class §15 and `check_stated_facts.py` exist for, sitting in the function that
carries the package's central promise. **Done looks like:** the two answers are two values, and a
layer the backend could not parse is reported as unparsed wherever the drift count is read.
**Prove it:** point `reconcile_layers` at a repo whose ORM layer no backend handles and read the
result — agreement and silence must not print the same. **Trap:** the other four gaps are extractor
coverage and are worth measuring before fixing; this one is a reporting defect and is worth fixing
before measuring anything.

**32.3 — the tracker's inbound reopen arc is an unelected open decision. STILL OPEN, and
deliberately.** `docs/design/tracker-projection.md:139`. A comment matching a declared form
(`/keel reopen <reason>`) becoming a `ReopenEvent` is the one direction worth having, and it needs a
ledger schema change plus three questions elected first. It is registered here **as an open
decision, not as a defect**: building it on a hunch puts an unauthenticated comment box on the write
path of the single source of truth. **Done looks like:** the three questions are elected in an
interview and the schema change is written, or the arc is recorded as refused with the reason.
**Prove it:** either a `ReopenEvent` whose provenance names an issue comment and whose author was
authenticated, or a "Do not re-litigate" entry. **Trap:** the attraction ("the team is already in
that surface") is an argument for the projection, which already exists — it is not an argument for
the door.

**32.4 — the apps' JavaScript is checked by no linter here. CLOSED 2026-08-13 in part, and the
residual is named.** `docs/design/mcp-apps.md:229` recorded it as a stated residual: the render path
was exercised manually under a stub DOM and never again. The cost of "never again" arrived exactly
where it was predicted — `renderEntry` read `q.options[].label/.implication`, a key
`interview_next` **never returned**, so the interview app rendered no options at all while four
shipped statements said rendering each option's implication was the whole reason it exists. The
byte-greps could not see it: they check that markup sinks are absent, not that anything appears.
What is closed is the defect (`interview.funnel` now carries `question.options` and
`allow_freeform`, and the app renders them and the brainstorm's proposals as two lists that are
never merged). What remains open is the residual itself: **no CI job executes this JavaScript.**
**Done looks like:** a node test that renders the served bytes under a stub DOM against a real
`interview_next` payload and asserts the option labels reach the tree — the `workflow-engine` job
already runs node 22, so the runner exists. **Prove it:** delete the `options` line from
`interview.funnel` and watch a suite go red. **Trap:** a grep for the string `options` in the served
bytes is not that test; the bug was a key mismatch between two files that both contained the word.

### Why it matters

A register whose completeness is asserted and unchecked is worse than no register, because it
converts "I have not looked" into "there is nothing there". The four above were each found by a
careful round, written up with named evidence, and then made invisible to the next session by being
filed in the document that round happened to be editing.

### What was done

The four are registered above in the register's own shape. 32.4's defect is fixed in the same commit
as this entry; 32.1, 32.2 and 32.3 are open and stated so in their headings.

### The gate that does not exist, and why it is argued rather than built

There is no mechanical check that "every defect a design doc records is registered here". A defect
in prose has no syntax — `docs/design/mcp-apps.md` states 32.1 in a table cell and 32.4 in a
paragraph, and any grep tight enough to find those would miss the next one written differently,
while any grep loose enough to catch it would fire on every sentence containing the word "bug". A
gate that reports a completeness it cannot decide is the defect this section is about, one layer up.

So it belongs to the ungated class §18 already names, with one procedural row worth copying:
**a round that files a finding in a design doc has not filed it.** The design doc is where the
evidence and the mechanism belong; the register is where a cold session looks. Writing in one is
not writing in the other, and the check is a question a human can actually ask at the end of a
round — *which documents did I edit, and does the register know about each finding in them?*

### Traps

- **Do not close 32.1 by pinning away from the prerelease.** The bug is in our predicate, not in the
  library; pinning hides the day it fires rather than the fault that fires it.
- **Do not merge 32.4's residual into the existing byte-greps.** They are static gates on absence
  and cannot observe a render; adding a string to their list would restore exactly the false
  confidence this section is about.
- **Do not read this section's existence as the completeness claim now being carried.** It is
  carried by nothing. What changed is that four known items are in the register instead of none.

---

## 33. The search doctrine's only carrier is a transcript nothing blocking reads — **OPEN**

### Verified

`src/core/search-strategy.md` and `src/core/rule-authoring.md` (added 2026-08-17) are the first
doctrines in `src/core/` that **write nothing**. Every other one lands in an artifact this repo can
re-read: a decision becomes a pin, a finding becomes a `defect`, an authored rule becomes a
`generator` with a measured precision. A search leaves a tool call and nothing else.

That is not a complaint about the doctrines — a search *should* not write to the ledger, and a pin
per grep would be the sediment the ledger spec forbids. It is a statement about what can be
**observed**, and the three places it bites were each checked rather than assumed:

- **The eval's checks read the transcript, and the job that runs them is advisory.**
  `static-first-analysis/evals/evals.json` grades six assertions with `shell_absent` /
  `searched_with` against the Bash command strings in `run.tools`. Those run only under
  `--execute`, which is `continue-on-error` in CI because it needs an `ANTHROPIC_API_KEY` no fork
  holds. `--validate`, the blocking gate, proves the file parses — never that the behaviour happened.
- **Eleven of that file's seventeen assertions carry no machine check at all.** They are reported
  `manual`, which is the harness being honest, not the assertion being covered.
- **Two of four hosts have no mechanism behind the prose.** `hooks/search-nudge.py` reaches Claude
  Code and Codex (both verified at the consumer — Codex's `PreToolUse` fires on commands matched as
  `Bash`, and a hook's `systemMessage` is surfaced as a warning). opencode's `tool.execute.before`
  and Pi's `tool_call` are block-or-nothing, and blocking a shell search is the one thing this hook
  must never do. So on those two the doctrine is prose with nothing behind it.

### Why it matters

This package's standing claim is that a doctrine with no carrier is a wish. §20–§27 spent seven
rounds proving that of the ledger's own rules. These two doctrines are currently in the state those
rounds were about: correct, shipped, and unfalsifiable by any blocking gate. A regression — someone
rewording the tool table into a no-op, or a future skill quietly dropping the pointer — would be
caught by nothing that runs on a pull request.

### What done looks like

Not "make search write to the ledger". Any of these, in increasing order of honesty:

1. The `manual` assertions get machine checks, or are rewritten until they can have one. An
   assertion that cannot be checked should say so in its own words rather than sit beside six that can.
2. A blocking, offline check that does not need an API key — the shape to copy is
   `check_tool_carriers.py`, which proves a *correspondence* (every write tool is named by a shipped
   playbook) without running an agent. The analogue here: every tool the search doctrine names is
   installed by `bootstrap.sh`, and every tool `bootstrap.sh` installs for navigation is named by the
   doctrine. That is decidable from the two files.
3. opencode or Pi grows a non-blocking advisory return, and the adapter — four lines, the rule
   already lives in one place — closes the host gap.

### How to prove it

```bash
python scripts/run_evals.py --validate                      # blocking: the file is well-formed
python scripts/run_evals.py --execute --skill static-first-analysis   # needs a key; grades behaviour
python -m unittest tests.test_run_evals                     # the two new predicates discriminate
```

The middle line is the one that currently proves the doctrine, and the one CI cannot be made to
depend on.

### Traps

- **Do not add a pin kind for a search.** The doctrine is right that a grep hit is a location and
  not a finding; giving it a ledger record would grant it exactly the standing the doctrine spends
  its opening paragraph denying it.
- **Do not close this by counting the 29 unit tests on `search-nudge.py`.** Those prove the hook's
  rules fire and stay silent where they should. They say nothing about whether an agent that read
  the doctrine searches differently, which is the claim.
- **Do not widen the nudge to make it observable.** Its value is the first firing and its silence
  everywhere else; a chattier hook would be easier to detect and worse at its job.

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
