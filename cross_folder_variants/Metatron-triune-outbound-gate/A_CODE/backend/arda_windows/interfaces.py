from __future__ import annotations

from typing import Dict, List, Optional, Protocol

from .models import (
    BootEventRecord,
    EnforcementResult,
    EvidencePacket,
    PcrSnapshot,
    SecureBootState,
    SovereigntyAssessment,
)


class AttestationProvider(Protocol):
    def get_pcr_snapshot(self, indices: List[int]) -> List[PcrSnapshot]:
        ...

    def get_secure_boot_state(self) -> SecureBootState:
        ...

    def get_boot_event_log(self) -> List[BootEventRecord]:
        ...


class EvidenceProvider(Protocol):
    def collect_varda_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        ...

    def collect_ulmo_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        ...

    def collect_manwe_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        ...

    def collect_mandos_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        ...


class PolicyEnforcementProvider(Protocol):
    def apply_posture(self, node_id: str, posture: str, verdict: Dict[str, object]) -> EnforcementResult:
        ...

    def trust_workload(self, identity: Dict[str, object]) -> EnforcementResult:
        ...

    def distrust_workload(self, identity: Dict[str, object]) -> EnforcementResult:
        ...


class SovereigntyMonitor(Protocol):
    def evaluate_sovereignty_state(self) -> SovereigntyAssessment:
        ...

    def explain_state_reasons(self) -> List[str]:
        ...
