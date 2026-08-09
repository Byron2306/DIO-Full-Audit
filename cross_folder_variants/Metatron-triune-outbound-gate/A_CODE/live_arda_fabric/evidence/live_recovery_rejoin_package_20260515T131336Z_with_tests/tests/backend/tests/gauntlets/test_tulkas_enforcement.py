import sys
import os
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Project root assumed to be in sys.path via run_sovereign_audit.py
from backend.arda.ainur import AinurChoir, ChoirVerdict, AinurVerdict
from backend.services.tulkas_executor import TulkasExecutor, TulkasPosture

class MockWorldModel:
    def __init__(self):
        self.constitutional_failure_count = 0
    def increment_failure_count(self):
        self.constitutional_failure_count += 1
        return self.constitutional_failure_count
    def reset_failure_count(self):
        self.constitutional_failure_count = 0
    def get_failure_count(self):
        return self.constitutional_failure_count

def mock_choir_verdict(state="vetoed", allowed=False, score=0.0):
    return ChoirVerdict(
        overall_state=state,
        heralding_allowed=allowed,
        confidence=score,
        ainur=[],
        reasons=["Test failure"]
    )

async def _test_tulkas_ladder():
    print("\n--- Testing Tulkas: ENFORCEMENT LADDER ---")
    wm = MockWorldModel()
    tulkas = TulkasExecutor(wm)
    valinor_runtime = SimpleNamespace(taniquetil=SimpleNamespace(mandos=SimpleNamespace(is_fallen=lambda _node_id: False)))
    fake_fabric = SimpleNamespace(update_resonance_amplitude=lambda *args, **kwargs: None, get_pid_for_node=lambda _node_id: None)
    fake_amplitude = SimpleNamespace(exec_rights="full", quorum_weight=1.0, network_trust=1.0, syscall_scope="full")
    fake_earendil = SimpleNamespace(shine_light=AsyncMock())

    with patch.object(TulkasExecutor, "_apply_actuators", new=AsyncMock()), \
         patch("backend.valinor.runtime_hooks.get_valinor_runtime", return_value=valinor_runtime), \
         patch("backend.services.tulkas_executor.get_arda_fabric", return_value=fake_fabric), \
         patch("backend.services.tulkas_executor.get_earendil_flow", return_value=fake_earendil), \
         patch("backend.services.tulkas_executor.get_house_fingolfin"), \
         patch("backend.arda.ainur.dissonance.ResonanceMapper.from_choir_state", return_value=fake_amplitude):

        # 1. Fresh Veto -> CONTAIN
        print("Testing First Veto...")
        verdict = mock_choir_verdict(state="vetoed")
        posture = await tulkas.execute_enforcement(verdict, "test-node")
        print(f"Post-Veto Posture: {posture}")
        assert posture == TulkasPosture.CONTAIN
        assert wm.get_failure_count() == 1

        # 2. Repeated Vetoes -> PURGE (at 4 failures)
        print("\nTesting Repeated Vetoes...")
        await tulkas.execute_enforcement(verdict, "test-node") # 2
        await tulkas.execute_enforcement(verdict, "test-node") # 3
        posture = await tulkas.execute_enforcement(verdict, "test-node") # 4
        print(f"Posture after 4 failures: {posture}")
        assert posture == TulkasPosture.PURGE

        # 3. Harmony -> RESET
        print("\nTesting Harmony Reset...")
        harmonic_verdict = mock_choir_verdict(state="harmonic", allowed=True, score=1.0)
        await tulkas.execute_enforcement(harmonic_verdict, "test-node")
        print(f"Failure count after harmony: {wm.get_failure_count()}")
        assert wm.get_failure_count() == 0

        # 4. Fresh Withheld -> RESTRAIN
        print("\nTesting First Withheld...")
        withheld_verdict = mock_choir_verdict(state="withheld")
        posture = await tulkas.execute_enforcement(withheld_verdict, "test-node")
        print(f"Posture after first Withheld: {posture}")
        assert posture == TulkasPosture.RESTRAIN

def test_tulkas_ladder():
    """Synchronous wrapper for pytest compatibility."""
    asyncio.run(_test_tulkas_ladder())

async def _test_aule_fallen():
    print("\n--- Testing Aulë: FALLEN STATE DETECTION ---")
    from backend.arda.ainur.aule import AuleInspector
    aule = AuleInspector()
    
    class FakeContext:
        def __init__(self, failures):
            self.failure_count = failures
            self.prior_verdicts = [
                AinurVerdict(ainur="vaire", state="lawful", score=1.0, reasons=["Test OK"]),
                AinurVerdict(ainur="varda", state="radiant", score=1.0, reasons=["Test OK"]),
                AinurVerdict(ainur="manwe", state="flowing", score=1.0, reasons=["Test OK"]),
                AinurVerdict(ainur="mandos", state="remembered", score=1.0, reasons=["Test OK"]),
                AinurVerdict(ainur="ulmo", state="clear", score=1.0, reasons=["Test OK"])
            ]
            # Provide a valid secret fire mock so Aulë doesn't veto
            self.secret_fire = MagicMock(freshness_valid=True, replay_suspected=False)
            
    # Under 10 failures -> harmonic
    ctx_normal = FakeContext(2)
    verdict_normal = aule.inspect(ctx_normal)
    print(f"Result with 2 failures: {verdict_normal.state}")
    assert verdict_normal.state == "harmonic"

    # 10 or more failures -> fallen
    ctx_fallen = FakeContext(10)
    verdict_fallen = aule.inspect(ctx_fallen)
    print(f"Result with 10 failures: {verdict_fallen.state}")
    assert verdict_fallen.state == "fallen"

def test_aule_fallen():
    """Synchronous wrapper for pytest compatibility."""
    asyncio.run(_test_aule_fallen())

if __name__ == "__main__":
    asyncio.run(_test_tulkas_ladder())
    asyncio.run(_test_aule_fallen())
    print("\nAll Tulkas enforcement tests PASSED.")
