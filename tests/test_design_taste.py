"""The taste lens is ONE lens, and every skill that can render a UI also judges one.

The gap this closes is not "a file was missing". For months the lens existed, was attributed, and was
pointed at — from `codebase-rescue` only. Greenfield could generate an entire presentation layer from
one DTCG contract, aligned by construction, and nothing anywhere asked whether the result looked like
every other generated UI. The half of the package most likely to produce the statistical center of
design was the half with no lens on it.

So the property under test is a **correspondence between two structural facts in the same catalog**:
a skill whose modules name a design engine (it can scan, or generate, a rendered surface) must also
carry the judgment module that reads what comes out. Asserted over `modules.json`, never over prose —
a grep for the word "taste" would pass on a paragraph that mentions it and runs nothing, which is the
exact failure this file exists to prevent recurring.

The one exemption is declared, not silent, and it is checked for staleness: an exemption that no
longer applies to a skill with a design engine is a hole nobody would notice closing.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "src" / "skills"
LENS = "references/core/design-taste.md"

#: Engines that mean "this skill's output IS a rendered surface" — it scans one, or generates one.
DESIGN_ENGINES = {"mcp:design_scan", "mcp:generate_tokens"}

#: skill -> why it has a design engine and deliberately does NOT run the taste lens.
NO_LENS_OK = {
    "screenshot-to-code": (
        "the reference image IS the elected oracle here; a lens that overruled it would re-decide "
        "what the human handed over. A taste observation in that skill is a pin about the reference"
    ),
}


def _catalogs() -> dict:
    out = {}
    for p in sorted(SKILLS.glob("*/modules.json")):
        out[p.parent.name] = json.loads(p.read_text(encoding="utf-8"))["modules"]
    return out


def _has_design_engine(modules: list) -> bool:
    return any(m.get("engine") in DESIGN_ENGINES for m in modules)


def _lens_modules(modules: list) -> list:
    """Modules that dispatch THE lens — matched on the reference, not on a module id or a word.

    Other judgment modules legitimately produce `design_concern` (screenshot-to-code's pixel
    comparison is one); they are not this lens and must not be counted as it.
    """
    return [m for m in modules if m.get("reference") == LENS]


class TestOneLensBothDirections(unittest.TestCase):
    def test_a_skill_that_can_render_a_ui_also_judges_one(self):
        for skill, modules in _catalogs().items():
            if not _has_design_engine(modules) or skill in NO_LENS_OK:
                continue
            lens = _lens_modules(modules)
            with self.subTest(skill=skill):
                self.assertTrue(
                    lens,
                    f"{skill} names a design engine but dispatches no taste lens — it can produce "
                    f"or scan a UI and cannot say whether the result reads as designed")
                for m in lens:
                    self.assertEqual("judgment", m.get("type"), m["id"])
                    self.assertIn("design_concern", m.get("produces", []), m["id"])

    def test_the_lens_is_one_file_and_lives_in_core(self):
        """Two catalogs pointing at two playbooks is two lenses that will disagree by Christmas."""
        self.assertTrue((ROOT / "src" / "core" / "design-taste.md").is_file())
        strays = list(SKILLS.glob("*/references/design-taste*.md"))
        self.assertEqual([], strays, f"the lens was re-authored inside a skill: {strays}")
        for skill, modules in _catalogs().items():
            for m in modules:
                if m["id"] == "design-taste":
                    with self.subTest(skill=skill):
                        self.assertEqual(LENS, m.get("reference"),
                                         "a second copy of the lens, under the module's own name")

    def test_rescue_judges_before_the_interview_and_forge_after_the_build(self):
        """The two directions are a phase fact, not a manner of speaking.

        Backward, a taste finding is INPUT to the interview, so it has to exist before the interview
        runs (rescue Phase 2). Forward, there is nothing to judge until something was built, so it
        runs at validation. Same catalog, opposite ends of the same arc.
        """
        cats = _catalogs()
        rescue = _lens_modules(cats["codebase-rescue"])
        forge = _lens_modules(cats["greenfield-forge"])
        self.assertEqual(1, len(rescue))
        self.assertEqual(1, len(forge))
        self.assertLess(rescue[0]["phase"], 2, "a taste finding the interview never sees is a "
                                               "finding nobody can elect anything about")
        self.assertGreaterEqual(forge[0]["phase"], 5, "nothing to judge before something is built")

    def test_the_exemption_is_still_about_a_skill_with_a_design_engine(self):
        cats = _catalogs()
        for skill, why in NO_LENS_OK.items():
            with self.subTest(skill=skill):
                self.assertIn(skill, cats, f"{skill} no longer exists — drop the exemption")
                self.assertTrue(_has_design_engine(cats[skill]),
                                f"{skill} no longer names a design engine, so the exemption "
                                f"({why}) is exempting nothing and hides the next real gap")


if __name__ == "__main__":
    unittest.main()
