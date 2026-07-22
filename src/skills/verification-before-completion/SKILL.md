---
name: verification-before-completion
description: Prove a change works by exercising it before calling it done — run the thing, observe the behavior, and only then move a pin to resolved. Distinguishes "the tests pass" from "the feature works". Use before claiming any task complete, closing a defect, or reporting a result to the user.
license: MIT
---

# Verification Before Completion

The failure this prevents is not laziness — it is the confident report. Code compiles, tests are
green, the diff looks right, and the claim "done" gets made without anyone running the thing. This
package has a name for that shape: **claiming versus doing**, and it is the failure mode it exists
to find in other people's codebases.

## The rule

**A pin becomes `resolved` when the behavior was observed, not when the code was written.**

Everything else — green CI, a clean typecheck, a passing suite — is evidence *about* the change, not
evidence *of* the outcome. They are necessary and they are not sufficient, because every one of them
can pass while the feature is unreachable, unwired, or wired to the wrong thing.

On AI-generated code the inversion is sharper: a suite that is *fully* green is a reason to **look**,
not to stop. The tests were usually generated with the code and encode the same misunderstanding, so
a 100% pass is a **suspect** signal until you have exercised the real path yourself — once you have
observed the behavior, the green is discharged and you stop. It is a question observation answers, not
a permanent doubt.

## What counts as verification

| claim | insufficient | sufficient |
|---|---|---|
| an endpoint works | the handler has a test | called it, saw the response and status |
| a migration is safe | it applied locally | applied, read the data back, ran the down-path |
| a UI change landed | the component renders in a test | loaded the page, saw it |
| a bug is fixed | a new test passes | the original reproduction no longer reproduces |
| a script is runnable | it is in the repo | ran it **from the directory the user will run it from** |

That last row is the one people skip. A script path that resolves in the repo you are sitting in and
dies in the directory the user actually runs from passes every check that anchors on the file's own
location — and fails for everyone. **Verify from the user's position, not yours.**

## The loop

1. **Name the observable outcome** the pin's `to_be` claims — before running anything.
2. **Exercise the real path.** Drive the actual flow: the endpoint, the command, the page. Not the
   unit test that stands in for it.
3. **Observe.** Read the output, the status, the row, the render. If you cannot observe it, say so
   plainly — an unverifiable claim reported as verified is worse than an open one.
4. **Check the negative.** Does it fail when it should? A change that only ever succeeds has not
   been shown to do anything.
5. **Then** move the pin, and record what you observed as the evidence.

## Reporting honestly

- Tests failed → say so, with the output. Never summarize a failure as progress.
- A step was skipped → say which, and why.
- Verified → say it plainly, without hedging. Earned confidence is information; reflexive hedging
  destroys it.
- **Partially verified is a real state, and it has a ledger form.** "The API returns correctly; I
  could not exercise the frontend" is a useful, honest report; "Done" is not. Record it as what it
  is — the pin stays `needs_input` and the unverified remainder is surfaced as an `incompleteness`
  pin, never silently `resolved`. This is
  the **honest exit** every gate must leave open: when the agent cannot satisfy the verification, it
  says so *in the ledger* rather than fabricating an observation or quietly stopping. A gate that
  blocks without leaving this exit does not prevent the shortcut — it forces it.

## Binding to the ledger

Bind it through the `ledger_*` MCP tools — the server resolves paths, so they work from the user's
cwd (see `using-the-ledger`). Call `ledger_resolve` ONLY after observing: the tool demands the
`evidence`, so a criterion cannot close on "code written" — then `ledger_summary` to confirm nothing
the scope claimed is still open.

An `acceptance_criterion` is the testable outcome, so it is also the verification target: what you
exercise in step 2 is exactly what the criterion states. That is why the criterion has to be
observable when it is written — an untestable criterion produces an unverifiable completion, and the
gap opens back in the interview, not here.

**Green is the executor's claim, not the measurer's evidence.** An `acceptance_criterion` the
executor both writes and codes against is a target it can build *to* — a passing suite proves the code
matches the test, not that it matches the intent. So the `measurer` (and the wave `reviewer`)
**independently re-exercise the behavior** against the elected criterion and **never accept the
executor's self-report** in its place: "it passes" is a claim to check, exactly like green CI —
evidence about the change, not of the outcome. This is independent re-execution, *not* a hidden
criterion: the ledger is one shared source of truth, so it is the same elected oracle, run by a role
that did not write the code.
