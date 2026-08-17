# Packaging — agent-agnostic by design

The skills are authored **once** to the [Anthropic Agent Skills specification] and run across
agents through thin per-platform adapters. Nothing skill-specific is duplicated per platform.

```
authored once (src/, never ships)          generated per host (plugins/, the only output)
------------------------------             ------------------------------------------------
src/skills/<name>/SKILL.md                 .claude-plugin/plugin.json     Claude Code
src/core/*.md        shared spine          .codex-plugin/plugin.json      Codex
src/core/agents.md   agent roster          agents/*.md  commands/  hooks/hooks.json
src/runtime/         the engine            .mcp.json                      MCP (Claude + Codex)
src/mcp/             its MCP adapter       adapters/opencode/{agent,command,plugin}/
src/agents|commands|hooks|adapters/        adapters/pi/extensions/
AGENTS.md            cross-agent entry     skills/<name>/  (doctrine + runtime vendored inside)
```

## Why this works everywhere

- **`skills/<name>/SKILL.md`** uses the Agent Skills frontmatter (`name` `^[a-z0-9-]+$` matching
  the directory, `description` ≥ 20 chars, optional `license`/`allowed-tools`). Claude Code loads
  these natively; **opencode** discovers them via the `opencode-skills` plugin (Agent Skills spec).
- **`AGENTS.md`** at the repo root is the emerging cross-agent instructions file — read by opencode
  (and Cursor, Codex, …). It is deliberately short (loaded as always-on context); the depth lives
  behind the skills.
- **`core/agents.md`** defines the agent roster once; each adapter materializes it natively.

## Install

**The user installs into their own project.** That sentence is the whole design constraint, and
getting it wrong is what this document used to do: it told Cursor and Codex users to *"open the
repo"* and copy MCP servers out of a `.mcp.json` at **our** root. That is not installing a plugin —
it is cloning a demo, and it meant two of four hosts had no delivery mechanism at all. Root host
config (`.mcp.json`, `opencode.json`, `.codex/config.toml`) is therefore **gone**; anything a user
needs is delivered by the install, and `tests/test_mcp_declaration.py` keeps it that way.

**Claude Code** — add the marketplace, then the plugin:
```
/plugin marketplace add r3vs/keel
/plugin install codebase-rescue@keel
```
`keel-core` follows automatically via `dependencies`. Skills, `agents/`, `commands/`
(`/rescue`, `/forge`), the hooks and the MCP servers all load from the plugin root.

**Codex** — same marketplace, one difference that matters:
```
codex plugin marketplace add r3vs/keel
codex plugin install codebase-rescue
codex plugin install keel-core     # Codex has no `dependencies` — install the core explicitly
```

**opencode / Pi** — neither has a plugin manifest, so their pieces are generated into
`plugins/keel-core/adapters/` (a directory Claude Code ignores) and a script places them:
```
git clone https://github.com/r3vs/keel && cd keel
python scripts/build.py && bash scripts/install.sh
```
Skills go to `~/.agents/skills` (both hosts auto-discover it); the roster, the commands, the ledger
gate and the MCP servers go to `~/.config/opencode/` and `~/.pi/agent/`. Everything is symlinked
into the clone, so keep it — a rebuild then needs no reinstall.

## MCP servers

**Delivery is the install, on every host that can take it — there is no block to copy.** The servers
are generated from the table in `src/core/knowledge-sources.md`: the doctrine that *orders* the agent
to ground its claims in them is the thing entitled to name them, so a server cannot be mandated in
prose and missing from the product.

| Host | How it arrives | Shape |
|---|---|---|
| **Claude Code** | `.mcp.json` at the plugin root, read on install | `type: stdio` / `http` |
| **Codex** | the same file — its manifest's `mcpServers: "./.mcp.json"` points at it | same |
| **opencode** | a `config(cfg)` hook in the placed plugin mutates the live merged config | `type: local` / `remote`, `command` is an **array**, `environment` (not `env`) |
| **Pi** | no native MCP — our own extension bridges it (`adapters/pi/extensions/mcp-bridge.ts`) | hand-rolled JSON-RPC over stdio; a proxy tool `alignment`; **no `@modelcontextprotocol/sdk`** |

Host facts verified **at the function that consumes the value**, not inferred, and none guessable
from the others:

