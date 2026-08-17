# Changelog

All notable changes to this project are documented here, in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) order. The design is complete and the
runtime spine has started; versions track design + packaging + runtime together.

**One number, four surfaces.** A version here is `VERSION` in `scripts/build.py` — the only
hand-written version in the repo. Every `.claude-plugin/` manifest, every `.codex-plugin/` manifest
and the root `.claude-plugin/marketplace.json` are stamped from it by the build, and a release is
the annotated git tag `{plugin-name}--v{version}` (see `CONTRIBUTING.md` § Release). A host decides
"do I need to update?" by comparing that string and nothing else.

**Which of these were actually tagged, stated rather than implied, and where those tags live**:
`origin` holds **0.3.0** and **0.4.0** (eight *lightweight* tags) and — since 2026-08-13 —
**0.7.0**, the first four **annotated** tags ever to reach the remote, pushed by the maintainer
from their own clone because pushing a tag needs credentials a session does not hold
(`CONTRIBUTING.md` § Release has the verified account and the two commands that tell the sides
apart). 0.1.0, 0.2.0, 0.4.1 and 0.5.0 moved the manifest number without any tag at all. The four
`--v0.6.0` tags are annotated and exist **only in the clone**, deliberately left there: 0.6.0 was
served to nobody, so a late push would anchor a comparison no install can be holding. That local
anchor was still enough to make `tests/test_plugin_version.py` bite for the **first time** at
0.7.0, after skipping green since 0.4.0: bytes moved under all four `plugins/<name>` paths while
the number stood still, and all four assertions failed at once. The gate's declared residual —
"tag at release, or this file is decoration" — is why tagging is written down as a step. 0.8.0's
four tags are the open maintainer step at its merge.

**Dates are the merge/commit dates of the range, best-effort.** Three versions landed on 2026-07-24;
that is what the history says, not a transcription error.

**This file deliberately restates old numbers, and is deliberately outside
`scripts/check_stated_facts.py`'s scope for that reason.** The 0.1.0 entry says "~170 tests" and
"spec v0.6" because those were true when 0.1.0 shipped; holding a changelog to today's carrier
would mean rewriting the record to keep a linter quiet. Present-tense claims live in
`README.md` / `CLAUDE.md` / `MEMORY.md`, all of which the gate does scan.

## [0.10.0] — 2026-08-17

### Added
- **The ledger audited as a memory — the first gate in this package pointed at its own store.**
  `src/runtime/memaudit.py` + `mcp:memory_audit` (tool 70). Every other carrier here points at the
  user's code; the one artifact everything is derived from had none. The failure modes are not
  invented: they are the eight on the `MODEL — MEMORY` edge of the interaction-centric taxonomy
  (arXiv:2607.28802), and six are decided from the file — a pin closed at a closing rung with no
  `evidence` ref (nothing can ever invalidate the claim), a policy scope wider than the case that
  produced it, a rule recorded without its reason and the cascade of that weakness into every
  decision it defaulted, transcript signatures pasted into a durable field, one statement written
  twice, and two standing policies selecting one pin with no precedence recorded.
- **The two modes it cannot decide are reported as undecidable, not as clean.** Missed Write and
  Missed Read are claims about a session, not about a file; approximating them would mean ranking
  absence, which this package refuses everywhere else. A green audit that skipped a quarter of its
  taxonomy is the `coverage.py` failure one layer up.

### Changed
- `policy_selects` is now a module-level function in `ledger.py`, read by `policy_preview` and by
  the auditor alike. It acquired a second reader, and a scope predicate written twice is two scope
  predicates.

### Fixed
- **`scripts/install.sh`'s override guard failed open on Windows, and then performed the override.**
  It decided with `case "/$skills_dir/" in */.claude/*)`, a glob needing forward slashes, so a
  native `…\.claude\skills` never matched — and the run went on to link 19 skills into that target,
  observed rather than reasoned. It now normalizes separators **for the decision only**, leaving
  `$skills_dir` as given; over-refusing costs one `--claude-personal`, under-refusing has no door.
  `tests/test_name_collision.py` hands the shell a POSIX path (which is the only spelling the script
  is written against) and runs the refusal over **both** spellings, so the regression leg exists on
  the platform that had it. This is the repo's own signature class with the sides swapped: green in
  CI on ubuntu and macOS, red only on the maintainer's machine.

### Notes
- `docs/open-gaps.md` §34 registers the finding this came out of, measured rather than recalled:
  the cross-layer field-shape diff both flagships call *"the core"* is 16% of the runtime, and the
  package holds carriers on **one** interaction edge. Three remain open there, with the evidence
  and the traps: the name-keyed correspondence engine, `project_type` → a capability vector, and
  the process edge.

## [0.9.0] — 2026-08-17

### Added
- **The navigation half of the tool surface, which had no doctrine at all.** `rg`, `ast-grep`,
  `semgrep`, `tokei` and `scc` were already installed and already documented — but only as
  *analyzers*, whose SARIF becomes pins. Nothing said how an agent **locates** something in a tree
  it has not read. `core/search-strategy.md` is that half, and it states the boundary the shared
  binaries hide: **a grep hit is a location, not a finding** — it earns neither `extracted`
  confidence nor the fp-check bypass a type error earns. A search is a scoped query, not a sweep:
  scope by type/path/shape before the first call, count before reading, collapse N walks into one
  (`-e` union, or parallel tool calls — never `&&`), and on an empty result **change rung** on the
  knowledge ladder rather than widening. Adapted from the ideas in `netresearch/file-search-skill`
  and ast-grep's own prompting guidance; no prose copied (their docs are CC-BY-SA-4.0, ours MIT —
  the facts and workflows are not copyrightable, the expression is).
- **`core/rule-authoring.md` — an instruction that had shipped with no method.** The ast-grep pack
  told an agent to "add one YAML file per new placeholder shape" and stopped at exactly the step
  where rules go wrong silently, in **both** directions. Verified against `ast-grep 0.45.1`: a rule
  whose `language:` does not match the file matches nothing and exits 1 — indistinguishable from a
  clean repo — while the malformed pattern `def $$$ {{{` matched an ordinary function and exited 0.
  Neither warns, so a rule's count says nothing about whether the rule is right; only a test does.
  Hence the loop: decompose → compose → test a positive **and** a negative example →
  `--debug-query=ast` when it will not match, where `$F` and `$$$A` render as `ERROR` nodes in a
  *working* pattern and must not be "fixed". New rules register as generators, so `generator_screen`
  can mute a bad one loudly rather than let it poison the stream.
- **`hooks/search-nudge.py` — the doctrine's mechanism, because prose gets skipped.** `PreToolUse`
  on `Bash`, **warn-only**, once per rule per session, on its own matcher: the ledger gate denies,
  this one never may. Silent where a nudge would be false — a pipe filter, a heredoc body, prose in
  `--body`/`-m`, an `echo`. Claude Code and Codex, both verified at the consumer rather than from
  this repo's host table: Codex's `PreToolUse` fires on commands matched as `Bash`, and a hook's
  `systemMessage` is surfaced as a warning. opencode and Pi get no adapter — both are
  block-or-nothing, and blocking a shell search is the one thing this hook must not do. 29 tests,
  most of them on the silent paths.
  It scans **statements, not the command string** — split on the shell separators outside quotes,
  each judged on its own. The whole-command spelling produced four wrong readings from one wrong
  model: `cd src\ngrep -rn TODO .` was silent (no newline in `(?:^|[|&;])`), an `echo` prefix
  covered whatever followed it, and a pipe filter *anywhere* excused a real tree sweep
  *elsewhere*. And its quoted-string regex is an unrolled loop, because the backreferenced spelling
  backtracks exponentially on an unterminated `-m "` — measured doubling every ~1.6 backslashes, so
  ~34 of them stall the Bash call the hook exists to annotate.
