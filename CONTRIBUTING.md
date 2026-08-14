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

**The list is the Commands block in `CLAUDE.md`, and only there.** This section used to hold its own
copy of it, and the copy was short by three gates (`check_hypotheses.py`, `check_schema_fields.py`,
`check_tool_carriers.py`) under a heading that reads as the complete set — which is the repo's own
signature bug, sitting in the file that tells a contributor what "must pass" means. Six documents
carried that list, each short by a different two-to-four; one carries it now, and it states that it
was read off `.github/workflows/ci.yml`.

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

## Release — at merge to main, tag every plugin

**A version that is never tagged is a version nobody can compare against, and the gate for it skips
green.** `tests/test_plugin_version.py` answers the one question no correspondence check inside this
repo can — *"do the bytes under `plugins/<name>` still equal the bytes that shipped under this
number?"* — by diffing the working tree against the `{plugin-name}--v{version}` tag. Its anchor lives
outside the tree, so with no tag there is nothing to diff and the assertion **skips**, quietly, at
the moment it matters most. That file states the residual in its own docstring: *"tag at release, or
this file is decoration."* This section is what stops it being decoration. Through 0.4.0 that was
the whole story — only 0.3.0 and 0.4.0 were ever tagged, so the check skipped for every version in
between.

**It stopped being decoration at 0.7.0, and the event is worth recording because it is the first
time the gate ever bit.** The four `--v0.6.0` tags were written locally, so the anchor existed; the
merge that became 0.7.0 changed bytes under all four `plugins/<name>` paths (`keel-core` directly,
the other three because they vendor `core/ledger.md`); all four assertions failed at once with
*"differs from what shipped as 0.6.0, but the version is still 0.6.0"*; and the fix was the one the
message names — bump `VERSION`, rebuild, and let the marketplace and every manifest restamp. Note
what it cost to arm it: nothing but a tag existing. The gate then disarmed itself again the moment
the number moved, which is the designed behavior, not a regression — an untagged version was served
to nobody, so no install can be holding it.

Tags are also load-bearing for **dependency resolution**, which is a second consumer and the reason
the name shape is not ours to choose. Claude Code resolves a semver-constrained dependency — ours is
`keel-kit` → `{"name": "keel-core", "version": "^<major>.<minor>"}`, derived from `VERSION` — by
listing tags on the hosting repository,
filtering to `keel-core--v*`, and fetching the highest that satisfies the range. Untagged, a
relative-path plugin falls back to the marketplace's current copy and the constraint is checked at
load instead of at fetch.

**One constant, then four commands.** `VERSION` in `scripts/build.py` is the only hand-written
version; the build stamps every `.claude-plugin/` and `.codex-plugin/` manifest **and** the root
`.claude-plugin/marketplace.json` from it. Bump it whenever `plugins/` content changes — a host
compares the string and nothing else, so bytes that move under a number that does not are bytes no
installed copy will ever receive.

```bash
# 1. bump VERSION in scripts/build.py, then regenerate and verify
python scripts/build.py && python scripts/build.py --check
python -m unittest discover -s tests

# 2. record the release in CHANGELOG.md, commit, merge to main

# 3. from main, one ANNOTATED tag per plugin — the name shape is Claude Code's, not ours
for p in keel-core codebase-rescue greenfield-forge keel-kit; do
  v=$(python -c "import json,sys;print(json.load(open(f'plugins/{sys.argv[1]}/.claude-plugin/plugin.json'))['version'])" "$p")
  git tag -a "$p--v$v" -m "$p $v"
done

# 4. push them, or the resolver on every other machine sees none of it
git push --follow-tags
```

Use `-a`. The remote holds two generations: the eight 0.3.0/0.4.0 tags are lightweight, which
carries no tagger, date or message — fine for a string match, useless for asking later *who
released this and when* — and the four `--v0.7.0` tags are annotated, the first annotated tags
ever to reach `origin` (pushed by the maintainer, 2026-08-13). The practice started locally with
the four `--v0.6.0` tags; 0.7.0 is where it first reached a resolver. `claude plugin tag --push`, run from a plugin directory, does the same job and
additionally validates the plugin, checks that `plugin.json` and the marketplace entry agree on the
version, and refuses on a dirty tree; prefer it when the CLI is available and treat the loop above
as the portable equivalent.

**Step 4 is a maintainer step, and an agent session cannot do it for you.** Learned at the 0.6.0
release: the credentials a Claude Code session runs under are scoped to the **work branch**, so
`git push --follow-tags` comes back **403 on `refs/tags/*`** while the branch push in the same
command succeeds. Steps 1–3 are all local — `git tag -a` writes into the clone — so a session
finishes them, reports the tags created, and everything *looks* released while the resolver on every
other machine still sees nothing. That is the same self-healing silence this whole section exists to
end, one layer further out: not a gate that skips green, but a release step that returns success for
the half it could do.

So verify the two sides separately, from the machine that will publish, rather than trusting the
transcript:

```bash
# annotated or not? `tag` = annotated (has its own object), `commit` = lightweight
git for-each-ref --format='%(refname:short) %(objecttype)' refs/tags
# what the RESOLVER sees — and what CI sees, since it fetches tags rather than reading your clone
git ls-remote --tags origin
# the maintainer's step; --follow-tags carries the annotated ones with the branch
git push --follow-tags
```

Today those first two disagree by exactly the four `--v0.6.0` tags: annotated in the clone, absent
from `origin` — and staying that way deliberately. Absent is the state `tests/test_plugin_version.py`
reads as *"this version was never released"*, which for 0.6.0 is the truth: it was served to
nobody (the number moved to 0.7.0 before any tag could be pushed), so a late push would anchor a
comparison no install can be holding. The 0.7.0 release closed the loop the designed way — the
maintainer ran the third command from their own clone, and the four annotated `--v0.7.0` tags are
what the resolver now sees.

**The version fallback chain — why the pin is worth keeping.** Claude Code resolves a plugin's
version from the first of these that is set:

1. `version` in the plugin's `plugin.json` — *what we ship*, so this always wins;
2. `version` in the plugin's marketplace entry in `marketplace.json`;
3. the git commit SHA of the plugin's source (for `github`, `url`, `git-subdir`, and relative-path
   sources in a git-hosted marketplace);
4. the SHA-256 digest, for `archive` sources;
5. `unknown`, for `npm` sources or local directories outside a git repository.

We sit on rung 1 deliberately: an explicit pin means users get an update **only** when we bump it,
which is what makes the number a promise rather than a side effect of pushing. Dropping to rung 3
would ship every commit to every user and make `test_plugin_version.py` meaningless, since the
version could never disagree with the content.

CI must fetch tags for any of this to run — `actions/checkout@v4` defaults to `fetch-depth: 1` and
brings none, so the workflow pins `fetch-depth: 0`. Without it every assertion in that file skips
green, which is the same silence this section exists to end.

## Licensing

Contributions are under the MIT `LICENSE`. Note that the external toolchain the skills invoke keeps
its own licenses (GitNexus is PolyForm Noncommercial and optional).
