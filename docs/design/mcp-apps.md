# MCP Apps — should this server render a UI, and what would it cost

> **Status: PARTLY ELECTED (2026-08-13).** Two apps are implemented and served — `src/mcp/apps.py`,
> registered in `src/mcp/server.py`, exercised over real stdio by
> `tests/test_mcp_server.py::TestTheAppsAreServedAndTheClaimIsTrue`. **Neither writes**, which
> reverses §4's own recommendation on evidence gathered while building it (§4a). The protocol bump
> was researched to a decision and the decision is *not yet* (§6). Written in English, unlike its
> sibling in this directory, because every fact below was read out of an English source and a
> translation layer between the citation and the claim is one more place for them to drift.

This is the design note for the **MCP Apps** extension in `src/mcp/server.py`. It exists because the
question keeps arriving in the wrong shape — *"can we show the interview as a UI?"* — and the answer
turns on four things that are cheap to verify and expensive to assume: what the extension actually
is, which of our hosts render it, what a candidate app would replace, and what the pending protocol
revision does to the machinery underneath.

**What changed since the first draft, in one line each.** The mismatch in §2 is closed, by serving
rather than by suppressing. §4's decision UI is built as a **read** surface, because an app turns out
to be unable to earn a provenance rung (§4a) — the single most important thing learned here. §5's
"start baked" is what shipped. §6's migration table was replaced by observations from actually
running the bumped server.

---

## 1. What MCP Apps is, precisely

Four corrections to the premise this note started from, each read at the source rather than
remembered. **Every one of them changes what the work is.**