- **The first machine-checked eval for a doctrine that writes nothing.** A search produces no pin,
  and the harness resolves assertions against artifacts — but `Run` already keeps each tool call's
  **input**, the same fact `file_untouched` uses. So `shell_absent()` / `searched_with()` grade the
  Bash command string, and `static-first-analysis/evals/evals.json` lands three cases with six
  machine-checked assertions (the corpus goes 29 → 35 checks). Both predicates carry a test that
  accepts the positive and rejects the negative — the rule `rule-authoring.md` states for an
  ast-grep rule, applied to the checks that grade it. `shell_absent` compiles `MULTILINE`, and that
  flag is the whole assertion: it grades *absence*, so a `^`-anchored pattern that stops at the
  first line marks a violating multi-line run PASS. A check that cannot fail is worse than no
  check, because it is counted as one.
- **`fd` in `bootstrap.sh`**, with the name clash checked rather than assumed: Debian and Ubuntu
  ship the binary as `fdfind`, so `have fd` is false on a machine that has the tool.

### Fixed
- **Four admiring backticks that were dependency edges.** A backticked `core/` pointer is a build
  instruction, and `search-strategy` / `rule-authoring` had named each other plus `static-analysis`
  and `trust-axes` for claims they merely *support* — so the mutual pair forced any skill wanting
  either to vendor both. `static-first-analysis` had gone from 3 vendored core docs to 6, its
  doctrine doubled by orientation. The evidence stays as plain text; a skill taking
  `search-strategy` alone now inherits 3. This is the failure `core/writing-for-agents.md` records
  against itself, caught the same way it says to catch it.
- **`CLAUDE.md`'s host table said Codex has 10 hook events; the published list is 11.** A restated
  count, so no gate covered it — corrected by reading. Recorded beside it, out of scope to fix:
  `permissionDecision: "ask"` is *"parsed but not supported yet"* on Codex, which is exactly the
  mechanism the ledger gate uses for a write into host memory.

### Known gaps
- **`docs/open-gaps.md` §33 — the search doctrine's only carrier is a transcript.** These are the
  first `core/` doctrines that write nothing, so no blocking gate can falsify them: the eval's six
  checks run only under `--execute`, which is `continue-on-error` because it needs an API key, and
  eleven of that file's seventeen assertions are still `manual`. The register names the shape of the
  fix (an offline correspondence gate in `check_tool_carriers.py`'s style) and three traps, the
  first being *do not add a pin kind for a search*.

## [0.8.0] — 2026-08-13

### Added
- **`tracker_diff` surfaces human issue comments as `awaiting_human_review` — the inbound half of
  the tracker projection, elected rather than assumed.** The maintainer elected **read-only
  surfacing** from the three recorded forks, presented verbatim in a session interview; the
  election record replaces the open decision in `docs/design/tracker-projection.md`,
  `flip_criteria` included. Comments never write the ledger: each surfaced item carries issue, pin,
  author and a bounded excerpt; the projection's own comments are excluded **by marker, not
  author** (an author check would silently break the day the token changes); an unavailable
  tracker is `null`, never `[]`, so "nothing to review" cannot be impersonated by "could not
  look". Reopening stays a human act through the interview, one-way stays structural (still no
  `Ledger` constructed, still held by the AST test), and the schema is unchanged.
- **The two MCP apps' JavaScript has a gate.** The apps' JS had shipped inside Python strings that
  nothing ever parsed, let alone ran. CI's `workflow-engine` job (blocking, node 22) now extracts
  both documents as `apps.py` and `map.py` actually render them and executes the scripts against
  well-formed **and hostile** pins under a stub DOM — a `<script>`-shaped pin title must land as
  text, not as markup.
- **The first live behavioral eval run in the package's history — and it indicted the harness
  before the skill.** `using-the-ledger` against the real `claude` CLI ($1.50 / 264 s): 1 PASS /
  3 FAIL / 15 manual. The adversarial reading of the FAILs found the skill was **never in context
  in any of the four runs** — the harness piped a bare prompt, and a user-invoked skill
  (`disable-model-invocation: true`) is exactly what the host refuses to load that way, a cost
  0.6.0 recorded and the harness then paid — so the runner now types `/<name>` for user-invoked
  skills, read off the built frontmatter. One FAIL was eval design (a recording demanded with no
  human present to elect — rewritten as relay-mode); one read "0 of 0 entries" off a fixture whose
  `ledger.json` never existed (seed ledgers are now built at runtime through the real `Ledger`
  API). MCP **write** tools were permission-denied throughout, so the ledger-reading predicates'
  live-artifact residual **remains open** — restated, not closed. The run, both refutations, costs
  and residuals: `docs/measurements.md` Postscript 3.

### Fixed
- **`_client_can_elicit` treated a declared capability as a working channel.** An unavailable-class
  failure at `ctx.elicit` now degrades to the transcribed-relay refusal exactly as if the
  capability had never been declared, while `Declined`/`Cancelled` keep their hard-refusal
  semantics — a human's "no" and a channel's absence are different answers. This was
  `docs/design/mcp-apps.md` §6's "fix first, independently of any bump" item, closed before any host
  negotiates protocol 2026-07-28, i.e. before it could ever fire.
