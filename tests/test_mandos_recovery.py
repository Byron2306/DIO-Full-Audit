from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from commerce.mandos import MandosLedger, commercial_outcome
from commerce.mandos_recovery import recover_orphan_outcomes, verify_complete_memory


class MandosRecoveryTests(unittest.TestCase):
    @staticmethod
    def outcome(lead_id: str) -> dict:
        return commercial_outcome(
            outcome_type="reply_received",
            lineage={"lead_id": lead_id},
            source_refs=[f"outlook:{lead_id}"],
            source_classes=["outlook_ingress"],
            occurred_at="2026-08-10T10:00:00+00:00",
            strategy={
                "product": "Evidex Evidence Packs",
                "offer": "bounded pilot",
                "communicative_act": "inbound_reply",
                "channel": "email",
            },
        )

    def test_valid_outcome_orphan_is_recovered_into_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            outcome = self.outcome("LEAD-ORPHAN-1")
            path = ledger.outcomes_root / f"{outcome['outcome_id']}.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")

            self.assertEqual(0, ledger.verify_journal()["entries"])
            receipt = verify_complete_memory(root)
            self.assertTrue(receipt["valid"])
            self.assertEqual("recovered", receipt["recovery"]["state"])
            self.assertEqual([outcome["outcome_id"]], receipt["recovery"]["recovered"])
            self.assertEqual(1, receipt["journal"]["entries"])
            self.assertEqual([], receipt["unjournaled_outcomes"])

    def test_broken_chain_is_not_silently_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.outcome("LEAD-CHAIN-1"))
            lines = [json.loads(line) for line in ledger.journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            lines[0]["entry_sha256"] = "sha256:" + "0" * 64
            ledger.journal_path.write_text("\n".join(json.dumps(row) for row in lines) + "\n", encoding="utf-8")

            orphan = self.outcome("LEAD-CHAIN-2")
            path = ledger.outcomes_root / f"{orphan['outcome_id']}.json"
            path.write_text(json.dumps(orphan, indent=2) + "\n", encoding="utf-8")

            recovery = recover_orphan_outcomes(root)
            self.assertEqual("refused_broken_chain", recovery["state"])
            verification = verify_complete_memory(root)
            self.assertFalse(verification["valid"])
            self.assertIn(orphan["outcome_id"], verification["unjournaled_outcomes"])

    def test_invalid_orphan_is_not_promoted_into_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            path = ledger.outcomes_root / "OUT-AAAAAAAAAAAAAAAAAAAAAAAA.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"schema":"not-mandos"}\n', encoding="utf-8")
            recovery = recover_orphan_outcomes(root)
            self.assertEqual("refused_invalid_orphan", recovery["state"])
            self.assertTrue(recovery["invalid_orphans"])
            self.assertEqual(0, ledger.verify_journal()["entries"])


if __name__ == "__main__":
    unittest.main()
