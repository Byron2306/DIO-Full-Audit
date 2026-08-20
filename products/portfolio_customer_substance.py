from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


READY = "SUBSTANCE_READY_NEEDS_BUYER_REVIEW"
PARTIAL = "SUBSTANCE_PARTIAL_NEEDS_REPAIR"
REFUSE = "REFUSE_CUSTOMER_SUBSTANCE"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return ""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _xlsx_nonempty_cells(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as archive:
            worksheet_names = [name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for item in root.findall(".//s:si", ns):
                    shared.append("".join(node.text or "" for node in item.findall(".//s:t", ns)))
            count = 0
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for name in worksheet_names:
                root = ET.fromstring(archive.read(name))
                for cell in root.findall(".//s:c", ns):
                    value = cell.find("s:v", ns)
                    inline = cell.find("s:is", ns)
                    text = ""
                    if inline is not None:
                        text = "".join(node.text or "" for node in inline.findall(".//s:t", ns))
                    elif value is not None and value.text is not None:
                        text = value.text
                        if cell.attrib.get("t") == "s":
                            try:
                                text = shared[int(text)]
                            except (ValueError, IndexError):
                                pass
                    if _clean(text):
                        count += 1
            return count
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        return 0


def _text(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        return _docx_text(path)
    if suffix in {".md", ".txt", ".csv", ".html", ".htm"}:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        if suffix in {".html", ".htm"}:
            raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<[^>]+>", " ", raw)
        return _clean(raw)
    return ""


def _files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return [path for path in sorted(root.rglob("*")) if path.is_file()]


def _find(files: list[Path], name: str) -> Path | None:
    target = name.casefold()
    return next((path for path in files if path.name.casefold() == target), None)


def _check(check: str, passed: bool, *, observed: Any = None, severity: str = "REFUSE", note: str = "") -> dict[str, Any]:
    return {
        "check": check,
        "passed": bool(passed),
        "observed": observed,
        "severity": severity,
        "note": note,
    }


def _generic_checks(files: list[Path], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    selected_names = [str(row.get("name") or "") for row in selected]
    substantive_selected = [name for name in selected_names if "invoice" not in name.casefold()]
    checks.append(_check("non_invoice_customer_artifact_selected", bool(substantive_selected), observed=substantive_selected))

    selected_xlsx = [Path(str(row.get("path") or "")) for row in selected if str(row.get("suffix") or "").casefold() == ".xlsx"]
    for path in selected_xlsx:
        cells = _xlsx_nonempty_cells(path) if path.is_file() else 0
        checks.append(_check("selected_spreadsheet_contains_data", cells >= 2, observed={"file": path.name, "nonempty_cells": cells}))

    selected_docx = [Path(str(row.get("path") or "")) for row in selected if str(row.get("suffix") or "").casefold() == ".docx"]
    for path in selected_docx:
        chars = len(_docx_text(path)) if path.is_file() else 0
        checks.append(_check("selected_docx_contains_substantive_text", chars >= 120, observed={"file": path.name, "visible_characters": chars}))
    return checks


def _homs_exam(files: list[Path]) -> list[dict[str, Any]]:
    final_suffixes = {".pdf", ".docx", ".html", ".htm"}
    finals = [path.name for path in files if path.suffix.casefold() in final_suffixes and "exam" in path.name.casefold()]
    return [
        _check(
            "exam_has_customer_presentation_format",
            bool(finals),
            observed=finals,
            note="A customer-grade exam should graduate beyond Markdown into a rendered PDF, DOCX or HTML surface.",
        )
    ]


def _homs_learning(files: list[Path]) -> list[dict[str, Any]]:
    pdfs = [path for path in files if path.suffix.casefold() == ".pdf" and path.stat().st_size >= 50_000]
    return [
        _check("learning_pack_has_multiple_rendered_pdf_artifacts", len(pdfs) >= 2, observed=[path.name for path in pdfs]),
    ]


def _sophia(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _check(
            "sophia_all_adversarial_variants_grounded",
            row.get("pipeline_state") == "PASS" and int(row.get("pipeline_verified_variants") or 0) == 3,
            observed={"pipeline_state": row.get("pipeline_state"), "verified_variants": row.get("pipeline_verified_variants")},
        )
    ]


def _vamp(files: list[Path]) -> list[dict[str, Any]]:
    summary = _find(files, "executive_summary.docx")
    summary_text = _docx_text(summary) if summary else ""
    tables = [path for path in files if path.suffix.casefold() == ".xlsx" and "evidence" in path.name.casefold()]
    table_counts = {path.name: _xlsx_nonempty_cells(path) for path in tables}
    return [
        _check("vamp_executive_summary_present", bool(summary), observed=summary.name if summary else None),
        _check("vamp_has_nonzero_kpi_coverage", "KPIs included: 0" not in summary_text and "KPIs included:" in summary_text, observed="KPIs included: 0" if "KPIs included: 0" in summary_text else "nonzero_or_unparsed"),
        _check("vamp_has_nonzero_source_coverage", "Source files reviewed: 0" not in summary_text and "Source files reviewed:" in summary_text, observed="Source files reviewed: 0" if "Source files reviewed: 0" in summary_text else "nonzero_or_unparsed"),
        _check("vamp_evidence_table_contains_rows", any(count >= 2 for count in table_counts.values()), observed=table_counts),
    ]


def _evidex(files: list[Path]) -> list[dict[str, Any]]:
    summary = _find(files, "executive_summary.docx")
    narrative = _find(files, "narrative_justification.docx")
    combined = "\n".join(_docx_text(path) for path in (summary, narrative) if path)
    placeholders = [phrase for phrase in ["Client organization to confirm", "To be confirmed to To be confirmed", "customer@example.invalid"] if phrase.casefold() in combined.casefold()]
    return [
        _check("evidex_summary_and_narrative_present", bool(summary and narrative), observed={"summary": bool(summary), "narrative": bool(narrative)}),
        _check(
            "evidex_customer_identity_and_period_resolved",
            not placeholders,
            observed=placeholders,
            severity="WARN",
            note="Placeholder identity/reporting metadata is acceptable for a controlled fixture but not for a final customer handoff.",
        ),
    ]


def _document_localize(files: list[Path]) -> list[dict[str, Any]]:
    bilingual = _find(files, "BILINGUAL_REVIEW_COPY.docx")
    text = _docx_text(bilingual) if bilingual else ""
    required = ["English", "Afrikaans", "Ubuntu Care Connect", "0800 220 911", "afspraakbevestiging"]
    missing = [token for token in required if token.casefold() not in text.casefold()]
    return [
        _check("localize_bilingual_review_copy_present", bool(bilingual), observed=bilingual.name if bilingual else None),
        _check("localize_preserves_languages_terms_and_protected_tokens", not missing, observed={"missing": missing}),
    ]


def _campaign(files: list[Path]) -> list[dict[str, Any]]:
    stories = [path for path in files if path.suffix.casefold() == ".md" and "stories" in {part.casefold() for part in path.parts}]
    creative = [path for path in files if path.suffix.casefold() in {".jpg", ".jpeg", ".png", ".webp", ".svg", ".mp4", ".webm"}]
    media_kinds = sorted({path.suffix.casefold() for path in creative})
    return [
        _check("campaign_has_semantic_story_surfaces", len(stories) >= 2, observed=[path.name for path in stories]),
        _check("campaign_has_multichannel_creative_set", len(creative) >= 6 and len(media_kinds) >= 2, observed={"asset_count": len(creative), "media_kinds": media_kinds}),
        _check(
            "campaign_visual_job_fidelity_requires_human_review",
            True,
            observed="NEEDS_YOU",
            severity="WARN",
            note="Automated checks cannot certify that the visual concept actually matches the requested working moment, audience or product job.",
        ),
    ]


def _site(row: dict[str, Any]) -> list[dict[str, Any]]:
    kinds = dict(row.get("material_kind_counts") or {})
    mixed = int(row.get("mixed_media_scene_count") or 0)
    return [
        _check("site_customer_visual_pack_ready", row.get("customer_visual_pack_state") == "READY_NEEDS_YOU", observed=row.get("customer_visual_pack_state")),
        _check("site_has_mixed_media_depth", mixed >= 4, observed=mixed),
        _check("site_material_mix_includes_photo_artifact_and_native", int(kinds.get("curated_photo") or 0) >= 2 and int(kinds.get("artifact_render") or 0) >= 1 and int(kinds.get("native_renderer") or 0) >= 1, observed=kinds),
    ]


def evaluate_row(row: dict[str, Any]) -> dict[str, Any]:
    surface = dict(row.get("customer_surface_gate") or {})
    root = Path(str(surface.get("surface_root") or ""))
    files = _files(root)
    selected = list(surface.get("selected") or [])
    checks = _generic_checks(files, selected)
    name = str(row.get("surface_name") or row.get("surface_id") or "")
    policy = str(row.get("surface_policy_id") or "")

    if name == "HOMS Exam":
        checks.extend(_homs_exam(files))
    elif name == "HOMS Learning Studio":
        checks.extend(_homs_learning(files))
    elif name == "Sophia Review":
        checks.extend(_sophia(row))
    elif name == "VAMP Performance":
        checks.extend(_vamp(files))
    elif name == "Evidex EvidenceOps":
        checks.extend(_evidex(files))
    elif name == "Document Studio Localize":
        checks.extend(_document_localize(files))
    elif name == "Campaign Lab":
        checks.extend(_campaign(files))
    elif name == "Site Studio" or str(row.get("surface_id")) == "site_studio":
        checks.extend(_site(row))

    pipeline_ready = row.get("engineering_surface_status") == "ENGINEERING_READY_NEEDS_BUYER_REVIEW"
    hard_failures = [check for check in checks if not check["passed"] and check["severity"] == "REFUSE"]
    warnings = [check for check in checks if check["severity"] == "WARN" and (not check["passed"] or check.get("observed") == "NEEDS_YOU")]
    if not pipeline_ready or hard_failures:
        state = REFUSE
    elif warnings:
        state = PARTIAL
    else:
        state = READY
    return {
        "surface_id": row.get("surface_id"),
        "surface_name": name,
        "surface_policy_id": policy,
        "engineering_surface_status": row.get("engineering_surface_status"),
        "buyer_substance_state": state,
        "checks": checks,
        "hard_failures": [check["check"] for check in hard_failures],
        "warnings": [check["check"] for check in warnings],
        "human_buyer_review_required": state != REFUSE,
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
    }


def evaluate_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    rows = [evaluate_row(dict(row)) for row in receipt.get("rows") or []]
    ready = sum(row["buyer_substance_state"] == READY for row in rows)
    partial = sum(row["buyer_substance_state"] == PARTIAL for row in rows)
    refused = sum(row["buyer_substance_state"] == REFUSE for row in rows)
    return {
        "schema": "dio.portfolio.customer_substance_audit.v1",
        "source_gauntlet_schema": receipt.get("schema"),
        "source_wave": receipt.get("wave"),
        "surface_count": len(rows),
        "substance_ready_count": ready,
        "substance_partial_count": partial,
        "substance_refuse_count": refused,
        "all_substance_ready": len(rows) > 0 and ready == len(rows),
        "rows": rows,
        "human_buyer_review_required": True,
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": "Buyer Substance Audit checks objective content and deliverable sufficiency signals on top of the customer-surface engineering gate. It cannot certify aesthetics, substantive professional correctness, buyer acceptance or willingness to pay.",
    }


__all__ = ["PARTIAL", "READY", "REFUSE", "evaluate_receipt", "evaluate_row"]
