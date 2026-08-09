from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression_guarded import CommunicativeAct, render_expression  # noqa: E402
from commerce.semantic import commercial_semantic_object_from_lead, semantic_value  # noqa: E402
from commerce.semantic_judgement import (  # noqa: E402
    assert_mail_semantic_judgement_current,
    judge_expression,
    judge_mail_intent,
    mail_execution_digest,
)


class SemanticJudgementTests(unittest.TestCase):
    def cso(self, *, conversation_id: str = "THREAD-C5-1") -> dict:
        return commercial_semantic_object_from_lead({
            "schema": "dio.lead.v1",
            "lead_id": "LEAD-C5-1",
            "conversation_id": conversation_id,
            "product": "Evidex Evidence Packs",
            "offer": "bounded evidence-pack pilot",
            "contact": {
                "name": "Alex",
                "email": "alex@example.org",
                "organisation": "Example Org",
            },
            "request": {"subject": "Evidence pack request"},
            "consents": {"processing_authority_confirmed": False},
            "attribution": {"source": "outlook_direct", "medium": "email"},
            "state": "pending",
            "qualification": {"state": "pending"},
        })

    @staticmethod
    def mail_intent(cso: dict, expression: dict) -> dict:
        return {
            "schema": "dio.mail_intent.v1",
            "mail_intent_id": "MAIL-C5-1",
            "direction": "outbound",
            "purpose": "conversation_reply",
            "lead_id": "LEAD-C5-1",
            "conversation_id": "THREAD-C5-1",
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
                "conversation_context_id": "CTX-C5-1",
                "communicative_act": expression["communicative_act"],
                "conversation_context_authority": "expression_only",
                "source_ref": "mail_ingress:INGRESS-C5-1",
            },
            "approval": {
                "required": True,
                "state": "pending",
                "approved_at": None,
                "expires_at": None,
                "token_sha256": None,
            },
            "send_state": "draft",
        }

    @staticmethod
    def execution(intent: dict) -> dict:
        return {
            "kind": "mail_send",
            "channel": "email",
            "mail_intent_id": intent["mail_intent_id"],
            "conversation_id": intent["conversation_id"],
            "source_message_id": intent["source_message_id"],
            "recipient": intent["recipient"],
            "binding_sha256": mail_execution_digest(intent),
        }

    def test_normal_reply_is_triune_judged_but_never_self_authorising(self) -> None:
        cso = self.cso()
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        intent = self.mail_intent(cso, expression)
        judgement = judge_expression(cso, expression, execution=self.execution(intent))

        self.assertEqual("ALLOW", judgement["triune"]["metatron"]["status"])
        self.assertIn(judgement["triune"]["loki"]["status"], {"CLEAR", "CHALLENGE"})
        self.assertIn(judgement["triune"]["beast"]["status"], {"PASS", "CAUTION"})
        self.assertEqual("ALLOW_WITH_OBLIGATIONS", judgement["verdict"])
        self.assertFalse(judgement["execution_authority_granted"])
        self.assertTrue(judgement["constitution"]["human_approval_not_replaced"])
        self.assertTrue(any(row["code"] == "HUMAN_APPROVAL_REQUIRED" for row in judgement["obligations"]))
        scorer = judgement["triune"]["beast"]["scorer"]
        self.assertEqual("EdgeK-BEAST EvidenceScorer", scorer["organ"])
        self.assertIn("EdgeK-BEAST", scorer["source"])

    def test_relaxed_generation_policy_is_loki_veto(self) -> None:
        cso = self.cso()
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        expression = copy.deepcopy(expression)
        expression["plan"]["generation_policy"]["may_add_facts"] = True
        judgement = judge_expression(cso, expression, execution=self.execution(self.mail_intent(cso, expression)))
        self.assertEqual("VETO", judgement["triune"]["loki"]["status"])
        self.assertEqual("BLOCK", judgement["verdict"])
        self.assertTrue(any(row["code"] == "GENERATION_POLICY_RELAXED" for row in judgement["triune"]["loki"]["vetoes"]))

    def test_explicit_prohibited_asserted_claim_is_loki_veto(self) -> None:
        cso = self.cso()
        source_ref = "lead:LEAD-C5-1"
        cso["need"]["workflow_pain"] = semantic_value(
            "manual evidence collation is slow",
            status="inferred",
            source_refs=[source_ref],
            authority="inference_only",
            confidence=0.6,
            method="bounded_test_inference",
        )
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        dependency = next(row for row in expression["claim_sources"] if row["path"] == "need.workflow_pain")
        expression["asserted_claims"] = [{
            "claim_id": "customer_workflow_pain",
            "statement": "Your evidence workflow is slow.",
            "path": dependency["path"],
            "status": dependency["status"],
            "source_refs": dependency["source_refs"],
        }]
        judgement = judge_expression(cso, expression, execution=self.execution(self.mail_intent(cso, expression)))
        self.assertEqual("VETO", judgement["triune"]["loki"]["status"])
        self.assertEqual("BLOCK", judgement["verdict"])
        self.assertTrue(any(row["code"] == "PROHIBITED_CLAIM_ASSERTED" for row in judgement["triune"]["loki"]["vetoes"]))

    def test_active_beast_negative_capability_blocks_execution(self) -> None:
        cso = self.cso()
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        judgement = judge_expression(
            cso,
            expression,
            execution=self.execution(self.mail_intent(cso, expression)),
            active_negative_capabilities=[{
                "capability_id": "dio:outlook:unsupported_claim",
                "state": "active",
                "evidence_count": 3,
            }],
        )
        self.assertEqual("BLOCK", judgement["triune"]["beast"]["status"])
        self.assertEqual("BLOCK", judgement["verdict"])
        self.assertTrue(any(row["code"] == "ACTIVE_NEGATIVE_CAPABILITY" for row in judgement["triune"]["beast"]["blockers"]))

    def test_semantic_object_mismatch_blocks(self) -> None:
        cso = self.cso()
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        other = self.cso(conversation_id="THREAD-C5-2")
        other["object_id"] = "CSO-OTHEROBJECT123456789"
        judgement = judge_expression(other, expression, execution=self.execution(self.mail_intent(cso, expression)))
        self.assertEqual("BLOCK", judgement["verdict"])
        self.assertEqual("BLOCK", judgement["triune"]["metatron"]["status"])
        self.assertEqual("BLOCK", judgement["triune"]["beast"]["status"])

    def test_judged_mail_becomes_stale_when_body_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state" / "leads" / "LEAD-C5-1.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"lead_id":"LEAD-C5-1","state":"pending"}\n', encoding="utf-8")

            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            intent = self.mail_intent(cso, expression)
            judgement, path = judge_mail_intent(root, cso, expression, intent, source_paths=[source])
            intent["semantic_judgement"] = {
                "judgement_id": judgement["judgement_id"],
                "path": str(path.relative_to(root)),
            }
            assert_mail_semantic_judgement_current(root, intent, require_execution_ready=False)
            intent["body"] += " Invented addition."
            with self.assertRaisesRegex(ValueError, "SEMANTIC_JUDGEMENT_STALE"):
                assert_mail_semantic_judgement_current(root, intent, require_execution_ready=False)

    def test_judged_mail_becomes_stale_when_bound_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state" / "leads" / "LEAD-C5-1.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"lead_id":"LEAD-C5-1","state":"pending"}\n', encoding="utf-8")

            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            intent = self.mail_intent(cso, expression)
            judgement, path = judge_mail_intent(root, cso, expression, intent, source_paths=[source])
            intent["semantic_judgement"] = {"judgement_id": judgement["judgement_id"], "path": str(path.relative_to(root))}
            source.write_text('{"lead_id":"LEAD-C5-1","state":"qualified"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SEMANTIC_JUDGEMENT_STALE"):
                assert_mail_semantic_judgement_current(root, intent, require_execution_ready=False)

    def test_human_approval_is_required_but_does_not_replace_judgement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state" / "leads" / "LEAD-C5-1.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"lead_id":"LEAD-C5-1"}\n', encoding="utf-8")
            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            intent = self.mail_intent(cso, expression)
            judgement, path = judge_mail_intent(root, cso, expression, intent, source_paths=[source])
            intent["semantic_judgement"] = {"judgement_id": judgement["judgement_id"], "path": str(path.relative_to(root))}

            with self.assertRaisesRegex(ValueError, "OBLIGATION_UNMET"):
                assert_mail_semantic_judgement_current(root, intent, require_execution_ready=True)

            intent["approval"]["state"] = "approved"
            current = assert_mail_semantic_judgement_current(root, intent, require_execution_ready=True)
            self.assertEqual(judgement["judgement_id"], current["judgement_id"])

    def test_semantically_bound_mail_without_receipt_is_refused_but_legacy_is_compatible(self) -> None:
        cso = self.cso()
        expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
        intent = self.mail_intent(cso, expression)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "SEMANTIC_JUDGEMENT_REFUSED"):
                assert_mail_semantic_judgement_current(Path(tmp), intent, require_execution_ready=False)
            legacy = copy.deepcopy(intent)
            legacy.pop("semantic_binding")
            self.assertIsNone(assert_mail_semantic_judgement_current(Path(tmp), legacy, require_execution_ready=False))

    def test_schema_file_carries_non_authority_constitution(self) -> None:
        schema = json.loads((ROOT / "schemas" / "dio.semantic_judgement.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("DIO Semantic Judgement v1", schema["title"])
        self.assertFalse(schema["properties"]["execution_authority_granted"]["const"])
        constitution = schema["properties"]["constitution"]["properties"]
        self.assertTrue(constitution["human_approval_not_replaced"]["const"])
        self.assertTrue(constitution["source_change_invalidates_judgement"]["const"])


if __name__ == "__main__":
    unittest.main()
