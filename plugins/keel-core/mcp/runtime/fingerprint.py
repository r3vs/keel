"""Incremental fingerprints — the `resume` / re-audit engine (study item A2).

A full re-analysis on every run is the waste the study calls out. The fix Understand-Anything proves:
fingerprint each file at two levels — a whole-file **content hash** for the "nothing changed" fast
path, and a **signature** (the structural interface: function params/returns/exports, class members,
imports) for everything else. A change that leaves the signature intact — reformatting, a comment, an
internal-logic tweak — is **COSMETIC** and costs zero model tokens; only a signature change is
**STRUCTURAL** and re-runs the semantic pass. A whole-tree delta then classifies to
SKIP / PARTIAL / ARCHITECTURE / FULL.

Determinism is the contract: the signature deliberately excludes body-dependent fields (line counts,
statements), so the same interface always fingerprints the same regardless of how the body is
written. Python signatures come from the stdlib `ast`; a language without structural analysis gets a
content-hash-only fingerprint and is treated conservatively (any content change ⇒ STRUCTURAL).

Two guards are copied verbatim because each encodes a real bug (UA #152):
- the fingerprint baseline must be written **before** the graph's commit stamp, else an auto-update
  sees a new commit with no baseline and escalates to FULL forever — `store()` stamps the same
  commit the caller will put on the graph, so they move together;
- **LOAD-PATCH-SAVE never overwrites a non-empty store with an empty one** (`save_store`).

Stdlib-only. Reuses `graph_build` for the file walk + language table.
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
from typing import Optional

import graph_build

STORE_VERSION = 1


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _py_signature(src: str) -> Optional[dict]:
    """The structural interface of a Python file — everything a *caller* can see, and nothing about
    how a body is written. Returns None on a syntax error (caller falls back to content-hash-only)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None

    def _fn(node: ast.AST) -> dict:
        a = node.args
        params = [p.arg for p in (a.posonlyargs + a.args + a.kwonlyargs)]
        if a.vararg:
            params.append("*" + a.vararg.arg)
        if a.kwarg:
            params.append("**" + a.kwarg.arg)
        return {
            "name": node.name,
            "params": params,
            "returns": ast.unparse(node.returns) if getattr(node, "returns", None) else None,
            "exported": not node.name.startswith("_"),
        }

    functions, classes = [], []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_fn(stmt))
        elif isinstance(stmt, ast.ClassDef):
            methods = sorted(m.name for m in stmt.body
                             if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
            classes.append({"name": stmt.name, "methods": methods,
                            "exported": not stmt.name.startswith("_")})

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.add(("." * (node.level or 0)) + (node.module or ""))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)

    return {
        "functions": sorted(functions, key=lambda f: f["name"]),
        "classes": sorted(classes, key=lambda c: c["name"]),
        "imports": sorted(imports),
    }


def file_fingerprint(root: pathlib.Path, rel: str) -> dict:
    """`{content_hash, total_lines, has_structural_analysis, signature?}` for one file."""
    text = (root / rel).read_text(encoding="utf-8", errors="replace")
    lang = graph_build._LANG_BY_EXT.get(pathlib.Path(rel).suffix.lower(), "text")
    sig = _py_signature(text) if lang == "python" else None
    return {
        "content_hash": _sha256(text),
        "total_lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        "has_structural_analysis": sig is not None,
        "signature": sig,
    }


def store(root: str | pathlib.Path, *, commit: Optional[str] = None) -> dict:
    """Fingerprint every source file under `root` → a store keyed by relative path. The `commit`
    is stamped here so the caller writes it in lockstep with the graph's `built_at_commit`."""
    root = pathlib.Path(root).resolve()
    files = graph_build._iter_source_files(root)
    return {
        "version": STORE_VERSION,
        "built_at_commit": commit if commit is not None else graph_build.head_commit(root),
        "files": {rel: file_fingerprint(root, rel) for rel in files},
    }


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

NONE, COSMETIC, STRUCTURAL, NEW, DELETED = "NONE", "COSMETIC", "STRUCTURAL", "NEW", "DELETED"


def compare(old: Optional[dict], new: Optional[dict]) -> str:
    """Classify one file's change. Fast path: equal content hash ⇒ NONE. Otherwise, if either side
    lacks structural analysis ⇒ STRUCTURAL (conservative); equal signatures ⇒ COSMETIC; else STRUCTURAL."""
    if old is None and new is None:
        return NONE
    if old is None:
        return NEW
    if new is None:
        return DELETED
    if old["content_hash"] == new["content_hash"]:
        return NONE
    if not old.get("has_structural_analysis") or not new.get("has_structural_analysis"):
        return STRUCTURAL
    return COSMETIC if old.get("signature") == new.get("signature") else STRUCTURAL


def diff_stores(old_store: dict, new_store: dict) -> dict[str, str]:
    """Per-file change verdicts across two stores (deterministic key order)."""
    old_files, new_files = old_store.get("files", {}), new_store.get("files", {})
    out: dict[str, str] = {}
    for rel in sorted(set(old_files) | set(new_files)):
        out[rel] = compare(old_files.get(rel), new_files.get(rel))
    return out


def _top_dir(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ""


def classify_update(changes: dict[str, str], total_files: int, *,
                    full_files: int = 30, full_ratio: float = 0.5,
                    architecture_files: int = 10) -> dict:
    """A whole-tree verdict from the per-file changes, mirroring UA's `change-classifier`:

    - **SKIP** — nothing structural (only NONE/COSMETIC): bump the commit, re-run nothing.
    - **FULL** — a big delta (`> full_files`, or `> full_ratio` of the tree): recommend a full rebuild.
    - **ARCHITECTURE** — a new/deleted top-level directory, or `> architecture_files` structural:
      re-run architecture + tour, not just the changed files.
    - **PARTIAL** — the common case: re-analyze exactly the changed files.
    """
    structural = [r for r, c in changes.items() if c in (STRUCTURAL, NEW, DELETED)]
    verdict = {
        "structural": sorted(structural),
        "cosmetic": sorted(r for r, c in changes.items() if c == COSMETIC),
        "structural_count": len(structural),
    }
    if not structural:
        verdict["update"] = "SKIP"
        return verdict
    if len(structural) > full_files or (total_files and len(structural) / total_files > full_ratio):
        verdict["update"] = "FULL"
        return verdict
    dir_changed = {_top_dir(r) for r, c in changes.items()
                   if c in (NEW, DELETED) and _top_dir(r)}
    if dir_changed or len(structural) > architecture_files:
        verdict["update"] = "ARCHITECTURE"
        verdict["directories_touched"] = sorted(dir_changed)
        return verdict
    verdict["update"] = "PARTIAL"
    return verdict


# ---------------------------------------------------------------------------
# Persistence — with the store-wipeout guard (UA #152)
# ---------------------------------------------------------------------------

def load_store(path: str | pathlib.Path) -> Optional[dict]:
    p = pathlib.Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_store(store_obj: dict, path: str | pathlib.Path) -> bool:
    """Write the store, refusing to clobber a non-empty store with an empty one — the LOAD-PATCH-SAVE
    guard that stops a botched partial update from wiping the whole baseline. Returns False (no write)
    when it would erase a populated store, True otherwise."""
    p = pathlib.Path(path)
    if not store_obj.get("files"):
        existing = load_store(p)
        if existing and existing.get("files"):
            return False  # never turn a real baseline into an empty one
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store_obj, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return True
