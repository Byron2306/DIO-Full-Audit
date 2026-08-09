from backend.schemas.polyphonic_models import BaselineRef, TimingFeatures
from backend.services.harmonic_inference import HarmonicInferenceService
from backend.services.harmonic_policy import HarmonicPolicyService


def test_harmonic_inference_service_isolated_from_feature_extraction():
    inference = HarmonicInferenceService()
    features = TimingFeatures(
        sample_size=8,
        intervals_ms=[200.0, 210.0, 195.0, 205.0],
        jitter_ms=6.2,
        jitter_norm=0.08,
        drift_norm=0.05,
        burstiness=0.02,
        entropy_signature=0.7,
        sequence_class="regular",
    )
    baseline_ref = BaselineRef(
        baseline_id="baseline::test",
        scope_type="actor_env",
        actor_id="svc",
        environment="prod",
        baseline_band={"entropy_target": 0.72, "entropy_tolerance": 0.28},
    )

    state = inference.infer_state(
        features=features,
        baseline_ref=baseline_ref,
        resonance_score=0.91,
        discord_score=0.18,
        confidence=0.82,
        spectral_factors={"micro": 1.0, "meso": 1.0, "macro": 1.0},
    )

    assert state.mode_recommendation == "normal_flow"
    assert state.resonance_score == 0.91
    assert state.discord_score == 0.18
    assert state.confidence == 0.82


def test_harmonic_policy_service_isolated_from_scoring_math():
    policy = HarmonicPolicyService()
    result = policy.apply_harmonic_obligations(
        harmonic_state={
            "resonance_score": 0.31,
            "discord_score": 0.74,
            "confidence": 0.77,
            "sample_size": 8,
            "baseline_ref": {"coverage_status": "explicit", "baseline_quality": 0.9},
        }
    )

    assert result["harmonic_guidance"]["band"] == "moderate_discord"
    assert "tighten_scrutiny" in result["harmonic_obligations"]
    assert result["release_not_before"] is not None
    assert result["harmonic_enforcement"]["elevated_scrutiny"] is True
    assert result["harmonic_enforcement"]["token_narrowing_required"] is True


def test_harmonic_policy_fails_closed_for_insufficient_baseline():
    policy = HarmonicPolicyService()
    result = policy.apply_harmonic_obligations(
        harmonic_state={
            "resonance_score": 0.92,
            "discord_score": 0.12,
            "confidence": 0.89,
            "sample_size": 12,
            "baseline_ref": {"coverage_status": "insufficient", "baseline_quality": 0.25},
        }
    )

    assert result["harmonic_guidance"]["band"] == "insufficient_baseline_review"
    assert result["harmonic_guidance"]["auto_privilege_allowed"] is False
    assert "manual_review_insufficient_baseline" in result["harmonic_obligations"]
    assert "no_auto_privilege" in result["harmonic_obligations"]
    assert result["harmonic_enforcement"]["additional_approval_required"] is True
    assert result["harmonic_enforcement"]["corroboration_required"] is True


def test_harmonic_policy_does_not_treat_low_confidence_discord_as_trust():
    policy = HarmonicPolicyService()
    result = policy.apply_harmonic_obligations(
        harmonic_state={
            "resonance_score": 0.54,
            "discord_score": 0.58,
            "confidence": 0.52,
            "sample_size": 6,
            "baseline_ref": {"coverage_status": "explicit", "baseline_quality": 0.82},
        }
    )

    assert result["harmonic_guidance"]["band"] == "low_confidence_discord_review"
    assert result["harmonic_guidance"]["review_required"] is True
    assert result["harmonic_guidance"]["auto_privilege_allowed"] is False
    assert "tighten_scrutiny" in result["harmonic_obligations"]
    assert "corroborate_with_vns_or_identity" in result["harmonic_obligations"]
    assert result["harmonic_enforcement"]["additional_approval_required"] is True
