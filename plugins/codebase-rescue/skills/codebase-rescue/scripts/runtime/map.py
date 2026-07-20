# GENERATED FILE - do not edit. Source: src/runtime/map.py at the repo root;
# regenerate with: python scripts/build.py
"""Visual map — render a ledger.json as one self-contained HTML page.

The map/wiki is one of the ledger's three surfaces and holds no state of its own: it *projects*
a view over `ledger.json` (`core/ledger.md`). This renderer is deliberately the lightest thing
that works (ponytail: build vs wrap CodeWiki → build a zero-dependency single file): no build
step, no framework, no external fetch — the ledger data is inlined and all CSS/JS is embedded, so
the output opens offline and is safe to hand to anyone.

It is **shared by both skills** with an as-is/to-be toggle (the open "fork rescue's map vs share
one" decision, resolved: share one). Rescue's pins render their `as_is` (extracted from code) as
the default view; greenfield's `open_decision`/`acceptance_criterion` pins render `to_be` (the
elected design) — the toggle flips which side leads. `contract_mismatch` pins get the three-column
cross-layer diff panel; every pin links its interview question; a completeness traffic-light sums
the states.

CLI: `python runtime/map.py path/to/ledger.json -o map.html`
"""
from __future__ import annotations

import html
import json
import pathlib
from typing import Optional

