"""The two MCP Apps this server serves, as `ui://` documents.

Why this file exists at all: the server was **claiming** the apps extension
--------------------------------------------------------------------------
`fastmcp/server/low_level.py::get_capabilities` — the function that builds the value a host
receives, so this is a consumer citation and not a type — ends by splicing
``UI_EXTENSION_ID: {}`` into ``capabilities.extensions`` with no branch on whether any app is
registered. So an `initialize` against this server has always answered
``"extensions": {"io.modelcontextprotocol/ui": {}}`` while serving zero ``ui://`` resources: an
artifact claiming a capability its bytes do not have, which is this repo's signature failure
arriving from upstream. `docs/design/mcp-apps.md` recorded it as a `contract_mismatch` with two
honest exits — serve an app, or stop announcing one — and noted that only the first is a decision
somebody makes. This file is that decision. The declaration is now **true**, and
`tests/test_mcp_server.py::TestTheAppsAreServedAndTheClaimIsTrue` is what keeps it true: it fails
if the capability is ever declared with no `ui://` resource behind it.

Worth stating plainly, because the bump was researched and rejected on it: moving the pin does not
fix this. FastMCP **4.0.0b2**'s own source calls the same splice *"unconditional — the SDK's
pre-2026 version sieve strips capabilities.extensions on legacy eras, a known limitation"*, and it
was observed on the wire at `server/discover` on a 2026-07-28 connection. Serving the resources is
the only thing that closes it at any pin.

Why the documents live in a .py file rather than an `apps/` asset directory
--------------------------------------------------------------------------
`scripts/build.py` vendors the adapter with ``for m in sorted((SRC / "mcp").glob("*.py"))`` — one
non-recursive glob over `.py` files. A `src/mcp/apps/decision.html` would therefore be **authored,
tested green here, and absent from the plugin**, so the shipped server would serve an app whose
body it cannot read. That is precisely the working-directory-sensitive path class
`verify_commands.py` and `tests/test_installed_package.py` exist for, one layer over: a file that
resolves in the authoring tree and nowhere else. Keeping the bytes in a module the existing glob
already carries removes the class instead of guarding it, and it follows `map.py`, which holds a
far larger page as a Python string for its own reasons.

What each app is, and the one thing neither of them does
--------------------------------------------------------
Neither app writes. That is a finding, not a simplification, and it reverses the plan
`docs/design/mcp-apps.md` §4 recommended — see that file's *"What an app cannot earn"* for the
evidence. The short form: under the apps extension an app's `tools/call` is proxied by the host and
arrives over the same MCP connection as the model's, with no field distinguishing the two, so a
server **cannot** verify that a value came from the app rather than from the agent. An app-elected
outcome would therefore have to claim `elicited` — the rung whose entire content is *the agent did
not hold this value* — on the agent's word. The extension's own answer, ``visibility: ["app"]``, is
a hint the host is asked to honour and not an enforcement: observed on the wire, a tool declaring
it is still served in full to everyone by `tools/list`. So an app-only write door would be a new
write vector for the agent on any host that ignores the hint, in exchange for a rung nobody can
check — and, per §3, on zero of the four hosts this package ships to.

What is left is worth having and is honest: the apps upgrade **presentation**, which is exactly
what the degradation ladder was always allowed to lose. The election itself keeps the ladder it
already had.

- ``ui://keel/interview.html`` — the funnel as a **read** surface, linked from `interview_next`.
  The elicitation prompt can carry one flat string with an `enum`; this carries what makes the
  choice a decision: each option's implication, the severity, the downstream fan-out one answer
  unblocks, what a pin is blocked by, and the brainstorm's proposals. Those all exist in the ledger
  today and reach the human only as prose the agent may or may not relay.
- ``ui://keel/map/{path*}`` — the visual map, baked. `map.py::render` already emits one
  self-contained page with the ledger inlined and no external fetch, written that way so the output
  "opens offline and is safe to hand to anyone" — which is, nearly word for word, what a `ui://`
  resource has to satisfy. So this app is the existing renderer plus a registration, it costs no
  new rendering code and no new dependency, and the page never enters the model's context the way
  wrapping it in a tool result would.

Untrusted content, and why the JS in THIS file never touches innerHTML
----------------------------------------------------------------------
Every string these apps render — pin titles, option labels, implications — is agent-authored
content out of somebody else's repo. `map.py` learned this twice (its `esc` did not escape; then a
chained-`replace` pass let inlined content be rewritten by a later substitution) and both times the
lesson was that **inlining is the dangerous step**, so the guarantee belongs at the step rather
than in the order of the lines around it.

The two documents reach it by two different routes, and saying otherwise was a rule true of one
side of a pairing. **The interview app**, whose JS lives here, takes the step out of play: data
arrives at runtime and goes in through `textContent` only, there is no `innerHTML` in this file,
and `test_the_interview_app_never_builds_dom_from_a_string` fails if one appears. **The map app**
is `map.py`'s page, which has exactly one sink (`mount`) fed only by a tagged template that escapes
everything not already an assembled fragment; that count and that exclusivity are asserted in
`tests/test_map.py`, and `test_the_map_apps_wrapper_adds_no_second_markup_sink` holds the served
bytes to the same one sink after `map_app` splices its note in. Two mechanisms, two gates, each
named where it applies.

What IS true of both, and is asserted of both, is self-containment: neither document fetches, links
or imports anything, which is what the shared `connectDomains: []` / `resourceDomains: []` in
`server.py::_APP_CSP` declares to the host on their behalf.
"""

