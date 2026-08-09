from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import httpx as _httpx  # noqa: F401
except ModuleNotFoundError:
    sys.modules["httpx"] = types.SimpleNamespace()

from presence_core.persona import apply_persona_response, load_public_profile  # noqa: E402
from presence_core.router import route_message  # noqa: E402
from scripts.reconcile_conversation_context import reconcile_conversation_contexts  # noqa: E402


class ConversationReconciliationTests(unittest.TestCase):
    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_reconciler_uses_received_and_sent_outlook_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root / "state/mail_ingress/IN-1.json", {
                "schema": "dio.mail_ingress.v1",
                "mail_ingress_id": "IN-1",
                "conversation_id": "THREAD-1",
                "received_at": "2026-08-09T10:00:00+00:00",
                "body_preview": "Could you confirm the next step?",
            })
            self.write(root / "state/mail_intents/DRAFT.json", {
                "mail_intent_id": "DRAFT",
                "conversation_id": "THREAD-1",
                "send_state": "draft",
                "created_at": "2026-08-09T10:01:00+00:00",
                "body": "Draft answer that the customer has not seen.",
            })
            receipt = reconcile_conversation_contexts(root)
            self.assertEqual(1, receipt["outlook"])
            index = json.loads((root / "state/conversation_context/INDEX.json").read_text(encoding="utf-8"))
            row = index["contexts"]["THREAD-1"]
            context = json.loads((root / row["path"]).read_text(encoding="utf-8"))
            self.assertEqual("awaiting_dio_response", context["thread"]["state"])
            self.assertEqual(0, context["thread"]["outbound_sent"])
            self.assertNotIn("Draft answer", json.dumps(context))

    def test_reconciler_can_seed_presence_context_from_existing_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root / "state/presence/conversations/CONV-1.json", {
                "schema": "dio.presence_conversation.v1",
                "conversation_id": "CONV-1",
                "channel": "telegram",
            })
            self.write(root / "state/presence/intakes/PRES-1.json", {
                "schema": "dio.presence_intake.v2",
                "intake_id": "PRES-1",
                "conversation_id": "CONV-1",
                "summary": "Please prepare an Evidex evidence pack for review.",
                "created_at": "2026-08-09T11:00:00+00:00",
            })
            receipt = reconcile_conversation_contexts(root)
            self.assertEqual(1, receipt["presence"])
            index = json.loads((root / "state/conversation_context/INDEX.json").read_text(encoding="utf-8"))
            row = index["contexts"]["CONV-1"]
            context = json.loads((root / row["path"]).read_text(encoding="utf-8"))
            self.assertEqual("telegram", context["channel"])
            self.assertEqual("awaiting_dio_response", context["thread"]["state"])
            self.assertIn("prepare an Evidex evidence pack", context["observations"]["last_requested_action"]["text"])

    def test_vesper_is_public_name_and_lilith_remains_legacy_alias(self) -> None:
        profile = load_public_profile(ROOT)
        self.assertEqual("Vesper", profile["name"])
        self.assertIn("Lilith", profile["legacy_aliases"])

        result = {"reply": {"text": "I’m Lilith, DIO’s public concierge."}}
        renamed = apply_persona_response(result, ROOT)
        self.assertIn("Vesper", renamed["reply"]["text"])
        self.assertNotIn("Lilith", renamed["reply"]["text"])
        self.assertEqual("Lilith", renamed["presence"]["legacy_codename"])

    def test_router_accepts_vesper_and_legacy_lilith_operator_invocations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            routes = Path(tmp) / "routes.json"
            routes.write_text(json.dumps({"routes": []}), encoding="utf-8")
            vesper = route_message("morning vesper", "operator", routes)
            lilith = route_message("morning lilith", "operator", routes)
            self.assertEqual("operator_summary", vesper.intent)
            self.assertEqual("operator_summary", lilith.intent)


if __name__ == "__main__":
    unittest.main()
