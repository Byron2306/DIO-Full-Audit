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

    def test_investor_market_class_is_registered_but_dormant_until_an_investor_registry_exists(self):
        capital = self.config["product_lines"]["DIO_CAPITAL"]
        self.assertEqual("investor", capital["target_type"])
        self.assertNotIn("DIO_CAPITAL", self.config["active_product_lines"])
        self.assertEqual(
            ["InvestorProof", "Report & Pitch Studio", "DIO CapitalRoom", "DIO Legalis"],
            capital["composition"],
        )

    def test_investor_target_builds_capital_context_without_granting_outreach(self):
        product = {
            "target_type": "investor",
            "product_layer": "dio_capital",
            "public_name": "DIO",
            "offer_id": "DIO-CAPITAL-CONVERSATION",
            "generic_audience": "seed and early-stage investors evaluating governed AI and product infrastructure",
            "proof_pointer": "docs/FUSION_WAVE9_CAPITALROOM_EXTERNAL_PROOF.md",
            "proof_summary": "Manifest-bound architecture, operational, refusal and product proof.",
            "public_hook": "One governed organism can compose many evidence-bound product incarnations.",
            "public_cta": "Review the CapitalRoom and request a diligence conversation.",
            "composition": ["InvestorProof", "Report & Pitch Studio", "DIO CapitalRoom", "DIO Legalis"],
            "preferred_route_states": ["PARTNERSHIP_ROUTE_AVAILABLE"],
            "success_event": "investor_meeting",
        }
        hypothesis = {
            "hypothesis_id": "INV-HYP-001",
            "product_line_id": "DIO_CAPITAL",
            "prospect_id": "INV-001",
            "organisation": "Example Ventures",
            "buyer_unit": "AI infrastructure partner",
            "hypothesis": "Governed product-factory proof will earn a diligence conversation.",
            "primary_channel": "warm introduction",
            "success_event": "investor_meeting",
            "kill_condition": "No qualified engagement after the evidence window.",
            "outreach_gate": "permission_required",
        }
        target = {
            "target_id": "INV-TGT-001",
            "prospect_id": "INV-001",
            "product_line_id": "DIO_CAPITAL",
            "target_type": "investor",
            "organisation": "Example Ventures",
            "investor_type": "seed VC",
            "stage": "pre-seed;seed",
            "typical_cheque": "$250k-$1m",
            "geography": "Africa;global",
            "investment_thesis": "AI infrastructure and vertical software",
            "partner": "Example Partner",
            "thesis_fit_score": "4.8",
            "proof_fit_score": "5.0",
            "capital_use_fit_score": "4.6",
            "timing_score": "4.2",
            "route_state": "PARTNERSHIP_ROUTE_AVAILABLE",
            "outreach_state": "Research only",
            "consent_status": "Not recorded",
            "do_not_contact": "No",
            "contact_source": "public investor profile",
            "contact_verified_date": "2026-09-08",
        }
        observation = integration.build_observation(Path("investor_registry.json"), "abc123", hypothesis, target)
        record = integration.build_hypothesis_record(self.config, "abc123", hypothesis, target, product, observation)

        self.assertEqual("investor", observation["market"]["target_type"])
        self.assertEqual("seed VC", observation["market"]["investor_type"])
        self.assertEqual(4.8, observation["signals"]["thesis_fit_score"])
        self.assertEqual("investor", record["audience"]["market_type"])
        self.assertEqual("investor_meeting", record["experiment"]["success_event"])
        self.assertEqual(product["composition"], record["composition"]["products"])
        self.assertEqual("required_before_external_action", record["gates"]["legalis"])
        self.assertEqual("required_for_diligence", record["gates"]["capitalroom"])
        self.assertEqual("blocked", record["gates"]["electronic_sales_outreach"])

        measurement = integration.measurement_template(record)
        self.assertIn("capital_funnel", measurement)
        self.assertNotIn("commerce", measurement)
        self.assertEqual(0, measurement["capital_funnel"]["term_sheets"])


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

    def test_investor_diligence_signal_continues_campaign(self):
        hypothesis = {
            "audience": {"market_type": "investor"},
            "experiment": {"window_days": 14},
            "gates": {"electronic_sales_outreach": "blocked"},
        }
        measurement = {
            "measurement_window": {"started_at": "2026-07-01T00:00:00+00:00", "ended_at": "2026-07-15T00:00:00+00:00"},
            "acquisition": {"profile_engagements": 12},
            "capital_funnel": {"replies": 2, "introductions": 1, "meetings": 1, "diligence_entries": 1, "partner_meetings": 0, "ic_reviews": 0, "term_sheets": 0, "passes": 0},
            "governance": {"outreach_attempts": 0, "permission_failures": 0, "unresolved_incidents": 0},
        }
        decision, reasons, complete = settlement.decide(hypothesis, measurement, self.as_of)
        self.assertTrue(complete)
        self.assertEqual("continue", decision)
        self.assertTrue(any("diligence" in reason.lower() for reason in reasons))

    def test_investor_term_sheet_promotes_campaign_not_investment_truth(self):
        hypothesis = {
            "audience": {"market_type": "investor"},
            "experiment": {"window_days": 14},
            "gates": {"electronic_sales_outreach": "blocked"},
        }
        measurement = {
            "measurement_window": {"started_at": "2026-07-01T00:00:00+00:00", "ended_at": "2026-07-15T00:00:00+00:00"},
            "acquisition": {"profile_engagements": 20},
            "capital_funnel": {"replies": 3, "introductions": 2, "meetings": 3, "diligence_entries": 2, "partner_meetings": 1, "ic_reviews": 1, "term_sheets": 1, "passes": 0},
            "governance": {"outreach_attempts": 0, "permission_failures": 0, "unresolved_incidents": 0},
        }
        decision, reasons, complete = settlement.decide(hypothesis, measurement, self.as_of)
        self.assertTrue(complete)
        self.assertEqual("promote", decision)
        self.assertTrue(any("campaign" in reason.lower() for reason in reasons))
        self.assertFalse(any("investment secured" in reason.lower() for reason in reasons))


if __name__ == "__main__":
    unittest.main()
