from __future__ import annotations

import unittest

from adapters.sophia.c10_scope import governed_scope_signature, registered_prior_candidates


class SophiaC10LineageIsolationTests(unittest.TestCase):
    def test_association_with_improved_outcome_is_not_causal(self) -> None:
        result = governed_scope_signature(
            "Structured feedback is associated with improved academic writing outcomes.",
            "associational",
        )
        self.assertFalse(result["causal"])
        self.assertTrue(result["associational"])
        self.assertTrue(result["outcome_verb"])

    def test_outcome_predicate_without_association_can_be_causal(self) -> None:
        result = governed_scope_signature(
            "Structured feedback improves academic writing outcomes.",
            "causal",
        )
        self.assertTrue(result["causal"])
        self.assertFalse(result["associational"])

    def test_only_registered_prior_versions_can_be_lineage_ancestors(self) -> None:
        registry = {
            "versions": [
                {"draft_version_id": "draft-v1", "revision_label": "initial"},
            ],
            "lineages": {
                "lineage-old": {
                    "state": "active",
                    "occurrences": [
                        {"draft_version_id": "draft-v1", "claim": "Older claim"},
                    ],
                },
                "lineage-current-sibling": {
                    "state": "active",
                    "occurrences": [
                        {"draft_version_id": "draft-v2", "claim": "First claim in current draft"},
                    ],
                },
            },
        }
        candidates = registered_prior_candidates(registry)
        self.assertEqual([lineage_id for lineage_id, _ in candidates], ["lineage-old"])

    def test_provisional_lineage_never_becomes_ancestor_before_resolution(self) -> None:
        registry = {
            "versions": [
                {"draft_version_id": "draft-v1"},
                {"draft_version_id": "draft-v2"},
            ],
            "lineages": {
                "lineage-provisional": {
                    "state": "provisional_continuity_candidate",
                    "occurrences": [
                        {"draft_version_id": "draft-v2", "claim": "Ambiguous paraphrase"},
                    ],
                }
            },
        }
        self.assertEqual(registered_prior_candidates(registry), [])


if __name__ == "__main__":
    unittest.main()
