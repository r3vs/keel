"""A1 — the eleven grammars beyond JS/TS, held to what they actually extract.

Every query in `graph_build._TS_QUERIES` was written by running it against the real grammar, not by
reasoning about node names, and this file is that run kept. It is the only honest way to add a
language here: a query naming a node type the grammar does not have does not fail loudly — it
raises inside the extractor's one `try`, which returns `[], []`, and the file silently degrades to a
file node with no symbols. A green suite over a table nobody exercised would report breadth this
package does not have.

Skipped without the backend, like every other tree-sitter test — and `tests/test_treesitter.py
::TestASkipIsAClaimAboutOneInterpreter` is what stops that skip from being a way to never find out.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import graph_build  # noqa: E402
import treesitter_extract as tse  # noqa: E402

#: One sample per language, each carrying the four shapes that decide a query: a type with methods,
#: a free function, a second type kind (interface/trait/protocol/module), and — where the language
#: has one — a static or singleton method.
SAMPLES = {
    ".go": '''package main
type Server struct{ port int }
func (s *Server) Start() error { return nil }
func NewServer(p int) *Server { return &Server{p} }
type Handler interface{ Serve() }
''',
    ".rs": '''pub struct Server { port: u16 }
impl Server { pub fn start(&self) -> Result<(), Error> { Ok(()) } }
pub fn new_server(p: u16) -> Server { Server { port: p } }
trait Handler { fn serve(&self); }
enum Mode { Fast, Slow }
''',
    ".java": '''package app;
public class Server {
  public void start() {}
  public static Server create(int p) { return new Server(); }
}
interface Handler { void serve(); }
''',
    ".cs": '''namespace App;
public class Server {
  public void Start() {}
}
public interface IHandler { void Serve(); }
''',
    ".rb": '''class Server
  def start; end
  def self.create(p); end
end
def top_level; end
''',
    ".php": '''<?php
class Server {
  public function start() {}
}
function topLevel() {}
''',
    ".c": '''struct Server { int port; };
int start(struct Server *s) { return 0; }
''',
    ".cpp": '''class Server {
public:
  static Server create(int p);
};
int topLevel(int a) { return a; }
''',
    ".kt": '''class Server(val port: Int) {
  fun start() {}
}
fun topLevel() {}
''',
    ".swift": '''class Server {
  func start() {}
}
func topLevel() {}
''',
    ".scala": '''class Server(port: Int) {
  def start(): Unit = {}
}
def topLevel(): Unit = {}
''',
}

#: `(symbol names that must be extracted)` per language. Deliberately not the FULL set each grammar
#: yields — this asserts the load-bearing captures, so a query that stops matching fails here while
#: a grammar that starts yielding one more node does not.
EXPECTED = {
    ".go": {"class:Server", "class:Handler", "function:NewServer", "method:Server.Start"},
    ".rs": {"class:Server", "class:Handler", "class:Mode", "function:new_server",
            "method:Server.start"},
    ".java": {"class:Server", "class:Handler", "method:Server.start", "method:Server.create",
              "method:Handler.serve"},
    ".cs": {"class:Server", "class:IHandler", "method:Server.Start", "method:IHandler.Serve"},
    ".rb": {"class:Server", "method:Server.start", "method:Server.create", "function:top_level"},
    ".php": {"class:Server", "method:Server.start", "function:topLevel"},
    ".c": {"class:Server", "function:start"},
    ".cpp": {"class:Server", "method:Server.create", "function:topLevel"},
    ".kt": {"class:Server", "method:Server.start", "function:topLevel"},
    ".swift": {"class:Server", "method:Server.start", "function:topLevel"},
    ".scala": {"class:Server", "method:Server.start", "function:topLevel"},
}

_LANG_OF = graph_build._TS_GRAMMAR_BY_EXT


def _grammar_loads(grammar: str) -> bool:
    """Can THIS grammar be loaded — asked the way the extractor asks it.

    Not `tse.available(lang)`, which resolves through the shape engine's `STACKS` registry and
    therefore answers *is there a field-shape spec for this stack*. `graph_build` calls
    `tse.parse(src, grammar)` with a grammar name directly, and the two registries do not contain
    the same names: `available("c")` raises `no stack spec for 'c'` on an environment where the C
    grammar loads perfectly. Probing the wrong one skipped a language that works.
    """
    try:
        tse.parse("", grammar)
        return True
    except Exception:
        return False


def _symbols(ext: str, source: str) -> set:
    root = pathlib.Path(tempfile.mkdtemp())
    (root / f"sample{ext}").write_text(source, encoding="utf-8")
    data = graph_build.build_graph(root)
    return {f'{n["type"]}:{n["name"]}' for n in data["nodes"] if n["type"] != "file"}


class TestEveryDeclaredGrammarIsExercised(unittest.TestCase):
    def test_the_table_and_the_expectations_name_the_same_languages(self):
        """Derived, so a grammar added to the table without a sample fails rather than shipping
        unexercised — which is the state every one of these was in before this file."""
        declared = {ext for ext, grammar in _LANG_OF.items()
                    if grammar not in ("typescript", "tsx", "javascript")}
        covered = {ext for ext in declared if ext in SAMPLES}
        uncovered = sorted(declared - covered)
        # `.h`, `.hpp`, `.hh`, `.cxx`, `.kts`, `.mts` … are aliases of a grammar already sampled.
        aliases = {ext for ext in uncovered if _LANG_OF[ext] in {_LANG_OF[e] for e in covered}}
        self.assertEqual(sorted(set(uncovered) - aliases), [],
                         "a grammar declared in `_TS_QUERIES` with no sample here is a query "
                         "nobody ran — and a query that does not compile fails silently")
        self.assertEqual(set(SAMPLES), set(EXPECTED))


@unittest.skipUnless(tse.available(), "tree-sitter backend not installed")
class TestTheQueriesExtractWhatTheyClaim(unittest.TestCase):
    def test_each_language_yields_its_load_bearing_symbols(self):
        ran = 0
        for ext, source in sorted(SAMPLES.items()):
            grammar = _LANG_OF[ext]
            if not _grammar_loads(grammar):
                continue          # a grammar this environment cannot fetch is not a failing query
            ran += 1
            with self.subTest(language=grammar):
                got = _symbols(ext, source)
                self.assertLessEqual(EXPECTED[ext], got,
                                     f"{grammar}: missing {sorted(EXPECTED[ext] - got)}")
        if not ran:
            self.skipTest("no non-JS grammar could be loaded in this environment")

    def test_a_method_the_grammar_does_not_nest_still_finds_its_owner(self):
        """Go's receiver and Rust's `impl` type. Both sit BESIDE the type rather than inside it, so
        the range rule finds nothing and the `@owner` capture is the only thing that can."""
        self.assertIn("method:Server.Start", _symbols(".go", SAMPLES[".go"]))
        self.assertIn("method:Server.start", _symbols(".rs", SAMPLES[".rs"]))

    def test_a_method_capture_with_no_owner_is_emitted_as_a_function(self):
        """Kotlin, Swift and Scala spell a free function and a method with one node type, so the
        distinction can only be structural."""
        for ext in (".kt", ".swift", ".scala", ".rb"):
            with self.subTest(language=_LANG_OF[ext]):
                got = _symbols(ext, SAMPLES[ext])
                free = next(n for n in got if n.endswith(("topLevel", "top_level")))
                self.assertTrue(free.startswith("function:"),
                                f"a method nobody owns is a function; got {free}")

    def test_a_grammar_with_no_import_query_still_yields_its_symbols(self):
        """The regression this change exists to prevent. One module-level import query, run against
        every grammar, raises on Go/Rust/Java — and the extractor's single `except` would throw away
        every symbol already found in that file."""
        for ext in (".go", ".rs", ".java"):
            with self.subTest(language=_LANG_OF[ext]):
                self.assertNotIn("imports", graph_build._TS_QUERIES[_LANG_OF[ext]])
                self.assertTrue(_symbols(ext, SAMPLES[ext]))

    def test_typescript_imports_still_resolve(self):
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "a.ts").write_text("import { b } from './b';\nexport class A { m() {} }\n",
                                   encoding="utf-8")
        (root / "b.ts").write_text("export const b = () => 1;\n", encoding="utf-8")
        data = graph_build.build_graph(root)
        self.assertIn(("file:a.ts", "file:b.ts"),
                      {(e["source"], e["target"]) for e in data["links"]
                       if e["type"] == "imports"})


if __name__ == "__main__":
    unittest.main()
