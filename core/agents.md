# Agent Roster (shared core) — neutral source of truth

The agent roles both skills run on, defined **once, platform-neutrally**. The per-platform
adapters materialize this roster into their native formats — Claude Code `agents/<role>.md`,
opencode `.opencode/agent/<role>.md` (or the `agent` block in `opencode.json`). Keep those in sync
with this file; this is the source.

## The discipline: serialized writing, parallel reading

Only **one** role writes code — the `executor`, one closed scope at a time. Every other role is
**read-only** and may fan out in parallel. This is the anti-divergence property applied at the
agent level, exactly as the single `ledger.json` applies it at the state level: many readers can
diverge harmlessly (they only propose/verify), one writer cannot. Each role runs in a **fresh
context** and communicates only through the ledger + artifacts on disk — never a shared session.

And the hard rule both skills already enforce: **only the human's committed answer in the
interview elects a decision.** No agent commits. Agents find, propose, build, and verify; the
person decides.

## The roles

| Role | Writes? | Job | Phases |
|------|---------|-----|--------|
| **researcher** | no (read-only) | Comprehension & finding; catalog/threat research; grounding via `core/knowledge-sources.md`. Fans out. | rescue P1 · greenfield P1 (frame, threat-model) |
| **brainstorm** | no (proposals only) | Proposes 2–3 options with tradeoffs to `pin.brainstorm.proposals[]`, grounded and cited; never decides. | on-demand · greenfield P2 hard forks |
| **executor** | **yes (the one writer)** | Implements ONE closed scope (a `RemediationItem`/`BuildItem`) via two-track TDD in fresh context; opens a PR; **never merges**. Serialized. | rescue P4 · greenfield P4 build, P6 release |
| **reviewer** | no (read-only) | Adversarial pre-merge gate. Two stages: spec-compliance vs `to_be` → code quality. Verdict `MERGE`/`ADJUST`/`REJECT`; ADJUST/REJECT restart the item. Also the wave-checkpoint reviewer. A rejection **teaches** (see below). | rescue P4 · greenfield P4 |
| **challenger** | no (challenges only) | Adversarial red-team of the elected **oracle** — the reviewer's upstream twin. The reviewer enforces the `to_be`; the challenger doubts it. Refutes `acceptance_criterion`/`to_be`/`Policy` as unfalsifiable / inconsistent / unsatisfiable / resting on an unstated assumption / ignoring fan-out; emits a `ChallengeEvent` that reopens the pin (`challenged`). Neutral: challenges, never decides. | rescue P2→P4 · greenfield P2→P4 |
| **measurer** | no (read-only) | Data/evidence verdict: Phase-5 validation, and evaluating `flip_signal`s in the feedback loop. Never guesses, never writes. | rescue P5 · greenfield P5, P7 evolve |

## Permissions (for the adapters)

- `researcher`, `brainstorm`, `reviewer`, `challenger`, `measurer` → **edit: deny** (read-only; may read, search, run read-only tools, fetch grounded sources). The `challenger` additionally writes **only** `ChallengeEvent`s and may set a challenged pin back to `needs_input` — never a `DecisionEvent`, never code.
- `executor` → **edit: allow** (the single writer; still gated by the reviewer and the Phase-5 evidence gate).

## Mapping notes

- The two-stage review the phase playbooks describe **is** the `reviewer`; the "data decides"
  Phase-5 gate **is** the `measurer`; the brainstorm agent **is** `brainstorm`; the
  comprehension/finding pass **is** the `researcher`; the remediation/build loop **is** the
  `executor`. This roster names what the phases already imply, and adds the explicit
  single-writer/parallel-reader orchestration.
- Grounding for `researcher` and `brainstorm` follows `core/knowledge-sources.md` (Context7 /
  DeepWiki / registry / web), cited and confidence-tagged, treated as untrusted input.
- The `challenger` is the **upstream** twin of the feedback loop (`core/feedback-loop.md`): the
  feedback loop reopens a decision when *production* falsifies it (downstream), the challenger
  reopens it when the *oracle itself* is unsound (upstream, before build). Both **reopen and never
  decide** — same schema-enforced neutrality as the brainstorm. Its `ChallengeEvent` schema and the
  `unstated_assumption` precondition live in `core/decisions-ledger-spec.md` (v0.6) and
  `core/assumptions.md`. It runs right after the interview commits (Phase 2) and again at each wave
  checkpoint (Phase 4), so an unsound oracle is caught before, not after, code rests on it.

## Teach on rejection (a gate that blocks must also teach)

Every read-only gate here can **block** — the reviewer REJECTs, the challenger reopens, the measurer
withholds `resolved`. A gate that only blocks maximizes today's output and freezes tomorrow's skill;
a gate that *teaches* raises the operator too. So a blocking verdict is never a bare code: it names
the **class** that was violated and **how to recognize it next time** (e.g. "REJECT — this is a
TOCTOU race: the check and the use straddle an `await`", not "REJECT — concurrency bug"). The class,
not the instance; the pattern gets a name. This costs one sentence, is emitted whether or not anyone
reads it (passive, opt-out), and is what the `learning-layer` skill consumes to close the operator
gap. Enforce the oracle *and* explain the enforcement.
