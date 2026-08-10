from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from commerce.mandos import MandosLedger, commercial_outcome
from commerce.mandos_feedback import campaign_feedback, enrich_nichefoundry_cso_with_mandos
from commerce.nichefoundry_bridge import commercial_semantic_object_from_nichefoundry
from commerce.semantic import validate_commercial_semantic_object
from scripts.run_hivenance_market_agents import build_context


class MandosFeedbackTests(unittest.TestCase):
    @staticmethod
    def score_receipt() -> dict:
        return {
            "schema": "dio.nichefoundry.score_receipt.v1",
            "audience_fit": {
                "persona": {"id": "evidence_owner", "name": "Evidence Owner"},
                "viewer_job": {"id": "decide", "label": "Help me decide"},
                "content_pillar": {"id": "proof", "name": "Proof"},
                "likely_next_action": "Inspect proof",
            },
            "scored_opportunity": {
                "schema": "nichefoundry.opportunity.v1",
                "opportunity_id": "opp_mandos_1",
                "title": "Evidex proof",
                "topic": "Evidence pack",
                "angle": "Show proof",
                "viewer_job": "decide whether the workflow is useful",
                "source_hints": [],
                "series_hint": "Evidence",
                "content_role": "commercial_intent",
                "opportunity_score": 70,
                "score_confidence": 0.7,
                "decision": "develop",
                "benefit_index": 0.7,
                "risk_index": 0.2,
                "normalized_signals": {},
                "signal_provenance": {},
                "signal_evidence": {},
            },
        }

    @staticmethod
    def campaign() -> dict:
        return {
            "schema": "dio.hivenance.marketing_hypothesis.v1",
            "campaign_id": "CMP-MANDOS-FEEDBACK",
            "hypothesis_id": "HYP-MANDOS-FEEDBACK",
            "product": {
                "product_layer": "evidex",
                "public_name": "Evidex Evidence Pack",
                "offer_id": "EVIDEX-PILOT-PACK",
            },
            "audience": {"public_segment": "NGO evidence teams"},
            "hypothesis": "Proof-led evidence may improve qualified interest.",
            "experiment": {"channel": "proof_content", "proof_asset": "proof.md"},
            "gates": {"publication": "operator_approval_required", "electronic_sales_outreach": "blocked"},
        }

    @staticmethod
    def outcome(lead_id: str) -> dict:
        return commercial_outcome(
            outcome_type="paid_order",
            lineage={"lead_id": lead_id, "campaign_id": "CMP-MANDOS-FEEDBACK"},
            source_refs=[f"payment:{lead_id}"],
            source_classes=["provider_payment_event"],
            occurred_at="2026-08-10T10:00:00+00:00",
            polarity="positive",
            evidence_state="verified",
            strategy={
                "product": "Evidex Evidence Pack",
                "offer": "EVIDEX-PILOT-PACK",
                "communicative_act": "proof_led_campaign_content",
                "channel": "proof_content",
                "audience": "NGO evidence teams",
            },
            economics={"currency": "ZAR", "revenue_minor": 95000},
        )

    def test_campaign_feedback_is_observed_evidence_not_a_synthetic_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            MandosLedger(root).record(self.outcome("LEAD-1"))
            feedback = campaign_feedback(root, "CMP-MANDOS-FEEDBACK")
            self.assertEqual(1, len(feedback["outcomes"]))
            self.assertEqual(95000, feedback["economics"]["revenue_minor"])
            self.assertTrue(feedback["authority"]["is_observed_evidence"])
            self.assertFalse(feedback["authority"]["is_synthetic_score"])
            self.assertFalse(feedback["authority"]["may_expand_execution_authority"])

    def test_nichefoundry_enrichment_adds_verified_outcomes_without_rewriting_scores_or_customer_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            MandosLedger(root).record(self.outcome("LEAD-1"))
            feedback = campaign_feedback(root, "CMP-MANDOS-FEEDBACK")
            cso = commercial_semantic_object_from_nichefoundry(
                self.score_receipt(),
                campaign_record=self.campaign(),
            )
            original_score = cso["market_context"]["scoring"]["opportunity_score"].copy()
            enriched = enrich_nichefoundry_cso_with_mandos(cso, feedback)
            self.assertEqual(original_score, enriched["market_context"]["scoring"]["opportunity_score"])
            self.assertEqual("unknown", enriched["subject"]["organisation"]["status"])
            self.assertEqual("unknown", enriched["need"]["workflow_pain"]["status"])
            self.assertTrue(any(
                row.get("authority") == "observed_commercial_outcome"
                for row in enriched["truth"]["verified_facts"]
            ))
            self.assertTrue(any(ref.startswith("mandos_outcome:OUT-") for ref in enriched["authority"]["evidence_refs"]))
            self.assertEqual([], validate_commercial_semantic_object(enriched))

    def test_hivenance_context_receives_mandos_outcomes_as_separate_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign_dir = root / "campaigns/dio_market_loop/wave4/campaigns/evidex"
            campaign_dir.mkdir(parents=True)
            (campaign_dir / "HIVENANCE_HYPOTHESIS.json").write_text(
                __import__("json").dumps(self.campaign()), encoding="utf-8"
            )
            (campaign_dir / "MARKET_OBSERVATION.json").write_text(
                '{"schema":"dio.market_observation.v1","observation_id":"OBS-1","signals":{}}', encoding="utf-8"
            )
            MandosLedger(root).record(self.outcome("LEAD-1"))
            with patch("scripts.run_hivenance_market_agents.ROOT", root):
                context = build_context(campaign_dir)
            feedback = context["mandos_outcomes"]
            self.assertEqual("CMP-MANDOS-FEEDBACK", feedback["campaign_id"])
            self.assertEqual(1, len(feedback["outcomes"]))
            self.assertFalse(feedback["authority"]["may_expand_execution_authority"])


if __name__ == "__main__":
    unittest.main()
