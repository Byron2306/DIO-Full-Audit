from backend.services.harmonic_engine import HarmonicEngine
from backend.services.harmonic_baselines import HarmonicBaselineCatalog
from backend.services.resonance_service import get_resonance_service


def test_harmonic_baseline_catalog_classifies_deception_and_break_glass():
    deception = HarmonicBaselineCatalog.classify(
        actor_id="svc_guardian",
        tool_name="deception_router",
        target_domain="deception",
        environment="prod",
        operation="deception_dispatch",
        context={"deception_mode": "mirror_world"},
    )
    emergency = HarmonicBaselineCatalog.classify(
        actor_id="admin_root",
        tool_name="outbound_gate",
        target_domain="prod",
        environment="emergency",
        operation="break_glass_release",
        context={"break_glass": True},
    )

    assert deception == "deception_execution"
    assert emergency == "emergency_break_glass"


def test_harmonic_engine_marks_cold_start_as_insufficient_baseline():
    get_resonance_service().reset()
    engine = HarmonicEngine(window_size=64)
    result = engine.score_observation(
        actor_id="admin_byron",
        tool_name="control_console",
        target_domain="prod",
        environment="prod",
        stage="exec",
        timestamp_ms=1000.0,
        operation="console_review",
        context={"actor_role": "admin", "learn_baseline": False},
    )

    baseline_ref = result["baseline_ref"]
    state = result["harmonic_state"]

    assert baseline_ref["coverage_status"] == "insufficient"
    assert baseline_ref["baseline_class"] == "human_admin_workflow"
    assert baseline_ref["review_status"] == "fallback_only"
    assert baseline_ref["baseline_quality"] <= 0.35
    assert baseline_ref["source"] == "harmonic_engine.default"
    assert state["confidence"] < 0.4


def test_harmonic_engine_uses_explicit_reviewed_baseline_for_mcp_workflow():
    get_resonance_service().reset()
    engine = HarmonicEngine(window_size=64)
    for i in range(10):
        engine.score_observation(
            actor_id="svc_orchestrator",
            tool_name="mcp_vector_search",
            target_domain="knowledge",
            environment="prod",
            stage="exec",
            timestamp_ms=1000.0 + (i * 180.0),
            operation="mcp_query",
            context={"mcp_server": "vector", "automation": True, "learn_baseline": True},
        )

    result = engine.score_observation(
        actor_id="svc_orchestrator",
        tool_name="mcp_vector_search",
        target_domain="knowledge",
        environment="prod",
        stage="exec",
        timestamp_ms=2800.0,
        operation="mcp_query",
        context={"mcp_server": "vector", "automation": True, "learn_baseline": False},
    )

    baseline_ref = result["baseline_ref"]
    assert baseline_ref["coverage_status"] == "explicit"
    assert baseline_ref["baseline_class"] == "mcp_tool_invocation"
    assert baseline_ref["derived_from_audited_behavior"] is True
    assert baseline_ref["review_status"] == "reviewed"
    assert baseline_ref["baseline_quality"] >= 0.8
