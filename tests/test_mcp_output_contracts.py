"""The type every MCP tool DECLARES must be the type it actually returns.

FastMCP derives each tool's `output_schema` from its return annotation, and the host validates the
payload against it. An annotation is therefore not documentation here — it is a contract enforced on
the wire by a component that never reads the function body.

`contract_diff` and `reconcile_layers` both annotated `-> dict` and both returned `shapes`' bare
`list[dict]`. Every call failed with `structured_content must be a dict` — including the zero-drift
case, which returns `[]`, so the two core cross-layer tools never worked over MCP at all. That is
the *only* runtime channel on all four hosts since the CLI was removed, and 550 tests stayed green
throughout: every behaviour test calls `tools.contract_diff(...)` in-process, where a list is
perfectly fine, and `test_mcp_server.py` inspected only the **input** schema.

So this walks the ASTs rather than executing anything (no uv, no FastMCP, no fixtures): for every
tool, the annotation on `server.py` must equal the annotation on the `tools.py` body it delegates
to, which must equal the type that body **provably** returns.

Unprovable is a FAILURE, not a skip. A gate that quietly ignores the returns it cannot follow is
exactly how the first one missed this — and the shape of every bug this repo keeps finding in
itself: the check anchored on what was easy to see instead of on what actually ships.
"""
import ast
import pathlib
import unittest

# An `async def` tool is still a tool. Matching only ast.FunctionDef made the elicitation path
# invisible to this gate the moment it was written — the exact silent-skip this file forbids.
FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
MCP = SRC / "mcp"
RUNTIME = SRC / "runtime"


class Unprovable(Exception):
    """The resolver could not follow a return to a declared type. Never swallowed."""


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _annotation(fn):
    return ast.unparse(fn.returns) if fn.returns else None


def _functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, FUNC)}


def _aliases(fn, module_tree):
    """`import shapes` / `import findings as F`, at module level or inside the function body.

    tools.py imports the runtime lazily inside each function — the import site is local, so alias
    resolution has to be too.
    """
    out = {}
    for scope in (module_tree, fn):
        for n in ast.walk(scope):
            if isinstance(n, ast.Import):
                for a in n.names:
                    out[a.asname or a.name] = a.name
    return out


def _returns_of(fn):
    """Returns belonging to THIS function — not to a nested def."""
    nested = {id(n) for outer in ast.walk(fn) if outer is not fn
              for n in ast.walk(outer) if isinstance(outer, FUNC)}
    return [n for n in ast.walk(fn)
            if isinstance(n, ast.Return) and n.value is not None and id(n) not in nested]


class Universe:
    """The functions a tool body may delegate to, keyed as `module.function`."""

    def __init__(self, py_files):
        self.functions = {}
        self.methods = {}
        for f in py_files:
            tree = _parse(f)
            for n in tree.body:
                if isinstance(n, FUNC):
                    self.functions[f"{f.stem}.{n.name}"] = _annotation(n)
                elif isinstance(n, ast.ClassDef):
                    for m in n.body:
                        if isinstance(m, FUNC):
                            self.methods.setdefault(m.name, set()).add(_annotation(m))

    def function(self, dotted):
        if dotted not in self.functions:
            raise Unprovable(f"{dotted} is not a function in this universe")
        ann = self.functions[dotted]
        if ann is None:
            raise Unprovable(f"{dotted} has no return annotation to check against")
        return ann

    def method(self, name):
        anns = self.methods.get(name)
        if not anns:
            raise Unprovable(f"no method named {name!r} anywhere in the universe")
        if len(anns) > 1 or None in anns:
            raise Unprovable(f"method {name!r} is ambiguous or unannotated: {sorted(map(str, anns))}")
        return next(iter(anns))


