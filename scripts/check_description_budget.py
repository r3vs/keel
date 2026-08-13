#!/usr/bin/env python3
"""What this package puts into the host's always-on skill listing, and how long the two flagships are.

**The failure this gate exists for is a deadlock, not a typo.** Claude Code loads a listing of every
skill's name and description into context so the model knows what is available, and that listing has
a hard ceiling:

> *"The listing always contains every skill name, but if you have many skills, Claude Code shortens
> descriptions to fit the listing's character budget, which can strip the keywords Claude needs to
> match your request. The budget scales at 1% of the model's context window. When the listing
> overflows, Claude Code drops descriptions starting with the skills you invoke least, so the skills
> you use most keep their full text."*
> — https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short

Read the drop order against a package this size and it closes on itself. Keel shipped eighteen
model-invoked skills of nineteen carrying **7,745** characters of description; the two longest were
the two flagships, at 824 and 845. For a **cold** user — the one the package is for — every Keel
skill has an invocation count of zero, so Keel's entries are first to lose their descriptions, and
the two longest are the most expensive to keep. A skill whose description is not in context cannot match a
request; a skill that never matches is never invoked; a skill that is never invoked stays at the
front of the drop queue. Nothing in that loop is broken enough to fail a test.

The escape hatch a user has for *their* skills does not reach ours: `skillOverrides` (the setting
that lists a low-priority skill by name only, freeing budget) says plainly *"Plugin skills are not
affected by `skillOverrides`. Manage those through `/plugin` instead."* Keel ships as a plugin. The
only lever on Keel's share of that budget is Keel's own frontmatter, which is what this gate holds.

So the fix is two-sided and this gate checks both sides:

1. **Fewer entries.** Every skill whose trigger is a name a person can remember sets
   `disable-model-invocation: true` — Claude Code's own behaviour table gives the consequence in the
   column that matters, *"Description not in context"*, and Pi reads the same key
   (`tests/test_invocation_axis.py` holds the one-source property and the Codex sidecar). Only the
   skills that must fire on a situation the user cannot name stay model-invoked, and only those are
   counted here.
2. **Shorter bodies.** A `SKILL.md` is not free once it loads: *"Once a skill loads, its content
   stays in context across turns, so every line is a recurring token cost"* (same page). That makes a
   loaded skill body behave like an instruction file for the rest of the session, and this repo
   already has the number for that regime — `src/core/instruction-files.md`, rule 3: *"One host
   truncates by bytes, another loses adherence past ~200 lines."* Anthropic's own published guidance
   for a SKILL.md body is 500 lines; ours is stricter, and the reason is that transfer, stated rather
   than assumed.

**What this gate does NOT claim.** It counts characters in `description`. It cannot tell a
description that triggers well from one that does not — that is what `evals/evals.json` is for. Nor
does it model the host's tokenizer: the ceiling below is derived, and the derivation is written out
so a wrong premise is visible rather than buried.

Run in CI: `python scripts/check_description_budget.py` (exit 1 on either violation).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build as B  # noqa: E402  — the authority on what ships; never a second copy of that fact

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
#: `description:` and everything indented under it — the YAML folded (`>-`) form both flagships use
#: folds its continuation lines with single spaces, which is what the host ends up with.
DESCRIPTION = re.compile(r"^description:\s*(>-|\|-|>|\|)?[ \t]*(.*(?:\n[ \t]+.*)*)", re.M)
#: The exact spelling both Claude Code and Pi parse. `tests/test_invocation_axis.py` refuses every
#: other truthy spelling, so matching the literal here is matching what the hosts match.
USER_INVOKED = re.compile(r"^disable-model-invocation:\s*true\s*$", re.M)

# ── the two declared numbers ───────────────────────────────────────────────────────────────────
# HYPOTHESIS. The listing budget, in characters, that Keel is allowed to occupy. The arithmetic,
# each step separately checkable:
#
#   200_000  the most conservative context window published for a model Claude Code runs (the
#            standard window for Haiku / Sonnet / Opus; Sonnet's 1M is a beta opt-in, so assuming it
#            would size the budget off the most generous case rather than the floor)
#   × 0.01   the doc's rule: "The budget scales at 1% of the model's context window"
#   = 2_000  the whole listing budget, shared by EVERY skill the user has
#   × 0.60   Keel's share. It is a guest in that budget: Claude Code's own bundled skills (/doctor,
#            /code-review, /batch, /debug, /loop, /claude-api, /verify …) are always present, and any
#            skill the user wrote is competing for the same characters. Sixty percent leaves 800
#            characters — enough for the bundled set plus a handful of the user's own — and it is a
#            deliberate over-allocation rather than a fair split, because Keel's two flagships are
#            the entries that must survive on a repo where nothing has been invoked yet.
#   = 1_200
#
# The unit is the one soft spot and it is named rather than hidden: the doc calls it a "character
# budget" whose size scales with a window measured in TOKENS, and the override
# (`SLASH_COMMAND_TOOL_CHAR_BUDGET`) is documented as "a fixed character count". Reading 1% of
# 200,000 as 2,000 *characters* is the conservative reading — if it is really 2,000 tokens the true
# ceiling is roughly four times larger and this gate is merely strict. The reverse error would be
# silent, which is why the conservative reading is the one encoded.
LISTING_BUDGET_CHARS = 1_200

# HYPOTHESIS. The line cap on the two flagship SKILL.md bodies. Not a guess and not Anthropic's
# number: `src/core/instruction-files.md` rule 3 records that Claude Code "loses adherence past ~200
# lines" of always-on instruction text, and a loaded skill body is always-on for the rest of the
# session ("its content stays in context across turns"). Anthropic's published SKILL.md guidance is
# 500 lines; this is stricter because the adherence fact bites before the token budget does, and the
# two flagships are the only bodies in this repo long enough for it to matter.
#
# **What this counts, stated because the honest version is narrower than the tempting one.** It
# counts the lines of ONE file. Progressive disclosure is what is supposed to pay for the cap — the
# detail moves to `references/*.md` behind a pointer, and a *conditional* pointer costs nothing
# until its condition holds. That is true of most of each flagship's "Read this when" table and it
# is NOT true of the file that absorbed most of the reduction that brought both bodies under the
# cap: `references/guardrails.md`, whose own row states its condition as *"before acting, in any
# mode"* — i.e. always. So `SKILL.md + guardrails.md` is what an executing agent actually carries,
# and that sum fell by far less than the body numbers alone suggest. The cap is still the right
# rule and the moved text is still better placed (a reference is read once and stays reachable, a
# body line is re-read every turn), but this gate cannot tell a conditional pointer from an
# unconditional one. Read it as "the body is capped", never as "the always-on load fell by 89
# lines". Making the sum the measured quantity needs a reader for the "Read this when" table's
# condition column, which nothing here has.
FLAGSHIP_MAX_LINES = 200

#: The bodies the cap applies to. Named individually rather than quantified over every skill,
#: because the other seventeen are already far below it and a cap they cannot reach is a rule
#: nobody is following.
FLAGSHIPS = ("codebase-rescue", "greenfield-forge")


def description_of(skill: str) -> str:
    """The description as the host receives it: folded to one line, whitespace-collapsed.

    A YAML folded block scalar joins its lines with single spaces, so counting the raw bytes of the
    authored block would over-count by the indentation — which is exactly the kind of number that
    reads as measured and is not.
    """
    text = (B.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    fm = FRONTMATTER.match(text)
    if not fm:
        raise SystemExit(f"ERROR {skill}/SKILL.md has no frontmatter — nothing to measure")
    m = DESCRIPTION.search(fm.group(1))
    if not m:
        raise SystemExit(f"ERROR {skill}/SKILL.md declares no `description`")
    return " ".join(m.group(2).split())


def model_invoked() -> list[str]:
    """Shipped skills whose description the host keeps in context — asked of the frontmatter, and of
    `build.py` for what ships. A dev-only skill costs a user nothing; `writing-skills` never travels."""
    out = []
    for skill in B.shipped_skills():
        fm = FRONTMATTER.match((B.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8"))
        if fm and not USER_INVOKED.search(fm.group(1)):
            out.append(skill)
    return sorted(out)


def main() -> int:
    errors = 0

    listed = model_invoked()
    sizes = {s: len(description_of(s)) for s in listed}
    total = sum(sizes.values())
    print("model-invoked skills (description in context on every turn):")
    for skill, n in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {skill}")
    print(f"  {total:5d}  TOTAL against a declared budget of {LISTING_BUDGET_CHARS}")

    if total > LISTING_BUDGET_CHARS:
        errors += 1
        print(f"ERROR the model-invoked descriptions total {total} characters, over the declared "
              f"{LISTING_BUDGET_CHARS}. The host drops descriptions starting with the least-invoked "
              f"skill, and on a cold repo every Keel skill is least-invoked — so overflow costs the "
              f"flagships their triggers first. Either tighten a description, set "
              f"`disable-model-invocation: true` on a skill whose trigger is a name a person can "
              f"remember, or re-derive LISTING_BUDGET_CHARS from the doc's 1% rule and say why here.")

    # A description under the spec's floor fails `claude plugin validate` rather than this gate, but
    # a gate that lets a 6-character description through while policing the total would be optimizing
    # the wrong end of the same field.
    for skill, n in sorted(sizes.items()):
        if n < 20:
            errors += 1
            print(f"ERROR {skill}: description is {n} characters; the Agent Skills spec requires at "
                  f"least 20, and a description this short cannot carry a trigger phrase")

    print("\nflagship SKILL.md bodies:")
    for skill in FLAGSHIPS:
        path = B.SKILLS / skill / "SKILL.md"
        lines = len(path.read_text(encoding="utf-8").splitlines())
        print(f"  {lines:5d}  {skill}/SKILL.md (cap {FLAGSHIP_MAX_LINES})")
        if lines > FLAGSHIP_MAX_LINES:
            errors += 1
            print(f"ERROR {path.relative_to(ROOT).as_posix()} is {lines} lines, over the "
                  f"{FLAGSHIP_MAX_LINES}-line cap. A loaded skill body stays in context across "
                  f"turns, so it is always-on text, and adherence falls off past ~200 lines of it "
                  f"(src/core/instruction-files.md, rule 3). Move the detail behind a "
                  f"`references/*.md` with a conditional pointer — that is what progressive "
                  f"disclosure is for.")

    print(f"\n{len(listed)} model-invoked of {len(B.shipped_skills())} shipped, "
          f"{total}/{LISTING_BUDGET_CHARS} listing characters, {len(FLAGSHIPS)} bodies capped "
          f"— {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
