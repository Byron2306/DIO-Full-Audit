from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_command.agency import prepare_agency_rfq
from market_command.core import MarketStore


CONFIG = {
    "default_experiment_window_days": 14,
    "max_experiment_budget_minor": 0,
    "promotion_min_qualified_leads": 5,
    "promotion_min_paid_orders": 2,
    "promotion_min_roas": 1.5,
    "kill_min_spend_minor": 50000,
    "revise_min_clicks": 50,
}


class SemanticJudgementAgencyTests(unittest.TestCase):
    @staticmethod
    def make_root(tmp: str) -> tuple[Path, MarketStore]:
        root = Path(tmp) / "dio"
        (root / "config").mkdir(parents=True)
        (root / "config" / "agency_partner_registry.json").write_text(json.dumps({
            "partners": [{
                "id": "TEST_AGENCY",
                "name": "Test Agency",
                "status": "public_route_verified",
                "inquiry": {
                    "mode": "email",
                    "email": "hello@example.test",
                    "url": "https://example.test/contact",
                    "permission": "single_rfq_only",
                },
            }]
        }), encoding="utf-8")
        (root / "config" / "marketing_channels.json").write_text('{"channels": []}', encoding="utf-8")
        (root / "config" / "sa_media_marketplace.json").write_text('{"vendors": []}', encoding="utf-8")
        (root / "config" / "market_command.json").write_text("{}", encoding="utf-8")
        store = MarketStore(
            root / "state" / "market_command" / "market.sqlite",
            root / "telemetry" / "events.jsonl",
            CONFIG,
        )
        return root, store

    @staticmethod
    def campaign(store: MarketStore) -> dict:
        return store.create_campaign({
            "product_line_id": "HOMS_ASSESS",
            "name": "HOMS controlled pilot",
            "audience": "South African secondary schools",
            "channel_id": "SA_MEDIA_BUY",
            "objective": "qualified pilot conversation",
        })

    def test_email_rfq_carries_triune_receipt_and_vendor_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, store = self.make_root(tmp)
            current = self.campaign(store)
            state = prepare_agency_rfq(
                root,
                store,
                current["campaign_id"],
                "TEST_AGENCY",
                "measurable education pilot",
                "test operator",
                True,
            )
            self.assertEqual("mail_intent_ready", state["state"])
            self.assertTrue(str(state["semantic_judgement_id"]).startswith("JUDGE-"))
            self.assertIn(state["semantic_judgement_verdict"], {"ALLOW", "ALLOW_WITH_OBLIGATIONS"})

            intent_path = root / "state" / "mail_intents" / f"{state['mail_intent_id']}.json"
            intent = json.loads(intent_path.read_text(encoding="utf-8"))
            self.assertEqual("request_for_quotation", intent["communicative_act"])
            self.assertTrue(intent["semantic_binding"]["semantic_object_id"].startswith("CSO-"))
            judgement_path = root / intent["semantic_judgement"]["path"]
            judgement = json.loads(judgement_path.read_text(encoding="utf-8"))
            self.assertFalse(judgement["execution_authority_granted"])
            source_paths = {row["path"] for row in judgement["bindings"]["source_states"]}
            self.assertIn("config/agency_partner_registry.json", source_paths)
            self.assertIn("config/market_command.json", source_paths)
            self.assertTrue(any(path.endswith("MEDIA_BUY_BRIEF.md") for path in source_paths))

    def test_registry_change_stales_rfq_judgement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, store = self.make_root(tmp)
            current = self.campaign(store)
            state = prepare_agency_rfq(
                root,
                store,
                current["campaign_id"],
                "TEST_AGENCY",
                "measurable education pilot",
                "test operator",
                True,
            )
            intent_path = root / "state" / "mail_intents" / f"{state['mail_intent_id']}.json"
            intent = json.loads(intent_path.read_text(encoding="utf-8"))
            registry = root / "config" / "agency_partner_registry.json"
            registry.write_text(json.dumps({"partners": []}), encoding="utf-8")

            from commerce.semantic_judgement import assert_mail_semantic_judgement_current
            with self.assertRaisesRegex(ValueError, "SEMANTIC_JUDGEMENT_STALE"):
                assert_mail_semantic_judgement_current(root, intent, require_execution_ready=False)


if __name__ == "__main__":
    unittest.main()
