from unified_agent.ui.web.app import create_app


def test_canonical_port5000_api_contract():
    app = create_app()
    app.config["TESTING"] = True

    client = app.test_client()

    required_get_routes = [
        "/api/status",
        "/api/dashboard",
        "/api/data",
        "/api/yara",
        "/api/security/tooling",
        "/api/tooling/health",
        "/api/external-access/status",
        "/api/attack-coverage",
        "/api/integration/backend-gap-report",
        "/api/integrations/core/tools",
        "/api/integrations/core/status",
        "/api/integrations/core/jobs",
        "/api/vpn/status",
        "/api/monitors/amsi",
        "/api/monitors/webview",
        "/api/monitors/trusted-ai",
        "/api/monitors/power",
        "/api/monitors/trivy",
        "/api/monitors/falco",
        "/api/monitors/suricata",
        "/api/monitors/volatility",
        "/api/monitors/cli-telemetry",
        "/api/monitors/autothrottle",
    ]

    for route in required_get_routes:
        resp = client.get(route)
        assert resp.status_code == 200, f"{route} returned {resp.status_code}"
        payload = resp.get_json()
        assert isinstance(payload, dict), f"{route} did not return JSON object"

    status = client.get("/api/status").get_json()
    assert "monolithic_bridge" in status

    dashboard = client.get("/api/dashboard").get_json()
    data_alias = client.get("/api/data").get_json()

    # /api/data must mirror /api/dashboard (legacy 5050 compatibility)
    assert set(dashboard.keys()) == set(data_alias.keys())

    tooling = client.get("/api/security/tooling").get_json()
    assert "tools" in tooling
    for tool_name in ["wireguard", "trivy", "falco", "suricata", "volatility"]:
        assert tool_name in tooling["tools"], f"Missing tooling status for {tool_name}"

    external_access = client.get("/api/external-access/status").get_json()
    assert "checks" in external_access
    assert "reachable" in external_access

    attack_coverage = client.get("/api/attack-coverage").get_json()
    assert "techniques" in attack_coverage
    assert "tactics" in attack_coverage
    assert "priority_gaps" in attack_coverage

    backend_gap = client.get("/api/integration/backend-gap-report").get_json()
    assert "supported_agent_command_types" in backend_gap
    assert "backend_feature_families" in backend_gap
    for cmd_type in ["trivy_scan", "falco_status", "suricata_status", "volatility_scan"]:
        assert cmd_type in backend_gap["supported_agent_command_types"], f"Missing command support: {cmd_type}"

    core_tools = client.get("/api/integrations/core/tools").get_json()
    assert "tools" in core_tools
    for tool_name in ["amass", "arkime", "bloodhound", "spiderfoot", "velociraptor", "sigma", "atomic"]:
        assert tool_name in core_tools["tools"], f"Missing core integration tool: {tool_name}"

    core_status = client.get("/api/integrations/core/status").get_json()
    assert "tools" in core_status

    core_jobs = client.get("/api/integrations/core/jobs").get_json()
    assert "jobs" in core_jobs