- **Five shape-engine gaps, closed and re-measured on the corpus that found them** (the point of
  recording extractor gaps as findings instead of quietly fixing them): `EmptyExtraction` refusal
  when a side parses nothing — an empty diff can no longer impersonate a clean bill of health,
  **including on `drift_check`**, the door the playbooks open first, which the first fix missed
  and the adversarial pass caught; SQLAlchemy 1.x idiom (`= Column(...)`, derived
  `__tablename__`); Pydantic base-chain following; `graphql` joining `_STRINGLY_LAYERS` (90% of
  keystone's `type_mismatch` noise was one missing tuple entry); structural-tier/relation-pair
  classification for the remainder. `docs/measurements.md` carries the dated before/after re-runs
  on both public repos.
- **A seed `files` entry was a path nobody looked at.** The eval harness's fixture-seeding
  mechanism was declared and dead; implementing it made every entry a write to a path an eval
  author chose, so both `--validate` and the runner now confine seed paths inside the fixture —
  `..`, absolute paths and symlink escapes refuse instead of writing.
- **`install.sh` now guards the `~/.claude/skills` footgun instead of only documenting it** —
  0.7.0 recorded that installing there replaces the bundled skill in every project the user opens;
  the installer now refuses that target unless explicitly forced.

### Changed
- **`VERSION` 0.7.0 → 0.8.0**; the suite grew 1,158 → 1,246 tests.
- **All three dependents now constrain `keel-core` symmetrically** (`^0.8`, derived from
  `VERSION`): `codebase-rescue` and `greenfield-forge` had been tracking whatever the marketplace
  last published while `keel-kit` alone carried the constraint 0.6.0 introduced — same exposure,
  one protected consumer.

## [0.7.0] — 2026-08-13

### Added
- **Two `ui://` MCP Apps, and the reason both of them only read.** `ui://keel/interview.html` (the
  funnel as a read surface, linked from `interview_next` via `_meta.ui.resourceUri`) and
  `ui://keel/map/{path*}` (`map.py`'s page baked with the ledger inline). They exist because the
  adapter had been *announcing* the apps extension with nothing behind it — FastMCP splices
  `io.modelcontextprotocol/ui` into `capabilities.extensions` unconditionally, with no constructor
  flag to stop it — so serving them is the only available way to make a declared capability true,
  and a test now fails if the capability is ever declared with no `ui://` resource behind it. The
  design note's own plan to let an app *elect* was reversed by a finding: an app's `tools/call` is
  proxied by the host onto the **same connection the model uses**, with nothing distinguishing the
  two, so an app-elected outcome could only claim the `elicited` rung on the agent's word — and
  `visibility: ["app"]` is a host hint (such a tool is still served in full by `tools/list`,
  observed on the wire), not an enforcement. Hand-written, no dependency added, no external origin.
- **The ledger ⇄ issue-tracker projection** — `src/runtime/tracker.py` plus `tracker_project` and
  `tracker_diff`. The same shape as `instructions.py` a second time: one source, a generated
  projection, managed markers, and a drift check computed by the **same planner the writer
  executes**. One-way by construction — no `Ledger` constructed, no write door imported, held by an
  AST test — because an issue box is unauthenticated input. Two host facts decided the design and
  were read at GitHub's docs rather than remembered: every pull request answers as an issue (the
  index skips anything carrying `pull_request`), and **labels are silently dropped without push
  access** — the label *is* the idempotency key, so a run that lost it stops rather than duplicating
  every pin forever. Idempotency comes from a label listing, not the search API, whose index is
  eventually consistent exactly when you project twice quickly.
- **`run_evals.py --execute`** — eval cases run against the real `claude` CLI with the built plugin
  loaded, and assertions resolved against the **artifacts the run produced** (the `ledger.json` it
  wrote, the ordered tool calls) rather than against its prose. 29 machine checks over 196
  assertions; everything else reports `manual` — never a pass, never a silent skip. `--validate`
  now also fails when a check is keyed to an assertion that no longer exists, so the prose-keyed
  table cannot rot. CI runs it as an advisory `behavioral-evals` job.
- **`docs/measurements.md` + `scripts/measure_public.py`** — the first honest read of what this
  engine finds on somebody else's code, provenance-stamped to a commit, with the null results
  written up at full length and five extractor gaps recorded as findings rather than quietly fixed.
- **`scripts/check_packaging_wire.py`** — the measured twin of the stated-fact linter. It spawns the
  server over stdio and re-measures the tool surface `docs/packaging.md` publishes, inside a
  declared tolerance, and fails a description crossing the host's silent 2 KB cut in **bytes**
  (the ceiling is stated in KB; our figures are characters).
- **`tests/test_name_collision.py`** — the `/code-review` name collision closed by keeping the name,
  after re-verification made the residual sharper than recorded: `install.sh` takes its target dir
  as `$1`, so `bash scripts/install.sh ~/.claude/skills` places every skill at the **personal**
  level and replaces the bundled skill in every project that user opens.

### Changed
- **`VERSION` 0.6.0 → 0.7.0, because the gate said so.** See the tag paragraph at the top of this
  file: this is the first bump this repo made because `tests/test_plugin_version.py` demanded it
  rather than because someone decided a release had happened.

## [0.6.0] — 2026-08-13 (tags clone-only, deliberately — 0.6.0 was served to nobody)

### Added
- **`which-skill`, and the two skills that name what an agent must *not* do alone.** The package had
  grown past the point where anyone remembers what is in it and had no map; `which-skill` is the
  router over them. It was the first **user-invoked** skill (`disable-model-invocation: true`,
  authored once, read by Claude Code and Pi, derived into Codex's `agents/openai.yaml`; opencode is
  a stated residual because its only door is the model's `skill` tool) — and by the end of this
  release fifteen of the nineteen shipped skills carry that key; see *The invocation axis* below.
  Beside it: **`prototype`** — a fork about how something
  behaves or looks is settled against a runnable artifact rather than by two people imagining the
  same words differently, and the human still elects; and **`wizard`** — the inverse of the
  assumptions doctrine, covering not what an agent does when it must guess but what it does when it
  must **wait** for a person, closed on something observed rather than on their "done".
- **Ledger v0.30 → v0.31 — two registers the schema had nowhere to put.** v0.30 adds **claims**:
  `ledger_claim` / `ledger_release` / `ledger_frontier`, a compare-and-set with expiry, because two
  sessions could take the same pin and neither could tell. v0.31 adds the **fog register**
  (`ledger_fog` / `ledger_add_fog` / `ledger_graduate_fog` / `ledger_clear_fog`): a decision you can
  sense and cannot yet phrase has no home in a register whose unit is a *question*, so it gets its
  own, and it **leaves** that register the moment a human phrases it into a pin.
- **`screenshot-to-code` (in `keel-kit`) — a reference image as evidence, not as a specification.**
  The prior art (`abi/screenshot-to-code`, MIT) answers a picture with a file, and everything the
  picture withheld — breakpoints, the hover and error states, which strings were placeholder, what a
  control does — gets supplied silently by a model at high confidence. Those are `agent_assumption`s
  wearing the costume of a deliverable, and they survive review because the render matches the
  picture, which is the one thing they were optimized to do. So the skill sorts every claim about an
  image into three buckets and treats each at its own trust: **computed** from the pixels (D0),
  **inferred** by a model looking at them (D2 → a vetoable pin), and **absent** — the things one
  still frame structurally cannot show (→ elicited, never filled in).
- **`runtime/visual.py` + the `image_palette` / `palette_verify` MCP tools** — the deterministic
  floor that makes the split enforceable rather than merely stated. A stdlib PNG decode (converting
  through ImageMagick / sips / ffmpeg when present, `unchecked` **with the reason** when not) yields
  the image's geometry and real color histogram with per-color coverage; `palette_verify` then asks
  the picture whether the colors a model claims to have seen are in it, summing coverage inside a
  CIE Lab ΔE radius so anti-aliasing and lossy re-encoding count *toward* a claim. A claimed token
  covering nothing is a hallucinated color, refuted at the contract for the price of one pin instead
  of after propagation into `tokens.css`, a Tailwind theme, a `DESIGN.md` and every component built
  on them. WCAG contrast of a *claimed* pair is graded in the same call — the one moment a contrast
  check is possible before any code exists for `design_scan` to scan.
- This also supplies a carrier greenfield's `design-propagation` had named and never had. Its rule
  is that a token set is *captured from an approved visual direction or imported, never invented by
  a text-only agent* — and of the three capture paths it named, only "import an existing brand" had
  a mechanism. A screenshot the user chose and handed over **is** an approved visual direction, and
  this is how it becomes a DTCG contract.

- **Eleven grammars beyond JS/TS in the comprehension graph** — Go · Rust · Java · C# · Ruby · PHP ·
  C · C++ · Kotlin · Swift · Scala, each one query table rather than one parser, so the graph stops
  being a two-language instrument on a polyglot repo.
- **MCP surface beyond tools** — the server now also serves three read-only ledger **resource**
  templates (`ledger://summary/…`, `ledger://pins/…`, `ledger://pin/{pin_id}/…`), three **prompts**
  (Claude Code shows them as `/mcp__keel__*`), **progress** notifications on the three long scans,
  and its own **version**. That last one was a bug, not a feature: with no `version=`, FastMCP had
  been answering `initialize` with **its own** version, so every host displaying a server version
  displayed the library's. It now reads the plugin manifest beside the vendored copy.
- **Evals: 3 files / 17 cases → 9 / 41.** The engineering-loop five plus `which-skill` gained
  `evals/evals.json`, each asserting the **ledger binding** rather than generic good practice — the
  red step is a pre-existing `acceptance_criterion` pin, a root cause lands in the `defect` pin,
  resolution demands `rung="observed"`, the reviewer reopens without deciding — and each carrying at
  least one adversarial case where the *user* offers the shortcut ("the suite is green, close the
  pin") and the assertion checks that the discipline held.

### Changed
- **The invocation axis, and the budget nobody had measured.** Claude Code keeps a listing of every
  skill's name and description in context, capped at **1% of the context window**, and on overflow
  *"drops descriptions starting with the skills you invoke least"*. Keel shipped eighteen
  model-invoked skills of nineteen carrying **7,745** characters — and on a cold repo, where nothing
  has been invoked, its own two flagships were first in the drop queue. That is a deadlock: a skill
  whose description is gone cannot match, so it is never invoked, so it stays at the front. Fifteen
  skills that a person can reach **by name** now set `disable-model-invocation: true`; the four whose
  trigger is a *situation* nobody names stay model-invoked (`codebase-rescue`, `greenfield-forge`,
  `systematic-debugging`, `screenshot-to-code`). Descriptions **7,745 → 1,178** characters, keeping
  the verbatim phrases a person actually types, and both flagship bodies came under the 200-line
  adherence limit with the detail moved into `references/guardrails.md`. `check_description_budget.py`
  is the gate. Two costs are recorded rather than discovered later (`docs/open-gaps.md` §31): the key
  is outside the Agent Skills spec, so claude.ai upload now hard-fails for fifteen skills instead of
  one; and a user-invoked skill is unreachable *by the model*, so no playbook may ever tell an agent
  to invoke a sibling skill.
- **CI grew a matrix, a Node job, and manifest gates** — `checks` now runs Python
  3.10/3.11/3.12/3.13/3.14 on ubuntu plus a macOS leg, this repo's first non-Linux coverage ever.
  The interpreter list is *derived*: it is the floor the shipped server declares
  (`requires-python = ">=3.10"`, which `ruff.toml` already targets) through the newest release, so
  the repo no longer lints a floor it never runs. The tree-sitter backend is installed before the
  suite (a missing backend used to skip 21 tests *green*), and blocking on every leg.
  `src/workflow/`'s 7 TypeScript suites ship inside `keel-core` and had been run by CI zero times;
  they are now a blocking job on node 22. Plus `ruff` as a measured floor and
  `validate_manifests.py`, which blocks on the subset of `claude plugin validate --strict` we can
  assert ourselves — that validator cannot block, since the CLI is not reliably installable.
- **`keel-kit` now constrains its dependency on `keel-core` to `^0.6`** instead of tracking whatever
  the marketplace last published. Every kit skill calls keel-core's MCP tools by name, so a core
  release that renames one breaks the kit's prose while both manifests stay valid. Verified at the
  consumer before being written (`docs/en/plugin-dependencies`): a `dependencies` entry may be a
  bare string or `{name, version}` with an npm semver range, resolved against `{name}--v{version}`
  git tags — the same tags `tests/test_plugin_version.py` already anchors on.

### Fixed
- **A 16-bit grayscale screenshot decoded to near-black, so the palette channel fabricated facts
  and *refuted* correct ones.** `visual.py` computed its rescale factor for the raw sample depth
  (255/65535 at depth 16) but had already reduced the sample to its high byte, so a white capture
  read `#010101` and `verify_palette` answered a correct `#ffffff` with `absent`, ΔE 99.7 — on the
  one channel that is `confidence: extracted` and skips fp-check, i.e. the one nothing downstream
  second-guesses. The rule was written twice with two different conditions, one per color path; it
  is one rescale now, and the test is the full (color type × bit depth) product rather than a
  sample of it — the missing pair was exactly the broken one.
- **A claim that was not a string crashed the palette tool** instead of taking the `unparsed`
  verdict the code already provides. The claim set is a model's JSON through an MCP tool whose
  schema is `list | None`, so `{"name": "primary"}` (or a value spelled `rgb`) normalizes to `None`
  and `None.strip()` raised out of the tool. `parse_hex` now rejects a non-string as a `ValueError`,
  which is what every caller turns into a per-claim verdict.
- **`/rescue` promised a learning-layer composition the model can no longer perform.** The command
  said *"I compose it over the whole workflow"* while the same release set
  `disable-model-invocation: true` on `learning-layer` — which blocks the model's call, and blocks
  reaching it from another skill. The guardrails playbook contradicted itself on the same page. Both
  now state the one real door (the operator types it) and say plainly that an uninvoked run is
  uncoached.
- **`code-review`'s only remaining door was a name Claude Code already owns.** `/code-review` is a
  bundled skill; a plugin skill is namespaced and *"the bare `/fancy` also invokes the skill unless
  another command already uses that name"*, so typing the bare name silently reached Anthropic's
  reviewer, not the ledger-bound one — while `which-skill` told the operator every non-flagship
  skill is "typed by name". The router and the kit README now give `/keel-kit:code-review`. Checked
  name by name against the *enumerated* bundled set: it is the only collision among the nineteen.
- **The 3.14 tolerance on the extraction-backend install rested on a false premise.**
  `tree-sitter-language-pack==1.12.5` ships `cp310-abi3` wheels (plus an sdist), so it installs on
  3.14 today — verified at PyPI and empirically on a clean 3.14. What the tolerance actually bought
  was a leg where the 21 extraction tests skip green behind an annotated step, because
  `TestASkipIsAClaimAboutOneInterpreter` cannot fire when no sibling interpreter has the backend.
  Gone; the step blocks everywhere.
- **`validate_manifests.py` validated a dependency's name and never its version RANGE**, in the same
  release that introduced the repo's first constrained dependency — a string `build.py` builds by
  string surgery. An unparseable range is a `range-conflict` that *disables the plugin* on the
  user's machine. There is a range reader now, with both halves tested: the documented spellings are
  accepted, `^0.` and friends are rejected.
- **Two counts and two twins.** README and both plugin READMEs said 28 and 15 modules against 29 and
  16 (`agent-instructions` was added to each catalog and listed in neither prose), and
  `check_stated_facts.py` now carries a fact for each. Its `listing_chars` pattern hardcoded the
  `1,200` budget it was checking against, so re-deriving `LISTING_BUDGET_CHARS` would have silently
  un-covered CLAUDE.md's restatement — the budget is read from the gate that declares it, and a
  pattern that matches nothing anywhere is now an ERROR rather than invisible coverage (one already
  was). And `test_installed_package.py` still held the shape-check-as-name-check whose twin in
  `test_mcp_declaration.py` was fixed this release: it would have failed on the *next* dependency to
  gain a version range, with a message about MCP reachability.
- **`MEMORY.md` was outside `check_stated_facts.py`'s `SCOPE`** while claiming a 179-test suite
  against 1017, and while listing `cognee` among the declared MCP servers when the build declares
  only the rows its own table marks `→ **http**`. That is the precise failure shape the gate was
  written for, in a file the gate could not see. It is in scope now; `CHANGELOG.md` is recorded in
  `EXCLUDED` with its reason, so its absence reads as a decision rather than an oversight.
- **`MEMORY.md`'s own header claimed it was always-on context** *"loaded by AGENTS.md-aware agents"*.
  It is loaded by nobody, on any of the four hosts — `AGENTS.md` names it in prose, which is a
  pointer, not an import, and no import syntax is portable. The audit that built the instruction
  carrier killed that claim in `project-memory`'s playbook and left it standing in the file it was
  about.
- **`docs/design/dynamic-workflows.md` was still in Italian** — the design authority for the TS
  workflow engine, unreadable to most of the agents and contributors expected to execute it. Fully
  translated; its open decisions and assumptions are retitled in English and flagged as what they
  are: `open_decision` and `agent_assumption` pins living in prose instead of in a ledger.

## [0.5.0] — 2026-08-05 (never tagged)

*Reconstructed from git history after the fact — the entries below are read off the commits between
`b692cd9` and `96d402a`, not written at release time.*

### Added
- **A human had no way to record a decision on any host.** The ledger's whole premise is that only a
  committed human answer elects anything, and every write door was an agent door. This release adds
  the human's: the recording tools take an election the person made and **refuse a relay with no
  quote**, so "the user said yes" cannot be typed by the thing that wanted the yes.

### Fixed
- **An item's `depends_on` was accepted, stored, and read by nobody** — the field the wave scheduler
  levels the DAG on, written faithfully into every ledger and consulted by nothing. This is the
  failure `check_schema_fields.py` now quantifies over: a field the schema declares that nothing
  which ships ever reads.

## [0.4.1] — 2026-08-05 (never tagged)

*Reconstructed from git history (`9bcf88a`..`b692cd9`).*

### Fixed
- **The two cross-layer tools declared `dict` and returned a bare `list`.** An MCP output contract
  that disagrees with the value is worse than an undocumented one: the client validates against the
  declaration and the tool works anyway, until a stricter client refuses it.
- **A colon in an agent description silently unrestricted a read-only agent** — YAML frontmatter
  parsed the rest of the line as a new key, dropping the tool allowlist that *was* the enforcement.

### Changed
- **The tool roster was pruned, and the pruning recorded** — a tool description is rent paid every
  session and its value arrives only when it is called. The docs were corrected in the same pass so
  they stop reading as if 52 tools shipped.
- **Docs and gates audited against their carriers**: three lines of one README said 34, 37 and 465;
  a constant with no carrier is a hypothesis, and `check_hypotheses.py` now says so; a backtick is a
  claim about the code, and `docs_claims` now checks them; two signals that agree are strong, two
  that disagree **are** the finding; `readiness_assess` was added because a correct plan onto ground
  that cannot hold it still fails; and `ledger_mark_correctness_unknown` gave an unverifiable claim
  somewhere honest to land instead of landing on green.

## [0.4.0] — 2026-07-24

*Reconstructed from git history (`0f75eb3`..`9bcf88a`) — one commit, and it is the whole release.*

### Added
- **The ledger reaches a fresh agent through `AGENTS.md`, or it does not reach it at all.** The
  ledger is the single source of truth and **no coding agent loads it**; every host loads exactly one
  markdown instruction file unprompted. So a project could hold a fully elected design and still
  hand every fresh executor a blank slate — and `greenfield-forge` shipped new repos with zero
  occurrences of `AGENTS.md`, `CLAUDE.md` or `MEMORY.md`. The ledger is now **projected** into a
  fenced managed region of the user's `AGENTS.md` (`runtime/instructions.py`,
  `mcp:generate_instructions` / `mcp:instructions_diff`), generated and drift-checked like
  `generate.py`'s contracts. Verified at each host's loading function rather than its docs — Codex
  `read_agents_md`, opencode `InstructionContext.observe`, Pi `loadProjectContextFiles`, Claude
  Code's `CLAUDE.md` hierarchy. Two facts decide the design: **no import syntax is portable** (only
  Claude Code parses `@path`, and it skips code spans), and **length is a correctness constraint**
  (Codex truncates by bytes, Claude Code loses adherence past ~200 lines), so the region is a
  budgeted index whose every clip is declared. The begin marker carries the body's fingerprint,
  which separates `hand_edited` (someone wrote a decision *into* the projection — reported, never
  auto-healed) from `stale` (the ledger moved).

## [0.3.0] — 2026-07-24

*Reconstructed from git history (`0158386`..`0f75eb3`). Its release commit is titled "the number
moves because the bytes moved", which is the rule this whole file exists to keep.*

### Removed
- **The root `.claude-plugin/plugin.json` is gone.** It declared the repository itself to be a
  plugin — which it stopped being on 2026-07-16, when the architecture became four plugins under
  `plugins/`, each with its own generated manifest. The file survived that change because **nothing
  read it**: not `build.py`, not a test, not CI. Verified at the docs rather than assumed — a
  marketplace entry's relative `source` *"resolve[s] relative to the marketplace root, which is the
  directory containing `.claude-plugin/`"*, ours are all `./plugins/<name>`, and a root manifest sits
  on no documented path. Unread **and** hand-written is this repo's worst pair: it had drifted to the
  old brand and the old repo URL, and only an eyeball caught it, which is not a mechanism.
  `tests/test_mcp_declaration.py::test_the_root_is_a_marketplace_not_a_plugin` now gates it — and was
  confirmed to fail with the file restored, rather than merely passing without it.

### Changed
- **One object per gate, evidence before judgment, one reopen path.** The roster was tightened so
  each role owns exactly one thing: the `measurer` owns the evidence, the `reviewer` owns the code,
  the `challenger` owns the oracle. The cheap deterministic gate runs first, so review judgment is
  never spent on a change that does not close the gap — this package's own static-first doctrine,
  applied to its own roster.
- **Each plugin got its own README**, because a plugin that ships 32 tools cannot be documented by
  one sentence in the repo's front page.

## [0.2.0] — 2026-07-24

*Reconstructed from git history (`b97f7bb`..`0158386`) — the largest reconstructed range, spanning
PRs #1 and #3–#7. Its release commit is the rebrand; it was never tagged.*

### Changed
- **The project is named `Keel`, and for the first time every surface agrees on it.** There used to
  be three answers to "what is this called": the repo was `codebase-rescue`, the marketplace was
  `codebase-alignment`, and the infrastructure plugins were `alignment-core` / `alignment-helpers` —
  so the install line read `codebase-rescue@codebase-alignment` and the flagship plugin shared a name
  with the repo that contained all four. Three names, no two agreeing: the exact drift this package
  exists to find, sitting in its own front door. Now: repo `r3vs/keel`, marketplace `keel`, MCP
  server `keel`, plugins `keel-core` + `keel-kit`.
- **`codebase-rescue` and `greenfield-forge` deliberately keep their names.** A skill self-activates
  off its `description`, and those two words are load-bearing there — `keel-rescue` would trade
  trigger accuracy for brand symmetry. The brand carries the infrastructure; the methodology carries
  the meaning.
- **README rewritten for a reader who has never heard of any of this.** It now opens on the failure
  it detects rather than on the architecture that detects it, and proves the claim with **real
  output** from `tests/fixtures/slop-repo` plus the one-line command to reproduce it. The old hero
  described the repository's own file layout in paragraph three.
  - One line of that rewrite was cut on the house rule: the draft's hero ran `keel contract-diff`,
    a CLI that has not existed since it was removed in favour of the MCP-only runtime. A fabricated
    command in the first code block of the README is the claiming-vs-doing bug in its purest form.
- **"Totale": the CLI ceases to exist — MCP is the only runtime channel** on all four hosts (Pi via
  `mcp-bridge.ts`), and `uv` becomes a hard prerequisite. What had been a CLI floor with an MCP
  ceiling became one channel, which is why `run-workflow`'s floor is the `build_waves` **tool** and
  not a command.

### Added
- **An `understand` mode** — comprehension as the deliverable rather than as phase 1 of a rescue,
  with the runtime family behind it: `graph_build` (tree-sitter-native backbone), `understand`,
  `explain`, `query`, `tours`, `impact`, `domain`, `graphmap`, `fingerprint`, `docs_claims`.
- **The cross-host dynamic-workflow engine** (`src/workflow/`, a TS fork of the MIT
  `pi-dynamic-workflows`) and the **`run-workflow`** skill that invokes it: deterministic journal
  with longest-unchanged-prefix replay, a `vm` sandbox with a determinism prelude, a four-adapter
  spawn seam (Claude · Codex · opencode · Pi), and three flagship topologies. Verified end-to-end
  live against real opencode; the engine is vendored **inside the skill** so its paths stay
  skill-relative and portable. Design authority: `docs/design/dynamic-workflows.md`.
- **The design-alignment layer** — the DTCG token contract (`design_tokens`: one source → CSS /
  Tailwind / `DESIGN.md`), greenfield's `design-propagation` twin, rescue's as-is DTCG extraction
  with Playwright browser verification, and the `playwright` MCP server declared as a capability
  server (it connects with zero setup, unlike cognee).
- **Per-role model + effort, resolved per provider profile** (`src/core/model-tiers.md`), and
  `spend_report` telemetry — measure the tiers rather than assert them.
- **The self-model doctrine + six anti-cheat extensions**, and a `learn:<level>` intensity dial for
  the learning layer.
- **The Phase-0 gating verdict recorded from the VibraFlow run**, closing the rescue TODO's step 0.

### Fixed
- **Every host claim that was verified at the *type* rather than at the *parser*** was re-checked and
  corrected, including the Codex `./`-prefix rule that had silently dropped manifest paths for
  months, and the refuted "`Bash` is a write vector Claude Code cannot restrict" claim that was still
  in the shipped doctrine.
- **`backend="auto"` did not actually degrade** — tree-sitter is now probed per grammar.
- **Bootstrap's grammar prefetch never ran** (`__file__` is `"<stdin>"` in a heredoc) and its uv
  cache warm-up resolved the wrong path while always claiming success.
- **The challenger's vibe-word heuristic was dropped** — it violated the no-heuristics rule and had a
  substring bug underneath it.

## [0.1.0] — 2026-07-17 (never tagged)

### Removed
- **The root's host config — `.mcp.json`, `opencode.json`, `.codex/config.toml` — is gone**, and
  with it the assumption underneath it: that a user might be working *here*. They install into their
  own project, so root config reached nobody. The docs sold it as the install path anyway (`README`
  told Cursor and Codex users to *"open the repo (or add it to your workspace root)"*; `install.sh`
  printed *"copy the mcpServers block into your opencode.json"*), which meant two of four hosts had
  no install path at all — only an invitation to clone a demo. And the three copies of that one fact
  had already drifted: deepwiki declared for Claude but missing for Codex, cognee `enabled: true` in
  two of them (which the doctrine forbids *because* it cannot connect without a container), context7
  over `npx` in one and http in the others.

### Added
- **MCP delivery is now the install itself, on every host that can take it** — generated from the
  one table in `src/core/knowledge-sources.md`, so a server cannot be ordered in prose and absent
  from the product:
  - **Claude Code** reads the plugin's own `.mcp.json`; **Codex** reaches the same file through its
    manifest's `mcpServers: ".mcp.json"` (verified in `openai/codex`: `PluginManifestMcpServers::Path`).
  - **opencode** has no manifest slot for servers, but a plugin's `config(cfg)` hook receives the
    live merged config and may mutate it (verified in `sst/opencode`) — so the generated
    `adapters/opencode/plugin/mcp.ts` declares them, and `scripts/install.sh` places it. Two shape
    facts there are verified rather than inferred, and neither follows from Claude's: opencode's
    discriminator is `local`/`remote`, not `stdio`/`http`, and a local `command` is an **array**.
    Emitting Claude's shape would be valid JSON that silently declares nothing. `${CLAUDE_PLUGIN_ROOT}`
    is likewise a Claude-ism no other host expands, so the plugin resolves our server from its own
    location and degrades gracefully when it cannot.
  - The user's own config wins on every key — this fills gaps, it never overwrites a choice.
- **`scripts/install.sh` places the opencode plugin and the Pi extension** instead of printing them
  as homework, and `tests/test_mcp_declaration.py` grew the gate that keeps the root clean.
- **`README`, `docs/packaging.md`, `AGENTS.md`, `CONTRIBUTING.md` and `MEMORY.md` rewritten** — all
  predated the `src/`↔`plugins/` split and still described `scripts/sync_core.py` and
  `scripts/install-opencode.sh` (both deleted), `skills/`+`core/` at the root, and — in the very
  "try it" section — `python runtime/ledger.py`, this repo's signature bug, still on its front page.

### Added
- **Runtime** — the executable layer both skills bind to (core stdlib-only, tested in CI;
  **~170 tests** across `tests/`):
  - `runtime/ledger.py` — the shared decisions-ledger runtime (spec v0.6): kind-discriminated pin
    validation, append-only Decision/Reopen/Challenge events, enforced brainstorm/challenger/
    feedback **neutrality**, the severity threshold (blocker/high never silently defaulted), policy
    cascade, `agent_assumption` surfacing, minimal transitive reopen on both arcs, RemediationItem/
    BuildItem verbs, an information-gain-ordered interview view, a read-only CLI.
  - `runtime/shapes.py` — the field-shape engine (`core/shape-engine.md`): extractors for
    **Postgres DDL, SQLAlchemy 2, Pydantic v2, TypeScript, Drizzle, Prisma, Django, GraphQL**
    (new stacks are additive), the cross-type-system diff with both honesty rules (unresolved →
    `ambiguous` note; absence is the finding), and the **CI drift-check CLI** (exit 1 on drift) —
    rescue's contract-reconciliation core and greenfield's guardrail.
  - `runtime/generate.py` — greenfield's **contract generators**: one descriptor → DDL / SQLAlchemy
    / Pydantic / TS, aligned by construction. Proven by a **round-trip test** (generate → drift-check
    == zero drift), turning the step-0 STRONG verdict into an executable invariant; `choose_carrier`
    picks shared-types / OpenAPI / protobuf.
  - `runtime/findings.py` — the mandatory **false-positive gate** (`module-fp-check.md`): normalize
    SARIF + OSV to one stream, the CONFIRM/DOWNGRADE/DROP gate (five ordered checks, injected
    reachability + stub oracles defaulting to keep, deterministic diagnostics skip the gate),
    root-cause clustering to one pin with N anchors, a showable DROP audit trail.
  - `runtime/interview.py` + `skills/greenfield-forge/assets/decision-catalog.json` — the
    **decision-frame + funnel**: the 11-cluster catalog as machine-usable data; `expand_catalog`
    prunes by project type and skips brief-decided forks; `funnel` compresses to the asked questions
    ordered by transitive information gain with the tail as `proposed_default`.
  - `runtime/challenger.py` — the deterministic slice of the v0.6 oracle red-team (`unfalsifiable`,
    `ignored_fanout`), emitting upheld `ChallengeEvent`s that reopen via the ledger; judgment classes
    stay agent-driven. Neutrality tested (never writes a DecisionEvent).
  - `runtime/buildloop.py` — the shared **Phase-4 wave scheduler**: levels the BuildItem/pin DAG
    topologically (cycle-detecting), yields ready pins, gates each wave checkpoint; restart-safe
    because the ledger is the state.
  - `runtime/map.py` — the **visual map** as one self-contained HTML file (no build step, no
    external fetch): clickable pins, three-column contract-diff, linked interview questions,
    completeness traffic-light, as-is/to-be toggle; shared by both skills. Now renders a pin
    anchor's `node_id` and a **blast-radius impact line** when the graph enriched it.
  - `runtime/graph.py` — **deterministic graph anchoring + blast-radius** over graphify's NetworkX
    `graph.json`, with **no heuristics**: resolves a pin anchor to a stable `node_id` **only by its
    `file:line`** (exact, or a node's declared line-range — no name-matching, no plural folding, no
    basename/nearest guessing); computes blast-radius by **reverse reachability over the graph's own
    EXTRACTED edges** (its deterministic confidence tag — never the INFERRED cross-layer edges, and
    no editorial edge-type filter); enforces the `built_at_commit == HEAD` staleness gate (**refuses
    to write on a stale graph** — worse than none); enriches the ledger's `anchors[]` in place so
    the map stays self-contained. Exactly the two things the Phase-0 verdict leaves the graph —
    anchoring + impact — and nothing it is not (no field-level correspondence). `tests/test_graph.py`.
  - `runtime/treesitter_extract.py` — the **primary extraction backend** (`shapes.py` defaults to
    `backend="auto"`): a real grammar parses the whole language, so real-world **TypeScript,
    GraphQL, and SQL** just work — none of the per-repo regex patches the stdlib parsers needed. It
    is one **generic engine driven by declarative per-grammar DATA** (a `STACKS` entry = a
    tree-sitter query + type/​node maps; **no per-stack code, no heuristics, no comment-sniffing**),
    plus a small custom walk where a grammar's shape differs (SQL columns are positional). Ships
    verified specs for **TS interfaces**, **GraphQL SDL**, **Postgres/SQL DDL**, and the backend
    struct/class stacks **Go, Java, Rust, C#** (each language's nullability convention — Go `*T`,
    Rust `Option<T>`, C# `T?`, Java primitives-vs-boxed — is spec DATA, not code); adding a stack is
    a data entry, not a parser. Not a *hard* dependency: it **degrades to the stdlib parsers**
    when tree-sitter is absent (a stdlib-only environment still runs; the ledger/core stay
    stdlib-only). Every spec is a verified **byte-identical drop-in** with the stdlib extractor on
    the fixtures (so the drift-check is identical) and strictly more robust on real code.
    `tests/test_treesitter.py` (skips cleanly without the backend; the full suite is green both with
    tree-sitter and with it simulated absent).
  - `scripts/run_evals.py` — eval harness: `--validate` (CI structural gate) and `--run` (behavioral
    execution against a real agent runner + fixture, LLM-judge per assertion; no pretend mode).
  - `skills/codebase-rescue/assets/ast-grep/` — the placeholder/stub rule pack: 8 python+typescript
    rules + `sgconfig.yml` + ripgrep markers, fixture-validated (18 findings, 0 false positives).
  - Fixtures: `tests/fixtures/slop-repo/` (a misaligned mini-repo whose planted drift/stub/SQLi the
    runtime detects) and `tests/fixtures/briefs/` (crud-saas, cli-tool, api-service).
- **Greenfield step-0 gating experiment run** (2026-07-14): verdict **STRONG** — one 4-entity
  contract carrier generated all four layers (DDL, SQLAlchemy 2 ORM, Pydantic-v2/FastAPI DTOs +
  routes, TS client), each machine-validated; full generation is Plan A for that stack family,
  with four recorded frictions keeping the CI drift-check mandatory
  (`skills/greenfield-forge/references/contract-propagation.md`).
- **Activation contract**: the SessionStart hook upgraded from a nudge to a mandatory-workflow
  bootstrap (entry rule + 8-skill inventory + the three non-negotiable disciplines).
- **Cursor install steps** (README + `docs/packaging.md`) and a README note on the
  repo-vs-package naming split (`codebase-rescue` repo, `codebase-alignment` package).
- **Two sibling skills on a shared core**: `codebase-rescue` (curative) and `greenfield-forge`
  (preventive), unified by `gap = diff(to-be, as-is)` and one append-only decisions ledger.
- **Full lifecycle loop** for greenfield (7 phases): frame (acceptance criteria + threat model) →
  interview → contract & roadmap → build → validate → release → operate & evolve, closing back via
  observable `flip_criteria` + `ReopenEvent` (ledger v0.5).
- **Shared core doctrines**: decisions-ledger spec, interview funnel, brainstorm, field-shape
  engine, contract-testing, feedback-loop, static-analysis, knowledge-sources, and the agent roster.
- **Agent-agnostic packaging**: Agent-Skills-spec `skills/<name>/`, root `AGENTS.md`, a Claude Code
  plugin (`.claude-plugin/`, `agents/`, `hooks/`, `commands/`) and an opencode adapter
  (`opencode.json` + `opencode-skills` + `.opencode/command/` + `scripts/install-opencode.sh`).
- **Agent roster** (`core/agents.md`): researcher · brainstorm · executor · reviewer · challenger ·
  measurer, under serialized-writing / parallel-reading.
- **Three-gap harness** (the definitive-harness pass): the package now closes three gaps with one
  anti-divergence machine, not one.
  - *Oracle gap* — a new read-only **`challenger`** role + `ChallengeEvent` (ledger **v0.6**) that
    red-teams an elected oracle **upstream** (unfalsifiable / inconsistent / unsatisfiable / unstated
    assumption / ignored fan-out) and reopens the pin before code rests on it — the feedback loop's
    upstream twin. Both **reopen, never decide**.
  - *Silent-assumption gap* — `core/assumptions.md` doctrine + `provenance: agent_assumption`: a
    forced assumption is materialized as a vetoable, challengeable pin, never encoded silently.
  - *Operator gap* — a composable **`learning-layer`** skill: senior-grade output *while the user
    learns*, via one-mode (default-on, opt-out) micro-retrieval, teach-from-the-delta ranked to 1–2
    items, teach-the-class, and a **learner-model** gradebook (the operator-gap twin of the ledger)
    that measures mastery, fades scaffolds on evidence, and detects cargo-cult.
  - *Teach-on-rejection* — a blocking gate (reviewer / challenger / feedback loop) now names the
    class and the recognition cue, not a bare verdict — raising the operator, not just the code.
  - *Prefer-the-checkable-formulation* — a selection heuristic in `core/static-analysis.md`: author
    the spec so the strongest static signal applies, not only run it in-loop.
- **Engineering hygiene**: drift-linter + pointer verifier, CI (`.github/workflows/ci.yml`), a
  version-pinning mechanism in `bootstrap.sh`, MIT `LICENSE`, `CONTRIBUTING.md`.

- **Complete-package layer** (composed, not cloned): six composable skills — `using-the-ledger`,
  `grounded-research`, `static-first-analysis`, `project-memory`, `learning-layer`, `writing-skills`
  (meta); a
  **memory** subsystem (ledger + `MEMORY.md` + cognee MCP); **MCP** servers wired across platforms
  (`context7`, `deepwiki`, `cognee`; `github` opt-in) via `.mcp.json`, `opencode.json`, and
  `.codex/config.toml`; **Codex** + any AGENTS.md-aware agent supported; and `superpowers` referenced
  in the marketplace for the generic engineering skills instead of reinventing them.

### Changed
- **No-heuristics pass on the shape engine + graph** (design directive: deterministic, tech-stack
  agnostic). Extraction now reads only a stack's own type system — the guessing came out:
  - **comment-branding removed** — a TS `// uuid` / `// ISO datetime` no longer coerces a `string`
    to uuid/datetime. The uuid/datetime↔string equivalence is instead a **deterministic, symmetric
    diff-time rule** for stringly-typed layers (`diff_shapes` / `_STRINGLY_LAYERS`) — where it
    belongs, per the equivalence table — so the drift-check stays clean without sniffing comments.
  - **Drizzle enum name-guess removed** — a column whose enum const is unresolved is honestly
    `unknown`/ambiguous, never guessed to be an enum from a `…Enum` name.
  - **pluralization guess removed** from carrier-less `reconcile_layers` (it was English-specific):
    entity matching is now **case-insensitive exact**. Cross-convention correspondence (`users`
    table ↔ `User` model) comes from the **carrier** (`drift_check`), the Phase-0 verdict's
    strongest anchor — not from folding names.
  - **`runtime/graph.py` anchors by `file:line` only** (exact/containment), and blast-radius is
    reverse reachability over the graph's own **EXTRACTED** edges — no `_LAYER_TYPES` name matching,
    no basename/nearest guessing, no editorial edge-type lists.
- **Real-repo end-to-end validation** (`plastital_lca`, a polyglot Supabase + FastAPI + React LCA
  app) drove two deterministic extractor improvements: `extract_ddl` **hardened for real Postgres/
  Supabase DDL** (`CREATE TABLE IF NOT EXISTS`, `public.` schema prefixes, quoted identifiers,
  multi-word types like `timestamp with time zone`, `numeric`/`decimal`) — it went from **0 → 17
  tables / 290 fields** on that schema; and an **int ⟷ float equivalence** for JS/TS-family layers
  (a client's single `number` cannot express, nor get wrong, the distinction), which removed ~109
  false type mismatches. The run produced a real **102-pin** ledger + map across 40 corresponded
  API↔client entities (genuine missing/extra-field and nullability drift, e.g. a `last_checked` vs
  `last_check` rename), found **0** DB↔code name correspondence (no carrier, divergent vocabularies),
  and surfaced 3 name collisions — confirming the Phase-0 thesis that the carrier is the strongest
  anchor. Both improvements are covered by tests (`test_ddl_real_world_postgres_forms`,
  `test_int_float_equivalent_across_js_layer`).
- **Tree-sitter promoted to the primary extraction path** (the durable answer to the DDL fragility
  above: a real grammar, not per-repo regex patches). `shapes.py` now defaults to `backend="auto"`,
  and **SQL DDL** joined TS/GraphQL on tree-sitter — a byte-identical drop-in with the (hardened)
  regex parser on the fixtures, but it eats plastital's real Postgres (`IF NOT EXISTS`, `public.`
  prefixes, `numeric`, `timestamp with time zone`) with **zero targeted patches**. The regex/line
  parsers stay as the always-available fallback; the Python `ast` extractors (SQLAlchemy/Pydantic/
  Django) are already real parsers and are unchanged. The full suite is green both with tree-sitter
  installed and with it simulated absent (regex fallback).
- **Stack coverage broadened** toward "the vast majority of cases". Extraction now covers, per
  layer: **DB** — Postgres/SQL DDL (tree-sitter); **ORM/model** — SQLAlchemy · Django (Python `ast`),
  Drizzle · Prisma (regex); **API/DTO** — Pydantic (`ast`), GraphQL SDL (tree-sitter); **client** —
  TypeScript (tree-sitter); and the **backend struct/class stacks Go · Java · Rust · C#**
  (tree-sitter), each added as a declarative spec (query + type map + nullability convention as
  DATA — Go `*T`, Rust `Option<T>`, C# `T?`, Java primitive-vs-boxed), verified on fixtures. Still
  open: migrate Drizzle/Prisma off regex, and add more stacks (Kotlin, PHP, Ruby, protobuf, …) —
  the same one-spec-per-stack pattern, each hardened on a real repo when one is available.
- **Self-contained skills (Model B)**: the shared `core/` is now a single **authoring source**,
  vendored into each skill under `references/core/` by `scripts/sync_core.py` (following the
  `core→core` dependency closure). No skill points at `core/` directly, so every skill directory
  ships complete on any platform. CI gained `sync_core.py --check` (keeps each copy identical to its
  source), and `check_consistency.py` now errors on a bare `` `core/x.md` `` pointer under `skills/`.
- **Model B slimmed** (after review feedback that the vendoring surface was confusing): see-also
  cross-links inside `core/*.md` demoted to plain text so the dependency closure only follows
  load-bearing pointers — vendored copies drop **65 → 39** and each helper skill now carries only
  the doc(s) that are its actual subject; every vendored copy is stamped with a
  `GENERATED FILE — do not edit` banner by `sync_core.py`; `check_consistency.py` gained
  **command parity** (`commands/` ↔ `.opencode/command/`); and `docs/packaging.md` now answers
  "why not write the text directly in each skill?" explicitly.
- **Graph-memory backend: `@modelcontextprotocol/server-memory` → `cognee` (`cognee/cognee-mcp`)**
  across `.mcp.json`, `opencode.json`, `.codex/config.toml`, the `project-memory` skill, and the
  docs. Cognee is Apache-2.0, ships an official MCP server, runs on a single Postgres or fully
  embedded (no Neo4j), self-edits (re-weights rather than append-only-grow), and supports
  **deliberate writes** (`cognee.remember(...)`) that match the skill's "one crisp line" discipline.
  Trade-off, documented: unlike the zero-config `server-memory`, cognee needs its Docker container
  running on `:8000` and an `LLM_API_KEY` — so it stays **opt-in**; the ledger + `MEMORY.md` cover
  durable memory without it. (The layer was flagged as the weakest/most-optional; this makes it a
  genuine upgrade when a project's scale earns it, or a clean drop when it doesn't.)

### Notes
- **Both step-0 gating verdicts are recorded on trustworthy data.** Greenfield (FastAPI+SQLAlchemy
  +TS): STRONG → full four-layer generation is Plan A. Rescue's VibraFlow verdict was challenged
  (its graph was stale — 37 commits behind HEAD) and then **re-run on a fresh graph (2026-07-14)**:
  `graphify update` rebuilt it to current (`built_at_commit` == HEAD), and the verdict is **WEAK**
  cross-layer correspondence → standalone extraction is Plan A — 75 INFERRED / 0 semantic edges,
  and DB-schema nodes that exist but carry no field-level correspondence (correcting the stale
  verdict's wrong "0 DB nodes" claim). Confirmed positively: `runtime/shapes.py` extracts 113
  tables / 1290 fields from VibraFlow's real Drizzle schema.
- What remains is agent-orchestrated at runtime (the per-item TDD loop); evals execute via
  `scripts/run_evals.py --run` against a live agent runner. See each skill's `TODO.md`.
- Generic skills are **composed** from `superpowers` (MIT), not authored here.
- The vendored `references/core/` copies are generated — edit `core/*.md`, then run `sync_core.py`.
