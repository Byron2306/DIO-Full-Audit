import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


integration = load_module("dio_marketing_integration", "scripts/run_dio_marketing_integration.py")
settlement = load_module("dio_marketing_settlement", "scripts/settle_dio_marketing_campaign.py")


class RegistrySelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = integration.load_json(ROOT / "config/dio_marketing_integration.json")
        cls.wave = integration.WaveArchive(ROOT / cls.config["active_registry_archive"])
        cls.hypotheses = cls.wave.csv("campaign_hypotheses.csv")
        cls.targets = integration.target_index(cls.wave.csv("buyer_unit_targets.csv"))

    @classmethod
    def tearDownClass(cls):
        cls.wave.close()

    def choose(self, product_line):
        product = self.config["product_lines"][product_line]
        return integration.choose_hypothesis(
            product_line,
            self.hypotheses,
            self.targets,
            product,
            self.config["route_priority"],
        )

    def test_homs_uses_reviewed_isasa_channel(self):
        hypothesis, target = self.choose("HOMS_ASSESS")
        self.assertEqual("W4-HYP-0002", hypothesis["hypothesis_id"])
        self.assertEqual("ISASA", hypothesis["organisation"])
        self.assertEqual("CHANNEL_SUBMISSION_AVAILABLE", target["route_state"])
        self.assertFalse(integration.outreach_allowed(target, self.config))

    def test_evidex_is_public_proof_only(self):
        hypothesis, target = self.choose("EVIDEX_PACK")
        self.assertEqual("W4-HYP-0011", hypothesis["hypothesis_id"])
        self.assertEqual("NASCEE", hypothesis["organisation"])
        self.assertEqual("public_proof_content_only", integration.route_mode(target))
        self.assertFalse(integration.outreach_allowed(target, self.config))

    def test_homs_learning_uses_wave4_guided_learning_lineage(self):
        hypothesis, target = self.choose("HOMS_LEARN")
        self.assertEqual("W4-HYP-0003", hypothesis["hypothesis_id"])
        self.assertEqual("SOPHIA_LEARN", hypothesis["product_line_id"])
        self.assertEqual("PARTNERSHIP_ROUTE_AVAILABLE", target["route_state"])

    def test_public_foundry_payloads_do_not_name_research_targets(self):
        for campaign_dir in (ROOT / "campaigns/dio_market_loop/wave4/campaigns").iterdir():
            if not campaign_dir.is_dir():
                continue
            public_text = "\n".join(
                (campaign_dir / name).read_text(encoding="utf-8")
                for name in ["foundry_opportunity.json", "storyboard.json", "visual_plan.json", "metadata_package.json"]
            )
            self.assertNotIn("ISASA", public_text)
            self.assertNotIn("NASCEE", public_text)
            self.assertNotRegex(public_text, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

    def test_measurement_is_not_overwritten_on_rerun(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "measurement.json"
            path.write_text('{"paid_orders": 1}\n', encoding="utf-8")
            integration.write_json_if_missing(path, {"paid_orders": 0})
            self.assertEqual({"paid_orders": 1}, json.loads(path.read_text(encoding="utf-8")))

    def test_all_registry_waves_are_retained_as_lineage(self):
        with tempfile.TemporaryDirectory() as temporary:
            lineage = integration.write_wave_lineage(Path(temporary), ROOT / self.config["active_registry_archive"])
            self.assertEqual(3, len(lineage))
            self.assertEqual(["wave4"], [item["schema"].split(".")[-2] for item in lineage if item["active"]])
            self.assertTrue((Path(temporary) / "REGISTRY_WAVE_LINEAGE.json").exists())


class SettlementTests(unittest.TestCase):
    def setUp(self):
        self.hypothesis = {
            "experiment": {"window_days": 14},
            "gates": {"electronic_sales_outreach": "blocked"},
        }
        self.measurement = {
            "measurement_window": {"started_at": "2026-07-01T00:00:00+00:00", "ended_at": "2026-07-15T00:00:00+00:00"},
            "acquisition": {"clicks": 20},
            "leads": {"qualified_leads": 4},
            "commerce": {"orders": 3, "paid_orders": 3, "revenue_minor": 150000, "refunds_minor": 0},
            "fulfilment": {"revisions": 1},
            "economics": {"ad_spend_minor": 10000, "payment_fees_minor": 5000, "external_cost_minor": 10000, "manual_labour_minor": 30000},
            "governance": {"outreach_attempts": 0, "permission_failures": 0, "unresolved_incidents": 0},
        }
        self.as_of = datetime(2026, 7, 16, tzinfo=timezone.utc)

    def test_positive_repeatable_result_promotes(self):
        decision, _, complete = settlement.decide(self.hypothesis, self.measurement, self.as_of)
        self.assertTrue(complete)
        self.assertEqual("promote", decision)

    def test_small_positive_sample_continues(self):
        self.measurement["commerce"]["orders"] = 1
        self.measurement["commerce"]["paid_orders"] = 1
        decision, _, _ = settlement.decide(self.hypothesis, self.measurement, self.as_of)
        self.assertEqual("continue", decision)

    def test_permission_failure_kills(self):
        self.measurement["governance"]["permission_failures"] = 1
        decision, _, _ = settlement.decide(self.hypothesis, self.measurement, self.as_of)
        self.assertEqual("kill", decision)


if __name__ == "__main__":
    unittest.main()
