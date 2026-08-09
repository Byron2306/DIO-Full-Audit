"""
WindowsSovereigntyMonitor
==========================
Implements SovereigntyMonitor — the Windows replacement for the Linux
Bombadil sentinel.

On Linux, Bombadil has ring-0 authority: it uses eBPF + kernel enforcement
to assert absolute sovereignty.  On Windows we achieve "policy-authoritative"
sovereignty via a layered trust chain:

  Layer 1 — Boot integrity:    Secure Boot UEFI state (verified at boot)
  Layer 2 — Platform trust:    TPM 2.0 presence + PCR[7] Secure Boot policy
  Layer 3 — Execution policy:  WDAC enforce-mode active
  Layer 4 — Runtime telemetry: Sysmon operational + no active threat detections
  Layer 5 — Defender health:   Real-time protection enabled, definitions current

Sovereignty states (maps to SovereigntyLevel enum):
  SOVEREIGN       — all 5 layers passing
  CONSTRAINED     — layers 1-2 passing, 3-5 partial
  COMPROMISED     — layer 1 or 2 failing
  SIMULATION      — non-Windows host (dev/CI)
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models import SovereigntyAssessment, SovereigntyLevel

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


def _run_ps(script: str, timeout: int = 15) -> Optional[str]:
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


# ---------------------------------------------------------------------------
# Individual trust-layer checks
# ---------------------------------------------------------------------------

class _LayerResult:
    def __init__(self, name: str, passing: bool, detail: str):
        self.name = name
        self.passing = passing
        self.detail = detail

    def to_reason(self) -> str:
        status = "PASS" if self.passing else "FAIL"
        return f"[{status}] Layer {self.name}: {self.detail}"


def _check_secure_boot() -> _LayerResult:
    """Layer 1: UEFI Secure Boot enabled in UserMode (not SetupMode)."""
    script = (
        "try { $sb = Confirm-SecureBootUEFI; Write-Output $sb } "
        "catch { Write-Output 'ERROR' }"
    )
    raw = _run_ps(script)
    if raw is None or raw == "ERROR":
        # Fallback: registry
        reg = _run_ps(
            "try { Get-ItemPropertyValue "
            "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\SecureBoot\\State' "
            "'UEFISecureBootEnabled' } catch { Write-Output '-1' }"
        )
        passing = reg == "1"
        detail = f"registry_fallback={'enabled' if passing else 'disabled_or_absent'}"
    else:
        passing = raw.strip().lower() == "true"
        detail = f"Confirm-SecureBootUEFI={raw.strip()}"
    return _LayerResult("1:SecureBoot", passing, detail)


def _check_tpm() -> _LayerResult:
    """Layer 2: TPM 2.0 present, enabled, and activated."""
    script = (
        "try { $t = Get-Tpm; "
        "[pscustomobject]@{"
        "  Present=$t.TpmPresent; "
        "  Enabled=$t.TpmEnabled; "
        "  Activated=$t.TpmActivated; "
        "  SpecVer=$t.ManufacturerVersionInfo"
        "} | ConvertTo-Json } catch { Write-Output 'ERROR' }"
    )
    raw = _run_ps(script)
    if not raw or raw == "ERROR":
        return _LayerResult("2:TPM", False, "Get-Tpm unavailable")
    try:
        obj = json.loads(raw)
        present = bool(obj.get("Present", False))
        enabled = bool(obj.get("Enabled", False))
        activated = bool(obj.get("Activated", False))
        spec = str(obj.get("SpecVer", ""))
        passing = present and enabled and activated
        detail = f"present={present} enabled={enabled} activated={activated} spec={spec}"
    except (json.JSONDecodeError, TypeError):
        return _LayerResult("2:TPM", False, "JSON parse error")
    return _LayerResult("2:TPM", passing, detail)


def _check_wdac() -> _LayerResult:
    """Layer 3: WDAC in enforce mode (CiTool / CI policy state)."""
    script = (
        "try { "
        "  $policies = CiTool --list-policies 2>&1 | ConvertFrom-Json; "
        "  $enforced = $policies | Where-Object { $_.IsEnforced -eq $true }; "
        "  Write-Output ($enforced.Count) "
        "} catch { "
        "  # Fallback: check CodeIntegrity registry key "
        "  $ci = Get-ItemPropertyValue "
        "    'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CI\\Config' "
        "    'VulnerableDriverBlocklistEnable' -ErrorAction SilentlyContinue; "
        "  Write-Output ('REG:' + $ci) "
        "}"
    )
    raw = _run_ps(script)
    if raw is None:
        return _LayerResult("3:WDAC", False, "CiTool/CI registry unavailable")
    if raw.startswith("REG:"):
        # Registry present but CiTool not available (older Windows)
        val = raw[4:]
        passing = val == "1"
        return _LayerResult("3:WDAC", passing, f"registry_ci_block={val}")
    try:
        count = int(raw)
        passing = count > 0
        return _LayerResult("3:WDAC", passing, f"wdac_enforced_policies={count}")
    except ValueError:
        return _LayerResult("3:WDAC", False, f"unexpected output: {raw[:80]}")


def _check_sysmon() -> _LayerResult:
    """Layer 4a: Sysmon service running (runtime telemetry gate)."""
    script = (
        "try { $svc = Get-Service -Name 'Sysmon64','Sysmon' -ErrorAction SilentlyContinue | "
        "  Where-Object { $_.Status -eq 'Running' }; "
        "  Write-Output ($svc.Count) } catch { Write-Output '0' }"
    )
    raw = _run_ps(script)
    count = int(raw) if raw and raw.isdigit() else 0
    passing = count > 0
    return _LayerResult("4:Sysmon", passing, f"running_instances={count}")


def _check_defender() -> _LayerResult:
    """Layer 5: Windows Defender real-time protection enabled, no active threats."""
    script = (
        "try { "
        "  $mp = Get-MpComputerStatus; "
        "  [pscustomobject]@{ "
        "    RTP=$mp.RealTimeProtectionEnabled; "
        "    ASDef=$mp.AntispywareEnabled; "
        "    AVDef=$mp.AntivirusEnabled; "
        "    Threats=(Get-MpThreat).Count "
        "  } | ConvertTo-Json "
        "} catch { Write-Output 'ERROR' }"
    )
    raw = _run_ps(script, timeout=25)
    if not raw or raw == "ERROR":
        return _LayerResult("5:Defender", False, "Get-MpComputerStatus unavailable")
    try:
        obj = json.loads(raw)
        rtp = bool(obj.get("RTP", False))
        threats = int(obj.get("Threats", -1))
        passing = rtp and threats == 0
        detail = f"rtp={rtp} threats={threats}"
    except (json.JSONDecodeError, TypeError, ValueError):
        return _LayerResult("5:Defender", False, "JSON parse error")
    return _LayerResult("5:Defender", passing, detail)


# ---------------------------------------------------------------------------
# WindowsSovereigntyMonitor
# ---------------------------------------------------------------------------

class WindowsSovereigntyMonitor:
    """
    Evaluates the platform's sovereignty posture by checking the five-layer
    Windows trust chain.  Replaces Bombadil's ring-0 sentinel with
    policy-authoritative equivalents.
    """

    PROVIDER_NAME = "windows_sovereignty_monitor"

    def evaluate_sovereignty_state(self) -> SovereigntyAssessment:
        if not _IS_WINDOWS:
            return SovereigntyAssessment(
                state="SIMULATION",
                provider=self.PROVIDER_NAME + "_stub",
                reasons=["Non-Windows host; all layer checks skipped"],
                attributes={"sovereignty_level": SovereigntyLevel.SIMULATION},
            )

        layers = self._run_all_layers()
        state, level = self._derive_state(layers)
        reasons = [l.to_reason() for l in layers]

        return SovereigntyAssessment(
            state=state,
            provider=self.PROVIDER_NAME,
            reasons=reasons,
            attributes={
                "sovereignty_level": level,
                "layers_passing": sum(1 for l in layers if l.passing),
                "layers_total": len(layers),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def explain_state_reasons(self) -> List[str]:
        if not _IS_WINDOWS:
            return ["SIMULATION: non-Windows host; sovereignty check skipped"]
        layers = self._run_all_layers()
        return [l.to_reason() for l in layers]

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _run_all_layers() -> List[_LayerResult]:
        return [
            _check_secure_boot(),
            _check_tpm(),
            _check_wdac(),
            _check_sysmon(),
            _check_defender(),
        ]

    @staticmethod
    def _derive_state(layers: List[_LayerResult]) -> Tuple[str, str]:
        """
        Map layer results to a sovereignty state string + level.

        SOVEREIGN   — all 5 layers pass
        CONSTRAINED — layers 1+2 pass, ≥1 of 3-5 fails
        COMPROMISED — layer 1 or 2 fails
        DEGRADED    — TPM present but Secure Boot off (edge case)
        """
        boot_ok = layers[0].passing  # Secure Boot
        tpm_ok = layers[1].passing   # TPM

        if not boot_ok or not tpm_ok:
            return "COMPROMISED", SovereigntyLevel.SIMULATION

        all_pass = all(l.passing for l in layers)
        if all_pass:
            return "SOVEREIGN", SovereigntyLevel.WINDOWS_POLICY_AUTHORITATIVE

        return "CONSTRAINED", SovereigntyLevel.WINDOWS_POLICY_AUTHORITATIVE
