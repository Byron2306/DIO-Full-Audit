from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.sophia.product_integrity import build_scholarly_risk_register  # noqa: E402


def mapped(label: str, entailment: str) -> dict:
    return {
        "claims": [
            {
                "claim_record": {
                    "claim": "The intervention causes improved outcomes.",
                    "claim_type": "causal",
                    "evidence_risk": "high",
                    "evidence_standard": "causal inference required",
                },
                "source_map": {
                    "results": [
                        {
                            "source_name": "Candidate Source",
                            "support_label": label,
                            "entailment_status": entailment,
                            "exact_span": "A visible but bounded source span.",
                            "page_locator": "p. 4",
                            "quality_score": 0.9,
                        }
                    ]
                },
            }
        ]
    }


class SophiaSupportMonotonicityTests(unittest.TestCase):
    def state(self, label: str, entailment: str) -> str:
        result = build_scholarly_risk_register(mapped(label, entailment), {})
        return result["risks"][0]["support_state"]

    def test_background_label_cannot_be_upgraded_by_partial_entailment(self) -> None:
        self.assertEqual(self.state("background only", "partial_or_contextual_only"), "background_only")

    def test_direct_support_is_downgraded_when_entailment_is_only_partial(self) -> None:
        self.assertEqual(self.state("supports", "partial_or_contextual_only"), "partial_support")

    def test_direct_support_survives_positive_entailment(self) -> None:
        self.assertEqual(self.state("supports", "entails"), "support_ready")

    def test_negative_entailment_overrides_optimistic_support_label(self) -> None:
        self.assertEqual(self.state("supports", "does_not_support"), "does_not_support")


if __name__ == "__main__":
    unittest.main()
