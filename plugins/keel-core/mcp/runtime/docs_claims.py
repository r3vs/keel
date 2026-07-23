"""Docs-as-claims — turn the target's own docs into checkable claims (study item C1).

The skill's own principle: you cannot audit slop against its own docs, because the found docs are
stale or aspirational. This module gives that principle a *deterministic* floor. It extracts the
**claims** a doc makes (headings, bullets) and the **code references** each claim names (backticked
identifiers, filenames), then resolves those references against the structural graph. A reference
the graph has no node for is a **dangling** claim — the doc names code that does not exist — which is
a candidate `contract_mismatch` / `internal_contradiction` pin: either the doc is stale (update it)
or the code is missing (build it), and the interview decides which.

Discipline (the whole point): this **never asserts** a defect. Dangling references become *candidate*
pins tagged `provenance: doc_claim`, `confidence: inferred` — the exact "surface it, don't decide it"
posture the assumptions doctrine requires. The deeper "does the code contradict what the claim says
it *does*" is a semantic judgment left to the agent; the runtime does only the checkable part.

Stdlib-only. Reuses `graph.Graph` for node names/files.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Optional

import graph as graphmod

_CODE_EXTS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".rb", ".php",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".kt", ".scala", ".swift", ".dart", ".sql", ".graphql",
})
_BACKTICK = re.compile(r"`([^`\n]+)`")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")


def _is_filename(tok: str) -> bool:
    return pathlib.PurePosixPath(tok).suffix.lower() in _CODE_EXTS


def _code_refs(text: str) -> dict:
    """Backticked code references in a line → {identifiers, files}. Only backticked spans count
    (the markdown convention for "this is code"), and only if they look like an identifier or a
    filename — so prose in backticks does not become a false reference."""
    idents, files = set(), set()
    for span in _BACKTICK.findall(text):
        span = span.strip()
        # a call like `getUser()` → the identifier
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*\(\s*\)?$", span)
        if m:
            span = m.group(1)
        if _is_filename(span):
            files.add(span.replace("\\", "/"))
        elif _IDENT.match(span):
            idents.add(span)
    return {"identifiers": sorted(idents), "files": sorted(files)}


def extract_claims(text: str, source: str) -> list[dict]:
    """Claim candidates from a markdown doc: each heading and bullet becomes a claim carrying its
    text, line, kind, and the code references it names. Deterministic and cheap; the semantic weight
    of a claim is the agent's to judge — this just finds them and what they point at."""
    claims: list[dict] = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        kind = "heading" if m else None
        if not m:
            m = _BULLET.match(line)
            kind = "bullet" if m else None
        if not m:
            continue
        body = m.group(1)
        refs = _code_refs(body)
        if not (refs["identifiers"] or refs["files"]):
            continue  # a claim with no code reference is not deterministically checkable — skip it
        claims.append({"text": body, "line": i, "kind": kind, "source": source, "refs": refs})
    return claims


def _graph_index(g: graphmod.Graph) -> tuple[set, set]:
    """(simple symbol names, file basenames+paths) present in the graph, for reference resolution."""
    names, files = set(), set()
    for node in g.nodes.values():
        nm = node.get("name")
        if node.get("type") in ("function", "class", "method") and nm:
            names.add(str(nm).split(".")[-1])   # simple name; a method's qualname tail
            names.add(str(nm))
        sf = node.get("source_file")
        if sf:
            sf = str(sf).replace("\\", "/")
            files.add(sf)
            files.add(sf.split("/")[-1])         # basename
            files.add(sf.rsplit(".", 1)[0].split("/")[-1])  # basename without extension
    return names, files


def check_claims(claims: list[dict], data: dict) -> list[dict]:
    """Resolve each claim's code references against the graph. Adds `grounded` / `dangling`
    (references the graph has a node for / does not)."""
    g = graphmod.Graph(data)
    names, files = _graph_index(g)
    out = []
    for c in claims:
        grounded, dangling = [], []
        for ident in c["refs"]["identifiers"]:
            (grounded if (ident in names or ident.split(".")[-1] in names) else dangling).append(ident)
        for f in c["refs"]["files"]:
            base = f.split("/")[-1]
            (grounded if (f in files or base in files) else dangling).append(f)
        out.append({**c, "grounded": grounded, "dangling": dangling})
    return out


def candidate_pins(checked: list[dict]) -> list[dict]:
    """Dangling claims → candidate pins. Candidates, never assertions: `confidence: inferred`,
    `provenance: doc_claim`, `to_be: null` (the interview decides doc-stale vs code-missing)."""
    pins = []
    for c in checked:
        if not c["dangling"]:
            continue
        pins.append({
            "kind": "contract_mismatch",
            "provenance": "doc_claim",
            "confidence": "inferred",
            "as_is": f"code has no {', '.join(c['dangling'])}",
            "to_be": None,
            "question": f"The doc ({c['source']}:{c['line']}) claims {c['dangling']}, which the code "
                        f"graph has no node for. Is the doc stale (update it) or the code missing "
                        f"(build it)?",
            "source": {"doc": c["source"], "line": c["line"], "text": c["text"]},
        })
    return pins


def analyze(doc_paths: list[str], data: dict) -> dict:
    """Extract → check → candidate pins across several docs. `{claims, checked, candidates, stats}`."""
    checked_all: list[dict] = []
    for dp in doc_paths:
        try:
            text = pathlib.Path(dp).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        checked_all.extend(check_claims(extract_claims(text, dp), data))
    candidates = candidate_pins(checked_all)
    return {
        "checked": checked_all,
        "candidates": candidates,
        "stats": {"claims": len(checked_all), "candidates": len(candidates),
                  "docs": len(doc_paths)},
    }


def load(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
