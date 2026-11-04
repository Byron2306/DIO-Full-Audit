#!/usr/bin/env python3
"""Validate completed editorial decisions against Article Publication Studio claim lineage.

Validation confirms worksheet completeness and source-row identity only. It
does not authenticate claims, grant rights, or authorize publication.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


FIELDS = {
    "source_authenticity_decision": {"VERIFIED", "NOT_VERIFIED", "UNAVAILABLE"},
    "factual_accuracy_and_context_decision": {"VERIFIED", "NOT_VERIFIED", "NEEDS_REVISION"},
    "rights_and_permission_decision": {"CLEARED", "NOT_CLEARED", "UNKNOWN"},
    "privacy_decision": {"CLEARED", "ISSUE_FOUND", "UNKNOWN"},
    "attribution_decision": {"CLEARED", "ISSUE_FOUND", "UNKNOWN"},
    "editorial_decision": {"APPROVED", "REJECTED", "NEEDS_REVISION"},
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(worksheet_path: Path, bindings_path: Path, source_register_path: Path) -> dict[str, Any]:
    with worksheet_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        headers = list(reader.fieldnames or [])
    bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    binding_rows = bindings.get("claims") or []
    expected: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, source_row in enumerate(binding_rows, 1):
        claim_id = str(source_row.get("claim_id") or "").strip()
        if not claim_id or claim_id in expected:
            issues.append({"code": "SOURCE_BINDING_CLAIM_ID_EMPTY_OR_DUPLICATE", "row": str(index), "field": "claim_id"})
            continue
        expected[claim_id] = source_row
    if bindings.get("schema") != "dio.article_publication.source_byte_bindings.v1":
        issues.append({"code": "SOURCE_BINDINGS_SCHEMA_INVALID", "field": "schema"})
    if bindings.get("all_source_spans_verified") is not True:
        issues.append({"code": "SOURCE_BINDINGS_NOT_VERIFIED", "field": "all_source_spans_verified"})
    required_headers = {
        "claim_id", "claim_text", "customer_record_id", "source_ref", "source_byte_start",
        "source_byte_end_exclusive", "source_file_sha256", "source_row_sha256", "source_statement_sha256",
        "independent_corroboration_ref", "reviewer_name", "reviewer_role",
        "reviewed_at_iso8601", "reviewer_rationale", *FIELDS.keys(),
    }
    for missing in sorted(required_headers - set(headers)):
        issues.append({"code": "REQUIRED_COLUMN_MISSING", "field": missing})
    if len(headers) != len(set(headers)):
        issues.append({"code": "DUPLICATE_WORKSHEET_HEADER", "field": "header"})
    if any(None in row for row in rows):
        issues.append({"code": "WORKSHEET_ROW_HAS_EXTRA_FIELDS", "field": "row"})
    if not rows:
        issues.append({"code": "NO_CLAIM_ROWS", "field": "claim_id"})
    source_register_bytes = source_register_path.read_bytes()
    source_register_sha256 = _sha(source_register_path)
    if source_register_sha256 != bindings.get("source_register_sha256"):
        issues.append({"code": "SOURCE_REGISTER_HASH_MISMATCH", "field": "source_register_sha256"})
    source_register_rows: dict[str, dict[str, str]] = {}
    try:
        with source_register_path.open(encoding="utf-8-sig", newline="") as handle:
            for source_row in csv.DictReader(handle):
                record_id = str(source_row.get("record_id") or "").strip()
                if not record_id or record_id in source_register_rows:
                    issues.append({"code": "SOURCE_REGISTER_RECORD_ID_EMPTY_OR_DUPLICATE", "field": "record_id"})
                    continue
                source_register_rows[record_id] = source_row
    except (UnicodeError, csv.Error):
        issues.append({"code": "SOURCE_REGISTER_NOT_VALID_UTF8_CSV", "field": "source_register"})
    for index, row in enumerate(rows, 1):
        claim_id = str(row.get("claim_id") or "").strip()
        if not claim_id or claim_id in seen:
            issues.append({"code": "CLAIM_ID_EMPTY_OR_DUPLICATE", "row": str(index), "field": "claim_id"})
            continue
        seen.add(claim_id)
        source = expected.get(claim_id)
        if source is None:
            issues.append({"code": "CLAIM_NOT_IN_SOURCE_LINEAGE", "row": str(index), "field": "claim_id"})
            continue
        for field, source_field in (
            ("claim_text", "claim_text"), ("customer_record_id", "customer_record_id"),
            ("source_ref", "source_ref"), ("source_byte_start", "source_byte_start"),
            ("source_byte_end_exclusive", "source_byte_end_exclusive"),
            ("source_file_sha256", "source_file_sha256"),
            ("source_row_sha256", "source_row_sha256"),
            ("source_statement_sha256", "source_statement_sha256"),
        ):
            if str(row.get(field) or "") != str(source.get(source_field) or ""):
                issues.append({"code": "SOURCE_LINEAGE_FIELD_CHANGED", "row": str(index), "field": field})
        try:
            start = int(source.get("source_byte_start", -1))
            end = int(source.get("source_byte_end_exclusive", -1))
        except (TypeError, ValueError):
            start, end = -1, -1
        row_bytes = source_register_bytes[start:end] if 0 <= start < end <= len(source_register_bytes) else b""
        statement = str(source.get("customer_statement") or "")
        record_id = str(source.get("customer_record_id") or "")
        register_row = source_register_rows.get(record_id)
        try:
            raw_row = next(csv.reader(io.StringIO(row_bytes.decode("utf-8-sig"), newline=""))) if row_bytes else []
        except (UnicodeError, csv.Error):
            raw_row = []
        if (not row_bytes
                or source.get("source_file_sha256") != source_register_sha256
                or hashlib.sha256(row_bytes).hexdigest() != source.get("source_row_sha256")
                or hashlib.sha256(statement.encode("utf-8")).hexdigest() != source.get("source_statement_sha256")
                or len(raw_row) != 2 or raw_row[0] != record_id or raw_row[1] != statement
                or not register_row or register_row.get("customer_supplied_record") != statement):
            issues.append({"code": "SOURCE_BYTES_DO_NOT_MATCH_REGISTER_RECORD", "row": str(index), "field": "source_ref"})
        for field, allowed in FIELDS.items():
            value = str(row.get(field) or "").strip().upper()
            if value not in allowed:
                issues.append({"code": "DECISION_INCOMPLETE_OR_INVALID", "row": str(index), "field": field})
        if (str(row.get("source_authenticity_decision") or "").strip().upper() == "VERIFIED"
                or str(row.get("factual_accuracy_and_context_decision") or "").strip().upper() == "VERIFIED") and not str(row.get("independent_corroboration_ref") or "").strip():
            issues.append({"code": "VERIFICATION_REFERENCE_REQUIRED", "row": str(index), "field": "independent_corroboration_ref"})
        for field in ("reviewer_name", "reviewer_role", "reviewer_rationale"):
            if not str(row.get(field) or "").strip():
                issues.append({"code": "REVIEWER_FIELD_REQUIRED", "row": str(index), "field": field})
        reviewed_at = str(row.get("reviewed_at_iso8601") or "").strip()
        try:
            parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("timezone required")
        except ValueError:
            issues.append({"code": "REVIEW_TIME_MUST_BE_TIMEZONE_AWARE_ISO8601", "row": str(index), "field": "reviewed_at_iso8601"})
    for missing_id in sorted(set(expected) - seen):
        issues.append({"code": "SOURCE_CLAIM_ROW_MISSING", "claim_id": missing_id, "field": "claim_id"})
    all_approved = bool(rows) and not issues and all(
        str(row.get("editorial_decision") or "").strip().upper() == "APPROVED"
        and str(row.get("source_authenticity_decision") or "").strip().upper() == "VERIFIED"
        and str(row.get("factual_accuracy_and_context_decision") or "").strip().upper() == "VERIFIED"
        and str(row.get("rights_and_permission_decision") or "").strip().upper() == "CLEARED"
        and str(row.get("privacy_decision") or "").strip().upper() == "CLEARED"
        and str(row.get("attribution_decision") or "").strip().upper() == "CLEARED"
        for row in rows
    )
    complete = bool(rows) and not issues
    state = (
        "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" if not complete else
        "REVIEW_COMPLETE_PENDING_SEPARATE_PUBLICATION_AUTHORITY" if all_approved else
        "REVIEW_COMPLETE_WITH_HOLDS"
    )
    return {
        "schema": "dio.article_publication_studio.editorial_review_validation.v1",
        "state": state,
        "worksheet_sha256": _sha(worksheet_path),
        "source_bindings_sha256": _sha(bindings_path), "source_register_sha256": source_register_sha256,
        "expected_claim_count": len(expected), "worksheet_row_count": len(rows),
        "issues": issues,
        "publication_authorized": False,
        "authority_created": False,
        "external_effects": False,
        "claim_boundary": "This validator checks row completeness and exact source-lineage identity. It does not independently verify truth, rights, privacy, attribution, or reviewer competence, and never authorizes publication.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", type=Path)
    parser.add_argument("--bindings", type=Path, required=True, help="ARTICLE_SOURCE_BYTE_BINDINGS.json")
    parser.add_argument("--source-register", type=Path, required=True, help="Original customer evidence register from the packet")
    parser.add_argument("--output", type=Path, required=True, help="Write validation JSON receipt here")
    args = parser.parse_args()
    try:
        result = validate(args.worksheet, args.bindings, args.source_register)
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError) as exc:
        parser.error(f"could not validate review inputs: {exc}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["state"] in {"REVIEW_COMPLETE_PENDING_SEPARATE_PUBLICATION_AUTHORITY", "REVIEW_COMPLETE_WITH_HOLDS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
