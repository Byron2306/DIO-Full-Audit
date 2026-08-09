from __future__ import annotations

from typing import Any, Dict, Optional


def build_harmonic_explanation(
    *,
    scope_key: Optional[str],
    stage: str,
    timing_features: Optional[Dict[str, Any]],
    harmonic_state: Optional[Dict[str, Any]],
    baseline_ref: Optional[Dict[str, Any]],
    harmonic_guidance: Optional[Dict[str, Any]] = None,
    harmonic_obligations: Optional[list[str]] = None,
    release_not_before: Optional[str] = None,
    override_source: Optional[str] = None,
    override_reason: Optional[str] = None,
) -> Dict[str, Any]:
    timing = dict(timing_features or {})
    state = dict(harmonic_state or {})
    baseline = dict(baseline_ref or {})
    guidance = dict(harmonic_guidance or {})
    return {
        "stage": stage,
        "scope_key": scope_key,
        "sample_size": int(timing.get("sample_size") or 0),
        "event_window": {
            "timestamps_ms": list(timing.get("timestamps_ms") or []),
            "intervals_ms": list(timing.get("intervals_ms") or []),
        },
        "timing_features": timing,
        "baseline_ref": baseline,
        "harmonic_state": state,
        "inferred_band": guidance.get("band"),
        "confidence": state.get("confidence"),
        "obligations_applied": list(harmonic_obligations or []),
        "release_delay_imposed_ms": guidance.get("release_delay_ms"),
        "release_not_before": release_not_before,
        "override_source": override_source,
        "override_reason": override_reason,
    }
