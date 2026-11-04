"""Byte-bound review leads for PromotionProof's supplied text export."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from products.professional_evidence_projection import evidence_register_record_bindings, evidence_rows, evidence_record_spans, sha256, write_json


MAX_TEXT_BYTES = 128 * 1024
REGISTER_CV = re.compile(r"\bCV\s+lists\s+(\d+)\s+publications\b", re.I)
REGISTER_EXPORT = re.compile(r"\b(?:institutional\s+)?export\s+verifies\s+(\d+)\b", re.I)
ATTACHMENT_COUNT = re.compile(r"\bEntries\s+in\s+declared\s+review\s+period\s*:\s*(\d+)\b", re.I)
THREE_YEAR_SCOPE = re.compile(r"\b(?:over|for)\s+(?:a\s+)?three\s+years?\b", re.I)


def _candidates(pattern: re.Pattern[str], text: str, raw: bytes) -> list[dict[str, Any]]:
    rows = []
    for match in pattern.finditer(text):
        token = match.group(1)
        start = len(text[:match.start(1)].encode("utf-8"))
        end = start + len(token.encode("utf-8"))
        rows.append({
            "value": int(token), "source_byte_start": start, "source_byte_end_exclusive": end,
            "source_span_sha256": hashlib.sha256(raw[start:end]).hexdigest(),
            "source_file_sha256": hashlib.sha256(raw).hexdigest(), "verified_value": False,
        })
    return rows


def _pdf_count_candidates(path: Path, raw: bytes) -> tuple[list[dict[str, Any]], str]:
    """Extract count leads from text PDFs with page-local, hash-bound citations."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            return [], "PDF_ENCRYPTED"
        rows = []
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            for match in ATTACHMENT_COUNT.finditer(text):
                token = match.group(1)
                rows.append({
                    "value": int(token), "page_number": page_number,
                    "page_text_char_start": match.start(1),
                    "page_text_char_end_exclusive": match.end(1),
                    "page_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "source_span_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "source_file_sha256": hashlib.sha256(raw).hexdigest(),
                    "citation_unit": "extracted_page_text_characters",
                    "verified_value": False,
                })
        return rows, "PDF_TEXT_CANDIDATE_EXTRACTED" if rows else "PDF_NO_TEXT_COUNT_CANDIDATE"
    except Exception as exc:
        # Malformed and image-only PDFs stay unresolved; never infer OCR text.
        return [], "PDF_EXTRACTION_UNAVAILABLE_" + type(exc).__name__.upper()


