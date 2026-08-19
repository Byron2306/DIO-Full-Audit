from pathlib import Path

import pytest

from commercial_metabolism.final_verification import (
    EXPECTED_PHASE_ACCEPTANCES,
    FINAL_GATES,
    M2_PHASE9_EXIT_TOKEN,
    phase9_final_verification_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def final_receipt():
    return phase9_final_verification_receipt(REPO_ROOT)


def test_m2_phase9_final_gate_passes(final_receipt):
    assert final_receipt["passed"] is True, final_receipt
    assert final_receipt["acceptance"] == M2_PHASE9_EXIT_TOKEN
    assert final_receipt["phase"] == "M2-9"


def test_phase9_requires_verified_m2_phase8_parent(final_receipt):
    assert final_receipt["parent_phase"] == "M2-8"
    assert final_receipt["parent_acceptance"] == "DIO_M2_PROJECTION_ADAPTATION_READY"
    assert final_receipt["parent_verified"] is True


def test_final_receipt_schema_and_sixteen_gate_contract(final_receipt):
    assert final_receipt["schema"] == "dio.commercial_metabolism_final_receipt.v1"
    assert final_receipt["gate_count"] == 16
    assert final_receipt["passed_gate_count"] == 16
    assert tuple(final_receipt["acceptance_gates"]) == FINAL_GATES


def test_every_m2_parent_phase_is_reverified(final_receipt):
    assert final_receipt["phase_acceptances"] == EXPECTED_PHASE_ACCEPTANCES


def test_m1_parent_remains_verified(final_receipt):
    assert final_receipt["m1_verified"] is True


def test_gate_commercial_context_bound(final_receipt):
    assert final_receipt["acceptance_gates"]["COMMERCIAL_CONTEXT_BOUND"] is True


def test_gate_market_crystal_schema_valid(final_receipt):
    assert final_receipt["acceptance_gates"]["MARKET_CRYSTAL_SCHEMA_VALID"] is True
    evidence = final_receipt["gate_evidence"]["MARKET_CRYSTAL_SCHEMA_VALID"]
    assert evidence["market_crystal_count"] == 4
    assert evidence["market_crystal_chain_valid"] is True


def test_gate_claim_evidence_bound(final_receipt):
    assert final_receipt["acceptance_gates"]["CLAIM_EVIDENCE_BOUND"] is True
    assert final_receipt["gate_evidence"]["CLAIM_EVIDENCE_BOUND"]["m1_projection_proof_anchor"].startswith("sha256:")


def test_gate_unproven_claims_refused(final_receipt):
    assert final_receipt["acceptance_gates"]["UNPROVEN_CLAIMS_REFUSED"] is True
    evidence = final_receipt["gate_evidence"]["UNPROVEN_CLAIMS_REFUSED"]
    assert evidence["held_market_claim_count"] == 6
    assert evidence["market_claim_upgrade_performed"] is False


def test_gate_channel_authority_separate(final_receipt):
    assert final_receipt["acceptance_gates"]["CHANNEL_AUTHORITY_SEPARATE"] is True


def test_gate_spend_authority_separate(final_receipt):
    assert final_receipt["acceptance_gates"]["SPEND_AUTHORITY_SEPARATE"] is True
    evidence = final_receipt["gate_evidence"]["SPEND_AUTHORITY_SEPARATE"]
    assert evidence["automatic_spend"] == "off"
    assert evidence["budget_cap_minor"] == 0


def test_gate_payment_lineage_bound(final_receipt):
    assert final_receipt["acceptance_gates"]["PAYMENT_LINEAGE_BOUND"] is True
    assert final_receipt["gate_evidence"]["PAYMENT_LINEAGE_BOUND"]["payment_only_wtp_gate"] is False


def test_gate_customer_lineage_bound(final_receipt):
    assert final_receipt["acceptance_gates"]["CUSTOMER_LINEAGE_BOUND"] is True


def test_gate_market_response_observed_without_real_market_overclaim(final_receipt):
    assert final_receipt["acceptance_gates"]["MARKET_RESPONSE_OBSERVED"] is True
    evidence = final_receipt["gate_evidence"]["MARKET_RESPONSE_OBSERVED"]
    assert evidence["scope"] == "controlled_fixture"
    assert evidence["real_market_response_observed"] is False


def test_gate_no_response_can_be_recorded_after_closed_window(final_receipt):
    assert final_receipt["acceptance_gates"]["NO_RESPONSE_CAN_BE_RECORDED"] is True
    evidence = final_receipt["gate_evidence"]["NO_RESPONSE_CAN_BE_RECORDED"]
    assert evidence["window_closed"] is True
    assert evidence["scope"] == "exact_commercial_context_only"


def test_gate_loss_can_be_recorded_without_global_product_failure(final_receipt):
    assert final_receipt["acceptance_gates"]["LOSS_CAN_BE_RECORDED"] is True
    assert final_receipt["repeatability_adversary"]["cases"]["loss_recordable_without_global_failure"] is True


def test_gate_world_settlement_complete(final_receipt):
    assert final_receipt["acceptance_gates"]["WORLD_SETTLEMENT_COMPLETE"] is True
    evidence = final_receipt["gate_evidence"]["WORLD_SETTLEMENT_COMPLETE"]
    assert evidence["world_settlement_complete"] is True
    assert evidence["commercial_settlement_complete"] is True


def test_gate_lingua_projection_can_update_without_claim_upgrade(final_receipt):
    assert final_receipt["acceptance_gates"]["LINGUA_PROJECTION_CAN_UPDATE"] is True
    assert final_receipt["gate_evidence"]["LINGUA_PROJECTION_CAN_UPDATE"]["claim_upgrade_performed"] is False


def test_gate_negative_market_learning_is_context_bound(final_receipt):
    assert final_receipt["acceptance_gates"]["NEGATIVE_MARKET_LEARNING_CONTEXT_BOUND"] is True
    evidence = final_receipt["gate_evidence"]["NEGATIVE_MARKET_LEARNING_CONTEXT_BOUND"]
    assert evidence["threshold"] == 3
    assert evidence["active_match_count"] == 0


def test_gate_commercial_success_does_not_create_authority(final_receipt):
    assert final_receipt["acceptance_gates"]["NO_AUTHORITY_FROM_COMMERCIAL_SUCCESS"] is True
    assert final_receipt["repeatability_adversary"]["cases"]["commercial_success_does_not_create_authority"] is True


def test_gate_repeatability_not_overclaimed(final_receipt):
    assert final_receipt["acceptance_gates"]["REPEATABILITY_NOT_OVERCLAIMED"] is True
    assert final_receipt["repeatability_proved"] is False


def test_repeatability_adversary_all_eight_cases_pass(final_receipt):
    adversary = final_receipt["repeatability_adversary"]
    assert adversary["case_count"] == 8
    assert adversary["passed_case_count"] == 8
    assert adversary["all_cases_passed"] is True
    assert all(adversary["cases"].values())


def test_three_replays_of_same_controlled_truth_are_not_three_independent_customers(final_receipt):
    adversary = final_receipt["repeatability_adversary"]
    assert adversary["controlled_replay_count"] == 3
    assert adversary["distinct_replayed_truth_count"] == 1
    assert adversary["same_fixture_replay_is_repeatability"] is False


def test_underpowered_repeatability_is_refused_by_contract(final_receipt):
    assert final_receipt["repeatability_adversary"]["contract_refuses_underpowered_repeatability"] is True


def test_commercial_metabolism_verification_does_not_claim_commercial_success(final_receipt):
    assert final_receipt["commercial_success_required_for_metabolism_verification"] is False
    assert final_receipt["commercial_success_proved"] is False
    assert final_receipt["real_market_evidence"] is False
    assert final_receipt["real_payment_verified"] is False
    assert final_receipt["real_customer_acceptance_observed"] is False
    assert final_receipt["real_willingness_to_pay_proved"] is False
    assert final_receipt["commercial_validation_proved"] is False
    assert final_receipt["repeatability_proved"] is False


def test_m3_content_dataflow_boundary_is_preserved(final_receipt):
    assert final_receipt["content_transform_dataflow_proved"] is False
    assert final_receipt["m3_boundary_preserved"] is True


def test_final_programme_boundary_and_completion_flags(final_receipt):
    assert final_receipt["authority_created"] is False
    assert final_receipt["authority_widened"] is False
    assert final_receipt["external_effects"] is False
    assert final_receipt["new_runtime_engine_created"] is False
    assert final_receipt["commercial_metabolism_verified"] is True
    assert final_receipt["m2_final_verified"] is True
    assert final_receipt["programme_complete"] is True
    assert final_receipt["final_gate_digest"].startswith("sha256:")
