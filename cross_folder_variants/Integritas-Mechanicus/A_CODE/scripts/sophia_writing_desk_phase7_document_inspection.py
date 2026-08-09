#!/usr/bin/env python3
"""Phase 7 document inspection validation for Sophia Writing Desk."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARDA_ROOT = ROOT / "arda_os"
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.document_evidence import (  # noqa: E402
    build_document_evidence_bundle,
    compare_claim_to_document_page,
    extract_document_evidence,
    inspect_document_page,
    render_document_evidence_context,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase7_document_inspection_latest.json")
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        clean = _write(
            base / "clean_article.txt",
            "This article defines human agency through accountable choice and reflective judgment. "
            "The method section describes a conceptual design study with explicit limitations.",
        )
        paged = _write(
            base / "paged_article.txt",
            "Page 1\nThe introduction frames academic integrity as disclosure, detection, and assessment redesign.\f"
            "Page 2\nThe findings report figure 1 and table 2 as evidence summaries, but the table structure is uncertain.",
        )
        sidecar_image = base / "scan.png"
        sidecar_image.write_bytes(b"not a real image; sidecar OCR is the bounded evidence")
        _write(
            base / "scan.png.ocr.txt",
            "OCR confidence is medium. Page 3. Figure caption says learner agency improved, but native vision is unavailable.",
        )
        empty_image = base / "empty_scan.png"
        empty_image.write_bytes(b"not a real image and no sidecar")

        cases = [
            {
                "id": "clean_text_readable",
                "path": clean,
                "modality": "text_only",
                "expect_quality": "readable_text",
                "expect_coverage": {"thin"},
                "expect_warnings": {"page_number_unavailable"},
            },
            {
                "id": "paged_figure_table",
                "path": paged,
                "modality": "text_only",
                "expect_pages": {1, 2},
                "expect_warnings": {"figure_or_caption_text_only_no_native_vision", "table_structure_uncertain_without_table_parser"},
                "expect_page_status": "page markers visible",
            },
            {
                "id": "image_sidecar_ocr",
                "path": sidecar_image,
                "modality": "image_ocr",
                "expect_quality": "ocr_supported",
                "expect_warnings": {"ocr_mediated_evidence"},
                "expect_pages": {3},
            },
            {
                "id": "image_without_ocr",
                "path": empty_image,
                "modality": "image_ocr_required",
                "expect_quality": "unreadable",
                "expect_warnings": {"page_number_unavailable", "image_text_unavailable"},
            },
        ]
        for case in cases:
            evidence = extract_document_evidence(case["path"], modality=case["modality"])
            inspection = evidence.get("document_inspection") or {}
            warnings = set(inspection.get("warnings") or [])
            pages = set(inspection.get("page_numbers") or [])
            checks = {
                "inspection_present": bool(inspection),
                "quality": not case.get("expect_quality") or (evidence.get("evidence_quality") or {}).get("quality") == case["expect_quality"],
                "coverage": not case.get("expect_coverage") or inspection.get("page_coverage") in case["expect_coverage"],
                "warnings": not case.get("expect_warnings") or case["expect_warnings"].issubset(warnings),
                "warning_absent": not case.get("expect_warning_absent") or case["expect_warning_absent"] not in warnings,
                "pages": not case.get("expect_pages") or case["expect_pages"].issubset(pages),
                "page_status": not case.get("expect_page_status") or inspection.get("page_number_status") == case["expect_page_status"],
                "safe_use": len(inspection.get("safe_use") or []) >= 3,
            }
            rows.append({
                "case_id": case["id"],
                "passed": all(checks.values()),
                "checks": checks,
                "quality": evidence.get("evidence_quality"),
                "inspection": inspection,
            })

        bundle = build_document_evidence_bundle([
            {"source_path": str(paged), "modality": "text_only"},
            {"source_path": str(sidecar_image), "modality": "image_ocr"},
        ], evidence_task="phase7_document_inspection")
        context = render_document_evidence_context(bundle)
        context_checks = {
            "contract_present": "[DOCUMENT EVIDENCE CONTRACT]" in context,
            "inspection_present": "inspection=" in context,
            "warnings_present": "inspection_warnings=" in context,
            "page_honesty_present": "page_status=page markers visible" in context,
        }
        rows.append({
            "case_id": "rendered_context_contract",
            "passed": all(context_checks.values()),
            "checks": context_checks,
            "context_excerpt": context[:1200],
        })
        page_two = inspect_document_page(bundle, 2)
        page_two_checks = {
            "page_available": page_two.get("status") == "page_available",
            "has_page_two_spans": any(str(span.get("page") or "") == "2" for span in page_two.get("spans") or []),
            "summary_mentions_table": "table" in str(page_two.get("summary") or "").lower(),
            "page_honesty": page_two.get("page_number_status") == "page markers visible",
        }
        rows.append({
            "case_id": "inspect_page_two",
            "passed": all(page_two_checks.values()),
            "checks": page_two_checks,
            "page": page_two,
        })
        missing_page = inspect_document_page(bundle, 9)
        missing_page_checks = {
            "page_not_available": missing_page.get("status") == "page_not_available",
            "no_spans": not missing_page.get("spans"),
            "no_invention_warning": "do not invent page evidence" in " ".join(missing_page.get("warnings") or []),
        }
        rows.append({
            "case_id": "inspect_missing_page",
            "passed": all(missing_page_checks.values()),
            "checks": missing_page_checks,
            "page": missing_page,
        })
        comparison = compare_claim_to_document_page(
            "The findings use a figure and table as evidence summaries, but table structure remains uncertain.",
            bundle,
            2,
        )
        sim = comparison.get("similarity") or {}
        comparison_checks = {
            "checked": comparison.get("status") == "checked",
            "page_summary_present": bool(comparison.get("page_summary")),
            "similarity_medium_or_high": (sim.get("summary") or {}).get("risk_level") in {"medium", "high"},
            "source_span_present": bool(((sim.get("spans") or [{}])[0]).get("source_span")),
        }
        rows.append({
            "case_id": "compare_claim_to_page",
            "passed": all(comparison_checks.values()),
            "checks": comparison_checks,
            "comparison": comparison,
        })

    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "passed": passed,
        "total": len(rows),
        "pass_rate": round(passed / len(rows), 4),
        "inspection_failures": len(rows) - passed,
        "page_specific_cases": sum(1 for row in rows if row["case_id"] in {"inspect_page_two", "inspect_missing_page", "compare_claim_to_page"} and row["passed"]),
    }
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase7_document_inspection",
        "summary": summary,
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
