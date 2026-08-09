"""Canonical digests shared by BEAST authority, notation, gate, and executor."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from backend.services.arda_trust_contracts import sha256_digest


def canonical_action_payload(
    *,
    action_type: str,
    actor: str,
    subject_id: Optional[str],
    impact_level: str,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    parameters = payload.get("parameters") or payload.get("params") or {}
    return {
        "action_type": str(action_type or "").strip().lower(),
        "actor": str(actor or ""),
        "subject_id": str(subject_id or ""),
        "impact_level": str(impact_level or "").strip().lower(),
        "action_id": str(payload.get("command_id") or payload.get("action_id") or ""),
        "operation": str(payload.get("command_type") or payload.get("tool") or ""),
        "parameters": parameters,
        "target_domain": str(payload.get("target_domain") or parameters.get("target_domain") or ""),
        "route": str(payload.get("route") or ""),
        "mission_id": str(payload.get("mission_id") or ""),
        "workspace_id": str(payload.get("workspace_id") or ""),
    }


def canonical_action_digest(**kwargs: Any) -> str:
    return sha256_digest(canonical_action_payload(**kwargs))


def canonical_target_digest(*, subject_id: Optional[str], payload: Mapping[str, Any]) -> str:
    parameters = payload.get("parameters") or payload.get("params") or {}
    return sha256_digest(
        {
            "subject_id": str(subject_id or ""),
            "target_domain": str(payload.get("target_domain") or parameters.get("target_domain") or ""),
            "route": str(payload.get("route") or ""),
        }
    )
