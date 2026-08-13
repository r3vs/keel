# MCP Apps — should this server render a UI, and what would it cost

> **Status: PROPOSAL — `open_decision`, not elected. No implementation in this PR.**
> Written in English, unlike its sibling in this directory, because every fact below was read out of
> an English source and a translation layer between the citation and the claim is one more place for
> them to drift.

This is the design note for adopting the **MCP Apps** extension in `src/mcp/server.py`. It exists
because the question keeps arriving in the wrong shape — *"can we show the interview as a UI?"* —
and the answer turns on four things that are cheap to verify and expensive to assume: what the
extension actually is, which of our hosts render it, what a candidate app would replace, and what
the pending protocol revision does to the machinery underneath.

---

## 1. What MCP Apps is, precisely

Four corrections to the premise this note started from, each read at the source rather than
remembered. **Every one of them changes what the work is.**

| Claim as it usually arrives | What the source says |
|---|---|
| "MCP Apps, SEP-1865" | The **extension identifier is `io.modelcontextprotocol/ui`** — not `apps`. That is the string in the capability object, and it is the string code has to match. Source: [extension support matrix](https://modelcontextprotocol.io/extensions/client-matrix), whose overview table maps *MCP Apps* → `io.modelcontextprotocol/ui`. |
| "spec revision 2026-07-28" | `2026-07-28` is the revision of the **core** protocol. The apps spec is versioned separately in its own repo: the current revision directory is **`specification/2026-01-26`** in [`modelcontextprotocol/ext-apps`](https://github.com/modelcontextprotocol/ext-apps/tree/main/specification), which the apps overview page links directly. Extensions "evolve independently of the core protocol" by design. |
| "it is part of the spec" | It is an **extension**, and extensions are "always disabled by default and require explicit opt-in from the developer". Negotiation is symmetric: the client declares support in `_meta["io.modelcontextprotocol/clientCapabilities"].extensions`, the server in its `server/discover` response's `capabilities.extensions`. |
| "we would have to move the FastMCP pin" | **No.** The pinned `fastmcp==3.4.4` already implements it — see §2. |

The mechanism, in one paragraph. A tool declares `_meta.ui.resourceUri` pointing at a `ui://`
resource; the host may preload that resource before the tool is even called; the resource is an HTML
page which the host renders in a **sandboxed iframe**; the page talks back over `postMessage` in a
JSON-RPC dialect that shares some methods with core MCP (`tools/call`) and adds others under a `ui/`
prefix (`ui/initialize`). `_meta.ui` also carries `csp` (which external origins the page may reach)
and `permissions` (iframe sandbox grants). The app cannot touch the parent DOM, cookies or storage.

## 2. The finding that reframes the decision: we already claim to support it

`src/mcp/server.py` advertises the UI extension **today**, with zero `ui://` resources behind it.
Observed on the wire, not inferred — an `initialize` against the current server answers:

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

There is no branch on whether any app is registered. So the current state is not "we have not
adopted apps"; it is **"we announce apps and serve none"** — an artifact claiming a capability its
bytes do not have, which is this repo's signature bug arriving from upstream. It is low-severity by
luck: a host that trusts the declaration finds no tool carrying `_meta.ui`, so nothing breaks. It
should still be recorded as a `contract_mismatch` pin rather than tidied away in prose, because the
honest options are to *serve* an app or to *stop announcing one*, and only the first is a decision
somebody makes.

**Not fixable by us without a fork.** FastMCP hardcodes it; there is no constructor flag. Suppressing
it would mean overriding `get_capabilities` in a subclass — which is a real option and belongs in the
fork below, not in this note's recommendation.

## 3. Host support — verified, per host, with what the verification is worth

The official matrix is the primary source and it is explicitly **community-maintained** ("If you
notice any inaccuracies… please submit a pull request"). That asymmetry decides how each row is
graded: a check mark is a positive claim somebody made; a blank row is *absence of a claim*, which is
weaker evidence than absence of support. Both are marked as such rather than collapsed into one
column.

| Host | Renders MCP Apps? | Verification |
|---|---|---|
| **claude.ai (web)** | **yes** | VERIFIED — listed with a check in the [client matrix](https://modelcontextprotocol.io/extensions/client-matrix) and named in the [apps overview](https://modelcontextprotocol.io/extensions/apps/overview)'s "Client support" paragraph. |
| **Claude Desktop** | **yes** | VERIFIED — same two sources. |
| **Claude Code (CLI)** | **not listed** | UNVERIFIED-negative. Absent from the matrix; the [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) document resources (`@server:protocol://resource/path`) and prompts (`/mcp__server__prompt`) at length and say nothing about `ui://`, iframes or apps. Two independent silences, neither of them a denial. |
| **Codex** | **not listed** | UNVERIFIED-negative. Absent from the matrix; its MCP page is silent on apps, resources and prompts alike. |
| **opencode** | **not listed** | UNVERIFIED-negative. Absent from the matrix; its MCP docs discuss only tools — "MCP tools are automatically available to the LLM alongside built-in tools" — with no mention of resources, prompts or UI. |
| **Pi** | **no** | VERIFIED, and ours: Pi has no MCP client at all (`docs/packaging.md` records zero `\bmcp\b` matches across the published `dist/`), so the surface is `src/adapters/pi/extensions/mcp-bridge.ts`, which speaks `initialize` / `tools/list` / `tools/call` by hand. Rendering an app would be our code, not Pi's. |
| *(Cursor, ChatGPT, VS Code Copilot, M365 Copilot, Goose, Postman, MCPJam, Archestra.AI, PostHog Code)* | **yes** | VERIFIED — listed. Named here only because Cursor is one of the AGENTS.md-only agents `docs/packaging.md` covers; the rest are not hosts we target. |

**The conclusion that follows, and it is uncomfortable.** *Zero of the four hosts this package ships
to is known to render an MCP App.* The two Claude surfaces that do — web and Desktop — are not where
this server runs: it is spawned by `uv run --script` from a plugin install, in a terminal. So an app
built today would be, on the evidence, invisible to every user we have.

That is an argument about *sequencing*, not about the idea. Two things could change it and both are
outside our control: Claude Code gaining apps support (plausible — it already implements the two
neighbouring primitives, and the matrix is a PR away from being stale in our favour), or the
extension reaching a host we already support. The correct posture is therefore to **keep the
candidates designed and unbuilt**, and to re-read the matrix rather than this paragraph.

## 4. Candidate A — the interview funnel as a decision UI

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
the value never passes through the agent. It is not a *stronger* rung, it is a **better-informed**
one — worth having because `docs/packaging.md` already records that on Claude Code `elicited` means
"the agent did not hold the value", not "a human was looked in the eye" (a hook may answer for
them). An app does not change that, and the note must not claim it does.

**The degradation ladder, which is the whole design.** Three rungs, chosen at runtime by asking the
session — never a per-host table, which is exactly what `_client_can_elicit` was written to avoid:

1. **App** — `ctx.client_supports_extension("io.modelcontextprotocol/ui")`. This is not speculative:
   `fastmcp/server/context.py` already defines `client_supports_extension(extension_id)`, so the
   check has the same shape as the existing capability probe and needs no new machinery.
2. **Elicitation** — `_client_can_elicit(ctx)`, unchanged, sending the enum it sends today.
3. **Transcribed relay** — the agent quotes the human verbatim, recorded as the weaker rung.

Each step down loses presentation and keeps correctness. No step may invent an outcome the pin's
`question` did not offer; the refusals already in `ledger_record_decision` sit below all three.

**The cost that decides feasibility.** FastMCP's prefab components (`fastmcp.apps.choice.Choice`,
`.approval.Approval`, `.form.Form`) would fit this almost exactly — and every one of them opens with
`raise ImportError("Choice requires prefab-ui. Install with: pip install 'fastmcp[apps]'")`. That is
a new dependency in the PEP 723 block, on a server whose whole delivery story is *zero install, one
`uv run --script`, ~7 s cold*. So the honest options are: hand-write the HTML (self-contained, no
`prefab-ui`, consistent with how `map.py` was decided), or accept the extra tree. **Hand-written is
the recommendation**, on the same reasoning that produced `map.py`: build the zero-dependency single
file rather than wrap a framework.

## 5. Candidate B — the visual map as an app

This one is cheaper than it looks, because the artifact already exists. `src/runtime/map.py::render`
emits **one self-contained HTML page**: no build step, no framework, no external fetch, the ledger
data inlined and all CSS/JS embedded — written that way so the output "opens offline and is safe to
hand to anyone". Those are, almost word for word, the constraints an MCP App resource has to satisfy;
`_meta.ui.csp` exists to permit external origins, and this page needs none.

Two shapes, and they are genuinely different decisions:

- **Baked** — a resource template `ui://keel/map/{path*}` that returns `map.render(ledger)` with the
  data already inline. Nearly free: the app is the existing renderer plus a registration. It is a
  snapshot, so it goes stale the moment the ledger is written.
- **Live** — a static shell that calls `ledger_summary` / the `ledger://` resources back through the
  host bridge and re-renders. This is what the existing `render_map(live=True)` registry
  (`tools.py::_register_live_map`, refreshed on every ledger write through `_saved`) already means
  on disk, and an app is the surface where "live" would be true for a viewer rather than for a file.

Start baked. It converts an artifact users currently open by hand into one the conversation shows,
with no new rendering code and no new dependency — and if apps never reach our hosts, nothing was
spent.

## 6. What changes when the pin moves past 2026-07-28

`src/mcp/server.py`'s own header already names this as the reason FastMCP is a dependency rather than
a hand-rolled server, and it lists three changes. Read against the published
[changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), the list is right
but **incomplete in a way that matters to this package specifically**:

| Change | SEP | What it does to us |
|---|---|---|
| `initialize` / `notifications/initialized` removed; MCP is stateless. Every request carries `io.modelcontextprotocol/protocolVersion` and `clientCapabilities` in `_meta` | 2575 | `_client_can_elicit` reads `ctx.session.check_client_capability(...)`, i.e. capabilities captured at handshake. There is no handshake. The probe moves to per-request `_meta` — FastMCP's problem to absorb, ours to re-verify. `tests/test_mcp_server.py::_Session` sends `initialize` explicitly and would need the compatibility path. |
| `server/discover` is mandatory; it carries `supportedVersions`, `capabilities.extensions`, `serverInfo` | 2575 | This is where `io.modelcontextprotocol/ui` is *supposed* to be declared, and where our `version` + `websiteUrl` land. §2's unconditional declaration becomes more visible, not less. |
| Every result carries `resultType` (`"complete"` \| `"input_required"`) | 2322 | Mechanical for us; FastMCP emits it. |
| **Server-initiated requests are replaced by MRTR.** `elicitation/create` gives way to an `InputRequiredResult` (`resultType: "input_required"`) whose `inputRequests` the client answers by **retrying the original request** with `inputResponses` | 2322 | **The big one.** Our flagship human door is a server-initiated `ctx.elicit`. Under MRTR the tool must return, be re-called, and correlate the two — "servers needing to correlate an elicitation across retries encode their own identifier in `requestState`". `ledger_record_decision` is written as one `async` body straddling the ask; that shape does not survive. It is FastMCP's job to hide, and a thing to test rather than trust. |
| `ping`, `logging/setLevel`, `notifications/roots/list_changed` removed; **Logging, Roots and Sampling deprecated** (migration: "log to `stderr` (stdio) or use OpenTelemetry") | 2575, 2577 | The `ctx.info` half of `server.py::_step` is on a deprecation clock, and already constrained: a server **MUST NOT** emit `notifications/message` for a request that did not carry `io.modelcontextprotocol/logLevel`. Progress is untouched. `_step` is the single place that goes. |
| `resources/subscribe` / `unsubscribe` → `subscriptions/listen` | 2575 | We subscribe to nothing (`resources.subscribe: false`). No work — worth knowing before someone builds the "live" map of §5 on subscriptions. |
| `ttlMs` + `cacheScope` **required** on `tools/list`, `prompts/list`, `resources/list`, `resources/read`, `resources/templates/list` | 2549 | Every surface added in this PR is in that list. Library-level, but it is the first protocol change that touches the resources and prompts rather than only the tools. |
| `tools/list` **SHOULD** be deterministically ordered | — | Ours is: every `@mcp.tool` sits at module level, which `tests/test_mcp_server.py` already relies on for set equality. |

**The upgrade is therefore not a version bump plus a shrug.** It is one real refactor (MRTR), one
deletion (`ctx.info`), and a re-verification of the capability probe — and the extension we would be
adopting here is versioned *outside* all of it, on `2026-01-26`, moving on its own schedule.

## 7. What this note does not decide

- **Whether to adopt apps at all.** It is an `open_decision`. §3 says the evidence for building now
  is weak; §2 says the status quo makes a claim we do not honour; those pull in different directions
  and the fork is the human's.
- **Whether to suppress the `io.modelcontextprotocol/ui` declaration** by overriding
  `get_capabilities` until an app exists. Smallest honest fix available, and a fork of its own —
  it makes us diverge from the pinned library's behaviour to say something truer.
- **Which candidate goes first.** B is cheaper (the renderer exists); A is worth more (it upgrades
  the decision surface, which is the package's whole point).

Implementation is a follow-up PR either way. The one thing this note asks to be kept current is
§3: it is a table of somebody else's product decisions, and its shelf life is measured in weeks.
