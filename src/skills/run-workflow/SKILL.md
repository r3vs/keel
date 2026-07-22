---
name: run-workflow
description: >-
  Run a deterministic, parallel workflow over the codebase — fan out many read-only sub-agents,
  verify adversarially, and surface findings as ledger pins. Use for codebase-wide finding/audit
  (rescue Phase-1), multi-perspective review, or any task too broad for one context window. The
  engine is pure and journaled (replayable); YOU write the results to the ledger.
---

# run-workflow — the cross-host dynamic-workflow engine

A deterministic orchestration engine (a TS fork of pi-dynamic-workflows, MIT) that decomposes a
task, fans it out across isolated sub-agents, verifies, and returns findings — with a positional
journal so a re-run replays instead of re-spending. It is the **runtime of the roster's rule**:
*serialized writing, parallel reading*. Read `docs/design/dynamic-workflows.md` before changing it.

**The one invariant:** the engine is **pure and never writes the ledger**. It fans out read-only
sub-agents and RETURNS the surviving pins as JSON. **You** — the agent invoking this skill — write
them with the `ledger_add_pin` MCP tool, one at a time. Fan-out is read; the write stays serialized.

## When to use

- A task too broad for one context window: codebase-wide finding/audit, multi-perspective review,
  adversarial red-team of what was elected, or a dependency-ordered build.
- Not for: a single edit, or electing a decision (only the human interview elects a to-be).

## Topologies (`--topology`)

- **`phase1-finding`** (read-only, default) — multi-modal sweep + loop-until-dry + adversarial
  verify. Returns surviving **pins** `{file,line,kind,summary}` → write each with `ledger_add_pin`.
- **`challenger-verify`** (read-only) — red-team each elected oracle under distinct lenses
  (unfalsifiable / inconsistent / unsatisfiable / unstated-assumption / ignores-fan-out). Needs
  `--args-file` with `{"oracles":[{"id","statement"}]}`. Returns **ChallengeEvents** `{reopen,
  refutations}` → reopen/surface each pin so the human re-elects. It challenges, never decides.
- **`build-waves`** (WRITE) — drives the DAG's waves (`--args-file` with `{"waves":[{"index",
  "items":[{"id","title"}]}]}`, e.g. from `build_waves`); each wave fans out **executor** sub-agents,
  one per item, each in its own git **worktree** (isolated automatically), with a checkpoint between
  waves. Executors write test-first and open PRs; they never merge.

## How to run it

The engine ships **inside this skill**, in `engine/`. Invoke `engine/cli.ts` with the absolute path
your host injects for this skill (on Claude Code: `${CLAUDE_PLUGIN_ROOT}/skills/run-workflow/engine`).
It needs **Node** and the host's own CLI on PATH — **no npm install** (the default adapters shell the
host cli). If Node is unavailable, degrade: run the topology's steps by hand, or the sequential floor.

1. **Run the engine** — it prints JSON to stdout, logs to stderr:

   ```bash
   node --experimental-strip-types <this-skill>/engine/cli.ts --host <the host you are> --topology <name>
   ```

   `--host` = `claude | codex | opencode` (the host you are). `--topology` defaults to
   `phase1-finding`. Pass topology args with `--args-file <json>` (challenger-verify, build-waves).
   Optional: `--model <id>`.

2. **Read the JSON** and act by topology:
   - `phase1-finding` → an array of pins. Write each with `ledger_add_pin` (`kind` = the pin's kind
     if a valid ledger kind, else `other` + `kind_detail`; `provenance = [{source:
     "workflow:phase1-finding", detail: "<file>:<line>"}]`; `confidence: inferred`).
   - `challenger-verify` → an array of ChallengeEvents. Reopen/surface each named pin so the human
     re-elects — never resolve it yourself.
   - `build-waves` → a wave summary; the executors already opened PRs. Report them; do not merge.

3. **Report** what was written / opened, and stop. A finding is a gap, not a resolution — the
   interview elects what to do next.

## Rules

- The engine calls no MCP and writes nothing — if you find yourself wanting it to, stop: that write
  is yours, via `ledger_add_pin`, so it stays serialized and auditable.
- Sub-agents (the fan-out) may call the deterministic tools (`contract_diff`, `blast_radius`) for
  FACTS; never spawn an agent to approximate what a deterministic tool gives exactly.
- Scale to the task: do not fan out a fleet for something one context holds. A workflow is expensive.
