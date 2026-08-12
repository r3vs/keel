"""A router that omits a shipped skill, or routes to one that is gone, is a router that lies.

`which-skill` exists to pay down cognitive load: the human remembers one name instead of nineteen.
That only works while the map is complete. The failure is quiet and asymmetric — a skill the router
never mentions is a capability the operator does not know they installed, and it stays invisible
precisely because the router is where they would have looked.

It cannot be caught by the other gates, and the reason is structural: `verify_pointers.py` checks
that pointers RESOLVE, `check_consistency.py` checks modules against references. Neither has any
notion of a document whose job is to be exhaustive over a set. This is the gate for that class, and
the set it is exhaustive over is `build.shipped_skills()` — asked of the build rather than kept as a
second list here, for the same reason the build asks its own question about which skills ship.

The router is **user-invoked**, which is what makes it worth gating rather than trusting. A
model-invoked skill announces itself through its description on every turn, so an omission from a
router would be partly self-healing. A user-invoked one has no such backstop: if the map does not
say it, nothing else will.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build as B  # noqa: E402

ROUTER = "which-skill"
BACKTICKED = re.compile(r"`([a-z][a-z0-9-]{3,})`")


def _named_by_router() -> set[str]:
    return set(BACKTICKED.findall((B.SKILLS / ROUTER / "SKILL.md").read_text(encoding="utf-8")))


class TestRouterIsCompleteAndCurrent(unittest.TestCase):
    def test_the_router_ships(self):
        """A map nobody receives is not a map."""
        self.assertIn(ROUTER, B.shipped_skills())

    def test_every_shipped_skill_is_on_the_map(self):
        named = _named_by_router()
        missing = sorted(s for s in B.shipped_skills() if s != ROUTER and s not in named)
        self.assertEqual(
            missing, [],
            f"{ROUTER} names no route to: {', '.join(missing)}. Add each to the map (or say plainly "
            f"why it is unroutable) — an installed skill the router omits is one the operator has "
            f"no way to discover.",
        )

    def test_the_router_names_no_skill_that_is_gone(self):
        """The other direction, which a rename produces silently."""
        all_dirs = {d.name for d in B.SKILLS.iterdir() if d.is_dir()}
        # Only judge tokens that LOOK like this package's skill names: hyphenated, and matching the
        # shape of a directory that once existed. Anything else in backticks is ordinary prose.
        suspects = {n for n in _named_by_router() if "-" in n and n.endswith(
            ("-skill", "-skills", "-lifecycle", "-analysis", "-memory", "-layer", "-research",
             "-review", "-debugging", "-development", "-completion", "-rescue", "-forge",
             "-ledger", "-workflow"))}
        stale = sorted(n for n in suspects if n not in all_dirs)
        self.assertEqual(stale, [], f"{ROUTER} routes to skills that do not exist: {stale}")


if __name__ == "__main__":
    unittest.main()
