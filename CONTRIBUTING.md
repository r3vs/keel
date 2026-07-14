# Contributing

This repository is **two Claude/agent skills + a shared core**, authored to the Anthropic Agent
Skills specification and packaged agent-agnostically (Claude Code + opencode + Codex/AGENTS.md).
The design is complete and the runtime spine has started (ledger runtime, eval harness, rule
pack) — see each skill's `TODO.md` for what remains. Contributions are welcome; please keep the
invariants below green.

## The checks (must pass — they run in CI)

```bash
python scripts/check_consistency.py   # drift-linter: modules ↔ references ↔ SKILL, all skills + core
python scripts/sync_core.py --check   # vendored references/core copies identical to core/ source
python scripts/verify_pointers.py     # every intra-playbook *.md pointer resolves
python -m unittest discover -s tests  # ledger-runtime tests (spec v0.6 rules)
python scripts/run_evals.py --validate # eval specs well-formed
bash -n scripts/bootstrap.sh          # installer shell syntax
```

## Editing conventions

- **Three-way sync.** When you add or rename a module, update its `modules.json` **and** its
  playbook **and** any `SKILL.md` pointer together (`CLAUDE.md` has the full rules).
- **Path convention.** `references/x.md` is skill-root-relative (`skills/<name>/`); `core/x.md` is
  repo-root-relative and shared. A core file pointing at a skill's playbook uses the full
  `skills/<name>/references/x.md`.
- **Agent Skills spec.** Each `skills/<name>/SKILL.md` frontmatter needs `name` (lowercase,
  hyphens, matching the directory) and `description` (≥ 20 chars). This is what makes it portable.
- **Adapters mirror the core.** `core/agents.md` is the roster's source of truth; keep `agents/*.md`
  (Claude) and the `agent` block in `opencode.json` (opencode) consistent with it.
- **The ledger spec (`core/decisions-ledger-spec.md`) is written in Italian** by design; the rest
  of the repo is English, with `core/ledger.md` as the English pointer.
- **Read the relevant reference before editing a phase/module** — don't work from memory.

## Licensing

Contributions are under the MIT `LICENSE`. Note that the external toolchain the skills invoke keeps
its own licenses (GitNexus is PolyForm Noncommercial and optional).