#: The concrete app, linked from `interview_next` via `_meta.ui.resourceUri`.
INTERVIEW_URI = "ui://keel/interview.html"

#: The baked map, as a resource TEMPLATE. `{path*}` and not `{path}` for the reason the ledger://
#: templates carry: FastMCP's `build_regex` compiles a bare `{path}` to `(?P<path>[^/]+)`, which
#: matches no absolute path at all, and fails by not being found — which reads as the user's typo.
MAP_URI_TEMPLATE = "ui://keel/map/{path*}"

#: The one MIME type the extension admits: *"MUST be 'text/html;profile=mcp-app' (other types
#: reserved for future extensions)"*.
#:
#: **Nothing passes this to the wire, and that is the point.** `server.py` fills both apps' mime
#: from `fastmcp/utilities/mime.py::resolve_ui_mime_type` — the static app implicitly, through the
#: `@mcp.resource` decorator, and the templated one explicitly in `_ui_document`, because
#: `ResourceTemplate.convert_result` drops what the decorator resolved. So the listing and the read
#: derive one value from one SDK function, and the tests assert what a host RECEIVES against a third
#: literal of their own. This constant is the spec quote, kept for the reader; a consumer of it
#: would be a second copy of a value the SDK owns, which is the drift `_ui_document` exists to avoid.
UI_MIME_TYPE = "text/html;profile=mcp-app"

#: The apps spec revision these documents speak, sent as `ui/initialize`'s `protocolVersion`. It is
#: deliberately NOT the core revision: extensions "evolve independently of the core protocol", and
#: `modelcontextprotocol/ext-apps` versions this one in `specification/2026-01-26`. Conflating the
#: two is how the core protocol's date ends up in a field that means something else.
APPS_PROTOCOL_VERSION = "2026-01-26"


