"""
tests/test_linux_providers.py
==============================
Linux provider tests — run on any platform.

On Linux, real tools (tpm2-tools, mokutil, auditd, ss, etc.) may or may
not be present; tests assert structural correctness and graceful degradation.
On non-Linux hosts every provider returns stub data (confidence varies).
"""
import platform
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from arda_windows.providers.linux_attestation import LinuxAttestationProvider
from arda_windows.providers.linux_evidence import LinuxEvidenceProvider
from arda_windows.providers.linux_enforcement import LinuxPolicyEnforcementProvider
from arda_windows.providers.linux_sovereignty import LinuxSovereigntyMonitor
from arda_windows.world_manifold import WorldManifold
from arda_windows.models import (
    PcrSnapshot,
    SecureBootState,
    BootEventRecord,
    EvidencePacket,
    EnforcementResult,
    SovereigntyAssessment,
)

IS_LINUX = platform.system() == "Linux"


# ---------------------------------------------------------------------------
# LinuxAttestationProvider
# ---------------------------------------------------------------------------

class TestLinuxAttestationProvider:
    def setup_method(self):
        self.p = LinuxAttestationProvider()

    def test_get_pcr_snapshot_returns_list(self):
        result = self.p.get_pcr_snapshot([0, 4, 7])
        assert isinstance(result, list)
        assert all(isinstance(r, PcrSnapshot) for r in result)

    def test_get_pcr_snapshot_indices_covered(self):
        result = self.p.get_pcr_snapshot([0, 4, 7])
        # Either real data or stubs — must cover requested indices
        returned_indices = {r.index for r in result}
        if not any(r.value.endswith("_stub") for r in result):
            # Real data: indices should be subset of requested
            assert returned_indices.issubset({0, 4, 7})
        else:
            # Stub: all requested indices must be present
            assert returned_indices == {0, 4, 7}

    def test_get_pcr_snapshot_value_nonempty(self):
        result = self.p.get_pcr_snapshot([0])
        assert len(result) >= 1
        assert result[0].value  # not empty

    def test_get_secure_boot_state_returns_type(self):
        state = self.p.get_secure_boot_state()
        assert isinstance(state, SecureBootState)

    def test_get_secure_boot_state_fields(self):
        state = self.p.get_secure_boot_state()
        assert isinstance(state.enabled, bool)
        assert isinstance(state.setup_mode, bool)
        assert isinstance(state.secure_boot_mode, str)
        assert isinstance(state.vendor_keys, list)

    def test_get_boot_event_log_returns_list(self):
        events = self.p.get_boot_event_log()
        assert isinstance(events, list)
        assert all(isinstance(e, BootEventRecord) for e in events)

    def test_get_boot_event_log_nonempty(self):
        events = self.p.get_boot_event_log()
        # At minimum stubs are returned (3 entries)
        assert len(events) >= 3

    def test_boot_event_has_required_fields(self):
        events = self.p.get_boot_event_log()
        for e in events[:5]:
            assert isinstance(e.pcr_index, int)
            assert isinstance(e.event_type, str)
            assert isinstance(e.digest, str)
            assert isinstance(e.timestamp_iso, str)


# ---------------------------------------------------------------------------
# LinuxEvidenceProvider
# ---------------------------------------------------------------------------

class TestLinuxEvidenceProvider:
    def setup_method(self):
        self.p = LinuxEvidenceProvider()

    def _assert_packet(self, pkt: EvidencePacket, source_prefix: str):
        assert isinstance(pkt, EvidencePacket)
        assert pkt.source.startswith(source_prefix)
        assert 0.0 <= pkt.confidence <= 1.0
        assert isinstance(pkt.evidence, dict)
        assert "collected_at" in pkt.evidence or "stub" in pkt.evidence

    def test_varda_returns_packet(self):
        pkt = self.p.collect_varda_evidence({})
        self._assert_packet(pkt, "varda_linux")

    def test_ulmo_returns_packet(self):
        pkt = self.p.collect_ulmo_evidence({})
        self._assert_packet(pkt, "ulmo_linux")

    def test_manwe_returns_packet(self):
        pkt = self.p.collect_manwe_evidence({})
        self._assert_packet(pkt, "manwe_linux")

    def test_mandos_returns_packet(self):
        pkt = self.p.collect_mandos_evidence({})
        self._assert_packet(pkt, "mandos_linux")

    def test_sweep_id_is_unique(self):
        p1 = self.p.collect_varda_evidence({})
        p2 = self.p.collect_varda_evidence({})
        assert p1.sweep_id != p2.sweep_id

    def test_ulmo_has_connection_count(self):
        pkt = self.p.collect_ulmo_evidence({})
        assert "connection_count" in pkt.evidence

    def test_manwe_has_process_count(self):
        pkt = self.p.collect_manwe_evidence({})
        assert "process_count" in pkt.evidence
        if IS_LINUX:
            # /proc always available on Linux
            assert pkt.evidence["process_count"] > 0

    def test_mandos_has_clean_flag(self):
        pkt = self.p.collect_mandos_evidence({})
        assert "clean" in pkt.evidence
        assert isinstance(pkt.evidence["clean"], bool)


