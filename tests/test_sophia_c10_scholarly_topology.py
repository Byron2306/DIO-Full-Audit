from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.sophia.c10_gate import require_scholarly_release_clear_summary
from adapters.sophia.longitudinal_speculum import (
    build_longitudinal_export,
    ingest_review_pack,
    record_author_decision,
)
from adapters.sophia.scholarly_topology import (
    build_and_write_topology,
    build_decision_queue,
    build_topology_audit,
    record_topology_decision,
)


ROOT = Path(__file__).resolve().parents[1]
VENDORED_SOPHIA = ROOT / "cross_folder_variants" / "Integritas-Mechanicus" / "A_CODE"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _source(
    label: str = "background only",
    *,
    name: str = "Feedback Study",
    doi: str = "10.0000/feedback",
    entailment: str = "partial_or_contextual_only",
) -> dict:
    return {
        "source_name": name,
        "support_label": label,
        "confidence": 0.80,
        "relevance": 0.78,
        "quality_score": 0.87,
        "source_quality_rubric": {"score": 0.87, "band": "usable"},
        "exact_span": "The study reports a relationship between feedback and postgraduate writing outcomes.",
        "authors": ["A. Scholar"],
        "year": "2025",
        "doi": doi,
        "url": f"https://doi.org/{doi}",
        "apa_candidate": f"Scholar, A. (2025). Feedback Study. https://doi.org/{doi}",
        "page_locator": "p. 12",
        "page_status": "page/span marker visible",
        "entailment_status": entailment,
        "entailment_score": 0.78,
        "semantic_score": 0.74,
    }


def _claim(
    text: str,
    *,
    claim_type: str = "associational",
    risk: str = "medium",
    source_label: str = "background only",
    source_name: str = "Feedback Study",
    doi: str = "10.0000/feedback",
    entailment: str = "partial_or_contextual_only",
) -> dict:
    standard = {
        "associational": "Needs evidence of an observed relationship; do not infer causation.",
        "causal": "Needs design capable of causal inference; otherwise downgrade to association or proposal.",
        "descriptive": "Needs a source that directly documents the stated condition.",
    }.get(claim_type, "Needs evidence proportionate to the claim.")
    return {
        "claim_record": {
            "claim": text,
            "claim_type": claim_type,
            "evidence_standard": standard,
            "evidence_risk": risk,
        },
        "source_map": {
            "results": [
                _source(
                    source_label,
                    name=source_name,
                    doi=doi,
                    entailment=entailment,
                )
            ]
        },
    }


def _pack(output: Path, claims: list[dict]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "CLAIM_SOURCE_LEDGER.json", {"schema": "test", "claims": claims})
    _write_json(
        output / "LITERATURE_MAP.json",
        {
            "deduplicated_sources": [
                {
                    "title": "Feedback Study",
                    "doi": "10.0000/feedback",
                    "year": "2025",
                    "source": "fixture",
                }
            ]
        },
    )
    _write_json(
        output / "REFERENCE_AUDIT.json",
        {
            "missing_from_reference_list": [],
            "reference_list_entries_not_cited": [],
            "duplicate_entries": [],
            "actionable_issue_count": 0,
        },
    )
    _write_json(
        output / "REVIEWER_COMMENTARY.json",
        {
            "status": "completed",
            "provider": "fixture-provider",
            "model": "fixture-model",
            "source": "reasoned_integrity_lane",
            "validation": {"passed": True},
            "mandos_judgment": {"passed": True},
            "article_conformity": {"summary": {"all_passed": True}},
            "repair_steps": [],
        },
    )
    _write_json(
        output / "SCHOLARLY_RISK_REGISTER.json",
        {
            "state": "attention_required",
            "open_risk_count": len(claims),
            "risks": [
                {
                    "risk_id": f"C{i}",
                    "kind": "claim_evidence_fit",
                    "severity": "medium",
                    "problems": ["fixture_review_required"],
                }
                for i, _ in enumerate(claims, 1)
            ],
        },
    )


