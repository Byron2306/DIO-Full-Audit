"""Conservative date extraction for hash-bound plain-text CPD attachments.

Date candidates are reviewer leads only. This module never authenticates a
certificate, awards points, or validates an attachment's professional status.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from products.professional_evidence_projection import evidence_register_record_bindings, evidence_rows, sha256, write_json


ISO_DATE = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
POINT_VALUE = re.compile(r"(?<!\d)(?P<value>\d+(?:\.\d+)?)(?:\s*(?:CPD\s+)?points?|-points?)\b", re.I)
MAX_TEXT_ATTACHMENT_BYTES = 128 * 1024
MAX_PDF_ATTACHMENT_BYTES = 128 * 1024


def _point_candidates(text: str, raw: bytes) -> list[dict[str, Any]]:
    candidates = []
    for match in POINT_VALUE.finditer(text):
        token = match.group("value")
        start = len(text[:match.start("value")].encode("utf-8"))
        end = start + len(token.encode("utf-8"))
        value = float(token)
        candidates.append({
            "value": int(value) if value.is_integer() else value,
            "point_expression": match.group(0),
            "source_file_sha256": hashlib.sha256(raw).hexdigest(),
            "source_byte_start": start,
            "source_byte_end_exclusive": end,
            "source_span_sha256": hashlib.sha256(raw[start:end]).hexdigest(),
            "verified_point_value": False,
        })
    return candidates


def _pdf_candidates(path: Path, raw: bytes, start: str, end: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, int]:
    """Read only embedded PDF text and cite candidates to page-text coordinates."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            return [], [], "PDF_ENCRYPTED", len(reader.pages)
        dates: list[dict[str, Any]] = []
        points: list[dict[str, Any]] = []
        raw_hash = hashlib.sha256(raw).hexdigest()
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            page_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            for match in ISO_DATE.finditer(text):
                try:
                    from datetime import date
                    parsed = date.fromisoformat(match.group(1))
                except ValueError:
                    continue
                observed = parsed.isoformat()
                token = match.group(1)
                dates.append({
                    "date_text": token, "date_iso": observed, "page_number": page_number,
                    "page_text_char_start": match.start(), "page_text_char_end_exclusive": match.end(),
                    "page_text_sha256": page_hash, "source_file_sha256": raw_hash,
                    "source_span_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "citation_unit": "extracted_page_text_characters",
                    "declared_window_comparison": "WITHIN_DECLARED_WINDOW_CANDIDATE" if start <= observed <= end else "OUTSIDE_DECLARED_WINDOW_CANDIDATE",
                    "verified_event_date": False,
                })
            for match in POINT_VALUE.finditer(text):
                token = match.group("value")
                value = float(token)
                points.append({
                    "value": int(value) if value.is_integer() else value,
                    "point_expression": match.group(0), "page_number": page_number,
                    "page_text_char_start": match.start("value"),
                    "page_text_char_end_exclusive": match.end("value"),
                    "page_text_sha256": page_hash, "source_file_sha256": raw_hash,
                    "source_span_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "citation_unit": "extracted_page_text_characters",
                    "verified_point_value": False,
                })
        state = "PDF_TEXT_CANDIDATES_EXTRACTED" if dates or points else "PDF_NO_TEXT_DATE_OR_POINT_CANDIDATE"
        return dates, points, state, len(reader.pages)
    except Exception as exc:
        return [], [], "PDF_EXTRACTION_UNAVAILABLE_" + type(exc).__name__.upper(), 0


