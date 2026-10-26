from pathlib import Path

import pytest

from commercial_metabolism.constitution import (
    M2_PHASE0_EXIT_TOKEN,
    REQUIRED_ANCHOR_IDS,
    REQUIRED_LAWS,
    validate_commercial_constitution,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def receipt():
    return validate_commercial_constitution(REPO_ROOT)


def test_m2_phase0_constitution_passes(receipt):
    assert receipt["passed"] is True, receipt
    assert receipt["acceptance"] == M2_PHASE0_EXIT_TOKEN


def test_m2_phase0_requires_verified_m1_parent(receipt):
    assert receipt["m1_parent_required"] is True
    assert receipt["m1_parent_verified"] is True
    assert receipt["m1_parent_acceptance"] == "DIO_METAMORPHIC_SPINE_M1_VERIFIED"
    assert receipt["reference_product"] == "funding_proposal_studio"


def test_m2_phase0_harvests_all_required_existing_anchors(receipt):
    assert receipt["missing_anchors"] == []
    assert receipt["invalid_anchors"] == []
    assert receipt["anchor_count"] == len(REQUIRED_ANCHOR_IDS)
    assert set(receipt["anchor_classifications"]) == REQUIRED_ANCHOR_IDS
    assert all(row["digest"].startswith("sha256:") for row in receipt["anchors"])


def test_m2_phase0_freezes_exact_commercial_laws(receipt):
    assert receipt["laws_exact"] is True
    assert receipt["laws_unique"] is True
    assert tuple(receipt["laws"]) == REQUIRED_LAWS


def test_m2_phase0_detects_and_quarantines_legacy_semantic_hazards(receipt):
    hazards = {row["id"]: row for row in receipt["legacy_semantic_hazards"]}
    assert receipt["legacy_semantic_hazard_failures"] == []
    assert hazards["legacy_payment_implies_wtp"]["state"] == "DETECTED_QUARANTINED"
    assert hazards["legacy_one_payment_means_someone_will_pay"]["state"] == "DETECTED_QUARANTINED"
    assert all(row["legacy_semantics_detected"] is True for row in hazards.values())
    assert all(row["required_correction_present"] is True for row in hazards.values())


def test_m2_phase0_payment_and_customer_truth_are_separate(receipt):
    assert receipt["payment_is_wtp"] is False
    assert receipt["payment_is_customer_acceptance"] is False
    assert receipt["self_payment_is_independent_demand"] is False
    checks = receipt["truth_guard_checks"]
    assert checks["payment_proves_payment_only"] is True
    assert checks["verified_payment_wtp_requires_independent_acceptance"] is True
    assert checks["one_customer_not_repeatability"] is True


def test_m2_phase0_market_command_is_not_promoted_to_authority(receipt):
    assert receipt["market_command_is_egress_authority"] is False
    assert receipt["authority_checks"]["market_command_is_not_authority_owner"] is True
    assert receipt["truth_guard_checks"]["market_command_automatic_spend_off"] is True


def test_m2_phase0_vesper_outlook_stays_draft_only(receipt):
    assert receipt["truth_guard_checks"]["vesper_outlook_remains_draft_only"] is True
    assert receipt["authority_checks"]["vesper_is_draft_only_customer_interface"] is True


def test_m2_phase0_seraph_remains_egress_boundary_owner(receipt):
    assert receipt["seraph_owns_egress_boundary"] is True
    assert receipt["authority_checks"]["seraph_is_egress_authority_owner"] is True
    assert receipt["authority_checks"]["legalis_is_prerequisite_not_egress"] is True


def test_m2_phase0_learning_crystals_and_success_never_mint_authority(receipt):
    assert receipt["commercial_success_mints_authority"] is False
    assert receipt["commercial_learning_direct_execution_allowed"] is False
    assert receipt["market_crystal_before_settlement_allowed"] is False
    assert receipt["truth_guard_checks"]["commercial_evidence_not_authority"] is True
    assert receipt["truth_guard_checks"]["learning_has_no_direct_execution_path"] is True
    assert receipt["authority_checks"]["beast_crystals_are_evidence_not_egress"] is True
    assert receipt["authority_checks"]["world_settlement_is_separate"] is True


def test_m2_phase0_controlled_reference_does_not_claim_market_validation(receipt):
    assert receipt["truth_guard_checks"]["controlled_reference_not_market_validation"] is True


def test_m2_phase0_creates_no_runtime_engine_or_external_effect(receipt):
    assert receipt["new_runtime_engine_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["authority_widened"] is False
    assert receipt["m2_final_verified"] is False
    assert receipt["m2_final_acceptance"] == "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"


def test_m2_phase0_fingerprint_is_deterministic_without_reexecuting_m1():
    first = validate_commercial_constitution(REPO_ROOT, verify_m1_parent=False)
    second = validate_commercial_constitution(REPO_ROOT, verify_m1_parent=False)
    assert first["constitution_fingerprint"] == second["constitution_fingerprint"]
    assert first["constitution_fingerprint"].startswith("sha256:")
