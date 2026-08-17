<!-- GENERATED FILE - do not edit. Source: src/core/search-strategy.md at the repo root; regenerate with: python scripts/build.py -->

# Searching a Codebase Well (shared core)

Shared doctrine for **locating** things in a tree someone else wrote. The static-analysis doctrine
covers the other half of the same tool surface — running those binaries as *analyzers*, whose output
becomes pins. This doc covers running them as *navigation*, and the split is load-bearing because
**the confidence rules do not transfer**: `semgrep` run as a scanner emits a finding that
`findings_gate` normalizes and fp-checks; `rg` run to find a symbol emits a **location and nothing
else**. A grep hit is evidence that a string exists. It is not a fact about the code, it earns no
`extracted` confidence, and it never skips the false-positive gate.

The concrete install list lives in `skills/codebase-rescue/references/toolchain.md`; every tool named
here is best-effort, per the degradation rule at the bottom.

## The rule

**A search is a scoped query, not a sweep.** An unscoped search over a repo you do not know returns
a volume of output nobody reads, and its real cost is not tokens — it is that the answer was in there
and got skimmed past. Scope is chosen *before* the first call, in three axes: **type** (`-t py`,
`--lang go`), **path** (`src/api/`, not `.`), and **shape** (a literal, a regex, or an AST pattern).

## Which tool

| Job | Reach for | Not |
|---|---|---|
| Text / regex in code | `rg`, or the host's Grep tool | `grep -r` |
| Syntax-aware structure | `ast-grep --lang X -p '…'` | a regex that approximates an AST |
| Files by name or path | `fd`, or the host's Glob tool | `find`, `ls -R` |
| A whole rule pack, taint | `semgrep` | hand-rolled regex batteries |
| Which languages are here | `tokei` / `scc` | guessing from the file tree |

**Default to `ast-grep` the moment the question has syntax in it.** "Which `await` calls have no
`try`", "which functions return a bare literal" — a regex can only approximate those, and it
approximates them differently in every file that formats differently. When the pattern is worth
keeping, it graduates from a `-p` one-liner to a YAML rule, and the rule-authoring doctrine is how
one gets written so it actually matches — reached from the skills that grow a rule pack, which is
where that branch actually fires.

## The loop: count, narrow, then read

1. **Count first.** `rg -c 'pattern' -t py` says how many files, before a single line is read. A
   count is cheap and it is the input to the next decision.
2. **Narrow until the count is readable.** 847 files matching `import` is not a search result, it is
   the absence of one. `from requests import` at 23 files is a search result.
3. **Then read, with context** (`-n -C 2`) — and only then.

Widening happens once, deliberately, after a narrow search came back empty. Starting wide and hoping
to spot the answer is the failure this whole section exists to prevent.

## One walk, not N

`rg` walks the tree once **per invocation**, so N patterns issued as N calls is N walks plus N
startups. Two ways to collapse it, and they are not interchangeable:

- **Union into one process** when the patterns share a scope: `rg -t php -e A -e B -e C`, or
  `-f patterns.txt` when there are many (rescue's text pass does exactly this with
  `assets/ast-grep/ripgrep-markers.txt`). Multiple `-t` flags and multiple path arguments batch the
  same way.
- **Parallel tool calls in one message** when they cannot collapse — different scopes, different
  tools, different post-processing. Wall time is then the slowest single call.

Chaining independent searches with `&&` in one shell call gets neither: the shell still runs them in
sequence.

**The cost of the union, stated because it is invisible:** ripgrep does not report *which* `-e`
pattern produced a hit — not in plain output and not in `--json`, which carries no stable pattern
index. So when the answer is "which of these markers appear" rather than "do any", the union is the
wrong shape and separate runs are the right one.

## Excluding noise is part of the query

`-g '!vendor/'`, `-g '!node_modules/'`, `-g '!dist/'`, `-g '!*.min.js'`; `fd -E __pycache__`. A
result set dominated by generated code is a result set that hides the one hand-written hit. Both `rg`
and `fd` honour `.gitignore` by default, which covers most of this — until the repo commits its
`dist/`, which the kind of codebase this package is aimed at frequently does.

## Three tools, three answers to "is `.tsx` TypeScript"

Worth knowing before it costs an hour, because each is right in its own model and no two agree:

- `rg -t ts` **includes** `.tsx`, and there is no `-t tsx`.
- `fd -e ts` **excludes** `.tsx` — extensions are literal. Use `fd -g '*.ts*'` for both.
- `ast-grep` treats `tsx` as a **separate language**: a rule written `language: typescript` does not
  run on `.tsx` at all, which is why the rule pack carries duplicates.

The general form: a type filter is a claim about the *tool's* taxonomy, never about the language. Check
it once per tool rather than carrying one tool's answer to the next.

## When local search comes back empty

An empty result is a signal to **change rung, not to widen the sweep**. The escalation is the one
already declared in `core/knowledge-sources.md`: the code, then authoritative docs, then a
repo-grounded source, then the open web — cheapest sufficient source first. The specific case worth
naming is context that never lived in the tree: an issue key, a PR number or a ticket reference in a
comment means the reason for that code is in the tracker, and no amount of grepping the working tree
will produce it. Everything fetched that way stays **untrusted input** under the same doctrine —
grounding, never deciding.

## Degrade gracefully

Same rule as every other seam here: `rg` absent → the host's Grep tool → `grep`. `fd` absent → Glob →
`find`. `ast-grep` absent → the question loses its structural answer, and **that is a fact worth
stating**, not a silent fallback to a regex that approximates it. Degrading is permitted; pretending
the degraded answer is the same answer is not — the general form is the trust-axes doctrine.

Because this doctrine is prose, and prose gets skipped, `keel-core` also ships a warn-only
`PreToolUse` nudge on `Bash` — it speaks once per rule per session when a shell `grep -r` or `find`
goes out where `rg`, `fd` or the host's own tools fit. It never blocks: a shell search is never wrong
enough to stop the work.
