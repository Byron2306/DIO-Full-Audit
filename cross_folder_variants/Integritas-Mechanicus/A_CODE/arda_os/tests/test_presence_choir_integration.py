import unittest
from unittest.mock import patch

from backend.services import presence_server


class _FakeResonance:
    def __init__(self):
        self.calls = []

    def sing_in_choir(self, tier, component_id, score, reasons, witness=None):
        self.calls.append((tier, component_id, score, reasons, witness))

    def get_resonance_spectrum(self):
        return {"micro": 1.0, "meso": 1.0, "macro": 1.0, "global": 1.0}


class _FakeForge:
    async def issue_challenge(self, ttl_ms=300000):
        return "nonce-1"

    async def forge_packet(self, **kwargs):
        class _Witness:
            freshness_valid = True
            replay_suspected = False
            latency_ms = 5.0
            witness_signature = "sig"
            tpm_quote = {"pcr_mask": "0,7,11", "quote": "lawful"}
            workload_hash = "sha256:workload"
            executable_path = "/usr/bin/uptime"

        return _Witness()


class _FakeOsEnforcement:
    def get_status(self):
        return {
            "is_authoritative": True,
            "attach_verified": True,
            "arm_mode": "ring0_loader",
            "enforcement_mode": "legacy_inode",
            "harmonic_runtime": {"mode_recommendation": "normal_flow"},
            "policy_projection_state": {"generation_hash_prefix": 1234},
            "phase3_measured_identity": {"next_mode": "fsverity_strict"},
            "phase4_attestation_gate": {"release_gate_ready": True},
            "phase4_secret_release": {"purposes": ["policy_signing"]},
        }


class _FakeCouncil:
    last_context = None

    def __init__(self):
        self.witnesses = []

    def register_witness(self, witness):
        self.witnesses.append(witness)

    async def consult_witnesses(self, context):
        _FakeCouncil.last_context = context
        return {
            "collective_testimony": "The sovereign chorus remains harmonic.",
            "overall_recommendation": "HARMONIC",
            "canonical_runtime_state": "harmonic",
            "action": "AUTONOMOUS_GRANT",
            "lane": "Shire",
            "principal": context.get("principal"),
            "node_id": context.get("node_id"),
            "harmonic_observation": {"event": {"target_domain": "/usr/bin/uptime"}},
            "provenance_attestation": {"payload": {"artifact_digest": "sha256:test"}},
        }


class _DummyWitness:
    def __init__(self, *args, **kwargs):
        pass


class PresenceChoirIntegrationTest(unittest.TestCase):
    def test_presence_choir_projects_advisory_with_sovereign_context(self):
        fake_resonance = _FakeResonance()
        projected = []

        with patch.object(presence_server, "_get_resonance", return_value=fake_resonance), \
            patch.object(presence_server, "get_secret_fire_forge", return_value=_FakeForge()), \
            patch.object(presence_server, "_get_principal_context", return_value={"name": "Byron"}), \
            patch("backend.services.ainur.ainur_council.AinurCouncil", _FakeCouncil), \
            patch("backend.services.ainur.witness_bridge.UnifiedAinurBridge", lambda witness: witness), \
            patch("backend.services.ainur.manwe.ManweInspector", _DummyWitness), \
            patch("backend.services.ainur.varda.VardaInspector", _DummyWitness), \
            patch("backend.services.ainur.vaire.VaireInspector", _DummyWitness), \
            patch("backend.services.ainur.mandos.MandosInspector", _DummyWitness), \
            patch("backend.services.ainur.lorien.LorienInspector", _DummyWitness), \
            patch("backend.services.ainur.ulmo.UlmoInspector", _DummyWitness), \
            patch("backend.services.ainur.aule.AuleInspector", _DummyWitness), \
            patch("backend.services.os_enforcement_service.get_os_enforcement_service", return_value=_FakeOsEnforcement()), \
            patch("backend.services.constitutional_projection.project_council_advisory", side_effect=lambda advisory: projected.append(advisory)):
            result = presence_server._presence_choir_sweep(
                encounter_id="enc-1",
                text="Please check uptime and remain lawful.",
                harmonic={"discord": 0.05, "resonance": 0.95, "mode": "normal_flow"},
                covenant_state="sealed",
            )

        self.assertEqual(result["collective_testimony"], "The sovereign chorus remains harmonic.")
        self.assertEqual(_FakeCouncil.last_context["os_guard"]["is_authoritative"], True)
        self.assertEqual(_FakeCouncil.last_context["os_guard"]["phase4_attestation_gate"]["release_gate_ready"], True)
        self.assertEqual(_FakeCouncil.last_context["node_id"], "enc-1")
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["canonical_runtime_state"], "harmonic")


if __name__ == "__main__":
    unittest.main()