- **The Pi bridge is a loose `.ts`, deliberately dependency-free.** Pi's jiti allowlist excludes
  `@modelcontextprotocol/sdk`, so using the SDK would force the bridge into an npm sub-package inside
  Pi's shared dependency tree — reintroducing the exact `ERESOLVE` that makes `nicobailon/pi-mcp-adapter`
  unusable (its open issue #176). **That last clause is now stale and carries no current
  verification**: the 2026-08-06 elicitation audit found the adapter importing
  `@modelcontextprotocol/client`, not `@modelcontextprotocol/sdk`, and did not re-run the resolution.
  The jiti-allowlist half stands on its own; do not lean on "pi-mcp-adapter is unusable" to justify
  anything without re-checking it. So `mcp-bridge.ts` speaks the protocol by hand (initialize →
  tools/list → tools/call, newline-delimited, mirroring `tests/test_mcp_server.py`), spawns the
  vendored `../../../mcp/server.py` via `uv run`, registers ONE proxy tool `alignment` synchronously,
  connects lazily, and fails open. `install.sh` symlinks it, keeping that relative link intact — the
  same trick opencode's `mcp.ts` uses.
- **Codex needs the `./`.** `resolve_manifest_mcp_servers` → `resolve_manifest_path`, which does
  `path.strip_prefix("./")` and returns `None` + a `tracing::warn` otherwise. This doc used to cite
  `PluginManifestMcpServers::Path` as the verification — the type that *holds* the value, which
  accepts any `String`. That citation is how `".mcp.json"` shipped for months. (Its severity was
  low: `plugin_mcp_config_paths` falls back to `<root>/.mcp.json`, so the declaration was inert
  rather than fatal. **`commands` has no such fallback** — declaring it without `./` is strictly
  worse than omitting it.)
- **opencode's discriminator is `local`/`remote`**, not Claude's `stdio`/`http` — and it is
  *ternaried*, not switched (`mcp.type === "remote" ? connectRemote : connectLocal`), so `"stdio"`
  is silently treated as **local**, then `const [cmd, ...args] = mcp.command` destructures the
  string `"npx"` into `cmd="n"`, `args=["p","x"]` → ENOENT. Valid JSON, no error, no server.
- **`enabled` defaults to ON** (`if (mcp.enabled === false)` — strict). Absence is not "off".
- **Nothing validates what a plugin writes into `cfg.mcp`.** File-borne config hard-fails through
  `ConfigParse.schema`; plugin-borne config bypasses it entirely and degrades to
  `logWarning("server unavailable")`. If our emitted shape ever goes wrong, CI stays green and the
  user gets a plugin that installs and declares nothing — the exact Codex signature, in a place no
  gate of ours currently watches.
- **`${CLAUDE_PLUGIN_ROOT}`** is a Claude-ism. opencode's `ConfigVariable.substitute` expands
  exactly `{env:VAR}` and `{file:path}`; an unknown `${...}` passes through **literal**, producing a
  nonexistent path rather than an error. So the opencode plugin resolves our server from
  `import.meta.url` instead. On Claude Code it does expand inside `.mcp.json` — officially, in a
  stdio server's `command`, `args` and `env`, which is exactly how we use it.

**What ships**: `context7` (live library/framework docs) and `deepwiki` (public-repo exemplars) —
the two servers `core/knowledge-sources.md` requires.

**What is named but deliberately NOT declared**: `cognee` and `github`. Each needs external setup —
a container plus an `LLM_API_KEY`, a token — and a declared-but-unreachable server is a broken entry
in *every* user's session, which is the opposite of the doctrine's own "degrade gracefully, never
hard-fail". Both root configs used to declare cognee `enabled: true`, which could only ever have
worked on the machine that wrote them.

**Cognee memory is opt-in and has a setup cost** (unlike the old zero-config `server-memory`): it
is served by the `cognee/cognee-mcp` Docker container and runs its own LLM extraction, so start the
container and give it a key, then add it to **your own** MCP config:
```
# .env holds LLM_API_KEY=sk-...
docker run -e TRANSPORT_MODE=http --env-file ./.env -p 8000:8000 --rm -it cognee/cognee-mcp:main
```
```json
{ "mcpServers": { "cognee": { "type": "http", "url": "http://localhost:8000/mcp" } } }
```
Prefer **deliberate writes** (`cognee.remember("…")`) over conversational auto-capture, so the graph
stays curated. If you don't want the container + key, skip it — the ledger + `MEMORY.md` cover
durable memory without it.

## The tool surface is a budget, and it is the host's to spend

**The assumption this package has been relying on silently, now written down: 69 MCP tools is
affordable only because the host defers them.** Nothing in `src/mcp/server.py` decides that, nothing
gates it, and it is false on at least one host we ship to. Naming it is the point of this section —
it is a load-bearing bet on somebody else's product behaviour, which is the class of fact this repo
insists on verifying at the consumer.

**What the surface actually costs, measured rather than estimated.** Start the server, complete the
handshake, and size the `tools/list` result:

| | |
|---|---|
| tools advertised | **69** |
| whole `tools/list` result | ~101 k characters of JSON — **≈25 k tokens** at ~4 chars/token |
| median tool object | ~1,410 characters (the JSON: name + description + `inputSchema` + annotations) |
| longest single description | 1,405 characters |
| server `instructions` | 335 characters |

Method, because a number in prose with no way to re-derive it is the thing
`scripts/check_stated_facts.py` exists to prevent: spawn `uv run --script src/mcp/server.py`, send
`initialize` + `notifications/initialized` + `tools/list` over stdio (the harness in
`tests/test_mcp_server.py` does exactly this), and `len(json.dumps(tool, ensure_ascii=False))` each
entry. Re-derive rather than trust.

**And the re-derivation now runs**, which for a year it did not: this paragraph used to end by
admitting *"these four have no gate"*, which is a published method with nobody executing it — a
measurement that was true on one afternoon, propping up every argument the section makes.
`scripts/check_packaging_wire.py` completes that handshake in CI, sizes what arrives, and fails when
any figure here drifts by more than a **declared 5%** from the wire. The tolerance is on the
*argument* the number carries (*"roughly a fifth of a 128 k window"*, *"about 640 of headroom"*),
never on the number, and it is why this is a second gate rather than four more rows in
`check_stated_facts.py`: that one compares for exact equality because its facts are **counts**, and
loosening it to a tolerance to admit `~98 k` would weaken every count it holds. The two split on
exactness and on cost — an AST walk under a second there, a PEP 723 resolve plus an MCP handshake
here. The tool count stays on both, deliberately: `check_stated_facts.py` asks the `@mcp.tool`
decorations, this asks the wire, and a tool registered behind a condition is the case where those
two answers differ.

Two things that measurement corrects, both of which were being estimated the easy way. **The
docstring is not the payload**: FastMCP splits a tool's docstring, sending the prose before `Args:`
as `description` and moving each `Args:` entry into the matching property's `description` inside
`inputSchema` — checked on the wire against `ledger_summary`, whose `ledger: Path to ledger.json.`
arrives inside the schema and not in the description. So counting docstrings sees about half the
truth: ~54 k characters of docstring against ~98 k on the wire. And **the schema is most of the
cost**: median description 410 characters inside a median tool object of ~1,410.

**Per host, and only the first row is a verified mechanism:**

| Host | Are the 69 loaded up front? | Verification |
|---|---|---|
| **Claude Code** | **No, deferred by default** | VERIFIED in its docs: *"Tool search is enabled by default: MCP tools are deferred and discovered on demand"* — only tool **names** and the server `instructions` load at session start. Off in named cases: `ENABLE_TOOL_SEARCH=false`; a non-first-party `ANTHROPIC_BASE_URL`; `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`; Microsoft Foundry on Azure (rejected server-side, unoverridable); Google Cloud Agent Platform models older than the 4.5 generation. `auto` is a middle setting: *"tools load upfront if they fit within 10% of the context window, deferred otherwise"* — at ≈25 k tokens we fit that only on a large window. |
| **Codex** | **UNVERIFIED** | Its MCP documentation is silent on tool deferral, count limits and context budgeting, and the Rust source was not read at the consuming function. Absence of a documented mechanism is not absence of one. Plan for the full surface — that is the conservative direction. |
| **opencode** | **Yes, on the docs' own account** | *"Once added, MCP tools are automatically available to the LLM alongside built-in tools"*, and it names the consequence itself: *"When you use an MCP server, it adds to the context. This can quickly add up if you have a lot of tools."* Docs-level, not source-level — call it verified-by-documentation. The available mitigation is the user's, not ours: opencode filters tools per agent by glob. |
| **Pi** | **No — one tool, ours** | VERIFIED in our own adapter: `src/adapters/pi/extensions/mcp-bridge.ts` registers a **single** proxy tool (`alignment`) synchronously and connects lazily, so Pi's context carries one description regardless of how many the server serves. The bridge is a deferral mechanism nobody planned; it is the reason the tool count has never been felt there. |

**So the cost is real on Codex and opencode and paid every turn**, and it is roughly a fifth of a
128 k window before the conversation starts. That is the honest statement of the risk. It is not
currently actionable by us — trimming to fit the worst host would degrade the two hosts that defer
— but it is the number to put beside any proposal to add tools, and the reason `EXPECTED_TOOLS` in
`tests/test_mcp_server.py` is asserted as set **equality**: adding a tool should cost somebody a
deliberate edit.

**One host-specific limit we sit under, and it is closer than it looks.** Claude Code *"truncates
tool descriptions and server instructions at 2KB each"*, and truncation is silent: the agent picks
a tool by its description, so a clipped one degrades selection with nothing reporting it. Our
longest description is 1,405 characters — about 640 of headroom, which one thorough docstring would
consume. Anything approaching 2,048 has to be shortened at the docstring, not accepted, and
`check_packaging_wire.py` now refuses one that is not.

**The unit is the soft spot, and this is the second place in this package where it is.** *2KB* is
**bytes**; every figure in this section is **characters**; and this repo's prose is full of em
dashes, which cost three bytes each. The same description measures 1,405 characters and **1,413
bytes**, so a check written against `len(s)` would report headroom the host does not honour. The
gate measures `len(s.encode("utf-8"))` for the ceiling and characters for the prose, because those
are the units each claim is actually made in. `docs/open-gaps.md` §31 residual 1 records the twin of
this — a *"character budget"* that *"scales at 1% of the model's context window"*, a window measured
in tokens — **now settled in favour of characters** (a *fraction* setting applied to the window
yields a character count), which is the reading the gate already encoded.

### The skill-listing ceiling is the user's to raise, and they have to be told

The listing budget is the other surface this package does not own, and unlike the tool surface the
user can move it. `skillOverrides` cannot name a Keel entry — *"Plugin skills are not affected by
`skillOverrides`"* — but that says nothing about the ceiling those entries compete under, and this
package spent months concluding it did. Three levers, all in the user's settings, none shippable by
us:

| Lever | What it does |
|---|---|
| `skillListingBudgetFraction` | raises the fraction itself — *"(e.g. `0.02` = 2%)"*, doubling the whole listing budget |
| `SLASH_COMMAND_TOOL_CHAR_BUDGET` | sets the budget to a fixed character count outright |
| `skillOverrides: "name-only"` on the user's **own** skills | lists them without a description, freeing room Keel's entries then compete for |

**Why a user would want to.** Fifteen of Keel's nineteen skills set `disable-model-invocation: true`
and are reached by typing their name, because at 1% the two flagships have to outbid everything else
to fire for a cold user. A user who raises the fraction is buying back the ability for the model to
reach more of them unprompted — the cost the invocation axis pays, refunded by a setting we cannot
write. The package's default must remain correct at 1%; that is a floor, not a recommendation.

**And it is measurable rather than derived.** `/doctor` estimates the listing's context cost and its
biggest contributors; the Skills row in `/context` reports the size *after* the budget is applied,
so it matches what the model receives (accurate since v2.1.196); `--debug` logs a warning when the
listing overflows. Anyone with Keel installed can replace this package's derived 1,200 with the
figure their own host reports — which nobody has yet done, and §31 residual 1 says so in place.

**What we deliberately do not use.** Claude Code offers two escapes from deferral — `alwaysLoad: true`
per server in `.mcp.json`, and `"anthropic/alwaysLoad": true` in an individual tool's `_meta` — and
we set neither. Nothing here is needed on every turn: an agent reaches for `contract_diff` when it
is doing cross-layer work and for `ledger_record_decision` when a human is answering, and the
`instructions` string plus the tool names are what point it at the search. Exempting a tool would
spend context on every turn to save a search step on a few, and it would also make startup wait for
this server (`alwaysLoad` blocks on connect, capped at 5 s) — a real cost for a `uv run --script`
server whose cold start is ~7 s.

**Resources and prompts add to the same budget, and much less.** `resources/list`, `prompts/list`
and `resources/templates/list` are separate calls a host makes on its own schedule, so they do not
enter the tool budget above at all; the three templates and three prompts this server serves are a
few hundred characters each. Which hosts even ask is uneven: Claude Code documents both surfaces
(resources as `@server:protocol://resource/path` mentions, prompts as `/mcp__servername__promptname`
commands), while the Codex and opencode MCP docs describe tools only — see `docs/design/mcp-apps.md`
for that matrix and how much each row's evidence is worth.

## Elicitation — does the host ask the human, or does the agent relay?

`ledger_record_decision` has two rungs. The strong one (`evidence: "elicited"`) has **this server**
ask the user through the host, so the answer never passes through the agent; the weak one
(`transcribed`) has the agent relay a quote. `ledger_record_policy` has the same two, and the row
below applies unchanged — it sends a two-option enum (accept / decline) with the rule and the pins
it would decide in the message, so a host that renders our enum as a picker renders that one too.
Which fires is decided at runtime by
`src/mcp/server.py::_client_can_elicit`, which asks the live session rather than consulting a table
that rots — `mcp/server/session.py::ServerSession.check_client_capability`, whose elicitation branch
is a bare presence check (`if capability.elicitation is not None and client_caps.elicitation is
None: return False`). **Nothing below is read by the code.** It is what an author needs to know about
where the strong rung actually fires, and it is written down because "it degrades correctly" and "it
is ever used" are different claims.

Audited **2026-08-06**, one independent read per host, each at the function that consumes the value.
Method for all four rows is **`read_source`** — the shipped binary or the pinned source, followed to
its consumer. **No host's `initialize` was captured on the wire**, so this is method 2 of
`docs/open-gaps.md`'s "Prove it", never method 1; say "read" and not "observed" when citing it.

| Host | declares `elicitation` in `initialize` | what it renders for our enum |
|---|---|---|
| **Claude Code** 2.1.221 | **yes**, unconditional | radio list; out-of-menu answer impossible |
| **Codex** (`openai/codex`) | **yes**, unconditional | single-select picker; same |
| **opencode** (`anomalyco/opencode`) | **no** — the line is commented out | nothing: no handler is registered |
| **Pi**, through our own bridge | **no** — the bridge sends `capabilities: {}` | not rendered |

**What our own call puts on the wire** — the link both positive rows depend on, and the one the
audits left open. Verified here by execution, not reading: `server.py::_ask` — the one function
every elicitation on this server now goes through — calls
`ctx.elicit(message, choices)` with a `list[str]`; under the pinned `fastmcp==3.4.4`,
`fastmcp/server/elicitation.py::_parse_list_syntax` takes the list branch and returns an
`ElicitConfig` whose `.schema` is

```json
{"type": "object", "title": "ScalarElicitationType", "required": ["value"],
 "properties": {"value": {"type": "string", "title": "Value",
                          "enum": ["opt_a — …", "accept_as_is — leave it as it is"]}}}
```

and that dict reaches the wire verbatim: `fastmcp/server/context.py:1190` passes
`requestedSchema=config.schema` to `ServerSession.elicit`, which forwards it into
`ElicitRequestFormParams(requestedSchema=…)` (`mcp/server/session.py:407-413`). So what a host
parses is **one flat string property carrying an `enum`** — inside Claude Code's flat-primitives
limit, and matching the one Codex variant that survives its `deny_unknown_fields`.

`ledger_record_policy` sends the same shape, and this one was **captured on the wire** rather than
traced through the library: a `stdio` client that declares `elicitation` and answers `decline`
receives `mode: "form"`, `message: "Set this policy?\n\n<rule>\n\nIt decides 1 pin(s) without
asking again: pin_0001"`, and a `requestedSchema` whose single `value` property carries the
two-member enum `["set this policy — …", "do not set it — …"]`. So the rows above apply to it
unchanged, and the pins a rule would decide are in the message a host renders, not only in the
tool's return value.

- **Claude Code — declares it, and honours the enum.** Read out of the binary that actually spawned
  our server on this machine (`…\claude-code\2.1.221\claude.exe`, found by walking the live
  `uv run --script …/mcp/server.py` process to its parent), so it is the client, not a docs claim.
  `Client.connect()` sends `params.capabilities = this._capabilities`; `_capabilities` comes from
  `new Client({name:"Claude Code",…},{capabilities:Lhr()})`, and `Lhr()` → `zYy()` returns the
  literal `{roots:{listChanged:true}, elicitation:{}}`. No flag, no config key, no transport branch
  touches the `elicitation` key (the `tasks.requests.elicitation` extension beside it is gated on
  `OPe()`, which is `function OPe(){return!1}`, and the v2 reshaper `VYy` strips *that* key, never
  this one). The rendering consumer is `registerElicitationHandler` → `setRequestHandler
  ("elicitation/create", …)` → the form component, whose enum predicate is
  `e.type==="string" && (("enum" in e)||("oneOf" in e))`; a string-with-enum field is **excluded**
  from the free-text path and drawn as a radio list, and validation rebuilds `z.enum([...])`, so a
  value outside the menu cannot be submitted. It also refuses anything but flat primitives
  ("Elicitation requestedSchema only supports flat primitive properties…") — our schema fits.
  Two things that qualify the guarantee rather than the declaration: an elicitation arriving before
  the REPL swaps in the interactive handler hits a placeholder that answers `{action:"cancel"}`, and
  a user-configured hook can answer *for* the human ("Elicitation resolved by hook") with no prompt
  ever shown — so on this host `elicited` means "the agent did not hold the value", not "a human
  was looked in the eye". **UNVERIFIED, do not promote:** whether the interactive handler is
  registered at all in non-interactive/`stream-json` runs (only the REPL call site was found, and
  its absence was not ruled out); and whether an elicitation from inside a subagent reaches that
  queue. The declaration is unconditional either way, so `_client_can_elicit` still returns True.
- **Codex — declares it, and renders a picker.** `codex-rs/codex-mcp/src/rmcp_client.rs::
  mcp_initialize_request_params` does `capabilities.elicitation = Some(client_elicitation_capability)`
  with no branch, and it is the only construction site feeding `RmcpClient::initialize`. The wire
  shape was checked at the serializer, not the type: `rmcp` is pinned `=3.0.0`, where
  `ClientCapabilities.elicitation` carries `skip_serializing_if = "Option::is_none"` and
  `ElicitationCapability`'s own fields are all optional, so `Some(default)` emits
  `"elicitation": {}` — exactly what the fake client in `tests/test_mcp_server.py` declares. The
  incoming request is handled by `rmcp-client/src/elicitation_client_service.rs::handle_request`
  (`ServerRequest::ElicitRequest`, plus a `CustomRequest` arm matching the method name), and the
  response is shaped by protocol version, older peers getting a `CustomResult` with the same
  `{action, content?}` wire shape — no mismatch with FastMCP. Rendering: `tui/…/
  mcp_server_elicitation.rs::parse_single_select_field` turns our property into
  `McpServerElicitationFieldInput::Select`, so the user picks from the offered menu.
  Two caveats. Every variant of `McpElicitationEnumSchema` is `#[serde(deny_unknown_fields)]`, so one
  extra key from a future FastMCP silently degrades the rich Select to nothing — version coupling,
  not stability. And `exec/src/lib.rs::canceled_mcp_server_elicitation_response` makes headless
  `codex exec` answer `Cancel` while still declaring the capability: `_client_can_elicit` returns
  True with no human present, `ctx.elicit` yields a non-`AcceptedElicitation`, and
  `ledger_record_decision`'s `not isinstance(result, AcceptedElicitation)` branch
  raises rather than writing one. That is the correct refusal to fabricate, but it means a
  non-interactive Codex run **errors instead of degrading to the transcribed rung** — a real
  behaviour, not detectable from the capability, and a decision to make deliberately if we want it
  to relay. This is deliberately **not** what the `_ask` backstop changed: a cancel is a *value*, so
  it still hard-refuses; only a door that never opened degrades. **Read at `main` with no release tag
  pinned**, so treat the facts as of the audit date — and note that both citations here were line
  numbers until the code moved under them, which is why they are symbols now.
- **opencode — does not declare it, and would not render it.** `packages/opencode/src/mcp/index.ts::
  createClient()` is the sole construction site for real connections; its `CLIENT_OPTIONS.capabilities`
  contains `roots: {}` only, with `// elicitation: {},` commented out beside an issue link. That value
  is consumed by the TS SDK's `Client` constructor (`this._capabilities = options?.capabilities ?? {}`)
  and sent by `Client.connect()`. `registerCapabilities()`, the only other mutator, is called zero
  times in the repo and zero times in the shipped binary. No handler either: `setRequestHandler` is
  called exactly once in the whole MCP module, for `ListRootsRequestSchema` — `ElicitRequestSchema`
  appears eight times in the binary and is never registered, which is the type-vs-consumer trap in
  its purest form. Agreed across three artifacts: tag `v1.18.14`, the `dev` HEAD, and the locally
  installed `opencode-ai@1.2.27` binary (which predates even `roots: {}` and passes no options at
  all). **The negative is recent and reverted, not "never considered"**: PR #35064 *feat(core): MCP
  elicitation support* merged 2026-07-03T04:25:55Z and PR #35080 reverted it 67 minutes later
  together with the Form service it depended on. Issue #23066 is closed as *completed* with a
  maintainer comment pointing at a `v2` branch that does not exist. Do not conflate the open PR
  #38311 *support acp elicitation* with this: that is ACP, where opencode is the agent side, and it
  would not make `ctx.elicit()` work.
- **Pi — does not declare it, and the negative is ours, not Pi's.** Pi itself has no MCP client at
  all (`grep -rIoE 'modelcontextprotocol|[^a-zA-Z]mcp[^a-zA-Z]'` over the published `dist/` of
  `@earendil-works/pi-coding-agent` v0.81.1 returns zero, and `elicit` case-insensitively returns
  zero), so **our bridge is the surface** — and `src/adapters/pi/extensions/mcp-bridge.ts::
  McpStdioClient.connect()` hardcodes `capabilities: {}` in the `initialize` it sends. No code path
  populates it, so every decision recorded through Pi is `transcribed`, always. What the bridge does
  with a server-initiated request is *ignore* it: `onData` dispatches only when `msg.id` is in
  `pending`, which holds client-generated ids only, so an `elicitation/create` falls out of the loop
  with no reply written. That verifies the other half of `_client_can_elicit`'s docstring at the
  consumer — an unguarded `ctx.elicit` here would hang until the bridge's own 60 s
  `REQUEST_TIMEOUT_MS` rejected the in-flight `tools/call`.
  Pi **could** render the prompt; we simply do not wire it. `ExtensionUIContext` declares
  `select(title, options, opts)` and it reaches tools as the 5th argument of `execute`
  (`wrapToolDefinition` → `runner.createContext()`), implemented for real in the TUI
  (`interactive-mode.js` → `ExtensionSelectorComponent`) and as a dialog RPC in RPC mode, degrading
  to a `noOpUIContext` whose `hasUI()` is false in print/json mode. Our bridge's `execute(_id,
  params)` has arity 2 and never touches it. Closing this on Pi is therefore a known piece of work:
  implement `elicitation/create` against `ctx.ui.select` and declare
  `capabilities: {elicitation: {}}` **only when `ctx.hasUI`**. `nicobailon/pi-mcp-adapter` is the
  proof it is reachable — it gates on `config.settings?.elicitation !== false && hasUI`, declares
  `{elicitation:{form:{},…}}` from `buildClientCapabilities()`, registers the handler, and branches
  on `schema.type === "string" && ("enum" in schema || "oneOf" in schema)` to `ui.select`, keeping
  free text as the last fallback.

**The rung stays on the two hosts that cannot use it.** It costs nothing — `_client_can_elicit` is
one session lookup — and it arms itself the day support lands, which is exactly why the capability is
asked and never assumed. opencode has the line sitting commented out with an issue link; Pi needs
only the bridge work above.

## Memory

Durable, cross-session memory in three layers (the `project-memory` skill): the **ledger**
(decision-memory, with `flip_criteria`), **`MEMORY.md`** (project facts, always-on via `AGENTS.md`
and opencode `instructions`), and the optional **cognee MCP** (`cognee/cognee-mcp`) — a
queryable, self-editing graph for associative recall at scale, opt-in per the setup above.

## The generic skills are ours, because they must be ledger-aware

**The rule: a programmer and their coding agent get everything they need from our plugins. No
external plugin, ever.** `tests/test_codex_manifest.py` enforces it — no marketplace source may
leave this repo.

This reverses a doctrine that stood here for months: *"generic engineering skills (TDD, debugging,
planning, code review, git worktrees) are **composed** from [`superpowers`](https://github.com/obra/superpowers),
not reinvented here."* Two things were wrong with it, and the second is the one that matters.

**It was never composed.** No plugin declared superpowers in `dependencies`; no file in `src/` named
one of its skills. The entry's `source` was `"github:obra/superpowers"` — a shorthand that does not
exist — so it could not even be fetched. Four documents asserted a mechanism that was not there, on
the shop window, for months. The house failure mode.

**And composing it was the wrong goal.** A dependency installs the *whole* plugin: 16 skills, of
which `brainstorming`, `writing-plans`/`executing-plans`, `dispatching-parallel-agents` and
`subagent-driven-development` are **stateless twins** of `core/brainstorm.md`, `buildloop.py` and
`core/agents.md`. None of them writes to the ledger; none ever will. Putting a forgetting twin
beside the single source of truth is exactly the divergence this package exists to find in other
people's codebases — we would have shipped our own anti-pattern, unpinned (the entry carried no
`ref`/`sha`), with session-start hooks, through our own catalog.

So: not a reinvention, a **binding**. superpowers' TDD cannot make its red step an
`acceptance_criterion` pin. Ours is nothing but that. Same for the rest — a debugging loop that
opens and closes a `defect` pin, a review that reopens rather than decides, a worktree discipline
that makes the executor's "one scope at a time" enforceable instead of promised.

The gap is smaller than 16 because the spine already owns the twins. What is genuinely missing:
`test-driven-development`, `systematic-debugging`, `verification-before-completion`, `code-review`
(their request/receive pair), and a branch/worktree lifecycle. superpowers is MIT, so where its
prose is good the honest move is to adapt it with attribution — not to pretend we did not read it.

## Cursor & other AGENTS.md-only agents

An agent that reads `AGENTS.md` but has no plugin format is a partial target, and saying so plainly
is better than the shortcut this document used to take (*"open the repo"*). Install the skills the
way opencode and Pi do — `bash scripts/install.sh` places them where an `.agents/skills` reader
finds them — and add the MCP servers from `plugins/keel-core/.mcp.json` through that agent's
own settings UI. The distinction that matters: you are pointing your agent at **your** project and
giving it our skills, not opening our repo and working inside it.

## The invocation axis — who may fire a skill

Every skill is **model-invoked** (the host may fire it, and so may the human) or **user-invoked**
(only the human, by name). It is a packaging fact because each host expresses it differently, and a
correctness fact because it decides whether the skill's `description` is in the model's context at
all. The choice itself — and the test for making it — lives in `src/core/writing-for-agents.md`.

Authored **once**, as `disable-model-invocation: true` in the skill's own frontmatter. Everything
below was read at the code or table that consumes the value:

| Host | Mechanism | The human keeps a door | Consumer |
|---|---|---|---|
| **Claude Code** | the authored frontmatter key | yes — `/name` | its own behaviour table: `disable-model-invocation: true` → **"Description not in context"**; the docs also state it stops the skill being preloaded into a subagent, and that the model's call is *blocked*, not warned |
| **Pi** | **the same authored key** | yes — `/skill:name` | `dist/core/skills.js`: `disableModelInvocation: frontmatter["disable-model-invocation"] === true`, then `formatSkillsForPrompt` does `skills.filter(s => !s.disableModelInvocation)` |
| **Codex** | `agents/openai.yaml` beside `SKILL.md`, `policy.allow_implicit_invocation: false` | yes — explicit `$skill` | documented as *"Codex won't implicitly invoke the skill based on user prompt; explicit `$skill` invocation still works"*; frontmatter's floor there is still `name` + `description`, so the sidecar is the only shape available |
| **opencode** | **none that preserves the human's reach** | **no** | `packages/opencode/src/tool/skill.ts` — the only door is the model's `skill` tool, and `ctx.ask({permission: "skill", …})` fires *inside* its `execute`. Denying the permission removes the skill from everyone |

Two consequences, and the second is the one that pays:

- **Only Codex is generated.** `build.py` derives its sidecar from the frontmatter key; nothing is
  hand-kept, and `tests/test_invocation_axis.py` asserts the derivation in both directions plus the
  absence of any authored sidecar. Emitting nothing for opencode is deliberate — a permission `deny`
  there is a *disabled* skill, and shipping it under this name would give one word three meanings.
- **Pi reading Claude's key is why the axis is cheap here.** Two of four hosts are served by one
  authored line, one by a generated file, and the fourth is a stated residual. The nearest thing
  opencode offers is `ask`, which leaves the description in the model's context — so it buys the
  human a prompt and buys the context budget nothing.

The value for this package is mostly **discipline, not tokens.** Its skills overwhelmingly *should*
be model-invoked — the whole design is that an agent meeting a broken build reaches
`systematic-debugging` itself — so the axis is not an invitation to convert them. What it fixes is
that model-invocation stops being the shape a skill has because nobody chose, and the two costs of
the other branch (unreachable by another skill; not preloaded into a subagent) are now written down
where the choice is made.

## When the name is already taken — `/code-review`, and the install path that overrides a bundled skill

Claude Code bundles skills of its own, and one of them is called `code-review`. So is ours, and the
name **stays**: it is what the skill is, a skill is chosen off its name and description, and the
namespace already provides the collision-avoidance a rename would buy — trading trigger accuracy for
it would be paying twice. What the collision actually costs is a *door*, and which door opens is
decided by three separate rules, each read at the page that states the consequence
(`https://code.claude.com/docs/en/skills`, *Skill name conflicts*):

