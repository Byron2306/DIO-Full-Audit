import json
from pathlib import Path
from types import SimpleNamespace

from unified_agent.ui.web.app import WebAgentBridge


class _StubRansomwareMonitor:
    enabled = True

    def __init__(self):
        self.canaries = {"/tmp/Budget_2026_CONFIDENTIAL.xlsx": {"hash": "abc"}}
        self.protected_folders = {"/tmp/Documents"}

    def scan(self):
        return {
            "threats_detected": 2,
            "canary_alerts": 1,
            "shadow_copy_threats": 1,
        }

    def get_status(self):
        return {
            "canaries_deployed": 1,
            "canary_paths": ["/tmp/Budget_2026_CONFIDENTIAL.xlsx"],
            "protected_folders": ["/tmp/Documents"],
            "shadow_copy_baseline": 3,
        }


class _StubSelfProtectionMonitor:
    enabled = True
    watchdog_enabled = True

    def scan(self):
        return {
            "protection_active": True,
            "protection_status": {
                "process_intact": True,
                "files_intact": True,
                "parent_valid": True,
                "not_debugged": True,
            },
            "details": {
                "debug_attempts": [{"type": "debugger_running", "name": "gdb"}],
                "tamper_events": [
                    {"type": "suspicious_library", "path": "/tmp/frida.so"},
                    {"type": "file_modified", "path": "/tmp/agent.py"},
                ],
            },
        }


def _build_bridge(monitors):
    bridge = WebAgentBridge.__new__(WebAgentBridge)
    bridge.monolithic_agent = SimpleNamespace(monitors=monitors)
    bridge.agent = SimpleNamespace(config=SimpleNamespace(server_url=""))
    return bridge


def test_ransomware_stats_map_runtime_monitor_fields():
    bridge = _build_bridge({"ransomware": _StubRansomwareMonitor()})

    data = bridge.get_ransomware_stats()

    assert data["enabled"] is True
    assert data["canary_files"] == ["/tmp/Budget_2026_CONFIDENTIAL.xlsx"]
    assert data["canary_alerts"] == 1
    assert data["shadow_copy_protected"] is True
    assert data["protected_folders"] == ["/tmp/Documents"]


def test_self_protection_stats_map_runtime_monitor_fields():
    bridge = _build_bridge({"self_protection": _StubSelfProtectionMonitor()})

    data = bridge.get_self_protection_stats()

    assert data["enabled"] is True
    assert data["watchdog_running"] is True
    assert len(data["debugger_detections"]) == 1
    assert len(data["injection_attempts"]) == 1
    assert data["integrity_status"]["files_intact"] is True


def test_vpn_update_config_persists_locally_without_remote_api(tmp_path):
    bridge = _build_bridge({})
    target = tmp_path / "vpn_ui_state.json"
    bridge._vpn_state_path = lambda: Path(target)

    result = bridge.vpn_update_config(
        {
            "server_address": "10.10.10.1/24",
            "port": 51825,
            "dns_servers": ["9.9.9.9"],
            "max_clients": 32,
        }
    )

    assert result["status"] == "updated"
    assert result["persisted"] == "local"
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["server_address"] == "10.10.10.1/24"
    assert saved["port"] == 51825
    assert saved["dns_servers"] == ["9.9.9.9"]
    assert saved["max_clients"] == 32
