from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:
    from backend.schemas.polyphonic_models import BaselineRef, HarmonicState, TimingFeatures
except Exception:
    from schemas.polyphonic_models import BaselineRef, HarmonicState, TimingFeatures  # type: ignore


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


class HarmonicInferenceService:
    """State inference layer for harmonic scoring."""

    @staticmethod
    def mode_recommendation(resonance: float, discord: float, confidence: float) -> Tuple[str, List[str]]:
        rationale: List[str] = []
        if confidence < 0.4:
            rationale.append("low confidence due to limited cadence evidence")
            return "observe_and_review", rationale
        if discord >= 0.85:
            rationale.append("extreme discord score")
            return "sandbox_or_contain", rationale
        if discord >= 0.65:
            rationale.append("high discord score")
            return "tighten_scrutiny", rationale
        if discord >= 0.45 or resonance <= 0.45:
            rationale.append("moderate timing strain")
            return "monitor_with_obligations", rationale
        rationale.append("timing resonance within expected bounds")
        return "normal_flow", rationale

    def infer_state(
        self,
        *,
        features: TimingFeatures,
        baseline_ref: BaselineRef,
        resonance_score: float,
        discord_score: float,
        confidence: float,
        spectral_factors: Dict[str, float],
        signal_context: Dict[str, float] | None = None,
    ) -> HarmonicState:
        mode_recommendation, rationale = self.mode_recommendation(resonance_score, discord_score, confidence)
        signal_context = signal_context or {}
        if str(getattr(baseline_ref, "coverage_status", "insufficient")) != "explicit":
            rationale.append("insufficient reviewed baseline coverage for trusted harmonic inference")
        if float(signal_context.get("world_graph_pressure", 0.0)) >= 0.4:
            rationale.append(
                f"world-graph pressure elevated:{signal_context.get('world_graph_pressure')}"
            )
        if float(signal_context.get("aatl_pressure", 0.0)) >= 0.45:
            rationale.append(
                f"AATL pressure elevated:{signal_context.get('aatl_pressure')}"
            )
        if float(signal_context.get("vns_pressure", 0.0)) >= 0.3:
            rationale.append(
                f"VNS pressure elevated:{signal_context.get('vns_pressure')}"
            )
        if float(signal_context.get("deception_pressure", 0.0)) >= 0.2:
            rationale.append(
                f"deception pressure elevated:{signal_context.get('deception_pressure')}"
            )
        if float(spectral_factors.get("micro", 1.0)) < 0.8:
            rationale.append(f"Infrasound (Micro) dissonance: {spectral_factors.get('micro')}")
        if float(spectral_factors.get("meso", 1.0)) < 0.8:
            rationale.append(f"Mid-range (Meso) rhythm drift: {spectral_factors.get('meso')}")
        if float(features.burstiness or 0.0) > 0.35:
            rationale.append("burstiness above expected range")
        if float(features.drift_norm or 0.0) > 0.35:
            rationale.append("cadence drift from baseline pulse")
        if float(features.jitter_norm or 0.0) > 0.5:
            rationale.append("jitter instability exceeds baseline band")

        return HarmonicState(
            resonance_score=_clamp(resonance_score),
            discord_score=_clamp(discord_score),
            confidence=_clamp(confidence),
            baseline_ref=baseline_ref,
            mode_recommendation=mode_recommendation,
            drift_norm=features.drift_norm,
            jitter_norm=features.jitter_norm,
            burstiness=features.burstiness,
            entropy_signature=features.entropy_signature,
            rationale=rationale,
        )


_harmonic_inference_singleton: HarmonicInferenceService | None = None


def get_harmonic_inference_service() -> HarmonicInferenceService:
    global _harmonic_inference_singleton
    if _harmonic_inference_singleton is None:
        _harmonic_inference_singleton = HarmonicInferenceService()
    return _harmonic_inference_singleton
