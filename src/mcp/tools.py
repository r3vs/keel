"""The MCP tool bodies — stdlib only, importable without FastMCP, testable in plain CI.

The split here is the repo's own pattern, the one `treesitter_extract.py` already follows: **the
engine stays pure, the adapter carries the dependency.** `server.py` is the FastMCP adapter and
pulls a ~77-package tree; this module is the part that is actually ours, so it holds no MCP
concepts at all and its tests need nothing installed.

It also survives the thing that killed the first attempt: MCP's 2026-07-28 revision drops the
`initialize` handshake, mandates `server/discover`, and requires `resultType` on every result. Not
one line in this file knows or cares — the protocol churn lands entirely on the adapter, where a
version bump absorbs it.

Every function calls the runtime's *library* API — never a subprocess or a printing entry point
(the modules no longer have a `main()` at all). Under stdio transport stdout is the wire, so a stray
print would corrupt the session.
"""
import json
import sys
from pathlib import Path

# The runtime sits beside this file once vendored into a plugin (mcp/runtime/), and one level up in
# the authoring tree (src/runtime/). Accept both so dev and shipped layouts behave identically.
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE / "runtime", _HERE.parent / "runtime"):
    if _candidate.is_dir():
        sys.path.insert(0, str(_candidate))
        break


def _open_existing(path: str):
    """Load a ledger that must already exist.

    `Ledger(path)` deliberately creates a fresh empty ledger when the file is absent — correct for
    the write path, but a trap for a read tool: a mistyped path would answer "no pins", and the
    agent would conclude there is nothing to do. That is a confident wrong answer, the exact failure
    this package exists to prevent. Reads refuse instead.
    """
    from ledger import Ledger
    if not Path(path).is_file():
        raise FileNotFoundError(
            f"no ledger at {path!r}. Not creating one: an empty summary would read as "
            f"'nothing to do'. Check the path, or run the skill's Phase 1 to build it."
        )
    return Ledger(path)


def ledger_summary(ledger: str) -> dict:
    return _open_existing(ledger).summary()


def interview_next(ledger: str) -> dict:
    import interview
    return interview.funnel(_open_existing(ledger))


# -- ledger writes (non-electing only; electing an outcome is the human interview's job) ----------

def _open_or_create(path: str):
    """Load a ledger for a WRITE. Unlike the read path, a missing file is created here — this is how
    the first pin lands. Reads refuse a missing path; writes bootstrap it."""
    from ledger import Ledger
    return Ledger(path)


def ledger_add_pin(ledger: str, kind: str, title: str, severity: str, confidence: str,
                   provenance: list, as_is: dict | None = None, to_be: dict | None = None,
                   question: dict | None = None, depends_on: list | None = None,
                   kind_detail: str | None = None, cluster_id: str | None = None) -> dict:
    led = _open_or_create(ledger)
    pin = led.add_pin(kind=kind, title=title, severity=severity, confidence=confidence,
                      provenance=provenance, as_is=as_is, to_be=to_be, question=question,
                      depends_on=depends_on, kind_detail=kind_detail, cluster_id=cluster_id)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin["id"], "kind": pin["kind"], "state": pin["state"]}


def ledger_surface_assumption(ledger: str, title: str, detail: str, severity: str = "medium",
                              confidence: str = "inferred") -> dict:
    led = _open_or_create(ledger)
    pin = led.surface_assumption(title=title, detail=detail, severity=severity, confidence=confidence)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin["id"], "state": pin["state"]}


def ledger_add_remediation(ledger: str, pin_id: str, action: str, ladder_rung: int,
                           canonical_target: str | None = None, build_track: str | None = None,
                           contract_carrier: str | None = None, depends_on: list | None = None) -> dict:
    led = _open_existing(ledger)
    item = led.add_remediation(pin_id, action=action, ladder_rung=ladder_rung,
                               canonical_target=canonical_target, build_track=build_track,
                               contract_carrier=contract_carrier, depends_on=depends_on)
    led.save()
    _refresh_live_maps(ledger)
    return {"item_id": item["id"], "pin_id": pin_id, "status": item["status"]}


def ledger_set_remediation_status(ledger: str, pin_id: str, item_id: str, status: str) -> dict:
    led = _open_existing(ledger)
    item = led.set_remediation_status(pin_id, item_id, status)
    led.save()
    _refresh_live_maps(ledger)
    return {"item_id": item["id"], "status": item["status"]}


