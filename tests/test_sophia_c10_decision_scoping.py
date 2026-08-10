from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.sophia.longitudinal_speculum import (
    build_longitudinal_export,
    ingest_review_pack,
    record_author_decision,
)
from adapters.sophia.scholarly_topology import (
    build_decision_queue,
    build_topology_audit,
    record_topology_decision,
)
from tests.test_sophia_c10_scholarly_topology import VENDORED_SOPHIA, _claim, _pack


class SophiaC10DecisionScopingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.project = "SOPHIA-C10-DECISION-SCOPING"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _ingest(self, label: str, text: str, claims: list[dict]) -> dict:
        document = self.root / f"{label}.txt"
        document.write_text(text, encoding="utf-8")
        output = self.root / f"pack-{label}"
        _pack(output, claims)
        return ingest_review_pack(
            project_id=self.project,
            state_root=self.state,
            output_dir=output,
            manuscript_path=document,
            revision_label=label,
            review_id=f"{self.project}-{label}",
            sophia_root=VENDORED_SOPHIA,
        )

    def _lineage(self) -> dict:
        return build_longitudinal_export(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )

    def test_prior_author_decision_does_not_clear_later_burden_mutation(self) -> None:
        text = "Structured feedback improves academic writing among postgraduate learners."
        first = self._ingest("initial", text, [_claim(text, claim_type="associational", risk="medium")])
        lineage_id = first["lineages"][0]["lineage_id"]
        record_author_decision(
            project_id=self.project,
            state_root=self.state,
            lineage_id=lineage_id,
            decision="retain_with_limitation",
            rationale="Retain the associational claim with an observational limitation.",
            actor="author",
            sophia_root=VENDORED_SOPHIA,
        )
        self._ingest("revision_1", text + "\n", [_claim(text, claim_type="causal", risk="high")])
        queue = build_decision_queue(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertTrue(
            any(row["kind"] == "author_decision_required_for_burden_mutation" for row in queue["items"]),
            "A v1 author decision must not silently authorize v2's stronger epistemic burden.",
        )

    def test_persistent_high_risk_claim_does_not_lose_its_obligation_by_surviving(self) -> None:
        text = "Structured feedback causes durable improvements in dissertation quality."
        self._ingest("initial", text, [_claim(text, claim_type="causal", risk="high")])
        self._ingest("revision_1", text + "\n", [_claim(text, claim_type="causal", risk="high")])
        queue = build_decision_queue(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        obligations = [row for row in queue["items"] if row["kind"] == "persistent_high_risk_claim_needs_author_decision"]
        self.assertEqual(len(obligations), 1)
        lineage_id = obligations[0]["lineage_id"]
        record_author_decision(
            project_id=self.project,
            state_root=self.state,
            lineage_id=lineage_id,
            decision="strengthen_evidence",
            rationale="The author will retain the causal claim only after adding evidence capable of carrying the causal burden.",
            actor="author",
            sophia_root=VENDORED_SOPHIA,
        )
        after = build_decision_queue(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertFalse(any(row["kind"] == "persistent_high_risk_claim_needs_author_decision" for row in after["items"]))

    def test_defer_is_a_human_action_but_not_a_release_resolution(self) -> None:
        prior = "The intervention improved writing for 42% of participants."
        current = "The intervention improved writing for 57% of participants."
        self._ingest("initial", prior, [_claim(prior, claim_type="descriptive")])
        self._ingest("revision_1", current, [_claim(current, claim_type="descriptive")])
        audit = build_topology_audit(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        issue = next(row for row in audit["issues"] if row["kind"] == "factual_surface_mutation")
        record_topology_decision(
            state_root=self.state,
            project_id=self.project,
            issue_id=issue["issue_id"],
            decision="defer",
            actor="human-reviewer",
            rationale="The numerical change needs the author and dataset owner in the room before it can be resolved.",
            sophia_root=VENDORED_SOPHIA,
        )
        after_audit = build_topology_audit(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        after_issue = next(row for row in after_audit["issues"] if row["issue_id"] == issue["issue_id"])
        self.assertEqual(after_issue["state"], "human_action_open")
        queue = build_decision_queue(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertTrue(any(row.get("topology_issue_id") == issue["issue_id"] for row in queue["items"]))

    def test_needs_revision_stays_open_until_a_resolving_interpretation(self) -> None:
        prior = "The intervention did not improve writing outcomes."
        current = "The intervention improved writing outcomes."
        self._ingest("initial", prior, [_claim(prior, claim_type="descriptive")])
        self._ingest("revision_1", current, [_claim(current, claim_type="descriptive")])
        audit = build_topology_audit(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        issue = next(row for row in audit["issues"] if row["kind"] == "factual_surface_mutation")
        record_topology_decision(
            state_root=self.state,
            project_id=self.project,
            issue_id=issue["issue_id"],
            decision="needs_revision",
            actor="human-reviewer",
            rationale="The polarity change is not adequately justified in the current revision.",
            sophia_root=VENDORED_SOPHIA,
        )
        queue = build_decision_queue(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertTrue(any(row.get("topology_issue_id") == issue["issue_id"] for row in queue["items"]))
        record_topology_decision(
            state_root=self.state,
            project_id=self.project,
            issue_id=issue["issue_id"],
            decision="intentional_change",
            actor="human-reviewer",
            rationale="The author supplied the corrected analysis and explicitly owns the changed conclusion.",
            sophia_root=VENDORED_SOPHIA,
        )
        final_queue = build_decision_queue(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertFalse(any(row.get("topology_issue_id") == issue["issue_id"] for row in final_queue["items"]))


if __name__ == "__main__":
    unittest.main()
