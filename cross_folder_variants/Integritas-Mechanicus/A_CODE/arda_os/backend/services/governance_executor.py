import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple

from backend.services.governed_dispatch import GovernedDispatchService

from backend.services.handoff_covenant import get_handoff_covenant_service
from backend.services.manwe_herald import manwe_herald
from backend.services.boot_attestation import boot_attestation
from backend.services.world_manifold import world_manifold
from backend.services.cluster_consensus_guard import get_cluster_consensus_guard
from backend.services.arda_fabric import get_arda_fabric

from backend.arda.ainur import AinurChoir
from backend.services.tulkas_executor import TulkasExecutor
from backend.services.constitutional_projection import project_choir_truth

from backend.services.governance_epoch import get_governance_epoch_service
from backend.services.notation_token import get_notation_token_service
from backend.services.harmonic_engine import get_harmonic_engine
from backend.services.chorus_engine import get_chorus_engine
from backend.services.vns import vns
from backend.services.vns_alerts import vns_alert_service
from backend.services.authority_binding import canonical_action_digest, canonical_target_digest
from backend.services.capability_authority import get_capability_lease_store

try:
    from backend.services.world_events import emit_world_event
except Exception:
    emit_world_event = None

try:
    from backend.services.telemetry_chain import tamper_evident_telemetry
except Exception:
    tamper_evident_telemetry = None

try:
    from backend.audit_logging import record_edge_closure, record_closure_lag, record_settlement_state
except Exception:
    record_edge_closure = None
    record_closure_lag = None
    record_settlement_state = None

# Phase II Transition: manwe_herald and handoff_covenant are used for constitutional checks.

logger = logging.getLogger(__name__)

_governance_executor_task: Optional[asyncio.Task] = None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


