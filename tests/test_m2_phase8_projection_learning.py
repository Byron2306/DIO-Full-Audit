from dataclasses import replace
from pathlib import Path

import pytest

from commercial_metabolism.learning import (
    M2_PHASE8_EXIT_TOKEN,
    exercise_projection_adaptation,
    phase8_projection_adaptation_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase_receipt():
    return phase8_projection_adaptation_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def adapted(tmp_path_factory):
    candidate, evidence = exercise_projection_adaptation(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("m2_phase8_adaptation"),
    )
    return candidate, evidence


def test_m2_phase8_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE8_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-8"


def test_phase8_requires_verified_m2_phase7_parent(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_COMMERCIAL_SETTLEMENT_READY"
    assert phase_receipt["parent_verified"] is True


def test_projection_adaptation_schema_is_present(phase_receipt):
    assert phase_receipt["projection_adaptation_schema_valid"] is True


def test_lingua_existing_organ_is_reused_for_candidate(phase_receipt, adapted):
    candidate, evidence = adapted
    assert phase_receipt["lingua_existing_organ_reused"] is True
    assert phase_receipt["lingua_projection_can_update"] is True
    assert evidence["lingua_receipt"]["schema"] == "dio.lingua.product_registration_receipt.v1"
    assert candidate.lingua_source_document_hash.startswith("sha256:")


def test_candidate_is_bound_to_exact_settled_commercial_context(phase_receipt, adapted):
    candidate, evidence = adapted
    assert candidate.context_digest == evidence["parent"]["context_digest"]
    assert phase_receipt["context_digest"].startswith("sha256:")


def test_market_truth_anchors_are_settled_semantic_anchors_not_block_hashes(phase_receipt, adapted):
    candidate, evidence = adapted
    assert len(candidate.market_truth_anchor_digests) == 4
    assert len(set(candidate.market_truth_anchor_digests)) == 4
    assert set(candidate.market_truth_anchor_digests) == set(evidence["truth_anchors"].values())
    assert phase_receipt["volatile_crystal_receipts_excluded_from_projection_identity"] is True


def test_all_market_claims_remain_held_unproved(phase_receipt, adapted):
    candidate, _evidence = adapted
    assert set(candidate.held_market_claim_ids) == {
        "market.demand",
        "market.customer_acceptance",
        "market.willingness_to_pay",
        "market.commercial_validation",
        "market.repeatability",
        "market.roi",
    }
    assert phase_receipt["held_market_claim_count"] == 6
    assert phase_receipt["market_claim_upgrade_performed"] is False


def test_controlled_gain_cannot_become_positive_reuse(phase_receipt, adapted):
    candidate, _evidence = adapted
    assert candidate.positive_reuse_state == "CONTROLLED_EVIDENCE_EXCLUDED_PENDING_REAL_EVIDENCE"
    assert candidate.reusable_credit_created is False
    assert phase_receipt["controlled_gain_positive_reuse_created"] is False


def test_positive_reuse_requires_future_operator_approval(phase_receipt, adapted):
    candidate, _evidence = adapted
    assert candidate.operator_approval_required is True
    assert candidate.operator_approval_recorded is False
    assert phase_receipt["operator_approval_required_for_positive_reuse"] is True
    assert phase_receipt["operator_approval_recorded"] is False


def test_negative_market_learning_reuses_beast_negative_capability_store(phase_receipt, adapted):
    _candidate, evidence = adapted
    records = evidence["negative_records"]
    assert phase_receipt["beast_negative_capability_store_reused"] is True
    assert len(records) == 2
    assert {row["scenario_id"] for row in records} == {
        "verified_payment_without_acceptance",
        "independent_acceptance_without_payment",
    }


def test_negative_market_learning_is_exact_context_bound(phase_receipt, adapted):
    candidate, evidence = adapted
    reference = evidence["projection"]["reference_context"]
    for row in evidence["negative_records"]:
        scope = row["scope"]
        assert scope["transform_type"] == candidate.context_digest
        assert scope["route"] == reference["channel_id"]
        assert scope["tool"] == reference["offer_id"]
        assert scope["model"] == candidate.product_id
        assert scope["provider"] == reference["buyer_segment_id"]
    assert phase_receipt["negative_learning_context_bound"] is True


def test_single_negative_observation_stays_observing(phase_receipt, adapted):
    _candidate, evidence = adapted
    assert evidence["negative_activation_threshold"] == 3
    assert all(row["failure_count"] == 1 for row in evidence["negative_records"])
    assert all(row["state"] == "observing" for row in evidence["negative_records"])
    assert phase_receipt["negative_pattern_activated_from_single_observation"] is False


def test_no_active_negative_pattern_exists_from_controlled_singletons(phase_receipt, adapted):
    _candidate, evidence = adapted
    assert evidence["active_negative_matches"] == []
    assert phase_receipt["active_negative_match_count"] == 0


def test_negative_learning_does_not_globally_invalidate_product(phase_receipt):
    assert phase_receipt["product_globally_invalidated"] is False
    assert phase_receipt["learning_doctrine_checks"]["negative_not_global_product_failure"] is True


def test_beast_capability_learning_ledger_records_candidates_only(phase_receipt, adapted):
    _candidate, evidence = adapted
    report = evidence["learning_report"]
    assert phase_receipt["beast_capability_learning_ledger_reused"] is True
    assert report["event_count"] == 4
    assert phase_receipt["beast_learning_event_count"] == 4
    assert all(row["authority"] == "evidence_only" for row in report["recent_events"])


def test_controlled_or_simulated_evidence_is_excluded_from_reusable_learning(phase_receipt):
    assert phase_receipt["controlled_or_simulated_evidence_excluded_from_reusable_learning"] is True
    assert phase_receipt["learning_doctrine_checks"]["simulated_demo_excluded_from_learning"] is True


def test_same_parent_produces_same_candidate_identity_and_lingua_source(adapted, tmp_path):
    candidate, evidence = adapted
    second, _second_evidence = exercise_projection_adaptation(
        REPO_ROOT,
        work_root=tmp_path / "second",
        parent_receipt=evidence["parent"],
    )
    assert second.candidate_digest == candidate.candidate_digest
    assert second.lingua_source_document_hash == candidate.lingua_source_document_hash
    assert second.market_truth_anchor_digests == candidate.market_truth_anchor_digests


def test_candidate_refuses_controlled_evidence_promotion(adapted):
    candidate, _evidence = adapted
    with pytest.raises(ValueError):
        replace(candidate, real_market_evidence=True)
    with pytest.raises(ValueError):
        replace(candidate, claim_upgrade_performed=True)
    with pytest.raises(ValueError):
        replace(candidate, reusable_credit_created=True)


def test_candidate_refuses_semantic_crystal_or_direct_execution(adapted):
    candidate, _evidence = adapted
    with pytest.raises(ValueError):
        replace(candidate, semantic_crystal_created=True)
    with pytest.raises(ValueError):
        replace(candidate, direct_learning_to_execution=True)


def test_phase8_preserves_truth_authority_and_programme_boundaries(phase_receipt):
    assert phase_receipt["real_market_evidence"] is False
    assert phase_receipt["real_payment_verified"] is False
    assert phase_receipt["real_customer_acceptance_observed"] is False
    assert phase_receipt["real_willingness_to_pay_proved"] is False
    assert phase_receipt["commercial_validation_proved"] is False
    assert phase_receipt["repeatability_proved"] is False
    assert phase_receipt["semantic_crystal_created"] is False
    assert phase_receipt["direct_learning_to_execution"] is False
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
