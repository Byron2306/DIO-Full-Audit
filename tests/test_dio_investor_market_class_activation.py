import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


integration = load_module(
    "dio_investor_marketing_integration_activation",
    "scripts/run_dio_investor_marketing_integration.py",
)


class InvestorActivationTests(unittest.TestCase):
    def setUp(self):
        self.config = integration.load_json(ROOT / "config/dio_marketing_integration.json")
        self.capital = self.config["product_lines"]["DIO_CAPITAL"]

    def hypothesis(self, prospect_id="INV-001", hypothesis_id="INV-ACT-001", attack_score="4.0"):
        return {
            "hypothesis_id": hypothesis_id,
            "product_line_id": "DIO_CAPITAL",
            "prospect_id": prospect_id,
            "organisation": "Example Ventures",
            "buyer_unit": "AI infrastructure partner",
            "hypothesis": "Governed proof earns a diligence conversation.",
            "primary_channel": "warm introduction",
            "success_event": "investor_meeting",
            "kill_condition": "No qualified engagement after the evidence window.",
            "outreach_gate": "permission_required",
            "attack_score": attack_score,
            "rank": "1",
        }

    def target(self, prospect_id="INV-001", route_state="PARTNERSHIP_ROUTE_AVAILABLE"):
        return {
            "target_id": f"INV-TGT-{prospect_id}",
            "prospect_id": prospect_id,
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
            "stage_fit_score": "4.5",
            "cheque_fit_score": "4.4",
            "geography_fit_score": "4.0",
            "timing_score": "4.2",
            "recent_signal_score": "4.0",
            "fund_deployment_score": "4.1",
            "route_freshness_score": "4.4",
            "route_state": route_state,
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

    def test_existing_route_priority_remains_primary_for_investor_selection(self):
        route_candidate = self.hypothesis("INV-ROUTE", "INV-H-ROUTE", attack_score="1.0")
        fit_candidate = self.hypothesis("INV-FIT", "INV-H-FIT", attack_score="5.0")
        route_target = self.target("INV-ROUTE", "PARTNERSHIP_ROUTE_AVAILABLE")
        fit_target = self.target("INV-FIT", "RESEARCH_ONLY")
        route_target.update(
            {
                "thesis_fit_score": "1.0",
                "proof_fit_score": "1.0",
                "capital_use_fit_score": "1.0",
                "stage_fit_score": "1.0",
                "cheque_fit_score": "1.0",
                "geography_fit_score": "1.0",
                "timing_score": "1.0",
            }
        )
        targets = integration.target_index([route_target, fit_target])

        selected, selected_target = integration.choose_hypothesis(
            "DIO_CAPITAL",
            [route_candidate, fit_candidate],
            targets,
            self.capital,
            self.config["route_priority"],
            self.config,
        )

        self.assertEqual("INV-H-ROUTE", selected["hypothesis_id"])
        self.assertEqual("PARTNERSHIP_ROUTE_AVAILABLE", selected_target["route_state"])

    def test_investor_fit_and_timing_supplement_route_ties(self):
        weak = self.hypothesis("INV-WEAK", "INV-H-WEAK", attack_score="5.0")
        strong = self.hypothesis("INV-STRONG", "INV-H-STRONG", attack_score="1.0")
        weak_target = self.target("INV-WEAK")
        strong_target = self.target("INV-STRONG")
        weak_target.update(
            {
                "thesis_fit_score": "2.0",
                "proof_fit_score": "2.0",
                "capital_use_fit_score": "2.0",
                "stage_fit_score": "2.0",
                "cheque_fit_score": "2.0",
                "geography_fit_score": "2.0",
                "timing_score": "2.0",
                "recent_signal_score": "2.0",
                "fund_deployment_score": "2.0",
                "route_freshness_score": "2.0",
            }
        )
        targets = integration.target_index([weak_target, strong_target])

        selected, _ = integration.choose_hypothesis(
            "DIO_CAPITAL",
            [weak, strong],
            targets,
            self.capital,
            self.config["route_priority"],
            self.config,
        )

        self.assertEqual("INV-H-STRONG", selected["hypothesis_id"])

    def test_investor_strategy_explains_who_when_and_what_pitch(self):
        target = self.target()
        target["investment_thesis"] = (
            "governed AI infrastructure, enterprise orchestration, compliance, AI safety and auditability"
        )
        target["recent_signal_score"] = "4.8"
        target["fund_deployment_score"] = "4.7"
        target["route_freshness_score"] = "4.9"

        strategy = integration.build_investor_strategy(target, self.capital, self.config)

        self.assertGreaterEqual(strategy["fit_score"], 85.0)
        self.assertGreaterEqual(strategy["timing_score"], 85.0)
        self.assertEqual("APPROACH_NOW", strategy["timing_decision"])
        self.assertEqual("governed_ai_infrastructure", strategy["pitch_thesis"]["id"])
        self.assertIn("route", strategy["explanation"])
        self.assertIn("fit", strategy["explanation"])
        self.assertIn("timing", strategy["explanation"])

    def test_investor_record_carries_strategy_into_market_command(self):
        target = self.target()
        target["investment_thesis"] = "venture studio, product factory, repeatable product creation"
        observation = integration.build_observation(
            Path("investor_registry.json"), "abc123", self.hypothesis(), target, self.capital
        )
        record = integration.build_hypothesis_record(
            self.config, "abc123", self.hypothesis(), target, self.capital, observation
        )

        self.assertEqual("investor", record["audience"]["market_type"])
        self.assertEqual("product_factory", record["investor_strategy"]["pitch_thesis"]["id"])
        self.assertIn(record["investor_strategy"]["timing_decision"], {"APPROACH_NOW", "WATCH", "HOLD"})
        self.assertEqual(
            record["investor_strategy"]["pitch_thesis"]["hook"],
            record["experiment"]["public_hook"],
        )


if __name__ == "__main__":
    unittest.main()
