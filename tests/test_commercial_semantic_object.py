from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.semantic import (  # noqa: E402
    SCHEMA,
    assert_valid_commercial_semantic_object,
    commercial_semantic_object_from_lead,
    semantic_claim,
    semantic_value,
    stable_semantic_object_id,
    validate_commercial_semantic_object,
)


class CommercialSemanticObjectTests(unittest.TestCase):
    def sample_lead(self) -> dict:
        return {
            "schema": "dio.lead.v1",
            "lead_id": "EVIDEX-20260809-ABC123",
            "product": "evidex",
            "offer": "review_ready_evidence_pack",
            "contact": {
                "name": "A Research Lead",
                "email": "researcher@example.org",
                "organisation": "Example University",
            },
            "request": {
                "subject": "Evidence mapping enquiry",
                "scope": "Please help with a review pack.",
            },
            "consents": {
                "email_received": True,
                "processing_authority_confirmed": False,
            },
            "attribution": {"source": "website", "medium": "web"},
            "state": "new",
            "qualification": {"state": "pending"},
            "conversation_id": "THREAD-1",
        }

    def test_thin_lead_adapter_is_valid_and_conservative(self) -> None:
        semantic = commercial_semantic_object_from_lead(self.sample_lead())

        self.assertEqual(SCHEMA, semantic["schema"])
        self.assertEqual("verified", semantic["commercial"]["product"]["status"])
        self.assertEqual("evidex", semantic["commercial"]["product"]["value"])
        self.assertEqual("verified", semantic["subject"]["organisation"]["status"])
        self.assertEqual("unknown", semantic["need"]["workflow_pain"]["status"])
        self.assertEqual("unknown", semantic["commercial"]["scope"]["status"])
        self.assertEqual("unknown", semantic["strategy"]["communicative_act"]["status"])
        self.assertEqual("processing_authority_not_confirmed", semantic["subject"]["consent_state"]["value"])
        self.assertIn("processing_authority", semantic["proof"]["prohibited_claims"])
        self.assertEqual([], validate_commercial_semantic_object(semantic))

    def test_request_text_does_not_become_verified_customer_pain(self) -> None:
        lead = self.sample_lead()
        lead["request"]["scope"] = "We are drowning in evidence and need this urgently."
        semantic = commercial_semantic_object_from_lead(lead)

        self.assertEqual("unknown", semantic["need"]["workflow_pain"]["status"])
        self.assertEqual("unknown", semantic["need"]["why_now"]["status"])
        statements = {row["statement"] for row in semantic["truth"]["verified_facts"]}
        self.assertFalse(any("drowning" in statement for statement in statements))

    def test_missing_organisation_stays_unknown(self) -> None:
        lead = self.sample_lead()
        lead["contact"]["organisation"] = None
        semantic = commercial_semantic_object_from_lead(lead)

        self.assertIsNone(semantic["subject"]["organisation"]["value"])
        self.assertEqual("unknown", semantic["subject"]["organisation"]["status"])

    def test_verified_values_require_evidence_reference(self) -> None:
        semantic = commercial_semantic_object_from_lead(self.sample_lead())
        semantic["commercial"]["product"] = semantic_value("evidex", status="verified")

        errors = validate_commercial_semantic_object(semantic)

        self.assertTrue(any("commercial.product.source_refs" in error for error in errors))
        with self.assertRaises(ValueError):
            assert_valid_commercial_semantic_object(semantic)

    def test_inferred_claim_requires_basis_reference(self) -> None:
        semantic = commercial_semantic_object_from_lead(self.sample_lead())
        semantic["truth"]["inferred_hypotheses"].append(
            semantic_claim("Buyer probably has a large budget.", status="inferred")
        )

        errors = validate_commercial_semantic_object(semantic)

        self.assertTrue(any("inferred_hypotheses[0].source_refs" in error for error in errors))

    def test_claim_cannot_be_permitted_and_prohibited(self) -> None:
        semantic = commercial_semantic_object_from_lead(self.sample_lead())
        semantic["proof"]["permitted_claims"].append("customer_budget")

        errors = validate_commercial_semantic_object(semantic)

        self.assertTrue(any("both permitted and prohibited" in error for error in errors))

    def test_object_id_is_deterministic(self) -> None:
        left = commercial_semantic_object_from_lead(self.sample_lead())
        right = commercial_semantic_object_from_lead(self.sample_lead())

        self.assertEqual(left["object_id"], right["object_id"])
        self.assertEqual(
            stable_semantic_object_id(
                "EVIDEX-20260809-ABC123",
                "THREAD-1",
                None,
                "evidex",
                "researcher@example.org",
            ),
            left["object_id"],
        )

    def test_json_schema_contract_is_present_and_named(self) -> None:
        schema_path = ROOT / "schemas" / "dio.commercial_semantic_object.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual("DIO Commercial Semantic Object v1", schema["title"])
        self.assertEqual(SCHEMA, schema["properties"]["schema"]["const"])
        self.assertIn("semantic_value", schema["$defs"])


if __name__ == "__main__":
    unittest.main()