def ledger_resolve(ledger: str, pin_id: str, evidence: str) -> dict:
    led = _open_existing(ledger)
    pin = led.resolve(pin_id, evidence=evidence)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin["id"], "state": pin["state"]}


def ledger_defer(ledger: str, pin_id: str) -> dict:
    led = _open_existing(ledger)
    pin = led.defer(pin_id)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin["id"], "state": pin["state"]}


# -- coverage manifest -------------------------------------------------------------------------

def coverage_gaps(langs: list, reports: list | None = None) -> dict:
    """Which expected analysis capabilities ran vs are missing, for the present stacks."""
    import coverage
    return coverage.report(langs, reports or [])


def contract_diff(contract: str, backend: str = "auto", **layers) -> dict:
    import shapes
    return shapes.drift_check(contract, backend=backend, **{k: v for k, v in layers.items() if v})


def reconcile_layers(layer_a: str, path_a: str, layer_b: str, path_b: str) -> dict:
    import shapes
    return shapes.reconcile_layers(layer_a, path_a, layer_b, path_b)


def _git_head(cwd: str | None = None) -> str:
    """HEAD of the repository the agent is working in. Resolved here rather than asked of the
    caller: an agent cannot reliably know the sha, and a wrong one silently defeats the staleness
    gate — which is the one thing making the graph's answers trustworthy."""
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def blast_radius(graph_path: str, node_id: str, head: str = "", depth: int = 2) -> dict:
    import graph as G
    g = G.load(graph_path)
    head = head or _git_head()
    if not head:
        raise RuntimeError(
            "cannot resolve HEAD (not a git repo, or git unavailable) — pass `head` explicitly; "
            "without it the staleness gate cannot run, and an ungated blast radius is worse than none"
        )
    if not g.is_current(head):
        # A stale blast radius reports impact for code that has since moved. Refuse, don't degrade.
        raise RuntimeError(
            f"graph is stale (built_at_commit={g.built_at_commit!r} != HEAD {head!r}) — rebuild it; "
            "a blast radius computed on a stale graph is worse than none"
        )
    return {"node_id": node_id, "head": head,
            "impacted": sorted(g.blast_radius(node_id, max_depth=depth))}


def generate_layers(contract: str, out: str, layers: list | None = None) -> dict:
    import generate as GEN
    c = GEN.Contract.load(contract)
    produced = GEN.generate_all(c, tuple(layers) if layers else GEN.LAYERS)
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    written = {}
    for layer, text in produced.items():
        p = outdir / GEN._FILENAMES[layer]
        p.write_text(text, encoding="utf-8", newline="\n")
        written[layer] = str(p)
    return {"written": written}


def findings_gate(reports: list) -> dict:
    import findings as F
    gated = F.FpGate().run(F.load_and_normalize(reports))
    return {"findings": gated, "audit": F.audit_log(gated)}


def build_waves(ledger: str) -> dict:
    import buildloop
    return buildloop.plan(_open_existing(ledger))


def challenge_oracle(ledger: str) -> dict:
    import challenger
    return {"proposed": challenger.scan(_open_existing(ledger))}


def _livemap_marker(ledger: str) -> Path:
    """Sidecar that records which map file(s) are tracking this ledger live. A file:// page cannot
    poll a sibling JSON (opaque origin), so 'live' is the MCP layer re-projecting the file on every
    ledger write; this marker is how a write knows a live map exists and where it is. It is a runtime
    artifact next to ledger.json (same gitignore class), created only when live=True is requested."""
    return Path(str(ledger) + ".livemap")


def _register_live_map(ledger: str, out: str) -> None:
    m = _livemap_marker(ledger)
    outs: list = []
    if m.is_file():
        try:
            outs = json.loads(m.read_text(encoding="utf-8")).get("outs", [])
        except (OSError, ValueError):
            outs = []
    ap = str(Path(out).resolve())
    if ap not in outs:
        outs.append(ap)
    m.write_text(json.dumps({"outs": outs}), encoding="utf-8", newline="\n")


