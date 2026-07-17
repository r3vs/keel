# Module: Test Validity (deterministic, gated)

Anti coverage-theater. On slop the tests are usually AI-generated too, so **treat tests as
suspect artifacts to audit, not as evidence.** High coverage means nothing if the tests don't
constrain behavior.

## Method
- **Mutation testing** per language (mutmut / stryker / pit / cargo-mutants). Slow → run ONLY
  on critical modules (auth, money, data integrity, anything on a blocker path).
- **Coverage as a cheap pre-filter**: high coverage + high mutation-survival = theater; that
  combination is the strongest signal to target.

## Pin mapping
- Surviving mutants → `design_concern` or `defect`: "tests exist but do not constrain
  behavior." The remediation is stronger tests, or acknowledging the module is effectively
  untested.
- Feeds Phase 5: a fix's new test must KILL the relevant mutants to count as validated (green
  tests that survive mutation do not validate anything).

## Gate interaction
Because it's slow, schedule it after clustering so you only mutate the modules that actually
matter, and let its results inform which `resolved` claims Phase 5 can trust.
