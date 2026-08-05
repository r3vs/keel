"""Render a map covering every `as_is` shape the spec allows, for a human to LOOK at.

The map's correctness is a DOM in a browser, and CI here has no browser. The honest response is not
to grep the template for the strings a correct renderer would contain — that would be the
name-matching heuristic this package forbids everywhere else, dressed as a test. It is to make the
manual pass repeatable, so "verified rendered in a browser" in `tests/test_map.py` names a
procedure instead of a memory:

    python scripts/preview_map.py && open .preview/map.html

The pins below are the spec's `as_is` variants (`core/decisions-ledger-spec.md`) plus the two cases
that actually broke: an agent-authored free-form payload of long prose under invented keys — which
rendered as a `JSON.stringify` blob until 0.4.1 — and hostile content, which went into `innerHTML`
unescaped for just as long. Both should now read as ordinary rows of text.

What to check, in both light and dark:
  1. prose reads as prose; paths, identifiers and enums read as monospace
  2. nested objects indent under their label; arrays of objects become separate items
  3. empty string, null and `{}` all render as "—" or "no as-is yet", never as `null` or `{}`
  4. the last pin's `<script>` and `<img onerror>` appear as TEXT, and no dialog opens
  5. `raw` still reveals the exact JSON — the projection may reformat, never hide
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

    # the three-column cross-layer panel — its own path, unchanged, so a regression shows here
    led.add_pin(kind="contract_mismatch", severity="high", confidence="extracted", provenance=P,
                title="role enum drift",
                as_is={"db": "ENUM('admin','user')", "api": "role: string",
                       "frontend": "'superadmin'", "disagreeing_layers": ["frontend"]},
                question={"prompt": "What is the intended role set?",
                          "options": [{"id": "a", "label": "Only {admin,user} — the DB is truth",
                                       "implication": "remove the frontend check"}],
                          "allow_freeform": True})

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