def _register_point_candidates(bindings: list[dict[str, Any]], register_bytes: bytes) -> list[dict[str, Any]]:
    candidates = []
    for binding in bindings:
        statement = str(binding.get("customer_statement") or "")
        row_start = int(binding["source_byte_start"])
        row_end = int(binding["source_byte_end_exclusive"])
        row_bytes = register_bytes[row_start:row_end]
        statement_bytes = statement.encode("utf-8")
        statement_offset = row_bytes.find(statement_bytes)
        if statement_offset < 0:
            raise ValueError(f"CPD register statement span not found in source row: {binding['record_id']}")
        role = (
            "ANNUAL_REQUIREMENT" if re.search(r"\bannual requirement\b", statement, re.I) else
            "SUBMITTED_LOG_CLAIM" if re.search(r"\b(?:log claims|claims)\b", statement, re.I) else
            "REGISTER_SUPPORT_CLAIM" if re.search(r"\b(?:directly support|support)\b", statement, re.I) else
            "OUT_OF_WINDOW_ACTIVITY_CLAIM" if re.search(r"\boutside (?:the )?(?:current )?cycle\b", statement, re.I) else
            "UNCLASSIFIED_REGISTER_CANDIDATE"
        )
        for match in POINT_VALUE.finditer(statement):
            token = match.group("value")
            start = row_start + statement_offset + len(statement[:match.start("value")].encode("utf-8"))
            end = start + len(token.encode("utf-8"))
            candidates.append({
                "record_id": binding["record_id"], "role": role,
                "value": int(float(token)) if float(token).is_integer() else float(token),
                "point_expression": match.group(0), "source_ref": binding["source_ref"],
                "source_file_sha256": binding["source_file_sha256"],
                "source_row_sha256": binding["source_row_sha256"],
                "source_statement_sha256": binding["source_statement_sha256"],
                "source_byte_start": start, "source_byte_end_exclusive": end,
                "source_span_sha256": hashlib.sha256(register_bytes[start:end]).hexdigest(),
                "verified_point_value": False,
            })
    return candidates


