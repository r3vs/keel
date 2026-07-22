"""The TS workflow engine must ship — one copy in the shared spine (alignment-core/workflow/),
beside mcp/, exactly as the Python runtime ships beside the server. Tests never ship. This is
belt-and-suspenders beside `build.py --check`: it states the intent as an executable fact."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "workflow"
OUT = ROOT / "plugins" / "alignment-core" / "workflow"


class TestWorkflowVendored(unittest.TestCase):
    def test_engine_ships_into_alignment_core(self):
        for rel in ("engine.ts", "journal.ts", "sandbox.ts", "cli.ts", "package.json",
                    "adapters/codex.ts", "adapters/opencode.ts", "topologies/phase1-finding.ts"):
            self.assertTrue((OUT / rel).exists(), f"workflow/{rel} did not ship")

    def test_tests_do_not_ship(self):
        self.assertFalse((OUT / "__tests__").exists(), "__tests__/ must never ship")
        self.assertEqual(list(OUT.rglob("*live-smoke*")), [], "live-smoke must never ship")

    def test_vendored_matches_source_byte_for_byte(self):
        for f in SRC.rglob("*"):
            rel = f.relative_to(SRC)
            if not f.is_file() or "__tests__" in rel.parts:
                continue
            shipped = OUT / rel
            self.assertTrue(shipped.exists(), f"missing shipped {rel}")
            self.assertEqual(
                f.read_text(encoding="utf-8"),
                shipped.read_text(encoding="utf-8"),
                f"drift between src and shipped for {rel} — run scripts/build.py",
            )


if __name__ == "__main__":
    unittest.main()
