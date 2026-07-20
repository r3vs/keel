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
- **Partially verified is a real state.** "The API returns correctly; I could not exercise the
  frontend" is a useful, honest report. "Done" is not.

## Binding to the ledger

```bash
python scripts/runtime/ledger.py summary ledger.json
```

An `acceptance_criterion` is the testable outcome, so it is also the verification target: what you
exercise in step 2 is exactly what the criterion states. That is why the criterion has to be
observable when it is written — an untestable criterion produces an unverifiable completion, and the
gap opens back in the interview, not here.
