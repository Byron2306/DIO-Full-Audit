from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from commerce.mandos import MandosLedger, commercial_outcome
from commerce.mandos_feedback import (
    campaign_feedback,
    enrich_nichefoundry_cso_with_mandos,
    hivenance_outcome_overlay,
)
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

    @staticmethod
    def hivenance_receipt(decision: str = "TEST", selected_family: str = "proof_demo") -> dict:
        return {
            "schema": "hivenance_non_crypto_market_intelligence_v1",
            "council": {
                "decision": decision,
                "selected_family": selected_family,
                "authority": "campaign_research_routing_only",
            },
            "authority": {
                "publication": "operator_only",
                "direct_outreach": "consent_gate_only",
                "commerce": "none",
            },
        }

    @staticmethod
    def overlay_feedback(*, direction: str, negative_state: str, reuse_state: str, tactic_id: str = "proof_demo") -> dict:
        return {
            "schema": "dio.mandos_campaign_feedback.v1",
            "campaign_id": "CMP-MANDOS-FEEDBACK",
            "outcomes": [
                {
                    "outcome_id": "OUT-AAAAAAAAAAAAAAAAAAAAAAAA",
                    "outcome_type": "reply_received",
                    "polarity": direction if direction in {"positive", "negative"} else "mixed",
                    "case_id": "lead_id:LEAD-1",
                }
            ],
            "patterns": [
                {
                    "pattern_key": "MANDOS-PAT-AAAAAAAAAAAAAAAAAAAA",
                    "strategy": {
                        "product": "Evidex Evidence Pack",
                        "offer": "EVIDEX-PILOT-PACK",
                        "communicative_act": "proof_led_campaign_content",
                        "channel": "proof_content",
                        "audience": "NGO evidence teams",
                        "tactic_id": tactic_id,
                        "proof_family": None,
                    },
                    "direction": direction,
                    "current_stage": "reusable_crystal" if reuse_state == "active" else "repeated_observation",
                    "evidence_summary": {
                        "verified_outcomes": 2,
                        "verified_cases": 2,
                        "positive_cases": 2 if direction == "positive" else 0,
                        "negative_cases": 2 if direction in {"negative", "contested"} else 0,
                        "source_classes": ["outlook_ingress", "operator_observation_window"],
                        "source_class_count": 2,
                    },
                    "negative_capability": {"state": negative_state, "reason": None},
                    "reuse_authority": {
                        "state": reuse_state,
                        "may_expand_execution_authority": False,
                        "scope": "strategy_hypothesis_only",
                        "exact_outcome_evidence_retained": True,
                    },
                }
            ],
            "economics": {"revenue_minor": 95000, "cost_minor": 0, "manual_minutes": 10.0, "gross_margin_minor": 95000},
            "authority": {
                "is_observed_evidence": True,
                "is_synthetic_score": False,
                "may_expand_execution_authority": False,
                "may_be_reused_as_strategy": reuse_state == "active",
            },
        }

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

    def test_exact_matched_repeated_failure_can_downgrade_hivenance_test_to_hold(self) -> None:
        overlay = hivenance_outcome_overlay(
            self.overlay_feedback(direction="negative", negative_state="active", reuse_state="not_earned"),
            self.hivenance_receipt(decision="TEST", selected_family="proof_demo"),
        )
        self.assertEqual("VETO_MATCHED_FAILURE", overlay["judgement"])
        self.assertEqual("TEST", overlay["hivenance_decision"])
        self.assertEqual("HOLD", overlay["effective_decision"])
        self.assertFalse(overlay["authority"]["may_upgrade_hivenance_decision"])
        self.assertFalse(overlay["authority"]["may_expand_execution_authority"])

    def test_contested_exact_family_can_only_refine_a_test(self) -> None:
        overlay = hivenance_outcome_overlay(
            self.overlay_feedback(direction="contested", negative_state="contested", reuse_state="not_earned"),
            self.hivenance_receipt(decision="TEST", selected_family="proof_demo"),
        )
        self.assertEqual("CHALLENGE_MATCHED_CONTRADICTION", overlay["judgement"])
        self.assertEqual("REFINE", overlay["effective_decision"])

    def test_positive_reusable_crystal_never_upgrades_native_hivenance_decision(self) -> None:
        overlay = hivenance_outcome_overlay(
            self.overlay_feedback(direction="positive", negative_state="inactive", reuse_state="active"),
            self.hivenance_receipt(decision="HOLD", selected_family="proof_demo"),
        )
        self.assertEqual("SUPPORTED_BY_REUSABLE_CRYSTAL", overlay["judgement"])
        self.assertEqual("HOLD", overlay["effective_decision"])
        self.assertFalse(overlay["authority"]["may_upgrade_hivenance_decision"])

    def test_outcomes_without_exact_hypothesis_scope_do_not_downgrade_or_upgrade(self) -> None:
        feedback = self.overlay_feedback(
            direction="negative",
            negative_state="active",
            reuse_state="not_earned",
            tactic_id="permission_first_partnership",
        )
        overlay = hivenance_outcome_overlay(
            feedback,
            self.hivenance_receipt(decision="TEST", selected_family="proof_demo"),
        )
        self.assertEqual("WITHHELD_SCOPE", overlay["judgement"])
        self.assertEqual("TEST", overlay["effective_decision"])
        self.assertEqual([], overlay["matched_pattern_keys"])


if __name__ == "__main__":
    unittest.main()
