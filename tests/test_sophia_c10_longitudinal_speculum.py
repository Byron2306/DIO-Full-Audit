from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.sophia.longitudinal_speculum import (
    _load_project_store,
    _match_claim,
    build_longitudinal_export,
    ingest_review_pack,
    record_author_decision,
    resolve_lineage_candidate,
)
from scripts.run_sophia_longitudinal_speculum_c10 import require_lineage_clear


ROOT = Path(__file__).resolve().parents[1]
VENDORED_SOPHIA = ROOT / "cross_folder_variants" / "Integritas-Mechanicus" / "A_CODE"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _source(label: str, *, name: str = "Feedback Study", doi: str = "10.0000/feedback", entailment: str = "partial_or_contextual_only") -> dict:
    return {
        "source_name": name,
        "support_label": label,
        "confidence": 0.78,
        "relevance": 0.75,
        "quality_score": 0.85,
        "source_quality_rubric": {"score": 0.85, "band": "usable"},
        "exact_span": "The study reports a relationship between structured feedback and academic writing outcomes.",
        "authors": ["A. Scholar"],
        "year": "2025",
        "doi": doi,
        "url": f"https://doi.org/{doi}",
        "apa_candidate": f"Scholar, A. (2025). Feedback Study. https://doi.org/{doi}",
        "page_locator": "p. 12",
        "page_status": "page/span marker visible",
        "entailment_status": entailment,
        "entailment_score": 0.76,
        "semantic_score": 0.72,
    }


def _claim(text: str, *, claim_type: str = "associational", risk: str = "medium", source_label: str = "background only", source_name: str = "Feedback Study", doi: str = "10.0000/feedback", entailment: str = "partial_or_contextual_only") -> dict:
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
            "results": [_source(source_label, name=source_name, doi=doi, entailment=entailment)],
        },
    }


def _pack(output: Path, claims: list[dict]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "CLAIM_SOURCE_LEDGER.json", {"schema": "test", "claims": claims})
    _write_json(output / "LITERATURE_MAP.json", {"deduplicated_sources": [
        {"title": "Feedback Study", "doi": "10.0000/feedback", "year": "2025", "source": "fixture"}
    ]})
    _write_json(output / "REFERENCE_AUDIT.json", {
        "missing_from_reference_list": [],
        "reference_list_entries_not_cited": [],
        "duplicate_entries": [],
        "actionable_issue_count": 0,
    })
    _write_json(output / "REVIEWER_COMMENTARY.json", {
        "status": "completed",
        "provider": "fixture-provider",
        "model": "fixture-model",
        "source": "reasoned_integrity_lane",
        "validation": {"passed": True},
        "mandos_judgment": {"passed": True},
        "article_conformity": {"summary": {"all_passed": True}},
        "repair_steps": [],
    })
    _write_json(output / "SCHOLARLY_RISK_REGISTER.json", {
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
    })


