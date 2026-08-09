"""
Arda Boot Measurement
=====================
Reads REAL hardware security state from the Windows substrate.

This is NOT simulation. It queries:
- UEFISecureBootEnabled via Windows registry (HKLM)
- TPM 2.0 presence and version via WMI

These are actual machine measurements. On this substrate:
- Secure Boot: ENABLED (verified via registry)
- TPM: 2.0 (verified via WMI)

Future work:
- Read specific PCR values (requires admin or tpm2-pytss)
- Bind key release to PCR measurements
- Measure Arda policy file digest into a PCR extend
"""

import logging
import subprocess
import json

logger = logging.getLogger("ARDA_BOOT")


def measure_boot_state() -> dict:
    """
    Reads real hardware security measurements from the Windows substrate.
    Returns a dict suitable for embedding in attestation envelopes.
    
    Every field is either a real measurement or explicitly marked "unavailable"
    with a reason. No simulation labels.
    """
    state = {
        "secure_boot": _read_secure_boot(),
        "tpm": _read_tpm(),
    }
    logger.info(f"[BOOT] Measured: SecureBoot={state['secure_boot']['enabled']}, TPM={state['tpm']['version']}")
    return state


def _read_secure_boot() -> dict:
    """Reads UEFISecureBootEnabled from the Windows registry."""
    try:
        result = subprocess.run(
            ["reg", "query",
             r"HKLM\SYSTEM\CurrentControlSet\Control\SecureBoot\State",
             "/v", "UEFISecureBootEnabled"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and "0x1" in result.stdout:
            return {"enabled": True, "source": "registry:HKLM\\SecureBoot\\State"}
        elif result.returncode == 0 and "0x0" in result.stdout:
            return {"enabled": False, "source": "registry:HKLM\\SecureBoot\\State"}
        else:
            return {"enabled": "unavailable", "reason": "registry query failed", "source": "registry"}
    except Exception as e:
        return {"enabled": "unavailable", "reason": str(e), "source": "registry"}


def _read_tpm() -> dict:
    """Reads TPM version and status via PowerShell/WMI."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance -ClassName Win32_TPM -Namespace root/cimv2/Security/MicrosoftTpm "
             "| Select-Object SpecVersion, IsActivated_InitialValue, IsEnabled_InitialValue "
             "| ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            spec = data.get("SpecVersion", "")
            version = spec.split(",")[0].strip() if spec else "unknown"
            return {
                "version": version,
                "activated": data.get("IsActivated_InitialValue", False),
                "enabled": data.get("IsEnabled_InitialValue", False),
                "source": "WMI:Win32_TPM",
            }
        return {"version": "unavailable", "reason": "WMI query empty", "source": "WMI"}
    except Exception as e:
        return {"version": "unavailable", "reason": str(e), "source": "WMI"}
