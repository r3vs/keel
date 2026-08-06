"""Every field the ledger spec declares must be read by something that ships.

A schema field is a promise. `depends_on` on a RemediationItem was declared, accepted, stored — and
read by no line of the runtime and no line of any playbook. It looked exactly like a capability from
the outside, which is how it reached a user's hands and got planned around before anyone noticed it
did nothing. The class is the repo's own signature failure: a claim the artifact does not keep.

Two reader classes, and BOTH count, because the ledger has two audiences:

  * **code** — `src/runtime/*.py`, `src/mcp/*.py`. A field the runtime branches on.
  * **doctrine** — `src/core/*.md` and the skills' shipped prose. A field addressed to an *agent* is
    consumed just as truly; `flip_signal`'s `comparator`/`threshold` are evaluated by the measurer
    reading `core/feedback-loop.md`, and demanding Python read them would be demanding the wrong
    thing. Requiring only a code reader would have failed this tree on two correct fields.

Deliberately NOT checked: keys nested inside an `as_is` / `to_be` / `question` payload. Those are
free-form by kind — the map projects them by structure precisely because the spec does not promise
their names — so requiring a reader would invert the design.

The honest limit, stated because a gate that hides one is worse than none: this matches on the field
NAME, so it cannot distinguish a pin's `depends_on` from an item's. It would not have caught the bug
that prompted it. It catches the *next* field — one declared under a name nothing else uses — and
the instance itself is pinned by `tests/test_ledger.py` instead. Two different questions, two
different gates.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "src" / "core" / "decisions-ledger-spec.md"
PAYLOAD_KEYS = ("as_is", "to_be", "question")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402  — the authority on what ships; never a second copy of that fact


def declared_fields(spec_text: str) -> list[tuple[str, int]]:
    """Field names from the spec's jsonc blocks, skipping free-form payload interiors.

    Tracks bracket depth rather than indentation: the spec's examples are hand-formatted and
    indentation is not a carrier.
    """
    out: list[tuple[str, int]] = []
    line_no = 0
    in_block = False
    skip_depth: int | None = None
    for line in spec_text.splitlines():
        line_no += 1
        if line.startswith("```"):
            in_block = line.startswith("```jsonc")
            skip_depth = None
            continue
        if not in_block:
            continue
        delta = line.count("{") + line.count("[") - line.count("}") - line.count("]")
        if skip_depth is not None:
            skip_depth += delta
            if skip_depth <= 0:
                skip_depth = None
            continue
        m = re.match(r'^\s*"([a-z_]+)"\s*:', line)
        if not m:
            continue
        name = m.group(1)
        if name in PAYLOAD_KEYS and delta > 0:
            skip_depth = delta          # descend past a free-form payload
            continue
        out.append((name, line_no))
    return out


def readers() -> str:
    """Everything that ships and could consume a field: our code, and our doctrine.

    The skill half is asked of `build.shipped_skill_files()` rather than globbed. The glob it
    replaced said "everything that ships" and included two `TODO.md` build checklists and all of
    `writing-skills`, which never ships — so a field whose only reader was a TODO passed a gate whose
    own docstring promised otherwise. Same bug as the one `check_tool_carriers.py` carried, and the
    same fix: the build owns the fact, nobody keeps a second copy of it.
    """
    text = []
    paths = [p for p in build.shipped_skill_files() if p.suffix in (".md", ".json")]
    for pattern in ("src/runtime/*.py", "src/mcp/*.py", "src/core/*.md", "src/hooks/*.py"):
        paths += ROOT.glob(pattern)
    for path in paths:
        if path.resolve() == SPEC.resolve():
            continue                    # the declaration is not a reading of itself
        text.append(path.read_text(encoding="utf-8"))
    return "\n".join(text)


def main() -> int:
    spec_text = SPEC.read_text(encoding="utf-8")
    corpus = readers()
    seen: set[str] = set()
    unread: list[tuple[str, int]] = []
    for name, line_no in declared_fields(spec_text):
        if name in seen:
            continue
        seen.add(name)
        if not re.search(rf"\b{re.escape(name)}\b", corpus):
            unread.append((name, line_no))

    for name, line_no in unread:
        print(f"ERROR {SPEC.relative_to(ROOT).as_posix()}:{line_no}: `{name}` is declared by the "
              f"schema and read by nothing that ships — no runtime code, no doctrine, no playbook. "
              f"Give it a reader or remove it; a field addressed to nobody reads as a capability.")
    print(f"\n{len(seen)} declared field(s) checked — {len(unread)} with no reader")
    return 1 if unread else 0


if __name__ == "__main__":
    sys.exit(main())