class SophiaC10LongitudinalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.project = "SOPHIA-C10-TEST"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _ingest(self, label: str, text: str, claims: list[dict]) -> dict:
        doc = self.root / f"{label}.txt"
        doc.write_text(text, encoding="utf-8")
        out = self.root / f"pack-{label}"
        _pack(out, claims)
        return ingest_review_pack(
            project_id=self.project,
            state_root=self.state,
            output_dir=out,
            manuscript_path=doc,
            revision_label=label,
            review_id=f"{self.project}-{label}",
            sophia_root=VENDORED_SOPHIA,
        )

    def test_two_versions_preserve_one_lineage_and_strengthen_evidence(self) -> None:
        text = "Structured formative feedback is associated with stronger academic writing among postgraduate learners."
        first = self._ingest("initial", text, [_claim(text, source_label="background only")])
        second_text = "Structured formative feedback is associated with improved academic writing among postgraduate learners."
        second = self._ingest(
            "revision_1",
            second_text,
            [_claim(second_text, source_label="supports", entailment="entails")],
        )
        payload = build_longitudinal_export(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertEqual(first["version_count"], 1)
        self.assertEqual(second["version_count"], 2)
        self.assertEqual(payload["lineage_count"], 1)
        lineage = payload["lineages"][0]
        self.assertEqual(lineage["occurrence_count"], 2)
        self.assertEqual(lineage["support_trajectory"], ["background_only", "support_ready"])
        self.assertEqual(lineage["state"], "evidence_strengthened")
        self.assertEqual(len(payload["native_integrity_record_hash"]), 64)
        self.assertEqual(len(payload["longitudinal_speculum_hash"]), 64)

    def test_same_wording_with_higher_epistemic_burden_is_mutation(self) -> None:
        text = "Structured formative feedback improves academic writing among postgraduate learners."
        self._ingest("initial", text, [_claim(text, claim_type="associational", risk="medium")])
        self._ingest("revision_1", text + "\n", [_claim(text, claim_type="causal", risk="high")])
        payload = build_longitudinal_export(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertEqual(payload["lineage_count"], 1)
        lineage = payload["lineages"][0]
        self.assertEqual(lineage["state"], "burden_mutated")
        changes = lineage["burden_mutations"][-1]["changes"]
        self.assertTrue(any("claim_type" in item for item in changes))
        self.assertTrue(any("evidence_risk_increased" in item for item in changes))

    def test_ambiguous_paraphrase_is_candidate_not_silent_new_claim(self) -> None:
        prior = {
            "claim": "Structured formative feedback improves postgraduate academic writing.",
            "claim_type": "causal",
            "evidence_risk": "high",
            "evidence_standard": "causal evidence required",
            "source_name": "Feedback Study",
            "doi": "10.0000/feedback",
            "draft_version_id": "draft-old",
        }
        registry = {
            "lineages": {
                "lineage-old": {"state": "active", "occurrences": [prior]},
            }
        }
        current = {
            "claim": "Formative feedback supports stronger writing by postgraduate researchers.",
            "claim_type": "causal",
            "evidence_risk": "high",
            "evidence_standard": "causal evidence required",
            "source_name": "Feedback Study",
            "doi": "10.0000/feedback",
        }
        match = _match_claim(
            project_id=self.project,
            draft_version_id="draft-new",
            index=1,
            current=current,
            registry=registry,
            previous_version_id="draft-old",
        )
        self.assertEqual(match.link_state, "continuation_candidate_needs_confirmation")
        self.assertEqual(match.candidate_parent_lineage_id, "lineage-old")
        self.assertGreaterEqual(match.score, 0.47)

    def test_human_can_confirm_ambiguous_continuation_into_native_store(self) -> None:
        initial = "Structured formative feedback improves postgraduate academic writing."
        revised = "Formative feedback supports stronger writing by postgraduate researchers."
        self._ingest("initial", initial, [_claim(initial, claim_type="causal", risk="high")])
        self._ingest("revision_1", revised, [_claim(revised, claim_type="causal", risk="high")])
        before = build_longitudinal_export(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        self.assertEqual(len(before["unresolved_continuity_candidates"]), 1)
        provisional = before["unresolved_continuity_candidates"][0]["lineage_id"]
        parent = before["unresolved_continuity_candidates"][0]["candidate_parent_lineage_id"]
        after = resolve_lineage_candidate(
            project_id=self.project,
            state_root=self.state,
            provisional_lineage_id=provisional,
            accept_parent=True,
            actor="human-reviewer",
            rationale="Same substantive claim after author paraphrase.",
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertEqual(len(after["unresolved_continuity_candidates"]), 0)
        merged = next(row for row in after["lineages"] if row["lineage_id"] == parent)
        self.assertEqual(merged["occurrence_count"], 2)
        ProjectStore, _root = _load_project_store(VENDORED_SOPHIA)
        native = ProjectStore(self.state / "project_store").load_project(self.project)
        latest = [row for row in native["claim_ledger"] if row.get("claim_lineage_id") == parent]
        self.assertEqual(len(latest), 2)
        self.assertTrue(any(row.get("lineage_link_state") == "human_confirmed_continuation" for row in latest))

    def test_author_decision_enters_native_final_decision_ledger(self) -> None:
        text = "Structured formative feedback is associated with stronger academic writing."
        self._ingest("initial", text, [_claim(text)])
        payload = build_longitudinal_export(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        lineage_id = payload["lineages"][0]["lineage_id"]
        after = record_author_decision(
            project_id=self.project,
            state_root=self.state,
            lineage_id=lineage_id,
            decision="retain_with_limitation",
            rationale="Keep the association but state the observational boundary.",
            actor="author",
            sophia_root=VENDORED_SOPHIA,
        )
        self.assertEqual(after["author_decisions"][-1]["decision"], "retain_with_limitation")
        ProjectStore, _root = _load_project_store(VENDORED_SOPHIA)
        native = ProjectStore(self.state / "project_store").export_integrity_record(project_id=self.project)
        self.assertEqual(native["counts"]["final_decisions"], 1)
        self.assertEqual(native["final_decisions"][0]["decision"], "retain_with_limitation")

    def test_disappearing_claim_is_absent_not_abandoned_without_author_decision(self) -> None:
        claim_a = "Structured formative feedback is associated with stronger academic writing."
        claim_b = "Reference-list inconsistencies increase review friction."
        self._ingest("initial", claim_a + "\n" + claim_b, [_claim(claim_a), _claim(claim_b, claim_type="descriptive", doi="10.0000/ref")])
        self._ingest("revision_1", claim_b + " revised", [_claim(claim_b, claim_type="descriptive", doi="10.0000/ref")])
        payload = build_longitudinal_export(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        absent = [row for row in payload["lineages"] if row["state"] == "absent_latest_revision"]
        self.assertEqual(len(absent), 1)
        self.assertFalse(absent[0]["latest_author_decision"])
        self.assertNotEqual(absent[0]["state"], "abandoned_by_author")

    def test_reintroduced_claim_is_not_new(self) -> None:
        claim_a = "Structured formative feedback is associated with stronger academic writing."
        claim_b = "Reference-list inconsistencies increase review friction."
        self._ingest("initial", claim_a, [_claim(claim_a)])
        self._ingest("revision_1", claim_b, [_claim(claim_b, claim_type="descriptive", doi="10.0000/ref")])
        self._ingest("revision_2", claim_a + " again", [_claim(claim_a)])
        payload = build_longitudinal_export(state_root=self.state, project_id=self.project, sophia_root=VENDORED_SOPHIA)
        lineage = next(row for row in payload["lineages"] if row["occurrence_count"] == 2)
        self.assertEqual(lineage["state"], "reintroduced")

    def test_ingest_is_idempotent_for_same_draft(self) -> None:
        text = "Structured formative feedback is associated with stronger academic writing."
        first = self._ingest("initial", text, [_claim(text)])
        second = self._ingest("initial", text, [_claim(text)])
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["version_count"], 1)
        self.assertEqual(second["lineage_count"], 1)

    def test_c10_release_gate_blocks_unresolved_continuity(self) -> None:
        job = {
            "longitudinal_speculum": {
                "state": "longitudinal_speculum_ready",
                "version_count": 2,
                "unresolved_continuity_candidates": 1,
                "longitudinal_speculum_hash": "a" * 64,
                "native_integrity_record_hash": "b" * 64,
            }
        }
        with self.assertRaises(ValueError):
            require_lineage_clear(job, minimum_versions=2)
        job["longitudinal_speculum"]["unresolved_continuity_candidates"] = 0
        require_lineage_clear(job, minimum_versions=2)


if __name__ == "__main__":
    unittest.main()
