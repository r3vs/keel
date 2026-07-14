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

## The two rules that keep it honest

1. **When equivalence is uncertain, mark `confidence: ambiguous` — do not assert.** A
   `varchar` that *might* correspond to a TS `string` is not a proven match. In diff mode this
   downgrades a would-be mismatch; in generate mode it forces an explicit choice rather than a
   silent guess.
2. **Never fabricate a correspondence.** If a field on one side has no counterpart on another,
   that absence is itself the finding (rescue: an orphan / incompleteness pin; greenfield: a
   gap in the contract to be decided) — never paper over it with an invented mapping.

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

**Runtime:** `runtime/shapes.py` (repo root; stdlib-only, tested in CI) implements this file for
the live stacks: extractors for Postgres DDL / SQLAlchemy 2 / Pydantic v2 / TS interfaces that
normalize to the descriptor, plus `diff_shapes`/`drift_check` with both honesty rules enforced
(unresolved → `ambiguous` note, absence → `missing_field`/`extra_field` finding). As a CLI it is
greenfield's CI drift-check: `python runtime/shapes.py --contract … --ddl … --sqlalchemy …
--pydantic … --typescript …` exits 1 on drift. New stacks are additive (tree-sitter
generalization on the TODO).
