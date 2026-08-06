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
the states. **An elected `Policy` is a decision and leads the list in its own right** (v0.15): it
used to be reachable only by joining backward from a pin a cascade had decided, so a rule the human
elected that bound no pin — held back by the severity threshold, or offered by no pin's question —
was on this page nowhere, while `ledger_summary` counted it and the projected `AGENTS.md` listed it
under "Standing rules". Its card carries the rule, the scope, the `default_outcome` the user
accepted, the rung it was elected on, the quote, and the decisions that name it. A decided pin
states **how the human's answer got there** (`evidence`, spec v0.10) and
shows the quote when an agent relayed it — the spec allows the weak rung only because it is made
visible, and this is the surface people actually read. A pin decided by a policy cascade
(`cascaded`, v0.11) shows the `Policy` it derives from and how *that* was elected, joined on the
event's `policy_id`: the human answered once, for a whole cluster, and the card says so instead of
reporting a relay that never happened. That rung binds writes, so for a ledger written before v0.11
the card reads it off the carrier the writer did leave (`derived_rungs` → `ledger.decision_rung`)
and states what the file records — the alternative was to keep printing *"relayed with no quote"*
over a policy the user elected, on every ledger that already exists.

Rendered by the `render_map` MCP tool (the runtime has no CLI — MCP is the one runtime channel).
Pass ``live=True`` for a dev-time monitor: the page self-reloads and re-projects the ledger as
pins land, preserving selection / view / scroll across reloads and flashing pins whose state
changed. The frozen default (``live=False``) stays a single offline file safe to hand to anyone —
so "live" is opt-in and never leaks into the shareable artifact. The re-projection on each ledger
mutation is driven by the MCP tool layer (`mcp/tools.py`), not a per-host hook.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
from typing import Optional

