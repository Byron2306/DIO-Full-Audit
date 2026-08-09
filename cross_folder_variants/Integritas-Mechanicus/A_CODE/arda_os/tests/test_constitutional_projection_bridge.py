import types
import unittest
from unittest.mock import patch

from backend.services.ainur.verdicts import ChoirVerdict
from backend.services.constitutional_projection import (
    canonical_runtime_state_from_advisory,
    project_council_advisory,
    project_choir_truth,
)


class _FakeBridge:
    def __init__(self):
        self.states = {}

    def update_state(self, entity_id, amplitude):
        self.states[entity_id] = amplitude


class _FakeMandos:
    def __init__(self):
        self.events = []

    def record_event(self, **kwargs):
        self.events.append(kwargs)


class _FakeValinor:
    def __init__(self):
        self.bridge = _FakeBridge()
        self.taniquetil = types.SimpleNamespace(mandos=_FakeMandos())


class _FakeFabric:
    def __init__(self):
        self.subjects = []
        self.amplitudes = []

    def ensure_subject(self, node_id, workload_hash=None, executable_path=None):
        self.subjects.append(
            {
                "node_id": node_id,
                "workload_hash": workload_hash,
                "executable_path": executable_path,
            }
        )

    def update_resonance_amplitude(self, node_id, amplitude):
        self.amplitudes.append((node_id, amplitude))


class _FakeFlow:
    def __init__(self):
        self.shines = []

    async def shine_light(self, entity_id, budget, source_reason=""):
        self.shines.append((entity_id, budget.constitutional_state, source_reason))


class ConstitutionalProjectionBridgeTest(unittest.IsolatedAsyncioTestCase):
    async def test_project_council_advisory_projects_harmonic_state(self):
        fake_valinor = _FakeValinor()
        fake_fabric = _FakeFabric()
        fake_flow = _FakeFlow()
        advisory = {
            "principal": "root-host-phase6",
            "node_id": "node-alpha",
            "lane": "Shire",
            "action": "AUTONOMOUS_GRANT",
            "overall_recommendation": "HARMONIC",
            "collective_testimony": "The Council sings in lawful harmony.",
            "command": "/usr/bin/uptime",
            "provenance_attestation": {
                "payload": {
                    "artifact_digest": "sha256:abc123",
                }
            },
            "harmonic_observation": {
                "event": {
                    "target_domain": "/usr/bin/uptime",
                }
            },
        }

        with patch("backend.services.constitutional_projection.get_projection_valinor_runtime", return_value=fake_valinor), \
            patch("backend.services.constitutional_projection.get_projection_arda_fabric", return_value=fake_fabric), \
            patch("backend.services.constitutional_projection.get_projection_earendil_flow", return_value=fake_flow):
            amplitude = await project_council_advisory(advisory)

        self.assertEqual(amplitude.constitutional_state, "harmonic")
        self.assertIn("root-host-phase6", fake_valinor.bridge.states)
        self.assertEqual(fake_fabric.subjects[0]["node_id"], "node-alpha")
        self.assertEqual(fake_fabric.subjects[0]["workload_hash"], "sha256:abc123")
        self.assertEqual(fake_fabric.subjects[0]["executable_path"], "/usr/bin/uptime")
        self.assertEqual(fake_valinor.taniquetil.mandos.events[0]["event_type"], "council_projection")

    async def test_project_choir_truth_preserves_fallen_path(self):
        fake_valinor = _FakeValinor()
        fake_fabric = _FakeFabric()
        fake_flow = _FakeFlow()
        verdict = ChoirVerdict(
            overall_state="vetoed",
            heralding_allowed=False,
            confidence=0.91,
            ainur=[],
            reasons=["Red-line violation"],
            subject_id="entity-x",
            node_id="node-x",
        )

        with patch("backend.services.constitutional_projection.get_projection_valinor_runtime", return_value=fake_valinor), \
            patch("backend.services.constitutional_projection.get_projection_arda_fabric", return_value=fake_fabric), \
            patch("backend.services.constitutional_projection.get_projection_earendil_flow", return_value=fake_flow):
            amplitude = await project_choir_truth(verdict)

        self.assertEqual(amplitude.constitutional_state, "fallen")
        self.assertEqual(fake_valinor.taniquetil.mandos.events[0]["event_type"], "choir_projection")

    def test_canonical_runtime_state_from_advisory(self):
        self.assertEqual(
            canonical_runtime_state_from_advisory(
                {"canonical_runtime_state": "dissonant"}
            ),
            "dissonant",
        )
        self.assertEqual(
            canonical_runtime_state_from_advisory(
                {"overall_recommendation": "HARMONIC", "lane": "Gondor", "action": "ESCALATE_TO_COUNCIL"}
            ),
            "strained",
        )


if __name__ == "__main__":
    unittest.main()
