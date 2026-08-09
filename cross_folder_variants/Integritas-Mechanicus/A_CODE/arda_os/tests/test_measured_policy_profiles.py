import os
from pathlib import Path

from backend.services.measured_policy_profiles import (
    expand_measurement_profile,
    expand_projection_profile,
    merge_discovered_manifest_paths,
)


def test_critical_host_projection_profile_contains_core_paths():
    paths = expand_projection_profile("critical-host")
    assert any(path.rsplit("/", 1)[-1].startswith("python3") for path in paths)
    assert any(path.endswith("/usr/bin/systemctl") for path in paths)


def test_critical_host_measurement_profile_includes_repo_policy_files():
    paths = expand_measurement_profile("critical-host")
    assert any(path.endswith("/arda_os/arda_policy.json") for path in paths)
    assert any(path.endswith("/arda_os/arda_policy_bundle.json") for path in paths)


def test_critical_host_measurement_profile_includes_rollout_and_systemd_surface():
    paths = expand_measurement_profile("critical-host")
    assert any(path.endswith("/arda_os/bin/arda_phase4_rollout.py") for path in paths)
    assert any(path.endswith("/usr/lib/systemd/systemd-logind") for path in paths)
    assert any(path.endswith("/arda_os/deploy/systemd/arda-phase4-remote-verifier.service") for path in paths)


def test_critical_host_measurement_profile_includes_verifier_ops_surface():
    paths = expand_measurement_profile("critical-host")
    assert any(path.endswith("/arda_os/kernel/valinor/PRODUCTION_OPERATIONS.md") for path in paths)


def test_critical_host_measurement_profile_includes_harmonic_and_voice_surface():
    paths = expand_measurement_profile("critical-host")
    assert any(path.endswith("/arda_os/backend/services/harmonic_engine.py") for path in paths)
    assert any(path.endswith("/arda_os/backend/services/voice_registry.py") for path in paths)
    assert any(path.endswith("/arda_os/backend/services/arda_discover.py") for path in paths)


def test_critical_host_projection_profile_includes_tpm_toolchain():
    paths = expand_projection_profile("critical-host")
    assert any(os.path.basename(path) == "tpm2" for path in paths)


def test_manifest_id_alias_path_shape_is_stable():
    output = "/var/lib/arda/projection/measured-critical-live.json"
    manifest_id = "measured-ff31353dbe844c81"
    manifest_id_path = os.path.join(os.path.dirname(output), f"{manifest_id}.json")
    assert manifest_id_path == "/var/lib/arda/projection/measured-ff31353dbe844c81.json"
    assert Path(manifest_id_path).name == "measured-ff31353dbe844c81.json"


def test_merge_discovered_manifest_paths_prefers_runtime_tiers():
    manifest = {
        "entries": [
            {"path": "/bin/bash", "tier": "critical"},
            {"path": "/usr/bin/python3", "tier": "operational"},
            {"path": "/usr/bin/gcc", "tier": "development"},
            {"path": "/home/byron/.local/bin/ruff", "tier": "operational"},
            {"path": "/usr/bin/thunar", "tier": "operational"},
            {"path": "/usr/lib/firefox-esr/firefox-esr", "tier": "operational"},
        ]
    }
    paths = merge_discovered_manifest_paths(manifest)
    assert any(path.endswith("/bin/bash") for path in paths)
    assert any(os.path.basename(path).startswith("python3") for path in paths)
    assert not any(path.endswith("/usr/bin/gcc") for path in paths)
    assert not any(path.endswith("/.local/bin/ruff") for path in paths)
    assert not any(path.endswith("/usr/bin/thunar") for path in paths)
    assert not any("/usr/lib/firefox-esr/" in path for path in paths)
