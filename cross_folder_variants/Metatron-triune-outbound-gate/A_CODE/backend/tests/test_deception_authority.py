import pytest

from backend.services.deception_authority import DeceptionAuthorityService
from backend.services.deception_policy import evaluate_deception_escalation
from backend.schemas.deception_models import DeceptionConfidenceBand, DeceptionMode


async def _create_case(service: DeceptionAuthorityService, **kwargs):
    return await service.create_case(
        session_id=kwargs.get("session_id", "sess-1"),
        campaign_id=kwargs.get("campaign_id", "camp-1"),
        source_ip=kwargs.get("source_ip", "198.51.100.7"),
        path=kwargs.get("path", "/api/v1/users"),
        trigger_reason=kwargs.get("trigger_reason", "test"),
        triggering_signals=kwargs.get("triggering_signals", ["machine_like_timing"]),
        desired_mode=kwargs.get("desired_mode", DeceptionMode.DISINFORMATION),
        risk_score=kwargs.get("risk_score", 80),
        headers=kwargs.get("headers", {}),
        behavior_flags=kwargs.get("behavior_flags", {}),
        evidence_refs=kwargs.get("evidence_refs", []),
        harmonic_state=kwargs.get("harmonic_state"),
    )


@pytest.mark.asyncio
async def test_trusted_principal_is_downgraded_to_observe():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        headers={"x-seraph-trusted": "true"},
        behavior_flags={"human_admin": True, "machine_plausibility": 0.95},
    )
    assert case.trusted_principal_blocked is True
    assert case.deception_mode == DeceptionMode.OBSERVE
    assert validation.allowed is False
    assert "trusted_principal_blocked" in validation.reasons


@pytest.mark.asyncio
async def test_low_confidence_active_deception_downgrades_to_friction():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.DISINFORMATION,
        behavior_flags={"machine_plausibility": 0.18, "agenticity_score": 0.21},
    )
    assert case.deception_mode == DeceptionMode.FRICTION
    assert validation.allowed is False
    assert "insufficient_confidence_for_active_deception" in validation.reasons


def test_payload_validator_rejects_internal_inventory_and_real_secret_patterns():
    service = DeceptionAuthorityService()
    payload = {
        "_seraph_synthetic": True,
        "status": "ok",
        "data": {
            "host": "vault.corp.internal",
            "token": "AKIAABCDEFGHIJKLMNOP",
        },
    }
    result = service.validate_payload(payload)
    assert result.allowed is False
    assert result.downgraded_mode == DeceptionMode.FRICTION
    assert any("secret_pattern" in item for item in result.collisions)
    assert any("host_pattern" in item for item in result.collisions)


def test_payload_validator_requires_synthetic_marker_and_blocks_real_paths():
    service = DeceptionAuthorityService()
    payload = {
        "status": "ok",
        "data": {
            "path": "/etc/kubernetes/admin.conf",
            "schema": {"openapi": "3.1.0"},
        },
    }
    result = service.validate_payload(payload)
    assert result.allowed is False
    assert any("synthetic_marker:missing" == item for item in result.collisions)
    assert any("path_pattern" in item for item in result.collisions)
    assert any("schema_pattern" in item for item in result.collisions)


@pytest.mark.asyncio
async def test_harmonic_governance_veto_blocks_active_deception():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        behavior_flags={"machine_plausibility": 0.91, "agenticity_score": 0.88},
        harmonic_state={
            "discord_score": 0.91,
            "resonance_score": 0.12,
            "confidence": 0.82,
        },
    )
    assert case.deception_mode == DeceptionMode.OBSERVE
    assert validation.allowed is False
    assert "governance_veto" in validation.reasons
    assert "harmonic_discord_critical" in validation.reasons
    assert case.execution_notes["harmonic_band"] == "severe_discord"


@pytest.mark.asyncio
async def test_harmonic_low_confidence_forces_observation_only():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.DISINFORMATION,
        behavior_flags={"machine_plausibility": 0.72, "agenticity_score": 0.69},
        harmonic_state={
            "discord_score": 0.52,
            "resonance_score": 0.42,
            "confidence": 0.31,
        },
    )
    assert case.deception_mode == DeceptionMode.OBSERVE
    assert validation.allowed is False
    assert "harmonic_low_confidence_blocks_aggressive_synthetic_content" in validation.reasons


@pytest.mark.asyncio
async def test_moderate_discord_caps_mirror_world_to_disinformation():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        behavior_flags={"machine_plausibility": 0.76, "agenticity_score": 0.71},
        triggering_signals=[
            "route_decision:mirror_world",
            "decoy_touched",
            "logic_budget_force_trap",
        ],
        harmonic_state={
            "discord_score": 0.67,
            "resonance_score": 0.33,
            "confidence": 0.62,
        },
    )
    assert case.deception_mode == DeceptionMode.DISINFORMATION
    assert validation.allowed is False
    assert "moderate_discord_caps_deception_below_mirror_world" in validation.reasons


