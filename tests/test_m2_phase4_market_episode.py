from dataclasses import replace
from pathlib import Path

import pytest

from commercial_metabolism.authority import phase3_authority_receipt
from commercial_metabolism.contracts import MarketObservationKind, PricingEvidenceState
from commercial_metabolism.episode import (
    M2_PHASE4_EXIT_TOKEN,
    MarketEpisodePlan,
    compile_reference_market_episode,
    phase4_market_episode_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase_receipt():
    return phase4_market_episode_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    parent = phase3_authority_receipt(REPO_ROOT)
    plan, pricing, observation, market = compile_reference_market_episode(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("m2_phase4_episode"),
        parent_receipt=parent,
    )
    return parent, plan, pricing, observation, market


def test_m2_phase4_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE4_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-4"


def test_phase4_requires_verified_phase3_parent(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_CHANNEL_AUTHORITY_SEPARATED"
    assert phase_receipt["parent_verified"] is True


def test_episode_binds_exact_phase3_context_and_authority(compiled):
    parent, plan, _pricing, _observation, _market = compiled
    assert plan.context_digest == parent["context_digest"]
    assert plan.projection_digest == parent["projection_digest"]
    assert plan.offer_state_digest == parent["offer_state_digest"]
    assert plan.channel_state_digest == parent["channel_state_digest"]
    assert plan.authority_preflight_digest == parent["preflight_digest"]


def test_market_episode_schema_and_identity_are_present(phase_receipt, compiled):
    _parent, plan, _pricing, _observation, _market = compiled
    assert phase_receipt["episode_schema_valid"] is True
    assert plan.schema == "dio.market_episode_plan.v1"
    assert plan.episode_id.startswith("episode:market:")
    assert plan.plan_digest.startswith("sha256:")


def test_pricing_hypothesis_is_bound_but_unexposed(compiled, phase_receipt):
    _parent, plan, pricing, _observation, _market = compiled
    assert pricing.context_digest == plan.context_digest
    assert pricing.pricing_state_digest == plan.pricing_state_digest
    assert pricing.evidence_state == PricingEvidenceState.UNTESTED
    assert pricing.exposure_count == 0
    assert pricing.verified_payment_count == 0
    assert pricing.accepted_customer_count == 0
    assert phase_receipt["pricing_evidence_state"] == "UNTESTED"


def test_market_command_existing_organ_materialises_only_draft_held(compiled, phase_receipt):
    _parent, _plan, _pricing, _observation, market = compiled
    campaign = market["campaign"]
    assert campaign["state"] == "draft"
    assert campaign["approval_state"] == "pending"
    assert campaign["publication_state"] == "held"
    assert phase_receipt["market_command_existing_organ_reused"] is True


def test_market_command_budget_and_automatic_spend_are_zero_off(compiled, phase_receipt):
    _parent, _plan, _pricing, _observation, market = compiled
    assert market["campaign"]["budget_cap_minor"] == 0
    assert market["policy"]["automatic_spend"] == "off"
    assert phase_receipt["market_command_budget_cap_minor"] == 0
    assert phase_receipt["market_command_automatic_spend"] == "off"


def test_market_command_lineage_binds_all_commercial_atoms(compiled, phase_receipt):
    parent, plan, pricing, observation, market = compiled
    lineage = market["campaign"]["governance"]["source_lineage"]
    assert lineage["context_digest"] == parent["context_digest"] == plan.context_digest
    assert lineage["projection_digest"] == plan.projection_digest
    assert lineage["offer_state_digest"] == plan.offer_state_digest
    assert lineage["channel_state_digest"] == plan.channel_state_digest
    assert lineage["preflight_digest"] == plan.authority_preflight_digest
    assert lineage["pricing_state_digest"] == pricing.pricing_state_digest
    assert lineage["observation_contract_digest"] == observation["observation_contract_digest"]
    assert phase_receipt["market_command_lineage_complete"] is True


def test_observation_contract_declares_complete_vocabulary(compiled, phase_receipt):
    _parent, plan, _pricing, observation, _market = compiled
    expected = {row.value for row in MarketObservationKind}
    assert set(observation["observation_kinds"]) == expected
    assert set(plan.observation_kinds) == expected
    assert phase_receipt["observation_kind_count"] == len(expected)


def test_no_response_requires_closed_measurement_window(compiled, phase_receipt):
    _parent, _plan, _pricing, observation, _market = compiled
    assert observation["no_response_requires_closed_window"] is True
    assert "only be recorded after" in observation["silence_rule"]
    assert phase_receipt["no_response_requires_closed_window"] is True


def test_phase4_does_not_fabricate_market_response(compiled, phase_receipt):
    _parent, plan, _pricing, observation, _market = compiled
    assert observation["market_response_observed"] is False
    assert observation["fabricated_observations_allowed"] is False
    assert plan.market_response_observed is False
    assert phase_receipt["market_response_observed"] is False


def test_phase4_does_not_claim_payment_acceptance_wtp_or_validation(phase_receipt):
    assert phase_receipt["payment_observed"] is False
    assert phase_receipt["customer_acceptance_observed"] is False
    assert phase_receipt["willingness_to_pay_proved"] is False
    assert phase_receipt["commercial_validation_proved"] is False
    assert phase_receipt["repeatability_proved"] is False


def test_episode_is_held_for_authority_and_never_activated(compiled, phase_receipt):
    parent, plan, _pricing, _observation, _market = compiled
    assert parent["all_external_effects_refused"] is True
    assert plan.release_state == "HELD_FOR_AUTHORITY"
    assert plan.activation_performed is False
    assert plan.seraph_operational_gate_executed is False
    assert phase_receipt["activation_performed"] is False
    assert phase_receipt["seraph_operational_gate_executed"] is False


def test_market_episode_plan_digest_is_deterministic_for_exact_same_atoms(compiled):
    _parent, plan, _pricing, _observation, _market = compiled
    twin = MarketEpisodePlan(
        episode_id=plan.episode_id,
        product_id=plan.product_id,
        context_digest=plan.context_digest,
        projection_digest=plan.projection_digest,
        offer_state_digest=plan.offer_state_digest,
        channel_state_digest=plan.channel_state_digest,
        pricing_state_digest=plan.pricing_state_digest,
        authority_preflight_digest=plan.authority_preflight_digest,
        market_command_plan_digest=plan.market_command_plan_digest,
        observation_contract_digest=plan.observation_contract_digest,
        campaign_id=plan.campaign_id,
        buyer_segment_id=plan.buyer_segment_id,
        channel_id=plan.channel_id,
        offer_id=plan.offer_id,
        currency=plan.currency,
        price_minor=plan.price_minor,
        measurement_window_seconds=plan.measurement_window_seconds,
        release_state=plan.release_state,
        observation_kinds=plan.observation_kinds,
    )
    assert twin.plan_digest == plan.plan_digest


def test_market_episode_refuses_fabricated_response_state(compiled):
    _parent, plan, _pricing, _observation, _market = compiled
    with pytest.raises(ValueError):
        replace(plan, market_response_observed=True)


def test_market_episode_refuses_activation_or_seraph_execution(compiled):
    _parent, plan, _pricing, _observation, _market = compiled
    with pytest.raises(ValueError):
        replace(plan, activation_performed=True)
    with pytest.raises(ValueError):
        replace(plan, seraph_operational_gate_executed=True)


def test_market_episode_refuses_incomplete_observation_vocabulary(compiled):
    _parent, plan, _pricing, _observation, _market = compiled
    with pytest.raises(ValueError):
        replace(plan, observation_kinds=(MarketObservationKind.IMPRESSION.value,))


def test_phase4_creates_no_authority_external_effect_or_new_runtime(phase_receipt, compiled):
    _parent, plan, _pricing, _observation, _market = compiled
    assert plan.authority_created is False
    assert plan.external_effects is False
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
