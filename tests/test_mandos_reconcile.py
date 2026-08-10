from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from commerce.mandos import MandosLedger
from commerce.mandos_reconcile import reconcile_transaction


class MandosReconcileTests(unittest.TestCase):
    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def transaction(*, lead_id: str = "LEAD-R-1", stage: str = "qualified", order_id: str | None = None, order_path: str | None = None) -> dict:
        return {
            "schema": "dio.commercial_transaction.v1",
            "transaction_id": f"TXN-{lead_id}",
            "created_at": "2026-08-10T08:00:00+00:00",
            "updated_at": "2026-08-10T12:00:00+00:00",
            "product": "Evidex Evidence Packs",
            "offer": "bounded pilot",
            "stage": stage,
            "lineage": {
                "lead_id": lead_id,
                "conversation_id": f"THREAD-{lead_id}",
                "campaign_id": "CMP-MANDOS-R",
                "job_id": None,
                "order_id": order_id,
                "mail_intent_ids": [f"MAIL-{lead_id}"],
            },
            "intake": {"message_ids": [f"IN-{lead_id}"], "attachments": []},
            "source_paths": {"orders": [order_path] if order_path else [], "jobs": []},
        }

    def test_sent_mail_followed_by_inbound_becomes_reply_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tx = self.transaction()
            self.write(root / "state/mail_intents/MAIL-LEAD-R-1.json", {
                "mail_intent_id": "MAIL-LEAD-R-1",
                "send_state": "sent",
                "sent_at": "2026-08-10T09:00:00+00:00",
                "purpose": "conversation_reply",
                "communicative_act": "inbound_reply",
                "conversation_id": "THREAD-LEAD-R-1",
                "semantic_binding": {"semantic_object_id": "CSO-R-1", "communicative_act": "inbound_reply"},
                "semantic_judgement": {"judgement_id": "JUDGE-R-1"},
            })
            self.write(root / "state/mail_ingress/IN-LEAD-R-1.json", {
                "mail_ingress_id": "IN-LEAD-R-1",
                "conversation_id": "THREAD-LEAD-R-1",
                "received_at": "2026-08-10T10:00:00+00:00",
            })
            result = reconcile_transaction(root, tx)
            self.assertGreaterEqual(len(result["created"]), 2)
            outcomes = MandosLedger(root).outcomes()
            reply = next(row for row in outcomes if row["outcome_type"] == "reply_received")
            self.assertEqual("MAIL-LEAD-R-1", reply["lineage"]["mail_intent_id"])
            self.assertEqual("JUDGE-R-1", reply["lineage"]["semantic_judgement_id"])
            self.assertEqual("positive", reply["polarity"])

    def test_inbound_before_send_is_not_reply_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tx = self.transaction()
            self.write(root / "state/mail_intents/MAIL-LEAD-R-1.json", {
                "mail_intent_id": "MAIL-LEAD-R-1",
                "send_state": "sent",
                "sent_at": "2026-08-10T11:00:00+00:00",
                "purpose": "conversation_reply",
                "communicative_act": "inbound_reply",
            })
            self.write(root / "state/mail_ingress/IN-LEAD-R-1.json", {
                "mail_ingress_id": "IN-LEAD-R-1",
                "conversation_id": "THREAD-LEAD-R-1",
                "received_at": "2026-08-10T10:00:00+00:00",
            })
            reconcile_transaction(root, tx)
            self.assertFalse(any(row["outcome_type"] == "reply_received" for row in MandosLedger(root).outcomes()))

    def test_delivery_reply_becomes_delivery_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tx = self.transaction()
            self.write(root / "state/mail_intents/MAIL-LEAD-R-1.json", {
                "mail_intent_id": "MAIL-LEAD-R-1",
                "send_state": "sent",
                "sent_at": "2026-08-10T09:00:00+00:00",
                "purpose": "delivery",
                "communicative_act": "delivery",
                "conversation_id": "THREAD-LEAD-R-1",
            })
            self.write(root / "state/mail_ingress/IN-LEAD-R-1.json", {
                "mail_ingress_id": "IN-LEAD-R-1",
                "conversation_id": "THREAD-LEAD-R-1",
                "received_at": "2026-08-10T10:00:00+00:00",
            })
            reconcile_transaction(root, tx)
            types = {row["outcome_type"] for row in MandosLedger(root).outcomes()}
            self.assertIn("delivery_sent", types)
            self.assertIn("reply_received", types)
            self.assertIn("delivery_acknowledged", types)

    def test_operator_qualification_is_remembered_as_operator_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tx = self.transaction()
            self.write(root / "state/leads/LEAD-R-1.json", {
                "lead_id": "LEAD-R-1",
                "qualification": {
                    "state": "qualified",
                    "decided_at": "2026-08-10T10:30:00+00:00",
                    "decided_by": "DIO operator via control deck",
                },
            })
            self.write(root / "state/mail_intents/MAIL-LEAD-R-1.json", {
                "mail_intent_id": "MAIL-LEAD-R-1",
                "send_state": "draft",
                "purpose": "conversation_reply",
                "communicative_act": "inbound_reply",
            })
            self.write(root / "state/mail_ingress/IN-LEAD-R-1.json", {
                "mail_ingress_id": "IN-LEAD-R-1",
                "received_at": "2026-08-10T08:00:00+00:00",
            })
            reconcile_transaction(root, tx)
            row = next(item for item in MandosLedger(root).outcomes() if item["outcome_type"] == "qualification_changed")
            self.assertEqual("operator_confirmed", row["evidence"]["state"])
            self.assertEqual("qualified", row["detail"]["qualification_state"])

    def test_provider_backed_paid_order_records_revenue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            order_path = root / "state/commerce/orders/ORDER-1.json"
            self.write(order_path, {
                "order_id": "ORDER-1",
                "payment_state": "paid",
                "provider": "paypal",
                "provider_event_id": "EVENT-1",
                "amount_minor": 95000,
                "currency": "ZAR",
            })
            self.write(root / "state/commerce/payment_events/paypal-EVENT-1.json", {
                "received_at": "2026-08-10T11:00:00+00:00",
                "payload": {
                    "provider_event_id": "EVENT-1",
                    "create_time": "2026-08-10T10:59:00+00:00",
                    "amount_minor": 95000,
                    "currency": "ZAR",
                    "outcome": "paid",
                },
            })
            tx = self.transaction(order_id="ORDER-1", order_path=str(order_path))
            self.write(root / "state/mail_intents/MAIL-LEAD-R-1.json", {
                "mail_intent_id": "MAIL-LEAD-R-1",
                "send_state": "draft",
                "purpose": "proposal",
                "communicative_act": "proposal",
            })
            self.write(root / "state/mail_ingress/IN-LEAD-R-1.json", {
                "mail_ingress_id": "IN-LEAD-R-1",
                "received_at": "2026-08-10T08:00:00+00:00",
            })
            reconcile_transaction(root, tx)
            paid = next(row for row in MandosLedger(root).outcomes() if row["outcome_type"] == "paid_order")
            self.assertEqual(95000, paid["economics"]["revenue_minor"])
            self.assertEqual("ZAR", paid["economics"]["currency"])
            self.assertIn("provider_payment_event", paid["evidence"]["source_classes"])

    def test_reconciliation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tx = self.transaction()
            self.write(root / "state/mail_intents/MAIL-LEAD-R-1.json", {
                "mail_intent_id": "MAIL-LEAD-R-1",
                "send_state": "sent",
                "sent_at": "2026-08-10T09:00:00+00:00",
                "purpose": "conversation_reply",
                "communicative_act": "inbound_reply",
            })
            self.write(root / "state/mail_ingress/IN-LEAD-R-1.json", {
                "mail_ingress_id": "IN-LEAD-R-1",
                "received_at": "2026-08-10T10:00:00+00:00",
            })
            first = reconcile_transaction(root, tx)
            second = reconcile_transaction(root, tx)
            self.assertTrue(first["created"])
            self.assertEqual([], second["created"])
            self.assertEqual(set(first["created"]), set(second["reused"]))
            self.assertTrue(MandosLedger(root).verify_journal()["valid"])


if __name__ == "__main__":
    unittest.main()
