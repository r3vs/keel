# Contributing

This repository **authors and builds** two agent skills + a shared core, to the Anthropic Agent
Skills specification, packaged for Claude Code, Codex, opencode and Pi. The design is complete and
the runtime is largely implemented — see each skill's `TODO.md` for what remains. Contributions are
welcome; please keep the invariants below green.

**Start here, because it decides where your edit goes:**

> **`src/` you write by hand. `plugins/` `build.py` writes. Nothing else exists.**

`plugins/` is generated output — committed, because a marketplace installs from the repo, but never
hand-edited. If you change shared doctrine, edit `src/core/*.md` and run the build; editing a
`plugins/**/references/core/` copy will be reverted by the next build and caught by `--check`.

## The checks (must pass — they run in CI)

```bash
python scripts/build.py --check       # every generated file still equals its src/ source
python scripts/check_consistency.py   # drift-linter: modules ↔ references ↔ SKILL, all skills + core
python scripts/verify_pointers.py     # every intra-playbook *.md pointer resolves
python scripts/verify_commands.py     # every COMMAND a shipped file names resolves AFTER INSTALL
python -m unittest discover -s tests  # runtime, MCP tools + server, ledger gate, installed package
python scripts/run_evals.py --validate # eval specs well-formed
bash -n src/tools/bootstrap.sh        # installer shell syntax
```

`verify_commands.py` and `tests/test_installed_package.py` are not more of the same: every other
gate anchors on `__file__` and so validates **the repo as a repo**, which is blind to the one path
class that is working-directory-sensitive — the strings a shipped file tells an agent to run. That
is how `python runtime/ledger.py` shipped for months, resolvable nowhere but here, with CI green
throughout.

## Editing conventions

- **Three-way sync.** When you add or rename a module, update its `modules.json` **and** its
  playbook **and** any `SKILL.md` pointer together (`CLAUDE.md` has the full rules).
- **Path convention.** `references/x.md` is skill-root-relative (e.g. `src/skills/codebase-rescue/`),
  and this includes the vendored `references/core/x.md` copies, which exist only after the build.
  Inside `src/skills/`, a bare `` `core/x.md` `` pointer is an error — vendor it.
- **Agent Skills spec.** Each `SKILL.md` frontmatter needs `name` (lowercase, hyphens, matching the
  directory) and `description` (≥ 20 chars). That floor is what makes it portable — Codex silently
  drops the rest, so nothing portable may depend on `allowed-tools`.
- **Don't hand-mirror a fact across hosts — give it one source and let the build derive it.** The
  roster's write verb lives in `src/core/agents.md`'s table; the required MCP servers live in
  `src/core/knowledge-sources.md`'s table. A parity linter over two hand-written copies is a smell:
  it says two things should be one thing, generated. And parse those tables, never grep the prose
  around them — "GitHub" appears in the knowledge-sources doc twice as ordinary English.
- **The ledger spec (`src/core/decisions-ledger-spec.md`) is the authoritative schema**;
  `src/core/ledger.md` is the short English pointer summary to it. Keep both in sync with the version.
- **Read the relevant reference before editing a phase/module** — don't work from memory.

## Licensing

Contributions are under the MIT `LICENSE`. Note that the external toolchain the skills invoke keeps
its own licenses (GitNexus is PolyForm Noncommercial and optional).
