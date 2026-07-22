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

- Rescue **Phase-1 finding**: sweep the codebase for drift / dead code / contradictions across many
  lenses in parallel, dedup, adversarially verify, and pin the survivors.
- Any audit / multi-angle review that does not fit one context window.
- Not for: a single edit, a decision (only the human interview elects a to-be), or writing code
  (that is the executor's serialized track).

## How to run it

The engine ships **inside this skill**, in `engine/`. Invoke `engine/cli.ts` with the absolute path
your host injects for this skill (on Claude Code: `${CLAUDE_PLUGIN_ROOT}/skills/run-workflow/engine`).
It needs **Node** and the host's own CLI on PATH — **no npm install** (the default adapters shell the
host cli). If Node is unavailable, degrade: run the topology's steps by hand, or the sequential floor.

1. **Run the engine** (discovery / dry-run — it prints JSON to stdout, logs to stderr):

   ```bash
   node --experimental-strip-types <this-skill>/engine/cli.ts --host <the host you are> --topology phase1-finding
   ```

   `--host` is one of `claude | codex | opencode` (the host you are running in). `--topology`
   defaults to `phase1-finding`. Optional: `--model <id>`.

2. **Read the JSON** — an array of pins: `{file, line, kind, summary}`. These are the findings that
   survived the adversarial verify. If the array is empty, report that nothing survived.

3. **Write each pin to the ledger** with the `ledger_add_pin` MCP tool — `kind` is the pin's kind if
   it is a valid ledger kind (else `other` + `kind_detail`), `provenance` = `[{source:
   "workflow:phase1-finding", detail: "<file>:<line>"}]`, `confidence: inferred`. Never elect a
   decision here; a finding is a gap, not a resolution.

4. **Report** the pins written (ids), and stop. The interview elects what to do about them.

## Rules

- The engine calls no MCP and writes nothing — if you find yourself wanting it to, stop: that write
  is yours, via `ledger_add_pin`, so it stays serialized and auditable.
- Sub-agents (the fan-out) may call the deterministic tools (`contract_diff`, `blast_radius`) for
  FACTS; never spawn an agent to approximate what a deterministic tool gives exactly.
- Scale to the task: do not fan out a fleet for something one context holds. A workflow is expensive.