| The operator types | What runs | The rule |
|---|---|---|
| `/keel-kit:code-review` | **ours**, always | *"Plugin skills use a `plugin-name:skill-name` namespace, so they can't conflict with other levels"* |
| `/code-review` | **the bundled one**, silently | *"The bare `/fancy` also invokes the skill unless another command already uses that name"* — and this name is already used |
| `/code-review`, after the skill folder lands in `.claude/skills/` or `~/.claude/skills/` | **ours**, in every project, replacing the host's | *"A skill at any of these levels also overrides a bundled skill with the same name… a `code-review` skill in your project's `.claude/skills/` replaces the bundled `/code-review`"* |

The first two rows are the trade, and they are fine: the qualified command is taught in
`which-skill` and in `src/readme/keel-kit.md`, which is the whole remedy the namespace needs. **The
third row is the one that bites, and this repo makes it reachable in one argument.**
`scripts/install.sh` takes its target directory as `$1`, defaulting to `~/.agents/skills` — the path
opencode and Pi discover and Claude Code ignores. Point it at Claude Code's own directory instead:

```bash
bash scripts/install.sh ~/.claude/skills   # NOT an install — this is an override
```

and every skill lands at the **personal** level, where ours no longer merely loses the bare name: it
*replaces* the bundled `/code-review` in every project that user opens, on a host that reports
nothing about having done so. (Whether Claude Code follows a *symlinked* skill directory is
**UNVERIFIED** — and it softens nothing: `place()` falls back to a real copy wherever symlinks are
unavailable, which is the same override with none of the doubt.) Claude Code's supported path is the
marketplace (`/plugin marketplace
add r3vs/keel`), where the namespace protects both skills; the directory argument exists for the two
hosts with no plugin format, and pointing it at `~/.claude/skills` is a supported-looking way to get
an unsupported result.

