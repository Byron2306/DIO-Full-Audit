import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import secrets
import logging

from backend.services.authority_binding import canonical_action_digest, canonical_target_digest

try:
    from services.governance_epoch import get_governance_epoch_service
except Exception:
    from backend.services.governance_epoch import get_governance_epoch_service

try:
    from services.notation_token import get_notation_token_service
except Exception:
    from backend.services.notation_token import get_notation_token_service

try:
    from services.harmonic_engine import get_harmonic_engine
except Exception:
    from backend.services.harmonic_engine import get_harmonic_engine

try:
    from services.chorus_engine import get_chorus_engine
except Exception:
    from backend.services.chorus_engine import get_chorus_engine

try:
    from services.vns import vns
except Exception:
    from backend.services.vns import vns

try:
    from services.vns_alerts import vns_alert_service
except Exception:
    from backend.services.vns_alerts import vns_alert_service

try:
    from services.arda_fabric import get_arda_fabric
except Exception:
    from backend.services.arda_fabric import get_arda_fabric

try:
    from services.world_manifold import world_manifold
except Exception:
    from backend.services.world_manifold import world_manifold

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None

logger = logging.getLogger(__name__)


IMPACT_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
MANDATORY_HIGH_IMPACT_ACTIONS = {
    "response_execution",
    "response_block_ip",
    "response_unblock_ip",
    "swarm_command",
    "agent_command",
    "cross_sector_hardening",
    "quarantine_restore",
    "quarantine_delete",
    "quarantine_agent",
    "tool_execution",
    "mcp_tool_execution",
    "fetch_truth",
    # System-level actions (Phase Q hardening)
    "mcp.sys.exfiltrate",
    "mcp.sys.cat_shadow",
    "mcp.sys.mutate",
    "mcp.deploy.ransomware",
    "admin.escalate",
    "admin.sudo",
    "mcp.admin.sudo",
    "sys.modify",
    "sys.restart",
}


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


