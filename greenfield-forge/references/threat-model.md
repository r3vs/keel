# Module: Threat Model (design-time security)

The preventive mirror of rescue's reactive security modules (SAST / secrets / SCA). Rescue
*finds* vulnerabilities in code that exists; this module elects security **as decisions, before
the code exists** — so the mitigations are designed in, not bolted on after a scanner screams.
It materializes security `open_decision` pins via **STRIDE** over the to-be map, feeding the
Phase-2 interview and generating mitigation BuildItems in Phase 3.

## Procedure

### 1. Enumerate the elements worth modeling
From the decided data model and boundaries (Phase 1's to-be map): entry points, data stores,
trust boundaries, external integrations, and the assets behind them (auth, payments, PII, tenant
data). Only **decided** elements — you do not threat-model what a decision hasn't scoped in (YAGNI).

### 2. Run STRIDE per element
For each element, walk the six classes and keep the ones that apply:
**S**poofing · **T**ampering · **R**epudiation · **I**nformation disclosure · **D**enial of
service · **E**levation of privilege. Each applicable threat becomes an `open_decision`
(`provenance: "threat-model"`): *"how do we handle `<threat>` on `<element>`?"* with options
framed as **accept · mitigate · transfer** and their tradeoffs.

### 3. Cluster and set severity by asset
Cluster threats by element so the interview asks once. Severity follows the asset: auth,
payments, and PII elements → `high`/`blocker` (always `asked`); low-value assets → may ride a
policy default. A threat is an **option, not a defect** — "accept this risk" is a legitimate,
recorded answer for a low-value asset. Never assert a threat as a finding (that is rescue's job,
on existing code, and even there it is gated).

### 4. Interview (via the shared funnel)
Policies first — they auto-resolve the tail: "default-deny authorization", "validate at the
contract boundary", "encrypt PII at rest", "no secrets in code". The genuine forks (how to
mitigate a real threat on a sensitive asset) are `asked`. Each committed answer carries a
`flip_criteria` — e.g. "revisit rate-limiting when traffic crosses N rps" — which the Operate
phase can then watch.

## Output

Security `open_decision`s → once decided, mitigation `BuildItem`s in Phase 3 (they fold into the
contract and the paved road: authz middleware, input validation at the boundary, encryption
config, audit logging). Where a mitigation is behavioral, its Track-A test encodes the security
assertion (e.g. a test that an unauthorized request is denied) — so security is validated by the
same evidence gate as everything else.

## Relationship to rescue

Same STRIDE lens, opposite direction: rescue can run it over an **as-is** to surface missing
mitigations as findings; greenfield runs it **forward**, elects the mitigations before any code
is written, and records them in the shared ledger. A forged project therefore arrives at rescue
(later) with its threat decisions already on record — one more loop closed.

## What NOT to do

- Do not present a threat as a defect. It is a decision with tradeoffs; `accept` is valid.
- Do not threat-model undecided elements. No speculative hardening of things not yet scoped.
- Do not let it become a security questionnaire. Same funnel discipline: cluster → policy →
  exception; the policies carry the bulk.
