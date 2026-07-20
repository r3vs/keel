# GENERATED FILE - do not edit. Source: src/runtime/graphmap.py at the repo root;
# regenerate with: python scripts/build.py
"""Graph map — render a structural graph.json as one self-contained, navigable HTML page (study D).

The `understand` mode's visual surface. The study's lesson from Understand-Anything: a flat node-link
"hairball" stops being legible a few hundred nodes in, so the map is a **layered lens** — an overview
of one card per architectural layer, click to drill into that layer's files, click a file for its
neighbourhood (what it depends on / what depends on it). Colour is by layer and by node type; a
search box filters; a tour panel plays the dependency-ordered steps; and an Export SVG button emits a
hand-rolled, dependency-free diagram of the layers and their couplings.

Same discipline as `map.py`: one self-contained file (data + CSS + JS inlined, **no external fetch**),
script-safe, holding no state of its own — it projects the graph. All adjacency is precomputed in
Python so the client stays simple. Reuses `graph.Graph` for neighbourhoods. Stdlib-only.
"""
from __future__ import annotations

import html
import json
import pathlib
from typing import Optional

import graph as graphmod

# a small, fixed palette indexed by layer order — legible, theme-neutral, no dependency
_LAYER_COLORS = ["#4f8cc9", "#c97b4f", "#6aa84f", "#a64fc9", "#c9a24f", "#4fc9b0", "#c94f6a", "#7a7f8c"]
_TYPE_COLORS = {"file": "#8892a6", "class": "#a64fc9", "function": "#4f8cc9",
                "method": "#6aa84f", "module": "#c9a24f"}


