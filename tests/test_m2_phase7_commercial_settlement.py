from dataclasses import replace
from pathlib import Path

import pytest

from adapters.beast.commercial_crystallisation import (
    CommercialCrystallisationError,
    crystallize_commercial_settlement,
)
from commercial_metabolism.contracts import (
    CommercialSettlementState,
    EvidenceClaimState,
)
from commercial_metabolism.settlement import (
    M2_PHASE7_EXIT_TOKEN,
    phase7_commercial_settlement_receipt,
    settle_and_crystallize_controlled_commercial_evidence,
)
from metamorphic.contracts import SettlementState


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase_receipt():
    return phase7_commercial_settlement_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def settled(tmp_path_factory):
    bundles, evidence = settle_and_crystallize_controlled_commercial_evidence(
        REPO_ROOT,
        state_root=tmp_path_factory.mktemp("m2_phase7_settlement"),
    )
    return {row.scenario_id: row for row in bundles}, evidence


def test_m2_phase7_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE7_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-7"


def test_phase7_requires_verified_m2_phase6_parent(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_CUSTOMER_PAYMENT_LINEAGE_BOUND"
    assert phase_receipt["parent_verified"] is True


def test_settlement_bundle_schema_is_present(phase_receipt):
    assert phase_receipt["settlement_bundle_schema_valid"] is True


def test_exact_four_controlled_lineage_worlds_are_settled(settled, phase_receipt):
    bundles, _evidence = settled
    assert set(bundles) == {
        "verified_payment_without_acceptance",
        "operator_self_paid_acceptance",
        "independent_acceptance_without_payment",
        "independent_paid_acceptance_structural_gate",
    }
    assert phase_receipt["commercial_settlement_count"] == 4


def test_world_settlement_is_complete_and_stable(settled, phase_receipt):
    bundles, _evidence = settled
    assert phase_receipt["world_settlement_complete"] is True
    for row in bundles.values():
        world = row.world_settlement
        assert world.settlement_state is SettlementState.SETTLED
        assert world.pre_world_digest == world.post_world_digest
        assert world.authority_preserved is True
        assert world.unexpected_effects == ()


def test_commercial_settlement_is_complete_and_crystal_eligible(settled, phase_receipt):
    bundles, _evidence = settled
    assert phase_receipt["commercial_settlement_complete"] is True
    for row in bundles.values():
        commercial = row.commercial_settlement
        assert commercial.settlement_state is CommercialSettlementState.SETTLED
        assert commercial.market_crystal_eligible is True
        assert commercial.world_settlement_digest == row.world_settlement.settlement_digest


def test_outcome_mapping_preserves_controlled_truth(settled):
    bundles, _evidence = settled
    assert bundles["verified_payment_without_acceptance"].commercial_settlement.outcome.value == "MIXED"
    assert bundles["operator_self_paid_acceptance"].commercial_settlement.outcome.value == "MIXED"
    assert bundles["independent_acceptance_without_payment"].commercial_settlement.outcome.value == "MIXED"
    assert bundles["independent_paid_acceptance_structural_gate"].commercial_settlement.outcome.value == "GAIN"


def test_controlled_fixture_never_promotes_real_commercial_claims(settled, phase_receipt):
    bundles, _evidence = settled
    for row in bundles.values():
        commercial = row.commercial_settlement
        assert commercial.verified_payment is EvidenceClaimState.UNPROVED
        assert commercial.customer_acceptance is EvidenceClaimState.UNPROVED
        assert commercial.willingness_to_pay is EvidenceClaimState.UNPROVED
        assert commercial.repeatability is EvidenceClaimState.UNPROVED
    assert phase_receipt["commercial_truth_promoted_from_controlled_fixture"] is False
    assert phase_receipt["real_market_evidence"] is False
    assert phase_receipt["real_payment_verified"] is False
    assert phase_receipt["real_customer_acceptance_observed"] is False
    assert phase_receipt["real_willingness_to_pay_proved"] is False
    assert phase_receipt["commercial_validation_proved"] is False
    assert phase_receipt["repeatability_proved"] is False


def test_structural_wtp_gate_is_preserved_without_becoming_real_wtp(settled, phase_receipt):
    bundles, evidence = settled
    row = bundles["independent_paid_acceptance_structural_gate"]
    assert evidence["parent"]["independent_paid_acceptance_structural_wtp_gate"] is True
    assert row.beast_market_crystal["real_market_evidence"] is False
    assert row.beast_market_crystal["willingness_to_pay_proved"] is False
    assert phase_receipt["structural_wtp_gate_preserved_without_real_wtp_claim"] is True


def test_market_crystals_bind_exact_lineage_and_both_settlements(settled, phase_receipt):
    bundles, _evidence = settled
    for row in bundles.values():
        crystal = row.beast_market_crystal
        assert crystal["lineage_truth_digest"] == row.lineage_truth_digest
        assert crystal["commercial_settlement_digest"] == row.commercial_settlement.settlement_digest
        assert crystal["world_settlement_digest"] == row.world_settlement.settlement_digest
    assert phase_receipt["lineage_truth_bound_to_crystals"] is True
    assert phase_receipt["commercial_and_world_settlement_bound_to_crystals"] is True


def test_beast_market_crystal_chain_is_valid_and_append_only(settled, phase_receipt):
    bundles, _evidence = settled
    counts = [row.beast_market_crystal["crystal_chain_block_count"] for row in bundles.values()]
    assert sorted(counts) == [1, 2, 3, 4]
    assert all(row.beast_market_crystal["crystal_chain_valid"] is True for row in bundles.values())
    assert phase_receipt["market_crystal_created"] is True
    assert phase_receipt["market_crystal_count"] == 4
    assert phase_receipt["market_crystal_final_block_count"] == 4


def test_beast_market_learning_remains_evidence_only(settled, phase_receipt):
    bundles, _evidence = settled
    assert all(row.beast_market_crystal["authority"] == "evidence_only" for row in bundles.values())
    assert all(row.beast_market_crystal["direct_learning_to_execution"] is False for row in bundles.values())
    assert phase_receipt["all_market_crystals_evidence_only"] is True
    assert phase_receipt["direct_learning_to_execution"] is False


def test_customer_and_payment_lineage_are_bound_but_not_collapsed(settled):
    bundles, _evidence = settled
    for row in bundles.values():
        commercial = row.commercial_settlement
        assert commercial.customer_lineage_digest is not None
        assert commercial.payment_lineage_digest is not None
        assert commercial.customer_lineage_digest != commercial.payment_lineage_digest


def test_crystallisation_refuses_non_settled_commercial_evidence(settled, tmp_path):
    bundles, _evidence = settled
    row = bundles["verified_payment_without_acceptance"]
    hostile = replace(row.commercial_settlement, settlement_state=CommercialSettlementState.PARTIAL)
    with pytest.raises(CommercialCrystallisationError):
        crystallize_commercial_settlement(
            REPO_ROOT,
            commercial_settlement=hostile,
            world_settlement=row.world_settlement,
            scenario_id=row.scenario_id,
            lineage_truth_digest=row.lineage_truth_digest,
            structural_wtp_gate_satisfied=False,
            state_root=tmp_path / "commercial_partial",
        )


def test_crystallisation_refuses_fractured_world_settlement(settled, tmp_path):
    bundles, _evidence = settled
    row = bundles["verified_payment_without_acceptance"]
    hostile_world = replace(row.world_settlement, settlement_state=SettlementState.FRACTURED)
    with pytest.raises(CommercialCrystallisationError):
        crystallize_commercial_settlement(
            REPO_ROOT,
            commercial_settlement=row.commercial_settlement,
            world_settlement=hostile_world,
            scenario_id=row.scenario_id,
            lineage_truth_digest=row.lineage_truth_digest,
            structural_wtp_gate_satisfied=False,
            state_root=tmp_path / "world_fractured",
        )


def test_crystallisation_refuses_world_settlement_lineage_mismatch(settled, tmp_path):
    bundles, _evidence = settled
    row = bundles["verified_payment_without_acceptance"]
    hostile = replace(
        row.commercial_settlement,
        world_settlement_digest="sha256:" + "a" * 64,
    )
    with pytest.raises(CommercialCrystallisationError):
        crystallize_commercial_settlement(
            REPO_ROOT,
            commercial_settlement=hostile,
            world_settlement=row.world_settlement,
            scenario_id=row.scenario_id,
            lineage_truth_digest=row.lineage_truth_digest,
            structural_wtp_gate_satisfied=False,
            state_root=tmp_path / "lineage_mismatch",
        )


def test_settlement_bundle_refuses_real_market_upgrade(settled):
    bundles, _evidence = settled
    row = bundles["independent_paid_acceptance_structural_gate"]
    with pytest.raises(ValueError):
        replace(row, real_market_evidence=True)


def test_no_response_or_negative_market_truth_is_not_invented_by_phase7(phase_receipt):
    assert phase_receipt["evidence_scope"] == "controlled_fixture"
    assert phase_receipt["commercial_truth_promoted_from_controlled_fixture"] is False


def test_market_crystal_does_not_mint_release_or_execution_authority(phase_receipt):
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["direct_learning_to_execution"] is False


def test_phase7_creates_no_new_runtime_engine_and_does_not_finish_m2(phase_receipt):
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
