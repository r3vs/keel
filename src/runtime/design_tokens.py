"""Design-token contract runtime — generate every design layer from one DTCG contract.

The **design analog of `runtime/generate.py`**. Where generate.py takes a data contract and emits
DB / ORM / API / client layers, this takes a **W3C Design Tokens (DTCG) contract** — the stable,
multi-vendor token standard (Format Module 2025.10) — and emits the aligned design layers a UI is
built from: CSS custom properties, a Tailwind v4 `@theme` block, and a `DESIGN.md` (Google's Stitch
format) whose frontmatter Impeccable's detector enforces token-membership against. One source of
truth; every layer a projection of it, so they cannot drift.

**Why DTCG, not DESIGN.md frontmatter, as the machine contract.** DTCG is a stable, externally
governed, 40+ vendor standard (Figma / Style Dictionary / Terrazzo / Tokens Studio / Penpot).
DESIGN.md's own frontmatter is a single-vendor **alpha** spec (Google Stitch) that already has an
incompatible fork (Open Design's prose-only dialect). The deterministic, non-drifting carrier is the
tokens; DESIGN.md is generated FROM them — exactly as Google's own `@google/design.md` CLI exports
DTCG — never authored as the primary machine artifact.

**Proof of alignment is mechanical**, like generate.py: generate the CSS layer, re-extract its
variables, diff against the DTCG source — a correct generator round-trips to **zero drift**. That
round-trip is the design twin of `contract_diff`, and it is what the CI drift-check runs.

**Scope of this floor.** Stdlib-only; the web targets (CSS variables, Tailwind v4, DESIGN.md
frontmatter), and the scalar token types a UI is styled from: `color`, `fontFamily`, and `dimension`
(radii / font-sizes / spacing). DTCG **composite** types (`typography` / `border` / `shadow`, whose
`$value` is an object) are **not projected** — they are skipped, never emitted as a broken CSS value;
handling them is additive. Style Dictionary / Terrazzo are the mature standard DTCG generators and add
more targets (iOS / Android / …); a project that uses one consumes the **same DTCG contract**, so they
are compatible with this floor, not replaced by it. This module **neither detects nor shells them** —
delegating to a present Style Dictionary would be an additive extension, not implemented here (do not
read this as a tree-sitter-style "prefer when present" code path; there is none).

**DTCG → DESIGN.md role mapping is read from the contract's own structure, never guessed.** A token's
`$type` decides most of it (`color` → `colors`, `fontFamily` → a typography family). The one genuine
ambiguity — a `dimension` is a radius, a font size, or spacing, and DTCG types them all `dimension` —
is resolved from the token's **top-level DTCG group** (the author put radii under `radius`), the same
way generate.py requires an explicit `table` rather than pluralizing an entity name. A dimension in an
unrecognized group is emitted to CSS only and surfaced, never force-fit into the DESIGN.md contract.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Optional

_BANNER = "GENERATED from the DTCG design contract by runtime/design_tokens.py — do not hand-edit."

# Top-level DTCG group names that declare a dimension's role (the contract author's own carrier).
_RADIUS_GROUPS = {"radius", "rounded", "radii", "corner", "cornerradius", "border-radius"}
_FONTSIZE_GROUPS = {"fontsize", "fontsizes", "font-size", "type", "typescale", "type-scale", "text"}


# ── DTCG parse (flatten + resolve aliases) ──────────────────────────────────

def _is_token(node) -> bool:
    return isinstance(node, dict) and "$value" in node


def _flatten(obj, prefix=(), inherited_type: Optional[str] = None) -> list:
    """Walk a DTCG token tree → flat tokens. A node with `$value` is a token; `$type` is inherited
    from the nearest enclosing group that declares it (DTCG type-inheritance)."""
    out = []
    if not isinstance(obj, dict):
        return out
    group_type = obj.get("$type", inherited_type)
    if _is_token(obj):
        out.append({
            "path": ".".join(prefix),
            "type": obj.get("$type", inherited_type),
            "value": obj["$value"],
            "description": obj.get("$description", ""),
        })
        return out
    for key, child in obj.items():
        if key.startswith("$"):
            continue
        out.extend(_flatten(child, prefix + (key,), group_type))
    return out


_ALIAS_RE = re.compile(r"^\{([^}]+)\}$")


def _resolve(tokens: list) -> list:
    """Resolve DTCG scalar aliases (`{group.token}` → the referenced value), with a cycle guard.
    A reference to a missing/cyclic token is left as-is (surfaced, never silently blanked)."""
    by_path = {t["path"]: t for t in tokens}

    def deref(path, seen):
        tok = by_path.get(path)
        if tok is None:
            return None
        val = tok["value"]
        m = _ALIAS_RE.match(val) if isinstance(val, str) else None
        if not m:
            return val
        ref = m.group(1)
        if ref in seen:                       # cycle → leave the literal alias, do not loop
            return val
        r = deref(ref, seen | {path})
        return r if r is not None else val

    return [{**t, "value": deref(t["path"], set())} for t in tokens]


class TokenSet:
    """A resolved DTCG contract: a flat list of `{path, type, value, description}` tokens."""

    def __init__(self, tokens: list):
        self.tokens = tokens

    @classmethod
    def from_obj(cls, obj: dict) -> "TokenSet":
        return cls(_resolve(_flatten(obj)))

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "TokenSet":
        return cls.from_obj(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))

    def of_type(self, *types: str) -> list:
        return [t for t in self.tokens if t["type"] in types]


# ── value formatting ────────────────────────────────────────────────────────

def _fmt_value(tok: dict) -> str:
    """A token's value as a CSS-ready string. fontFamily lists join into a stack; everything else is
    its literal (color hex/oklch, dimension `16px`, number). Non-scalar composites are JSON-dumped so
    nothing is silently dropped."""
    v = tok["value"]
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, (str, int, float)):
        return str(v)
    return json.dumps(v)


def _kebab(path: str) -> str:
    """DTCG dot path → a kebab CSS-variable stem: `color.primaryText` → `color-primary-text`."""
    s = path.replace(".", "-")
    s = re.sub(r"(?<!^)(?=[A-Z])", "-", s).lower()
    return re.sub(r"[^a-z0-9-]+", "-", s).strip("-")


def _top_group(path: str) -> str:
    return path.split(".", 1)[0].lower() if path else ""


def _leaf(path: str) -> str:
    return path.rsplit(".", 1)[-1] if path else path


def _scalar_tokens(ts: "TokenSet") -> list:
    """Tokens whose value is a single CSS-emittable scalar (string / number / a fontFamily list) —
    NOT a DTCG composite (`typography` / `border` / `shadow`, whose `$value` is an object). A composite
    cannot be one `--var: value;`, so the web generators skip it rather than emit invalid CSS."""
    return [t for t in ts.tokens if not isinstance(t["value"], dict)]


# ── generators (one DTCG contract → each design layer) ──────────────────────

def to_css_vars(ts: TokenSet, selector: str = ":root") -> str:
    """DTCG → CSS custom properties. The exact, lossless projection — every token becomes one
    `--<kebab-path>` variable; this is the layer the drift-check round-trips against."""
    lines = [f"/* {_BANNER} */", f"{selector} {{"]
    for t in _scalar_tokens(ts):
        lines.append(f"  --{_kebab(t['path'])}: {_fmt_value(t)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_tailwind(ts: TokenSet) -> str:
    """DTCG → Tailwind v4 `@theme` block. v4 reads design tokens straight from CSS variables under
    `@theme`, so this is the same projection as `to_css_vars` in Tailwind's namespaced form
    (`--color-*`, `--font-*`, `--radius-*`, `--text-*`) — token names Tailwind turns into utilities."""
    lines = [f"/* {_BANNER} */", "@theme {"]
    for t in _scalar_tokens(ts):
        lines.append(f"  --{_tw_name(t)}: {_fmt_value(t)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _tw_name(tok: dict) -> str:
    """Tailwind v4 theme-namespace name for a token (drives which utilities are generated)."""
    stem = _kebab(tok["path"])
    typ, group = tok["type"], _top_group(tok["path"])
    if typ == "color":
        return stem if stem.startswith("color-") else f"color-{_kebab(_leaf(tok['path']))}"
    if typ == "fontFamily":
        return f"font-{_kebab(_leaf(tok['path']))}"
    if typ == "dimension" and group in _RADIUS_GROUPS:
        return f"radius-{_kebab(_leaf(tok['path']))}"
    if typ == "dimension" and group in _FONTSIZE_GROUPS:
        return f"text-{_kebab(_leaf(tok['path']))}"
    return stem


def _yaml_scalar(v: str) -> str:
    """Quote a frontmatter scalar when it contains YAML-significant characters (a font stack has
    commas; oklch()/rgb() have parens/colons). Impeccable's frontmatter parser reads quoted scalars."""
    s = _fmt_value({"value": v}) if not isinstance(v, str) else v
    return f'"{s}"' if re.search(r"[,:#(){}\[\]]", s) else s


