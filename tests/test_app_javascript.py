"""The two MCP Apps' JavaScript is checked by a node gate — and this is what makes CI run it.

The gate itself is `src/workflow/__tests__/mcp-apps.ts`: it renders both served documents through
the Python that produces them, parses every `<script>` block with `node:vm`, and runs them against
a hand-rolled stub DOM on a well-formed ledger and a hostile one. Its own docstring carries the
argument for why it exists; this file exists for the sentence *after* that one.

**A gate CI does not run is not a gate.** This repo has the receipts: `check_schema_fields.py` and
`check_tool_carriers.py` ran in CI while appearing in no list a developer reads, and the shipped
`python runtime/ledger.py` was green for months because nothing exercised the axis it broke on. The
mirror failure is a checker committed, never wired, and quietly rotting — which is the more likely
one here, because the node gate lives in a directory named `__tests__` inside a package whose
`npm test` deliberately does **not** name it (`package.json` is vendored into `keel-core`; adding
the gate there would move shipped bytes for a dev-only check).

So the assertions below are about wiring, not about JavaScript:

  * the gate and the renderer it spawns both exist where the workflow says they are;
  * `.github/workflows/ci.yml` invokes the gate; and
  * it does so from a **blocking** job — an advisory JS check is a JS check nobody has to fix.

What is deliberately NOT here: running the gate. It needs node, `checks` does not install node, and
a `skipUnless(node)` would report success by not running on every leg — the self-healing silence
`tests/test_treesitter.py` was written to end. The gate runs in `workflow-engine`, once, where node
is a declared dependency of the job.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GATE = ROOT / "src" / "workflow" / "__tests__" / "mcp-apps.ts"
RENDERER = ROOT / "src" / "workflow" / "__tests__" / "render-app-documents.py"
CI = ROOT / ".github" / "workflows" / "ci.yml"

#: The command as CI must spell it. Repo-relative, because the step runs from the checkout root —
#: the working-directory-sensitive path class this repo has already been bitten by once.
COMMAND = "node --experimental-strip-types src/workflow/__tests__/mcp-apps.ts"


def _job(name: str) -> str:
    """One top-level job's block, by indentation — CI's jobs are two-space keys under `jobs:`."""
    text = CI.read_text(encoding="utf-8")
    start = text.index(f"\n  {name}:")
    rest = text[start + 1:]
    nxt = re.search(r"\n  [A-Za-z][\w-]*:\n", rest)
    return rest[: nxt.start()] if nxt else rest


class TestTheAppsJavaScriptGateIsWired(unittest.TestCase):
    def test_the_gate_and_its_renderer_exist(self):
        self.assertTrue(GATE.is_file(), f"{GATE} is gone — CI's step points at nothing")
        self.assertTrue(RENDERER.is_file(),
                        f"{RENDERER} is gone; the gate spawns it and would fail with a message "
                        f"about an interpreter rather than about the apps")

    def test_the_gate_spawns_the_renderer_beside_it(self):
        """The two halves are one gate, and the node side must not silently start checking a
        document it built itself — the whole point is that the bytes come from `apps.py`."""
        self.assertIn(RENDERER.name, GATE.read_text(encoding="utf-8"))

    def test_ci_runs_it(self):
        self.assertIn(COMMAND, CI.read_text(encoding="utf-8"),
                      "no CI step runs the MCP-apps JS gate. The two apps' JavaScript is then "
                      "linted by nothing again — which is the finding this gate was written for")

    def test_it_runs_in_a_blocking_job(self):
        """`plugin-validate` and `behavioral-evals` are `continue-on-error` for reasons a developer
        cannot fix locally (an uninstallable CLI, a credential CI does not hold). Neither reason
        applies to a node script with no dependencies, so this one blocks."""
        block = _job("workflow-engine")
        self.assertIn(COMMAND, block,
                      "the gate is invoked from some other job than `workflow-engine`; if that is "
                      "deliberate, move this assertion to the job that owns it")
        self.assertNotIn("continue-on-error", block,
                         "the job carrying the MCP-apps JS gate is advisory — an app that renders "
                         "blank would report as a warning nobody has to clear")

    def test_the_job_installs_the_two_runtimes_the_gate_needs(self):
        """The gate is node driving Python. A job with only one of them fails with a message about
        a missing interpreter, which reads as infrastructure rather than as a regression."""
        block = _job("workflow-engine")
        self.assertIn("actions/setup-node@", block)
        self.assertIn("actions/setup-python@", block,
                      "the gate renders the served documents through `apps.py` and `map.py`; "
                      "without Python on this job it cannot get the bytes it checks")

    def test_the_gate_is_not_vendored_into_the_package(self):
        """`build.py` skips `__tests__` when it copies `src/workflow/` into keel-core. That is what
        lets this gate be added without moving a shipped byte, and it is asserted rather than
        assumed because the exclusion is one string in one condition."""
        vendored = list(ROOT.glob("plugins/*/skills/*/engine/**/*"))
        # The glob is held to a non-empty result first, because everything below it is a claim about
        # what the vendored engine does NOT contain — and a `for` over nothing asserts that of an
        # empty tree just as happily. Rename the destination in `build.py` and this test would keep
        # reporting green over a directory it can no longer see, which is the exact shape of the
        # vacuous guard the file beside it exists to close.
        self.assertTrue(vendored,
                        "no vendored engine found under plugins/*/skills/*/engine — either the "
                        "build has not run or `build.py` now vendors it somewhere else; this "
                        "assertion is about the tree it lands in, so it cannot be checked blind")
        for path in vendored:
            self.assertNotIn("__tests__", path.parts,
                             f"{path} shipped a dev-only test directory")


if __name__ == "__main__":
    unittest.main()
