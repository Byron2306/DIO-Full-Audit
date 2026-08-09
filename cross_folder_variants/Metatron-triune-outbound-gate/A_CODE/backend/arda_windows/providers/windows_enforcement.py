"""
WindowsPolicyEnforcementProvider
==================================
Implements PolicyEnforcementProvider using Windows-native enforcement APIs:

  • apply_posture  — WDAC (Windows Defender Application Control) via CiTool
                    with AppLocker GPO fallback
  • trust_workload — Add code integrity allow-rule for a signed identity
  • distrust_workload — Block/deny rule via AppLocker or Windows Firewall

All actions are logged via the Windows Event Log (Applications channel)
so that the constitutional layer has a durable audit trail.

On non-Windows hosts every method returns a no-op EnforcementResult with
provider="windows_enforcement_stub" so callers can detect simulation mode.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import EnforcementResult

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


def _run_ps(script: str, timeout: int = 20) -> Optional[str]:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("PowerShell unavailable: %s", exc)
    return None


def _log_enforcement_event(action: str, node_id: str, posture: str, success: bool) -> None:
    """Write a structured enforcement record to the Windows Application event log."""
    if not _IS_WINDOWS:
        return
    msg = (
        f"ARDA Enforcement | action={action} | node={node_id} | "
        f"posture={posture} | success={success} | "
        f"ts={datetime.now(timezone.utc).isoformat()}"
    )
    _run_ps(
        f"Write-EventLog -LogName Application -Source 'ARDA' "
        f"-EventId 9000 -EntryType Information -Message '{msg}' "
        f"-ErrorAction SilentlyContinue"
    )


# ---------------------------------------------------------------------------
# WDAC helpers
# ---------------------------------------------------------------------------

_WDAC_POSTURE_POLICY_IDS: Dict[str, str] = {
    "enforce":   "{A244370E-44C9-4C06-B551-F6016E563076}",  # AllowMicrosoft base policy
    "audit":     "{7E3B4B8E-5B93-4B29-A8CD-7A79A4C44AE2}",  # Audit-only policy
    "off":       "",  # sentinel: remove active policies
}


def _citool_apply_policy(policy_id: str) -> bool:
    """Activate a WDAC policy by GUID using CiTool (Windows 11 22H2+)."""
    if not policy_id:
        return False
    raw = _run_ps(f"CiTool --update-policy {policy_id} 2>&1", timeout=30)
    return raw is not None and "error" not in raw.lower()


def _applocker_set_enforcement(posture: str) -> bool:
    """
    Toggle AppLocker enforcement mode via GPO registry path.
    posture: 'enforce' | 'audit' | 'off'
    """
    # AppLocker enforcement level: 0=not configured, 1=enforce, 2=audit
    level_map = {"enforce": 1, "audit": 2, "off": 0}
    level = level_map.get(posture, 0)
    # Requires elevation; failure is non-fatal
    script = (
        f"$path = 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\SrpV2'; "
        f"if (-not (Test-Path $path)) {{ New-Item -Path $path -Force | Out-Null }}; "
        f"Set-ItemProperty -Path $path -Name 'EnforcementMode' -Value {level} -Type DWord"
    )
    raw = _run_ps(script, timeout=15)
    return raw is not None


# ---------------------------------------------------------------------------
# Firewall helpers
# ---------------------------------------------------------------------------

def _firewall_block_ip(remote_addr: str, direction: str = "Outbound") -> bool:
    script = (
        f"New-NetFirewallRule -DisplayName 'ARDA_BLOCK_{remote_addr.replace('.','_')}' "
        f"-Direction {direction} -RemoteAddress {remote_addr} "
        f"-Action Block -Profile Any -ErrorAction SilentlyContinue | Out-Null; "
        f"Write-Output 'ok'"
    )
    raw = _run_ps(script, timeout=15)
    return raw == "ok"


def _firewall_remove_block(remote_addr: str) -> bool:
    rule_name = f"ARDA_BLOCK_{remote_addr.replace('.', '_')}"
    script = (
        f"Remove-NetFirewallRule -DisplayName '{rule_name}' "
        f"-ErrorAction SilentlyContinue; Write-Output 'ok'"
    )
    raw = _run_ps(script, timeout=15)
    return raw == "ok"


# ---------------------------------------------------------------------------
# Defender helpers
# ---------------------------------------------------------------------------

def _defender_scan_path(path: str) -> bool:
    script = f"Start-MpScan -ScanPath '{path}' -ScanType CustomScan -ErrorAction SilentlyContinue"
    raw = _run_ps(script, timeout=60)
    return raw is not None


# ---------------------------------------------------------------------------
# WindowsPolicyEnforcementProvider
# ---------------------------------------------------------------------------

class WindowsPolicyEnforcementProvider:
    """
    Applies sovereignty posture to Windows nodes via WDAC + AppLocker + Firewall.

    Posture values understood by apply_posture():
      'enforce'  — activate WDAC enforce-mode policy, AppLocker enforce
      'audit'    — WDAC audit policy, AppLocker audit
      'quarantine' — block all outbound connections for node_id (IP-based)
      'off'      — remove ARDA-managed policies
    """

    PROVIDER_NAME = "windows_policy_enforcement"

    # -----------------------------------------------------------------------
    # apply_posture
    # -----------------------------------------------------------------------

    def apply_posture(
        self,
        node_id: str,
        posture: str,
        verdict: Dict[str, object],
    ) -> EnforcementResult:
        if not _IS_WINDOWS:
            return self._stub_result(posture, ["Non-Windows host: no-op"])

        actions: List[str] = []
        success = True

        if posture == "quarantine":
            # Quarantine: block outbound firewall for node IP
            node_ip = str(verdict.get("node_ip", node_id))
            ok = _firewall_block_ip(node_ip, direction="Outbound")
            actions.append(f"firewall_block_outbound:{node_ip}:{'ok' if ok else 'fail'}")
            # Also trigger a Defender scan if a path hint is present
            scan_path = str(verdict.get("scan_path", ""))
            if scan_path:
                _defender_scan_path(scan_path)
                actions.append(f"defender_scan:{scan_path}")
            success = ok

        elif posture in ("enforce", "audit", "off"):
            # WDAC
            policy_id = _WDAC_POSTURE_POLICY_IDS.get(posture, "")
            if policy_id:
                ok = _citool_apply_policy(policy_id)
                actions.append(f"wdac_policy:{posture}:{'ok' if ok else 'fail'}")
                if not ok:
                    success = False

            # AppLocker
            ok = _applocker_set_enforcement(posture)
            actions.append(f"applocker:{posture}:{'ok' if ok else 'fail'}")
            if not ok:
                success = False

        else:
            actions.append(f"unknown_posture:{posture}")
            success = False

        _log_enforcement_event("apply_posture", node_id, posture, success)
        return EnforcementResult(
            success=success,
            posture=posture,
            provider=self.PROVIDER_NAME,
            actions=actions,
            details={"node_id": node_id, "verdict_keys": list(verdict.keys())},
        )

    # -----------------------------------------------------------------------
    # trust_workload
    # -----------------------------------------------------------------------

    def trust_workload(self, identity: Dict[str, object]) -> EnforcementResult:
        """
        Add an allow rule for a workload identity.
        identity keys used:
          - publisher_name: str  (code-signing cert CN)
          - file_path: str       (optional; hash-based allow if present)
          - file_hash: str       (SHA-256 of the binary)
        """
        if not _IS_WINDOWS:
            return self._stub_result("trusted", ["Non-Windows host: no-op"])

        actions: List[str] = []
        success = True
        pub = str(identity.get("publisher_name", ""))
        file_hash = str(identity.get("file_hash", ""))
        file_path = str(identity.get("file_path", ""))

        if file_hash:
            # Hash-based AppLocker allow rule
            script = (
                f"$rule = New-AppLockerPolicy -FileInformation "
                f"  (Get-AppLockerFileInformation -Path '{file_path}') "
                f"-RuleType Hash -User Everyone -ErrorAction SilentlyContinue; "
                f"$rule | Set-AppLockerPolicy -Merge -ErrorAction SilentlyContinue; "
                f"Write-Output 'ok'"
            )
            raw = _run_ps(script, timeout=20)
            actions.append(f"applocker_hash_allow:{file_hash[:16]}…:{'ok' if raw=='ok' else 'fail'}")
            if raw != "ok":
                success = False

        if pub:
            # Publisher-based AppLocker allow rule (preferred — survives updates)
            script = (
                f"$rule = New-AppLockerPolicy -FileInformation "
                f"  (Get-AppLockerFileInformation -Path '{file_path}') "
                f"-RuleType Publisher -User Everyone -ErrorAction SilentlyContinue; "
                f"$rule | Set-AppLockerPolicy -Merge -ErrorAction SilentlyContinue; "
                f"Write-Output 'ok'"
            )
            raw = _run_ps(script, timeout=20)
            actions.append(f"applocker_publisher_allow:{pub}:{'ok' if raw=='ok' else 'fail'}")
            if raw != "ok":
                success = False

        node_id = file_path or pub or "unknown"
        _log_enforcement_event("trust_workload", node_id, "trusted", success)
        return EnforcementResult(
            success=success,
            posture="trusted",
            provider=self.PROVIDER_NAME,
            actions=actions,
            details=dict(identity),
        )

    # -----------------------------------------------------------------------
    # distrust_workload
    # -----------------------------------------------------------------------

    def distrust_workload(self, identity: Dict[str, object]) -> EnforcementResult:
        """
        Block a workload: deny AppLocker rule + optional firewall block.
        identity keys:
          - publisher_name: str
          - file_path: str
          - file_hash: str
          - remote_ip: str  (optional; blocks outbound to that IP)
        """
        if not _IS_WINDOWS:
            return self._stub_result("distrusted", ["Non-Windows host: no-op"])

        actions: List[str] = []
        success = True
        file_path = str(identity.get("file_path", ""))
        file_hash = str(identity.get("file_hash", ""))
        remote_ip = str(identity.get("remote_ip", ""))

        if file_path or file_hash:
            # Deny rule via AppLocker
            script = (
                f"$rule = New-AppLockerPolicy -FileInformation "
                f"  (Get-AppLockerFileInformation -Path '{file_path}') "
                f"-RuleType Hash -User Everyone -DenyRule "
                f"-ErrorAction SilentlyContinue; "
                f"$rule | Set-AppLockerPolicy -Merge -ErrorAction SilentlyContinue; "
                f"Write-Output 'ok'"
            )
            raw = _run_ps(script, timeout=20)
            actions.append(f"applocker_deny:{file_hash[:16] if file_hash else file_path}:{'ok' if raw=='ok' else 'fail'}")
            if raw != "ok":
                success = False

        if remote_ip:
            ok = _firewall_block_ip(remote_ip)
            actions.append(f"firewall_block:{remote_ip}:{'ok' if ok else 'fail'}")
            if not ok:
                success = False

        # Request Defender quarantine scan if path present
        if file_path:
            _defender_scan_path(file_path)
            actions.append(f"defender_scan:{file_path}")

        node_id = file_path or remote_ip or "unknown"
        _log_enforcement_event("distrust_workload", node_id, "distrusted", success)
        return EnforcementResult(
            success=success,
            posture="distrusted",
            provider=self.PROVIDER_NAME,
            actions=actions,
            details=dict(identity),
        )

    # -----------------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _stub_result(posture: str, actions: List[str]) -> EnforcementResult:
        return EnforcementResult(
            success=False,
            posture=posture,
            provider="windows_enforcement_stub",
            actions=actions,
            details={"stub": True},
        )
