from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.meta import load_meta_registry
from products.registry import load_portfolio
from products.unpromoted_evidence_profile import (
    load_unpromoted_evidence_profile,
    run_unpromoted_evidence_review,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T14:00:00+00:00"
PROFILES = (
    "impactproof",
    "projectproof",
    "certificationproof",
    "diligenceroom",
    "donorproof",
)


def _case(
    tmp_path: Path,
    *,
    product: str,
    intake_state: str = "approved",
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"controlled-{product}-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["authorised criteria or requests", "supporting evidence"],
        expected_outputs=[
            "requirement-evidence matrix",
            "issue register",
            "open-question list",
            "controlled evidence review pack",
            "human decision receipt",
        ],
        required_authorities=[
            "evidence_owner",
            "evidence_reviewer",
            "authorised_domain_decision_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


@pytest.mark.parametrize("profile_id", PROFILES)
def test_five_evidex_profiles_run_controlled_review_without_authority(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }
    prefix = profile["artifact_prefix"]

    result = run_unpromoted_evidence_review(
        case,
        profile_id=profile_id,
        requirements=[
            {
                "requirement_key": "REQ-1",
                "statement": "The first supplied criterion is supported by current reviewable evidence.",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
            {
                "requirement_key": "REQ-2",
                "statement": "The second supplied criterion is supported by current reviewable evidence.",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
        ],
        evidence_inputs=[
            {
                "evidence_kind": "controlled_source_record",
                "source_ref": f"{profile_id}://fixture/support",
                "sha256": "a" * 64,
                "target_requirement_keys": ["REQ-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "controlled_challenge_record",
                "source_ref": f"{profile_id}://fixture/challenge",
                "sha256": "b" * 64,
                "target_requirement_keys": ["REQ-2"],
                "relation": "contradicts",
                "severity": "material",
                "hypothesis": "The supplied record conflicts with the stated criterion.",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
        ],
        issues=[],
        output_dir=tmp_path / profile_id / "out",
        operator_id="human.evidex_profile_batch_test",
        now=NOW,
    )

    states = {
        row["requirement_key"]: row["review_state"]
        for row in result["review_pack"]["requirement_evidence_matrix"]
    }
    assert states == {"REQ-1": "SUPPORTED", "REQ-2": "CONTESTED"}

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

    proof = result["proof_manifest"]
    assert proof["execution_performed"] is False
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    for artifact in proof["artifacts"]:
        path = Path(result["output_dir"]) / artifact["filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["generic_executor_gate"] == "refuse"
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["domain_decision_created"] is False
    assert receipt["domain_score_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False
    assert not any(receipt["forbidden_outcomes_created"].values())

    for field in before:
        assert case[field] == before[field]

    out = Path(result["output_dir"])
    assert (out / f"{prefix}_REVIEW_PACK.json").is_file()
    assert (out / f"{prefix}_REVIEW_PACK.html").is_file()
    assert (out / "PROOF_MANIFEST.json").is_file()
    assert (out / f"{prefix}_PROCESSING_RECEIPT.json").is_file()


def test_five_evidex_profiles_remain_unpromoted_noncanonical_and_non_autopromotable() -> None:
    portfolio_ids = {row["id"] for row in load_portfolio()["products"]}
    composition_ids = {
        row["product_id"]
        for row in load_meta_registry()["vertical_compositions"]
    }
    routes = json.loads(
        (ROOT / "config" / "product_class_routes.json").read_text(encoding="utf-8")
    )
    reconciliation = json.loads(
        (ROOT / "config" / "product_class_reconciliation.json").read_text(
            encoding="utf-8"
        )
    )

    for profile_id in PROFILES:
        profile = load_unpromoted_evidence_profile(profile_id)
        product_id = profile["product_id"]
        assert profile["identity_state"] == "genuine_profile_extension_unpromoted"
        assert profile["canonical_portfolio_registration"] is False
        assert profile["scope_basis"] == "atlas_product_class_name_and_reconciliation_route_only"
        assert product_id not in portfolio_ids
        assert product_id not in composition_ids

        route = routes["product_classes"][profile_id]
        assert route["route_kind"] == "profile_extension"
        assert route["suggested_engine"] == "evidex"
        assert route["auto_promotable"] is False
        assert reconciliation["genuine_profile_extensions"][profile_id]["suggested_engine"] == "evidex"
        assert profile_id not in reconciliation["exact_canonical_incarnations"]
        assert profile_id not in reconciliation["equivalence_candidates"]
        assert profile_id not in reconciliation["resolved_composition_bindings"]


def test_generic_unpromoted_runner_refuses_unapproved_intake_and_wrong_product(
    tmp_path: Path,
) -> None:
    pending = _case(tmp_path / "pending", product="dio_impactproof", intake_state="pending")
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_unpromoted_evidence_review(
            pending,
            profile_id="impactproof",
            requirements=[
                {
                    "requirement_key": "REQ-1",
                    "statement": "A bounded evidence requirement exists.",
                    "dependency_requirement_keys": [],
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / "pending-out",
            operator_id="human.evidex_profile_batch_test",
            now=NOW,
        )

    wrong = _case(tmp_path / "wrong", product="dio_vendorproof")
    with pytest.raises(ValueError, match="requires product=dio_impactproof"):
        run_unpromoted_evidence_review(
            wrong,
            profile_id="impactproof",
            requirements=[
                {
                    "requirement_key": "REQ-1",
                    "statement": "A bounded evidence requirement exists.",
                    "dependency_requirement_keys": [],
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / "wrong-out",
            operator_id="human.evidex_profile_batch_test",
            now=NOW,
        )


def test_generic_unpromoted_runner_rejects_unsafe_profile_identifier() -> None:
    with pytest.raises(ValueError, match="safe lowercase identifier"):
        load_unpromoted_evidence_profile("../impactproof")