**The script now says so itself, and refuses by default.** Documenting a footgun the script hands
over on request was half a fix: the person about to fire it is at a terminal, not in this file. Any
target with a `.claude` component now prints the consequence above and stops — interactively it asks
for the word `override`, and with no tty on stdin it exits 3 having placed nothing, so an unattended
run cannot take the branch nobody would be there to read. There are exactly two ways through and
both require somebody to mean it: `--claude-personal` up front, or typing `override` at the prompt
— which only exists when a person is there to type it. Nothing gets through by scrolling past.

`tests/test_name_collision.py` holds this shut, and its subject is the class rather than the
instance: the colliding set is **derived** — `build.shipped_skills()` intersected with Claude Code's
bundled roster — so a future skill named `debug`, `verify` or `simplify` inherits the requirement to
teach its namespaced form instead of inheriting an exemption. The declared limit is that the bundled
roster is a dated copy of somebody else's list: if the host bundles a new name tomorrow, nothing
here notices, and that is a fact about their release notes rather than a hole a gate can close.

## Shared-core resolution

`src/core/*.md` is the single **authoring source** for the shared doctrine, and each skill is
**self-contained** (Model B): `scripts/build.py` vendors the docs a skill needs into its own
`references/core/` (following the `core→core` dependency closure) and rewrites the pointers, so no
skill ever points outside its own tree. A skill directory therefore ships complete on every
platform, with no external `core/` dependency at read time. `src/core/` is the edit point only and
never ships; CI's `build.py --check` fails if any vendored copy drifts from it, so the duplication
can never diverge — the very anti-divergence property the skills enforce on the codebases they
touch, applied to their own shared prose.