# ---------------------------------------------------------------------------
# LinuxPolicyEnforcementProvider
# ---------------------------------------------------------------------------

class TestLinuxPolicyEnforcementProvider:
    def setup_method(self):
        self.p = LinuxPolicyEnforcementProvider()

    def _assert_result(self, result: EnforcementResult):
        assert isinstance(result, EnforcementResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.posture, str)
        assert isinstance(result.provider, str)
        assert isinstance(result.actions, list)
        assert isinstance(result.details, dict)

    def test_apply_posture_enforce_returns_result(self):
        r = self.p.apply_posture("node-1", "enforce", {})
        self._assert_result(r)
        assert r.posture == "enforce"

    def test_apply_posture_audit_returns_result(self):
        r = self.p.apply_posture("node-1", "audit", {})
        self._assert_result(r)
        assert r.posture == "audit"

    def test_apply_posture_off_returns_result(self):
        r = self.p.apply_posture("node-1", "off", {})
        self._assert_result(r)
        assert r.posture == "off"
        # off always reported as success (cleanup is best-effort)
        assert r.success is True

    def test_apply_posture_unknown_posture(self):
        r = self.p.apply_posture("node-1", "unknown_posture_xyz", {})
        self._assert_result(r)
        assert r.success is False

    def test_trust_workload_returns_result(self):
        r = self.p.trust_workload({"id": "wl-1", "remote_addr": "10.0.0.99"})
        self._assert_result(r)
        assert r.posture == "trust"

    def test_distrust_workload_returns_result(self):
        r = self.p.distrust_workload({"id": "wl-2", "remote_addr": "10.0.0.100"})
        self._assert_result(r)
        assert r.posture == "distrust"

    def test_quarantine_posture_accepts_remote_addr(self):
        r = self.p.apply_posture("node-q", "quarantine", {"remote_addr": "192.168.1.50"})
        self._assert_result(r)
        assert r.posture == "quarantine"


# ---------------------------------------------------------------------------
# LinuxSovereigntyMonitor
# ---------------------------------------------------------------------------

class TestLinuxSovereigntyMonitor:
    def setup_method(self):
        self.m = LinuxSovereigntyMonitor()

    def test_evaluate_returns_assessment(self):
        a = self.m.evaluate_sovereignty_state()
        assert isinstance(a, SovereigntyAssessment)

    def test_state_is_valid_string(self):
        a = self.m.evaluate_sovereignty_state()
        assert a.state in {"SOVEREIGN", "CONSTRAINED", "COMPROMISED", "SIMULATION"}

    def test_provider_is_linux(self):
        a = self.m.evaluate_sovereignty_state()
        assert a.provider == "linux_sovereignty"

    def test_reasons_is_list_of_strings(self):
        reasons = self.m.explain_state_reasons()
        assert isinstance(reasons, list)
        assert all(isinstance(r, str) for r in reasons)

    def test_reasons_has_layer_labels(self):
        reasons = self.m.explain_state_reasons()
        assert any("Layer" in r for r in reasons)

    def test_attributes_has_required_keys(self):
        a = self.m.evaluate_sovereignty_state()
        for key in ("sovereignty_level", "layers_passing", "layers_total", "evaluated_at"):
            assert key in a.attributes

    def test_layers_total_gte_5(self):
        a = self.m.evaluate_sovereignty_state()
        assert a.attributes["layers_total"] >= 5


# ---------------------------------------------------------------------------
# WorldManifold — Linux platform wiring
# ---------------------------------------------------------------------------

class TestWorldManifoldLinux:
    def test_build_on_linux_uses_linux_providers(self):
        m = WorldManifold.build()
        summary = m.platform_summary()
        if IS_LINUX:
            assert summary["platform"] == "linux"
            # Evidence and sovereignty providers should be Linux-native
            assert "linux" in summary["evidence_provider"].lower() or \
                   summary["evidence_provider"] != "WindowsEvidenceProvider"

    def test_sovereignty_state_runs_on_linux(self):
        m = WorldManifold.build()
        if IS_LINUX:
            assessment = m.sovereignty.evaluate_sovereignty_state()
            assert assessment.state in {"SOVEREIGN", "CONSTRAINED", "COMPROMISED", "SIMULATION"}

    def test_full_pipeline_linux(self):
        m = WorldManifold.build()
        if IS_LINUX:
            varda = m.evidence.collect_varda_evidence({})
            ulmo = m.evidence.collect_ulmo_evidence({})
            manwe = m.evidence.collect_manwe_evidence({})
            mandos = m.evidence.collect_mandos_evidence({})
            for pkt in (varda, ulmo, manwe, mandos):
                assert isinstance(pkt, EvidencePacket)
                assert 0.0 <= pkt.confidence <= 1.0
