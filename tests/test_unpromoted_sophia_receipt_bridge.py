from __future__ import annotations

import copy
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile
from products.unpromoted_sophia_profile import run_unpromoted_sophia_artifact_review


NOW = "2026-08-17T16:30:00+00:00"
PROFILES = ("sophia_integrity", "sophia_research")


def _case(tmp_path: Path, *, product: str, intake_state: str = "approved") -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"controlled-{product}-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["governed Sophia Review receipt"],
        expected_outputs=["controlled artifact provenance review", "human decision receipt"],
        required_authorities=["manuscript_owner", "academic_reviewer", "authorised_domain_decision_owner"],
        intake_state=intake_state,
        now=NOW,
    )


def _receipt() -> dict:
    return {
        "schema": "dio.sophia_review_receipt.v1",
        "job_id": "SOPHIA-RECEIPT-FIXTURE-001",
        "status": "needs_human_review",
        "source": {
            "name": "fixture.md",
            "sha256": "1" * 64,
            "parser": "plain_text",
            "word_count": 1200,
            "full_text_copied_to_pack": False,
        },
        "metrics": {
            "literature_queries": 2,
            "candidate_sources": 5,
            "claims_reviewed": 4,
            "reference_entries": 7,
            "reference_findings": 1,
            "reviewer_commentary_status": "completed",
            "reviewer_provider": "gemini",
            "reviewer_model": "fixture",
            "reviewer_grounding_passed": True,
        },
        "remote_processing": {
            "gemini_review_approved": True,
            "performed": True,
            "characters_transmitted": 4200,
        },
        "outputs": [
            {"name": "CLAIM_SOURCE_LEDGER.json", "sha256": "2" * 64},
            {"name": "REFERENCE_AUDIT.json", "sha256": "3" * 64},
            {"name": "REVIEWER_COMMENTARY.json", "sha256": "4" * 64},
            {"name": "HUMAN_APPROVAL.md", "sha256": "5" * 64},
        ],
        "delivery_released": False,
    }


@pytest.mark.parametrize("profile_id", PROFILES)
def test_sophia_receipt_bridge_proves_artifact_provenance_only(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }

    result = run_unpromoted_sophia_artifact_review(
        case,
        profile_id=profile_id,
        sophia_receipt=_receipt(),
        selected_output_names=["CLAIM_SOURCE_LEDGER.json", "REFERENCE_AUDIT.json"],
        output_dir=tmp_path / profile_id / "out",
        operator_id="human.sophia_receipt_test",
        now=NOW,
    )

    assert [
        row["review_state"]
        for row in result["review_pack"]["requirement_evidence_matrix"]
    ] == ["SUPPORTED", "SUPPORTED"]
    assert result["review_pack"]["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert result["review_pack"]["external_release"] == "REFUSE"
    assert result["receipt"]["execution_performed"] is False
    assert result["receipt"]["authority_created"] is False
    assert result["receipt"]["external_effects"] is False
    assert result["receipt"]["external_release"] is False

    binding = result["sophia_source_binding"]
    assert binding["source_contract"] == "sophia_review_receipt_artifacts"
    assert binding["selected_output_names"] == [
        "CLAIM_SOURCE_LEDGER.json",
        "REFERENCE_AUDIT.json",
    ]
    assert len(binding["receipt_sha256"]) == 64
    assert binding["source_sha256"] == "1" * 64
    assert binding["substantive_conclusion_proved"] is False
    assert binding["execution_proof_created"] is False
    assert binding["authority_created"] is False
    assert binding["external_effects"] is False
    assert binding["external_release"] is False

    for field in before:
        assert case[field] == before[field]


@pytest.mark.parametrize("profile_id", PROFILES)
def test_sophia_receipt_bridge_rejects_release_unapproved_remote_processing_and_approval_template(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])

    released = _receipt()
    released["delivery_released"] = True
    with pytest.raises(RuntimeError, match="already released"):
        run_unpromoted_sophia_artifact_review(
            case,
            profile_id=profile_id,
            sophia_receipt=released,
            selected_output_names=["REFERENCE_AUDIT.json"],
            output_dir=tmp_path / profile_id / "released",
            operator_id="human.sophia_receipt_test",
            now=NOW,
        )

    unapproved = _receipt()
    unapproved["remote_processing"]["gemini_review_approved"] = False
    with pytest.raises(RuntimeError, match="without explicit approval"):
        run_unpromoted_sophia_artifact_review(
            case,
            profile_id=profile_id,
            sophia_receipt=unapproved,
            selected_output_names=["REFERENCE_AUDIT.json"],
            output_dir=tmp_path / profile_id / "unapproved",
            operator_id="human.sophia_receipt_test",
            now=NOW,
        )

    with pytest.raises(ValueError, match="not bounded review artifacts"):
        run_unpromoted_sophia_artifact_review(
            case,
            profile_id=profile_id,
            sophia_receipt=_receipt(),
            selected_output_names=["HUMAN_APPROVAL.md"],
            output_dir=tmp_path / profile_id / "approval-template",
            operator_id="human.sophia_receipt_test",
            now=NOW,
        )


@pytest.mark.parametrize("profile_id", PROFILES)
def test_sophia_receipt_bridge_requires_explicit_output_scope_and_approved_intake(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    approved = _case(tmp_path / profile_id / "approved", product=profile["product_id"])
    with pytest.raises(ValueError, match="explicit non-empty selected_output_names"):
        run_unpromoted_sophia_artifact_review(
            approved,
            profile_id=profile_id,
            sophia_receipt=_receipt(),
            selected_output_names=[],
            output_dir=tmp_path / profile_id / "empty",
            operator_id="human.sophia_receipt_test",
            now=NOW,
        )

    with pytest.raises(ValueError, match="absent from the receipt"):
        run_unpromoted_sophia_artifact_review(
            approved,
            profile_id=profile_id,
            sophia_receipt=_receipt(),
            selected_output_names=["LITERATURE_MAP.json"],
            output_dir=tmp_path / profile_id / "unknown",
            operator_id="human.sophia_receipt_test",
            now=NOW,
        )

    pending = _case(
        tmp_path / profile_id / "pending",
        product=profile["product_id"],
        intake_state="pending",
    )
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_unpromoted_sophia_artifact_review(
            pending,
            profile_id=profile_id,
            sophia_receipt=_receipt(),
            selected_output_names=["REFERENCE_AUDIT.json"],
            output_dir=tmp_path / profile_id / "pending-out",
            operator_id="human.sophia_receipt_test",
            now=NOW,
        )
