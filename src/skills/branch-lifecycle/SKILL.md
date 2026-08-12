---
name: branch-lifecycle
description: Run work on a branch or git worktree from start to finish — branch per scope, commit against pins, keep parallel agents from colliding, and finish cleanly. Makes the executor's "one scope at a time" enforceable by giving each scope its own tree. Use when starting a unit of work, running agents in parallel, or finishing a development branch.
license: MIT
---

# Branch & Worktree Lifecycle

The roster's core safety rule is **serialized writing, parallel reading** — only the `executor`
writes, one scope at a time (`references/core/agents.md`). Prose cannot enforce that. A worktree
can: two agents in two trees cannot corrupt each other's files no matter what they do.

## Start — a branch per scope, and the scope is on disk

```bash
git checkout -b <scope>                    # sequential work
git worktree add ../wt-<scope> -b <scope>  # parallel work: an isolated tree per scope
```

Before any agent starts, **write the scope down**: which pins it closes, and which file globs it may
touch. That file is what makes "one scope at a time" checkable instead of promised — an agent's
scope is a declared fact, not a shared assumption, and two scopes whose globs intersect must not run
concurrently.

Distinguish two relations, because conflating them is how a schedule deadlocks or corrupts:
- **`depends_on`** — B needs A's *result*. Ordering.
- **`conflicts_with`** — B and A touch the same files. Mutual exclusion, no ordering implied.

Independent scopes go in parallel worktrees. Conflicting scopes serialize, whatever the DAG says.

### The tree protects the files. It does not protect the item.

Both relations above are about **files**, and so is the worktree: two agents in two trees cannot
corrupt each other's work. Neither says anything about who is doing the *item*. Two sessions
resolving the same pin may legitimately touch disjoint files — one writes the fix, one writes the
test — so `conflicts_with` correctly reports no conflict while both do the same work, and nobody
finds out until the merge. On a pin that carries a question it is worse than waste: the second
session asks the human something the first already answered.

So take the item as well as the tree:

1. `ledger_frontier` — what is open, unblocked **and unclaimed**, beside who holds the rest. Pick
   from the first list.
2. `ledger_claim` — take the pin **before** you start. A claim taken afterwards is a receipt.
   `claimed: false` names the holder: that is a normal answer, so pick something else.
3. `ledger_release` — you stopped without finishing. Settling the pin releases it for you, so this
   is only for the other ending; with no holder it also clears up after a session that died.

A claim expires on its own, so nothing is parked forever, and it never blocks a write: if the human
tells you to work a pin somebody holds, work it. It stops two sessions doing one job — the tree
stops them doing it to the same file.

## During — commit against pins

- Commit at each green step, referencing the pin: the ledger says *why*, the commit says *what*.
- **Never commit on the default branch.** Branch first, always.
- A shared file (types, config, schema) belongs to **one** scope. Assign it explicitly rather than
  hoping two agents edit it politely.
- Rebase on the base branch often. Never auto-resolve a conflict in code you did not write — a
  conflict is a finding about overlapping scope, and resolving it silently destroys that signal.

## The wide refactor — the scope no vertical slice can hold

One mechanical change whose **blast radius** fans across the whole codebase — rename a column,
retype a shared symbol, move a package — cannot be a normal scope. Every slice of it breaks
thousands of call sites at once, so no slice lands green, and forcing it into one produces a branch
that is red for days and conflicts with everything.

Sequence it **expand → migrate → contract** instead, and let the DAG carry the ordering:

1. **Expand.** Add the new form *beside* the old one. Nothing breaks, because nothing has moved.
2. **Migrate**, in batches sized by blast radius — per package, per directory. Each batch is its own
   scope, each `depends_on` the expand, and CI stays green batch to batch because the old form is
   still there. Batches that touch disjoint trees run in parallel worktrees; batches that share a
   file are `conflicts_with` and serialize, exactly as any other scope.
3. **Contract.** Delete the old form once no caller remains, in a scope that `depends_on` every
   migrate batch.

Where even a batch cannot stay green alone, keep the sequence but give the batches a shared
integration branch that they all block, and promise green **only there** — declared up front, so a
red batch is the plan rather than a surprise. *Make the change easy, then make the easy change*: the
expand step is the "make it easy" half, and it is the half that gets skipped.

## Finish — and this is where discipline usually collapses

1. `verification-before-completion` — the behavior was observed, not merely tested.
2. Every pin the scope claimed is actually `resolved`. **A pin still `needs_input` blocks the
   finish**; unfinished work merged as finished is precisely the state this package rescues others
   from.
3. The full suite and the gates pass — on the merge result, not on the branch in isolation.
4. Merge, then clean up:

```bash
git worktree remove ../wt-<scope>
git branch -d <scope>
```

5. **Leave nothing dangling.** A stale worktree is a tree an agent can still write into, silently,
   long after everyone believes the scope is closed.

## Binding to the ledger

Bind it through the `ledger_*` MCP tools — the server resolves paths, so they work from the user's
cwd (see `using-the-ledger`).

The branch is a **reader** here: before finishing, confirm with `ledger_summary` that no pin the
scope claimed is still open — a `needs_input` or decided-not-resolved pin blocks the finish.

Pins are closed **during** the work with `resolve … --evidence` (see `verification-before-completion`),
not batched at the end.

The branch exists to close pins. If you cannot name which pins a branch closes, the work was never
scoped — go back and scope it. And if the work reveals the *decision* was wrong rather than the code,
reopen the pin instead of finishing the branch: shipping a scope that satisfies an unsound decision
is the fastest way to bury the finding that mattered.
