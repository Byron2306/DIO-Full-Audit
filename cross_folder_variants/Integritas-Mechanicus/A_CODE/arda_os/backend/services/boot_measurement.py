import json
import os
from typing import Any, Dict


SECURE_BOOT_EFIVAR = "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
SETUP_MODE_EFIVAR = "/sys/firmware/efi/efivars/SetupMode-8be4df61-93ca-11d2-aa0d-00e098032b8c"


def _read_efivar_flag(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"available": False, "enabled": None, "source": path}

    with open(path, "rb") as handle:
        payload = handle.read()
    enabled = bool(payload[4]) if len(payload) >= 5 else None
    return {"available": True, "enabled": enabled, "source": path}


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _safe_text(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"available": False, "value": None, "source": path}
    try:
        return {"available": True, "value": _read_text(path), "source": path}
    except Exception as error:
        return {"available": True, "value": None, "source": path, "error": str(error)}


def classify_boot_state(measurement: Dict[str, Any]) -> str:
    secure_boot_enabled = bool(measurement.get("secure_boot", {}).get("enabled"))
    setup_mode_disabled = measurement.get("setup_mode", {}).get("enabled") is False
    lockdown_mode = (measurement.get("lockdown", {}).get("value") or "").lower()
    active_lsms = (measurement.get("active_lsms", {}).get("value") or "").lower()
    pcrs = measurement.get("pcrs", {})
    required_pcrs_present = all(pcrs.get(index) for index in ("0", "1", "7", "11"))

    lawful_signals = 0
    if secure_boot_enabled:
        lawful_signals += 1
    if setup_mode_disabled:
        lawful_signals += 1
    if "integrity" in lockdown_mode or "confidentiality" in lockdown_mode:
        lawful_signals += 1
    if any(lsm in active_lsms for lsm in ("ima", "evm", "bpf")):
        lawful_signals += 1
    if required_pcrs_present:
        lawful_signals += 1

    if lawful_signals >= 4 and secure_boot_enabled and required_pcrs_present:
        return "LAWFUL_FULL"
    if lawful_signals >= 2 and (secure_boot_enabled or required_pcrs_present):
        return "LAWFUL_PARTIAL"
    return "ATTESTED_ONLY"


def measure_boot_state(*, pcrs: Dict[str, str] | None = None) -> Dict[str, Any]:
    measurement = {
        "source": "linux_host_measurement_v1",
        "secure_boot": _read_efivar_flag(SECURE_BOOT_EFIVAR),
        "setup_mode": _read_efivar_flag(SETUP_MODE_EFIVAR),
        "lockdown": _safe_text("/sys/kernel/security/lockdown"),
        "active_lsms": _safe_text("/sys/kernel/security/lsm"),
        "kernel_cmdline": _safe_text("/proc/cmdline"),
        "kernel_release": _safe_text("/proc/sys/kernel/osrelease"),
        "pcrs": {str(key): str(value).lower() for key, value in (pcrs or {}).items()},
    }
    measurement["classification"] = classify_boot_state(measurement)
    return measurement


def read_sealed_secret_bundle(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
