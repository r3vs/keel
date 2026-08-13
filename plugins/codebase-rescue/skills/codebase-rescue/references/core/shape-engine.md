<!-- GENERATED FILE - do not edit. Source: src/core/shape-engine.md at the repo root; regenerate with: python scripts/build.py -->

# The Field-Shape Engine (shared core)

Both skills reduce a data field to one comparable descriptor and reason across type systems
with one equivalence table. The machinery is identical; only the **direction** differs:

- `codebase-rescue` runs it in **diff mode** — extract the shape of the same field at each
  layer (DB / ORM / API / frontend) and compare them to find where they disagree
  (`skills/codebase-rescue/references/contract-reconciliation.md`).
- `greenfield-forge` runs it in **generate mode** — author one canonical shape and emit an
  aligned representation for each layer, so they cannot disagree by construction
  (`skills/greenfield-forge/references/contract-propagation.md`).

This file is the authority for the descriptor and the equivalence table. Read it before writing
either module.

## The common shape descriptor

Reduce every representation of a field to:

```jsonc
{ "name": "role", "type": "enum", "nullable": false,
  "enum": ["admin", "user"], "constraints": { "default": "user" } }
```

`{ name, type, nullable, enum?, constraints? }`. Everything a boundary can assert about a field
normalizes to this. Diff mode compares two descriptors; generate mode expands one descriptor
into each layer's syntax.

## The cross-type-system equivalence table

Types must be compared/generated across DB, ORM, API, and TS/JS type systems. A small
equivalence table crosses them (illustrative, extend per stack):

| Canonical | DB (Postgres)        | ORM (Python/TS)      | API / TS type      |
|-----------|----------------------|----------------------|--------------------|
| `string`  | `varchar` / `text`   | `str` / `string`     | `string`           |
| `int`     | `integer` / `bigint` | `int` / `number`     | `number`           |
| `bool`    | `boolean`            | `bool` / `boolean`   | `boolean`          |
| `enum`    | `ENUM(...)`          | enum type / union    | string-literal union |
| `uuid`    | `uuid`               | `UUID` / `string`    | `string` (branded) |
| `json`    | `jsonb`              | `dict` / object type | interface / `object` |
| `datetime`| `timestamptz`        | `datetime` / `Date`  | `string` (ISO) / `Date` |

### The projections the table grants, and to whom

A row above says two spellings *can* mean the same canonical type. Three **diff-time projections**
say that a disagreement across a particular boundary is not drift at all — each because the
receiving type system cannot express the distinction, so it can neither state it nor get it wrong.
They are applied symmetrically at diff time and never inferred during extraction:

1. **`string` ⟷ `uuid`/`datetime`, on a layer with neither type.** The JS/TS family (a client, a TS
   interface) and **GraphQL**: an SDL has no `uuid` and no `datetime` scalar either, so a timestamp
   travels as `String` or as a custom scalar the schema declares.
2. **`int` ⟷ `float`, on a layer with ONE number type.** The JS/TS family only. **GraphQL is
   excluded**: it has `Int` and `Float`, so a disagreement there is a finding. The two projections
   were one list until this was written down, and merging them is a live trap — granting GraphQL the
   first silently grants it the second.
3. **GraphQL `ID` ⟷ `string`/`int`/`uuid`.** `ID` is opaque by specification — serialized as a
   String, accepting an Int on input — and an SDL cannot say what the store holds. Against
   `bool`/`enum`/`json`/`datetime` it is still drift.

Projection 3 is the largest measured false-positive class this engine has ever had removed
(`docs/measurements.md`, `keystonejs/keystone`): a Prisma `String @id` under a GraphQL `ID!`
accounted for nine tenths of that run's `type_mismatch` findings.

## The three rules that keep it honest

1. **When equivalence is uncertain, mark `confidence: ambiguous` — do not assert.** A
   `varchar` that *might* correspond to a TS `string` is not a proven match. In diff mode this
   downgrades a would-be mismatch; in generate mode it forces an explicit choice rather than a
   silent guess.
2. **Never fabricate a correspondence.** If a field on one side has no counterpart on another,
   that absence is itself the finding (rescue: an orphan / incompleteness pin; greenfield: a
   gap in the contract to be decided) — never paper over it with an invented mapping.
3. **A diff over nothing is not a clean diff — refuse it.** If a side extracted zero entities, say
   which side and what its extractor needed to see; never answer "no findings", which is the same
   value as "these layers agree" and is read as a pass. Extraction preconditions are silent by
   nature — a model file in an idiom the extractor does not read looks exactly like a model file —
   so this is the one place where the engine must speak up rather than report an empty result. It
   was measured before it was written down: a large production service reconciled to zero findings
   because neither of its two layers had been parsed at all.

**Classify the noise; never filter it.** Some findings are true and structural: a GraphQL SDL has
`Query` and `Mutation` and no database has a counterpart; a DB keeps `author_id` where an API
exposes `author`, so one disagreement arrives in two kinds. Mark those with a machine-readable tag
(a structural tier, a relation pair) and leave the finding, its kind and its count exactly as they
were. Folding is a decision for the surface that shows findings to a human — a clustering pass, an
fp-check gate — and the raw counts must stay derivable by ignoring the tag. An engine that drops its
own noise is an engine whose error rate cannot be measured.

## Why this is the shared spine of both contract modules

Rescue's Phase-0 verdict (see `skills/codebase-rescue/references/contract-reconciliation.md`) found that a monorepo's
**shared-types package is the strongest standalone contract** — stronger than any inferred
cross-layer graph edge. That empirical finding is the hinge between the two skills:

- rescue *discovers* it after the fact (the shared-types package is where the real contract
  already lives, so diff the layers against it);
- greenfield *installs* it up front (author the shared-types package first, generate every
  layer from it, and wire the same shape-diff as a CI drift check so no future hand-edit can
  break alignment).

Same descriptor, same table, same "never fabricate" discipline — pointed backward to reconcile,
or forward to prevent.

**Runtime:** the `contract_diff` / `reconcile_layers` tools implement this file for
the live stacks: extractors for Postgres DDL / SQLAlchemy (both idioms) / Pydantic v2 / TS
interfaces that normalize to the descriptor, plus `diff_shapes`/`drift_check` with the honesty rules
enforced (unresolved → `ambiguous` note, absence → `missing_field`/`extra_field` finding). Rule 3 is
enforced one layer up, at each entry point that does the extracting — `drift_check` over the carrier
**and** every layer handed to it, `reconcile_layers`, `propose_correspondence` — each refusing with
the empty side named and the idiom its extractor needed to see. `diff_shapes` is handed two
already-extracted dicts and cannot tell an empty layer from an empty file, so it does not enforce
it; the distinction is worth stating because a tool that wraps the diff and skips the extraction
refusal answers "no findings" over a layer nothing read, which is the failure rule 3 exists for and
is what `drift_check` did on every layer but the carrier until this was written down. It is also
greenfield's CI drift-check — the same shape-diff wired to fail the build on drift. New stacks are
additive: an optional tree-sitter extraction backend is one generic engine driven by declarative
per-grammar **data** (a query + type maps — no per-stack code, no heuristics, no comment sniffing),
so a new stack is a data entry, not a parser. It degrades to the stdlib parsers when tree-sitter is
absent — pass `backend="auto"` to route TS/GraphQL through it. Types come only from the
grammar's own type system; the uuid/datetime↔string equivalence for stringly-typed layers is
applied deterministically at diff time, never inferred from a comment.
