from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression_guarded import CommunicativeAct, render_expression  # noqa: E402
from commerce.semantic import commercial_semantic_object_from_lead  # noqa: E402
from commerce.semantic_judgement import judge_mail_intent  # noqa: E402


class SemanticJudgementIdempotenceTests(unittest.TestCase):
    def test_same_evidence_reuses_same_receipt_across_clock_ticks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state/leads/LEAD-IDEMPOTENT.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"lead_id":"LEAD-IDEMPOTENT","state":"pending"}\n', encoding="utf-8")
            cso = commercial_semantic_object_from_lead({
                "schema": "dio.lead.v1",
                "lead_id": "LEAD-IDEMPOTENT",
                "conversation_id": "THREAD-IDEMPOTENT",
                "product": "Evidex Evidence Packs",
                "offer": "bounded pilot",
                "contact": {"email": "alex@example.org", "organisation": "Example Org"},
                "request": {"subject": "Evidence"},
                "consents": {"processing_authority_confirmed": False},
                "attribution": {"source": "outlook_direct", "medium": "email"},
                "state": "pending",
                "qualification": {"state": "pending"},
            })
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            intent = {
                "mail_intent_id": "MAIL-IDEMPOTENT",
                "purpose": "conversation_reply",
                "recipient": "alex@example.org",
                "subject": "Re: Evidence",
                "body": expression["body"],
                "body_html": None,
                "body_path": None,
                "attachments": [],
                "conversation_id": "THREAD-IDEMPOTENT",
                "source_message_id": "GRAPH-IDEMPOTENT",
                "communicative_act": expression["communicative_act"],
                "semantic_binding": {
                    "semantic_object_id": cso["object_id"],
                    "conversation_context_id": "CTX-IDEMPOTENT",
                    "communicative_act": expression["communicative_act"],
                },
            }
            with patch("commerce.semantic_judgement.timestamp", return_value="2026-08-10T00:00:00+00:00"):
                first, first_path = judge_mail_intent(root, cso, expression, intent, source_paths=[source])
            with patch("commerce.semantic_judgement.timestamp", return_value="2026-08-10T00:00:05+00:00"):
                second, second_path = judge_mail_intent(root, cso, expression, intent, source_paths=[source])
            self.assertEqual(first["judgement_id"], second["judgement_id"])
            self.assertEqual(first_path, second_path)
            persisted = first_path.read_text(encoding="utf-8")
            self.assertIn("2026-08-10T00:00:00+00:00", persisted)
            self.assertNotIn("2026-08-10T00:00:05+00:00", persisted)


if __name__ == "__main__":
    unittest.main()