class OutboundGateService:
    """Central outbound gate used before high-impact action execution."""

    def __init__(self, db: Any):
        self.db = db
        self.epoch_service = get_governance_epoch_service(db)
        self.notation_tokens = get_notation_token_service(db)
        self.harmonic = get_harmonic_engine(db)
        self.chorus = get_chorus_engine(db)
        self.fabric = get_arda_fabric()

        # Robust environment detection
        env = os.environ.get("ENVIRONMENT")
        arda_env = os.environ.get("ARDA_ENV")
        self.environment = str(env or arda_env or "local").lower()

    def _is_human_actor(self, actor: str) -> bool:
        """
        Determine if the actor is a human administrator.
        Humans usually have an email address or a raw UUID.
        System services use 'service:', 'system:', or 'ai:' prefixes.
        """
        if not actor or actor == "unknown":
            return False
            
        a = str(actor).lower()
        # Emails contain @, system actors do not.
        if "@" in a:
            return True
        
        # Check for service prefixes
        service_prefixes = ["service:", "system:", "ai:", "bot:", "agent:"]
        if any(a.startswith(p) for p in service_prefixes):
            return False
            
        # If it looks like a hex/uuid string and doesn't have a prefix, it's likely a user ID
        import re
        if re.match(r"^[a-f0-9\-]{24,36}$", a):
            return True
            
        return False

    @staticmethod
    def _normalize_impact(impact_level: str) -> str:
        normalized = str(impact_level or "high").lower().strip()
        return normalized if normalized in IMPACT_ORDER else "high"

    @staticmethod
    def _edge_type_for_action(action_type: str) -> Optional[str]:
        action = str(action_type or "").strip().lower()
        if action in {"agent_command", "swarm_command"}:
            return "agent_command_execution"
        if action in {"mcp_tool_execution", "tool_execution"}:
            return "mcp_tool_invocation"
        if action in MANDATORY_HIGH_IMPACT_ACTIONS:
            return "outbound_gated_action"
        return None

    def verify_transport_lock(self, node_id: str) -> bool:
        """
        Synchronously verifies that the peer is communication over 
        a cryptographically established and VERIFIED WireGuard tunnel.
        """
        from backend.services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        peer = fabric.known_peers.get(node_id)
        
        # Bypass for local development / testing environment
        if self.environment in ("local", "dev", "development") or os.environ.get("BYPASS_TRANSPORT_LOCK") == "true":
            logger.info(f"OutboundGate: Transport Lock BYPASS for {node_id} (Env: {self.environment})")
            return True

        if not peer:
            return False
            
        # Hardening: Check for real WireGuard public key AND the verification flag from the handshake
        has_real_transport = peer.get("wg_pubkey") != "local-only"
        is_verified = peer.get("is_peer_verified", False)
        
        if not (has_real_transport and is_verified):
            logger.warning(f"OutboundGate: Transport Lock VIOLATION for {node_id}. (Verified:{is_verified})")
            return False
            
        return True

    def attach_required_companions(
        self,
        *,
        payload: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> List[str]:
        existing = [str(x) for x in (payload.get("required_companions") or []) if x]
        required = [str(x) for x in (spec.get("required_companions") or []) if x]
        merged = list(dict.fromkeys(existing + required))
        payload["required_companions"] = merged
        return merged

    def open_edge_context(
        self,
        *,
        action_type: str,
        action_id: str,
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        gate_seen_at_ms: int,
        world_state_bound: bool,
    ) -> Dict[str, Any]:
        edge_type = self._edge_type_for_action(action_type)
        if not edge_type:
            return {}
        spec_obj = self.chorus.load_edge_chorus_spec(
            edge_type=edge_type,
            genre_mode=str(payload.get("genre_mode") or polyphonic_context.get("genre_mode") or ""),
        )
        spec = _model_dump(spec_obj)
        required_companions = self.attach_required_companions(payload=payload, spec=spec)
        dispatch_ts = payload.get("dispatch_created_at_ms")
        try:
            dispatch_ts = int(float(dispatch_ts)) if dispatch_ts is not None else None
        except Exception:
            dispatch_ts = None
        observed_participants = ["outbound_gate"]
        observed_sequence = ["outbound_gate"]
        state_events = ["edge_opened"]
        timestamps_ms = {"edge_opened": float(gate_seen_at_ms), "outbound_gate": float(gate_seen_at_ms)}
        if dispatch_ts is not None:
            observed_participants.insert(0, "dispatch")
            observed_sequence.insert(0, "dispatch")
            timestamps_ms["dispatch"] = float(dispatch_ts)
        if world_state_bound:
            insertion_index = 1 if observed_participants and observed_participants[0] == "dispatch" else 0
            observed_participants.insert(insertion_index, "world_state_bind")
            observed_sequence.insert(insertion_index, "world_state_bind")
            state_events.append("state_bound_to_action")
            timestamps_ms["world_state_bind"] = float(gate_seen_at_ms)
        edge_context = {
            "edge_type": edge_type,
            "action_id": action_id,
            "required_companions": required_companions,
            "required_participants": list(spec.get("required_participants") or []),
            "optional_participants": list(spec.get("optional_participants") or []),
            "expected_sequence": list(spec.get("expected_sequence") or []),
            "settlement_timeout_ms": spec.get("settlement_timeout_ms"),
            "observed_participants": observed_participants,
            "observed_sequence": observed_sequence,
            "timestamps_ms": timestamps_ms,
            "state_events": state_events,
            "audit_events": [],
            "vns_events": [],
            "opened_at_ms": int(gate_seen_at_ms),
        }
        polyphonic_context["chorus_spec"] = spec
        polyphonic_context["edge_observation"] = {
            "action_id": action_id,
            "edge_type": edge_type,
            "observed_participants": observed_participants,
            "observed_sequence": observed_sequence,
            "timestamps_ms": timestamps_ms,
            "audit_events": [],
            "state_events": state_events,
            "vns_events": [],
            "missing_participants": [],
            "unexpected_participants": [],
        }
        polyphonic_context["edge_type"] = edge_type
        polyphonic_context["edge_context"] = edge_context
        return edge_context

    async def emit_edge_opened_event(
        self,
        *,
        edge_context: Dict[str, Any],
        refs: List[str],
        actor: str,
    ) -> None:
        if emit_world_event is None or self.db is None or not edge_context:
            return
        try:
            await emit_world_event(
                self.db,
                event_type="edge_opened",
                entity_refs=refs,
                payload={
                    "edge_type": edge_context.get("edge_type"),
                    "action_id": edge_context.get("action_id"),
                    "actor": actor,
                    "required_participants": edge_context.get("required_participants") or [],
                    "required_companions": edge_context.get("required_companions") or [],
                    "settlement_timeout_ms": edge_context.get("settlement_timeout_ms"),
                    "state_events": edge_context.get("state_events") or [],
                    "timestamps_ms": edge_context.get("timestamps_ms") or {},
                },
                trigger_triune=False,
                source="outbound_gate",
            )
        except Exception:
            logger.debug("Failed to emit edge_opened event", exc_info=True)

    def attach_gate_timing_observation(
        self,
        *,
        actor: str,
        action_type: str,
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        target_domain: str,
        impact_level: str,
        notation_valid: bool,
        gate_seen_at_ms: int,
    ) -> Dict[str, Any]:
        dispatch_created_at_ms = payload.get("dispatch_created_at_ms")
        if dispatch_created_at_ms is None and isinstance(polyphonic_context, dict):
            dispatch_created_at_ms = (polyphonic_context.get("harmonic_timeline") or {}).get(
                "dispatch_created_at_ms"
            )
        try:
            dispatch_created_at_ms = int(float(dispatch_created_at_ms)) if dispatch_created_at_ms is not None else None
        except Exception:
            dispatch_created_at_ms = None
        gate_lag_ms = (
            max(0, int(gate_seen_at_ms - dispatch_created_at_ms))
            if dispatch_created_at_ms is not None
            else None
        )
        harmonic_observation = self.harmonic.score_observation(
            actor_id=str(actor or "unknown"),
            tool_name=str(payload.get("command_type") or payload.get("tool") or action_type),
            target_domain=target_domain,
            environment=self.environment,
            stage="gate",
            timestamp_ms=float(gate_seen_at_ms),
            operation=action_type,
            context={
                "impact_level": impact_level,
                "notation_valid": notation_valid,
                "gate_lag_ms": gate_lag_ms,
            },
        )
        if isinstance(polyphonic_context, dict):
            polyphonic_context["timing_features"] = harmonic_observation.get("timing_features")
            polyphonic_context["harmonic_state"] = harmonic_observation.get("harmonic_state")
            polyphonic_context["baseline_ref"] = harmonic_observation.get("baseline_ref")
            history = list(polyphonic_context.get("harmonic_history") or [])
            history.append(
                {
                    "stage": "gate",
                    "timestamp_ms": gate_seen_at_ms,
                    "harmonic_state": harmonic_observation.get("harmonic_state"),
                }
            )
            polyphonic_context["harmonic_history"] = history[-20:]
            timeline = dict(polyphonic_context.get("harmonic_timeline") or {})
            if dispatch_created_at_ms is not None:
                timeline.setdefault("dispatch_created_at_ms", dispatch_created_at_ms)
            timeline["gate_seen_at_ms"] = gate_seen_at_ms
            if gate_lag_ms is not None:
                timeline["gate_lag_ms"] = gate_lag_ms
            polyphonic_context["harmonic_timeline"] = timeline
        return {
            "dispatch_created_at_ms": dispatch_created_at_ms,
            "gate_lag_ms": gate_lag_ms,
            "harmonic_observation": harmonic_observation,
        }

    def refresh_harmonic_state(
        self,
        *,
        actor: str,
        action_type: str,
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        target_domain: str,
        impact_level: str,
        notation_valid: bool,
        gate_seen_at_ms: int,
    ) -> Dict[str, Any]:
        return self.attach_gate_timing_observation(
            actor=actor,
            action_type=action_type,
            payload=payload,
            polyphonic_context=polyphonic_context,
            target_domain=target_domain,
            impact_level=impact_level,
            notation_valid=notation_valid,
            gate_seen_at_ms=gate_seen_at_ms,
        )

    async def gate_action(
        self,
        *,
        action_type: str,
        actor: str,
        payload: Dict[str, Any],
        impact_level: str = "high",
        subject_id: Optional[str] = None,
        entity_refs: Optional[List[str]] = None,
        requires_triune: bool = True,
        polyphonic_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Queue action for approval. Mandatory for high-impact action types."""
        normalized_action = str(action_type or "unknown").strip().lower()
        normalized_impact = self._normalize_impact(impact_level)
        resolved_polyphonic_context = polyphonic_context or payload.get("polyphonic_context") or {}
        gate_seen_at_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        voice_profile = (
            resolved_polyphonic_context.get("voice_profile")
            if isinstance(resolved_polyphonic_context, dict)
            else {}
        )

        # Governance hardening: these paths cannot skip triune and cannot be low impact
        # UNLESS the actor is a verified human administrator (UI operator).
        if normalized_action in MANDATORY_HIGH_IMPACT_ACTIONS:
            if not self._is_human_actor(actor):
                requires_triune = True
                if IMPACT_ORDER[normalized_impact] < IMPACT_ORDER["high"]:
                    normalized_impact = "high"
            # If it's a human, we respect the requires_triune flag passed in (can be True or False)

        scope = str(
            (payload.get("target_domain") or (payload.get("parameters") or {}).get("target_domain") or "global")
        )
        active_epoch = await self.epoch_service.get_active_epoch(scope=scope)
        active_epoch_doc = (
            active_epoch.model_dump() if (active_epoch is not None and hasattr(active_epoch, "model_dump")) else (
                active_epoch.dict() if active_epoch is not None else {}
            )
        )
        notation_token = None
        notation_token_id = None
        if isinstance(resolved_polyphonic_context, dict):
            notation_token = resolved_polyphonic_context.get("notation_token")
            notation_token_id = resolved_polyphonic_context.get("notation_token_id")
            if active_epoch is not None:
                resolved_polyphonic_context.setdefault("governance_epoch", active_epoch.epoch_id)
                resolved_polyphonic_context.setdefault("score_id", active_epoch.score_id)
                resolved_polyphonic_context.setdefault("genre_mode", active_epoch.genre_mode)
                resolved_polyphonic_context.setdefault("strictness_level", active_epoch.strictness_level)
                resolved_polyphonic_context.setdefault("world_state_hash", active_epoch.world_state_hash)
        notation_token = notation_token or payload.get("notation_token")
        notation_token_id = notation_token_id or payload.get("notation_token_id")
        # The gate is a relying/enforcement point.  It must not manufacture the
        # prerequisite notation or BEAST capability that it is meant to check.
        if isinstance(resolved_polyphonic_context, dict):
            resolved_polyphonic_context["notation_auto_issued"] = False
        enforcement_profile = self.notation_tokens.resolve_enforcement_profile(
            genre_mode=(active_epoch.genre_mode if active_epoch is not None else payload.get("genre_mode")),
            strictness_level=(
                active_epoch.strictness_level if active_epoch is not None else payload.get("strictness_level")
            ),
        )
        validation_context = {
            "baseline_time": payload.get("created_at") or payload.get("requested_at"),
            "observed_slot": payload.get("sequence_slot"),
            "observed_companions": payload.get("observed_companions") or [],
            "enforce_sequence_slot": bool(enforcement_profile.get("enforce_sequence_slot", False)),
            "enforce_required_companions": bool(enforcement_profile.get("enforce_required_companions", False)),
        }
        capability_required = bool(
            self.environment == "production"
            and (
                normalized_action in MANDATORY_HIGH_IMPACT_ACTIONS
                or normalized_impact in {"high", "critical"}
            )
        )
        expected_action_digest = canonical_action_digest(
            action_type=normalized_action,
            actor=actor,
            subject_id=subject_id,
            impact_level=normalized_impact,
            payload=payload,
        )
        expected_target_digest = canonical_target_digest(subject_id=subject_id, payload=payload)
        validation_context.update(
            {
                "require_capability": capability_required,
                "capability_lease_id": payload.get("capability_lease_id"),
                "authority_request_digest": payload.get("authority_request_digest"),
                "action_digest": expected_action_digest,
                "audience": "metatron-outbound-gate",
                "target_digest": expected_target_digest,
            }
        )
        notation_validation = await self.notation_tokens.validate_notation_token(
            token=notation_token or notation_token_id,
            active_epoch=active_epoch_doc if active_epoch_doc else None,
            world_state_hash=(
                active_epoch.world_state_hash
                if active_epoch is not None
                else (resolved_polyphonic_context.get("world_state_hash") if isinstance(resolved_polyphonic_context, dict) else None)
            ),
            context=validation_context,
        )
        notation_checks = notation_validation.get("checks") or {}
        notation_valid = bool(notation_validation.get("valid"))
        notation_failure_reason = ";".join(notation_validation.get("reasons") or []) or None
        world_state_hash_match = bool(notation_checks.get("world_state_hash_match", False))
        epoch_match = bool(notation_checks.get("epoch_match", False))
        score_match = bool(notation_checks.get("score_match", False))
        capability_binding_valid = bool(notation_checks.get("capability_binding_valid", False))
        authority_request_binding_valid = bool(
            notation_checks.get("authority_request_binding_valid", False)
        )
        action_binding_valid = bool(notation_checks.get("action_binding_valid", False))
        audience_binding_valid = bool(notation_checks.get("audience_binding_valid", False))
        target_binding_valid = bool(notation_checks.get("target_binding_valid", False))
        if isinstance(resolved_polyphonic_context, dict):
            if notation_validation.get("token"):
                resolved_polyphonic_context["notation_token"] = notation_validation.get("token")
                resolved_polyphonic_context["notation_token_id"] = (
                    (notation_validation.get("token") or {}).get("token_id")
                )
                notation_token_id = (notation_validation.get("token") or {}).get("token_id")
            if active_epoch is not None:
                resolved_polyphonic_context["governance_epoch_descriptor"] = active_epoch_doc
            resolved_polyphonic_context["notation_enforcement_profile"] = notation_validation.get(
                "enforcement_profile"
            )

        action_id = payload.get("command_id") or payload.get("action_id") or secrets.token_hex(8)
        world_state_bound = bool(
            (active_epoch is not None and active_epoch.world_state_hash)
            or payload.get("world_state_hash")
            or (
                resolved_polyphonic_context.get("world_state_hash")
                if isinstance(resolved_polyphonic_context, dict)
                else None
            )
        )
        edge_context: Dict[str, Any] = (
            self.open_edge_context(
                action_type=normalized_action,
                action_id=str(action_id),
                payload=payload,
                polyphonic_context=(
                    resolved_polyphonic_context if isinstance(resolved_polyphonic_context, dict) else {}
                ),
                gate_seen_at_ms=gate_seen_at_ms,
                world_state_bound=world_state_bound,
            )
            if isinstance(resolved_polyphonic_context, dict)
            else {}
        )

        dispatch_created_at_ms = None
        gate_lag_ms = None
        harmonic_observation: Dict[str, Any] = {}
        try:
            harmonic_payload = self.refresh_harmonic_state(
                actor=str(actor),
                action_type=normalized_action,
                payload=payload,
                polyphonic_context=(
                    resolved_polyphonic_context
                    if isinstance(resolved_polyphonic_context, dict)
                    else {}
                ),
                target_domain=scope,
                impact_level=normalized_impact,
                notation_valid=notation_valid,
                gate_seen_at_ms=gate_seen_at_ms,
            )
            dispatch_created_at_ms = harmonic_payload.get("dispatch_created_at_ms")
            gate_lag_ms = harmonic_payload.get("gate_lag_ms")
            harmonic_observation = harmonic_payload.get("harmonic_observation") or {}
            if hasattr(vns, "update_domain_pulse"):
                pulse_state = vns.update_domain_pulse(
                    domain=scope,
                    timing_features=harmonic_observation.get("timing_features") or {},
                    harmonic_state=harmonic_observation.get("harmonic_state") or {},
                    timestamp_ms=gate_seen_at_ms,
                )
                if (
                    pulse_state
                    and float(pulse_state.get("pulse_stability_index") or 1.0) < 0.45
                    and hasattr(vns_alert_service, "alert_pulse_instability_by_domain")
                ):
                    vns_alert_service.alert_pulse_instability_by_domain(pulse_state)
                    if edge_context:
                        (edge_context.setdefault("vns_events", [])).append("pulse_instability_warning")
            timing_features = harmonic_observation.get("timing_features") or {}
            if (
                float(timing_features.get("drift_norm") or 0.0) >= 0.6
                and hasattr(vns_alert_service, "alert_harmonic_drift_detected")
            ):
                vns_alert_service.alert_harmonic_drift_detected(
                    {
                        "scope": scope,
                        "action_type": normalized_action,
                        "actor": actor,
                        "drift_norm": timing_features.get("drift_norm"),
                        "confidence": float(
                            (harmonic_observation.get("harmonic_state") or {}).get("confidence") or 0.0
                        ),
                    }
                )
                if edge_context:
                    (edge_context.setdefault("vns_events", [])).append("harmonic_drift_detected")
            if (
                float(timing_features.get("burstiness") or 0.0) >= 0.6
                and hasattr(vns_alert_service, "alert_burst_cluster_detected")
            ):
                vns_alert_service.alert_burst_cluster_detected(
                    {
                        "scope": scope,
                        "action_type": normalized_action,
                        "burstiness": timing_features.get("burstiness"),
                        "discord_score": float(
                            (harmonic_observation.get("harmonic_state") or {}).get("discord_score") or 0.0
                        ),
                    }
                )
                if edge_context:
                    (edge_context.setdefault("vns_events", [])).append("burst_cluster_detected")
            discord = float((harmonic_observation.get("harmonic_state") or {}).get("discord_score") or 0.0)
            if discord >= 0.7 and hasattr(vns_alert_service, "alert_discord_threshold_crossed"):
                vns_alert_service.alert_discord_threshold_crossed(
                    {
                        "scope": scope,
                        "action_type": normalized_action,
                        "actor": actor,
                        "discord_score": discord,
                        "confidence": float(
                            (harmonic_observation.get("harmonic_state") or {}).get("confidence") or 0.0
                        ),
                    }
                )
                if edge_context:
                    (edge_context.setdefault("vns_events", [])).append("discord_threshold_crossed")
        except Exception:
            logger.debug("Failed to compute gate harmonic observation", exc_info=True)

        if edge_context and isinstance(resolved_polyphonic_context, dict):
            edge_observation = dict(resolved_polyphonic_context.get("edge_observation") or {})
            if not edge_observation:
                edge_observation = {
                    "action_id": str(action_id),
                    "edge_type": edge_context.get("edge_type"),
                    "observed_participants": [],
                    "observed_sequence": [],
                    "timestamps_ms": {},
                    "audit_events": [],
                    "state_events": [],
                    "vns_events": [],
                    "missing_participants": [],
                    "unexpected_participants": [],
                }
            edge_observation["vns_events"] = list(dict.fromkeys(edge_context.get("vns_events") or []))
            resolved_polyphonic_context["edge_observation"] = edge_observation
            resolved_polyphonic_context["edge_context"] = edge_context

        now = datetime.now(timezone.utc).isoformat()
        queue_id = secrets.token_hex(8)
        decision_id = secrets.token_hex(8)

        refs = [r for r in (entity_refs or []) if r]
        if subject_id and subject_id not in refs:
            refs.insert(0, subject_id)
        if isinstance(voice_profile, dict):
            if voice_profile.get("component_id"):
                refs.append(str(voice_profile.get("component_id")))
            if voice_profile.get("voice_type"):
                refs.append(str(voice_profile.get("voice_type")))

        payload_with_polyphonic = dict(payload or {})
        if resolved_polyphonic_context:
            payload_with_polyphonic["polyphonic_context"] = resolved_polyphonic_context
        if edge_context:
            payload_with_polyphonic["edge_type"] = edge_context.get("edge_type")
            payload_with_polyphonic["edge_context"] = edge_context
            payload_with_polyphonic["required_companions"] = edge_context.get("required_companions") or []
            payload_with_polyphonic["settlement_timeout_ms"] = edge_context.get("settlement_timeout_ms")
        payload_with_polyphonic["gate_seen_at_ms"] = gate_seen_at_ms
        payload_with_polyphonic["canonical_action_digest"] = expected_action_digest
        payload_with_polyphonic["canonical_target_digest"] = expected_target_digest
        if gate_lag_ms is not None:
            payload_with_polyphonic["gate_lag_ms"] = gate_lag_ms
        if harmonic_observation:
            payload_with_polyphonic["timing_features_at_gate"] = harmonic_observation.get("timing_features")
            payload_with_polyphonic["harmonic_state_at_gate"] = harmonic_observation.get("harmonic_state")
            payload_with_polyphonic["baseline_ref"] = harmonic_observation.get("baseline_ref")
        if notation_token_id:
            payload_with_polyphonic["notation_token_id"] = notation_token_id
        if active_epoch is not None:
            payload_with_polyphonic.setdefault("governance_epoch", active_epoch.epoch_id)
            payload_with_polyphonic.setdefault("score_id", active_epoch.score_id)
            payload_with_polyphonic.setdefault("genre_mode", active_epoch.genre_mode)
            payload_with_polyphonic.setdefault("strictness_level", active_epoch.strictness_level)
            payload_with_polyphonic.setdefault("world_state_hash", active_epoch.world_state_hash)

        harmonic_state_at_gate = harmonic_observation.get("harmonic_state") if harmonic_observation else {}
        harmonic_discord = float((harmonic_state_at_gate or {}).get("discord_score") or 0.0)
        harmonic_confidence = float((harmonic_state_at_gate or {}).get("confidence") or 0.0)
        harmonic_mode_recommendation = (harmonic_state_at_gate or {}).get("mode_recommendation")
        harmonic_review_required = bool(
            harmonic_discord >= 0.65
            or (harmonic_discord >= 0.45 and harmonic_confidence < 0.4)
        )
        requested_triune = bool(requires_triune)
        explicit_human_override = self._is_human_actor(actor) and not requested_triune
        requires_triune = requested_triune
        if harmonic_review_required and not explicit_human_override:
            requires_triune = True
            
        # Bypass Triune for local development/testing scenarios
        if self.environment in ("local", "dev", "development") or os.environ.get("BYPASS_TRIUNE_GATE") == "true":
            requires_triune = False

        # Constitutional Veto: Mandatory Attestation Guard (Phase D Hardening)
        attestation_state = self.fabric.get_subject_state(str(subject_id or actor or "unknown"))
        is_attestation_failed = attestation_state in {"fallen", "dissonant", "strained", "unknown"}
        if self.environment in ("local", "dev", "development") and attestation_state == "unknown":
            is_attestation_failed = False

        # Physical Veto: Transport Lock (Phase Q Hardening)
        transport_verified = self.verify_transport_lock(str(subject_id or actor or "unknown"))

        # Integrity Veto: high-impact actions require a valid manifold seal.
        manifold_signature_valid = True
        if normalized_action in MANDATORY_HIGH_IMPACT_ACTIONS:
            try:
                current_manifold = world_manifold.get_current_manifold()
                manifold_signature_valid = bool(current_manifold and getattr(current_manifold, "signature_valid", False))
            except Exception:
                manifold_signature_valid = False

        # Impact-level based gate enforcement: high/critical actions trigger ALL vetoes regardless of action type
        is_high_or_critical_impact = normalized_impact in {"high", "critical"}
        is_mandatory_high = normalized_action in MANDATORY_HIGH_IMPACT_ACTIONS
        applies_veto_checks = is_mandatory_high or is_high_or_critical_impact

        deny_for_notation = (
            (not notation_valid)
            and applies_veto_checks
        )
        
        deny_for_attestation = is_attestation_failed and applies_veto_checks
        
        # Deny if action is high-impact but transport is not cryptographically locked (no WireGuard)
        deny_for_transport = (not transport_verified) and applies_veto_checks
        deny_for_manifold_signature = (
            (not manifold_signature_valid)
            and applies_veto_checks
        )
        deny_for_capability = capability_required and not all(
            (
                capability_binding_valid,
                authority_request_binding_valid,
                action_binding_valid,
                audience_binding_valid,
                target_binding_valid,
            )
        )

        # Human review may satisfy a discretionary approval requirement, but it
        # must never transmute failed attestation or transport evidence into a
        # pass.  Those are hard physical/identity vetoes and require fresh
        # evidence, not an override bit.

        is_denied = (
            deny_for_notation
            or deny_for_attestation
            or deny_for_transport
            or deny_for_manifold_signature
            or deny_for_capability
        )
        
        if is_denied:
            queue_status = "denied"
            decision_status = "denied"
            execution_status = "skipped"
        elif not requires_triune:
            queue_status = "approved"
            decision_status = "approved"
            execution_status = "pending_executor"
        else:
            queue_status = "pending"
            decision_status = "pending"
            execution_status = "awaiting_decision"

        queue_doc = {
            "queue_id": queue_id,
            "action_id": action_id,
            "action_type": normalized_action,
            "subject_id": subject_id,
            "actor": actor,
            "impact_level": normalized_impact,
            "payload": payload_with_polyphonic,
            "voice_type": voice_profile.get("voice_type") if isinstance(voice_profile, dict) else None,
            "capability_class": voice_profile.get("capability_class") if isinstance(voice_profile, dict) else None,
            "polyphonic_context": resolved_polyphonic_context or None,
            "edge_type": edge_context.get("edge_type") if edge_context else None,
            "edge_context": edge_context or None,
            "governance_epoch": active_epoch.epoch_id if active_epoch is not None else None,
            "score_id": active_epoch.score_id if active_epoch is not None else None,
            "genre_mode": active_epoch.genre_mode if active_epoch is not None else None,
            "strictness_level": active_epoch.strictness_level if active_epoch is not None else None,
            "world_state_hash": active_epoch.world_state_hash if active_epoch is not None else None,
            "notation_token_id": notation_token_id,
            "notation_valid": notation_valid,
            "notation_failure_reason": notation_failure_reason,
            "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
            "capability_required": capability_required,
            "capability_binding_valid": capability_binding_valid,
            "action_binding_valid": action_binding_valid,
            "authority_request_binding_valid": authority_request_binding_valid,
            "audience_binding_valid": audience_binding_valid,
            "target_binding_valid": target_binding_valid,
            "deny_for_capability": deny_for_capability,
            "canonical_action_digest": expected_action_digest,
            "canonical_target_digest": expected_target_digest,
            # Veto audit trail (Phase Q hardening)
            "applies_veto_checks": applies_veto_checks,
            "is_high_or_critical_impact": is_high_or_critical_impact,
            "is_mandatory_high": is_mandatory_high,
            "deny_for_notation": deny_for_notation,
            "deny_for_attestation": deny_for_attestation,
            "deny_for_transport": deny_for_transport,
            "deny_for_manifold_signature": deny_for_manifold_signature,
            "attestation_state": attestation_state,
            "transport_verified": transport_verified,
            "manifold_signature_valid": manifold_signature_valid,
            "world_state_hash_match": world_state_hash_match,
            "epoch_match": epoch_match,
            "score_match": score_match,
            "gate_seen_at_ms": gate_seen_at_ms,
            "gate_lag_ms": gate_lag_ms,
            "timing_features_at_gate": harmonic_observation.get("timing_features") if harmonic_observation else None,
            "harmonic_state_at_gate": harmonic_observation.get("harmonic_state") if harmonic_observation else None,
            "baseline_ref": harmonic_observation.get("baseline_ref") if harmonic_observation else None,
            "harmonic_review_required": harmonic_review_required,
            "harmonic_mode_recommendation": harmonic_mode_recommendation,
            "status": queue_status,
            "execution_status": execution_status,
            "created_at": now,
            "updated_at": now,
        }

        decision_doc = {
            "decision_id": decision_id,
            "related_queue_id": queue_id,
            "action_id": action_id,
            "action_type": normalized_action,
            "subject_id": subject_id,
            "actor": actor,
            "source": "outbound_gate",
            "status": decision_status,
            "execution_status": execution_status,
            "voice_type": voice_profile.get("voice_type") if isinstance(voice_profile, dict) else None,
            "capability_class": voice_profile.get("capability_class") if isinstance(voice_profile, dict) else None,
            "polyphonic_context": resolved_polyphonic_context or None,
            "edge_type": edge_context.get("edge_type") if edge_context else None,
            "edge_context": edge_context or None,
            "governance_epoch": active_epoch.epoch_id if active_epoch is not None else None,
            "score_id": active_epoch.score_id if active_epoch is not None else None,
            "genre_mode": active_epoch.genre_mode if active_epoch is not None else None,
            "strictness_level": active_epoch.strictness_level if active_epoch is not None else None,
            "world_state_hash": active_epoch.world_state_hash if active_epoch is not None else None,
            "notation_token_id": notation_token_id,
            "notation_valid": notation_valid,
            "notation_failure_reason": notation_failure_reason,
            "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
            "capability_required": capability_required,
            "capability_binding_valid": capability_binding_valid,
            "action_binding_valid": action_binding_valid,
            "authority_request_binding_valid": authority_request_binding_valid,
            "audience_binding_valid": audience_binding_valid,
            "target_binding_valid": target_binding_valid,
            "deny_for_capability": deny_for_capability,
            "canonical_action_digest": expected_action_digest,
            "canonical_target_digest": expected_target_digest,
            # Veto audit trail (Phase Q hardening)
            "applies_veto_checks": applies_veto_checks,
            "is_high_or_critical_impact": is_high_or_critical_impact,
            "is_mandatory_high": is_mandatory_high,
            "deny_for_notation": deny_for_notation,
            "deny_for_attestation": deny_for_attestation,
            "deny_for_transport": deny_for_transport,
            "deny_for_manifold_signature": deny_for_manifold_signature,
            "attestation_state": attestation_state,
            "transport_verified": transport_verified,
            "manifold_signature_valid": manifold_signature_valid,
            "world_state_hash_match": world_state_hash_match,
            "epoch_match": epoch_match,
            "score_match": score_match,
            "gate_seen_at_ms": gate_seen_at_ms,
            "gate_lag_ms": gate_lag_ms,
            "timing_features_at_gate": harmonic_observation.get("timing_features") if harmonic_observation else None,
            "harmonic_state_at_gate": harmonic_observation.get("harmonic_state") if harmonic_observation else None,
            "baseline_ref": harmonic_observation.get("baseline_ref") if harmonic_observation else None,
            "harmonic_review_required": harmonic_review_required,
            "harmonic_mode_recommendation": harmonic_mode_recommendation,
            "notes": (
                f"Notation denied before triune approval: {normalized_action} | {notation_failure_reason}"
                if deny_for_notation
                else (
                    f"Attestation denied: subject '{subject_id or actor}' is {attestation_state.upper()}"
                    if deny_for_attestation
                    else (
                        (
                            f"Manifold signature denied: no valid manifold seal for {normalized_action}"
                            if deny_for_manifold_signature
                            else (
                                f"Approved for immediate execution: {normalized_action}"
                                if not requires_triune
                                else f"Queued for triune approval: {normalized_action}"
                            )
                        )
                    )
                )
            ),
            "created_at": now,
            "updated_at": now,
        }

        try:
            await self.db.triune_outbound_queue.insert_one(queue_doc)
            await self.db.triune_decisions.insert_one(decision_doc)
        except Exception as exc:
            logger.exception("Failed to gate outbound action '%s': %s", normalized_action, exc)
            raise

        if edge_context:
            await self.emit_edge_opened_event(
                edge_context=edge_context,
                refs=refs + [action_id, queue_id, decision_id],
                actor=str(actor or "unknown"),
            )

        if emit_world_event is not None and self.db is not None:
            try:
                await emit_world_event(
                    self.db,
                    event_type="outbound_gate_action_queued",
                    entity_refs=refs + [action_id, queue_id, decision_id],
                    payload={
                        "status": queue_status,
                        "action_type": normalized_action,
                        "impact_level": normalized_impact,
                        "actor": actor,
                        "voice_type": voice_profile.get("voice_type") if isinstance(voice_profile, dict) else None,
                        "capability_class": voice_profile.get("capability_class") if isinstance(voice_profile, dict) else None,
                        "polyphonic_context": resolved_polyphonic_context or None,
                        "edge_type": edge_context.get("edge_type") if edge_context else None,
                        "edge_context": edge_context or None,
                        "governance_epoch": active_epoch.epoch_id if active_epoch is not None else None,
                        "score_id": active_epoch.score_id if active_epoch is not None else None,
                        "genre_mode": active_epoch.genre_mode if active_epoch is not None else None,
                        "world_state_hash": active_epoch.world_state_hash if active_epoch is not None else None,
                        "notation_token_id": notation_token_id,
                        "notation_valid": notation_valid,
                        "notation_failure_reason": notation_failure_reason,
                        "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                        "manifold_signature_valid": manifold_signature_valid,
                        "world_state_hash_match": world_state_hash_match,
                        "epoch_match": epoch_match,
                        "score_match": score_match,
                        "gate_seen_at_ms": gate_seen_at_ms,
                        "gate_lag_ms": gate_lag_ms,
                        "timing_features_at_gate": harmonic_observation.get("timing_features") if harmonic_observation else None,
                        "harmonic_state_at_gate": harmonic_observation.get("harmonic_state") if harmonic_observation else None,
                        "harmonic_review_required": harmonic_review_required,
                        "harmonic_mode_recommendation": harmonic_mode_recommendation,
                    },
                    trigger_triune=requires_triune,
                    source="outbound_gate",
                )
            except Exception:
                logger.debug("World event emit failed for queued outbound action", exc_info=True)

        # Determine final gate status
        final_status = "denied" if is_denied else ("approved" if not requires_triune else "queued")

        return {
            "status": final_status,
            "action_id": action_id,
            "queue_id": queue_id,
            "decision_id": decision_id,
            "action_type": normalized_action,
            "impact_level": normalized_impact,
            "voice_type": voice_profile.get("voice_type") if isinstance(voice_profile, dict) else None,
            "capability_class": voice_profile.get("capability_class") if isinstance(voice_profile, dict) else None,
            "polyphonic_context": resolved_polyphonic_context or None,
            "edge_type": edge_context.get("edge_type") if edge_context else None,
            "edge_context": edge_context or None,
            "governance_epoch": active_epoch.epoch_id if active_epoch is not None else None,
            "score_id": active_epoch.score_id if active_epoch is not None else None,
            "genre_mode": active_epoch.genre_mode if active_epoch is not None else None,
            "world_state_hash": active_epoch.world_state_hash if active_epoch is not None else None,
            "notation_token_id": notation_token_id,
            "notation_valid": notation_valid,
            "notation_failure_reason": notation_failure_reason,
            "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
            "manifold_signature_valid": manifold_signature_valid,
            "world_state_hash_match": world_state_hash_match,
            "epoch_match": epoch_match,
            "score_match": score_match,
            "gate_seen_at_ms": gate_seen_at_ms,
            "gate_lag_ms": gate_lag_ms,
            "timing_features_at_gate": harmonic_observation.get("timing_features") if harmonic_observation else None,
            "harmonic_state_at_gate": harmonic_observation.get("harmonic_state") if harmonic_observation else None,
            "harmonic_review_required": harmonic_review_required,
            "harmonic_mode_recommendation": harmonic_mode_recommendation,
            "message": (
                "Action denied due to notation validation failure"
                if deny_for_notation
                else (
                    "Action denied due to attestation failure"
                    if deny_for_attestation
                    else (
                        "Action denied due to manifold signature validation failure"
                        if deny_for_manifold_signature
                        else ("Action approved for immediate execution" if not requires_triune else "Action queued for triune approval")
                    )
                )
            ),
        }

    async def enqueue_command_for_approval(self, agent_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible command-gating wrapper."""
        return await self.gate_action(
            action_type="agent_command",
            actor="system",
            payload=command,
            impact_level="high",
            subject_id=agent_id,
            entity_refs=[agent_id, command.get("command_id")],
            requires_triune=True,
        )
