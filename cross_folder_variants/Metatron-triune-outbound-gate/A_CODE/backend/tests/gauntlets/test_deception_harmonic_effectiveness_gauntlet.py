import pytest

from backend.scripts.deception_harmonic_effectiveness_gauntlet import run_gauntlet


@pytest.mark.asyncio
async def test_deception_harmonic_effectiveness_gauntlet_passes():
    summary = await run_gauntlet()

    assert summary["all_passed"] is True
    assert summary["passed"] == summary["total"]
    assert summary["score"] == 1.0

    scenario_names = {result["name"] for result in summary["results"]}
    assert "trusted_principal_block" in scenario_names
    assert "harmonic_veto_blocks_aggressive_deception" in scenario_names
    assert "anti_feedback_loop_requires_independent_corroboration" in scenario_names
    assert "outbound_gate_binds_revocable_deception_provenance" in scenario_names
