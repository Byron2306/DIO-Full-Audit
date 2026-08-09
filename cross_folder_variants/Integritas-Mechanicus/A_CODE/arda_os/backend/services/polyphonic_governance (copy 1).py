from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from schemas.polyphonic_models import (
        ActionContextRefs,
        ActionIntent,
        ActionRequestEnvelope,
        PolyphonicContext,
        VoiceProfile,
    )
except Exception:
    from backend.schemas.polyphonic_models import (
        ActionContextRefs,
        ActionIntent,
        ActionRequestEnvelope,
        PolyphonicContext,
        VoiceProfile,
    )

try:
    from services.voice_registry import VoiceRegistry, get_voice_registry
except Exception:
    from backend.services.voice_registry import VoiceRegistry, get_voice_registry


def _model_dump(model: Any) -> Dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolyphonicGovernanceService:
    """Phase 1 normalization/enrichment bridge for action envelopes."""

    def __init__(self, voice_registry: Optional[VoiceRegistry] = None):
        self.voice_registry = voice_registry or get_voice_registry()

    def build_action_request_envelope(
        self,
        *,
        actor_id: str,
        actor_type: str,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        resource_uris: Optional[List[str]] = None,
        context_refs: Optional[Dict[str, Any]] = None,
        policy_refs: Optional[List[str]] = None,
        evidence_hashes: Optional[List[str]] = None,
        target_domain: Optional[str] = None,
    ) -> ActionRequestEnvelope:
        refs = ActionContextRefs(**(context_refs or {}))
        intent = ActionIntent(
            tool_name=tool_name,
            operation=operation,
            parameters=dict(parameters or {}),
            resource_uris=list(resource_uris or []),
            target_domain=target_domain,
        )
        envelope = ActionRequestEnvelope(
            actor_id=str(actor_id or "unknown"),
            actor_type=str(actor_type or "unknown"),
            intent=intent,
            context_refs=refs,
            policy_refs=[str(x) for x in (policy_refs or []) if x],
            evidence_hashes=[str(x) for x in (evidence_hashes or []) if x],
            polyphonic_context=PolyphonicContext(),
            created_at=_utc_now(),
        )
        return envelope

    def attach_voice_profile(
        self,
        envelope: ActionRequestEnvelope,
        *,
        component_id: Optional[str] = None,
        route: Optional[str] = None,
        tool_name: Optional[str] = None,
        component_type: Optional[str] = None,
    ) -> ActionRequestEnvelope:
        resolved_tool = tool_name or (envelope.intent.tool_name if envelope and envelope.intent else None)
        voice_profile = self.voice_registry.resolve_voice_for_action(
            tool_name=resolved_tool,
            component_id=component_id,
            route=route,
            component_type=component_type,
        )
        if envelope.polyphonic_context is None:
            envelope.polyphonic_context = PolyphonicContext()
        envelope.polyphonic_context.voice_profile = voice_profile
        return envelope

    def serialize_polyphonic_context(self, envelope: ActionRequestEnvelope) -> Dict[str, Any]:
        context = envelope.polyphonic_context if envelope else None
        if context is None:
            return {}
        return _model_dump(context)

    def extract_polyphonic_context(self, doc: Optional[Dict[str, Any]]) -> Optional[PolyphonicContext]:
        if not doc:
            return None
        raw_context = doc.get("polyphonic_context")
        if not raw_context:
            return None
        if isinstance(raw_context, PolyphonicContext):
            return raw_context
        try:
            return PolyphonicContext(**raw_context)
        except Exception:
            return None

    def to_storage_dict(self, envelope: ActionRequestEnvelope) -> Dict[str, Any]:
        return _model_dump(envelope)


_polyphonic_governance_singleton: Optional[PolyphonicGovernanceService] = None


def get_polyphonic_governance_service(
    voice_registry: Optional[VoiceRegistry] = None,
) -> PolyphonicGovernanceService:
    global _polyphonic_governance_singleton
    if _polyphonic_governance_singleton is None:
        _polyphonic_governance_singleton = PolyphonicGovernanceService(
            voice_registry=voice_registry or get_voice_registry()
        )
    return _polyphonic_governance_singleton
