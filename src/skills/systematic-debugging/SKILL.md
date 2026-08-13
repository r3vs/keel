---
name: systematic-debugging
description: Find a bug by building a tight loop that goes red on it, then narrowing a hypothesis against evidence instead of guessing at fixes. Root cause lands in a defect pin. Use when something is broken, a test fails mysteriously, or behavior differs between environments.
license: MIT
---

# Systematic Debugging

Most failed debugging is not a reasoning failure — it is skipping straight to a fix that plausibly
explains the symptom, watching the symptom move, and calling it solved. This is the loop that makes
that impossible, and it is deliberately slower at the start and much faster at the end.

## Redact before you show anything

This skill has you show commands, their output, and captured artifacts. **Redact every secret first**
— write `<REDACTED>` in its place. Build the loop against environment variables so the credential
stays in the environment rather than in the transcript, and quote only the lines that carry the
signal: a captured request carries auth headers, a log dump carries tokens, a stack trace carries
connection strings. If the redacted output is no longer enough to diagnose the bug, say so and ask
the human rather than pasting the unredacted version.

## Phase 1 — build a loop that goes red on THIS bug

**This is the skill. Everything after it is mechanical.** With a **tight** pass/fail signal that goes
**red** on this specific bug, you will find the cause — bisection, hypothesis-testing and
instrumentation all just consume it. Without one, no amount of reading code will save you, and the
confident-sounding theory you produce instead is the failure mode this skill exists to prevent.

Spend disproportionate effort here. Be aggressive, be inventive, and do not give up early.

**Ways to build one, roughly in this order:**

1. **Failing test** at whatever seam reaches the bug — unit, integration, end-to-end.
2. **HTTP script** (`curl`, a request file) against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** driving the UI, asserting on DOM, console or network.
5. **Replay a captured trace** — save the real payload, request or event log to disk and push it
   through the code path in isolation.
6. **Throwaway harness** — the smallest subset of the system (one service, stubbed dependencies)
   that reaches the bug in a single call.
7. **Property or fuzz loop** — for "sometimes wrong output", run a thousand inputs and look for the
   failure mode.
8. **Bisection harness** — if it appeared between two known states (commit, dataset, version),
   automate "boot at state X, check, repeat" so `git bisect run` can consume it.
9. **Differential loop** — same input through two versions or two configs, diff the outputs.
10. **A human in the loop, scripted.** Last resort, and still structured: hand the human an exact
    sequence and a place to paste what they saw, so the result comes back as evidence rather than as
    a recollection.

**Then tighten it — treat the loop as a product.** Faster (cache the setup, skip unrelated init,
narrow the scope), sharper (assert the specific symptom, not "did not crash"), more deterministic
(pin the clock, seed the RNG, isolate the filesystem, freeze the network). A flaky thirty-second loop
is barely better than none; a deterministic two-second one is the whole game.

**Non-deterministic bugs: the goal is a higher reproduction rate, not a clean repro.** Loop the
trigger a hundred times, parallelise, add load, narrow the timing window, inject sleeps. A bug that
reproduces half the time is debuggable; one in a hundred is not — keep raising the rate until it is.

### The completion criterion — one command, already run

Phase 1 is done when you can name **one command** — a script path, a test invocation, a request —
that you have **already run at least once**, showing the invocation and its (redacted) output, and
that is:

- **Red-capable** — it drives the actual bug code path and asserts the **human's exact symptom**, so
  it can go red now and green once fixed. Not "runs without erroring".
- **Deterministic** — same verdict every run, or a pinned high reproduction rate.
- **Fast** — seconds.
- **Runnable unattended** — you can re-run it yourself, without a human clicking.

If you catch yourself reading code to build a theory before that command exists, **stop**. Jumping to
a hypothesis is the exact failure this phase prevents. No red-capable command, no Phase 2.

**When you genuinely cannot build one**, say so explicitly, list what you tried, and ask for the one
thing that would unblock it — access to an environment that reproduces it, a redacted captured
artifact, or permission to add temporary instrumentation. Do **not** proceed to hypothesise. That is
also the moment to surface the absence as a pin rather than swallow it
(`references/core/assumptions.md`): a bug nobody can reproduce is a fact about the system, not a
gap in your effort.

## Phase 2 — reproduce, then minimise

Run the loop. Watch it go red. Confirm it is **the human's** failure mode and not a different one
that happens to live nearby — wrong bug, wrong fix.

