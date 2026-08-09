from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if "msal" not in sys.modules:
    try:
        import msal as _msal  # noqa: F401
    except ModuleNotFoundError:
        sys.modules["msal"] = types.SimpleNamespace(
            SerializableTokenCache=object,
            PublicClientApplication=object,
        )

from commerce.expression_guarded import CommunicativeAct, render_expression  # noqa: E402
from commerce.semantic import commercial_semantic_object_from_lead  # noqa: E402
from commerce.semantic_judgement import (  # noqa: E402
    assert_mail_semantic_judgement_current,
    judge_mail_intent,
)
from scripts.manage_mail_intent import read_json, write_json  # noqa: E402
from scripts.sync_outlook_mail import create_outlook_draft, send_outlook_draft  # noqa: E402


class FakeGraph:
    def __init__(self, *, conversation_id: str = "THREAD-C5-GRAPH", recipient: str = "alex@example.org") -> None:
        self.conversation_id = conversation_id
        self.recipient = recipient
        self.calls: list[tuple[str, str, dict]] = []
        self.deleted: list[str] = []

    def json(self, method: str, resource: str, **kwargs):
        self.calls.append((method, resource, kwargs))
        if method == "POST" and resource.endswith("/createReply"):
            return {
                "id": "DRAFT-REPLY-1",
                "conversationId": self.conversation_id,
                "toRecipients": [{"emailAddress": {"address": self.recipient}}],
                "isDraft": True,
            }
        if method == "PATCH" and resource == "/me/messages/DRAFT-REPLY-1":
            return {
                "id": "DRAFT-REPLY-1",
                "conversationId": self.conversation_id,
                "toRecipients": [{"emailAddress": {"address": self.recipient}}],
                "isDraft": True,
            }
        if method == "POST" and resource == "/me/messages":
            return {
                "id": "DRAFT-NEW-1",
                "conversationId": "NEW-THREAD",
                "toRecipients": [{"emailAddress": {"address": self.recipient}}],
                "isDraft": True,
            }
        if method == "POST" and resource.endswith("/send"):
            return {}
        if method == "POST" and resource.endswith("/attachments"):
            return {"id": "ATTACHMENT-1"}
        return {}

    def request(self, method: str, resource: str, **kwargs):
        self.calls.append((method, resource, kwargs))
        if method == "DELETE":
            self.deleted.append(resource)
        return types.SimpleNamespace(content=b"")


