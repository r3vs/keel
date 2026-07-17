# The Learner Model — `learner.json` (the operator-gap gradebook)

The structural twin of the decisions ledger. The ledger (`references/core/ledger.md`) measures the
**codebase's** gap and drives its closure; this measures the **operator's** gap and drives the
teaching. Same anti-divergence discipline: a single `learner.json` on disk is the source of truth for
what this user has and hasn't internalized, and every hook reads/writes it — no surface holds a
private opinion of the user's level. Portable, git-ignored per user (it is personal data), never
committed to the project repo.

Without it, "the delta fades as you improve" is an unmeasured hope and "you might be cargo-culting"
is unfalsifiable. The learner model makes both **observable**: it is what ranks the delta, fades the
scaffold, and catches rote execution.

## What it records

The unit is a **category** — a reusable class of judgment the layer can teach and measure (not a
one-off fix). Categories are open-ended and accrue as work surfaces them; seed examples:
`edge-case-enumeration`, `auth-invariants`, `concurrency-TOCTOU`, `error-handling-completeness`,
`contract-shape-drift`, `test-falsifiability`, `reversibility-of-decisions`, `domain:food-contact`.

```jsonc
{
  "user": "opaque-id",                 // never PII; a local handle
  "categories": {
    "concurrency-TOCTOU": {
      "attempts": 7,                    // times the user made a prediction in this category
      "matched": 5,                     // times their prediction already met the senior version
      "streak": 3,                      // consecutive current matches (drives fade)
      "state": "learning",             // untouched | learning | fading | mastered | cargo_cult_watch
      "last_delta": "checked auth before the await, used it after — TOCTOU",
      "exposure_only": 1               // times seen as a passive delta with NO prediction (weak signal)
    }
  },
  "settings": { "micro_retrieval": "on", "max_taught_per_cycle": 2 }
}
```

## The three rules it drives

1. **Rank the delta.** When a reveal produces a multi-item delta, teach the 1–2 items whose category
   is **weakest and live** for this user (low `matched/attempts`, `state: learning`) — at the edge of
   ability, not the whole diff. `max_taught_per_cycle` (default 2) is a hard cap; the rest ship
   untaught.
2. **Fade on evidence, and say so.** When `streak ≥ fade_threshold` (default 3) a category moves to
   `fading` then `mastered`; the layer stops prompting for it and **tells the user** ("you've got
   this — dropping the prompt"). Fade is *measured*, not assumed by time. A later miss reopens it
   (`mastered → learning`), exactly as a fired `flip_signal` reopens a ledger pin.
3. **Detect cargo-cult.** The tell is a **divergence between output and prediction**: deliverables
   keep passing (the layer/gates carry them) while `matched/attempts` stays flat and `exposure_only`
   climbs. That is rote execution, not learning — set `cargo_cult_watch` and escalate from passive
   deltas to an **active interrogation** ("why does this gate fire?") and a low-stakes forced
   prediction. Good output is not evidence of learning; only improving predictions are.

## How the hooks use it

- **Read before a reveal** to decide *whether* to prompt (skip mastered categories) and *what* to
  rank the delta by.
- **Write after each attempt**: increment `attempts`, and `matched` + `streak` on a match, else reset
  `streak` and record `last_delta`. A passive delta with no prediction increments `exposure_only`
  only — it is the weak signal, never counted as a match.
- **Never let it gate delivery.** The learner model shapes *teaching*, never *shipping*. A user on
  `cargo_cult_watch` still gets the senior-grade deliverable; what changes is the coaching, not the
  output.

## Boundary

The learner model measures what the layer **can** verify — categories with a checkable senior
version (the same "prefer the checkable formulation" bias as `references/core/static-analysis.md`).
It deliberately does **not** score frontier judgment, where there is no senior version to match
against; there the layer exposes reasoning and is honest that it cannot grade. Claiming to measure
frontier taste would be the false-confidence failure the model exists to prevent.