**Why vendor at all — distribution atomicity, and nothing else.** The Agent Skills spec's unit of
distribution is the **standalone skill folder**, and `scripts/install.sh` links each skill directory
individually into the host — a sibling `core/` is not part of what travels. Vendoring guarantees the
bytes a skill needs live *inside* the unit that ships. It buys nothing about path resolution: both
opencode and Pi inject the skill's own base directory and delegate resolution to the model (no host
resolves skill-relative reads deterministically), so a `../../core/x.md` is not rejected — it is
lexically internal and would silently read the user's *own* file at that path. Self-containment is
enforced by no host; our linter is the only thing between us and a bug both would happily ship.

### Why not just write the text directly in each skill (and delete `core/`)?

Because the same doctrine is load-bearing in several places at once — the ledger spec alone is
used by both methodology skills, two helpers, and the challenger agent. Written "directly where
needed" it becomes N hand-maintained copies with **no mechanical guard**: the next spec bump
updates some copies and misses others, and nothing can flag it because there is no source to
compare against. That silent divergence is the exact failure mode this package exists to cure, so
the repo applies its own medicine: one source, generated copies, a CI gate. The copies exist only
because the Agent Skills spec's unit of distribution is a **standalone skill folder** — a skill
copied out of the repo must not contain dangling pointers.

