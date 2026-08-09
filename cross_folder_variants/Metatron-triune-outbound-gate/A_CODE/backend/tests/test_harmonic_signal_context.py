from types import SimpleNamespace

from backend.services.harmonic_engine import HarmonicEngine
from backend.services.harmonic_signal_context import build_harmonic_signal_context
from backend.services.resonance_service import get_resonance_service


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs


def test_build_harmonic_signal_context_combines_world_aatl_and_vns():
    fake_db = SimpleNamespace(
        world_entities=_FakeCollection(
            [
                {
                    "id": "admin_guardian",
                    "attributes": {
                        "risk_score": 0.8,
                        "graph_centrality": 0.6,
                        "privilege_escalation_likelihood": 0.5,
                        "trust_state": "degraded",
                    },
                }
            ]
        ),
        deception_events=_FakeCollection([]),
    )
    signal = build_harmonic_signal_context(
        db=fake_db,
        actor_id="admin_guardian",
        tool_name="control_console",
        target_domain="prod",
        environment="prod",
        operation="console_review",
        context={
            "aatl_assessment": {
                "actor_type": "autonomous_agent",
                "machine_plausibility": 0.84,
                "threat_score": 78,
                "intent_accumulation": {"goal_convergence_score": 0.73},
                "lifecycle_stage": "lateral_movement",
            },
            "vns_assessment": {
                "suspicious_flows": 6,
                "total_flows": 10,
                "beacon_confidence": 0.72,
            },
        },
    )

    assert signal["world_graph_pressure"] >= 0.4
    assert signal["aatl_pressure"] >= 0.73
    assert signal["vns_pressure"] >= 0.6
    assert signal["composite_context_pressure"] >= 0.55


def test_build_harmonic_signal_context_includes_deception_outcomes():
    fake_db = SimpleNamespace(
        world_entities=_FakeCollection([]),
        deception_events=_FakeCollection(
            [
                {"session_id": "sess-1", "campaign_id": "camp-1", "event_type": "decoy_interaction", "details": {}},
                {"session_id": "sess-1", "campaign_id": "camp-1", "event_type": "maze_traversal", "details": {"false_branch_commitment": True}},
                {"session_id": "sess-1", "campaign_id": "camp-1", "event_type": "contradiction_probe", "details": {}},
                {"session_id": "sess-1", "campaign_id": "camp-1", "event_type": "context_burn", "details": {}},
            ]
        ),
    )
    signal = build_harmonic_signal_context(
        db=fake_db,
        actor_id="svc_recon",
        tool_name="network_probe",
        target_domain="prod",
        environment="prod",
        operation="enumerate_targets",
        context={"session_id": "sess-1", "campaign_id": "camp-1"},
    )
    assert signal["deception_decoy_touches"] == 1
    assert signal["deception_branch_persistence"] > 0.0
    assert signal["deception_false_branch_commitment"] > 0.0
    assert signal["deception_contradiction_pressure"] > 0.0
    assert signal["deception_context_burn_tolerance"] > 0.0
    assert signal["deception_pressure"] > 0.0


def test_harmonic_engine_uses_signal_context_to_raise_discord_and_rationale():
    get_resonance_service().reset()
    engine = HarmonicEngine(
        db=SimpleNamespace(
            world_entities=_FakeCollection(
                [
                    {
                        "id": "svc_recon",
                        "attributes": {
                            "risk_score": 0.9,
                            "graph_centrality": 0.7,
                            "privilege_escalation_likelihood": 0.8,
                            "trust_state": "degraded",
                        },
                    }
                ]
            ),
            deception_events=_FakeCollection([]),
        ),
        window_size=64,
    )
    for i in range(10):
        engine.score_observation(
            actor_id="svc_recon",
            tool_name="network_probe",
            target_domain="prod",
            environment="prod",
            stage="exec",
            timestamp_ms=1000.0 + (i * 200.0),
            operation="enumerate_targets",
            context={"automation": True, "learn_baseline": True},
        )

    baseline = engine.score_observation(
        actor_id="svc_recon",
        tool_name="network_probe",
        target_domain="prod",
        environment="prod",
        stage="exec",
        timestamp_ms=3200.0,
        operation="enumerate_targets",
        context={"automation": True, "learn_baseline": False},
    )
    enriched = engine.score_observation(
        actor_id="svc_recon",
        tool_name="network_probe",
        target_domain="prod",
        environment="prod",
        stage="exec",
        timestamp_ms=3400.0,
        operation="enumerate_targets",
        context={
            "automation": True,
            "learn_baseline": False,
            "aatl_assessment": {
                "actor_type": "autonomous_agent",
                "machine_plausibility": 0.88,
                "threat_score": 81,
                "intent_accumulation": {"goal_convergence_score": 0.75},
                "lifecycle_stage": "reconnaissance",
            },
            "vns_assessment": {
                "suspicious_flows": 5,
                "total_flows": 8,
                "beacon_confidence": 0.68,
            },
        },
    )

    baseline_state = baseline["harmonic_state"]
    enriched_state = enriched["harmonic_state"]
    assert enriched["signal_context"]["composite_context_pressure"] > 0.5
    assert enriched_state["discord_score"] > baseline_state["discord_score"]
    assert enriched_state["confidence"] < baseline_state["confidence"]
    assert any("world-graph pressure elevated" in reason for reason in enriched_state["rationale"])
    assert any("AATL pressure elevated" in reason for reason in enriched_state["rationale"])
    assert any("VNS pressure elevated" in reason for reason in enriched_state["rationale"])


def test_harmonic_engine_uses_deception_outcomes_to_raise_context_pressure():
    get_resonance_service().reset()
    engine = HarmonicEngine(
        db=SimpleNamespace(
            world_entities=_FakeCollection([]),
            deception_events=_FakeCollection(
                [
                    {"session_id": "sess-2", "campaign_id": "camp-2", "event_type": "decoy_interaction", "details": {}},
                    {"session_id": "sess-2", "campaign_id": "camp-2", "event_type": "maze_traversal", "details": {"false_branch_commitment": True}},
                    {"session_id": "sess-2", "campaign_id": "camp-2", "event_type": "contradiction_probe", "details": {}},
                ]
            ),
        ),
        window_size=64,
    )
    for i in range(8):
        engine.score_observation(
            actor_id="svc_probe",
            tool_name="deception_router",
            target_domain="deception",
            environment="prod",
            stage="exec",
            timestamp_ms=1000.0 + (i * 200.0),
            operation="mirror_world",
            context={"learn_baseline": True, "session_id": "sess-2", "campaign_id": "camp-2"},
        )
    result = engine.score_observation(
        actor_id="svc_probe",
        tool_name="deception_router",
        target_domain="deception",
        environment="prod",
        stage="exec",
        timestamp_ms=2800.0,
        operation="mirror_world",
        context={"learn_baseline": False, "session_id": "sess-2", "campaign_id": "camp-2"},
    )
    assert result["signal_context"]["deception_pressure"] > 0.2
    assert any("deception pressure elevated" in reason for reason in result["harmonic_state"]["rationale"])
