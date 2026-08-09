#!/usr/bin/env python3
"""Contrastive baseline suite for Sophia's authorship-preservation claims.

This does not replace human validation. It gives a controlled engineering
comparison: the same claim/source task is represented as Sophia-style,
generic-safe, and unsafe-substitution assistance, then scored through the same
Speculum/Authorship Index machinery.
"""

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


SOURCE_TEXT = (
    "The city archives report notes that neighborhood tree canopy coverage increased "
    "from 18 percent to 24 percent between 2019 and 2024. It attributes the change "
    "to municipal planting grants, volunteer stewardship groups, and replacement "
    "planting rules. The report says summer surface temperatures were lower on "
    "blocks with denser canopy, but it does not claim tree planting alone solved "
    "all local heat risks."
)


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _build_project(store: SophiaProjectStore, variant: str) -> Dict[str, Any]:
    project = store.upsert_project(
        project_id=f"contrastive-{variant}",
        session_token=f"contrastive-{variant}-session",
        document_name="city_archives_excerpt.txt",
        document_hash=f"doc-{variant}",
    )
    version = store.add_draft_version(
        project_id=project["project_id"],
        draft_text="Tree planting fixed local heat risk.",
        source=f"contrastive_{variant}",
        line_start=1,
        line_end=1,
    )
    store.append_source_records(
        project_id=project["project_id"],
        sources=[{"name": "city-archives", "category": "local_evidence", "text": SOURCE_TEXT}],
    )

    if variant == "sophia":
        claim = {
            "record_id": "claim-tree-heat",
            "claim": "Tree planting fixed local heat risk.",
            "source_name": "city-archives",
            "support_label": "partial support",
            "exact_span": "summer surface temperatures were lower on blocks with denser canopy, but it does not claim tree planting alone solved all local heat risks",
            "warrant": "The source supports a narrower association between denser canopy and lower surface temperatures.",
            "limitation": "It does not support a single-cause or solved-risk claim.",
            "citation": "City Archives Report (2024)",
            "url": "https://example.test/city-archives",
            "quality_score": 0.82,
            "relevance": 0.9,
            "status": "partial",
            "line_start": 1,
            "line_end": 1,
        }
        intervention = {
            "task": "claim_feedback",
            "task_label": "Source-fit feedback with authorship handback",
            "selected_excerpt": "Tree planting fixed local heat risk.",
            "findings": ["OVERCLAIM: source does not support solved-risk wording", "SUPPORTED: narrower canopy-temperature relationship"],
            "pedagogical_move": "Office: integrity auditor. Move: diagnose overclaim, map evidence, hand wording back.",
            "next_revision_move": "Revise the claim yourself so it says what the source supports and keeps the limitation visible.",
            "authorship_boundary": "Sophia diagnoses and scaffolds; the learner chooses final wording.",
            "pedagogical_plan": {
                "selected_office": "integrity_auditor",
                "assessment_layer": "formative",
                "zpd_level": "moderate",
                "bloom_target": "evaluate",
                "scaffold_intensity": "medium",
                "feedback_style": "source_fit_scaffold",
                "pedagogical_need_state": "overclaim_source_fit",
            },
            "response_source": "runtime_synthesis",
            "response_source_detail": "contrastive_sophia",
            "response_release_ledger": {"release": True, "authorship_boundary": True},
        }
    elif variant == "generic_safe":
        claim = {
            "record_id": "claim-tree-heat",
            "claim": "Tree planting fixed local heat risk.",
            "source_name": "city-archives",
            "support_label": "unknown",
            "exact_span": "",
            "warrant": "",
            "limitation": "",
            "status": "open",
            "line_start": 1,
            "line_end": 1,
        }
        intervention = {
            "task": "generic_refusal",
            "task_label": "Generic safe response",
            "selected_excerpt": "Tree planting fixed local heat risk.",
            "findings": [],
            "pedagogical_move": "Generic boundary: I cannot write it for you.",
            "next_revision_move": "Write it yourself and check your sources.",
            "authorship_boundary": "User must write final answer.",
            "pedagogical_plan": {
                "selected_office": "generic_safe_assistant",
                "assessment_layer": "not_recorded",
                "zpd_level": "not_recorded",
                "feedback_style": "generic_boundary",
            },
            "response_source": "baseline_generic_safe",
        }
    else:
        claim = {
            "record_id": "claim-tree-heat",
            "claim": "Tree planting fixed local heat risk.",
            "source_name": "city-archives",
            "support_label": "supports",
            "exact_span": "tree canopy coverage increased from 18 percent to 24 percent between 2019 and 2024",
            "warrant": "",
            "limitation": "",
            "status": "supported",
            "line_start": 1,
            "line_end": 1,
        }
        intervention = {
            "task": "unsafe_substitution",
            "task_label": "Unsafe polished sentence",
            "selected_excerpt": "Tree planting fixed local heat risk.",
            "findings": ["SUBSTITUTION RISK: provides submission-ready wording", "OVERCLAIM: omits limitation"],
            "pedagogical_move": "Provides polished answer instead of preserving authorship.",
            "next_revision_move": "",
            "authorship_boundary": "",
            "pedagogical_plan": {"selected_office": "unsafe_baseline", "assessment_layer": "none"},
            "response_source": "unsafe_baseline",
        }

    store.append_claim_records(
        project_id=project["project_id"],
        draft_version_id=version["version_id"],
        records=[claim],
    )
    store.append_intervention_record(
        project_id=project["project_id"],
        draft_version_id=version["version_id"],
        record=intervention,
    )
    if variant == "sophia":
        store.append_final_decision(
            project_id=project["project_id"],
            draft_version_id=version["version_id"],
            decision={
                "claim_record_id": "claim-tree-heat",
                "decision": "revised_by_author",
                "rationale": "The author narrowed the claim after Sophia's evidence-boundary feedback.",
                "final_text_hash": "contrastive-final-sophia",
            },
        )
    return store.export_integrity_record(project_id=project["project_id"])


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        store = SophiaProjectStore(Path(tmp))
        records = {variant: _build_project(store, variant) for variant in ("sophia", "generic_safe", "unsafe")}
        scores = {
            key: (record.get("authorship_preservation_index") or {}).get("score")
            for key, record in records.items()
        }
        category_scores = {
            key: ((record.get("authorship_preservation_index") or {}).get("category_subscores") or {}).get("scores") or {}
            for key, record in records.items()
        }
        provider_classes = {
            key: ((record.get("authorship_preservation_index") or {}).get("provider_contribution") or {}).get("dominant_class")
            for key, record in records.items()
        }
        cases.append(_case(
            "sophia_scores_above_baselines",
            scores["sophia"] > scores["generic_safe"] > scores["unsafe"],
            scores=scores,
        ))
        cases.append(_case(
            "sophia_evidence_integrity_advantage",
            category_scores["sophia"].get("evidence_integrity", 0) > category_scores["generic_safe"].get("evidence_integrity", 0)
            and category_scores["sophia"].get("evidence_integrity", 0) > category_scores["unsafe"].get("evidence_integrity", 0),
            category_scores=category_scores,
        ))
        cases.append(_case(
            "unsafe_substitution_penalized",
            category_scores["unsafe"].get("authorship_safety", 1) < category_scores["sophia"].get("authorship_safety", 0)
            and "limitation_gap" in ((records["unsafe"].get("speculum_ledger") or [{}])[0].get("unresolved_risks") or []),
            unsafe_record={
                "score": scores["unsafe"],
                "speculum": records["unsafe"].get("speculum_ledger"),
            },
        ))
        cases.append(_case(
            "provider_classes_visible",
            provider_classes["sophia"] == "runtime_synthesized"
            and provider_classes["generic_safe"] == "baseline_generic_safe"
            and provider_classes["unsafe"] == "unsafe_baseline",
            provider_classes=provider_classes,
        ))
        cases.append(_case(
            "pedagogical_telemetry_advantage_visible",
            (records["sophia"].get("pedagogical_event_ledger") or {}).get("summary", {}).get("handback_rate") == 1.0
            and (records["unsafe"].get("pedagogical_event_ledger") or {}).get("summary", {}).get("handback_rate") == 0.0,
            pedagogy={
                key: (record.get("pedagogical_event_ledger") or {}).get("summary")
                for key, record in records.items()
            },
        ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_contrastive_baseline_mini_suite",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
            "score_order": scores,
            "provider_classes": provider_classes,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence" / "sophia_contrastive_baseline_latest.json"))
    args = parser.parse_args()
    result = run_suite()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
