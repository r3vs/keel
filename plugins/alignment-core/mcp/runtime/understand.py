"""`understand` mode entrypoint — comprehension as an end, in one command.

Ties the pieces the study recommends into the deliverable the `understand` mode promises: build the
structural graph (`graph_build`), compute a layered overview (what the system is made of, where the
weight sits), and generate a dependency-ordered tour (`tours`) — then write the bundle to disk so
the map, the query surface (`query`), and the explain drill-down (`explain`) all read one artifact.

It stops at the **as-is**: it never elects a `to_be`, never opens the interview, never proposes a
fix. That boundary is what lets comprehension be terminal here without the engine becoming a second
product. Stdlib-only; every heavy artifact is persisted (the phases-communicate-through-disk rule).
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

import graph as graphmod
import graph_build
import graphmap
import tours as toursmod


def _indeg_over(data: dict, types: tuple[str, ...]) -> dict[str, int]:
    """In-degree per node over edges of the given types = 'how depended-upon'. Deterministic."""
    deg: dict[str, int] = {}
    edges = data.get("links")
    if edges is None:
        edges = data.get("edges") or []
    for e in edges:
        if str(e.get("type") or "").lower() in types:
            t = str(e.get("target"))
            deg[t] = deg.get(t, 0) + 1
    return deg


def overview(data: dict, *, hotspots: int = 10) -> dict:
    """A layered summary of the as-is: language + layer census, entry points, and the hotspots
    (the most-depended-upon nodes — where a change ripples widest, i.e. what to understand first)."""
    g = graphmod.Graph(data)
    files = [n for n in data.get("nodes", []) if n.get("type") == "file"]
    langs: dict[str, int] = {}
    layers: dict[str, int] = {}
    for n in files:
        langs[n.get("language") or "text"] = langs.get(n.get("language") or "text", 0) + 1
        layers[n.get("layer") or "root"] = layers.get(n.get("layer") or "root", 0) + 1

    indeg = _indeg_over(data, ("imports", "calls", "references"))
    ranked = sorted(indeg.items(), key=lambda kv: (-kv[1], kv[0]))
    hot = [{"name": g.node_name(nid) or nid, "loc": g.node_loc(nid),
            "type": (g.nodes.get(nid) or {}).get("type"), "dependents": cnt}
           for nid, cnt in ranked[:hotspots] if nid in g.nodes]

    return {
        "files": len(files),
        "symbols": sum(1 for n in data.get("nodes", []) if n.get("type") != "file"),
        "edges": len(data.get("links") or data.get("edges") or []),
        "languages": dict(sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))),
        "layers": dict(sorted(layers.items(), key=lambda kv: (-kv[1], kv[0]))),
        "hotspots": hot,
        "built_at_commit": (data.get("graph") or {}).get("built_at_commit"),
    }


def understand(root: str | pathlib.Path, *, commit: Optional[str] = None) -> dict:
    """Build the full comprehension bundle for `root`: `{graph, overview, tour}`. Pure as-is."""
    data = graph_build.build_graph(root, commit=commit)
    return {"graph": data, "overview": overview(data), "tour": toursmod.build_tour(data)}


def write_bundle(bundle: dict, out_dir: str | pathlib.Path) -> dict:
    """Persist the bundle (graph.json, overview.json, tour.json) → paths. Phases talk through disk."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, name in (("graph", "graph.json"), ("overview", "overview.json"), ("tour", "tour.json")):
        p = out / name
        p.write_text(json.dumps(bundle[key], ensure_ascii=False, indent=2),
                     encoding="utf-8", newline="\n")
        paths[key] = str(p)
    # the navigable, self-contained HTML map (layered lens) — the mode's visual deliverable
    map_path = out / "graph-map.html"
    map_path.write_text(graphmap.render(bundle["graph"], bundle["tour"], title="codebase map"),
                        encoding="utf-8", newline="\n")
    paths["map"] = str(map_path)
    return paths


def _render_text(bundle: dict) -> str:
    ov, tour = bundle["overview"], bundle["tour"]
    lines = [
        "Understand — as-is comprehension (no interview, no remediation).",
        f"  {ov['files']} files · {ov['symbols']} symbols · {ov['edges']} edges"
        + (f" · built at {ov['built_at_commit']}" if ov.get("built_at_commit") else ""),
        f"  languages: {', '.join(f'{k}×{v}' for k, v in ov['languages'].items())}",
        f"  layers:    {', '.join(f'{k}×{v}' for k, v in ov['layers'].items())}",
        "",
        "Hotspots (most depended-upon — understand these first):",
    ]
    for h in ov["hotspots"]:
        loc = f"  [{h['loc']}]" if h.get("loc") else ""
        lines.append(f"  - {h['name']} ({h['type']}) — {h['dependents']} dependents{loc}")
    lines += ["", f"Guided tour: {tour['stats']['steps']} steps across "
              f"{tour['stats']['layers']} layers; entry points: "
              f"{', '.join(tour['entry_points']) or '(none detected)'}"]
    for s in tour["steps"]:
        lines.append(f"  {s['order'] + 1}. {s['title']} — {len(s['files'])} file(s)")
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the understand mode over a repo: build the structural graph, a layered "
                    "overview, and a guided tour — comprehension as the deliverable. Pure as-is.")
    parser.add_argument("root", nargs="?", default=".", help="repo root (default: .)")
    parser.add_argument("-o", "--out", help="write the bundle here (e.g. .understand/)")
    parser.add_argument("--commit", help="override built_at_commit (default: git HEAD)")
    parser.add_argument("--json", action="store_true", help="emit the whole bundle as JSON")
    args = parser.parse_args(argv)

    bundle = understand(args.root, commit=args.commit)
    if args.out:
        paths = write_bundle(bundle, args.out)
        if not args.json:
            print(f"wrote: {', '.join(paths.values())}\n")
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        print(_render_text(bundle), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
