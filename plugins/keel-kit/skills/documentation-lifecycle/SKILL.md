---
name: documentation-lifecycle
description: Plan, write, ground and maintain documentation as a governed artifact — register a doc with its subject, owner and source files before writing it, block any code reference that does not resolve, and track graded staleness by distance from what changed. Use when writing or regenerating docs, or when asking which docs a change invalidated.
disable-model-invocation: true
license: MIT
---

# Documentation Lifecycle

Documentation is the one artifact a coding agent produces that **nothing checks**. Code has a
compiler, a type-checker and a test suite; prose has a reader who assumes it is true. That asymmetry
is why AI-written docs go wrong in a specific, boring way — they name functions, flags and files
that do not exist — and why this skill exists as machinery rather than advice.

Four steps, and only the middle one is judgment.

## 1. Register before you write (`doc_register`)

A doc is registered with its **subject**, **owner** and **source files** *before the prose exists*.
That inverts the usual order for a reason: a catalog built from files that already exist can only
describe what somebody already wrote, so "nobody has documented the payment flow" stays a discovery
instead of becoming a query.

The source set is also what makes the doc checkable at all. A doc anchored to no code can never be
stale, which sounds like a feature and is the opposite — `doc_freshness` reports those separately as
a gap, not a pass.

## 2. Gather, then think, then write — in that order

The failure mode is writing first and looking things up to justify it. Collect the sources
(`graph_query`, `explain_node`, the files themselves), form the explanation, *then* draft. When an
external API is involved, get its **current** shape (`references/core/knowledge-sources.md`) rather
than its training-cutoff shape.

**A doc an agent will read is written under different rules than one only a human reads**, and this
is where they apply: `references/core/writing-for-agents.md` holds them — the pointer's wording is
what decides whether the material is ever reached, always-loaded prose is a correctness constraint
and not just a cost, and an instruction the model already obeys by default pays load to say nothing.
The user's own `AGENTS.md` is the sharpest case: it is loaded on every turn, so a line that fails
the no-op test there is charged for on every turn.

**Never bootstrap truth from generated docs.** An agent-written doc is a *derived* artifact: it may
feed retrieval afterwards, it may never be the path by which the system learns what the code does.
A pipeline that writes docs and then re-ingests them to answer questions has built a loop that
confirms itself, and its confidence will rise exactly as its accuracy falls. Rung 1 is the code
(`references/core/knowledge-sources.md`).

## 3. Ground it before publishing (`docs_claims`, `mode: publish`)

Every backticked reference is a **claim about the code**, and it is checked against the graph before
the prose reaches anyone. A reference that does not resolve is dropped, fixed, or explicitly marked —
never published as fact.

This is case 1 of the determinism dial (`references/core/trust-axes.md`): a symbol table already
encodes the answer, so asking a model would be slower *and* worse. It is also the check this package
needed on itself — a `SKILL.md` naming an MCP tool that did not exist yet is the same bug, one layer
up.

Two publishing modes, because the honest answer differs:
- **`publish`** — prose about code that exists. A dangling reference **blocks**: it is a typo or a
  lie.
- **`publish_prospective`** — a design doc or plan that deliberately names unbuilt things. Dangling
  references are listed to be marked, not banned. The danger there is the *present tense*, not the
  plan.

(The third mode, `audit`, is the inbound direction: the docs a repo already has.)

The gate resolves references and claims nothing about meaning. Whether a symbol that *does* resolve
is described correctly is judgment, and stays with you.

## 4. Track staleness by distance, not by a flag (`doc_freshness`)

`built_at_commit` gives one bit for a whole artifact. A doc rots unevenly:

| Distance | What changed | Reading |
|---|---|---|
| 0 | a file the doc directly cites | the doc is **invalid** — a hash equality, no assumptions |
| 1 | something that **imports** a cited file | the described behavior may have moved under it |
| 2 | something that historically **co-changes** with a cited file | the team has felt a coupling nobody declared |

A content hash tells you *what literally changed*; the cascade tells you *what is now stale because
of it*.

**Read the two signals apart.** `invalid` is `D0` — bytes differ, end of argument. `aging`/`stale` is
`D1` — arithmetic over decay weights **nobody measured**, reproducible from the policy pinned inside
the catalog file and labeled a hypothesis there. Do not quote the second as if it were the first, and
tune the weights rather than treating them as discovered constants. Distances that could not be
measured come back as `unknown`, never as zero: an unchecked distance reading as "nothing changed
there" is the silent-degrade failure this package refuses everywhere else.

## Regenerating: approve per file, and record what was approved

A regeneration run touches many docs, and "approve all" is how a wrong section ships inside a
correct batch. Four outcomes per file — **approved**, **rejected**, **amended then approved**,
**partially selected** — and the commit records the run that produced it, so a bad regeneration is
one query away from being identified rather than archaeology.
