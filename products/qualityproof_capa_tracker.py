"""Build a source-bound, human-completed CAPA review tracker."""
from __future__ import annotations
import csv
import hashlib
import io
import re
from datetime import date
from typing import Any, Mapping

DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CAPA_ID = re.compile(r"\bCAPA-[A-Za-z0-9_-]+\b", re.I)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _anchors(source_id: str, source: Mapping[str, Any], pattern: re.Pattern[str]) -> list[dict[str, Any]]:
    text = str(source.get("text") or "")
    raw = text.encode("utf-8")
    result = []
    for match in pattern.finditer(text):
        start, end = match.span()
        byte_start = len(text[:start].encode("utf-8"))
        byte_end = len(text[:end].encode("utf-8"))
        quote = raw[byte_start:byte_end]
        result.append({"literal": match.group(0), "source_id": source_id,
                       "source_sha256": _sha(raw), "source_byte_start": byte_start,
                       "source_byte_end_exclusive": byte_end,
                       "literal_sha256": _sha(quote),
                       "source_ref": f"customer-packet://{source_id}#bytes={byte_start}:{byte_end}"})
    return result


def build_capa_tracker(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    candidates = []
    for source_id, source in sources.items():
        text = str(source.get("text") or "")
        ids = {m.group(0).upper() for m in CAPA_ID.finditer(text)}
        if ids and "effectiveness check" in text.casefold():
            candidates.append((source_id, source, ids))
    capa_ids = sorted({capa_id for _, _, ids in candidates for capa_id in ids})
    if len(capa_ids) != 1:
        raise ValueError("QualityProof tracker requires exactly one uniquely named CAPA in the supplied packet")
    capa_id = capa_ids[0]
    action_source = next((row for row in candidates
                          if capa_id in row[2] and re.search(r"owner\s+assigned", str(row[1].get("text") or ""), re.I)
                          and re.search(r"effectiveness\s+check\s+planned", str(row[1].get("text") or ""), re.I)), None)
    exception_source = next((row for row in candidates
                             if capa_id in row[2] and re.search(r"effectiveness\s+check\s+record.*?not\s+found", str(row[1].get("text") or ""), re.I)), None)
    if action_source is None or exception_source is None:
        raise ValueError("QualityProof tracker requires source-reported ownership/schedule and closure-evidence status")
    action_id, action_record, _ = action_source
    exception_id, exception_record, _ = exception_source
    action_text = str(action_record.get("text") or "")
    exception_text = str(exception_record.get("text") or "")
    action_dates = _anchors(action_id, action_record, DATE)
    exception_dates = _anchors(exception_id, exception_record, DATE)
    if len(action_dates) < 2 or not exception_dates:
        raise ValueError("QualityProof tracker could not anchor the supplied assigned, planned and review dates")
    planned_date = next((row["literal"] for row in action_dates if "planned" in action_text[max(0, action_text.find(row["literal"])-50):action_text.find(row["literal"])] .casefold()), action_dates[-1]["literal"])
    issue_date = exception_dates[0]["literal"]
    date.fromisoformat(planned_date)
    date.fromisoformat(issue_date)
    relation = "PLANNED_DATE_PRECEDES_REVIEW_NOTE_DATE" if planned_date < issue_date else "PLANNED_DATE_NOT_BEFORE_REVIEW_NOTE_DATE"
    action_quote = _anchors(action_id, action_record, re.compile(re.escape(action_text)))[0]
    exception_quote = _anchors(exception_id, exception_record, re.compile(re.escape(exception_text)))[0]
    row = {
        "capa_id": capa_id,
        "source_reported_finding": {"quote": action_text, **action_quote},
        "owner_state": "OWNER_ASSIGNMENT_REPORTED_NAME_NOT_SUPPLIED",
        "owner_name": None,
        "action_source_id": action_id,
        "assigned_date_candidates": action_dates,
        "planned_effectiveness_date": next((item for item in action_dates if item["literal"] == planned_date), None),
        "closure_evidence_state": "SOURCE_REPORTS_RECORD_NOT_FOUND",
        "closure_evidence_issue": {"quote": exception_text, **exception_quote},
        "review_note_date": next((item for item in exception_dates if item["literal"] == issue_date), None),
        "date_relation": relation,
        "date_relation_boundary": "String-ordered ISO calendar dates only. This does not decide that an action is overdue, ineffective or nonconforming.",
        "review_fields": {
            "verified_owner": "", "verified_action_due_date": "", "closure_evidence_reference": "",
            "effectiveness_check_result": "", "reviewer_decision": "", "reviewer_name": "",
            "reviewed_at_iso8601": "", "reviewer_rationale": "",
        },
    }
    return {
        "schema": "dio.qualityproof.capa_review_tracker.v1",
        "items": [row],
        "claim_boundary": "Customer-source preparation only. All extracted dates, names, status and exceptions remain unverified. Blank review fields require a qualified reviewer; this tracker does not determine CAPA adequacy or closure.",
        "human_review_required": True,
        "professional_approval": "NOT_GRANTED",
        "release_authorized": False,
    }


def tracker_csv(tracker: Mapping[str, Any]) -> str:
    fields = ["capa_id", "source_reported_finding", "owner_state", "verified_owner",
              "assigned_date_candidates", "planned_effectiveness_date", "verified_action_due_date",
              "closure_evidence_state", "closure_evidence_issue", "closure_evidence_reference",
              "effectiveness_check_result", "review_note_date", "date_relation",
              "reviewer_decision", "reviewer_name", "reviewed_at_iso8601", "reviewer_rationale"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in tracker.get("items") or []:
        reviewer = row["review_fields"]
        writer.writerow({
            "capa_id": row["capa_id"], "source_reported_finding": row["source_reported_finding"]["quote"],
            "owner_state": row["owner_state"], "verified_owner": reviewer["verified_owner"],
            "assigned_date_candidates": " | ".join(item["literal"] for item in row["assigned_date_candidates"]),
            "planned_effectiveness_date": (row.get("planned_effectiveness_date") or {}).get("literal", ""),
            "verified_action_due_date": reviewer["verified_action_due_date"],
            "closure_evidence_state": row["closure_evidence_state"],
            "closure_evidence_issue": row["closure_evidence_issue"]["quote"],
            "closure_evidence_reference": reviewer["closure_evidence_reference"],
            "effectiveness_check_result": reviewer["effectiveness_check_result"],
            "review_note_date": (row.get("review_note_date") or {}).get("literal", ""),
            "date_relation": row["date_relation"], "reviewer_decision": reviewer["reviewer_decision"],
            "reviewer_name": reviewer["reviewer_name"], "reviewed_at_iso8601": reviewer["reviewed_at_iso8601"],
            "reviewer_rationale": reviewer["reviewer_rationale"],
        })
    return buffer.getvalue()