Three rules keep the model honest:
- every vendored copy carries a `GENERATED FILE — do not edit` banner (the source is `src/core/`);
- the sharing surface stays **minimal**: only load-bearing dependencies are backticked pointers
  (which the closure follows); see-also mentions stay plain text, so helpers vendor only the doc
  that is their actual subject;
- `agents/*.md` and other **plugin-root adapters resolve `${CLAUDE_PLUGIN_ROOT}/core/x.md`** — they
  are not inside any skill, so the build gives them a plugin-root copy. Only files under `skills/`
  must use the per-skill vendored copies (the linter enforces exactly this split).

## Keeping adapters honest

Nothing here is kept in sync by hand, because a parity linter is a smell — it says two things should
be one thing, generated. So each fact lives once and the build derives every host's shape from it:

| Fact | Its one source | Derived into |
|---|---|---|
| the agent roster + its write verb | the table in `src/core/agents.md` | `disallowedTools` (Claude) · `permission.edit` (opencode) |
| the required MCP servers | the table in `src/core/knowledge-sources.md` | `.mcp.json` (Claude + Codex) · the opencode plugin's `config()` hook |
| the ledger gate's rule | `src/hooks/ledger-gate.py` | `hooks.json` (Claude + Codex) · thin TS adapters (opencode + Pi) that carry no logic |
| the search-tool nudge | `src/hooks/search-nudge.py` | `hooks.json` (Claude + Codex) — **no opencode/Pi adapter, stated below** |