class SophiaC10ScholarlyTopologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.project = "SOPHIA-C10-TOPOLOGY-TEST"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _ingest(self, label: str, text: str, claims: list[dict]) -> dict:
        doc = self.root / f"{label}.txt"
        doc.write_text(text, encoding="utf-8")
        output = self.root / f"pack-{label}"
        _pack(output, claims)
        return ingest_review_pack(
            project_id=self.project,
            state_root=self.state,
            output_dir=output,
            manuscript_path=doc,
            revision_label=label,
            review_id=f"{self.project}-{label}",
            sophia_root=VENDORED_SOPHIA,
        )

    def _lineage_summary(self) -> dict:
        return build_longitudinal_export(
            state_root=self.state,
            project_id=self.project,
            sophia_root=VENDORED_SOPHIA,
        )

    def test_claim_split_is_a_human_topology_question(self) -> None:
        parent = "Structured feedback improves academic writing and revision quality among postgraduate learners."
        child_a = "Structured feedback improves academic writing among postgraduate learners."
        child_b = "Structured feedback improves revision quality among postgraduate learners."
        self._ingest("initial", parent, [_claim(parent)])
        self._ingest("revision_1", child_a + "\n" + child_b, [_claim(child_a), _claim(child_b)])
        audit = build_topology_audit(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        splits = [row for row in audit["issues"] if row["kind"] == "claim_split_candidate"]
        self.assertGreaterEqual(len(splits), 1)
        queue = build_decision_queue(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertTrue(any(row["kind"] == "topology:claim_split_candidate" for row in queue["items"]))
        resolved = record_topology_decision(
            state_root=self.state,
            project_id=self.project,
            issue_id=splits[0]["issue_id"],
            decision="confirm_split",
            actor="human-reviewer",
            rationale="The author intentionally decomposed one composite proposition into two separately supportable claims.",
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertEqual(resolved["state"], "scholarly_topology_ready")

    def test_claim_merge_is_visible_instead_of_collapsed_to_best_parent(self) -> None:
        prior_a = "Structured feedback improves academic writing among postgraduate learners."
        prior_b = "Structured feedback improves revision quality among postgraduate learners."
        current = "Structured feedback improves academic writing and revision quality among postgraduate learners."
        self._ingest("initial", prior_a + "\n" + prior_b, [_claim(prior_a), _claim(prior_b)])
        self._ingest("revision_1", current, [_claim(current)])
        audit = build_topology_audit(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertTrue(any(row["kind"] == "claim_merge_candidate" for row in audit["issues"]))

    def test_numeric_and_negation_mutations_are_high_priority_review_signals(self) -> None:
        prior = "The intervention improved writing for 42% of participants."
        current = "The intervention did not improve writing for 57% of participants."
        self._ingest("initial", prior, [_claim(prior, claim_type="descriptive")])
        self._ingest("revision_1", current, [_claim(current, claim_type="descriptive")])
        audit = build_topology_audit(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        mutations = [row for row in audit["issues"] if row["kind"] == "factual_surface_mutation"]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0]["severity"], "high")
        joined = " | ".join(mutations[0]["mutations"])
        self.assertIn("numeric_surface", joined)
        self.assertIn("negation_surface", joined)

    def test_burden_mutation_stays_blocking_until_author_owns_it(self) -> None:
        text = "Structured formative feedback improves academic writing among postgraduate learners."
        self._ingest("initial", text, [_claim(text, claim_type="associational", risk="medium")])
        self._ingest("revision_1", text + "\n", [_claim(text, claim_type="causal", risk="high")])
        queue = build_decision_queue(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        obligations = [row for row in queue["items"] if row["kind"] == "author_decision_required_for_burden_mutation"]
        self.assertEqual(len(obligations), 1)
        longitudinal = self._lineage_summary()
        lineage_id = longitudinal["lineages"][0]["lineage_id"]
        record_author_decision(
            project_id=self.project,
            state_root=self.state,
            lineage_id=lineage_id,
            decision="strengthen_evidence",
            rationale="The author intends to retain causal wording only if evidence meeting the stronger causal burden is added.",
            actor="author",
            sophia_root=VENDORED_SOPHIA,
        )
        after = build_decision_queue(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertFalse(any(row["kind"] == "author_decision_required_for_burden_mutation" for row in after["items"]))

    def test_high_risk_disappearance_is_not_silently_called_resolved(self) -> None:
        high = "The intervention causes durable improvements in postgraduate academic writing."
        other = "Reference-list inconsistencies increase review friction."
        self._ingest("initial", high + "\n" + other, [_claim(high, claim_type="causal", risk="high"), _claim(other, claim_type="descriptive")])
        self._ingest("revision_1", other, [_claim(other, claim_type="descriptive")])
        queue = build_decision_queue(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        disappeared = [row for row in queue["items"] if row["kind"] == "high_risk_claim_disappearance_needs_author_decision"]
        self.assertEqual(len(disappeared), 1)
        lineage_id = disappeared[0]["lineage_id"]
        record_author_decision(
            project_id=self.project,
            state_root=self.state,
            lineage_id=lineage_id,
            decision="remove",
            rationale="The author intentionally removed the causal claim because the available evidence did not meet its burden.",
            actor="author",
            sophia_root=VENDORED_SOPHIA,
        )
        after = build_decision_queue(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertFalse(any(row["kind"] == "high_risk_claim_disappearance_needs_author_decision" for row in after["items"]))

    def test_new_high_risk_claim_requires_explicit_author_decision(self) -> None:
        first = "Feedback is associated with revision quality."
        new_high = "Structured feedback causes durable gains in dissertation quality."
        self._ingest("initial", first, [_claim(first)])
        self._ingest("revision_1", first + "\n" + new_high, [_claim(first), _claim(new_high, claim_type="causal", risk="high")])
        queue = build_decision_queue(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertTrue(any(row["kind"] == "new_high_risk_claim_needs_author_decision" for row in queue["items"]))

    def test_final_release_gate_requires_zero_scholarly_decision_obligations(self) -> None:
        c10 = {
            "state": "longitudinal_speculum_ready",
            "version_count": 2,
            "unresolved_continuity_candidates": 0,
            "longitudinal_speculum_hash": "a" * 64,
            "native_integrity_record_hash": "b" * 64,
        }
        topology = {
            "state": "scholarly_topology_ready",
            "blocking_decision_queue": 2,
            "topology_audit_hash": "c" * 64,
            "decision_queue_hash": "d" * 64,
        }
        with self.assertRaises(ValueError):
            require_scholarly_release_clear_summary(c10, minimum_versions=2, topology=topology)
        topology["blocking_decision_queue"] = 0
        require_scholarly_release_clear_summary(c10, minimum_versions=2, topology=topology)

    def test_command_bundle_is_hash_bound_and_supervisor_facing(self) -> None:
        first = "Structured feedback is associated with stronger academic writing."
        second = "Structured feedback may be associated with stronger academic writing."
        self._ingest("initial", first, [_claim(first)])
        self._ingest("revision_1", second, [_claim(second)])
        summary = build_and_write_topology(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertEqual(len(summary["topology_audit_hash"]), 64)
        self.assertEqual(len(summary["decision_queue_hash"]), 64)
        html = (self.state / "SUPERVISOR_COMMAND_BRIEF.html").read_text(encoding="utf-8")
        self.assertIn("Needs a human decision", html)
        audit = (self.state / "SCHOLARLY_TOPOLOGY_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("topology hypotheses", audit)
        self.assertIn("not findings of author intent", audit)


if __name__ == "__main__":
    unittest.main()
