"""Tests for runtime/design_tokens.py — the DTCG design-contract generator (design twin of generate.py).

Offline/stdlib. Pins the four things that must hold: DTCG parse (type inheritance + alias resolution +
cycle guard), the three layer projections (CSS vars / Tailwind v4 / DESIGN.md frontmatter), the
role/scale/radius mapping read from $type + group, and the round-trip alignment guarantee — a correct
generator's CSS layer drift-checks to zero against its own contract.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import design_tokens as dt  # noqa: E402

# A DTCG contract exercising: type inheritance (group $type), an alias, every mapped role, and a
# spacing dimension that must NOT reach the DESIGN.md contract (CSS-only).
CONTRACT = {
    "color": {
        "$type": "color",
        "primary": {"$value": "#1a1a1a"},
        "surface": {"$value": "#faf9f7"},
        "accent": {"$value": "{color.primary}"},          # alias → resolves to #1a1a1a
    },
    "font": {
        "$type": "fontFamily",
        "display": {"$value": ["Fraunces", "serif"]},       # list → stack
        "body": {"$value": "Avenir Next, sans-serif"},
    },
    "type": {                                               # a font-size group
        "$type": "dimension",
        "base": {"$value": "16px"},
        "lg": {"$value": "20px"},
    },
    "radius": {
        "$type": "dimension",
        "sm": {"$value": "4px"},
        "md": {"$value": "8px"},
    },
    "space": {                                              # spacing dimension — CSS-only
        "$type": "dimension",
        "gap": {"$value": "12px"},
    },
}


class TestParse(unittest.TestCase):
    def test_flatten_inherits_group_type(self):
        ts = dt.TokenSet.from_obj(CONTRACT)
        by = {t["path"]: t for t in ts.tokens}
        self.assertEqual(len(ts.tokens), 10)
        self.assertEqual(by["color.primary"]["type"], "color")     # inherited from group $type
        self.assertEqual(by["radius.sm"]["type"], "dimension")

    def test_alias_resolves(self):
        by = {t["path"]: t for t in dt.TokenSet.from_obj(CONTRACT).tokens}
        self.assertEqual(by["color.accent"]["value"], "#1a1a1a")

    def test_alias_cycle_leaves_literal(self):
        cyc = {"a": {"$type": "color", "x": {"$value": "{a.y}"}, "y": {"$value": "{a.x}"}}}
        by = {t["path"]: t for t in dt.TokenSet.from_obj(cyc).tokens}
        # a cycle must not loop; the literal alias survives rather than hanging or blanking
        self.assertTrue(by["a.x"]["value"].startswith("{"))


class TestGenerators(unittest.TestCase):
    def setUp(self):
        self.ts = dt.TokenSet.from_obj(CONTRACT)

    def test_css_vars_are_exact_and_lossless(self):
        css = dt.to_css_vars(self.ts)
        self.assertIn("--color-primary: #1a1a1a;", css)
        self.assertIn("--font-display: Fraunces, serif;", css)   # list → stack
        self.assertIn("--type-base: 16px;", css)
        self.assertIn("--radius-sm: 4px;", css)
        self.assertIn("--color-accent: #1a1a1a;", css)           # alias resolved
        self.assertIn("--space-gap: 12px;", css)                 # spacing IS in CSS

    def test_tailwind_namespaces_by_type(self):
        tw = dt.to_tailwind(self.ts)
        self.assertIn("--color-primary:", tw)
        self.assertIn("--font-display:", tw)     # fontFamily → font-*
        self.assertIn("--radius-sm:", tw)        # radius dimension → radius-*
        self.assertIn("--text-base:", tw)        # font-size dimension → text-*

    def test_design_md_populates_only_the_enforced_surfaces(self):
        md = dt.to_design_md(self.ts)
        self.assertTrue(md.startswith("---"))
        # colors
        self.assertIn("colors:", md)
        self.assertIn("primary:", md)
        self.assertIn("accent:", md)             # alias-resolved color present
        # typography families + scale
        self.assertIn("typography:", md)
        self.assertIn("fontFamily:", md)
        self.assertIn("scale:", md)
        self.assertIn("base:", md)
        # rounded
        self.assertIn("rounded:", md)
        # a font stack must be quoted so Impeccable's frontmatter parser reads it
        self.assertIn('"Avenir Next, sans-serif"', md)

    def test_design_md_excludes_unmapped_spacing(self):
        # space.gap is a dimension in no recognized group → CSS-only, never force-fit into the contract
        md = dt.to_design_md(self.ts)
        self.assertNotIn("gap:", md)


class TestRoundTripDriftCheck(unittest.TestCase):
    def setUp(self):
        self.ts = dt.TokenSet.from_obj(CONTRACT)

    def test_a_correct_generator_round_trips_to_zero_drift(self):
        css = dt.to_css_vars(self.ts)
        self.assertEqual(dt.drift_check(self.ts, css)["drift"], [])   # the alignment guarantee

    def test_changed_value_is_drift(self):
        broken = dt.to_css_vars(self.ts).replace("--color-primary: #1a1a1a;",
                                                  "--color-primary: #000000;")   # a hand-edit
        d = dt.drift_check(self.ts, broken)["drift"]
        self.assertTrue(any(x["var"] == "--color-primary" and x["kind"] == "changed" for x in d))
        self.assertTrue(all(x["confidence"] == "extracted" for x in d))          # a fact, skips fp-check

    def test_missing_and_extra_are_drift(self):
        d = dt.drift_check(self.ts, ":root { --rogue: 1px; }")["drift"]
        self.assertTrue(any(x["kind"] == "missing" for x in d))    # contract tokens absent
        self.assertTrue(any(x["var"] == "--rogue" and x["kind"] == "extra" for x in d))


if __name__ == "__main__":
    unittest.main()
