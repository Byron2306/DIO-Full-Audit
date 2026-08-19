from dataclasses import replace
from pathlib import Path

import pytest

from commercial_metabolism.contracts import PaymentLineage, PaymentState
from commercial_metabolism.lineage import (
    M2_PHASE6_EXIT_TOKEN,
    exercise_controlled_lineage_scenarios,
    phase6_customer_payment_lineage_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase_receipt():
    return phase6_customer_payment_lineage_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def lineage_rows():
    rows, evidence = exercise_controlled_lineage_scenarios(REPO_ROOT)
    return {row.scenario_id: row for row in rows}, evidence


def test_m2_phase6_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE6_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-6"


def test_phase6_requires_verified_m2_phase5_parent(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_MARKET_RESPONSE_OBSERVED"
    assert phase_receipt["parent_verified"] is True


def test_lineage_evidence_schema_is_present(phase_receipt):
    assert phase_receipt["lineage_schema_valid"] is True


def test_exact_four_lineage_scenarios_are_exercised(lineage_rows, phase_receipt):
    rows, _evidence = lineage_rows
    assert set(rows) == {
        "verified_payment_without_acceptance",
        "operator_self_paid_acceptance",
        "independent_acceptance_without_payment",
        "independent_paid_acceptance_structural_gate",
    }
    assert phase_receipt["controlled_lineage_scenario_count"] == 4


def test_all_lineage_truth_is_bound_to_exact_commercial_context(lineage_rows, phase_receipt):
    rows, evidence = lineage_rows
    context = evidence["parent"]["context_digest"]
    assert all(row.context_digest == context for row in rows.values())
    assert phase_receipt["all_lineage_context_bound"] is True


def test_customer_and_payment_lineage_never_collapse_into_one_identity(lineage_rows, phase_receipt):
    rows, _evidence = lineage_rows
    assert all(row.customer_lineage_digest != row.payment_lineage_digest for row in rows.values())
    assert phase_receipt["customer_payment_lineage_distinct"] is True


def test_verified_payment_without_acceptance_does_not_satisfy_wtp_gate(lineage_rows, phase_receipt):
    rows, _evidence = lineage_rows
    row = rows["verified_payment_without_acceptance"]
    assert row.payment_verified_in_controlled_fixture is True
    assert row.customer_acceptance_observed_in_controlled_fixture is False
    assert row.structural_wtp_gate_satisfied is False
    assert phase_receipt["payment_only_wtp_gate"] is False


def test_operator_self_payment_and_acceptance_never_become_independent_demand(lineage_rows, phase_receipt):
    rows, _evidence = lineage_rows
    row = rows["operator_self_paid_acceptance"]
    assert row.customer_independence == "OPERATOR_SELF"
    assert row.payment_verified_in_controlled_fixture is True
    assert row.customer_acceptance_observed_in_controlled_fixture is True
    assert row.structural_wtp_gate_satisfied is False
    assert phase_receipt["operator_self_payment_wtp_gate"] is False


def test_independent_acceptance_without_verified_payment_does_not_satisfy_wtp_gate(lineage_rows, phase_receipt):
    rows, _evidence = lineage_rows
    row = rows["independent_acceptance_without_payment"]
    assert row.customer_independence == "INDEPENDENT_EXTERNAL"
    assert row.payment_state == "PENDING"
    assert row.customer_acceptance_observed_in_controlled_fixture is True
    assert row.structural_wtp_gate_satisfied is False
    assert phase_receipt["independent_acceptance_without_payment_wtp_gate"] is False


def test_independent_paid_acceptance_exercises_structural_gate_without_claiming_real_wtp(lineage_rows, phase_receipt):
    rows, _evidence = lineage_rows
    row = rows["independent_paid_acceptance_structural_gate"]
    assert row.customer_independence == "INDEPENDENT_EXTERNAL"
    assert row.payment_verified_in_controlled_fixture is True
    assert row.customer_acceptance_observed_in_controlled_fixture is True
    assert row.structural_wtp_gate_satisfied is True
    assert row.willingness_to_pay_proved is False
    assert phase_receipt["independent_paid_acceptance_structural_wtp_gate"] is True
    assert phase_receipt["real_willingness_to_pay_proved"] is False


def test_payment_observations_bind_exact_payment_lineage(lineage_rows, phase_receipt):
    rows, evidence = lineage_rows
    for scenario_id, row in rows.items():
        if not row.payment_verified_in_controlled_fixture:
            continue
        payment = evidence["rows"][scenario_id]["payment"]
        observations = evidence["rows"][scenario_id]["observations"]
        assert any(
            obs["kind"] == "PAYMENT" and obs["payment_lineage_id"] == payment["payment_lineage_id"]
            for obs in observations
        )
    assert phase_receipt["payment_observations_lineage_bound"] is True


def test_acceptance_observations_bind_exact_customer_lineage(lineage_rows, phase_receipt):
    rows, evidence = lineage_rows
    for scenario_id, row in rows.items():
        if not row.customer_acceptance_observed_in_controlled_fixture:
            continue
        customer = evidence["rows"][scenario_id]["customer"]
        observations = evidence["rows"][scenario_id]["observations"]
        assert any(
            obs["kind"] == "ACCEPTANCE" and obs["customer_lineage_id"] == customer["customer_lineage_id"]
            for obs in observations
        )
    assert phase_receipt["acceptance_observations_lineage_bound"] is True


def test_acceptance_is_bound_to_exact_controlled_artifact(lineage_rows, phase_receipt):
    rows, evidence = lineage_rows
    artifact = evidence["artifact_digest"]
    for scenario_id, row in rows.items():
        if row.customer_acceptance_observed_in_controlled_fixture:
            assert artifact in evidence["rows"][scenario_id]["customer"]["acceptance_refs"]
    assert phase_receipt["acceptance_artifact_bound"] is True


def test_existing_commercial_proof_v1_1_payment_guard_is_reused(lineage_rows, phase_receipt):
    rows, evidence = lineage_rows
    for scenario_id, row in rows.items():
        if not row.payment_verified_in_controlled_fixture:
            continue
        guard = evidence["rows"][scenario_id]["payment_guard"]
        assert guard["verified_payment"] == "VERIFIED_PAYMENT_PROVED"
        assert guard["willingness_to_pay"] == "WILLINGNESS_TO_PAY_UNPROVED"
        assert guard["controlled_fixture_only"] is True
    assert phase_receipt["commercial_proof_v1_1_payment_guard_reused"] is True
    assert phase_receipt["verified_payment_still_wtp_unproved_without_acceptance"] is True


def test_verified_payment_contract_rejects_missing_provider_and_live_order_evidence(lineage_rows):
    _rows, evidence = lineage_rows
    context = evidence["parent"]["context_digest"]
    with pytest.raises(ValueError):
        PaymentLineage(
            payment_lineage_id="PAYMENT-HOSTILE",
            context_digest=context,
            order_id="ORDER-HOSTILE",
            provider="CONTROLLED_DIO_EDGE_FIXTURE",
            amount_minor=12500,
            currency="ZAR",
            payment_state=PaymentState.VERIFIED,
            customer_lineage_id="CUSTOMER-HOSTILE",
            provider_event_refs=(),
            live_order_refs=(),
            verified_at=None,
        )


def test_controlled_lineage_evidence_refuses_wtp_or_commercial_overclaim(lineage_rows):
    rows, _evidence = lineage_rows
    row = rows["independent_paid_acceptance_structural_gate"]
    with pytest.raises(ValueError):
        replace(row, willingness_to_pay_proved=True)
    with pytest.raises(ValueError):
        replace(row, commercial_validation_proved=True)
    with pytest.raises(ValueError):
        replace(row, repeatability_proved=True)


def test_phase6_claims_no_real_payment_or_real_customer_acceptance(phase_receipt):
    assert phase_receipt["real_payment_verified"] is False
    assert phase_receipt["real_customer_acceptance_observed"] is False
    assert phase_receipt["real_willingness_to_pay_proved"] is False
    assert phase_receipt["commercial_validation_proved"] is False
    assert phase_receipt["repeatability_proved"] is False


def test_phase6_does_not_settle_crystallise_create_authority_or_external_effects(phase_receipt):
    assert phase_receipt["commercial_settlement_performed"] is False
    assert phase_receipt["market_crystal_created"] is False
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
