"""Validate completed Offer Lab owner-review worksheets without granting authority."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REVIEW_COLUMNS = [
    "record_id", "component", "customer_statement", "source_ref", "source_byte_ref",
    "source_register_sha256", "source_row_sha256", "source_statement_sha256",
    "source_byte_start", "source_byte_end_exclusive", "epistemic_state",
    "reviewer_decision", "reviewer_name", "reviewer_role", "reviewed_at_iso8601",
    "rationale", "revised_wording",
]
DECISIONS = {"ACCEPT_AS_HYPOTHESIS", "REVISE", "REQUEST_EVIDENCE", "DEFER"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(offer_path: Path, source_register_path: Path, review_csv_path: Path) -> dict[str, Any]:
    offer = json.loads(offer_path.read_text(encoding="utf-8"))
    register_bytes = source_register_path.read_bytes()
    register_sha = _sha(register_bytes)
    with review_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REVIEW_COLUMNS:
            raise ValueError("review CSV columns do not match the issued Offer Lab schema")
        rows = list(reader)
    source_rows = offer.get("source_records") or []
    if len(rows) != len(source_rows) or not source_rows:
        raise ValueError("review CSV must contain exactly one row for each source-bound offer component")
    expected = {str(row.get("record_id") or ""): row for row in source_rows}
    if len(expected) != len(source_rows):
        raise ValueError("Offer Lab source record IDs are not unique")
    seen: set[str] = set()
    decisions: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []
    for row in rows:
        record_id = str(row.get("record_id") or "")
        if record_id in seen or record_id not in expected:
            raise ValueError(f"duplicate or unknown offer-review record: {record_id}")
        seen.add(record_id)
        source = expected[record_id]
        try:
            start, end = int(row["source_byte_start"]), int(row["source_byte_end_exclusive"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{record_id}: source byte range is invalid") from exc
        span = register_bytes[start:end] if 0 <= start < end <= len(register_bytes) else b""
        statement = str(source.get("statement") or "")
        required = {
            "record_id": record_id,
            "customer_statement": statement,
            "source_ref": source.get("source_ref"),
            "source_byte_ref": source.get("source_byte_ref"),
            "source_register_sha256": register_sha,
            "source_row_sha256": source.get("source_row_sha256"),
            "source_statement_sha256": source.get("source_statement_sha256"),
            "source_byte_start": str(source.get("source_byte_start")),
            "source_byte_end_exclusive": str(source.get("source_byte_end_exclusive")),
            "epistemic_state": "CUSTOMER_DECLARED",
        }
        for field, value in required.items():
            if str(row.get(field) or "") != str(value or ""):
                raise ValueError(f"{record_id}: source-bound field changed: {field}")
        if (not span or _sha(span) != source.get("source_row_sha256")
                or _sha(statement.encode("utf-8")) != source.get("source_statement_sha256")
                or statement.encode("utf-8") not in span):
            raise ValueError(f"{record_id}: original source bytes no longer match the bound statement")
        decision = str(row.get("reviewer_decision") or "").strip()
        if decision not in DECISIONS:
            issues.append({"record_id": record_id, "code": "REVIEWER_DECISION_REQUIRED_OR_INVALID"})
        for field in ("reviewer_name", "reviewer_role", "rationale"):
            if not str(row.get(field) or "").strip():
                issues.append({"record_id": record_id, "code": field.upper() + "_REQUIRED"})
        timestamp = str(row.get("reviewed_at_iso8601") or "").strip()
        if not timestamp:
            issues.append({"record_id": record_id, "code": "REVIEW_TIME_REQUIRED"})
        else:
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                issues.append({"record_id": record_id, "code": "REVIEW_TIME_INVALID_ISO8601"})
            else:
                if parsed.utcoffset() is None:
                    issues.append({"record_id": record_id, "code": "REVIEW_TIME_MISSING_UTC_OFFSET"})
        decisions.append({"record_id": record_id, "decision": decision})
    return {
        "schema": "dio.offer_lab.owner_review_validation.v1",
        "validation_state": "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" if issues else "OWNER_REVIEW_RECORDED",
        "review_row_count": len(rows),
        "reviewer_decision_count": sum(bool(item["decision"]) for item in decisions),
        "issues": issues,
        "source_register_sha256": register_sha,
        "review_csv_sha256": _sha(review_csv_path.read_bytes()),
        "all_source_rows_verified": True,
        "decisions": decisions,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_validation": "UNPROVED",
        "professional_suitability": "NOT_ESTABLISHED",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "publication_authorized": False,
        "claim_boundary": "This receipt records source-bound customer/owner review only. It does not verify demand, payment, professional suitability, truth of customer statements, or authority to release the offer.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offer-json", type=Path, required=True)
    parser.add_argument("--source-register", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.offer_json, args.source_register, args.review_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"validation_state": result["validation_state"], "review_row_count": result["review_row_count"],
                      "external_release": result["external_release"], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
