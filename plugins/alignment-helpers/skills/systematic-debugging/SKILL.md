---
name: systematic-debugging
description: Find a bug by narrowing a hypothesis against evidence instead of guessing at fixes — reproduce, isolate, prove the cause, fix, then prove the fix. Binds to the decisions ledger as a defect pin so the root cause is recorded, not just the patch. Use when something is broken, a test fails mysteriously, or behavior differs between environments.
license: MIT
---

# Systematic Debugging

Most failed debugging is not a reasoning failure — it is skipping straight to a fix that plausibly
explains the symptom, watching the symptom move, and calling it solved. This is the loop that makes
that impossible, and it is deliberately slower at the start and much faster at the end.

## The loop

1. **Reproduce it deterministically.** A bug you cannot trigger on demand cannot be proven fixed —
   every later step is guesswork. If it reproduces only sometimes, that intermittency *is* the first
   finding: race, ordering, uninitialized state, environment.
2. **Capture the actual evidence.** The real error, the real stack, the real values. Not your
   recollection of them, and not what the code says should happen.
3. **State one hypothesis** that explains **all** the evidence. If it explains only part, it is
   wrong or incomplete — say so rather than proceeding.
4. **Design the cheapest experiment that could REFUTE it.** This is the step that separates
   debugging from guessing. Looking for confirmation finds it every time; a hypothesis that survives
   an honest attempt to kill it is worth acting on. Same discipline the `challenger` applies to an
   elected oracle.
5. **Narrow.** Bisect the input, the commit range, the call path — halve the space each time rather
   than re-reading code hoping to spot it.
6. **Fix the cause, not the symptom.** If you cannot say *why* the fix works, you have not found the
   cause; you have found something that perturbs it.
7. **Prove it.** The failing reproduction from step 1 now passes, and a test asserts it stays fixed
   (`test-driven-development`: break it on purpose, watch the test catch it).

## Binding to the ledger

A bug is a `defect` pin, and the pin holds what a commit message loses:

- `as_is` = the observed wrong behavior, with the reproduction.
- `to_be` = the correct behavior — the same object the test asserts.
- The **root cause** goes in the pin. Six months later the code shows *what* changed; only the pin
  says *why it was wrong in the first place*, which is what stops the class recurring.

```bash
python scripts/runtime/ledger.py summary ledger.json
```

If the cause turns out to be a decision that was wrong rather than code that was wrong, **do not
fix it here** — reopen the decision. Fixing code to work around an unsound elected decision buries
the real finding, and the loop that exists for it is `references/core/feedback-loop.md`.

## Stop rules

- **Two failed hypotheses in a row → widen, don't iterate.** You are narrowing inside the wrong
  region; go back to the evidence.
- **"It works now" without a cause is not done.** Record it as still-open, or you will meet it again
  under a deadline.
- **Never fix by coincidence.** Reverting a change that makes the symptom vanish is evidence about
  location, not about cause.
