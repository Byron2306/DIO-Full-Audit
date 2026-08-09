"""Regression tests for AI reasoning method bindings."""

from backend.services.ai_reasoning import ReasoningContext, ai_reasoning


def test_ai_reasoning_exposes_core_methods():
    expected = [
        "analyze_threat",
        "analyze_snapshot",
        "predict_next_step",
        "predict_lateral_path",
        "explain_candidates",
        "triage_incident",
        "query",
    ]
    for method in expected:
        assert hasattr(ai_reasoning, method), f"ai_reasoning missing method: {method}"
        assert callable(getattr(ai_reasoning, method)), f"ai_reasoning.{method} must be callable"


def test_ai_reasoning_snapshot_analysis_executes():
    context = ReasoningContext(
        entities=[{"id": "host-1", "attributes": {"telemetry": []}}],
        relationships={"edges": [{"source": "host-1", "target": "host-2"}]},
        evidence_set=[{"type": "c2_beacon"}],
        trust_state={},
        timeline_window=[],
    )
    result = ai_reasoning.analyze_snapshot(context)
    assert isinstance(result, dict)
    assert "predictions" in result
