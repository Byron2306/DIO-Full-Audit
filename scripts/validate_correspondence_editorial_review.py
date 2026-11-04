#!/usr/bin/env python3
"""Validate sender/editor review rows without authorizing correspondence sending."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISIONS = {
    "support_decision": {"SUPPORTED", "NOT_SUPPORTED", "UNRESOLVED", "CUSTOMER_REQUEST_ACKNOWLEDGED", "NOT_AUTHORIZED"},
    "identity_and_recipient_checked": {"CONFIRMED", "NOT_CONFIRMED", "NOT_APPLICABLE"},
    "sender_authority_checked": {"CONFIRMED", "NOT_CONFIRMED", "NOT_APPLICABLE"},
    "commitment_boundary_checked": {"CLEAR", "COMMITMENT_PRESENT", "REVIEW_REQUIRED"},
    "editorial_decision": {"APPROVE_FOR_SENDER_REVIEW", "REVISE", "REJECT"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(worksheet_path: Path, bindings_path: Path) -> dict[str, Any]:
    with worksheet_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        rows = list(reader)
    binding_doc = json.loads(bindings_path.read_text(encoding="utf-8"))
    bindings = {str(row.get("item_id") or ""): row for row in binding_doc.get("bindings") or []}
    required = {"item_id", "item_type", "source_id", "source_sha256", "exact_source_text", "proposed_text",
                "revision_reference", "rationale", "reviewer_name", "reviewer_role", "reviewed_at_iso8601", *DECISIONS.keys()}
    issues: list[dict[str, str]] = []
    for missing in sorted(required - headers):
        issues.append({"code": "REQUIRED_COLUMN_MISSING", "field": missing})
    if not rows:
        issues.append({"code": "NO_REVIEW_ROWS", "field": "item_id"})
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        item_id = str(row.get("item_id") or "").strip()
        if not item_id or item_id in seen:
            issues.append({"code": "ITEM_ID_EMPTY_OR_DUPLICATE", "row": str(index), "field": "item_id"})
            continue
        seen.add(item_id)
        if row.get("item_type") == "source_fact":
            if str(row.get("support_decision") or "").strip().upper() not in {"SUPPORTED", "NOT_SUPPORTED", "UNRESOLVED"}:
                issues.append({"code": "SOURCE_FACT_DECISION_INVALID", "row": str(index), "field": "support_decision"})
            binding = bindings.get(item_id)
            if not binding:
                issues.append({"code": "SOURCE_FACT_NOT_IN_BINDINGS", "row": str(index), "field": "item_id"})
            else:
                try:
                    offsets_match = (int(row.get("source_start")) == int(binding.get("quote_local_byte_start"))
                                     and int(row.get("source_end")) == int(binding.get("quote_local_byte_end_exclusive")))
                except (TypeError, ValueError):
                    offsets_match = False
                if (str(row.get("source_record_id") or "") != str(binding.get("customer_record_id") or "")
                  or not offsets_match
                  or str(row.get("exact_source_text") or "") != str(binding.get("customer_statement") or "")
                  or str(row.get("source_id") or "") != str(binding.get("source_id") or "")
                  or str(row.get("source_sha256") or "") != str(binding.get("source_statement_sha256") or "")):
                    issues.append({"code": "SOURCE_FACT_LINEAGE_CHANGED", "row": str(index), "field": "source_record_id/source_offsets/source_text"})
        elif row.get("item_type") == "requested_action":
            if str(row.get("support_decision") or "").strip().upper() not in {"CUSTOMER_REQUEST_ACKNOWLEDGED", "NOT_AUTHORIZED", "UNRESOLVED"}:
                issues.append({"code": "REQUESTED_ACTION_DECISION_INVALID", "row": str(index), "field": "support_decision"})
        else:
            issues.append({"code": "UNKNOWN_ITEM_TYPE", "row": str(index), "field": "item_type"})
        for field, allowed in DECISIONS.items():
            if str(row.get(field) or "").strip().upper() not in allowed:
                issues.append({"code": "DECISION_INCOMPLETE_OR_INVALID", "row": str(index), "field": field})
        for field in ("rationale", "reviewer_name", "reviewer_role"):
            if not str(row.get(field) or "").strip():
                issues.append({"code": "REVIEWER_FIELD_REQUIRED", "row": str(index), "field": field})
        stamp = str(row.get("reviewed_at_iso8601") or "").strip()
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("timezone required")
        except ValueError:
            issues.append({"code": "REVIEW_TIME_MUST_BE_TIMEZONE_AWARE_ISO8601", "row": str(index), "field": "reviewed_at_iso8601"})
    expected_ids = set(bindings)
    if seen.intersection(expected_ids) != expected_ids:
        for missing_id in sorted(expected_ids - seen):
            issues.append({"code": "SOURCE_FACT_ROW_MISSING", "item_id": missing_id, "field": "item_id"})
    if sum(row.get("item_type") == "requested_action" for row in rows) != 1:
        issues.append({"code": "EXACTLY_ONE_REQUESTED_ACTION_ROW_REQUIRED", "field": "item_type"})
    complete = bool(rows) and not issues
    all_clear = complete and all(
        str(row.get("support_decision") or "").upper() == ("SUPPORTED" if row.get("item_type") == "source_fact" else "CUSTOMER_REQUEST_ACKNOWLEDGED")
        and str(row.get("identity_and_recipient_checked") or "").upper() == "CONFIRMED"
        and str(row.get("sender_authority_checked") or "").upper() in {"CONFIRMED", "NOT_APPLICABLE"}
        and str(row.get("commitment_boundary_checked") or "").upper() == "CLEAR"
        and str(row.get("editorial_decision") or "").upper() == "APPROVE_FOR_SENDER_REVIEW"
        for row in rows
    )
    state = "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" if not complete else "REVIEW_COMPLETE_PENDING_SENDER_DECISION" if all_clear else "REVIEW_COMPLETE_WITH_HOLDS"
    return {
        "schema": "dio.professional_correspondence.editorial_review_validation.v1",
        "state": state,
        "worksheet_sha256": sha(worksheet_path), "source_bindings_sha256": sha(bindings_path),
        "expected_source_fact_count": len(bindings), "worksheet_row_count": len(rows), "issues": issues,
        "send_authorized": False, "authority_created": False, "external_effects": False,
        "claim_boundary": "Validation checks reviewer completeness and fact-row identity only. It does not authenticate claims, approve legal positions, or authorize sending; a named sender must make the final send decision.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", type=Path)
    parser.add_argument("--bindings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = validate(args.worksheet, args.bindings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["state"] != "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