# The postMessage bridge, shared by both documents.
#
# The transport is `window.parent.postMessage`, and the dialect is JSON-RPC: some methods are core
# MCP (`tools/call`), some are the extension's (`ui/initialize`, and the `ui/notifications/*` the
# host pushes). Hand-written rather than taken from `@modelcontextprotocol/ext-apps`, for the same
# reason `map.py` is hand-written and for one more: a CDN import is a fetch, and a `ui://` document
# that fetches needs a `csp.resourceDomains` entry — so a convenience wrapper would cost this app
# the property that makes it safe to render, which is that it reaches nothing.
#
# `ui/initialize` is a REQUEST (it has a result); `ui/notifications/initialized` is the
# notification that follows it, and both are sent by the view. Everything degrades: a document
# opened where no host answers must say so rather than sit blank, which is why `boot` races the
# handshake against a timer and renders a stated fallback instead of a spinner nobody can read.
_BRIDGE = r"""
var RPC = {}, seq = 1;
function post(msg){ try { parent.postMessage(msg, '*'); } catch (e) { /* no host */ } }
function call(method, params){
  var id = seq++;
  post({ jsonrpc:'2.0', id:id, method:method, params:params||{} });
  return new Promise(function(res, rej){
    RPC[id] = { res:res, rej:rej };
    setTimeout(function(){ if (RPC[id]) { delete RPC[id]; rej(new Error('no answer from the host')); } }, 15000);
  });
}
function notify(method, params){ post({ jsonrpc:'2.0', method:method, params:params||{} }); }

// The host answers requests and pushes notifications down the same channel.
var ON = {};
addEventListener('message', function(ev){
  var m = ev.data;
  if (!m || m.jsonrpc !== '2.0') return;
  if (m.id !== undefined && RPC[m.id]) {
    var p = RPC[m.id]; delete RPC[m.id];
    return m.error ? p.rej(new Error(m.error.message || 'host error')) : p.res(m.result);
  }
  if (m.method && ON[m.method]) ON[m.method](m.params || {});
});

function boot(name, onReady, onFail){
  call('ui/initialize', {
    appCapabilities: { availableDisplayModes: ['inline', 'fullscreen'] },
    clientInfo: { name: name, version: '1' },
    protocolVersion: '__APPS_PROTOCOL_VERSION__'
  }).then(function(result){
    notify('ui/notifications/initialized', {});
    onReady(result || {});
  }).catch(function(err){ onFail(err); });
}

// Theme is the host's to state; `hostContext.theme` arrives in the handshake result. Absent, the
// document follows the viewer's own `prefers-color-scheme` and nothing has to be guessed.
function applyTheme(ctx){
  var t = ctx && ctx.hostContext && ctx.hostContext.theme;
  if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
}
"""


_INTERVIEW_CSS = r"""
:root{
  --bg:#fbfbfa; --fg:#1a1a18; --mut:#6b6b66; --line:#e2e1dd; --card:#fff;
  --accent:#3a5f8a; --blocker:#8a2f2f; --high:#8a5a1f; --med:#5a5a52; --low:#6b6b66;
}
:root[data-theme="dark"]{
  --bg:#16161a; --fg:#e8e8e4; --mut:#9a9a94; --line:#2c2c32; --card:#1e1e24;
  --accent:#8fb4de; --blocker:#e08a8a; --high:#dcb277; --med:#a5a59c; --low:#9a9a94;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#16161a; --fg:#e8e8e4; --mut:#9a9a94; --line:#2c2c32; --card:#1e1e24;
    --accent:#8fb4de; --blocker:#e08a8a; --high:#dcb277; --med:#a5a59c; --low:#9a9a94;
  }
}
*{box-sizing:border-box}
body{margin:0;padding:18px;background:var(--bg);color:var(--fg);
  font:14px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:14px}
h1{font-size:15px;margin:0;letter-spacing:.01em}
.sub{color:var(--mut);font-size:12.5px}
button{font:inherit;font-size:12.5px;padding:5px 11px;border:1px solid var(--line);
  border-radius:7px;background:var(--card);color:var(--fg);cursor:pointer}
button:hover{border-color:var(--accent)}
button:disabled{opacity:.5;cursor:default}
.note{border:1px solid var(--line);border-left:3px solid var(--accent);background:var(--card);
  border-radius:7px;padding:11px 13px;color:var(--mut);font-size:13px;margin-bottom:14px}
.q{border:1px solid var(--line);background:var(--card);border-radius:9px;padding:13px 15px;
  margin-bottom:11px}
.qh{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin-bottom:3px}
.t{font-weight:600}
.sev{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.sev-blocker{color:var(--blocker)} .sev-high{color:var(--high)}
.sev-medium{color:var(--med)} .sev-low{color:var(--low)}
.id{color:var(--mut);font-size:11.5px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.prompt{margin:7px 0 9px}
.fan{color:var(--mut);font-size:12px}
.sect{margin-top:10px;font-size:11.5px;font-weight:700;letter-spacing:.05em;
  text-transform:uppercase;color:var(--mut)}
ul{margin:8px 0 0;padding:0;list-style:none}
li{padding:7px 0 7px 13px;border-left:2px solid var(--line);margin-bottom:5px}
li .lab{font-weight:550}
li .imp{color:var(--mut);font-size:12.5px;display:block;margin-top:2px}
.tag{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:20px;
  padding:1px 8px;color:var(--mut);margin-left:6px}
.blocked{color:var(--blocker);font-size:12.5px;margin-top:6px}
.empty{color:var(--mut);padding:22px 0;text-align:center}
"""


