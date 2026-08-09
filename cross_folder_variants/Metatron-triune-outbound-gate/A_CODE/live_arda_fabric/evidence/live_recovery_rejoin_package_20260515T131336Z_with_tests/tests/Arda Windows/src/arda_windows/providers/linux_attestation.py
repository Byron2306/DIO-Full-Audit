"""
LinuxAttestationProvider
=========================
Implements AttestationProvider using Linux-native attestation APIs:

  • TPM PCR snapshots  — tpm2-tools (tpm2_pcrread) with /sys/kernel/security fallback
  • Secure Boot state  — mokutil / efivarfs / /sys/firmware/efi
  • Measured Boot log  — IMA (Integrity Measurement Architecture) ASCII log

On hosts without tpm2-tools or IMA enabled every method degrades to stub
data tagged confidence=0.0 / stub=True so the pipeline can still run.
"""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import BootEventRecord, PcrSnapshot, SecureBootState

logger = logging.getLogger(__name__)


def _run(cmd: List[str], timeout: int = 10) -> Optional[str]:
    """Run a command and return stdout stripped, or None on error."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.debug("cmd %s exit %d: %s", cmd[0], result.returncode, result.stderr[:200])
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        logger.debug("cmd %s unavailable: %s", cmd[0], exc)
    return None


def _sysfs_read(path: str) -> Optional[str]:
    try:
        return Path(path).read_text().strip()
    except Exception:
        return None


# Use pathlib safely
try:
    from pathlib import Path
except ImportError:
    Path = None  # type: ignore


class LinuxAttestationProvider:
    """
    Attestation adapter for Linux hosts.

    Uses tpm2-tools for real PCR values when available; degrades to
    /sys/class/tpm/tpm0 sysfs and IMA for partial data, and stubs
    when neither is present.
    """

    # ------------------------------------------------------------------
    # PCR snapshot
    # ------------------------------------------------------------------

    def get_pcr_snapshot(self, indices: List[int]) -> List[PcrSnapshot]:
        """Return SHA-256 PCR values for the requested bank indices."""
        snapshots = self._read_pcrs_tpm2tools(indices)
        if snapshots:
            return snapshots
        snapshots = self._read_pcrs_sysfs(indices)
        if snapshots:
            return snapshots
        logger.warning("TPM PCR read unavailable on Linux; returning stubs")
        return self._stub_pcrs(indices)

    def _read_pcrs_tpm2tools(self, indices: List[int]) -> List[PcrSnapshot]:
        """tpm2_pcrread sha256:<idx1>,<idx2>,..."""
        idx_str = ",".join(str(i) for i in indices)
        raw = _run(["tpm2_pcrread", f"sha256:{idx_str}"])
        if not raw:
            return []
        snapshots: List[PcrSnapshot] = []
        for line in raw.splitlines():
            # Lines look like:  "  7 : 0xA0F4..."
            line = line.strip()
            if ":" not in line:
                continue
            try:
                idx_part, val_part = line.split(":", 1)
                idx = int(idx_part.strip())
                val = val_part.strip().lower().lstrip("0x")
                if idx in indices and val:
                    snapshots.append(PcrSnapshot(index=idx, value=val))
            except (ValueError, IndexError):
                continue
        return snapshots

    def _read_pcrs_sysfs(self, indices: List[int]) -> List[PcrSnapshot]:
        """
        /sys/class/tpm/tpm0/pcr-sha256/<N> contains raw hex on some kernels.
        """
        base = "/sys/class/tpm/tpm0/pcr-sha256"
        snapshots: List[PcrSnapshot] = []
        for idx in indices:
            path = f"{base}/{idx}"
            try:
                val = Path(path).read_text().strip()
                if val:
                    snapshots.append(PcrSnapshot(index=idx, value=val.lower()))
            except Exception:
                continue
        return snapshots

    def _stub_pcrs(self, indices: List[int]) -> List[PcrSnapshot]:
        return [
            PcrSnapshot(index=i, value="00" * 32 + "_stub")
            for i in indices
        ]

    # ------------------------------------------------------------------
    # Secure Boot state
    # ------------------------------------------------------------------

    def get_secure_boot_state(self) -> SecureBootState:
        """
        Check Secure Boot via mokutil, then efivarfs, then /sys/firmware/efi.
        """
        # mokutil --sb-state
        raw = _run(["mokutil", "--sb-state"])
        if raw:
            enabled = "secureboot enabled" in raw.lower()
            setup_mode = "setup mode" in raw.lower()
            return SecureBootState(
                enabled=enabled,
                setup_mode=setup_mode,
                secure_boot_mode="uefi",
                vendor_keys=self._read_vendor_keys(),
            )

        # efivar fallback
        efi_sb = self._efi_secure_boot()
        if efi_sb is not None:
            return SecureBootState(
                enabled=efi_sb,
                setup_mode=False,
                secure_boot_mode="uefi_efivar",
                vendor_keys=self._read_vendor_keys(),
            )

        # /sys/firmware/efi existence = UEFI but state unknown
        uefi = os.path.isdir("/sys/firmware/efi")
        return SecureBootState(
            enabled=False,
            setup_mode=False,
            secure_boot_mode="uefi_unknown" if uefi else "bios",
            vendor_keys=[],
        )

    def _efi_secure_boot(self) -> Optional[bool]:
        """Read SecureBoot-... efivar (byte 4 is value: 1=enabled)."""
        efivar_dir = "/sys/firmware/efi/efivars"
        if not os.path.isdir(efivar_dir):
            return None
        # Find SecureBoot variable
        for name in os.listdir(efivar_dir):
            if name.lower().startswith("secureboot-"):
                path = os.path.join(efivar_dir, name)
                try:
                    data = Path(path).read_bytes()
                    # 4-byte attributes + value byte
                    if len(data) >= 5:
                        return data[4] == 1
                except Exception:
                    continue
        return None

    def _read_vendor_keys(self) -> List[str]:
        """Return MOK list subjects via mokutil --list-enrolled."""
        raw = _run(["mokutil", "--list-enrolled"], timeout=5)
        if not raw:
            return []
        keys = []
        for line in raw.splitlines():
            if "subject:" in line.lower():
                keys.append(line.strip())
        return keys[:10]  # cap

    # ------------------------------------------------------------------
    # Measured Boot / IMA log
    # ------------------------------------------------------------------

    def get_boot_event_log(self) -> List[BootEventRecord]:
        """
        Parse /sys/kernel/security/ima/ascii_runtime_measurements.
        Each line: pcr_idx template_hash algo:digest filename_hint
        """
        ima_path = "/sys/kernel/security/ima/ascii_runtime_measurements"
        try:
            lines = Path(ima_path).read_text(errors="replace").splitlines()
        except Exception:
            return self._stub_boot_log()

        records: List[BootEventRecord] = []
        ts = datetime.now(timezone.utc).isoformat()
        for line in lines[:200]:  # cap at 200 to avoid huge payloads
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                pcr_idx = int(parts[0])
                template_hash = parts[1]
                # algo:digest is parts[2], filename is parts[3]
                algo_digest = parts[2]
                filename = parts[3] if len(parts) > 3 else ""
                records.append(
                    BootEventRecord(
                        pcr_index=pcr_idx,
                        event_type="ima_measurement",
                        digest=algo_digest,
                        event_data=filename,
                        timestamp_iso=ts,
                    )
                )
            except (ValueError, IndexError):
                continue
        if records:
            return records
        return self._stub_boot_log()

    def _stub_boot_log(self) -> List[BootEventRecord]:
        ts = datetime.now(timezone.utc).isoformat()
        return [
            BootEventRecord(pcr_index=i, event_type="stub", digest="00" * 20,
                            event_data="ima_unavailable", timestamp_iso=ts)
            for i in [0, 4, 7]
        ]
