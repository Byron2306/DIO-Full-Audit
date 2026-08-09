from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
import asyncio
import logging

try:
    from websocket_service import realtime_ws, WSMessage
except Exception:
    try:
        from backend.websocket_service import realtime_ws, WSMessage
    except Exception:
        realtime_ws = None
        WSMessage = None


logger = logging.getLogger(__name__)


def _load_triune_orchestrator():
    try:
        from backend.services.triune_orchestrator import TriuneOrchestrator
        return TriuneOrchestrator
    except Exception:
        return None


EVENT_CLASS_PASSIVE_FACT = "passive_fact"
EVENT_CLASS_LOCAL_REFLEX = "local_reflex"
EVENT_CLASS_STRATEGIC_RECOMPUTE = "strategic_recompute"
EVENT_CLASS_ACTION_CRITICAL_RECOMPUTE = "action_critical_recompute"

_ACTION_CRITICAL_MARKERS = (
    "outbound_gate",
    "boundary_crossing",
    "gated",
    "approval",
    "command_created",
    "command_queued",
    "tool_execution",
    "quarantine_",
    "cross_sector",
    "response_block",
    "response_unblock",
    "governance_epoch",
    "notation_token",
    "world_state_hash_changed",
    "edge_opened",
    "state_bound_to_action",
    "governance_authorized",
    "executor_started",
    "executor_completed",
    "audit_closed",
    "edge_settled",
    "edge_chorus_fractured",
    "policy_bind_completed",
    "policy_obligations_emitted",
    "policy_resolution_class",
    # AI adversary action-critical events (force Triune recompute + governance veto eligible)
    "ai_logic_budget_trap",
    "ai_token_revoked",
)

_STRATEGIC_MARKERS = (
    "deception_interaction",
    "beacon",
    "campaign",
    "threat",
    "detection",
    "risk",
    "triune_periodic_tick",
    "genre_mode_changed",
    "score_id_changed",
    # AI adversary strategic events (trigger Triune analysis)
    "ai_adversary_",
    "agenticity_",
    "logic_budget_",
)

_LOCAL_REFLEX_MARKERS = (
    "heartbeat",
    "telemetry",
    "acknowledged",
    "status_update",
    "settings_updated",
)


def classify_event_type(event_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Classify event into persistence class independent of trigger policy."""
    et = str(event_type or "").lower().strip()
    payload = payload or {}

    if any(marker in et for marker in _ACTION_CRITICAL_MARKERS):
        return EVENT_CLASS_ACTION_CRITICAL_RECOMPUTE
    if any(marker in et for marker in _STRATEGIC_MARKERS):
        return EVENT_CLASS_STRATEGIC_RECOMPUTE
    if any(marker in et for marker in _LOCAL_REFLEX_MARKERS):
        return EVENT_CLASS_LOCAL_REFLEX

    if payload.get("impact_level") in {"high", "critical"}:
        return EVENT_CLASS_ACTION_CRITICAL_RECOMPUTE
    if payload.get("notation_valid") is False:
        return EVENT_CLASS_ACTION_CRITICAL_RECOMPUTE
    if payload.get("risk_delta") or payload.get("predicted_next_sectors"):
        return EVENT_CLASS_STRATEGIC_RECOMPUTE

    # Keep default behavior close to historic "trigger by default".
    return EVENT_CLASS_STRATEGIC_RECOMPUTE


def should_trigger_triune(event_class: str) -> bool:
    return event_class in {
        EVENT_CLASS_STRATEGIC_RECOMPUTE,
        EVENT_CLASS_ACTION_CRITICAL_RECOMPUTE,
    }


async def emit_world_event(
    db: Any,
    event_type: str,
    entity_refs: Optional[List[str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    trigger_triune: Optional[bool] = None,
    source: Optional[str] = None,
    event_class: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist a canonical world event and optionally execute Triune recomputation.

    This helper keeps routers/tasks from hand-rolling event persistence and
    direct Metatron/Michael/Loki wiring.
    """

    entity_refs = entity_refs or []
    payload = payload or {}

    resolved_event_class = event_class or classify_event_type(event_type, payload)
    resolved_trigger_triune = should_trigger_triune(resolved_event_class) if trigger_triune is None else bool(trigger_triune)

    event = {
        "id": f"wevt-{uuid.uuid4().hex[:12]}",
        "type": event_type,
        "event_class": resolved_event_class,
        "entity_refs": entity_refs,
        "payload": payload,
        "source": source or "world_event_emitter",
        "triune_triggered": resolved_trigger_triune,
        "created": datetime.now(timezone.utc).isoformat(),
    }

    if db is not None and hasattr(db, "world_events"):
        try:
            await db.world_events.insert_one(event)
        except Exception:
            # best-effort persistence
            pass

    triune_bundle = None
    if resolved_trigger_triune:
        triune_orchestrator_cls = _load_triune_orchestrator()
        if triune_orchestrator_cls is None:
            logger.warning("world_events: triune orchestrator unavailable; skipping recompute for %s", event_type)
        else:
            orchestrator = triune_orchestrator_cls(db)
            triune_bundle = await orchestrator.handle_world_change(
                event_type=event_type,
                entity_ids=entity_refs,
                context={
                    "source": source or "world_event_emitter",
                    "payload": payload,
                    "event_class": resolved_event_class,
                    "polyphonic_context": payload.get("polyphonic_context") if isinstance(payload, dict) else None,
                    "score_id": payload.get("score_id") if isinstance(payload, dict) else None,
                    "genre_mode": payload.get("genre_mode") if isinstance(payload, dict) else None,
                    "governance_epoch": payload.get("governance_epoch") if isinstance(payload, dict) else None,
                    "notation_token_id": payload.get("notation_token_id") if isinstance(payload, dict) else None,
                    "world_state_hash": payload.get("world_state_hash") if isinstance(payload, dict) else None,
                },
            )

    # 3. Broadcast to real-time dashboards
    if realtime_ws is not None:
        try:
            # Create a background task for broadcasting to avoid blocking the caller
            msg = WSMessage(
                type="world_event",
                payload=event,
                source=source or "world_event_emitter"
            )
            asyncio.create_task(realtime_ws.broadcast_to_dashboards(msg))
        except Exception as e:
            # We don't want telemetry failures to crash the main logic
            logger.error(f"Failed to broadcast world event: {e}")

    return {"event": event, "triune": triune_bundle}
