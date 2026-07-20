# Module: Test Validity (deterministic, gated)

Anti coverage-theater. On slop the tests are usually AI-generated too, so **treat tests as
suspect artifacts to audit, not as evidence.** High coverage means nothing if the tests don't
constrain behavior.

## Method
- **Mutation testing** per language (mutmut / stryker / pit / cargo-mutants). Slow → run ONLY
  on critical modules (auth, money, data integrity, anything on a blocker path).
- **Coverage as a cheap pre-filter**: high coverage + high mutation-survival = theater; that
  combination is the strongest signal to target.

## Run it

```bash
mutmut run --paths-to-mutate src/auth        # or: stryker / pit / cargo-mutants, per stack
python scripts/runtime/findings.py .audit/mutation.sarif
```

Mutation tools that emit SARIF go through `findings.py` like every other finding source, so a
surviving mutant becomes a pin by the same path as an SQLi. Those that only print a report are read
into the pin mapping below by hand — and note *why* that is acceptable here and not elsewhere: the
mapping below is a genuine judgment ("is this module effectively untested?"), which is why this
module is the one place where reading a report is the work rather than a shortcut around it.

## Pin mapping
- Surviving mutants → `design_concern` or `defect`: "tests exist but do not constrain
  behavior." The remediation is stronger tests, or acknowledging the module is effectively
  untested.
- Feeds Phase 5: a fix's new test must KILL the relevant mutants to count as validated (green
  tests that survive mutation do not validate anything).

## Gate interaction
Because it's slow, schedule it after clustering so you only mutate the modules that actually
matter, and let its results inform which `resolved` claims Phase 5 can trust.