| Claim as it usually arrives | What the source says |
|---|---|
| "MCP Apps, SEP-1865" | The **extension identifier is `io.modelcontextprotocol/ui`** — not `apps`. That is the string in the capability object, and it is the string code has to match. Source: [extension support matrix](https://modelcontextprotocol.io/extensions/client-matrix), whose overview table maps *MCP Apps* → `io.modelcontextprotocol/ui`. |
| "spec revision 2026-07-28" | `2026-07-28` is the revision of the **core** protocol. The apps spec is versioned separately in its own repo: the current revision directory is **`specification/2026-01-26`** in [`modelcontextprotocol/ext-apps`](https://github.com/modelcontextprotocol/ext-apps/tree/main/specification), which the apps overview page links directly. Extensions "evolve independently of the core protocol" by design. That is why `apps.APPS_PROTOCOL_VERSION` is `2026-01-26` and not the core date — the two live in different fields and conflating them is a silent wrong answer. |
| "it is part of the spec" | It is an **extension**, and extensions are "always disabled by default and require explicit opt-in from the developer". Negotiation is symmetric: the client declares support in `_meta["io.modelcontextprotocol/clientCapabilities"].extensions`, the server in its `server/discover` response's `capabilities.extensions`. |
| "we would have to move the FastMCP pin" | **No.** The pinned `fastmcp==3.4.4` already implements it — see §2 — and the surface we use (`fastmcp/apps/`, `fastmcp/utilities/mime.py`) is byte-identical at `3.4.7`, so the bump buys the app work nothing. |

The mechanism, in one paragraph. A tool declares `_meta.ui.resourceUri` pointing at a `ui://`
resource; the host may preload that resource before the tool is even called; the resource is an HTML
page which the host renders in a **sandboxed iframe**; the page talks back over `postMessage` in a
JSON-RPC dialect that shares some methods with core MCP (`tools/call`) and adds others under a `ui/`
prefix (`ui/initialize`, and the `ui/notifications/*` the host pushes). `_meta.ui` also carries `csp`
(which external origins the page may reach) and `permissions` (iframe sandbox grants). The app
cannot touch the parent DOM, cookies or storage. The resource's MIME type **MUST** be
`text/html;profile=mcp-app` — "other types reserved for future extensions".

## 2. The finding that reframed the decision, and how it was closed

`src/mcp/server.py` advertised the UI extension **with zero `ui://` resources behind it**. Observed
on the wire, not inferred — an `initialize` against the server answered:

```json
"capabilities": {"experimental": {}, "logging": {}, "prompts": {"listChanged": false},
                 "resources": {"subscribe": false, "listChanged": false},
                 "tools": {"listChanged": true},
                 "extensions": {"io.modelcontextprotocol/ui": {}}}
```

The cause is in the dependency, not in our code, and it is unconditional. `fastmcp/server/
low_level.py::get_capabilities` — the function that *builds the value a host receives*, so this is a
consumer citation and not a type — ends with:

```python
return capabilities.model_copy(update={
    "tasks": get_task_capabilities(),
    "extensions": {**existing_extensions, UI_EXTENSION_ID: {}},   # UI_EXTENSION_ID = "io.modelcontextprotocol/ui"
})
```

There is no branch on whether any app is registered. So the state was not "we have not adopted
apps"; it was **"we announce apps and serve none"** — an artifact claiming a capability its bytes do
not have, which is this repo's signature bug arriving from upstream.

**Not fixable by us without a fork, and not fixable by upgrading either.** FastMCP hardcodes it;
there is no constructor flag. The same splice survives into **4.0.0b2**, whose own source calls it
*"unconditional — the SDK's pre-2026 version sieve strips capabilities.extensions on legacy eras, a
known limitation (sdk-feedback #2)"*. That sieve is why the key is **absent** from a legacy
`initialize` on 4.0.0b2 and **present** on a modern `server/discover` — both observed. Upgrading
would have hidden the mismatch on one era and left it on the other.

**So it was closed the other way: by serving.** Two `ui://` resources now exist, which makes the
declaration true. The property is held from the side we control —
`test_the_capability_is_backed_by_something_it_can_point_at` fails if the capability is ever
declared with no `ui://` resource behind it. A gate on the property, rather than prose about it.

## 3. Host support — verified, per host, with what the verification is worth

The official matrix is the primary source and it is explicitly **community-maintained** ("This list
is maintained by the community. If you notice any inaccuracies… please submit a pull request"). That
asymmetry decides how each row is graded: a check mark is a positive claim somebody made; a blank row
is *absence of a claim*, which is weaker evidence than absence of support. Both are marked as such
rather than collapsed into one column.

**Re-read 2026-08-13.** The matrix lists eleven clients with MCP Apps support: Claude (web), Claude
Desktop, VS Code GitHub Copilot, Microsoft 365 Copilot, Goose, Postman, MCPJam, ChatGPT, Cursor,
Archestra.AI, PostHog Code.

| Host | Renders MCP Apps? | Verification |
|---|---|---|
| **claude.ai (web)** | **yes** | VERIFIED — listed with a check in the [client matrix](https://modelcontextprotocol.io/extensions/client-matrix) and named in the [apps overview](https://modelcontextprotocol.io/extensions/apps/overview)'s "Client support" paragraph. |
| **Claude Desktop** | **yes** | VERIFIED — same two sources. |
| **Claude Code (CLI)** | **not listed** | UNVERIFIED-negative. Still absent from the matrix on 2026-08-13; the [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) document resources (`@server:protocol://resource/path`) and prompts (`/mcp__server__prompt`) at length and say nothing about `ui://`, iframes or apps. Two independent silences, neither of them a denial. |
| **Codex** | **not listed** | UNVERIFIED-negative. Absent from the matrix; its MCP page is silent on apps, resources and prompts alike. |
| **opencode** | **not listed** | UNVERIFIED-negative. Absent from the matrix; its MCP docs discuss only tools — "MCP tools are automatically available to the LLM alongside built-in tools" — with no mention of resources, prompts or UI. |
| **Pi** | **no** | VERIFIED, and ours: Pi has no MCP client at all (`docs/packaging.md` records zero `\bmcp\b` matches across the published `dist/`), so the surface is `src/adapters/pi/extensions/mcp-bridge.ts`, which speaks `initialize` / `tools/list` / `tools/call` by hand. Rendering an app would be our code, not Pi's. |
| **Cursor** | **yes** | VERIFIED — listed. Worth naming separately because Cursor is one of the AGENTS.md-only agents `docs/packaging.md` covers, so it is the one surface adjacent to this package where an app would render today. |

**The conclusion that follows, and it is still uncomfortable.** *Zero of the four hosts this package
ships to is known to render an MCP App.* The Claude surfaces that do — web and Desktop — are not
where this server runs: it is spawned by `uv run --script` from a plugin install, in a terminal.

That was an argument for keeping the candidates designed and unbuilt, and it is **no longer the
whole argument**, because §2 changed what building costs. With the capability already announced,
"unbuilt" was not neutral — it was a false claim we were shipping. Serving two read-only documents
costs no new dependency, no new tool, no new write door, and roughly one file; it makes the
declaration true today and it is already correct for whichever of these hosts adds support next.
Re-read this table rather than this paragraph.

## 4. Candidate A — the interview funnel, as a decision UI

**What it would replace.** Today the strong rung of `ledger_record_decision` / `ledger_record_policy`
is an **elicitation**: the server sends one flat string property carrying an `enum`, and the host
draws it (Claude Code: a radio list; Codex: a single-select picker — both traced to the rendering
function in `docs/packaging.md`). It works, and it is thin. What it cannot show is everything that
makes the choice a *decision*: the pin's `as_is`, each option's `implication`, the blast radius a
policy would cascade over, the pins a rule would settle without asking again. Those exist in the
ledger and reach the human only as prose the agent may or may not relay.

**What the app would be.** A `ui://keel/decision.html` resource rendering one open fork: the
question, its options with implications, the current `as_is`, and — for a policy — the list of pins
the rule would decide. The user clicks; the app calls `ledger_record_decision` back through the
host's `tools/call` bridge; the ledger is written by the same door as today.

**The rung it would earn.** Same as elicitation (`evidence: "elicited"`) and for the same reason:
the value never passes through the agent.

**That last paragraph is wrong, and §4a is why.** It is left standing rather than edited away,
because the reasoning that produced it is the reasoning a future session will reproduce.

## 4a. What an app cannot earn — the finding that reversed §4

**An app cannot earn a provenance rung, because this server cannot tell an app's tool call from the
agent's.**

Follow the value. Under the extension the app calls `tools/call` over `postMessage` to the **host**;
the host proxies it onto the same MCP connection the model's calls arrive on. Nothing in the
`tools/call` params carries an origin: not in the apps spec's own request shape, not in what FastMCP
exposes to a tool body. So a value arriving as a tool *argument* is, at the server, indistinguishable
from a value the agent composed — which is the exact definition of the `transcribed` rung.

Claiming `elicited` for it would therefore mean stamping the rung whose entire content is *the agent
did not hold this value* on the agent's own word. That is not a smaller version of the guarantee;
it is the guarantee inverted, on the one field the whole ledger's trustworthiness rests on.

**The extension's own answer does not close it.** `_meta.ui.visibility: ["app"]` looks like an access
control and is not one. Observed on the wire against `fastmcp==3.4.4`: a tool declaring
`visibility: ["app"]` is still returned **in full** by `tools/list`. Hiding it from the model is the
host's choice, so an app-only write tool would be guarded by host cooperation alone — and per §3, on
the hosts this package ships to, by nothing at all. It would be a **new write vector for the agent**,
bought in exchange for a rung nobody can check. `test_no_tool_hides_behind_a_hint_the_host_is_merely_
asked_to_honour` keeps that door shut.

**So what shipped is the honest half.** `ui://keel/interview.html` is linked from `interview_next`
(read-only) and renders the funnel with what the enum cannot carry: each option's implication, the
severity, the downstream fan-out that says which question is worth answering first, and what a pin
is blocked by. It reads; it never elects. The only tool it is wired to call back is `interview_next`
itself.

**The degradation ladder, which is still the whole design — one rung shorter than planned.** Chosen
at runtime by asking the session, never a per-host table, which is exactly what `_client_can_elicit`
was written to avoid:

1. **App** — *presentation only*. The host preloads the resource and pushes the funnel into it.
2. **Elicitation** — `_client_can_elicit(ctx)`, unchanged, sending the enum it sends today.
3. **Transcribed relay** — the agent quotes the human verbatim, recorded as the weaker rung.

Rung 1 no longer sits *above* rung 2 on provenance; it sits *beside* it, and every election still
walks 2→3. `TestAnAppCapableClientEarnsNoStrongerRung` asserts exactly that, from the client shape
most likely to tempt an implementer: UI extension declared, elicitation not.

**The cost that decided the implementation.** FastMCP's prefab components
(`fastmcp.apps.choice.Choice`, `.approval.Approval`, `.form.Form`) would have fit the original plan
almost exactly — and every one opens with `raise ImportError("Choice requires prefab-ui. Install
with: pip install 'fastmcp[apps]'")`. That is a new dependency in the PEP 723 block, on a server
whose whole delivery story is *zero install, one `uv run --script`, ~7 s cold*. Hand-written won, on
the same reasoning that produced `map.py`. The typed metadata models we *do* use (`AppConfig`,
`ResourceCSP`, `UI_MIME_TYPE`) are in the **base** package and need no extra.

## 5. Candidate B — the visual map as an app (shipped, baked)

This one was cheaper than it looked, because the artifact already existed. `src/runtime/map.py::
render` emits **one self-contained HTML page**: no build step, no framework, no external fetch, the
ledger data inlined and all CSS/JS embedded — written that way so the output "opens offline and is
safe to hand to anyone". Those are, almost word for word, the constraints an MCP App resource has to
satisfy; `_meta.ui.csp` exists to permit external origins, and this page needs none.

Two shapes were genuinely different decisions, and **baked** is what shipped:

- **Baked** — a resource template `ui://keel/map/{path*}` returning `map.render(ledger)` with the
  data already inline. Nearly free: the app is the existing renderer plus a registration. It is a
  snapshot, so it goes stale the moment the ledger is written — and because a stale map looks exactly
  like a current one, `apps.map_app` appends a footer that **says** it is a snapshot. That is the
  same reasoning that made `render_map(live=True)` exist in the first place.
- **Live** — a static shell that calls `ledger_summary` / the `ledger://` resources back through the
  host bridge and re-renders. Rejected for now: re-implementing any of `map.py`'s projection in JS
  would be the stateless twin this repo refuses to author, and two surfaces disagreeing about one
  ledger is the divergence the package exists to find, arriving in our own server.

Two mechanics worth keeping. The `{path*}` wildcard is load-bearing for the reason the `ledger://`
templates already record — `build_regex` compiles a bare `{path}` to `(?P<path>[^/]+)`, which matches
no absolute path and fails by not being found, which reads as the user's typo. And the read goes
through `tools.map_app_html` → `_open_existing`, like every other read door, so a missing ledger is
**refused** rather than rendered blank: an empty map reads as "this project has no decisions", which
is the confident wrong answer rendered handsomely.

## 5a. Where the app bytes live, and why it is not an `apps/` directory

`scripts/build.py` vendors the adapter with `for m in sorted((SRC / "mcp").glob("*.py"))` — one
**non-recursive glob over `.py` files**. A `src/mcp/apps/interview.html` would therefore have been
authored here, tested green here, and **absent from the shipped plugin**, leaving the server serving
an app whose body it cannot read. That is the working-directory-sensitive path class
`verify_commands.py` and `tests/test_installed_package.py` exist for, one layer over: a file that
resolves in the authoring tree and nowhere else.

Keeping the documents in `src/mcp/apps.py` removes the class instead of guarding it — the existing
glob carries the module with no change to `build.py` at all, which was confirmed by building and
driving the vendored server. It also follows `map.py`, which holds a far larger page as a Python
string.

One consequence to know before editing: the apps' JavaScript is checked by no linter here. It was
syntax-checked with `node --check` and its render path was exercised against a hostile pin under a
stub DOM while this was built — both **manual**, both unrepeated by CI, and that is a **stated
residual**. What CI does hold is the property those checks were for:
`test_the_interview_app_never_builds_dom_from_a_string` greps the served bytes for every markup sink,
because pin titles and option labels are agent-authored content out of the user's own repo.

## 6. What changes when the pin moves past 2026-07-28

`src/mcp/server.py`'s header names this as the reason FastMCP is a dependency rather than a
hand-rolled server. The migration was researched to a decision on 2026-08-13, by **running** the
bumped server rather than reading its changelog, and the decision is **do not bump yet**.

**The fact that settles it: no stable release speaks 2026-07-28.** `fastmcp==3.4.7` — the latest
stable, published 2026-08-10 — resolves `mcp==1.29.0`, whose `LATEST_PROTOCOL_VERSION` is
`2025-11-25`. Only `4.0.0b2` pulls `mcp==2.0.0` / `2026-07-28`, and it is a **beta**. There is no
lowest-stable-that-speaks-2026-07-28 to choose, so the honest report is that the option does not yet
exist — not a prerelease shipped to everyone who installs from the marketplace.

What was observed while establishing that, kept because it makes the eventual migration cheap:

| Observation | Consequence |
|---|---|
| 4.0.0b2 runs this server's **entire** surface unchanged on a legacy `initialize` — every tool, all `ledger://` templates, all prompts, elicitation end to end | The bump is not an API-breakage cascade. Nothing in `server.py` or `tools.py` had to change to start. |
| On a modern connection, `server/discover` answers with `supportedVersions: ["2026-07-28"]`, `resultType: "complete"`, `ttlMs`, `cacheScope`, and `serverInfo` under `_meta` | SEP-2575/2549/2322's mechanical parts are the library's, exactly as the header predicted. Our `version` and `websiteUrl` arrive correctly. |
| Every modern request **must** carry `_meta` with both `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities`; omitting the second is rejected `-32602` | The stateless handshake is real. A test harness for that era is a different client, not a tweaked one. |
| **`ctx.elicit` raises before touching the wire on a modern connection** — `fastmcp/server/context.py`: *"elicitation via server-initiated requests is unavailable on 2026-07-28 connections"* (SEP-2577 removed the back-channel) | **Was the blocker; the hard-error half is closed** (§6a, 2026-08-13). Driven end to end, `ledger_record_decision` came back `isError` rather than degrading, because `_client_can_elicit` answered True from the client's declared capability and the code then committed to a path the era deleted. It now degrades to the relay rung instead. What the era still costs is the strong rung itself, which is MRTR's row below. |
| The supported replacement is the **guard pattern**: return an `InputRequiredResult` with `input_requests`, read `ctx.input_responses` / `ctx.request_state` when the client retries | A real refactor of the two most carefully tested tools here (`ledger_record_decision`, `ledger_record_policy`), both written as one `async` body straddling the ask. |
| An exact `==` pin on a prerelease resolves under a bare `uv run --script`, with **no** `--prerelease` flag | Mechanically shippable — worth knowing, because the host's command line is fixed in `.mcp.json` and is not ours to change. It removes an excuse, not the objection. |
| `resources/subscribe` → `subscriptions/listen`; we subscribe to nothing | No work — worth knowing before someone builds §5's "live" map on subscriptions. |
| Logging deprecated (SEP-2577, "log to `stderr` (stdio) or use OpenTelemetry"); progress untouched | The `ctx.info` half of `server.py::_step` is the line that goes, and it goes from one place. |

**The order of work, when someone takes it.** Fix `_client_can_elicit` **first** and independently of
any bump: it answers from the client's declared capability alone, so on a modern connection it
promises a door the era has removed and the tool hard-errors instead of degrading to the relay rung
that is sitting right there. That is a correctness bug the day any host negotiates 2026-07-28,
whatever pin we are on. Then MRTR, then the pin.

### 6a. The first step is DONE (2026-08-13), and this is the mechanism

Two layers, because the probe alone would have been a guess about somebody else's protocol and the
backstop alone would have been silent about why:

- **The backstop — `server.py::_ask`, and it is the guarantee.** Every elicitation this server sends
  goes through it, and it turns on one distinction the protocol already draws: **a refusal is a
  VALUE, a missing door is a RAISE.** `DeclinedElicitation`/`CancelledElicitation` are *returned*, so
  they reach the call site untouched and keep the hard refusal v0.29 argued for — degrading on a
  decline converts a human's "no" into an outcome the agent wrote, and `Declined` cannot distinguish
  *no prompt was drawn* from *the human refused*. A raise means nothing was asked, so nothing was
  refused: the tool falls through to the `transcribed` rung exactly as on a client that declared
  nothing, and refuses — naming `option_id`, `human_answer` and the `decide.py` path — only when the
  caller relayed nothing at all. Never `isError` for the unavailability itself.
- **The probe — `_client_can_elicit` now also asks what the session NEGOTIATED**, via
  `_negotiated_era`, which reads `ServerSession.protocol_version` (`mcp>=2.0`) or
  `request_context.protocol_version` (`fastmcp>=4`) where they exist. **At the current pin neither
  does**, and that is stated in the code rather than papered over: `mcp==1.29.0`'s `RequestContext`
  has no such field and its session keeps only `client_params` — the version the client *asked* for.
  So the last branch re-derives the negotiated value with the library's own expression
  (`requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION`,
  `mcp/server/session.py::_received_request`). The era set is `mcp_types.version.
  MODERN_PROTOCOL_VERSIONS` where importable — the same table `fastmcp>=4`'s own
  `_is_modern_protocol` compares against — and the literal `2026-07-28` until that module exists.

Two findings worth keeping, each of which changed the code:

1. **The classifier is an allowlist, and it has to be.** The first draft caught `Exception`, which
   swallowed the opposite fact: a `list[str]` response type compiles to an enum schema, so a reply
   *outside* the enum raises pydantic's `ValidationError` out of `handle_elicit_accept` — **after**
   the human answered. Degrading there replaced the user's real answer with the option the caller
   proposed. `_no_question_was_put()` now names the classes that mean no answer arrived
   (`ToolError`, plus `McpError` **and** `MCPError` — `mcp==2.0.0` renames that class with no alias,
   so one spelling goes blind at the very pin this fix is for), and
   `test_an_answer_outside_the_offered_choices_leaves_the_pin_open` is what fails if it widens again.
2. **The era branch is unreachable from this repo's tests, and that is declared rather than faked.**
   No stable release speaks 2026-07-28, so `tests/test_mcp_server.py` drives the same *class* through
   the door that is reachable — a client that declares elicitation and answers `elicitation/create`
   with a JSON-RPC error — and asserts the degradation, the two refusals that must not move, and
   that an era the library cannot speak is negotiated *down* rather than routed around. The two
   properties the wire cannot check (the probe still being consulted; no `ctx.elicit` outside `_ask`)
   are held by AST, the way `test_human_door.py` quantifies the `elicited` rung over its callers.

What this does **not** do is MRTR's guard pattern. On a modern connection the strong rung is simply
gone and every decision lands as `transcribed` or goes through `decide.py`; the refactor that gets
it back — `InputRequiredResult` + `ctx.input_responses` — is still step two, and it is now a
capability upgrade rather than a bug fix.

## 7. What this note still does not decide

- **Whether an app should ever hold a write door.** §4a says it cannot hold one *and* claim a
  provenance rung, which is a narrower claim than "never". If a host ever exposes a verifiable
  app-origin marker, the fork reopens — and it reopens as a question about that host's guarantee,
  not about our preference.
- **Whether to keep the `io.modelcontextprotocol/ui` declaration honest by our own hand.** It is true
  today because we serve apps, not because we control it. If both apps were ever removed, the
  mismatch returns and the fix would be overriding `get_capabilities` in a subclass — diverging from
  the pinned library to say something truer. The gate in §2 is what would tell us.
- **Whether a host offers TEMPLATE `ui://` resources anywhere a human can reach them.** Same
  UNVERIFIED residual the `ledger://` templates already carry: where a host lists only concrete
  resources, `ui://keel/map/{path*}` is reachable by typing the URI and not by picking it. The
  interview app is concrete and does not share the problem.
- **When to bump.** §6 says not yet and says what would change it: a stable release that speaks
  2026-07-28. The elicit refactor is worth doing before that lands, not with it.

The one thing this note asks to be kept current is §3: it is a table of somebody else's product
decisions, and its shelf life is measured in weeks.
