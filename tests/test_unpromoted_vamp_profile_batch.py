from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.meta import load_meta_registry
from products.registry import load_portfolio
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile
from products.unpromoted_vamp_profile import run_unpromoted_vamp_snapshot_review


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T15:30:00+00:00"
PROFILES = ("promotionproof", "cpdproof")


def _case(tmp_path: Path, *, product: str, intake_state: str = "approved") -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"controlled-{product}-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["governed VAMP evidence-coverage snapshot"],
        expected_outputs=[
            "controlled evidence-readiness pack",
            "issue register",
            "human review receipt",
        ],
        required_authorities=[
            "evidence_owner",
            "evidence_reviewer",
            "authorised_domain_decision_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


def _snapshot() -> dict:
    return {
        "schema": "dio.vamp_snapshot.v1",
        "job_id": "VAMP-PROFILE-FIXTURE-001",
        "quality_gates": [
            {"name": "profile_validated", "passed": True, "detail": "fixture"},
            {"name": "source_read_only", "passed": True, "detail": "fixture"},
            {"name": "ratings_disabled", "passed": True, "detail": "fixture"},
            {"name": "provenance_registered", "passed": True, "detail": "fixture"},
            {"name": "human_review_required", "passed": True, "detail": "fixture"},
        ],
        "release": {
            "status": "ready_for_human_review",
            "rating_generated": False,
            "employment_decision_generated": False,
        },
        "objectives": [
            {
                "objective_id": "OBJ-1",
                "domain_code": "KPA1",
                "title": "Evidence-backed activity",
                "period": "2026-01",
                "minimum_required": 1,
                "accepted_evidence": 1,
                "candidate_evidence": 0,
                "declared_no_evidence": False,
                "coverage_status": "evidence_backed",
            },
            {
                "objective_id": "OBJ-2",
                "domain_code": "KPA3",
                "title": "Partially evidenced activity",
                "period": "2026-01",
                "minimum_required": 2,
                "accepted_evidence": 1,
                "candidate_evidence": 1,
                "declared_no_evidence": False,
                "coverage_status": "partial",
            },
            {
                "objective_id": "OBJ-3",
                "domain_code": "KPA5",
                "title": "Activity with an unresolved evidence gap",
                "period": "2026-01",
                "minimum_required": 1,
                "accepted_evidence": 0,
                "candidate_evidence": 1,
                "declared_no_evidence": False,
                "coverage_status": "gap",
            },
        ],
    }


@pytest.mark.parametrize("profile_id", PROFILES)
def test_vamp_profiles_prepare_human_review_without_hr_or_professional_authority(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }

    result = run_unpromoted_vamp_snapshot_review(
        case,
        profile_id=profile_id,
        vamp_snapshot=_snapshot(),
        selected_objective_ids=["OBJ-1", "OBJ-2", "OBJ-3"],
        output_dir=tmp_path / profile_id / "out",
        operator_id="human.vamp_profile_test",
        now=NOW,
    )

    states = {
        row["requirement_key"]: row["review_state"]
        for row in result["review_pack"]["requirement_evidence_matrix"]
    }
    assert states == {"OBJ-1": "SUPPORTED", "OBJ-2": "PARTIAL", "OBJ-3": "UNKNOWN"}

    pack = result["review_pack"]
    assert pack["meta_composition"]["required_meta_products"] == [
        "meta_evidence",
        "meta_assurance",
        "meta_room",
    ]
    assert pack["meta_composition"]["release_guard_meta_product"] == "meta_authority"
    assert pack["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert pack["human_review"]["decision_receipt_created"] is False
    assert pack["external_release"] == "REFUSE"
    assert not any(pack["forbidden_outcomes_created"].values())

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["execution_performed"] is False
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False
    assert not any(receipt["forbidden_outcomes_created"].values())

    binding = result["vamp_source_binding"]
    assert binding["source_contract"] == "vamp_snapshot_evidence_coverage"
    assert binding["selected_objective_ids"] == ["OBJ-1", "OBJ-2", "OBJ-3"]
    assert len(binding["snapshot_sha256"]) == 64
    assert binding["rating_generated"] is False
    assert binding["employment_decision_generated"] is False
    assert binding["authority_created"] is False
    assert binding["external_effects"] is False
    assert binding["external_release"] is False

    for field in before:
        assert case[field] == before[field]



def test_vamp_profiles_remain_unpromoted_noncanonical_and_non_autopromotable() -> None:
    portfolio_ids = {row["id"] for row in load_portfolio()["products"]}
    composition_ids = {
        row["product_id"]
        for row in load_meta_registry()["vertical_compositions"]
    }
    routes = json.loads(
        (ROOT / "config" / "product_class_routes.json").read_text(encoding="utf-8")
    )

    for profile_id in PROFILES:
        profile = load_unpromoted_evidence_profile(profile_id)
        assert profile["identity_state"] == "genuine_profile_extension_unpromoted"
        assert profile["canonical_portfolio_registration"] is False
        assert profile["scope_basis"] == (
            "atlas_product_class_name_reconciliation_route_and_vamp_snapshot_only"
        )
        assert profile["source_contract"] == "vamp_snapshot_evidence_coverage"
        assert profile["product_id"] not in portfolio_ids
        assert profile["product_id"] not in composition_ids
        assert routes["product_classes"][profile_id] == {
            "route_kind": "profile_extension",
            "suggested_engine": "vamp",
            "auto_promotable": False,
        }


@pytest.mark.parametrize("profile_id", PROFILES)
def test_vamp_profiles_require_explicit_objective_scope(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])

    with pytest.raises(ValueError, match="explicit non-empty selected_objective_ids"):
        run_unpromoted_vamp_snapshot_review(
            case,
            profile_id=profile_id,
            vamp_snapshot=_snapshot(),
            selected_objective_ids=[],
            output_dir=tmp_path / profile_id / "out-empty",
            operator_id="human.vamp_profile_test",
            now=NOW,
        )

    with pytest.raises(ValueError, match="unknown objectives"):
        run_unpromoted_vamp_snapshot_review(
            case,
            profile_id=profile_id,
            vamp_snapshot=_snapshot(),
            selected_objective_ids=["OBJ-404"],
            output_dir=tmp_path / profile_id / "out-unknown",
            operator_id="human.vamp_profile_test",
            now=NOW,
        )


@pytest.mark.parametrize("profile_id", PROFILES)
def test_vamp_profiles_refuse_rating_employment_decision_or_blocked_snapshot(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])

    rated = _snapshot()
    rated["release"]["rating_generated"] = True
    with pytest.raises(RuntimeError, match="generated a rating"):
        run_unpromoted_vamp_snapshot_review(
            case,
            profile_id=profile_id,
            vamp_snapshot=rated,
            selected_objective_ids=["OBJ-1"],
            output_dir=tmp_path / profile_id / "out-rated",
            operator_id="human.vamp_profile_test",
            now=NOW,
        )

    employment = _snapshot()
    employment["release"]["employment_decision_generated"] = True
    with pytest.raises(RuntimeError, match="employment decision"):
        run_unpromoted_vamp_snapshot_review(
            case,
            profile_id=profile_id,
            vamp_snapshot=employment,
            selected_objective_ids=["OBJ-1"],
            output_dir=tmp_path / profile_id / "out-employment",
            operator_id="human.vamp_profile_test",
            now=NOW,
        )

    blocked = _snapshot()
    blocked["release"]["status"] = "blocked"
    with pytest.raises(RuntimeError, match="ready for human review"):
        run_unpromoted_vamp_snapshot_review(
            case,
            profile_id=profile_id,
            vamp_snapshot=blocked,
            selected_objective_ids=["OBJ-1"],
            output_dir=tmp_path / profile_id / "out-blocked",
            operator_id="human.vamp_profile_test",
            now=NOW,
        )


@pytest.mark.parametrize("profile_id", PROFILES)
def test_vamp_profiles_still_require_approved_intake_authority(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    pending = _case(
        tmp_path / profile_id / "pending",
        product=profile["product_id"],
        intake_state="pending",
    )
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_unpromoted_vamp_snapshot_review(
            pending,
            profile_id=profile_id,
            vamp_snapshot=_snapshot(),
            selected_objective_ids=["OBJ-1"],
            output_dir=tmp_path / profile_id / "out-pending",
            operator_id="human.vamp_profile_test",
            now=NOW,
        )
