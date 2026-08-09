from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.manage_mail_intent import create_intent_from_payload


class SemanticMailBindingGateTests(unittest.TestCase):
    def test_communicative_act_without_semantic_binding_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "SEMANTIC_BINDING_REQUIRED"):
                create_intent_from_payload(
                    {
                        "purpose": "proposal",
                        "communicative_act": "proposal",
                        "recipient": "buyer@example.org",
                        "subject": "Proposal",
                        "body": "Governed proposal copy.",
                    },
                    root / "intents",
                    root / "events.jsonl",
                )

    def test_semantic_binding_without_communicative_act_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "COMMUNICATIVE_ACT_REQUIRED"):
                create_intent_from_payload(
                    {
                        "purpose": "proposal",
                        "semantic_binding": {"semantic_object_id": "CSO-123"},
                        "recipient": "buyer@example.org",
                        "subject": "Proposal",
                        "body": "Governed proposal copy.",
                    },
                    root / "intents",
                    root / "events.jsonl",
                )

    def test_legacy_mail_without_act_or_binding_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intent = create_intent_from_payload(
                {
                    "purpose": "legacy_notice",
                    "recipient": "buyer@example.org",
                    "subject": "Legacy notice",
                    "body": "Existing non-semantic mail remains supported.",
                },
                root / "intents",
                root / "events.jsonl",
            )
            self.assertIsNone(intent["communicative_act"])
            self.assertIsNone(intent["semantic_binding"])

    def test_bound_communicative_act_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binding = {
                "semantic_object_id": "CSO-123",
                "communicative_act": "proposal",
                "source_ref": "lead:LEAD-1",
            }
            intent = create_intent_from_payload(
                {
                    "purpose": "proposal",
                    "communicative_act": "proposal",
                    "semantic_binding": binding,
                    "recipient": "buyer@example.org",
                    "subject": "Proposal",
                    "body": "Governed proposal copy.",
                },
                root / "intents",
                root / "events.jsonl",
            )
            self.assertEqual("proposal", intent["communicative_act"])
            self.assertEqual(binding, intent["semantic_binding"])


if __name__ == "__main__":
    unittest.main()
