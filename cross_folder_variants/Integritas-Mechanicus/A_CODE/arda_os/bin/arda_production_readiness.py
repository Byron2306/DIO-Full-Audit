#!/usr/bin/env python3
"""
Production readiness gate for Arda host integration.

This does not claim Arda is a standalone distribution. It verifies whether the
current host has crossed the more practical OS boundary: boot-ordered services,
policy artifacts, attestation storage, and kernel-adjacent enforcement paths.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULTS = {
    "home": "/opt/arda/arda_os",
    "env": "/etc/arda/arda.env",
    "policy_bundle": "/etc/arda/policy/active_bundle.json",
    "projection_plan": "/etc/arda/policy/active_projection_plan.json",
    "attestation_dir": "/var/lib/arda/attestation/latest",
    "status_snapshot": "/var/log/arda/status_snapshot.json",
    "bpf_pin_root": "/sys/fs/bpf/arda",
    "systemd_dir": "/etc/systemd/system",
}

REQUIRED_UNITS = [
    "arda-loader.service",
    "arda-policy-projection.service",
    "arda-attestation.service",
    "arda-ledger.service",
]


def _run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    except FileNotFoundError:
        return 127, "command not found"
    except subprocess.TimeoutExpired:
        return 124, "command timed out"
    return result.returncode, (result.stdout + result.stderr).strip()


def _path_check(path: str, expected: str) -> dict:
    target = Path(path)
    try:
        exists = target.exists()
        if expected == "dir":
            ok = target.is_dir()
        elif expected == "file":
            ok = target.is_file()
        elif expected == "executable":
            ok = target.is_file() and os.access(target, os.X_OK)
        else:
            ok = exists
        return {"path": path, "expected": expected, "exists": exists, "ok": ok}
    except PermissionError as error:
        return {
            "path": path,
            "expected": expected,
            "exists": "permission_denied",
            "ok": False,
            "error": str(error),
        }


def _json_file_check(path: str) -> dict:
    check = _path_check(path, "file")
    if not check["ok"]:
        check["valid_json"] = False
        return check
    try:
        with open(path, "r", encoding="utf-8") as handle:
            json.load(handle)
        check["valid_json"] = True
    except Exception as error:
        check["valid_json"] = False
        check["error"] = str(error)
    check["ok"] = check["ok"] and check["valid_json"]
    return check


def _systemd_unit_check(unit: str, systemd_dir: str) -> dict:
    unit_path = Path(systemd_dir) / unit
    present = unit_path.is_file()
    enabled_code, enabled_output = _run(["systemctl", "is-enabled", unit])
    active_code, active_output = _run(["systemctl", "is-active", unit])
    return {
        "unit": unit,
        "path": str(unit_path),
        "installed": present,
        "enabled": enabled_code == 0,
        "enabled_state": enabled_output,
        "active": active_code == 0,
        "active_state": active_output,
        "ok": present and enabled_code == 0,
    }


def _secure_boot_check() -> dict:
    efi_dir = Path("/sys/firmware/efi")
    efivars = efi_dir / "efivars"
    mount_code, mount_output = _run(["findmnt", "-n", "/sys/firmware/efi/efivars"])
    mok_code, mok_output = _run(["mokutil", "--sb-state"])
    return {
        "uefi_boot": efi_dir.is_dir(),
        "efivars_dir": efivars.is_dir(),
        "efivarfs_mounted": mount_code == 0,
        "mokutil_state": mok_output,
        "secure_boot_visible": "EFI variables are not supported" not in mok_output,
        "secure_boot_enabled": "SecureBoot enabled" in mok_output,
        "ok": efi_dir.is_dir() and mount_code == 0 and "SecureBoot enabled" in mok_output,
    }


def _bpf_check(pin_root: str) -> dict:
    lsm_path = Path("/sys/kernel/security/lsm")
    lsm_text = lsm_path.read_text(encoding="utf-8").strip() if lsm_path.is_file() else ""
    bpffs_code, bpffs_output = _run(["findmnt", "-n", "/sys/fs/bpf"])
    pin_root_check = _path_check(pin_root, "dir")
    return {
        "active_lsms": lsm_text or "unavailable",
        "bpf_lsm_active": "bpf" in lsm_text.split(","),
        "bpffs_mounted": bpffs_code == 0,
        "bpffs_mount": bpffs_output,
        "pin_root": pin_root,
        "pin_root_present": pin_root_check["ok"],
        "pin_root_error": pin_root_check.get("error"),
        "ok": "bpf" in lsm_text.split(",") and bpffs_code == 0 and pin_root_check["ok"],
    }


def build_report(paths: dict) -> dict:
    checks = {
        "arda_home": _path_check(paths["home"], "dir"),
        "arda_cli": _path_check(str(Path(paths["home"]) / "bin" / "arda"), "executable"),
        "environment": _path_check(paths["env"], "file"),
        "policy_bundle": _json_file_check(paths["policy_bundle"]),
        "projection_plan": _json_file_check(paths["projection_plan"]),
        "attestation_dir": _path_check(paths["attestation_dir"], "dir"),
        "status_snapshot": _json_file_check(paths["status_snapshot"]),
        "secure_boot": _secure_boot_check(),
        "bpf": _bpf_check(paths["bpf_pin_root"]),
    }
    checks["systemd_units"] = {
        unit: _systemd_unit_check(unit, paths["systemd_dir"]) for unit in REQUIRED_UNITS
    }

    blockers = []
    warnings = []

    for name, check in checks.items():
        if name == "systemd_units":
            for unit, unit_check in check.items():
                if not unit_check["ok"]:
                    blockers.append(f"{unit} is not installed and enabled")
            continue
        if not check.get("ok"):
            if name in {"secure_boot", "bpf", "policy_bundle", "projection_plan", "arda_home", "arda_cli"}:
                blockers.append(f"{name} is not production-ready")
            else:
                warnings.append(f"{name} is incomplete")

    production_ready = not blockers
    if production_ready:
        boundary = "OS-grade host substrate"
    else:
        boundary = "OS-adjacent integration layer"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "production_ready": production_ready,
        "boundary": boundary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def _text_report(report: dict) -> str:
    lines = [
        "ARDA PRODUCTION READINESS",
        f"boundary: {report['boundary']}",
        f"production_ready: {report['production_ready']}",
        "",
        "blockers:",
    ]
    lines.extend([f"- {blocker}" for blocker in report["blockers"]] or ["- none"])
    lines.append("")
    lines.append("warnings:")
    lines.extend([f"- {warning}" for warning in report["warnings"]] or ["- none"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Arda production host readiness")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--home", default=os.environ.get("ARDA_HOME", DEFAULTS["home"]))
    parser.add_argument("--env", default=DEFAULTS["env"])
    parser.add_argument("--policy-bundle", default=os.environ.get("ARDA_POLICY_BUNDLE", DEFAULTS["policy_bundle"]))
    parser.add_argument("--projection-plan", default=os.environ.get("ARDA_POLICY_PROJECTION_PLAN", DEFAULTS["projection_plan"]))
    parser.add_argument("--attestation-dir", default=os.environ.get("ARDA_ATTESTATION_DIR", DEFAULTS["attestation_dir"]))
    parser.add_argument("--status-snapshot", default=os.environ.get("ARDA_STATUS_SNAPSHOT_PATH", DEFAULTS["status_snapshot"]))
    parser.add_argument("--bpf-pin-root", default=os.environ.get("ARDA_BPF_PIN_ROOT", DEFAULTS["bpf_pin_root"]))
    parser.add_argument("--systemd-dir", default=DEFAULTS["systemd_dir"])
    args = parser.parse_args()

    paths = {
        "home": args.home,
        "env": args.env,
        "policy_bundle": args.policy_bundle,
        "projection_plan": args.projection_plan,
        "attestation_dir": args.attestation_dir,
        "status_snapshot": args.status_snapshot,
        "bpf_pin_root": args.bpf_pin_root,
        "systemd_dir": args.systemd_dir,
    }
    report = build_report(paths)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_text_report(report))
    return 0 if report["production_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
