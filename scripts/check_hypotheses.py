#!/usr/bin/env python3
"""Every tuned number in the runtime is declared, or it is a bug.

The rule this gate enforces comes straight out of the trust-axes doctrine: **a constant with no
carrier is a hypothesis, and a hypothesis that hides inside code reads as a finding.** `0.7`,
`min_commits = 3`, `precision_bar = 0.5` — each is a choice somebody made once. Written plainly they
are tunable; written as a bare module constant they acquire an authority nobody granted them, and
six months later they get quoted as if they were measured.

**This is an AST walk, not a prose grep**, and the distinction is the whole reason the gate is
allowed to exist here. It parses Python, finds module-level bindings to numeric literals, and asks
one mechanical question: is there a `HYPOTHESIS` marker in the comment block directly above, or is
this name in the allowlist with a stated reason? Both answers are exact string membership. Nothing
guesses what a number *means* — the repo's own rule against keyword-guessing applies to its linters
too, and has been broken here before.

Scope, stated because a silent limit is the failure this gate exists to prevent: **module level
only**. A tuned default in a function signature (`min_commits: int = 3`) is not caught. Those mirror
a module constant by convention in this repo, and widening the walk to every default would flag
`max_depth=2`-style structural arguments with no way to tell them apart. That is a real hole, and
naming it is better than a gate that quietly covers less than its name suggests.

Exit 1 on any undeclared constant. Runs in CI.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = [ROOT / "src" / "runtime", ROOT / "src" / "mcp"]

MARKER = "HYPOTHESIS"

# Structurally forced constants: the number is not a choice, it is the shape of the thing. Each
# entry carries WHY, because an allowlist without reasons is just a bigger blind spot.
ALLOWED = {
    "_SEVERITY_RANK": "ordinals of the SEVERITIES tuple — the ranks ARE the enum's order",
    "_SARIF_LEVEL": "the SARIF spec's own level names; not ours to tune",
    "_SEVERITY_ORDER": "ordinals of the SEVERITIES tuple",
    "_CONF_RANK": "ordinals of the CONFIDENCES tuple — the ranks ARE the enum's order",
    "_TYPE_RANK": "ordinals of the node-type ladder file<class<function<method",
    "_MIN_LINES": "computed from the header template's own length plus the 4 lines a region "
                  "structurally needs (heading + item + clip note) — arithmetic, not a choice",
    "SCHEMA_VERSION": "a version string, not a threshold",
    "CATALOG_VERSION": "a version string, not a threshold",
    "_INDENT": "formatting width",
    "MAX_LINES_DEFAULT": "a host-imposed budget, not a tuned guess — Codex truncates by bytes and "
                         "Claude Code loses adherence past ~200 lines (core/instruction-files.md)",
}

# Numbers that carry no tuning anywhere: identity and emptiness. Nothing else is exempt — `2` is
# not structural just because it is small, and treating it as such was this gate's own first bug:
# `2 in {2.0}` is True in Python, so an earlier float in this set silently exempted every integer 2
# in the runtime, including a real fan-out threshold.
STRUCTURAL_VALUES = {0, 1, -1}


def _numbers(node: ast.AST) -> list:
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, (int, float)) \
                and not isinstance(sub.value, bool):
            out.append(sub.value)
    return out


def _declared_above(lines: list[str], lineno: int) -> bool:
    """Is `HYPOTHESIS` in the contiguous comment block immediately above this binding?"""
    i = lineno - 2                      # 0-indexed, line above the assignment
    while i >= 0:
        stripped = lines[i].strip()
        if not stripped.startswith("#"):
            return False
        if MARKER in stripped:
            return True
        i -= 1
    return False


def check_file(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"{path}: cannot parse ({exc})"]
    problems = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names or node.value is None:
            continue
        nums = [n for n in _numbers(node.value) if n not in STRUCTURAL_VALUES]
        if not nums:
            continue
        if any(n in ALLOWED for n in names):
            continue
        # a policy dict that declares itself is self-marking; the flag IS the declaration
        if isinstance(node.value, ast.Dict):
            keys = [k.value for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if "hypothesis" in keys:
                continue
        if _declared_above(lines, node.lineno):
            continue
        rel = path.relative_to(ROOT).as_posix()
        problems.append(
            f"{rel}:{node.lineno}: `{names[0]}` binds tuned number(s) {nums} with no carrier and no "
            f"`{MARKER}` marker. Either state the carrier that forces it (and add it to ALLOWED "
            f"with the reason), or mark the comment above it `{MARKER}` so it reads as the choice "
            f"it is (core/trust-axes.md)."
        )
    return problems


def main() -> int:
    problems, scanned = [], 0
    for target in TARGETS:
        for path in sorted(target.rglob("*.py")):
            scanned += 1
            problems.extend(check_file(path))
    for p in problems:
        print(f"ERROR {p}")
    print(f"\n{scanned} runtime file(s) scanned — {len(problems)} undeclared constant(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
