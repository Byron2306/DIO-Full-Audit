#!/usr/bin/env python3
"""Phase 7 completion validation for page citation, tables, and vision honesty."""

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

from backend.services.advanced_evidence_engine import extract_structured_tables, vision_status_from_document_evidence  # noqa: E402
from backend.services.document_evidence import build_document_evidence_bundle, cite_document_page  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        doc = Path(temp_dir) / "paper.txt"
        doc.write_text(
            "Page 1\nThe study defines agency as meaningful human choice and visible provenance.\f"
            "Page 2\nFigure 1 caption: architecture overview. Table 1 reports condition scores.",
            encoding="utf-8",
        )
        bundle = build_document_evidence_bundle([{"source_path": str(doc), "modality": "text_only"}])
        cite = cite_document_page(bundle, 1)
        missing = cite_document_page(bundle, 9)
        cases.append(_case(
            "cite_visible_page_returns_lead",
            cite["status"] == "page_citation_lead"
            and cite["page_locator"] == "p. 1"
            and len(cite["quote_leads"]) >= 1,
            result=cite,
        ))
        cases.append(_case(
            "cite_missing_page_refuses_invention",
            missing["status"] == "page_citation_unavailable"
            and "do not invent" in " ".join(missing.get("warnings") or []),
            result=missing,
        ))
        vision = vision_status_from_document_evidence(bundle)
        cases.append(_case(
            "vision_status_text_only_for_figure_without_provider",
            vision["status"] == "text_or_ocr_only_for_visual_material"
            and not vision["native_vision_enabled"],
            result=vision,
        ))

    tables = extract_structured_tables([
        {"source_name": "csv", "text": "a,b,c\n1,2,3\n"},
        {"source_name": "md", "text": "| a | b |\n|---|---|\n| 1 | 2 |\n"},
        {"source_name": "html", "text": "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>"},
        {"source_name": "fixed", "text": "a   b   c\n1   2   3\n"},
    ])
    parsers = {table["parser"] for table in tables["tables"]}
    cases.append(_case(
        "four_table_parsers_available",
        {"stdlib_csv_tsv", "markdown_pipe_table", "html_table", "fixed_width_text_table"}.issubset(parsers),
        result=tables,
    ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_writing_desk_phase7_completion",
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
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence" / "sophia_writing_desk_phase7_completion_latest.json"))
    args = parser.parse_args()
    artifact = run_suite()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
