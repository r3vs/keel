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
    the first pin lands. Reads refuse a missing path; writes bootstrap it.

    Also stamps the governance record when one is absent. This used to be an agent-facing tool, and
    that was wrong twice: it rented ~250 tokens of description in every session to expose a button no
    playbook ever pressed, and it made the trail's completeness depend on an agent remembering to
    press it. The server already knows its own root and version, so it can answer "under which rules"
    without being asked. A fact the machine can establish should never be a question put to a model.
    """
    from ledger import Ledger
    led = Ledger(path)
    if not led.data.get("governance"):
        led.set_governance(_governance_record())
    return led


def _governance_record() -> dict:
    """The policy fingerprint from what this process can see: the vendored roster and the spec
    version it ships with. Unresolvable inputs land in `missing` rather than being dropped."""
    import governance
    from ledger import SCHEMA_VERSION
    roster = next((str(c) for c in (_HERE / "core" / "agents.md",
                                    _HERE.parent / "core" / "agents.md") if c.is_file()), "")
    version = ""
    for manifest in (_HERE.parent / ".claude-plugin" / "plugin.json",
                     _HERE.parent.parent / ".claude-plugin" / "plugin.json"):
        if manifest.is_file():
            try:
                version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
            except (OSError, ValueError):
                version = ""
            break
    return governance.record(roster=roster, spec_version=SCHEMA_VERSION, skill_version=version)


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


def decision_prompt(ledger: str, pin_id: str) -> dict:
    """The fork exactly as the pin poses it — what to put in front of the human, nothing invented.

    Read-only, and separate from recording on purpose: the thing that ASKS must be able to run
    without the power to write.
    """
    pin = _open_existing(ledger).pin(pin_id)
    question = pin.get("question")
    if not question:
        raise ValueError(
            f"{pin_id} poses no question, so there is nothing to elect. A pin reaches "
            f"`decided` only through the fork the interview put to the user; a `defect` needs no "
            f"election and goes straight to remediation."
        )
    return {
        "pin_id": pin_id,
        "title": pin["title"],
        "kind": pin["kind"],
        "severity": pin["severity"],
        "prompt": question["prompt"],
        "options": [{"id": o["id"], "label": o["label"], "implication": o.get("implication", "")}
                    for o in question.get("options", [])],
        "allow_freeform": bool(question.get("allow_freeform")),
        "can_accept_as_is": pin["kind"] == "design_concern",
    }


def record_decision(ledger: str, pin_id: str, option_id: str, rationale: str, flip_criteria: str,
                    human_answer: str = "", evidence: str = "transcribed",
                    accept_as_is: bool = False, apply_to_cluster: bool = False) -> dict:
    """Record an election the HUMAN made. This tool does not elect; it writes down what was elected.

    That distinction is the package's central invariant, and until now it was implemented by having
    no tool at all — which stopped an agent from choosing and also stopped the human from being
    recorded, so after the CLI was removed no pin on any host could reach `decided`. The whole
    downstream chain rests on that state: `DecisionEvent`, `flip_criteria`, the reopen loop, and
    `roadmap = diff(to_be, as_is)`. Only `defect` pins moved, because they need no election.

    What replaces "there is no tool" is a tool that cannot be used to choose:

      * `option_id` must name an option the pin's own `question` offers. An agent cannot elect an
        outcome the interview never put to the user — the menu is the ledger's, not the caller's.
      * freeform is allowed only where the question says `allow_freeform`, and then the human's
        words ARE the outcome.
      * `flip_criteria` is required, so no decision fossilizes out of reach of the reopen loop.
      * a `transcribed` decision must quote the human. An agent asserting "the user chose B" with
        nothing quoted is exactly the claim `evidence` exists to make checkable — and this is the
        boundary where that claim gets made, which is why the rule lives here and not in `ledger.py`.

    `evidence="elicited"` is reserved for the adapter's elicitation path, where the server asks the
    user through the host and the agent never carries the value. See `mcp/server.py`.
    """
    prompt = decision_prompt(ledger, pin_id)
    offered = {o["id"] for o in prompt["options"]}

    if accept_as_is:
        if not prompt["can_accept_as_is"]:
            raise ValueError(
                f"{pin_id} is a {prompt['kind']}; leaving-as-is is the legitimate resolution of a "
                f"design_concern only — an open_decision has nothing to keep."
            )
    elif option_id == "freeform":
        if not prompt["allow_freeform"]:
            raise ValueError(f"{pin_id} does not allow a freeform answer; choose one of {sorted(offered)}")
        if not human_answer:
            raise ValueError("a freeform election IS the human's words — human_answer is required")
    elif option_id not in offered:
        raise ValueError(
            f"{option_id!r} is not an option this pin offers ({sorted(offered) or 'none'}). An "
            f"agent may record an election, never invent one: the menu belongs to the question the "
            f"interview asked. Use option_id='freeform' if the question allows it."
        )

    if evidence == "transcribed" and not human_answer:
        raise ValueError(
            "a transcribed decision must carry the human's answer verbatim in human_answer — "
            "without it, an honest relay and a fabricated one are indistinguishable in the ledger"
        )

    led = _open_existing(ledger)
    if accept_as_is:
        led.accept(pin_id, rationale=rationale, flip_criteria=flip_criteria,
                   evidence=evidence, human_answer=human_answer)
        outcome, state = "keep", "accepted"
    else:
        outcome = human_answer if option_id == "freeform" else option_id
        led.decide(pin_id, outcome=outcome, rationale=rationale, flip_criteria=flip_criteria,
                   evidence=evidence, human_answer=human_answer,
                   apply_to_cluster=apply_to_cluster)
        state = "decided"
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin_id, "state": state, "outcome": outcome, "evidence": evidence}


def interview_expand(ledger: str, project_type: str = "web-saas",
                     brief_decisions: dict | None = None) -> dict:
    """Materialize the decision catalog as pins — greenfield's Phase-2 opening move.

    Exposed because the funnel had no pins to funnel: `interview_next` reads, and the thing that
    CREATES the forks lived in `interview.expand_catalog` with no surface at all, so Phase 2 could
    not start through the only runtime channel there is.
    """
    import interview
    led = _open_or_create(ledger)
    result = interview.expand_catalog(led, interview.load_catalog(), project_type=project_type,
                                      brief_decisions=brief_decisions or {})
    led.save()
    _refresh_live_maps(ledger)
    return result


def ledger_add_remediation(ledger: str, pin_id: str, action: str, ladder_rung: int,
                           canonical_target: str | None = None, build_track: str | None = None,
                           contract_carrier: str | None = None) -> dict:
    led = _open_existing(ledger)
    item = led.add_remediation(pin_id, action=action, ladder_rung=ladder_rung,
                               canonical_target=canonical_target, build_track=build_track,
                               contract_carrier=contract_carrier)
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


def readiness_assess(ledger: str, pin_id: str, graph_path: str, repo: str = ".",
                     max_depth: int = 2, head: str = "") -> dict:
    import readiness
    led = _open_existing(ledger)
    pin = led.pin(pin_id)
    head = head or _git_head()
    if not head:
        raise RuntimeError(
            "cannot resolve HEAD (not a git repo, or git unavailable) — pass `head` explicitly; "
            "without it the staleness gate cannot run, and a zone from a stale graph describes "
            "ground that has since moved"
        )
    return readiness.assess(graph_path, led.data, pin.get("anchors", []),
                            repo=repo, max_depth=max_depth, head=head)


def ledger_set_readiness(ledger: str, pin_id: str, verdict: str, zone: dict, evidence: dict,
                         hardens: list | None = None, rationale: str = "") -> dict:
    led = _open_existing(ledger)
    pin = led.set_readiness(pin_id, verdict, zone, evidence,
                            hardens=hardens, rationale=rationale)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin["id"], "readiness": pin["readiness"],
            "depends_on": pin["depends_on"]}


def ledger_mark_correctness_unknown(
    ledger: str,
    pin_id: str,
    blocked_by: str,
    attempted: list,
    determinism: str | None = None,
    rung: str | None = None,
) -> dict:
    led = _open_existing(ledger)
    pin = led.mark_correctness_unknown(
        pin_id, blocked_by=blocked_by, attempted=attempted,
        determinism=determinism, rung=rung)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin["id"], "state": pin["state"],
            "verification": pin["verification"]}


def ledger_premortem(ledger: str, pin_id: str, failure_modes: list,
                     guardrails: list | None = None, abort_criteria: list | None = None,
                     paper_tigers: list | None = None) -> dict:
    led = _open_existing(ledger)
    pm = led.premortem(pin_id, failure_modes, guardrails=guardrails,
                       abort_criteria=abort_criteria, paper_tigers=paper_tigers)
    led.save()
    _refresh_live_maps(ledger)
    return {"pin_id": pin_id, "premortem": pm}


def ledger_label_failure(ledger: str, pin_id: str, failure_class: str, detail: str,
                         phase: str, source: str = "measurer") -> dict:
    led = _open_existing(ledger)
    event = led.label_failure(pin_id, failure_class, detail, phase, source=source)
    led.save()
    return {"event": event, "foresight": led.foresight(pin_id)}


def learning_report(ledger: str, min_cluster: int = 2, candidates: list | None = None) -> dict:
    import learning
    return learning.report(_open_existing(ledger), min_cluster=min_cluster, candidates=candidates)


def generator_observe(registry: str, generator: str, outcome: str) -> dict:
    import generators
    reg = generators.load(registry)
    rec = generators.observe(reg, generator, outcome)
    generators.save(reg, registry)
    return {"generator": generator, "record": rec,
            "verdict": generators.health(reg)}


def generator_screen(registry: str, findings: list, bump_run: bool = False) -> dict:
    import generators
    reg = generators.load(registry)
    if bump_run:
        reg["runs"] = reg.get("runs", 0) + 1
        generators.save(reg, registry)
    return generators.screen(reg, findings)


def doc_register(catalog: str, path: str, subject: str, owner: str, sources: list,
                 repo: str = ".", status: str = "planned", commit: str = "") -> dict:
    import doccatalog
    cat = doccatalog.load(catalog)
    entry = doccatalog.register(cat, path, subject, owner, sources, repo=repo,
                                status=status, commit=commit)
    doccatalog.save(cat, catalog)
    return {"registered": entry, "total": len(cat["docs"])}


def doc_freshness(catalog: str, repo: str = ".", graph_path: str = "",
                  changed: list | None = None, git_base: str = "") -> dict:
    import doccatalog
    import impact
    cat = doccatalog.load(catalog)
    graph_data = impact.load(graph_path) if graph_path else None
    files = list(changed) if changed is not None else (
        impact.changed_files_from_git(repo, git_base) if git_base else None)
    out = doccatalog.cascade(cat, files or [], repo=repo, graph_data=graph_data) \
        if files is not None else {
            "rows": [doccatalog.freshness(cat, d, repo=repo, graph_data=graph_data)
                     for d in cat.get("docs", [])],
            "policy": cat.get("policy"),
        }
    out["coverage"] = doccatalog.coverage(cat)
    return out


def ledger_cross_derive(ledger: str, pin_id: str, claim: str, derivations: list,
                        agreement: str, notes: str = "") -> dict:
    led = _open_existing(ledger)
    record = led.cross_derive(pin_id, claim, derivations, agreement, notes)
    led.save()
    _refresh_live_maps(ledger)
    pin = led.pin(pin_id)
    return {"pin_id": pin_id, "cross_derivation": record, "state": pin["state"],
            "verification": pin.get("verification")}


def cochange_omissions(changed: list | None = None, repo: str = ".", git_base: str = "",
                       min_commits: int = 3, window: int = 500) -> dict:
    import cochange
    import impact
    files = list(changed or [])
    if not files and git_base:
        files = impact.changed_files_from_git(repo, git_base)
    if not files:
        raise RuntimeError(
            "no changed files — pass `changed` explicitly or a `git_base` to diff against; "
            "an empty diff would report zero omissions, and that would read as clean"
        )
    return cochange.omissions(repo, files, min_commits=min_commits, limit=window)


def scope_check(ledger: str, pin_id: str, changed: list | None = None, repo: str = ".",
                git_base: str = "") -> dict:
    import impact
    led = _open_existing(ledger)
    files = list(changed or [])
    if not files and git_base:
        files = impact.changed_files_from_git(repo, git_base)
    return impact.declared_vs_actual(led.pin(pin_id), files)


def agent_ready(ledger: str, pin_id: str = "") -> dict:
    import agentready
    led = _open_existing(ledger)
    return agentready.card(led, pin_id) if pin_id else agentready.gate(led)


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
    # Wrapped under a key, not returned bare: MCP's `structuredContent` is an object, so a tool that
    # hands back the engine's `list[dict]` is rejected on the wire before the agent sees a thing —
    # even at zero drift, where the list is empty. `findings_gate` already answers under that key,
    # and a named key leaves room to say more later without breaking a caller that reads
    # `["findings"]`.
    import shapes
    findings = shapes.drift_check(contract, backend=backend, **{k: v for k, v in layers.items() if v})
    return {"findings": findings}


def reconcile_layers(layer_a: str, path_a: str, layer_b: str, path_b: str) -> dict:
    import shapes
    return {"findings": shapes.reconcile_layers(layer_a, path_a, layer_b, path_b)}


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


def spend_report(project: str = "", session: str = "", pricing: str = "",
                 declared_mcp: list | None = None) -> dict:
    import spend
    price = pricing or None
    if session:
        return spend.report_session(session, pricing=price, declared_mcp=declared_mcp)
    if project:
        return spend.report_project(project, pricing=price, declared_mcp=declared_mcp)
    raise ValueError(
        "spend_report needs `session` (a transcript .jsonl) or `project` (a repo dir, to discover "
        "this host's session store)")


def design_scan(paths: list, scope: str = "", viewport: str = "", no_advisory: bool = False) -> dict:
    import design
    return design.scan(paths, scope=scope or None, viewport=viewport, no_advisory=no_advisory)


def generate_tokens(contract: str, out: str) -> dict:
    import design_tokens as DT
    ts = DT.TokenSet.load(contract)
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    files = {"tokens.css": DT.to_css_vars(ts), "theme.css": DT.to_tailwind(ts),
             "DESIGN.md": DT.to_design_md(ts)}
    written = {}
    for name, text in files.items():
        p = outdir / name
        p.write_text(text, encoding="utf-8", newline="\n")
        written[name] = str(p)
    return {"written": written}


def tokens_diff(contract: str, css: str) -> dict:
    import design_tokens as DT
    ts = DT.TokenSet.load(contract)
    p = Path(css)
    text = p.read_text(encoding="utf-8") if p.exists() else css
    return DT.drift_check(ts, text)


def extract_tokens(css: str) -> dict:
    import design_tokens as DT
    p = Path(css)
    text = p.read_text(encoding="utf-8") if p.exists() else css
    return {"candidate": DT.harvest_tokens(text)}


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


def docs_claims(graph_path: str, docs: list | None = None, draft: str = "",
                mode: str = "audit") -> dict:
    """Audit docs that exist, or gate a draft before publishing. One engine, two directions —
    two tools would have been two descriptions for one idea."""
    import docs_claims as DC
    data = DC.load(graph_path)
    if mode == "audit":
        return DC.analyze(list(docs or []), data)
    if not draft and docs:
        draft = Path(docs[0]).read_text(encoding="utf-8", errors="replace")
    if not draft:
        raise RuntimeError("publishing modes need `draft` text, or a `docs` path to read it from")
    pub_mode = "prospective" if mode == "publish_prospective" else "descriptive"
    return DC.publication_gate(draft, data, source=(docs or ["<draft>"])[0], mode=pub_mode)


def _agents_md(root: str) -> Path:
    return Path(root) / "AGENTS.md"


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _instructions_render(ledger: str, root: str, max_lines: int, generated: list | None):
    """Shared by the generate/diff pair so the two can never disagree about what the region SHOULD be
    — the same failure mode as a linter that reimplements its formatter. That sharing is also what
    makes the generated-file recovery below correct in both: ask the same question, get the same
    answer.

    `generated=None` means "keep whatever the region already records" — recovered from the region
    itself, so a regeneration triggered by anything else (a pin decided, a policy added) cannot
    silently drop the never-hand-edit list. `[]` clears it, explicitly.
    """
    import instructions as INS
    led = _open_existing(ledger)
    if generated is None:
        generated = INS.extract_generated(_read(_agents_md(root)))
    try:
        rel = str(Path(ledger).resolve().relative_to(Path(root).resolve()))
    except ValueError:                      # ledger outside the project root — name it as given
        rel = ledger
    return INS, INS.render(led.data, max_lines=max_lines or INS.MAX_LINES,
                           ledger_path=rel.replace("\\", "/"), generated=generated), generated


def generate_instructions(ledger: str, root: str = ".", generated: list | None = None,
                          generated_from: str = "", generated_by: str = "",
                          max_lines: int = 0, bridge: bool = True) -> dict:
    INS, body, effective = _instructions_render(ledger, root, max_lines, generated)
    base = Path(root)
    agents = _agents_md(root)
    agents.parent.mkdir(parents=True, exist_ok=True)
    agents.write_text(INS.apply(_read(agents), body), encoding="utf-8", newline="\n")
    written = {"agents_md": str(agents)}

    if bridge:
        claude = base / "CLAUDE.md"
        bridged = INS.claude_bridge(_read(claude))
        if bridged is not None:
            claude.write_text(bridged, encoding="utf-8", newline="\n")
            written["claude_md"] = str(claude)

    # The Claude-only rule is a projection of the SAME list the region carries, so it is rewritten
    # and removed in lockstep with it. Letting it outlive an emptied list would leave two carriers
    # of one fact disagreeing — the drift this module exists to make impossible.
    rule = base / ".claude" / "rules" / "keel-generated-files.md"
    if effective:
        rule.parent.mkdir(parents=True, exist_ok=True)
        rule.write_text(
            INS.rule_generated_files(list(effective), generated_from or "the contract",
                                     generated_by or "generate_layers"),
            encoding="utf-8", newline="\n")
        written["claude_rule"] = str(rule)
    elif rule.is_file():
        rule.unlink()
        written["claude_rule_removed"] = str(rule)

    return {"written": written, "region_lines": len(body.splitlines()),
            "generated": sorted(str(g) for g in effective)}


def instructions_diff(ledger: str, root: str = ".", generated: list | None = None,
                      max_lines: int = 0, bridge: bool = True) -> dict:
    INS, body, effective = _instructions_render(ledger, root, max_lines, generated)
    agents = _agents_md(root)
    out = INS.drift_check(_read(agents), body)
    ctext = _read(Path(root) / "CLAUDE.md")
    if not bridge:
        # The caller opted out of the bridge; reporting it "missing" would describe a deliberate
        # choice as a defect, and a status nobody can ever clear gets ignored on sight.
        out["claude_bridge"] = "not_requested"
    else:
        out["claude_bridge"] = "present" if (ctext and INS.claude_bridge(ctext) is None) else "missing"
    out["path"] = str(agents)
    out["generated"] = sorted(str(g) for g in effective)
    return out
