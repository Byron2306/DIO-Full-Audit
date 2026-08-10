from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from commerce.beast_semantic_governance import assess_expression_evidence
from commerce.expression_guarded import CommunicativeAct, render_expression
from commerce.mandos import MandosLedger, commercial_outcome
from commerce.semantic import commercial_semantic_object_from_lead


class MandosBeastMemoryTests(unittest.TestCase):
    @staticmethod
    def cso() -> dict:
        return commercial_semantic_object_from_lead({
            "schema": "dio.lead.v1",
            "lead_id": "LEAD-BEAST-CURRENT",
            "product": "Evidex Evidence Packs",
            "offer": "bounded pilot",
            "contact": {"email": "current@example.org", "organisation": "Current Org"},
            "request": {"subject": "Evidence"},
            "consents": {"processing_authority_confirmed": False},
            "attribution": {"source": "outlook_direct", "medium": "email"},
            "state": "pending",
            "qualification": {"state": "pending"},
        })

    @staticmethod
    def negative(lead_id: str, *, tactic_id: str | None = None) -> dict:
        return commercial_outcome(
            outcome_type="no_reply_window_closed",
            lineage={"lead_id": lead_id},
            source_refs=[f"operator_window:{lead_id}"],
            source_classes=["operator_observation_window"],
            occurred_at="2026-08-10T10:00:00+00:00",
            polarity="negative",
            evidence_state="operator_confirmed",
            strategy={
                "product": "Evidex Evidence Packs",
                "offer": "bounded pilot",
                "communicative_act": "inbound_reply",
                "channel": "email",
                "tactic_id": tactic_id,
            },
        )

    def test_two_independent_repeated_failures_are_loaded_automatically_by_beast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.negative("LEAD-FAIL-1"))
            ledger.record(self.negative("LEAD-FAIL-2"))
            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            assessment = assess_expression_evidence(
                cso,
                expression,
                execution_kind="mail_send",
                memory_root=root,
            )
            self.assertEqual("BLOCK", assessment["status"])
            self.assertEqual(1, assessment["mandos_memory"]["remembered_matches"])
            self.assertTrue(any(row["code"] == "ACTIVE_NEGATIVE_CAPABILITY" for row in assessment["blockers"]))
            self.assertFalse(assessment["mandos_memory"]["positive_memory_may_expand_authority"])

    def test_single_failure_does_not_create_veto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            MandosLedger(root).record(self.negative("LEAD-FAIL-1"))
            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            assessment = assess_expression_evidence(cso, expression, execution_kind="mail_send", memory_root=root)
            self.assertEqual(0, assessment["mandos_memory"]["remembered_matches"])
            self.assertFalse(any(row["code"] == "ACTIVE_NEGATIVE_CAPABILITY" for row in assessment["blockers"]))

    def test_positive_contradiction_removes_automatic_veto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.negative("LEAD-FAIL-1"))
            ledger.record(self.negative("LEAD-FAIL-2"))
            ledger.record(commercial_outcome(
                outcome_type="reply_received",
                lineage={"lead_id": "LEAD-SUCCESS-3"},
                source_refs=["outlook:LEAD-SUCCESS-3"],
                source_classes=["outlook_ingress"],
                occurred_at="2026-08-10T11:00:00+00:00",
                polarity="positive",
                evidence_state="verified",
                strategy={
                    "product": "Evidex Evidence Packs",
                    "offer": "bounded pilot",
                    "communicative_act": "inbound_reply",
                    "channel": "email",
                },
            ))
            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            assessment = assess_expression_evidence(cso, expression, execution_kind="mail_send", memory_root=root)
            self.assertEqual(0, assessment["mandos_memory"]["remembered_matches"])
            self.assertFalse(any(row["code"] == "ACTIVE_NEGATIVE_CAPABILITY" for row in assessment["blockers"]))

    def test_tactic_specific_failure_does_not_broaden_when_current_tactic_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.negative("LEAD-TACTIC-1", tactic_id="TACTIC-A"))
            ledger.record(self.negative("LEAD-TACTIC-2", tactic_id="TACTIC-A"))
            cso = self.cso()
            expression = render_expression(cso, CommunicativeAct.INBOUND_REPLY)
            assessment = assess_expression_evidence(cso, expression, execution_kind="mail_send", memory_root=root)
            self.assertEqual(0, assessment["mandos_memory"]["remembered_candidates"])
            self.assertEqual(0, assessment["mandos_memory"]["remembered_matches"])
            self.assertFalse(assessment["mandos_memory"]["unprovable_selector_may_broaden_veto"])
            self.assertFalse(any(row["code"] == "ACTIVE_NEGATIVE_CAPABILITY" for row in assessment["blockers"]))

    def test_tactic_specific_failure_vetoes_when_current_expression_proves_same_tactic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = MandosLedger(root)
            ledger.record(self.negative("LEAD-TACTIC-1", tactic_id="TACTIC-A"))
            ledger.record(self.negative("LEAD-TACTIC-2", tactic_id="TACTIC-A"))
            cso = self.cso()
            expression = copy.deepcopy(render_expression(cso, CommunicativeAct.INBOUND_REPLY))
            expression["tactic_id"] = "TACTIC-A"
            assessment = assess_expression_evidence(cso, expression, execution_kind="mail_send", memory_root=root)
            self.assertEqual(1, assessment["mandos_memory"]["remembered_candidates"])
            self.assertEqual(1, assessment["mandos_memory"]["remembered_matches"])
            self.assertEqual("BLOCK", assessment["status"])
            self.assertTrue(any(row["code"] == "ACTIVE_NEGATIVE_CAPABILITY" for row in assessment["blockers"]))


if __name__ == "__main__":
    unittest.main()
