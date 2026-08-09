import asyncio

from backend.services.ainur.dissonance import ResonanceMapper
from backend.services.earendil_flow import get_earendil_flow
from backend.services.gates_of_night import get_boundary_guard
from backend.valinor.runtime_hooks import get_valinor_runtime


def test_gates_of_night_uses_shared_valinor_runtime():
    async def scenario():
        runtime = get_valinor_runtime()
        guard = get_boundary_guard()

        assert await guard.evaluate_egress("https://metatron.ai/api", {"entity_id": "pid:test"}) is True
        assert await guard.evaluate_egress("https://unsafe-void.example/leak", {"entity_id": "pid:test"}) is False

        sealed = ResonanceMapper.from_choir_state("pid:sealed", "harmonic")
        sealed.egress_rights = "star_seal"
        runtime.bridge.update_state("pid:sealed", sealed)

        assert await guard.evaluate_egress("https://unsafe-void.example/leak", {"entity_id": "pid:sealed"}) is True

    asyncio.run(scenario())


def test_earendil_flow_updates_shared_valinor_runtime_and_denies_execve():
    async def scenario():
        runtime = get_valinor_runtime()
        flow = get_earendil_flow()
        muted = ResonanceMapper.from_choir_state("pid:shadow", "muted")

        await flow.receive_summons(
            {
                "type": "earendil_signal",
                "entity_id": "pid:shadow",
                "resonance": muted.model_dump(),
                "issuer": "test-node",
            }
        )

        assert runtime.bridge.get_state("pid:shadow").constitutional_state == "muted"
        try:
            runtime.syscall("pid:shadow", "execve")
        except PermissionError:
            return
        raise AssertionError("muted entity execve should be denied")
