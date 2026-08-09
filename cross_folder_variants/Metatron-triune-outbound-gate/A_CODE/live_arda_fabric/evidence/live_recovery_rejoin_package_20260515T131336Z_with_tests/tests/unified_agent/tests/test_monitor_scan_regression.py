import json

from unified_agent.core.agent import AgentConfig, UnifiedAgent


def test_all_monitors_scan_without_exceptions():
    """Regression guard: every instantiated monitor must complete one scan without raising."""
    config = AgentConfig(server_url="", local_ui_enabled=False)
    agent = UnifiedAgent(config=config)

    failures = {}
    result_types = {}

    for monitor_name, monitor in agent.monitors.items():
        try:
            result = monitor.scan()
            result_types[monitor_name] = type(result).__name__
        except Exception as exc:
            failures[monitor_name] = f"{type(exc).__name__}: {exc}"

    assert "cli_telemetry" in agent.monitors, "Expected cli_telemetry monitor to be present"
    assert len(agent.monitors) >= 25, f"Expected at least 25 monitors, got {len(agent.monitors)}"

    assert not failures, (
        "One or more monitors failed one-pass scan regression. "
        f"Failures={json.dumps(failures, indent=2, sort_keys=True)} "
        f"ResultTypes={json.dumps(result_types, sort_keys=True)}"
    )
