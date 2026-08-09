#!/usr/bin/env python3
"""Phase 8 integrity-record validation for Sophia Writing Desk."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "arda_os"))

from backend.services.sophia_project_store import SophiaProjectStore  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        store = SophiaProjectStore(Path(tmp))
        project = store.upsert_project(
            project_id="phase8-proof-project",
            session_token="phase8-session",
            document_name="Fides_test.md",
            document_hash="doc-hash-001",
        )
        version = store.add_draft_version(
            project_id=project["project_id"],
            draft_text="Human agency is preserved when Sophia scaffolds judgment rather than substituting authorship.",
            source="phase8_suite",
            line_start=3,
            line_end=3,
        )
        store.append_source_records(
            project_id=project["project_id"],
            sources=[
                {
                    "name": "agency-source",
                    "category": "local_evidence",
                    "text": "Agency requires meaningful human choice, responsibility, and visible provenance.",
                }
            ],
        )
        store.append_claim_records(
            project_id=project["project_id"],
            draft_version_id=version["version_id"],
            records=[
                {
                    "record_id": "claim-supported",
                    "claim": "Sophia scaffolds judgment rather than substituting authorship.",
                    "source_name": "agency-source",
                    "support_label": "supports",
                    "exact_span": "Agency requires meaningful human choice, responsibility, and visible provenance.",
                    "warrant": "The source defines agency in terms of choice and responsibility.",
                    "limitation": "This supports the agency definition, not learning outcomes.",
                    "citation": "Agency Source (2026)",
                    "doi": "10.0000/agency.test",
                    "url": "https://example.test/agency",
                    "quality_score": 0.91,
                    "relevance": 0.88,
                    "status": "supported",
                    "entailment_status": "entails",
                    "entailment_score": 0.89,
                    "semantic_similarity": 0.84,
                    "support_model": "fixture-mnli",
                    "similarity_model": "fixture-embedding",
                    "support_source": "phase8_fixture",
                    "line_start": 3,
                    "line_end": 3,
                    "page_status": "no page number visible; do not invent one",
                },
                {
                    "record_id": "claim-needs-warrant",
                    "claim": "The architecture improves academic integrity at institutional scale.",
                    "source_name": "Unassigned",
                    "support_label": "does not support",
                    "exact_span": "",
                    "warrant": "",
                    "limitation": "Institutional-scale outcome not established.",
                    "status": "unsupported",
                    "entailment_status": "does_not_support",
                    "entailment_score": 0.92,
                    "semantic_similarity": 0.21,
                    "support_model": "fixture-mnli",
                    "similarity_model": "fixture-embedding",
                    "support_source": "phase8_fixture",
                    "line_start": 5,
                    "line_end": 5,
                },
            ],
        )
        store.append_intervention_record(
            project_id=project["project_id"],
            draft_version_id=version["version_id"],
            record={
                "task": "map_sources",
                "task_label": "Selected-claim source-support map",
                "selected_excerpt": "Sophia scaffolds judgment rather than substituting authorship.",
                "line_start": 3,
                "line_end": 3,
                "findings": ["SUPPORTED: visible source span present", "NEEDS LIMITATION: learning outcomes not proven"],
                "pedagogical_move": "Office: integrity auditor. Move: source fit then limitation.",
                "next_revision_move": "Keep the agency claim, but add a limitation about outcomes.",
                "authorship_boundary": "Sophia scaffolds; learner chooses final wording.",
                "pedagogical_plan": {
                    "selected_office": "integrity_auditor",
                    "assessment_layer": "formative",
                    "zpd_level": "moderate",
                    "bloom_target": "analyze",
                    "scaffold_intensity": "medium",
                    "feedback_style": "source_fit_scaffold",
                    "pedagogical_need_state": "source_support_gap",
                },
                "similarity_report": {
                    "summary": {"risk_level": "medium", "flagged_spans": 1},
                    "spans": [{"source_name": "agency-source", "risk_level": "medium"}],
                },
                "repair_without_rewriting": ["cite", "add limitation"],
            },
        )
        store.append_intervention_record(
            project_id=project["project_id"],
            draft_version_id=version["version_id"],
            record={
                "task": "map_sources",
                "task_label": "Selected-claim source-support map after revision",
                "selected_excerpt": "Sophia scaffolds judgment rather than substituting authorship.",
                "line_start": 3,
                "line_end": 3,
                "findings": ["SUPPORTED: visible source span present"],
                "pedagogical_move": "Office: integrity auditor. Move: confirm source fit and hand back authorship.",
                "next_revision_move": "Keep the agency claim with its limitation visible.",
                "authorship_boundary": "Sophia mirrors; learner chooses final wording.",
                "pedagogical_plan": {
                    "selected_office": "integrity_auditor",
                    "assessment_layer": "criterion",
                    "zpd_level": "moderate",
                    "bloom_target": "evaluate",
                    "scaffold_intensity": "low",
                    "feedback_style": "criterion_check",
                    "pedagogical_need_state": "criterion_check",
                },
                "response_source": "runtime_synthesis",
                "response_source_detail": "phase8_speculum_fixture",
                "repair_steps": ["source_grounding_confirmed"],
                "response_release_ledger": {"mandos_passed": True, "articles_passed": True},
                "similarity_report": {
                    "summary": {"risk_level": "low", "flagged_spans": 0},
                    "spans": [],
                },
                "repair_without_rewriting": ["keep limitation"],
            },
        )
        store.append_final_decision(
            project_id=project["project_id"],
            draft_version_id=version["version_id"],
            decision={
                "claim_record_id": "claim-supported",
                "decision": "kept_with_limitation",
                "rationale": "The claim was retained after adding a scope limitation.",
                "final_text_hash": "final-hash-001",
            },
        )

        record = store.export_integrity_record(project_id=project["project_id"])
        markdown = record.get("markdown") or ""
        cases.append(_case(
            "record_has_schema_and_hash",
            record.get("schema_version") == "sophia.integrity_record.v1"
            and len(record.get("integrity_record_hash") or "") == 64,
            hash=record.get("integrity_record_hash"),
        ))
        cases.append(_case(
            "hash_chain_present",
            all((record.get("hashes") or {}).get(key) for key in (
                "project_hash",
                "draft_versions_hash",
                "claim_ledger_hash",
                "intervention_ledger_hash",
                "source_pool_hash",
                "speculum_ledger_hash",
                "authorship_preservation_index_hash",
                "pedagogical_event_ledger_hash",
            )),
            hashes=record.get("hashes"),
        ))
        cases.append(_case(
            "counts_match_project_state",
            record["counts"]["draft_versions"] == 1
            and record["counts"]["claim_records"] == 2
            and record["counts"]["intervention_records"] == 2
            and record["counts"]["source_pool_records"] == 1
            and record["counts"].get("pedagogical_events") == 2,
            counts=record.get("counts"),
        ))
        speculum = record.get("speculum_ledger") or []
        cases.append(_case(
            "speculum_ledger_mirrors_claim_evidence_warrant_limitation",
            record["counts"].get("speculum_entries") == 2
            and len((record.get("hashes") or {}).get("speculum_ledger_hash") or "") == 64
            and any(
                item.get("claim_record_id") == "claim-supported"
                and item.get("evidence_source") == "agency-source"
                and item.get("warrant")
                and item.get("limitation")
                and (item.get("source_quality") or {}).get("quality_score") == 0.91
                and (item.get("response_provenance") or {}).get("response_source") == "runtime_synthesis"
                and (item.get("revision_movement") or {}).get("status") == "improved"
                and (item.get("evidence_transition") or {}).get("state") == "support_ready_with_limitation"
                and (item.get("claim_lineage") or {}).get("state") == "retained_with_limitation"
                and (item.get("nli_support") or {}).get("entailment_status") == "entails"
                and item.get("support_confidence", 0) >= 0.8
                for item in speculum
            )
            and any(
                item.get("claim_record_id") == "claim-needs-warrant"
                and "unsupported_or_missing_source" in (item.get("unresolved_risks") or [])
                and "nli_does_not_support" in (item.get("unresolved_risks") or [])
                and "warrant_gap" in (item.get("unresolved_risks") or [])
                for item in speculum
            )
            and "## Speculum Ledger" in markdown
            and "Learner next action" in markdown
            and "Response provenance" in markdown
            and "Revision movement" in markdown
            and "Evidence transition" in markdown
            and "Claim lineage" in markdown
            and "NLI/semantic support" in markdown,
            speculum=speculum,
            speculum_hash=(record.get("hashes") or {}).get("speculum_ledger_hash"),
        ))
        authorship_index = record.get("authorship_preservation_index") or {}
        cases.append(_case(
            "authorship_preservation_index_computed",
            authorship_index.get("schema_version") == "sophia.authorship_preservation_index.v2"
            and authorship_index.get("score", 0) >= 0.7
            and authorship_index.get("lower_bound_score", 0) <= authorship_index.get("score", 0)
            and authorship_index.get("band") in {"adequate", "strong"}
            and authorship_index.get("maturity") in {"usable_engineering_signal", "stable_engineering_signal"}
            and authorship_index.get("validation_status") == "engineering_metric_unvalidated"
            and len(authorship_index.get("entry_scores") or []) == 2
            and "source_grounding" in (authorship_index.get("dimension_means") or {})
            and "semantic_entailment" in (authorship_index.get("dimension_means") or {})
            and "response_provenance" in (authorship_index.get("dimension_means") or {})
            and "unknown_transparency" in (authorship_index.get("dimension_means") or {})
            and (authorship_index.get("distribution") or {}).get("entries") == 2
            and "authorship_safety" in ((authorship_index.get("category_subscores") or {}).get("scores") or {})
            and (authorship_index.get("provider_contribution") or {}).get("dominant_class") == "runtime_synthesized_with_repair"
            and "human rater calibration" in (authorship_index.get("calibration_needed") or [])
            and all("dimension_weights" in item for item in (authorship_index.get("entry_scores") or []))
            and "## Authorship Preservation Index" in markdown
            and "Lower-bound score" in markdown
            and "Category subscores" in markdown
            and "Provider contribution" in markdown
            and "Calibration needed" in markdown
            and len((record.get("hashes") or {}).get("authorship_preservation_index_hash") or "") == 64,
            authorship_index=authorship_index,
            authorship_index_hash=(record.get("hashes") or {}).get("authorship_preservation_index_hash"),
        ))
        pedagogy = record.get("pedagogical_event_ledger") or {}
        pedagogy_events = pedagogy.get("events") or []
        cases.append(_case(
            "pedagogical_event_telemetry_exported",
            pedagogy.get("schema_version") == "sophia.pedagogical_event_ledger.v1"
            and pedagogy.get("event_count") == 2
            and (pedagogy.get("summary") or {}).get("handback_rate") == 1.0
            and (pedagogy.get("summary") or {}).get("authorship_boundary_rate") == 1.0
            and (pedagogy.get("summary") or {}).get("office_counts", {}).get("integrity_auditor") == 2
            and any(
                event.get("learner_need") == "source_support_gap"
                and event.get("assessment_layer") == "formative"
                and event.get("scaffold_type") == "source_fit_scaffold"
                and event.get("complexity_level") == "moderate"
                and event.get("outcome_state") == "diagnosis_with_scaffold"
                for event in pedagogy_events
            )
            and any(
                event.get("learner_need") == "criterion_check"
                and event.get("assessment_layer") == "criterion"
                and event.get("scaffold_intensity") == "low"
                for event in pedagogy_events
            )
            and "## Pedagogical Event Telemetry" in markdown
            and "Learner need" in markdown
            and len((record.get("hashes") or {}).get("pedagogical_event_ledger_hash") or "") == 64,
            pedagogy=pedagogy,
            pedagogy_hash=(record.get("hashes") or {}).get("pedagogical_event_ledger_hash"),
        ))
        cases.append(_case(
            "unresolved_unsupported_claim_visible",
            any(item.get("record_id") == "claim-needs-warrant" for item in record.get("unresolved_issues") or []),
            unresolved=record.get("unresolved_issues"),
        ))
        cases.append(_case(
            "authorship_and_provenance_contract_visible",
            "human author decides final wording" in markdown
            and "No source is treated as proof" in markdown,
            markdown_excerpt=markdown[:900],
        ))
        cases.append(_case(
            "reviewer_markdown_contains_recent_intervention",
            "Selected-claim source-support map" in markdown
            and "Keep the agency claim" in markdown,
            markdown_excerpt=markdown[-1200:],
        ))
        cases.append(_case(
            "similarity_report_exported",
            (record["interventions"][0].get("similarity_summary") or {}).get("risk_level") == "medium"
            and "Similarity summary" in markdown,
            intervention=record["interventions"][0],
        ))
        cases.append(_case(
            "final_user_decision_exported",
            record["counts"]["final_decisions"] == 1
            and record["final_decisions"][0]["decision"] == "kept_with_limitation"
            and "Final User Decisions" in markdown,
            final_decisions=record.get("final_decisions"),
        ))
        packet = store.export_blinded_evaluator_packet(project_id=project["project_id"])
        cases.append(_case(
            "blinded_evaluator_packet_generated",
            packet.get("schema_version") == "sophia.blinded_evaluator_packet.v1"
            and len(packet.get("items") or []) == 2
            and len(packet.get("packet_hash") or "") == 64,
            packet={
                "packet_id": packet.get("packet_id"),
                "packet_hash": packet.get("packet_hash"),
                "items": len(packet.get("items") or []),
                "columns": packet.get("rater_form_columns"),
            },
        ))
        research = store.export_anonymized_research_dataset(project_id=project["project_id"])
        cases.append(_case(
            "anonymized_research_export_generated",
            research.get("schema_version") == "sophia.anonymized_research_export.v1"
            and len(research.get("rows") or []) == 2
            and "claim_excerpt" not in json.dumps(research)
            and len(research.get("dataset_hash") or "") == 64,
            research={
                "dataset_hash": research.get("dataset_hash"),
                "rows": len(research.get("rows") or []),
                "privacy_contract": research.get("privacy_contract"),
            },
        ))
        dashboard = store.export_reviewer_dashboard(project_id=project["project_id"])
        cases.append(_case(
            "reviewer_dashboard_generated",
            dashboard.get("schema_version") == "sophia.reviewer_dashboard.v1"
            and "<html" in (dashboard.get("html") or "")
            and "Sophia Reviewer Dashboard" in (dashboard.get("html") or "")
            and len(dashboard.get("dashboard_hash") or "") == 64,
            dashboard={
                "dashboard_hash": dashboard.get("dashboard_hash"),
                "integrity_record_hash": dashboard.get("integrity_record_hash"),
                "research_dataset_hash": dashboard.get("research_dataset_hash"),
            },
        ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_writing_desk_phase8_integrity_record",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence" / "sophia_writing_desk_phase8_integrity_record_latest.json"))
    args = parser.parse_args()
    artifact = run_suite()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
