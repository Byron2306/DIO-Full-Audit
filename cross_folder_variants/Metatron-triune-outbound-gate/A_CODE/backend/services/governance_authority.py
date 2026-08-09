from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from backend.services.harmonic_policy import get_harmonic_policy_service
from backend.services.governance_epoch import get_governance_epoch_service
from backend.services.notation_token import get_notation_token_service
from backend.services.chorus_engine import get_chorus_engine
from backend.services.world_events import emit_world_event
from backend.services.harmonic_explainability import build_harmonic_explanation


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


class GovernanceDecisionAuthority:
    """Canonical transition service for triune decision authority state."""

    def __init__(self, db: Any):
        self.db = db
        self.epoch_service = get_governance_epoch_service(db)
        self.notation_tokens = get_notation_token_service(db)
        self.chorus = get_chorus_engine(db)
        self.harmonic_policy = get_harmonic_policy_service()

    @staticmethod
    def interpret_harmonic_band(harmonic_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return get_harmonic_policy_service().interpret_harmonic_band(harmonic_state)

    def apply_harmonic_obligations(
        self,
        *,
        harmonic_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self.harmonic_policy.apply_harmonic_obligations(harmonic_state=harmonic_state)

    @staticmethod
    def _updated_deception_provenance(
        *,
        provenance: Optional[Dict[str, Any]],
        decision_status: str,
        queue_status: str,
        notation_valid: bool,
        world_state_hash_match: bool,
        actor: str,
        reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(provenance, dict) or not provenance:
            return None

        updated = dict(provenance)
        revocation_conditions = list(dict.fromkeys(updated.get("revocation_conditions") or []))
        revocation_triggers = list(updated.get("revocation_triggers") or [])
        revocation_reason = reason

        corroboration = updated.get("independent_corroboration")
        if not isinstance(corroboration, dict):
            corroboration = {}
        corroboration_satisfied = bool(corroboration.get("satisfied", True))

        if not world_state_hash_match and "world_state_hash_drift" in revocation_conditions:
            revocation_triggers.append("world_state_hash_drift")
            revocation_reason = revocation_reason or "world_state_hash_drift"
        if not notation_valid and "notation_token_revoked" in revocation_conditions:
            revocation_triggers.append("notation_token_revoked")
            revocation_reason = revocation_reason or "notation_validation_failed"
        if not corroboration_satisfied and "corroboration_degraded" in revocation_conditions:
            revocation_triggers.append("corroboration_degraded")
            revocation_reason = revocation_reason or "corroboration_degraded"

        updated["triune_decision_status"] = decision_status
        updated["outbound_queue_status"] = queue_status
        updated["governance_actor"] = actor
        updated["revocation_triggers"] = list(dict.fromkeys(revocation_triggers))
        updated["revocation_triggered"] = len(updated["revocation_triggers"]) > 0
        updated["revocation_reason"] = revocation_reason
        return updated

    async def _validate_notation_for_approval(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        related_queue_id = decision.get("related_queue_id")
        if not related_queue_id:
            return {"valid": True, "checks": {}, "reasons": [], "queue_doc": None}
        queue_doc = await self.db.triune_outbound_queue.find_one({"queue_id": related_queue_id}, {"_id": 0})
        if not queue_doc:
            return {"valid": False, "checks": {"queue_present": False}, "reasons": ["related_queue_missing"], "queue_doc": None}
        payload = queue_doc.get("payload") or {}
        polyphonic = queue_doc.get("polyphonic_context") or payload.get("polyphonic_context") or {}
        token = (
            (polyphonic.get("notation_token") if isinstance(polyphonic, dict) else None)
            or (polyphonic.get("notation_token_id") if isinstance(polyphonic, dict) else None)
            or queue_doc.get("notation_token_id")
            or payload.get("notation_token_id")
        )
        scope = str(payload.get("target_domain") or (payload.get("parameters") or {}).get("target_domain") or "global")
        active_epoch = await self.epoch_service.get_active_epoch(scope=scope)
        active_epoch_doc = (
            active_epoch.model_dump() if hasattr(active_epoch, "model_dump") else active_epoch.dict()
        ) if active_epoch is not None else None
        validation = await self.notation_tokens.validate_notation_token(
            token=token,
            active_epoch=active_epoch_doc,
            world_state_hash=active_epoch.world_state_hash if active_epoch is not None else None,
            context={
                "baseline_time": queue_doc.get("created_at"),
                "observed_slot": payload.get("sequence_slot"),
                "observed_companions": payload.get("observed_companions") or [],
                **self.notation_tokens.resolve_enforcement_profile(
                    genre_mode=(
                        (active_epoch.genre_mode if active_epoch is not None else None)
                        or (polyphonic.get("genre_mode") if isinstance(polyphonic, dict) else None)
                        or queue_doc.get("genre_mode")
                    ),
                    strictness_level=(
                        (active_epoch.strictness_level if active_epoch is not None else None)
                        or (polyphonic.get("strictness_level") if isinstance(polyphonic, dict) else None)
                        or queue_doc.get("strictness_level")
                    ),
                ),
            },
        )
        validation["queue_doc"] = queue_doc
        return validation

    async def approve_decision(
        self,
        *,
        decision_id: str,
        actor: str,
        notes: Optional[str] = None,
        execution_status: str = "pending_executor",
        source: str = "governance_authority",
    ) -> Dict[str, Any]:
        decision = await self.db.triune_decisions.find_one({"decision_id": decision_id}, {"_id": 0})
        if not decision:
            return {"found": False, "decision_id": decision_id}

        now = _iso_now()
        related_queue_id = decision.get("related_queue_id")
        notation_validation = await self._validate_notation_for_approval(decision)
        notation_valid = bool(notation_validation.get("valid"))
        notation_checks = notation_validation.get("checks") or {}
        notation_reason = ";".join(notation_validation.get("reasons") or []) or None
        queue_doc = notation_validation.get("queue_doc") or {}
        queue_polyphonic = (
            queue_doc.get("polyphonic_context")
            or (queue_doc.get("payload") or {}).get("polyphonic_context")
            or {}
        )
        if not isinstance(queue_polyphonic, dict):
            queue_polyphonic = {}
        approval_ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        edge_observation = dict(queue_polyphonic.get("edge_observation") or {})
        if edge_observation:
            participants = list(edge_observation.get("observed_participants") or [])
            for participant in ["policy_bind", "governance_authority"]:
                if participant not in participants:
                    participants.append(participant)
            edge_observation["observed_participants"] = participants
            sequence = list(edge_observation.get("observed_sequence") or [])
            for step in ["policy_bind", "governance_authority"]:
                if step not in sequence:
                    sequence.append(step)
            edge_observation["observed_sequence"] = sequence
            timestamps_ms = dict(edge_observation.get("timestamps_ms") or {})
            timestamps_ms.setdefault("policy_bind", float(approval_ts_ms))
            timestamps_ms["governance_authority"] = float(approval_ts_ms)
            edge_observation["timestamps_ms"] = timestamps_ms
            state_events = list(edge_observation.get("state_events") or [])
            for event_name in ["policy_bind_completed", "governance_authorized"]:
                if event_name not in state_events:
                    state_events.append(event_name)
            edge_observation["state_events"] = state_events
            queue_polyphonic["edge_observation"] = edge_observation
            try:
                edge_type = str(queue_polyphonic.get("edge_type") or "agent_command_execution")
                spec_model = self.chorus.load_edge_chorus_spec(
                    edge_type=edge_type,
                    genre_mode=str(queue_polyphonic.get("genre_mode") or queue_doc.get("genre_mode") or ""),
                )
                observation_model = self.chorus.collect_edge_participants(
                    action_id=str(queue_doc.get("action_id") or related_queue_id or decision_id),
                    context=edge_observation,
                )
                chorus_state_model = self.chorus.assemble_chorus_state(
                    spec=spec_model,
                    observation=observation_model,
                )
                queue_polyphonic["chorus_spec"] = _model_dump(spec_model)
                queue_polyphonic["chorus_state"] = _model_dump(chorus_state_model)
            except Exception:
                pass
        harmonic_state = (
            (queue_polyphonic.get("harmonic_state") if isinstance(queue_polyphonic, dict) else None)
            or queue_doc.get("harmonic_state_at_gate")
            or queue_doc.get("harmonic_state")
        )
        harmonic_modulation = self.apply_harmonic_obligations(harmonic_state=harmonic_state)
        harmonic_guidance = harmonic_modulation.get("harmonic_guidance") or {}
        harmonic_obligations = harmonic_modulation.get("harmonic_obligations") or []
        harmonic_enforcement = harmonic_modulation.get("harmonic_enforcement") or {}
        release_not_before = harmonic_modulation.get("release_not_before")
        harmonic_explanation = build_harmonic_explanation(
            scope_key=str(((queue_polyphonic.get("baseline_ref") or {}) if isinstance(queue_polyphonic, dict) else {}).get("baseline_id") or ""),
            stage="governance_authority",
            timing_features=(queue_polyphonic.get("timing_features") if isinstance(queue_polyphonic, dict) else None),
            harmonic_state=harmonic_state,
            baseline_ref=(queue_polyphonic.get("baseline_ref") if isinstance(queue_polyphonic, dict) else None),
            harmonic_guidance=harmonic_guidance,
            harmonic_obligations=harmonic_obligations,
            release_not_before=release_not_before,
        )
        deception_provenance = self._updated_deception_provenance(
            provenance=queue_doc.get("deception_provenance") or queue_polyphonic.get("deception_provenance"),
            decision_status="denied" if related_queue_id and not notation_valid else "approved",
            queue_status="denied" if related_queue_id and not notation_valid else "approved",
            notation_valid=notation_valid,
            world_state_hash_match=bool(notation_checks.get("world_state_hash_match", notation_valid)),
            actor=actor,
            reason=notation_reason,
        )
        if deception_provenance:
            queue_polyphonic["deception_provenance"] = deception_provenance
        if related_queue_id and not notation_valid:
            polyphonic_ctx = queue_doc.get("polyphonic_context") or (queue_doc.get("payload") or {}).get("polyphonic_context") or {}
            notation_token_id = (
                (polyphonic_ctx.get("notation_token_id") if isinstance(polyphonic_ctx, dict) else None)
                or queue_doc.get("notation_token_id")
                or (queue_doc.get("payload") or {}).get("notation_token_id")
            )
            await self.db.triune_decisions.update_one(
                {"decision_id": decision_id},
                {
                    "$set": {
                        "status": "denied",
                        "denied_by": actor,
                        "denied_at": now,
                        "updated_at": now,
                        "execution_status": "skipped",
                        "denial_reason": notation_reason or "notation_validation_failed",
                        "notation_valid": False,
                        "notation_failure_reason": notation_reason,
                        "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", False)),
                        "epoch_match": bool(notation_checks.get("epoch_match", False)),
                        "score_match": bool(notation_checks.get("score_match", False)),
                        "harmonic_state": harmonic_state,
                        "harmonic_band": harmonic_guidance.get("band"),
                        "harmonic_obligations": harmonic_obligations,
                        "harmonic_enforcement": harmonic_enforcement,
                        "harmonic_explanation": harmonic_explanation,
                        "deception_provenance": deception_provenance,
                        "polyphonic_context": queue_polyphonic or None,
                    }
                },
            )
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "denied",
                        "denied_by": actor,
                        "denied_at": now,
                        "updated_at": now,
                        "execution_status": "skipped",
                        "notation_valid": False,
                        "notation_failure_reason": notation_reason,
                        "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", False)),
                        "epoch_match": bool(notation_checks.get("epoch_match", False)),
                        "score_match": bool(notation_checks.get("score_match", False)),
                        "harmonic_state": harmonic_state,
                        "harmonic_band": harmonic_guidance.get("band"),
                        "harmonic_obligations": harmonic_obligations,
                        "harmonic_enforcement": harmonic_enforcement,
                        "harmonic_explanation": harmonic_explanation,
                        "deception_provenance": deception_provenance,
                        "polyphonic_context": queue_polyphonic or None,
                    }
                },
            )
            if notation_token_id:
                await self.notation_tokens.revoke_notation_token(
                    str(notation_token_id),
                    reason=notation_reason or "approval_notation_validation_failed",
                )
            if emit_world_event is not None:
                try:
                    await emit_world_event(
                        self.db,
                        event_type="governance_decision_denied",
                        entity_refs=[decision_id, related_queue_id],
                        payload={
                            "actor": actor,
                            "reason": notation_reason or "notation_validation_failed",
                            "source": source,
                            "notation_valid": False,
                            "notation_failure_reason": notation_reason,
                            "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", False)),
                            "epoch_match": bool(notation_checks.get("epoch_match", False)),
                            "score_match": bool(notation_checks.get("score_match", False)),
                            "harmonic_band": harmonic_guidance.get("band"),
                            "harmonic_obligations": harmonic_obligations,
                            "harmonic_explanation": harmonic_explanation,
                            "deception_provenance": deception_provenance,
                        },
                        trigger_triune=False,
                        source=source,
                    )
                except Exception:
                    pass
            return {
                "found": True,
                "decision_id": decision_id,
                "related_queue_id": related_queue_id,
                "execution_status": "skipped",
                "denied": True,
                "notation_valid": False,
                "notation_failure_reason": notation_reason,
            }
        resolved_execution_status = execution_status if related_queue_id else "policy_only"
        await self.db.triune_decisions.update_one(
            {"decision_id": decision_id},
            {
                "$set": {
                    "status": "approved",
                    "approved_by": actor,
                    "approved_at": now,
                    "updated_at": now,
                    "execution_status": resolved_execution_status,
                    "approval_notes": notes,
                    "notation_valid": notation_valid,
                    "notation_failure_reason": notation_reason,
                    "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", True)),
                    "epoch_match": bool(notation_checks.get("epoch_match", True)),
                    "score_match": bool(notation_checks.get("score_match", True)),
                    "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                    "harmonic_state": harmonic_state,
                    "harmonic_band": harmonic_guidance.get("band"),
                    "harmonic_obligations": harmonic_obligations,
                    "harmonic_enforcement": harmonic_enforcement,
                    "harmonic_release_not_before": release_not_before,
                    "harmonic_explanation": harmonic_explanation,
                    "deception_provenance": deception_provenance,
                    "polyphonic_context": queue_polyphonic or None,
                }
            },
        )
        if related_queue_id:
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "approved",
                        "approved_by": actor,
                        "approved_at": now,
                        "updated_at": now,
                        "execution_status": resolved_execution_status,
                        "notation_valid": notation_valid,
                        "notation_failure_reason": notation_reason,
                        "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", True)),
                        "epoch_match": bool(notation_checks.get("epoch_match", True)),
                        "score_match": bool(notation_checks.get("score_match", True)),
                        "notation_enforcement_profile": notation_validation.get("enforcement_profile"),
                        "harmonic_state": harmonic_state,
                        "harmonic_band": harmonic_guidance.get("band"),
                        "harmonic_obligations": harmonic_obligations,
                        "harmonic_enforcement": harmonic_enforcement,
                        "harmonic_release_not_before": release_not_before,
                        "harmonic_explanation": harmonic_explanation,
                        "deception_provenance": deception_provenance,
                        "polyphonic_context": queue_polyphonic or None,
                    }
                },
            )

        # Mirror policy state when this decision originated from policy evaluation.
        await self.db.policy_decisions.update_one(
            {"decision_id": decision_id},
            {
                "$set": {
                    "status": "approved",
                    "approved_by": actor,
                    "approved_at": now,
                    "updated_at": now,
                    "approval_notes": notes,
                }
            },
        )

        if emit_world_event is not None:
            try:
                await emit_world_event(
                    self.db,
                    event_type="governance_decision_approved",
                    entity_refs=[decision_id, related_queue_id],
                    payload={
                        "actor": actor,
                        "notes": notes,
                        "source": source,
                        "notation_valid": notation_valid,
                        "notation_failure_reason": notation_reason,
                        "world_state_hash_match": bool(notation_checks.get("world_state_hash_match", True)),
                        "epoch_match": bool(notation_checks.get("epoch_match", True)),
                        "score_match": bool(notation_checks.get("score_match", True)),
                        "harmonic_band": harmonic_guidance.get("band"),
                        "harmonic_obligations": harmonic_obligations,
                        "harmonic_enforcement": harmonic_enforcement,
                        "harmonic_release_not_before": release_not_before,
                        "harmonic_explanation": harmonic_explanation,
                        "deception_provenance": deception_provenance,
                    },
                    trigger_triune=False,
                    source=source,
                )
                await emit_world_event(
                    self.db,
                    event_type="governance_authorized",
                    entity_refs=[decision_id, related_queue_id],
                    payload={
                        "actor": actor,
                        "action_id": (queue_doc or {}).get("action_id"),
                        "edge_type": ((queue_polyphonic or {}).get("edge_type") or (queue_doc or {}).get("edge_type")),
                        "approved_at_ms": approval_ts_ms,
                        "policy_resolution_class": "governance_authorized",
                        "polyphonic_context": queue_polyphonic or None,
                    },
                    trigger_triune=False,
                    source=source,
                )
            except Exception:
                pass

        return {
            "found": True,
            "decision_id": decision_id,
            "related_queue_id": related_queue_id,
            "execution_status": resolved_execution_status,
            "harmonic_band": harmonic_guidance.get("band"),
            "harmonic_obligations": harmonic_obligations,
            "harmonic_enforcement": harmonic_enforcement,
            "harmonic_release_not_before": release_not_before,
            "harmonic_explanation": harmonic_explanation,
        }

    async def deny_decision(
        self,
        *,
        decision_id: str,
        actor: str,
        reason: Optional[str] = None,
        source: str = "governance_authority",
    ) -> Dict[str, Any]:
        decision = await self.db.triune_decisions.find_one({"decision_id": decision_id}, {"_id": 0})
        if not decision:
            return {"found": False, "decision_id": decision_id}

        now = _iso_now()
        related_queue_id = decision.get("related_queue_id")
        queue_doc = None
        if related_queue_id:
            queue_doc = await self.db.triune_outbound_queue.find_one({"queue_id": related_queue_id}, {"_id": 0})
        queue_polyphonic = (
            (queue_doc or {}).get("polyphonic_context")
            or (((queue_doc or {}).get("payload") or {}).get("polyphonic_context"))
            or {}
        )
        if not isinstance(queue_polyphonic, dict):
            queue_polyphonic = {}
        deception_provenance = self._updated_deception_provenance(
            provenance=(queue_doc or {}).get("deception_provenance") or queue_polyphonic.get("deception_provenance"),
            decision_status="denied",
            queue_status="denied" if related_queue_id else "policy_only",
            notation_valid=False,
            world_state_hash_match=False if "world_state_hash" in str(reason or "").lower() else True,
            actor=actor,
            reason=reason,
        )
        if deception_provenance:
            queue_polyphonic["deception_provenance"] = deception_provenance
        await self.db.triune_decisions.update_one(
            {"decision_id": decision_id},
            {
                "$set": {
                    "status": "denied",
                    "denied_by": actor,
                    "denied_at": now,
                    "updated_at": now,
                    "execution_status": "skipped",
                    "denial_reason": reason,
                    "deception_provenance": deception_provenance,
                }
            },
        )
        if related_queue_id:
            await self.db.triune_outbound_queue.update_one(
                {"queue_id": related_queue_id},
                {
                    "$set": {
                        "status": "denied",
                        "denied_by": actor,
                        "denied_at": now,
                        "updated_at": now,
                        "execution_status": "skipped",
                        "deception_provenance": deception_provenance,
                        "polyphonic_context": queue_polyphonic or None,
                    }
                },
            )
            if queue_doc:
                polyphonic_ctx = queue_doc.get("polyphonic_context") or (queue_doc.get("payload") or {}).get("polyphonic_context") or {}
                notation_token_id = (
                    (polyphonic_ctx.get("notation_token_id") if isinstance(polyphonic_ctx, dict) else None)
                    or queue_doc.get("notation_token_id")
                    or (queue_doc.get("payload") or {}).get("notation_token_id")
                )
                if notation_token_id:
                    await self.notation_tokens.revoke_notation_token(
                        str(notation_token_id),
                        reason=reason or "decision_denied",
                    )

        await self.db.policy_decisions.update_one(
            {"decision_id": decision_id},
            {
                "$set": {
                    "status": "denied",
                    "denied_by": actor,
                    "denied_at": now,
                    "updated_at": now,
                    "denial_reason": reason,
                }
            },
        )

        if emit_world_event is not None:
            try:
                await emit_world_event(
                    self.db,
                    event_type="governance_decision_denied",
                    entity_refs=[decision_id, related_queue_id],
                    payload={
                        "actor": actor,
                        "reason": reason,
                        "source": source,
                        "deception_provenance": deception_provenance,
                    },
                    trigger_triune=False,
                    source=source,
                )
            except Exception:
                pass

        return {
            "found": True,
            "decision_id": decision_id,
            "related_queue_id": related_queue_id,
            "execution_status": "skipped",
        }
