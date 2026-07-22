"""Business entry-point detector — the deterministic floor under the domain view (study item C3).

You cannot elect a *to-be* until the user can see the *as-is* in **business** terms. The domain view
(Domain → Flow → Step) starts from a codebase's entry points — the places the outside world calls in:
HTTP routes, CLI commands, scheduled jobs, queue/task handlers, event listeners. This module finds
them **deterministically** (Python decorators + argparse via the stdlib `ast`, not a fragile regex),
producing the raw material an agent then lifts into the hierarchy. The scan is a fact; the hierarchy
is the agent's — the same deterministic-facts / LLM-semantics split the graph builder uses.

Stdlib-only. Reuses `graph_build` for the file walk. Non-Python files are skipped (the tree-sitter
generalization is the same additive step tracked for the graph builder); the Python floor is testable.
"""
from __future__ import annotations

import ast
import json
import pathlib
from typing import Optional

import graph_build

# decorator attribute (the method on a router/app object) → entry kind. Matched on the LAST attribute
# of the decorator, so `app.get`, `router.get`, `api.get`, `bp.get` all classify the same way.
_HTTP_METHODS = frozenset({"route", "get", "post", "put", "delete", "patch", "head", "options",
                           "websocket"})
_DECORATOR_KIND = {
    "command": "cli", "group": "cli",                       # click / typer
    "task": "task", "shared_task": "task",                  # celery
    "on_event": "event", "subscribe": "event", "listener": "event", "event": "event",
    "scheduled": "cron", "periodic_task": "cron", "cron": "cron",
}
# a receiver/object name that, combined with an http-ish method, signals a route (avoids matching a
# random `.get` on a dict). Kept broad but explicit.
_HTTP_RECEIVERS = frozenset({"app", "router", "api", "bp", "blueprint", "route", "routes",
                             "application", "server", "web", "mcp"})


def _decorator_parts(dec: ast.AST) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(receiver, attr, first-string-arg) for a decorator, e.g. `@app.get("/x")` → (app, get, /x)."""
    call_arg = None
    node = dec
    if isinstance(dec, ast.Call):
        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
            call_arg = dec.args[0].value
        node = dec.func
    if isinstance(node, ast.Attribute):
        recv = node.value.id if isinstance(node.value, ast.Name) else (
            node.value.attr if isinstance(node.value, ast.Attribute) else None)
        return recv, node.attr, call_arg
    if isinstance(node, ast.Name):
        return None, node.id, call_arg
    return None, None, call_arg


def _classify(recv: Optional[str], attr: Optional[str]) -> Optional[str]:
    if attr is None:
        return None
    a = attr.lower()
    if a in _HTTP_METHODS and (recv is None or recv.lower() in _HTTP_RECEIVERS):
        return "http"
    return _DECORATOR_KIND.get(a)


def _scan_python(rel: str, src: str) -> list[dict]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    found: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                recv, attr, arg = _decorator_parts(dec)
                kind = _classify(recv, attr)
                if kind:
                    found.append({
                        "file": rel, "line": node.lineno, "kind": kind,
                        "handler": node.name, "route": arg,
                        "signal": f"@{recv + '.' if recv else ''}{attr}",
                    })
                    break  # one classification per handler
        # argparse / __main__ as a CLI entry (module-level)
        elif isinstance(node, ast.If) and _is_main_guard(node):
            found.append({"file": rel, "line": node.lineno, "kind": "cli",
                          "handler": "__main__", "route": None, "signal": '__name__ == "__main__"'})

    return found


def _is_main_guard(node: ast.If) -> bool:
    t = node.test
    return (isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == "__name__"
            and len(t.comparators) == 1 and isinstance(t.comparators[0], ast.Constant)
            and t.comparators[0].value == "__main__")


def scan_entry_points(root: str | pathlib.Path) -> dict:
    """Deterministically locate the codebase's entry points → `{entry_points: [...], by_kind, stats}`.
    Sorted, so a re-run is byte-identical. The agent turns these into Domain → Flow → Step."""
    root = pathlib.Path(root).resolve()
    eps: list[dict] = []
    for rel in graph_build._iter_source_files(root):
        if graph_build._LANG_BY_EXT.get(pathlib.Path(rel).suffix.lower()) != "python":
            continue
        try:
            src = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        eps.extend(_scan_python(rel, src))

    eps.sort(key=lambda e: (e["file"], e["line"], e["handler"]))
    by_kind: dict[str, int] = {}
    for e in eps:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    return {
        "entry_points": eps,
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: (-kv[1], kv[0]))),
        "stats": {"count": len(eps), "kinds": len(by_kind)},
    }


def load_root(p: str) -> str:
    return p