Then shrink the repro to the **smallest scenario that still goes red**: cut inputs, callers, config,
data and steps **one at a time**, re-running after each cut. Done when every remaining element is
load-bearing — removing any one of them turns it green. A minimal repro shrinks the hypothesis space
in Phase 3 and becomes the regression test in Phase 5.

## Phase 3 — hypothesise, plural and falsifiable

Generate **three to five ranked hypotheses before testing any of them**; a single hypothesis anchors
you on the first plausible idea. Each must state the prediction that could kill it — *"if X is the
cause, then changing Y makes it disappear"*. A hypothesis with no prediction is a vibe: sharpen it or
drop it.

**Design the cheapest experiment that could REFUTE the top one.** This is the step that separates
debugging from guessing: looking for confirmation finds it every time, and a hypothesis that survives
an honest attempt to kill it is worth acting on. Same discipline the `challenger` applies to an
elected oracle.

Show the ranked list to the human before testing. They re-rank it instantly more often than not
("we deployed a change to #3 yesterday"). Do not block on it if they are away.

## Phase 4 — instrument, one variable at a time

Each probe maps to a specific prediction from Phase 3. A debugger or REPL breakpoint beats ten log
lines; targeted logs at the boundary that *distinguishes* two hypotheses beat logging everything and
grepping.

**Tag every debug log with a unique prefix** — `[DEBUG-a4f2]` — so cleanup is one grep. Untagged
instrumentation survives; tagged instrumentation dies.

For a performance regression, logs are usually the wrong tool: establish a baseline measurement
(timing harness, profiler, query plan) and bisect against it. Measure first, fix second.

## Phase 5 — narrow, fix the cause, prove it

**Narrow** by halving the space each time — the input, the commit range, the call path — rather than
re-reading code hoping to spot it.

**Fix the cause, not the symptom.** If you cannot say *why* the fix works, you have not found the
cause; you have found something that perturbs it.

**Write the regression test before the fix — if there is a correct seam for it.** A correct seam is
one where the test exercises the real bug pattern *as it occurs at the call site*. A unit test that
cannot replicate the chain that triggered the bug gives false confidence, which is worse than no
test. **If no correct seam exists, that is itself the finding**: raise it as a `design_concern` pin
(`references/core/module-design.md` for the vocabulary to say where the seam belongs), because the
architecture is what is preventing the bug from being locked down.

Where a seam exists: turn the minimised repro into a failing test, watch it fail, apply the fix,
watch it pass, then re-run the Phase 1 loop against the original un-minimised scenario.

## Phase 6 — clean up, and record the cause where it survives

- The Phase 1 loop no longer goes red.
- The regression test passes, or the absence of a seam is recorded as a pin.
- Every `[DEBUG-…]` probe is gone (grep the prefix).
- Throwaway harnesses are deleted or clearly marked as such.

## Binding to the ledger

Prefer the `ledger_*` MCP tools (the server resolves paths, so they work from the user's cwd); the CLI below is the floor when the MCP server is absent — see `using-the-ledger`.

A bug is a `defect` pin, and the pin holds what a commit message loses:

- `as_is` = the observed wrong behavior, **with the Phase 1 command as its reproduction**.
- `to_be` = the correct behavior — the same object the test asserts.
- The **root cause** goes in the pin's `as_is` (or `kind_detail`). Six months later the code shows *what* changed; only the pin
  says *why it was wrong in the first place*, which is what stops the class recurring.

Record it through the ledger's MCP tools: `ledger_add_pin` opens the `defect` (root cause in
`as_is`, provenance the reproduction at the test); `ledger_add_remediation` plans the fix and
`ledger_set_remediation_status` marks it done; then `ledger_resolve` closes it against the OBSERVED
reproduction — the tool demands `evidence` **and `rung="observed"`**, so the pin cannot close until
the repro no longer reproduces and you say that you watched it not reproduce. A pin that records no
verification at all is refused exactly like one whose verification was weak: absence is the weakest
reading, never permission.

**Phase 1 is what makes that gate reachable.** `rung="observed"` demands a behavior somebody watched;
the tight loop is the thing that does the watching. Skip Phase 1 and the honest close available to
you is `correctness_unknown`, not `resolved`.

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
- **The post-mortem question, asked after the fix is in and not before:** what would have prevented
  this? When the answer is architectural — no good seam, tangled callers, hidden coupling — that is a
  pin, not a paragraph in the commit message. You know more now than you did at the start, which is
  exactly why the question waits until the end.
