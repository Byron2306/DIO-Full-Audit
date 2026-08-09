from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SovereigntyLevel(str, Enum):
    LINUX_RING0_AUTHORITATIVE = "linux_ring0_authoritative"
    WINDOWS_POLICY_AUTHORITATIVE = "windows_policy_authoritative"
    SIMULATION = "simulation"


@dataclass(frozen=True)
class SecureBootState:
    enabled: bool
    setup_mode: bool
    secure_boot_mode: str
    vendor_keys: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PcrSnapshot:
    index: int
    value: str


@dataclass(frozen=True)
class BootEventRecord:
    pcr_index: int
    event_type: str
    digest: str
    event_data: str
    timestamp_iso: str


@dataclass(frozen=True)
class EvidencePacket:
    source: str
    confidence: float
    evidence: Dict[str, Any]
    sweep_id: Optional[str] = None


@dataclass(frozen=True)
class EnforcementResult:
    success: bool
    posture: str
    provider: str
    actions: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SovereigntyAssessment:
    state: str
    provider: str
    reasons: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformCapabilities:
    platform: str
    sovereignty_level: SovereigntyLevel
    secure_boot_check: bool
    tpm_attestation: bool
    measured_boot_events: bool
    execution_policy_enforcement: bool
    kernel_ring0_exec_gate: bool
    deep_signal_collection: bool
    notes: List[str] = field(default_factory=list)
