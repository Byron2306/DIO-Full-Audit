from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


class HarmonicPolicyService:
    """Policy modulation layer for harmonic state."""

    @staticmethod
    def interpret_harmonic_band(harmonic_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        state = harmonic_state or {}
        resonance = float(state.get("resonance_score") or 0.0)
        discord = float(state.get("discord_score") or 0.0)
        confidence = float(state.get("confidence") or 0.0)
        sample_size = int(state.get("sample_size") or 0)
        baseline_ref = state.get("baseline_ref") or {}
        if not isinstance(baseline_ref, dict):
            baseline_ref = {}
        baseline_coverage = str(baseline_ref.get("coverage_status") or "insufficient").lower()
        baseline_quality = float(baseline_ref.get("baseline_quality") or 0.0)
        obligations: List[str] = []
        band = "normal"
        release_delay_ms = 0
        auto_privilege_allowed = False
        review_required = False

        if baseline_coverage != "explicit":
            band = "insufficient_baseline_review"
            obligations.extend([
                "manual_review_insufficient_baseline",
                "corroborate_with_vns_or_identity",
                "no_auto_privilege",
            ])
            release_delay_ms = 2500
            review_required = True
        elif sample_size < 4:
            band = "incomplete_telemetry_review"
            obligations.extend([
                "manual_review_incomplete_telemetry",
                "collect_more_timing_evidence",
                "no_auto_privilege",
            ])
            release_delay_ms = 2000
            review_required = True
        elif confidence < 0.4:
            band = "low_confidence_review"
            obligations.extend([
                "manual_review_low_confidence",
                "no_auto_privilege",
            ])
            release_delay_ms = 1500
            review_required = True
        elif confidence < 0.6 and discord >= 0.45:
            band = "low_confidence_discord_review"
            obligations.extend([
                "manual_review_low_confidence",
                "tighten_scrutiny",
                "corroborate_with_vns_or_identity",
                "no_auto_privilege",
            ])
            release_delay_ms = 2500
            review_required = True
        elif discord >= 0.8:
            band = "severe_discord"
            obligations.extend(["tighten_scrutiny", "sandbox_recommended", "triune_recheck_before_release"])
            release_delay_ms = 3000
        elif discord >= 0.6 or resonance <= 0.4:
            band = "moderate_discord"
            obligations.extend(["tighten_scrutiny", "monitor_execution_timing"])
            release_delay_ms = 1500
        elif discord >= 0.4:
            band = "mild_strain"
            obligations.append("monitor_execution_timing")
        else:
            auto_privilege_allowed = baseline_quality >= 0.8 and sample_size >= 4 and confidence >= 0.75
        return {
            "band": band,
            "obligations": list(dict.fromkeys(obligations)),
            "release_delay_ms": release_delay_ms,
            "confidence": confidence,
            "discord_score": discord,
            "resonance_score": resonance,
            "sample_size": sample_size,
            "baseline_coverage": baseline_coverage,
            "baseline_quality": baseline_quality,
            "review_required": review_required,
            "auto_privilege_allowed": auto_privilege_allowed,
        }

    def apply_harmonic_obligations(
        self,
        *,
        harmonic_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        guidance = self.interpret_harmonic_band(harmonic_state)
        release_delay_ms = int(guidance.get("release_delay_ms") or 0)
        obligations = list(guidance.get("obligations") or [])
        release_not_before = (
            (datetime.now(timezone.utc) + timedelta(milliseconds=release_delay_ms)).isoformat()
            if release_delay_ms > 0
            else None
        )
        harmonic_enforcement = {
            "elevated_scrutiny": any(
                item in obligations for item in ["tighten_scrutiny", "monitor_execution_timing"]
            ),
            "sandbox_required": "sandbox_recommended" in obligations,
            "token_narrowing_required": any(
                item in obligations for item in ["tighten_scrutiny", "no_auto_privilege"]
            ),
            "additional_approval_required": any(
                item in obligations
                for item in [
                    "manual_review_low_confidence",
                    "manual_review_insufficient_baseline",
                    "manual_review_incomplete_telemetry",
                    "triune_recheck_before_release",
                ]
            ),
            "stronger_audit_required": any(
                item in obligations
                for item in ["triune_recheck_before_release", "manual_review_insufficient_baseline"]
            ),
            "deception_preferred_routing": "sandbox_recommended" in obligations,
            "corroboration_required": "corroborate_with_vns_or_identity" in obligations,
            "release_not_before": release_not_before,
            "review_required": bool(guidance.get("review_required")),
            "auto_privilege_allowed": bool(guidance.get("auto_privilege_allowed")),
        }
        return {
            "harmonic_guidance": guidance,
            "harmonic_obligations": obligations,
            "harmonic_enforcement": harmonic_enforcement,
            "release_not_before": release_not_before,
        }


_harmonic_policy_singleton: Optional[HarmonicPolicyService] = None


def get_harmonic_policy_service() -> HarmonicPolicyService:
    global _harmonic_policy_singleton
    if _harmonic_policy_singleton is None:
        _harmonic_policy_singleton = HarmonicPolicyService()
    return _harmonic_policy_singleton
