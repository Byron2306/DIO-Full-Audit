from pathlib import Path

import pytest

from commercial_metabolism.authority import (
    AuthorityDecision,
    CommercialAuthorityPreflight,
    CommercialEffect,
    EffectAuthorityDecision,
    M2_PHASE3_EXIT_TOKEN,
    build_reference_authority_preflight,
    evaluate_non_authority_influences,
    phase3_authority_receipt,
)
from commercial_metabolism.contracts import ChannelAccessState


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase_receipt():
    return phase3_authority_receipt(REPO_ROOT)


@pytest.fixture(scope="module")
def reference_preflight(tmp_path_factory):
    return build_reference_authority_preflight(
        REPO_ROOT,
        work_root=tmp_path_factory.mktemp("m2_phase3_authority"),
    )


def test_m2_phase3_gate_passes(phase_receipt):
    assert phase_receipt["passed"] is True, phase_receipt
    assert phase_receipt["acceptance"] == M2_PHASE3_EXIT_TOKEN
    assert phase_receipt["phase"] == "M2-3"


def test_phase3_requires_verified_m2_phase2_parent(phase_receipt):
    assert phase_receipt["parent_acceptance"] == "DIO_M2_LINGUA_COMMERCIAL_PROJECTION_READY"
    assert phase_receipt["parent_verified"] is True


def test_reference_channel_is_draft_only_but_can_describe_publish_capability(reference_preflight):
    preflight, channel, _anchors = reference_preflight
    assert channel.access_state == ChannelAccessState.DRAFT_ONLY
    assert channel.read_capability_present is True
    assert channel.draft_capability_present is True
    assert channel.publish_capability_present is True
    assert channel.authority_created is False
    assert preflight.any_effect_allowed is False


def test_seraph_is_canonical_external_effect_authority_owner(reference_preflight, phase_receipt):
    preflight, _channel, anchors = reference_preflight
    assert phase_receipt["seraph_owns_external_effect_authority"] is True
    assert anchors["checks"]["seraph_gate_action_present"] is True
    assert anchors["checks"]["seraph_world_state_bound"] is True
    assert anchors["checks"]["seraph_vns_bound"] is True
    assert anchors["checks"]["seraph_arda_bound"] is True
    assert preflight.seraph_anchor_digest.startswith("sha256:")


def test_market_command_remains_planning_not_authority(reference_preflight, phase_receipt):
    _preflight, _channel, anchors = reference_preflight
    assert anchors["checks"]["market_command_automatic_spend_off"] is True
    assert anchors["checks"]["market_command_publication_approval_required"] is True
    assert phase_receipt["market_command_release_is_egress_authority"] is False


def test_vesper_remains_draft_only_customer_interface(reference_preflight):
    preflight, _channel, anchors = reference_preflight
    assert anchors["checks"]["vesper_draft_only"] is True
    assert anchors["checks"]["vesper_send_authorized_false"] is True
    assert anchors["checks"]["vesper_sent_false"] is True
    assert preflight.vesper_draft_only is True


def test_authority_plane_preserves_evidence_and_legalis_boundaries(reference_preflight, phase_receipt):
    _preflight, _channel, anchors = reference_preflight
    assert anchors["checks"]["authority_plane_evidence_not_authority"] is True
    assert anchors["checks"]["authority_plane_legalis_not_execution_authority"] is True
    assert anchors["checks"]["authority_plane_capability_lease_not_self_authorizing"] is True
    assert phase_receipt["legalis_allow_is_release_authority"] is False


def test_safe_claim_language_does_not_authorize_publish_or_send(reference_preflight, phase_receipt):
    preflight, _channel, _anchors = reference_preflight
    assert preflight.claim_language_safe is True
    assert preflight.decision_for(CommercialEffect.PUBLISH).decision == AuthorityDecision.REFUSE
    assert preflight.decision_for(CommercialEffect.SEND).decision == AuthorityDecision.REFUSE
    assert phase_receipt["safe_claim_is_release_authority"] is False


