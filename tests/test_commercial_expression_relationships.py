from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression_guarded import CommunicativeAct, render_expression  # noqa: E402
from commerce.prospect_bridge import commercial_semantic_object_from_prospect_target  # noqa: E402
from commerce.semantic import commercial_semantic_object_from_lead  # noqa: E402


class CommercialExpressionRelationshipTests(unittest.TestCase):
    def cold_cso(self) -> dict:
        return commercial_semantic_object_from_prospect_target({
            "target_id": "W4-TGT-9999",
            "organisation": "Example Foundation",
            "product_line_id": "EVIDEX_PACK",
            "product_name": "Evidex Evidence Packs",
            "route_state": "PARTNERSHIP_ROUTE_AVAILABLE",
            "public_contact_route": "partnerships@example.org",
            "contact_source": "https://example.org/contact",
            "do_not_contact": "No",
        })

    def inbound_cso(self) -> dict:
        return commercial_semantic_object_from_lead({
            "schema": "dio.lead.v1",
            "lead_id": "LEAD-INBOUND-1",
            "product": "Evidex Evidence Packs",
            "contact": {"email": "lead@example.org"},
            "request": {"subject": "Evidence pack enquiry"},
            "consents": {"processing_authority_confirmed": True},
            "attribution": {"source": "email", "medium": "email"},
            "qualification": {"state": "pending"},
        })

    def test_cold_prospect_cannot_be_rendered_as_proposal(self) -> None:
        with self.assertRaisesRegex(ValueError, "incompatible with relationship_state=cold"):
            render_expression(self.cold_cso(), CommunicativeAct.PROPOSAL)

    def test_cold_prospect_can_render_only_cold_permission_path(self) -> None:
        expression = render_expression(self.cold_cso(), CommunicativeAct.COLD_PERMISSION_REQUEST)
        self.assertEqual("cold_permission_request", expression["communicative_act"])

    def test_pending_inbound_can_reply_but_cannot_quote(self) -> None:
        cso = self.inbound_cso()
        reply = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        self.assertEqual("inbound_reply", reply["communicative_act"])
        with self.assertRaisesRegex(ValueError, "incompatible with relationship_state=pending"):
            render_expression(cso, CommunicativeAct.QUOTE)


if __name__ == "__main__":
    unittest.main()
