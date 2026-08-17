from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.education_research_execution_proof import (
    controlled_education_research_fixture,
    profiles_by_product,
    run_education_research_execution_proof,
)
from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof


NOW = "2026-08-17T21:35:00+00:00"
PROFILE_IDS = (
    "homs_moderate",
    "homs_curriculum",
    "sophia_integrity",
    "sophia_research",
    "sophia_supervisor",
    "sophia_tutor",
)


def _product_for(profile_id: str) -> str:
    matches = [product_id for product_id, bound_profile in profiles_by_product().items() if bound_profile == profile_id]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_homs_sophia_execution_proof_runs_bounded_review_route_without_domain_authority(
    tmp_path: Path,
    profile_id: str,
) -> None:
    product_id = _product_for(profile_id)
    out = tmp_path / profile_id
    result = run_education_research_execution_proof(
        product_id,
        controlled_education_research_fixture(profile_id),
        output_dir=out,
        operator_id="human.education_research_execution_proof_test",
        now=NOW,
    )
    proof = result["proof"]
    assert proof["product_id"] == product_id
    assert proof["profile_id"] == profile_id
    assert proof["adapter_family"] == "homs_sophia_controlled_review"
    assert proof["executor_id"] == "controlled_evidence_review_v1"
    assert proof["suggested_engine"] == ("homs" if profile_id.startswith("homs_") else "sophia")
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert result["processor_result"]["receipt"]["execution_performed"] is False
    assert verify_execution_proof(out) == proof

    if profile_id == "homs_curriculum":
        binding = proof["source_binding"]
        assert binding["upstream_learning_pack_generation_proved"] is True
        assert binding["upstream_learning_pack_validation_proved"] is True
        assert binding["curriculum_correctness_proved"] is False
        assert binding["curriculum_approval_created"] is False
    elif profile_id in {"sophia_integrity", "sophia_research"}:
        binding = proof["source_binding"]
        assert binding["substantive_conclusion_proved"] is False
        assert binding["authority_created"] is False
    else:
        assert proof["source_binding"] is None


def test_homs_curriculum_execution_proof_refuses_released_upstream_pack(tmp_path: Path) -> None:
    fixture = copy.deepcopy(controlled_education_research_fixture("homs_curriculum"))
    fixture["manifest"]["authority"]["classroom_release"] = "released"
    with pytest.raises(RuntimeError, match="blocked classroom release"):
        run_education_research_execution_proof(
            _product_for("homs_curriculum"),
            fixture,
            output_dir=tmp_path / "released",
            operator_id="human.education_research_execution_proof_test",
            now=NOW,
        )


def test_sophia_execution_proof_refuses_human_approval_template_as_source_artifact(tmp_path: Path) -> None:
    fixture = copy.deepcopy(controlled_education_research_fixture("sophia_integrity"))
    fixture["selected_output_names"] = ["HUMAN_APPROVAL.md"]
    with pytest.raises(ValueError, match="not bounded review artifacts"):
        run_education_research_execution_proof(
            _product_for("sophia_integrity"),
            fixture,
            output_dir=tmp_path / "approval-template",
            operator_id="human.education_research_execution_proof_test",
            now=NOW,
        )


def test_homs_sophia_execution_proof_detects_top_level_tamper(tmp_path: Path) -> None:
    out = tmp_path / "tamper"
    product_id = _product_for("sophia_supervisor")
    run_education_research_execution_proof(
        product_id,
        controlled_education_research_fixture("sophia_supervisor"),
        output_dir=out,
        operator_id="human.education_research_execution_proof_test",
        now=NOW,
    )
    path = out / "PRODUCT_EXECUTION_PROOF.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    proof["authority_created"] = True
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="fingerprint mismatch"):
        verify_execution_proof(out)
