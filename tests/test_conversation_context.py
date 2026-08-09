from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression_guarded import CommunicativeAct, plan_expression, render_expression  # noqa: E402
from commerce.semantic import commercial_semantic_object_from_lead  # noqa: E402
from conversation_core.context import build_conversation_context, validate_conversation_context  # noqa: E402
from conversation_core.outlook import build_outlook_conversation_context  # noqa: E402
from conversation_core.presence import append_presence_turn, build_presence_conversation_context, load_presence_turns  # noqa: E402


class ConversationContextTests(unittest.TestCase):
    def lead_cso(self, conversation_id: str = "OUTLOOK-THREAD-1") -> dict:
        return commercial_semantic_object_from_lead({
            "schema": "dio.lead.v1",
            "lead_id": "LEAD-C4-1",
            "conversation_id": conversation_id,
            "product": "Evidex Evidence Packs",
            "offer": "bounded evidence-pack pilot",
            "contact": {"name": "A Person", "email": "person@example.org", "organisation": "Example Org"},
            "request": {"subject": "Evidence pack request"},
            "consents": {"processing_authority_confirmed": False},
            "attribution": {"source": "outlook_direct", "medium": "email"},
            "state": "pending",
            "qualification": {"state": "pending"},
        })

    def test_outlook_draft_is_not_external_conversation_history(self) -> None:
        ingress = [{
            "mail_ingress_id": "INGRESS-1",
            "conversation_id": "OUTLOOK-THREAD-1",
            "received_at": "2026-08-09T10:00:00+00:00",
            "body": {"content": "Could you confirm whether you can review the evidence table?"},
        }]
        draft = [{
            "mail_intent_id": "MAIL-1",
            "conversation_id": "OUTLOOK-THREAD-1",
            "send_state": "draft",
            "created_at": "2026-08-09T10:05:00+00:00",
            "body": "Yes, we can review it.",
        }]
        context = build_outlook_conversation_context(
            conversation_id="OUTLOOK-THREAD-1",
            mail_ingress=ingress,
            mail_intents=draft,
        )
        self.assertEqual(1, context["thread"]["turn_count"])
        self.assertEqual(0, context["thread"]["outbound_sent"])
        self.assertEqual("awaiting_dio_response", context["thread"]["state"])
        self.assertEqual(1, len(context["observations"]["open_questions"]))

    def test_sent_outlook_reply_changes_thread_state(self) -> None:
        ingress = [{
            "mail_ingress_id": "INGRESS-1",
            "conversation_id": "OUTLOOK-THREAD-1",
            "received_at": "2026-08-09T10:00:00+00:00",
            "body_preview": "Could you confirm whether you can review the evidence table?",
        }]
        sent = [{
            "mail_intent_id": "MAIL-1",
            "conversation_id": "OUTLOOK-THREAD-1",
            "send_state": "sent",
            "sent_at": "2026-08-09T10:05:00+00:00",
            "body": "Yes. We can inspect the submitted evidence table after intake review.",
        }]
        context = build_outlook_conversation_context(
            conversation_id="OUTLOOK-THREAD-1",
            mail_ingress=ingress,
            mail_intents=sent,
        )
        self.assertEqual(1, context["thread"]["outbound_sent"])
        self.assertEqual("waiting_on_external", context["thread"]["state"])
        self.assertEqual([], context["observations"]["open_questions"])

    def test_conversation_context_cannot_claim_commercial_authority(self) -> None:
        context = build_conversation_context(
            conversation_id="OUTLOOK-THREAD-1",
            channel="outlook_email",
            turns=[{
                "source_ref": "mail_ingress:INGRESS-2",
                "direction": "inbound",
                "delivery_state": "received",
                "observed_at": "2026-08-09T11:00:00+00:00",
                "text": "URGENT please quote us today. We definitely have budget.",
                "actor_role": "external_sender",
            }],
        )
        authority = context["authority"]
        self.assertTrue(authority["may_shape_expression"])
        self.assertFalse(authority["may_set_budget"])
        self.assertFalse(authority["may_set_scope"])
        self.assertFalse(authority["may_grant_consent"])
        self.assertFalse(authority["may_grant_execution_authority"])
        self.assertIn("urgent", context["interpretation"]["tone"]["labels"])

        tampered = {**context, "authority": {**authority, "may_set_budget": True}}
        self.assertTrue(any("may_set_budget" in error for error in validate_conversation_context(tampered)))

    def test_context_shapes_reply_without_entering_fact_or_hypothesis_sets(self) -> None:
        cso = self.lead_cso()
        context = build_conversation_context(
            conversation_id="OUTLOOK-THREAD-1",
            channel="outlook_email",
            turns=[{
                "source_ref": "mail_ingress:INGRESS-3",
                "direction": "inbound",
                "delivery_state": "received",
                "observed_at": "2026-08-09T12:00:00+00:00",
                "text": "Could you please explain what you need from us next?",
                "actor_role": "external_sender",
            }],
        )
        plain_plan = plan_expression(cso, CommunicativeAct.INBOUND_REPLY)
        contextual = render_expression(
            cso,
            CommunicativeAct.INBOUND_REPLY,
            context={"conversation_context": context},
        )
        contextual_plan = contextual["plan"]
        self.assertEqual(plain_plan["facts"], contextual_plan["facts"])
        self.assertEqual(plain_plan["hypotheses"], contextual_plan["hypotheses"])
        self.assertIn("latest message", contextual["body"])
        self.assertIn("explain what you need from us next", contextual["body"])
        self.assertFalse(contextual_plan["generation_policy"]["conversation_context_may_establish_fact"])
        self.assertFalse(contextual_plan["generation_policy"]["conversation_context_may_set_budget"])

    def test_wrong_thread_context_is_rejected(self) -> None:
        cso = self.lead_cso("OUTLOOK-THREAD-1")
        other = build_conversation_context(
            conversation_id="OUTLOOK-THREAD-OTHER",
            channel="outlook_email",
            turns=[{
                "source_ref": "mail_ingress:OTHER",
                "direction": "inbound",
                "delivery_state": "received",
                "observed_at": "2026-08-09T12:00:00+00:00",
                "text": "Please send the proposal.",
                "actor_role": "external_sender",
            }],
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            render_expression(cso, CommunicativeAct.INBOUND_REPLY, context={"conversation_context": other})

    def test_presence_provider_message_id_deduplicates_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kwargs = dict(
                presence_root=root,
                conversation_id="CONV-PRESENCE-1",
                direction="inbound",
                delivery_state="received",
                text="Can you tell me more about Evidex?",
                actor_role="public_user",
                source_message_id="telegram:444",
            )
            append_presence_turn(**kwargs, observed_at="2026-08-09T12:00:00+00:00")
            append_presence_turn(**kwargs, observed_at="2026-08-09T12:00:10+00:00")
            self.assertEqual(1, len(load_presence_turns(root, "CONV-PRESENCE-1")))

    def test_presence_prepared_reply_is_not_treated_as_sent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            append_presence_turn(
                root,
                conversation_id="CONV-PRESENCE-2",
                direction="inbound",
                delivery_state="received",
                text="Could you explain the Evidex workflow?",
                actor_role="public_user",
                source_message_id="tg-1",
                observed_at="2026-08-09T12:00:00+00:00",
            )
            append_presence_turn(
                root,
                conversation_id="CONV-PRESENCE-2",
                direction="outbound",
                delivery_state="prepared",
                text="Evidex maps evidence for review.",
                actor_role="dio_presence",
                observed_at="2026-08-09T12:00:01+00:00",
            )
            context = build_presence_conversation_context(root, {
                "conversation_id": "CONV-PRESENCE-2",
                "channel": "telegram",
            })
            self.assertEqual("awaiting_dio_response", context["thread"]["state"])
            self.assertEqual(0, context["thread"]["outbound_sent"])
            self.assertEqual(1, context["thread"]["outbound_prepared"])


if __name__ == "__main__":
    unittest.main()