def build_view(data: dict, tour: Optional[dict] = None) -> dict:
    """Precompute the view model the page renders: layers → files, per-node neighbourhood, and the
    inter-layer coupling counts. Deterministic (sorted throughout)."""
    g = graphmod.Graph(data)

    layer_files: dict[str, list[dict]] = {}
    node_layer: dict[str, str] = {}
    for nid, node in g.nodes.items():
        node_layer[nid] = str(node.get("layer") or "root")
    for nid in sorted(g.nodes):
        node = g.nodes[nid]
        lyr = node_layer[nid]
        layer_files.setdefault(lyr, [])
        # symbols live under their file in the drill-down; files anchor the layer card
        if node.get("type") == "file":
            deps = [g.node_loc(x) or g.node_name(x) or x for x in g.dependencies(nid, 1)]
            dependents = [g.node_loc(x) or g.node_name(x) or x for x in g.blast_radius(nid, 1)]
            layer_files[lyr].append({
                "id": nid, "name": node.get("name") or nid, "type": "file",
                "loc": g.node_loc(nid), "language": node.get("language"),
                "symbols": sorted(g.node_name(x) or x for x in g.dependencies(nid, 1, edge_types=["contains"])),
                "depends_on": sorted(set(deps))[:20],
                "depended_on_by": sorted(set(dependents))[:20],
            })

    # inter-layer coupling from import edges (file → file)
    coupling: dict[tuple, int] = {}
    for s, t, et, _c in g.edges:
        if et != "imports":
            continue
        a, b = node_layer.get(s), node_layer.get(t)
        if a and b and a != b:
            coupling[(a, b)] = coupling.get((a, b), 0) + 1

    layers = []
    for i, name in enumerate(sorted(layer_files)):
        files = sorted(layer_files[name], key=lambda f: f["name"])
        layers.append({"name": name, "color": _LAYER_COLORS[i % len(_LAYER_COLORS)],
                       "files": files, "count": len(files)})

    tour_steps = []
    if tour:
        for s in tour.get("steps", []):
            tour_steps.append({"order": s.get("order", 0), "title": s.get("title", ""),
                               "layer": s.get("layer"), "files": s.get("files", [])})

    return {
        "layers": layers,
        "coupling": [{"from": a, "to": b, "count": n}
                     for (a, b), n in sorted(coupling.items())],
        "tour": tour_steps,
        "type_colors": _TYPE_COLORS,
        "stats": {"files": sum(l["count"] for l in layers), "layers": len(layers),
                  "built_at_commit": (data.get("graph") or {}).get("built_at_commit")},
    }


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;background:#fafafa}
@media(prefers-color-scheme:dark){body{color:#e8e8e8;background:#141416}.card,.panel,.step{background:#1e1e22!important;border-color:#33343a!important}header{background:#1a1a1e!important}input{background:#26262c!important;color:#e8e8e8!important;border-color:#3a3a42!important}}
header{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #e2e2e2;padding:10px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
header b{font-size:15px}
.muted{color:#8a8a8a;font-size:12px}
input{padding:6px 10px;border:1px solid #d5d5d5;border-radius:6px;font-size:13px;min-width:200px}
button{padding:6px 10px;border:1px solid #d5d5d5;border-radius:6px;background:transparent;color:inherit;cursor:pointer;font-size:13px}
button:hover{border-color:#999}
main{display:grid;grid-template-columns:1fr minmax(280px,360px);gap:0;min-height:calc(100vh - 54px)}
@media(max-width:760px){main{grid-template-columns:1fr}}
#board{padding:16px;display:flex;flex-wrap:wrap;gap:12px;align-content:flex-start}
.card{border:1px solid #e2e2e2;border-radius:10px;background:#fff;min-width:200px;max-width:320px;overflow:hidden}
.card>.head{padding:8px 12px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px;border-left:5px solid var(--c)}
.card>.head:hover{background:rgba(127,127,127,.06)}
.card .files{display:none;border-top:1px solid #ededed;max-height:340px;overflow:auto}
.card.open .files{display:block}
.file{padding:5px 12px 5px 16px;cursor:pointer;display:flex;gap:7px;align-items:center;border-top:1px solid #f3f3f3;font-size:13px}
.file:hover{background:rgba(127,127,127,.06)}
.dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
.count{font-size:12px;color:#8a8a8a}
.panel{border-left:1px solid #e2e2e2;padding:14px 16px;overflow:auto}
.panel h3{margin:.2em 0 .1em;font-size:15px;word-break:break-all}
.panel .k{color:#8a8a8a;font-size:12px;margin-top:10px;text-transform:uppercase;letter-spacing:.04em}
.panel li{font-size:13px;word-break:break-all}
.hidden{display:none!important}
.step{border:1px solid #e6e6e6;border-radius:8px;padding:7px 10px;margin:6px 0;cursor:pointer;font-size:13px}
.step:hover{border-color:#aaa}
.hl{outline:2px solid #f0a500;outline-offset:1px}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:#8a8a8a;padding:0 16px 8px}
.legend span{display:inline-flex;gap:5px;align-items:center}
</style></head>
<body>
<header>
  <b>__TITLE__</b>
  <span class="muted" id="stats"></span>
  <input id="q" placeholder="search files…" autocomplete="off">
  <button onclick="toggleAll(true)">expand all</button>
  <button onclick="toggleAll(false)">collapse</button>
  <button onclick="exportSvg()">export SVG</button>
</header>
<div class="legend" id="legend"></div>
<main>
  <div id="board"></div>
  <div class="panel">
    <div id="detail"><p class="muted">Select a layer, then a file — or play the tour below.</p></div>
    <div id="tour"></div>
  </div>
</main>
<script>
const VIEW = __DATA__;
const board=document.getElementById('board'), detail=document.getElementById('detail');
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tc=t=>VIEW.type_colors[t]||'#8892a6';
let FILES={};

function render(){
  document.getElementById('stats').textContent=
    `${VIEW.stats.files} files · ${VIEW.stats.layers} layers`+(VIEW.stats.built_at_commit?` · @${VIEW.stats.built_at_commit}`:'');
  document.getElementById('legend').innerHTML=Object.entries(VIEW.type_colors)
    .map(([t,c])=>`<span><i class="dot" style="background:${c}"></i>${t}</span>`).join('');
  board.innerHTML=VIEW.layers.map((L,li)=>`
    <div class="card" data-layer="${esc(L.name)}" style="--c:${L.color}">
      <div class="head" onclick="toggle(${li})">
        <span><b>${esc(L.name)}</b></span><span class="count">${L.count} file${L.count===1?'':'s'}</span>
      </div>
      <div class="files">${L.files.map(f=>{FILES[f.id]=f;return `
        <div class="file" data-id="${esc(f.id)}" data-name="${esc(f.name).toLowerCase()}" onclick="pick('${esc(f.id)}')">
          <i class="dot" style="background:${tc(f.type)}"></i><span>${esc(f.name)}</span>
        </div>`}).join('')}</div>
    </div>`).join('');
  const t=VIEW.tour||[];
  document.getElementById('tour').innerHTML = t.length? `<div class="k">Guided tour</div>`+
    t.map((s,i)=>`<div class="step" onclick="playStep(${i})"><b>${s.order+1}. ${esc(s.title)}</b>
      <div class="muted">${s.files.length} file(s)</div></div>`).join('') : '';
}
function toggle(i){board.children[i].classList.toggle('open');}
function toggleAll(open){[...board.children].forEach(c=>c.classList.toggle('open',open));}
function pick(id){
  const f=FILES[id]; if(!f)return;
  [...document.querySelectorAll('.file')].forEach(e=>e.classList.toggle('hl',e.dataset.id===id));
  const list=a=>a&&a.length?`<ul>${a.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p class="muted">none</p>';
  detail.innerHTML=`<h3>${esc(f.name)}</h3>
    <div class="muted">${esc(f.type)} · ${esc(f.loc||'')}${f.language?' · '+esc(f.language):''}</div>
    <div class="k">Defined here</div>${list(f.symbols)}
    <div class="k">Depends on</div>${list(f.depends_on)}
    <div class="k">Depended on by</div>${list(f.depended_on_by)}`;
}
function playStep(i){
  const s=VIEW.tour[i]; const names=new Set(s.files);
  VIEW.layers.forEach((L,li)=>{ if(L.name===s.layer) board.children[li].classList.add('open'); });
  [...document.querySelectorAll('.file')].forEach(e=>{
    const f=FILES[e.dataset.id]; e.classList.toggle('hl', f && names.has(f.loc||f.name));
  });
  const first=[...document.querySelectorAll('.file.hl')][0]; if(first)first.scrollIntoView({block:'center'});
}
document.getElementById('q').addEventListener('input',e=>{
  const q=e.target.value.trim().toLowerCase();
  [...document.querySelectorAll('.card')].forEach(card=>{
    let any=false;
    [...card.querySelectorAll('.file')].forEach(fl=>{
      const hit=!q||fl.dataset.name.includes(q); fl.classList.toggle('hidden',!hit); any=any||hit;
    });
    card.classList.toggle('hidden',!any); if(q&&any)card.classList.add('open');
  });
});
function exportSvg(){
  const L=VIEW.layers, pad=20, bw=200, bh=46, gap=26, W=bw+pad*2, H=pad*2+L.length*(bh+gap);
  let s=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${Math.max(H,80)}" font-family="sans-serif" font-size="13">`;
  const y=i=>pad+i*(bh+gap);
  L.forEach((l,i)=>{ s+=`<rect x="${pad}" y="${y(i)}" width="${bw}" height="${bh}" rx="8" fill="${l.color}" opacity="0.9"/>`+
    `<text x="${pad+12}" y="${y(i)+20}" fill="#fff">${esc(l.name)}</text>`+
    `<text x="${pad+12}" y="${y(i)+37}" fill="#fff" opacity="0.85">${l.count} files</text>`; });
  const idx=Object.fromEntries(L.map((l,i)=>[l.name,i]));
  (VIEW.coupling||[]).forEach(c=>{ const a=idx[c.from],b=idx[c.to]; if(a==null||b==null)return;
    s+=`<line x1="${pad+bw}" y1="${y(a)+bh/2}" x2="${pad+bw+14}" y2="${y(a)+bh/2}" stroke="#999"/>`;
  });
  s+='</svg>';
  const a=document.createElement('a');
  a.href='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(s);
  a.download='graph-map.svg'; a.click();
}
render();
</script></body></html>
"""


def render(data: dict, tour: Optional[dict] = None, title: str = "") -> str:
    view = build_view(data, tour)
    payload = json.dumps(view, ensure_ascii=False).replace("</", "<\\/")  # script-safe
    return (_TEMPLATE.replace("__DATA__", payload)
            .replace("__TITLE__", html.escape(title or "codebase map")))


def render_file(graph_path: str | pathlib.Path, out_path: str | pathlib.Path,
                tour_path: Optional[str | pathlib.Path] = None) -> pathlib.Path:
    data = json.loads(pathlib.Path(graph_path).read_text(encoding="utf-8"))
    tour = json.loads(pathlib.Path(tour_path).read_text(encoding="utf-8")) if tour_path else None
    out = pathlib.Path(out_path)
    out.write_text(render(data, tour, title=out.stem), encoding="utf-8", newline="\n")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Render a structural graph.json as one self-contained, navigable HTML map "
                    "(layered lens: layers → files → neighbourhood). The understand-mode visual.")
    parser.add_argument("graph", help="path to graph.json (from scripts/runtime/graph_build.py)")
    parser.add_argument("-o", "--out", default="graph-map.html")
    parser.add_argument("--tour", help="optional tour.json to drive the tour panel")
    parser.add_argument("--title", default="")
    args = parser.parse_args(argv)

    data = json.loads(pathlib.Path(args.graph).read_text(encoding="utf-8"))
    tour = json.loads(pathlib.Path(args.tour).read_text(encoding="utf-8")) if args.tour else None
    pathlib.Path(args.out).write_text(render(data, tour, title=args.title or pathlib.Path(args.out).stem),
                                      encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
