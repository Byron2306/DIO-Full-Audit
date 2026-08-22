from __future__ import annotations

from pathlib import Path
from typing import Any

from products.dossierops_native_hardening import load_json


def _paths(rows: list[dict[str, Any]]) -> str:
    return "; ".join(str(row.get("path") or "") for row in rows) if rows else "None separately matched"


def build_dossier_review_semantic(
    *,
    case_root: Path,
    manifest: dict[str, Any],
    cross_reference: dict[str, Any],
    chronology: list[dict[str, str]],
    open_questions: dict[str, Any],
) -> dict[str, Any]:
    intake = load_json(case_root / "CUSTOMER_PACKET" / "INTAKE.json")
    customer = dict(intake.get("customer") or {})
    organisation = str(customer.get("organisation") or intake.get("organisation") or "Customer organisation")
    buyer_role = str(customer.get("buyer_role") or intake.get("buyer") or "Authorised professional reviewer")
    request = str(intake.get("request") or "Prepare an indexed professional review dossier.").strip().rstrip(".")

    source_rows = []
    for row in manifest.get("sources") or []:
        source_rows.append([
            str(row.get("record_id") or ""),
            str(row.get("filename") or ""),
            str(row.get("record_class") or ""),
            str(row.get("record_state") or ""),
            "; ".join(str(v) for v in row.get("explicit_dates") or []) or "None extracted",
            "; ".join(str(v) for v in row.get("monetary_values") or []) or "None extracted",
        ])

    claim_rows = []
    for row in cross_reference.get("claims") or []:
        claim_rows.append([
            str(row.get("claim_id") or ""),
            str(row.get("customer_statement") or ""),
            str(row.get("corroboration_state") or ""),
            _paths(list(row.get("candidate_record_links") or [])),
            _paths(list(row.get("metadata_mentions") or [])),
        ])

    chronology_rows = [[
        row["date_as_supplied"], row["source_level"], row["filename"], row["record_class"], row["record_state"]
    ] for row in chronology]

    question_rows = [[
        str(row.get("question_id") or ""),
        str(row.get("severity") or ""),
        str(row.get("question") or ""),
        str(row.get("state") or ""),
    ] for row in open_questions.get("questions") or []]

    blocks: list[dict[str, Any]] = [
        {"block_id": "title", "type": "title", "text": "DIO DossierOps Controlled Review Brief"},
        {"block_id": "purpose-h", "type": "heading", "level": 1, "text": "Review purpose and boundary"},
        {"block_id": "purpose-p1", "type": "paragraph", "text": f"This dossier preparation was created from {len(source_rows)} customer-supplied source records captured through Vesper custody. The requested work is: {request}. The pack is a review aid for an authorised human reviewer. It does not certify dossier completeness, determine legal sufficiency or enforceability, attest authenticity, authorise retention or disposal, submit material externally, or release a final dossier."},
        {"block_id": "purpose-p2", "type": "paragraph", "text": "DossierOps keeps record state separate from legal effect. A source described by the customer as signed is indexed according to the visible supplied state; DIO does not independently authenticate signatures. An unsigned draft remains an unsigned draft even where correspondence records agreement in principle. Financial values remain customer-supplied values unless an authorised reviewer reconciles them to controlling records."},
        {"block_id": "context-h", "type": "heading", "level": 1, "text": "Customer context"},
        {"block_id": "context-p", "type": "paragraph", "text": f"Organisation: {organisation}. Buyer / reviewer role: {buyer_role}. The review task is to preserve which record says what, distinguish record states, identify missing controlling records, and surface unresolved questions for authorised professional review."},
        {"block_id": "inventory-h", "type": "heading", "level": 1, "text": "Source inventory and custody"},
        {"block_id": "inventory-table", "type": "table", "headers": ["ID", "File", "Record class", "Record state", "Dates", "Monetary values"], "rows": source_rows},
        {"block_id": "inventory-note", "type": "paragraph", "text": "Full SHA-256 hashes and custody metadata are retained in the hardened source manifest. Hash binding identifies the exact bytes used in this review; it does not establish authenticity or legal effect."},
        {"block_id": "claims-h", "type": "heading", "level": 1, "text": "Customer statements and record cross-reference"},
        {"block_id": "claims-table", "type": "table", "headers": ["Claim", "Customer statement", "Navigation state", "Actual record candidates", "Metadata mentions"], "rows": claim_rows},
        {"block_id": "claims-note", "type": "paragraph", "text": "Candidate links are navigation aids only. Metadata containers and case indexes are shown separately and are not treated as corroborating records. Claim support and legal effect remain undetermined."},
        {"block_id": "chronology-h", "type": "heading", "level": 1, "text": "Chronology for review"},
        {"block_id": "chronology-table", "type": "table", "headers": ["Date", "Source level", "File", "Record class", "Record state"], "rows": chronology_rows or [["No explicit date extracted", "n/a", "n/a", "n/a", "n/a"]]},
        {"block_id": "chronology-note", "type": "paragraph", "text": "Chronology entries are ordered by the date as supplied. Metadata assertions and dates visible in record text remain distinct. No chronology entry determines legal, financial or procedural effect."},
        {"block_id": "hierarchy-h", "type": "heading", "level": 1, "text": "Record-state hierarchy"},
        {"block_id": "hierarchy-p", "type": "paragraph", "text": "The pack does not collapse signed, unsigned, draft, correspondence and metadata states. The signed agreement and unsigned amendment draft occupy different positions in the supplied material. Agreement-in-principle correspondence is not transformed into an executed amendment. A case-file index is an index, not proof that every listed item has been separately supplied or authenticated."},
        {"block_id": "questions-h", "type": "heading", "level": 1, "text": "Open questions and gaps"},
        {"block_id": "questions-table", "type": "table", "headers": ["Question", "Severity", "Review question", "State"], "rows": question_rows or [["None detected", "review", "Absence of a machine-detected gap is not a completeness finding.", "OPEN_HUMAN_REVIEW"]]},
        {"block_id": "queue-h", "type": "heading", "level": 1, "text": "Counsel review queue"},
        {"block_id": "queue-list", "type": "bullet_list", "items": [
            "Confirm the governing role of the signed agreement by inspecting the controlling signed record.",
            "Resolve the status of the 18 April 2026 unsigned amendment draft without treating agreement-in-principle correspondence as execution authority.",
            "Confirm the source, period and reconciliation status of the R426,000 outstanding amount before it is used in a decision or external communication.",
            "Reconcile the case-file index against the separately supplied files and request missing controlling records.",
            "Review chronology and cross-reference entries against underlying customer records before adopting any professional conclusion.",
        ]},
        {"block_id": "provenance-h", "type": "heading", "level": 1, "text": "Provenance and limitations"},
        {"block_id": "provenance-p1", "type": "paragraph", "text": "Every indexed source remains hash-bound to the Vesper-rehydrated customer packet. DossierOps may classify visible record states and extract dates or amounts as navigation observations. It does not authenticate documents, infer missing signatures, decide contractual effect, certify completeness, or decide retention, disclosure, submission or release."},
        {"block_id": "provenance-p2", "type": "paragraph", "text": "Cross-reference links are deterministic navigation aids filtered by record class. Where only a metadata container mentions a record, the final dossier says no separately supplied controlling record was matched instead of promoting that metadata mention into corroboration."},
        {"block_id": "release-h", "type": "heading", "level": 1, "text": "Release gate"},
        {"block_id": "release-p", "type": "paragraph", "text": "HUMAN REVIEW REQUIRED. EXTERNAL RELEASE REFUSED. Dossier completeness, legal sufficiency, authenticity, enforceability, retention or disposal decisions, external submission and final release remain with authorised humans."},
    ]

    return {
        "schema": "dio.semantic_content.v1",
        "object_id": "dossierops-stonebridge-controlled-review-finalized",
        "version": "1.0.0",
        "title": "DIO DossierOps Controlled Review Brief",
        "source_language": "English",
        "context": {"product": "DossierOps", "artifact_type": "controlled_professional_review_dossier", "audience": buyer_role},
        "blocks": blocks,
        "translations": {},
    }