def build_promotionproof_attachment_reconciliation(packet: dict[str, Any], window: dict[str, Any], output_path: Path) -> dict[str, Any]:
    root = Path(packet["packet_dir"]).resolve()
    statement_rows = {str(row.get("record_id") or ""): str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)}
    bindings = evidence_register_record_bindings(packet)
    register_path = root / "SOURCES/02_evidence_register.csv"
    register_bytes = register_path.read_bytes()
    register_hash = hashlib.sha256(register_bytes).hexdigest()
    spans = evidence_record_spans(packet)
    cv_claims = []
    export_claims = []
    for record_id, statement in statement_rows.items():
        span = spans[record_id]
        row_bytes = register_bytes[int(span["source_byte_start"]):int(span["source_byte_end_exclusive"])]
        for pattern, target in ((REGISTER_CV, cv_claims), (REGISTER_EXPORT, export_claims)):
            for match in pattern.finditer(statement):
                token_bytes = match.group(1).encode("utf-8")
                relative = row_bytes.find(token_bytes)
                if relative < 0:
                    raise ValueError(f"PromotionProof count candidate is not present in its exact register row: {record_id}")
                start = int(span["source_byte_start"]) + relative
                end = start + len(token_bytes)
                target.append({
                    "value": int(match.group(1)), "record_id": record_id,
                    "source_file_sha256": register_hash,
                    "source_row_sha256": span["source_row_sha256"],
                    "source_byte_start": start, "source_byte_end_exclusive": end,
                    "source_span_sha256": hashlib.sha256(register_bytes[start:end]).hexdigest(),
                    "verified_value": False,
                })
    attachments = []
    for binding in bindings:
        attachment = binding.get("source_attachment")
        if not attachment:
            continue
        record_id = str(binding["record_id"])
        row = next((item for item in evidence_rows(packet) if str(item.get("record_id") or "") == record_id), {})
        relative = str(row.get("artifact_path") or "")
        path = (root / relative).resolve()
        if path.suffix.casefold() == ".pdf":
            raw = path.read_bytes()
            if len(raw) > MAX_TEXT_BYTES:
                attachments.append({"record_id": record_id, "state": "PDF_LIMIT_EXCEEDED", "count_candidates": [], "source_attachment": attachment})
                continue
            if hashlib.sha256(raw).hexdigest() != attachment.get("source_file_sha256"):
                raise ValueError(f"PromotionProof attachment changed after manifest binding: {relative}")
            candidates, state = _pdf_count_candidates(path, raw)
            attachments.append({
                "record_id": record_id, "source_ref": attachment.get("source_ref"),
                "source_file_sha256": hashlib.sha256(raw).hexdigest(),
                "register_row_sha256": binding.get("source_row_sha256"),
                "state": state, "count_candidates": candidates,
                "source_trust_state": "CAPTURED_UNTRUSTED", "source_validation": "NOT_PERFORMED",
                "ocr_performed": False,
            })
            continue
        if path.suffix.casefold() not in {".txt", ".md", ".csv"}:
            attachments.append({"record_id": record_id, "state": "UNSUPPORTED_FILE_TYPE", "count_candidates": [], "source_attachment": attachment})
            continue
        raw = path.read_bytes()
        if len(raw) > MAX_TEXT_BYTES:
            attachments.append({"record_id": record_id, "state": "TEXT_LIMIT_EXCEEDED", "count_candidates": [], "source_attachment": attachment})
            continue
        if hashlib.sha256(raw).hexdigest() != attachment.get("source_file_sha256"):
            raise ValueError(f"PromotionProof attachment changed after manifest binding: {relative}")
        text = raw.decode("utf-8", errors="strict")
        candidates = _candidates(ATTACHMENT_COUNT, text, raw)
        attachments.append({
            "record_id": record_id, "source_ref": attachment.get("source_ref"),
            "source_file_sha256": hashlib.sha256(raw).hexdigest(),
            "register_row_sha256": binding.get("source_row_sha256"),
            "state": "COUNT_CANDIDATE_EXTRACTED" if candidates else "NO_RECOGNIZED_COUNT_CANDIDATE",
            "count_candidates": candidates, "source_trust_state": "CAPTURED_UNTRUSTED",
            "source_validation": "NOT_PERFORMED",
        })
    attachment_candidates = [candidate for row in attachments for candidate in row["count_candidates"]]
    cv_value = cv_claims[0]["value"] if len(cv_claims) == 1 else None
    export_value = export_claims[0]["value"] if len(export_claims) == 1 else None
    attachment_value = attachment_candidates[0]["value"] if len(attachment_candidates) == 1 else None
    count_alignment = export_value == attachment_value if export_value is not None and attachment_value is not None else None
    delta = cv_value - export_value if cv_value is not None and export_value is not None else None
    criterion = next((value for value in statement_rows.values() if THREE_YEAR_SCOPE.search(value)), "")
    report = {
        "schema": "dio.promotionproof.attachment_reconciliation.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "declared_review_window": {"start": window["start"], "end": window["end"], "source_quote": window.get("source_quote"), "verified": False},
        "register_count_candidates": {"cv_publications": cv_claims, "institutional_export": export_claims},
        "attachment_records": attachments,
        "count_reconciliation_candidate": {
            "cv_publication_count": cv_value,
            "register_export_count": export_value,
            "attachment_count": attachment_value,
            "register_export_matches_attachment_candidate": count_alignment,
            "cv_to_export_difference": delta,
            "verified": False,
        },
        "period_coverage_candidate": {
            "criterion_quote": criterion,
            "available_declared_review_years": [int(window["start"][:4])],
            "required_year_span_candidate": 3 if criterion else None,
            "multi_year_coverage_established": False,
            "review_required": bool(criterion),
        },
        "interpretation_boundary": "Text count extraction and arithmetic preserve customer-declared values only; no source authenticity, publication status, institutional acceptance, sustained output, eligibility or promotion conclusion is verified.",
        "promotion_decision_created": False,
        "human_review_required": True,
        "external_release_authorized": False,
    }
    write_json(output_path, report)
    html_path = output_path.with_suffix(".html")
    attachment_summary = "; ".join(f"{row['record_id']}: " + ", ".join(str(x['value']) for x in row['count_candidates']) for row in attachments) or "No supported text attachment count found."
    html_path.write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>PromotionProof evidence reconciliation review</title>"
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#172b29}.gate{padding:1rem;background:#fff4df;border-left:5px solid #a66a27}table{border-collapse:collapse;width:100%}th,td{padding:.65rem;border:1px solid #ccd5cf;text-align:left;vertical-align:top}th{background:#163f3b;color:white}</style></head><body>"
        "<h1>PromotionProof · source count and period review</h1><p class=\"gate\"><strong>Reviewer lead only.</strong> Extracted numbers remain unverified source statements. This report does not authenticate records or determine promotion eligibility.</p>"
        f"<p>Declared review period: {html.escape(window['start'])} to {html.escape(window['end'])}. Declared criterion: {html.escape(criterion or 'No three-year criterion detected')}.</p>"
        f"<p>CV count candidate: {html.escape(str(cv_value))}; customer-reported export count: {html.escape(str(export_value))}; attachment count candidate: {html.escape(str(attachment_value))}; difference candidate: {html.escape(str(delta))}.</p>"
        f"<p>Attachment records: {html.escape(attachment_summary)}</p>"
        "<p>The supplied case declares one review year while the cited criterion calls for three years. Obtain the missing period records and have the institution confirm the applicable criteria.</p>"
        "<p>All counts are captured-untrusted and remain subject to source review. No promotion decision, rating, recommendation or external release was created.</p></body></html>\n",
        encoding="utf-8",
    )
    report["artifacts"] = [
        {"path": output_path.name, "sha256": sha256(output_path), "bytes": output_path.stat().st_size},
        {"path": html_path.name, "sha256": sha256(html_path), "bytes": html_path.stat().st_size},
    ]
    return report
