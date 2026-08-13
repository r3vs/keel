"""Tests for runtime/visual.py — the deterministic half of reading a reference image.

Offline/stdlib, and the PNG fixtures are **built here rather than committed**: the decoder is the
thing under test, so a binary blob checked into the repo would test it against bytes nobody in this
repo can read or amend. `_png` below is an independent encoder written from the same spec, which is
what makes a passing decode a real agreement between two implementations instead of a round-trip
through one.

What is pinned: the decode itself across the color types and bit depths a real capture arrives in;
the palette as a population statistic (coverage, not just presence); the two verdicts that carry the
skill's whole claim — a color that IS in the picture is `present` and one that is not is `absent`,
across anti-aliasing; the published color math; and the degradation contract, which is the one that
would fail silently in production — an image that could not be read must say `unchecked`, never
report an empty-but-successful palette.
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import visual  # noqa: E402

BG = (0xFA, 0xF9, 0xF7)          # a surface
ACCENT = (0x25, 0x63, 0xEB)      # a primary action
INK = (0x11, 0x18, 0x27)         # body text


def _chunk(tag: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + tag + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))


def _png(width: int, height: int, pixel, ctype: int = 2, depth: int = 8,
         palette: bytes = b"", filter_type: int = 0) -> bytes:
    """Encode a PNG from a `(x, y) -> tuple-of-samples` callable, written against the spec rather
    than against `visual.py`. `filter_type` is applied to every scanline so the decoder's five
    unfilter branches can each be exercised."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = (width * channels * depth + 7) // 8
    bpp = max(1, (channels * depth) // 8)
    raw, prev = b"", bytearray(stride)
    for y in range(height):
        line = bytearray(stride)
        if depth == 8:
            for x in range(width):
                line[x * channels:(x + 1) * channels] = bytes(pixel(x, y))
        elif depth == 16:
            for x in range(width):
                for c, v in enumerate(pixel(x, y)):
                    line[(x * channels + c) * 2] = v          # high byte carries the value
        else:                                                  # sub-byte: pack MSB-first
            per_byte = 8 // depth
            for x in range(width):
                v = pixel(x, y)[0]
                line[x // per_byte] |= v << (8 - depth * (x % per_byte + 1))
        enc = bytearray(line)
        if filter_type == 1:
            for i in range(stride - 1, bpp - 1, -1):
                enc[i] = (line[i] - line[i - bpp]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                enc[i] = (line[i] - prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                enc[i] = (line[i] - ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                enc[i] = (line[i] - pr) & 0xFF
        raw += bytes([filter_type]) + bytes(enc)
        prev = line
    out = b"\x89PNG\r\n\x1a\n" + _chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, depth, ctype, 0, 0, 0))
    if palette:
        out += _chunk(b"PLTE", palette)
    return out + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


def _button_screenshot(filter_type: int = 0) -> bytes:
    """A surface with a small accent button on it — the shape of every UI screenshot that matters
    here: one dominant background, one accent covering a couple of percent."""
    def px(x, y):
        return ACCENT if (10 <= x < 40 and 10 <= y < 20) else BG
    return _png(200, 100, px, filter_type=filter_type)


class TempImage:
    def __init__(self, data: bytes, suffix: str = ".png"):
        self.data, self.suffix = data, suffix

    def __enter__(self) -> str:
        self.dir = tempfile.TemporaryDirectory()
        p = Path(self.dir.name) / f"image{self.suffix}"
        p.write_bytes(self.data)
        return str(p)

    def __exit__(self, *exc):
        self.dir.cleanup()


class TestDecode(unittest.TestCase):
    def test_every_filter_type_decodes_to_the_same_image(self):
        """The five unfilter branches are the decoder's only real machinery; an encoder is free to
        pick any of them per scanline, so all five must land on identical pixels."""
        baselines = []
        for ft in range(5):
            with TempImage(_button_screenshot(filter_type=ft)) as path:
                facts = visual.image_facts(path)
            self.assertEqual(facts["status"], "read", f"filter {ft}")
            baselines.append([(e["hex"], round(e["coverage"], 4)) for e in facts["palette"]])
        for other in baselines[1:]:
            self.assertEqual(baselines[0], other)

    def test_geometry_is_reported_as_captured(self):
        with TempImage(_button_screenshot()) as path:
            facts = visual.image_facts(path)
        self.assertEqual((facts["width"], facts["height"]), (200, 100))

    def test_grayscale_palette_and_16bit_all_decode(self):
        """Every (color type × bit depth) combination a capture arrives in, decoded to the color a
        second implementation encoded.

        The matrix is the test. Its first version held four cases — gray@8, indexed@8, rgb@16,
        gray@4 — and the one pair it left out is the one that was broken: **grayscale at depth 16**
        multiplied its already-high-byte sample by 255/65535, so a white screenshot decoded to
        `#010101` and `verify_palette` refuted a correct `#ffffff`. Neither axis alone finds it —
        depth 16 was covered on the RGB path, grayscale was covered at depths 8 and 4 — which is why
        the cases below are now the product of the two axes rather than a sample of it.
        """
        cases = {
            "gray": (_png(20, 10, lambda x, y: (0x80,), ctype=0), "#808080"),
            "gray4": (_png(20, 10, lambda x, y: (0xF,), ctype=0, depth=4), "#ffffff"),
            "gray2": (_png(20, 10, lambda x, y: (0x2,), ctype=0, depth=2), "#aaaaaa"),
            "gray16": (_png(20, 10, lambda x, y: (0xFF,), ctype=0, depth=16), "#ffffff"),
            "gray16_mid": (_png(20, 10, lambda x, y: (0x80,), ctype=0, depth=16), "#808080"),
            "gray_alpha16": (_png(20, 10, lambda x, y: (0xFF, 0xFF), ctype=4, depth=16), "#ffffff"),
            "indexed": (_png(20, 10, lambda x, y: (1,), ctype=3,
                             palette=bytes(BG) + bytes(ACCENT)), visual.to_hex(ACCENT)),
            "indexed4": (_png(20, 10, lambda x, y: (1,), ctype=3, depth=4,
                              palette=bytes(BG) + bytes(ACCENT)), visual.to_hex(ACCENT)),
            "rgb": (_png(20, 10, lambda x, y: ACCENT, ctype=2), visual.to_hex(ACCENT)),
            "rgb16": (_png(20, 10, lambda x, y: ACCENT, ctype=2, depth=16), visual.to_hex(ACCENT)),
            "rgba": (_png(20, 10, lambda x, y: (*ACCENT, 255), ctype=6), visual.to_hex(ACCENT)),
        }
        for name, (data, expected) in cases.items():
            with self.subTest(name), TempImage(data) as path:
                facts = visual.image_facts(path)
                self.assertEqual(facts["status"], "read")
                self.assertEqual(facts["palette"][0]["hex"], expected)

    def test_a_16bit_grayscale_capture_does_not_refute_the_color_it_contains(self):
        """The decode bug's real cost, asserted where it was paid rather than where it happened.

        `image_palette` is D0, `confidence: extracted`, and skips fp-check — so a fabricated palette
        is not second-guessed by anything downstream. A white 16-bit grayscale that decodes to
        `#010101` does not merely report a wrong fact; it makes the picture *refute* a correct claim
        (`verdict: absent`, ΔE 99.7), which is the one output a caller reads to decide it may not
        propagate the palette.
        """
        with TempImage(_png(20, 10, lambda x, y: (0xFF,), ctype=0, depth=16)) as path:
            out = visual.verify_palette(path, ["#ffffff"])
        self.assertFalse(out["refuted"])
        self.assertEqual(out["claims"][0]["verdict"], "present")
        self.assertEqual(out["claims"][0]["delta_e"], 0.0)

    def test_a_fully_transparent_region_contributes_no_color(self):
        """A transparent area of a mockup export is not a background decision. Compositing it over
        an assumed white would invent a color the author never chose."""
        def px(x, y):
            return (*ACCENT, 255) if x < 5 else (0xFF, 0xFF, 0xFF, 0)
        with TempImage(_png(50, 10, px, ctype=6)) as path:
            facts = visual.image_facts(path)
        self.assertEqual([e["hex"] for e in facts["palette"]], [visual.to_hex(ACCENT)])
        self.assertEqual(facts["palette"][0]["coverage"], 1.0)


class TestPalette(unittest.TestCase):
    def test_coverage_is_a_population_statistic_not_a_presence_flag(self):
        """The accent covers 30x10 of 200x100 — 1.5%. Reporting presence without the fraction is
        what lets a stray artifact read like a brand color."""
        with TempImage(_button_screenshot()) as path:
            facts = visual.image_facts(path)
        by_hex = {e["hex"]: e["coverage"] for e in facts["palette"]}
        self.assertAlmostEqual(by_hex[visual.to_hex(ACCENT)], 0.015, places=3)
        self.assertAlmostEqual(by_hex[visual.to_hex(BG)], 0.985, places=3)

    def test_the_palette_is_ordered_by_coverage(self):
        with TempImage(_button_screenshot()) as path:
            palette = visual.image_facts(path)["palette"]
        self.assertEqual([e["coverage"] for e in palette],
                         sorted((e["coverage"] for e in palette), reverse=True))


class TestVerify(unittest.TestCase):
    def test_a_color_in_the_picture_is_present_and_one_that_is_not_is_absent(self):
        with TempImage(_button_screenshot()) as path:
            out = visual.verify_palette(path, {"surface": "#faf9f7", "accent": "#2563EB",
                                               "invented": "#ff00ff"})
        verdicts = {c["name"]: c["verdict"] for c in out["claims"]}
        self.assertEqual(verdicts, {"surface": "present", "accent": "present",
                                    "invented": "absent"})
        self.assertTrue(out["refuted"])
        self.assertEqual(out["absent"], ["#ff00ff"])

    def test_an_absent_claim_reports_the_nearest_color_that_IS_there(self):
        """A refutation nobody can act on gets ignored. The nearest real color plus the distance is
        what turns 'not in the image' into a next step."""
        with TempImage(_button_screenshot()) as path:
            claim = visual.verify_palette(path, ["#ff00ff"])["claims"][0]
        self.assertIn(claim["nearest_in_image"], (visual.to_hex(BG), visual.to_hex(ACCENT)))
        self.assertGreater(claim["delta_e"], visual.DELTA_E_TOLERANCE)

    def test_anti_aliasing_counts_toward_the_claim_rather_than_against_it(self):
        """The whole reason membership is asked in Lab with a radius: a solid fill in a real capture
        arrives as a cloud of near-shades, and exact equality would refute the color that is there."""
        def px(x, y):
            jitter = (x * 7 + y * 3) % 5 - 2                    # +/-2 per channel, as AA produces
            return tuple(max(0, min(255, c + jitter)) for c in ACCENT)
        with TempImage(_png(60, 40, px)) as path:
            out = visual.verify_palette(path, ["#2563eb"])
        self.assertEqual(out["claims"][0]["verdict"], "present")
        self.assertGreater(out["claims"][0]["coverage"], 0.9)

    def test_a_dtcg_style_name_map_keeps_the_names_in_the_verdict(self):
        with TempImage(_button_screenshot()) as path:
            out = visual.verify_palette(path, {"color.brand.primary": "#2563eb"})
        self.assertEqual(out["claims"][0]["name"], "color.brand.primary")

    def test_an_unparseable_claim_is_reported_not_dropped(self):
        with TempImage(_button_screenshot()) as path:
            out = visual.verify_palette(path, ["rebeccapurple"])
        self.assertEqual(out["claims"][0]["verdict"], "unparsed")

    def test_a_claim_that_is_not_even_a_string_takes_the_same_unparsed_path(self):
        """The claim set is a model's JSON arriving through an MCP tool whose schema is `list |
        None`, so nothing upstream constrains the element type. `{"name": "primary"}` with the value
        under a key nobody aliased normalizes to `None`, and `None.strip()` raised an
        `AttributeError` **out of the tool** — a hard fail in the module whose stated contract is
        *degrades, never hard-fails*, on the branch that already had the right answer one line away.
        """
        with TempImage(_button_screenshot()) as path:
            out = visual.verify_palette(path, {"a": None, "b": 123, "c": ["#fff"], "d": "#faf9f7"})
        verdicts = {c["name"]: c["verdict"] for c in out["claims"]}
        self.assertEqual(verdicts, {"a": "unparsed", "b": "unparsed", "c": "unparsed",
                                    "d": "present"})


class TestColorMath(unittest.TestCase):
    def test_wcag_contrast_matches_the_published_extremes(self):
        self.assertAlmostEqual(visual.contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)
        self.assertAlmostEqual(visual.contrast_ratio((255, 255, 255), (255, 255, 255)), 1.0,
                               places=6)

    def test_grades_land_on_the_right_side_of_each_criterion(self):
        graded = visual.check_contrast([
            {"label": "body", "fg": "#111827", "bg": "#faf9f7"},
            {"label": "muted", "fg": "#9ca3af", "bg": "#faf9f7"},
        ])
        self.assertTrue(graded[0]["passes_aa_normal"])
        self.assertEqual(graded[0]["normal_text"], "AAA")
        self.assertFalse(graded[1]["passes_aa_normal"])
        self.assertEqual(graded[1]["normal_text"], "fail")

    def test_hex_forms_all_parse_to_the_same_color(self):
        for form in ("#2563eb", "2563EB", "#2563ebff"):
            self.assertEqual(visual.parse_hex(form), ACCENT)
        self.assertEqual(visual.parse_hex("#fff"), (255, 255, 255))

    def test_identical_colors_are_zero_apart_and_opposites_are_far(self):
        self.assertAlmostEqual(visual.delta_e(visual.to_lab(INK), visual.to_lab(INK)), 0.0)
        self.assertGreater(visual.delta_e(visual.to_lab((0, 0, 0)), visual.to_lab((255, 255, 255))),
                           visual.DELTA_E_TOLERANCE)


class TestDegradation(unittest.TestCase):
    """The contract that fails silently if it is wrong: not-looked-at must never read as clean."""

    def test_an_unreadable_image_is_unchecked_with_a_reason_not_an_empty_palette(self):
        with TempImage(b"GIF89a not really an image", suffix=".gif") as path:
            facts = visual.image_facts(path)
        self.assertEqual(facts["status"], "unchecked")
        self.assertTrue(facts["reason"])
        self.assertNotIn("palette", facts)

    def test_verify_on_an_unreadable_image_marks_every_claim_unchecked(self):
        with TempImage(b"\x00\x01\x02", suffix=".webp") as path:
            out = visual.verify_palette(path, ["#2563eb", "#ffffff"])
        self.assertEqual(out["status"], "unchecked")
        self.assertEqual([c["verdict"] for c in out["claims"]], ["unchecked", "unchecked"])
        self.assertNotIn("refuted", out)

    def test_an_empty_claim_set_is_unchecked_rather_than_a_clean_bill(self):
        """The other way of examining nothing, and the one that answered wrongly.

        With no claims the verdict loop ran zero times and the result was `status: "checked"`,
        `absent: []`, `refuted: false` — a pass issued by a check that inspected no color. It is
        reachable with no mistake on the caller's part (`palette_verify(image)` before any color has
        been proposed; a DTCG contract whose color group is empty), and `refuted` is precisely the
        field a caller reads to decide the palette may be propagated into tokens.css and everything
        generated from it.
        """
        with TempImage(_button_screenshot()) as path:
            for empty in ([], {}):
                with self.subTest(claimed=empty):
                    out = visual.verify_palette(path, empty)
                    self.assertEqual(out["status"], "unchecked")
                    self.assertEqual(out["claims"], [])
                    self.assertNotIn("refuted", out,
                                     "a check of nothing may not report itself unrefuted")
                    self.assertIn("claimed", out["reason"])

    def test_the_readable_image_does_not_rescue_an_empty_claim_set(self):
        """Ordering, asserted rather than assumed: the claim set is checked BEFORE the pixels,
        because no image makes an empty claim set checkable. Reading first would have produced
        `status: "checked"` on a perfectly good screenshot, which is the vacuous pass again."""
        with TempImage(_button_screenshot()) as path:
            self.assertEqual(visual.image_facts(path)["status"], "read")
            self.assertEqual(visual.verify_palette(path, [])["status"], "unchecked")

    def test_the_coverage_floor_override_reaches_the_verdict(self):
        """The parameter existed and nothing could pass it. It decides `present` vs `absent`, so a
        floor above the accent's own coverage must flip that claim — which is what makes the
        override real rather than accepted-and-ignored."""
        with TempImage(_button_screenshot()) as path:
            accent = visual.to_hex(ACCENT)
            default = visual.verify_palette(path, [accent])
            raised = visual.verify_palette(path, [accent], coverage_floor=0.5)
        self.assertEqual(default["claims"][0]["verdict"], "present")
        self.assertEqual(raised["claims"][0]["verdict"], "absent")
        self.assertEqual(raised["coverage_floor"], 0.5)

    def test_a_missing_file_says_so(self):
        facts = visual.image_facts("/nonexistent/never-captured.png")
        self.assertEqual(facts["status"], "unchecked")
        self.assertIn("no such image", facts["reason"])

    def test_an_interlaced_png_is_refused_rather_than_decoded_wrongly(self):
        """Adam7 is not decoded here. Reading it as progressive would produce a plausible palette
        from scrambled pixels, which is worse than the gap."""
        data = bytearray(_png(20, 10, lambda x, y: ACCENT))
        data[28] = 1                                            # IHDR interlace byte
        data[29:33] = struct.pack(">I", zlib.crc32(bytes(data[12:29])) & 0xFFFFFFFF)
        with TempImage(bytes(data)) as path:
            facts = visual.image_facts(path)
        self.assertEqual(facts["status"], "unchecked")
        self.assertIn("interlaced", facts["reason"])

    def test_a_truncated_capture_does_not_raise_out_of_the_tool(self):
        good = _png(40, 20, lambda x, y: ACCENT)
        with TempImage(good[:len(good) // 2]) as path:
            facts = visual.image_facts(path)
        self.assertEqual(facts["status"], "unchecked")


class TestSamplingCeiling(unittest.TestCase):
    def test_a_large_image_is_subsampled_to_the_declared_ceiling(self):
        """`MAX_SAMPLES` is a declared hypothesis, so the code must actually honour it — an
        unenforced ceiling is a comment, and the decode cost it exists to bound is real."""
        side = 900                                              # 810_000 px > MAX_SAMPLES
        with TempImage(_png(side, side, lambda x, y: BG)) as path:
            facts = visual.image_facts(path)
        self.assertLessEqual(facts["sampled_pixels"], visual.MAX_SAMPLES)
        self.assertEqual(facts["palette"][0]["hex"], visual.to_hex(BG))


if __name__ == "__main__":
    unittest.main()