def to_design_md(ts: TokenSet) -> str:
    """DTCG → a `DESIGN.md` (Google Stitch format) Impeccable enforces membership against.

    Only the three surfaces Impeccable's detector reads are populated from typed tokens: `colors`
    (every `color` token), `typography` (each `fontFamily` token → a role; each font-size `dimension`
    → a `scale` step), and `rounded` (each radius `dimension`). The role/scale/radius split is read
    from `$type` + top-level group (see module docstring), never guessed. A dimension in an
    unrecognized group is intentionally NOT projected here (it lives in CSS only) rather than
    misfiled into the contract."""
    colors, families, scale, rounded = {}, {}, {}, {}
    for t in ts.tokens:
        typ, group, leaf = t["type"], _top_group(t["path"]), _leaf(t["path"])
        if typ == "color":
            colors[leaf] = _fmt_value(t)
        elif typ == "fontFamily":
            families[leaf] = _fmt_value(t)
        elif typ == "dimension" and group in _RADIUS_GROUPS:
            rounded[leaf] = _fmt_value(t)
        elif typ == "dimension" and group in _FONTSIZE_GROUPS:
            scale[leaf] = _fmt_value(t)

    fm = ["---"]
    if families or scale:
        fm.append("typography:")
        for name, fam in families.items():
            fm.append(f"  {name}:")
            fm.append(f"    fontFamily: {_yaml_scalar(fam)}")
        if scale:
            fm.append("  scale:")
            for name, size in scale.items():
                fm.append(f"    {name}: {_yaml_scalar(size)}")
    if colors:
        fm.append("colors:")
        for name, val in colors.items():
            fm.append(f"  {name}: {_yaml_scalar(val)}")
    if rounded:
        fm.append("rounded:")
        for name, val in rounded.items():
            fm.append(f"  {name}: {_yaml_scalar(val)}")
    fm.append("---")
    body = [
        "",
        f"<!-- {_BANNER} The prose below is a scaffold; the frontmatter above is the enforced contract. -->",
        "",
        "## Overview",
        "This design system is generated from the project's DTCG token contract. The token values in",
        "the frontmatter are the single source of truth; Impeccable's detector fails any UI that uses a",
        "font, color, radius, or size outside them.",
        "",
        "## Colors", "## Typography", "## Rounded", "## Do's and Don'ts",
        "",
    ]
    return "\n".join(fm + body)