@pytest.mark.asyncio
async def test_severe_discord_with_high_autonomy_confidence_allows_mirror_world():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        behavior_flags={
            "machine_plausibility": 0.91,
            "agenticity_score": 0.88,
            "decoy_touched": True,
            "aatl_actor_type": "autonomous_ai",
            "vns_suspicious_flows": 4,
        },
        triggering_signals=[
            "route_decision:mirror_world",
            "decoy_touched",
            "logic_budget_force_trap",
            "aatl_autonomous_operator",
            "vns_beacon_pattern_detected",
        ],
        harmonic_state={
            "discord_score": 0.83,
            "resonance_score": 0.28,
            "confidence": 0.72,
        },
    )
    assert case.deception_mode == DeceptionMode.MIRROR_WORLD
    assert validation.allowed is True
    assert "severe_discord_plus_high_autonomy_confidence_mirror_world_eligible" in case.execution_notes["harmonic_shape_reasons"]


@pytest.mark.asyncio
async def test_mirror_world_requires_independent_corroboration():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        behavior_flags={"machine_plausibility": 0.93, "agenticity_score": 0.91, "decoy_touched": True},
        triggering_signals=[
            "route_decision:mirror_world",
            "decoy_touched",
            "logic_budget_force_trap",
        ],
        harmonic_state={
            "discord_score": 0.82,
            "resonance_score": 0.24,
            "confidence": 0.73,
        },
    )
    assert case.deception_mode == DeceptionMode.DISINFORMATION
    assert validation.allowed is False
    assert "anti_feedback_loop_guard_triggered" in validation.reasons
    assert "independent_corroboration_required_for_high_impact_deception" in validation.reasons
    assert case.execution_notes["independent_corroboration"]["satisfied"] is False


@pytest.mark.asyncio
async def test_mirror_world_allowed_with_aatl_vns_and_governance_corroboration():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        behavior_flags={
            "machine_plausibility": 0.94,
            "agenticity_score": 0.92,
            "decoy_touched": True,
            "aatl_actor_type": "autonomous_ai",
            "vns_suspicious_flows": 6,
            "notation_token_present": True,
        },
        triggering_signals=[
            "route_decision:mirror_world",
            "decoy_touched",
            "logic_budget_force_trap",
            "aatl_autonomous_operator",
            "vns_beacon_pattern_detected",
            "world_state_hash_mismatch",
        ],
        harmonic_state={
            "discord_score": 0.84,
            "resonance_score": 0.21,
            "confidence": 0.77,
        },
    )
    assert case.deception_mode == DeceptionMode.MIRROR_WORLD
    assert validation.allowed is True
    corroboration = case.execution_notes["independent_corroboration"]
    assert corroboration["satisfied"] is True
    assert "aatl" in corroboration["sources"]
    assert "vns" in corroboration["sources"]
    assert "governance_evidence" in corroboration["sources"]


def test_policy_matrix_blocks_active_deception_when_confidence_is_below_minimum():
    decision = evaluate_deception_escalation(
        desired_mode=DeceptionMode.DISINFORMATION,
        confidence_band=DeceptionConfidenceBand.LOW,
        triggering_signals=["route_decision:disinformation", "machine_like_timing"],
        trusted_principal_blocked=False,
        harmonic_veto=False,
    )
    assert decision["transition_allowed"] is False
    assert decision["approved_mode"] == DeceptionMode.FRICTION
    assert "minimum_confidence_not_met" in decision["denial_reasons"]


@pytest.mark.asyncio
async def test_case_records_policy_bound_escalation_metadata():
    service = DeceptionAuthorityService()
    case, validation = await _create_case(
        service,
        desired_mode=DeceptionMode.MIRROR_WORLD,
        behavior_flags={
            "machine_plausibility": 0.92,
            "agenticity_score": 0.91,
            "decoy_touched": True,
            "aatl_actor_type": "autonomous_ai",
            "notation_token_present": True,
        },
        triggering_signals=[
            "route_decision:mirror_world",
            "decoy_touched",
            "logic_budget_force_trap",
            "aatl_autonomous_operator",
            "world_state_hash_mismatch",
        ],
    )
    assert validation.allowed is True
    policy = case.execution_notes["policy_decision"]["policy"]
    assert case.deception_mode == DeceptionMode.MIRROR_WORLD
    assert policy["minimum_confidence"] == "high"
    assert "rollback_rule" in policy
    assert "approval_requirement" in policy
    assert "audit_requirement" in policy