def prove(fn, module_tree, universe):
    """Every type this function can return, or Unprovable.

    Deliberately small: it understands dict literals, a delegated call, a conditional between the
    two, and a local whose type is pinned by an assignment or by a `x[...] = ...` (which only a
    mapping survives). Anything else must be made explicit at the call site rather than guessed
    here — this file may not become the heuristic it exists to prevent.
    """
    aliases = _aliases(fn, module_tree)
    subscripted = {t.value.id for n in ast.walk(fn) if isinstance(n, (ast.Assign, ast.AugAssign))
                   for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                   if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)}

    def assigned(name):
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == name for t in n.targets):
                return n.value
        raise Unprovable(f"local {name!r} is returned but never plainly assigned")

    def of(node, seen=()):
        if isinstance(node, ast.Dict):
            return {"dict"}
        if isinstance(node, ast.IfExp):
            return of(node.body, seen) | of(node.orelse, seen)
        if isinstance(node, ast.Name):
            if node.id in subscripted:
                return {"dict"}          # `out["k"] = v` succeeds on nothing else
            if node.id in seen:
                raise Unprovable(f"local {node.id!r} resolves to itself")
            return of(assigned(node.id), seen + (node.id,))
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "dict":
                return {"dict"}
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in aliases:
                return {universe.function(f"{aliases[f.value.id]}.{f.attr}")}
            if isinstance(f, ast.Attribute):
                return {universe.method(f.attr)}     # a method on a value, e.g. `ledger.summary()`
            if isinstance(f, ast.Name):
                raise Unprovable(f"local call {f.id}(...) — annotate or inline it")
        raise Unprovable(f"cannot follow `{ast.unparse(node)}`")

    proven = set()
    for r in _returns_of(fn):
        proven |= of(r.value)
    return proven


class TestDeclaredOutputMatchesActual(unittest.TestCase):
    """Static, total, and dependency-free — it runs everywhere the rest of the suite does."""

    @classmethod
    def setUpClass(cls):
        cls.server_tree = _parse(MCP / "server.py")
        cls.tools_tree = _parse(MCP / "tools.py")
        cls.server_fns = _functions(cls.server_tree)
        cls.tools_fns = _functions(cls.tools_tree)
        cls.runtime = Universe(sorted(RUNTIME.glob("*.py")))
        cls.tools_universe = Universe([MCP / "tools.py"])
        cls.tool_names = sorted(
            n.name for n in cls.server_tree.body
            if isinstance(n, FUNC) and any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
                for d in n.decorator_list)
        )

    def test_the_walk_found_the_tools(self):
        # If the decorator shape ever changes, every assertion below would vacuously pass.
        self.assertGreater(len(self.tool_names), 40,
                           "no @mcp.tool functions found — the decorator shape changed and this "
                           "whole file went silently vacuous")

    def test_every_tool_returns_what_its_body_provably_returns(self):
        """The gate proper. `tools.py` is where the type is really decided."""
        for name in self.tool_names:
            with self.subTest(tool=name):
                fn = self.tools_fns.get(name)
                if fn is None:
                    continue                     # composed in the adapter; covered by the test below
                declared = _annotation(fn)
                self.assertIsNotNone(declared, f"tools.{name} has no return annotation; FastMCP "
                                               f"would derive the tool's output_schema from it")
                try:
                    actual = prove(fn, self.tools_tree, self.runtime)
                except Unprovable as exc:
                    self.fail(f"tools.{name}: {exc}. Make the return type provable — an "
                              f"unverifiable annotation is what shipped contract_diff broken.")
                self.assertEqual(actual, {declared},
                                 f"tools.{name} declares `{declared}` but returns {sorted(actual)}. "
                                 f"FastMCP builds the output_schema from the annotation, so the host "
                                 f"rejects the payload on EVERY call — including the empty one. Wrap "
                                 f"the value in a dict (the house shape is `{{'findings': [...]}}`).")

    def test_the_adapter_declares_the_same_type_as_the_body(self):
        """`server.py` carries the annotation FastMCP actually reads; `tools.py` carries the value."""
        for name in self.tool_names:
            with self.subTest(tool=name):
                srv = self.server_fns[name]
                declared = _annotation(srv)
                self.assertIsNotNone(declared, f"server.{name} has no return annotation")
                try:
                    actual = prove(srv, self.server_tree, self.tools_universe)
                except Unprovable as exc:
                    self.fail(f"server.{name}: {exc}")
                self.assertEqual(actual, {declared},
                                 f"server.{name} declares `{declared}` but forwards {sorted(actual)}")

    def test_the_structured_payload_is_always_an_object(self):
        """MCP's `structuredContent` is an object. A tool annotated as anything else is dead on the
        wire whatever the annotation says — so the only correct declaration is `dict`."""
        for name in self.tool_names:
            with self.subTest(tool=name):
                self.assertEqual(_annotation(self.server_fns[name]), "dict",
                                 "structuredContent must be a JSON object: return a dict with a "
                                 "named key rather than a bare list or scalar")


if __name__ == "__main__":
    unittest.main()
