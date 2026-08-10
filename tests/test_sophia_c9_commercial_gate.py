from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SophiaCommercialGateTests(unittest.TestCase):
    def test_canonical_run_requires_c9_enrichment(self) -> None:
        source = (ROOT / "scripts" / "manage_sophia_commercial.py").read_text(encoding="utf-8")
        for required in (
            "from adapters.sophia.product_integrity import enrich_review_pack",
            "integrity = enrich_review_pack(",
            '"sophia.c9_integrity_blocked"',
            'integrity.get("state") == "integrity_pack_ready"',
        ):
            self.assertIn(required, source)

    def test_legacy_approval_and_delivery_are_fail_closed_on_c9(self) -> None:
        source = (ROOT / "scripts" / "manage_sophia_commercial.py").read_text(encoding="utf-8")
        self.assertIn("Only a grounded Sophia C9 integrity pack can be approved.", source)
        self.assertIn("Sophia C9 integrity enrichment is required before delivery.", source)
        self.assertIn("integrity_record_hash", source)

    def test_c9_runner_does_not_double_enrich_initial_review(self) -> None:
        source = (ROOT / "scripts" / "run_sophia_scholarly_integrity_c9.py").read_text(encoding="utf-8")
        function = source.split("def run_initial(", 1)[1].split("def run_revision(", 1)[0]
        self.assertIn("return commercial.run_job", function)
        self.assertNotIn("enrich_review_pack(", function)

    def test_revision_and_revision_delivery_each_require_human_release_boundary(self) -> None:
        revision = (ROOT / "scripts" / "run_sophia_scholarly_integrity_c9.py").read_text(encoding="utf-8")
        delivery = (ROOT / "scripts" / "prepare_sophia_c9_revision_delivery.py").read_text(encoding="utf-8")
        self.assertIn("Only a grounded, C9-integrity-complete revision pack can be approved.", revision)
        self.assertIn("Human approval is required before preparing revision delivery.", delivery)
        self.assertIn("not plagiarism, AI-authorship or misconduct verdicts", delivery)


if __name__ == "__main__":
    unittest.main()
