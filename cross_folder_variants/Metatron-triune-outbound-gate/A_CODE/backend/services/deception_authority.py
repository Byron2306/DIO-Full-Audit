from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.schemas.deception_models import (
    DeceptionCase,
    DeceptionConfidenceBand,
    DeceptionMode,
    DeceptionRiskBand,
    DeceptionValidationResult,
)
from backend.services.governance_authority import GovernanceDecisionAuthority
from backend.services.deception_policy import evaluate_deception_escalation

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)
    return dict(model)


class DeceptionAuthorityService:
    """
    Canonical Phase 1 deception contract + safety enforcement layer.

    This service does not replace Mystique or the disinformation engine.
    It sits in front of them and decides whether those engines may be used,
    under what mode, and with what safety constraints.
    """

    REAL_SECRET_PATTERNS = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE KEY)-----"),
        re.compile(r"sk_live_[0-9a-zA-Z]{16,}"),
        re.compile(r"sk-[0-9a-zA-Z]{24,}"),
        re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
        re.compile(r"gh[pousr]_[0-9A-Za-z]{20,}"),
    ]

    FORBIDDEN_HOST_PATTERNS = [
        re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)\b", re.I),
        re.compile(r"\.corp\.internal\b", re.I),
        re.compile(r"\.localdomain\b", re.I),
    ]

    REAL_PATH_PATTERNS = [
        re.compile(r"/etc/(?:passwd|shadow|ssh|kubernetes)\b", re.I),
        re.compile(r"/var/run/secrets/", re.I),
        re.compile(r"/home/[^/]+/\.ssh/", re.I),
        re.compile(r"/root/\.kube/config", re.I),
    ]

    REAL_SCHEMA_PATTERNS = [
        re.compile(r"openapi['\"]?\s*:\s*['\"]?3\.", re.I),
        re.compile(r"/api/v[0-9]+/secrets", re.I),
        re.compile(r"x-requires-role", re.I),
    ]

    TRUST_BLOCK_SIGNALS = {
        "trusted_principal",
        "trusted_agent",
        "verified_internal",
        "human_admin",
        "lawful_operator",
    }

    def __init__(self, db: Any = None):
        self.db = db

    @staticmethod
    def _harmonic_guardrails(
        harmonic_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        state = harmonic_state or {}
        if not state:
            return {
                "guidance": {},
                "band": "normal",
                "obligations": [],
                "veto": False,
                "veto_reasons": [],
            }
        if GovernanceDecisionAuthority is not None:
            try:
                guidance = GovernanceDecisionAuthority.interpret_harmonic_band(state)
            except Exception:
                guidance = {}
        else:
            guidance = {}

        band = str(guidance.get("band") or "normal")
        obligations = list(guidance.get("obligations") or [])
        confidence = float(state.get("confidence") or guidance.get("confidence") or 0.0)
        discord = float(state.get("discord_score") or guidance.get("discord_score") or 0.0)
        resonance = float(state.get("resonance_score") or guidance.get("resonance_score") or 0.0)
        if band in {"normal", "insufficient_baseline_review", "incomplete_telemetry_review"}:
            if confidence < 0.4:
                band = "low_confidence_review"
            elif discord >= 0.85:
                band = "severe_discord"
            elif discord >= 0.65:
                band = "moderate_discord"
            elif discord >= 0.45 or resonance <= 0.45:
                band = "mild_strain"

        veto_reasons: List[str] = []
        if band in {"severe_discord", "low_confidence_review"}:
            veto_reasons.append(f"harmonic_band:{band}")
        if discord >= 0.85:
            veto_reasons.append("harmonic_discord_critical")
        if confidence < 0.35:
            veto_reasons.append("harmonic_confidence_too_low")
        if resonance <= 0.20 and discord >= 0.65:
            veto_reasons.append("harmonic_resonance_collapse")

        return {
            "guidance": guidance,
            "band": band,
            "obligations": obligations,
            "veto": len(veto_reasons) > 0,
            "veto_reasons": veto_reasons,
        }

    @staticmethod
    def _harmonic_shaped_mode(
        *,
        desired_mode: DeceptionMode,
        harmonic_state: Optional[Dict[str, Any]],
        harmonic_guard: Dict[str, Any],
        behavior_flags: Dict[str, Any],
    ) -> Tuple[DeceptionMode, List[str]]:
        state = harmonic_state or {}
        reasons: List[str] = []
        if not state:
            return desired_mode, reasons

        band = str(harmonic_guard.get("band") or "normal").lower()
        confidence = float(state.get("confidence") or 0.0)
        discord = float(state.get("discord_score") or 0.0)
        autonomy_confidence = max(
            float(behavior_flags.get("machine_plausibility") or 0.0),
            float(behavior_flags.get("agenticity_score") or 0.0),
        )

        if confidence < 0.4:
            reasons.append("harmonic_low_confidence_blocks_aggressive_synthetic_content")
            return DeceptionMode.OBSERVE, reasons

        if desired_mode == DeceptionMode.MIRROR_WORLD:
            if discord >= 0.8 and confidence >= 0.65 and autonomy_confidence >= 0.75:
                reasons.append("severe_discord_plus_high_autonomy_confidence_mirror_world_eligible")
                return DeceptionMode.MIRROR_WORLD, reasons
            if discord >= 0.6:
                reasons.append("moderate_discord_caps_deception_below_mirror_world")
                return DeceptionMode.DISINFORMATION, reasons
            reasons.append("mirror_world_requires_severe_discord_and_high_autonomy_confidence")
            return DeceptionMode.DISINFORMATION, reasons

        if band in {"mild_strain", "low_confidence_review"} and confidence < 0.6:
            reasons.append("mild_strain_with_low_confidence_observation_only")
            return DeceptionMode.OBSERVE, reasons

        if band in {"moderate_discord", "low_confidence_discord_review"} or discord >= 0.6:
            if desired_mode == DeceptionMode.MIRROR_WORLD:
                reasons.append("moderate_discord_caps_deception_below_mirror_world")
                return DeceptionMode.DISINFORMATION, reasons
            if desired_mode not in {DeceptionMode.OBSERVE, DeceptionMode.FRICTION, DeceptionMode.DISINFORMATION}:
                reasons.append("moderate_discord_allows_friction_or_disinformation_only")
                return DeceptionMode.FRICTION, reasons
            reasons.append("moderate_discord_allows_bounded_active_deception")
            return desired_mode, reasons

        return desired_mode, reasons

    @staticmethod
    def _risk_band_from_score(score: int) -> DeceptionRiskBand:
        if score >= 90:
            return DeceptionRiskBand.CRITICAL
        if score >= 75:
            return DeceptionRiskBand.HIGH
        if score >= 45:
            return DeceptionRiskBand.MEDIUM
        return DeceptionRiskBand.LOW

    @staticmethod
    def _confidence_band(
        *,
        machine_plausibility: float = 0.0,
        agenticity_score: float = 0.0,
        decoy_touched: bool = False,
    ) -> DeceptionConfidenceBand:
        blended = max(float(machine_plausibility or 0.0), float(agenticity_score or 0.0))
        if decoy_touched:
            blended = max(blended, 0.9)
        if blended >= 0.75:
            return DeceptionConfidenceBand.HIGH
        if blended >= 0.45:
            return DeceptionConfidenceBand.MEDIUM
        return DeceptionConfidenceBand.LOW

    @staticmethod
    def _independent_corroboration_guard(
        *,
        desired_mode: DeceptionMode,
        triggering_signals: List[str],
        behavior_flags: Dict[str, Any],
        harmonic_guard: Dict[str, Any],
    ) -> Dict[str, Any]:
        if desired_mode != DeceptionMode.MIRROR_WORLD:
            return {
                "required": False,
                "satisfied": True,
                "sources": [],
                "missing_sources": [],
                "reasons": [],
            }

        normalized_signals = {str(signal).lower() for signal in triggering_signals}
        normalized_flags = {str(key).lower(): value for key, value in behavior_flags.items()}
        obligations = {
            str(item).lower() for item in (harmonic_guard.get("obligations") or [])
        }

        def _has_signal(*terms: str) -> bool:
            return any(any(term in signal for term in terms) for signal in normalized_signals)

        def _has_flag(*terms: str) -> bool:
            return any(term in key for key in normalized_flags.keys() for term in terms)

        sources: List[str] = []

        if (
            _has_flag("aatl", "aatl_actor_type", "aatl_assessment", "aatl_stage")
            or _has_signal("aatl", "aatl_", "autonomous_operator", "agent_lifecycle")
        ):
            sources.append("aatl")

        if (
            _has_flag("cce", "cce_", "reasoning_ddos", "inference_waste")
            or _has_signal("cce", "reasoning_ddos", "inference_waste", "cce_")
        ):
            sources.append("cce")

        if _has_flag("vns", "suspicious_flows", "network_truth") or _has_signal(
            "vns",
            "beacon",
            "network_truth",
            "suspicious_flow",
            "east_west",
            "dns_burst",
        ):
            sources.append("vns")

        if _has_flag("identity", "trust", "attestation", "principal") or _has_signal(
            "identity",
            "trust_state:degraded",
            "trust_boundary",
            "boundary_violation",
            "attestation_failed",
            "identity_drift",
        ):
            sources.append("identity_trust")

        if (
            obligations
            or _has_flag("notation", "world_state", "triune", "governance")
            or _has_signal(
                "notation",
                "world_state",
                "triune",
                "governance",
                "policy_bind",
                "hash_mismatch",
            )
        ):
            sources.append("governance_evidence")

        required_sources = [
            "aatl",
            "cce",
            "vns",
            "identity_trust",
            "governance_evidence",
        ]
        present_sources = sorted(set(sources))
        satisfied = len(present_sources) >= 2
        missing_sources = [source for source in required_sources if source not in present_sources]
        reasons: List[str] = []

        if not satisfied:
            reasons.extend(
                [
                    "anti_feedback_loop_guard_triggered",
                    "independent_corroboration_required_for_high_impact_deception",
                ]
            )
            reasons.extend(
                f"missing_independent_corroboration:{source}" for source in missing_sources
            )

        return {
            "required": True,
            "satisfied": satisfied,
            "sources": present_sources,
            "missing_sources": missing_sources,
            "reasons": reasons,
        }

    @staticmethod
    def _looks_trusted(
        *,
        session_id: Optional[str],
        headers: Optional[Dict[str, str]],
        behavior_flags: Optional[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        flags = behavior_flags or {}
        lowered_headers = {str(k).lower(): str(v).lower() for k, v in (headers or {}).items()}

        for key in DeceptionAuthorityService.TRUST_BLOCK_SIGNALS:
            if bool(flags.get(key)):
                reasons.append(f"behavior_flag:{key}")

        actor_type = str(flags.get("actor_type") or flags.get("aatl_actor_type") or "").lower()
        if actor_type in {"human", "human_admin", "trusted_agent"}:
            reasons.append(f"actor_type:{actor_type}")

        if lowered_headers.get("x-seraph-trusted") in {"1", "true", "yes"}:
            reasons.append("header:x-seraph-trusted")
        if lowered_headers.get("x-internal-verified") in {"1", "true", "yes"}:
            reasons.append("header:x-internal-verified")

        if session_id and session_id.startswith(("admin_", "internal_", "trusted_")):
            reasons.append("session_prefix:trusted")

        return (len(reasons) > 0, reasons)

    def validate_payload(self, payload: Dict[str, Any]) -> DeceptionValidationResult:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        collisions: List[str] = []

        synthetic_marker = payload.get("_seraph_synthetic") if isinstance(payload, dict) else None
        if synthetic_marker is not True:
            collisions.append("synthetic_marker:missing")

        for pattern in self.REAL_SECRET_PATTERNS:
            if pattern.search(serialized):
                collisions.append(f"secret_pattern:{pattern.pattern}")

        for pattern in self.FORBIDDEN_HOST_PATTERNS:
            if pattern.search(serialized):
                collisions.append(f"host_pattern:{pattern.pattern}")

        for pattern in self.REAL_PATH_PATTERNS:
            if pattern.search(serialized):
                collisions.append(f"path_pattern:{pattern.pattern}")

        for pattern in self.REAL_SCHEMA_PATTERNS:
            if pattern.search(serialized):
                collisions.append(f"schema_pattern:{pattern.pattern}")

        allowed = len(collisions) == 0
        reasons = [] if allowed else ["synthetic_payload_collision_detected"]
        downgraded_mode = None if allowed else DeceptionMode.FRICTION
        return DeceptionValidationResult(
            allowed=allowed,
            reasons=reasons,
            collisions=collisions,
            downgraded_mode=downgraded_mode,
        )

    async def persist_case(self, case: DeceptionCase) -> None:
        if self.db is None or not hasattr(self.db, "deception_cases"):
            return
        try:
            payload = _model_dump(case)
            payload["updated_at"] = _utc_now_iso()
            await self.db.deception_cases.replace_one(
                {"deception_case_id": case.deception_case_id},
                payload,
                upsert=True,
            )
        except Exception:
            logger.exception("Failed to persist deception case %s", case.deception_case_id)

    async def persist_event(
        self,
        *,
        deception_case_id: str,
        event_type: str,
        session_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if self.db is None or not hasattr(self.db, "deception_events"):
            return None
        event_id = f"de-{uuid.uuid4().hex[:12]}"
        try:
            await self.db.deception_events.insert_one(
                {
                    "event_id": event_id,
                    "deception_case_id": deception_case_id,
                    "event_type": event_type,
                    "session_id": session_id,
                    "campaign_id": campaign_id,
                    "source_ip": source_ip,
                    "details": details or {},
                    "timestamp": _utc_now_iso(),
                }
            )
            return event_id
        except Exception:
            logger.exception("Failed to persist deception event %s", event_type)
            return None

    async def create_case(
        self,
        *,
        session_id: Optional[str],
        campaign_id: Optional[str],
        source_ip: Optional[str],
        path: Optional[str],
        trigger_reason: str,
        triggering_signals: List[str],
        desired_mode: DeceptionMode,
        risk_score: int,
        headers: Optional[Dict[str, str]] = None,
        behavior_flags: Optional[Dict[str, Any]] = None,
        evidence_refs: Optional[List[str]] = None,
        harmonic_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[DeceptionCase, DeceptionValidationResult]:
        flags = behavior_flags or {}
        harmonic_guard = self._harmonic_guardrails(harmonic_state)
        trusted_blocked, trusted_reasons = self._looks_trusted(
            session_id=session_id,
            headers=headers,
            behavior_flags=flags,
        )
        confidence_band = self._confidence_band(
            machine_plausibility=float(flags.get("machine_plausibility") or 0.0),
            agenticity_score=float(flags.get("agenticity_score") or 0.0),
            decoy_touched=bool(flags.get("decoy_touched")),
        )
        harmonic_shaped_mode, harmonic_shape_reasons = self._harmonic_shaped_mode(
            desired_mode=desired_mode,
            harmonic_state=harmonic_state,
            harmonic_guard=harmonic_guard,
            behavior_flags=flags,
        )
        corroboration_guard = self._independent_corroboration_guard(
            desired_mode=harmonic_shaped_mode,
            triggering_signals=triggering_signals,
            behavior_flags=flags,
            harmonic_guard=harmonic_guard,
        )

        mode = desired_mode
        validation = DeceptionValidationResult(allowed=True, reasons=[])
        constraints = [
            "never_serve_real_credentials",
            "never_serve_real_inventory",
            "degrade_to_friction_on_validator_uncertainty",
        ]
        policy_decision = evaluate_deception_escalation(
            desired_mode=harmonic_shaped_mode,
            confidence_band=confidence_band,
            triggering_signals=triggering_signals,
            trusted_principal_blocked=trusted_blocked,
            harmonic_veto=bool(harmonic_guard["veto"]),
        )
        mode = policy_decision["approved_mode"]
        if trusted_blocked:
            validation = DeceptionValidationResult(
                allowed=False,
                reasons=["trusted_principal_blocked", *trusted_reasons],
                downgraded_mode=DeceptionMode.OBSERVE,
            )
            constraints.append("trusted_principal_block")
        elif harmonic_guard["veto"]:
            validation = DeceptionValidationResult(
                allowed=False,
                reasons=["governance_veto", *harmonic_guard["veto_reasons"], *harmonic_shape_reasons],
                downgraded_mode=DeceptionMode.OBSERVE,
            )
            constraints.extend(["harmonic_governance_veto", *harmonic_guard["obligations"]])
        elif harmonic_shaped_mode != desired_mode:
            validation = DeceptionValidationResult(
                allowed=False,
                reasons=list(harmonic_shape_reasons),
                downgraded_mode=mode,
            )
            constraints.append("harmonic_shaped_deception_bound")
        elif not corroboration_guard["satisfied"]:
            mode = DeceptionMode.DISINFORMATION
            validation = DeceptionValidationResult(
                allowed=False,
                reasons=list(corroboration_guard["reasons"]),
                downgraded_mode=mode,
            )
            constraints.append("independent_corroboration_required")
        elif not policy_decision["transition_allowed"]:
            denial_reasons = list(policy_decision["denial_reasons"] or [])
            if (
                "minimum_confidence_not_met" in denial_reasons
                and desired_mode in {DeceptionMode.DISINFORMATION, DeceptionMode.MIRROR_WORLD}
            ):
                denial_reasons.append("insufficient_confidence_for_active_deception")
            validation = DeceptionValidationResult(
                allowed=False,
                reasons=denial_reasons,
                downgraded_mode=mode,
            )
            constraints.append("policy_bound_escalation_block")

        case = DeceptionCase(
            deception_case_id=f"deception-{uuid.uuid4().hex[:12]}",
            subject_session_id=session_id,
            campaign_id=campaign_id,
            source_ip=source_ip,
            path=path,
            trigger_reason=trigger_reason,
            triggering_signals=list(dict.fromkeys(triggering_signals or [])),
            deception_mode=mode,
            risk_band=self._risk_band_from_score(int(risk_score or 0)),
            confidence_band=confidence_band,
            safety_constraints=constraints,
            allowed_output_classes=(
                ["timing_friction"]
                if mode == DeceptionMode.FRICTION
                else ["synthetic_payload"]
                if mode == DeceptionMode.DISINFORMATION
                else ["synthetic_graph_state"]
                if mode == DeceptionMode.MIRROR_WORLD
                else []
            ),
            termination_conditions=[
                "trusted_principal_detected",
                "validator_collision_detected",
                "governance_veto",
                "session_terminated",
            ],
            evidence_refs=list(evidence_refs or []),
            trusted_principal_blocked=trusted_blocked,
            execution_notes={
                "requested_mode": desired_mode.value,
                "behavior_digest": hashlib.sha256(
                    json.dumps(flags, sort_keys=True, default=str).encode()
                ).hexdigest()[:24],
                "harmonic_state": harmonic_state or {},
                "harmonic_band": harmonic_guard["band"],
                "harmonic_obligations": harmonic_guard["obligations"],
                "harmonic_shape_reasons": harmonic_shape_reasons,
                "harmonic_shaped_requested_mode": harmonic_shaped_mode.value,
                "independent_corroboration": corroboration_guard,
                "policy_decision": policy_decision,
            },
        )
        await self.persist_case(case)
        return case, validation

    async def authorize_payload(
        self,
        *,
        case: DeceptionCase,
        payload: Dict[str, Any],
    ) -> DeceptionValidationResult:
        result = self.validate_payload(payload)
        if result.allowed:
            case.status = "ready"
            case.execution_notes["payload_hash"] = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
        else:
            case.status = "downgraded"
            case.execution_notes["validator_collisions"] = list(result.collisions)
            if result.downgraded_mode is not None:
                case.deception_mode = result.downgraded_mode
        case.updated_at = _utc_now_iso()
        await self.persist_case(case)
        return result

    async def record_execution_outcome(
        self,
        *,
        case: DeceptionCase,
        status: str,
        note: str,
        output_class: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> DeceptionCase:
        case.status = status
        case.updated_at = _utc_now_iso()
        timeline = case.execution_notes.setdefault("timeline", [])
        timeline.append(
            {
                "timestamp": case.updated_at,
                "status": status,
                "note": note,
                "output_class": output_class,
            }
        )
        if output_class:
            emitted = case.execution_notes.setdefault("emitted_output_classes", [])
            if output_class not in emitted:
                emitted.append(output_class)
        if extra:
            case.execution_notes.update(extra)
        await self.persist_case(case)
        return case
