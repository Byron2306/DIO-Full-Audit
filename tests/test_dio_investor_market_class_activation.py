import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


integration = load_module("dio_marketing_integration_activation", "scripts/run_dio_marketing_integration.py")


class InvestorActivationTests(unittest.TestCase):
    def setUp(self):
        self.config = integration.load_json(ROOT / "config/dio_marketing_integration.json")
        self.capital = self.config["product_lines"]["DIO_CAPITAL"]

    def hypothesis(self):
        return {
            "hypothesis_id": "INV-ACT-001",
            "product_line_id": "DIO_CAPITAL",
            "prospect_id": "INV-001",
            "organisation": "Example Ventures",
            "buyer_unit": "AI infrastructure partner",
            "hypothesis": "Governed proof earns a diligence conversation.",
            "primary_channel": "warm introduction",
            "success_event": "investor_meeting",
            "kill_condition": "No qualified engagement after the evidence window.",
            "outreach_gate": "permission_required",
        }

    def target(self):
        return {
            "target_id": "INV-TGT-001",
            "prospect_id": "INV-001",
            "product_line_id": "DIO_CAPITAL",
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

    def test_dio_capital_has_a_product_layer_before_activation(self):
        layers = integration.product_layers()

        self.assertNotIn("DIO_CAPITAL", self.config["active_product_lines"])
        self.assertEqual("REGISTERED_DORMANT_UNTIL_INVESTOR_REGISTRY", self.capital["activation_state"])
        self.assertIn("dio_capital", layers)
        self.assertEqual("capital_diligence", layers["dio_capital"]["category"])
        self.assertIn("CapitalRoom", layers["dio_capital"]["proof_asset"])

    def test_product_classification_prevents_investor_row_from_falling_back_to_buyer(self):
        target = self.target()
        target.pop("target_type", None)
        observation = integration.build_observation(
            Path("investor_registry.json"),
            "abc123",
            self.hypothesis(),
            target,
            self.capital,
        )

        self.assertEqual("investor_registry_wave", observation["source"]["kind"])
        self.assertEqual("investor", observation["market"]["target_type"])

    def test_investor_outreach_requires_both_permission_and_legalis_allow(self):
        target = self.target()
        target["target_type"] = "investor"
        target["outreach_state"] = "Sales outreach allowed"
        target["consent_status"] = "Consented"

        observation = integration.build_observation(
            Path("investor_registry.json"), "abc123", self.hypothesis(), target, self.capital
        )
        record = integration.build_hypothesis_record(
            self.config, "abc123", self.hypothesis(), target, self.capital, observation
        )
        self.assertEqual("blocked", record["gates"]["electronic_sales_outreach"])
        self.assertEqual("not_evaluated", record["gates"]["legalis_verdict"])

        target["legalis_verdict"] = "ALLOW"
        observation = integration.build_observation(
            Path("investor_registry.json"), "abc123", self.hypothesis(), target, self.capital
        )
        record = integration.build_hypothesis_record(
            self.config, "abc123", self.hypothesis(), target, self.capital, observation
        )
        self.assertEqual("allowed", record["gates"]["electronic_sales_outreach"])
        self.assertEqual("ALLOW", record["gates"]["legalis_verdict"])
        self.assertEqual("operator_approval_required", record["gates"]["publication"])


if __name__ == "__main__":
    unittest.main()
