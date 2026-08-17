# Authoring a Structural Rule (shared core)

How to write an `ast-grep` pattern or rule that will run over code nobody in this session has read —
rescue's placeholder/stub pack, a one-off structural query, a mechanical Phase-4 rewrite. Finding
*with* rules is `core/search-strategy.md`; running them as a scanner whose output becomes pins is
`core/static-analysis.md`. This is the authoring step between them, and it exists because that step
is where the package's own rule pack is grown at runtime: rescue's ast-grep pack tells an agent to
add a YAML file per new placeholder shape it meets, which is an instruction to author a rule under
exactly the conditions that make rules wrong.

## The failure mode this guards

**A wrong rule does not announce itself.** Both directions fail silently, and they fail in opposite
ways — verified against `ast-grep 0.45.1`, because the whole point is that the tool will not tell you:

- **Too specific, or the wrong language → matches nothing, exits 1.** A rule declared
  `language: typescript` run against a `.tsx` file that contains JSX matches *zero* nodes and prints
  nothing. It does not warn that the grammar rejected the file. Read as a result, that is "clean" —
  and it is the `core/static-analysis.md` rule turned structural: **a check that could not run found
  nothing, not zero.**
- **Malformed → matches everything, exits 0.** The pattern `def $$$ {{{` is not valid Python and not
  a meaningful query, and `ast-grep` ran it happily and reported a match on an ordinary function. A
  pattern is parsed leniently by design (that is what makes metavariables possible); the cost is that
  degenerate input produces confident output.

So the count a rule returns carries no information about whether the rule is right. Nothing in the
tool closes that gap. Only a test does.

## Do not author from memory

Rule syntax is exactly the kind of surface a model half-remembers: metavariable spelling,
`pattern` vs `rule`, which relational keys exist (`inside`, `has`, `follows`, `precedes`), how
`constraints` bind. Reconstructed from training data it produces YAML that loads and is wrong —
which, per the section above, looks the same as YAML that is right.

Fetch the current reference before writing anything non-trivial. That is rung 2 of the ladder in
`core/knowledge-sources.md` (Context7 for authoritative library docs); ast-grep also publishes its
docs as a single `llms.txt` for exactly this purpose. The doctrine's discipline applies unchanged:
what comes back grounds the rule, it does not decide it, and the rule is still tested afterwards.

## The loop

1. **Decompose the question.** "An auth-shaped function that unconditionally returns true" is two
   claims — a shape (`def $F($$$A): return True`) and a name constraint (`^(is_|can_|has_|verify_)`).
   Write them as separate sub-rules before combining. A single pattern trying to carry both is where
   the over-specific failure comes from.
2. **Compose.** `all` / `any` / `not` for logic, `inside` / `has` for relation. Keep each leaf small
   enough to test on its own.
3. **Test against a positive AND a negative example.** This is the step that is skipped, and the only
   one that catches either failure above. The positive proves it fires; the negative — a real
   function that legitimately returns `True`, a docstring-only body — proves it discriminates. A rule
   with only a positive test is indistinguishable from `pattern: $ANY`.
4. **When the pattern does not match, dump the AST rather than guessing.**
   `ast-grep run --lang python -p '<pattern>' --debug-query=ast <file>` prints the parsed query;
   `=cst` shows unnamed nodes too, `=pattern` shows it in Pattern form. Compare the query's tree to
   the target's shape. Tweaking a pattern that parses to something other than what you meant is
   unbounded work.

   **Expect `ERROR` nodes and do not "fix" them.** In the debug AST for the working pattern above,
   `$F` and `$$$A` both render as `ERROR` — tree-sitter's Python grammar has no production for a
   metavariable — while the pattern matches correctly. ERROR nodes at metavariable positions are
   normal. ERROR nodes anywhere *else* are the real signal.
5. **Ship it only once step 3 passed.** A rule is not done when it is written; it is done when it
   matched the example and rejected the counter-example. That is
   `verification-before-completion` applied to a rule, and the rung it earns is the one it observed
   (`core/trust-axes.md`) — never the one the author intended.

## Per-language duplication is not optional

`ast-grep` treats `tsx` as a language distinct from `typescript`, not as a dialect flag: the rule has
to be duplicated with `language: tsx` or it silently does not run on `.tsx` at all. The same holds for
untyped JavaScript beside TypeScript. This is one instance of a wider trap — `rg -t ts` *includes*
`.tsx` while `fd -e ts` excludes it, so three tools give three answers to the same question
(`core/search-strategy.md`). Check the taxonomy per tool; never carry one tool's answer to the next.

## A rule flags candidates; it never pins

Unchanged from the rescue doctrine, and restated because a freshly-authored rule is the most tempting
one to trust: severity in the YAML is a **routing hint**, not a verdict. Every hit goes through
reachability and framework-suppression (`fp-check`) before it becomes a `defect` or an
`incompleteness`, and an intentional stub is never rendered as an error by default.

## Measure the rule, not just its findings

A rule that is wrong *repeatedly* is invisible to a gate that judges one finding at a time — each
instance is individually plausible. So a rule that ships in the pack is a **generator**: record every
verdict with `generator_observe` (`confirmed` / `refuted`; silence is never confirmation) and route
by `generator_screen`. Below the declared precision bar the rule is muted **loudly** — its findings
still appear, carrying the precision that muted them, and one confirmed finding moves it back. This
is what makes "grow the pack" safe: a new rule authored against one repo's shapes can be added
without betting the stream on it.
