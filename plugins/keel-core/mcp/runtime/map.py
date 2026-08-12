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

**The two dangerous steps are structural, not remembered** (v0.16). A ledger is written by agents
reading someone else's repo and may arrive from anywhere, so both places where its content becomes
page are closed by construction rather than by a rule each site obeys: `h` is a tagged template
whose every hole is escaped and the only thing that produces markup (`severity` was the one field
still interpolated raw — into a row, a sub-line, and a `style` attribute), and `_inline` emits a
JSON payload carrying no `<` at all (escaping `</` closed one way out of the inline script; `<!--`
before a later `<script` closed the *page*, leaving a header with two empty panes and no error —
the worst thing this surface can say, because a blank map reads as "no findings").

**The pin's whole envelope reaches the page, and the log with it** (v0.19). Eight fields were
written by the runtime and read here by nothing — `verification`, `resolution_mode`, `brainstorm`,
`remediation`, `premortem`, `readiness`, the pin's `evidence`, and five of the six kinds of
`decision_log` entry. Two of them were load-bearing rather than decorative: `verification` is what
`settlement_verdict` reads to decide whether ANY pin may close (absence is the weakest rung, not a
neutral one), so the reader asking *why will this pin not close* had nowhere to look but the JSON;
and `remediation` is the other half of that gate. `resolution_mode` is the field that says whether
the reader's SILENCE counts as an answer, which is the funnel's whole compression argument.
The fix is one change with one information architecture — a fixed stack of cards in the order a
reader asks the questions, each empty when its field is absent — because five independent additions
to one pane is how a surface acquires five vocabularies. The order and the reasoning are stated once
at the cards themselves. Nothing is dumped: `sideCard`'s `raw` already exists for the free-form
payloads, and everything else is projected because a projection is a claim about what matters.

**A sentence about the interview is false of a pin the interview cannot reach** (v0.21). The
`resolution_mode` line above shipped guarded on `SETTLED` alone, so the funnel's countdown —
*"if you say nothing, the interview settles this with the proposed answer"* — was printed on six
`detected` pins of the preview fixture, none of which poses a fork and none of which
`interview_view` returns. Reach is now read off `ledger.INTERVIEW_STATES` (`__ASKABLE__`) plus the
pin's own options, and a pin failing either half is told so instead of being told a countdown.

**Reading is never the operation that fails, and what could not be read is ON the page** (v0.23).
This surface was the last one still projecting a ledger it had not read through the guarded path,
and it failed in both directions at once: a `null` entry in `pins`, or a `pins` that is not a list,
threw inside the page's own `trafficLight` before anything was mounted — so the document rendered
its header and nothing else, while `render_map` returned `{"written": …}` with `isError: false`; and
a non-object entry in `decision_log` or `policies` made `render` itself raise in Python. Both halves
have one answer, and it is the one the schema already gave: `ledger.readable_ledger` is what this
module renders, so the page cannot be handed an entry the schema does not describe, and
`ledger.nonconforming` is inlined beside it so the page SAYS what was dropped (`nonconfBanner`) —
which it had never done, on any file, though `ledger_summary` reported it in the same session.
The counts here are therefore the counts `ledger_summary` reports; they used to be the raw array
lengths. Inside a record — free-form by kind, so not enumerable without guessing — the answer is the
one boundary at `mount`: it takes a thunk and renders what it could not project as a card a human
reads, rather than leaving the pane blank as it did for a `brainstorm.proposals` that was not a list.

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
/* The amber is not decoration: it is the whole mechanism by which a weak rung reads as weaker at a
   glance, and at #f08c00 it measured 2.48:1 as text on the light card and 2.33:1 on the tinted warn
   card — a warning nobody can read is the same failure as a warning nobody prints. `--low` measured
   3.32:1 as a badge fill (not the 2.48 first reported; the number is stated here because the
   correction is the point).
   ONE token cannot serve both uses of amber, and that is why the dark block re-declares it: as TEXT
   it must contrast with the surface, so it has to be dark on light and light on dark; as a BADGE
   FILL it must contrast with its own foreground. So the hue stays one hue (a fifth colour costs the
   reader more than it buys) and what splits is the foreground, `--onhigh`. Light: #ad5a00 gives
   4.95:1 as text on the card, 4.65:1 on `--warnbg`, 4.79:1 as the traffic dot, and 4.95:1 for white
   on the badge. Dark: #f08c00 stays (6.61:1 / 6.14:1 as text) and the badge takes a dark foreground
   for 6.61:1 instead of white's 2.48:1 — which is the half the finding did not report, because the
   badge pair is theme-independent and was failing in BOTH. `--low` #6c757d is 4.69:1 under white in
   both themes (it measured 3.32:1 before, not the 2.48:1 first written down).
   `--ok` was NOT in the finding and is fixed with it, because a sweep of every badge on every pin
   found the strong rung at 3.45:1 (and the live badge's green text at 3.33:1) — leaving it would
   have meant a gate named "a badge is readable against its own foreground" that skipped the one
   badge it would have failed on, which is the other defect this register is currently carrying.
   Same split, same reason: light #28802f (4.98:1 under white, 4.82:1 as the live badge's text),
   dark #2f9e44 kept for that text (5.25:1) with a dark badge foreground (4.77:1).
   `--accent` was the third and last, found the same way: the `policy` pill measured 4.32:1 in light
   and 2.97:1 in DARK (white on the lighter indigo), and the same token is the link colour, which was
   4.32:1 as text. Light #4263eb (4.98:1 both ways), dark #748ffc kept (5.54:1 as text) with the dark
   badge foreground (5.54:1).
   At three, this stopped being three fixes and became ONE RULE, which is why it is stated here
   rather than at each site: **a hue that is both a badge fill and a text colour needs a paired
   foreground, and the pair — not the hue — is what switches by theme.** `--blocker`, `--medium` and
   `--low` need no pair because they are only ever fills; the other three are both, and all three
   were failing on the use the palette was not designed around.
   `tests/test_map.py::TestThePaletteCarriesTheWarningItIsUsedFor` computes these from this block —
   a fact about the stylesheet, not a claim about a DOM; the DOM half is the preview walk. */
