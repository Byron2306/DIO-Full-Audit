from backend.routers.enterprise import (
    _endpoint_boundary_trigger_triune,
    _extract_endpoint_boundary_context,
)


def test_extract_endpoint_boundary_context_normalizes_outcome_and_decision_context():
    data = {
        "outcome": "",
        "boundary": {
            "decision_context": {
                "decision_id": "dec-123",
                "queue_id": "queue-123",
            }
        },
        "post_observation": {
            "gate_outcome": "throttle",
            "beacon": {"state": "Red", "score": 88},
        },
    }
    context = _extract_endpoint_boundary_context(data, fallback_agent_id="agent-xyz")
    assert context["agent_id"] == "agent-xyz"
    assert context["decision_context"]["decision_id"] == "dec-123"
    assert context["outcome"] == "queued"


def test_endpoint_boundary_trigger_triune_for_red_beacon():
    should = _endpoint_boundary_trigger_triune(
        {
            "outcome": "allowed",
            "beacon": {"state": "Red"},
        }
    )
    assert should is True
