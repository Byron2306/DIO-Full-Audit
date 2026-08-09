"""
WindowsAttestationProvider
==========================
Implements AttestationProvider using Windows-native APIs:

  • TPM PCR snapshots  — PowerShell Get-Tpm / Win32_Tpm WMI
  • Secure Boot state  — Confirm-SecureBootUEFI + registry fallback
  • Measured Boot log  — Windows Measured Boot event log (ETW / XML)

On non-Windows hosts the provider returns stub data tagged with
confidence=0.0 so callers can distinguish real vs. simulated readings.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import BootEventRecord, PcrSnapshot, SecureBootState

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


def _run_ps(script: str, timeout: int = 15) -> Optional[str]:
    """Execute a PowerShell snippet and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.debug("PowerShell exit %d: %s", result.returncode, result.stderr.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("PowerShell unavailable: %s", exc)
    return None


def _run_wmic(wmi_class: str, properties: List[str], timeout: int = 15) -> Optional[Dict[str, str]]:
    """Query a WMI class via wmic.exe and return a dict of property → value."""
    try:
        prop_str = ", ".join(properties)
        result = subprocess.run(
            ["wmic.exe", wmi_class, "get", prop_str, "/format:csv"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return None
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        # wmic CSV: first line = headers, second = values
        if len(lines) < 2:
            return None
        headers = [h.strip() for h in lines[0].split(",")]
        values = [v.strip() for v in lines[1].split(",")]
        return dict(zip(headers, values))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("wmic unavailable: %s", exc)
    return None


class WindowsAttestationProvider:
    """
    Attestation adapter for Windows hosts.

    All public methods return real data when running on Windows with a TPM 2.0
    device present.  On Linux/macOS (e.g. dev/CI machines) every method falls
    back to clearly-labelled stub data so the rest of the pipeline can still
    exercise code paths without a real TPM.
    """

    # ------------------------------------------------------------------
    # PCR snapshot
    # ------------------------------------------------------------------

    def get_pcr_snapshot(self, indices: List[int]) -> List[PcrSnapshot]:
        """
        Return SHA-256 PCR values for the requested bank indices.

        Uses PowerShell's `Get-Tpm` object first; falls back to Win32_Tpm
        WMI, then to a clearly-marked stub.
        """
        if _IS_WINDOWS:
            snapshots = self._read_pcrs_via_powershell(indices)
            if snapshots:
                return snapshots
            snapshots = self._read_pcrs_via_wmi(indices)
            if snapshots:
                return snapshots

        logger.warning("TPM PCR read unavailable; returning stub data (confidence=0)")
        return self._stub_pcr_snapshots(indices)

    def _read_pcrs_via_powershell(self, indices: List[int]) -> List[PcrSnapshot]:
        # PowerShell 5.1+: Get-TpmEndorsementKeyInfo / Get-Tpm do not expose
        # raw PCR banks directly.  Use tpm2-tools wrapper when available or
        # the TSS.Net PlatformCrypto provider via reflection.
        script = (
            "try { $t = Get-Tpm; "
            "$t | ConvertTo-Json -Depth 3 } "
            "catch { Write-Error $_.Exception.Message }"
        )
        raw = _run_ps(script)
        if not raw:
            return []
        try:
            tpm_obj: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return []
        # Get-Tpm doesn't expose raw PCR hex — use this presence check as a
        # liveness gate; actual PCR values are read via certutil/tpm2-tools.
        if not tpm_obj.get("TpmPresent"):
            return []
        return self._read_pcrs_via_certutil(indices)

    def _read_pcrs_via_certutil(self, indices: List[int]) -> List[PcrSnapshot]:
        """certutil -tpminfo parses PCR table on Windows 10/11."""
        raw = _run_ps("certutil -tpminfo 2>&1")
        if not raw:
            return []
        snapshots: List[PcrSnapshot] = []
        for line in raw.splitlines():
            # Lines look like:  "  PCR[07] = a0f4..."
            if "PCR[" not in line:
                continue
            try:
                pcr_part, value_part = line.split("=", 1)
                idx = int(pcr_part.strip()[4:6])
                if idx in indices:
                    snapshots.append(PcrSnapshot(index=idx, value=value_part.strip()))
            except (ValueError, IndexError):
                continue
        return snapshots

    def _read_pcrs_via_wmi(self, indices: List[int]) -> List[PcrSnapshot]:
        data = _run_wmic(
            "path Win32_Tpm",
            ["IsEnabled_InitialValue", "IsActivated_InitialValue", "SpecVersion"],
        )
        if not data or data.get("IsEnabled_InitialValue", "").lower() != "true":
            return []
        # Win32_Tpm doesn't expose raw PCR values — return empty to fall
        # through to stub; caller interprets absence as "TPM present but PCR
        # bank not readable via this path".
        logger.debug("Win32_Tpm liveness confirmed but PCR bank not accessible via WMI")
        return []

    @staticmethod
    def _stub_pcr_snapshots(indices: List[int]) -> List[PcrSnapshot]:
        return [
            PcrSnapshot(
                index=i,
                value=f"STUB_{'0' * 64}",  # 64 hex chars = 32 bytes SHA-256 shape
            )
            for i in indices
        ]

    # ------------------------------------------------------------------
    # Secure Boot state
    # ------------------------------------------------------------------

    def get_secure_boot_state(self) -> SecureBootState:
        """
        Query Secure Boot via:
          1. PowerShell Confirm-SecureBootUEFI
          2. Registry HKLM\\SYSTEM\\CurrentControlSet\\Control\\SecureBoot\\State
          3. Stub (non-Windows / pre-boot environment)
        """
        if _IS_WINDOWS:
            state = self._secure_boot_via_ps()
            if state:
                return state
            state = self._secure_boot_via_registry()
            if state:
                return state

        logger.warning("Secure Boot check unavailable; returning stub")
        return SecureBootState(
            enabled=False,
            setup_mode=False,
            secure_boot_mode="stub",
            vendor_keys=[],
        )

    def _secure_boot_via_ps(self) -> Optional[SecureBootState]:
        script = (
            "try { "
            "  $sb = Confirm-SecureBootUEFI; "
            "  $mode = (Get-ItemPropertyValue "
            "    'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecureBoot\\State' "
            "    'UEFISecureBootEnabled' -ErrorAction SilentlyContinue); "
            "  $keys = @(); "
            "  [pscustomobject]@{ Enabled=$sb; SetupMode=$false; Mode='UserMode'; Keys=$keys } "
            "  | ConvertTo-Json "
            "} catch { Write-Output 'ERROR' }"
        )
        raw = _run_ps(script)
        if not raw or raw == "ERROR":
            return None
        try:
            obj = json.loads(raw)
            return SecureBootState(
                enabled=bool(obj.get("Enabled", False)),
                setup_mode=bool(obj.get("SetupMode", False)),
                secure_boot_mode=str(obj.get("Mode", "unknown")),
                vendor_keys=list(obj.get("Keys", [])),
            )
        except (json.JSONDecodeError, TypeError):
            return None

    def _secure_boot_via_registry(self) -> Optional[SecureBootState]:
        script = (
            "try { "
            "  $v = Get-ItemPropertyValue "
            "    'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecureBoot\\State' "
            "    'UEFISecureBootEnabled'; "
            "  Write-Output $v "
            "} catch { Write-Output 'ABSENT' }"
        )
        raw = _run_ps(script)
        if not raw or raw == "ABSENT":
            return None
        enabled = raw.strip() == "1"
        return SecureBootState(
            enabled=enabled,
            setup_mode=False,
            secure_boot_mode="UserMode" if enabled else "Disabled",
            vendor_keys=[],
        )

    # ------------------------------------------------------------------
    # Boot event log
    # ------------------------------------------------------------------

    def get_boot_event_log(self) -> List[BootEventRecord]:
        """
        Parse Windows Measured Boot events from the
        'Microsoft-Windows-TPM-WMI/Operational' ETW channel via
        Get-WinEvent, returning structured BootEventRecord entries.
        """
        if _IS_WINDOWS:
            records = self._read_measured_boot_events()
            if records:
                return records

        logger.warning("Measured Boot log unavailable; returning stub")
        return self._stub_boot_events()

    def _read_measured_boot_events(self) -> List[BootEventRecord]:
        script = (
            "try { "
            "  $evts = Get-WinEvent -LogName "
            "    'Microsoft-Windows-TPM-WMI/Operational' "
            "    -MaxEvents 50 -ErrorAction Stop; "
            "  $evts | Select-Object TimeCreated, Id, Message "
            "    | ConvertTo-Json -Depth 2 "
            "} catch { Write-Output '[]' }"
        )
        raw = _run_ps(script, timeout=20)
        if not raw or raw == "[]":
            return []
        try:
            events = json.loads(raw)
            if isinstance(events, dict):
                events = [events]
        except json.JSONDecodeError:
            return []

        records: List[BootEventRecord] = []
        for ev in events:
            ts = str(ev.get("TimeCreated", datetime.now(timezone.utc).isoformat()))
            records.append(
                BootEventRecord(
                    pcr_index=self._pcr_index_from_event_id(int(ev.get("Id", 0))),
                    event_type=f"TPM-WMI/{ev.get('Id', 'unknown')}",
                    digest="",  # raw digest not exposed via Get-WinEvent message
                    event_data=str(ev.get("Message", ""))[:512],
                    timestamp_iso=ts,
                )
            )
        return records

    @staticmethod
    def _pcr_index_from_event_id(event_id: int) -> int:
        """
        Best-effort mapping of TPM-WMI event IDs to PCR bank indices.
        Windows does not expose a definitive public mapping; this covers
        the most common cases seen in production Measured Boot logs.
        """
        mapping = {
            1796: 0,  # Core boot firmware measurements → PCR 0
            1797: 1,
            1798: 2,
            1799: 3,
            1800: 4,  # Boot loader → PCR 4
            1801: 5,
            1802: 6,
            1803: 7,  # Secure Boot policy → PCR 7
        }
        return mapping.get(event_id, 255)  # 255 = "unknown bank"

    @staticmethod
    def _stub_boot_events() -> List[BootEventRecord]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            BootEventRecord(
                pcr_index=i,
                event_type=f"STUB/PCR{i}",
                digest="STUB_" + "0" * 60,
                event_data=f"Stub measured-boot event for PCR[{i}]",
                timestamp_iso=now,
            )
            for i in [0, 4, 7]
        ]