class SemanticJudgementOutlookGateTests(unittest.TestCase):
    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def prepare_bound_intent(self, root: Path) -> tuple[dict, Path, Path]:
        lead = {
            "schema": "dio.lead.v1",
            "lead_id": "LEAD-C5-GRAPH",
            "conversation_id": "THREAD-C5-GRAPH",
            "product": "Evidex Evidence Packs",
            "offer": "bounded evidence-pack pilot",
            "contact": {"name": "Alex", "email": "alex@example.org", "organisation": "Example Org"},
            "request": {"subject": "Evidence pack request"},
            "consents": {"processing_authority_confirmed": False},
            "attribution": {"source": "outlook_direct", "medium": "email"},
            "state": "pending",
            "qualification": {"state": "pending"},
        }
        lead_path = root / "state/leads/LEAD-C5-GRAPH.json"
        context_path = root / "state/conversation_context/CTX-C5-GRAPH.json"
        self.write(lead_path, lead)
        self.write(context_path, {
            "schema": "test.context.state",
            "conversation_id": "THREAD-C5-GRAPH",
            "latest_source": "GRAPH-MESSAGE-1",
        })

        cso = commercial_semantic_object_from_lead(lead)
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        intent = {
            "schema": "dio.mail_intent.v1",
            "mail_intent_id": "MAIL-C5-GRAPH",
            "direction": "outbound",
            "purpose": "conversation_reply",
            "lead_id": "LEAD-C5-GRAPH",
            "conversation_id": "THREAD-C5-GRAPH",
            "source_message_id": "GRAPH-MESSAGE-1",
            "recipient": "alex@example.org",
            "subject": "Re: Evidence pack request",
            "body": expression["body"],
            "body_html": None,
            "body_path": None,
            "attachments": [],
            "risk": "moderate",
            "communicative_act": expression["communicative_act"],
            "semantic_binding": {
                "semantic_object_id": cso["object_id"],
                "conversation_context_id": "CTX-C5-GRAPH",
                "communicative_act": expression["communicative_act"],
                "conversation_context_authority": "expression_only",
                "source_ref": "mail_ingress:INGRESS-GRAPH-1",
            },
            "approval": {
                "required": True,
                "state": "pending",
                "approved_at": None,
                "expires_at": None,
                "token_sha256": None,
            },
            "send_state": "draft",
            "created_at": "2026-08-10T00:00:00+00:00",
            "updated_at": "2026-08-10T00:00:00+00:00",
        }
        judgement, judgement_path = judge_mail_intent(
            root,
            cso,
            expression,
            intent,
            source_paths=[lead_path, context_path],
        )
        intent["semantic_judgement"] = {
            "judgement_id": judgement["judgement_id"],
            "path": str(judgement_path.relative_to(root)),
            "verdict": judgement["verdict"],
        }
        intent_path = root / "state/mail_intents/MAIL-C5-GRAPH.json"
        write_json(intent_path, intent)
        return intent, lead_path, intent_path

    def test_conversation_reply_uses_create_reply_and_stays_in_judged_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, lead_path, intent_path = self.prepare_bound_intent(root)
            lead_before = lead_path.read_bytes()
            graph = FakeGraph()
            receipt = create_outlook_draft(
                graph,
                root / "state/mail_intents",
                root / "telemetry/events.jsonl",
                "MAIL-C5-GRAPH",
            )
            self.assertEqual("createReply", receipt["provider_draft_mode"])
            self.assertEqual("THREAD-C5-GRAPH", receipt["conversation_id"])
            self.assertTrue(any(method == "POST" and resource == "/me/messages/GRAPH-MESSAGE-1/createReply" for method, resource, _ in graph.calls))
            self.assertTrue(any(method == "PATCH" and resource == "/me/messages/DRAFT-REPLY-1" for method, resource, _ in graph.calls))
            self.assertFalse(any(method == "POST" and resource == "/me/messages" for method, resource, _ in graph.calls))
            self.assertEqual(lead_before, lead_path.read_bytes(), "Draft preparation must not mutate judged lead evidence")
            current = read_json(intent_path)
            self.assertIsNotNone(assert_mail_semantic_judgement_current(root, current, require_execution_ready=False))

    def test_reply_draft_with_wrong_thread_is_deleted_and_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_bound_intent(root)
            graph = FakeGraph(conversation_id="WRONG-THREAD")
            with self.assertRaisesRegex(ValueError, "conversation does not match"):
                create_outlook_draft(graph, root / "state/mail_intents", root / "telemetry/events.jsonl", "MAIL-C5-GRAPH")
            self.assertIn("/me/messages/DRAFT-REPLY-1", graph.deleted)

    def test_reply_draft_with_wrong_recipient_is_deleted_and_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_bound_intent(root)
            graph = FakeGraph(recipient="other@example.org")
            with self.assertRaisesRegex(ValueError, "recipient does not match"):
                create_outlook_draft(graph, root / "state/mail_intents", root / "telemetry/events.jsonl", "MAIL-C5-GRAPH")
            self.assertIn("/me/messages/DRAFT-REPLY-1", graph.deleted)

    def test_tampered_body_is_refused_before_graph_is_called(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_bound_intent(root)
            path = root / "state/mail_intents/MAIL-C5-GRAPH.json"
            intent = read_json(path)
            intent["body"] += " invented promise"
            write_json(path, intent)
            graph = FakeGraph()
            with self.assertRaisesRegex(ValueError, "SEMANTIC_JUDGEMENT_STALE"):
                create_outlook_draft(graph, root / "state/mail_intents", root / "telemetry/events.jsonl", "MAIL-C5-GRAPH")
            self.assertEqual([], graph.calls)

    def test_send_requires_both_current_judgement_and_human_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare_bound_intent(root)
            graph = FakeGraph()
            create_outlook_draft(graph, root / "state/mail_intents", root / "telemetry/events.jsonl", "MAIL-C5-GRAPH")
            path = root / "state/mail_intents/MAIL-C5-GRAPH.json"
            intent = read_json(path)
            token = "approval-token-c5"
            intent["approval"].update({
                "state": "approved",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            })
            intent["send_state"] = "approved"
            write_json(path, intent)
            receipt = send_outlook_draft(
                graph,
                root / "state/mail_intents",
                root / "state/mail_receipts",
                root / "telemetry/events.jsonl",
                "MAIL-C5-GRAPH",
                token,
            )
            self.assertTrue(receipt["approval_consumed"])
            self.assertTrue(receipt["semantic_judgement_id"].startswith("JUDGE-"))
            self.assertTrue(any(method == "POST" and resource == "/me/messages/DRAFT-REPLY-1/send" for method, resource, _ in graph.calls))

    def test_legacy_unbound_mail_keeps_pre_c5_draft_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intent = {
                "schema": "dio.mail_intent.v1",
                "mail_intent_id": "MAIL-LEGACY",
                "direction": "outbound",
                "purpose": "legacy_notice",
                "recipient": "alex@example.org",
                "subject": "Legacy",
                "body": "Legacy governed mail.",
                "body_html": None,
                "attachments": [],
                "approval": {"required": True, "state": "pending"},
                "send_state": "draft",
            }
            write_json(root / "state/mail_intents/MAIL-LEGACY.json", intent)
            graph = FakeGraph()
            receipt = create_outlook_draft(graph, root / "state/mail_intents", root / "telemetry/events.jsonl", "MAIL-LEGACY")
            self.assertEqual("new_message", receipt["provider_draft_mode"])
            self.assertIsNone(receipt["semantic_judgement_id"])
            self.assertTrue(any(method == "POST" and resource == "/me/messages" for method, resource, _ in graph.calls))


if __name__ == "__main__":
    unittest.main()
