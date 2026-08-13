# The tracker projection — design note

**Status:** implemented (`src/runtime/tracker.py`, `mcp:tracker_project` / `mcp:tracker_diff`,
`tests/test_tracker.py`). One open decision is recorded at the end and is deliberately unbuilt.

## The gap

`instructions.py` exists because the ledger is the single source of truth and **no coding agent
loads it**. This module exists because of the other half of that sentence: **no human's team loads
it either.**

A project can hold a fully elected design, an unanswered `blocker` fork and three `defect` pins, and
the tracker its team stands in front of every morning shows none of it. What happens next is not
that the pins are ignored — it is worse. They get re-answered in the standup, in a thread, with
nothing written back, and now two answers exist. That is the divergence this package exists to
find, occurring in the one surface it had no carrier for.

## The shape, which is not new

The same four properties as every projection here — `generate.py` (contract → layers),
`design_tokens.py` (DTCG → CSS), `instructions.py` (ledger → `AGENTS.md`):

| property | how it lands here |
|---|---|
| one source | the ledger. Nothing reads an issue to learn what is true. |
| a generated projection | the issue body's managed region is rendered from the pin, never authored. Byte-identical on an unchanged pin — `sort_keys=True` on the JSON payloads, severity-then-id ordering — which is what lets drift mean anything at all. |
| a round-trip drift check | `tracker_diff` answers *is the tracker still what the ledger projects*, writing on neither side. |
| managed markers | `<!-- keel:pin v1 id=… sha256=… -->` … `<!-- keel:pin-end -->`. Everything outside is preserved byte for byte. |

Two things are inherited from `instructions.py` on purpose, so a reader who has learned one has
learned both: the **four drift statuses** (`absent` · `hand_edited` · `stale` · `in_sync`) with
identical meanings, and the rule that a hand-edited region is **reported and never healed** —
re-rendering would discard what somebody wrote, and what they wrote may be the only copy of a real
decision.

One property is new, and it is the label axis: the projection owns `keel` and every `keel:`-prefixed
label and **nothing else**, so a team's `priority:p1` survives every run. That is the same rule as
"everything outside the fence is preserved", one dimension over — a projection that replaced the
label set wholesale would delete their triage on every run.

## A window, not a door

**Nothing in `tracker.py` writes the ledger, and it is structural rather than promised.** The
module imports the read half of `ledger` (`pin_read`, `read_collection`, the state sets,
`severity_rank`), never constructs a `Ledger`, and never calls `save`.
`tests/test_tracker.py::TestTheTrackerIsAWindowAndNotADoor` asserts all three by AST, plus the
end-to-end version: projecting twice leaves `ledger.json` byte-identical.

The rendered body says the same thing to the human reading it — *answering in a comment here decides
nothing, no tool reads it* — because the instinct is exactly the opposite and a rule the team
discovers by being surprised by it is a rule that has already cost somebody an afternoon.

## Host facts, each read at GitHub's own docs

The house rule is to verify a host fact at the **consumer** and cite it. Four decide this design,
and none follows from the others.

1. **Pull requests answer as issues.** *"GitHub's REST API considers every pull request an issue,
   but not every issue is a pull request."* The index therefore skips any entry carrying a
   `pull_request` key. Without the skip, a PR whose body quotes a fence becomes an issue this module
   believes it owns — and closes when the pin settles.
2. **Labels are dropped silently without push access.** *"Only users with push access can set labels
   for new issues. Labels are silently dropped otherwise."* This is the one that would break
   idempotency invisibly, because the index **is** the label: a read-only token creates a
   good-looking issue the next run cannot see, so the next run creates another, and the one after a
   third. Unbounded duplication out of a 201. So the created issue's labels are read back off the
   response and a run that lost the index label **stops**.
3. **Rate limits are headers, and the docs say not to retry.** `x-ratelimit-remaining`,
   `x-ratelimit-reset` (*"in UTC epoch seconds"*), and on 403/429 *"if the `retry-after` response
   header is present, you should not retry your request until after that many seconds has elapsed"*
   — with the warning that *"continuing to make requests while you are rate limited may result in
   the banning of your integration."* So this stops early and says so; it never sleeps and never
   retries. It also stops inside a **reserve** (`RATE_LIMIT_RESERVE`, a declared HYPOTHESIS),
   because the budget is the user's and is shared with their CI and their `gh` CLI: spending it to
   the last request would make this package the reason something else of theirs failed.
4. **Pagination is the `link` header's `rel="next"`, followed rather than reconstructed** (*"the
   query parameters in the `link` URLs may differ between endpoints"*). One thing is added on top:
   a `next` URL is server-supplied input and every request carries a bearer token, so a link naming
   any host but the API host is refused rather than followed.

### Why the index is a label listing and not a search query

