# Module: Logic & Correctness (judgment, highest FP risk)

Finds the subtle, executes-but-wrong problems that tools miss. Model reasoning over the graph +
the elected `to_be` — so it runs partly after the interview (it needs to know intended
behavior), or iteratively as `to_be` fragments crystallize.

## What it looks for
- **Silent failures**: swallowed errors, ignored return values, unchecked None/null/undefined,
  fallthroughs that hide problems (the ~45% silent-failure signature of vibecoded code).
- **Wrong business logic**: behavior that contradicts the elected `to_be`.
- **Unhandled states**: missing branches, non-exhaustive enum/`match` handling, absent error
  paths, race-y state on concurrent paths.

## Discipline (this module over-reports the most)
- **Every finding hard-gated through `fp-check`** with reachability + corroboration. No
  exceptions.
- **Prefer `ambiguity` over `defect` when intent is unclear.** "Is this fallthrough intended?"
  is a question; asserting a bug on ambiguous intent is the opinion-as-finding failure.
- Silent failures on a reachable prod path → high/blocker; the same on an unfinished path →
  `incompleteness` (route through completeness first).

## Why it needs the to_be
Without the elected intended behavior, "wrong logic" is just the model's opinion. This module
is only trustworthy once Phase 2 has established what the code is *supposed* to do — which is
why the workflow reconstructs intent before judging correctness.
