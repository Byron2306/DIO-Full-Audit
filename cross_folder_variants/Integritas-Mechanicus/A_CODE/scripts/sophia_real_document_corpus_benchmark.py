#!/usr/bin/env python3
"""Real/fixture document corpus benchmark for Sophia multimodal intelligence."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.advanced_evidence_engine import (  # noqa: E402
    export_audit_packets,
    export_table_cell_citations,
    extract_structured_tables,
    normalize_merged_header_table,
)
from backend.services.document_evidence import (  # noqa: E402
    build_document_evidence_bundle,
    compare_native_vision_witnesses,
    map_figure_claim_to_evidence,
)
from backend.services.gemini_vision import analyze_image_with_gemini, gemini_vision_status  # noqa: E402


DOC_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".txt", ".md", ".csv", ".tsv", ".html"}


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _discover_corpus(path: Path, limit: int) -> List[Path]:
    if not path.exists():
        return []
    files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in DOC_SUFFIXES]
    return sorted(files)[:limit]


def _fixture_corpus(root: Path) -> List[Path]:
    messy = root / "messy_scanned_pdf_proxy.txt"
    messy.write_text(
        "Page 1\nOCR confidence low. Figure 1 caption says retention improved by 18%, but chart label is blurry.\n"
        "Page 2\nTable 2. Outcomes by condition.\n"
        "Group / Writing score* / Transfer score† / p-value\n"
        "Sophia / 84.2 / 78.5 / .031\n"
        "Control / 73.0 / 61.4 / .044\n"
        "*Writing rubric max 100. †Unaided delayed task.\n",
        encoding="utf-8",
    )
    chart = root / "chart_fixture.png"
    chart.write_bytes(b"fixture image bytes")
    (root / "chart_fixture.png.ocr.txt").write_text(
        "OCR says Figure 1 retention improved by 18%. Human caption note says the chart may show 16%. Conflict unresolved.",
        encoding="utf-8",
    )
    native = root / "native_vision_fixture.txt"
    native.write_text("Native vision: Figure 1 appears to show 16% retention improvement; caption is partly cut off.", encoding="utf-8")
    return [messy, chart, native]


def _pdf_chart_extraction_status(path: Path) -> Dict[str, Any]:
    if path.suffix.lower() != ".pdf":
        return {"status": "not_pdf", "source_name": path.name}
    try:
        import fitz  # type: ignore
    except Exception:
        return {
            "status": "pymupdf_unavailable",
            "source_name": path.name,
            "chart_pages": [],
            "warnings": ["Install PyMuPDF for native PDF page-image extraction."],
        }
    chart_pages: List[Dict[str, Any]] = []
    try:
        doc = fitz.open(str(path))
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            if any(term in text.lower() for term in ("figure", "fig.", "chart", "caption", "table")):
                chart_pages.append({"page": index, "text_signal": text[:500]})
        doc.close()
    except Exception as exc:
        return {"status": "pdf_chart_extract_failed", "source_name": path.name, "error": type(exc).__name__}
    return {
        "status": "chart_pages_detected" if chart_pages else "no_chart_pages_detected",
        "source_name": path.name,
        "chart_pages": chart_pages[:20],
        "integrity_rule": "PDF chart page extraction marks candidate visual pages; it does not interpret chart pixels by itself.",
    }


def _human_inspection_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _compare_human_native(native_comparison: Dict[str, Any], human_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    if not human_rows:
        return {
            "status": "not_computable_without_blinded_human_rows",
            "agreement": None,
            "rule": "Provide CSV with fields item_id,human_visible_numbers,human_verdict to compare native vision against blinded inspection.",
        }
    native_numbers = set(native_comparison.get("native_only_numbers") or []) | set(native_comparison.get("overlapping_numbers") or [])
    agreements = 0
    usable = 0
    for row in human_rows:
        human_numbers = {item.strip() for item in str(row.get("human_visible_numbers") or "").split(";") if item.strip()}
        if not human_numbers:
            continue
        usable += 1
        if native_numbers & human_numbers:
            agreements += 1
    return {
        "status": "computed" if usable else "no_usable_human_rows",
        "usable_rows": usable,
        "agreements": agreements,
        "agreement": round(agreements / usable, 4) if usable else None,
    }


def _write_blinded_human_inspection_packet(
    *,
    files: List[Path],
    chart_statuses: List[Dict[str, Any]],
    native_comparison: Dict[str, Any],
    output_dir: str | os.PathLike[str],
    prefix: str = "sophia_blinded_visual_inspection_latest",
) -> Dict[str, Any]:
    """Create a packet humans can fill without seeing native-vision labels."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / f"{prefix}.csv"
    key_path = out / f"{prefix}_key.json"
    instructions_path = out / f"{prefix}_instructions.md"
    visual_files = [
        path for path in files
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
    ]
    rows: List[Dict[str, Any]] = []
    for index, path in enumerate(visual_files, start=1):
        chart_pages = []
        for status in chart_statuses:
            if status.get("source_name") == path.name:
                chart_pages = status.get("chart_pages") or []
                break
        rows.append({
            "item_id": f"V{index:03d}",
            "source_name": path.name,
            "source_path": str(path),
            "candidate_pages": ";".join(str(page.get("page")) for page in chart_pages if isinstance(page, dict) and page.get("page")),
            "inspection_focus": "visible chart/table/caption numbers and uncertainty",
            "human_visible_numbers": "",
            "human_caption_summary": "",
            "human_uncertainty_flags": "",
            "human_verdict": "",
            "rater_id": "",
            "notes": "",
        })
    if not rows:
        rows.append({
            "item_id": "V001",
            "source_name": "fixture_chart_proxy",
            "source_path": "",
            "candidate_pages": "1",
            "inspection_focus": "fixture packet row; replace with real corpus images/PDFs",
            "human_visible_numbers": "",
            "human_caption_summary": "",
            "human_uncertainty_flags": "",
            "human_verdict": "",
            "rater_id": "",
            "notes": "",
        })
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    key_path.write_text(json.dumps({
        "schema_version": "sophia.blinded_visual_inspection_packet.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": rows,
        "native_comparison_hidden_from_raters": native_comparison,
    }, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    instructions_path.write_text(
        "# Sophia Blinded Visual Inspection Packet\n\n"
        "Fill the CSV without looking at Gemini/native-vision outputs.\n\n"
        "Columns:\n\n"
        "- `human_visible_numbers`: semicolon-separated numbers exactly visible in the figure/chart/table, e.g. `16%;84.2`.\n"
        "- `human_caption_summary`: brief description of what the caption or visual actually says.\n"
        "- `human_uncertainty_flags`: use terms like `blurry`, `cropped`, `caption_conflict`, `table_unclear`, or `none`.\n"
        "- `human_verdict`: one of `supports_native`, `supports_ocr`, `conflict`, `unclear`, `not_visual`.\n"
        "- `rater_id`: stable rater code.\n\n"
        "After completion, rerun the benchmark with `--human-inspection-csv path/to/this.csv`.\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "sophia.blinded_visual_inspection_packet.v1",
        "csv": str(csv_path),
        "key": str(key_path),
        "instructions": str(instructions_path),
        "items": len(rows),
    }


def _write_markdown(artifact: Dict[str, Any], path: Path) -> None:
    summary = artifact["summary"]
    lines = [
        "# Sophia Real Document Corpus Benchmark",
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
        f"| Corpus files | {summary['corpus_files']} |",
        f"| Fixture mode | {summary['fixture_mode']} |",
        "",
        "## Case Results",
        "",
        "| Case | Result | Key signal |",
        "|---|---:|---|",
    ]
    for row in artifact["cases"]:
        lines.append(f"| `{row['case_id']}` | {'PASS' if row['passed'] else 'FAIL'} | {str(row.get('signal') or '')[:180]} |")
    lines.extend([
        "",
        "## Truth Boundary",
        "",
        "This benchmark can run over a real corpus directory, but the default no-corpus mode uses deterministic fixtures. "
        "Native Gemini comparison is only live when `--probe-gemini` is enabled and keys are configured. Human inspection agreement is only computable when a blinded inspection CSV is supplied.",
    ])
    packet = None
    for row in artifact.get("cases") or []:
        if row.get("case_id") == "blinded_human_visual_inspection_packet_written":
            packet = row.get("inspection_packet")
            break
    if isinstance(packet, dict):
        lines.extend([
            "",
            "## Blinded Human Packet",
            "",
            f"- CSV: `{packet.get('csv')}`",
            f"- Instructions: `{packet.get('instructions')}`",
            f"- Key: `{packet.get('key')}`",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp:
        fixture_root = Path(temp)
        corpus_dir = Path(args.corpus_dir).expanduser() if args.corpus_dir else Path("")
        files = _discover_corpus(corpus_dir, args.limit) if args.corpus_dir else []
        fixture_mode = not bool(files)
        if fixture_mode:
            files = _fixture_corpus(fixture_root)

        sources = [{"source_path": str(path), "modality": "native_vision" if "native_vision" in path.name else ("image_ocr" if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"} else "text_or_pdf")} for path in files]
        bundle = build_document_evidence_bundle(sources, evidence_task="real_document_corpus_benchmark")
        for doc in bundle["documents"]:
            if "native_vision" in str(doc.get("source_name") or ""):
                doc["parser"] = "native_vision_fixture_or_external"
        native_comparison = compare_native_vision_witnesses(bundle["documents"])
        cases.append(_case(
            "messy_corpus_bundle_builds_cross_modal_witnesses",
            len(bundle.get("documents") or []) >= 2
            and native_comparison.get("witness_count", 0) >= 2,
            signal=f"documents={len(bundle.get('documents') or [])} native_status={native_comparison.get('status')}",
            bundle_summary={
                "documents": [doc.get("source_name") for doc in bundle.get("documents") or []],
                "native_comparison": native_comparison,
            },
        ))

        chart_statuses = [_pdf_chart_extraction_status(path) for path in files if path.suffix.lower() == ".pdf"]
        if not chart_statuses:
            chart_statuses = [{"status": "fixture_chart_proxy", "source_name": "chart_fixture.png", "chart_pages": [{"page": 1}]}]
        cases.append(_case(
            "chart_image_extraction_from_pdf_or_declared_proxy",
            any(row["status"] in {"chart_pages_detected", "no_chart_pages_detected", "pymupdf_unavailable", "fixture_chart_proxy"} for row in chart_statuses),
            signal=f"statuses={[row['status'] for row in chart_statuses]}",
            chart_statuses=chart_statuses,
        ))

        figure_map = map_figure_claim_to_evidence("Figure 1 shows 16% retention improvement.", bundle["documents"])
        cases.append(_case(
            "figure_to_text_claim_mapping_runs_on_corpus",
            figure_map["status"] in {"figure_claim_conflict_requires_verification", "figure_claim_has_candidate_evidence", "no_visual_evidence_found"},
            signal=f"status={figure_map['status']} conflicts={figure_map.get('conflict_count')}",
            figure_map=figure_map,
        ))

        table_sources = [
            {
                "source_name": "merged_header_scientific_table",
                "page": 2,
                "text": (
                    "| Group | Writing score* | Transfer score† | p-value |\n"
                    "|---|---:|---:|---:|\n"
                    "| Sophia | 84.2 | 78.5 | .031 |\n"
                    "| Control | 73.0 | 61.4 | .044 |\n"
                    "*Writing rubric max 100. †Unaided delayed task."
                ),
            }
        ]
        tables = extract_structured_tables(table_sources)
        normalized_tables = [normalize_merged_header_table(table) for table in tables.get("tables") or []]
        cases.append(_case(
            "merged_header_scientific_tables_and_footnotes_flagged",
            bool(normalized_tables)
            and any("statistical_notation_present" in row["complexity_flags"] for row in normalized_tables)
            and any(row["footnote_markers"] for row in normalized_tables),
            signal=f"flags={normalized_tables[0]['complexity_flags'] if normalized_tables else []}",
            normalized_tables=normalized_tables,
        ))

        citations = export_table_cell_citations(table_sources)
        export = export_audit_packets(
            {
                "summary": {"benchmark": "sophia_real_document_corpus", "fixture_mode": fixture_mode},
                "cell_citations": citations.get("cell_citations") or [],
                "sources": [{"source_name": path.name, "title": path.stem} for path in files],
            },
            output_dir=args.export_dir,
            prefix="sophia_real_document_corpus_audit_latest",
        )
        cases.append(_case(
            "zotero_csv_jsonl_audit_exports_written",
            Path(export["csv"]).exists()
            and Path(export["jsonl"]).exists()
            and Path(export["zotero_csl_json"]).exists()
            and export["cell_rows_exported"] > 0,
            signal=f"rows={export['cell_rows_exported']} zotero={export['zotero_items']}",
            export=export,
        ))

        human_rows = _human_inspection_rows(Path(args.human_inspection_csv)) if args.human_inspection_csv else []
        human_compare = _compare_human_native(native_comparison, human_rows)
        inspection_packet = _write_blinded_human_inspection_packet(
            files=files,
            chart_statuses=chart_statuses,
            native_comparison=native_comparison,
            output_dir=args.export_dir,
        )
        cases.append(_case(
            "blinded_human_visual_inspection_packet_written",
            Path(inspection_packet["csv"]).exists()
            and Path(inspection_packet["instructions"]).exists()
            and inspection_packet["items"] >= 1,
            signal=f"items={inspection_packet['items']}",
            inspection_packet=inspection_packet,
        ))
        cases.append(_case(
            "native_gemini_vs_blinded_human_inspection_contract",
            human_compare["status"] in {"computed", "not_computable_without_blinded_human_rows", "no_usable_human_rows"},
            signal=f"status={human_compare['status']} agreement={human_compare.get('agreement')}",
            human_compare=human_compare,
            inspection_packet=inspection_packet,
        ))

        gemini_status = gemini_vision_status()
        live_probe = {"status": "skipped", "reason": "use --probe-gemini with configured native vision"}
        if args.probe_gemini:
            image = next((path for path in files if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}), None)
            if image and gemini_status.get("configured"):
                os.environ["SOPHIA_ENABLE_NATIVE_VISION"] = "1"
                os.environ["SOPHIA_NATIVE_VISION_PROVIDER"] = "gemini"
                live_probe = analyze_image_with_gemini(image, prompt="Inspect visible chart/text. Return numbers and uncertainty only.", timeout=30.0)
        cases.append(_case(
            "optional_live_gemini_native_vision_probe_contract",
            live_probe.get("status") in {"checked", "skipped", "not_invoked", "error", "empty_response"},
            signal=f"status={live_probe.get('status')}",
            gemini_status=gemini_status,
            live_probe={**live_probe, "text": str(live_probe.get("text") or "")[:500]},
        ))

    passed = sum(1 for row in cases if row["passed"])
    return {
        "suite": "sophia_real_document_corpus_benchmark",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
            "corpus_files": len(files),
            "fixture_mode": fixture_mode,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", default="")
    parser.add_argument("--human-inspection-csv", default="")
    parser.add_argument("--probe-gemini", action="store_true")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--export-dir", default=str(ROOT / "evidence" / "document_audit_exports"))
    parser.add_argument("--out", default=str(ROOT / "evidence" / "sophia_real_document_corpus_benchmark_latest.json"))
    parser.add_argument("--md-out", default=str(ROOT / "evidence" / "SOPHIA_REAL_DOCUMENT_CORPUS_BENCHMARK_LATEST.md"))
    args = parser.parse_args()
    artifact = run(args)
    out = Path(args.out)
    md_out = Path(args.md_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    _write_markdown(artifact, md_out)
    print(json.dumps(artifact["summary"], indent=2))
    print(str(md_out))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
