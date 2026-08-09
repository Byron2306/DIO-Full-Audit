#!/usr/bin/env python3
"""Phase 7/8 validation for native vision comparison, tables, figures, and citations."""

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
    export_table_cell_citations,
    extract_structured_tables,
)
from backend.services.document_evidence import (  # noqa: E402
    build_document_evidence_bundle,
    compare_native_vision_witnesses,
    map_figure_claim_to_evidence,
    render_document_evidence_context,
)


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _write_markdown_report(artifact: Dict[str, Any], out_path: Path) -> None:
    summary = artifact["summary"]
    lines = [
        "# Sophia Phase 7/8 Native Vision, Table, Figure, and Citation Gauntlet",
        "",
        f"Timestamp: `{artifact['timestamp']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Cases | {summary['total']} |",
        f"| Passed | {summary['passed']} |",
        f"| Failed | {summary['failed']} |",
        f"| Pass rate | {summary['pass_rate']:.2%} |",
        "",
        "## Case Results",
        "",
        "| Case | Result | Key signal |",
        "|---|---:|---|",
    ]
    for case in artifact["cases"]:
        result = "PASS" if case["passed"] else "FAIL"
        signal = str(case.get("signal") or case.get("status") or "")[:160]
        lines.append(f"| `{case['case_id']}` | {result} | {signal} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This run validates the next hardening slice for Sophia's document intelligence. "
        "The important change is not that Sophia can merely read more text; it is that she now keeps visual, OCR, caption, table, and page evidence as separate inspectable witnesses.",
        "",
        "What is proven here:",
        "",
        "- Native vision comparison can represent Gemini/native-vision output as one witness rather than a silent override.",
        "- Conflicting chart/caption numbers trigger a verification hold instead of a confident visual claim.",
        "- Parsed tables export page/table/row/column/cell citation leads.",
        "- Figure-to-text claim mapping returns candidate page/span anchors and conflict status.",
        "- The advanced evidence report surfaces cell citations alongside span ranking, NLI-style support, and vision readiness.",
        "",
        "What is not yet proven:",
        "",
        "- This deterministic fixture suite does not prove real-world scanned-PDF accuracy across a large corpus.",
        "- It does not benchmark native Gemini vision against human visual inspection on real figures.",
        "- It does not yet parse complex merged scientific table headers with statistical footnotes as robustly as specialist layout models.",
        "- Page/cell exports remain citation leads for human verification, not finalized bibliographic claims.",
    ])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        messy_scan = root / "messy_scanned_page.txt"
        messy_scan.write_text(
            "Page 4\nOCR says: Figure 2 caption reports 42% completion, but the scan is blurry and one digit may be wrong.\n"
            "Table 3\nCondition   Mean score   n\nSophia      84.5         12\nControl     71.0         12\n",
            encoding="utf-8",
        )
        native = root / "native_vision_witness.txt"
        native.write_text(
            "Page 4\nNative vision: Figure 2 appears to show 43% completion. Caption is partially occluded. "
            "The table lists Sophia mean score 84.5 and Control mean score 71.0.",
            encoding="utf-8",
        )
        caption = root / "caption_witness.txt"
        caption.write_text(
            "Page 4\nFigure caption: Completion rate was 42%. Chart annotation may conflict with caption.",
            encoding="utf-8",
        )
        bundle = build_document_evidence_bundle([
            {"source_path": str(messy_scan), "modality": "ocr"},
            {"source_path": str(native), "modality": "native_vision"},
            {"source_path": str(caption), "modality": "caption_text"},
        ])
        for doc in bundle["documents"]:
            if doc["source_name"] == native.name:
                doc["parser"] = "native_vision_gemini_fixture"
        bundle["native_vision_comparison"] = compare_native_vision_witnesses(bundle["documents"])

        comparison = bundle["native_vision_comparison"]
        cases.append(_case(
            "native_vision_conflict_detected",
            comparison["status"] == "native_vision_text_conflict"
            and "43%" in comparison["native_only_numbers"]
            and "42%" in comparison["text_or_ocr_only_numbers"],
            status=comparison["status"],
            signal=f"native_only={comparison['native_only_numbers']} text_or_ocr_only={comparison['text_or_ocr_only_numbers']}",
            result=comparison,
        ))

        figure_map = map_figure_claim_to_evidence("Figure 2 shows 43% completion.", bundle["documents"])
        cases.append(_case(
            "figure_to_text_conflict_mapping",
            figure_map["status"] == "figure_claim_conflict_requires_verification"
            and figure_map["conflict_count"] >= 1,
            status=figure_map["status"],
            signal=f"conflicts={figure_map['conflict_count']}",
            result=figure_map,
        ))

        context = render_document_evidence_context(bundle)
        cases.append(_case(
            "rendered_context_exposes_native_comparison",
            "[NATIVE VISION COMPARISON]" in context
            and "native_vision_text_conflict" in context,
            signal="native comparison visible to provider prompt",
            context=context[:2200],
        ))

    table_sources = [
        {
            "source_name": "complex_scientific_table_page_7",
            "page": 7,
            "text": (
                "| Condition | Mean score | SD | n | Note |\n"
                "|---|---:|---:|---:|---|\n"
                "| Sophia full | 85.2 | 4.1 | 24 | authorship-preserving support |\n"
                "| Matched tutor | 79.4 | 5.0 | 24 | no Mandos continuity |\n"
            ),
        }
    ]
    tables = extract_structured_tables(table_sources)
    citations = export_table_cell_citations(table_sources)
    cases.append(_case(
        "complex_table_cell_citations_exported",
        tables["tables_detected"] == 1
        and citations["cell_citation_count"] >= 10
        and any("row 1, column 2" in row["locator"] for row in citations["cell_citations"]),
        signal=f"cells={citations['cell_citation_count']}",
        result={"tables": tables, "citations": citations},
    ))

    report = build_evidence_engine_report(
        "Sophia full had a mean score of 85.2.",
        sources=table_sources,
        document_evidence=None,
    )
    cases.append(_case(
        "advanced_report_includes_page_cell_export",
        report["page_cell_citation_export"]["cell_citation_count"] >= 10
        and report["structured_tables"]["tables_detected"] == 1,
        signal=f"cells={report['page_cell_citation_export']['cell_citation_count']}",
        result=report,
    ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "suite": "sophia_phase78_native_table_figure_gauntlet",
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
    parser.add_argument("--out", default=str(REPO_ROOT / "evidence" / "sophia_phase78_native_table_figure_gauntlet_latest.json"))
    parser.add_argument("--md-out", default=str(REPO_ROOT / "evidence" / "SOPHIA_PHASE78_NATIVE_TABLE_FIGURE_GAUNTLET_LATEST.md"))
    args = parser.parse_args()
    artifact = run_suite()
    out = Path(args.out)
    md_out = Path(args.md_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown_report(artifact, md_out)
    print(json.dumps(artifact["summary"], indent=2))
    print(str(md_out))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
