"""Hash-bound technical editor handoff for Document Studio Edit."""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any


FIELDS = [
    "paragraph_id", "source_sha256", "draft_sha256", "source_text", "draft_text",
    "provider_category", "provider_confidence", "provider_rationale",
    "editor_decision", "editor_revision", "editor_revision_sha256",
    "editor_rationale", "editor_reviewer", "editor_role",
    "editor_qualification_reference", "reviewed_at",
]


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp_is_aware_iso(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def build_technical_edit_review(change_ledger_path: str | Path, output_csv: str | Path) -> dict[str, Any]:
    ledger_path, output_path = Path(change_ledger_path), Path(output_csv)
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    if not source_rows:
        raise ValueError("Document Studio change ledger contains no paragraph rows")
    rows = []
    for source in source_rows:
        original = str(source.get("original") or "")
        draft = str(source.get("revised") or "")
        rows.append({
            "paragraph_id": str(source.get("paragraph_id") or ""),
            "source_sha256": _text_hash(original),
            "draft_sha256": _text_hash(draft),
            "source_text": original,
            "draft_text": draft,
            "provider_category": str(source.get("category") or ""),
            "provider_confidence": str(source.get("confidence") or ""),
            "provider_rationale": str(source.get("rationale") or ""),
            "editor_decision": "", "editor_revision": "", "editor_revision_sha256": "",
            "editor_rationale": "", "editor_reviewer": "", "editor_role": "",
            "editor_qualification_reference": "", "reviewed_at": "",
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    return {
        "schema": "dio.document_studio.technical_edit_review_template.v1",
        "path": output_path.name,
        "sha256": _file_hash(output_path),
        "paragraph_count": len(rows),
        "all_editor_decisions_blank": True,
        "blank_is_approval": False,
        "release_authorized": False,
    }


def validate_technical_edit_review(
    review_csv: str | Path, change_ledger_csv: str | Path
) -> dict[str, Any]:
    review_path, ledger_path = Path(review_csv).resolve(), Path(change_ledger_csv).resolve()
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    expected = {str(row.get("paragraph_id") or ""): row for row in source_rows}
    issues: list[dict[str, Any]] = []
    incomplete: list[str] = []
    seen: dict[str, dict[str, str]] = {}
    with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = sorted(set(FIELDS) - set(reader.fieldnames or []))
        if missing_columns:
            return {
                "schema": "dio.document_studio.technical_edit_review_validation.v1",
                "state": "INVALID_REVIEW_TEMPLATE", "issues": [{"code": "REQUIRED_COLUMNS_MISSING", "columns": missing_columns}],
                "release_authorized": False,
            }
        rows = list(reader)
    for line, row in enumerate(rows, 2):
        pid = str(row.get("paragraph_id") or "").strip()
        if pid not in expected:
            issues.append({"line": line, "code": "UNKNOWN_PARAGRAPH_ID", "paragraph_id": pid})
            continue
        if pid in seen:
            issues.append({"line": line, "code": "DUPLICATE_PARAGRAPH_ID", "paragraph_id": pid})
            continue
        seen[pid] = row
        source = expected[pid]
        original, draft = str(source.get("original") or ""), str(source.get("revised") or "")
        if row.get("source_text") != original or row.get("source_sha256") != _text_hash(original):
            issues.append({"line": line, "code": "SOURCE_BINDING_MISMATCH", "paragraph_id": pid})
        if row.get("draft_text") != draft or row.get("draft_sha256") != _text_hash(draft):
            issues.append({"line": line, "code": "DRAFT_BINDING_MISMATCH", "paragraph_id": pid})
        decision = str(row.get("editor_decision") or "").strip().upper()
        revision = str(row.get("editor_revision") or "")
        revision_hash = str(row.get("editor_revision_sha256") or "").strip()
        rationale = str(row.get("editor_rationale") or "").strip()
        reviewer = str(row.get("editor_reviewer") or "").strip()
        role = str(row.get("editor_role") or "").strip()
        qualification = str(row.get("editor_qualification_reference") or "").strip()
        reviewed_at = str(row.get("reviewed_at") or "").strip()
        decision_fields = (revision, revision_hash, rationale, reviewer, role, qualification, reviewed_at)
        if not decision and not any(value.strip() for value in decision_fields):
            incomplete.append(pid)
            continue
        if decision not in {"ACCEPT", "REVISE", "HOLD"}:
            issues.append({"line": line, "code": "INVALID_OR_MISSING_EDITOR_DECISION", "paragraph_id": pid})
            continue
        if not reviewer or not role or not qualification:
            issues.append({"line": line, "code": "EDITOR_IDENTITY_ROLE_AND_QUALIFICATION_REFERENCE_REQUIRED", "paragraph_id": pid})
            continue
        if not _timestamp_is_aware_iso(reviewed_at):
            issues.append({"line": line, "code": "REVIEW_TIMESTAMP_MUST_BE_ISO_WITH_TIMEZONE", "paragraph_id": pid})
            continue
        if decision == "ACCEPT" and (revision or revision_hash):
            issues.append({"line": line, "code": "ACCEPT_MUST_NOT_CONTAIN_REVISION", "paragraph_id": pid})
        elif decision == "REVISE":
            if not revision.strip() or revision == draft or revision_hash != _text_hash(revision):
                issues.append({"line": line, "code": "REVISED_TEXT_OR_HASH_INVALID", "paragraph_id": pid})
            if not rationale:
                issues.append({"line": line, "code": "REVISION_REQUIRES_RATIONALE", "paragraph_id": pid})
        elif decision == "HOLD" and (revision or revision_hash or not rationale):
            issues.append({"line": line, "code": "HOLD_REQUIRES_RATIONALE_AND_NO_REVISION", "paragraph_id": pid})
    missing_ids = sorted(set(expected) - set(seen))
    if missing_ids:
        issues.extend({"code": "SOURCE_PARAGRAPH_MISSING", "paragraph_id": pid} for pid in missing_ids)
    decisions = {str(row.get("editor_decision") or "").strip().upper() for row in seen.values()}
    if issues:
        state = "INVALID_REVIEW_REQUIRES_CORRECTION"
    elif incomplete or missing_ids:
        state = "NEEDS_TECHNICAL_EDITOR_COMPLETION"
    elif "HOLD" in decisions:
        state = "NEEDS_TECHNICAL_EDITOR_RESOLUTION"
    elif "REVISE" in decisions:
        state = "REVISIONS_RECORDED_REQUIRES_REPROCESSING"
    else:
        state = "TECHNICAL_EDITOR_REVIEW_COMPLETE_CLIENT_APPROVAL_PENDING"
    return {
        "schema": "dio.document_studio.technical_edit_review_validation.v1",
        "state": state, "review_csv_sha256": _file_hash(review_path),
        "change_ledger_sha256": _file_hash(ledger_path),
        "expected_paragraph_count": len(expected), "observed_paragraph_count": len(rows),
        "matched_paragraph_count": len(seen), "missing_paragraph_ids": missing_ids,
        "incomplete_paragraph_ids": incomplete, "issues": issues,
        "reviewer_identity_or_qualification_independently_verified": False,
        "editorial_quality_independently_verified": False,
        "client_approval_required": True, "release_authorized": False,
        "note": "A source-bound editor record does not independently verify credentials, editorial correctness, client approval, or release authority.",
    }
