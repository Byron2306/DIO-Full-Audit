from backend.services.harmonic_explainability import build_harmonic_explanation


def test_harmonic_explanation_contains_reconstruction_fields():
    explanation = build_harmonic_explanation(
        scope_key="baseline::actor_tool_domain_env::svc::tool::prod",
        stage="governance_authority",
        timing_features={
            "sample_size": 6,
            "timestamps_ms": [1000.0, 1200.0, 1400.0],
            "intervals_ms": [200.0, 200.0],
            "drift_norm": 0.12,
            "burstiness": 0.08,
        },
        harmonic_state={
            "resonance_score": 0.81,
            "discord_score": 0.33,
            "confidence": 0.77,
            "sample_size": 6,
        },
        baseline_ref={
            "baseline_id": "baseline::actor_tool_domain_env::svc::tool::prod",
            "scope_type": "actor_tool_domain_env",
            "coverage_status": "explicit",
            "baseline_quality": 0.88,
        },
        harmonic_guidance={
            "band": "mild_strain",
            "release_delay_ms": 1500,
            "auto_privilege_allowed": False,
        },
        harmonic_obligations=["monitor_execution_timing"],
        release_not_before="2026-08-01T12:00:01.500000+00:00",
        override_source="human_override",
        override_reason="operator accepted temporary delay",
    )

    assert explanation["scope_key"]
    assert explanation["sample_size"] == 6
    assert explanation["event_window"]["timestamps_ms"] == [1000.0, 1200.0, 1400.0]
    assert explanation["event_window"]["intervals_ms"] == [200.0, 200.0]
    assert explanation["timing_features"]["drift_norm"] == 0.12
    assert explanation["baseline_ref"]["scope_type"] == "actor_tool_domain_env"
    assert explanation["harmonic_state"]["confidence"] == 0.77
    assert explanation["inferred_band"] == "mild_strain"
    assert explanation["obligations_applied"] == ["monitor_execution_timing"]
    assert explanation["release_delay_imposed_ms"] == 1500
    assert explanation["release_not_before"] == "2026-08-01T12:00:01.500000+00:00"
    assert explanation["override_source"] == "human_override"
    assert explanation["override_reason"] == "operator accepted temporary delay"
