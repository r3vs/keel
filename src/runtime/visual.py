"""Reference-image evidence — the deterministic half of "build me this screenshot".

A screenshot handed to a coding agent is **evidence, not a specification**, and the single most
expensive mistake a screenshot-to-code tool makes is to erase that difference: the model reads a
picture, states a palette, a grid and a component tree with total confidence, and everything it
guessed becomes code nobody elected. This module exists to split that act in two, along the line
this package splits every other act — **what is computed from the pixels, and what a model inferred
about them**:

- **Computed here (D0, `confidence: extracted`, skips fp-check).** The image's real geometry and its
  real color histogram: which colors actually occur, and over what fraction of the image. A claimed
  token either occurs in the picture or it does not, and that is set membership over decoded pixels,
  not a judgment. WCAG contrast of a *claimed* pair is likewise arithmetic on the two values.
- **Not here, and deliberately (D2, a vetoable pin).** Everything semantic — that a band of pixels is
  a nav bar, that `#2563EB` *means* primary-action, that the layout is a 12-column grid. A model
  infers all of it, so it goes to the ledger as an inference under `provenance: agent_assumption`
  (`core/assumptions.md`), never as a fact this module blessed.

The load-bearing consequence is that the model's palette gets **fact-checked before a line of CSS is
generated**. `verify_palette` takes the DTCG colors the model proposes and asks the picture whether
they are in it. A claimed accent that occupies no pixels is a hallucinated token — caught at the
contract, where fixing it costs one pin, instead of after it has been propagated into `tokens.css`,
a Tailwind theme, a DESIGN.md and every component built against them.

**Perceptual distance, because exact equality is the wrong question.** A screenshot is
anti-aliased, often JPEG-degraded, sometimes color-managed: the button that renders `#2563EB` leaves
thousands of neighbouring shades and possibly not one exact hit. So membership is asked in CIE Lab
with a ΔE radius (CIE76 — the simple one, and the choice is deliberate: its known weakness is
saturated-color *ordering*, while what is asked here is a coarse "same color or not" at a radius an
order of magnitude above the JND, where CIE76 and ΔE2000 agree). Coverage is summed over every
histogram bucket inside that radius, so anti-aliasing counts toward the claim rather than against it.

**Degrades, never hard-fails.** PNG is decoded here, in the stdlib, because it is what a screen
capture produces on every platform this package targets. Anything else (JPEG, WebP, HEIC, a video
frame) is converted through whichever of ImageMagick / sips / ffmpeg is on PATH, and when none is,
the answer is `unchecked` with the reason — a palette that could not be read is *not looked at*, never
a clean bill. That is the same rule `design.py` applies when Impeccable is absent and
`treesitter_extract.py` applies when a grammar is: the gap is reported as a gap.

**No model, no network, no third-party code.** The PNG decoder is the format spec (RFC 2083 /
W3C PNG) implemented against zlib; the color math is CIE and WCAG 2.x, both published formulae. The
prior art this capability answers to — `abi/screenshot-to-code` (MIT) — is a *generator*: image in,
HTML out. Nothing of its code is used or needed here; what is adapted is the problem statement, and
what is added is the half it does not have, which is a check.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Optional

# HYPOTHESIS: at most this many pixels are sampled into the histogram. A screenshot's palette is a
# population statistic, and a uniform stride over a 4K capture reaches this many samples while
# reading every region of the image; going higher costs seconds of pure-Python decode for digits
# that do not change a coverage verdict. Lower it and a 1%-coverage accent starts to alias in and
# out of the sample.
MAX_SAMPLES = 400_000

# HYPOTHESIS: histogram bucket width per 8-bit channel. 8 collapses the anti-aliasing halo and the
# JPEG ringing around a solid fill into few enough buckets to sum, while keeping 32 levels per
# channel — far finer than the ΔE radius that actually decides membership, so the bucketing never
# decides a verdict the distance metric would not.
QUANT = 8

# HYPOTHESIS: how many palette entries `image_facts` reports. Enough to cover a background, a
# surface, a text color, a border and two or three accents — the shape of a real UI palette — without
# turning the report into a histogram dump the agent has to summarize.
TOP_COLORS = 12

# HYPOTHESIS: the ΔE76 radius inside which a claimed color counts as occurring in the image. The
# just-noticeable difference is ~2.3; this is deliberately several times that, because the claim
# being checked is "this color is in the picture", not "this color is reproduced exactly" — the
# picture may be a lossy re-encode of the design. Tightening it toward the JND turns every
# screenshot compression artifact into a refuted token.
DELTA_E_TOLERANCE = 12.0

# HYPOTHESIS: the fraction of sampled pixels a claimed color must cover to count as present. A
# primary action button on a desktop screenshot is well under one percent of it, so this floor is
# about excluding stray artifacts, not about prominence — prominence is reported as the coverage
# number and weighed by a human, never thresholded into a verdict here.
COVERAGE_FLOOR = 0.0005

# HYPOTHESIS: alpha below this is treated as carrying no color evidence and is dropped from the
# histogram. A fully transparent region of a mockup export is not a color decision; compositing it
# over an assumed white would invent a background the author never chose.
ALPHA_FLOOR = 16

_SIG = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}   # PNG color type -> samples per pixel

#: Format converters, in preference order. Each is `(binary, argv template)`; the first one on PATH
#: wins. ImageMagick 7 renamed `convert` to `magick`, so both are named — a host that has only the
#: older one is not a host without ImageMagick.
_CONVERTERS = (
    ("magick", ["magick", "{src}", "png:{dst}"]),
    ("convert", ["convert", "{src}", "png:{dst}"]),
    ("sips", ["sips", "-s", "format", "png", "{src}", "--out", "{dst}"]),
    ("ffmpeg", ["ffmpeg", "-y", "-loglevel", "error", "-i", "{src}", "{dst}"]),
)


class ImageUnreadable(Exception):
    """The pixels could not be reached. Carries the reason, which is reported, never swallowed."""


# --- PNG decode (RFC 2083 / W3C PNG, against zlib) --------------------------------------------

def _chunks(data: bytes):
    pos = len(_SIG)
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        yield ctype, data[pos + 8:pos + 8 + length]
        pos += 12 + length


def _unfilter(raw: bytes, height: int, bpp: int, stride: int) -> bytearray:
    """Reverse the five PNG scanline filters. Every row depends on the one above it, which is why
    the decode cannot be decimated — the sampling stride is applied afterwards, on pixels."""
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        if pos + 1 + stride > len(raw):
            raise ImageUnreadable("PNG image data ends mid-scanline")
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ImageUnreadable(f"unknown PNG filter type {ft}")
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def _expand_bits(row: bytes, depth: int, count: int) -> list:
    """Sub-byte sample depths (1/2/4), most-significant bits first, as the spec packs them."""
    per_byte, mask = 8 // depth, (1 << depth) - 1
    out = []
    for byte in row:
        for k in range(per_byte):
            out.append((byte >> (8 - depth * (k + 1))) & mask)
            if len(out) == count:
                return out
    return out


def decode_png(data: bytes) -> tuple:
    """`(width, height, samples)` where `samples` is a list of `(r, g, b)` at most `MAX_SAMPLES`
    long, taken on a uniform stride. Raises `ImageUnreadable` for anything not decodable here."""
    if not data.startswith(_SIG):
        raise ImageUnreadable("not a PNG (signature mismatch)")
    header, palette, trns, idat = None, b"", b"", bytearray()
    for ctype, body in _chunks(data):
        if ctype == b"IHDR":
            header = struct.unpack(">IIBBBBB", body[:13])
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"tRNS":
            trns = body
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
    if header is None:
        raise ImageUnreadable("PNG has no IHDR chunk")
    width, height, depth, ctype_n, comp, filt, interlace = header
    if interlace:
        raise ImageUnreadable("interlaced (Adam7) PNG — not decoded here")
    if comp != 0 or filt != 0:
        raise ImageUnreadable(f"unsupported PNG compression/filter method ({comp}/{filt})")
    if ctype_n not in _CHANNELS:
        raise ImageUnreadable(f"unknown PNG color type {ctype_n}")
    if not width or not height:
        raise ImageUnreadable("PNG declares a zero dimension")

    channels = _CHANNELS[ctype_n]
    stride = (width * channels * depth + 7) // 8
    bpp = max(1, (channels * depth) // 8)
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:                                   # truncated or corrupt capture
        raise ImageUnreadable(f"PNG image data will not inflate: {exc}")
    flat = _unfilter(raw, height, bpp, stride)

    total = width * height
    # Ceiling division, and the distinction is not pedantic: flooring picks a stride that leaves up
    # to twice `MAX_SAMPLES` samples, so the declared ceiling would be a comment rather than a bound.
    step = max(1, -(-total // MAX_SAMPLES))
    alpha_index = {4: 1, 6: 3}.get(ctype_n)
    scale = 1 if depth == 8 else (255 / ((1 << depth) - 1))
    samples = []
    for idx in range(0, total, step):
        y, x = divmod(idx, width)
        row = flat[y * stride:(y + 1) * stride]
        if depth < 8:
            vals = _expand_bits(row, depth, width * channels)
            px = vals[x * channels:(x + 1) * channels]
        elif depth == 16:
            base = x * channels * 2
            px = [row[base + 2 * c] for c in range(channels)]   # high byte: 16 -> 8 bit
        else:
            base = x * channels
            px = list(row[base:base + channels])
        if not px:
            continue
        if ctype_n == 3:
            i = px[0]
            if i * 3 + 2 >= len(palette):
                continue
            if i < len(trns) and trns[i] < ALPHA_FLOOR:
                continue
            samples.append((palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2]))
            continue
        if alpha_index is not None and px[alpha_index] < ALPHA_FLOOR:
            continue
        if ctype_n in (0, 4):
            g = round(px[0] * scale) if depth != 8 else px[0]
            samples.append((g, g, g))
        else:
            if depth in (1, 2, 4):
                px = [round(v * scale) for v in px]
            samples.append((px[0], px[1], px[2]))
    return width, height, samples


def _to_png(path: Path) -> bytes:
    """PNG bytes for `path`, converting through the first available external tool when it is not
    already a PNG. Raises `ImageUnreadable` naming the tools it looked for."""
    data = path.read_bytes()
    if data.startswith(_SIG):
        return data
    for binary, argv in _CONVERTERS:
        if not shutil.which(binary):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "converted.png"
            cmd = [a.format(src=str(path), dst=str(dst)) for a in argv]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            except (subprocess.SubprocessError, OSError):
                continue
            if dst.exists() and dst.stat().st_size:
                out = dst.read_bytes()
                if out.startswith(_SIG):
                    return out
    names = ", ".join(b for b, _ in _CONVERTERS)
    raise ImageUnreadable(
        f"{path.suffix or 'this file'} is not a PNG and no converter is on PATH (looked for: "
        f"{names}) — the palette is unchecked, which is not the same as clean")


# --- color math (CIE Lab / ΔE76, WCAG 2.x relative luminance) ---------------------------------

def parse_hex(value: str) -> tuple:
    """`#rgb` / `#rrggbb` (with or without `#`) -> `(r, g, b)`. Raises ValueError otherwise."""
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 8:                        # #rrggbbaa — alpha is not a color claim
        s = s[:6]
    if len(s) != 6:
        raise ValueError(f"not a hex color: {value!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _linear(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_lab(rgb) -> tuple:
    """sRGB -> CIE L*a*b* under D65, the standard two-step through XYZ."""
    r, g, b = (_linear(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(lab_a, lab_b) -> float:
    """CIE76 — Euclidean distance in Lab. See the module docstring for why the simple one."""
    return sum((a - b) ** 2 for a, b in zip(lab_a, lab_b)) ** 0.5


def relative_luminance(rgb) -> float:
    r, g, b = (_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg) -> float:
    """WCAG 2.x contrast ratio, 1.0 … 21.0. Arithmetic on two values — a fact, not a judgment."""
    a, b = relative_luminance(fg), relative_luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


#: WCAG 2.x success criteria, as published. Not tuned here, so not hypotheses: 1.4.3 (AA) and 1.4.6
#: (AAA), each with its normal-text and large-text floor.
WCAG_FLOORS = (("AAA", 7.0, 4.5), ("AA", 4.5, 3.0))


def wcag_grade(ratio: float) -> dict:
    """The highest criterion a ratio meets, for normal and for large text."""
    normal = next((name for name, n, _ in WCAG_FLOORS if ratio >= n), "fail")
    large = next((name for name, _, l in WCAG_FLOORS if ratio >= l), "fail")
    return {"ratio": round(ratio, 2), "normal_text": normal, "large_text": large}


# --- the histogram, and the two questions asked of it ------------------------------------------

def _histogram(samples) -> dict:
    """Quantized color -> count. The bucket is `QUANT`-wide per channel; the reported color is the
    bucket's own mean, so an entry names a color that is actually in the image rather than a
    lattice point near it."""
    buckets: dict = {}
    for r, g, b in samples:
        key = (r // QUANT, g // QUANT, b // QUANT)
        acc = buckets.get(key)
        if acc is None:
            buckets[key] = [1, r, g, b]
        else:
            acc[0] += 1
            acc[1] += r
            acc[2] += g
            acc[3] += b
    return buckets


def _entries(buckets: dict, total: int) -> list:
    out = []
    for count, sr, sg, sb in buckets.values():
        rgb = (sr / count, sg / count, sb / count)
        out.append({"hex": to_hex(rgb), "rgb": tuple(int(round(c)) for c in rgb),
                    "coverage": count / total, "lab": to_lab(rgb)})
    out.sort(key=lambda e: -e["coverage"])
    return out


def read_image(path) -> dict:
    """Decode + histogram, or raise `ImageUnreadable`. The one place pixels are touched."""
    p = Path(path)
    if not p.exists():
        raise ImageUnreadable(f"no such image: {p}")
    width, height, samples = decode_png(_to_png(p))
    if not samples:
        raise ImageUnreadable("every sampled pixel was transparent — no color evidence")
    return {"width": width, "height": height, "sampled": len(samples),
            "entries": _entries(_histogram(samples), len(samples))}


def image_facts(path) -> dict:
    """What the picture is, computed. Never what the picture *means*.

    On success: `status: "read"`, the pixel dimensions, and the dominant palette with each entry's
    coverage. On failure: `status: "unchecked"` and the reason — the coverage-gap discipline, so a
    caller can never mistake "not looked at" for "nothing there"."""
    try:
        img = read_image(path)
    except ImageUnreadable as exc:
        return {"status": "unchecked", "reason": str(exc), "source": str(path)}
    palette = [{k: (round(v, 5) if k == "coverage" else v)
                for k, v in e.items() if k != "lab"} for e in img["entries"][:TOP_COLORS]]
    return {"status": "read", "source": str(path),
            "width": img["width"], "height": img["height"],
            "sampled_pixels": img["sampled"], "distinct_colors": len(img["entries"]),
            "palette": palette}


def verify_palette(path, claimed, tolerance: Optional[float] = None,
                   coverage_floor: Optional[float] = None) -> dict:
    """Fact-check proposed colors against the image they claim to come from.

    `claimed` is either a list of hex strings or a `{name: hex}` mapping (a DTCG color group,
    flattened). For each claim, coverage is summed over every histogram bucket within `tolerance`
    ΔE — so anti-aliasing and lossy re-encoding count *toward* the claim. A claim under the coverage
    floor comes back `absent`: it is a color the model produced that the picture does not contain,
    which is a refutation to raise before the token is propagated anywhere.
    """
    tol = DELTA_E_TOLERANCE if tolerance is None else float(tolerance)
    floor = COVERAGE_FLOOR if coverage_floor is None else float(coverage_floor)
    pairs = list(claimed.items()) if isinstance(claimed, dict) else [(None, c) for c in claimed]
    try:
        img = read_image(path)
    except ImageUnreadable as exc:
        return {"status": "unchecked", "reason": str(exc), "source": str(path),
                "claims": [{"name": n, "claimed": c, "verdict": "unchecked"} for n, c in pairs]}

    entries = img["entries"]
    results = []
    for name, value in pairs:
        try:
            rgb = parse_hex(value)
        except ValueError as exc:
            results.append({"name": name, "claimed": value, "verdict": "unparsed",
                            "reason": str(exc)})
            continue
        lab = to_lab(rgb)
        coverage, nearest, best = 0.0, None, None
        for e in entries:
            d = delta_e(lab, e["lab"])
            if best is None or d < best:
                best, nearest = d, e["hex"]
            if d <= tol:
                coverage += e["coverage"]
        results.append({
            "name": name, "claimed": to_hex(rgb),
            "verdict": "present" if coverage >= floor else "absent",
            "coverage": round(coverage, 5),
            "nearest_in_image": nearest, "delta_e": round(best, 2) if best is not None else None,
        })
    absent = [r for r in results if r["verdict"] == "absent"]
    return {"status": "checked", "source": str(path),
            "tolerance_delta_e": tol, "coverage_floor": floor,
            "claims": results, "absent": [r["claimed"] for r in absent],
            "refuted": bool(absent)}


def check_contrast(pairs) -> list:
    """WCAG grade for each `(foreground, background)` hex pair — the claimed contract, before any
    code exists to scan. `design_scan` covers the rendered result; nothing else covers this moment."""
    out = []
    for item in pairs:
        fg, bg = (item.get("fg"), item.get("bg")) if isinstance(item, dict) else tuple(item)[:2]
        try:
            grade = wcag_grade(contrast_ratio(parse_hex(fg), parse_hex(bg)))
        except ValueError as exc:
            out.append({"fg": fg, "bg": bg, "verdict": "unparsed", "reason": str(exc)})
            continue
        label = item.get("label") if isinstance(item, dict) else None
        out.append({"label": label, "fg": fg, "bg": bg, **grade,
                    "passes_aa_normal": grade["normal_text"] in ("AA", "AAA")})
    return out
