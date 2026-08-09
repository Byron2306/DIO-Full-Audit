from __future__ import annotations

from typing import Any, Dict


HARMONIC_FIELD_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "resonance_score": {
        "formula": "sigmoid(1.4*(1-jitter_norm) + 1.6*(1-drift_norm) + 1.2*(1-burstiness) + 0.8*entropy_fit - 2.0), then spectrum-modulated",
        "domain": "[0.0, 1.0]",
        "required_sample_size": 4,
        "confidence_penalties": [
            "global fallback baseline reduces effective confidence",
            "degraded environment lowers confidence before policy use",
            "micro resonance collapse can force score to 0.0",
        ],
        "interpretation": {
            "high": "cadence is close to lawful baseline and timing structure remains stable",
            "medium": "timing is somewhat lawful but contains visible strain or adaptation",
            "low": "timing diverges materially from baseline or choral resonance is degraded",
        },
        "misuse_boundaries": [
            "must not be used as a direct trust grant without confidence and baseline context",
            "must not be treated as identity proof",
        ],
    },
    "discord_score": {
        "formula": "sigmoid(1.5*drift_norm + 1.2*jitter_norm + 1.4*burstiness + 0.9*entropy_delta + perfect_tempo_penalty - 1.6), then spectrum-boosted",
        "domain": "[0.0, 1.0]",
        "required_sample_size": 4,
        "confidence_penalties": [
            "insufficient intervals weaken inference confidence",
            "fallback baseline limits policy force",
        ],
        "interpretation": {
            "high": "timing behavior is strained, adversarial, or materially off-baseline",
            "medium": "timing drift is meaningful but not yet catastrophic",
            "low": "timing remains within expected lawful variation",
        },
        "misuse_boundaries": [
            "must not trigger irreversible action without policy review",
            "must not be equated with maliciousness in isolation",
        ],
    },
    "confidence": {
        "formula": "0.65*sample_factor + 0.35*baseline_quality - degradation_penalty",
        "domain": "[0.0, 1.0]",
        "required_sample_size": 1,
        "confidence_penalties": [
            "low sample counts sharply reduce usable confidence",
            "incident or degraded environment reduces confidence",
            "fallback baseline lowers baseline_quality",
        ],
        "interpretation": {
            "high": "harmonic inference is supported by enough cadence evidence and a credible baseline",
            "medium": "harmonic inference is directionally useful but should be policy-bounded",
            "low": "harmonic inference may only increase caution, not privilege",
        },
        "misuse_boundaries": [
            "must never be ignored when applying policy consequences",
            "low confidence must not greenlight sensitive actions",
        ],
    },
    "drift_norm": {
        "formula": "abs(observed_median_interval_ms - baseline_median_interval_ms) / max(baseline_median_interval_ms, 1.0)",
        "domain": "[0.0, 1.0] after clamp",
        "required_sample_size": 2,
        "confidence_penalties": [
            "few intervals reduce stability of the median",
            "fallback baselines make interpretation weaker",
        ],
        "interpretation": {
            "high": "median cadence has drifted materially from lawful baseline pulse",
            "medium": "visible but not extreme tempo shift",
            "low": "tempo remains near baseline",
        },
        "misuse_boundaries": [
            "must not be interpreted without reference baseline quality",
        ],
    },
    "jitter_norm": {
        "formula": "pstdev(intervals_ms) / baseline_jitter_ms",
        "domain": "[0.0, 1.0] after clamp",
        "required_sample_size": 2,
        "confidence_penalties": [
            "single-interval observations are not meaningful",
        ],
        "interpretation": {
            "high": "timing variance is materially less stable than lawful baseline",
            "medium": "variation is elevated but not extreme",
            "low": "variation remains within expected bounds",
        },
        "misuse_boundaries": [
            "must not be used as a sole determinant of discord",
        ],
    },
    "burstiness": {
        "formula": "max(0, short_interval_ratio - expected_burstiness_baseline)",
        "domain": "[0.0, 1.0] after clamp",
        "required_sample_size": 2,
        "confidence_penalties": [
            "small windows can exaggerate burst clusters",
        ],
        "interpretation": {
            "high": "rapid clustered execution exceeds lawful baseline expectation",
            "medium": "some short-interval clustering is present",
            "low": "cluster pressure stays near baseline",
        },
        "misuse_boundaries": [
            "must be considered alongside role-specific automation baselines",
        ],
    },
    "entropy_signature": {
        "formula": "normalized Shannon entropy over interval buckets",
        "domain": "[0.0, 1.0]",
        "required_sample_size": 4,
        "confidence_penalties": [
            "few buckets with low sample counts reduce interpretability",
        ],
        "interpretation": {
            "high": "interval distribution is varied across buckets",
            "medium": "distribution has moderate diversity",
            "low": "distribution is overly regular or concentrated",
        },
        "misuse_boundaries": [
            "must not be treated as maliciousness on its own",
        ],
    },
    "sequence_class": {
        "formula": "categorical classifier over median interval and coefficient of variation",
        "domain": "{cold_start, rapid_regular, regular, chaotic, adaptive}",
        "required_sample_size": 2,
        "confidence_penalties": [
            "cold_start means no meaningful sequence conclusion yet",
        ],
        "interpretation": {
            "rapid_regular": "high-speed, low-variance sequence",
            "regular": "stable lawful-looking sequence",
            "chaotic": "high-variance irregular sequence",
            "adaptive": "mixed tempo with meaningful variance",
            "cold_start": "insufficient sequence evidence",
        },
        "misuse_boundaries": [
            "must not be used as a severity score",
            "must remain descriptive unless combined with other harmonic fields",
        ],
    },
}


def get_harmonic_ontology() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in HARMONIC_FIELD_DEFINITIONS.items()}
