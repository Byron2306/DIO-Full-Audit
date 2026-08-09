from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import lingua_beast_bridge as bridge  # noqa: E402


class LinguaBeastIntegrationTests(unittest.TestCase):
    def test_repeated_deterministic_failure_activates_full_beast_learning_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            replacements = {
                "ROOT": root,
                "STORAGE_ROOT": root / "credits",
                "CHAIN_PATH": root / "chain.jsonl",
                "BEAST_OPERATIONS_ROOT": root / "operations",
                "BEAST_MEMORY_ROOT": root / "memory",
                "BEAST_CHRONICLE_ROOT": root / "chronicle",
                "BEAST_NEGATIVE_PATH": root / "negative.json",
                "BEAST_LEARNING_LEDGER": root / "learning.jsonl",
                "BEAST_PREC_PATH": root / "prec.db",
            }
            payload = {
                "operation": "learn_flags",
                "semantic_object_id": "TEST-OBJECT",
                "target_language": "Setswana",
                "domain": "education",
                "flags": [{
                    "severity": "high",
                    "issue": "Operational numeral was dropped from target unit P2.",
                    "observation_type": "deterministic_failure",
                }],
                "validation": {"errors": []},
            }
            with patch.multiple(bridge, **replacements):
                receipts = [bridge.learn_flags(payload) for _ in range(3)]
                status = bridge.write_status()

            self.assertEqual("active", receipts[-1]["learned"][-1]["negative_capability_state"])
            self.assertEqual(1, status["negative_capability"]["active"])
            self.assertGreaterEqual(status["learning"]["event_count"], 3)
            self.assertEqual(3, status["prec"]["count"])
            self.assertGreaterEqual(status["memory_hull"]["verified_sidecars"], 3)
            self.assertEqual(0, status["memory_hull"]["failed_sidecars"])
            self.assertTrue(any((root / "chronicle" / "evidence_chronicles").glob("*.json")))
            self.assertFalse(receipts[-1]["semantic_translation_truth_promoted"])


if __name__ == "__main__":
    unittest.main()