def test_conversion_does_not_authorize_spend(reference_preflight, phase_receipt):
    preflight, _channel, _anchors = reference_preflight
    result = evaluate_non_authority_influences(preflight, conversion_observed=True)
    assert result["decisions_unchanged"]["SPEND"] == "REFUSE"
    assert result["any_effect_allowed"] is False
    assert phase_receipt["conversion_is_spend_authority"] is False


def test_verified_payment_does_not_authorize_delivery(reference_preflight, phase_receipt):
    preflight, _channel, _anchors = reference_preflight
    result = evaluate_non_authority_influences(preflight, verified_payment=True)
    assert result["decisions_unchanged"]["DELIVER"] == "REFUSE"
    assert phase_receipt["payment_is_delivery_authority"] is False


def test_customer_acceptance_does_not_widen_product_or_egress_authority(reference_preflight, phase_receipt):
    preflight, _channel, _anchors = reference_preflight
    result = evaluate_non_authority_influences(preflight, customer_acceptance=True)
    assert result["any_effect_allowed"] is False
    assert result["authority_widened"] is False
    assert phase_receipt["acceptance_is_product_authority"] is False


def test_all_non_authority_influences_together_still_cannot_authorize(reference_preflight):
    preflight, _channel, _anchors = reference_preflight
    result = evaluate_non_authority_influences(
        preflight,
        claim_language_safe=True,
        conversion_observed=True,
        verified_payment=True,
        customer_acceptance=True,
        market_command_release_state=True,
        legalis_allow=True,
        beast_market_crystal=True,
        harmonic_normal_flow=True,
    )
    assert all(value == "REFUSE" for value in result["decisions_unchanged"].values())
    assert result["any_effect_allowed"] is False
    assert result["authority_created"] is False
    assert result["external_effects"] is False


def test_effect_authority_slots_are_complete_unique_and_separate(reference_preflight, phase_receipt):
    preflight, _channel, _anchors = reference_preflight
    effects = [row.effect for row in preflight.decisions]
    assert len(effects) == len(CommercialEffect) == 6
    assert len(set(effects)) == 6
    assert phase_receipt["effect_authority_slots_separate"] is True
    assert set(phase_receipt["effect_decisions"]) == {row.value for row in CommercialEffect}


def test_allow_cannot_be_fabricated_without_external_authority_receipt():
    with pytest.raises(ValueError):
        EffectAuthorityDecision(
            effect=CommercialEffect.SEND,
            owner="Seraph",
            decision=AuthorityDecision.ALLOW,
            reason="attempted fabricated allow",
            authority_ref=None,
        )


def test_non_seraph_external_effect_owner_is_rejected():
    with pytest.raises(ValueError):
        EffectAuthorityDecision(
            effect=CommercialEffect.SEND,
            owner="Market Command",
            decision=AuthorityDecision.REFUSE,
            reason="wrong owner",
        )


def test_preflight_is_deterministic_and_does_not_execute_seraph(reference_preflight, tmp_path):
    first, _channel, _anchors = reference_preflight
    second, _channel2, _anchors2 = build_reference_authority_preflight(
        REPO_ROOT,
        work_root=tmp_path / "second",
    )
    assert first.preflight_digest == second.preflight_digest
    assert first.seraph_operational_gate_executed is False
    assert second.seraph_operational_gate_executed is False
    assert first.authority_created is False
    assert first.external_effects is False


def test_phase3_creates_no_runtime_or_external_effect(phase_receipt):
    assert phase_receipt["authority_schema_valid"] is True
    assert phase_receipt["all_external_effects_refused"] is True
    assert phase_receipt["seraph_operational_gate_executed"] is False
    assert phase_receipt["authority_created"] is False
    assert phase_receipt["authority_widened"] is False
    assert phase_receipt["external_effects"] is False
    assert phase_receipt["new_runtime_engine_created"] is False
    assert phase_receipt["m2_final_verified"] is False
