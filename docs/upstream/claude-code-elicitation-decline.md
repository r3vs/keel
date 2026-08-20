# Upstream report (drafted, not filed) — an MCP elicitation is answered `decline` by a client that never drew a prompt

**Status: drafted for a human to file.** Nothing in this repo sends it. It is written as a report to
the Claude Code / Agent SDK maintainers and kept here because the finding decides one of our own
design questions (`docs/open-gaps.md` §41) and because a report nobody can reproduce is not a report.

**Method: read in the shipped bundles**, plus one field observation. No `initialize` and no
`elicitation/create` was captured on the wire, so every claim below is either *observed behaviour of
a running system* or *read at the function that consumes the value* — marked per item, never mixed.

---

## Summary

When Claude Code is driven over `--input-format stream-json`, an MCP server's
`elicitation/create` is forwarded to the controlling SDK client as a control request. A client that
registered no `onElicitation` callback gets an unconditional

```js
return { action: "decline" }
```

from the SDK. The MCP spec defines `decline` as *"User explicitly declined the action"*, so a server
receives a positive statement about a human who was never shown anything.

The SDK's own adjacent branch handles the identical situation without inventing an answer, which is
what makes this look like an oversight rather than a design choice.

## Observed (field)

- Claude Code inside the Claude desktop app, Windows 11, 2026-08-19/20.
- An MCP server (ours) whose decision tool elicits a single-select enum. Every call returned a
  declined elicitation. **No prompt was rendered at any point**, while the human was active in the
  same conversation and answered ~25 questions through the assistant's own question UI in the same
  minutes.
- 23 elections had to be recorded through a separate local CLI instead.

## Read at the consumer

Versions as installed on the machine above:

| Component | Version |
|---|---|
| Claude desktop app | `1.32885.1.0` |
| Claude Code CLI (spawned by it) | `2.1.234` |
| Agent SDK bundled in the desktop app | `0.3.234` |
| Server side | `fastmcp==3.4.4` / `mcp==1.29.0` |

1. **The launch.** Walking the live process tree from the running MCP server to its ancestors gives
   `…\claude-code\2.1.234\claude.exe --output-format stream-json --verbose --input-format stream-json …`.
   So the CLI is not in REPL mode; the desktop app is the controlling client.

2. **The CLI forwards rather than renders.** In the CLI bundle, `registerElicitationHandler` — the
   path that pushes onto the interactive queue — is registered from the REPL's own React layer.
   The other path is `handleElicitation`, which sends a control request:

   ```js
   async handleElicitation(e, t, r, n, o, i, s, a) {
     try {
       return await this.sendRequest({ subtype: "elicitation", mcp_server_name: e, message: t,
                                       mode: o, url: i, elicitation_id: s, requested_schema: r, … }, …)
     } catch { return { action: "cancel" } }
   }
   ```

3. **The SDK answers for the absent handler.** In the desktop app's bundle, `processControlRequest`:

   ```js
   if (e.request.subtype === `elicitation`) {
     let n = e.request
     if (this.onElicitation) { … return r }
     return { action: `decline` }          // ← no handler, no prompt, positive refusal
   }
   if (e.request.subtype === `request_user_dialog`) {
     if (this.onUserDialog) { … return n }
     uL(`[Query] No onUserDialog handler for request_user_dialog (kind=…) — staying silent so a
         capable client (or the worker's park deadline) settles it`)
     return s$                              // suppressControlResponse
   }
   ```

   `onElicitation` occurs five times in that bundle and every occurrence is inside the vendored SDK
   (field declaration, the `hasCallbacks` predicate, the constructor assignment, the use site above,
   and the `query()` options destructure). No application call site supplies one.

## Why it is not recoverable server-side

`ElicitResult` carries `action` and `content` and nothing else. FastMCP's `Context.elicit` maps
`decline` onto a payload-free `DeclinedElicitation()`, so even an `_meta` a client might attach
would not reach the tool body. `clientInfo` is identical in REPL and `stream-json` mode. There is no
capability shape, era, or field that separates *a human refused* from *nobody was asked* — and a
timing threshold is a guess, not a signal.

For a server that treats a refusal as load-bearing — ours records *who* supplied a decision, and a
fabricated refusal is indistinguishable from a real one — this collapses two opposite facts onto one
value with no way back.

## Suggested fix, in the SDK's own idiom

Make the elicitation branch behave like the `request_user_dialog` branch immediately below it: with
no `onElicitation` registered, do not answer. Let a capable client or the park deadline settle it,
and log the same way. A server sees a request that was never answered, which is the truth.

If a reply is required by the transport, `cancel` is strictly better than `decline`: the spec
defines it as *"User dismissed without making an explicit choice"*, which does not assert a user
decision that did not happen. `handleElicitation` already uses `cancel` for its own failure path.

A third option, if the shape can be extended: let the client state that no handler exists, so a
server can distinguish *declined* from *undeliverable* rather than inferring it.

## Reproduction

1. Any MCP server whose tool calls `ctx.elicit(...)` (FastMCP) or issues `elicitation/create`.
2. Run Claude Code with `--input-format stream-json` under a controlling client that passes no
   `onElicitation` to `query()` — the desktop app is one such client.
3. Call the tool. The server receives `{"action": "decline"}` with no UI shown anywhere.
4. Run the same server against the Claude Code REPL: a radio list is drawn and the human answers.
