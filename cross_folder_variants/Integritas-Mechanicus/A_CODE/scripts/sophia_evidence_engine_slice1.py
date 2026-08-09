#!/usr/bin/env python3
"""Focused validation for Sophia's advanced evidence-engine slice 1."""

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

from backend.services.advanced_evidence_engine import (  # noqa: E402
    build_evidence_engine_report,
    extract_structured_tables,
    judge_claim_support,
    rank_evidence_spans,
)
from backend.services.document_evidence import build_document_evidence_bundle  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite() -> Dict[str, Any]:
    claim = "The system preserves human agency by scaffolding decisions rather than substituting authorship."
    sources = [
        {
            "source_name": "agency-support.txt",
            "text": (
                "The design preserves learner agency when AI feedback scaffolds choices, "
                "keeps authorship with the human, and makes provenance visible."
            ),
            "source_type": "local_evidence",
        },
        {
            "source_name": "agency-contradiction.txt",
            "text": (
                "The trial did not demonstrate preserved learner agency and found no evidence "
                "that authorship remained under user control."
            ),
            "source_type": "local_evidence",
        },
        {
            "source_name": "scores.csv",
            "text": "case_id,condition,score\nA,baseline,0.61\nB,intervention,0.84\n",
            "source_type": "table_attachment",
        },
        {
            "source_name": "scores.md",
            "text": "| case_id | condition | score |\n|---|---|---|\n| C | baseline | 0.55 |\n| D | intervention | 0.88 |\n",
            "source_type": "table_attachment",
        },
        {
            "source_name": "scores.html",
            "text": "<table><tr><th>case_id</th><th>condition</th><th>score</th></tr><tr><td>E</td><td>baseline</td><td>0.58</td></tr></table>",
            "source_type": "table_attachment",
        },
        {
            "source_name": "scores-fixed.txt",
            "text": "case_id  condition     score\nF        baseline      0.62\nG        intervention  0.91\n",
            "source_type": "table_attachment",
        },
    ]
    cases: List[Dict[str, Any]] = []

    ranking = rank_evidence_spans(claim, sources)
    cases.append(_case(
        "embedding_fallback_ranks_visible_span",
        ranking["ranked_spans"][0]["source_name"] == "agency-support.txt"
        and "fallback" in ranking["method"],
        method=ranking["method"],
        top=ranking["ranked_spans"][0],
    ))

    support = judge_claim_support(claim, sources[0]["text"])
    contradiction = judge_claim_support(claim, sources[1]["text"])
    nei = judge_claim_support("The intervention improves graduation rates.", sources[0]["text"])
    cases.append(_case("nli_support_label", support["label"] == "supports", result=support))
    cases.append(_case("nli_contradiction_label", contradiction["label"] == "contradicts", result=contradiction))
    cases.append(_case("nli_nei_label", nei["label"] == "not_enough_information", result=nei))

    tables = extract_structured_tables(sources)
    cases.append(_case(
        "csv_table_parser_extracts_headers_and_rows",
        any(table["parser"] == "stdlib_csv_tsv" for table in tables["tables"])
        and tables["tables"][0]["headers"] == ["case_id", "condition", "score"]
        and tables["tables"][0]["row_count_detected"] == 2,
        result=tables,
    ))
    cases.append(_case(
        "markdown_html_fixed_width_tables_extract",
        {"markdown_pipe_table", "html_table", "fixed_width_text_table"}.issubset(
            {table["parser"] for table in tables["tables"]}
        ),
        result=tables,
    ))

    with tempfile.TemporaryDirectory() as temp_dir:
        doc = Path(temp_dir) / "paged_evidence.txt"
        doc.write_text(
            "Page 1\nHuman agency means preserved choice and authorship.\f"
            "Page 2\nA figure caption describes the system architecture, but no native image analysis is available.",
            encoding="utf-8",
        )
        bundle = build_document_evidence_bundle([{"source_path": str(doc), "modality": "text_only"}])
        report = build_evidence_engine_report(
            claim,
            sources=sources,
            document_evidence=bundle,
            page_number=1,
        )
        cases.append(_case(
            "page_specific_check_present",
            (report.get("page_check") or {}).get("status") == "checked",
            result=report.get("page_check"),
        ))
        cases.append(_case(
            "vision_status_does_not_overclaim_native_vision",
            report["vision_status"]["status"] in {"text_or_ocr_only_for_visual_material", "native_vision_not_enabled"}
            and not report["vision_status"]["native_vision_enabled"],
            result=report["vision_status"],
        ))
        cases.append(_case(
            "integrity_contract_declares_method_limits",
            "report whether neural components were actually used" in report["integrity_contract"],
            result=report["integrity_contract"],
        ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_evidence_engine_slice1",
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
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence" / "sophia_evidence_engine_slice1_latest.json"))
    args = parser.parse_args()
    artifact = run_suite()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
