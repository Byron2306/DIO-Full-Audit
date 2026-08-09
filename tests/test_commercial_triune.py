from __future__ import annotations

import base64
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.orchestrator import CommercialOrchestrator  # noqa: E402
from commerce.triune import assess_transaction, harmonic_assessment  # noqa: E402
from scripts.sync_outlook_mail import capture_message_attachments  # noqa: E402


class CommercialTriuneTests(unittest.TestCase):
    def test_payment_integrity_failure_vetoes_progress(self) -> None:
        transaction = {
            "stage": "paid",
            "product": "sophia",
            "lineage": {"lead_id": "LEAD-1", "conversation_id": "THREAD-1", "job_id": "JOB-1", "order_id": "ORDER-1"},
            "intake": {"meaningful_input": True, "attachments": [], "attachments_untrusted": False},
            "payment": {"state": "amount_mismatch"},
            "review_approved": False,
            "consents": {"processing_authority": True},
            "signals": {"stage_confidence": 1.0},
            "event_times": [],
        }

        decision = assess_transaction(transaction)

        self.assertEqual("BLOCK", decision["verdict"])
        self.assertIn("PAYMENT_INTEGRITY_FAILURE", {row["code"] for row in decision["loki"]["challenges"]})

    def test_harmonic_layer_detects_burst_discord(self) -> None:
        result = harmonic_assessment({
            "stage": "processing",
            "updated_at": "2026-08-09T10:00:00+00:00",
            "event_times": [
                "2026-08-09T10:00:00+00:00",
                "2026-08-09T10:00:01+00:00",
                "2026-08-09T10:00:02+00:00",
                "2026-08-09T10:30:00+00:00",
            ],
            "signals": {"duplicate_messages": 4},
        })

        self.assertGreaterEqual(result["discord_score"], 0.4)
        self.assertIn(result["mode_recommendation"], {"inspect_transition", "slow_and_gate", "follow_up_or_close"})


class MailAttachmentCaptureTests(unittest.TestCase):
    def test_file_is_hashed_private_and_quarantined(self) -> None:
        class FakeGraph:
            def json(self, method: str, resource: str):
                self.method = method
                self.resource = resource
                return {"value": [{
                    "id": "ATTACH-1",
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": "../../review.exe",
                    "contentType": "application/octet-stream",
                    "size": 12,
                    "isInline": False,
                    "contentBytes": base64.b64encode(b"not-executed").decode("ascii"),
                }]}

        with tempfile.TemporaryDirectory() as temporary:
            receipt = capture_message_attachments(FakeGraph(), "MESSAGE-1", "INGRESS-1", Path(temporary))
            captured = Path(receipt[0]["path"])

            self.assertEqual("captured_quarantined", receipt[0]["capture_state"])
            self.assertEqual("captured_untrusted", receipt[0]["trust_state"])
            self.assertEqual("review.exe", captured.name)
            self.assertEqual(b"not-executed", captured.read_bytes())
            self.assertEqual(stat.S_IMODE(captured.stat().st_mode), 0o600)


class CommercialOrchestratorTests(unittest.TestCase):
    def test_direct_mail_creates_reviewable_transaction_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state" / "mail_ingress").mkdir(parents=True)
            (root / "config").mkdir(parents=True)
            (root / "config" / "routes.json").write_text(json.dumps({"routes": [{
                "product": "sophia",
                "priority": 10,
                "keywords": ["literature review", "dissertation"],
                "approval_required": True,
            }]}), encoding="utf-8")
            ingress_path = root / "state" / "mail_ingress" / "INGRESS-1.json"
            ingress_path.write_text(json.dumps({
                "schema": "dio.mail_ingress.v1",
                "mail_ingress_id": "INGRESS-1",
                "provider": "microsoft_graph",
                "provider_message_id": "MESSAGE-1",
                "conversation_id": "THREAD-1",
                "received_at": "2026-08-09T12:00:00+00:00",
                "captured_at": "2026-08-09T12:00:01+00:00",
                "sender": {"name": "Researcher", "address": "researcher@example.org"},
                "subject": "Dissertation literature review",
                "body": {"contentType": "text", "content": "Please review the literature section of my dissertation."},
                "body_preview": "Please review the literature section.",
                "attachments": [],
                "routing_state": "pending_triage",
            }), encoding="utf-8")

            first = CommercialOrchestrator(root).run(stage_jobs=True)
            second = CommercialOrchestrator(root).run(stage_jobs=True)

            leads = list((root / "state" / "leads").glob("*.json"))
            transactions = list((root / "state" / "transactions").glob("*/TRANSACTION.json"))
            ingress = json.loads(ingress_path.read_text(encoding="utf-8"))
            transaction = json.loads(transactions[0].read_text(encoding="utf-8"))
            events = [json.loads(line) for line in (root / "telemetry" / "dio_events.jsonl").read_text(encoding="utf-8").splitlines()]

            self.assertEqual(1, len(leads))
            self.assertEqual(1, len(transactions))
            self.assertEqual("bound_to_transaction", ingress["routing_state"])
            self.assertTrue((ingress["triage"].get("staged_job") or {}).get("job_id"))
            self.assertEqual("qualification_pending", transaction["stage"])
            self.assertEqual(1, sum(event["event"] == "lead.created_from_mail" for event in events))
            self.assertEqual(1, sum(event["event"] == "job.staged_from_mail" for event in events))
            self.assertEqual(1, sum(event["event"] == "commercial.triune_assessed" for event in events))
            self.assertEqual(1, first["triage"]["staged"])
            self.assertEqual(0, second["triage"]["staged"])


if __name__ == "__main__":
    unittest.main()
