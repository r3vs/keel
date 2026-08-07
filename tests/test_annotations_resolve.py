"""Every annotation must RESOLVE — the one class this repo's own interpreter hides.

CI failed on `scripts/build.py` with `NameError: name 'pathlib' is not defined`, raised from the
`def` line of a function whose annotation read `pathlib.Path` in a module that imports
`from pathlib import Path`. It had been committed and pushed with nine gates green and 921 tests
passing, because **this machine runs Python 3.14 and CI runs 3.12**, and PEP 649 changed when an
annotation is evaluated: 3.14 defers it until something asks, 3.12 evaluates it at definition time.
So the name was never looked up locally and was looked up on the first import in CI.

That is the same shape as `tests/test_treesitter.py::TestASkipIsAClaimAboutOneInterpreter`, one
language feature over: **a green run is a claim about the interpreter that produced it.** The fix
there was to make the environment's difference detectable; the fix here is to stop depending on the
difference at all — ask for the VALUE of every annotation, which is what an older interpreter does
whether we ask or not.

Deliberately not a name analysis over the AST. Re-implementing Python's scoping rules would be a
second implementation of something the interpreter already owns, and it would be wrong at the edges
(string annotations, `if TYPE_CHECKING`, PEP 695 type parameters) in ways nobody would notice until
one of them shipped. `inspect.get_annotations(..., eval_str=True)` is the consumer.

Three limits, stated rather than discovered later:
  * it evaluates what a module DEFINES — its functions, classes, methods and module-level variables.
    An annotation inside a function body is evaluated by neither this nor 3.12, so neither can fail.
  * three linters under `scripts/` run their own `main()` at import. Importing them therefore RUNS
    them, which is what CI does too (`check_schema_fields.py` does `import build`); a clean exit is
    treated as a successful import and the namespace it left behind is still checked.
  * `src/mcp/server.py` imports `fastmcp`, which is never installed in this repo's environment — the
    server runs under `uv run --script` off its PEP 723 header. That is the ONLY import this file
    excuses, it is named, and any other missing module is a failure rather than a skip.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Where the code that must import cleanly on the OLDEST interpreter CI uses lives. `scripts/` is
#: here because CI imports it (`check_schema_fields.py` does `import build`) — which is exactly how
#: the failure reached a runner, and it is not covered by anything that only looks at what ships.
SOURCE_DIRS = ("src/runtime", "src/mcp", "scripts")

#: Third-party modules this repo's own environment deliberately does not carry, with the reason.
#: An unlisted `ModuleNotFoundError` fails: it means one of OUR modules stopped importing.
NOT_INSTALLED_HERE = {
    "fastmcp": "the MCP server runs under `uv run --script` off its PEP 723 header, so the "
               "dependency is resolved at launch and never in this repo's environment",
}


def _modules() -> list[tuple[str, Path]]:
    out = []
    for rel in SOURCE_DIRS:
        for path in sorted((ROOT / rel).glob("*.py")):
            if path.name.startswith("_"):
                continue
            out.append((f"{rel}/{path.name}", path))
    return out


def _annotations_of(module) -> None:
    """Ask for the VALUE of every annotation the module defines. Raises exactly what 3.12 raises."""
    inspect.get_annotations(module, eval_str=True)
    for obj in list(vars(module).values()):
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        if getattr(obj, "__module__", None) != module.__name__:
            continue                                    # imported from elsewhere; not this module's
        inspect.get_annotations(obj, eval_str=True)
        if inspect.isclass(obj):
            for attr in list(vars(obj).values()):
                if inspect.isfunction(attr):
                    inspect.get_annotations(attr, eval_str=True)


class TestEveryAnnotationResolves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for rel in SOURCE_DIRS:
            d = str(ROOT / rel)
            if d not in sys.path:
                sys.path.insert(0, d)

    def test_no_module_annotates_a_name_it_never_bound(self):
        checked, excused = 0, []
        for name, path in _modules():
            with self.subTest(module=name):
                spec = importlib.util.spec_from_file_location(f"_annots_{path.stem}", path)
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except SystemExit as exc:               # a linter that runs its own main() on import
                    self.assertIn(exc.code, (0, None),
                                  f"{name} exits non-zero when imported")
                except ModuleNotFoundError as exc:
                    self.assertIn(exc.name, NOT_INSTALLED_HERE,
                                  f"{name} imports `{exc.name}`, which is not installed here and is "
                                  f"not one of the excused third-party modules")
                    excused.append(name)
                    continue
                except Exception as exc:               # an import that fails in CI fails here
                    self.fail(f"{name} does not import: {type(exc).__name__}: {exc}")
                _annotations_of(module)
                checked += 1
        self.assertGreater(checked, 30,
                           "this gate went vacuous — it found almost no modules to check")
        self.assertEqual(excused, ["src/mcp/server.py"],
                         "the excused set is a claim about the environment and must stay exactly "
                         "as small as its reason: only the FastMCP server is resolved at launch")

    def test_the_gate_would_have_caught_the_one_that_shipped(self):
        """The plant, because a gate nobody has watched fail is a claim about itself.

        `pathlib.Path` in a module that imported only `Path` is the exact expression CI rejected —
        and it is written UNQUOTED on purpose. `from __future__ import annotations` at the top of
        this file already stringifies it; writing `"pathlib.Path"` would stringify the quotes too,
        so `eval_str` would evaluate a string literal to a string and raise nothing. The first draft
        of this test did exactly that and passed while proving the opposite.
        """
        def planted(path: pathlib.Path) -> bool:                 # noqa: F821 — the point
            return True

        with self.assertRaises(NameError):
            inspect.get_annotations(planted, eval_str=True)


if __name__ == "__main__":
    unittest.main()