:root{--bg:#fbfbfd;--fg:#1c1c1e;--mut:#6b6b70;--card:#fff;--line:#e3e3e8;--accent:#4263eb;
--code:#f1f1f5;--blocker:#e03131;--high:#ad5a00;--medium:#1971c2;--low:#6c757d;--ok:#28802f;
--onhigh:#ffffff;--onok:#ffffff;--onaccent:#ffffff;--warnbg:#fff7e6}
@media(prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececf1;--mut:#9a9aa2;--card:#1f1f23;
--line:#303036;--accent:#748ffc;--code:#2a2a31;--high:#f08c00;--onhigh:#1f1f23;--ok:#2f9e44;
--onok:#1f1f23;--onaccent:#1f1f23;--warnbg:#2e2413}}
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
.toggle button.on{background:var(--accent);color:var(--onaccent)}
main{display:grid;grid-template-columns:minmax(260px,340px) 1fr;gap:0;min-height:calc(100vh - 62px)}
@media(max-width:720px){main{grid-template-columns:1fr}}
.list{border-right:1px solid var(--line);overflow-y:auto;max-height:calc(100vh - 62px)}
.pin{padding:11px 16px;border-bottom:1px solid var(--line);cursor:pointer}
.pin:hover{background:var(--card)}.pin.sel{background:var(--card);box-shadow:inset 3px 0 0 var(--accent)}
.grp{padding:9px 16px 6px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--mut);font-weight:650;border-bottom:1px solid var(--line);background:var(--bg)}
.pol{padding:1px 7px;border-radius:20px;font-size:11px;font-weight:600;
  color:var(--onaccent);background:var(--accent)}
.lnk{color:var(--accent);cursor:pointer;text-decoration:underline}
.pin .t{font-weight:600;margin-bottom:3px}.pin .m{font-size:12px;color:var(--mut);display:flex;gap:8px;flex-wrap:wrap}
.sev{padding:1px 7px;border-radius:20px;font-size:11px;font-weight:600}
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
.rung.strong{background:var(--ok);color:var(--onok)}.rung.weak{background:var(--high);color:var(--onhigh)}
.why{color:var(--mut);font-size:12px;margin-top:7px}
.warn{color:var(--high);font-size:12px;font-weight:600;margin-top:7px}
/* The one line that says whether SILENCE settles this pin. It sits under the sub-line rather than
   in a card because it is not a finding about the pin, it is an instruction to the reader — and
   only one of the three modes is a countdown, so only that one takes a colour. */
.mode{font-size:12px;color:var(--mut);margin:-13px 0 16px}
/* The countdown carries the accent as a BORDER and not as text: `--accent` on `--bg` measures
   4.32:1 in light mode, and adding a new 12px text element below the text bar while fixing two
   other tokens for failing it would be this section's own finding, re-committed. A border is a
   non-text UI element, where 3:1 is the bar, and the words stay at `--fg`. */
.mode.cd{color:var(--fg);font-weight:600;border-left:3px solid var(--accent);padding-left:9px}
.trail .item{padding:0 0 0 12px}
.trail b{font-weight:650}.trail .imp{color:var(--mut);padding:1px 0 0}
.quote{margin:9px 0 0;padding:5px 0 5px 12px;border-left:3px solid var(--line);font-style:italic;
  overflow-wrap:anywhere}
/* The banner sits between the header and the two panes: what it says is true of the FILE, so it may
   not live inside a pane one selection can replace. Empty and zero-height when the file conforms. */
#warnbar:not(:empty){padding:0 22px;border-bottom:1px solid var(--line)}
#warnbar .card{margin:12px 0}
__LIVE_STYLE__</style></head><body>
<header>
  <h1>🧭 Decisions map</h1>__LIVE_BADGE__
  <div class="light"><span class="dot" id="tl"></span><span id="tltext"></span>
    <span class="bar"><i id="prog"></i></span></div>
  <div class="toggle"><button id="bAsis" class="on" onclick="setView('as_is')">as-is</button>
    <button id="bTobe" onclick="setView('to_be')">to-be</button></div>
</header>
<div id="warnbar"></div>
<main><div class="list" id="list"></div><div class="detail" id="detail"></div></main>
<script>
const LEDGER = __DATA__;
// Background AND foreground, because they are not independent: white on the amber that is dark
// enough to be readable as text is fine, white on the amber that is light enough to be readable ON
// a dark card is 2.48:1. The pair travels together so a theme cannot change one without the other.
const SEV = {blocker:{bg:'var(--blocker)',fg:'#fff'}, high:{bg:'var(--high)',fg:'var(--onhigh)'},
             medium:{bg:'var(--medium)',fg:'#fff'}, low:{bg:'var(--low)',fg:'#fff'}};
// The states in which a pin has stopped being open, taken from `ledger.SETTLED_STATES` rather than
// re-listed here. v0.16 made `deferred` one of them and this page went on counting a deferred
// blocker as an OPEN blocker: the traffic light reported a question the human had already answered,
// in the loudest colour the page has. A set the schema owns cannot fall behind the schema.
const SETTLED = new Set(__SETTLED__);
// The marks a pin carries because something put it BACK in front of the human. From
// `ledger.REOPENED_SUBSTATES` for the same reason `SETTLED` is from `SETTLED_STATES`: a fourth arc
// leaving a fourth mark must arrive here rather than be silently unrecognised.
const REOPENED = new Set(__REOPENED__);
// The states the INTERVIEW reads, from `ledger.INTERVIEW_STATES` — `interview_view`'s own selection
// and not a second list beside it. This page had no such set and re-derived reach from `SETTLED`
// alone, which is how the funnel's countdown came to be printed on `detected` pins the funnel does
// not carry. See `modeLine`.
const ASKABLE = new Set(__ASKABLE__);
// How long a claim stays live, from `ledger.CLAIM_TTL_SECONDS`. Inlined for the reason the three
// sets above are: a tuned number typed twice is two surfaces disagreeing about one pin.
const CLAIM_TTL = __CLAIM_TTL__;
let view='as_is', sel=null, selPol=null;
const ENT={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
const esc = s => (s==null?'':String(s)).replace(/[&<>"']/g, c=>ENT[c]);
function has(o,k){return Object.prototype.hasOwnProperty.call(o,k);}

// -- the only way this page builds HTML -------------------------------------------------------
// Calling `esc` at each site is a rule every site has to remember, and this file has now got it
// wrong twice: first `esc` was a String() cast that escaped nothing at all, then `severity` — alone
// among the fields — was interpolated raw into the list row, the detail sub-line and a `style`
// attribute, so a ledger carrying `severity: "<img src=x onerror=…>"` put a live img node in the
// DOM of a page whose whole promise is that it is safe to hand to anyone. Fixing the field would
// leave the next field to be remembered by the next author.
//
// So the mechanism escapes, not the author. `h` is a tagged template: every hole goes through
// `frag`, `frag` escapes anything that is not an `H`, and only `h` produces an `H`. There is no
// opt-out to reach for — no `raw()`, no second constructor — so an unescaped interpolation is not
// something you can write here, and a bare string that reaches the DOM sink unassembled renders as
// visible text rather than as markup. One sink, one assembler: `mount` is the only place this page
// writes markup into the document, which is the property `tests/test_map.py` holds.
function H(s){this.s=s;}
function frag(v){
  if(v instanceof H) return v.s;
  if(Array.isArray(v)) return v.map(frag).join('');
  return esc(v);
}
function h(strings){
  let out=strings[0];
  for(let i=1;i<arguments.length;i++) out+=frag(arguments[i])+strings[i];
  return new H(out);
}
// -- the only way this page STOPS building HTML ------------------------------------------------
// `mount` takes a THUNK, not a node, and that one signature change is the whole of the second
// mechanism. It used to take an already-built node, so anything that threw while building one threw
// BEFORE the sink was reached and the pane was simply never written: clicking a pin whose
// `brainstorm.proposals` was not a list left the detail pane blank, in a browser, with no console
// reader — and the list beside it went on showing the pin as selected. A pane that renders nothing
// says "there is nothing here", which is the same lie as a blank map.
//
// The rule this page is held to is the schema's own: **a surface that cannot render something says
// so where a human reads, never blank and never raised.** The Python side guarantees the CONTAINER
// (`ledger.readable_ledger`), so what reaches here is always a list of objects; this is the answer
// for everything inside one of those objects, which is free-form by kind and cannot be enumerated
// without guessing. One boundary serves every pane and every card added later, and the subject is
// shown raw so nothing is hidden by the failure to project it.
function mount(id,build,subject){
  let node;
  try{ node=build(); }
  catch(err){ node=cannotRender(err,subject); }
  document.getElementById(id).innerHTML=frag(node);
}
function cannotRender(err,subject){
  return h`<div class="card dec weak"><div class="ch">this map could not render this</div>
    <div class="warn">⚠ ${String((err&&err.message)||err)}</div>
    <div class="why">something inside this record is not the shape the schema describes, so the
      projection of it stopped here. Nothing has been hidden and nothing has been rewritten — the
      ledger is exactly as it was. Run <code>ledger_summary</code> for the file's own nonconformance
      report; the record itself is below.</div>
    ${subject===undefined?'':h`<details class="raw" open><summary>the record, as the file holds it</summary>
      <pre>${JSON.stringify(subject,null,2)}</pre></details>`}</div>`;
}
// A colour from a closed table, never a value off the file: `SEV[p.severity]` reached
// `constructor` and every other inherited name, and put a function body inside a style attribute.
// The fallback is a real badge and is held to the same bar as the four named ones: at `#888` it
// measured 3.54:1 under white, and it is the badge a HOSTILE severity lands on — the one case where
// the reader most needs to see the value they were handed. `#495057` is 8.18:1 and is deliberately
// darker than `--low`, so an unrecognised severity never reads as the quietest one.
const SEV_UNKNOWN={bg:'#495057',fg:'#ffffff'};
function sevStyle(s){
  const e=has(SEV,String(s))?SEV[String(s)]:SEV_UNKNOWN;
  return 'background:'+e.bg+';color:'+e.fg;
}
function sevBadge(s){return h`<span class="sev" style="${sevStyle(s)}">${s}</span>`;}

// -- one vocabulary for NOT KNOWING ------------------------------------------------------------
// The rung case was thought through carefully — THREE states, because "a rung this page does not
// know" and "no rung recorded" cannot both be true of one card — and then the settlement table,
// added in the same version, took the older two-state shape and printed an unrecognised
// `settles_as` as a bare label in the card's key position. One page, one condition, two behaviours.
// What is shared is the SENTENCE, not the tables: they answer different questions off the same
// event, and merging them would be the fix overshooting the finding.
function unknownNote(what,v,consequence){
  return 'this map does not know the '+what+' `'+v+'` — it was most likely added to the schema '+
         'after this page was generated, so '+consequence;
}

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
  if(v===null||v===undefined||v==='') return h`<span class="nul">—</span>`;
  if(typeof v==='boolean') return h`<span class="bool">${v?'yes':'no'}</span>`;
  if(typeof v==='number') return h`<code>${v}</code>`;
  const s=String(v);
  return /\s/.test(s) ? h`${s}` : h`<code>${s}</code>`;
}
function valueHTML(v){
  if(isScalar(v)) return scalarHTML(v);
  if(Array.isArray(v)){
    if(!v.length) return h`<span class="nul">none</span>`;
    if(v.every(isScalar)) return h`<span class="chips">${v.map(scalarHTML)}</span>`;
    return h`<div class="items">${v.map(x=>h`<div class="item">${valueHTML(x)}</div>`)}</div>`;
  }
  const keys=Object.keys(v);
  if(!keys.length) return h`<span class="nul">—</span>`;
  return h`<dl class="fields">${keys.map(k=>
    h`<dt>${labelize(k)}</dt><dd>${valueHTML(v[k])}</dd>`)}</dl>`;
}
function sideCard(side,label){
  return h`<div class="card"><div class="ch">${label}</div>${valueHTML(side)}
    <details class="raw"><summary>raw</summary><pre>${JSON.stringify(side,null,2)}</pre></details></div>`;
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
    why:'settled in the project brief at frame time; the brief is the evidence, quoted below'},
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
// THREE states, not two. A card used to badge the rung the file records — `bogus` — and print
// underneath it "⚠ no evidence rung recorded", which cannot both be true of one event: a rung this
// page does not know is not an absent one. It is most likely a rung added to the schema after this
// page was written, and saying so is a different instruction to the reader than saying nothing was
// recorded. `known` drives the wording; both non-table cases stay `weak`, because a rung you cannot
// weigh is not a rung you may lean on.
function rungInfo(r){
  const s=(r==null?'':String(r));
  if(has(RUNG,s)) return {label:RUNG[s].label, cls:RUNG[s].cls, why:RUNG[s].why, known:true};
  if(s) return {label:s, cls:'weak', known:false,
    warn:unknownNote('rung',s,'nothing here says how strong the answer’s road was')};
  return {label:'no rung recorded', cls:'weak', known:false,
    warn:'no evidence rung recorded — how this answer reached the ledger is unknown'};
}

// -- the Policy as its own decision (v0.15) ---------------------------------------------------
// A policy is an election the human made over a whole cluster, so it is a DECISION and this surface
// has to show it. Until now it could only be reached by joining BACKWARD from a cascaded pin, so a
// policy that cascaded over nothing — held back by the threshold, or offered by no pin's question —
// appeared on this page nowhere at all, while `ledger_summary` counted it and the projected
// AGENTS.md listed it under "Standing rules". Three surfaces, three answers about one elected rule.
function scopeText(P){
  const a=P.applies_to||{}, ks=Object.keys(a);
  return ks.length?ks.map(k=>k+'='+String(a[k])).join(' · '):'every pin';
}
function policyRows(P){
  const pm=rungInfo(P.evidence);
  return h`<div class="kv"><b>rule</b><span>${P.rule}</span></div>
    <div class="kv"><b>applies to</b><span>${scopeText(P)}</span></div>
    <div class="kv"><b>decides</b><span>${scalarHTML(P.default_outcome)}</span></div>
    <div class="kv"><b>elected</b><span class="rung ${pm.cls}">${pm.label}</span></div>
    ${P.human_answer?h`<div class="quote">“${P.human_answer}”</div>`:''}`;
}
// WHY a standing rule must be weighed — one code per rule, computed in Python by
// `ledger.policy_weakness` and inlined, exactly like `DERIVED`. It used to be re-decided here, and
// the projected AGENTS.md re-decided it a third time under a narrower rule, so the two surfaces
// counted the same fixture and reported two and one. The classification is the schema's; only the
// sentence below belongs to this page.
const WEAK_POL = __WEAK_POLICIES__;
const WEAK_WHY={
  no_rung:'the policy itself records no rung — how the user elected it is unknown',
  unknown_rung:'the policy records a rung this map does not know, so how the user elected it cannot be weighed here',
  unquoted_relay:'the policy itself was relayed with no quote'};
// A rule's badge names WHAT IS MISSING, not the rung. On a pin the badge marks a weak rung and the
// card carries the quote to weigh; on a rule the quote is what decides whether it is weak at all,
// so a badge reading `transcribed` would sit on the unquoted rule and NOT on the quoted one beside
// it — the same token meaning two things, three rows apart.
const WEAK_BADGE={no_rung:'no rung recorded', unknown_rung:'unknown rung',
                  unquoted_relay:'relayed, no quote'};
function policyWeakness(P){return has(WEAK_POL,P.id)?WEAK_POL[P.id]:'';}
// One rule, two subjects: on a pin's card what rests on the policy is that pin and its cluster; on
// the policy's own card it is every decision that names it — or, when it decided none, the work
// that follows. `rests` carries the whole clause rather than being assembled from a subject and a
// verb that only agree in one of the calls: the card for a rule that bound nothing printed
// "…every decision that names it rests on that" directly above "no decision in this ledger names
// this rule", two adjacent sentences that read as an accusation about nothing.
function policyRungWarning(P,rests){
  const w=policyWeakness(P);
  if(!has(WEAK_WHY,w))return '';   // `relayed` (weak, but quoted) is badged, not warned about
  return h`<div class="warn">⚠ ${WEAK_WHY[w]}, and ${rests}</div>`;
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
  if(!P)return h`<div class="empty">select a rule</div>`;
  const evs=eventsOfPolicy(P.id);
  let did;
  if(!evs.length)
    // Not a warning: an elected rule that bound no pin is a legitimate state, and it is exactly the
    // state that used to be invisible here. Say what the file records — no decision names it — and
    // no more; WHY it bound nothing (threshold, options, or no match) is not on the event.
    did=h`<div class="why">no decision in this ledger names this rule: it cascaded over no pin. It
      stands as an elected rule for the work that follows — the projected <code>AGENTS.md</code>
      carries it under “Standing rules”.</div>`;
  else{
    // NOT `RUNG.cascaded.why`: that sentence is written to a reader looking at one pin ("this pin
    // fell under it"), and reusing it here would say the wrong thing about a rule that decided
    // several. Same fact, addressed to the reader who is actually here.
    did=h`<div class="why">the human answered once, here, for the whole radius below — so what you
      weigh on each of these is not invention but FIT: whether this rule suits that pin.</div>
      <div class="kv"><b>decided</b><span>${evs.length} pin(s)</span></div>
      ${evs.map(e=>{
        const f=pinById(e.pin_id);
        return f?h`<div class="opt" onclick="select(${f.i})" style="cursor:pointer"><b>${f.pin.title}</b>
          <div class="imp">→ ${e.outcome}</div></div>`
          :h`<div class="opt"><b>${e.pin_id}</b><div class="imp">this ledger holds no such pin</div></div>`;
      })}`;
  }
  const exc=(P.exceptions||[]).length
    ? h`<div class="kv"><b>exceptions</b><span class="chips">${P.exceptions.map(scalarHTML)}</span></div>`
    : '';
  // The clause has to be true of THIS card: a rule that decided nothing has no decisions resting on
  // it, and saying otherwise beside "no decision names this rule" reads as a contradiction.
  const rests=evs.length?'every decision that names it rests on that'
                        :'what gets written from here rests on it';
  return h`<h2>${P.rule}</h2>
    <div class="sub"><span class="pol">standing rule</span> · ${P.id} · elected by the ${P.set_by||'interview'}</div>
    ${nonconfCard(P.id)}
    <div class="card dec ${rungInfo(P.evidence).cls}">${policyRows(P)}${exc}
      ${policyRungWarning(P,rests)}${did}</div>`;
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
// Which settled state an ELECTION produced (`settles_as`, v0.16). Two of the three are not "the
// fork was answered" at all: `accepted` leaves the finding standing, `deferred` takes the question
// off the interview for now — and both used to render as "decided: keep" / "decided: defer", which
// is the card telling a reader a choice was made about the thing when the choice was about the
// scope. A value this table does not carry is shown as it stands rather than as `decided`.
const SETTLES={decided:'decided', accepted:'accepted (left as it is)',
               deferred:'deferred (not now)'};
// ...and a value it does not carry SAYS SO, in the sentence `rungInfo` already uses for the
// identical condition — a schema that grew after this artifact was written. It used to print the
// bare token in the card's key position, formatted exactly like the three it understands, so a
// reader was shown a word the page could not describe and given no sign of it. The `cls` is
// deliberately NOT touched: the card's colour is the rung's answer, and letting a second axis
// recolour it would merge two tables that answer different questions off one event.
function settlesInfo(v){
  const s=String(v||'decided');
  if(has(SETTLES,s)) return {label:SETTLES[s], known:true};
  return {label:s, known:false,
    warn:unknownNote('settled state',s,'nothing here says what this election produced — the pin’s '+
                     'own state, in the line under the title, is what the file records')};
}
function decisionCard(p){
  const ev=decisionEvent(p.decision.event_id)||{};
  const d=derived(ev);
  const r=d.rung?String(d.rung):(ev.evidence?String(ev.evidence):'');
  const info=rungInfo(r), cls=info.cls;
  const settles=settlesInfo(ev.settles_as);
  // Two rungs quote something, and each quotes a different thing: `transcribed` quotes the human an
  // agent relayed, `brief` (v0.24) quotes the passage of the project brief that settled the fork
  // with nobody asked. One line, because the reader's question is the same both times — what,
  // exactly, is this decision resting on — and the rung above already says whose words these are.
  const said=ev.human_answer||ev.brief_quote||'';
  const quote=said?h`<div class="quote">“${said}”</div>`:'';
  let note=info.known?h`<div class="why">${info.why}</div>`
    :h`<div class="warn">⚠ ${info.warn}</div>`;
  const notes=[note];
  if(!settles.known) notes.push(h`<div class="warn">⚠ ${settles.warn}</div>`);
  // The card describes the EVENT, which is a historical fact; the pin may since have been handed
  // back. Without this line the card reads `decided → request_id` on a pin whose sub-line says
  // `needs_input (challenged)`, which is the same false reading the projected AGENTS.md was fixed
  // for one surface over — an outcome under dispute formatted exactly like an elected one.
  if(REOPENED.has(p.substate))
    notes.push(h`<div class="warn">⚠ this answer is under dispute (${p.substate}) — the pin is back
      in front of the human, and nothing should be built on it until they answer again</div>`);
  if(r==='transcribed'&&!ev.human_answer)
    notes.push(h`<div class="warn">⚠ relayed with no quote — nothing here separates it from an invention</div>`);
  // The same sentence for the same reason, on the rung that acquired its carrier one version later
  // (v0.24). A `brief` event written before that has no passage and none can be reconstructed, so
  // the card says what the file records rather than going quiet — and `nonconforming` reports it.
  if(r==='brief'&&!ev.brief_quote)
    notes.push(h`<div class="warn">⚠ from the brief, with the brief unquoted — nothing here separates an honest reading of a document from an invented one</div>`);
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
      notes.push(h`<div class="warn">⚠ written before the <code>cascaded</code> rung existed (this ledger is v${String(LEDGER.version||'?')}); the event records <code>${d.as_recorded}</code>, which was the default of the call it was written by — nobody relayed this, and nothing has been rewritten to say otherwise</div>`);
    if(!P) notes.push(h`<div class="warn">⚠ cascaded from policy ${pid||'(unnamed)'}, which this ledger does not contain</div>`);
    else{
      const idx=(LEDGER.policies||[]).indexOf(P);
      // a span, not an <a>: the page styles nothing else as a link, and an unstyled anchor took the
      // browser's default blue — unreadable on the dark card this very warning sits in.
      pol=h`<div class="kv"><b>policy</b><span class="lnk" onclick="selectPolicy(${idx})">${P.id}</span></div>
        ${policyRows(P)}`;
      // Two different states, and merging them was the same false sentence one level up: a policy
      // written before v0.11 carries NO rung (they moved onto the Policy there), so calling it a
      // relay asserts something its file never said. Unrecorded is unknown, not weak.
      notes.push(policyRungWarning(P,'this pin and every other one in its cluster rest on that'));
      // The rule writes ONE outcome; this pin records another. Only a file written outside the
      // cascade can hold that, which is exactly when a reader has to be told rather than shown two
      // values on one card and left to notice.
      if(P.default_outcome!==undefined&&String(P.default_outcome)!==String(p.decision.outcome))
        notes.push(h`<div class="warn">⚠ this pin records <code>${p.decision.outcome}</code>, but the rule it names decides <code>${P.default_outcome}</code> — the cascade cannot have written both</div>`);
    }
  }
  return h`<div class="card dec ${cls}">
    <div class="kv"><b>${settles.label}</b><span>${p.decision.outcome}</span></div>
    <div class="kv"><b>evidence</b><span class="rung ${cls}">${info.label}</span></div>
    ${pol}${quote}${notes}</div>`;
}

// -- what this file holds that the schema does not describe --------------------------------------
// `ledger.nonconforming()` has existed since the log half was guarded and has been readable through
// `ledger_summary`'s `pre_rule_events` since v0.21 — and it reached this page, the surface a HUMAN
// opens, nowhere at all. So the map could count nine pins where the file holds eleven, or report
// "all settled" over a `pins` collection that is not a list, and say nothing about either.
// It is a banner and not a card because it is a fact about the FILE, true whatever is selected.
const NONCONF = __NONCONF__;
// The sentence per rule name. Not the schema's own message (`PIN_RULES` writes one per pin, for an
// agent about that pin); this one addresses the reader of a whole file about a whole class, which is
// the same split `WEAK_WHY` makes against `policy_weakness`. A rule with no sentence here is printed
// as its bare name rather than dropped — `unknownNote`'s discipline, one table over.
// The sentence per rule the two SHAPE tables derive, computed by `ledger.shape_notes` and inlined
// here for the same reason `__SETTLED__` is: thirty-one derived rules against thirty-one
// hand-written sentences is a table that falls behind its schema the first time a field is added.
// `NONCONF_WHY` below wins where it has an entry — those are the rules whose prose was argued.
const SHAPE_WHY = __SHAPE_WHY__;
const NONCONF_WHY={
  ledger_shape:'the file’s top level is not an object at all — there is nothing here to read a pin, a decision or a version off',
  collection_shape:'a whole collection is not a list, so everything in it is missing from this page',
  entry_shape:'an entry is not an object, so it is in the file and on no surface',
  log_entry_kind:'a log entry whose id names no kind — nothing dispatches it',
  pin_id:'a pin with no id: nothing can depend on it or link to it',
  pin_state:'a state outside the schema’s set — it is in no bucket and no count',
  pin_severity:'a severity this runtime cannot rank; it sorts last rather than being guessed at',
  pin_depends_on:'a `depends_on` that is not a list of pin ids — no wave is levelled by it',
  pin_question:'a `question` that is not an object, so the interview has no fork to ask',
  pin_title:'a title that is not a string',
  pin_decision:'a `decision` that is not an object — the elected outcome cannot be read off it',
  policy_id:'a standing rule with no id: no decision can name it',
  policy_rule:'a standing rule with no readable rule text',
  policy_applies_to:'a scope that is not an object — the radius of the rule cannot be read',
  // `EVENT_RULES`, which reports on the LOG and whose membership question is different: these are
  // decidable from the stored event alone, and a file predating the rule keeps its old version
  // rather than being rewritten. The first draft of this table left all seven out and the browser
  // walk showed two of them on the page as "no sentence here describes this rule" — a table
  // quantifying over less than the report can produce, which is the class this register calls its
  // worst. The gate is derived from all three tuples now.
  committing_source:'a decision whose `source` is neither the interview nor a policy — nothing says who committed it',
  evidence_rung:'a decision on a rung the schema does not name — how the answer travelled cannot be weighed',
  cascade_rung:'a decision whose rung and whose source disagree about whether a policy decided it',
  cascade_policy_id:'a cascaded decision that names no policy, or a policy named by a decision that did not cascade',
  brief_quote:'a decision the brief settled without quoting it, or a quote on a decision the brief did not settle — nothing separates an honest reading of a document from an invented one',
  flip_criteria:'a decision with no `flip_criteria` — nothing says when to reopen it',
  flip_signal_source:'a flip signal whose source is not one the measurer can read',
  offered_outcome:'a decision whose outcome the pin’s own question never offered',
  settled_state:'a `settles_as` naming a state no election produces'};
function nonconfCount(){
  let n=0; for(const k in NONCONF) n+=(NONCONF[k]||[]).length; return n;
}
// One lookup, two tables, the argued sentence first. A rule in neither is printed as its bare name
// rather than dropped — `unknownNote`'s discipline, one table over.
function nonconfWhy(k){
  if(has(NONCONF_WHY,k)) return NONCONF_WHY[k];
  if(has(SHAPE_WHY,k)&&SHAPE_WHY[k]) return SHAPE_WHY[k];
  return 'no sentence here describes this rule';
}
// The rules this ONE pin breaks — the banner's report, asked by id. The banner is a fact about the
// file and a reader looking at a card was not being told that the card's own pin was in it: a pin
// carrying `verification: "observed"` rendered *"no verification rung recorded"*, which is what the
// guarded read makes true, over a file that records one — and no surface contradicted it. The
// report knows; it just had no place on the card until v0.25.
function nonconfFor(id){
  const out=[]; if(!id) return out;
  for(const k in NONCONF) if((NONCONF[k]||[]).indexOf(id)>=0) out.push(k);
  return out;
}
function nonconfCard(id){
  // A record this runtime cannot NAME cannot be joined to a report entry about it, and the honest
  // move is to say so rather than to show a clean card. `nonconforming` names such a record by its
  // position (`pins[5]`), which is a thing a reader can find in the banner and this page cannot
  // match against a card. Not a guess and not silence — the third option.
  if(!id) return h`<div class="card dec weak"><div class="ch">this record carries no readable id</div>
    <div class="why">so the report at the top of this page cannot be joined to this card. Whatever
      it says about this record is listed there by POSITION — look for <code>pins[N]</code> or
      <code>policies[N]</code>.</div></div>`;
  const rules=nonconfFor(id); if(!rules.length) return '';
  return h`<div class="card dec weak"><div class="ch">this record breaks ${rules.length} rule(s) of
      the schema — what the cards below show is the guarded reading, not the file</div>
    ${rules.map(k=>h`<div class="kv"><b>${k}</b><span>${nonconfWhy(k)}</span></div>`)}</div>`;
}
function nonconfBanner(){
  const keys=Object.keys(NONCONF);
  if(!keys.length) return '';
  return h`<div class="card dec weak"><div class="ch">this ledger holds ${nonconfCount()} thing(s)
      the schema does not describe</div>
    ${keys.map(k=>h`<div class="kv"><b>${k}</b><span>${nonconfWhy(k)} —
      <span class="chips">${(NONCONF[k]||[]).map(scalarHTML)}</span></span></div>`)}
    <div class="why">the counts and the list on this page are what a reader can index, which is why
      they can be smaller than the arrays in the file. Nothing was rewritten;
      <code>ledger_summary</code> reports the same list under <code>pre_rule_events</code>, and a
      file in this state does not get its <code>version</code> raised.</div></div>`;
}

function trafficLight(){
  const pins=LEDGER.pins||[]; const done=pins.filter(p=>SETTLED.has(p.state)).length;
  const openBlockers=pins.filter(p=>!SETTLED.has(p.state)&&(p.severity==='blocker')).length;
  const pct=pins.length?Math.round(100*done/pins.length):100;
  const tl=document.getElementById('tl'); const txt=document.getElementById('tltext');
  // "settled", not "resolved": the bar counts every pin that has stopped being open, and one of
  // those states is `deferred` — a question the human answered with "not now". Calling that
  // resolved would be this surface reporting work that was not done as work that was.
  //
  // And a file with unreadable content NEVER reads green, whatever the readable part says. This
  // light used to sum the raw arrays: on a ledger whose `pins` is not a list it went full green and
  // said "all settled", which is a completeness claim about a file this page could not read.
  const bad=nonconfCount();
  // "nonconforming", the schema's own word, and not "unreadable": most of what this report names IS
  // readable and merely breaks a rule (a decision on a rung the schema does not name, a legacy
  // cascade). Only the collection case below is genuinely unreadable, and it says so in its own
  // sentence rather than borrowing this one.
  const unreadable=bad?' · '+bad+' nonconforming':'';
  // A ledger with no pins is 100% settled — there is nothing to settle. A ledger whose pins could
  // not be READ is not, and the bar has to say so too: on a `pins` that is not a list this page
  // showed a full green bar over the words "all settled", which is a completeness claim about a
  // file it had failed to open.
  const nothingReadable=!pins.length&&bad;
  document.getElementById('prog').style.width=(nothingReadable?0:pct)+'%';
  if(openBlockers>0){tl.style.background='var(--blocker)';txt.textContent=openBlockers+' open blocker(s) · '+pct+'% settled'+unreadable;}
  else if(nothingReadable){tl.style.background='var(--high)';txt.textContent='nothing on this file could be read'+unreadable;}
  else if(pct<100||bad){tl.style.background='var(--high)';txt.textContent=pct+'% settled'+unreadable;}
  else{tl.style.background='var(--ok)';txt.textContent='all settled';}
}
function renderList(){
  const pins=LEDGER.pins||[];
  const pols=LEDGER.policies||[];
  if(!pins.length&&!pols.length){mount('list',()=>h`<div class="empty">empty ledger</div>`);return;}
  // The policies lead the list because one of them decides a whole cluster, and because a rule the
  // human elected must be reachable whether or not it happened to bind a pin.
  const polRows=!pols.length?'':[h`<div class="grp">Standing rules — elected by the human</div>`,
    pols.map((P,j)=>{
      const w=policyWeakness(P);
      return h`<div class="pin${j===selPol?' sel':''}" onclick="selectPolicy(${j})">
      <div class="t">${P.rule}</div>
      <div class="m"><span class="pol">policy</span><span>${P.id}</span>
      <span>· ${eventsOfPolicy(P.id).length} pin(s)</span>
      ${w?h`<span class="rung weak">${has(WEAK_BADGE,w)?WEAK_BADGE[w]:w}</span>`:''}</div></div>`;}),
    pins.length?h`<div class="grp">Pins</div>`:''];
  // Only the WEAK rung is badged in the list. Badging all three would turn the signal into
  // decoration; the card states the rung for every decision, whichever it is.
  mount('list',()=>[polRows,pins.map((p,i)=>{
    const r=rungOf(p), m=r===null?null:rungInfo(r);
    const weak=r!==null&&m.cls==='weak';
    return h`<div class="pin${i===sel?' sel':''}" data-pin="${i}" onclick="select(${i})">
    <div class="t">${p.title}</div>
    <div class="m">${sevBadge(p.severity)}
    <span>${p.kind}</span><span>· ${p.state}</span>
    ${claimNote(p)}
    ${weak?h`<span class="rung weak">${m.label}</span>`:''}</div></div>`;})]);
}
// -- who is on it right now (`claimed_by`/`claimed_at`, spec v0.30) --------------------------
// A human opening this page while two sessions are running needs to know which pins are already
// taken, and the answer is time-dependent — a claim expires — so it cannot be a stored flag. The
// TTL is passed in from the runtime (`CLAIM_TTL_SECONDS`) rather than re-typed here: two copies of
// a tuned number is how one surface says live and another says stale about the same pin.
//
// A claim this page cannot date reads as STALE, exactly as the runtime reads it, and says so. The
// alternative — rendering it as held — would park a pin behind a timestamp nobody can fix, on the
// one surface where a human could otherwise notice and clear it.
function claimState(p){
  if(!p.claimed_by) return null;
  const at=Date.parse(p.claimed_at||'');
  if(Number.isNaN(at)) return 'stale';
  return (Date.now()-at)/1000 < CLAIM_TTL ? 'live' : 'stale';
}
function claimNote(p){
  const st=claimState(p);
  if(!st) return '';
  return st==='live'
    ? h`<span class="rung weak">held by ${p.claimed_by}</span>`
    : h`<span class="rung weak">stale claim (${p.claimed_by})</span>`;
}
// -- the same claim, re-derived by a DIFFERENT provider (`cross_derivations`, spec v0.9) ------
// Written by `Ledger.cross_derive` and, until this reader existed, read by NOTHING: not this page,
// not `ledger_summary`, not the projected AGENTS.md. One writer, zero readers — while the writer's
// own comment said "the derivations are on the pin either way, so the human sees what disagreed".
// A disagreement is also the one branch that REOPENS the pin (state `needs_input`, substate
// `contested`), so the reason a settled question was back in the interview was on no surface a
// human reads, and the fork they were asked to answer said nothing about it.
//
// The colour vocabulary is the one this page already has for how hard a claim was checked, not a
// second one: agreement earns the `cross_derived` rung and reads green like an elicited decision;
// a disagreement reads amber on a tinted card, like a relay with no quote.
const AGREE={agree:{label:'agree', cls:''},
             partial:{label:'partially agree', cls:'weak'},
             disagree:{label:'disagree', cls:'weak'}};
function crossCard(x){
  const k=String(x.agreement);
  const a=has(AGREE,k)?AGREE[k]:{label:k||'agreement not recorded', cls:'weak'};
  return h`<div class="card dec ${a.cls}">
    <div class="ch">cross-derivation — ${a.label}</div>
    <div class="kv"><b>claim</b><span>${x.claim}</span></div>
    ${(x.derivations||[]).map(d=>h`<div class="opt"><b>${d.provider}/${d.model}</b>
      <div class="imp">${d.result}</div></div>`)}
    ${detRow('were the providers distinct',x.independence_determinism)}
    ${detRow('do the answers mean the same',x.agreement_determinism)}
    ${x.notes?h`<div class="why">${x.notes}</div>`:''}
    ${a.cls?h`<div class="warn">⚠ two independent providers were asked and did not answer the same
      thing — what you weigh is WHICH derivation holds, not that a check was run</div>`:''}</div>`;
}
// -- the rest of the envelope: six fields that were WRITTEN and read here by nothing -------------
//
// One change, one information architecture, decided once — because five independent additions to
// one pane is how a surface acquires five vocabularies. The detail pane is a fixed stack of cards
// in the order a reader asks the questions, and each card answers '' when its field is absent, so
// the order below IS the design:
//
//   what is it        as-is / to-be           (or the three-column contract diff)
//   how hard checked  verification            ← the field that decides whether ANY pin may close
//   who else checked  cross_derivations
//   what was proposed brainstorm              ← proposals become the options of the fork below
//   what is asked     question + resolution   ← and whether SILENCE settles it
//   where it lives    anchors
//   what was elected  decision
//   can it land       readiness
//   what will be done remediation             ← what `resolve` is refused on
//   how it may die    premortem
//   how it got here   the trail
//
// Nothing here is a raw dump: `sideCard` already offers `raw` for the free-form payloads, and the
// reason the REST is projected is that a projection is a claim about what matters. Two fields were
// weighed for exclusion and kept: `premortem` and `readiness` are the only two addressed to a
// builder rather than to a decider, and they earn the page because each answers a question a reader
// of a pin actually has — *can the ground bear this* and *what did we already decide would kill it*
// — with a closed verdict vocabulary the page can colour honestly. They are last for that reason.

// How hard the claim was CHECKED (`verification`, spec v0.7) — three axes reported together, never
// blended into one number. The rung is a DIFFERENT closed set from a decision's (`how the answer
// travelled` vs `how the work was verified`), so it is its own table; what is reused is the badge,
// the strong/weak colouring, and the not-knowing sentence. `test_map.py` holds these keys against
// `ledger.VERIFICATION_RUNGS` and the `strong` ones against `ledger._CLOSING_RUNGS`, so the two
// rungs a pin may close on cannot drift from the two this page shows as strong.
const VRUNG={
  self_check:{label:'self-check', cls:'weak',
    why:'the agent re-read its own work — the weakest rung there is, and not one a pin may close on'},
  re_read:{label:'re-read', cls:'weak',
    why:'the artifact was read again, over the full diff rather than the output; nothing was run'},
  observed:{label:'observed', cls:'strong',
    why:'the behaviour was exercised and watched — this is what `resolved` means, and nothing weaker earns it'},
  cross_derived:{label:'cross-derived', cls:'strong',
    why:'a second provider re-derived the same claim independently and agreed — a single-provider invention rarely reproduces cross-provider'}};
function vrungInfo(r){
  const s=(r==null?'':String(r));
  if(has(VRUNG,s)) return {label:VRUNG[s].label, cls:VRUNG[s].cls, why:VRUNG[s].why, known:true};
  if(s) return {label:s, cls:'weak', known:false,
    warn:unknownNote('verification rung',s,'nothing here says how hard this was actually checked')};
  return {label:'no rung recorded', cls:'weak', known:false,
    warn:'no verification rung recorded — a pin carrying none records LESS than one at a weak rung, '+
         'so this cannot close as `resolved` until something is observed'};
}
const DET={D0:'D0 — a carrier computed it; the same input gives the same answer',
           D1:'D1 — reconstructible from a pinned artifact',
           D2:'D2 — model judgment on the path, not a computation'};
// The dial is SPLIT wherever a judgment sits on top of computed evidence, and the schema's rule is
// that the halves are "never merged into one score". Three pairs are written that way; until 2026-08-06
// this page printed the unsplit half of one pair and dropped the other five fields entirely, which
// is merging them by omission — the one thing the rule forbids — on the surface where the rule was
// supposed to be cashed. One row, six callers, so the next split arrives with a reader.
function detRow(label,v){
  const s=(v==null?'':String(v)); if(!s)return '';
  return h`<div class="kv"><b>${label}</b><span>${has(DET,s)?DET[s]
    :h`⚠ ${unknownNote('determinism level',s,'nothing here says whether it reproduces')}`}</span></div>`;
}
// `ledger.refuted_claim`, computed in Python and inlined — the same arrangement as DERIVED and
// WEAK_POL, for the same reason: two carriers make this fact (`blocked_by` AND a rung below the
// closing ones), and a page that asks only the first one gets it wrong in the direction that reads
// worst. It printed `⚠ this pin cannot close` on a RESOLVED pin, because `resolve` deliberately
// keeps `blocked_by` so that "it was blocked, then it was observed" survives as the sequence it is.
// Standing -> the warning. Answered -> the same words as history, which is what they are.
const REFUTED = __REFUTED__;
function blockedNote(p,v){
  const standing = (p&&p.id&&has(REFUTED,p.id))?REFUTED[p.id]:'';
  if(standing) return h`<div class="warn">⚠ this pin cannot close: ${standing}</div>`;
  if(!v||isBlank(v.blocked_by)) return '';
  return h`<div class="why">was blocked: ${v.blocked_by} — answered since, and the rung above is
    what answered it</div>`;
}
function verificationCard(p){
  const v=p.verification||null;
  if(!v&&!p.evidence)return '';
  const info=vrungInfo(v?v.rung:null);
  return h`<div class="card dec ${info.cls}">
    <div class="ch">verification — how hard this was checked</div>
    <div class="kv"><b>rung</b><span class="rung ${info.cls}">${info.label}</span></div>
    ${detRow('reproduces',v?v.determinism:null)}
    ${p.evidence?h`<div class="kv"><b>observation</b><span>${p.evidence}</span></div>`:''}
    ${v&&(v.attempted||[]).length?h`<div class="kv"><b>attempted</b>
      <span class="chips">${v.attempted.map(scalarHTML)}</span></div>`:''}
    ${v&&(v.cross_derived_by||[]).length?h`<div class="kv"><b>agreed by</b>
      <span class="chips">${v.cross_derived_by.map(scalarHTML)}</span></div>`:''}
    ${v&&!isBlank(v.evidence)?h`<div class="kv"><b>checks</b><span>${valueHTML(v.evidence)}</span></div>`:''}
    ${info.known?h`<div class="why">${info.why}</div>`:h`<div class="warn">⚠ ${info.warn}</div>`}
    ${blockedNote(p,v)}</div>`;
}

// What the brainstorm proposed. `add_proposals` is the only writer of the `brainstorming` state and
// its proposals are what the fork below is supposed to be answerable from, so a page that shows the
// fork and not the proposals shows the menu with the dishes removed. Neutral by construction: a
// proposal carries no outcome (the writer refuses one), and `recommended` is the brainstorm's own
// mark, never a default.
function brainstormCard(p){
  const b=p.brainstorm||null; const props=b?(b.proposals||[]):[];
  if(!props.length&&!(b&&b.notes))return '';
  return h`<div class="card"><div class="ch">brainstorm — proposals, not decisions</div>
    ${props.map(x=>h`<div class="opt"><b>${x.summary||x.id}</b>
      ${x.recommended?h`<span class="rung strong">recommended</span>`:''}
      <div class="imp">${x.id}${x.effort?' · effort '+x.effort:''}${x.tradeoff?' — '+x.tradeoff:''}</div></div>`)}
    ${b&&b.notes?h`<div class="why">${b.notes}</div>`:''}</div>`;
}

// Whether SILENCE settles this pin. `proposed_default` is the funnel's whole compression argument —
// *this one will be settled with the proposed answer unless you object* — and on this page such a
// pin was a row reading `needs_input`, identical to one nobody will settle without asking.
// Only the countdown is coloured: badging all three would turn the signal into decoration, and
// `policy_default` is already the decision card's story one card down.
// One honest consequence of the reach gate below, stated rather than left to be discovered: on a
// ledger THIS runtime wrote, `policy_default` only ever sits on a settled pin (`apply_policy` writes
// the mode in the same breath as the decision), so that clause fires only on a file we did not
// write. It is here because `RESOLUTION_MODES` is closed and a value with no sentence would fall
// through to "a mode this map does not know" — which would be false, and the preview fixture carries
// such a pin so the clause is looked at rather than assumed.
const MODE={
  asked:{cd:false,
    why:'this one must be ASKED: no standing rule and no proposed default may settle it for you'},
  policy_default:{cd:false,
    why:'a standing rule may settle this one on your behalf — the rule, and how you elected it, are on its own card'},
  proposed_default:{cd:true,
    why:'if you say nothing, the interview settles this with the proposed answer — here, silence IS the answer'}};

// **All three sentences are claims about what the INTERVIEW will do with this pin, so all three are
// false of a pin the interview cannot reach** — and that is what the guard used to miss. It excluded
// settled pins only, so a `detected` pin carrying `proposed_default` was told, in the page's most
// urgent voice, *"if you say nothing, the interview settles this with the proposed answer"*.
// Observed in a browser on six pins of the preview fixture at once. No host can ask a pin that poses
// no fork and no policy may take one (`unasked_verdict` refuses an outcome the pin's own question
// does not offer), so the page was stating a mechanism that cannot run — on the surface §7 added to
// make the mode honest.
//
// Reach has two carriers and neither is a judgement. `ASKABLE` is `ledger.INTERVIEW_STATES`, which
// is `interview_view`'s own selection rather than a second list beside it — the settled-pin gate is
// subsumed by it (no settled state is in it) and the reason that gate existed still holds: there the
// mode is history. The fork is the other half: an election writes an outcome the question offered,
// so a pin with no options has nothing for a proposed answer to BE.
//
// A pin that fails either half gets a sentence rather than silence, because silence where a
// countdown used to be is its own claim. It is the one thing a reader can act on: `set_question`
// (`mcp:ledger_set_question`) is the door that gives such a pin a fork.
function forkOptions(p){
  const q=p.question; const o=q&&q.options;
  return Array.isArray(o)?o:[];
}
function outOfReach(p){
  if(!ASKABLE.has(p.state))
    return 'no interview reads a pin in this state';
  if(!forkOptions(p).length)
    return 'it poses no question, so there is nothing to answer';
  return '';
}
function modeLine(p){
  if(SETTLED.has(p.state))return '';        // the mode is history once the pin is settled
  const m=p.resolution_mode; if(m==null||m==='')return '';
  const stuck=outOfReach(p);
  if(stuck)
    return h`<div class="mode cd">⚠ nothing will settle this one: ${stuck}, so no interview can ask it and no standing rule may take it — whatever mode it carries</div>`;
  const s=String(m);
  if(!has(MODE,s))
    return h`<div class="mode cd">⚠ ${unknownNote('resolution mode',s,
      'nothing here says whether your silence would settle this pin')}</div>`;
  return MODE[s].cd ? h`<div class="mode cd">⏳ ${MODE[s].why}</div>`
                    : h`<div class="mode">${MODE[s].why}</div>`;
}

// Can the ground bear the change (`readiness`, v0.8) — a D2 verdict over D0 evidence, and the
// object records both rather than blending them, so this card does too.
const READY={ready:{label:'ready', cls:'strong'},
             harden_first:{label:'harden first', cls:'weak'},
             redesign:{label:'redesign', cls:'weak'}};
function readinessCard(p){
  const r=p.readiness||null; if(!r)return '';
  const v=String(r.verdict||'');
  const info=has(READY,v)?READY[v]:{label:v||'no verdict recorded', cls:'weak'};
  const zone=r.zone||{}; const ev=r.evidence||{};
  const pins=ev.open_pins_in_zone||[];
  return h`<div class="card dec ${info.cls}"><div class="ch">landing zone — can the ground bear it</div>
    <div class="kv"><b>verdict</b><span class="rung ${info.cls}">${info.label}</span></div>
    ${detRow('the verdict',r.determinism)}
    ${detRow('the evidence under it',r.evidence_determinism)}
    ${(zone.files||[]).length?h`<div class="kv"><b>zone</b>
      <span class="chips">${zone.files.map(scalarHTML)}</span></div>`:''}
    ${pins.length?h`<div class="kv"><b>open pins in the zone</b><span class="chips">${
      pins.map(x=>scalarHTML((x&&x.pin?x.pin:x)+(x&&x.severity?' ('+x.severity+')':'')))}</span></div>`:''}
    ${(ev.untested_files||[]).length?h`<div class="kv"><b>no test reaches</b>
      <span class="chips">${ev.untested_files.map(scalarHTML)}</span></div>`:''}
    ${!isBlank(ev.churn)?h`<div class="kv"><b>churn</b><span class="chips">${
      Object.keys(ev.churn).map(f=>scalarHTML(f+' ×'+ev.churn[f]))}</span></div>`:''}
    ${(ev.coupled_outside_zone||[]).length?h`<div class="kv"><b>co-changes from outside</b><span class="chips">${
      ev.coupled_outside_zone.map(x=>scalarHTML((x&&x.file?x.file:x)+(x&&x.co_commits?' ×'+x.co_commits:'')))
      }</span></div>`:''}
    ${(r.hardens||[]).length?h`<div class="kv"><b>blocked on</b>
      <span class="chips">${r.hardens.map(scalarHTML)}</span></div>`:''}
    ${r.rationale?h`<div class="why">${r.rationale}</div>`:''}
    ${has(READY,v)?'':h`<div class="warn">⚠ ${unknownNote('readiness verdict',v,
      'nothing here says whether the ground was judged fit')}</div>`}</div>`;
}

// The plan, and the reason a pin will not close. `resolve` is refused while ANY item is open
// (`remediation_open`), and that refusal was readable on this page nowhere: the reader who asks
// *why is this still open* had to open the JSON to find an item at `todo`.
const REM_STATUS={todo:'to do', in_progress:'in progress', done:'done'};
function remediationCard(p){
  const items=p.remediation||[]; if(!items.length)return '';
  const done=items.filter(i=>i&&i.status==='done').length;
  return h`<div class="card"><div class="ch">remediation — what has to happen</div>
    ${items.map(i=>{
      const st=String(i.status||'');
      return h`<div class="opt"><b>${i.action}</b>
        <span class="bool">${has(REM_STATUS,st)?REM_STATUS[st]:st}</span>
        <div class="imp">${i.id} · ladder rung ${i.ladder_rung}${
          i.canonical_target?' → '+i.canonical_target:''}${
          i.build_track?' · track '+i.build_track:''}${
          i.contract_carrier?' · carrier '+i.contract_carrier:''}</div></div>`;})}
    ${done<items.length
      ? h`<div class="warn">⚠ ${done} of ${items.length} done — this pin cannot be resolved until every item is</div>`
      : h`<div class="why">every item is done, so this pin is resolvable once an observation reaches the closing rung</div>`}</div>`;
}

// How the work dies anyway (`premortem`, v0.9) — the challenger's second mode. It writes guardrails
// and abort criteria and never a decision, so this card carries no colour of election: it is D2 and
// says so. A `paper_tiger` is a risk already mitigated and must carry the evidence of that, which is
// the only part of it worth reading twice.
function premortemCard(p){
  const m=p.premortem||null; if(!m)return '';
  const chips=(xs)=>h`<span class="chips">${(xs||[]).map(scalarHTML)}</span>`;
  return h`<div class="card"><div class="ch">premortem — assume it already failed</div>
    ${(m.failure_modes||[]).map(f=>h`<div class="opt"><b>${f.class}</b>
      <div class="imp">${f.description||f.detail||''}</div></div>`)}
    ${(m.guardrails||[]).length?h`<div class="kv"><b>guardrails</b>${chips(m.guardrails)}</div>`:''}
    ${(m.abort_criteria||[]).length?h`<div class="kv"><b>abort if</b>${chips(m.abort_criteria)}</div>`:''}
    ${(m.paper_tigers||[]).map(t=>h`<div class="opt"><b>dismissed: ${t.risk}</b>
      <div class="imp">already mitigated — ${t.evidence}</div></div>`)}
    <div class="why">imagining how it dies is judgment (D2), recorded as judgment</div></div>`;
}

// -- how this pin got where it is: the whole trail, not only the decisions ----------------------
// The page read exactly one of the six kinds of entry the runtime appends (`ev_`), so it could show
// that a pin was settled and never HOW it stopped being open, or that it had ever been un-closed —
// which is the question `SETTLEMENT_DOORS` and the two reopen arcs exist to answer. Every entry is
// already inlined; none of them was on the page.
// A timeline was deliberately not built until the reopen arcs were reachable (they now are), because
// a timeline whose rows no host can produce is verified against fixtures only.
// This does NOT duplicate the decision card: that card weighs the CURRENT answer's rung, this says
// what happened, in order. One label and one sentence per kind, from a closed table held against
// `ledger.LOG_ENTRY_PREFIXES`, so a new kind arrives here instead of being silently dropped — which
// is not a hypothetical any more: `cas_` was added one round later and the gate is what put its row
// on this page.
const TRAIL={
  // The rung is READ through `derived`, exactly as the decision card reads it, and not taken off
  // `e.evidence`. Caught by looking at the page: on the pre-v0.11 cascade the card said "cascaded
  // from a policy" and this row said "transcribed" — one page, one event, two answers, which is the
  // divergence `derived_rungs` exists to prevent and which a second reader re-introduced.
  ev_:{label:'decision', line:e=>{
    const d=derived(e), r=d.rung?String(d.rung):(e.evidence?String(e.evidence):'');
    return h`elected ${e.outcome} → ${settlesInfo(e.settles_as).label}${
      r?' · '+rungInfo(r).label:''}`;}},
  stl_:{label:'settlement', line:e=>h`${e.door}: ${e.from_state} → ${e.to_state}${
    e.verification_rung?' · '+vrungInfo(e.verification_rung).label:''}`},
  chl_:{label:'challenge', line:e=>h`${e.class} against the ${e.target} — ${
    e.upheld?'upheld':'not upheld'}${e.reopened?', pin reopened':''}. ${e.argument||''}`},
  xdr_:{label:'cross-derivation', line:e=>h`${e.agreement} on: ${e.claim}${
    e.reopened?' — pin reopened':''}`},
  fal_:{label:'failure', line:e=>h`${e.class} in ${e.phase} — ${e.detail}`},
  rev_:{label:'reopen', line:e=>h`${e.fired} (${e.source})${e.reopened?'':' — nothing was settled to reopen'} — ${e.reason}`},
  // The cascade. `stl_`'s twin one direction over, and the row that did not exist while the write
  // did not either: a pin swept back into the open set by an arc aimed at something it depends on
  // showed a state change here with no entry explaining it.
  cas_:{label:'cascade', line:e=>h`${e.from_state} → ${e.to_state} (${e.substate}) — swept up by the ${e.arc} recorded as ${e.via}`}};
function trailKind(id){
  const s=String(id||'');
  const keys=Object.keys(TRAIL);
  for(let i=0;i<keys.length;i++) if(s.indexOf(keys[i])===0) return keys[i];
  return '';
}
function trailCard(p){
  const log=LEDGER.decision_log||[];
  const mine=[];
  for(let i=0;i<log.length;i++) if(log[i]&&log[i].pin_id===p.id) mine.push(log[i]);
  if(!mine.length)return '';
  return h`<div class="card trail"><div class="ch">trail — how this pin got here</div>
    <div class="items">${mine.map(e=>{
      const k=trailKind(e.id);
      if(!k) return h`<div class="item"><b>unrecognised entry</b>
        <div class="imp">⚠ ${unknownNote('log entry',String(e.id||'(no id)'),
          'this step is in the file and cannot be described here')}</div></div>`;
      return h`<div class="item"><b>${TRAIL[k].label}</b> ${TRAIL[k].line(e)}
        <div class="imp">${e.id} · ${e.timestamp||'no timestamp'}</div></div>`;})}</div></div>`;
}

function contractCols(p){
  const a=p.as_is||{}; const dis=new Set(a.disagreeing_layers||[]);
  const layers=Object.keys(a).filter(k=>k!=='disagreeing_layers');
  if(!layers.length)return '';
  return h`<div class="cols">${layers.map(l=>h`<div class="col${dis.has(l)?' dis':''}">
    <h4>${l}${dis.has(l)?' ⚠':''}</h4><code>${a[l]}</code></div>`)}</div>`;
}
function detail(p){
  if(!p)return h`<div class="empty">select a pin</div>`;
  const side=p[view]; const body=[];
  const label = view==='as_is'?'as-is':'to-be';
  // `contractCols` answers '' for a contract_mismatch carrying no layers, so taking that branch on
  // `kind` alone rendered the pin as a bare title: no columns, no card, no message, and no `raw` to
  // fall back on. Branch on what it PRODUCED, not on what it was asked for.
  const cols = (p.kind==='contract_mismatch'&&view==='as_is') ? contractCols(p) : '';
  if(cols) body.push(cols);
  else if(!isBlank(side)) body.push(sideCard(side,label));
  else body.push(h`<div class="card nul">no ${label} yet</div>`);
  // Before the question, because they are the evidence the question rests on: `cross_derive` leaves
  // the human's own fork untouched, so without this card the menu arrives with no account of why
  // the pin was reopened — and `verification.blocked_by` is the one sentence that makes a
  // `correctness_unknown` pin answerable at all.
  body.push(verificationCard(p));
  if((p.cross_derivations||[]).length) body.push(p.cross_derivations.map(crossCard));
  body.push(brainstormCard(p));
  if(p.question) body.push(h`<div class="card q"><b>Interview question</b><p>${p.question.prompt}</p>
    ${(p.question.options||[]).map(o=>h`<div class="opt"><b>${o.label}</b>${o.implication?h`<div class="imp">→ ${o.implication}</div>`:''}</div>`)}</div>`);
  if((p.anchors||[]).length) body.push(h`<div class="card anchors"><b>Anchors</b>
    ${p.anchors.map(a=>{
      const nid=a.node_id?h` <span class="nid">${a.node_id}</span>`:'';
      let br='';
      if(a.blast_radius&&a.blast_radius.count){
        const s=(a.blast_radius.sample||[]).join(', ');
        br=h`<div class="imp">↯ impact: ${a.blast_radius.count} dependent(s)${s?' — '+s:''}</div>`;
      }
      return h`<code>${a.layer||''} ${a.loc||a.node_id||''}${nid}</code>${br}`;
    })}</div>`);
  if(p.decision) body.push(decisionCard(p));
  body.push(readinessCard(p));
  body.push(remediationCard(p));
  body.push(premortemCard(p));
  body.push(trailCard(p));
  return h`<h2>${p.title}</h2><div class="sub">${sevBadge(p.severity)} · ${p.kind} · ${p.state}${p.substate?' ('+p.substate+')':''}</div>${modeLine(p)}${nonconfCard(p.id)}${body}`;
}
function select(i){const p=(LEDGER.pins||[])[i];sel=i;selPol=null;renderList();
  mount('detail',()=>detail(p),p);}
function selectPolicy(j){const P=(LEDGER.policies||[])[j];selPol=j;sel=null;renderList();
  mount('detail',()=>policyDetail(P),P);}
function setView(v){view=v;document.getElementById('bAsis').classList.toggle('on',v==='as_is');
  document.getElementById('bTobe').classList.toggle('on',v==='to_be');
  if(sel!=null){const p=LEDGER.pins[sel];mount('detail',()=>detail(p),p);}}
mount('warnbar',nonconfBanner);
trafficLight();renderList();
if((LEDGER.pins||[]).length)select(0);
else if((LEDGER.policies||[]).length)selectPolicy(0);
else mount('detail',()=>detail(null));
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
    from ledger import cascaded_from, decision_rung, read_collection
    out: dict = {}
    for event in read_collection(ledger_data, "decision_log"):
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


def weak_policies(ledger_data: dict) -> dict:
    """`policy_id -> why it must be weighed`, for every standing rule that must be — and nothing for
    the rest. The classification is `ledger.policy_weakness`, applied here in Python for the same
    reason `derived_rungs` is: a rule with an implementation in this module AND one in the page's
    JavaScript has already begun to drift, and only one of the two is reachable by a test without a
    browser.

    It had drifted, in the direction that matters least visibly: this page asked *"is the rung
    weak"*, the projected `AGENTS.md` asked *"is the quote missing"*, and on the repo's own preview
    fixture one surface badged two standing rules and the other reported one. Neither number was
    wrong on its own terms, which is precisely why a reader could act on neither.
    """
    from ledger import policy_read, policy_weakness, read_collection
    out: dict = {}
    for policy in read_collection(ledger_data, "policies"):
        reason = policy_weakness(policy)
        if reason:
            out[policy_read(policy)["id"]] = reason
    return out


def refuted_claims(ledger_data: dict) -> dict:
    """`pin_id -> the refutation still standing on it`, and nothing for a pin whose claim was
    answered. Computed by `ledger.refuted_claim`, inlined, for the reason `derived_rungs` and
    `weak_policies` are: the rule has one implementation, in Python, testable without a browser.

    The page had the field and not the rule. `blocked_by` is deliberately HISTORY — `resolve` keeps
    it verbatim when a later observation closes the pin, so *"it was blocked, then it was observed"*
    reads as the sequence it is — and this card printed it as a present-tense verdict on any pin
    carrying it. So on the most ordinary lifecycle in the package (work blocked, blocker lifted,
    work observed and closed) the card said `resolved` and *"⚠ this pin cannot close"* in the same
    breath; after the incident arc it printed *"nothing has been observed since"* directly under the
    observation that closed the pin.

    Two carriers make the fact and neither alone is it — which is exactly why the page must not
    re-derive it from one of them. `refuted_claim` is the predicate, it already existed, and until
    now it had one caller and this surface was not it.
    """
    from ledger import pin_read, read_collection, refuted_claim
    out: dict = {}
    for pin in read_collection(ledger_data, "pins"):
        standing = refuted_claim(pin)
        if standing:
            out[pin_read(pin)["id"]] = standing
    return out


#: The characters JSON may hold that JavaScript-inside-HTML may not, and their JSON escapes. Two
#: different holes, one table, because the mistake both times was fixing a SITE instead of the step.
#:
#: `<` is the HTML side: it cannot appear in JSON outside a string (the structural characters are
#: `{}[],:"` and the literals), so `<` is always the right encoding of it and always
#: round-trips.
#:
#: U+2028 / U+2029 are the JavaScript side, and they are the classic JSON-is-not-a-JS-subset hole:
#: legal inside a JSON string, statement terminators inside a pre-ES2019 string literal. Measured
#: rather than assumed — a page carrying both raw was opened in Chromium and there was no failure,
#: because ES2019's JSON-superset proposal made them legal in string literals. So this is a stated
#: discipline being made whole, not an observed breakage, and it is written down at that strength.
#: Escaping them costs nothing: an escaped U+2028 inside a JSON string is the same character, so
#: `test_the_data_survives_the_escape_intact` covers them for free.
#:
#: What is deliberately NOT done is `ensure_ascii=True`. The ledger is full of non-ASCII prose (the
#: preview fixture is largely Italian) and escaping all of it would multiply the page for no reader.
_SCRIPT_UNSAFE = str.maketrans({"<": "\\u003c", "\u2028": "\\u2028", "\u2029": "\\u2029"})


def _inline(value) -> str:
    """A JSON payload safe to sit inside a `<script>` element — the ONLY way data gets there.

    `.replace("</", "<\\/")` closed exactly one of the two ways out of an inline script, and the
    other one blanked the whole page: HTML's script-data tokenizer treats `<!--` followed later by
    `<script` as the start of a *double-escaped* span, in which `</script>` no longer closes
    anything. A pin titled ``A <!--<script> double escape`` therefore swallowed the rest of the
    document — `LEDGER` never got defined, both panes stayed empty, and the page rendered its
    header and nothing else. **No error, no console message: a map that silently shows nothing
    reads as "no findings", which is the worst thing this surface can say.**

    So the escape is not a longer list of dangerous sequences — it is the character all of them
    need. That sentence was true of the HTML hole and said nothing about the second one: U+2028 and
    U+2029 are legal in a JSON string and were statement terminators inside a pre-ES2019 JavaScript
    string literal, and `ensure_ascii=False` emitted them raw. One character per HOLE, and the holes
    are enumerated in `_SCRIPT_UNSAFE` above with what each is.

    **This function is the only path, which is what makes that enumeration worth anything.** Every
    payload the page carries is substituted by `render` from a call to this function — `__DATA__`,
    `__NONCONF__`, `__DERIVED__`, `__WEAK_POLICIES__`, `__SETTLED__` — and `json.dumps` is called
    nowhere else in this module. `tests/test_map.py::TestTheOnlyWayDataEntersThePage` asserts both by AST, because
    the two escaping bugs this file has had were both a SITE that did not go through the mechanism,
    and a fifth payload inlined by hand would be the third.
    """
    return json.dumps(value, ensure_ascii=False).translate(_SCRIPT_UNSAFE)


#: Every placeholder the template carries. `render` substitutes them in ONE pass over the template,
#: so no substitution can ever run over content a previous one inlined.
_PLACEHOLDER_RE = re.compile(
    r"__(?:DATA|NONCONF|SHAPE_WHY|DERIVED|WEAK_POLICIES|REFUTED|SETTLED|REOPENED|ASKABLE|CLAIM_TTL"
    r"|TITLE"
    r"|LIVE_STYLE|LIVE_BADGE|LIVE_SCRIPT)__")


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
    from ledger import (CLAIM_TTL_SECONDS, INTERVIEW_STATES, REOPENED_SUBSTATES,
                        SETTLED_STATES, nonconforming,
                        readable_ledger, shape_notes)
    # v0.23 — the page is rendered from the GUARDED view, never from the file. Two things follow,
    # and they are the whole of this round's map half:
    #
    #  * the page's own JavaScript can no longer be handed an entry the schema does not describe.
    #    `pins.filter(...)` on a string and `p.state` on a `null` both threw inside `trafficLight`,
    #    which runs before anything is mounted, so the document rendered its header and NOTHING —
    #    while `render_map` returned `{"written": …}` with `isError: false`. A blank map reads as
    #    "no findings", which is the most expensive wrong answer this surface can give, and it is
    #    the same failure `_inline` was fixed for one hole over.
    #  * the counts on this page are now the counts `ledger_summary` reports for the same file,
    #    because both read the same carrier. They used to be the raw array lengths.
    #
    # And what the guard DROPPED is stated on the page rather than silently missing (`__NONCONF__`):
    # `nonconforming` is asked of the ORIGINAL, so the banner describes the file as it stands.
    values = {
        # script-safe: no `<` from the data reaches the page's script text at all (`_inline`)
        "__DATA__": _inline(readable_ledger(ledger_data)),
        "__NONCONF__": _inline(nonconforming(ledger_data)),
        # The sentence per DERIVED rule name (v0.25). `PIN_SHAPES` grew from five rules to
        # thirty-one, and hand-writing thirty-one sentences beside a table that derives thirty-one
        # rules is the drift this round exists to remove — so the page inlines the schema's own,
        # exactly as it already inlines `__SETTLED__` and `__ASKABLE__`, and `NONCONF_WHY` keeps
        # only the entries that carry argued prose.
        "__SHAPE_WHY__": _inline(shape_notes()),
        "__DERIVED__": _inline(derived_rungs(ledger_data)),
        "__WEAK_POLICIES__": _inline(weak_policies(ledger_data)),
        # the refutations still STANDING (v0.28). `blocked_by` alone is history and the card used to
        # print it as a verdict, so a resolved pin read "this pin cannot close".
        "__REFUTED__": _inline(refuted_claims(ledger_data)),
        # the schema's own set, so the page cannot fall behind it (v0.16 added `deferred`)
        "__SETTLED__": _inline(list(SETTLED_STATES)),
        # the marks the two reopen arcs and `cross_derive` leave, so a disputed answer cannot read
        # as an elected one on the card that prints it (v0.19)
        "__REOPENED__": _inline(list(REOPENED_SUBSTATES)),
        # the states `interview_view` selects, so the page cannot say what the interview will do
        # with a pin the interview never sees (v0.21)
        "__ASKABLE__": _inline(list(INTERVIEW_STATES)),
        # the TTL the runtime computes staleness against, so this page and `claim_state` cannot
        # disagree about whether the same claim is still live (v0.30)
        "__CLAIM_TTL__": _inline(CLAIM_TTL_SECONDS),
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