_INTERVIEW_JS = r"""
var elFunnel = document.getElementById('funnel');
var elState  = document.getElementById('state');
var elLedger = document.getElementById('ledger');
var elRefresh = document.getElementById('refresh');
var LEDGER = null;

function el(tag, cls, text){
  var n = document.createElement(tag);
  if (cls) n.className = cls;
  // `textContent` and no markup sink, ever. Every string below is agent-authored content out of
  // the user's own repo; this is the one line that makes that safe, so it is the only way text
  // gets in. (The sink names are spelled out nowhere in this document on purpose — the test that
  // forbids them greps the served bytes, and a comment naming one would defeat its own gate.)
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}

function say(msg){ elState.textContent = msg; }

function renderEntry(q){
  var card = el('div', 'q');
  var head = el('div', 'qh');
  head.appendChild(el('span', 't', q.title || '(untitled pin)'));
  var sev = String(q.severity || 'low').toLowerCase();
  head.appendChild(el('span', 'sev sev-' + (/^(blocker|high|medium|low)$/.test(sev) ? sev : 'low'), sev));
  head.appendChild(el('span', 'id', q.pin_id || ''));
  card.appendChild(head);

  if (q.prompt) card.appendChild(el('div', 'prompt', q.prompt));

  // The fan-out is the number that makes one question worth answering before another, and the
  // enum elicitation has nowhere to put it.
  if (typeof q.downstream === 'number' && q.downstream > 0)
    card.appendChild(el('div', 'fan', q.downstream + ' pin(s) downstream wait on this answer'));

  if (q.blocked_by) card.appendChild(el('div', 'blocked', 'blocked by: ' + q.blocked_by));

  // The fork's own options, and then the brainstorm's proposals. Two lists and not one, because
  // they are two different things: an option is something this pin OFFERS as an outcome (the
  // carrier the offered-options rule anchors on), a proposal is something an agent suggested and
  // nobody elected. Merging them would put an unelected suggestion in the menu a human chooses
  // from, which is the offered-options rule dismantled in the presentation layer.
  var opts = q.options || [];
  if (opts.length){
    var ul = el('ul');
    opts.forEach(function(o){
      var li = el('li');
      li.appendChild(el('span', 'lab', (o.label || o.id || '')));
      // The implication is the half that turns an option into a decision, and it is exactly what
      // a flat enum row cannot carry.
      if (o.implication) li.appendChild(el('span', 'imp', o.implication));
      ul.appendChild(li);
    });
    card.appendChild(ul);
    if (q.allow_freeform)
      card.appendChild(el('div', 'fan', 'an answer in the human’s own words is allowed here'));
  }

  var props = q.proposals || [];
  if (props.length){
    card.appendChild(el('div', 'sect', 'brainstorm proposals — suggested, not offered'));
    var pl = el('ul');
    props.forEach(function(p){
      var li = el('li');
      li.appendChild(el('span', 'lab', (p.summary || p.id || '')));
      if (p.effort) li.appendChild(el('span', 'imp', 'effort: ' + p.effort));
      if (p.recommended) li.appendChild(el('span', 'tag', 'recommended'));
      pl.appendChild(li);
    });
    card.appendChild(pl);
  }

  if (q.already_elected && q.already_elected.outcome)
    card.appendChild(el('div', 'blocked', 'already elected: ' + q.already_elected.outcome +
                        ' — back on this list because ' + (q.pin_state || 'the pin reopened')));
  return card;
}

function render(view){
  elFunnel.replaceChildren();
  var asked = (view && (view.asked || view.questions)) || [];
  if (!asked.length){
    elFunnel.appendChild(el('div', 'empty', 'No open questions in this funnel.'));
    return;
  }
  asked.forEach(function(q){ elFunnel.appendChild(renderEntry(q)); });
}

// The funnel arrives one of two ways, and both are the host's to give: pushed as the result of the
// `interview_next` call the model just made, or fetched by this app through the host's tools/call
// proxy when the reader asks for it again.
function adopt(payload){
  if (!payload) return;
  var view = payload.structuredContent || payload;
  if (payload.arguments && payload.arguments.ledger) { LEDGER = payload.arguments.ledger; }
  if (view && (view.asked || view.questions)) {
    render(view);
    say('');
    elLedger.textContent = LEDGER ? LEDGER : '';
  }
}

ON['ui/notifications/tool-input'] = function(p){
  var a = (p && p.arguments) || {};
  if (a.ledger) { LEDGER = a.ledger; elLedger.textContent = LEDGER; }
};
ON['ui/notifications/tool-result'] = function(p){ adopt(p && (p.result || p)); };

// Read-only by construction: the ONLY tool this app is wired to call is `interview_next`, which
// is annotated readOnlyHint. Nothing here can elect, record or resolve anything — see this
// module's docstring for why an app may not hold the write door.
function refresh(){
  if (!LEDGER) { say('waiting for a ledger path from the host'); return; }
  elRefresh.disabled = true;
  say('reading the funnel...');
  call('tools/call', { name:'interview_next', arguments:{ ledger: LEDGER } })
    .then(function(r){ adopt(r); })
    .catch(function(e){ say(e.message); })
    .then(function(){ elRefresh.disabled = false; });
}
elRefresh.addEventListener('click', refresh);

boot('keel-interview', function(ctx){
  applyTheme(ctx);
  say('ready — waiting for the funnel');
}, function(err){
  // Degradation, stated. A document opened outside a host that speaks the extension is still a
  // readable page; what it must not do is pretend to be connected.
  say('no MCP Apps host answered (' + err.message + '). This view is read-only either way; the '
      + 'interview still runs through the server: elicitation where the host supports it, a '
      + 'transcribed relay where it does not.');
});
"""


