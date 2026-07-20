---
name: test-driven-development
description: Write the failing test first, then the code that passes it — with the red step recorded as an acceptance_criterion pin in the decisions ledger, so what the test proves is the same object the interview elected. Use when implementing any BuildItem, fixing a defect, or when asked to add tests to existing code.
license: MIT
---

# Test-Driven Development

Red → green → refactor, with one addition that makes it more than a habit: **the red step is a
ledger pin.** A test written first is a claim about required behavior, and this package already has
a place where required behavior lives — `acceptance_criterion`. Writing the test without recording
the pin gives you TDD that forgets; recording the pin without the test gives you a criterion nothing
enforces. Do both, in that order.

## The loop

1. **Pin the criterion.** Before writing code, the outcome exists as an `acceptance_criterion` pin
   whose `to_be` is the observable behavior. It came from the interview (greenfield) or from a
   `defect` you are closing (rescue). If there is no pin, stop — you are about to build something
   nobody elected.
2. **Write the failing test.** It must fail for the *stated* reason. A test that fails because the
   import is broken proves nothing about behavior.
3. **Watch it fail.** Run it. An unobserved red step is an assumption, and this package makes
   assumptions vetoable rather than silent (`references/core/assumptions.md`).
4. **Write the minimum that passes.** Not the design you plan to end at — the minimum. The design
   lives in the contract; this step only satisfies the criterion.
5. **Watch it pass, then refactor** with the test as the harness.
6. **Only now** may the pin move toward `resolved` — and `verification-before-completion` decides
   whether it actually gets there.

## The rule this skill exists to enforce

**A test written after the code is a description; a test written before it is a specification.**
Both pass. Only one could have failed. When you are handed code with no tests, you cannot recover
the red step retroactively — so write the test, then *break the code on purpose* and watch the test
catch it. That restores the only property that made the red step worth anything.

## Binding to the ledger

```bash
python scripts/runtime/ledger.py summary ledger.json
```

- The pin's `to_be` is the assertion, in words. If you cannot state it as an observable outcome, the
  criterion is not testable yet and the gap is in the interview, not in your test file.
- One criterion, one test, one `BuildItem`. `buildloop.py` roots its dependency DAG at these pins,
  so a criterion that maps to no test is a DAG node that can never be shown complete.
- **Never invent a criterion to justify code you already wrote.** That is deriving the to-be from
  the as-is — the exact circularity this package refuses. Surface it as an `open_decision` instead
  and let the human elect it.

## Mutation is the honest coverage metric

Coverage says the line ran. Mutation says the test would have noticed if the line were wrong. On
AI-generated code the tests are usually generated too, so treat them as suspect artifacts rather
than as evidence: high coverage plus high mutation-survival is coverage theater, and it is the
strongest signal for where to look. The `codebase-rescue` skill's test-validity module runs this
as a full audit when you need the verdict on an existing suite.
