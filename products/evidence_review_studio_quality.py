from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.evidence_review_studio import ENGINE_IDENTITY


SCHEMA = "dio.evidence_review_studio.artifact_quality.v1"
PASS_TOKEN = "DIO_EVIDENCE_REVIEW_STUDIO_ARTIFACT_QUALITY_VERIFIED"
REFUSE_TOKEN = "DIO_EVIDENCE_REVIEW_STUDIO_ARTIFACT_QUALITY_REFUSED"
DEFAULT_UNRESOLVED_REVIEW_STATES = {"CONTESTED", "PARTIAL", "UNKNOWN", "STALE"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit_profile_studio(
    receipt_path: Path,
    *,
    expected_profile_id: str,
    min_separate_records: int = 4,
    min_requirements: int = 2,
    min_issues: int = 1,
    required_review_states: set[str] | None = None,
) -> dict[str, Any]:
    receipt_path = Path(receipt_path).resolve()
    receipt = _load(receipt_path)
    root = receipt_path.parent
    rendered_root = root / "rendered"

    outputs = list(receipt.get("rendered_outputs") or [])
    output_by_channel = {str(row.get("channel") or ""): row for row in outputs}

    def rendered_ok(channel: str, minimum: int) -> bool:
        row = output_by_channel.get(channel)
        if not row:
            return False
        relative = str(row.get("path") or "")
        path = rendered_root / relative
        return path.is_file() and path.stat().st_size >= minimum

    forbidden = dict(receipt.get("forbidden_outcomes_created") or {})
    bundle = Path(str(receipt.get("bundle") or ""))
    mapping = dict(receipt.get("requirement_evidence_source_map") or {})
    provenance = list(receipt.get("evidence_provenance_index") or [])
    requirement_count = int(receipt.get("requirement_count") or 0)
    mapped_rows = [row for rows in mapping.values() for row in (rows or [])]
    named_sources = [str(row.get("source_path") or row.get("source_ref") or "") for row in mapped_rows]
    mapped_ids = {str(row.get("evidence_id") or "") for row in mapped_rows if str(row.get("evidence_id") or "")}
    provenance_ids = {str(row.get("evidence_id") or "") for row in provenance if str(row.get("evidence_id") or "")}
    observed_review_states = {str(value) for value in receipt.get("review_states") or [] if str(value)}
    expected_review_states = {
        str(value)
        for value in (required_review_states if required_review_states is not None else DEFAULT_UNRESOLVED_REVIEW_STATES)
        if str(value)
    }

    checks = {
        "schema": receipt.get("schema") == "dio.evidence_review_studio.receipt.v1",
        "engine_identity": receipt.get("engine_identity") == ENGINE_IDENTITY,
        "profile_identity": receipt.get("profile_id") == expected_profile_id,
        "separately_supplied_records": int(receipt.get("separately_supplied_record_count") or 0) >= min_separate_records,
        "requirements_substantive": requirement_count >= min_requirements,
        "issues_preserved": int(receipt.get("issue_count") or 0) >= min_issues,
        "open_questions_preserved": int(receipt.get("open_question_count") or 0) >= min_issues,
        "required_review_state_present": bool(expected_review_states) and bool(expected_review_states.intersection(observed_review_states)),
        "named_evidence_mapping_present": receipt.get("named_evidence_mapping_present") is True,
        "all_requirements_have_named_evidence": len(mapping) >= requirement_count > 0 and all(bool(rows) for rows in mapping.values()),
        "named_evidence_uses_customer_source_refs": bool(named_sources) and all(name.startswith("SOURCES/") for name in named_sources),
        "evidence_provenance_index_present": bool(mapped_ids) and mapped_ids.issubset(provenance_ids) and all(str(row.get("source_ref") or "") for row in provenance),
        "customer_assertions_not_self_supporting": receipt.get("customer_assertions_used_as_self_supporting_evidence") is False,
        "baseline_review_preserved": receipt.get("baseline_controlled_review_preserved") is True,
        "format_core_qa": receipt.get("format_core_qa_passed") is True,
        "docx_present": rendered_ok("docx", 15000),
        "pdf_present": rendered_ok("pdf", 15000),
        "html_present": rendered_ok("html", 3000),
        "bundle_present": bundle.is_file() and bundle.stat().st_size >= 20000,
        "forbidden_outcomes_explicit": bool(forbidden),
        "forbidden_outcomes_absent": bool(forbidden) and not any(forbidden.values()),
        "identity_unpromoted": receipt.get("identity_state") == "controlled_pilot_unpromoted",
        "canonical_registration_not_claimed": receipt.get("canonical_portfolio_registration") is False,
        "promotion_not_performed": receipt.get("promotion_performed") is False,
        "site_promotion_refused": receipt.get("site_promotion_allowed") is False,
        "commercial_validation_unproved": receipt.get("commercial_validation") == "UNPROVED",
        "human_review_required": receipt.get("human_review_gate") == "NEEDS_YOU",
        "external_release_refused": receipt.get("external_release_gate") == "REFUSE",
        "domain_decision_absent": receipt.get("domain_decision_created") is False,
        "domain_score_absent": receipt.get("domain_score_created") is False,
        "authority_absent": receipt.get("authority_created") is False,
        "external_effects_absent": receipt.get("external_effects") is False,
        "provider_not_called": receipt.get("provider_called") is False,
    }
    passed = all(checks.values())
    return {
        "schema": SCHEMA,
        "acceptance_token": PASS_TOKEN if passed else REFUSE_TOKEN,
        "artifact_quality_verified": passed,
        "profile_id": expected_profile_id,
        "required_review_states": sorted(expected_review_states),
        "observed_review_states": sorted(observed_review_states),
        "checks": checks,
        "failed_quality_checks": [name for name, ok in checks.items() if not ok],
        "identity_state": "controlled_pilot_unpromoted",
        "canonical_portfolio_registration": False,
        "promotion_performed": False,
        "site_promotion_allowed": False,
        "commercial_validation": "UNPROVED",
        "human_review": "NEEDS_YOU",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }


__all__ = [
    "DEFAULT_UNRESOLVED_REVIEW_STATES",
    "PASS_TOKEN",
    "REFUSE_TOKEN",
    "SCHEMA",
    "audit_profile_studio",
]