The nudge's missing adapters are a **declared residual, not an oversight**. The ledger gate earns its
two TS adapters because it *denies*: a rule that blocks on one host and not another is a rule the
user cannot rely on. The nudge only prints a sentence, and neither opencode's `tool.execute.before`
nor Pi's `tool_call` has a warn channel — both offer block-or-nothing, and the one thing this hook
must never do is block a shell search. So on those two hosts `core/search-strategy.md` reaches the
agent the ordinary way, as vendored prose, and the reminder is simply absent rather than
reimplemented as something it is not. If either host grows a non-blocking advisory return, the
adapter is four lines and the rule already lives in one place.

**The Codex half of that row was asserted from the table above before it was checked, which is the
error this page exists to warn about** — the `./` bug shipped for months because a *type* was cited
instead of the function that consumes the value. It is now checked, and it holds on both halves it
depends on: Codex's `PreToolUse` fires for shell commands **matched as `Bash`** (the same matcher
string this hook registers), and a command hook's stdout `systemMessage` is honored and *"surfaced
as a warning in the UI or event stream"* — so the nudge both fires and speaks there, rather than
running silently. Verified against the current hooks reference (`learn.chatgpt.com/docs/hooks`,
formerly `developers.openai.com/codex/hooks`, now a 308).

Two things that reference settles which are **not** about this hook, recorded because they were read
first-hand and cost nothing to keep:

