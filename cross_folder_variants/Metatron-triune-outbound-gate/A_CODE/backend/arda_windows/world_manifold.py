"""
WorldManifold
=============
Platform-normalisation bridge for the ARDA Windows port.

Responsibilities:
  1. Detect the host platform (Linux vs Windows vs unknown/sim).
  2. Auto-wire the correct concrete adapter providers.
  3. Expose a unified runtime facade so the constitutional layer
     never has to branch on platform.

Usage (basic)
-------------
    from arda_windows.world_manifold import WorldManifold

    manifold = WorldManifold.build()
    assessment  = manifold.sovereignty.evaluate_sovereignty_state()
    evidence    = manifold.evidence.collect_manwe_evidence({})

Usage (with Arkime network evidence)
-------------------------------------
    manifold = WorldManifold.build(arkime_es_url="http://127.0.0.1:9200")
    # Ulmo and Mandos evidence now sourced from Arkime full-packet capture.
    # Varda and Manwë evidence still use platform-native collectors.
    ulmo   = manifold.evidence.collect_ulmo_evidence({})
    mandos = manifold.evidence.collect_mandos_evidence({})

Environment variables (Arkime)
--------------------------------
    ARKIME_ES_URL   — Elasticsearch URL   (default: http://127.0.0.1:9200)
    ARKIME_ES_INDEX — Index pattern        (default: arkime_sessions3-*)
    ARKIME_ES_USER  — Basic-auth user      (default: empty)
    ARKIME_ES_PASS  — Basic-auth password  (default: empty)

Extending
---------
To add a Linux provider, implement the same Protocol interfaces and pass
them to WorldManifold() directly instead of using build().
"""
from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from typing import Optional

from .capabilities import detect_platform_capabilities
from .interfaces import (
    AttestationProvider,
    EvidenceProvider,
    PolicyEnforcementProvider,
    SovereigntyMonitor,
)
from .models import PlatformCapabilities, SovereigntyLevel
from .registry import AdapterRegistry, build_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports for platform-specific providers
# ---------------------------------------------------------------------------

def _load_windows_providers():
    from .providers.windows_attestation import WindowsAttestationProvider
    from .providers.windows_evidence import WindowsEvidenceProvider
    from .providers.windows_enforcement import WindowsPolicyEnforcementProvider
    from .providers.windows_sovereignty import WindowsSovereigntyMonitor
    return (
        WindowsAttestationProvider(),
        WindowsEvidenceProvider(),
        WindowsPolicyEnforcementProvider(),
        WindowsSovereigntyMonitor(),
    )


def _load_linux_providers():
    from .providers.linux_attestation import LinuxAttestationProvider
    from .providers.linux_evidence import LinuxEvidenceProvider
    from .providers.linux_enforcement import LinuxPolicyEnforcementProvider
    from .providers.linux_sovereignty import LinuxSovereigntyMonitor
    return (
        LinuxAttestationProvider(),
        LinuxEvidenceProvider(),
        LinuxPolicyEnforcementProvider(),
        LinuxSovereigntyMonitor(),
    )


def _load_stub_providers():
    """
    Minimal simulation providers used on non-Windows, non-Linux hosts
    (e.g. macOS CI runners, containers without a real TPM).
    These return confidence=0.0 packets so the pipeline can still run.
    """
    from .providers.windows_attestation import WindowsAttestationProvider
    from .providers.windows_evidence import WindowsEvidenceProvider
    from .providers.windows_enforcement import WindowsPolicyEnforcementProvider
    from .providers.windows_sovereignty import WindowsSovereigntyMonitor
    # Same classes; they auto-detect non-Windows and return stubs
    return (
        WindowsAttestationProvider(),
        WindowsEvidenceProvider(),
        WindowsPolicyEnforcementProvider(),
        WindowsSovereigntyMonitor(),
    )


# ---------------------------------------------------------------------------
# WorldManifold
# ---------------------------------------------------------------------------