_MAP_NOTE_CSS = r"""
#keel-app-note{position:fixed;left:0;right:0;bottom:0;z-index:2147483647;
  font:12px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  padding:6px 12px;text-align:center;color:#6b6b66;background:rgba(251,251,250,.94);
  border-top:1px solid #e2e1dd}
@media (prefers-color-scheme: dark){
  #keel-app-note{color:#9a9a94;background:rgba(22,22,26,.94);border-top-color:#2c2c32}
}
"""


def interview_app() -> str:
    """The interview funnel as a read surface — one self-contained document, no external fetch."""
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>Keel — the interview funnel</title>\n"
        f"<style>{_INTERVIEW_CSS}</style>\n"
        "</head><body>\n"
        "<header><h1>Open decisions, best-first</h1>"
        '<span class="sub" id="ledger"></span>'
        '<button id="refresh" type="button">Re-read</button></header>\n'
        '<div class="note">This view reads. It never elects — only the human\'s committed answer '
        "does, recorded by the server through <code>ledger_record_decision</code>. What it adds to "
        "the enum the host would otherwise draw is the part that makes a fork a decision: each "
        "option’s implication, the severity, and how many pins one answer unblocks.</div>\n"
        '<div class="sub" id="state">connecting to the host…</div>\n'
        '<div id="funnel"></div>\n'
        f"<script>{_BRIDGE.replace('__APPS_PROTOCOL_VERSION__', APPS_PROTOCOL_VERSION)}"
        f"{_INTERVIEW_JS}</script>\n"
        "</body></html>\n"
    )


def map_app(page: str) -> str:
    """Wrap `map.py`'s already-self-contained page as an app document.

    The page is passed in rather than rendered here: `apps.py` holds documents and knows nothing
    about ledgers, and the guarded read belongs with every other guarded read, in `tools.py`. All
    this adds is a footer stating what the reader is looking at — a **snapshot**, taken when the
    resource was read. Saying so is not decoration: `render_map(live=True)` exists precisely
    because a map that has gone stale looks exactly like one that has not, and an app the host may
    keep on screen across later ledger writes is the surface where that costs most.
    """
    note = (
        f"<style>{_MAP_NOTE_CSS}</style>"
        '<div id="keel-app-note">Snapshot of the ledger as it was when this view was read — '
        "re-read the resource after a write.</div>"
    )
    lower = page.lower()
    end = lower.rfind("</body>")
    if end == -1:
        end = lower.rfind("</html>")
    return page if end == -1 else page[:end] + note + page[end:]
