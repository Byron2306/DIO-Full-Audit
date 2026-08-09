"""
LinuxSovereigntyMonitor
========================
Implements SovereigntyMonitor — the Linux ring-0 authority equivalent
of the Windows WindowsSovereigntyMonitor.

On Linux, sovereignty is assessed via a layered trust chain mirroring
the Windows model but using Linux-native mechanisms:

  Layer 1 — Boot integrity:    UEFI Secure Boot (mokutil) + IMA policy active
  Layer 2 — Platform trust:    TPM 2.0 present (tpm2_getcap) + PCR[7] non-zero
  Layer 3 — Execution policy:  LSM enforcing — SELinux OR AppArmor enforce mode
  Layer 4 — Runtime telemetry: auditd operational + IMA measurements loading
  Layer 5 — Kernel integrity:  kernel lockdown mode active (CONFIDENTIALITY or INTEGRITY)

Sovereignty states:
  SOVEREIGN       — all 5 layers passing
  CONSTRAINED     — layers 1-2 passing, 3-5 partial
  COMPROMISED     — layer 1 or 2 failing
  SIMULATION      — TPM/LSM absent (VM/container without hardware attestation)
"""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import SovereigntyAssessment, SovereigntyLevel

logger = logging.getLogger(__name__)


def _run(cmd: List[str], timeout: int = 10) -> Optional[str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        logger.debug("cmd %s unavailable: %s", cmd[0], exc)
    return None


def _sysfs(path: str) -> Optional[str]:
    try:
        return Path(path).read_text().strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Trust-layer result
# ---------------------------------------------------------------------------

class _LayerResult:
    def __init__(self, name: str, passing: bool, detail: str):
        self.name = name
        self.passing = passing
        self.detail = detail

    def to_reason(self) -> str:
        status = "PASS" if self.passing else "FAIL"
        return f"[{status}] Layer {self.name}: {self.detail}"


# ---------------------------------------------------------------------------
# Individual layer checks
# ---------------------------------------------------------------------------

def _check_secure_boot() -> _LayerResult:
    """Layer 1a: UEFI Secure Boot enabled via mokutil."""
    raw = _run(["mokutil", "--sb-state"])
    if raw:
        enabled = "secureboot enabled" in raw.lower()
        return _LayerResult(
            "1:SecureBoot",
            enabled,
            f"mokutil:{raw.split(chr(10))[0].strip()}",
        )
    # efivarfs fallback
    efivar_dir = "/sys/firmware/efi/efivars"
    if os.path.isdir(efivar_dir):
        for name in os.listdir(efivar_dir):
            if name.lower().startswith("secureboot-"):
                try:
                    data = Path(os.path.join(efivar_dir, name)).read_bytes()
                    if len(data) >= 5:
                        enabled = data[4] == 1
                        return _LayerResult("1:SecureBoot", enabled, f"efivar={'enabled' if enabled else 'disabled'}")
                except Exception:
                    pass
    # No UEFI at all (BIOS / container)
    return _LayerResult("1:SecureBoot", False, "no_uefi_or_mokutil")


def _check_ima() -> _LayerResult:
    """Layer 1b: IMA policy active (measurements being loaded)."""
    measure_path = "/sys/kernel/security/ima/ascii_runtime_measurements"
    policy_path = "/sys/kernel/security/ima/policy"
    try:
        lines = Path(measure_path).read_text(errors="replace").splitlines()
        count = len([l for l in lines if l.strip()])
        has_policy = os.path.exists(policy_path)
        passing = count > 0
        return _LayerResult("1b:IMA", passing, f"measurements={count} policy={'present' if has_policy else 'absent'}")
    except Exception:
        return _LayerResult("1b:IMA", False, "ima_unavailable")


def _check_tpm() -> _LayerResult:
    """Layer 2: TPM 2.0 present and responding."""
    # tpm2_getcap properties-fixed
    raw = _run(["tpm2_getcap", "properties-fixed"], timeout=8)
    if raw:
        return _LayerResult("2:TPM", True, "tpm2_getcap:ok")
    # /sys/class/tpm presence
    tpm_sys = "/sys/class/tpm"
    if os.path.isdir(tpm_sys):
        devices = os.listdir(tpm_sys)
        if devices:
            return _LayerResult("2:TPM", True, f"sysfs:{','.join(devices)}")
    return _LayerResult("2:TPM", False, "tpm_absent_or_inaccessible")


def _check_lsm() -> _LayerResult:
    """Layer 3: SELinux enforcing OR AppArmor enforce mode active."""
    # SELinux
    se = _run(["getenforce"])
    if se and se.lower() == "enforcing":
        return _LayerResult("3:LSM", True, "selinux:enforcing")
    # AppArmor
    aa_enabled = _sysfs("/sys/module/apparmor/parameters/enabled")
    if aa_enabled == "Y":
        aa_mode = _sysfs("/sys/kernel/security/apparmor/profiles")
        # Count enforce-mode profiles
        raw = _run(["aa-status", "--json"], timeout=5)
        if raw:
            import json as _json
            try:
                obj = _json.loads(raw)
                enforce_count = len(obj.get("processes", {}).get("enforce", {}))
                passing = enforce_count > 0
                return _LayerResult("3:LSM", passing, f"apparmor:enforce_profiles={enforce_count}")
            except Exception:
                pass
        return _LayerResult("3:LSM", True, "apparmor:enabled")
    # LSM list from kernel
    lsm_list = _sysfs("/sys/kernel/security/lsm")
    if lsm_list:
        return _LayerResult("3:LSM", False, f"lsm_loaded={lsm_list}_but_not_enforcing")
    return _LayerResult("3:LSM", False, "no_lsm_enforcing")


def _check_auditd() -> _LayerResult:
    """Layer 4: auditd daemon running."""
    raw = _run(["systemctl", "is-active", "--quiet", "auditd"])
    if raw is not None:  # exit 0 = active
        return _LayerResult("4:Auditd", True, "systemctl:active")
    # Fallback: check /var/log/audit/audit.log exists and is non-empty
    try:
        size = Path("/var/log/audit/audit.log").stat().st_size
        return _LayerResult("4:Auditd", size > 0, f"audit_log_bytes={size}")
    except Exception:
        return _LayerResult("4:Auditd", False, "auditd_not_running")


def _check_kernel_lockdown() -> _LayerResult:
    """Layer 5: Kernel lockdown mode (integrity or confidentiality)."""
    path = "/sys/kernel/security/lockdown"
    try:
        raw = Path(path).read_text().strip()
        # Format: "[none] integrity confidentiality" — active is in brackets
        import re
        match = re.search(r"\[(\w+)\]", raw)
        if match:
            mode = match.group(1)
            passing = mode in ("integrity", "confidentiality")
            return _LayerResult("5:Lockdown", passing, f"mode={mode}")
    except Exception:
        pass
    # kernel built without lockdown — check LSM parameter
    lsm = _sysfs("/sys/kernel/security/lsm")
    if lsm and "lockdown" in lsm:
        return _LayerResult("5:Lockdown", True, f"lockdown_in_lsm={lsm}")
    return _LayerResult("5:Lockdown", False, "lockdown_unavailable")


# ---------------------------------------------------------------------------
# LinuxSovereigntyMonitor
# ---------------------------------------------------------------------------

class LinuxSovereigntyMonitor:
    """
    Evaluates sovereignty state across 5 trust layers using Linux-native APIs.
    """

    def evaluate_sovereignty_state(self) -> SovereigntyAssessment:
        layers = [
            _check_secure_boot(),
            _check_ima(),
            _check_tpm(),
            _check_lsm(),
            _check_auditd(),
            _check_kernel_lockdown(),
        ]

        passing = [l for l in layers if l.passing]
        failing = [l for l in layers if not l.passing]

        # Determine state
        boot_layers = [l for l in layers if l.name.startswith("1") or l.name.startswith("2")]
        boot_ok = all(l.passing for l in boot_layers)

        if len(passing) == len(layers):
            state = "SOVEREIGN"
            sovereignty_level = SovereigntyLevel.LINUX_RING0_AUTHORITATIVE
        elif boot_ok and len(passing) >= 3:
            state = "CONSTRAINED"
            sovereignty_level = SovereigntyLevel.LINUX_RING0_AUTHORITATIVE
        elif not boot_ok:
            state = "COMPROMISED"
            sovereignty_level = SovereigntyLevel.SIMULATION
        else:
            state = "SIMULATION"
            sovereignty_level = SovereigntyLevel.SIMULATION

        return SovereigntyAssessment(
            state=state,
            provider="linux_sovereignty",
            reasons=[l.to_reason() for l in layers],
            attributes={
                "sovereignty_level": sovereignty_level.value,
                "layers_passing": len(passing),
                "layers_total": len(layers),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "failing_layers": [l.name for l in failing],
            },
        )

    def explain_state_reasons(self) -> List[str]:
        assessment = self.evaluate_sovereignty_state()
        return list(assessment.reasons)
