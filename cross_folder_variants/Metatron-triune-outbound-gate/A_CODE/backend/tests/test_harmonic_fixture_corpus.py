from backend.services.harmonic_engine import HarmonicEngine
from backend.services.harmonic_fixture_corpus import (
    get_harmonic_fixture_corpus,
    replay_fixture,
)
from backend.services.resonance_service import get_resonance_service


def _assert_expected_ranges(state, expected):
    if "band" in expected:
        assert state["mode_recommendation"] == expected["band"]
    if "resonance_min" in expected:
        assert state["resonance_score"] >= expected["resonance_min"]
    if "resonance_max" in expected:
        assert state["resonance_score"] <= expected["resonance_max"]
    if "discord_min" in expected:
        assert state["discord_score"] >= expected["discord_min"]
    if "discord_max" in expected:
        assert state["discord_score"] <= expected["discord_max"]
    if "confidence_min" in expected:
        assert state["confidence"] >= expected["confidence_min"]
    if "confidence_max" in expected:
        assert state["confidence"] <= expected["confidence_max"]


def test_harmonic_fixture_corpus_covers_all_phase_2g_scenarios():
    fixtures = get_harmonic_fixture_corpus()
    fixture_ids = {fixture["fixture_id"] for fixture in fixtures}
    assert fixture_ids == {
        "lawful_human_admin_session",
        "rapid_lawful_automation",
        "noisy_benign_burst",
        "autonomous_reconnaissance",
        "autonomous_exfil_staging",
        "compromised_but_human",
        "replay_timing_spoof",
        "incomplete_telemetry_window",
    }


def test_harmonic_fixture_corpus_replays_expected_bands():
    get_resonance_service().reset()
    for fixture in get_harmonic_fixture_corpus():
        engine = HarmonicEngine(window_size=64)
        result = replay_fixture(engine, fixture)
        state = result["harmonic_state"]
        _assert_expected_ranges(state, fixture["expected"])


def test_harmonic_fixture_corpus_can_compare_threshold_changes():
    fixtures = get_harmonic_fixture_corpus()
    get_resonance_service().reset()
    baseline_engine = HarmonicEngine(window_size=64)
    baseline_outcomes = {}
    for fixture in fixtures:
        result = replay_fixture(baseline_engine, fixture)
        baseline_outcomes[fixture["fixture_id"]] = {
            "mode": result["harmonic_state"]["mode_recommendation"],
            "discord": result["harmonic_state"]["discord_score"],
            "resonance": result["harmonic_state"]["resonance_score"],
        }

    class ComparisonEngine(HarmonicEngine):
        def compute_discord_score(self, features, baseline_ref):
            base = super().compute_discord_score(features, baseline_ref)
            return min(1.0, round(base + 0.08, 6))

        def compute_resonance_score(self, features, baseline_ref):
            base = super().compute_resonance_score(features, baseline_ref)
            return max(0.0, round(base - 0.05, 6))

    get_resonance_service().reset()
    tuned_engine = ComparisonEngine(window_size=64)

    changed = 0
    for fixture in fixtures:
        result = replay_fixture(tuned_engine, fixture)
        current = result["harmonic_state"]
        baseline = baseline_outcomes[fixture["fixture_id"]]
        if (
            abs(current["discord_score"] - baseline["discord"]) > 0.01
            or abs(current["resonance_score"] - baseline["resonance"]) > 0.01
            or current["mode_recommendation"] != baseline["mode"]
        ):
            changed += 1

    assert changed >= 1
