from __future__ import annotations

import unittest

from adapters.sophia.c10_validation import build_human_validation, evaluate_stress_proof


class SophiaC10ValidationTests(unittest.TestCase):
    def human(self, **overrides):
        payload = {
            "project_id": "SOPHIA-C10-VALIDATION",
            "reviewer_alias": "academic-reviewer",
            "reviewer_role": "supervisor",
            "independent_of_build": False,
            "claims_checked": 10,
            "support_mappings_correct": 9,
            "review_flags_checked": 10,
            "false_positive_flags": 1,
            "source_verifications_completed": 4,
            "topology_questions_reviewed": 2,
            "topology_questions_useful": 2,
            "missed_material_issues": 0,
            "decisions_materially_helped": 3,
            "authorship_boundary_respected": True,
            "would_use_again": True,
            "notes": "Fixture validation.",
        }
        payload.update(overrides)
        return build_human_validation(**payload)

    def stress_inputs(self):
        base = {"proof_passed": True}
        longitudinal = {
            "project_id": "SOPHIA-C10-VALIDATION",
            "lineages": [
                {
                    "lineage_id": "L1",
                    "state": "evidence_strengthened",
                    "support_trajectory": ["background_only", "support_ready"],
                },
                {
                    "lineage_id": "L2",
                    "state": "burden_mutated",
                    "support_trajectory": ["partial_support", "partial_support"],
                },
            ],
            "burden_mutation_lineages": [{"lineage_id": "L2"}],
            "lineage_resolution_events": [],
            "author_decisions": [
                {"lineage_id": "L1", "decision": "retain_with_limitation"},
                {"lineage_id": "L2", "decision": "strengthen_evidence"},
            ],
        }
        topology = {
            "topology_audit_hash": "a" * 64,
            "issues": [
                {
                    "issue_id": "TI-1",
                    "kind": "factual_surface_mutation",
                    "state": "human_resolved",
                }
            ],
        }
        queue = {"blocking_count": 0, "decision_queue_hash": "b" * 64}
        return base, longitudinal, topology, queue

    def test_human_validation_passes_with_inspectable_sample(self) -> None:
        payload = self.human()
        self.assertTrue(payload["validation_passed"])
        self.assertEqual(payload["metrics"]["support_mapping_accuracy"], 0.9)
        self.assertEqual(payload["metrics"]["review_false_positive_rate"], 0.1)
        self.assertEqual(len(payload["validation_receipt_sha256"]), 64)

    def test_human_validation_fails_small_or_sloppy_sample(self) -> None:
        payload = self.human(
            claims_checked=4,
            support_mappings_correct=3,
            review_flags_checked=10,
            false_positive_flags=4,
        )
        self.assertFalse(payload["validation_passed"])
        self.assertFalse(payload["gates"]["minimum_claim_sample"])
        self.assertFalse(payload["gates"]["review_false_positive_rate"])

    def test_authorship_boundary_breach_is_a_hard_failure(self) -> None:
        payload = self.human(authorship_boundary_respected=False)
        self.assertFalse(payload["validation_passed"])
        self.assertFalse(payload["gates"]["authorship_boundary_respected"])

    def test_stress_proof_requires_nontrivial_change_and_human_validation(self) -> None:
        base, longitudinal, topology, queue = self.stress_inputs()
        payload = evaluate_stress_proof(
            base_receipt=base,
            longitudinal=longitudinal,
            topology_audit=topology,
            decision_queue=queue,
            human_validation=self.human(),
        )
        self.assertTrue(payload["stress_proof_passed"])
        self.assertEqual(payload["result"], "C10_STRESS_PROOF_PASSED")
        self.assertGreaterEqual(payload["meaningful_change_class_count"], 2)
        self.assertEqual(len(payload["stress_proof_sha256"]), 64)

    def test_boring_two_draft_case_cannot_claim_stress_proof(self) -> None:
        base, longitudinal, topology, queue = self.stress_inputs()
        longitudinal["lineages"] = [
            {"lineage_id": "L1", "state": "continued", "support_trajectory": ["support_ready", "support_ready"]}
        ]
        longitudinal["burden_mutation_lineages"] = []
        longitudinal["lineage_resolution_events"] = []
        topology["issues"] = []
        payload = evaluate_stress_proof(
            base_receipt=base,
            longitudinal=longitudinal,
            topology_audit=topology,
            decision_queue=queue,
            human_validation=self.human(topology_questions_reviewed=0, topology_questions_useful=0),
        )
        self.assertFalse(payload["stress_proof_passed"])
        self.assertFalse(payload["gates"]["at_least_two_meaningful_change_classes"])

    def test_open_decision_queue_prevents_stress_victory(self) -> None:
        base, longitudinal, topology, queue = self.stress_inputs()
        queue["blocking_count"] = 1
        payload = evaluate_stress_proof(
            base_receipt=base,
            longitudinal=longitudinal,
            topology_audit=topology,
            decision_queue=queue,
            human_validation=self.human(),
        )
        self.assertFalse(payload["stress_proof_passed"])
        self.assertFalse(payload["gates"]["scholarly_decision_queue_clear"])


if __name__ == "__main__":
    unittest.main()
