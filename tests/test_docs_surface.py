"""Tests for the docs surface (Block 3 of docs/design/sota-alignment.md): the publication
grounding gate and the DocCatalog's graded staleness. Stdlib unittest (also runs under pytest)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "runtime"))

import doccatalog  # noqa: E402
import docs_claims  # noqa: E402

GRAPH = {
    "built_at_commit": "abc1234",
    "nodes": [
        {"id": "n1", "name": "charge", "type": "function", "source_file": "src/pay/charge.ts"},
        {"id": "n2", "name": "checkout", "type": "function", "source_file": "src/pay/checkout.ts"},
    ],
    "edges": [{"source": "n2", "target": "n1", "type": "imports", "confidence": "extracted"}],
}


class TestPublicationGate(unittest.TestCase):
    def test_a_reference_that_does_not_resolve_blocks_publication(self):
        out = docs_claims.publication_gate("- call `refundOrder()` to undo a charge", GRAPH)
        self.assertFalse(out["publishable"])
        self.assertEqual(out["dangling"][0]["refs"], ["refundOrder"])

    def test_a_resolving_reference_passes(self):
        out = docs_claims.publication_gate("- `charge` takes an amount", GRAPH)
        self.assertTrue(out["publishable"])
        self.assertEqual(out["dangling"], [])

    def test_prospective_mode_lists_without_blocking(self):
        """A design doc may name unbuilt things; the danger is the present tense, not the plan."""
        out = docs_claims.publication_gate("- `refundOrder()` will undo a charge", GRAPH,
                                           mode="prospective")
        self.assertTrue(out["publishable"])
        self.assertEqual(len(out["dangling"]), 1)

    def test_it_claims_resolution_only_never_meaning(self):
        out = docs_claims.publication_gate("- `charge` deletes the database", GRAPH)
        self.assertTrue(out["publishable"])        # resolves; whether it is TRUE is a judgment
        self.assertIn("judgment", out["note"])

    def test_the_gate_is_deterministic(self):
        out = docs_claims.publication_gate("- `charge`", GRAPH)
        self.assertEqual(out["determinism"], "D0")


class TestDocCatalog(unittest.TestCase):
    def _repo(self) -> str:
        repo = tempfile.mkdtemp()
        os.makedirs(os.path.join(repo, "src", "pay"))
        with open(os.path.join(repo, "src", "pay", "charge.ts"), "w", encoding="utf-8") as fh:
            fh.write("// v1")
        return repo

    def test_a_doc_can_be_registered_before_it_exists(self):
        repo = self._repo()
        cat = doccatalog.new_catalog()
        entry = doccatalog.register(cat, "docs/pay.md", "the payment flow", "pietro",
                                    ["src/pay/charge.ts"], repo=repo)
        self.assertEqual(entry["status"], "planned")
        self.assertIsNone(entry["content_hash"])            # the prose is not written yet
        self.assertIsNotNone(entry["source_hashes"]["src/pay/charge.ts"])

    def test_a_changed_source_invalidates_by_hash_equality_not_by_estimate(self):
        repo = self._repo()
        cat = doccatalog.new_catalog()
        doccatalog.register(cat, "docs/pay.md", "s", "o", ["src/pay/charge.ts"], repo=repo)
        with open(os.path.join(repo, "src", "pay", "charge.ts"), "w", encoding="utf-8") as fh:
            fh.write("// v2")
        f = doccatalog.freshness(cat, cat["docs"][0], repo=repo)
        self.assertTrue(f["invalid"])
        self.assertEqual(f["invalid_determinism"], "D0")
        self.assertEqual(f["changed_sources"], ["src/pay/charge.ts"])

    def test_the_decay_signal_is_D1_and_says_its_weights_are_a_hypothesis(self):
        repo = self._repo()
        cat = doccatalog.new_catalog()
        doccatalog.register(cat, "docs/pay.md", "s", "o", ["src/pay/charge.ts"], repo=repo)
        f = doccatalog.freshness(cat, cat["docs"][0], repo=repo)
        self.assertEqual(f["decay_determinism"], "D1")
        self.assertTrue(f["policy_is_hypothesis"])

    def test_unmeasured_distances_are_unknown_not_zero(self):
        repo = self._repo()
        cat = doccatalog.new_catalog()
        doccatalog.register(cat, "docs/pay.md", "s", "o", ["src/pay/charge.ts"], repo=repo)
        f = doccatalog.freshness(cat, cat["docs"][0], repo=repo)
        self.assertTrue(any("distance 1 and 2" in u for u in f["unknown"]))

    def test_distance_1_reaches_the_importers_of_a_cited_source(self):
        repo = self._repo()
        cat = doccatalog.new_catalog()
        doccatalog.register(cat, "docs/pay.md", "s", "o", ["src/pay/charge.ts"], repo=repo)
        f = doccatalog.freshness(cat, cat["docs"][0], repo=repo, graph_data=GRAPH,
                                 changed_files=["src/pay/checkout.ts"])
        self.assertEqual(f["distance_1"], ["src/pay/checkout.ts"])
        self.assertFalse(f["invalid"])          # the cited source itself did not change

    def test_the_policy_lives_in_the_artifact_it_grades(self):
        """A constant hidden in code reads as a fact; pinned in the data it reads as a choice."""
        cat = doccatalog.new_catalog()
        self.assertTrue(cat["policy"]["hypothesis"])
        self.assertIn("distance_weights", cat["policy"])

    def test_a_sourceless_doc_is_reported_as_a_gap_not_a_pass(self):
        cat = doccatalog.new_catalog()
        doccatalog.register(cat, "docs/vibes.md", "s", "o", [], repo=tempfile.mkdtemp())
        cov = doccatalog.coverage(cat)
        self.assertEqual(cov["sourceless"], ["docs/vibes.md"])
        self.assertIn("That is a gap, not a pass", cov["note"])

    def test_coverage_answers_what_prose_cannot_answer_about_itself(self):
        repo = self._repo()
        cat = doccatalog.new_catalog()
        doccatalog.register(cat, "docs/a.md", "s", "o", ["src/pay/charge.ts"], repo=repo)
        doccatalog.register(cat, "docs/b.md", "s", "", ["src/pay/charge.ts"], repo=repo,
                            status="published")
        cov = doccatalog.coverage(cat)
        self.assertEqual(cov["by_status"]["published"], ["docs/b.md"])
        self.assertEqual(cov["unowned"], ["docs/b.md"])


if __name__ == "__main__":
    unittest.main()
