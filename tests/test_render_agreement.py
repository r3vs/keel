"""Two renderers, and the arithmetic that says whether they looked at the same thing.

A design pass has always had two of them: the detector renders the URL itself to compute contrast and
token membership, and the picture a taste critique is read off is captured separately. Nothing tied
them together, so a critique of a desktop screenshot could rest on facts computed at 390x844 and
read, in the write-up, exactly like a critique that did not. The claim was not wrong — it was
*unfalsifiable*, because nobody could tell which render it was about.

What is testable here is the half that is arithmetic: a browser capture is an integer
device-pixel-ratio multiple of its viewport, so the geometry either maps or the two pictures are
different renders. The URL is not testable — a PNG carries no address — and the property this file
asserts about it is that the tool says so, reporting it under `declared` and never counting it as
agreement. A checker that quietly graded a declared string as evidence would be the exact confusion
the package spends its determinism dial on.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

import design  # noqa: E402
import visual  # noqa: E402
from test_visual import BG, TempImage, _png  # noqa: E402


def _shot(width: int, height: int) -> bytes:
    return _png(width, height, lambda x, y: BG)


def _scan(kind: str = "render", viewport: str = "390x844", urls=("http://localhost:3000",)) -> dict:
    """The `target` block `design.scan()` reports — built through the real function, not by hand."""
    paths = list(urls) if kind == "render" else ["src/ui"]
    return {"target": design._target(paths, viewport), "findings": []}


class TestTheScanSaysWhatItLookedAt(unittest.TestCase):
    """The report used to say only what it FOUND, which cannot answer 'over what?'."""

    def test_urls_and_paths_are_told_apart(self):
        self.assertEqual("render", design._target(["https://example.test"], "")["kind"])
        self.assertEqual("source", design._target(["src/ui/App.tsx"], "")["kind"])
        self.assertEqual("mixed", design._target(["src/ui", "http://localhost:3000"], "")["kind"])

    def test_the_target_survives_the_paths_that_report_no_findings(self):
        """An `unchecked` report is exactly when a caller most needs to know what was attempted.

        The detector is stubbed absent rather than invoked: what is under test is the report's
        shape on the path where nothing ran, and shelling out to npx to reach it would make the
        assertion depend on whether this machine has Node."""
        original = design._detect_cmd
        design._detect_cmd = lambda: None
        try:
            out = design.scan(["src/ui/App.tsx"])
        finally:
            design._detect_cmd = original
        self.assertTrue(out.get("unchecked"))
        self.assertIn("target", out, "a scan that could not run still says what it was pointed at")
        self.assertEqual("source", out["target"]["kind"])


class TestRenderAgreement(unittest.TestCase):
    def test_the_same_viewport_at_1x_agrees(self):
        with TempImage(_shot(390, 844)) as img:
            out = visual.render_agreement(img, scan=_scan())
        self.assertEqual("agree", out["status"], out)
        self.assertEqual(1, out["device_pixel_ratio"])
        self.assertEqual("viewport", out["capture"])

    def test_a_retina_capture_is_the_same_render(self):
        """2x is not a mismatch — it is the same page on a denser screen, and flagging it would
        train everyone to ignore the checker."""
        with TempImage(_shot(780, 1688)) as img:
            out = visual.render_agreement(img, scan=_scan())
        self.assertEqual("agree", out["status"], out)
        self.assertEqual(2, out["device_pixel_ratio"])

    def test_a_full_page_capture_agrees_and_is_reported_as_one(self):
        with TempImage(_shot(390, 2400)) as img:
            out = visual.render_agreement(img, scan=_scan())
        self.assertEqual("agree", out["status"], out)
        self.assertEqual("full_page", out["capture"])

    def test_a_desktop_picture_against_mobile_facts_is_a_mismatch(self):
        """The failure the tool exists for: judged one render, evidenced by another."""
        with TempImage(_shot(1440, 900)) as img:
            out = visual.render_agreement(img, scan=_scan())
        self.assertEqual("mismatch", out["status"])
        self.assertEqual(["width"], [m["field"] for m in out["mismatches"]])

    def test_a_crop_is_a_mismatch_even_at_the_right_width(self):
        with TempImage(_shot(390, 400)) as img:
            out = visual.render_agreement(img, scan=_scan())
        self.assertEqual("mismatch", out["status"])
        self.assertEqual(["height"], [m["field"] for m in out["mismatches"]])

    def test_facts_read_off_source_do_not_cover_a_picture(self):
        """§36's first residual, as arithmetic: the JSX has no composition in it."""
        with TempImage(_shot(390, 844)) as img:
            out = visual.render_agreement(img, scan=_scan(kind="source"))
        self.assertEqual("mismatch", out["status"])
        self.assertEqual("kind", out["mismatches"][0]["field"])

    def test_a_fractional_scale_factor_is_declared_rather_than_guessed(self):
        """Pixel 5 is 2.625x and a 125% Windows display is 1.25x — both real, neither inferrable.

        The inference deliberately claims only 1x/2x/3x, because one that stretched to fit any ratio
        would agree with a desktop capture judged against mobile facts. So the honest path is to
        declare what the browser was driven at, and the declaration is then checked against the
        pixels rather than believed.
        """
        with TempImage(_shot(1024, 2216)) as img:   # 390x844 at 2.625, rounded as a browser rounds
            declared = visual.render_agreement(img, scan=_scan(), captured="390x844@2.625")
            guessed = visual.render_agreement(img, scan=_scan())
        self.assertEqual("agree", declared["status"], declared)
        self.assertEqual("declared", declared["scale_source"])
        self.assertEqual("mismatch", guessed["status"])
        self.assertIn("declared", guessed["mismatches"][0]["note"])

    def test_a_declaration_the_pixels_refute_is_caught(self):
        """The declared path is not a way to assert your way past the check."""
        with TempImage(_shot(390, 844)) as img:
            out = visual.render_agreement(img, scan=_scan(), captured="390x844@3")
        self.assertEqual("mismatch", out["status"])
        self.assertEqual("scale", out["mismatches"][0]["field"])

    def test_a_capture_driven_at_another_viewport_is_a_mismatch(self):
        with TempImage(_shot(1440, 900)) as img:
            out = visual.render_agreement(img, scan=_scan(), captured="1440x900@1")
        self.assertEqual("mismatch", out["status"])
        self.assertEqual("viewport", out["mismatches"][0]["field"])

    def test_a_scan_with_no_viewport_is_unchecked_not_agreed(self):
        """The detector's default viewport is not ours to guess, and guessing it would manufacture
        an agreement out of an unknown."""
        with TempImage(_shot(390, 844)) as img:
            out = visual.render_agreement(img, scan=_scan(viewport=""))
        self.assertEqual("unchecked", out["status"])
        self.assertIn("viewport", out["reason"])

    def test_nothing_to_reconcile_with_is_unchecked(self):
        with TempImage(_shot(390, 844)) as img:
            out = visual.render_agreement(img)
        self.assertEqual("unchecked", out["status"])

    def test_an_unreadable_picture_is_unchecked_never_agree(self):
        with TempImage(b"not a png at all", suffix=".png") as img:
            out = visual.render_agreement(img, scan=_scan())
        self.assertEqual("unchecked", out["status"])

    def test_the_url_is_reported_as_declared_and_never_as_agreement(self):
        with TempImage(_shot(390, 844)) as img:
            same = visual.render_agreement(img, scan=_scan(), url="http://localhost:3000")
            other = visual.render_agreement(img, scan=_scan(), url="http://localhost:3000/admin")
            silent = visual.render_agreement(img, scan=_scan())
        self.assertEqual("same", same["declared"]["url_match"])
        self.assertNotIn("url", same["checked"], "a declared string is not something we measured")
        self.assertEqual("mismatch", other["status"])
        self.assertEqual("differs", other["declared"]["url_match"])
        self.assertEqual("undeclared", silent["declared"]["url_match"])
        self.assertEqual("agree", silent["status"], "an unstated URL is unknown, not disagreement")


if __name__ == "__main__":
    unittest.main()
