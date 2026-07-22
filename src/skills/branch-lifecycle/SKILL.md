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

## During — commit against pins

- Commit at each green step, referencing the pin: the ledger says *why*, the commit says *what*.
- **Never commit on the default branch.** Branch first, always.
- A shared file (types, config, schema) belongs to **one** scope. Assign it explicitly rather than
  hoping two agents edit it politely.
- Rebase on the base branch often. Never auto-resolve a conflict in code you did not write — a
  conflict is a finding about overlapping scope, and resolving it silently destroys that signal.

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

The branch is a **reader** here: before finishing, confirm no pin the scope claimed is still open.

```bash
python scripts/runtime/ledger.py summary ledger.json   # a needs_input or decided-not-resolved pin blocks the finish
```

Pins are closed **during** the work with `resolve … --evidence` (see `verification-before-completion`),
not batched at the end.

The branch exists to close pins. If you cannot name which pins a branch closes, the work was never
scoped — go back and scope it. And if the work reveals the *decision* was wrong rather than the code,
reopen the pin instead of finishing the branch: shipping a scope that satisfies an unsound decision
is the fastest way to bury the finding that mattered.
