from __future__ import annotations

import json
from pathlib import Path

from products.evidence_review_studio import ENGINE_IDENTITY
from products.evidence_review_studio_quality import PASS_TOKEN, REFUSE_TOKEN, audit_profile_studio


def _write_valid_receipt(tmp_path: Path, *, review_states: list[str]) -> Path:
    studio = tmp_path / "studio"
    rendered = studio / "rendered"
    rendered.mkdir(parents=True)

    for name, size in [
        ("review.docx", 15000),
        ("review.pdf", 15000),
        ("review.html", 3000),
    ]:
        (rendered / name).write_bytes(b"x" * size)

    bundle = studio / "ASSURANCEROOM_CONTROLLED_REVIEW_BUNDLE.zip"
    bundle.write_bytes(b"z" * 20000)

    mapping = {
        "OP-12": [
            {
                "evidence_id": "EVID-1",
                "source_ref": "customer-packet://SOURCES/monthly_reconciliation_signoffs.csv#SIGNOFFS",
                "source_path": "SOURCES/monthly_reconciliation_signoffs.csv",
            }
        ],
        "F-19": [
            {
                "evidence_id": "EVID-2",
                "source_ref": "customer-packet://SOURCES/remediation_ticket_f19.md#TICKET",
                "source_path": "SOURCES/remediation_ticket_f19.md",
            }
        ],
    }
    provenance = [
        {
            "evidence_id": "EVID-1",
            "source_ref": "customer-packet://SOURCES/monthly_reconciliation_signoffs.csv#SIGNOFFS",
        },
        {
            "evidence_id": "EVID-2",
            "source_ref": "customer-packet://SOURCES/remediation_ticket_f19.md#TICKET",
        },
    ]
    receipt = {
        "schema": "dio.evidence_review_studio.receipt.v1",
        "engine_identity": ENGINE_IDENTITY,
        "profile_id": "assuranceroom",
        "separately_supplied_record_count": 4,
        "requirement_count": 2,
        "issue_count": 2,
        "open_question_count": 2,
        "review_states": review_states,
        "named_evidence_mapping_present": True,
        "requirement_evidence_source_map": mapping,
        "evidence_provenance_index": provenance,
        "customer_assertions_used_as_self_supporting_evidence": False,
        "baseline_controlled_review_preserved": True,
        "format_core_qa_passed": True,
        "rendered_outputs": [
            {"channel": "docx", "path": "review.docx"},
            {"channel": "pdf", "path": "review.pdf"},
            {"channel": "html", "path": "review.html"},
        ],
        "bundle": str(bundle),
        "forbidden_outcomes_created": {"assurance_opinion": False},
        "identity_state": "controlled_pilot_unpromoted",
        "canonical_portfolio_registration": False,
        "promotion_performed": False,
        "site_promotion_allowed": False,
        "commercial_validation": "UNPROVED",
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "domain_decision_created": False,
        "domain_score_created": False,
        "authority_created": False,
        "external_effects": False,
        "provider_called": False,
    }
    path = studio / "EVIDENCE_REVIEW_STUDIO_RECEIPT.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def test_partial_is_valid_unresolved_family_state(tmp_path: Path) -> None:
    receipt = _write_valid_receipt(tmp_path, review_states=["PARTIAL"])
    quality = audit_profile_studio(
        receipt,
        expected_profile_id="assuranceroom",
        min_separate_records=4,
        min_requirements=2,
        min_issues=2,
    )
    assert quality["acceptance_token"] == PASS_TOKEN
    assert quality["artifact_quality_verified"] is True
    assert quality["checks"]["required_review_state_present"] is True
    assert quality["observed_review_states"] == ["PARTIAL"]


def test_product_can_require_contested_state_explicitly(tmp_path: Path) -> None:
    receipt = _write_valid_receipt(tmp_path, review_states=["PARTIAL"])
    quality = audit_profile_studio(
        receipt,
        expected_profile_id="assuranceroom",
        min_separate_records=4,
        min_requirements=2,
        min_issues=2,
        required_review_states={"CONTESTED"},
    )
    assert quality["acceptance_token"] == REFUSE_TOKEN
    assert quality["artifact_quality_verified"] is False
    assert quality["failed_quality_checks"] == ["required_review_state_present"]
