from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile
from products.unpromoted_homs_profile import (
    run_unpromoted_homs_curriculum_artifact_review,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = (
    ROOT
    / "deliverables"
    / "homs_learning_studio"
    / "grade_10_physical_sciences_term_3_motion"
)
NOW = "2026-08-17T19:45:00+00:00"


def _load(name: str) -> dict:
    return json.loads((PACK / name).read_text(encoding="utf-8"))


def _case(tmp_path: Path, *, intake_state: str = "approved") -> dict:
    profile = load_unpromoted_evidence_profile("homs_curriculum")
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=profile["product_id"],
        job_id=f"homs-curriculum-bridge-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["HOMS Learning Studio manifest and receipts"],
        expected_outputs=[
            "curriculum provenance matrix",
            "controlled curriculum review pack",
            "human curriculum decision receipt",
        ],
        required_authorities=[
            "education_material_owner",
            "education_reviewer",
            "authorised_academic_decision_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


def test_homs_curriculum_consumes_learning_studio_provenance_without_promoting_authority(
    tmp_path: Path,
) -> None:
    manifest = _load("LEARNING_PACK_MANIFEST.json")
    validation = _load("HOMS_LEARNING_PACK_VALIDATION.json")
    receipt = _load("HOMS_LEARNING_PACK_BUILD_RECEIPT.json")
    selected = [
        "documents/HOMS_G10_T3_MOTION_LEARNER_GUIDE.docx",
        "documents/HOMS_G10_T3_MOTION_MINI_ASSESSMENT.docx",
    ]

    case = _case(tmp_path / "case")
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }

    result = run_unpromoted_homs_curriculum_artifact_review(
        case,
        manifest=manifest,
        validation=validation,
        build_receipt=receipt,
        selected_document_paths=selected,
        output_dir=tmp_path / "out",
        operator_id="human.homs_curriculum_bridge_test",
        now=NOW,
    )

    states = {
        row["requirement_key"]: row["review_state"]
        for row in result["review_pack"]["requirement_evidence_matrix"]
    }
    assert states == {
        "HOMS-ARTIFACT-1": "SUPPORTED",
        "HOMS-ARTIFACT-2": "SUPPORTED",
        "HOMS-CURRICULUM-SOURCE": "SUPPORTED",
    }

    binding = result["homs_source_binding"]
    assert binding["homs_pack_id"] == manifest["pack_id"]
    assert binding["selected_document_paths"] == selected
    assert binding["upstream_learning_pack_generation_proved"] is True
    assert binding["upstream_learning_pack_validation_proved"] is True
    assert binding["curriculum_correctness_proved"] is False
    assert binding["curriculum_approval_created"] is False
    assert binding["programme_quality_certification_created"] is False
    assert binding["execution_proof_created"] is False
    assert binding["authority_created"] is False
    assert binding["external_effects"] is False
    assert binding["external_release"] is False

    assert result["review_pack"]["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert result["review_pack"]["external_release"] == "REFUSE"
    assert result["receipt"]["execution_performed"] is False
    assert result["receipt"]["authority_created"] is False
    assert result["receipt"]["external_effects"] is False
    assert result["receipt"]["external_release"] is False
    assert not any(result["receipt"]["forbidden_outcomes_created"].values())

    for field in before:
        assert case[field] == before[field]


def test_homs_curriculum_refuses_released_or_unvalidated_learning_pack(
    tmp_path: Path,
) -> None:
    manifest = _load("LEARNING_PACK_MANIFEST.json")
    validation = _load("HOMS_LEARNING_PACK_VALIDATION.json")
    receipt = _load("HOMS_LEARNING_PACK_BUILD_RECEIPT.json")

    released = copy.deepcopy(manifest)
    released["authority"]["classroom_release"] = "released"
    with pytest.raises(RuntimeError, match="blocked classroom release"):
        run_unpromoted_homs_curriculum_artifact_review(
            _case(tmp_path / "released"),
            manifest=released,
            validation=validation,
            build_receipt=receipt,
            selected_document_paths=[
                "documents/HOMS_G10_T3_MOTION_LEARNER_GUIDE.docx"
            ],
            output_dir=tmp_path / "released-out",
            operator_id="human.homs_curriculum_bridge_test",
            now=NOW,
        )

    failed_validation = copy.deepcopy(validation)
    failed_validation["passed"] = False
    with pytest.raises(RuntimeError, match="passed pack validation"):
        run_unpromoted_homs_curriculum_artifact_review(
            _case(tmp_path / "failed"),
            manifest=manifest,
            validation=failed_validation,
            build_receipt=receipt,
            selected_document_paths=[
                "documents/HOMS_G10_T3_MOTION_LEARNER_GUIDE.docx"
            ],
            output_dir=tmp_path / "failed-out",
            operator_id="human.homs_curriculum_bridge_test",
            now=NOW,
        )


def test_homs_curriculum_requires_explicit_known_artifact_selection(
    tmp_path: Path,
) -> None:
    manifest = _load("LEARNING_PACK_MANIFEST.json")
    validation = _load("HOMS_LEARNING_PACK_VALIDATION.json")
    receipt = _load("HOMS_LEARNING_PACK_BUILD_RECEIPT.json")

    with pytest.raises(ValueError, match="explicit non-empty selected_document_paths"):
        run_unpromoted_homs_curriculum_artifact_review(
            _case(tmp_path / "empty"),
            manifest=manifest,
            validation=validation,
            build_receipt=receipt,
            selected_document_paths=[],
            output_dir=tmp_path / "empty-out",
            operator_id="human.homs_curriculum_bridge_test",
            now=NOW,
        )

    with pytest.raises(ValueError, match="absent from the manifest"):
        run_unpromoted_homs_curriculum_artifact_review(
            _case(tmp_path / "unknown"),
            manifest=manifest,
            validation=validation,
            build_receipt=receipt,
            selected_document_paths=["documents/NOT_A_REAL_HOMS_ARTIFACT.docx"],
            output_dir=tmp_path / "unknown-out",
            operator_id="human.homs_curriculum_bridge_test",
            now=NOW,
        )


def test_homs_curriculum_bridge_still_requires_approved_intake(
    tmp_path: Path,
) -> None:
    manifest = _load("LEARNING_PACK_MANIFEST.json")
    validation = _load("HOMS_LEARNING_PACK_VALIDATION.json")
    receipt = _load("HOMS_LEARNING_PACK_BUILD_RECEIPT.json")

    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_unpromoted_homs_curriculum_artifact_review(
            _case(tmp_path / "pending", intake_state="pending"),
            manifest=manifest,
            validation=validation,
            build_receipt=receipt,
            selected_document_paths=[
                "documents/HOMS_G10_T3_MOTION_LEARNER_GUIDE.docx"
            ],
            output_dir=tmp_path / "pending-out",
            operator_id="human.homs_curriculum_bridge_test",
            now=NOW,
        )
