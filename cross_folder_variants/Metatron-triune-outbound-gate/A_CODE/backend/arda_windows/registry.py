from __future__ import annotations

from dataclasses import dataclass

from .interfaces import AttestationProvider, EvidenceProvider, PolicyEnforcementProvider, SovereigntyMonitor


@dataclass
class AdapterRegistry:
    attestation: AttestationProvider
    evidence: EvidenceProvider
    enforcement: PolicyEnforcementProvider
    sovereignty: SovereigntyMonitor


def build_registry(
    attestation: AttestationProvider,
    evidence: EvidenceProvider,
    enforcement: PolicyEnforcementProvider,
    sovereignty: SovereigntyMonitor,
) -> AdapterRegistry:
    return AdapterRegistry(
        attestation=attestation,
        evidence=evidence,
        enforcement=enforcement,
        sovereignty=sovereignty,
    )
