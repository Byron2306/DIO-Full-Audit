from __future__ import annotations

import json
import zipfile
from pathlib import Path

from products.portfolio_customer_substance import PARTIAL, READY, REFUSE, evaluate_receipt, evaluate_row


def _docx(path: Path, paragraphs: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>' for text in paragraphs)
    xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
        archive.writestr("[Content_Types].xml", "<Types/>")
    return path


def _xlsx(path: Path, values: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cells = "".join(f'<c r="A{index}" t="inlineStr"><is><t>{value}</t></is></c>' for index, value in enumerate(values, 1))
    sheet = f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">{cells}</row></sheetData></worksheet>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("[Content_Types].xml", "<Types/>")
    return path


def _candidate(path: Path) -> dict:
    return {"name": path.name, "path": str(path.resolve()), "suffix": path.suffix.casefold()}


def _row(name: str, root: Path, selected: list[Path], **extra) -> dict:
    return {
        "surface_id": extra.pop("surface_id", name),
        "surface_name": name,
        "surface_policy_id": extra.pop("surface_policy_id", "general"),
        "engineering_surface_status": extra.pop("engineering_surface_status", "ENGINEERING_READY_NEEDS_BUYER_REVIEW"),
        "pipeline_state": extra.pop("pipeline_state", "PASS"),
        "pipeline_verified_variants": extra.pop("pipeline_verified_variants", 3),
        "customer_surface_gate": {
            "state": "PASS",
            "surface_root": str(root.resolve()),
            "selected": [_candidate(path) for path in selected],
        },
        **extra,
    }


def test_blank_spreadsheet_is_not_substantive_customer_evidence(tmp_path: Path) -> None:
    root = tmp_path / "vamp"
    sheet = _xlsx(root / "evidence_table.xlsx", [])
    summary = _docx(root / "executive_summary.docx", ["KPIs included: 0", "Source files reviewed: 0", "Performance evidence snapshot"])
    row = evaluate_row(_row("VAMP Performance", root, [sheet, summary], surface_policy_id="performance_evidence_deliverable"))
    assert row["buyer_substance_state"] == REFUSE
    assert "selected_spreadsheet_contains_data" in row["hard_failures"]
    assert "vamp_has_nonzero_kpi_coverage" in row["hard_failures"]
    assert "vamp_has_nonzero_source_coverage" in row["hard_failures"]


def test_homs_exam_requires_rendered_customer_format(tmp_path: Path) -> None:
    root = tmp_path / "exam"
    paper = root / "HOMS_EXAM_PAPER.md"
    paper.parent.mkdir(parents=True, exist_ok=True)
    paper.write_text("# Examination\n" + "Question and source-bound assessment content. " * 20, encoding="utf-8")
    row = evaluate_row(_row("HOMS Exam", root, [paper], surface_policy_id="education_deliverable"))
    assert row["buyer_substance_state"] == REFUSE
    assert "exam_has_customer_presentation_format" in row["hard_failures"]


def test_document_localize_checks_languages_and_protected_tokens(tmp_path: Path) -> None:
    root = tmp_path / "localize"
    bilingual = _docx(
        root / "BILINGUAL_REVIEW_COPY.docx",
        [
            "English and Afrikaans bilingual review copy for professional customer review.",
            "Ubuntu Care Connect remains protected. Telephone 0800 220 911 remains unchanged.",
            "The approved Afrikaans term is afspraakbevestiging. Human language approval remains required.",
        ],
    )
    row = evaluate_row(_row("Document Studio Localize", root, [bilingual], surface_policy_id="document_deliverable"))
    assert row["buyer_substance_state"] == READY
    assert not row["hard_failures"]


def test_evidex_placeholder_metadata_is_partial_not_fake_ready(tmp_path: Path) -> None:
    root = tmp_path / "evidex"
    summary = _docx(root / "executive_summary.docx", ["Client organization to confirm", "Reporting Period: To be confirmed to To be confirmed", "Evidence pack with source traceability and review boundary."])
    narrative = _docx(root / "narrative_justification.docx", ["Narrative justification with evidence gaps, contradictions, source references and operator review boundary."])
    row = evaluate_row(_row("Evidex EvidenceOps", root, [summary, narrative], surface_policy_id="evidence_assurance_deliverable"))
    assert row["buyer_substance_state"] == PARTIAL
    assert "evidex_customer_identity_and_period_resolved" in row["warnings"]


def test_site_mix_can_be_substance_ready_without_claiming_customer_grade(tmp_path: Path) -> None:
    root = tmp_path / "site"
    index = root / "index.html"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("<html><body><h1>Research advisory</h1><p>Substantial governed customer website content.</p></body></html>", encoding="utf-8")
    row = evaluate_row(
        _row(
            "Site Studio",
            root,
            [index],
            surface_id="site_studio",
            customer_visual_pack_state="READY_NEEDS_YOU",
            mixed_media_scene_count=5,
            material_kind_counts={"curated_photo": 3, "artifact_render": 2, "native_renderer": 3},
        )
    )
    assert row["buyer_substance_state"] == READY
    assert row["customer_grade_claimed"] is False


def test_receipt_summary_preserves_human_boundary(tmp_path: Path) -> None:
    root = tmp_path / "localize"
    bilingual = _docx(root / "BILINGUAL_REVIEW_COPY.docx", ["English Afrikaans Ubuntu Care Connect 0800 220 911 afspraakbevestiging " * 5])
    source = {"schema": "dio.portfolio.customer_surface_gauntlet_receipt.v1", "wave": "alpha", "rows": [_row("Document Studio Localize", root, [bilingual])]}
    audit = evaluate_receipt(source)
    assert audit["surface_count"] == 1
    assert audit["substance_ready_count"] == 1
    assert audit["human_buyer_review_required"] is True
    assert audit["customer_grade_claimed"] is False
    assert audit["commercial_validation"] == "UNPROVED"
