"""
tests/test_phase1_providers.py
==============================
Phase 1 provider tests — run on any platform (Linux CI, Windows target).

On Linux every provider returns stub data (confidence=0.0, stub=True).
On Windows real data is returned; tests assert structural correctness only
(not specific values, which vary by host).
"""
import platform
import sys
import os

# Allow importing from src/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from arda_windows.providers.windows_attestation import WindowsAttestationProvider
from arda_windows.providers.windows_evidence import WindowsEvidenceProvider
from arda_windows.providers.windows_enforcement import WindowsPolicyEnforcementProvider
from arda_windows.providers.windows_sovereignty import WindowsSovereigntyMonitor
from arda_windows.world_manifold import WorldManifold
from arda_windows.models import (
    PcrSnapshot,
    SecureBootState,
    BootEventRecord,
    EvidencePacket,
    EnforcementResult,
    SovereigntyAssessment,
)

IS_WINDOWS = platform.system() == "Windows"


# ---------------------------------------------------------------------------
# AttestationProvider
# ---------------------------------------------------------------------------

class TestWindowsAttestationProvider:
    def setup_method(self):
        self.p = WindowsAttestationProvider()

    def test_get_pcr_snapshot_returns_list(self):
        result = self.p.get_pcr_snapshot([0, 4, 7])
        assert isinstance(result, list)
        assert all(isinstance(r, PcrSnapshot) for r in result)

    def test_get_pcr_snapshot_indices_match(self):
        result = self.p.get_pcr_snapshot([0, 4, 7])
        if not IS_WINDOWS:
            # Stub returns one entry per requested index
            assert len(result) == 3
            assert {r.index for r in result} == {0, 4, 7}

    def test_get_pcr_snapshot_value_nonempty(self):
        result = self.p.get_pcr_snapshot([0])
        assert result[0].value  # not empty string

    def test_get_secure_boot_state_returns_type(self):
        state = self.p.get_secure_boot_state()
        assert isinstance(state, SecureBootState)

    def test_get_secure_boot_state_fields_present(self):
        state = self.p.get_secure_boot_state()
        assert isinstance(state.enabled, bool)
        assert isinstance(state.setup_mode, bool)
        assert isinstance(state.secure_boot_mode, str)
        assert isinstance(state.vendor_keys, list)

    def test_get_boot_event_log_returns_list(self):
        events = self.p.get_boot_event_log()
        assert isinstance(events, list)
        assert all(isinstance(e, BootEventRecord) for e in events)

    def test_get_boot_event_log_stub_has_3_entries(self):
        if not IS_WINDOWS:
            events = self.p.get_boot_event_log()
            assert len(events) == 3  # PCR 0, 4, 7 stubs


# ---------------------------------------------------------------------------
# EvidenceProvider
# ---------------------------------------------------------------------------

class TestWindowsEvidenceProvider:
    def setup_method(self):
        self.p = WindowsEvidenceProvider()

    def _assert_packet(self, pkt: EvidencePacket, source_prefix: str):
        assert isinstance(pkt, EvidencePacket)
        assert pkt.source.startswith(source_prefix)
        assert 0.0 <= pkt.confidence <= 1.0
        assert isinstance(pkt.evidence, dict)
        assert "collected_at" in pkt.evidence or "stub" in pkt.evidence

    def test_varda_returns_packet(self):
        pkt = self.p.collect_varda_evidence({})
        self._assert_packet(pkt, "varda_windows")

    def test_ulmo_returns_packet(self):
        pkt = self.p.collect_ulmo_evidence({})
        self._assert_packet(pkt, "ulmo_windows")

    def test_manwe_returns_packet(self):
        pkt = self.p.collect_manwe_evidence({})
        self._assert_packet(pkt, "manwe_windows")

    def test_mandos_returns_packet(self):
        pkt = self.p.collect_mandos_evidence({})
        self._assert_packet(pkt, "mandos_windows")

    def test_stub_confidence_is_zero_on_linux(self):
        if not IS_WINDOWS:
            for collect in [
                self.p.collect_varda_evidence,
                self.p.collect_ulmo_evidence,
                self.p.collect_manwe_evidence,
                self.p.collect_mandos_evidence,
            ]:
                pkt = collect({})
                assert pkt.confidence == 0.0
                assert pkt.evidence.get("stub") is True

    def test_sweep_id_is_unique(self):
        p1 = self.p.collect_varda_evidence({})
        p2 = self.p.collect_varda_evidence({})
        assert p1.sweep_id != p2.sweep_id


