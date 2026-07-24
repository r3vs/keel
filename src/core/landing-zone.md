# Landing-Zone Readiness (shared core)

Before planning a change **onto code that already exists**, ask whether the ground can bear it. This
is a **premortem of the terrain**, and it is deliberately distinct from the two doubts the package
already carries:

| Gate | Doubts | When |
|------|--------|------|
| `challenger` | the **oracle** — is the elected `to_be` / criterion sound? | after the interview |
| wave checkpoint | the **build** — did this wave actually close? | during Phase 4 |
| **landing zone** | the **terrain** — can this code bear the change at all? | before planning the change |

The failure it prevents is specific and common: a correct plan, executed correctly, onto a zone that
was never going to hold it. Adding a feature to a fragile, untested, heavily-coupled area is not a
planning problem — planning harder produces a better plan that fails anyway.

## What it computes, and what it refuses to compute

The **zone** is the blast radius of the planned change: the pins' anchors plus what transitively
depends on them. The **evidence** is four carriers, every one `D0`:

| Signal | Carrier | Says |
|--------|---------|------|
| open pins in the zone | the ledger itself | you are about to build on ground this ledger already calls broken |
| untested files | the graph — does a test file import it *directly* | nothing exercises this |
| churn | `git log` | this area moves constantly |
| coupled outside the zone | `git log` co-change | changing here has historically forced changes there |

The **verdict** — `ready` / `harden_first` / `redesign` — is `D2`, judgment over that evidence, and
the ledger records both levels rather than blending them (`core/trust-axes.md`). The runtime computes
facts and **refuses to conclude**. Inventing a threshold here (*"coupling above 0.6 means harden"*)
would be a number with no carrier wearing a green badge — exactly what the trust-axes doc forbids.

Two deliberate refusals, both consistent with how `blast_radius` already behaves: a **stale graph**
raises rather than degrades (a zone computed at another commit describes ground that has since
moved), and an **unresolvable anchor** is reported rather than dropped (a zone built from half the
anchors is not a smaller zone, it is an unknown one).

The co-change signal is worth naming separately: it is a **second, independent carrier** for the same
thesis the field-shape engine serves. Shapes compare *declared structure*; co-change compares
*recorded behaviour* — what the team has actually had to edit together. Two carriers agreeing is a
strong finding. **Two disagreeing is itself the finding**, which is why they are reported side by
side and never merged into one score.

## Acting on the verdict

- **`ready`** → plan the change directly.
- **`harden_first`** → the named prerequisite pins **block** the change. They join `depends_on`, so
  the wave scheduler orders them first with no new mechanism, and the existing rule that only
  `resolved`/`accepted` closes an edge means the change cannot start until the ground is really
  fixed. *Make the change easy, then make the easy change.*
- **`redesign`** → reshape the change to avoid the unsafe zone entirely.

## The two disciplines that keep it bounded

Without bounds this gate becomes an open-ended rewrite — which is the failure mode of every
"improve the codebase first" instinct.

- **Blast-radius-scoped.** Evidence counts only what lies *inside* the zone. A hotspot elsewhere is
  not this change's problem and never enters the bundle.
- **Change-justified**, and this one is **enforced, not promised**: a pin may become a hardening
  prerequisite only if its own anchors land in the zone. The ledger refuses the edge otherwise.
  Remediation is admitted because it reduces *this* change's risk, never because the code is
  imperfect somewhere else.

`harden_first` naming no prerequisites is refused too: that is a worry, not a verdict.

## Why this is the bridge between the two skills

Rescue derives the to-be backward from existing code; forge elects it forward and builds. They have
always shared the ledger, but they were still two workflows meeting at a handoff.

The hardening edge makes them **one DAG**: a rescue pin becomes a *blocking prerequisite* of a forge
build item, ordered by the same scheduler, closed by the same evidence rule. And the zone that
hardens itself is the same zone that has earned the ability to be *verified* — which is what the
verification exit asks for one step later, when a change that cannot be observed lands in
`correctness_unknown` instead of a green close.

## Output

A `readiness` object on the pin: the verdict with its two determinism levels, the zone, the four
evidence carriers, and — for `harden_first` — the prerequisite pins, which are also `depends_on`
entries so the roadmap orders itself.
