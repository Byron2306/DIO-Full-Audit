from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.nichefoundry_bridge import commercial_semantic_object_from_nichefoundry  # noqa: E402
from commerce.semantic import market_signal, validate_commercial_semantic_object  # noqa: E402


class NicheFoundrySemanticBridgeTests(unittest.TestCase):
    def score_receipt(self) -> dict:
        return {
            "schema": "dio.nichefoundry.score_receipt.v1",
            "audience_fit": {
                "schema": "nichefoundry.audience_fit.v1.0",
                "passed": True,
                "score": 82,
                "threshold": 70,
                "persona": {
                    "id": "evidence_accountability_owner",
                    "name": "Evidence Accountability Owner",
                },
                "viewer_job": {"id": "decide", "label": "Help me decide", "confidence": 0.81},
                "content_pillar": {"id": "evidence_proof", "name": "Evidence Proof"},
                "value_proposition": "Help me decide by inspecting a proof-led evidence workflow.",
                "desired_reward": "A review-ready evidence pack with traceable claims.",
                "likely_next_action": "Inspect the golden case.",
            },
            "scored_opportunity": {
                "schema": "nichefoundry.opportunity.v1",
                "opportunity_id": "opp_evidex_001",
                "title": "Evidex Evidence Pack: proof before promises",
                "topic": "Proof-led evidence pack pilot",
                "angle": "Show the real proof artifact and bounded pilot.",
                "viewer_job": "decide whether Evidex can solve this workflow pain without surrendering control",
                "source_hints": ["campaigns/phase3/evidex/golden_case/GOLDEN_EVIDEX_CASE.md"],
                "series_hint": "Proof-bearing workflow services",
                "content_role": "commercial_intent",
                "opportunity_score": 70,
                "score_confidence": 0.72,
                "decision": "develop",
                "benefit_index": 0.71,
                "risk_index": 0.25,
                "normalized_signals": {
                    "audience_demand": 0.57,
                    "content_gap": 0.58,
                    "series_potential": 0.72,
                    "visual_potential": 0.78,
                    "monetization_alignment": 0.88,
                    "evidence_availability": 0.95,
                    "production_burden": 0.2,
                    "policy_risk": 0.42,
                    "freshness_risk": 0.08,
                    "studio_authority_fit": 1.0,
                },
                "signal_provenance": {
                    "audience_demand": "documented_proxy_heuristic",
                    "content_gap": "documented_proxy_heuristic",
                    "series_potential": "operator_or_provider_signal",
                    "visual_potential": "operator_or_provider_signal",
                    "monetization_alignment": "operator_or_provider_signal",
                    "evidence_availability": "operator_or_provider_signal",
                    "production_burden": "operator_or_provider_signal",
                    "policy_risk": "operator_or_provider_signal",
                    "freshness_risk": "operator_or_provider_signal",
                    "studio_authority_fit": "studio_pack_fit_engine",
                },
                "signal_evidence": {},
            },
        }

    def campaign_record(self) -> dict:
        return {
            "schema": "dio.hivenance.marketing_hypothesis.v1",
            "campaign_id": "CMP-EVIDEX-001",
            "hypothesis_id": "W4-HYP-0011",
            "product": {
                "product_layer": "evidex",
                "public_name": "Evidex Evidence Pack",
                "offer_id": "EVIDEX-PILOT-PACK",
            },
            "audience": {
                "public_segment": "South African NGO, NPO, M&E, grant and programme teams",
            },
            "hypothesis": "Proof-led evidence packs may reduce reporting friction for evidence-heavy teams.",
            "experiment": {
                "channel": "proof_content",
                "proof_asset": "campaigns/phase3/evidex/golden_case/GOLDEN_EVIDEX_CASE.md",
            },
            "gates": {
                "publication": "operator_approval_required",
                "electronic_sales_outreach": "blocked",
            },
        }

    def market_observation(self) -> dict:
        return {
            "schema": "dio.market_observation.v1",
            "observation_id": "OBS-001",
            "signals": {
                "seasonal_trigger": "annual donor reporting cycle",
                "seasonal_urgency": "moderate",
            },
        }

    def test_proxy_and_engine_signals_are_derived_not_observed(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(),
            campaign_record=self.campaign_record(),
            market_observation=self.market_observation(),
        )

        signals = cso["market_context"]["signals"]
        self.assertEqual("derived", signals["audience_demand"]["state"])
        self.assertEqual("documented_proxy_heuristic", signals["audience_demand"]["provenance"])
        self.assertEqual("derived", signals["studio_authority_fit"]["state"])
        self.assertNotIn("observed_at", signals["audience_demand"])
        self.assertEqual([], validate_commercial_semantic_object(cso))

    def test_operator_or_provider_signal_is_not_automatically_observed(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(), campaign_record=self.campaign_record()
        )

        monetization = cso["market_context"]["signals"]["monetization_alignment"]
        self.assertEqual("derived", monetization["state"])
        self.assertEqual("nichefoundry_operator_or_provider_signal_unresolved", monetization["method"])

    def test_explicit_measurement_can_be_observed(self) -> None:
        receipt = self.score_receipt()
        receipt["scored_opportunity"]["signal_evidence"]["audience_demand"] = {
            "state": "observed",
            "value": 0.66,
            "measurement": "normalized_relevant_public_video_demand_sample",
            "observed_at": "2026-08-09T20:00:00+00:00",
            "source_refs": ["market_observation:LIVE-OBS-1"],
            "provenance": "youtube_public_connector",
        }

        cso = commercial_semantic_object_from_nichefoundry(
            receipt, campaign_record=self.campaign_record()
        )

        demand = cso["market_context"]["signals"]["audience_demand"]
        self.assertEqual("observed", demand["state"])
        self.assertEqual(0.66, demand["value"])
        self.assertEqual("normalized_relevant_public_video_demand_sample", demand["measurement"])
        self.assertEqual(["market_observation:LIVE-OBS-1"], demand["source_refs"])

    def test_audience_strategy_survives_the_handoff(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(), campaign_record=self.campaign_record()
        )

        audience = cso["market_context"]["audience"]
        self.assertEqual("inferred", audience["primary_persona"]["status"])
        self.assertEqual("evidence_accountability_owner", audience["primary_persona"]["value"]["id"])
        self.assertEqual("decide", audience["viewer_job"]["value"]["id"])
        self.assertEqual("evidence_proof", audience["content_pillar"]["value"]["id"])
        self.assertEqual("Inspect the golden case.", audience["likely_next_action"]["value"])
        self.assertEqual("inferred", cso["need"]["job_to_be_done"]["status"])

    def test_target_persona_never_becomes_verified_buyer_identity(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(), campaign_record=self.campaign_record()
        )

        self.assertEqual("unknown", cso["subject"]["buyer_role"]["status"])
        self.assertEqual("unknown", cso["subject"]["organisation"]["status"])
        self.assertEqual("unknown", cso["need"]["workflow_pain"]["status"])
        self.assertIn("verified_customer_workflow_pain", cso["proof"]["prohibited_claims"])
        self.assertIn("measured_customer_demand", cso["proof"]["prohibited_claims"])

    def test_prelead_campaign_lineage_is_valid(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(), campaign_record=self.campaign_record()
        )

        self.assertIsNone(cso["lineage"]["lead_id"])
        self.assertEqual("CMP-EVIDEX-001", cso["lineage"]["campaign_id"])
        self.assertEqual("W4-HYP-0011", cso["lineage"]["hypothesis_id"])
        self.assertEqual("opp_evidex_001", cso["lineage"]["opportunity_id"])
        self.assertEqual([], validate_commercial_semantic_object(cso))

    def test_scoring_outputs_are_always_derived(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(), campaign_record=self.campaign_record()
        )

        scoring = cso["market_context"]["scoring"]
        self.assertEqual("derived", scoring["opportunity_score"]["state"])
        self.assertEqual("derived", scoring["score_confidence"]["state"])
        self.assertEqual("inferred", scoring["decision"]["status"])

    def test_observed_market_signal_requires_measurement_metadata(self) -> None:
        cso = commercial_semantic_object_from_nichefoundry(
            self.score_receipt(), campaign_record=self.campaign_record()
        )
        cso["market_context"]["signals"]["audience_demand"] = market_signal(
            0.9,
            state="observed",
            source_refs=["somewhere"],
        )

        errors = validate_commercial_semantic_object(cso)

        self.assertTrue(any("measurement is required" in error for error in errors))
        self.assertTrue(any("observed_at is required" in error for error in errors))

    def test_legacy_nichefoundry_job_bridge_contains_no_fixed_market_scores(self) -> None:
        source = (ROOT / "scripts" / "run_nichefoundry_jobs.py").read_text(encoding="utf-8")
        self.assertIn('"signals": {}', source)
        self.assertNotIn('"audience_demand": 0.72', source)
        self.assertNotIn('"monetization_alignment": 0.9', source)

    def test_json_schema_has_market_signal_authority_contract(self) -> None:
        schema = json.loads((ROOT / "schemas" / "dio.commercial_semantic_object.v1.schema.json").read_text(encoding="utf-8"))
        self.assertIn("market_context", schema["properties"])
        self.assertEqual(["observed", "derived", "unknown"], schema["$defs"]["market_signal"]["properties"]["state"]["enum"])


if __name__ == "__main__":
    unittest.main()