_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decisions map — __TITLE__</title>
<style>
:root{--bg:#fbfbfd;--fg:#1c1c1e;--mut:#6b6b70;--card:#fff;--line:#e3e3e8;--accent:#4c6ef5;
--blocker:#e03131;--high:#f08c00;--medium:#1971c2;--low:#868e96;--ok:#2f9e44}
@media(prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececf1;--mut:#9a9aa2;--card:#1f1f23;
--line:#303036;--accent:#748ffc}}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--fg)}
header{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:18px;flex-wrap:wrap}
h1{font-size:16px;margin:0;font-weight:650}
.light{display:flex;gap:8px;align-items:center;font-size:13px;color:var(--mut)}
.dot{width:11px;height:11px;border-radius:50%}
.bar{flex:1;min-width:120px;height:8px;border-radius:4px;background:var(--line);overflow:hidden;max-width:260px}
.bar>i{display:block;height:100%;background:var(--ok)}
.toggle{margin-left:auto;display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.toggle button{border:0;background:var(--card);color:var(--mut);padding:6px 12px;cursor:pointer;font:inherit}
.toggle button.on{background:var(--accent);color:#fff}
main{display:grid;grid-template-columns:minmax(260px,340px) 1fr;gap:0;min-height:calc(100vh - 62px)}
@media(max-width:720px){main{grid-template-columns:1fr}}
.list{border-right:1px solid var(--line);overflow-y:auto;max-height:calc(100vh - 62px)}
.pin{padding:11px 16px;border-bottom:1px solid var(--line);cursor:pointer}
.pin:hover{background:var(--card)}.pin.sel{background:var(--card);box-shadow:inset 3px 0 0 var(--accent)}
.pin .t{font-weight:600;margin-bottom:3px}.pin .m{font-size:12px;color:var(--mut);display:flex;gap:8px;flex-wrap:wrap}
.sev{padding:1px 7px;border-radius:20px;color:#fff;font-size:11px;font-weight:600}
.detail{padding:22px 26px;overflow-y:auto;max-height:calc(100vh - 62px)}
.detail h2{font-size:18px;margin:0 0 4px}.detail .sub{color:var(--mut);margin-bottom:18px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.col{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.col.dis{border-color:var(--high)}.col h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
.col code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-word}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0}
.q{border-left:3px solid var(--accent)}
.opt{padding:8px 10px;border:1px solid var(--line);border-radius:8px;margin:6px 0}
.opt b{font-weight:600}.opt .imp{color:var(--mut);font-size:12px}
.anchors code{display:block;font:12px ui-monospace,monospace;color:var(--mut);padding:2px 0}
.anchors .nid{color:var(--accent);font-weight:600}
.imp{color:var(--high);font-size:12px;padding:0 0 4px 0}
.kv{display:flex;gap:8px;font-size:13px;margin:3px 0}.kv b{color:var(--mut);min-width:88px}
.empty{color:var(--mut);padding:40px;text-align:center}
</style></head><body>
<header>
  <h1>🧭 Decisions map</h1>
  <div class="light"><span class="dot" id="tl"></span><span id="tltext"></span>
    <span class="bar"><i id="prog"></i></span></div>
  <div class="toggle"><button id="bAsis" class="on" onclick="setView('as_is')">as-is</button>
    <button id="bTobe" onclick="setView('to_be')">to-be</button></div>
</header>
<main><div class="list" id="list"></div><div class="detail" id="detail"></div></main>
<script>
const LEDGER = __DATA__;
const SEV = {blocker:'var(--blocker)',high:'var(--high)',medium:'var(--medium)',low:'var(--low)'};
const DONE = new Set(['decided','resolved','accepted']);
let view='as_is', sel=null;
const esc = s => (s==null?'':String(s));

function trafficLight(){
  const pins=LEDGER.pins||[]; const done=pins.filter(p=>DONE.has(p.state)).length;
  const openBlockers=pins.filter(p=>!DONE.has(p.state)&&(p.severity==='blocker')).length;
  const pct=pins.length?Math.round(100*done/pins.length):100;
  document.getElementById('prog').style.width=pct+'%';
  const tl=document.getElementById('tl'); const txt=document.getElementById('tltext');
  if(openBlockers>0){tl.style.background='var(--blocker)';txt.textContent=openBlockers+' open blocker(s) · '+pct+'% resolved';}
  else if(pct<100){tl.style.background='var(--high)';txt.textContent=pct+'% resolved';}
  else{tl.style.background='var(--ok)';txt.textContent='all resolved';}
}
function renderList(){
  const el=document.getElementById('list'); const pins=LEDGER.pins||[];
  if(!pins.length){el.innerHTML='<div class="empty">empty ledger</div>';return;}
  el.innerHTML=pins.map((p,i)=>`<div class="pin${i===sel?' sel':''}" onclick="select(${i})">
    <div class="t">${esc(p.title)}</div>
    <div class="m"><span class="sev" style="background:${SEV[p.severity]||'#888'}">${p.severity}</span>
    <span>${esc(p.kind)}</span><span>· ${esc(p.state)}</span></div></div>`).join('');
}
function contractCols(p){
  const a=p.as_is||{}; const dis=new Set(a.disagreeing_layers||[]);
  const layers=Object.keys(a).filter(k=>k!=='disagreeing_layers');
  if(!layers.length)return '';
  return `<div class="cols">`+layers.map(l=>`<div class="col${dis.has(l)?' dis':''}">
    <h4>${esc(l)}${dis.has(l)?' ⚠':''}</h4><code>${esc(a[l])}</code></div>`).join('')+`</div>`;
}
function detail(p){
  if(!p)return '<div class="empty">select a pin</div>';
  const side=p[view]; let body='';
  if(p.kind==='contract_mismatch'&&view==='as_is') body+=contractCols(p);
  else if(side) body+=`<div class="card"><b>${view}</b><pre style="white-space:pre-wrap;margin:8px 0 0">${esc(JSON.stringify(side,null,2))}</pre></div>`;
  else body+=`<div class="card" style="color:var(--mut)">no ${view} yet</div>`;
  if(p.question) body+=`<div class="card q"><b>Interview question</b><p>${esc(p.question.prompt)}</p>`+
    (p.question.options||[]).map(o=>`<div class="opt"><b>${esc(o.label)}</b>${o.implication?`<div class="imp">→ ${esc(o.implication)}</div>`:''}</div>`).join('')+`</div>`;
  if((p.anchors||[]).length) body+=`<div class="card anchors"><b>Anchors</b>`+
    p.anchors.map(a=>{
      const nid=a.node_id?` <span class="nid">${esc(a.node_id)}</span>`:'';
      let br='';
      if(a.blast_radius&&a.blast_radius.count){
        const s=(a.blast_radius.sample||[]).map(esc).join(', ');
        br=`<div class="imp">↯ impact: ${a.blast_radius.count} dependent(s)`+(s?` — ${s}`:'')+`</div>`;
      }
      return `<code>${esc(a.layer||'')} ${esc(a.loc||a.node_id||'')}${nid}</code>${br}`;
    }).join('')+`</div>`;
  if(p.decision) body+=`<div class="card"><div class="kv"><b>decided</b><span>${esc(p.decision.outcome)}</span></div></div>`;
  return `<h2>${esc(p.title)}</h2><div class="sub"><span class="sev" style="background:${SEV[p.severity]||'#888'}">${p.severity}</span> · ${esc(p.kind)} · ${esc(p.state)}${p.substate?' ('+esc(p.substate)+')':''}</div>`+body;
}
function select(i){sel=i;renderList();document.getElementById('detail').innerHTML=detail((LEDGER.pins||[])[i]);}
function setView(v){view=v;document.getElementById('bAsis').classList.toggle('on',v==='as_is');
  document.getElementById('bTobe').classList.toggle('on',v==='to_be');
  if(sel!=null)document.getElementById('detail').innerHTML=detail(LEDGER.pins[sel]);}
trafficLight();renderList();
if((LEDGER.pins||[]).length)select(0);else document.getElementById('detail').innerHTML=detail(null);
</script></body></html>
"""


def render(ledger_data: dict, title: str = "") -> str:
    data = json.dumps(ledger_data, ensure_ascii=False).replace("</", "<\\/")  # script-safe
    return (_TEMPLATE
            .replace("__DATA__", data)
            .replace("__TITLE__", html.escape(title or "ledger")))


def render_file(ledger_path: str | pathlib.Path, out_path: str | pathlib.Path) -> pathlib.Path:
    data = json.loads(pathlib.Path(ledger_path).read_text(encoding="utf-8"))
    out = pathlib.Path(out_path)
    out.write_text(render(data, title=str(pathlib.Path(ledger_path).stem)),
                   encoding="utf-8", newline="\n")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Render a ledger.json as a self-contained HTML map")
    parser.add_argument("ledger", help="path to ledger.json")
    parser.add_argument("-o", "--out", default="map.html")
    args = parser.parse_args(argv)
    out = render_file(args.ledger, args.out)
    pins = len(json.loads(pathlib.Path(args.ledger).read_text(encoding="utf-8")).get("pins", []))
    print(f"wrote {out} ({pins} pins)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
