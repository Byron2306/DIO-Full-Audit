from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression import CommunicativeAct, render_expression  # noqa: E402
from commerce.vendor_bridge import commercial_semantic_object_for_vendor_rfq  # noqa: E402
from commerce.workflow_bridge import commercial_semantic_object_from_product_workflow  # noqa: E402
from market_command.agency_copy import mail_copy as agency_mail_copy  # noqa: E402
from scripts.product_notification_copy import notification_copy  # noqa: E402


class CommercialExpressionAdapterTests(unittest.TestCase):
    def campaign(self) -> dict:
        return {
            "campaign_id": "CMP-TEST-001",
            "product_line_id": "EVIDEX_PACK",
            "name": "Evidex Evidence Packs",
            "audience": "South African NGO reporting teams",
            "objective": "Generate qualified pilot enquiries with measurable attribution",
        }

    def partner(self, **overrides) -> dict:
        partner = {
            "id": "agency-test",
            "name": "Example Media",
            "status": "public_route_verified",
            "inquiry": {
                "permission": "single_rfq_only",
                "mode": "email",
                "email": "rfq@example.org",
            },
        }
        partner.update(overrides)
        return partner

    def homs_workflow(self, **overrides) -> dict:
        workflow = {
            "schema": "dio.product_workflow.v1",
            "job_id": "HOMS-JOB-001",
            "product": "homs",
            "source_job_path": "/tmp/source.json",
            "customer": {"recipient": "teacher@example.org"},
            "processing": {"state": "request_ready", "receipt_path": "/tmp/homs-receipt.json", "output_dir": "/tmp/homs"},
            "output_review": {"state": "not_required"},
        }
        workflow.update(overrides)
        return workflow

    def evidex_workflow(self, approved: bool = True) -> dict:
        return {
            "schema": "dio.product_workflow.v1",
            "job_id": "EVIDEX-JOB-001",
            "product": "evidex",
            "source_job_path": "/tmp/source.json",
            "customer": {"recipient": "ngo@example.org"},
            "processing": {"state": "review_ready", "receipt_path": "/tmp/evidex-receipt.json", "output_dir": "/tmp/evidex"},
            "output_review": {"state": "approved" if approved else "pending"},
        }

    def test_vendor_rfq_is_explicit_act_and_not_spend_authority(self) -> None:
        cso = commercial_semantic_object_for_vendor_rfq(self.campaign(), self.partner())
        expression = render_expression(
            cso,
            CommunicativeAct.REQUEST_FOR_QUOTATION,
            context={
                "verified_context": {
                    "audience": {"value": "South African NGO reporting teams", "source_refs": ["campaign:CMP-TEST-001"]},
                    "objective": {"value": "Generate qualified pilot enquiries", "source_refs": ["campaign:CMP-TEST-001"]},
                    "placement": {"value": "measurable digital pilot", "source_refs": ["campaign:CMP-TEST-001", "vendor:agency-test"]},
                }
            },
        )
        self.assertEqual("request_for_quotation", expression["communicative_act"])
        self.assertIn("quotation request only", expression["body"].lower())
        self.assertIn("spend_authorised", expression["prohibited_claims"])

    def test_unqualified_vendor_route_cannot_render_rfq(self) -> None:
        cso = commercial_semantic_object_for_vendor_rfq(
            self.campaign(),
            self.partner(status="research_only", inquiry={"permission": "none", "mode": "email"}),
        )
        with self.assertRaisesRegex(ValueError, "not permitted"):
            render_expression(cso, CommunicativeAct.REQUEST_FOR_QUOTATION)

    def test_agency_mail_copy_uses_rfq_contract(self) -> None:
        subject, body, html = agency_mail_copy(self.campaign(), self.partner(), "measurable digital pilot")
        self.assertIn("RFQ", subject)
        self.assertIn("quotation", body.lower())
        self.assertIn("not a booking", html.lower())

    def test_homs_notification_is_intake_request(self) -> None:
        purpose, subject, body, html = notification_copy(self.homs_workflow())
        self.assertEqual("intake", purpose)
        self.assertIn("source material request", subject.lower())
        self.assertIn("electronic submission batch", body.lower())
        self.assertIn("HOMS Assessment Desk", html)

    def test_unready_homs_workflow_cannot_render_notification(self) -> None:
        workflow = self.homs_workflow()
        workflow["processing"]["state"] = "not_started"
        with self.assertRaisesRegex(ValueError, "not permitted"):
            notification_copy(workflow)

    def test_evidex_delivery_requires_approved_review_state(self) -> None:
        purpose, subject, body, html = notification_copy(self.evidex_workflow(approved=True))
        self.assertEqual("delivery", purpose)
        self.assertIn("reviewed Evidex Evidence Packs output is ready", subject)
        self.assertIn("retain the source material", body.lower())
        self.assertIn("REVIEWED DELIVERY READY", html)

        with self.assertRaisesRegex(ValueError, "not permitted"):
            notification_copy(self.evidex_workflow(approved=False))


if __name__ == "__main__":
    unittest.main()