The obvious idempotency key is the search API (`q=repo:x "keel:pin id=…" in:body`) and it is the
wrong one: GitHub's search index is **eventually consistent**, so an issue created seconds ago is
not findable yet. It fails exactly when it costs most — two projections in quick succession, a
retry after a partial run — and its failure mode is a duplicate issue per pin, which is the one
outcome an idempotent projection may not produce. A listing (`GET /issues?state=all&labels=keel`)
is read-your-writes against the same store, and the `keel` label is what keeps it cheap.

The index's own honesty rule follows from that: a listing that could not be walked in full makes
*"no issue carries this pin"* an artifact of the walk rather than a fact, and creating on that
reading duplicates every pin. So a truncated index writes **nothing at all** and says why.

### UNVERIFIED, and flagged rather than guessed

- **Whether GitHub auto-creates a label named on an issue write.** In practice it appears to; the
  REST docs do not say so anywhere, and the "Create a label" endpoint's existence reads as evidence
  the other way. Nothing here depends on it: a validation failure on one pin is reported against
  that pin and the run continues. Settle it by projecting into a scratch repository and reading the
  response, not by reasoning from the docs' silence.
- **The issue title's maximum length.** Not stated in the REST docs. `TITLE_MAX` is therefore not
  derived from it — it is the width at which a title still reads in a list view, declared as a
  HYPOTHESIS, and the clip is stated with an ellipsis rather than silent.

## What the projection deliberately does not carry

The body carries the pin's identity, the delta (`as_is` / `to_be`), the open fork with its offered
option ids, the elected outcome if there is one, and the provenance — with `agent_assumption`
called out, because a pin an agent assumed into existence is exactly the one a human reading a
tracker should veto rather than schedule.

It refuses the remediation list, the verification envelope, the premortem and the `depends_on`
edges. Those are the working state of a loop that runs against the ledger, and restating them here
would make the issue a second place to look for them — at which point a reader has to know which
one is stale. Same bargain as the `AGENTS.md` region's line budget: the projection is an index into
the source, not a copy of it.

Two more refusals worth naming:

- **A settled pin with no issue is `ignored`, never `create`.** Opening an issue in order to close
  it in the same run would fill a team's tracker with the history of a ledger they never asked to
  mirror.
- **No severity label.** A fourth axis on a surface that already has three, on the field most likely
  to be re-elected — every change would be an API write for a fact the body already carries.

## Two rules enforced at the MCP boundary, not in the runtime

Both are facts about the boundary an agent crosses rather than about the projection:

- **Neither tool takes a token.** A secret an agent can pass is a secret an agent has read, and a
  tool argument is model context that ends up in transcripts. The server reads `GITHUB_TOKEN` /
  `GH_TOKEN` from the environment the host started it in.
- **No absolute local path reaches the issue body.** The `AGENTS.md` region writes into the user's
  own working copy, where an absolute path is at worst ugly. This writes into a tracker that may be
  **public**, and `/home/<name>/clients/<client>/ledger.json` stamped on every issue discloses the
  user's name, their layout and often their client. `tools._tracker_label` reduces it to a
  cwd-relative path, or to the bare filename when it is outside.

## Open decision — an issue comment as a reopen signal (designed, NOT built)

The one direction that would be worth having, and the reason it is not here.

**The proposal.** A comment on a projected issue matching a declared form (say `/keel reopen
<reason>`) becomes a `ReopenEvent` on the pin, the way a production `flip_signal` does. It is
attractive for the same reason the rest of this is: the team is already in that surface, and a
reopen is the one ledger write that is *not* an election — the feedback loop and the challenger
both reopen without deciding, so an inbound reopen would not violate "only the human elects".

**Why it stays unbuilt.** Three questions have to be elected before any of it is written, and each
one is a fork a maintainer must answer rather than an implementation detail:

1. **Whose comment counts?** An issue comment box is unauthenticated input from anyone who can see
   the repository. `references/core/knowledge-sources.md` already governs this class — external
   content is untrusted and grounds proposals, never decides — and a reopen *does* move ledger
   state. Repository write access is the obvious bar; whether it is the right one is not obvious.
2. **What does the ledger record as the source?** `reopen` holds `source` to a closed vocabulary
   (`feedback:incident` and its siblings) precisely so an arc that never elects cannot sign itself
   `interview`. A tracker comment is a new origin and would need a new member of that tuple, which
   is a schema change, which is a spec version.
3. **Does a door invalidate the window?** The whole safety argument above is that the direction is
   one-way *by construction* — the module cannot write the ledger. Adding one inbound path means
   that argument becomes a claim about which code path is taken, which is exactly the weaker form
   of guarantee this repo keeps replacing.

Recorded here rather than left as a good idea nobody wrote down. Building it on a hunch would put
an unauthenticated comment box on the write path of the single source of truth.