def generate_all(ts: TokenSet) -> dict:
    """Every design layer from the one contract — the design twin of generate.generate_all."""
    return {"css": to_css_vars(ts), "tailwind": to_tailwind(ts), "design_md": to_design_md(ts)}


# ── drift-check (re-extract + diff → zero on a correct generator) ───────────

_CSS_VAR_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")


def extract_css_vars(css: str) -> dict:
    """Re-extract `--var: value;` declarations from generated (or hand-edited) CSS. The inverse of
    to_css_vars, so a round-trip diffs to nothing."""
    return {m.group(1): m.group(2).strip() for m in _CSS_VAR_RE.finditer(css or "")}


_COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\))$")
_LEN_RE = re.compile(r"^-?[\d.]+(px|rem|em|%|vh|vw)$")


def _classify_type(value: str) -> Optional[str]:
    """The DTCG `$type` a declared value unambiguously IS — or None. A hex/rgb/hsl/oklch literal is a
    `color`, a px/rem/… literal is a `dimension`, a comma-separated stack with letters is a
    `fontFamily`. Anything else (a z-index, a raw number, a shadow, a gradient) is NOT classified —
    left out rather than guessed, per the no-heuristics rule (the value class is a fact; a guess is not)."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if _COLOR_RE.match(v):
        return "color"
    if _LEN_RE.match(v):
        return "dimension"
    if "," in v and re.search(r"[A-Za-z]", v):
        return "fontFamily"
    return None


def harvest_tokens(css: str) -> dict:
    """De-facto design tokens declared as CSS custom properties → a **candidate DTCG contract** (the
    as-is). Only values that are unambiguously a design token are harvested (see `_classify_type`);
    the value classification is a fact, ambiguous values are dropped, not guessed. This is a PROPOSED
    `to_be` for the interview to elect and refine — e.g. splitting the flat `dimension` group into
    radius / font-size / spacing, which the value alone cannot tell apart — never an enforced contract
    on its own. It is the design analog of extracting the as-is from code before the user elects the to-be."""
    buckets = {"color": ("color", {}), "font": ("fontFamily", {}), "dimension": ("dimension", {})}
    group_of = {"color": "color", "fontFamily": "font", "dimension": "dimension"}
    for name, value in extract_css_vars(css).items():
        typ = _classify_type(value)
        if typ is None:
            continue
        buckets[group_of[typ]][1][name] = {"$value": value.strip()}
    return {g: {"$type": gtype, **toks} for g, (gtype, toks) in buckets.items() if toks}


def drift_check(ts: TokenSet, css: str) -> dict:
    """Diff a CSS layer's variables against the DTCG contract. Every mismatch is a drift finding
    (`confidence: extracted` — a value comparison is a fact). Missing/extra/changed are all surfaced;
    a correct generated layer produces `{"drift": []}` (the executable alignment guarantee)."""
    want = {f"--{_kebab(t['path'])}": _fmt_value(t) for t in _scalar_tokens(ts)}
    have = {f"--{k}": v for k, v in extract_css_vars(css).items()}
    drift = []
    for var, val in want.items():
        if var not in have:
            drift.append({"var": var, "kind": "missing", "expected": val, "actual": None,
                          "confidence": "extracted"})
        elif have[var] != val:
            drift.append({"var": var, "kind": "changed", "expected": val, "actual": have[var],
                          "confidence": "extracted"})
    for var, val in have.items():
        if var not in want:
            drift.append({"var": var, "kind": "extra", "expected": None, "actual": val,
                          "confidence": "extracted"})
    return {"drift": drift}
