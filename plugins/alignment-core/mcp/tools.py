"""The MCP tool bodies — stdlib only, importable without FastMCP, testable in plain CI.

The split here is the repo's own pattern, the one `treesitter_extract.py` already follows: **the
engine stays pure, the adapter carries the dependency.** `server.py` is the FastMCP adapter and
pulls a ~77-package tree; this module is the part that is actually ours, so it holds no MCP
concepts at all and its tests need nothing installed.

It also survives the thing that killed the first attempt: MCP's 2026-07-28 revision drops the
`initialize` handshake, mandates `server/discover`, and requires `resultType` on every result. Not
one line in this file knows or cares — the protocol churn lands entirely on the adapter, where a
version bump absorbs it.

Every function calls the runtime's *library* API rather than its `main()` entry points, which print
to stdout. Under stdio transport stdout is the wire, so a stray print corrupts the session.
"""
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


def render_map(ledger: str, out: str) -> dict:
    import map as M
    _open_existing(ledger)  # refuse to render a map of a ledger that isn't there
    M.render_file(ledger, out)
    return {"written": out}
