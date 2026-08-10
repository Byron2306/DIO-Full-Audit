from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from commerce.mandos import MandosLedger
from commerce.mandos_reconcile import reconcile_market_measurements


class MandosMarketAttributionTests(unittest.TestCase):
    @staticmethod
    def build_market_db(root: Path) -> Path:
        db = root / "state/market_command/market_command.sqlite"
        db.parent.mkdir(parents=True)
        con = sqlite3.connect(db)
        con.executescript(
            """
            CREATE TABLE campaigns (
                campaign_id TEXT PRIMARY KEY,
                product_line_id TEXT,
                offer_id TEXT,
                audience TEXT,
                channel_id TEXT
            );
            CREATE TABLE measurements (
                measurement_id TEXT PRIMARY KEY,
                campaign_id TEXT,
                recorded_at TEXT,
                spend_minor INTEGER,
                revenue_minor INTEGER,
                manual_minutes REAL,
                paid_orders INTEGER,
                qualified_leads INTEGER,
                impressions INTEGER,
                reach INTEGER,
                clicks INTEGER,
                enquiries INTEGER,
                orders INTEGER
            );
            """
        )
        con.execute(
            "INSERT INTO campaigns VALUES (?, ?, ?, ?, ?)",
            ("CMP-ATTR-1", "EVIDEX", "EVIDEX-PILOT", "NGO evidence teams", "proof_content"),
        )
        con.execute(
            "INSERT INTO measurements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("MEASURE-1", "CMP-ATTR-1", "2026-08-10T10:00:00+00:00", 1000, 5000, 12.0, 1, 1, 1000, 800, 30, 2, 1),
        )
        con.commit()
        con.close()
        return db

    @staticmethod
    def write_later_hivenance_recommendation(root: Path) -> None:
        campaign_dir = root / "campaigns/dio_market_loop/wave4/campaigns/evidex"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "HIVENANCE_HYPOTHESIS.json").write_text(
            json.dumps({"campaign_id": "CMP-ATTR-1"}), encoding="utf-8"
        )
        (campaign_dir / "HIVENANCE_MARKET_AGENTS.json").write_text(
            json.dumps({
                "created_at": "2026-08-10T11:00:00+00:00",
                "council": {"decision": "TEST", "selected_family": "proof_demo"},
            }),
            encoding="utf-8",
        )

    def test_later_hivenance_recommendation_is_not_retroactively_called_execution_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_market_db(root)
            self.write_later_hivenance_recommendation(root)
            result = reconcile_market_measurements(root)
            self.assertEqual(1, len(result["created"]))
            outcome = MandosLedger(root).outcomes()[0]
            self.assertIsNone(outcome["strategy"]["tactic_id"])
            self.assertEqual("unknown_no_execution_receipt", outcome["detail"]["tactic_attribution_state"])
            self.assertEqual(["market_measurement"], outcome["evidence"]["source_classes"])
            self.assertFalse(any("HIVENANCE_MARKET_AGENTS" in row["path"] for row in outcome["evidence"]["source_states"]))

    def test_measurement_remains_idempotent_even_when_later_recommendation_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_market_db(root)
            self.write_later_hivenance_recommendation(root)
            first = reconcile_market_measurements(root)
            receipt = root / "campaigns/dio_market_loop/wave4/campaigns/evidex/HIVENANCE_MARKET_AGENTS.json"
            receipt.write_text(
                json.dumps({"created_at": "2026-08-10T12:00:00+00:00", "council": {"decision": "TEST", "selected_family": "permission_first_partnership"}}),
                encoding="utf-8",
            )
            second = reconcile_market_measurements(root)
            self.assertEqual(1, len(first["created"]))
            self.assertEqual([], second["created"])
            self.assertEqual(first["created"], second["reused"])
            self.assertEqual(1, len(MandosLedger(root).outcomes()))


if __name__ == "__main__":
    unittest.main()
