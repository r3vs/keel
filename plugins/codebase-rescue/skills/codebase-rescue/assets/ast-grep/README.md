# ast-grep rule pack — placeholder/stub detection

The reusable rules that `references/module-placeholder-stub.md` (step 2) and
`references/module-completeness.md` (signal gathering) invoke. The text pass (step 1) uses
`ripgrep-markers.txt`.

## Run

```bash
# structural pass (needs ast-grep; bootstrap.sh installs it)
ast-grep scan --config skills/codebase-rescue/assets/ast-grep/sgconfig.yml <target-repo>

# text pass (fast first sweep; literal markers)
rg -n -f skills/codebase-rescue/assets/ast-grep/ripgrep-markers.txt <target-repo> \
   --glob '!**/test*' --glob '!**/*.test.*' --glob '!**/*_test.*'
```

## Severity → pin routing

These rules **flag candidates**; they never pin directly. Route every hit through
`references/module-fp-check.md` (reachability + framework suppression), then classify per
`references/module-completeness.md`:

| severity | meaning | typical pin |
|---|---|---|
| `error` | security-critical shape (fake auth) | `defect` if reachable, else `incompleteness` |
| `warning` | correctness-critical shape (swallowed error, not-implemented) | `defect` / `incompleteness` by reachability |
| `hint` | completeness signal (trivial body) | `incompleteness` with `is_intentional_stub` judged |

The hard rule from the completeness playbook applies: **never render an intentional stub as an
error by default**.

## Growing the pack (variant analysis)

Once you see a new placeholder shape in the wild, add one YAML file per rule under `rules/`
(`id` = filename). Language note: rules are authored for `python` and `typescript` — the live
stacks from the Phase-0 verdict. `.tsx` needs a `language: tsx` duplicate of the ts rules;
add JavaScript variants the same way if the target repo is untyped.

**Author it against `references/core/rule-authoring.md`, not from memory.** That instruction used
to stop at "add one YAML file", which is the moment a rule is most likely to be wrong and least likely to be
caught: a rule whose language does not match the file matches nothing and exits 1 — indistinguishable
from a clean repo — and a malformed pattern matches *everything* and exits 0. Both were verified
against `ast-grep 0.45.1`; neither prints a warning. The loop there (decompose → compose → test a
positive **and** a negative example → `--debug-query=ast` when it will not match) is what separates
the two, and a new rule is registered as a generator so `generator_screen` can mute it loudly if its
precision does not hold up on real code.
