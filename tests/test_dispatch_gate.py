"""The dispatch gate in `check_consistency.py`, exercised by RUNNING it on a built tree.

The gate it replaced asked whether a reference was *linked anywhere* — SKILL.md, modules.json or any
sibling. `design-taste-lens.md` satisfied that for months while nothing ran it: it was named by a
sibling playbook, in a paragraph whose point was that the taste half is **not** that module, and by a
row in the conditional index. So the property under test is not "the linter reports something"; it is
that a **cross-reference and a lookup do not count as a dispatch, and the two real idioms do**.

Asserted against a throwaway skill tree, not against this repo, for the reason `test_map.py` states
about renderers: a test that reads the gate's source would pass on a gate someone disarmed, and a
test that only runs it against a green repo proves the tree is green today, not that the rule bites.
Each leg builds the tree that SHOULD fail or SHOULD pass and runs the real script over it.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "check_consistency.py"

SKILL_MD = """---
name: fake-skill
description: Exists only to be linted by the dispatch gate; twenty characters is easily cleared.
---

# Fake skill

## Before you act

Read `references/guard.md` first.

## The phases

### Phase 1 — Comprehension

Run the analysis modules in `modules.json`, then read `references/phase-1.md`.
{extra_phase_line}

## Read this when

| When | Read |
|---|---|
| you are judging how a UI looks | `references/lens.md` |
"""

SIBLING_MD = """# A module playbook

The taste half is NOT this detector — it is a separate lens. Full playbook:
`references/lens.md`.
"""

MODULE = {
    "id": "sibling",
    "phase": 1,
    "kind": "core",
    "type": "judgment",
    "produces": ["design_concern"],
    "reference": "references/module-sibling.md",
}


class TestAMentionIsNotADispatch(unittest.TestCase):
    def _run(self, modules: list, extra_phase_line: str = "") -> tuple[int, str]:
        """Build a minimal repo around the REAL gate script and run it."""
        import json

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "scripts").mkdir()
        shutil.copy2(GATE, tmp / "scripts" / GATE.name)
        sroot = tmp / "src" / "skills" / "fake-skill"
        (sroot / "references").mkdir(parents=True)
        (tmp / "src" / "core").mkdir(parents=True)
        (sroot / "SKILL.md").write_text(SKILL_MD.format(extra_phase_line=extra_phase_line),
                                        encoding="utf-8")
        (sroot / "modules.json").write_text(json.dumps({"modules": modules}), encoding="utf-8")
        (sroot / "references" / "guard.md").write_text("# Guard\n", encoding="utf-8")
        (sroot / "references" / "phase-1.md").write_text("# Phase 1\n", encoding="utf-8")
        (sroot / "references" / "module-sibling.md").write_text(SIBLING_MD, encoding="utf-8")
        (sroot / "references" / "lens.md").write_text("# The lens\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(tmp / "scripts" / GATE.name)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_a_sibling_mention_plus_a_conditional_row_is_not_a_dispatch(self):
        """The exact shape the old orphan check passed: linked twice, run by nobody."""
        code, out = self._run([MODULE])
        self.assertEqual(code, 1, f"the gate accepted an undispatched playbook:\n{out}")
        self.assertIn("undispatched playbook: references/lens.md", out)
        self.assertNotIn("references/module-sibling.md", out.split("undispatched playbook")[0][-200:],
                         "the module's own reference is dispatched by the catalog and must not be "
                         "reported")

    def test_the_catalog_dispatches_a_module_in_a_phase_that_reads_it(self):
        """Idiom A: `### Phase 1` names modules.json, so every phase-1 module is a step."""
        lens_module = dict(MODULE, id="lens", reference="references/lens.md")
        code, out = self._run([MODULE, lens_module])
        self.assertNotIn("undispatched playbook", out,
                         f"a catalog entry in a dispatched phase is a dispatch:\n{out}")
        self.assertEqual(code, 0, out)

    def test_the_flow_dispatches_what_the_phase_names_directly(self):
        """Idiom B: named in a phase section — no catalog entry needed."""
        code, out = self._run([MODULE], extra_phase_line="Then apply `references/lens.md`.")
        self.assertNotIn("undispatched playbook", out, out)
        self.assertEqual(code, 0, out)

    def test_a_module_in_a_phase_that_never_reads_the_catalog_is_still_undispatched(self):
        """The loophole this rule closes, and the reason the check is per-phase.

        Registering a capability under `phase: 5` while only Phase 1's playbook reads the catalog
        leaves it exactly as unrun as it was — with a catalog entry now saying otherwise, which is
        worse than silence. `browser-verification` is the real instance: its module entry only
        became a dispatch once `phase-5-validate.md` named the Phase-5 modules.
        """
        stranded = dict(MODULE, id="stranded", phase=5, reference="references/lens.md")
        code, out = self._run([MODULE, stranded])
        self.assertEqual(code, 1, f"a phase-5 entry passed while no phase-5 playbook reads the "
                                  f"catalog:\n{out}")
        self.assertIn("undispatched playbook: references/lens.md", out)


if __name__ == "__main__":
    unittest.main()
