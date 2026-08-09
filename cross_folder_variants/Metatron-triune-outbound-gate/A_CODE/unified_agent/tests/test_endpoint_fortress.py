from unified_agent.core.agent import AgentConfig, LocalExecutionBroker, LocalMCPGate, LocalVNSSentinel


def test_local_vns_beacon_lights_on_decoy_and_missing_context():
    cfg = AgentConfig(server_url="", local_ui_enabled=False)
    vns = LocalVNSSentinel(cfg)
    observed = vns.pre_observe(
        {
            "principal": "agent:test",
            "capability": "run_command",
            "target": "canary://fake-admin-creds",
            "decision_context": {},
            "token": None,
            "risk_hint": {"decoy_hit": True},
        }
    )

    assert observed["classification"] == "beacon_lit"
    assert observed["beacon"]["state"] == "Red"
    assert "decoy_interaction_detected" in observed["reasons"]


def test_local_mcp_gate_queues_without_decision_context_for_sensitive_action():
    cfg = AgentConfig(server_url="", local_ui_enabled=False)
    gate = LocalMCPGate(cfg)
    pre = {"tempo_per_minute": 1, "beacon": {"state": "Green"}}
    decision = gate.evaluate(
        {
            "principal": "service:control_plane",
            "capability": "kill_process",
            "target": "pid:1234",
            "token": {"token_id": "tok-1"},
            "decision_context": {},
        },
        pre,
    )
    assert decision["decision"] == "queue"
    assert decision["reason"] == "decision_context_required"


def test_local_mcp_gate_denies_invalid_signed_token():
    cfg = AgentConfig(
        server_url="",
        local_ui_enabled=False,
        endpoint_local_token_signing_key="top-secret-signing-key",
    )
    gate = LocalMCPGate(cfg)
    pre = {"tempo_per_minute": 1, "beacon": {"state": "Green"}}
    decision = gate.evaluate(
        {
            "principal": "service:control_plane",
            "capability": "block_ip",
            "target": "1.2.3.4",
            "token": {
                "token_id": "tok-1",
                "expires_at": "2999-01-01T00:00:00+00:00",
                "signature": "bad-signature",
            },
            "decision_context": {"decision_id": "d1"},
        },
        pre,
    )
    assert decision["decision"] == "deny"
    assert decision.get("error_type") == "token-invalid"


def test_local_execution_broker_allows_and_emits_boundary_event():
    events = []
    cfg = AgentConfig(server_url="", local_ui_enabled=False)
    broker = LocalExecutionBroker(cfg, emit_event_cb=lambda et, sv, data, tr: events.append((et, sv, data, tr)))

    ok, msg, meta = broker.execute_sensitive_action(
        principal="service:control_plane",
        capability="run_command",
        target="echo test",
        parameters={"command": "echo test"},
        decision_context={"decision_id": "dec-1"},
        token={"token_id": "tok-1"},
        risk_hint={},
        executor=lambda: (True, "ok", {"return_code": 0}),
        trace_id="trace-local-1",
    )

    assert ok is True
    assert msg == "ok"
    assert meta["status"] == "completed"
    assert events, "Expected broker to emit endpoint boundary world event callback"
    assert events[-1][0] == "endpoint_boundary_crossing"
    assert events[-1][2].get("outcome") == "allowed"


def test_local_execution_broker_throttles_burst_crossings():
    cfg = AgentConfig(
        server_url="",
        local_ui_enabled=False,
        endpoint_mcp_throttle_per_minute=2,
    )
    broker = LocalExecutionBroker(cfg)
    args = {
        "principal": "service:control_plane",
        "capability": "run_command",
        "target": "echo test",
        "parameters": {"command": "echo test"},
        "decision_context": {"decision_id": "dec-1"},
        "token": {"token_id": "tok-1"},
        "risk_hint": {},
        "executor": lambda: (True, "ok", {"return_code": 0}),
    }

    first_ok, _, first_meta = broker.execute_sensitive_action(**args)
    second_ok, second_msg, second_meta = broker.execute_sensitive_action(**args)
    assert first_ok is True
    assert first_meta["status"] == "completed"
    assert second_ok is False
    assert second_meta["status"] == "throttled"
    assert "tempo" in second_msg.lower()