_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decisions map — __TITLE__</title>
<style>
:root{--bg:#fbfbfd;--fg:#1c1c1e;--mut:#6b6b70;--card:#fff;--line:#e3e3e8;--accent:#4c6ef5;
--code:#f1f1f5;--blocker:#e03131;--high:#f08c00;--medium:#1971c2;--low:#868e96;--ok:#2f9e44;
--warnbg:#fff7e6}
@media(prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececf1;--mut:#9a9aa2;--card:#1f1f23;
--line:#303036;--accent:#748ffc;--code:#2a2a31;--warnbg:#2e2413}}
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
.grp{padding:9px 16px 6px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--mut);font-weight:650;border-bottom:1px solid var(--line);background:var(--bg)}
.pol{padding:1px 7px;border-radius:20px;font-size:11px;font-weight:600;color:#fff;background:var(--accent)}
.lnk{color:var(--accent);cursor:pointer;text-decoration:underline}
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
.ch{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);font-weight:650;
  margin:0 0 12px}
dl.fields{display:grid;grid-template-columns:minmax(96px,168px) 1fr;gap:9px 16px;margin:0;align-items:baseline}
dl.fields dt{color:var(--mut);font-size:12px;font-weight:650;line-height:1.45;overflow-wrap:anywhere}
dl.fields dd{margin:0;overflow-wrap:anywhere;min-width:0}
dl.fields dl.fields{grid-column:1/-1;padding-left:12px;border-left:2px solid var(--line)}
@media(max-width:640px){dl.fields{grid-template-columns:1fr;gap:2px}
  dl.fields dd{margin:0 0 10px}dl.fields dl.fields{padding-left:10px}}
.fields code,.chips code{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
  background:var(--code);border-radius:5px;padding:1px 5px;overflow-wrap:anywhere}
.nul{color:var(--mut)}
.bool{font-size:11px;font-weight:650;padding:1px 8px;border-radius:20px;background:var(--line)}
.chips code{margin:0 4px 4px 0;display:inline-block}
.items{display:grid;gap:10px}
.items>.item{padding-left:12px;border-left:2px solid var(--line)}
.raw{margin-top:14px}
.raw summary{cursor:pointer;color:var(--mut);font-size:12px;list-style:none}
.raw summary::-webkit-details-marker{display:none}
.raw summary::before{content:"⌄";display:inline-block;margin-right:7px;transition:transform .15s}
.raw[open] summary::before{transform:rotate(180deg)}
.raw pre{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--mut);margin:8px 0 0;
  font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.dec{border-left:3px solid var(--ok)}
.dec.mid{border-left-color:var(--medium)}
.dec.weak{border-left-color:var(--high);background:var(--warnbg)}
.rung{font-size:11px;font-weight:650;padding:1px 8px;border-radius:20px;background:var(--line);color:var(--fg)}
.rung.strong{background:var(--ok);color:#fff}.rung.weak{background:var(--high);color:#fff}
.why{color:var(--mut);font-size:12px;margin-top:7px}
.warn{color:var(--high);font-size:12px;font-weight:600;margin-top:7px}
.quote{margin:9px 0 0;padding:5px 0 5px 12px;border-left:3px solid var(--line);font-style:italic;
  overflow-wrap:anywhere}
__LIVE_STYLE__</style></head><body>
<header>
  <h1>🧭 Decisions map</h1>__LIVE_BADGE__
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
let view='as_is', sel=null, selPol=null;
const ENT={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
// Named `esc` but, until now, only a String() cast — so every pin title, extracted layer shape and
// file path went into innerHTML raw. The ledger is written by agents reading someone else's code
// and this page is meant to be safe to hand to anyone; it escapes for real now.
const esc = s => (s==null?'':String(s)).replace(/[&<>"']/g, c=>ENT[c]);

// -- as_is / to_be ---------------------------------------------------------------------------
// The payload is free-form by design (`other` is an open escape hatch, and every kind's shape is
// constrained but never closed), so this walks the VALUE's structure, never its key names: object
// -> labelled rows, array -> items, scalar -> text. Key-driven rendering would be a guess about
// content the spec does not promise.
//
// The one content-driven choice is typographic and stays that: a string with no whitespace is an
// identifier, a path, a type or an enum, and reads as one in monospace; a string with whitespace is
// prose and reads as prose. Nothing is hidden either way — the raw JSON stays one click below,
// because a projection that quietly drops a field would be the divergence this package hunts.
function labelize(k){return String(k).replace(/[_-]+/g,' ').replace(/^./,c=>c.toUpperCase());}
function isScalar(v){return v===null||typeof v!=='object';}
function isBlank(v){
  return v===null||v===undefined||v===''||
    (typeof v==='object'&&!(Array.isArray(v)?v.length:Object.keys(v).length));
}
function scalarHTML(v){
  if(v===null||v===undefined||v==='') return '<span class="nul">—</span>';
  if(typeof v==='boolean') return `<span class="bool">${v?'yes':'no'}</span>`;
  if(typeof v==='number') return `<code>${esc(v)}</code>`;
  const s=String(v);
  return /\s/.test(s) ? esc(s) : `<code>${esc(s)}</code>`;
}
function valueHTML(v){
  if(isScalar(v)) return scalarHTML(v);
  if(Array.isArray(v)){
    if(!v.length) return '<span class="nul">none</span>';
    if(v.every(isScalar)) return `<span class="chips">${v.map(scalarHTML).join('')}</span>`;
    return `<div class="items">${v.map(x=>`<div class="item">${valueHTML(x)}</div>`).join('')}</div>`;
  }
  const keys=Object.keys(v);
  if(!keys.length) return '<span class="nul">—</span>';
  return `<dl class="fields">`+keys.map(k=>
    `<dt>${esc(labelize(k))}</dt><dd>${valueHTML(v[k])}</dd>`).join('')+`</dl>`;
}
function sideCard(side,label){
  return `<div class="card"><div class="ch">${esc(label)}</div>${valueHTML(side)}
    <details class="raw"><summary>raw</summary><pre>${esc(JSON.stringify(side,null,2))}</pre></details></div>`;
}

// -- how the human's answer reached the ledger (`evidence`, spec v0.10) -----------------------
// The spec permits the weak rung on the grounds that it is made VISIBLE — so it has to be visible
// HERE, on the surface people actually read, and it has to read as weaker rather than merely be
// present. `pin.decision` carries only {event_id, outcome}; the rung lives on the DecisionEvent, and
// the whole ledger is inlined, so this is a lookup in `decision_log` and never a fetch.
// Not a confidence score: every rung `DECISION_EVIDENCE` names has its own failure mode, and they
// are kept apart rather than blended (`test_map.py` holds this table against that tuple, so a rung
// added there cannot go missing here — which is the only kind of count worth writing down).
const RUNG={
  elicited:{label:'elicited', cls:'strong',
    why:'the server asked the user through the host and wrote the reply itself — the agent never held the value, so it could not have invented it'},
  brief:{label:'from the brief', cls:'mid',
    why:'settled in the project brief at frame time; the brief is the evidence'},
  transcribed:{label:'transcribed', cls:'weak',
    why:'an agent relayed what the user said — an honest relay and a fabricated one are the same line here, so what you weigh is the quote'},
  cascaded:{label:'cascaded from a policy', cls:'mid',
    why:'the user elected a policy and this pin fell under it — the answer was given once, for the cluster, so what you weigh is not invention but FIT: whether the rule suits this pin'}};
function policyById(id){
  if(!id)return null;
  const pols=LEDGER.policies||[];
  for(let i=0;i<pols.length;i++)if(pols[i]&&pols[i].id===id)return pols[i];
  return null;
}
function decisionEvent(id){
  if(!id)return null;
  const log=LEDGER.decision_log||[];
  for(let i=0;i<log.length;i++)if(log[i]&&log[i].id===id)return log[i];
  return null;
}
// hasOwnProperty, not `RUNG[r]`: the rung comes from a file agents write, and `constructor` would
// otherwise resolve to a function and render as a rung nobody defined.
function rungMeta(r){return Object.prototype.hasOwnProperty.call(RUNG,r)?RUNG[r]:null;}

// -- the Policy as its own decision (v0.15) ---------------------------------------------------
// A policy is an election the human made over a whole cluster, so it is a DECISION and this surface
// has to show it. Until now it could only be reached by joining BACKWARD from a cascaded pin, so a
// policy that cascaded over nothing — held back by the threshold, or offered by no pin's question —
// appeared on this page nowhere at all, while `ledger_summary` counted it and the projected
// AGENTS.md listed it under "Standing rules". Three surfaces, three answers about one elected rule.
function scopeText(P){
  const a=P.applies_to||{}, ks=Object.keys(a);
  return ks.length?ks.map(k=>esc(k)+'='+esc(a[k])).join(' · '):'every pin';
}
function policyRows(P){
  const pm=rungMeta(P.evidence?String(P.evidence):'');
  return `<div class="kv"><b>rule</b><span>${esc(P.rule)}</span></div>`
    +`<div class="kv"><b>applies to</b><span>${scopeText(P)}</span></div>`
    // the value the user accepted, which this card never showed: a reader could see WHICH rule
    // decided a pin and not what that rule writes.
    // `scalarHTML`, so a policy from a file that predates the field says "—" rather than rendering
    // an empty box that reads as an outcome nobody can see.
    +`<div class="kv"><b>decides</b><span>${scalarHTML(P.default_outcome)}</span></div>`
    +`<div class="kv"><b>elected</b><span class="rung ${pm?pm.cls:'weak'}">${esc(pm?pm.label:'no rung recorded')}</span></div>`
    +(P.human_answer?`<div class="quote">“${esc(P.human_answer)}”</div>`:'');
}
// One rule, two subjects: on a pin's card what rests on the policy is that pin and its cluster; on
// the policy's own card it is every decision that names it. Same test, stated to whoever is reading,
// so `rests` carries the whole clause rather than being assembled from a subject and a verb that
// only agree in one of the two calls.
function policyRungWarning(P,rests){
  if(!P.evidence)
    return `<div class="warn">⚠ the policy itself records no rung — how the user elected it is unknown, and ${rests}</div>`;
  if(!P.human_answer&&String(P.evidence)==='transcribed')
    return `<div class="warn">⚠ the policy itself was relayed with no quote — ${rests}</div>`;
  return '';
}
// The decisions a policy produced, joined on the event's own `policy_id` (or, for an event written
// before that field existed, the id `map.render` already took out of `source` — in Python, once).
function eventsOfPolicy(id){
  const out=[], log=LEDGER.decision_log||[];
  for(let i=0;i<log.length;i++){
    const e=log[i];
    if(!e||String(e.id||'').indexOf('ev_')!==0)continue;
    if((e.policy_id||derived(e).policy_id||'')===id)out.push(e);
  }
  return out;
}
function pinById(id){
  const ps=LEDGER.pins||[];
  for(let i=0;i<ps.length;i++)if(ps[i]&&ps[i].id===id)return {pin:ps[i],i:i};
  return null;
}
function policyDetail(P){
  if(!P)return '<div class="empty">select a rule</div>';
  const evs=eventsOfPolicy(P.id);
  let did;
  if(!evs.length)
    // Not a warning: an elected rule that bound no pin is a legitimate state, and it is exactly the
    // state that used to be invisible here. Say what the file records — no decision names it — and
    // no more; WHY it bound nothing (threshold, options, or no match) is not on the event.
    did=`<div class="why">no decision in this ledger names this rule: it cascaded over no pin. It
      stands as an elected rule for the work that follows — the projected <code>AGENTS.md</code>
      carries it under “Standing rules”.</div>`;
  else{
    // NOT `RUNG.cascaded.why`: that sentence is written to a reader looking at one pin ("this pin
    // fell under it"), and reusing it here would say the wrong thing about a rule that decided
    // several. Same fact, addressed to the reader who is actually here.
    did=`<div class="why">the human answered once, here, for the whole radius below — so what you
      weigh on each of these is not invention but FIT: whether this rule suits that pin.</div>`
      +`<div class="kv"><b>decided</b><span>${evs.length} pin(s)</span></div>`
      +evs.map(e=>{
        const f=pinById(e.pin_id);
        return f?`<div class="opt" onclick="select(${f.i})" style="cursor:pointer"><b>${esc(f.pin.title)}</b>
          <div class="imp">→ ${esc(e.outcome)}</div></div>`
          :`<div class="opt"><b>${esc(e.pin_id)}</b><div class="imp">this ledger holds no such pin</div></div>`;
      }).join('');
  }
  const exc=(P.exceptions||[]).length
    ? `<div class="kv"><b>exceptions</b><span class="chips">${P.exceptions.map(scalarHTML).join('')}</span></div>`
    : '';
  const pm=rungMeta(P.evidence?String(P.evidence):'');
  return `<h2>${esc(P.rule)}</h2>
    <div class="sub"><span class="pol">standing rule</span> · ${esc(P.id)} · elected by the ${esc(P.set_by||'interview')}</div>
    <div class="card dec ${pm?pm.cls:'weak'}">${policyRows(P)}${exc}
      ${policyRungWarning(P,'every decision that names it rests on that')}${did}</div>`;
}
// Events whose rung this page must READ rather than take off the field, computed by `map.render`
// from `ledger.decision_rung` — the one implementation of that rule, in the module that owns the
// schema. A pre-v0.11 cascade records `transcribed`, and rendering that literally is how this
// surface called the user's own elected policy an agent's unquoted relay. Empty for every ledger
// this runtime wrote, so the branch below is visibly the exception it is.
const DERIVED = __DERIVED__;
function derived(ev){
  return (ev&&ev.id&&Object.prototype.hasOwnProperty.call(DERIVED,ev.id))?DERIVED[ev.id]:{};
}
function rungOf(p){
  if(!p||!p.decision)return null;
  const ev=decisionEvent(p.decision.event_id);
  if(!ev)return null;
  const d=derived(ev);
  return d.rung?String(d.rung):(ev.evidence?String(ev.evidence):'');
}
function decisionCard(p){
  const ev=decisionEvent(p.decision.event_id)||{};
  const d=derived(ev);
  const r=d.rung?String(d.rung):(ev.evidence?String(ev.evidence):'');
  const meta=rungMeta(r), cls=meta?meta.cls:'weak';
  const quote=ev.human_answer?`<div class="quote">“${esc(ev.human_answer)}”</div>`:'';
  let note=meta?`<div class="why">${meta.why}</div>`
    :`<div class="warn">⚠ no evidence rung recorded — how this answer reached the ledger is unknown</div>`;
  if(r==='transcribed'&&!ev.human_answer)
    note+=`<div class="warn">⚠ relayed with no quote — nothing here separates it from an invention</div>`;
  // A cascaded decision was never answered here: it points at the policy election that produced it,
  // so the card shows that policy's rule AND how the human elected it. Joined on `policy_id`, the
  // event's own field — the `policy:<id>` in `source` is not parsed, because a surface should not
  // have to take a string apart to find the record it needs.
  let pol='';
  if(r==='cascaded'){
    // `policy_id` when the writer left one; for a pre-v0.11 event the id is in `source` and
    // `map.render` has already taken it apart — once, in Python, not here.
    const pid=ev.policy_id||d.policy_id||'';
    const P=policyById(pid);
    if(d.as_recorded)
      note+=`<div class="warn">⚠ written before the <code>cascaded</code> rung existed (this ledger is v${esc(String(LEDGER.version||'?'))}); the event records <code>${esc(d.as_recorded)}</code>, which was the default of the call it was written by — nobody relayed this, and nothing has been rewritten to say otherwise</div>`;
    if(!P) note+=`<div class="warn">⚠ cascaded from policy ${esc(pid||'(unnamed)')}, which this ledger does not contain</div>`;
    else{
      const idx=(LEDGER.policies||[]).indexOf(P);
      // a span, not an <a>: the page styles nothing else as a link, and an unstyled anchor took the
      // browser's default blue — unreadable on the dark card this very warning sits in.
      pol=`<div class="kv"><b>policy</b><span class="lnk" onclick="selectPolicy(${idx})">${esc(P.id)}</span></div>`
        +policyRows(P);
      // Two different states, and merging them was the same false sentence one level up: a policy
      // written before v0.11 carries NO rung (they moved onto the Policy there), so calling it a
      // relay asserts something its file never said. Unrecorded is unknown, not weak.
      note+=policyRungWarning(P,'this pin and every other one in its cluster rest on that');
      // The rule writes ONE outcome; this pin records another. Only a file written outside the
      // cascade can hold that, which is exactly when a reader has to be told rather than shown two
      // values on one card and left to notice.
      if(P.default_outcome!==undefined&&String(P.default_outcome)!==String(p.decision.outcome))
        note+=`<div class="warn">⚠ this pin records <code>${esc(p.decision.outcome)}</code>, but the rule it names decides <code>${esc(P.default_outcome)}</code> — the cascade cannot have written both</div>`;
    }
  }
  return `<div class="card dec ${cls}">
    <div class="kv"><b>decided</b><span>${esc(p.decision.outcome)}</span></div>
    <div class="kv"><b>evidence</b><span class="rung ${cls}">${esc(meta?meta.label:(r||'unrecorded'))}</span></div>
    ${pol}${quote}${note}</div>`;
}

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
  const pols=LEDGER.policies||[];
  if(!pins.length&&!pols.length){el.innerHTML='<div class="empty">empty ledger</div>';return;}
  // The policies lead the list because one of them decides a whole cluster, and because a rule the
  // human elected must be reachable whether or not it happened to bind a pin.
  const polHTML=!pols.length?'':`<div class="grp">Standing rules — elected by the human</div>`+
    pols.map((P,j)=>{
      const pm=rungMeta(P.evidence?String(P.evidence):'');
      const weak=!pm||pm.cls==='weak';
      return `<div class="pin${j===selPol?' sel':''}" onclick="selectPolicy(${j})">
      <div class="t">${esc(P.rule)}</div>
      <div class="m"><span class="pol">policy</span><span>${esc(P.id)}</span>
      <span>· ${eventsOfPolicy(P.id).length} pin(s)</span>`+
      (weak?`<span class="rung weak">${esc(pm?pm.label:'no rung recorded')}</span>`:'')+
      `</div></div>`;}).join('')+
    (pins.length?`<div class="grp">Pins</div>`:'');
  // Only the WEAK rung is badged in the list. Badging all three would turn the signal into
  // decoration; the card states the rung for every decision, whichever it is.
  el.innerHTML=polHTML+pins.map((p,i)=>{
    const r=rungOf(p), m=r===null?null:rungMeta(r);
    const weak=r!==null&&(m?m.cls:'weak')==='weak';
    return `<div class="pin${i===sel?' sel':''}" data-pin="${i}" onclick="select(${i})">
    <div class="t">${esc(p.title)}</div>
    <div class="m"><span class="sev" style="background:${SEV[p.severity]||'#888'}">${p.severity}</span>
    <span>${esc(p.kind)}</span><span>· ${esc(p.state)}</span>`+
    (weak?`<span class="rung weak">${esc(m?m.label:'unrecorded')}</span>`:'')+
    `</div></div>`;}).join('');
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
  const label = view==='as_is'?'as-is':'to-be';
  // `contractCols` answers '' for a contract_mismatch carrying no layers, so taking that branch on
  // `kind` alone rendered the pin as a bare title: no columns, no card, no message, and no `raw` to
  // fall back on. Branch on what it PRODUCED, not on what it was asked for.
  const cols = (p.kind==='contract_mismatch'&&view==='as_is') ? contractCols(p) : '';
  if(cols) body+=cols;
  else if(!isBlank(side)) body+=sideCard(side,label);
  else body+=`<div class="card nul">no ${label} yet</div>`;
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
  if(p.decision) body+=decisionCard(p);
  return `<h2>${esc(p.title)}</h2><div class="sub"><span class="sev" style="background:${SEV[p.severity]||'#888'}">${p.severity}</span> · ${esc(p.kind)} · ${esc(p.state)}${p.substate?' ('+esc(p.substate)+')':''}</div>`+body;
}
function select(i){sel=i;selPol=null;renderList();
  document.getElementById('detail').innerHTML=detail((LEDGER.pins||[])[i]);}
function selectPolicy(j){selPol=j;sel=null;renderList();
  document.getElementById('detail').innerHTML=policyDetail((LEDGER.policies||[])[j]);}
function setView(v){view=v;document.getElementById('bAsis').classList.toggle('on',v==='as_is');
  document.getElementById('bTobe').classList.toggle('on',v==='to_be');
  if(sel!=null)document.getElementById('detail').innerHTML=detail(LEDGER.pins[sel]);}
trafficLight();renderList();
if((LEDGER.pins||[]).length)select(0);
else if((LEDGER.policies||[]).length)selectPolicy(0);
else document.getElementById('detail').innerHTML=detail(null);
__LIVE_SCRIPT__</script></body></html>
"""

# Live mode is opt-in and additive: these three fragments are injected only when live=True, so the
# frozen default is byte-for-byte the shareable artifact. No external fetch is introduced — the page
# re-reads nothing; it reloads itself and the MCP tool layer re-writes the file on each ledger write
# (a file:// page cannot poll a sibling JSON, so self-reload of a re-projected file is the only
# offline-safe "live"). Selection / view / scroll survive the reload via sessionStorage.
_LIVE_STYLE = """.livebadge{display:inline-flex;gap:7px;align-items:center;font-size:12px;font-weight:600;color:var(--ok);
padding:3px 10px;border:1px solid var(--ok);border-radius:20px}
.livebadge::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--ok);animation:pulse 1.4s infinite}
.livebadge em{color:var(--mut);font-style:normal;font-weight:500}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}
@keyframes flash{0%{background:var(--accent)}100%{background:transparent}}
.pin.changed{animation:flash 1.8s ease-out}
"""
_LIVE_BADGE = '<span class="livebadge" title="auto-refreshing from ledger.json">LIVE <em id="liveclock"></em></span>'
_LIVE_SCRIPT = """
(function(){
  var KEY='decmap.live', MS=2500;
  function keyOf(p,i){return p&&p.id!=null?String(p.id):'#'+i;}
  var prev={}; try{prev=JSON.parse(sessionStorage.getItem(KEY)||'{}');}catch(e){}
  try{
    if(prev.view&&prev.view!==view)setView(prev.view);
    if(prev.selKey){var ps=LEDGER.pins||[];for(var i=0;i<ps.length;i++){if(keyOf(ps[i],i)===prev.selKey){select(i);break;}}}
    if(prev.scroll)document.getElementById('list').scrollTop=prev.scroll;
  }catch(e){}
  try{
    // `.pin[data-pin]`, not `.pin`: the standing-rule rows share the row class and sit ABOVE the
    // pins, so a positional query would flash the wrong row for every pin in the list.
    var st=prev.states||{}, nodes=document.querySelectorAll('.pin[data-pin]');
    (LEDGER.pins||[]).forEach(function(p,i){var k=keyOf(p,i);if((k in st)&&st[k]!==p.state&&nodes[i])nodes[i].classList.add('changed');});
  }catch(e){}
  function snapshot(){
    var states={};(LEDGER.pins||[]).forEach(function(p,i){states[keyOf(p,i)]=p.state;});
    var selKey=(sel!=null&&LEDGER.pins&&LEDGER.pins[sel])?keyOf(LEDGER.pins[sel],sel):'';
    try{sessionStorage.setItem(KEY,JSON.stringify({view:view,selKey:selKey,scroll:document.getElementById('list').scrollTop,states:states}));}catch(e){}
  }
  var c=document.getElementById('liveclock');if(c)c.textContent=new Date().toLocaleTimeString();
  window.addEventListener('beforeunload',snapshot);
  setTimeout(function(){snapshot();location.reload();},MS);
})();
"""


def derived_rungs(ledger_data: dict) -> dict:
    """`event_id -> {rung, policy_id, as_recorded}` for every DecisionEvent whose rung this page must
    read instead of taking off the field. `{}` for anything this runtime wrote.

    The rule lives in `ledger.decision_rung` and is applied here, in Python, rather than mirrored in
    the page's JavaScript: a rule with two implementations in two languages has already begun to
    drift, and only one of them is reachable by a test without a browser. What crosses into the page
    is the *result* — which is also what makes the fix assertable: `test_map.py` reads this out of
    the rendered document.

    `as_recorded` carries the value the file actually holds, so the card can state the disagreement
    instead of quietly winning it. Nothing is rewritten; the ledger inlined beside this is untouched.
    """
    from ledger import cascaded_from, decision_rung
    out: dict = {}
    for event in ledger_data.get("decision_log") or []:
        if not str(event.get("id") or "").startswith("ev_"):
            continue
        rung = decision_rung(event)
        if rung == str(event.get("evidence") or ""):
            continue
        entry = {"rung": rung}
        if not event.get("policy_id") and cascaded_from(event):
            entry["policy_id"] = cascaded_from(event)
        if event.get("evidence"):
            entry["as_recorded"] = str(event["evidence"])
        out[str(event["id"])] = entry
    return out


#: Every placeholder the template carries. `render` substitutes them in ONE pass over the template,
#: so no substitution can ever run over content a previous one inlined.
_PLACEHOLDER_RE = re.compile(r"__(?:DATA|DERIVED|TITLE|LIVE_STYLE|LIVE_BADGE|LIVE_SCRIPT)__")


def render(ledger_data: dict, title: str = "", live: bool = False) -> str:
    """The whole page, as one string.

    Substitution is a **single pass** over the template, and that is a correctness property rather
    than a tidy-up. Chained `.replace()` calls run each one over the output of the last, so the
    ledger — agent-written content, from someone else's repo — was inlined first and then rewritten
    by the four substitutions that followed it. A pin titled ``evil __DERIVED__ title`` rendered as
    ``evil {} title``, or as the whole derived-rungs JSON when that was non-empty; ``__LIVE_SCRIPT__``
    in a pin title injected the self-reload loop into a frozen artifact meant to be safe to hand to
    anyone. `esc` cannot help — this happens in Python, before the page exists, to the JSON literal
    itself.

    One pass fixes it structurally: `re.sub` never re-scans what a replacement emitted, so inlined
    content is inert by construction and cannot be un-fixed by adding a placeholder later. Which is
    the point — the previous bug in this file was `esc` not escaping, and the lesson both times is
    that **inlining is the dangerous step**, so the guarantee has to hold at the step rather than in
    the order of the lines around it. An unknown placeholder raises `KeyError` here rather than
    surviving into the page as literal text.
    """
    values = {
        # script-safe: a `</script>` inside the data cannot close the script it rides in
        "__DATA__": json.dumps(ledger_data, ensure_ascii=False).replace("</", "<\\/"),
        "__DERIVED__": json.dumps(derived_rungs(ledger_data),
                                  ensure_ascii=False).replace("</", "<\\/"),
        "__TITLE__": html.escape(title or "ledger"),
        "__LIVE_STYLE__": _LIVE_STYLE if live else "",
        "__LIVE_BADGE__": _LIVE_BADGE if live else "",
        "__LIVE_SCRIPT__": _LIVE_SCRIPT if live else "",
    }
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(0)], _TEMPLATE)


def render_file(ledger_path: str | pathlib.Path, out_path: str | pathlib.Path,
                live: bool = False) -> pathlib.Path:
    data = json.loads(pathlib.Path(ledger_path).read_text(encoding="utf-8"))
    out = pathlib.Path(out_path)
    out.write_text(render(data, title=str(pathlib.Path(ledger_path).stem), live=live),
                   encoding="utf-8", newline="\n")
    return out
