import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphError, load_config  # noqa: E402
from scripts.manage_graph_subscription import redact_client_state, webhook_settings  # noqa: E402
from scripts.manage_mail_intent import approve_intent, create_intent, write_json  # noqa: E402
from scripts.sync_onedrive_jobs import safe_name  # noqa: E402
from scripts.sync_outlook_mail import create_outlook_draft, lead_reference, send_outlook_draft  # noqa: E402
from scripts.sync_dio_edge_events import materialize_public_intakes  # noqa: E402
from scripts.process_commerce_events import safe_component  # noqa: E402
from services.microsoft_graph_webhook import append_queue, notification_event, validate_notifications  # noqa: E402


class MailIntentTests(unittest.TestCase):
    def test_concurrent_mail_state_writes_are_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mail.json"
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda value: write_json(path, {"value": value}), range(40)))
            self.assertIn(json.loads(path.read_text(encoding="utf-8"))["value"], range(40))
            self.assertFalse(list(path.parent.glob(".mail.json.*.tmp")))

    def test_approval_stores_only_token_hash_and_valid_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            intent_dir = base / "intents"
            event_log = base / "events.jsonl"
            intent = create_intent(ROOT / "samples/mail/evidex_delivery_intent.json", intent_dir, event_log)
            approved, token = approve_intent(intent["mail_intent_id"], intent_dir, event_log, 10)

            self.assertGreaterEqual(len(token), 32)
            self.assertNotIn(token, (intent_dir / f"{intent['mail_intent_id']}.json").read_text(encoding="utf-8"))
            self.assertEqual("approved", approved["approval"]["state"])
            self.assertRegex(approved["approval"]["token_sha256"], r"^[a-f0-9]{64}$")

            intent_schema = json.loads((ROOT / "schemas/mail_intent.schema.json").read_text(encoding="utf-8"))
            event_schema = json.loads((ROOT / "schemas/dio_event.schema.json").read_text(encoding="utf-8"))
            jsonschema.validate(approved, intent_schema)
            events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(2, len(events))
            for event in events:
                jsonschema.validate(event, event_schema)
            self.assertEqual(events[0]["event_sha256"], events[1]["previous_event_sha256"])