# ---------------------------------------------------------------------------
# PolicyEnforcementProvider
# ---------------------------------------------------------------------------

class TestWindowsPolicyEnforcementProvider:
    def setup_method(self):
        self.p = WindowsPolicyEnforcementProvider()

    def _assert_result(self, result: EnforcementResult):
        assert isinstance(result, EnforcementResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.posture, str)
        assert isinstance(result.provider, str)
        assert isinstance(result.actions, list)

    def test_apply_posture_enforce(self):
        r = self.p.apply_posture("node-1", "enforce", {})
        self._assert_result(r)
        assert r.posture == "enforce"

    def test_apply_posture_audit(self):
        r = self.p.apply_posture("node-1", "audit", {})
        self._assert_result(r)
        assert r.posture == "audit"

    def test_apply_posture_unknown_fails(self):
        r = self.p.apply_posture("node-1", "unicorn", {})
        self._assert_result(r)
        assert not r.success

    def test_trust_workload(self):
        r = self.p.trust_workload({"publisher_name": "TestPublisher", "file_path": "C:\\fake.exe"})
        self._assert_result(r)
        assert r.posture == "trusted"

    def test_distrust_workload(self):
        r = self.p.distrust_workload({"file_path": "C:\\evil.exe", "remote_ip": "10.0.0.1"})
        self._assert_result(r)
        assert r.posture == "distrusted"

    def test_stub_provider_name_on_linux(self):
        if not IS_WINDOWS:
            r = self.p.apply_posture("n", "enforce", {})
            assert r.provider == "windows_enforcement_stub"


# ---------------------------------------------------------------------------
# SovereigntyMonitor
# ---------------------------------------------------------------------------

class TestWindowsSovereigntyMonitor:
    def setup_method(self):
        self.m = WindowsSovereigntyMonitor()

    def test_evaluate_returns_assessment(self):
        a = self.m.evaluate_sovereignty_state()
        assert isinstance(a, SovereigntyAssessment)

    def test_state_is_valid_string(self):
        a = self.m.evaluate_sovereignty_state()
        assert a.state in {"SOVEREIGN", "CONSTRAINED", "COMPROMISED", "SIMULATION", "DEGRADED"}

    def test_simulation_on_linux(self):
        if not IS_WINDOWS:
            a = self.m.evaluate_sovereignty_state()
            assert a.state == "SIMULATION"

    def test_explain_returns_list_of_strings(self):
        reasons = self.m.explain_state_reasons()
        assert isinstance(reasons, list)
        assert all(isinstance(r, str) for r in reasons)

    def test_attributes_contain_sovereignty_level(self):
        a = self.m.evaluate_sovereignty_state()
        assert "sovereignty_level" in a.attributes


# ---------------------------------------------------------------------------
# WorldManifold (integration)
# ---------------------------------------------------------------------------

class TestWorldManifold:
    def test_build_returns_manifold(self):
        m = WorldManifold.build()
        assert isinstance(m, WorldManifold)

    def test_manifold_has_all_providers(self):
        m = WorldManifold.build()
        assert m.attestation is not None
        assert m.evidence is not None
        assert m.enforcement is not None
        assert m.sovereignty is not None

    def test_platform_summary_has_required_keys(self):
        m = WorldManifold.build()
        summary = m.platform_summary()
        for key in ["platform", "sovereignty_level", "tpm_attestation",
                    "secure_boot_check", "kernel_ring0_exec_gate"]:
            assert key in summary

    def test_manifold_shortcuts_match_registry(self):
        m = WorldManifold.build()
        assert m.attestation is m.registry.attestation
        assert m.evidence is m.registry.evidence
        assert m.enforcement is m.registry.enforcement
        assert m.sovereignty is m.registry.sovereignty

    def test_full_pipeline_stub(self):
        """Smoke-test the complete pipeline end-to-end (stub mode on Linux)."""
        m = WorldManifold.build()
        pcrs = m.attestation.get_pcr_snapshot([0, 4, 7])
        ev = m.evidence.collect_manwe_evidence({})
        enf = m.enforcement.apply_posture("test-node", "audit", {})
        sov = m.sovereignty.evaluate_sovereignty_state()

        assert len(pcrs) > 0
        assert isinstance(ev, EvidencePacket)
        assert isinstance(enf, EnforcementResult)
        assert isinstance(sov, SovereigntyAssessment)
