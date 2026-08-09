from unified_agent.core.agent import AgentConfig, CLITelemetryMonitor


def _monitor() -> CLITelemetryMonitor:
    cfg = AgentConfig(server_url="", local_ui_enabled=False)
    return CLITelemetryMonitor(cfg)


def test_extract_identity_techniques_from_metadata_and_creds_commands():
    mon = _monitor()
    cmd = "curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/ && cat ~/.aws/credentials"
    techniques = mon._extract_priority_mitre_techniques(cmd)
    assert "T1528" in techniques
    assert "T1552.001" in techniques
    assert "T1552.005" in techniques


def test_identity_provider_inference_for_okta_and_m365():
    mon = _monitor()
    assert mon._infer_identity_provider_from_command("curl https://company.okta.com/api/v1/users") == "okta"
    assert mon._infer_identity_provider_from_command("az account get-access-token --resource https://graph.microsoft.com") == "m365"


def test_identity_payload_classifies_metadata_harvest_event_type():
    mon = _monitor()
    cmd_event = {
        "command": "curl 169.254.169.254/latest/meta-data/iam/security-credentials/",
        "username": "analyst",
        "timestamp": "2026-03-09T00:00:00+00:00",
    }
    payload = mon._build_identity_event_payload(cmd_event, ["T1528", "T1552.005"])
    assert payload["event_type"] == "metadata_token_harvest"
    assert payload["riskScore"] >= 90
    assert payload["source"] == "cli_telemetry_monitor"
