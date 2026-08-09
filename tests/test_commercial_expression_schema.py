from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression import CommunicativeAct, EXPRESSION_SCHEMA, PLAN_SCHEMA  # noqa: E402


class CommercialExpressionSchemaTests(unittest.TestCase):
    def test_schema_declares_every_communicative_act(self) -> None:
        schema = json.loads((ROOT / "schemas" / "dio.commercial_expression.v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("DIO Commercial Expression v1", schema["title"])
        self.assertEqual(EXPRESSION_SCHEMA, schema["properties"]["schema"]["const"])
        declared = set(schema["properties"]["communicative_act"]["enum"])
        self.assertEqual({act.value for act in CommunicativeAct}, declared)
        self.assertEqual(PLAN_SCHEMA, schema["properties"]["plan"]["properties"]["schema"]["const"])

    def test_schema_forbids_generation_authority_escalation(self) -> None:
        schema = json.loads((ROOT / "schemas" / "dio.commercial_expression.v1.schema.json").read_text(encoding="utf-8"))
        policy = schema["properties"]["plan"]["properties"]["generation_policy"]["properties"]
        self.assertEqual(False, policy["may_add_facts"]["const"])
        self.assertEqual(False, policy["may_promote_inference_to_fact"]["const"])
        self.assertEqual(False, policy["may_fill_unknowns"]["const"])
        self.assertEqual(True, policy["human_approval_required"]["const"])


if __name__ == "__main__":
    unittest.main()
