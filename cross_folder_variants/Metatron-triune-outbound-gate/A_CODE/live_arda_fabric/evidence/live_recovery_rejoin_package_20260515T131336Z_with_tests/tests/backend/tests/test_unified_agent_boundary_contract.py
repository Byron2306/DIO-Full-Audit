from backend.routers.unified_agent import (
    _extract_boundary_crossing_from_command_result,
    _serialize_agent_command_for_delivery,
)


def test_serialize_agent_command_for_delivery_includes_authority_and_decision_context():
    command_doc = {
        "command_id": "cmd-1",
        "agent_id": "agent-1",
        "command_type": "kill_process",
        "parameters": {"pid": 1234},
        "priority": "critical",
        "issued_by": "operator:test@example.com",
        "decision_id": "dec-1",
        "queue_id": "queue-1",
        "status": "pending",
    }

    payload = _serialize_agent_command_for_delivery(command_doc)
    assert payload["command_id"] == "cmd-1"
    assert payload["decision_context"]["decision_id"] == "dec-1"
    assert payload["decision_context"]["queue_id"] == "queue-1"
    assert payload["authority_context"]["principal"] == "operator:test@example.com"
    assert payload["authority_context"]["capability"] == "kill_process"
    assert payload["authority_context"]["requires_decision_context"] is True


def test_extract_boundary_crossing_from_command_result_promotes_denied_outcome():
    result = {
        "command_id": "cmd-2",
        "fortress": {
            "boundary": {
                "decision_context": {
                    "decision_id": "dec-2",
                    "queue_id": "queue-2",
                }
            },
            "gate": {"decision": "deny"},
            "post": {"gate_outcome": "deny", "beacon": {"state": "Amber"}},
        },
    }
    boundary = _extract_boundary_crossing_from_command_result(
        agent_id="agent-2",
        command_id="cmd-2",
        result=result,
    )
    assert boundary["event_type"] == "boundary_crossing"
    assert boundary["payload"]["crossing_outcome"] == "denied"
    assert boundary["trigger_triune"] is True
