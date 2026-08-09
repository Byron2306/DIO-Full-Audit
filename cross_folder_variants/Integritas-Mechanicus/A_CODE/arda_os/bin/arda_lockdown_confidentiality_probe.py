#!/usr/bin/env python3
"""Probe whether the current host is likely ready for confidentiality lockdown."""

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone


def _safe_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception:
        return ""


def _ps() -> str:
    try:
        return subprocess.run(["ps", "-eo", "comm="], capture_output=True, text=True, check=False).stdout
    except Exception:
        return ""


def _command_exists(path: str) -> bool:
    return os.path.exists(path) and os.access(path, os.X_OK)


def _command_runs(command: list[str]) -> bool:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=5).returncode == 0
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe confidentiality-lockdown readiness")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    lockdown = _safe_text("/sys/kernel/security/lockdown")
    process_list = {line.strip() for line in _ps().splitlines() if line.strip()}
    blockers = []
    warnings = []
    workflow_checks = {
        "sudo_available": _command_runs(["sudo", "-n", "true"]),
        "systemd_logind_present": "systemd-logind" in process_list,
        "graphics_stack_present": any(name in process_list for name in {"Xorg", "wayland", "xfce4-session"}),
        "measured_policy_cli_present": _command_exists("/home/byron/Integritas-Mechanicus/arda_os/bin/arda"),
    }

    if not lockdown:
        blockers.append("lockdown_interface_missing")
    if "confidentiality" not in lockdown:
        blockers.append("confidentiality_mode_unavailable")
    if "Xorg" in process_list:
        warnings.append("xorg_running_raw_io_may_break")
    if any(name in process_list for name in {"dkms", "depmod", "modprobe"}):
        warnings.append("module_tooling_running")
    if os.path.exists("/usr/bin/systemd-hibernate"):
        warnings.append("hibernation_paths_present")
    if "gdb" in process_list:
        warnings.append("debugger_present")
    if "bpftool" not in process_list and not _command_exists("/usr/bin/bpftool"):
        warnings.append("bpftool_unavailable_for_postswitch_diagnostics")
    if _command_exists("/usr/bin/kexec"):
        warnings.append("kexec_available_validate_lockdown_policy")
    if _command_exists("/usr/bin/Xorg") or "Xorg" in process_list:
        warnings.append("graphics_stack_should_be_revalidated_under_confidentiality")
    if not workflow_checks["sudo_available"]:
        warnings.append("sudo_noninteractive_check_unavailable")
    if not workflow_checks["systemd_logind_present"]:
        warnings.append("systemd_logind_not_detected")
    if not workflow_checks["graphics_stack_present"]:
        warnings.append("graphics_session_not_detected")

    payload = {
        "ok": not blockers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lockdown": lockdown,
        "blockers": blockers,
        "warnings": warnings,
        "workflow_checks": workflow_checks,
        "recommended_next_state": "test_confidentiality" if not blockers else "stay_integrity",
        "next_actions": [
            "stop DKMS or module build activity before switching",
            "capture a fresh signed remote-verifier verdict before promotion",
            "reboot and validate graphics, sudo, systemd-logind, and measured-policy paths under confidentiality",
        ] if not blockers else [
            "stay on integrity lockdown until blockers clear",
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
