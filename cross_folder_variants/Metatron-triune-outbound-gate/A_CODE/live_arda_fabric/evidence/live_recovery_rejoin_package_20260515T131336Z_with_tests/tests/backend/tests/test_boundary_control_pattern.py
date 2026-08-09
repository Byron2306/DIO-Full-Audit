import pytest

from backend.services.boundary_control import (
    CANONICAL_BOUNDARY_OUTCOMES,
    build_boundary_contract,
    boundary_control,
)
from backend.services.mcp_server import MCPMessageType, mcp_server


def test_boundary_pre_observe_scores_missing_context_and_token():
    contract = build_boundary_contract(
        principal="agent:test-1",
        sector_from="governance",
        sector_to="tool_execution",
        capability="mcp.firewall.block_ip",
        target="10.1.2.3",
        decision_context={},
        token="",
        risk_hint={},
        trace_id="trace-pre-1",
    )

    observed = boundary_control.pre_observe(contract)
    assert observed["phase"] == "pre"
    assert observed["anomaly_score"] >= 20
    assert "missing_decision_context" in observed["reasons"]
    assert "missing_capability_token" in observed["reasons"]
    assert observed["beacon"]["sector"] == "tool_execution"


def test_boundary_post_observe_prioritizes_token_invalid():
    contract = build_boundary_contract(
        principal="operator:admin@example.com",
        sector_from="governance",
        sector_to="tool_execution",
        capability="mcp.soar.run_playbook",
        target="playbook://critical",
        decision_context={"decision_id": "decision-1"},
        token="tok-123",
        risk_hint={},
        trace_id="trace-post-1",
    )
    pre = boundary_control.pre_observe(contract)
    post = boundary_control.post_observe(
        contract,
        pre_observation=pre,
        mcp_outcome="token-invalid",
        mcp_reason="signature mismatch",
        execution_status="failed",
    )
    assert post["phase"] == "post"
    assert post["world_event_outcome"] == "token-invalid"
    assert post["world_event_outcome"] in CANONICAL_BOUNDARY_OUTCOMES


@pytest.mark.asyncio
async def test_mcp_emits_canonical_boundary_crossing_event(monkeypatch):
    mcp_server.executions.clear()
    mcp_server.message_history.clear()
    captured_events = []

    async def fake_emit(*, event_type, entity_refs, payload, trigger_triune):
        captured_events.append(
            {
                "event_type": event_type,
                "entity_refs": entity_refs,
                "payload": payload,
                "trigger_triune": trigger_triune,
            }
        )

    monkeypatch.setattr(mcp_server, "_emit_mcp_event", fake_emit)

    message = mcp_server.create_message(
        message_type=MCPMessageType.TOOL_REQUEST,
        source="agent:boundary-test",
        destination="mcp.scanner.network",
        payload={
            "params": {"target": "127.0.0.1", "scan_type": "quick"},
            "sector_from": "governance",
            "sector_to": "tool_execution",
            "risk_hint": {"vns_score_boost": 80},
        },
        trace_id="trace-mcp-boundary-1",
    )

    response = await mcp_server.handle_message(message)
    assert response.payload.get("execution_id")
    assert response.payload.get("status") in {"success", "failed", "timeout", "denied"}

    boundary_events = [e for e in captured_events if e["event_type"] == "boundary_crossing"]
    assert boundary_events, "Expected canonical boundary_crossing world event to be emitted"
    crossing_payload = boundary_events[-1]["payload"]
    assert crossing_payload.get("crossing_outcome") in CANONICAL_BOUNDARY_OUTCOMES
    assert crossing_payload.get("boundary_contract", {}).get("sector_from") == "governance"
    assert crossing_payload.get("boundary_contract", {}).get("sector_to") == "tool_execution"
