"""Render a map covering every `as_is` shape the spec allows, for a human to LOOK at.

The map's correctness is a DOM in a browser, and CI here has no browser. The honest response is not
to grep the template for the strings a correct renderer would contain — that would be the
name-matching heuristic this package forbids everywhere else, dressed as a test. It is to make the
manual pass repeatable, so "verified rendered in a browser" in `tests/test_map.py` names a
procedure instead of a memory:

    python scripts/preview_map.py && open .preview/map.html

The pins below are the spec's `as_is` variants (`core/decisions-ledger-spec.md`) plus the cases that
actually broke: an agent-authored free-form payload of long prose under invented keys — which
rendered as a `JSON.stringify` blob until 0.4.1 — hostile content, which went into `innerHTML`
unescaped for just as long, the `evidence` rungs, which until 0.4.2 were written by
`Ledger.decide()` and rendered nowhere, so a decision an agent merely relayed looked exactly like one
the server elicited from the user, and the policy cascade, which then rendered as a relay that
nobody had made.

What to check, in both light and dark:
  1. prose reads as prose; paths, identifiers and enums read as monospace
  2. nested objects indent under their label; arrays of objects become separate items
  3. empty string, null and `{}` all render as "—" or "no as-is yet", never as `null` or `{}`
  4. the hostile pin's `<script>` and `<img onerror>` appear as TEXT, and no dialog opens — INCLUDING
     its `severity`, which is the field that was still interpolated raw into the row, the sub-line
     and a `style` attribute (open the console: no `img` node, no `onerror`, no request for `x`)
  5. `raw` still reveals the exact JSON — the projection may reformat, never hide
  6. the decided pins read as different strengths WITHOUT reading the words: `elicited` is green,
     `from the brief` and `cascaded from a policy` neutral, `transcribed` amber on a tinted card. If
     they look alike, the fix did not land — presence is not visibility.
  7. the transcribed pin quotes the human verbatim, escaped (its answer contains `"` and `<b>`), and
     the unquoted relay says so in amber. Only the weak rung is badged in the left-hand list.
  8. the cascaded pin (the validation one) names the policy, its rule, how the POLICY was elected,
     and quotes that answer — and says nothing about a relay, because nobody relayed anything about
     this pin. That sentence is what the rung was added to stop.
  9. the retries pin — the same cascade as a runtime PREDATING the rung wrote it — reads as a
     cascade too, not as a relay, and says in amber that the file records `transcribed` and why.
     Its policy carries no rung at all, so the card says that is unknown rather than calling it a
     relay. A rule enforced at the write governs no file that already exists, and this is the pin
     that shows it: if these two cascades read differently in kind, the fix did not land.
 10. the logging pin carries NO rung: the card must say the rung is unknown, which is a third thing
     — not the green of an elicited one and not the amber of an unquoted relay.
 11. the STANDING RULES lead the left-hand list, and `pol_0003` — elected, and holding back every
     pin it matched — is reachable and readable there. Until v0.15 it appeared on this page nowhere
     at all, while `ledger_summary` counted it and `AGENTS.md` listed it. Its card must state the
     rule, the scope, the `default_outcome` the user accepted, the rung, and that no decision in
     this ledger names it. `pol_0001`'s card must list the pin it did decide, and clicking through
     must land on that pin.
 12. no pin title is rewritten by the page's own assembly: the `__DERIVED__` pin renders its title
     verbatim, and this frozen page carries no LIVE badge and no self-reload.
 13. the page RENDERS AT ALL with the `A <!--<script> double escape` pin present. It did not: that
     sequence opens HTML's script-data-double-escaped span, `</script>` stops closing anything, and
     the document ended inside the inlined ledger — header, two empty panes, no error in the
     console. Check the panes, not the header.
 14. the `oracle` pin says the rung is one this map does not know — and does NOT also say no rung
     was recorded. Both were printed on one card, and they cannot both be true.
 15. the DEFERRED blocker is not counted as an open blocker by the traffic light (the bar reads
     "settled", not "resolved" — one of those states means "not now"), and its card says
     `deferred (not now)` rather than `decided`.
 16. the correctness-unknown defect reads as OPEN and blocked: the state in the sub-line, and the
     question `mark_correctness_unknown` wrote, naming what blocked verification.
 17. `pol_0001` (transcribed WITH the quote) carries no weak badge in the list, and `pol_0002` (no
     rung) does — the same two the projected `AGENTS.md` counts. Two surfaces, one number.
 18. the CONTESTED pin (`at-least-once`) says, ABOVE its question, that two providers were asked and
     answered differently, and shows both answers. Its own fork is untouched — `cross_derive` no
     longer rewrites the menu, and the field it writes instead had one writer and no reader, so a
     pin that came back to the interview said nowhere why. The `export endpoint` pin, where the two
     providers agreed, must read as agreement and NOT as a warning: if they look alike, the reader
     is decoration.
 19. CONTRAST, in LIGHT mode specifically, and on purpose: the amber warning must read as a warning
     at a glance beside the green `role enum drift` card. It measured 2.48:1 as text and 2.33:1 on
     the tinted card — a warning nobody can read at a glance is a warning nobody printed, arriving
     by another route. Chrome's "auto dark mode for web contents" force-darkens light pages in a
     dark-themed browser: check `matchMedia('(prefers-color-scheme: dark)').matches` before trusting
     a screenshot of either theme.
 20. `Config: files or flags` (and every medium/low open pin) carries a COUNTDOWN line under the
     sub-line: *if you say nothing, the interview settles this with the proposed answer*. `Secrets:
     env vars or a manager` says the opposite — it must be asked. `Validation lives in the handler`
     is decided, so it says nothing at all: a settled pin's resolution mode is history, and printing
     "a rule may settle this without you" over an answered question is a rule on the wrong object.
 21. the `Webhook signature` pin says WHAT BLOCKED VERIFICATION on the page — read it without
     opening the JSON. Its neighbour `The rate limiter counted retries` says what was observed and
     why that earned `resolved`; `Export streams the whole table` says it cannot close and how many
     remediation items are outstanding. Three cards, one vocabulary.
 22. `Export streams the whole table` also carries the landing-zone verdict (harden first, blocked on
     the rate-limiter pin) and the premortem, including the dismissed risk WITH its evidence.
 23. `Background job runner` shows the two proposals and which one the brainstorm recommends —
     above the fork they are supposed to be answerable from.
 24. the TRAIL, at the bottom of a pin: `Checkout completes under 800ms` shows decision → settlement
     → reopen, in order, and says what production reported. `Idempotency key` shows the upheld
     challenge and its argument; `Export streams` shows the recorded failure. Five of these six kinds
     of entry were in the page and on no part of it.
 25. `Feature flags` says its `settles_as` is one this map does not know — in the SAME sentence the
     `oracle` rung uses (item 14), not a bare token in the card's key position.
 26. the `line U+2028 sep U+2029 para` pin renders its title intact and the page still works: those
     two characters are legal in a JSON string and were statement terminators in a pre-ES2019 JS
     string literal, and `ensure_ascii=False` emitted them raw into the inline script.
 27. and in the projected `AGENTS.md` (`instructions.render`, not this page): the three pins whose
     elected outcome is under dispute — `Checkout` (reopened), `Idempotency key` (challenged),
     `outbox` (contested) — say so beside the outcome, and `The importer duplicates the CSV parser`
     sits under a heading that says it is NOT to be built, beside the deferred one.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "runtime"))

import map as mapmod          # noqa: E402
from ledger import Ledger     # noqa: E402

P = [{"source": "preview", "detail": "fixture"}]


def build() -> Ledger:
    led = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.json"))

    # Free-form, agent-authored: invented keys, long prose, a path and a line number. The shape the
    # spec explicitly permits (`other` is open, every variant is constrained but not closed) and the
    # one the old renderer served worst.
    led.add_pin(
        kind="defect", severity="blocker", confidence="extracted", provenance=P,
        title="La fase processi del motore LCA fallisce per intero: adjusted_energy non esiste piu",
        anchors=[{"node_id": "process_strategy", "layer": "backend", "role": "src",
                  "loc": "backend/app/services/lca/strategies/process_strategy.py:299",
                  "blast_radius": {"count": 4, "depth": 2, "edges": "structural/extracted",
                                   "sample": ["backend/app/api/lca.py:88"]}}],
        as_is={
            "file": "backend/app/services/lca/strategies/process_strategy.py",
            "riga": 299,
            "sintomo": "NameError a ogni iterazione del ciclo su PROCESS_NAMES",
            "mascheramento": "la chiamata sta dentro un try/except Exception che registra e "
                             "continua; poiche TUTTI i processi falliscono, "
                             "len(failed_processes)==len(PROCESS_NAMES) e la fase esce in errore",
            "perche_nessuno_se_ne_accorge": "nessun file di test nomina process_strategy: "
                                            "copertura zero sulla strategia",
        },
        to_be={"corrected": "usare total_energy dopo aver confermato la grandezza",
               "evidence": {"tool": "pytest", "rule_id": "test_process_strategy", "loc": "tests/"}})

    # nested object + boolean + array of scalars
    led.add_pin(kind="incompleteness", severity="high", confidence="extracted", provenance=P,
                title="Handler POST /orders is a stub",
                as_is={"present": "route POST /orders defined", "missing": "handler body is `pass`",
                       "is_intentional_stub": True, "touched_layers": ["api", "orm"],
                       "evidence": {"tool": "semgrep", "rule_id": "python.stub.pass",
                                    "loc": "api/orders.py:41"}})

    # array of objects
    led.add_pin(kind="internal_contradiction", severity="medium", confidence="inferred",
                provenance=P, title="Two auth flows coexist",
                as_is={"variants": [{"desc": "JWT on /api/v1", "anchor_ref": "n_501"},
                                    {"desc": "session cookie on /api/v2", "anchor_ref": "n_777"}]})

    # the three-column cross-layer panel — its own path, unchanged, so a regression shows here.
    # Also the STRONG evidence rung: the server asked the user through the host and wrote the reply.
    role = led.add_pin(kind="contract_mismatch", severity="high", confidence="extracted",
                       provenance=P, title="role enum drift",
                       as_is={"db": "ENUM('admin','user')", "api": "role: string",
                              "frontend": "'superadmin'", "disagreeing_layers": ["frontend"]},
                       question={"prompt": "What is the intended role set?",
                                 "options": [{"id": "a",
                                              "label": "Only {admin,user} — the DB is truth",
                                              "implication": "remove the frontend check"}],
                                 "allow_freeform": True})
    led.decide(role["id"], outcome="a", rationale="the DB enum is the narrowest of the three",
               flip_criteria="a fourth role appears in a product requirement",
               evidence="elicited",
               # the shape the elicitation path actually writes: the choice string the host
               # returned, not a bare option id (`mcp/server.py::record_decision`)
               human_answer="a — Only {admin,user} — the DB is truth "
                            "(→ remove the frontend check)")

    # a contract_mismatch with no layers at all: `contractCols` returns '' here, so before 0.4.1
    # the as-is side vanished with no card and no message. Its own row, because the three-column
    # path bypasses `sideCard` and nothing else exercises the empty case.
    led.add_pin(kind="contract_mismatch", severity="medium", confidence="inferred", provenance=P,
                title="contract_mismatch carrying no layers",
                as_is={"disagreeing_layers": ["frontend"]})

    # blank values, and a pin with no to_be at all
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="ranking_service.py repeats 180 lines in three near-identical blocks",
                as_is={"current_design": "three copy-pasted blocks", "concern": "", "note": None})

    # hostile content: the ledger is written by agents reading someone else's repo
    led.add_pin(kind="other", kind_detail="naming convention", severity="low",
                confidence="inferred", provenance=P,
                title="<img src=x onerror=alert('title')>",
                as_is={"payload": "<script>alert('as_is')</script>",
                       "quoted": 'he said "ciao" & left <b>bold</b>'})
    # ...and hostile in the ONE field that never went through `esc`: `severity` was interpolated
    # raw into the list row, the detail sub-line and a `style` attribute, so this put a live `img`
    # node with a live `onerror` into a page whose whole promise is that it is safe to hand to
    # anyone. `add_pin` refuses the value, which is the point — a ledger can arrive from anywhere,
    # and every renderer must survive one that this runtime did not write.
    led.data["pins"][-1]["severity"] = "<img src=x onerror=alert('SEVERITY-XSS')>"
    # The sequence that blanked the WHOLE page: `<!--` unclosed, then a later `<script`. HTML's
    # tokenizer stops honouring `</script>` inside that span, so the inlined ledger swallowed the
    # rest of the document — no LEDGER, two empty panes, no error. A blank map reads as "no
    # findings", which is the worst thing this surface can say.
    led.add_pin(kind="other", kind_detail="renderer", severity="low", confidence="inferred",
                provenance=P, title="A <!--<script> double escape",
                as_is={"payload": "<!-- <script> -->"})

    # The page assembles itself by substituting placeholders into a template, and the ledger is
    # inlined into it — so content carrying a placeholder used to be REWRITTEN by the substitutions
    # that ran after the data was already in the page. `esc` cannot help: it happens in Python,
    # before the page exists. This title must render verbatim, and this frozen file must stay frozen.
    led.add_pin(kind="other", kind_detail="renderer", severity="low", confidence="inferred",
                provenance=P, title="placeholders in content: __DERIVED__ and __LIVE_SCRIPT__",
                as_is={"payload": "__DATA__ __TITLE__ __LIVE_STYLE__ __LIVE_BADGE__"})

    # -- the remaining `evidence` rungs (spec v0.10) ------------------------------------------
    # `elicited` is on the role-enum pin above. These three complete the set the map must tell
    # apart: the weak rung with its quote, the brief, and the relay that quotes nobody. The point
    # of rendering them side by side is that "weaker" must be legible before the words are read.
    relayed = led.add_pin(
        kind="open_decision", severity="blocker", confidence="inferred", provenance=P,
        title="Persistence: Postgres or SQLite",
        as_is={"givens": [], "built": None},
        to_be={"statement": "one primary store, chosen before the first migration"},
        question={"prompt": "Which store does v1 run on?",
                  "options": [{"id": "pg", "label": "Postgres",
                               "implication": "a container in dev; JSONB available"},
                              {"id": "sqlite", "label": "SQLite",
                               "implication": "zero-ops; no concurrent writers"}],
                  "allow_freeform": True})
    # The quote carries `"` and `<b>`: it is human prose relayed by an agent, so it goes through
    # `esc` like every other user-supplied string on this page.
    led.decide(relayed["id"], outcome="pg",
               rationale="the user rejected SQLite over concurrent writers",
               flip_criteria="single-writer deployment becomes the only target",
               evidence="transcribed",
               human_answer='Postgres. "one writer only" is <b>not</b> a constraint I can accept '
                            'in v1 & I would rather pay the container cost now.')

    brief = led.add_pin(
        kind="open_decision", severity="medium", confidence="inferred", provenance=P,
        title="Auth: sessions or JWT",
        as_is={"givens": [], "built": None},
        question={"prompt": "Which session model?",
                  "options": [{"id": "cookie", "label": "Server sessions in a cookie"}],
                  "allow_freeform": False})
    led.decide(brief["id"], outcome="cookie", rationale="pre-decided by the brief",
               flip_criteria="a third-party client needs a bearer token",
               evidence="brief")

    # A relay that quotes nobody. `mcp:record_decision` refuses to write this, so it can only reach
    # a ledger from outside the guarded path — which is exactly when a reader needs to be told.
    unquoted = led.add_pin(
        kind="design_concern", severity="medium", confidence="inferred", provenance=P,
        title="Background jobs: in-process or a queue",
        as_is={"current_design": "a thread pool inside the API process"})
    led.decide(unquoted["id"], outcome="keep the thread pool",
               rationale="the user said it is fine for now",
               flip_criteria="job latency exceeds the request budget",
               evidence="transcribed")

    # `cascaded` (v0.11): nobody answered THIS pin — the user elected a policy over the cluster and
    # this fell under it. Before the rung existed it rendered as "an agent relayed what the user
    # said" plus the missing-quote warning, about the user's own rule. The card must now name the
    # policy and how that was elected, and the quote it shows is the policy's.
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="Validation lives in the handler, not at the boundary",
                cluster_id="cl_nfrs",
                as_is={"current_design": "each handler re-checks its own payload"},
                # v0.12: the cascade may only write an outcome this pin's own question offers, so
                # the pin has to pose the fork the policy answers. A cluster of pins with no
                # question is not one decision.
                question={"prompt": "Where is the payload validated?",
                          "options": [{"id": "boundary", "label": "at the contract boundary"},
                                      {"id": "handler", "label": "in each handler"}]})
    policy = led.add_policy(applies_to={"cluster_id": "cl_nfrs"},
                            rule="validate at the contract boundary; structured errors from one "
                                 "taxonomy",
                            default_outcome="boundary",
                            evidence="transcribed",
                            human_answer="yes — take the boundary rule for all of these, I'll flag "
                                         "the ones I want to argue about")
    led.apply_policy(policy)

    # The same cascade as written by a runtime that PREDATES the rung (v0.13). Composed by hand
    # because `decide()` refuses this shape now: `source` names the policy, `evidence` is the old
    # parameter default, and there is no `policy_id` and no quote. Read literally — which is what
    # every surface did — the card said "an agent relayed what the user said" and warned that
    # nothing separated it from an invention, about a policy the user elected. The `version` below
    # is the file's floor, and it is the reason the two cascades can sit in one fixture: this is
    # what the runtime leaves alone rather than restamping.
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="Retries are configured per call site (decided by a pre-v0.11 cascade)",
                as_is={"current_design": "each caller sets its own retry policy"},
                question={"prompt": "Where does the retry policy live?",
                          "options": [{"id": "central", "label": "one shared client"},
                                      {"id": "call_site", "label": "per call site"}]})
    old_pin = led.data["pins"][-1]
    led.data["policies"].append({"id": "pol_0002", "applies_to": {"kind": "design_concern"},
                                 "rule": "one shared client owns retries", "default_outcome":
                                 "central", "exceptions": []})
    led.data["decision_log"].append({
        "id": "ev_legacy", "pin_id": old_pin["id"], "timestamp": "2026-01-01T00:00:00+00:00",
        "outcome": "central", "rationale": "one shared client owns retries",
        "flip_criteria": "a call site needs its own backoff",
        "source": "policy:pol_0002", "evidence": "transcribed"})
    old_pin["state"] = "decided"
    old_pin["resolution_mode"] = "policy_default"
    old_pin["decision"] = {"event_id": "ev_legacy", "outcome": "central"}

    # A decision with NO rung at all — the third state the card must tell apart from the two weak
    # ones. `decide()` has written `evidence` since v0.10, so this can only come from a file older
    # than that, which is exactly when a reader must be told the rung is unknown rather than weak.
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="Logging format (decided before the rung existed)",
                as_is={"current_design": "each module picks its own format"},
                question={"prompt": "Which log format?",
                          "options": [{"id": "json", "label": "structured JSON"}]})
    unrunged = led.data["pins"][-1]
    led.data["decision_log"].append({
        "id": "ev_norung", "pin_id": unrunged["id"], "timestamp": "2026-01-01T00:00:00+00:00",
        "outcome": "json", "rationale": "the user picked structured logs",
        "flip_criteria": "a log shipper that cannot parse JSON becomes the target",
        "source": "interview"})
    unrunged["state"] = "decided"
    unrunged["decision"] = {"event_id": "ev_norung", "outcome": "json"}

    # -- an elected policy that decided NOTHING (v0.15) ----------------------------------------
    # The state that was invisible: the human elects a rule, every pin it matches is held back by
    # the severity threshold, no DecisionEvent is ever written — and the map showed nothing at all,
    # because a policy card could only be reached by joining backward from a cascaded pin.
    # `ledger_summary` counted it and the projected AGENTS.md listed it; this surface did not.
    led.add_pin(kind="open_decision", severity="blocker", confidence="inferred", provenance=P,
                title="Secrets: env vars or a manager", cluster_id="cl_platform",
                as_is={"givens": ["one deploy target"], "built": None},
                question={"prompt": "Where do secrets live?",
                          "options": [{"id": "manager", "label": "a secrets manager"},
                                      {"id": "env", "label": "environment variables"}]})
    # ...and a pin the same rule matches but whose own fork does not offer its outcome: `not_offered`
    led.add_pin(kind="open_decision", severity="low", confidence="inferred", provenance=P,
                title="Config: files or flags", cluster_id="cl_platform",
                as_is={"givens": [], "built": None},
                question={"prompt": "Where does config live?",
                          "options": [{"id": "file", "label": "a config file"},
                                      {"id": "flags", "label": "command-line flags"}]})
    held = led.add_policy(applies_to={"cluster_id": "cl_platform"},
                          rule="platform choices default to the managed service",
                          default_outcome="manager",
                          evidence="elicited")
    radius = led.apply_policy(held)
    assert radius["would_decide"] == [], radius     # the fixture is only useful if it decided none

    # The SAME state, weakly elected — and the card that used to contradict itself. A rule that
    # bound no pin printed "⚠ …relayed with no quote — every decision that names it rests on that"
    # directly above "no decision in this ledger names this rule": vacuously true, and reading as an
    # accusation about nothing. The clause has to be true of the card it is on.
    led.apply_policy(led.add_policy(
        applies_to={"cluster_id": "cl_observability"},
        rule="every service ships a health endpoint and structured logs",
        default_outcome="both", evidence="transcribed"))

    # -- a rung this page does not know (v0.16) ------------------------------------------------
    # `decide()` refuses it, so it can only come from a hand-edit or from a runtime NEWER than this
    # artifact — which is the likeliest case and the one the wording has to serve. The card used to
    # badge `oracle` and print "no evidence rung recorded" underneath it: one card, two claims,
    # and they cannot both be true.
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="Rate limiting (decided on a rung this map does not know)",
                as_is={"current_design": "no limiter anywhere"},
                question={"prompt": "Where does rate limiting live?",
                          "options": [{"id": "gateway", "label": "at the gateway"}]})
    future = led.data["pins"][-1]
    led.data["decision_log"].append({
        "id": "ev_future", "pin_id": future["id"], "timestamp": "2026-01-01T00:00:00+00:00",
        "outcome": "gateway", "rationale": "the user picked the gateway",
        "flip_criteria": "a second entry point appears", "source": "interview",
        "evidence": "oracle"})
    future["state"] = "decided"
    future["decision"] = {"event_id": "ev_future", "outcome": "gateway"}

    # -- the settled states that are not `decided` (v0.16) --------------------------------------
    # A DEFERRED blocker. Deferring is an election and leaves the open set, so the traffic light
    # must not count this as an open blocker — it did, in the loudest colour the page has, because
    # the page kept its own list of settled states and that list never learned `deferred`.
    led.add_pin(kind="incompleteness", severity="blocker", confidence="extracted", provenance=P,
                title="Multi-tenant isolation is unimplemented",
                as_is={"present": "one shared schema", "missing": "any tenant boundary"},
                question={"prompt": "Does v1 carry more than one tenant?",
                          "options": [{"id": "single", "label": "single tenant"},
                                      {"id": "multi", "label": "multi-tenant from day one"}]})
    led.defer(led.data["pins"][-1]["id"],
              rationale="v1 ships to one customer; the boundary is v2 work",
              flip_criteria="a second customer signs",
              human_answer="not now - v1 is one web client, one customer")

    # A pin whose correctness could NOT be established: it is open, it blocks its own closure, and
    # `mark_correctness_unknown` writes the question a reader has to answer to move it.
    led.add_pin(kind="defect", severity="high", confidence="extracted", provenance=P,
                title="Webhook signature check may accept a replayed body",
                as_is={"file": "api/webhooks.py", "riga": 62,
                       "sintomo": "the timestamp window is never compared"})
    unknown = led.data["pins"][-1]
    led.add_remediation(unknown["id"], action="implement", ladder_rung=3,
                        canonical_target="api/webhooks.py")
    led.mark_correctness_unknown(
        unknown["id"],
        attempted=["tests", "smoke_probe"],
        blocked_by="no fixture reproduces the provider's signing key")

    # -- the same claim re-derived by a second provider (`cross_derivations`, spec v0.9) --------
    # The DISAGREEMENT case, on a pin that already carries the human's own fork — which is exactly
    # the case v0.16 created and nothing rendered: `cross_derive` stopped overwriting the question
    # (rightly: the menu is the human's), and the field it writes instead had one writer and zero
    # readers. So the pin came back to the interview as `needs_input (contested)` with its original
    # menu and no account anywhere of what disagreed or why it was reopened.
    led.add_pin(kind="ambiguity", severity="high", confidence="ambiguous", provenance=P,
                title="Does the scheduler guarantee at-least-once delivery?",
                as_is={"claim": "the README says exactly-once", "code": "no dedup table exists"},
                question={"prompt": "Which delivery guarantee does v1 promise?",
                          "options": [{"id": "at_least_once", "label": "at-least-once + idempotent "
                                       "consumers"},
                                      {"id": "exactly_once", "label": "exactly-once, with a dedup "
                                       "table"}],
                          "allow_freeform": True})
    led.cross_derive(
        led.data["pins"][-1]["id"],
        claim="the scheduler re-delivers on consumer timeout",
        derivations=[{"provider": "anthropic", "model": "opus", "result": "yes — the ack deadline "
                      "expires and the row is re-queued, so duplicates are possible"},
                     {"provider": "openai", "model": "gpt-5", "result": "no — the row is marked "
                      "taken before the handler runs, so a timeout loses the message"}],
        agreement="disagree",
        notes="the two readings differ on WHEN the row is marked, which is the whole question")

    # ...and the AGREEMENT case, so the two must read differently at a glance: agreement is what
    # earns the `cross_derived` rung, and it is not a warning.
    led.add_pin(kind="ambiguity", severity="low", confidence="ambiguous", provenance=P,
                title="Is the export endpoint paginated?",
                as_is={"claim": "the docs show a cursor", "code": "the handler returns all rows"})
    led.cross_derive(
        led.data["pins"][-1]["id"],
        claim="the export endpoint returns every row in one response",
        derivations=[{"provider": "anthropic", "model": "opus", "result": "yes — no LIMIT is "
                      "applied anywhere on that path"},
                     {"provider": "openai", "model": "gpt-5", "result": "yes — the cursor "
                      "parameter is parsed and then never used"}],
        agreement="agree")

    # -- the rest of the pin envelope, and the rest of the log (v0.19) --------------------------
    # Eight fields and five of the six log kinds were written by the runtime and rendered by
    # nothing. Each block below exists so the manual pass has the state to look at: a fixture that
    # cannot show a state cannot check it, which is why §7 could not be seen in a browser at all.

    # A pin that went the whole way: decided → remediation done → observed → resolved. Its trail is
    # the only place a reader can see HOW it stopped being open (`stl_`), and its verification card
    # is the only place the observation that earned `resolved` is stated.
    led.add_pin(kind="defect", severity="medium", confidence="extracted", provenance=P,
                title="The rate limiter counted retries against the caller's budget",
                anchors=[{"node_id": "token_bucket", "layer": "backend", "role": "src",
                          "loc": "api/limits.py:88"}],
                as_is={"file": "api/limits.py", "riga": 88,
                       "sintomo": "a 429 retry decremented the bucket a second time"})
    fixed = led.data["pins"][-1]
    item = led.add_remediation(fixed["id"], action="implement", ladder_rung=2,
                               canonical_target="api/limits.py")
    led.set_remediation_status(fixed["id"], item["id"], "done")
    led.resolve(fixed["id"], rung="observed",
                evidence="drove 200 requests with induced 429s and watched the bucket: one "
                         "decrement per request, not two")

    # ...and the SAME shape with the remediation still open, so the card that says why a pin cannot
    # close is on the page beside the one that closed. `resolve` is refused here (`remediation_open`)
    # and until now that refusal was readable nowhere but the JSON.
    led.add_pin(kind="defect", severity="high", confidence="extracted", provenance=P,
                title="Export streams the whole table into memory before writing",
                as_is={"file": "api/export.py", "riga": 34,
                       "sintomo": "resident memory tracks row count"})
    open_plan = led.data["pins"][-1]
    led.add_remediation(open_plan["id"], action="refactor", ladder_rung=3,
                        canonical_target="api/export.py")
    led.add_remediation(open_plan["id"], action="implement", ladder_rung=2,
                        canonical_target="tests/test_export.py")
    led.set_remediation_status(open_plan["id"], open_plan["remediation"][0]["id"], "in_progress")
    # ...carrying the terrain verdict and the premortem, the two cards addressed to a builder.
    led.set_readiness(open_plan["id"], verdict="harden_first",
                      zone={"files": ["api/export.py", "api/limits.py"], "nodes": [1, 2, 3]},
                      evidence={"cochange": "export.py and limits.py move together in 7 of 9 PRs",
                                "coverage": "no test names export.py"},
                      hardens=[fixed["id"]],
                      rationale="the zone has no test naming it, so the refactor lands blind")
    led.premortem(open_plan["id"],
                  failure_modes=[{"class": "untested_path",
                                  "description": "the streaming path is exercised by nothing, so a "
                                                 "regression ships silently"},
                                 {"class": "nondeterminism",
                                  "description": "chunk boundaries depend on row width; a flake "
                                                 "reads as a pass"}],
                  guardrails=["a fixture with 100k rows before any refactor"],
                  abort_criteria=["memory does not fall below 200MB on the fixture"],
                  paper_tigers=[{"risk": "the client cannot consume a chunked response",
                                 "evidence": "the only two clients already stream (checked in "
                                             "clients/*.py)"}])
    led.label_failure(open_plan["id"], failure_class="untested_path", phase="build",
                      detail="the first attempt passed CI and broke the nightly export",
                      source="measurer")

    # A pin the production signal reopened: elected, closed, then falsified. `rev_` was the arc no
    # host could run until v0.17 and no surface could show until now — a page that reports a pin as
    # settled and never that it was UN-settled answers the wrong question.
    led.add_pin(kind="acceptance_criterion", severity="high", confidence="extracted", provenance=P,
                title="Checkout completes under 800ms at p95",
                as_is={"measured": "p95 620ms at release"},
                to_be={"statement": "p95 under 800ms with the payment provider in the loop"},
                question={"prompt": "What is the checkout latency budget?",
                          "options": [{"id": "800ms", "label": "p95 under 800ms"},
                                      {"id": "2s", "label": "p95 under 2s"}]})
    slo = led.data["pins"][-1]
    led.decide(slo["id"], outcome="800ms", rationale="the payment provider's own p99 is 400ms",
               flip_criteria="p95 exceeds the budget for three consecutive days",
               evidence="transcribed", human_answer="800ms — anything slower and people abandon")
    slo_item = led.add_remediation(slo["id"], action="implement", ladder_rung=2,
                                   canonical_target="checkout/handler.py")
    led.set_remediation_status(slo["id"], slo_item["id"], "done")
    led.resolve(slo["id"], rung="observed",
                evidence="load test at release: p95 620ms over 10k checkouts")
    led.reopen(slo["id"], fired="flip_signal", source="feedback:metrics",
               reason="p95 has been 1.4s for six days since the provider changed region")

    # An upheld CHALLENGE (`chl_`): the upstream arc. The pin keeps the outcome the human elected
    # and is handed back to them — which is exactly the state the projected AGENTS.md printed as a
    # build instruction, because `grep -c substate` over that file returned 0.
    led.add_pin(kind="open_decision", severity="high", confidence="inferred", provenance=P,
                title="Idempotency key: client-supplied or server-derived",
                as_is={"givens": [], "built": None},
                question={"prompt": "Where does the idempotency key come from?",
                          "options": [{"id": "client", "label": "the client sends one"},
                                      {"id": "request_id", "label": "derived from the request id"}],
                          "allow_freeform": True})
    idem = led.data["pins"][-1]
    led.decide(idem["id"], outcome="request_id", rationale="one less thing for a caller to get wrong",
               flip_criteria="a caller needs to retry across two request ids",
               evidence="transcribed", human_answer="derive it — I don't trust callers with this")
    led.challenge(idem["id"], target="decision", challenge_class="unstated_assumption",
                  argument="a derived key assumes the retry carries the same request id, and the "
                           "mobile client generates a new one per attempt — so the guarantee is "
                           "void on exactly the path it was elected for",
                  severity="high", upheld=True)

    # A DECIDED pin two providers then contradicted (`xdr_` + substate `contested`). The pair to the
    # challenge above: same outcome-under-dispute state, reached by the other arc.
    led.add_pin(kind="ambiguity", severity="medium", confidence="ambiguous", provenance=P,
                title="Does the outbox flush before or after the transaction commits?",
                as_is={"claim": "the comment says after", "code": "the call sits inside the block"},
                question={"prompt": "When is the outbox flushed?",
                          "options": [{"id": "after", "label": "after commit"},
                                      {"id": "inside", "label": "inside the transaction"}],
                          "allow_freeform": True})
    outbox = led.data["pins"][-1]
    led.decide(outbox["id"], outcome="after", rationale="the comment is the documented contract",
               flip_criteria="a duplicate delivery is traced to a pre-commit flush",
               evidence="transcribed", human_answer="after commit — that's what we documented")
    led.cross_derive(
        outbox["id"], claim="the flush runs after the transaction commits",
        derivations=[{"provider": "anthropic", "model": "opus",
                      "result": "no — the call is inside the `with` block, so it runs first"},
                     {"provider": "openai", "model": "gpt-5",
                      "result": "yes — the session commits on block exit before the flush task runs"}],
        agreement="disagree",
        notes="the two readings differ on when the session commits, which is the whole question")

    # A pin the brainstorm worked on: `brainstorming` is the state `add_proposals` writes, and the
    # proposals are what the fork is supposed to be answerable from.
    led.add_pin(kind="open_decision", severity="medium", confidence="inferred", provenance=P,
                title="Background job runner", cluster_id="cl_platform",
                as_is={"givens": ["one deploy target"], "built": None},
                question={"prompt": "What runs the background jobs?",
                          "options": [{"id": "rq", "label": "RQ on the existing Redis"},
                                      {"id": "celery", "label": "Celery with a broker"}],
                          "allow_freeform": True})
    led.add_proposals(
        led.data["pins"][-1]["id"],
        proposals=[{"summary": "RQ on the Redis that already exists", "effort": "S",
                    "recommended": True,
                    "tradeoffs": {"pros": ["no new infrastructure"], "cons": ["no native chaining"]}},
                   {"summary": "Celery with a dedicated broker", "effort": "L",
                    "tradeoffs": {"pros": ["chaining, retries, beat"], "cons": ["a broker to run"]}}],
        notes="both were priced against the single deploy target the frame records")

    # A design_concern the human elected to LEAVE AS IS. `accepted` is a settled state whose
    # instruction is *do not build this* — the same instruction as `deferred` — and the projected
    # AGENTS.md listed it under a heading that named only `defer`.
    led.add_pin(kind="design_concern", severity="high", confidence="inferred", provenance=P,
                title="The importer duplicates the CSV parser instead of reusing it",
                as_is={"current_design": "two parsers, one per entry point"})
    led.accept(led.data["pins"][-1]["id"],
               rationale="the duplication is 40 lines and the importer is scheduled for deletion",
               flip_criteria="the importer outlives the next release",
               human_answer="leave it — that whole module goes away in Q4")

    # A `settles_as` this page does not carry. Hand-composed, because `decide` refuses it: it can
    # only come from a runtime NEWER than this artifact, which is the likeliest case and the one the
    # wording has to serve. Its sibling one field over (the `oracle` rung) got three states and a
    # sentence; this one printed the bare token in the card's key position.
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="Feature flags (settled in a way this map does not know)",
                as_is={"current_design": "flags read straight from the environment"},
                question={"prompt": "Where do feature flags live?",
                          "options": [{"id": "config", "label": "in the config file"}]})
    future_state = led.data["pins"][-1]
    led.data["decision_log"].append({
        "id": "ev_future_state", "pin_id": future_state["id"],
        "timestamp": "2026-01-01T00:00:00+00:00", "outcome": "config",
        "rationale": "the user picked the config file",
        "flip_criteria": "a flag has to change without a deploy", "source": "interview",
        "evidence": "elicited", "settles_as": "quarantined"})
    future_state["state"] = "decided"
    future_state["decision"] = {"event_id": "ev_future_state", "outcome": "config"}

    # The two characters `ensure_ascii=False` emitted raw into the inline script: legal in a JSON
    # string, statement terminators in a pre-ES2019 JavaScript one. The title must round-trip and
    # the page must render.
    led.add_pin(kind="other", kind_detail="renderer", severity="low", confidence="inferred",
                provenance=P, title="line \u2028 sep \u2029 para (JSON is not a JS subset)",
                as_is={"payload": "U+2028 and U+2029 ride inside the inlined ledger"})

    # An OPEN pin carrying `policy_default`. Hand-composed, because no path in this runtime produces
    # it — `apply_policy` writes that mode in the same breath as the decision, so on a ledger we
    # wrote it only ever sits on a settled pin, where the decision card already tells the story and
    # the mode line deliberately says nothing. A ledger arrives from anywhere, `RESOLUTION_MODES` is
    # closed, and the page must have a true sentence for each of the three or the third would
    # surface as "a mode this map does not know" — which would be a lie, since it does.
    led.add_pin(kind="design_concern", severity="low", confidence="inferred", provenance=P,
                title="Cache eviction policy (a rule may settle this without asking)",
                cluster_id="cl_nfrs",
                as_is={"current_design": "each cache picks its own TTL"},
                question={"prompt": "Who owns cache eviction?",
                          "options": [{"id": "central", "label": "one shared policy"},
                                      {"id": "per_cache", "label": "per cache"}]})
    led.data["pins"][-1]["resolution_mode"] = "policy_default"

    # LAST, so it fills the field only where the blocks above left it absent: this is what the
    # funnel calls before it asks anything, and it is the only writer of `proposed_default` — the
    # mode that means *silence settles this*. Nothing in this fixture called it, which is why the
    # browser walk could not see that state at all.
    led.assign_resolution_modes()

    led.data["version"] = "0.9"
    return led


def main() -> int:
    out_dir = ROOT / ".preview"
    out_dir.mkdir(exist_ok=True)
    led = build()
    led.save()
    out = mapmod.render_file(led.path, out_dir / "map.html")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
