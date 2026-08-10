from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from commerce.mandos import MandosLedger, commercial_outcome, summarize_economics
from commerce.mandos_feedback import campaign_feedback


class MandosEconomicsTests(unittest.TestCase):
    @staticmethod
    def paid(
        *,
        lead_id: str,
        order_id: str,
        evidence_state: str,
        source_class: str,
        currency: str = "ZAR",
        revenue_minor: int = 95000,
        campaign_id: str = "CMP-ECON-1",
    ) -> dict:
        return commercial_outcome(
            outcome_type="paid_order",
            lineage={
                "lead_id": lead_id,
                "order_id": order_id,
                "campaign_id": campaign_id,
            },
            source_refs=[f"order:{order_id}"],
            source_classes=[source_class],
            occurred_at="2026-08-10T10:00:00+00:00",
            polarity="positive",
            evidence_state=evidence_state,
            strategy={
                "product": "Evidex Evidence Packs",
                "offer": "bounded pilot",
                "communicative_act": "proposal",
                "channel": "email",
            },
            economics={"currency": currency, "revenue_minor": revenue_minor},
            detail={"provider": "paypal", "payment_state": "paid"},
        )

    def test_two_attestations_of_same_payment_count_one_coin(self) -> None:
        observed = self.paid(
            lead_id="LEAD-1",
            order_id="ORDER-1",
            evidence_state="observed",
            source_class="local_order_state",
        )
        verified = self.paid(
            lead_id="LEAD-1",
            order_id="ORDER-1",
            evidence_state="verified",
            source_class="provider_payment_event",
        )
        self.assertNotEqual(observed["outcome_id"], verified["outcome_id"])
        summary = summarize_economics([observed, verified])
        self.assertEqual("single_currency", summary["aggregation_state"])
        self.assertEqual("ZAR", summary["currency"])
        self.assertEqual(95000, summary["revenue_minor"])
        self.assertEqual(1, summary["economic_event_count"])
        self.assertTrue(summary["attestation_deduplication"])

    def test_mixed_currencies_are_partitioned_not_added(self) -> None:
        zar = self.paid(
            lead_id="LEAD-1",
            order_id="ORDER-ZAR",
            evidence_state="verified",
            source_class="provider_payment_event",
            currency="ZAR",
            revenue_minor=95000,
        )
        usd = self.paid(
            lead_id="LEAD-2",
            order_id="ORDER-USD",
            evidence_state="verified",
            source_class="provider_payment_event",
            currency="USD",
            revenue_minor=1000,
        )
        summary = summarize_economics([zar, usd])
        self.assertEqual("mixed_currency_not_aggregated", summary["aggregation_state"])
        self.assertIsNone(summary["currency"])
        self.assertEqual(0, summary["revenue_minor"])
        self.assertEqual(95000, summary["by_currency"]["ZAR"]["revenue_minor"])
        self.assertEqual(1000, summary["by_currency"]["USD"]["revenue_minor"])
        self.assertEqual(2, summary["economic_event_count"])

    def test_pattern_economics_deduplicates_epistemic_attestations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.paid(
                lead_id="LEAD-1",
                order_id="ORDER-1",
                evidence_state="operator_confirmed",
                source_class="operator_order_review",
            ))
            verified, _ = ledger.record(self.paid(
                lead_id="LEAD-1",
                order_id="ORDER-1",
                evidence_state="verified",
                source_class="provider_payment_event",
            ))
            pattern = ledger.pattern(verified["strategy"]["pattern_key"])
            self.assertEqual(2, pattern["evidence_summary"]["verified_outcomes"])
            self.assertEqual(1, pattern["evidence_summary"]["verified_cases"])
            self.assertEqual(95000, pattern["economics"]["revenue_minor"])
            self.assertEqual(1, pattern["economics"]["economic_event_count"])

    def test_campaign_measurement_summary_does_not_stack_direct_order_revenue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.paid(
                lead_id="LEAD-1",
                order_id="ORDER-1",
                evidence_state="verified",
                source_class="provider_payment_event",
                revenue_minor=95000,
            ))
            ledger.record(commercial_outcome(
                outcome_type="campaign_measurement",
                lineage={"campaign_id": "CMP-ECON-1"},
                source_refs=["market_measurement:MEASURE-1"],
                source_classes=["market_measurement"],
                occurred_at="2026-08-10T12:00:00+00:00",
                polarity="positive",
                evidence_state="verified",
                strategy={
                    "product": "EVIDEX",
                    "offer": "bounded pilot",
                    "communicative_act": "proof_led_campaign_content",
                    "channel": "proof_content",
                },
                economics={"currency": "ZAR", "revenue_minor": 95000, "cost_minor": 1000},
                detail={"paid_orders": 1},
            ))
            feedback = campaign_feedback(root, "CMP-ECON-1")
            self.assertEqual("market_measurement_ledger_preferred_to_avoid_overlap", feedback["economics_basis"])
            self.assertEqual(95000, feedback["economics"]["revenue_minor"])
            self.assertEqual(95000, feedback["economics_views"]["direct_events"]["revenue_minor"])
            self.assertEqual(95000, feedback["economics_views"]["market_measurements"]["revenue_minor"])
            self.assertTrue(feedback["economics_views"]["views_are_not_additive"])
            self.assertFalse(feedback["authority"]["economic_views_may_be_added_together"])

    def test_provenance_collection_order_does_not_change_outcome_identity(self) -> None:
        left = commercial_outcome(
            outcome_type="reply_received",
            lineage={"lead_id": "LEAD-PROV-1"},
            source_refs=["source:b", "source:a"],
            source_classes=["class:b", "class:a"],
            occurred_at="2026-08-10T10:00:00+00:00",
            strategy={"product": "Evidex", "communicative_act": "inbound_reply", "channel": "email"},
        )
        right = commercial_outcome(
            outcome_type="reply_received",
            lineage={"lead_id": "LEAD-PROV-1"},
            source_refs=["source:a", "source:b"],
            source_classes=["class:a", "class:b"],
            occurred_at="2026-08-10T10:00:00+00:00",
            strategy={"product": "Evidex", "communicative_act": "inbound_reply", "channel": "email"},
        )
        self.assertEqual(left["outcome_id"], right["outcome_id"])
        self.assertEqual(["source:a", "source:b"], left["evidence"]["source_refs"])
        self.assertEqual(["class:a", "class:b"], left["evidence"]["source_classes"])


if __name__ == "__main__":
    unittest.main()
