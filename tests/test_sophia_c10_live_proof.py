from __future__ import annotations

import unittest

from scripts.prove_sophia_c10_live import evaluate_proof


class SophiaC10LiveProofTests(unittest.TestCase):
    def fixtures(self):
        job = {
            "review": {
                "grounding_passed": True,
                "c9_integrity": {"state": "integrity_pack_ready"},
            },
            "revision_rounds": [
                {
                    "round": 1,
                    "grounding_passed": True,
                    "integrity_enrichment": {"state": "integrity_pack_ready"},
                }
            ],
        }
        longitudinal = {
            "version_count": 2,
            "lineage_count": 1,
            "lineages": [
                {
                    "lineage_id": "lineage-1",
                    "state": "evidence_strengthened",
                    "occurrence_count": 2,
                    "support_trajectory": ["background_only", "support_ready"],
                }
            ],
            "unresolved_continuity_candidates": [],
            "author_decisions": [
                {"lineage_id": "lineage-1", "decision": "retain_with_limitation", "actor": "author"}
            ],
            "burden_mutation_lineages": [],
            "lineage_resolution_events": [],
            "longitudinal_speculum_hash": "a" * 64,
            "native_integrity_record_hash": "b" * 64,
            "authority_boundary": "Claim lineage is not a forensic authorship or misconduct determination.",
        }
        native = {
            "claim_ledger": [
                {"record_id": "claim-v1"},
                {"record_id": "claim-v2"},
            ],
            "final_decisions": [
                {"decision": "retain_with_limitation"}
            ],
            "authorship_preservation_index": {
                "validation_status": "engineering_metric_unvalidated",
                "score": 0.84,
                "band": "strong",
            },
        }
        topology = {
            "state": "scholarly_topology_ready",
            "topology_issue_count": 1,
            "open_topology_issues": 0,
            "blocking_decision_queue": 0,
            "topology_audit_hash": "c" * 64,
            "decision_queue_hash": "d" * 64,
        }
        return job, longitudinal, native, topology

    def test_complete_case_passes_only_when_receipts_cover_longitudinal_claim(self) -> None:
        job, longitudinal, native, topology = self.fixtures()
        receipt = evaluate_proof(
            job=job,
            longitudinal=longitudinal,
            native_record=native,
            topology=topology,
        )
        self.assertTrue(receipt["proof_passed"])
        self.assertEqual(receipt["required_cases_passed"], receipt["required_cases_total"])
        self.assertEqual(receipt["result"], "C10_LONGITUDINAL_PROOF_PASSED")

    def test_missing_human_decision_prevents_victory_claim(self) -> None:
        job, longitudinal, native, topology = self.fixtures()
        longitudinal["author_decisions"] = []
        receipt = evaluate_proof(job=job, longitudinal=longitudinal, native_record=native, topology=topology)
        self.assertFalse(receipt["proof_passed"])
        failed = {row["case_id"] for row in receipt["cases"] if not row["passed"]}
        self.assertIn("human_author_decision_recorded", failed)
        self.assertEqual(receipt["result"], "C10_LONGITUDINAL_PROOF_NOT_YET_ESTABLISHED")

    def test_unresolved_continuity_prevents_victory_claim(self) -> None:
        job, longitudinal, native, topology = self.fixtures()
        longitudinal["unresolved_continuity_candidates"] = [{"lineage_id": "provisional-1"}]
        receipt = evaluate_proof(job=job, longitudinal=longitudinal, native_record=native, topology=topology)
        self.assertFalse(receipt["proof_passed"])
        failed = {row["case_id"] for row in receipt["cases"] if not row["passed"]}
        self.assertIn("ambiguous_continuity_resolved", failed)

    def test_duplicate_native_record_ids_prevent_history_claim(self) -> None:
        job, longitudinal, native, topology = self.fixtures()
        native["claim_ledger"][1]["record_id"] = "claim-v1"
        receipt = evaluate_proof(job=job, longitudinal=longitudinal, native_record=native, topology=topology)
        self.assertFalse(receipt["proof_passed"])
        failed = {row["case_id"] for row in receipt["cases"] if not row["passed"]}
        self.assertIn("version_scoped_native_claim_records_preserved", failed)

    def test_blocking_scholarly_decision_queue_prevents_victory_claim(self) -> None:
        job, longitudinal, native, topology = self.fixtures()
        topology["blocking_decision_queue"] = 2
        topology["open_topology_issues"] = 1
        receipt = evaluate_proof(job=job, longitudinal=longitudinal, native_record=native, topology=topology)
        self.assertFalse(receipt["proof_passed"])
        failed = {row["case_id"] for row in receipt["cases"] if not row["passed"]}
        self.assertIn("scholarly_decision_queue_clear", failed)

    def test_missing_topology_hash_prevents_victory_claim(self) -> None:
        job, longitudinal, native, topology = self.fixtures()
        topology["topology_audit_hash"] = ""
        receipt = evaluate_proof(job=job, longitudinal=longitudinal, native_record=native, topology=topology)
        self.assertFalse(receipt["proof_passed"])
        failed = {row["case_id"] for row in receipt["cases"] if not row["passed"]}
        self.assertIn("scholarly_topology_ready_and_hashed", failed)


if __name__ == "__main__":
    unittest.main()
