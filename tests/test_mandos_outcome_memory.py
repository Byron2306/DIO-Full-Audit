from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from commerce.mandos import MandosLedger, commercial_outcome, pattern_key, strategy_signature


STRATEGY = {
    "product": "Evidex Evidence Pack",
    "offer": "EVIDEX-PILOT-PACK",
    "communicative_act": "cold_permission_request",
    "channel": "email",
    "audience": "South African NGO evidence teams",
    "tactic_id": None,
    "proof_family": "golden_case",
}


class MandosOutcomeMemoryTests(unittest.TestCase):
    def outcome(
        self,
        lead_id: str,
        *,
        polarity: str = "positive",
        source_class: str = "outlook_ingress",
        outcome_type: str = "reply_received",
        revenue_minor: int = 0,
    ) -> dict:
        return commercial_outcome(
            outcome_type=outcome_type,
            lineage={"lead_id": lead_id, "campaign_id": "CMP-MANDOS-1"},
            source_refs=[f"source:{lead_id}:{source_class}"],
            source_classes=[source_class],
            occurred_at=f"2026-08-{10 + int(lead_id[-1])}T10:00:00+00:00",
            polarity=polarity,
            evidence_state="verified",
            strategy=STRATEGY,
            economics={"currency": "ZAR", "revenue_minor": revenue_minor},
        )

    def test_verified_outcome_requires_provenance_and_cannot_grant_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_refs"):
            commercial_outcome(
                outcome_type="reply_received",
                lineage={"lead_id": "LEAD-1"},
                source_refs=[],
                source_classes=["outlook_ingress"],
                occurred_at="2026-08-10T10:00:00+00:00",
                strategy=STRATEGY,
            )
        outcome = self.outcome("LEAD-1")
        self.assertFalse(outcome["authority"]["may_expand_execution_authority"])
        self.assertFalse(outcome["authority"]["may_become_reusable_strategy"])

    def test_journal_is_hash_chained_and_reconcile_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            outcome = self.outcome("LEAD-1")
            first, created = ledger.record(outcome)
            second, created_again = ledger.record(outcome)
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(first["outcome_id"], second["outcome_id"])
            verification = ledger.verify_journal()
            self.assertTrue(verification["valid"])
            self.assertEqual(1, verification["entries"])

    def test_one_case_never_becomes_reusable_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            outcome, _ = ledger.record(self.outcome("LEAD-1"))
            pattern = ledger.pattern(outcome["strategy"]["pattern_key"])
            self.assertEqual("observation", pattern["current_stage"])
            self.assertEqual("not_earned", pattern["reuse_authority"]["state"])
            self.assertFalse(pattern["reuse_authority"]["may_expand_execution_authority"])

    def test_independent_case_count_not_repeated_events_controls_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            ledger.record(self.outcome("LEAD-1", outcome_type="reply_received"))
            ledger.record(self.outcome("LEAD-1", outcome_type="qualification_changed"))
            pkey = pattern_key(strategy_signature(**STRATEGY))
            pattern = ledger.pattern(pkey)
            self.assertEqual(1, pattern["evidence_summary"]["verified_cases"])
            self.assertEqual("observation", pattern["earned_stage"])

    def test_three_independent_cases_and_two_source_classes_only_earn_corroboration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            ledger.record(self.outcome("LEAD-1", source_class="outlook_ingress"))
            ledger.record(self.outcome("LEAD-2", source_class="operator_qualification", outcome_type="qualification_changed"))
            ledger.record(self.outcome("LEAD-3", source_class="outlook_ingress"))
            pkey = pattern_key(strategy_signature(**STRATEGY))
            pattern = ledger.pattern(pkey)
            self.assertEqual(3, pattern["evidence_summary"]["verified_cases"])
            self.assertEqual(2, pattern["evidence_summary"]["source_class_count"])
            self.assertEqual("corroborated_pattern", pattern["current_stage"])
            self.assertEqual("not_earned", pattern["reuse_authority"]["state"])

    def test_reusable_crystal_requires_nomination_adversarial_pass_and_human_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            for lead_id, source_class in (("LEAD-1", "outlook_ingress"), ("LEAD-2", "operator_qualification"), ("LEAD-3", "outlook_ingress")):
                ledger.record(self.outcome(lead_id, source_class=source_class))
            pkey = pattern_key(strategy_signature(**STRATEGY))
            with self.assertRaisesRegex(ValueError, "adversarial validation"):
                ledger.promote(pkey, actor="operator", confirmed=True, rationale="too early")
            ledger.nominate(pkey, actor="operator", rationale="candidate after corroboration")
            with self.assertRaisesRegex(ValueError, "passed adversarial"):
                ledger.promote(pkey, actor="operator", confirmed=True, rationale="still too early")
            ledger.validate_adversarially(
                pkey,
                actor="loki-reviewer",
                state="passed",
                receipt_refs=["validation:VAL-1"],
            )
            with self.assertRaisesRegex(ValueError, "explicit human confirmation"):
                ledger.promote(pkey, actor="operator", confirmed=False, rationale="missing confirmation")
            ledger.promote(pkey, actor="operator", confirmed=True, rationale="bounded reusable strategy")
            pattern = ledger.pattern(pkey)
            self.assertEqual("reusable_crystal", pattern["current_stage"])
            self.assertEqual("active", pattern["reuse_authority"]["state"])
            self.assertFalse(pattern["reuse_authority"]["may_expand_execution_authority"])

    def test_revocation_does_not_erase_history_or_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            for lead_id, source_class in (("LEAD-1", "outlook_ingress"), ("LEAD-2", "operator_qualification"), ("LEAD-3", "outlook_ingress")):
                ledger.record(self.outcome(lead_id, source_class=source_class))
            pkey = pattern_key(strategy_signature(**STRATEGY))
            ledger.nominate(pkey, actor="operator", rationale="candidate")
            ledger.validate_adversarially(pkey, actor="loki", state="passed", receipt_refs=["validation:VAL-1"])
            ledger.promote(pkey, actor="operator", confirmed=True, rationale="promote")
            before_ids = {row["outcome_id"] for row in ledger.outcomes()}
            ledger.revoke(pkey, actor="operator", confirmed=True, reason="new external contradiction")
            pattern = ledger.pattern(pkey)
            after_ids = {row["outcome_id"] for row in ledger.outcomes()}
            self.assertEqual(before_ids, after_ids)
            self.assertEqual("reusable_crystal", pattern["historical_max_stage"])
            self.assertEqual("revoked", pattern["reuse_authority"]["state"])
            self.assertTrue(pattern["reuse_authority"]["exact_outcome_evidence_retained"])

    def test_repeated_verified_failure_activates_negative_capability_earlier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            ledger.record(self.outcome("LEAD-1", polarity="negative", outcome_type="no_reply_window_closed"))
            ledger.record(self.outcome("LEAD-2", polarity="negative", outcome_type="no_reply_window_closed"))
            pkey = pattern_key(strategy_signature(**STRATEGY))
            pattern = ledger.pattern(pkey)
            self.assertEqual("repeated_observation", pattern["earned_stage"])
            self.assertEqual("active", pattern["negative_capability"]["state"])
            registry = json.loads((Path(tmp) / "state/mandos/beast/NEGATIVE_CAPABILITIES.json").read_text(encoding="utf-8"))
            row = next(item for item in registry["capabilities"] if item["pattern_key"] == pkey)
            self.assertTrue(row["may_veto_semantic_execution"])

    def test_positive_contradiction_makes_negative_capability_contested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = MandosLedger(Path(tmp))
            ledger.record(self.outcome("LEAD-1", polarity="negative", outcome_type="no_reply_window_closed"))
            ledger.record(self.outcome("LEAD-2", polarity="negative", outcome_type="no_reply_window_closed"))
            ledger.record(self.outcome("LEAD-3", polarity="positive", outcome_type="reply_received"))
            pkey = pattern_key(strategy_signature(**STRATEGY))
            pattern = ledger.pattern(pkey)
            self.assertEqual("contested", pattern["direction"])
            self.assertEqual("contested", pattern["negative_capability"]["state"])
            registry = json.loads((Path(tmp) / "state/mandos/beast/NEGATIVE_CAPABILITIES.json").read_text(encoding="utf-8"))
            row = next(item for item in registry["capabilities"] if item["pattern_key"] == pkey)
            self.assertFalse(row["may_veto_semantic_execution"])

    def test_schema_files_encode_mandos_constitution(self) -> None:
        root = Path(__file__).resolve().parents[1]
        outcome_schema = json.loads((root / "schemas/dio.commercial_outcome.v1.schema.json").read_text(encoding="utf-8"))
        pattern_schema = json.loads((root / "schemas/dio.mandos_pattern.v1.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(outcome_schema["properties"]["authority"]["properties"]["may_expand_execution_authority"]["const"])
        self.assertFalse(pattern_schema["properties"]["promotion_law"]["properties"]["automatic_crystallization"]["const"])
        self.assertTrue(pattern_schema["properties"]["promotion_law"]["properties"]["human_promotion_required"]["const"])


if __name__ == "__main__":
    unittest.main()
