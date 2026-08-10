from __future__ import annotations

import unittest

from commerce.mandos import commercial_outcome


class MandosAttestationIdentityTests(unittest.TestCase):
    @staticmethod
    def make(*, evidence_state: str, source_classes: list[str], source_states: list[dict] | None = None) -> dict:
        return commercial_outcome(
            outcome_type="reply_received",
            lineage={"lead_id": "LEAD-ATTEST-1"},
            source_refs=["mail_ingress:IN-ATTEST-1"],
            source_classes=source_classes,
            occurred_at="2026-08-10T10:00:00+00:00",
            polarity="positive",
            evidence_state=evidence_state,
            strategy={
                "product": "Evidex Evidence Packs",
                "offer": "bounded pilot",
                "communicative_act": "inbound_reply",
                "channel": "email",
            },
            source_states=source_states or [],
        )

    def test_observed_and_verified_attestations_get_distinct_outcome_ids_but_same_case(self) -> None:
        observed = self.make(evidence_state="observed", source_classes=["outlook_ingress"])
        verified = self.make(evidence_state="verified", source_classes=["outlook_ingress"])
        self.assertNotEqual(observed["outcome_id"], verified["outcome_id"])
        self.assertEqual(observed["case_id"], verified["case_id"])

    def test_different_evidence_class_is_a_distinct_epistemic_receipt(self) -> None:
        provider = self.make(evidence_state="verified", source_classes=["provider_event"])
        operator = self.make(evidence_state="verified", source_classes=["operator_confirmation"])
        self.assertNotEqual(provider["outcome_id"], operator["outcome_id"])
        self.assertEqual(provider["case_id"], operator["case_id"])

    def test_source_state_order_does_not_change_attestation_identity(self) -> None:
        one = {"path": "state/a.json", "sha256": "sha256:" + "a" * 64, "size": 10}
        two = {"path": "state/b.json", "sha256": "sha256:" + "b" * 64, "size": 20}
        left = self.make(evidence_state="verified", source_classes=["provider_event"], source_states=[one, two])
        right = self.make(evidence_state="verified", source_classes=["provider_event"], source_states=[two, one])
        self.assertEqual(left["outcome_id"], right["outcome_id"])
        self.assertEqual(left["evidence"]["source_states"], right["evidence"]["source_states"])


if __name__ == "__main__":
    unittest.main()