- **`permissionDecision: "ask"` is *"parsed but not supported yet"* on Codex.** That is the exact
  mechanism `keel-core`'s README gives the ledger gate for a write into host memory — deliberately
  *ask*, never deny. On Codex that rung is currently unavailable, so that path degrades to whatever
  the fallback is rather than prompting. Pre-existing and out of this change's scope; flagged here
  rather than left for the next reader to rediscover.
- The events list published there is **eleven**, not the ten this repo's table in `CLAUDE.md` states
  (`SessionStart`, `SessionEnd`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `PreCompact`,
  `PostCompact`, `UserPromptSubmit`, `SubagentStart`, `SubagentStop`, `Stop`). A count restated from
  a doc that has since moved is exactly the drift class the gates cover for numbers this repo
  computes — this one is not computed, so it is corrected by reading, here.

Both tables are **parsed, never grepped** — "GitHub" appears in the knowledge-sources prose twice as
ordinary English (DeepWiki indexes *public GitHub repos*; *GitHub Advisory* is a registry), and a
word-match would "find" a server nobody declared. Correspondence comes from a declared fact or not
at all.

The gates that hold the above shut are `scripts/build.py --check` (every generated file still equals
its source) and `scripts/verify_commands.py` (every command a shipped file tells an agent to run
resolves *after install*, not just here). They are two of the set; **the whole list is the Commands
block in `CLAUDE.md`**, complete against `.github/workflows/ci.yml`, and is not restated here —
this sentence used to read "The gates: …" over a copy that was short by four.

The residual none of them close: **a plugin cannot ship a selective, agent-scoped `Bash` rule.**
Claude Code restricts `Bash` fine — `Bash(rm *)`-style matchers exist, with `deny → ask → allow`
precedence — but only in the user's own `settings.json`, session-wide, which a plugin cannot write.
The ledger gate closes that residual at runtime.

## External tool licenses

This repo's code and prose are MIT (`LICENSE`). The deterministic toolchain it *invokes* keeps its
own licenses — notably **GitNexus is PolyForm Noncommercial** (optional secondary graph engine; not
installed unless `RESCUE_INSTALL_GITNEXUS=1`). Graphify (optional graph source) is MIT.

[Anthropic Agent Skills specification]: https://code.claude.com/docs
