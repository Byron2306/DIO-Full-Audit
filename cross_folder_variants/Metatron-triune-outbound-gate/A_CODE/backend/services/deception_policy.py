from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

try:
    from backend.schemas.deception_models import DeceptionConfidenceBand, DeceptionMode
except Exception:
    from schemas.deception_models import DeceptionConfidenceBand, DeceptionMode  # type: ignore


_CONFIDENCE_RANK = {
    DeceptionConfidenceBand.LOW: 1,
    DeceptionConfidenceBand.MEDIUM: 2,
    DeceptionConfidenceBand.HIGH: 3,
}


@dataclass(frozen=True)
class DeceptionEscalationPolicy:
    mode: str
    minimum_confidence: DeceptionConfidenceBand
    evidence_classes: List[str]
    allowable_scope: str
    rollback_rule: str
    approval_requirement: str
    audit_requirement: str
    allowed_output_classes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "minimum_confidence": self.minimum_confidence.value,
            "evidence_classes": list(self.evidence_classes),
            "allowable_scope": self.allowable_scope,
            "rollback_rule": self.rollback_rule,
            "approval_requirement": self.approval_requirement,
            "audit_requirement": self.audit_requirement,
            "allowed_output_classes": list(self.allowed_output_classes),
        }


POLICY_MATRIX: Dict[str, DeceptionEscalationPolicy] = {
    "observe": DeceptionEscalationPolicy(
        mode="observe",
        minimum_confidence=DeceptionConfidenceBand.LOW,
        evidence_classes=["anomaly_signal"],
        allowable_scope="session_monitoring_only",
        rollback_rule="return_to_passive_monitoring_on_signal_decay",
        approval_requirement="none",
        audit_requirement="case_record_required",
        allowed_output_classes=[],
    ),
    "friction": DeceptionEscalationPolicy(
        mode="friction",
        minimum_confidence=DeceptionConfidenceBand.LOW,
        evidence_classes=["anomaly_signal", "timing_signal"],
        allowable_scope="timing_and_challenge_controls",
        rollback_rule="drop_to_observe_when_risk_or_confidence_falls",
        approval_requirement="none",
        audit_requirement="case_record_and_delay_log_required",
        allowed_output_classes=["timing_friction"],
    ),
    "disinformation": DeceptionEscalationPolicy(
        mode="disinformation",
        minimum_confidence=DeceptionConfidenceBand.MEDIUM,
        evidence_classes=["multi_signal_probe", "synthetic_safety_clearance"],
        allowable_scope="single_response_synthetic_payloads_only",
        rollback_rule="downgrade_to_friction_on_validator_or_confidence_failure",
        approval_requirement="automatic_if_policy_and_validator_clear",
        audit_requirement="case_record_payload_hash_and_serve_log_required",
        allowed_output_classes=["synthetic_payload"],
    ),
    "mirror_world": DeceptionEscalationPolicy(
        mode="mirror_world",
        minimum_confidence=DeceptionConfidenceBand.HIGH,
        evidence_classes=["agentic_behavior", "decoy_touch_or_logic_pressure", "synthetic_safety_clearance"],
        allowable_scope="session_bound_synthetic_graph_state",
        rollback_rule="collapse_to_friction_or_observe_on_governance_or_safety_veto",
        approval_requirement="automatic_if_high_confidence_and_governance_clear",
        audit_requirement="case_record_maze_id_traversal_log_and_outcome_timeline_required",
        allowed_output_classes=["synthetic_graph_state"],
    ),
    "containment_prep": DeceptionEscalationPolicy(
        mode="containment_prep",
        minimum_confidence=DeceptionConfidenceBand.HIGH,
        evidence_classes=["persistent_hostility", "operator_or_governance_signal"],
        allowable_scope="handoff_preparation_and_non-deceptive_containment_readying",
        rollback_rule="return_to_mirror_world_or_friction_if_hostility_signal_weakens",
        approval_requirement="operator_review_or_governance_authority_required",
        audit_requirement="case_record_handoff_reason_and_approval_reference_required",
        allowed_output_classes=["containment_handoff"],
    ),
}


def get_policy_matrix() -> Dict[str, Dict[str, Any]]:
    return {key: value.to_dict() for key, value in POLICY_MATRIX.items()}


def evaluate_deception_escalation(
    *,
    desired_mode: DeceptionMode,
    confidence_band: DeceptionConfidenceBand,
    triggering_signals: List[str],
    trusted_principal_blocked: bool,
    harmonic_veto: bool,
) -> Dict[str, Any]:
    desired_key = desired_mode.value
    policy = POLICY_MATRIX.get(desired_key, POLICY_MATRIX["observe"])
    observed: Set[str] = {str(item) for item in (triggering_signals or []) if item}

    def _satisfies(required: str) -> bool:
        if required == "synthetic_safety_clearance":
            return True
        if required == "anomaly_signal":
            return len(observed) >= 1
        if required == "timing_signal":
            return any("timing" in signal or "machine" in signal for signal in observed)
        if required == "multi_signal_probe":
            return len(observed) >= 2
        if required == "agentic_behavior":
            return any(
                marker in signal
                for signal in observed
                for marker in {"agenticity", "machine", "mirror_world", "logic_budget"}
            )
        if required == "decoy_touch_or_logic_pressure":
            return any(
                marker in signal
                for signal in observed
                for marker in {"decoy_touched", "logic_budget", "trap", "honeypot"}
            )
        if required == "persistent_hostility":
            return any(
                marker in signal
                for signal in observed
                for marker in {"persistent", "repeat", "trap", "campaign"}
            )
        if required == "operator_or_governance_signal":
            return any(
                marker in signal
                for signal in observed
                for marker in {"governance", "operator", "manual"}
            )
        return any(required in signal for signal in observed)

    if trusted_principal_blocked or harmonic_veto:
        fallback = POLICY_MATRIX["observe"]
        return {
            "transition_allowed": False,
            "approved_mode": DeceptionMode.OBSERVE,
            "policy": fallback.to_dict(),
            "denial_reasons": [
                "trusted_principal_blocked" if trusted_principal_blocked else None,
                "governance_veto" if harmonic_veto else None,
            ],
        }

    min_conf_ok = _CONFIDENCE_RANK[confidence_band] >= _CONFIDENCE_RANK[policy.minimum_confidence]
    evidence_ok = all(_satisfies(required) for required in policy.evidence_classes)

    if not min_conf_ok:
        fallback = POLICY_MATRIX["friction"] if desired_mode in {DeceptionMode.DISINFORMATION, DeceptionMode.MIRROR_WORLD} else POLICY_MATRIX["observe"]
        return {
            "transition_allowed": False,
            "approved_mode": DeceptionMode(fallback.mode) if fallback.mode in {m.value for m in DeceptionMode} else DeceptionMode.OBSERVE,
            "policy": fallback.to_dict(),
            "denial_reasons": ["minimum_confidence_not_met"],
        }

    if not evidence_ok and desired_mode not in {DeceptionMode.OBSERVE, DeceptionMode.FRICTION}:
        fallback = POLICY_MATRIX["friction"]
        return {
            "transition_allowed": False,
            "approved_mode": DeceptionMode.FRICTION,
            "policy": fallback.to_dict(),
            "denial_reasons": ["required_evidence_classes_not_met"],
        }

    return {
        "transition_allowed": True,
        "approved_mode": desired_mode,
        "policy": policy.to_dict(),
        "denial_reasons": [],
    }