def build_cpd_attachment_date_review(packet: dict[str, Any], window: dict[str, Any], output_path: Path) -> dict[str, Any]:
    packet_root = Path(packet["packet_dir"]).resolve()
    rows = {str(row.get("record_id") or ""): row for row in evidence_rows(packet)}
    bindings = evidence_register_record_bindings(packet)
    start = str(window["start"])
    end = str(window["end"])
    reviewed: list[dict[str, Any]] = []
    register_path = packet_root / "SOURCES" / "02_evidence_register.csv"
    register_bytes = register_path.read_bytes()
    register_point_candidates = _register_point_candidates(bindings, register_bytes)
    for binding in bindings:
        attachment = binding.get("source_attachment")
        if not attachment:
            continue
        record_id = str(binding["record_id"])
        register_row = rows.get(record_id) or {}
        relative = str(register_row.get("artifact_path") or "")
        path = (packet_root / relative).resolve()
        if path.suffix.casefold() == ".pdf":
            if path.stat().st_size > MAX_PDF_ATTACHMENT_BYTES:
                reviewed.append({
                    "record_id": record_id, "source_attachment": attachment,
                    "extraction_state": "PDF_ATTACHMENT_LIMIT_EXCEEDED",
                    "event_date_candidates": [], "point_value_candidates": [],
                    "owner_action": "Review the original PDF; this bounded preview did not read its text.",
                })
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != attachment.get("source_file_sha256"):
                raise ValueError(f"CPD attachment changed after manifest binding: {relative}")
            date_candidates, point_candidates, extraction_state, page_count = _pdf_candidates(path, raw, start, end)
            for point_candidate in point_candidates:
                if any(candidate["declared_window_comparison"] == "OUTSIDE_DECLARED_WINDOW_CANDIDATE" for candidate in date_candidates):
                    point_candidate["declared_window_comparison"] = "OUTSIDE_DECLARED_WINDOW_CANDIDATE"
                elif any(candidate["declared_window_comparison"] == "WITHIN_DECLARED_WINDOW_CANDIDATE" for candidate in date_candidates):
                    point_candidate["declared_window_comparison"] = "WITHIN_DECLARED_WINDOW_CANDIDATE"
                else:
                    point_candidate["declared_window_comparison"] = "DATE_NOT_ESTABLISHED"
            reviewed.append({
                "record_id": record_id,
                "register_source_ref": binding["source_ref"],
                "register_row_sha256": binding["source_row_sha256"],
                "source_attachment": attachment,
                "source_file_sha256": hashlib.sha256(raw).hexdigest(),
                "extraction_state": extraction_state,
                "page_count": page_count,
                "ocr_performed": False,
                "event_date_candidates": date_candidates,
                "point_value_candidates": point_candidates,
                "owner_action": "Compare each page-cited candidate with the original certificate and confirm provider accreditation and point allocation. Extracted text does not authenticate the source or establish CPD credit.",
            })
            continue
        if path.suffix.casefold() not in {".txt", ".md", ".csv"}:
            reviewed.append({
                "record_id": record_id,
                "source_attachment": attachment,
                "extraction_state": "UNSUPPORTED_FILE_TYPE",
                "event_date_candidates": [],
                "point_value_candidates": [],
                "owner_action": "Open the original attachment and verify its activity date, provider accreditation and awarded points.",
            })
            continue
        size = path.stat().st_size
        if size > MAX_TEXT_ATTACHMENT_BYTES:
            reviewed.append({
                "record_id": record_id,
                "source_attachment": attachment,
                "extraction_state": "TEXT_ATTACHMENT_LIMIT_EXCEEDED",
                "event_date_candidates": [],
                "point_value_candidates": [],
                "owner_action": "Review the original attachment; this bounded preview did not read its text.",
            })
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != attachment.get("source_file_sha256"):
            raise ValueError(f"CPD attachment changed after manifest binding: {relative}")
        text = raw.decode("utf-8", errors="strict")
        candidates = []
        for match in ISO_DATE.finditer(text):
            try:
                from datetime import date
                parsed = date.fromisoformat(match.group(1))
            except ValueError:
                continue
            byte_start = len(text[:match.start()].encode("utf-8"))
            byte_end = byte_start + len(match.group(1).encode("utf-8"))
            observed = parsed.isoformat()
            in_window = start <= observed <= end
            candidates.append({
                "date_text": match.group(1),
                "date_iso": observed,
                "source_file_sha256": hashlib.sha256(raw).hexdigest(),
                "source_byte_start": byte_start,
                "source_byte_end_exclusive": byte_end,
                "source_span_sha256": hashlib.sha256(raw[byte_start:byte_end]).hexdigest(),
                "declared_window_comparison": "WITHIN_DECLARED_WINDOW_CANDIDATE" if in_window else "OUTSIDE_DECLARED_WINDOW_CANDIDATE",
                "verified_event_date": False,
            })
        point_candidates = _point_candidates(text, raw)
        for point_candidate in point_candidates:
            if any(candidate["declared_window_comparison"] == "OUTSIDE_DECLARED_WINDOW_CANDIDATE" for candidate in candidates):
                point_candidate["declared_window_comparison"] = "OUTSIDE_DECLARED_WINDOW_CANDIDATE"
            elif any(candidate["declared_window_comparison"] == "WITHIN_DECLARED_WINDOW_CANDIDATE" for candidate in candidates):
                point_candidate["declared_window_comparison"] = "WITHIN_DECLARED_WINDOW_CANDIDATE"
            else:
                point_candidate["declared_window_comparison"] = "DATE_NOT_ESTABLISHED"
        reviewed.append({
            "record_id": record_id,
            "register_source_ref": binding["source_ref"],
            "register_row_sha256": binding["source_row_sha256"],
            "source_attachment": attachment,
            "extraction_state": "UTF8_TEXT_DATE_CANDIDATES_EXTRACTED" if candidates else "NO_ISO_DATE_CANDIDATE_FOUND",
            "event_date_candidates": candidates,
            "point_value_candidates": point_candidates,
            "owner_action": "Compare each quoted date with the original certificate and confirm provider accreditation and point allocation. A matching or out-of-window date candidate does not authenticate the source or establish CPD credit.",
        })
    out_of_window = sum(
        candidate["declared_window_comparison"] == "OUTSIDE_DECLARED_WINDOW_CANDIDATE"
        for item in reviewed for candidate in item["event_date_candidates"]
    )
    attachment_point_candidates = [candidate for row in reviewed for candidate in row["point_value_candidates"]]
    register_values = {row["role"]: row["value"] for row in register_point_candidates
                       if row["role"] in {"ANNUAL_REQUIREMENT", "SUBMITTED_LOG_CLAIM", "REGISTER_SUPPORT_CLAIM"}}
    attachment_current_cycle_candidate = sum(
        float(candidate["value"]) for candidate in attachment_point_candidates
        if candidate["declared_window_comparison"] == "WITHIN_DECLARED_WINDOW_CANDIDATE"
    )
    attachment_out_of_window_candidate = sum(
        float(candidate["value"]) for candidate in attachment_point_candidates
        if candidate["declared_window_comparison"] == "OUTSIDE_DECLARED_WINDOW_CANDIDATE"
    )
    undated_attachment_candidate = sum(
        float(candidate["value"]) for candidate in attachment_point_candidates
        if candidate["declared_window_comparison"] == "DATE_NOT_ESTABLISHED"
    )
    reconcile = {
        "annual_requirement_candidate": register_values.get("ANNUAL_REQUIREMENT"),
        "submitted_log_claim_candidate": register_values.get("SUBMITTED_LOG_CLAIM"),
        "register_certificate_support_candidate": register_values.get("REGISTER_SUPPORT_CLAIM"),
        "attachment_points_within_window_candidate": attachment_current_cycle_candidate,
        "attachment_points_outside_window_candidate": attachment_out_of_window_candidate,
        "attachment_points_without_date_candidate": undated_attachment_candidate,
        "claim_minus_register_support_candidate": (
            register_values["SUBMITTED_LOG_CLAIM"] - register_values["REGISTER_SUPPORT_CLAIM"]
            if "SUBMITTED_LOG_CLAIM" in register_values and "REGISTER_SUPPORT_CLAIM" in register_values else None
        ),
        "register_support_minus_requirement_candidate": (
            register_values["REGISTER_SUPPORT_CLAIM"] - register_values["ANNUAL_REQUIREMENT"]
            if "REGISTER_SUPPORT_CLAIM" in register_values and "ANNUAL_REQUIREMENT" in register_values else None
        ),
        "unvalued_activity_record_ids": [binding["record_id"] for binding in bindings
            if re.search(r"do not state accredited point values|no accredited provider point allocation", str(binding.get("customer_statement") or ""), re.I)],
        "verified": False,
        "interpretation": "Arithmetic over customer-declared register values and attachment text candidates only. Undated and out-of-window candidates are not counted as eligible CPD credit.",
    }
    report = {
        "schema": "dio.cpdproof.attachment_date_and_points_review.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "declared_review_window": {
            "start": start,
            "end": end,
            "source_quote": window.get("source_quote"),
            "source_events_verified": False,
        },
        "processing_scope": "UTF-8 text and embedded PDF page-text date and numeric point candidates; text uses byte spans, PDF uses page-local character offsets; no certificate authenticity, accreditation or credit validation",
        "source_trust_state": "CAPTURED_UNTRUSTED",
        "content_validation": "PARTIAL_TEXT_DATE_AND_POINT_CANDIDATE_EXTRACTION_ONLY",
        "record_count": len(reviewed),
        "date_candidate_count": sum(len(item["event_date_candidates"]) for item in reviewed),
        "outside_window_candidate_count": out_of_window,
        "register_point_candidates": register_point_candidates,
        "attachment_point_candidate_count": len(attachment_point_candidates),
        "point_candidate_reconciliation": reconcile,
        "records": reviewed,
        "cpd_credit_awarded": False,
        "cpd_compliance_certified": False,
        "human_professional_review_required": True,
        "external_release_authorized": False,
    }
    write_json(output_path, report)
    html_path = output_path.with_suffix(".html")
    rows_html = []
    for item in reviewed:
        candidates = item["event_date_candidates"] or [{"date_iso": "No ISO date candidate found", "declared_window_comparison": "REVIEW ORIGINAL"}]
        for candidate in candidates:
            point_text = "; ".join(
                f"{row['value']} ({row['declared_window_comparison']}) [{row['point_expression']}]"
                + (f" — PDF page {row['page_number']}, text chars {row['page_text_char_start']}–{row['page_text_char_end_exclusive']}"
                   if row.get("citation_unit") == "extracted_page_text_characters" else "")
                for row in item["point_value_candidates"]
            ) or "No numeric point candidate found"
            date_text = str(candidate["date_iso"])
            if candidate.get("citation_unit") == "extracted_page_text_characters":
                date_text += f" — PDF page {candidate['page_number']}, text chars {candidate['page_text_char_start']}–{candidate['page_text_char_end_exclusive']}"
            rows_html.append(
                "<tr><td>" + html.escape(item["record_id"]) + "</td><td>"
                + html.escape(date_text) + "</td><td>"
                + html.escape(str(candidate["declared_window_comparison"])) + "</td><td>"
                + html.escape(point_text) + "</td><td>"
                + html.escape(str(item["source_attachment"].get("source_ref") or "")) + "</td><td>"
                + html.escape(str(item["owner_action"])) + "</td></tr>"
            )
    html_path.write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>CPDProof attachment date review</title>"
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#172b29}h1{line-height:1.2}.gate{padding:1rem;background:#fff4df;border-left:5px solid #a66a27}table{border-collapse:collapse;width:100%}th,td{padding:.65rem;border:1px solid #ccd5cf;text-align:left;vertical-align:top}th{background:#163f3b;color:white}code{overflow-wrap:anywhere}</style></head><body>"
        "<h1>CPDProof · attachment date review</h1><p class=\"gate\"><strong>Reviewer lead only.</strong> Extracted dates are unverified text candidates. This report does not authenticate certificates, verify accreditation, award CPD points or certify compliance.</p>"
        f"<p>Declared review window: <strong>{html.escape(start)} to {html.escape(end)}</strong>. Source: {html.escape(str(window.get('source_quote') or ''))}</p>"
        f"<p>{len(reviewed)} attached records reviewed; {sum(len(row['event_date_candidates']) for row in reviewed)} date candidate(s); {out_of_window} outside-window date candidate(s); {len(attachment_point_candidates)} numeric point candidate(s).</p>"
        f"<p>Register point candidates: requirement {html.escape(str(reconcile['annual_requirement_candidate']))}; log claim {html.escape(str(reconcile['submitted_log_claim_candidate']))}; certificate support {html.escape(str(reconcile['register_certificate_support_candidate']))}. Attachment candidates: {html.escape(str(reconcile['attachment_points_without_date_candidate']))} without a date candidate; {html.escape(str(reconcile['attachment_points_outside_window_candidate']))} outside the window. These are not awarded credits.</p>"
        "<table><thead><tr><th>Record</th><th>Date text</th><th>Window comparison</th><th>Point candidate</th><th>Bound attachment</th><th>Required human action</th></tr></thead><tbody>"
        + "".join(rows_html) + "</tbody></table><p>Source content remains captured-untrusted. Verify every candidate against the original source and obtain an authorised professional decision.</p></body></html>\n",
        encoding="utf-8",
    )
    report["artifacts"] = [
        {"path": output_path.name, "sha256": sha256(output_path), "bytes": output_path.stat().st_size},
        {"path": html_path.name, "sha256": sha256(html_path), "bytes": html_path.stat().st_size},
    ]
    return report
