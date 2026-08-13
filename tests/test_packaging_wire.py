"""`scripts/check_packaging_wire.py` — shown to fail, not just observed passing.

A gate whose only evidence is a green run on today's tree has never been demonstrated to do
anything; that is the shape this repo keeps finding in other people's suites and it applies to its
own linters first. So the prose half of the gate is driven here with a **doctored document** and a
**fake measurement**, which is exactly why `audit()` is a pure function of those two arguments.

The wire half — spawning the server — is not re-run here. `tests/test_mcp_server.py` already pays
that cost once per suite, and the gate itself runs in CI; duplicating a 3-second handshake to
re-learn what that step already proves would buy nothing.
"""
import importlib.util
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_cpw", ROOT / "scripts" / "check_packaging_wire.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CPW = _gate()

#: A measurement standing in for the server's, so the assertions below are about the COMPARISON
#: rather than about whatever the server happens to serve today. The values are the ones measured on
#: 2026-08-13 — keeping them here does not make them a second carrier of the truth, because nothing
#: compares them to the doc: they are only ever paired with the doctored text written beside them.
TRUTH = {
    "tools": 67,
    "wire_chars": 98_112,
    "tokens": 98_112 / 4,
    "chars_per_token": 4,
    "median_tool_chars": 1_410,
    "longest_desc_chars": 1_405,
    "median_desc_chars": 372,
    "instructions_chars": 335,
    "docstring_chars": 51_117,
    "headroom_chars": 2_048 - 1_405,
}


def _drift(errors: list[str]) -> list[str]:
    """Only the stale-number reports. A synthetic document is missing every OTHER measurement by
    construction, so it also trips the dead-pattern rule — which is that rule working, and noise
    here. The two are told apart by shape: a drift report cites a line and quotes the sentence."""
    return [e for e in errors if "says `" in e]


class TestTheProseHalfCanFail(unittest.TestCase):
    def test_a_restatement_inside_tolerance_passes(self):
        # 99 k against 98,112 measured is 0.9% off — the prose rounds, and rounding is not drift.
        errors, checked, _ = CPW.audit("the result is ~99 k characters of JSON today", TRUTH)
        self.assertEqual(checked, 1)
        self.assertEqual(_drift(errors), [])

    def test_a_restatement_outside_tolerance_fails(self):
        # 120 k is 22% off: somebody added tools, and the section's "~a fifth of a 128 k window"
        # argument is the thing that needs re-reading.
        errors, _, _ = CPW.audit("the result is ~120 k characters of JSON today", TRUTH)
        stale = _drift(errors)
        self.assertEqual(len(stale), 1, errors)
        self.assertIn("98,112", stale[0])
        self.assertIn("tolerance 5%", stale[0])

    def test_a_count_gets_no_tolerance(self):
        """66 tools is not 67 within any tolerance — 1.5% would pass the default and must not."""
        errors, _, _ = CPW.audit("| tools advertised | **66** |", TRUTH)
        self.assertTrue([e for e in _drift(errors) if "advertises on the wire" in e], errors)

    def test_a_pattern_that_matches_nothing_is_an_error(self):
        """The lesson `check_stated_facts.py` learned the hard way: a dead pattern reads as
        coverage. Against an empty document EVERY pattern is dead, so every one must report."""
        errors, checked, hits = CPW.audit("nothing here", TRUTH)
        self.assertEqual(checked, 0)
        self.assertEqual(len(errors), len(hits))
        self.assertTrue(all("matched nothing" in e for e in errors))


class TestEveryPatternIsAliveInTheDoc(unittest.TestCase):
    """The other direction, and the one that fires without uv on a developer's machine: the doc
    still spells every number in a shape the gate can see. A rewrite that drops a measurement is a
    gate quietly covering less, which is indistinguishable from a green run."""

    def test_each_pattern_matches_the_shipped_doc(self):
        text = CPW.DOC.read_text(encoding="utf-8")
        for fact in CPW.FACTS:
            for pattern in fact["patterns"]:
                with self.subTest(fact=fact["label"], pattern=pattern.pattern):
                    self.assertTrue(
                        pattern.search(text),
                        f"{CPW.DOC.name} no longer spells {fact['label']} in this shape")


class TestTheCeilingIsTheHostsUnit(unittest.TestCase):
    """The 2 KB ceiling is stated by Claude Code in KB — bytes — while the doc's figures are
    characters, and this repo's prose is full of em dashes. The gate must not quietly compare the
    two: `len(s)` and `len(s.encode())` differ by 2 per em dash, which is ~8 on our longest
    description today and grows with every one somebody adds."""

    def test_the_two_units_are_not_the_same_number_for_our_prose(self):
        sample = "a — b — c — d"
        self.assertNotEqual(len(sample), len(sample.encode("utf-8")))

    def test_the_limit_is_declared_in_bytes(self):
        self.assertEqual(CPW.TRUNCATION_LIMIT_BYTES, 2048)
        source = (ROOT / "scripts" / "check_packaging_wire.py").read_text(encoding="utf-8")
        # The ceiling check must measure encoded bytes. A regression to `len(desc)` would still
        # pass every other assertion in this file.
        self.assertTrue(re.search(r"len\(desc\.encode\(\"utf-8\"\)\)", source),
                        "the ceiling check stopped measuring bytes")


if __name__ == "__main__":
    unittest.main()
