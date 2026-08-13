# The tracker projection — the ledger in the board your team already reads

The ledger is the single source of truth and **nobody's team loads it.** Standups happen in front of
an issue tracker; a fork that is not there is a fork that gets re-answered in a thread, verbally,
with nothing written back. That is the divergence this whole package exists to find, happening in
the one surface it had no carrier for.

So the tracker gets what `AGENTS.md` gets (`references/core/instruction-files.md`): **one source, a
generated projection, a round-trip drift check, managed markers.** One issue per open pin, its body
rendered from the pin, its state following the pin's.

## The direction is one-way, and that is the whole design

**The tracker is a window, not a door.** Nothing reads an issue back into `ledger.json` — not a
comment, not a label somebody changed, not a close. This is structural rather than promised: the
projection module never constructs a ledger and never saves one.

Say it out loud to the team the first time you run this, because the instinct is exactly wrong:
**answering the question in a comment decides nothing.** The issue body says so too. An election
happens in the interview (`interview_next` → `ledger_record_decision`) and reaches the tracker on
the next projection. A comment that reads like a decision and changes nothing is worse than no
issue at all, so do not leave the team to discover that rule by being surprised by it.

## Running it

| you want | tool |
|---|---|
| what has drifted between ledger and tracker, changing nothing | `tracker_diff` |
| the tracker brought level with the ledger | `tracker_project` |

Run `tracker_diff` first, always. It costs one request, writes on neither side, and answers the
question a team actually has. Run `tracker_project` when the ledger has moved: after the interview
elects, after a pin resolves, after a reopen. It is idempotent by pin id — a second run against an
unchanged ledger writes nothing at all, which is what makes it safe to put in a hook or a routine.

Both take the ledger and a repository as `owner/name`. **Neither takes a token**, deliberately: the
server reads `GITHUB_TOKEN` / `GH_TOKEN` from its own environment, so no credential ever passes
through an agent's context. The token needs **push access** — GitHub silently drops labels for
tokens without it, and the label is what makes the projection idempotent, so a read-only token
would create a fresh duplicate of every issue on every run. The projection checks for that after
its first create and stops rather than multiplying.

## What each verdict means, and what you do about it

`tracker_diff` returns one plan, in one vocabulary, and `tracker_project` executes that same plan —
so the two can never disagree about what the projection should be.

- **`create` / `update` / `reopen` / `close`** — ordinary drift. Run `tracker_project`.
- **`hand_edited`** — someone wrote inside the managed region. It is **reported, never
  overwritten**, and the issue is skipped until it is dealt with: re-rendering would delete what
  they wrote, and what they wrote may be the only copy of a real decision. Read it, put it in the
  ledger (a pin, a decision, a `flip_criteria`), then project again.
- **`orphan`** — an issue naming a pin the ledger does not hold. Reported and left completely
  alone. Before doing anything about it, check you pointed the tool at the right ledger: the
  cheapest explanation for a tracker full of orphans is a mistyped path, and it is also the one
  where "clean them up" destroys a team's work.
- **`ignored`** — a settled pin that was never projected. No issue is opened in order to close it;
  the ledger's history is not the tracker's to carry.

## What stays yours

Two things are preserved on every run, and both are the same rule at different scales:

- **everything outside the fence** in an issue body — the team's own notes, the thread's context;
- **every label this projection does not own.** It owns `keel` and the `keel:`-prefixed ones; your
  `priority:p1`, your sprint label, your triage survives untouched.

## When it cannot run

It degrades into a result, never a traceback: no token, no network, an unreachable repository, an
exhausted rate limit each come back as `{"available": false, "reason": …}`. Read the reason — and
read it as a fact about the **tracker**, never about the ledger. "The tracker could not be reached"
and "there is nothing to project" are different answers, and this package never conflates the two.

If the run stops early it says so and says where: it stops inside a reserve of the hour's rate
limit rather than spending the user's last requests (that budget is shared with their CI and their
`gh` CLI), and it never retries a rate-limited call. A partial projection that reports itself
partial is the honest outcome; a complete one that gets the token banned is not.

The design, the host facts it rests on, and the one arc that is deliberately **not** built — an
issue comment as a reopen signal — are recorded in the Keel repository's
`docs/design/tracker-projection.md`, a maintainer's note that does not ship with this skill.
