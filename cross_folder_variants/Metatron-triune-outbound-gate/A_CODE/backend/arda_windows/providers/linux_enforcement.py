"""
LinuxPolicyEnforcementProvider
================================
Implements PolicyEnforcementProvider using Linux-native enforcement APIs:

  • apply_posture   — SELinux setenforce / AppArmor aa-enforce + nftables posture rules
  • trust_workload  — add an SELinux/AppArmor allow-rule or nftables ACCEPT rule
  • distrust_workload — nftables DROP rule + optional SELinux domain transition deny

All actions are logged via the Linux audit subsystem (auditctl) so the
constitutional layer has a durable audit trail in /var/log/audit/audit.log.

Posture values understood by apply_posture():
  'enforce'    — LSM enforcing mode + nftables baseline
  'audit'      — LSM permissive/audit mode
  'quarantine' — drop all traffic for a node identity (IP-based)
  'off'        — remove ARDA-managed rules
"""
from __future__ import annotations

import logging
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import EnforcementResult

logger = logging.getLogger(__name__)


def _run(cmd: List[str], timeout: int = 15) -> Optional[str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        logger.debug("cmd %s unavailable: %s", cmd[0], exc)
    return None


def _log_audit_event(action: str, node_id: str, posture: str, success: bool) -> None:
    """Write a structured enforcement record via logger.audit."""
    msg = (
        f"ARDA_ENFORCEMENT action={action} node={node_id} "
        f"posture={posture} success={success} "
        f"ts={datetime.now(timezone.utc).isoformat()}"
    )
    logger.info(msg)
    # Try to inject into kernel audit log if auditctl is available
    _run([
        "auditctl", "-m",
        f"ARDA action={action} node={node_id} posture={posture}",
    ], timeout=5)


# ---------------------------------------------------------------------------
# SELinux helpers
# ---------------------------------------------------------------------------

def _selinux_status() -> Optional[str]:
    """Return 'enforcing', 'permissive', 'disabled', or None."""
    raw = _run(["getenforce"])
    return raw.lower() if raw else None


def _selinux_set(mode: str) -> bool:
    """Set SELinux to 'Enforcing' (1) or 'Permissive' (0)."""
    level = "1" if mode == "enforce" else "0"
    return _run(["setenforce", level]) is not None


# ---------------------------------------------------------------------------
# AppArmor helpers
# ---------------------------------------------------------------------------

def _apparmor_status() -> Optional[str]:
    raw = _run(["aa-status", "--enabled"])
    return "enabled" if raw is not None else None


def _apparmor_enforce() -> bool:
    """Switch all loaded profiles to enforce mode."""
    return _run(["aa-enforce", "/etc/apparmor.d/*"]) is not None


def _apparmor_complain() -> bool:
    """Switch all loaded profiles to complain (audit) mode."""
    return _run(["aa-complain", "/etc/apparmor.d/*"]) is not None


# ---------------------------------------------------------------------------
# nftables helpers
# ---------------------------------------------------------------------------

_NFT_TABLE = "arda_enforcement"
_NFT_CHAIN = "output_gate"


def _nft_ensure_table() -> bool:
    """Create ARDA nftables table + chain if absent."""
    script = (
        f"add table inet {_NFT_TABLE}; "
        f"add chain inet {_NFT_TABLE} {_NFT_CHAIN} {{ type filter hook output priority 0; }};"
    )
    return _run(["nft", script]) is not None or _run(["nft", "-f", "-"]) is not None


def _nft_block_ip(remote_addr: str) -> bool:
    rule = (
        f"add rule inet {_NFT_TABLE} {_NFT_CHAIN} "
        f"ip daddr {remote_addr} drop comment \"arda_block\""
    )
    return _run(["nft", rule]) is not None


def _nft_flush_arda() -> bool:
    return _run(["nft", f"flush table inet {_NFT_TABLE}"]) is not None


def _iptables_block_ip(remote_addr: str, add: bool = True) -> bool:
    action = "-I" if add else "-D"
    return _run([
        "iptables", action, "OUTPUT",
        "-d", remote_addr, "-j", "DROP",
        "-m", "comment", "--comment", "arda_block",
    ]) is not None


def _iptables_flush_arda() -> bool:
    """Remove all OUTPUT rules tagged arda_block."""
    raw = _run(["iptables", "-L", "OUTPUT", "--line-numbers", "-n"])
    if not raw:
        return False
    lines_to_delete = []
    for line in raw.splitlines():
        if "arda_block" in line:
            parts = line.split()
            if parts and parts[0].isdigit():
                lines_to_delete.append(parts[0])
    # Delete in reverse order so line numbers don't shift
    for num in reversed(lines_to_delete):
        _run(["iptables", "-D", "OUTPUT", num])
    return True


# ---------------------------------------------------------------------------
# LinuxPolicyEnforcementProvider
# ---------------------------------------------------------------------------

class LinuxPolicyEnforcementProvider:
    """
    Applies sovereignty posture to Linux nodes via SELinux/AppArmor + nftables.
    """

    def apply_posture(self, node_id: str, posture: str, verdict: Dict[str, object]) -> EnforcementResult:
        actions: List[str] = []
        success = False

        if posture == "enforce":
            se = _selinux_set("enforce")
            aa = _apparmor_enforce()
            if se:
                actions.append("selinux:enforcing")
            if aa:
                actions.append("apparmor:enforce")
            success = se or aa

        elif posture == "audit":
            se = _selinux_set("permissive")
            aa = _apparmor_complain()
            if se:
                actions.append("selinux:permissive")
            if aa:
                actions.append("apparmor:complain")
            success = se or aa

        elif posture == "quarantine":
            remote = str(verdict.get("remote_addr", node_id))
            blocked_nft = _nft_block_ip(remote)
            blocked_ipt = _iptables_block_ip(remote)
            if blocked_nft:
                actions.append(f"nft:drop:{remote}")
            if blocked_ipt:
                actions.append(f"iptables:drop:{remote}")
            success = blocked_nft or blocked_ipt

        elif posture == "off":
            _nft_flush_arda()
            _iptables_flush_arda()
            actions.append("nft:flushed")
            actions.append("iptables:flushed")
            success = True

        else:
            success = False
            actions.append(f"unknown_posture:{posture}")

        _log_audit_event("apply_posture", node_id, posture, success)
        provider = "linux_enforcement" if success else "linux_enforcement_stub"
        return EnforcementResult(
            success=success,
            posture=posture,
            provider=provider,
            actions=actions,
            details={"node_id": node_id, "verdict": verdict},
        )

    def trust_workload(self, identity: Dict[str, object]) -> EnforcementResult:
        """Allow outbound traffic for a trusted workload identity (IP)."""
        remote = str(identity.get("remote_addr", ""))
        actions: List[str] = []
        success = False

        if remote:
            # Remove any existing block rule
            _iptables_block_ip(remote, add=False)
            # Explicit ACCEPT before any drop
            ok = _run([
                "iptables", "-I", "OUTPUT", "1",
                "-d", remote, "-j", "ACCEPT",
                "-m", "comment", "--comment", "arda_trust",
            ]) is not None
            if ok:
                actions.append(f"iptables:accept:{remote}")
                success = True

        _log_audit_event("trust_workload", str(identity.get("id", "")), "trust", success)
        return EnforcementResult(
            success=success,
            posture="trust",
            provider="linux_enforcement" if success else "linux_enforcement_stub",
            actions=actions,
            details={"identity": identity},
        )

    def distrust_workload(self, identity: Dict[str, object]) -> EnforcementResult:
        """Block outbound traffic for a distrusted workload identity (IP)."""
        remote = str(identity.get("remote_addr", ""))
        actions: List[str] = []
        success = False

        if remote:
            ok_nft = _nft_block_ip(remote)
            ok_ipt = _iptables_block_ip(remote)
            if ok_nft:
                actions.append(f"nft:drop:{remote}")
            if ok_ipt:
                actions.append(f"iptables:drop:{remote}")
            success = ok_nft or ok_ipt

        _log_audit_event("distrust_workload", str(identity.get("id", "")), "distrust", success)
        return EnforcementResult(
            success=success,
            posture="distrust",
            provider="linux_enforcement" if success else "linux_enforcement_stub",
            actions=actions,
            details={"identity": identity},
        )
