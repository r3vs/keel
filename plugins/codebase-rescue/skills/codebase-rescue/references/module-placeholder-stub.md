# Module: Placeholder / Stub Detection (deterministic-ish)

Finds the *syntactic signature* of vibecoded shortcuts. It flags; the completeness module and
`fp-check` decide intentional-vs-broken and reachable-vs-not. ast-grep for the structural/
semantic patterns (they need AST context), ripgrep for the pure-text fast first pass.

## Patterns

**Security-critical (high severity when on a reachable path):**
- Auth/authz that always allows: a function named like `is_authorized`/`can_*`/`verify_*`/
  `check_*` whose body is `return true` / `return True` / `if (true)`; middleware that no-ops.
- Disabled protections: commented-out auth middleware, `# nosec`, `eslint-disable
  security/*`, CSRF/verification turned off.

**Correctness-critical:**
- Swallowed errors: `catch (e) {}`, `except: pass`, `.catch(() => {})`, empty error branches.
- Not-implemented on prod paths: `NotImplementedError`, `throw new Error("not implemented")`,
  `TODO`/`FIXME`/`XXX`/`HACK` in non-test source on a reachable path.
- Fake/mock returns where dynamic behavior is expected: `return {mock...}`, `return []  #
  TODO`, hardcoded success responses in a handler.

## Method

1. ripgrep text pass for the literal markers (fast, catches TODO/empty-catch/nosec).
2. ast-grep structural rules for the semantic ones (return-true-inside-an-auth-function needs
   the AST, not a regex). The reusable YAML rules live in `assets/ast-grep/` (one file per rule,
   wired by `sgconfig.yml`; the text-pass markers in `ripgrep-markers.txt`; see its README for
   run commands and the severity→pin routing). Grow the pack with experience
   (variant-analysis: once you see a new placeholder shape, add a rule file).
3. Cross-check with the graph: a placeholder on a reachable prod path (inbound edge from an
   entry point) is high/blocker (fake auth guarding a real route = blocker); the same shape on
   an unfinished/unreachable path is `incompleteness`, not a defect — route through completeness.

## Output

```bash
ast-grep scan --config assets/ast-grep/sgconfig.yml --json > .audit/ast-grep.json
# ast-grep also emits SARIF: --format sarif. Prefer it when available — findings.py reads SARIF
# natively, and a native format needs no hand-translation to go wrong.

python scripts/runtime/findings.py .audit/ast-grep.sarif
```

`defect` (reachable placeholder on a live path — e.g. fake auth) or `incompleteness`
(unfinished stub), clustered by pattern. `findings.py` performs that clustering and applies
`fp-check` (reachability + framework suppression) — it is the same gate every other finding module
feeds, which is exactly why a placeholder and an SQLi arrive at the ledger comparable.

**The reachability oracle is injected, not faked.** `findings.py` takes a `reachable(file)`
predicate from the graph and defaults unknown → keep, so a missing graph never silently drops a
real bug. Run `graph-build` first when you can; when you cannot, findings surface conservatively
rather than disappearing. Never substitute your own judgment of reachability for that predicate —
step 3 below tells you what reachability *means* here, not that you should guess it.

## Relationship to completeness
Placeholder-stub finds the shape; completeness + fp-check classify intent and reachability.
They cooperate — this module never decides "broken vs unfinished" alone.
