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
  4. the last pin's `<script>` and `<img onerror>` appear as TEXT, and no dialog opens
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
