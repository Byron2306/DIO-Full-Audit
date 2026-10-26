from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from commercial_metabolism.projection import (
    CommercialClaimState,
    M2_PHASE2_EXIT_TOKEN,
    build_commercial_projection,
    build_reference_commercial_context,
    evaluate_buyer_draft,
    phase2_projection_receipt,
)
from products.funding_proposal_studio import build_funding_proposal_metamorphic_unit


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = datetime(2026, 8, 19, 0, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def phase_receipt():
    return phase2_projection_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def reference_projection(tmp_path_factory):
    context = build_reference_commercial_context(REPO_ROOT, now=FIXED_NOW)
    work_root = tmp_path_factory.mktemp("m2_phase2_projection")
    projection, offer, registration = build_commercial_projection(
        REPO_ROOT,
        context=context,
        work_root=work_root,
    )
    return context, projection, offer, registration


def test_m2_phase2_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE2_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-2"


def test_m2_phase2_requires_verified_contract_parent_and_m1(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_COMMERCIAL_CONTRACTS_READY"
    assert phase_receipt["parent_verified"] is True
    assert phase_receipt["m1_parent_acceptance"] == "DIO_METAMORPHIC_SPINE_M1_VERIFIED"
    assert phase_receipt["m1_parent_verified"] is True


def test_m2_phase2_reuses_lingua_and_validates_projection_schema(phase_receipt):
    assert phase_receipt["lingua_existing_organ_reused"] is True
    assert phase_receipt["projection_schema_valid"] is True
    assert phase_receipt["semantic_object_id"].startswith("M2P2-")
    assert phase_receipt["lingua_source_document_hash"].startswith("sha256:")


def test_reference_projection_preserves_verified_product_identity(reference_projection):
    context, projection, offer, registration = reference_projection
    unit = build_funding_proposal_metamorphic_unit(REPO_ROOT)
    assert context.product_id == unit.unit_id == "funding_proposal_studio"
    assert context.metamorphic_unit_digest == projection.unit_digest == unit.unit_digest
    assert offer.product_id == unit.unit_id
    assert registration["schema"] == "dio.lingua.product_registration_receipt.v1"


def test_supported_claims_are_only_source_bound_m1_truth(reference_projection):
    _, projection, _, _ = reference_projection
    supported = {row.claim_id for row in projection.supported_claims}
    assert {
        "capability.controlled_pack",
        "proof.governed_composition",
        "proof.settled_crystal",
        "proof.same_identity",
        "proof.controlled_artifact_reference",
    } <= supported
    assert all(row.allowed_in_buyer_copy for row in projection.supported_claims)


def test_m3_substantive_content_dataflow_remains_unproved(reference_projection, phase_receipt):
    _, projection, _, _ = reference_projection
    claim = next(row for row in projection.claims if row.claim_id == "proof.substantive_content_dataflow")
    assert phase_receipt["content_transform_dataflow_proved"] is False
    assert claim.state == CommercialClaimState.HELD_UNPROVED
    assert claim.allowed_in_buyer_copy is False


def test_market_success_claims_remain_held_before_observation(reference_projection, phase_receipt):
    _, projection, _, _ = reference_projection
    held = {row.claim_id for row in projection.held_claims}
    assert {
        "market.demand",
        "market.customer_acceptance",
        "market.willingness_to_pay",
        "market.commercial_validation",
        "market.repeatability",
        "market.roi",
    } <= held
    assert phase_receipt["market_response_observed"] is False
    assert phase_receipt["payment_verified"] is False
    assert phase_receipt["customer_acceptance_observed"] is False


def test_constitutional_authority_and_outcome_claims_are_refused(reference_projection):
    _, projection, _, _ = reference_projection
    refused = {row.claim_id for row in projection.refused_claims}
    assert {
        "prohibition.guaranteed_outcome",
        "prohibition.automatic_submission",
        "prohibition.external_authority",
        "prohibition.success_mints_authority",
    } <= refused
    assert all(row.allowed_in_buyer_copy is False for row in projection.refused_claims)


def test_safe_source_bound_reference_copy_passes_configured_guard(reference_projection):
    _, projection, _, _ = reference_projection
    result = evaluate_buyer_draft(
        REPO_ROOT,
        projection=projection,
        draft_text=(
            "Funding Proposal Studio prepares a controlled funding proposal pack. "
            "It is a governed metamorphic composition with one governed identity."
        ),
    )
    assert result["safe_by_configured_guard"] is True
    assert result["blocked_claims"] == []
    assert result["release_authority_created"] is False


def test_guaranteed_funding_claim_is_blocked(reference_projection):
    _, projection, _, _ = reference_projection
    result = evaluate_buyer_draft(
        REPO_ROOT,
        projection=projection,
        draft_text="Guaranteed funding approval with Funding Proposal Studio.",
    )
    assert result["safe_by_configured_guard"] is False
    assert "prohibition.guaranteed_outcome" in result["blocked_claims"]


def test_unproved_wtp_and_commercial_validation_are_blocked(reference_projection):
    _, projection, _, _ = reference_projection
    result = evaluate_buyer_draft(
        REPO_ROOT,
        projection=projection,
        draft_text="Proven willingness to pay means Funding Proposal Studio is commercially validated.",
    )
    assert result["safe_by_configured_guard"] is False
    assert "market.willingness_to_pay" in result["blocked_claims"]
    assert "market.commercial_validation" in result["blocked_claims"]


def test_automatic_submission_claim_is_blocked(reference_projection):
    _, projection, _, _ = reference_projection
    result = evaluate_buyer_draft(
        REPO_ROOT,
        projection=projection,
        draft_text="We automatically submits and send the proposal on your behalf.",
    )
    assert result["safe_by_configured_guard"] is False
    assert "prohibition.automatic_submission" in result["blocked_claims"]


def test_unproved_substantive_dataflow_claim_is_blocked(reference_projection):
    _, projection, _, _ = reference_projection
    result = evaluate_buyer_draft(
        REPO_ROOT,
        projection=projection,
        draft_text="End-to-end substantive dataflow is proven.",
    )
    assert result["safe_by_configured_guard"] is False
    assert "proof.substantive_content_dataflow" in result["blocked_claims"]


def test_projection_digest_is_deterministic_for_same_context(reference_projection, tmp_path):
    context, projection, _, _ = reference_projection
    second, _, _ = build_commercial_projection(
        REPO_ROOT,
        context=context,
        work_root=tmp_path / "second",
    )
    assert projection.projection_digest == second.projection_digest
    assert projection.lingua_source_document_hash == second.lingua_source_document_hash


def test_context_change_changes_projection_identity(reference_projection, tmp_path):
    context, projection, _, _ = reference_projection
    changed_context = replace(context, price_minor=context.price_minor + 1)
    changed_projection, _, _ = build_commercial_projection(
        REPO_ROOT,
        context=changed_context,
        work_root=tmp_path / "changed",
    )
    assert changed_context.context_digest != context.context_digest
    assert changed_projection.projection_digest != projection.projection_digest
    assert all(row.context_digest == changed_context.context_digest for row in changed_projection.claims)


def test_phase2_claim_guard_does_not_pretend_general_nlu_or_create_authority(phase_receipt, reference_projection):
    _, projection, _, _ = reference_projection
    assert phase_receipt["claim_extraction_mode"] == "source_bound_structured_claim_catalog_with_deterministic_phrase_guards"
    assert phase_receipt["deterministic_phrase_guard_only"] is True
    assert phase_receipt["autonomous_natural_language_claim_inference_claimed"] is False
    assert projection.autonomous_natural_language_claim_inference_claimed is False
    assert phase_receipt["release_authority_created"] is False
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
