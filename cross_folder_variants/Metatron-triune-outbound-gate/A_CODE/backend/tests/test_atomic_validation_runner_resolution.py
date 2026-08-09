"""Tests for AtomicValidationManager runner resolution."""

import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from atomic_validation import AtomicValidationManager


def test_resolve_runner_falls_back_to_bundled_pwsh(monkeypatch):
    monkeypatch.delenv("ATOMIC_RUNNER", raising=False)

    manager = AtomicValidationManager()
    resolved = manager._resolve_runner("/usr/bin/pwsh")

    assert resolved is not None
    assert Path(resolved).name in {"pwsh", "pwsh.exe"}
    assert Path(resolved).exists()


def test_build_winrm_command_falls_back_to_local_pwsh_when_pywinrm_unavailable(monkeypatch):
    monkeypatch.setattr("atomic_validation.winrm", None)
    manager = AtomicValidationManager()

    profile = {
        "type": "winrm",
        "remote_host": "192.168.122.13",
        "remote_user": "labadmin",
        "password_env": "ATOMIC_WINDOWS_LAB_PASSWORD",
    }
    command = manager._build_winrm_command(["T1176"], profile)

    assert command[0].endswith("pwsh") or command[0].endswith("powershell")
    assert "-Command" in command


def test_build_winrm_command_uses_pywinrm_when_available(monkeypatch):
    monkeypatch.setattr("atomic_validation.winrm", object())
    manager = AtomicValidationManager()

    profile = {
        "type": "winrm",
        "remote_host": "192.168.122.13",
        "remote_user": "labadmin",
        "password_env": "ATOMIC_WINDOWS_LAB_PASSWORD",
    }
    command = manager._build_winrm_command(["T1176"], profile)

    assert command[:4] == ["pywinrm", "192.168.122.13", "labadmin", "ATOMIC_WINDOWS_LAB_PASSWORD"]
    assert command[4:] == ["T1176"]


def test_resolve_runner_profile_prefers_configured_windows_profile(monkeypatch, tmp_path):
    config_path = tmp_path / "atomic_powershell.yml"
    config_path.write_text(
        """
runner: /usr/bin/pwsh
module_path: C:/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1
atomic_root: C:/AtomicRedTeam/atomics
runner_profiles:
  - profile_id: windows-lab-winrm
    type: winrm
    enabled: true
    remote_host: 192.168.122.13
    remote_user: labadmin
    password_env: ATOMIC_WINDOWS_LAB_PASSWORD
jobs: []
"""
    )
    monkeypatch.setenv("ATOMIC_POWERSHELL_CONFIG", str(config_path))
    manager = AtomicValidationManager()

    profile = manager._resolve_runner_profile("windows-lab-winrm")

    assert profile["profile_id"] == "windows-lab-winrm"
    assert profile["type"] == "winrm"
    assert profile["remote_host"] == "192.168.122.13"
    assert profile["remote_user"] == "labadmin"


def test_execute_winrm_profile_auto_falls_back_to_basic(monkeypatch, tmp_path):
    calls = []
    scripts = []

    class DummyResponse:
        status_code = 0
        std_out = b"ok"
        std_err = b""

    class DummySession:
        def __init__(self, endpoint, auth, transport, server_cert_validation):
            calls.append(transport)
            if transport == "auto":
                raise InvalidCredentialsError("auto auth failed")

        def run_ps(self, script):
            scripts.append(script)
            return DummyResponse()

    import sys
    import types

    InvalidCredentialsError = type("InvalidCredentialsError", (Exception,), {})
    fake_winrm = types.ModuleType("winrm")
    fake_exceptions = types.ModuleType("winrm.exceptions")
    fake_exceptions.InvalidCredentialsError = InvalidCredentialsError
    fake_winrm.Session = DummySession
    fake_winrm.exceptions = fake_exceptions

    monkeypatch.setitem(sys.modules, "winrm", fake_winrm)
    monkeypatch.setitem(sys.modules, "winrm.exceptions", fake_exceptions)
    monkeypatch.setattr("atomic_validation.winrm", fake_winrm)
    monkeypatch.setenv("ATOMIC_WINDOWS_LAB_PASSWORD", "Password123!")

    manager = AtomicValidationManager()
    local_atomic_root = tmp_path / "atomics"
    technique_dir = local_atomic_root / "T1176"
    technique_dir.mkdir(parents=True, exist_ok=True)
    (technique_dir / "T1176.yaml").write_text("attack_technique: T1176\n", encoding="utf-8")
    manager.module_path = "C:/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1"
    manager.atomic_root = local_atomic_root

    profile = {
        "type": "winrm",
        "remote_host": "192.168.122.13",
        "remote_user": "labadmin",
        "password_env": "ATOMIC_WINDOWS_LAB_PASSWORD",
        "module_path": "C:/AtomicRedTeam/invoke-atomicredteam/Invoke-AtomicRedTeam.psd1",
        "atomic_root": "C:/AtomicRedTeam/atomics",
        "winrm_transport": "auto",
    }

    exit_code, stdout, stderr = manager._execute_winrm_profile(["T1176"], profile)

    assert exit_code == 0
    assert stdout == "ok"
    assert calls == ["auto", "basic"]
    assert scripts
    assert "Invoke-AtomicTest T1176 -PathToAtomicsFolder 'C:/AtomicRedTeam/atomics'" in scripts[-1]