class GovernanceExecutorService:
    """Executes approved triune decisions into operational command queues."""

    DISPATCHABLE_ACTIONS = {
        "agent_command",
        "swarm_command",
        "response_execution",
        "cross_sector_hardening",
    }
    DOMAIN_OPERATION_ACTIONS = {
        "response_block_ip",
        "response_unblock_ip",
        "quarantine_restore",
        "quarantine_delete",
        "quarantine_agent",
        "vpn_initialize",
        "vpn_start",
        "vpn_stop",
        "vpn_peer_add",
        "vpn_peer_remove",
        "vpn_kill_switch_enable",
        "vpn_kill_switch_disable",
    }

    def __init__(self, db: Any):
        self.db = db
        self.dispatch = GovernedDispatchService(db)
        self.epoch_service = get_governance_epoch_service(db)
        self.notation_tokens = get_notation_token_service(db)
        self.harmonic = get_harmonic_engine(db)
        self.chorus = get_chorus_engine(db)
        self.choir = AinurChoir()
        from backend.services.world_model import WorldModelService
        self.world_model = WorldModelService(db)
        self.tulkas = TulkasExecutor(self.world_model)
        self.fabric = get_arda_fabric()
        self.environment = str(os.environ.get("ENVIRONMENT") or "local").lower()

    @staticmethod
    def _governance_context_for_execution(
        *,
        decision_id: str,
        queue_id: str,
        action_type: str,
    ) -> Dict[str, Any]:
        return {
            "approved": True,
            "decision_id": decision_id,
            "queue_id": queue_id,
            "action_type": action_type,
        }

    @staticmethod
    def _notation_token_from_context(
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        polyphonic_context = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        token = (
            (polyphonic_context.get("notation_token") if isinstance(polyphonic_context, dict) else None)
            or payload.get("notation_token")
            or None
        )
        token_id = (
            (polyphonic_context.get("notation_token_id") if isinstance(polyphonic_context, dict) else None)
            or payload.get("notation_token_id")
            or queue_doc.get("notation_token_id")
            or ((token or {}).get("token_id") if isinstance(token, dict) else None)
        )
        return {
            "polyphonic_context": polyphonic_context,
            "token": token,
            "token_id": token_id,
        }

    @staticmethod
    def _to_epoch_ms(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(float(value))
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(float(text))
        except Exception:
            pass
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except Exception:
            return None

    def _attach_execution_timing_observation(
        self,
        *,
        actor: str,
        action_type: str,
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        stage: str,
        timestamp_ms: Optional[int] = None,
        outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        ts_ms = int(timestamp_ms or int(datetime.now(timezone.utc).timestamp() * 1000))
        scope = str(
            payload.get("target_domain")
            or (payload.get("parameters") or {}).get("target_domain")
            or queue_doc.get("target_domain")
            or "global"
        )
        dispatch_created_at_ms = self._to_epoch_ms(
            payload.get("dispatch_created_at_ms")
            or queue_doc.get("dispatch_created_at_ms")
            or (polyphonic_context.get("harmonic_timeline") or {}).get("dispatch_created_at_ms")
        )
        approved_at_ms = self._to_epoch_ms(
            queue_doc.get("approved_at")
            or payload.get("approved_at")
            or queue_doc.get("updated_at")
        )
        observation = self.harmonic.score_observation(
            actor_id=str(actor or "governance_executor"),
            tool_name=str(payload.get("command_type") or payload.get("tool") or action_type),
            target_domain=scope,
            environment=self.environment,
            stage=stage,
            timestamp_ms=float(ts_ms),
            operation=action_type,
            context={
                "outcome": outcome,
                "queue_id": queue_doc.get("queue_id"),
                "decision_id": queue_doc.get("decision_id"),
            },
        )
        polyphonic_context["timing_features"] = observation.get("timing_features")
        polyphonic_context["harmonic_state"] = observation.get("harmonic_state")
        polyphonic_context["baseline_ref"] = observation.get("baseline_ref")
        history = list(polyphonic_context.get("harmonic_history") or [])
        history.append(
            {
                "stage": stage,
                "timestamp_ms": ts_ms,
                "harmonic_state": observation.get("harmonic_state"),
            }
        )
        polyphonic_context["harmonic_history"] = history[-30:]
        timeline = dict(polyphonic_context.get("harmonic_timeline") or {})
        if dispatch_created_at_ms is not None:
            timeline.setdefault("dispatch_created_at_ms", dispatch_created_at_ms)
            if stage == "executor_start":
                timeline["time_since_queue_ms"] = max(0, ts_ms - dispatch_created_at_ms)
        if approved_at_ms is not None and stage == "executor_start":
            timeline["approved_at_ms"] = approved_at_ms
            timeline["time_since_approval_ms"] = max(0, ts_ms - approved_at_ms)
        if stage == "executor_start":
            timeline["executor_start_ms"] = ts_ms
        elif stage == "executor_end":
            timeline["executor_end_ms"] = ts_ms
            start = self._to_epoch_ms(timeline.get("executor_start_ms"))
            if start is not None:
                timeline["execution_duration_ms"] = max(0, ts_ms - start)
        elif stage == "audit_closed":
            timeline["audit_closed_at_ms"] = ts_ms
            end = self._to_epoch_ms(timeline.get("executor_end_ms"))
            if end is not None:
                timeline["closure_lag_ms"] = max(0, ts_ms - end)
        polyphonic_context["harmonic_timeline"] = timeline
        edge_observation = dict(polyphonic_context.get("edge_observation") or {})
        participant = None
        step_name = None
        if stage == "executor_start":
            participant = "executor"
            step_name = "executor_started"
        elif stage == "executor_end":
            participant = "executor"
            step_name = "executor_completed"
        elif stage == "audit_closed":
            participant = "audit_closure"
            step_name = "audit_closure"
        if participant and step_name:
            participants = list(edge_observation.get("observed_participants") or [])
            if participant not in participants:
                participants.append(participant)
            edge_observation["observed_participants"] = participants
            sequence = list(edge_observation.get("observed_sequence") or [])
            if step_name not in sequence:
                sequence.append(step_name)
            edge_observation["observed_sequence"] = sequence
            timestamps = dict(edge_observation.get("timestamps_ms") or {})
            timestamps[step_name] = float(ts_ms)
            edge_observation["timestamps_ms"] = timestamps
            state_events = list(edge_observation.get("state_events") or [])
            if step_name not in state_events:
                state_events.append(step_name)
            edge_observation["state_events"] = state_events
            polyphonic_context["edge_observation"] = edge_observation
            if hasattr(vns, "update_edge_mesh_state"):
                mesh_state = vns.update_edge_mesh_state(
                    action_id=str(payload.get("command_id") or queue_doc.get("action_id") or queue_doc.get("queue_id") or ""),
                    edge_type=str(polyphonic_context.get("edge_type") or queue_doc.get("edge_type") or "agent_command_execution"),
                    participant=participant,
                    timestamp_ms=float(ts_ms),
                )
                if mesh_state and mesh_state.get("mesh_state") in {"strained", "scattered"}:
                    vns_events = list(edge_observation.get("vns_events") or [])
                    if "pulse_instability_warning" not in vns_events:
                        vns_events.append("pulse_instability_warning")
                    edge_observation["vns_events"] = vns_events
                    polyphonic_context["edge_observation"] = edge_observation
        try:
            if hasattr(vns, "update_domain_pulse"):
                pulse_state = vns.update_domain_pulse(
                    domain=scope,
                    timing_features=observation.get("timing_features") or {},
                    harmonic_state=observation.get("harmonic_state") or {},
                    timestamp_ms=ts_ms,
                )
                if (
                    pulse_state
                    and float(pulse_state.get("pulse_stability_index") or 1.0) < 0.45
                    and hasattr(vns_alert_service, "alert_pulse_instability_by_domain")
                ):
                    vns_alert_service.alert_pulse_instability_by_domain(pulse_state)
        except Exception:
            pass
        return observation

    def attach_execution_timing_observation(
        self,
        *,
        actor: str,
        action_type: str,
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        stage: str,
        timestamp_ms: Optional[int] = None,
        outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._attach_execution_timing_observation(
            actor=actor,
            action_type=action_type,
            queue_doc=queue_doc,
            payload=payload,
            polyphonic_context=polyphonic_context,
            stage=stage,
            timestamp_ms=timestamp_ms,
            outcome=outcome,
        )

    async def finalize_harmonic_state(
        self,
        *,
        decision_id: Optional[str],
        queue_id: Optional[str],
        actor: str,
        action_type: str,
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        outcome: str,
        reason: Optional[str] = None,
    ) -> None:
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        obs = self.attach_execution_timing_observation(
            actor=str(actor),
            action_type=action_type,
            queue_doc=queue_doc,
            payload=payload,
            polyphonic_context=polyphonic_context,
            stage="executor_end",
            timestamp_ms=end_ms,
            outcome=outcome,
        )
        self.attach_execution_timing_observation(
            actor=str(actor),
            action_type=action_type,
            queue_doc=queue_doc,
            payload=payload,
            polyphonic_context=polyphonic_context,
            stage="audit_closed",
            timestamp_ms=end_ms,
            outcome=outcome,
        )
        payload["polyphonic_context"] = polyphonic_context
        queue_doc["polyphonic_context"] = polyphonic_context
        harmonic_state = obs.get("harmonic_state")
        await self.db.triune_outbound_queue.update_one(
            {"queue_id": queue_id},
            {
                "$set": {
                    "executor_end_ms": end_ms,
                    "polyphonic_context": polyphonic_context,
                    "timing_features_at_executor_end": obs.get("timing_features"),
                    "harmonic_state_at_executor_end": harmonic_state,
                    "baseline_ref": obs.get("baseline_ref"),
                    "updated_at": _iso_now(),
                }
            },
        )
        await self.db.triune_decisions.update_one(
            {"decision_id": decision_id},
            {
                "$set": {
                    "executor_end_ms": end_ms,
                    "polyphonic_context": polyphonic_context,
                    "timing_features_at_executor_end": obs.get("timing_features"),
                    "harmonic_state_at_executor_end": harmonic_state,
                    "baseline_ref": obs.get("baseline_ref"),
                    "updated_at": _iso_now(),
                }
            },
        )
        timing_features = obs.get("timing_features") or {}
        if (
            float(timing_features.get("drift_norm") or 0.0) >= 0.6
            and hasattr(vns_alert_service, "alert_harmonic_drift_detected")
        ):
            vns_alert_service.alert_harmonic_drift_detected(
                {
                    "scope": str(
                        payload.get("target_domain")
                        or (payload.get("parameters") or {}).get("target_domain")
                        or queue_doc.get("target_domain")
                        or "global"
                    ),
                    "action_type": action_type,
                    "actor": actor,
                    "drift_norm": timing_features.get("drift_norm"),
                    "confidence": float((harmonic_state or {}).get("confidence") or 0.0),
                }
            )
        if (
            float(timing_features.get("burstiness") or 0.0) >= 0.6
            and hasattr(vns_alert_service, "alert_burst_cluster_detected")
        ):
            vns_alert_service.alert_burst_cluster_detected(
                {
                    "scope": str(
                        payload.get("target_domain")
                        or (payload.get("parameters") or {}).get("target_domain")
                        or queue_doc.get("target_domain")
                        or "global"
                    ),
                    "action_type": action_type,
                    "burstiness": timing_features.get("burstiness"),
                    "discord_score": float((harmonic_state or {}).get("discord_score") or 0.0),
                }
            )
        discord = float((harmonic_state or {}).get("discord_score") or 0.0)
        if discord >= 0.75 and hasattr(vns_alert_service, "alert_discord_threshold_crossed"):
            vns_alert_service.alert_discord_threshold_crossed(
                {
                    "scope": str(
                        payload.get("target_domain")
                        or (payload.get("parameters") or {}).get("target_domain")
                        or queue_doc.get("target_domain")
                        or "global"
                    ),
                    "action_type": action_type,
                    "actor": actor,
                    "discord_score": discord,
                    "confidence": float((harmonic_state or {}).get("confidence") or 0.0),
                    "reason": reason,
                }
            )

    def build_execution_edge_observation(
        self,
        *,
        action_id: str,
        action_type: str,
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        outcome: str,
    ) -> Dict[str, Any]:
        edge_type = (
            (polyphonic_context.get("edge_type") if isinstance(polyphonic_context, dict) else None)
            or queue_doc.get("edge_type")
            or ("agent_command_execution" if action_type in {"agent_command", "swarm_command"} else "outbound_gated_action")
        )
        edge_context = (
            (polyphonic_context.get("edge_context") if isinstance(polyphonic_context, dict) else None)
            or queue_doc.get("edge_context")
            or {}
        )
        base_observation = (
            (polyphonic_context.get("edge_observation") if isinstance(polyphonic_context, dict) else None)
            or {}
        )
        harmonic_timeline = (
            (polyphonic_context.get("harmonic_timeline") if isinstance(polyphonic_context, dict) else None)
            or {}
        )
        observed_participants = list(base_observation.get("observed_participants") or edge_context.get("observed_participants") or [])
        for participant in ["executor", "audit_closure"]:
            if participant not in observed_participants:
                observed_participants.append(participant)
        observed_sequence = list(base_observation.get("observed_sequence") or edge_context.get("observed_sequence") or [])
        for step in ["executor_started", "executor_completed", "audit_closure", "edge_settled"]:
            if step not in observed_sequence:
                observed_sequence.append(step)
        timestamps_ms = dict(base_observation.get("timestamps_ms") or edge_context.get("timestamps_ms") or {})
        if harmonic_timeline.get("executor_start_ms") is not None:
            timestamps_ms["executor_started"] = float(harmonic_timeline.get("executor_start_ms"))
            timestamps_ms.setdefault("executor", float(harmonic_timeline.get("executor_start_ms")))
        if harmonic_timeline.get("executor_end_ms") is not None:
            timestamps_ms["executor_completed"] = float(harmonic_timeline.get("executor_end_ms"))
        if harmonic_timeline.get("audit_closed_at_ms") is not None:
            timestamps_ms["audit_closure"] = float(harmonic_timeline.get("audit_closed_at_ms"))
            timestamps_ms["audit_closed"] = float(harmonic_timeline.get("audit_closed_at_ms"))
            timestamps_ms["edge_settled"] = float(harmonic_timeline.get("audit_closed_at_ms"))
        state_events = list(base_observation.get("state_events") or edge_context.get("state_events") or [])
        for event_name in ["executor_started", "executor_completed", "edge_settled"]:
            if event_name not in state_events:
                state_events.append(event_name)
        audit_events = list(base_observation.get("audit_events") or edge_context.get("audit_events") or [])
        if "audit_closed" not in audit_events:
            audit_events.append("audit_closed")
        vns_events = list(base_observation.get("vns_events") or edge_context.get("vns_events") or [])
        mesh_state = vns.assess_local_entrainment(action_id=str(action_id)) if hasattr(vns, "assess_local_entrainment") else {}
        if mesh_state and mesh_state.get("mesh_state") in {"scattered", "strained"}:
            if "pulse_instability_warning" not in vns_events:
                vns_events.append("pulse_instability_warning")
        observation_model = self.chorus.collect_edge_participants(
            action_id=str(action_id),
            context={
                "edge_type": edge_type,
                "observed_participants": observed_participants,
                "observed_sequence": observed_sequence,
                "timestamps_ms": timestamps_ms,
                "audit_events": audit_events,
                "state_events": state_events,
                "vns_events": vns_events,
            },
        )
        return _model_dump(observation_model)

    async def attach_chorus_state_to_action(
        self,
        *,
        decision_id: Optional[str],
        queue_id: Optional[str],
        payload: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        spec: Dict[str, Any],
        observation: Dict[str, Any],
        chorus_state: Dict[str, Any],
    ) -> None:
        polyphonic_context["chorus_spec"] = spec
        polyphonic_context["edge_observation"] = observation
        polyphonic_context["chorus_state"] = chorus_state
        payload["polyphonic_context"] = polyphonic_context
        update_fields = {
            "polyphonic_context": polyphonic_context,
            "chorus_spec": spec,
            "edge_observation": observation,
            "chorus_state": chorus_state,
            "resolution_class": chorus_state.get("resolution_class"),
            "dissonance_class": chorus_state.get("dissonance_class"),
            "updated_at": _iso_now(),
        }
        await self.db.triune_outbound_queue.update_one(
            {"queue_id": queue_id},
            {"$set": update_fields},
        )
        await self.db.triune_decisions.update_one(
            {"decision_id": decision_id},
            {"$set": update_fields},
        )

    async def finalize_chorus_state(
        self,
        *,
        decision_id: Optional[str],
        queue_id: Optional[str],
        action_id: str,
        action_type: str,
        actor: str,
        outcome: str,
        payload: Dict[str, Any],
        queue_doc: Dict[str, Any],
        polyphonic_context: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        edge_type = (
            (polyphonic_context.get("edge_type") if isinstance(polyphonic_context, dict) else None)
            or queue_doc.get("edge_type")
            or ("agent_command_execution" if action_type in {"agent_command", "swarm_command"} else "outbound_gated_action")
        )
        spec_model = self.chorus.load_edge_chorus_spec(
            edge_type=str(edge_type),
            genre_mode=str(payload.get("genre_mode") or polyphonic_context.get("genre_mode") or ""),
        )
        observation_doc = self.build_execution_edge_observation(
            action_id=str(action_id),
            action_type=action_type,
            queue_doc=queue_doc,
            payload=payload,
            polyphonic_context=polyphonic_context,
            outcome=outcome,
        )
        observation_model = self.chorus.collect_edge_participants(
            action_id=str(action_id),
            context=observation_doc,
        )
        chorus_state_model = self.chorus.assemble_chorus_state(
            spec=spec_model,
            observation=observation_model,
        )
        spec_doc = _model_dump(spec_model)
        observation_dump = _model_dump(observation_model)
        chorus_state = _model_dump(chorus_state_model)

        await self.attach_chorus_state_to_action(
            decision_id=decision_id,
            queue_id=queue_id,
            payload=payload,
            polyphonic_context=polyphonic_context,
            spec=spec_doc,
            observation=observation_dump,
            chorus_state=chorus_state,
        )

        if tamper_evident_telemetry is not None:
            try:
                tamper_evident_telemetry.set_db(self.db)
                if hasattr(tamper_evident_telemetry, "record_edge_sequence"):
                    tamper_evident_telemetry.record_edge_sequence(
                        action_id=str(action_id),
                        edge_type=str(edge_type),
                        sequence=observation_dump.get("observed_sequence") or [],
                        timeline=observation_dump.get("timestamps_ms") or {},
                        trace_id=str(payload.get("trace_id") or ""),
                    )
                if hasattr(tamper_evident_telemetry, "record_participant_appearance"):
                    for participant in observation_dump.get("observed_participants") or []:
                        tamper_evident_telemetry.record_participant_appearance(
                            action_id=str(action_id),
                            edge_type=str(edge_type),
                            participant=str(participant),
                            timestamp_ms=(observation_dump.get("timestamps_ms") or {}).get(str(participant)),
                            trace_id=str(payload.get("trace_id") or ""),
                        )
            except Exception:
                logger.debug("Failed to record chorus telemetry", exc_info=True)

        settlement_timeout_ms = int(spec_doc.get("settlement_timeout_ms") or 0)
        opened = float((observation_dump.get("timestamps_ms") or {}).get("edge_opened") or 0.0)
        settled = float((observation_dump.get("timestamps_ms") or {}).get("edge_settled") or 0.0)
        settlement_lag_ms = max(0.0, settled - opened) if opened and settled else None
        if record_edge_closure is not None:
            try:
                await record_edge_closure(
                    edge_type=str(edge_type),
                    action_id=str(action_id),
                    actor=f"service:{actor or 'governance_executor'}",
                    closure_completed=True,
                    closure_lag_ms=settlement_lag_ms,
                    settlement_timeout_ms=settlement_timeout_ms or None,
                    evidence_anchors_present=bool(observation_dump.get("audit_events")),
                    details={"resolution_class": chorus_state.get("resolution_class"), "dissonance_class": chorus_state.get("dissonance_class")},
                )
                if settlement_lag_ms is not None:
                    await record_closure_lag(
                        edge_type=str(edge_type),
                        action_id=str(action_id),
                        closure_lag_ms=settlement_lag_ms,
                        settlement_timeout_ms=settlement_timeout_ms or None,
                        actor=f"service:{actor or 'governance_executor'}",
                    )
                await record_settlement_state(
                    edge_type=str(edge_type),
                    action_id=str(action_id),
                    settlement_state=str(chorus_state.get("resolution_class") or "unknown"),
                    actor=f"service:{actor or 'governance_executor'}",
                    details={"reason": reason, "outcome": outcome},
                )
            except Exception:
                logger.debug("Failed to record edge closure audit", exc_info=True)

        if emit_world_event is not None:
            try:
                event_type = "edge_chorus_fractured" if str(chorus_state.get("resolution_class")) in {"dissonant", "fractured"} else "edge_settled"
                await emit_world_event(
                    self.db,
                    event_type=event_type,
                    entity_refs=[decision_id, queue_id, str(action_id)],
                    payload={
                        "action_id": str(action_id),
                        "edge_type": str(edge_type),
                        "outcome": outcome,
                        "reason": reason,
                        "chorus_state": chorus_state,
                        "edge_observation": observation_dump,
                        "polyphonic_context": polyphonic_context or None,
                    },
                    trigger_triune=str(chorus_state.get("resolution_class")) in {"dissonant", "fractured"},
                    source="governance_executor",
                )
                await emit_world_event(
                    self.db,
                    event_type="audit_closed",
                    entity_refs=[decision_id, queue_id, str(action_id)],
                    payload={
                        "action_id": str(action_id),
                        "edge_type": str(edge_type),
                        "audit_events": observation_dump.get("audit_events") or [],
                        "timestamps_ms": observation_dump.get("timestamps_ms") or {},
                        "chorus_state": chorus_state,
                        "polyphonic_context": polyphonic_context or None,
                    },
                    trigger_triune=False,
                    source="governance_executor",
                )
            except Exception:
                logger.debug("Failed to emit chorus world events", exc_info=True)

        mesh_state = vns.assess_local_entrainment(action_id=str(action_id)) if hasattr(vns, "assess_local_entrainment") else {}
        if mesh_state and float(mesh_state.get("pulse_coherence") or 1.0) < 0.55 and hasattr(vns_alert_service, "alert_edge_entrainment_warning"):
            vns_alert_service.alert_edge_entrainment_warning(mesh_state)
        if str(chorus_state.get("resolution_class") or "") in {"dissonant", "fractured"} and hasattr(vns_alert_service, "alert_chorus_fracture_warning"):
            vns_alert_service.alert_chorus_fracture_warning(
                {
                    "action_id": str(action_id),
                    "edge_type": str(edge_type),
                    "resolution_class": chorus_state.get("resolution_class"),
                    "dissonance_class": chorus_state.get("dissonance_class"),
                    "rationale": chorus_state.get("rationale") or [],
                }
            )
        if settlement_lag_ms is not None and settlement_timeout_ms and settlement_lag_ms > settlement_timeout_ms and hasattr(vns_alert_service, "alert_settlement_timeout_warning"):
            vns_alert_service.alert_settlement_timeout_warning(
                {
                    "action_id": str(action_id),
                    "edge_type": str(edge_type),
                    "settlement_lag_ms": settlement_lag_ms,
                    "settlement_timeout_ms": settlement_timeout_ms,
                }
            )
        return {
            "chorus_spec": spec_doc,
            "edge_observation": observation_dump,
            "chorus_state": chorus_state,
            "mesh_state": mesh_state,
        }

    async def _validate_notation_for_execution(
        self,
        *,
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        enforce_sequence_slot: Optional[bool] = None,
        enforce_required_companions: Optional[bool] = None,
    ) -> Dict[str, Any]:
        notation_ctx = self._notation_token_from_context(queue_doc, payload)
        scope = str(
            payload.get("target_domain") or (payload.get("parameters") or {}).get("target_domain") or "global"
        )
        active_epoch = await self.epoch_service.get_active_epoch(scope=scope)
        active_epoch_doc = (
            active_epoch.model_dump() if hasattr(active_epoch, "model_dump") else active_epoch.dict()
        ) if active_epoch is not None else None
        profile = self.notation_tokens.resolve_enforcement_profile(
            genre_mode=(
                (active_epoch.genre_mode if active_epoch is not None else None)
                or payload.get("genre_mode")
                or queue_doc.get("genre_mode")
            ),
            strictness_level=(
                (active_epoch.strictness_level if active_epoch is not None else None)
                or payload.get("strictness_level")
                or queue_doc.get("strictness_level")
            ),
        )
        capability_required = bool(
            self.environment == "production"
            and str(queue_doc.get("impact_level") or "").lower() in {"high", "critical"}
        )
        expected_action_digest = canonical_action_digest(
            action_type=str(queue_doc.get("action_type") or ""),
            actor=str(queue_doc.get("actor") or ""),
            subject_id=queue_doc.get("subject_id"),
            impact_level=str(queue_doc.get("impact_level") or ""),
            payload=payload,
        )
        expected_target_digest = canonical_target_digest(
            subject_id=queue_doc.get("subject_id"),
            payload=payload,
        )
        return await self.notation_tokens.validate_notation_token(
            token=notation_ctx.get("token") or notation_ctx.get("token_id"),
            active_epoch=active_epoch_doc,
            world_state_hash=active_epoch.world_state_hash if active_epoch is not None else None,
            context={
                "baseline_time": queue_doc.get("created_at") or payload.get("created_at"),
                "observed_slot": payload.get("sequence_slot"),
                "observed_companions": payload.get("observed_companions") or [],
                "enforce_sequence_slot": profile.get("enforce_sequence_slot")
                if enforce_sequence_slot is None
                else bool(enforce_sequence_slot),
                "enforce_required_companions": profile.get("enforce_required_companions")
                if enforce_required_companions is None
                else bool(enforce_required_companions),
                "require_capability": capability_required,
                "capability_lease_id": payload.get("capability_lease_id"),
                "authority_request_digest": payload.get("authority_request_digest"),
                "action_digest": expected_action_digest,
                "target_digest": expected_target_digest,
                "audience": "metatron-outbound-gate",
            },
        )

    async def _mark_notation_execution_outcome(self, token_id: Optional[str], *, outcome: str) -> None:
        if not token_id:
            return
        try:
            await self.notation_tokens.consume_notation_token(str(token_id), outcome=outcome)
        except Exception:
            logger.debug("Failed to mark notation token %s outcome=%s", token_id, outcome, exc_info=True)

    async def _emit_execution_completion_event(
        self,
        *,
        decision_id: Optional[str],
        queue_id: Optional[str],
        action_type: str,
        outcome: str,
        reason: Optional[str] = None,
        command_id: Optional[str] = None,
        command_type: Optional[str] = None,
        token_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        polyphonic_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if emit_world_event is None:
            return
        resolved_polyphonic = polyphonic_context if isinstance(polyphonic_context, dict) else {}
        voice_profile = resolved_polyphonic.get("voice_profile") if isinstance(resolved_polyphonic.get("voice_profile"), dict) else {}
        refs = [r for r in [decision_id, queue_id, command_id, token_id, execution_id] if r]
        payload = {
            "decision_id": decision_id,
            "queue_id": queue_id,
            "action_type": action_type,
            "outcome": outcome,
            "reason": reason,
            "command_id": command_id,
            "command_type": command_type,
            "token_id": token_id,
            "execution_id": execution_id,
            "trace_id": trace_id,
            "polyphonic_context": resolved_polyphonic or None,
            "voice_type": voice_profile.get("voice_type"),
            "capability_class": voice_profile.get("capability_class"),
        }
        await emit_world_event(
            self.db,
            event_type="governance_execution_completed",
            entity_refs=refs,
            payload=payload,
            trigger_triune=outcome == "failed",
            source="governance_executor",
        )
        await emit_world_event(
            self.db,
            event_type="executor_completed",
            entity_refs=refs,
            payload=payload,
            trigger_triune=outcome in {"failed", "skipped"},
            source="governance_executor",
        )

    def _record_execution_audit(
        self,
        *,
        decision_id: Optional[str],
        queue_id: Optional[str],
        action_type: str,
        outcome: str,
        reason: Optional[str] = None,
        actor: Optional[str] = None,
        targets: Optional[list] = None,
        command_id: Optional[str] = None,
        command_type: Optional[str] = None,
        token_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        polyphonic_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if tamper_evident_telemetry is None:
            return
        try:
            tamper_evident_telemetry.set_db(self.db)
            resolved_polyphonic = polyphonic_context if isinstance(polyphonic_context, dict) else {}
            voice_profile = (
                resolved_polyphonic.get("voice_profile")
                if isinstance(resolved_polyphonic.get("voice_profile"), dict)
                else {}
            )
            harmonic_state = resolved_polyphonic.get("harmonic_state") if isinstance(resolved_polyphonic, dict) else None
            timing_features = resolved_polyphonic.get("timing_features") if isinstance(resolved_polyphonic, dict) else None
            baseline_ref = resolved_polyphonic.get("baseline_ref") if isinstance(resolved_polyphonic, dict) else None
            harmonic_timeline = (
                resolved_polyphonic.get("harmonic_timeline")
                if isinstance(resolved_polyphonic, dict)
                else None
            )
            resolved_targets = [str(t) for t in (targets or []) if t]
            if not resolved_targets:
                resolved_targets = [str(x) for x in [queue_id, command_id, token_id] if x]
            tamper_evident_telemetry.record_action(
                principal=f"service:{actor or 'governance_executor'}",
                principal_trust_state="trusted",
                action=f"governance_execution:{action_type}",
                targets=resolved_targets,
                policy_decision_id=decision_id,
                governance_decision_id=decision_id,
                governance_queue_id=queue_id,
                token_id=token_id,
                execution_id=execution_id or command_id or "",
                trace_id=trace_id,
                constraints={
                    "command_type": command_type,
                    "reason": reason,
                    "voice_type": voice_profile.get("voice_type"),
                    "capability_class": voice_profile.get("capability_class"),
                    "timing_features": timing_features,
                    "harmonic_state": harmonic_state,
                    "baseline_ref": baseline_ref,
                },
                result="success" if outcome == "executed" else ("denied" if outcome == "skipped" else "failed"),
                result_details=reason,
            )
            if harmonic_timeline and hasattr(tamper_evident_telemetry, "record_harmonic_timeline"):
                tamper_evident_telemetry.record_harmonic_timeline(
                    trace_id=str(trace_id or ""),
                    timeline=harmonic_timeline,
                    baseline_ref=baseline_ref,
                    harmonic_state=harmonic_state,
                )
            if harmonic_state and hasattr(tamper_evident_telemetry, "store_harmonic_state"):
                tamper_evident_telemetry.store_harmonic_state(
                    trace_id=str(trace_id or ""),
                    state=harmonic_state,
                    contributors={
                        "timing_features": timing_features,
                        "baseline_ref": baseline_ref,
                    },
                )
        except Exception:
            logger.exception(
                "Failed to record governance execution audit for decision=%s queue=%s",
                decision_id,
                queue_id,
            )

    async def _run_domain_operation(
        self,
        *,
        action_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if action_type == "response_block_ip":
            from threat_response import ResponseStatus, firewall

            ip = str(payload.get("ip") or "").strip()
            if not ip:
                raise ValueError("Missing ip for response_block_ip")
            reason = str(payload.get("reason") or "Governed block")
            duration_hours = int(payload.get("duration_hours") or 24)
            result = await firewall.block_ip(ip=ip, reason=reason, duration_hours=duration_hours)
            if result.status != ResponseStatus.SUCCESS:
                raise RuntimeError(result.message)
            return {"operation": action_type, "ip": ip, "details": result.details}

        if action_type == "response_unblock_ip":
            from threat_response import ResponseStatus, firewall

            ip = str(payload.get("ip") or "").strip()
            if not ip:
                raise ValueError("Missing ip for response_unblock_ip")
            result = await firewall.unblock_ip(ip=ip)
            if result.status != ResponseStatus.SUCCESS:
                raise RuntimeError(result.message)
            return {"operation": action_type, "ip": ip, "details": result.details}

        if action_type == "quarantine_restore":
            from quarantine import restore_file

            entry_id = str(payload.get("entry_id") or "").strip()
            if not entry_id:
                raise ValueError("Missing entry_id for quarantine_restore")
            restored = bool(restore_file(entry_id))
            if not restored:
                raise RuntimeError(f"Failed to restore quarantined entry: {entry_id}")
            return {"operation": action_type, "entry_id": entry_id, "restored": True}

        if action_type == "quarantine_delete":
            from quarantine import delete_quarantined

            entry_id = str(payload.get("entry_id") or "").strip()
            if not entry_id:
                raise ValueError("Missing entry_id for quarantine_delete")
            deleted = bool(delete_quarantined(entry_id))
            if not deleted:
                raise RuntimeError(f"Failed to delete quarantined entry: {entry_id}")
            return {"operation": action_type, "entry_id": entry_id, "deleted": True}

        if action_type == "quarantine_agent":
            try:
                from services.identity import identity_service
            except Exception:
                from backend.services.identity import identity_service

            identity_service.set_db(self.db)
            agent_id = str(payload.get("agent_id") or "").strip()
            reason = str(payload.get("reason") or "Governed quarantine")
            if not agent_id:
                raise ValueError("Missing agent_id for quarantine_agent")
            quarantined = bool(identity_service.quarantine_agent(agent_id=agent_id, reason=reason))
            if not quarantined:
                raise RuntimeError(f"Failed to quarantine agent: {agent_id}")
            return {"operation": action_type, "agent_id": agent_id, "quarantined": True}

        if action_type in {
            "vpn_initialize",
            "vpn_start",
            "vpn_stop",
            "vpn_peer_add",
            "vpn_peer_remove",
            "vpn_kill_switch_enable",
            "vpn_kill_switch_disable",
        }:
            from vpn_integration import vpn_manager

            if action_type == "vpn_initialize":
                result = await vpn_manager.initialize()
            elif action_type == "vpn_start":
                result = await vpn_manager.start()
            elif action_type == "vpn_stop":
                result = await vpn_manager.stop()
            elif action_type == "vpn_peer_add":
                peer_name = str(payload.get("peer_name") or payload.get("name") or "").strip()
                if not peer_name:
                    raise ValueError("Missing peer_name for vpn_peer_add")
                result = await vpn_manager.add_peer(peer_name)
            elif action_type == "vpn_peer_remove":
                peer_id = str(payload.get("peer_id") or "").strip()
                if not peer_id:
                    raise ValueError("Missing peer_id for vpn_peer_remove")
                removed = bool(await vpn_manager.remove_peer(peer_id))
                if not removed:
                    raise RuntimeError(f"Failed to remove VPN peer: {peer_id}")
                result = {"peer_id": peer_id, "removed": True}
            elif action_type == "vpn_kill_switch_enable":
                result = await vpn_manager.kill_switch.enable()
            else:
                result = await vpn_manager.kill_switch.disable()
            return {"operation": action_type, "result": result}

        raise ValueError(f"Unsupported domain action_type: {action_type}")

    async def _execute_domain_operation(
        self,
        *,
        decision: Dict[str, Any],
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        actor: str,
        action_type: str,
    ) -> Dict[str, Any]:
        decision_id = decision.get("decision_id")
        related_queue_id = queue_doc.get("queue_id")
        polyphonic_context = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        now = _iso_now()
        
        # --- PHASE II: Constitutional Handoff Verification ---
        covenant_service = get_handoff_covenant_service(self.db)
        covenant = covenant_service.get_covenant() or await covenant_service.seal_covenant()
        
        # Final gate for manifestation
        if not covenant.runtime_permission:
            # Constitutional Veto
            error_reason = f"CONSTITUTIONAL VETO: {covenant.reason}"
            logger.error(f"Execution blocked for action '{action_type}' due to fractured formation. Reason: {covenant.reason}")
            
            # Record Veto Audit
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="constitutional_veto",
                actor=actor,
                command_type=action_type,
                token_id=payload.get("token_id"),
                reason=error_reason
            )
            
            # Update decision as blocked
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "vetoed",
                        "execution_error": error_reason,
                        "updated_at": now
                    }
                }
            )
            
            return {"outcome": "vetoed", "reason": error_reason}
            
        # Manwe check (Individual Integrity)
        herald_state = manwe_herald.get_state()
        if not herald_state or herald_state.status != "active":
            raise RuntimeError(f"Manwe Herald not active or in fractured state: {herald_state.status if herald_state else 'None'}")
            
        # --- PHASE IV: Cluster Consensus Guard ---
        consensus_guard = get_cluster_consensus_guard()
        sensitivity = "high" if action_type in {"quarantine_agent", "token_revoke", "domain_takeover"} else "medium"
        verdict = await consensus_guard.get_cluster_verdict(action_sensitivity=sensitivity)
        
        if verdict == "veto":
            error_reason = "CLUSTER VETO: Quorum resonance lost or cryptographic dissonance detected."
            logger.error(f"Execution VETOED for action '{action_type}' by the Triune Chorus.")
            
            # Record Veto Audit
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="cluster_veto",
                actor=actor,
                command_type=action_type,
                token_id=payload.get("token_id"),
                reason=error_reason
            )
            
            # Update decision as blocked
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "vetoed",
                        "execution_error": error_reason,
                        "updated_at": now
                    }
                }
            )
            
            return {"outcome": "vetoed", "reason": error_reason}
        elif verdict == "caution":
            logger.warning(f"PHASE IV: Executing action '{action_type}' under CAUTION (Degraded Quorum).")
        # --- PHASE V: Process Birth & Manifestation Gate ---
        # If the action requires creating a local OS process, we consult the Birth Guard.
        if action_type in {"job_manifest", "process_spawn", "service_restart", "agent_manifest"}:
            try:
                from services.process_birth_guard import get_process_birth_guard
                from schemas.phase5_models import ProcessBirthRequest, ExecutionClass, ManifestationStatus
            except Exception:
                from backend.services.process_birth_guard import get_process_birth_guard
                from backend.schemas.phase5_models import ProcessBirthRequest, ExecutionClass, ManifestationStatus
            
            birth_guard = get_process_birth_guard(self.db)
            birth_request = ProcessBirthRequest(
                binary_path=payload.get("binary_path", "unknown-path"),
                target_uid=0, # Assuming privileged manifestation context
                target_gid=0,
                execution_class=ExecutionClass.PROTECTED,
                capability_token=payload.get("token_id")
            )
            
            birth_decision = await birth_guard.evaluate_manifestation(birth_request)
            
            if birth_decision.status in {ManifestationStatus.VETOED, ManifestationStatus.REJECTED}:
                error_reason = f"MANIFESTATION VETO: Process birth denied by Arda Law. Reason: {birth_decision.reason}"
                logger.error(f"Process manifestation for '{action_type}' failed constitutional birth check.")
                
                # Record Veto Audit
                self._record_execution_audit(
                    decision_id=decision_id,
                    queue_id=related_queue_id,
                    action_type=action_type,
                    outcome="manifestation_veto",
                    actor=actor,
                    command_type=action_type,
                    token_id=payload.get("token_id"),
                    reason=error_reason
                )
                return {"outcome": "vetoed", "reason": error_reason}
            
            elif birth_decision.status == ManifestationStatus.SANDBOXED:
                logger.warning(f"PHASE V: Action '{action_type}' permitted but SANDBOXED (profile: {birth_decision.seccomp_profile}).")
        
        # --- END PHASE V GUARD ---

        try:
            op_result = await self._run_domain_operation(action_type=action_type, payload=payload)
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "released_to_execution",
                        "released_at": now,
                        "updated_at": now,
                        "execution_result": op_result,
                        "polyphonic_context": polyphonic_context or None,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "executed",
                        "executed_at": now,
                        "updated_at": now,
                        "execution_result": op_result,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    }
                },
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="governance_domain_operation_executed",
                    entity_refs=[decision_id, related_queue_id, action_type],
                    payload={
                        **op_result,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    },
                    trigger_triune=False,
                    source="governance_executor",
                )
            resolved_execution_id = str(
                op_result.get("execution_id")
                or op_result.get("entry_id")
                or op_result.get("ip")
                or op_result.get("agent_id")
                or f"{action_type}:{decision_id}"
            )
            resolved_token_id = str(payload.get("token_id") or "")
            resolved_trace_id = str(payload.get("trace_id") or "")
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="executed",
                actor=actor,
                command_type=action_type,
                token_id=resolved_token_id,
                execution_id=resolved_execution_id,
                trace_id=resolved_trace_id,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[
                    payload.get("agent_id"),
                    payload.get("entry_id"),
                    payload.get("ip"),
                    payload.get("peer_id"),
                    payload.get("peer_name"),
                    related_queue_id,
                ],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="executed",
                reason=action_type,
                command_type=action_type,
                token_id=resolved_token_id,
                execution_id=resolved_execution_id,
                trace_id=resolved_trace_id,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "executed", "result": op_result}
        except Exception as exc:
            error_reason = str(exc)
            logger.exception(
                "Failed domain operation '%s' for decision %s: %s",
                action_type,
                decision_id,
                exc,
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": error_reason,
                        "updated_at": _iso_now(),
                    }
                },
            )
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "approved_execution_failed",
                        "updated_at": _iso_now(),
                    }
                },
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=error_reason,
                actor=actor,
                command_type=action_type,
                token_id=str(payload.get("token_id") or ""),
                execution_id=str(payload.get("entry_id") or payload.get("ip") or f"{action_type}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[
                    payload.get("agent_id"),
                    payload.get("entry_id"),
                    payload.get("ip"),
                    payload.get("peer_id"),
                    payload.get("peer_name"),
                    related_queue_id,
                ],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=error_reason,
                command_type=action_type,
                token_id=str(payload.get("token_id") or ""),
                execution_id=str(payload.get("entry_id") or payload.get("ip") or f"{action_type}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "failed", "reason": "domain_operation_exception"}

    async def _execute_tool_runtime_operation(
        self,
        *,
        decision: Dict[str, Any],
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        actor: str,
    ) -> Dict[str, Any]:
        decision_id = decision.get("decision_id")
        related_queue_id = queue_doc.get("queue_id")
        polyphonic_context = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        now = _iso_now()
        tool = str(payload.get("tool") or "").strip().lower()
        runtime_target = str(payload.get("runtime_target") or "server").strip().lower()
        agent_id = str(payload.get("agent_id") or "").strip() or None
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        params = dict(params or {})
        # Backward compatibility for legacy payload shapes.
        if payload.get("domain") and not params.get("domain"):
            params["domain"] = payload.get("domain")
        if payload.get("collection_name") and not params.get("collection_name"):
            params["collection_name"] = payload.get("collection_name")
        if payload.get("target") and not params.get("target"):
            params["target"] = payload.get("target")
        if payload.get("options") and not params.get("options"):
            params["options"] = payload.get("options")

        governance_context = self._governance_context_for_execution(
            decision_id=decision_id,
            queue_id=related_queue_id,
            action_type="tool_execution",
        )
        try:
            from integrations_manager import run_runtime_tool

            job = await run_runtime_tool(
                tool=tool,
                params=params,
                runtime_target=runtime_target,
                agent_id=agent_id,
                actor=actor,
                governance_context=governance_context,
            )
            op_result = {
                "operation": "tool_execution",
                "tool": tool,
                "runtime_target": runtime_target,
                "agent_id": agent_id,
                "job_id": job.get("id"),
                "job_status": job.get("status"),
                "job_result": job.get("result"),
            }
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "released_to_execution",
                        "released_at": now,
                        "updated_at": now,
                        "execution_result": op_result,
                        "polyphonic_context": polyphonic_context or None,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "executed",
                        "executed_at": now,
                        "updated_at": now,
                        "execution_result": op_result,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    }
                },
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="governance_tool_execution_executed",
                    entity_refs=[decision_id, related_queue_id, tool, str(job.get("id"))],
                    payload={
                        **op_result,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    },
                    trigger_triune=False,
                    source="governance_executor",
                )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="tool_execution",
                outcome="executed",
                actor=actor,
                command_id=str(job.get("id") or ""),
                command_type=f"tool:{tool}",
                execution_id=str(job.get("id") or f"{tool}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[tool, runtime_target, agent_id, related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="tool_execution",
                outcome="executed",
                reason=f"tool:{tool}",
                command_id=str(job.get("id") or ""),
                command_type=f"tool:{tool}",
                execution_id=str(job.get("id") or f"{tool}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "executed", "result": op_result}
        except Exception as exc:
            error_reason = str(exc)
            logger.exception("Failed tool execution for decision %s: %s", decision_id, exc)
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": error_reason,
                        "updated_at": _iso_now(),
                    }
                },
            )
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "approved_execution_failed",
                        "updated_at": _iso_now(),
                    }
                },
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="tool_execution",
                outcome="failed",
                reason=error_reason,
                actor=actor,
                command_type=f"tool:{tool}",
                execution_id=str(payload.get("command_id") or f"{tool}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[tool, runtime_target, agent_id, related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="tool_execution",
                outcome="failed",
                reason=error_reason,
                command_type=f"tool:{tool}",
                execution_id=str(payload.get("command_id") or f"{tool}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "failed", "reason": "tool_execution_exception"}

    async def process_approved_decisions(self, *, limit: int = 100) -> Dict[str, Any]:
        cursor = self.db.triune_decisions.find(
            {
                "status": "approved",
                "related_queue_id": {"$exists": True, "$ne": None},
                "execution_status": {"$nin": ["executed", "skipped", "failed"]},
            },
            {"_id": 0},
        ).sort("updated_at", 1).limit(limit)
        decisions = await cursor.to_list(limit)

        processed = 0
        executed = 0
        skipped = 0
        failed = 0
        for decision in decisions:
            release_not_before = decision.get("harmonic_release_not_before")
            if release_not_before:
                release_dt = self._to_epoch_ms(release_not_before)
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                if release_dt is not None and now_ms < release_dt:
                    continue
            processed += 1
            result = await self._execute_decision(decision)
            outcome = result.get("outcome")
            if outcome == "executed":
                executed += 1
            elif outcome == "skipped":
                skipped += 1
            else:
                failed += 1

        return {
            "processed": processed,
            "executed": executed,
            "skipped": skipped,
            "failed": failed,
        }

    async def _verify_constitutional_compliance(self, action_type: str, context_id: Optional[str] = None) -> Tuple[bool, str]:
        """Verify the constitutional health (Phase I) before any execution."""
        is_dev = os.environ.get("ARDA_ENV") != "production"
        allow_dev_override = os.environ.get("ARDA_ALLOW_DEV_CONSTITUTIONAL_OVERRIDE", "0").lower() in (
            "1",
            "true",
            "yes",
        )
        
        # 1. Check Tree of Truth (Boot)
        bundle = boot_attestation.get_current_bundle() if boot_attestation else None
        if bundle is None and boot_attestation is not None:
            try:
                if getattr(boot_attestation, "db", None) is None:
                    boot_attestation.db = self.db
                world_model = getattr(boot_attestation, "world_model", None)
                if world_model is not None and getattr(world_model, "db", None) is None and hasattr(world_model, "set_database"):
                    world_model.set_database(self.db)
                bundle = await boot_attestation.collect_boot_truth()
                logger.info("Governance executor initialized missing boot attestation bundle on demand")
            except Exception as exc:
                logger.warning("Governance executor failed to initialize boot attestation bundle: %s", exc)
        if not bundle or bundle.status != "lawful":
                        msg = f"Constitutional failure: Boot state is {bundle.status if bundle else 'none'}"
                        if is_dev and allow_dev_override:
                                logger.warning(f"{msg} (Overridden in development)")
                        else:
                                return False, msg
             
        # 2. Check Herald (Identity)
        herald = manwe_herald.get_state() if manwe_herald else None
        if not herald or herald.status != "active":
                        msg = "Constitutional failure: Manwë Herald is inactive"
                        if is_dev and allow_dev_override:
                                logger.warning(f"{msg} (Overridden in development)")
                        else:
                                return False, msg
             
        # 3. Check Arda Fabric (Workload Integrity - Phase D)
        node_id = herald.attested_state_ref or herald.device_id if herald else "local-substrate"
        fabric_state = self.fabric.get_subject_state(node_id)
        if fabric_state in {"fallen", "dissonant"}:
                        msg = f"Constitutional blockade: node '{node_id}' is in {fabric_state.upper()} state"
                        if is_dev and allow_dev_override:
                                logger.warning(f"{msg} (Overridden in development)")
                        else:
                                return False, msg

        # 4. Consult Ainur Choir
        from backend.services.secret_fire import get_secret_fire_forge
        fire_service = get_secret_fire_forge()
        secret_fire = fire_service.get_current_packet()
        
        choir_verdict = await self.choir.evaluate({
            "action_type": action_type,
            "secret_fire": secret_fire,
            "runtime_identity": herald.runtime_identity if herald else "governance-executor",
            "node_id": node_id,
            "entity_id": context_id or action_type
        })
        await project_choir_truth(choir_verdict)
        if not choir_verdict.heralding_allowed:
            # Phase VII: Engage Tulkas for enforcement
            await self.tulkas.execute_enforcement(choir_verdict, node_id)
            msg = f"Ainur Choir {choir_verdict.overall_state.upper()}: {'; '.join(choir_verdict.reasons)}"
            if is_dev and allow_dev_override:
                logger.warning(f"{msg} (Overridden in development)")
            else:
                return False, msg

        return True, "Constitutional compliance verified"

    async def _execute_response_operation(
        self,
        *,
        decision: Dict[str, Any],
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        actor: str,
    ) -> Dict[str, Any]:
        decision_id = decision.get("decision_id")
        related_queue_id = queue_doc.get("queue_id")
        now = _iso_now()
        polyphonic_context = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        if not isinstance(polyphonic_context, dict):
            polyphonic_context = {}

        operation = str(payload.get("operation") or "").strip().lower()
        if not operation:
            return {"outcome": "skipped", "reason": "missing_response_operation"}

        if operation == "soar_execute_playbook":
            from backend.soar_engine import soar_engine

            playbook_id = str(payload.get("playbook_id") or queue_doc.get("subject_id") or "").strip()
            if not playbook_id:
                raise ValueError("Missing playbook_id for soar_execute_playbook")
            event = payload.get("event") or {}
            execution = await soar_engine.execute_playbook(playbook_id, event)
            execution_payload = execution.to_dict() if hasattr(execution, "to_dict") else _model_dump(execution)
            execution_id = execution_payload.get("id") or execution_payload.get("execution_id")

            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "released_to_execution",
                        "execution_status": "executed",
                        "released_to_execution": True,
                        "released_at": now,
                        "executed_at": now,
                        "execution_result": {
                            "operation": operation,
                            "playbook_id": playbook_id,
                            "execution": execution_payload,
                        },
                        "polyphonic_context": polyphonic_context or None,
                        "updated_at": now,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "executed",
                        "executed_at": now,
                        "execution_result": {
                            "operation": operation,
                            "playbook_id": playbook_id,
                            "execution": execution_payload,
                        },
                        "polyphonic_context": polyphonic_context or None,
                        "updated_at": now,
                    }
                },
            )

            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="response_execution",
                outcome="executed",
                actor=actor,
                command_id=playbook_id,
                command_type=operation,
                execution_id=str(execution_id or playbook_id),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[playbook_id, related_queue_id, decision_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="response_execution",
                outcome="executed",
                command_id=playbook_id,
                command_type=operation,
                execution_id=str(execution_id or playbook_id),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {
                "outcome": "executed",
                "operation": operation,
                "playbook_id": playbook_id,
                "execution_id": execution_id,
            }

        if operation == "soar_trigger_playbooks":
            from backend.soar_engine import soar_engine

            event = payload.get("event") or {}
            event_id = str(payload.get("event_id") or queue_doc.get("subject_id") or "").strip()
            executions = await soar_engine.trigger_playbooks(event)
            execution_payloads = [
                execution.to_dict() if hasattr(execution, "to_dict") else _model_dump(execution)
                for execution in executions
            ]

            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "released_to_execution",
                        "execution_status": "executed",
                        "released_to_execution": True,
                        "released_at": now,
                        "executed_at": now,
                        "execution_result": {
                            "operation": operation,
                            "event_id": event_id,
                            "execution_count": len(execution_payloads),
                            "executions": execution_payloads,
                        },
                        "polyphonic_context": polyphonic_context or None,
                        "updated_at": now,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "executed",
                        "executed_at": now,
                        "execution_result": {
                            "operation": operation,
                            "event_id": event_id,
                            "execution_count": len(execution_payloads),
                            "executions": execution_payloads,
                        },
                        "polyphonic_context": polyphonic_context or None,
                        "updated_at": now,
                    }
                },
            )

            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="response_execution",
                outcome="executed",
                actor=actor,
                command_id=event_id or related_queue_id,
                command_type=operation,
                execution_id=event_id or related_queue_id,
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[event_id, related_queue_id, decision_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="response_execution",
                outcome="executed",
                command_id=event_id or related_queue_id,
                command_type=operation,
                execution_id=event_id or related_queue_id,
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {
                "outcome": "executed",
                "operation": operation,
                "event_id": event_id,
                "execution_count": len(execution_payloads),
            }

        return {"outcome": "skipped", "reason": f"unsupported_response_operation:{operation}"}

    async def _execute_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        decision_id = decision.get("decision_id")
        related_queue_id = decision.get("related_queue_id")
        now = _iso_now()

        queue_doc = await self.db.triune_outbound_queue.find_one(
            {"queue_id": related_queue_id},
            {"_id": 0},
        )
        if not queue_doc:
            reason = f"Queue document not found: {related_queue_id}"
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": reason,
                        "updated_at": now,
                    }
                },
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="unknown",
                outcome="failed",
                reason=reason,
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type="unknown",
                outcome="failed",
                reason=reason,
            )
            return {"outcome": "failed", "reason": "queue_not_found"}

        action_type = str(queue_doc.get("action_type") or "").lower()
        
        # Phase 1: Constitutional Intercept
        constitutional_valid, constitutional_msg = await self._verify_constitutional_compliance(
            action_type, 
            context_id=decision_id or related_queue_id
        )
        logger.debug(f"DEBUG: constitutional_valid={constitutional_valid}, msg={constitutional_msg}")
        if not constitutional_valid:
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": f"constitutional_veto: {constitutional_msg}",
                        "updated_at": now,
                    }
                },
            )
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {"$set": {"status": "constitutional_veto", "updated_at": now}},
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=constitutional_msg,
            )
            return {"outcome": "vetoed", "reason": f"CONSTITUTIONAL VETO: {constitutional_msg}"}

        payload = queue_doc.get("payload") or {}
        polyphonic_context = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        if not isinstance(polyphonic_context, dict):
            polyphonic_context = {}
        actor = queue_doc.get("actor") or "governance_executor"
        executor_start_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        harmonic_pre: Dict[str, Any] = {}
        try:
            harmonic_pre = self.attach_execution_timing_observation(
                actor=str(actor),
                action_type=action_type,
                queue_doc=queue_doc,
                payload=payload,
                polyphonic_context=polyphonic_context,
                stage="executor_start",
                timestamp_ms=executor_start_ms,
            )
            payload["polyphonic_context"] = polyphonic_context
            queue_doc["polyphonic_context"] = polyphonic_context
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "executor_start_ms": executor_start_ms,
                        "polyphonic_context": polyphonic_context,
                        "timing_features_at_executor_start": harmonic_pre.get("timing_features"),
                        "harmonic_state_at_executor_start": harmonic_pre.get("harmonic_state"),
                        "baseline_ref": harmonic_pre.get("baseline_ref"),
                        "updated_at": now,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "executor_start_ms": executor_start_ms,
                        "polyphonic_context": polyphonic_context,
                        "timing_features_at_executor_start": harmonic_pre.get("timing_features"),
                        "harmonic_state_at_executor_start": harmonic_pre.get("harmonic_state"),
                        "baseline_ref": harmonic_pre.get("baseline_ref"),
                        "updated_at": now,
                    }
                },
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="executor_started",
                    entity_refs=[decision_id, related_queue_id, str(queue_doc.get("action_id") or "")],
                    payload={
                        "action_type": action_type,
                        "executor_start_ms": executor_start_ms,
                        "polyphonic_context": polyphonic_context or None,
                    },
                    trigger_triune=False,
                    source="governance_executor",
                )
        except Exception:
            logger.debug("Failed to attach pre-execution harmonic observation", exc_info=True)
        notation_ctx = self._notation_token_from_context(queue_doc, payload)
        notation_validation = await self._validate_notation_for_execution(
            queue_doc=queue_doc,
            payload=payload,
        )
        notation_valid = bool(notation_validation.get("valid"))
        notation_checks = notation_validation.get("checks") or {}
        notation_failure_reason = ";".join(notation_validation.get("reasons") or []) or None
        capability_required = bool(
            self.environment == "production"
            and str(queue_doc.get("impact_level") or "").lower() in {"high", "critical"}
        )
        if notation_valid and capability_required:
            verified_token = notation_validation.get("token") or {}
            try:
                get_capability_lease_store().consume_bound(
                    str(verified_token.get("capability_lease_id") or ""),
                    notation_token_id=str(verified_token.get("token_id") or ""),
                    expected_audience="metatron-outbound-gate",
                    authority_request_digest=str(
                        verified_token.get("authority_request_digest") or ""
                    ),
                    action_digest=str(verified_token.get("action_digest") or ""),
                )
                notation_checks["capability_consumed"] = True
            except Exception as exc:
                notation_valid = False
                notation_checks["capability_consumed"] = False
                notation_failure_reason = f"capability_consumption_failed:{type(exc).__name__}"
        resolved_action_id = str(
            payload.get("command_id")
            or queue_doc.get("action_id")
            or related_queue_id
            or decision_id
            or ""
        )
        async def _finalize_harmonic(outcome: str, reason: Optional[str] = None) -> None:
            try:
                await self.finalize_harmonic_state(
                    decision_id=decision_id,
                    queue_id=related_queue_id,
                    actor=str(actor),
                    action_type=action_type,
                    queue_doc=queue_doc,
                    payload=payload,
                    polyphonic_context=polyphonic_context,
                    outcome=outcome,
                    reason=reason,
                )
                await self.finalize_chorus_state(
                    decision_id=decision_id,
                    queue_id=related_queue_id,
                    action_id=resolved_action_id,
                    action_type=action_type,
                    actor=str(actor),
                    outcome=outcome,
                    payload=payload,
                    queue_doc=queue_doc,
                    polyphonic_context=polyphonic_context,
                    reason=reason,
                )
            except Exception:
                logger.debug("Failed to finalize harmonic/chorus state", exc_info=True)
        if not notation_valid:
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": "notation_validation_failed",
                        "notation_valid": False,
                        "notation_failure_reason": notation_failure_reason,
                        "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                        "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", False)),
                        "epoch_match": bool(notation_checks.get("epoch_match", False)),
                        "score_match": bool(notation_checks.get("score_match", False)),
                        "polyphonic_context": polyphonic_context or None,
                        "updated_at": now,
                    }
                },
            )
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "approved_execution_failed",
                        "execution_status": "failed",
                        "notation_valid": False,
                        "notation_failure_reason": notation_failure_reason,
                        "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                        "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", False)),
                        "epoch_match": bool(notation_checks.get("epoch_match", False)),
                        "score_match": bool(notation_checks.get("score_match", False)),
                        "polyphonic_context": polyphonic_context or None,
                        "updated_at": now,
                    }
                },
            )
            await self._mark_notation_execution_outcome(
                notation_ctx.get("token_id"),
                outcome="failed",
            )
            await _finalize_harmonic(
                "failed",
                reason=f"notation_validation_failed:{notation_failure_reason or 'unknown'}",
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="governance_notation_validation_failed",
                    entity_refs=[decision_id, related_queue_id, str(notation_ctx.get("token_id") or "")],
                    payload={
                        "action_type": action_type,
                        "notation_valid": False,
                        "notation_failure_reason": notation_failure_reason,
                        "checks": notation_checks,
                        "polyphonic_context": polyphonic_context if isinstance(polyphonic_context, dict) else None,
                    },
                    trigger_triune=True,
                    source="governance_executor",
                )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=f"notation_validation_failed:{notation_failure_reason or 'unknown'}",
                actor=actor,
                command_id=payload.get("command_id") or queue_doc.get("action_id"),
                command_type=payload.get("command_type") or action_type,
                execution_id=payload.get("command_id") or queue_doc.get("action_id"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[queue_doc.get("subject_id"), related_queue_id, notation_ctx.get("token_id")],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=f"notation_validation_failed:{notation_failure_reason or 'unknown'}",
                command_id=payload.get("command_id") or queue_doc.get("action_id"),
                command_type=payload.get("command_type") or action_type,
                execution_id=payload.get("command_id") or queue_doc.get("action_id"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "failed", "reason": "notation_validation_failed"}

        await self.db.triune_decisions.update_one(
            {"decision_id": decision_id},
            {
                "$set": {
                    "notation_valid": True,
                    "notation_failure_reason": None,
                    "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                    "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", True)),
                    "epoch_match": bool(notation_checks.get("epoch_match", True)),
                    "score_match": bool(notation_checks.get("score_match", True)),
                    "polyphonic_context": polyphonic_context or None,
                    "updated_at": _iso_now(),
                }
            },
        )
        await self.db.triune_outbound_queue.update_one(
            {"queue_id": related_queue_id},
            {
                "$set": {
                    "notation_valid": True,
                    "notation_failure_reason": None,
                    "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                    "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", True)),
                    "epoch_match": bool(notation_checks.get("epoch_match", True)),
                    "score_match": bool(notation_checks.get("score_match", True)),
                    "polyphonic_context": polyphonic_context or None,
                    "updated_at": _iso_now(),
                }
            },
        )

        if action_type == "cross_sector_hardening":
            operation = str(payload.get("operation") or "").strip().lower()
            if operation in {"issue_token", "revoke_token", "revoke_principal_tokens"}:
                result = await self._execute_token_operation(
                    decision=decision,
                    queue_doc=queue_doc,
                    payload=payload,
                    operation=operation,
                    actor=actor,
                )
                await self._mark_notation_execution_outcome(
                    notation_ctx.get("token_id"),
                    outcome="completed" if result.get("outcome") == "executed" else "failed",
                )
                await _finalize_harmonic(
                    result.get("outcome") or "failed",
                    reason=result.get("reason"),
                )
                return result

        if action_type in self.DOMAIN_OPERATION_ACTIONS:
            result = await self._execute_domain_operation(
                decision=decision,
                queue_doc=queue_doc,
                payload=payload,
                actor=actor,
                action_type=action_type,
            )
            await self._mark_notation_execution_outcome(
                notation_ctx.get("token_id"),
                outcome="completed" if result.get("outcome") == "executed" else "failed",
            )
            await _finalize_harmonic(
                result.get("outcome") or "failed",
                reason=result.get("reason"),
            )
            return result

        if action_type == "tool_execution":
            result = await self._execute_tool_runtime_operation(
                decision=decision,
                queue_doc=queue_doc,
                payload=payload,
                actor=actor,
            )
            await self._mark_notation_execution_outcome(
                notation_ctx.get("token_id"),
                outcome="completed" if result.get("outcome") == "executed" else "failed",
            )
            await _finalize_harmonic(
                result.get("outcome") or "failed",
                reason=result.get("reason"),
            )
            return result

        if action_type == "response_execution" and str(payload.get("operation") or "").strip():
            try:
                result = await self._execute_response_operation(
                    decision=decision,
                    queue_doc=queue_doc,
                    payload=payload,
                    actor=actor,
                )
                if result.get("outcome") != "executed":
                    reason = result.get("reason") or "unsupported_response_operation"
                    await self.db.triune_outbound_queue.update_one(
                        {"queue_id": related_queue_id},
                        {
                            "$set": {
                                "status": "approved_no_executor" if result.get("outcome") == "skipped" else "approved_execution_failed",
                                "execution_status": result.get("outcome"),
                                "execution_error": reason if result.get("outcome") != "skipped" else None,
                                "updated_at": _iso_now(),
                            }
                        },
                    )
                    await self.db.triune_decisions.update_one(
                        {"decision_id": decision_id},
                        {
                            "$set": {
                                "execution_status": result.get("outcome"),
                                "execution_error": reason if result.get("outcome") != "skipped" else None,
                                "updated_at": _iso_now(),
                            }
                        },
                    )
                    self._record_execution_audit(
                        decision_id=decision_id,
                        queue_id=related_queue_id,
                        action_type=action_type,
                        outcome=result.get("outcome") or "failed",
                        reason=reason,
                        actor=actor,
                        command_id=str(payload.get("playbook_id") or payload.get("event_id") or related_queue_id),
                        command_type=str(payload.get("operation") or action_type),
                        execution_id=str(payload.get("event_id") or payload.get("playbook_id") or related_queue_id),
                        trace_id=str(payload.get("trace_id") or ""),
                        polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                        targets=[queue_doc.get("subject_id"), related_queue_id, decision_id],
                    )
                    await self._emit_execution_completion_event(
                        decision_id=decision_id,
                        queue_id=related_queue_id,
                        action_type=action_type,
                        outcome=result.get("outcome") or "failed",
                        reason=reason,
                        command_id=str(payload.get("playbook_id") or payload.get("event_id") or related_queue_id),
                        command_type=str(payload.get("operation") or action_type),
                        execution_id=str(payload.get("event_id") or payload.get("playbook_id") or related_queue_id),
                        trace_id=str(payload.get("trace_id") or ""),
                        polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                    )
                await self._mark_notation_execution_outcome(
                    notation_ctx.get("token_id"),
                    outcome="completed" if result.get("outcome") == "executed" else "failed",
                )
                await _finalize_harmonic(
                    result.get("outcome") or "failed",
                    reason=result.get("reason"),
                )
                return result
            except Exception as exc:
                error_reason = str(exc)
                logger.exception("Failed to execute response operation for decision %s: %s", decision_id, exc)
                await self.db.triune_outbound_queue.update_one(
                    {"queue_id": related_queue_id},
                    {
                        "$set": {
                            "status": "approved_execution_failed",
                            "execution_status": "failed",
                            "execution_error": error_reason,
                            "updated_at": _iso_now(),
                        }
                    },
                )
                await self.db.triune_decisions.update_one(
                    {"decision_id": decision_id},
                    {
                        "$set": {
                            "execution_status": "failed",
                            "execution_error": error_reason,
                            "updated_at": _iso_now(),
                        }
                    },
                )
                self._record_execution_audit(
                    decision_id=decision_id,
                    queue_id=related_queue_id,
                    action_type=action_type,
                    outcome="failed",
                    reason=error_reason,
                    actor=actor,
                    command_id=str(payload.get("playbook_id") or payload.get("event_id") or related_queue_id),
                    command_type=str(payload.get("operation") or action_type),
                    execution_id=str(payload.get("event_id") or payload.get("playbook_id") or related_queue_id),
                    trace_id=str(payload.get("trace_id") or ""),
                    polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                    targets=[queue_doc.get("subject_id"), related_queue_id, decision_id],
                )
                await self._emit_execution_completion_event(
                    decision_id=decision_id,
                    queue_id=related_queue_id,
                    action_type=action_type,
                    outcome="failed",
                    reason=error_reason,
                    command_id=str(payload.get("playbook_id") or payload.get("event_id") or related_queue_id),
                    command_type=str(payload.get("operation") or action_type),
                    execution_id=str(payload.get("event_id") or payload.get("playbook_id") or related_queue_id),
                    trace_id=str(payload.get("trace_id") or ""),
                    polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                )
                await self._mark_notation_execution_outcome(notation_ctx.get("token_id"), outcome="failed")
                await _finalize_harmonic("failed", reason=error_reason)
                return {"outcome": "failed", "reason": "response_execution_exception"}

        if action_type not in self.DISPATCHABLE_ACTIONS:
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {"$set": {"status": "approved_no_executor", "updated_at": now}},
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {"$set": {"execution_status": "skipped", "updated_at": now}},
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="governance_executor_handler_missing",
                    entity_refs=[decision_id, related_queue_id, action_type],
                    payload={"action_type": action_type},
                    trigger_triune=False,
                    source="governance_executor",
                )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="skipped",
                reason="unsupported_action_type",
                actor=actor,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[related_queue_id, decision_id, action_type],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="skipped",
                reason="unsupported_action_type",
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            await self._mark_notation_execution_outcome(notation_ctx.get("token_id"), outcome="failed")
            await _finalize_harmonic("skipped", reason="unsupported_action_type")
            return {"outcome": "skipped", "reason": "unsupported_action_type"}

        agent_id = queue_doc.get("subject_id") or payload.get("agent_id")
        command_id = payload.get("command_id") or queue_doc.get("action_id")
        command_type = (
            payload.get("command_type")
            or payload.get("type")
            or payload.get("operation")
            or action_type
        )
        parameters = payload.get("parameters") or payload.get("params") or payload.get("payload") or {}

        if not agent_id or not command_id:
            reason = "missing agent_id or command_id in approved payload"
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": reason,
                        "updated_at": now,
                    }
                },
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=reason,
                actor=actor,
                command_id=command_id,
                command_type=command_type,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[agent_id, command_id, related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=reason,
                command_id=command_id,
                command_type=command_type,
                execution_id=command_id,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            await self._mark_notation_execution_outcome(notation_ctx.get("token_id"), outcome="failed")
            await _finalize_harmonic("failed", reason=reason)
            return {"outcome": "failed", "reason": "missing_agent_or_command"}

        try:
            await self.dispatch.enqueue_command_delivery(
                command_id=command_id,
                agent_id=agent_id,
                command_type=command_type,
                parameters=parameters,
                actor=actor,
                decision_id=decision_id,
                queue_id=related_queue_id,
                metadata={"action_type": action_type, "source": "governance_executor"},
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )

            await self.db.agent_commands.update_many(
                {
                    "$or": [
                        {"decision_id": decision_id},
                        {"command_id": command_id},
                    ]
                },
                {
                    "$set": {
                        "status": "pending",
                        "updated_at": now,
                        "decision_context": {
                            "decision_id": decision_id,
                            "queue_id": related_queue_id,
                            "approved": True,
                            "released_to_execution": True,
                        },
                        "authority_context": {
                            "principal": actor,
                            "capability": command_type,
                            "target": str((parameters or {}).get("target") or agent_id),
                            "token_id": str(payload.get("token_id") or (parameters or {}).get("token_id") or ""),
                            "scope": {"zone_from": "governance", "zone_to": "agent_control_zone"},
                            "contract_version": "endpoint-boundary.v1",
                        },
                        "polyphonic_context": polyphonic_context or None,
                    },
                    "$inc": {"state_version": 1},
                    "$push": {
                        "state_transition_log": {
                            "from_status": "gated_pending_approval",
                            "to_status": "pending",
                            "actor": "system:governance-executor",
                            "reason": "triune decision approved; released to command_queue",
                            "timestamp": now,
                            "metadata": {
                                "decision_id": decision_id,
                                "queue_id": related_queue_id,
                            },
                        }
                    },
                },
            )

            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "released_to_execution",
                        "released_at": now,
                        "updated_at": now,
                        "polyphonic_context": polyphonic_context or None,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "executed",
                        "executed_at": now,
                        "updated_at": now,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    }
                },
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="governance_decision_executed",
                    entity_refs=[decision_id, related_queue_id, agent_id, command_id],
                    payload={
                        "action_type": action_type,
                        "command_type": command_type,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    },
                    trigger_triune=False,
                    source="governance_executor",
                )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="executed",
                actor=actor,
                command_id=command_id,
                command_type=command_type,
                token_id=str(payload.get("token_id") or ""),
                execution_id=command_id,
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[agent_id, command_id, related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="executed",
                command_id=command_id,
                command_type=command_type,
                token_id=str(payload.get("token_id") or ""),
                execution_id=command_id,
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            await self._mark_notation_execution_outcome(notation_ctx.get("token_id"), outcome="completed")
            await _finalize_harmonic("executed")
            return {"outcome": "executed"}
        except Exception as exc:
            logger.exception("Failed to execute approved decision %s: %s", decision_id, exc)
            error_reason = str(exc)
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": error_reason,
                        "updated_at": _iso_now(),
                    }
                },
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=error_reason,
                actor=actor,
                command_id=command_id,
                command_type=command_type,
                token_id=str(payload.get("token_id") or ""),
                execution_id=command_id,
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[agent_id, command_id, related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=error_reason,
                command_id=command_id,
                command_type=command_type,
                token_id=str(payload.get("token_id") or ""),
                execution_id=command_id,
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            await self._mark_notation_execution_outcome(notation_ctx.get("token_id"), outcome="failed")
            await _finalize_harmonic("failed", reason=error_reason)
            return {"outcome": "failed", "reason": "execution_exception"}


    async def _execute_token_operation(
        self,
        *,
        decision: Dict[str, Any],
        queue_doc: Dict[str, Any],
        payload: Dict[str, Any],
        operation: str,
        actor: str,
    ) -> Dict[str, Any]:
        decision_id = decision.get("decision_id")
        related_queue_id = queue_doc.get("queue_id")
        action_type = str(queue_doc.get("action_type") or "").lower()
        now = _iso_now()
        polyphonic_context = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        governance_context = self._governance_context_for_execution(
            decision_id=decision_id,
            queue_id=related_queue_id,
            action_type=action_type,
        )
        try:
            from backend.services.token_broker import token_broker
            if hasattr(token_broker, "set_db"):
                token_broker.set_db(self.db)

            op_result: Dict[str, Any]
            if operation == "issue_token":
                principal = str(payload.get("principal") or "").strip()
                principal_identity = str(payload.get("principal_identity") or "").strip()
                requested_action = str(payload.get("action") or "").strip()
                targets = list(payload.get("targets") or [])
                if not principal or not principal_identity or not requested_action or not targets:
                    raise ValueError(
                        "issue_token requires principal, principal_identity, action, and non-empty targets"
                    )
                token = token_broker.issue_token(
                    principal=principal,
                    principal_identity=principal_identity,
                    action=requested_action,
                    targets=targets,
                    tool_id=payload.get("tool_id"),
                    ttl_seconds=int(payload.get("ttl_seconds") or 300),
                    max_uses=int(payload.get("max_uses") or 1),
                    constraints=payload.get("constraints") or {},
                    governance_context=governance_context,
                    polyphonic_token_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                    future_notation_token_ref=(
                        (polyphonic_context.get("notation_token_id") if isinstance(polyphonic_context, dict) else None)
                    ),
                    issued_by=actor,
                )
                op_result = {
                    "operation": operation,
                    "token_id": token.token_id,
                    "principal": token.principal,
                    "expires_at": token.expires_at,
                    "max_uses": token.max_uses,
                }
            elif operation == "revoke_token":
                token_id = str(payload.get("token_id") or "")
                if not token_id:
                    raise ValueError("Missing token_id for revoke_token")
                token_broker.revoke_token(
                    token_id,
                    governance_context=governance_context,
                    revoked_by=actor,
                )
                op_result = {"operation": operation, "token_id": token_id, "revoked": True}
            elif operation == "revoke_principal_tokens":
                principal = str(payload.get("principal") or "")
                if not principal:
                    raise ValueError("Missing principal for revoke_principal_tokens")
                revoked_count = token_broker.revoke_tokens_for_principal(
                    principal,
                    governance_context=governance_context,
                    revoked_by=actor,
                )
                op_result = {
                    "operation": operation,
                    "principal": principal,
                    "revoked_count": int(revoked_count),
                }
            else:
                raise ValueError(f"Unsupported token operation: {operation}")

            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "released_to_execution",
                        "released_at": now,
                        "updated_at": now,
                        "execution_result": op_result,
                        "polyphonic_context": polyphonic_context or None,
                    }
                },
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "executed",
                        "executed_at": now,
                        "updated_at": now,
                        "execution_result": op_result,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    }
                },
            )
            if emit_world_event is not None:
                await emit_world_event(
                    self.db,
                    event_type="governance_token_operation_executed",
                    entity_refs=[decision_id, related_queue_id, operation],
                    payload={
                        **op_result,
                        "polyphonic_context": polyphonic_context or None,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                    },
                    trigger_triune=False,
                    source="governance_executor",
                )
            resolved_token_id = str(op_result.get("token_id") or "")
            resolved_trace_id = str(payload.get("trace_id") or "")
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="executed",
                actor=actor,
                token_id=resolved_token_id,
                execution_id=resolved_token_id or f"{operation}:{decision_id}",
                trace_id=resolved_trace_id,
                command_type=operation,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[payload.get("principal"), resolved_token_id, related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="executed",
                reason=operation,
                command_type=operation,
                token_id=resolved_token_id,
                execution_id=resolved_token_id or f"{operation}:{decision_id}",
                trace_id=resolved_trace_id,
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "executed", "result": op_result}
        except Exception as exc:
            logger.exception("Failed token operation '%s' for decision %s: %s", operation, decision_id, exc)
            error_reason = str(exc)
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "execution_status": "failed",
                        "execution_error": error_reason,
                        "updated_at": _iso_now(),
                    }
                },
            )
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "approved_execution_failed",
                        "updated_at": _iso_now(),
                    }
                },
            )
            self._record_execution_audit(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=error_reason,
                actor=actor,
                command_type=operation,
                token_id=str(payload.get("token_id") or ""),
                execution_id=str(payload.get("token_id") or f"{operation}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
                targets=[payload.get("principal"), payload.get("token_id"), related_queue_id],
            )
            await self._emit_execution_completion_event(
                decision_id=decision_id,
                queue_id=related_queue_id,
                action_type=action_type,
                outcome="failed",
                reason=error_reason,
                command_type=operation,
                token_id=str(payload.get("token_id") or ""),
                execution_id=str(payload.get("token_id") or f"{operation}:{decision_id}"),
                trace_id=str(payload.get("trace_id") or ""),
                polyphonic_context=polyphonic_context if isinstance(polyphonic_context, dict) else None,
            )
            return {"outcome": "failed", "reason": "token_operation_exception"}


def _executor_enabled() -> bool:
    return os.environ.get("GOVERNANCE_EXECUTOR_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _executor_interval_seconds() -> float:
    try:
        return max(1.0, float(os.environ.get("GOVERNANCE_EXECUTOR_INTERVAL_SECONDS", "5")))
    except Exception:
        return 5.0


async def _executor_loop(db: Any) -> None:
    svc = GovernanceExecutorService(db)
    interval = _executor_interval_seconds()
    logger.info("Governance executor loop started (interval=%ss)", interval)
    try:
        while True:
            try:
                result = await svc.process_approved_decisions(limit=100)
                if result.get("processed", 0) > 0:
                    logger.info("Governance executor cycle: %s", result)
            except Exception:
                logger.exception("Governance executor cycle failed")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Governance executor loop stopped")
        raise


def start_governance_executor(db: Any) -> None:
    global _governance_executor_task
    if not _executor_enabled():
        logger.info("Governance executor disabled by env")
        return
    if _governance_executor_task is None or _governance_executor_task.done():
        _governance_executor_task = asyncio.create_task(_executor_loop(db))


async def stop_governance_executor() -> None:
    global _governance_executor_task
    if _governance_executor_task is None:
        return
    _governance_executor_task.cancel()
    try:
        await _governance_executor_task
    except asyncio.CancelledError:
        pass
    _governance_executor_task = None
