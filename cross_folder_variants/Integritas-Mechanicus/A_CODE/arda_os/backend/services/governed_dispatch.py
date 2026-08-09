import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.arda_trust_contracts import BeastCapabilityLeaseV1, sha256_digest
from backend.services.authority_binding import canonical_action_digest, canonical_target_digest
from backend.services.capability_authority import get_capability_lease_store

try:
    from services.outbound_gate import OutboundGateService
except Exception:
    from backend.services.outbound_gate import OutboundGateService

try:
    from services.polyphonic_governance import get_polyphonic_governance_service
except Exception:
    from backend.services.polyphonic_governance import get_polyphonic_governance_service

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
    from services.vns import vns
except Exception:
    from backend.services.vns import vns

try:
    from services.vns_alerts import vns_alert_service
except Exception:
    from backend.services.vns_alerts import vns_alert_service

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernedDispatchService:
    """Shared command dispatch service for all governed queue writes."""

    def __init__(self, db: Any):
        self.db = db
        self.gate = OutboundGateService(db)
        self.polyphonic = get_polyphonic_governance_service()
        self.epoch_service = get_governance_epoch_service(db)
        self.notation_tokens = get_notation_token_service(db)
        self.harmonic = get_harmonic_engine(db)
        self.environment = str(os.environ.get("ENVIRONMENT") or "local").lower()

    @staticmethod
    def _edge_type_for_action(action_type: str) -> Optional[str]:
        action = str(action_type or "").strip().lower()
        if action in {"agent_command", "swarm_command"}:
            return "agent_command_execution"
        if action in {"mcp_tool_execution", "tool_execution"}:
            return "mcp_tool_invocation"
        return "outbound_gated_action"

    async def queue_gated_agent_command(
        self,
        *,
        action_type: str,
        actor: str,
        agent_id: str,
        command_doc: Dict[str, Any],
        impact_level: str = "high",
        entity_refs: Optional[List[str]] = None,
        requires_triune: bool = True,
        event_type: Optional[str] = None,
        event_payload: Optional[Dict[str, Any]] = None,
        event_entity_refs: Optional[List[str]] = None,
        event_trigger_triune: bool = True,
        route: Optional[str] = None,
        component_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gate and persist a command in agent_commands with uniform metadata."""
        envelope = self.polyphonic.build_action_request_envelope(
            actor_id=str(actor or "unknown"),
            actor_type="service_or_user",
            operation=str(action_type or "agent_command"),
            parameters=(command_doc.get("parameters") or command_doc.get("params") or {}),
            tool_name=command_doc.get("command_type") or command_doc.get("tool"),
            resource_uris=[agent_id] if agent_id else [],
            context_refs={
                "session_id": command_doc.get("session_id"),
                "decision_id": command_doc.get("decision_id"),
                "request_id": command_doc.get("command_id") or command_doc.get("action_id"),
                "trace_id": command_doc.get("trace_id"),
            },
            policy_refs=[str(x) for x in (command_doc.get("policy_refs") or []) if x],
            evidence_hashes=[str(x) for x in (command_doc.get("evidence_hashes") or []) if x],
            target_domain=command_doc.get("target_domain"),
        )
        envelope = self.polyphonic.attach_voice_profile(
            envelope,
            component_id=component_id or "governed_dispatch",
            route=route or "queue_gated_agent_command",
            tool_name=command_doc.get("command_type") or command_doc.get("tool"),
            component_type="orchestration",
        )
        polyphonic_context = self.polyphonic.serialize_polyphonic_context(envelope)
        working_command_doc = dict(command_doc or {})
        dispatch_created_at_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        action_id = (
            working_command_doc.get("command_id")
            or working_command_doc.get("action_id")
            or f"act_{dispatch_created_at_ms}"
        )
        working_command_doc["dispatch_created_at_ms"] = dispatch_created_at_ms
        edge_type = self._edge_type_for_action(action_type)
        if isinstance(polyphonic_context, dict):
            timeline = dict(polyphonic_context.get("harmonic_timeline") or {})
            timeline["dispatch_created_at_ms"] = dispatch_created_at_ms
            polyphonic_context["harmonic_timeline"] = timeline
            polyphonic_context["edge_type"] = edge_type
            polyphonic_context["edge_observation"] = {
                "action_id": str(action_id),
                "edge_type": edge_type,
                "observed_participants": ["dispatch"],
                "observed_sequence": ["dispatch"],
                "timestamps_ms": {"dispatch": float(dispatch_created_at_ms)},
                "audit_events": [],
                "state_events": [],
                "vns_events": [],
                "missing_participants": [],
                "unexpected_participants": [],
            }
        try:
            scope = str(
                working_command_doc.get("target_domain")
                or (working_command_doc.get("parameters") or {}).get("target_domain")
                or "global"
            )
            active_epoch = await self.epoch_service.get_active_epoch(scope=scope)
            world_state_snapshot = working_command_doc.get("world_state_snapshot")
            if active_epoch is not None and isinstance(world_state_snapshot, dict):
                incoming_hash = self.epoch_service.compute_world_state_hash(world_state_snapshot)
                if incoming_hash != active_epoch.world_state_hash:
                    active_epoch = await self.epoch_service.rotate_epoch(
                        reason="world_state_hash_changed",
                        world_state=world_state_snapshot,
                        force=True,
                        scope=scope,
                        genre_mode=active_epoch.genre_mode,
                        strictness_level=active_epoch.strictness_level,
                    )
            if active_epoch is not None:
                active_epoch_doc = (
                    active_epoch.model_dump() if hasattr(active_epoch, "model_dump") else active_epoch.dict()
                )
                voice_profile = (
                    (polyphonic_context.get("voice_profile") or {})
                    if isinstance(polyphonic_context, dict)
                    else {}
                )
                capability_required = bool(
                    self.environment == "production"
                    and str(impact_level or "").lower() in {"high", "critical"}
                )
                if capability_required:
                    raw_lease = working_command_doc.get("capability_lease")
                    if not isinstance(raw_lease, dict):
                        raise PermissionError("BEAST capability lease is required before notation issuance")
                    lease_payload = dict(raw_lease)
                    for field in ("data_scope", "route_scope", "output_scope", "approval_receipt_ids"):
                        lease_payload[field] = tuple(lease_payload.get(field) or ())
                    lease = BeastCapabilityLeaseV1(**lease_payload)
                    lease_store = get_capability_lease_store()
                    lease_store.register(lease)
                    action_digest = canonical_action_digest(
                        action_type=action_type,
                        actor=actor,
                        subject_id=agent_id,
                        impact_level=impact_level,
                        payload=working_command_doc,
                    )
                    target_digest = canonical_target_digest(
                        subject_id=agent_id,
                        payload=working_command_doc,
                    )
                    parameters_digest = sha256_digest(
                        working_command_doc.get("parameters")
                        or working_command_doc.get("params")
                        or {}
                    )
                    notation = await self.notation_tokens.mint_authorized_notation_token(
                        lease=lease,
                        lease_store=lease_store,
                        expected_audience="metatron-outbound-gate",
                        action_digest=action_digest,
                        parameters_digest=parameters_digest,
                        target_digest=target_digest,
                        epoch_id=active_epoch.epoch_id,
                        score_id=active_epoch.score_id,
                        genre_mode=active_epoch.genre_mode,
                        voice_role=str(voice_profile.get("voice_type") or "unknown_voice"),
                        world_state_hash=active_epoch.world_state_hash,
                        entry_window_ms=working_command_doc.get("entry_window_ms") or [0, 300000],
                        sequence_slot=working_command_doc.get("sequence_slot"),
                        required_companions=working_command_doc.get("required_companions") or [],
                        response_class=action_type,
                        ttl_seconds=int(working_command_doc.get("notation_ttl_seconds") or 600),
                    )
                    working_command_doc["capability_lease_id"] = lease.lease_id
                    working_command_doc["authority_request_digest"] = lease.authority_request_digest
                    working_command_doc["canonical_action_digest"] = action_digest
                    working_command_doc["canonical_target_digest"] = target_digest
                    working_command_doc.pop("capability_lease", None)
                else:
                    notation = await self.notation_tokens.mint_notation_token(
                        epoch_id=active_epoch.epoch_id,
                        score_id=active_epoch.score_id,
                        genre_mode=active_epoch.genre_mode,
                        voice_role=str(voice_profile.get("voice_type") or "unknown_voice"),
                        capability_class=str(voice_profile.get("capability_class") or "orchestration"),
                        world_state_hash=active_epoch.world_state_hash,
                        issued_to=str(agent_id or actor or "unknown"),
                        entry_window_ms=working_command_doc.get("entry_window_ms") or [0, 300000],
                        sequence_slot=working_command_doc.get("sequence_slot"),
                        required_companions=working_command_doc.get("required_companions") or [],
                        response_class=action_type,
                        ttl_seconds=int(working_command_doc.get("notation_ttl_seconds") or 600),
                    )
                notation_doc = notation.model_dump() if hasattr(notation, "model_dump") else notation.dict()
                if isinstance(polyphonic_context, dict):
                    polyphonic_context["governance_epoch"] = active_epoch.epoch_id
                    polyphonic_context["score_id"] = active_epoch.score_id
                    polyphonic_context["genre_mode"] = active_epoch.genre_mode
                    polyphonic_context["strictness_level"] = active_epoch.strictness_level
                    polyphonic_context["world_state_hash"] = active_epoch.world_state_hash
                    polyphonic_context["notation_token_id"] = notation.token_id
                    polyphonic_context["notation_token"] = notation_doc
                    polyphonic_context["governance_epoch_descriptor"] = active_epoch_doc
                    edge_observation = dict(polyphonic_context.get("edge_observation") or {})
                    edge_observation["state_events"] = list(
                        dict.fromkeys((edge_observation.get("state_events") or []) + ["state_bound_to_action"])
                    )
                    ts_map = dict(edge_observation.get("timestamps_ms") or {})
                    ts_map.setdefault("world_state_bind", float(dispatch_created_at_ms))
                    edge_observation["timestamps_ms"] = ts_map
                    participants = list(edge_observation.get("observed_participants") or [])
                    if "world_state_bind" not in participants:
                        participants.append("world_state_bind")
                    edge_observation["observed_participants"] = participants
                    sequence = list(edge_observation.get("observed_sequence") or [])
                    if "world_state_bind" not in sequence:
                        sequence.append("world_state_bind")
                    edge_observation["observed_sequence"] = sequence
                    polyphonic_context["edge_observation"] = edge_observation
                working_command_doc["governance_epoch"] = active_epoch.epoch_id
                working_command_doc["score_id"] = active_epoch.score_id
                working_command_doc["genre_mode"] = active_epoch.genre_mode
                working_command_doc["strictness_level"] = active_epoch.strictness_level
                working_command_doc["world_state_hash"] = active_epoch.world_state_hash
                working_command_doc["notation_token_id"] = notation.token_id
                working_command_doc["entry_window_ms"] = notation_doc.get("entry_window_ms")
                working_command_doc["sequence_slot"] = notation_doc.get("sequence_slot")
                working_command_doc["required_companions"] = notation_doc.get("required_companions", [])
                if emit_world_event is not None:
                    try:
                        await emit_world_event(
                            self.db,
                            event_type="state_bound_to_action",
                            entity_refs=[str(agent_id or ""), str(action_id), str(active_epoch.epoch_id)],
                            payload={
                                "action_id": str(action_id),
                                "edge_type": edge_type,
                                "world_state_hash": active_epoch.world_state_hash,
                                "governance_epoch": active_epoch.epoch_id,
                                "score_id": active_epoch.score_id,
                                "genre_mode": active_epoch.genre_mode,
                                "notation_token_id": notation.token_id,
                                "dispatch_created_at_ms": dispatch_created_at_ms,
                            },
                            trigger_triune=False,
                            source="governed_dispatch",
                        )
                    except Exception:
                        pass
        except Exception:
            # Keep dispatch non-breaking: gate layer will mark notation invalid if required.
            pass
        try:
            target_domain = str(
                working_command_doc.get("target_domain")
                or (working_command_doc.get("parameters") or {}).get("target_domain")
                or "global"
            )
            harmonic_observation = self.harmonic.score_observation(
                actor_id=str(actor or "unknown"),
                tool_name=str(
                    working_command_doc.get("command_type")
                    or working_command_doc.get("tool")
                    or action_type
                ),
                target_domain=target_domain,
                environment=self.environment,
                stage="dispatch",
                timestamp_ms=float(dispatch_created_at_ms),
                operation=str(action_type),
                context={
                    "agent_id": agent_id,
                    "command_id": working_command_doc.get("command_id"),
                },
            )
            if isinstance(polyphonic_context, dict):
                polyphonic_context["timing_features"] = harmonic_observation.get("timing_features")
                polyphonic_context["baseline_ref"] = harmonic_observation.get("baseline_ref")
                polyphonic_context["harmonic_state"] = harmonic_observation.get("harmonic_state")
                history = list(polyphonic_context.get("harmonic_history") or [])
                history.append(
                    {
                        "stage": "dispatch",
                        "timestamp_ms": dispatch_created_at_ms,
                        "harmonic_state": harmonic_observation.get("harmonic_state"),
                    }
                )
                polyphonic_context["harmonic_history"] = history[-20:]
                timeline = dict(polyphonic_context.get("harmonic_timeline") or {})
                timeline.setdefault("dispatch_created_at_ms", dispatch_created_at_ms)
                polyphonic_context["harmonic_timeline"] = timeline
            working_command_doc["timing_features_at_dispatch"] = harmonic_observation.get("timing_features")
            working_command_doc["harmonic_state_at_dispatch"] = harmonic_observation.get("harmonic_state")
            working_command_doc["baseline_ref"] = harmonic_observation.get("baseline_ref")
            if hasattr(vns, "update_domain_pulse"):
                pulse_state = vns.update_domain_pulse(
                    domain=target_domain,
                    timing_features=harmonic_observation.get("timing_features") or {},
                    harmonic_state=harmonic_observation.get("harmonic_state") or {},
                    timestamp_ms=dispatch_created_at_ms,
                )
                if (
                    pulse_state
                    and float(pulse_state.get("pulse_stability_index") or 1.0) < 0.45
                    and hasattr(vns_alert_service, "alert_pulse_instability_by_domain")
                ):
                    vns_alert_service.alert_pulse_instability_by_domain(pulse_state)
            timing_features = harmonic_observation.get("timing_features") or {}
            harmonic_state = harmonic_observation.get("harmonic_state") or {}
            if (
                float(timing_features.get("drift_norm") or 0.0) >= 0.6
                and hasattr(vns_alert_service, "alert_harmonic_drift_detected")
            ):
                vns_alert_service.alert_harmonic_drift_detected(
                    {
                        "scope": target_domain,
                        "action_type": action_type,
                        "actor": actor,
                        "drift_norm": timing_features.get("drift_norm"),
                        "confidence": harmonic_state.get("confidence"),
                    }
                )
            if (
                float(timing_features.get("burstiness") or 0.0) >= 0.6
                and hasattr(vns_alert_service, "alert_burst_cluster_detected")
            ):
                vns_alert_service.alert_burst_cluster_detected(
                    {
                        "scope": target_domain,
                        "action_type": action_type,
                        "burstiness": timing_features.get("burstiness"),
                        "discord_score": harmonic_state.get("discord_score"),
                    }
                )
        except Exception:
            pass
        if polyphonic_context:
            working_command_doc["polyphonic_context"] = polyphonic_context
        queued = await self.gate.gate_action(
            action_type=action_type,
            actor=actor,
            payload=working_command_doc,
            impact_level=impact_level,
            subject_id=agent_id,
            entity_refs=entity_refs or [agent_id, working_command_doc.get("command_id")],
            requires_triune=requires_triune,
            polyphonic_context=polyphonic_context,
        )

        now = _iso_now()
        persisted = dict(working_command_doc)
        persisted.setdefault("agent_id", agent_id)
        persisted.setdefault("created_at", now)
        persisted["updated_at"] = now
        gate_status = str(queued.get("status") or "queued").strip().lower()
        if gate_status == "denied":
            persisted_status = "rejected"
        elif gate_status == "approved":
            persisted_status = "approved"
        else:
            persisted_status = "gated_pending_approval"
        persisted["status"] = persisted_status
        persisted.setdefault("state_version", 1)
        state_transition_log = list(persisted.get("state_transition_log") or [])
        if not state_transition_log:
            state_transition_log = [
                {
                    "from_status": None,
                    "to_status": "gated_pending_approval",
                    "actor": actor or "unknown",
                    "reason": "queued for triune approval",
                    "timestamp": now,
                }
            ]
        if persisted_status != "gated_pending_approval":
            previous_status = state_transition_log[-1].get("to_status") if state_transition_log else None
            if previous_status != persisted_status:
                state_transition_log.append(
                    {
                        "from_status": previous_status,
                        "to_status": persisted_status,
                        "actor": actor or "unknown",
                        "reason": queued.get("reason") or queued.get("notes") or f"gate returned {gate_status}",
                        "timestamp": now,
                        "metadata": {
                            "gate_status": gate_status,
                            "queue_id": queued.get("queue_id"),
                            "decision_id": queued.get("decision_id"),
                        },
                    }
                )
        persisted["state_transition_log"] = state_transition_log
        persisted["queue_id"] = queued.get("queue_id")
        persisted["decision_id"] = queued.get("decision_id")
        persisted["decision_context"] = {
            "decision_id": queued.get("decision_id"),
            "queue_id": queued.get("queue_id"),
            "approved": persisted_status == "approved",
            "released_to_execution": persisted_status == "approved",
        }
        persisted["execution_status"] = queued.get("execution_status")
        if queued.get("reason"):
            persisted["gate_reason"] = queued.get("reason")
        if queued.get("notes"):
            persisted["gate_notes"] = queued.get("notes")
        if persisted_status == "approved":
            persisted["approved_at"] = now
        elif persisted_status == "rejected":
            persisted["rejected_at"] = now
        if "authority_context" not in persisted:
            persisted["authority_context"] = {
                "principal": actor,
                "capability": persisted.get("command_type"),
                "token_id": (persisted.get("parameters") or {}).get("token_id"),
                "scope": {"zone_from": "governance", "zone_to": "agent_control_zone"},
                "contract_version": "endpoint-boundary.v1",
            }
        persisted["gate"] = {
            "queue_id": queued.get("queue_id"),
            "decision_id": queued.get("decision_id"),
            "action_id": queued.get("action_id"),
        }
        if polyphonic_context:
            persisted["polyphonic_context"] = polyphonic_context

        await self.db.agent_commands.insert_one(persisted)

        if event_type and emit_world_event is not None:
            outbound_event_payload = dict(event_payload or {})
            if polyphonic_context and "polyphonic_context" not in outbound_event_payload:
                outbound_event_payload["polyphonic_context"] = polyphonic_context
                outbound_event_payload["voice_type"] = (
                    (polyphonic_context.get("voice_profile") or {}).get("voice_type")
                    if isinstance(polyphonic_context, dict)
                    else None
                )
                outbound_event_payload["capability_class"] = (
                    (polyphonic_context.get("voice_profile") or {}).get("capability_class")
                    if isinstance(polyphonic_context, dict)
                    else None
                )
            await emit_world_event(
                self.db,
                event_type=event_type,
                entity_refs=event_entity_refs or [agent_id, persisted.get("command_id")],
                payload=outbound_event_payload,
                trigger_triune=event_trigger_triune,
            )

        return {"queued": queued, "command": persisted}

    async def enqueue_command_delivery(
        self,
        *,
        command_id: str,
        agent_id: str,
        command_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        actor: str = "system",
        status: str = "pending",
        decision_id: Optional[str] = None,
        queue_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        polyphonic_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Insert into command_queue via one shared helper."""
        now = _iso_now()
        queue_doc: Dict[str, Any] = {
            "command_id": command_id,
            "agent_id": agent_id,
            "command_type": command_type,
            "parameters": parameters or {},
            "status": status,
            "created_at": now,
            "created_by": actor,
        }
        if decision_id:
            queue_doc["decision_id"] = decision_id
        if queue_id:
            queue_doc["outbound_queue_id"] = queue_id
        if metadata:
            queue_doc["metadata"] = metadata
        if polyphonic_context:
            queue_doc["polyphonic_context"] = polyphonic_context

        await self.db.command_queue.insert_one(queue_doc)

        if emit_world_event is not None:
            await emit_world_event(
                self.db,
                event_type="command_delivery_queued",
                entity_refs=[agent_id, command_id],
                payload={
                    "command_type": command_type,
                    "decision_id": decision_id,
                    "queue_id": queue_id,
                    "polyphonic_context": polyphonic_context or None,
                    "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if isinstance(polyphonic_context, dict) else None),
                    "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if isinstance(polyphonic_context, dict) else None),
                },
                trigger_triune=False,
                source="governed_dispatch",
            )

        return queue_doc
