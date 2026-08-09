import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "run_last_chord_armageddon.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_last_chord_armageddon", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_wave_plan_divides_all_38_classes_evenly():
    module = _load_module()
    providers = module._default_providers()
    agent_classes = module._select_agent_classes("all")

    waves = module.build_wave_plan(
        group_id="armageddon_test",
        agent_classes=agent_classes,
        providers=providers,
        wave_size=12,
        mutation="stealth_slow",
        steps=6,
    )

    assert len(agent_classes) == 38
    assert [len(wave) for wave in waves] == [12, 12, 12, 2]
    provider_counts = {provider.name: 0 for provider in providers}
    for wave in waves:
        for run in wave:
            provider_counts[run.provider] += 1
    assert max(provider_counts.values()) - min(provider_counts.values()) <= 1


def test_build_wave_plan_uses_scenario_attempted_action_for_known_class():
    module = _load_module()
    providers = module._default_providers()

    waves = module.build_wave_plan(
        group_id="armageddon_test",
        agent_classes=["rogue_trusted_agent", "audit_evidence_forger", "cloud_lateral"],
        providers=providers,
        wave_size=3,
        mutation="stealth_slow",
        steps=6,
    )

    runs = waves[0]
    assert runs[0].attempted_action == "EXEC_KILL_PROCESS"
    assert runs[0].scenario_id == "LC-001"
    assert runs[1].attempted_action == "EXEC_ISOLATE_HOST"
    assert runs[1].scenario_id == "LC-002"
    assert runs[2].attempted_action == "EXEC_ISOLATE_HOST"
    assert runs[2].scenario_id == "LC-005"


def test_network_capture_manifest_records_explicit_capture_bounds():
    module = _load_module()
    session = module.NetworkCaptureSession(
        group_id="armageddon_test",
        port=8099,
        requested_backend="zeek",
        capture_interface="lo",
        capture_with_sudo=False,
        capture_packet_limit=7,
        capture_wait_seconds=12.5,
    )
    session._capture_dir = module.OUTPUT_DIR / "armageddon_test_network_capture"
    session._pcap_path = session._capture_dir / "armageddon_test.pcap"
    session._zeek_dir = session._capture_dir / "zeek"
    session._zeek_backend = lambda: "docker"

    manifest = session.manifest_stub()

    assert manifest["pcap"]["packet_limit"] == 7
    assert manifest["pcap"]["wait_seconds"] == 12.5


def test_run_zeek_analysis_uses_docker_entrypoint_without_extra_zeek_token(tmp_path, monkeypatch):
    module = _load_module()
    session = module.NetworkCaptureSession(
        group_id="armageddon_test",
        port=8099,
        requested_backend="zeek",
        capture_interface="lo",
        capture_with_sudo=False,
    )
    session._capture_dir = tmp_path
    session._pcap_path = tmp_path / "armageddon_test.pcap"
    session._pcap_path.write_bytes(b"pcap")
    session._zeek_dir = tmp_path / "zeek"
    session._zeek_dir.mkdir()
    session._zeek_backend = lambda: "docker"

    captured = {}

    def fake_run(cmd, cwd, capture_output, text):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = session._run_zeek_analysis()

    image_index = captured["cmd"].index(session._zeek_image)
    assert captured["cmd"][image_index + 1:] == ["-Cr", f"/capture/{session._pcap_path.name}"]
    assert result["status"] == "completed"