def _unregister_live_map(ledger: str, out: str) -> None:
    m = _livemap_marker(ledger)
    if not m.is_file():
        return
    try:
        outs = json.loads(m.read_text(encoding="utf-8")).get("outs", [])
    except (OSError, ValueError):
        return
    outs = [o for o in outs if o != str(Path(out).resolve())]
    if outs:
        m.write_text(json.dumps({"outs": outs}), encoding="utf-8", newline="\n")
    else:
        try:
            m.unlink()
        except OSError:
            pass


def _refresh_live_maps(ledger: str) -> None:
    """Re-project every live map registered for this ledger. Best-effort by design: a render failure
    must never break the ledger write that triggered it, and a ledger with no live map pays nothing
    (the marker check returns immediately)."""
    m = _livemap_marker(ledger)
    if not m.is_file():
        return
    try:
        outs = json.loads(m.read_text(encoding="utf-8")).get("outs", [])
    except (OSError, ValueError):
        return
    if not outs:
        return
    import map as M
    for out in outs:
        try:
            M.render_file(ledger, out, live=True)
        except (OSError, ValueError):
            continue


def render_map(ledger: str, out: str, live: bool = False) -> dict:
    import map as M
    _open_existing(ledger)  # refuse to render a map of a ledger that isn't there
    M.render_file(ledger, out, live=live)
    # live=True registers the file so every later ledger write re-projects it; live=False (the
    # shareable frozen artifact) clears any prior registration so it stops auto-refreshing.
    (_register_live_map if live else _unregister_live_map)(ledger, out)
    return {"written": out, "live": live}


# -- comprehension / understand-mode (the structural-graph family) ----------------------------
# These read/write the graph.json + its projections on disk. The graph is the foundational
# artifact the rest of the family consumes (phases communicate through disk, never a session).

def build_graph(root: str, out: str, commit: str = "") -> dict:
    import graph_build
    data = graph_build.build_graph(root, commit=commit or None)
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return {"written": out, "nodes": len(data.get("nodes", [])), "edges": len(data.get("links", [])),
            "built_at_commit": (data.get("graph") or {}).get("built_at_commit")}


def understand_codebase(root: str, out: str, commit: str = "") -> dict:
    import understand
    bundle = understand.understand(root, commit=commit or None)
    paths = understand.write_bundle(bundle, out)
    return {"written": paths, "overview": bundle.get("overview")}


def explain_node(graph_path: str, target: str, root: str = "") -> dict:
    import explain
    return explain.explain(explain.load(graph_path), target, root=root or None)


def graph_query(graph_path: str, query: str, limit: int = 10, expand: bool = True) -> dict:
    import query as Q
    return Q.search(Q.load(graph_path), query, limit=limit, expand=expand)


def guided_tour(graph_path: str, max_steps: int = 14) -> dict:
    import tours
    return tours.build_tour(tours.load(graph_path), max_steps=max_steps)


def domain_view(root: str) -> dict:
    import domain
    return domain.scan_entry_points(root)


def fingerprint_scan(root: str, out: str, against: str = "", commit: str = "") -> dict:
    import fingerprint as FP
    new = FP.store(root, commit=commit or None)
    result = {"files": len(new.get("files", {})), "built_at_commit": new.get("built_at_commit")}
    if against:
        old = FP.load_store(against)
        result["verdict"] = FP.classify_update(FP.diff_stores(old, new), len(new.get("files", {}))) \
            if old else {"verdict": "FULL", "reason": "no prior fingerprint store"}
    result["wrote"] = FP.save_store(new, out)   # guarded: False rather than clobber a non-empty store
    return result


def graph_map(graph_path: str, out: str, tour_path: str = "", title: str = "") -> dict:
    import graphmap
    graphmap.render_file(graph_path, out, tour_path or None)
    return {"written": out}


def impact_overlay(graph_path: str, changed: list | None = None, git_base: str = "",
                   root: str = ".", depth: int = 1) -> dict:
    import impact
    files = list(changed) if changed else (
        impact.changed_files_from_git(root, git_base) if git_base else None)
    if not files:
        raise ValueError("provide `changed` (a file list) or `git_base` (a git ref) — "
                         "impact needs a change set to compute a blast radius over")
    return impact.overlay(impact.load(graph_path), files, depth=depth)


def docs_claims(graph_path: str, docs: list) -> dict:
    import docs_claims as DC
    return DC.analyze(list(docs), DC.load(graph_path))
