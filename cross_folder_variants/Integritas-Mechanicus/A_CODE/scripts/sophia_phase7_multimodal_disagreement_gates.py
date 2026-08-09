#!/usr/bin/env python3
"""Phase 7 multimodal disagreement, page-anchor, and table gates."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.advanced_evidence_engine import extract_structured_tables  # noqa: E402
from backend.services.document_evidence import (  # noqa: E402
    build_document_evidence_bundle,
    cite_document_page,
    classify_multimodal_disagreement,
    render_document_evidence_context,
)


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        chart = base / "chart.png"
        chart.write_bytes(b"sidecar mediated test image")
        (base / "chart.png.ocr.txt").write_text(
            "OCR says Page 4. Figure caption says treatment group improved by 12%. "
            "User description says the chart shows 21%. These witnesses conflict.",
            encoding="utf-8",
        )
        note = base / "user_description.txt"
        note.write_text(
            "User description says Page 4 chart improvement is 21%, but OCR says 12%; disagreement remains unresolved.",
            encoding="utf-8",
        )
        bundle = build_document_evidence_bundle([
            {"source_path": str(chart), "modality": "image_ocr"},
            {"source_path": str(note), "modality": "text_only"},
        ], evidence_task="phase7_multimodal_disagreement")
        disagreement = bundle.get("multimodal_disagreement") or {}
        context = render_document_evidence_context(bundle)
        cases.append(_case(
            "ocr_caption_user_description_conflict_holds_interpretation",
            disagreement.get("status") == "disagreement_requires_human_verification"
            and disagreement.get("safe_response_mode") == "hold_visual_interpretation"
            and disagreement.get("numeric_conflict") is True
            and "Do not resolve OCR" in disagreement.get("integrity_rule", ""),
            disagreement=disagreement,
        ))
        cases.append(_case(
            "rendered_context_exposes_disagreement_contract",
            "multimodal_disagreement=status=disagreement_requires_human_verification" in context
            and "safe_response_mode=hold_visual_interpretation" in context,
            context_excerpt=context[:1600],
        ))
        page4 = cite_document_page(bundle, 4)
        missing = cite_document_page(bundle, 8)
        cases.append(_case(
            "visible_ocr_page_anchor_allowed_as_lead_only",
            page4.get("status") == "page_citation_lead"
            and page4.get("page_locator") == "p. 4"
            and "not a finalized reference" in page4.get("integrity_rule", ""),
            result=page4,
        ))
        cases.append(_case(
            "missing_ocr_page_anchor_refuses_invention",
            missing.get("status") == "page_citation_unavailable"
            and "do not invent" in " ".join(missing.get("warnings") or []).lower(),
            result=missing,
        ))

    tables = extract_structured_tables([
        {
            "source_name": "scores.csv",
            "text": "condition,score,n\nbaseline,62,18\nintervention,74,18\n",
        },
        {
            "source_name": "scores.md",
            "text": "| condition | score |\n|---|---:|\n| baseline | 62 |\n| intervention | 74 |\n",
        },
        {
            "source_name": "scores.html",
            "text": "<table><tr><th>condition</th><th>score</th></tr><tr><td>baseline</td><td>62</td></tr></table>",
        },
        {
            "source_name": "scores.fixed",
            "text": "condition      score      n\nbaseline       62         18\nintervention   74         18\n",
        },
    ])
    parsers = {table.get("parser") for table in tables.get("tables") or []}
    cases.append(_case(
        "native_table_parsing_routes_available",
        {"stdlib_csv_tsv", "markdown_pipe_table", "html_table", "fixed_width_text_table"}.issubset(parsers),
        parsers=sorted(str(p) for p in parsers),
        tables=tables,
    ))

    clean = classify_multimodal_disagreement([
        {
            "source_name": "clean_text",
            "extracted_text": "Page 1. The method section describes a conceptual design study.",
            "parser": "plain_text",
            "evidence_quality": {"quality": "readable_text"},
        }
    ])
    cases.append(_case(
        "clean_text_does_not_trigger_false_disagreement",
        clean.get("status") == "no_disagreement_detected"
        and clean.get("safe_response_mode") == "bounded_text_or_ocr_summary",
        disagreement=clean,
    ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_phase7_multimodal_disagreement_gates",
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4),
            "disagreement_hold_cases": sum(1 for case in cases if case["case_id"].endswith("holds_interpretation") and case["passed"]),
            "page_anchor_cases": sum(1 for case in cases if "page_anchor" in case["case_id"] and case["passed"]),
            "table_gate_passed": any(case["case_id"] == "native_table_parsing_routes_available" and case["passed"] for case in cases),
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_phase7_multimodal_disagreement_gates_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
