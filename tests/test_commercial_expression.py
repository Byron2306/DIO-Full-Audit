from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression import (  # noqa: E402
    ACT_CONTRACTS,
    CommunicativeAct,
    expression_contract,
    plan_expression,
    render_expression,
)
from commerce.prospect_bridge import commercial_semantic_object_from_prospect_target  # noqa: E402
from commerce.semantic import (  # noqa: E402
    assert_valid_commercial_semantic_object,
    commercial_semantic_object_from_lead,
    semantic_value,
)
from scripts.prospect_outreach_copy import message_for  # noqa: E402


class CommercialExpressionTests(unittest.TestCase):
    def prospect(self, **overrides) -> dict:
        target = {
            "target_id": "W4-TGT-9001",
            "organisation": "Example Foundation",
            "product_line_id": "EVIDEX_PACK",
            "product_name": "Evidex Evidence Packs",
            "primary_offer": "A donor-reporting evidence-pack pilot",
            "buyer_unit": "Monitoring and Evaluation",
            "segment": "NGO",
            "route_state": "PARTNERSHIP_ROUTE_AVAILABLE",
            "public_contact_route": "partnerships@example.org",
            "contact_source": "https://example.org/contact",
            "contact_verified_date": "2026-08-09",
            "do_not_contact": "No",
        }
        target.update(overrides)
        return target

    def qualified_cso(self) -> dict:
        cso = commercial_semantic_object_from_lead({
            "schema": "dio.lead.v1",
            "lead_id": "LEAD-QUAL-1",
            "conversation_id": "THREAD-QUAL-1",
            "product": "Evidex Evidence Packs",
            "offer": "bounded evidence-pack pilot",
            "contact": {
                "name": "Research Lead",
                "email": "lead@example.org",
                "organisation": "Example Foundation",
            },
            "request": {"subject": "Evidence pack enquiry"},
            "consents": {"processing_authority_confirmed": True},
            "attribution": {"source": "inbound_email", "medium": "email"},
            "qualification": {"state": "qualified"},
        })
        cso["need"]["job_to_be_done"] = semantic_value(
            "prepare a review-ready evidence pack",
            status="inferred",
            source_refs=["conversation:THREAD-QUAL-1"],
            authority="conversation_interpretation",
            method="qualified_intake_interpretation",
        )
        cso["need"]["workflow_pain"] = semantic_value(
            "evidence is spread across multiple files",
            status="verified",
            source_refs=["conversation:THREAD-QUAL-1"],
            authority="customer_statement",
        )
        cso["strategy"]["desired_next_action"] = semantic_value(
            "confirm a bounded pilot input",
            status="inferred",
            source_refs=["conversation:THREAD-QUAL-1"],
            authority="strategy_only",
            method="qualification_strategy",
        )
        cso["proof"]["relevant_proof"] = ["proof:evidex-golden-case"]
        cso["authority"]["authority_state"] = "qualified_lead_operator_review_required"
        assert_valid_commercial_semantic_object(cso)
        return cso

    def test_all_declared_acts_have_contracts(self) -> None:
        self.assertEqual(set(CommunicativeAct), set(ACT_CONTRACTS))
        self.assertGreaterEqual(len(ACT_CONTRACTS), 15)
        self.assertEqual("binary_permission", expression_contract("cold_permission_request")["cta_mode"])
        self.assertEqual("approve_revise_decline", expression_contract("proposal")["cta_mode"])
        self.assertEqual("inspect_proof", expression_contract("paid_ad")["cta_mode"])

    def test_same_truth_produces_materially_different_acts(self) -> None:
        cso = self.qualified_cso()
        inbound = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        proposal = render_expression(cso, CommunicativeAct.PROPOSAL)
        ad = render_expression(cso, CommunicativeAct.PAID_AD)
        video = render_expression(cso, CommunicativeAct.VIDEO_CTA)

        self.assertEqual("email", inbound["channel"])
        self.assertEqual("proposal", proposal["format"])
        self.assertEqual("paid_ad", ad["format"])
        self.assertEqual("video_cta", video["format"])
        self.assertNotEqual(inbound["body"], proposal["body"])
        self.assertNotEqual(proposal["body"], ad["body"])
        self.assertNotEqual(ad["body"], video["body"])
        self.assertIn("Thank you for getting in touch", inbound["body"])
        self.assertIn("Approve, revise or decline", proposal["body"])
        self.assertIn("Before you buy", ad["body"])
        self.assertIn("nominate one bounded pilot input", video["body"])

    def test_cold_permission_request_has_zero_customer_pain_assumptions(self) -> None:
        cso = commercial_semantic_object_from_prospect_target(self.prospect())
        expression = render_expression(cso, CommunicativeAct.COLD_PERMISSION_REQUEST)

        self.assertEqual(0, expression["plan"]["contract"]["assumption_budget"])
        self.assertIn("need.workflow_pain", expression["plan"]["unknowns"])
        self.assertNotIn("donor-reporting evidence-pack pilot", expression["body"].lower())
        self.assertNotIn("Monitoring and Evaluation", expression["body"])
        self.assertIn("permission", expression["body"].lower())
        self.assertIn("Reply YES", expression["body"])
        self.assertIn("Reply NO", expression["body"])

    def test_targeting_persona_does_not_become_buyer_fact(self) -> None:
        cso = commercial_semantic_object_from_prospect_target(self.prospect())
        self.assertEqual("inferred", cso["subject"]["buyer_role"]["status"])
        self.assertEqual("targeting_hypothesis_only", cso["subject"]["buyer_role"]["authority"])
        cold = plan_expression(cso, CommunicativeAct.COLD_PERMISSION_REQUEST)
        used_paths = {row["path"] for row in cold["facts"] + cold["hypotheses"]}
        self.assertNotIn("subject.buyer_role", used_paths)

    def test_do_not_contact_blocks_cold_expression(self) -> None:
        cso = commercial_semantic_object_from_prospect_target(self.prospect(do_not_contact="Yes"))
        with self.assertRaisesRegex(ValueError, "authority_state=research_only|blocked by consent"):
            render_expression(cso, CommunicativeAct.COLD_PERMISSION_REQUEST)

    def test_public_content_only_authority_cannot_be_used_for_direct_email(self) -> None:
        cso = self.qualified_cso()
        cso["authority"]["authority_state"] = "market_strategy_public_content_only"
        with self.assertRaisesRegex(ValueError, "not permitted"):
            render_expression(cso, CommunicativeAct.INBOUND_REPLY)

    def test_public_ad_does_not_personalise_to_organisation(self) -> None:
        cso = self.qualified_cso()
        ad = render_expression(cso, CommunicativeAct.PAID_AD)
        self.assertNotIn("Example Foundation", ad["body"])
        self.assertIn("Evidex Evidence Packs", ad["body"])

    def test_quote_refuses_to_invent_price_or_scope(self) -> None:
        cso = self.qualified_cso()
        with self.assertRaisesRegex(ValueError, "scope.*price|price.*scope"):
            render_expression(cso, CommunicativeAct.QUOTE)

        quote = render_expression(
            cso,
            CommunicativeAct.QUOTE,
            context={
                "verified_context": {
                    "scope": {"value": "one bounded reporting-period evidence pack", "source_refs": ["quote:Q-1"]},
                    "price": {"value": "ZAR 2,500", "source_refs": ["quote:Q-1"]},
                }
            },
        )
        self.assertIn("ZAR 2,500", quote["body"])
        self.assertIn("one bounded reporting-period evidence pack", quote["body"])
        self.assertEqual("quote", quote["format"])

    def test_invoice_requires_authorised_transaction_context(self) -> None:
        cso = self.qualified_cso()
        with self.assertRaisesRegex(ValueError, "invoice_reference"):
            render_expression(cso, CommunicativeAct.INVOICE_NOTICE)

    def test_generation_plan_forbids_fact_invention(self) -> None:
        plan = plan_expression(self.qualified_cso(), CommunicativeAct.PROPOSAL)
        policy = plan["generation_policy"]
        self.assertFalse(policy["may_add_facts"])
        self.assertFalse(policy["may_promote_inference_to_fact"])
        self.assertFalse(policy["may_fill_unknowns"])
        self.assertTrue(policy["must_preserve_claim_status"])
        self.assertTrue(policy["human_approval_required"])

    def test_expression_preserves_claim_source_refs(self) -> None:
        expression = render_expression(self.qualified_cso(), CommunicativeAct.QUALIFIED_LEAD_REPLY)
        pain = next(row for row in expression["claim_sources"] if row["path"] == "need.workflow_pain")
        self.assertEqual("verified", pain["status"])
        self.assertEqual(["conversation:THREAD-QUAL-1"], pain["source_refs"])

    def test_live_prospect_copy_adapter_uses_c3_contract(self) -> None:
        subject, body, html = message_for(self.prospect())
        self.assertIn("May I send Example Foundation", subject)
        self.assertIn("Reply YES", body)
        self.assertIn("Reply NO", body)
        self.assertIn("once-off permission request", body.lower())
        self.assertNotIn("donor-reporting evidence-pack pilot", body.lower())
        self.assertIn("YES, send the proof", html)
        self.assertIn("NO, thank you", html)

    def test_each_renderer_respects_its_word_ceiling(self) -> None:
        cso = self.qualified_cso()
        for act in (
            CommunicativeAct.INBOUND_REPLY,
            CommunicativeAct.QUALIFIED_LEAD_REPLY,
            CommunicativeAct.PILOT_INVITATION,
            CommunicativeAct.FOLLOW_UP,
            CommunicativeAct.PROPOSAL,
            CommunicativeAct.LINKEDIN_POST,
            CommunicativeAct.CLASSIFIED_LISTING,
            CommunicativeAct.PAID_AD,
            CommunicativeAct.VIDEO_CTA,
        ):
            expression = render_expression(cso, act)
            self.assertLessEqual(expression["word_count"], ACT_CONTRACTS[act].max_words, act.value)


if __name__ == "__main__":
    unittest.main()
