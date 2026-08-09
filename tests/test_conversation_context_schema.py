from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conversation_core.context import SCHEMA  # noqa: E402


class ConversationContextSchemaTests(unittest.TestCase):
    def test_schema_is_valid_json_and_matches_runtime_contract(self) -> None:
        payload = json.loads((ROOT / "schemas" / "dio.conversation_context.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("DIO Conversation Context v1", payload["title"])
        self.assertEqual(SCHEMA, payload["properties"]["schema"]["const"])
        self.assertEqual(40, payload["properties"]["turns"]["maxItems"])

    def test_schema_hard_codes_conversation_authority_limits(self) -> None:
        payload = json.loads((ROOT / "schemas" / "dio.conversation_context.v1.schema.json").read_text(encoding="utf-8"))
        authority = payload["properties"]["authority"]["properties"]
        self.assertTrue(authority["may_shape_expression"]["const"])
        for name in (
            "may_establish_commercial_fact",
            "may_grant_consent",
            "may_set_scope",
            "may_set_budget",
            "may_set_payment_state",
            "may_confirm_identity",
            "may_grant_execution_authority",
        ):
            self.assertFalse(authority[name]["const"], name)


if __name__ == "__main__":
    unittest.main()