@dataclass
class WorldManifold:
    """
    Unified, platform-agnostic access point for all ARDA adapter providers.

    Attributes
    ----------
    capabilities : PlatformCapabilities
        Detected platform profile (ring0 vs policy-authoritative, TPM, etc.)
    registry : AdapterRegistry
        Dependency-injected provider set for this platform.
    attestation : AttestationProvider
        Shortcut to registry.attestation.
    evidence : EvidenceProvider
        Shortcut to registry.evidence.
    enforcement : PolicyEnforcementProvider
        Shortcut to registry.enforcement.
    sovereignty : SovereigntyMonitor
        Shortcut to registry.sovereignty.
    """

    capabilities: PlatformCapabilities
    registry: AdapterRegistry

    # Convenience shortcuts (populated by build())
    attestation: AttestationProvider
    evidence: EvidenceProvider
    enforcement: PolicyEnforcementProvider
    sovereignty: SovereigntyMonitor

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        attestation: Optional[AttestationProvider] = None,
        evidence: Optional[EvidenceProvider] = None,
        enforcement: Optional[PolicyEnforcementProvider] = None,
        sovereignty: Optional[SovereigntyMonitor] = None,
        arkime_es_url: Optional[str] = None,
        arkime_es_index: Optional[str] = None,
        arkime_ulmo_lookback: int = 300,
        arkime_mandos_lookback: int = 3600,
    ) -> "WorldManifold":
        """
        Auto-detect the host platform and construct the appropriate
        provider set.

        Parameters
        ----------
        attestation / evidence / enforcement / sovereignty
            Explicit provider overrides.  If None, platform-appropriate
            defaults are used.
        arkime_es_url : str, optional
            If provided (or ARKIME_ES_URL env var is set), Arkime integration
            is enabled.  Ulmo and Mandos evidence will be sourced from Arkime's
            Elasticsearch store; Varda and Manwë remain platform-native.
            Pass an empty string "" to explicitly disable even if env var is set.
        arkime_es_index : str, optional
            Arkime session index pattern (default: arkime_sessions3-*).
        arkime_ulmo_lookback : int
            Lookback window in seconds for Ulmo (network flow) queries.
        arkime_mandos_lookback : int
            Lookback window in seconds for Mandos (threat) queries.
        """
        import os

        caps = detect_platform_capabilities()
        logger.info(
            "WorldManifold: platform=%s sovereignty=%s",
            caps.platform,
            caps.sovereignty_level,
        )

        if caps.platform == "windows":
            auto_attest, auto_evid, auto_enf, auto_sov = _load_windows_providers()
        elif caps.platform == "linux":
            auto_attest, auto_evid, auto_enf, auto_sov = _load_linux_providers()
            logger.info("WorldManifold: Linux native providers loaded.")
        else:
            auto_attest, auto_evid, auto_enf, auto_sov = _load_stub_providers()

        # ------------------------------------------------------------------
        # Arkime integration: replace the evidence provider with a hybrid that
        # sources Ulmo + Mandos from Arkime while keeping Varda + Manwë stubs.
        # ------------------------------------------------------------------
        resolved_arkime_url = arkime_es_url if arkime_es_url is not None else os.environ.get("ARKIME_ES_URL", "")
        if resolved_arkime_url and evidence is None:
            evidence = _build_arkime_hybrid_provider(
                es_url=resolved_arkime_url,
                es_index=arkime_es_index,
                ulmo_lookback=arkime_ulmo_lookback,
                mandos_lookback=arkime_mandos_lookback,
                platform_provider=auto_evid,
            )
            logger.info("WorldManifold: Arkime evidence provider wired (ES=%s)", resolved_arkime_url)

        # Allow remaining caller overrides
        final_attest = attestation or auto_attest
        final_evid = evidence or auto_evid
        final_enf = enforcement or auto_enf
        final_sov = sovereignty or auto_sov

        registry = build_registry(
            attestation=final_attest,
            evidence=final_evid,
            enforcement=final_enf,
            sovereignty=final_sov,
        )

        return cls(
            capabilities=caps,
            registry=registry,
            attestation=final_attest,
            evidence=final_evid,
            enforcement=final_enf,
            sovereignty=final_sov,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def platform_summary(self) -> dict:
        """Return a human-readable dict summarising platform posture."""
        c = self.capabilities
        from .integrations.arkime_evidence_provider import ArkimeEvidenceProvider

        evidence_type = type(self.evidence).__name__
        arkime_active = isinstance(self.evidence, (_ArkimeHybridProvider, ArkimeEvidenceProvider))

        return {
            "platform": c.platform,
            "sovereignty_level": c.sovereignty_level,
            "secure_boot_check": c.secure_boot_check,
            "tpm_attestation": c.tpm_attestation,
            "measured_boot_events": c.measured_boot_events,
            "execution_policy_enforcement": c.execution_policy_enforcement,
            "kernel_ring0_exec_gate": c.kernel_ring0_exec_gate,
            "deep_signal_collection": c.deep_signal_collection,
            "notes": c.notes,
            "evidence_provider": evidence_type,
            "arkime_integration_active": arkime_active,
        }


# ---------------------------------------------------------------------------
# Hybrid evidence provider: Arkime (Ulmo+Mandos) + platform-native (Varda+Manwë)
# ---------------------------------------------------------------------------

class _ArkimeHybridProvider:
    """
    Combines ArkimeEvidenceProvider for network evidence (Ulmo / Mandos)
    with the platform-native provider for host evidence (Varda / Manwë).
    The constitutional layer sees a single EvidenceProvider.
    """

    def __init__(
        self,
        arkime: "ArkimeEvidenceProvider",
        native: EvidenceProvider,
    ):
        self._arkime = arkime
        self._native = native

    def collect_varda_evidence(self, context):
        return self._native.collect_varda_evidence(context)

    def collect_ulmo_evidence(self, context):
        return self._arkime.collect_ulmo_evidence(context)

    def collect_manwe_evidence(self, context):
        return self._native.collect_manwe_evidence(context)

    def collect_mandos_evidence(self, context):
        return self._arkime.collect_mandos_evidence(context)


def _build_arkime_hybrid_provider(
    es_url: str,
    es_index: Optional[str],
    ulmo_lookback: int,
    mandos_lookback: int,
    platform_provider: EvidenceProvider,
) -> _ArkimeHybridProvider:
    from .integrations.arkime_client import ArkimeElasticsearchClient
    from .integrations.arkime_evidence_provider import ArkimeEvidenceProvider

    client = ArkimeElasticsearchClient(
        es_url=es_url,
        index_pattern=es_index,
    )
    arkime_provider = ArkimeEvidenceProvider(
        client=client,
        ulmo_lookback_seconds=ulmo_lookback,
        mandos_lookback_seconds=mandos_lookback,
    )
    return _ArkimeHybridProvider(arkime=arkime_provider, native=platform_provider)