class MicrosoftTransportTests(unittest.TestCase):
    def test_outlook_draft_uploads_governed_attachment(self):
        class FakeGraph:
            def __init__(self):
                self.calls = []

            def json(self, method, resource, **kwargs):
                self.calls.append((method, resource, kwargs))
                if resource == "/me/messages":
                    return {"id": "DRAFT-1", "conversationId": "THREAD-1"}
                return {"id": "ATTACHMENT-1"}

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            attachment = base / "review.zip"
            attachment.write_bytes(b"review-pack")
            spec = base / "mail.json"
            spec.write_text(json.dumps({
                "purpose": "delivery",
                "recipient": "author@example.org",
                "subject": "Your Sophia review",
                "body": "Attached for review.",
                "body_html": "<p>Attached for review.</p><p><a href=\"https://example.org/pay\">Pay securely</a></p>",
                "attachments": [str(attachment)],
            }), encoding="utf-8")
            intent_dir = base / "intents"
            event_log = base / "events.jsonl"
            intent = create_intent(spec, intent_dir, event_log)
            graph = FakeGraph()

            receipt = create_outlook_draft(graph, intent_dir, event_log, intent["mail_intent_id"])

            self.assertFalse(receipt["sent"])
            self.assertEqual("review.zip", receipt["attachments"][0]["name"])
            self.assertEqual("ATTACHMENT-1", receipt["attachments"][0]["provider_attachment_id"])
            self.assertEqual("/me/messages/DRAFT-1/attachments", graph.calls[1][1])
            self.assertEqual("HTML", graph.calls[0][2]["json"]["body"]["contentType"])
            self.assertIn("Pay securely", graph.calls[0][2]["json"]["body"]["content"])

    def test_approved_exact_draft_is_sent_and_lease_consumed(self):
        class FakeGraph:
            def __init__(self):
                self.calls = []

            def json(self, method, resource, **kwargs):
                self.calls.append((method, resource, kwargs))
                return {}

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            spec = base / "mail.json"
            spec.write_text(json.dumps({"purpose": "lead_acknowledgement", "recipient": "lead@example.org", "subject": "Thanks [HOMS-20260808-ABCDEF1234]", "body": "Received."}), encoding="utf-8")
            intent_dir = base / "intents"
            event_log = base / "events.jsonl"
            intent = create_intent(spec, intent_dir, event_log)
            intent_path = intent_dir / f"{intent['mail_intent_id']}.json"
            stored = json.loads(intent_path.read_text())
            stored["provider_draft_id"] = "DRAFT-EXACT-1"
            intent_path.write_text(json.dumps(stored), encoding="utf-8")
            _, token = approve_intent(intent["mail_intent_id"], intent_dir, event_log, 5)
            receipt = send_outlook_draft(FakeGraph(), intent_dir, base / "receipts", event_log, intent["mail_intent_id"], token)
            final = json.loads(intent_path.read_text())
            self.assertEqual("sent", final["send_state"])
            self.assertEqual("consumed", final["approval"]["state"])
            self.assertIsNone(final["approval"]["token_sha256"])
            self.assertEqual("DRAFT-EXACT-1", receipt["provider_draft_id"])

    def test_lead_reference_is_recovered_from_outlook_subject(self):
        self.assertEqual("SOPHIA-20260808-ABCDEF1234", lead_reference("Re: Thanks [sophia-20260808-abcdef1234]"))
        self.assertIsNone(lead_reference("Unrelated message"))

    def test_public_edge_event_materializes_lead_and_acknowledgement(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            created = materialize_public_intakes([{
                "id": 7,
                "source": "public_intake",
                "event_type": "public.intake.received",
                "received_at": "2026-08-08T12:00:00+00:00",
                "payload": {
                    "lead_id": "VAMP-20260808-ABCDEF1234",
                    "envelope": {
                        "schema": "dio.public_intake.v1",
                        "product": "vamp",
                        "offer": "performance_evidence_snapshot",
                        "contact": {"name": "Reviewer", "email": "reviewer@example.org"},
                        "request": {"scope": "One bounded review"},
                        "consents": {"authorised": True},
                        "attribution": {"source": "vamp_site"},
                        "submitted_at": "2026-08-08T12:00:00+00:00",
                    },
                },
            }], base / "leads", base / "intents", base / "events.jsonl")
            self.assertEqual(1, created)
            lead = json.loads((base / "leads" / "VAMP-20260808-ABCDEF1234.json").read_text())
            self.assertEqual("pending", lead["qualification"]["state"])
            intent_path = base / "intents" / f"{lead['acknowledgement']['mail_intent_id']}.json"
            self.assertIn("VAMP-20260808-ABCDEF1234", json.loads(intent_path.read_text())["subject"])

    def test_onedrive_names_cannot_escape_mirror(self):
        self.assertEqual("HOMS-JOB-001", safe_name("HOMS-JOB-001"))
        for unsafe in ["../escape", "a/b", "..", "a\\b"]:
            with self.assertRaises(ValueError):
                safe_name(unsafe)

    def test_commerce_ids_cannot_escape_state_directory(self):
        self.assertEqual("INVOICE-001", safe_component("INVOICE-001"))
        self.assertEqual("escape", safe_component("../../escape"))

    def test_placeholder_graph_config_refuses_authentication(self):
        with self.assertRaises(GraphError):
            load_config(ROOT / "config/microsoft_graph.example.json")

    def test_placeholder_webhook_url_cannot_create_subscription(self):
        config = json.loads((ROOT / "config/microsoft_graph.example.json").read_text(encoding="utf-8"))
        with self.assertRaises(GraphError):
            webhook_settings(config)

    def test_subscription_output_redacts_client_state(self):
        result = redact_client_state({"clientState": "sensitive", "value": [{"clientState": None}]})
        self.assertEqual("[REDACTED]", result["clientState"])
        self.assertIsNone(result["value"][0]["clientState"])

    def test_webhook_queue_validates_and_removes_client_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            queue_path = Path(temporary) / "notifications.jsonl"
            raw = {
                "clientState": "x" * 48,
                "subscriptionId": "SUB-1",
                "changeType": "created",
                "resource": "me/messages/MSG-1",
                "resourceData": {"id": "MSG-1"},
            }
            accepted = validate_notifications([raw], "x" * 48)
            self.assertNotIn("clientState", accepted[0])
            append_queue(queue_path, accepted)
            self.assertNotIn("clientState", queue_path.read_text(encoding="utf-8"))
            event = notification_event(accepted[0], lifecycle=False)
            self.assertEqual("mail.notification_received", event[0])
            self.assertEqual("MSG-1", event[3])

    def test_webhook_rejects_wrong_client_state(self):
        with self.assertRaises(PermissionError):
            validate_notifications([{"clientState": "wrong"}], "x" * 48)


if __name__ == "__main__":
    unittest.main()
