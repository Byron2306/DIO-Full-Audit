from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from .customer_cases import (
    CASE_SCHEMA,
    _case_path,
    _load_index,
    _new_case,
    _now,
    _write_index,
    load_case,
    update_case,
)
from .state import write_json


JOURNEY_BINDING_SCHEMA = "dio.customer_journey_surface_binding.v1"
JOURNEY_EVENT_SCHEMA = "dio.customer_journey_event.v1"

# Phase 1 is deliberately stricter than the legacy monotonic stage helper.
# These transitions describe customer-lifecycle truth, not every internal organ step.
_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "NEW_LEAD": ("QUALIFIED", "INTAKE_OPEN"),
    "QUALIFIED": ("INTAKE_OPEN",),
    "INTAKE_OPEN": ("FILES_RECEIVED_QUARANTINED", "SCOPE_ASSESSED"),
    "FILES_RECEIVED_QUARANTINED": ("SCOPE_ASSESSED",),
    "SCOPE_ASSESSED": ("PRICE_RECOMMENDED", "QUOTE_READY", "NEEDS_YOU"),
    "PRICE_RECOMMENDED": ("QUOTE_READY", "NEEDS_YOU"),
    "QUOTE_READY": ("NEEDS_YOU", "INVOICE_DRAFTED", "PAYMENT_PENDING"),
    "NEEDS_YOU": ("QUOTE_READY", "INVOICE_DRAFTED", "RELEASE_APPROVAL"),
    "INVOICE_DRAFTED": ("INVOICE_SEND_APPROVAL",),
    "INVOICE_SEND_APPROVAL": ("INVOICE_SENT",),
    "INVOICE_SENT": ("PAYMENT_PENDING",),
    "PAYMENT_PENDING": ("PAYMENT_VERIFIED",),
    "PAYMENT_VERIFIED": ("WORK_QUEUED",),
    "WORK_QUEUED": ("PROCESSING",),
    "PROCESSING": ("REVIEW_READY",),
    "REVIEW_READY": ("RELEASE_APPROVAL",),
    "RELEASE_APPROVAL": ("DELIVERED",),
    "DELIVERED": ("CLOSED",),
    "CLOSED": (),
}

_AVAILABLE_ACTIONS: dict[str, tuple[str, ...]] = {
    "NEW_LEAD": ("QUALIFY", "OPEN_INTAKE"),
    "QUALIFIED": ("OPEN_INTAKE",),
    "INTAKE_OPEN": ("RECEIVE_FILES", "ASSESS_SCOPE"),
    "FILES_RECEIVED_QUARANTINED": ("ASSESS_SCOPE",),
    "SCOPE_ASSESSED": ("RECOMMEND_PRICE", "PREPARE_QUOTE", "REQUEST_OPERATOR"),
    "PRICE_RECOMMENDED": ("PREPARE_QUOTE", "REQUEST_OPERATOR"),
    "QUOTE_READY": ("DRAFT_INVOICE", "AWAIT_SETTLEMENT", "REQUEST_OPERATOR"),
    "NEEDS_YOU": ("RESUME_AUTHORISED_PATH",),
    "INVOICE_DRAFTED": ("REQUEST_INVOICE_SEND_APPROVAL",),
    "INVOICE_SEND_APPROVAL": ("SEND_INVOICE",),
    "INVOICE_SENT": ("AWAIT_SETTLEMENT",),
    "PAYMENT_PENDING": ("VERIFY_SETTLEMENT",),
    "PAYMENT_VERIFIED": ("QUEUE_WORK",),
    "WORK_QUEUED": ("START_PROCESSING",),
    "PROCESSING": ("RECORD_FULFILMENT_RESULT",),
    "REVIEW_READY": ("REQUEST_RELEASE_APPROVAL",),
    "RELEASE_APPROVAL": ("DELIVER",),
    "DELIVERED": ("CLOSE",),
    "CLOSED": (),
}


def _surface_key(surface: str, external_user_id: str, conversation_id: str | None) -> str:
    surface = str(surface or "").strip().lower()
    external_user_id = str(external_user_id or "").strip()
    conversation_id = str(conversation_id or "").strip()
    if not surface:
        raise ValueError("surface is required")
    if not external_user_id:
        raise ValueError("external_user_id is required")
    return "|".join((surface, external_user_id, conversation_id))


def _binding_id(surface: str, external_user_id: str, conversation_id: str | None) -> str:
    material = _surface_key(surface, external_user_id, conversation_id)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20].upper()
    return f"BIND-{digest}"


def _new_journey_case_id() -> str:
    # Identity creation is intentionally independent from any channel or conversation.
    # Once created, every subsequent projection is deterministic over this canonical ID.
    return f"CASE-{uuid.uuid4().hex[:20].upper()}"


def create_journey_case(
    state_root: Path,
    *,
    product_id: str | None = None,
    contact_email: str | None = None,
    customer_id: str | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case_id = _new_journey_case_id()

    # Reuse the established customer-case shape and storage so Phase 1 extends the
    # organism rather than creating a parallel commercial ledger. The seed below is
    # internal only and is never a surface identity.
    seed = f"journey-core:{case_id}"
    case = _new_case(
        conversation_id=seed,
        channel="journey_core",
        external_user_id=f"unbound:{case_id}",
        product_id=product_id,
        contact_email=contact_email,
        customer_id=customer_id,
    )
    case["case_id"] = case_id
    case["channel_origins"] = []
    case["conversation_ids"] = []
    case["customer_identity"]["external_user_ids"] = []
    case["surface_bindings"] = []
    case["preferred_return_binding_id"] = None
    case["journey_events"] = []
    case["journey_core"] = {
        "surface_neutral": True,
        "available_actions": available_actions(case),
    }
    case["stage_history"] = [
        {
            "stage": "NEW_LEAD",
            "at": case["created_at"],
            "evidence_ref": "journey_core:case_created",
        }
    ]

    write_json(_case_path(state_root, case_id), case)
    return case


def bind_surface_to_case(
    state_root: Path,
    case_id: str,
    *,
    surface: str,
    external_user_id: str,
    conversation_id: str | None = None,
    preferred_return: bool = False,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    surface = str(surface or "").strip().lower()
    external_user_id = str(external_user_id or "").strip()
    conversation_id = str(conversation_id or "").strip() or None
    key = _surface_key(surface, external_user_id, conversation_id)
    binding_id = _binding_id(surface, external_user_id, conversation_id)

    index = _load_index(state_root)
    surface_index = index.setdefault("surface_bindings", {})
    existing_case_id = surface_index.get(key)
    if existing_case_id and str(existing_case_id) != str(case_id):
        raise ValueError("surface binding already belongs to another customer case")

    bindings = list(case.get("surface_bindings") or [])
    existing_binding = next(
        (row for row in bindings if str(row.get("binding_id")) == binding_id),
        None,
    )
    timestamp = _now()
    binding = {
        "schema": JOURNEY_BINDING_SCHEMA,
        "binding_id": binding_id,
        "surface": surface,
        "external_user_id": external_user_id,
        "conversation_id": conversation_id,
        "bound_at": existing_binding.get("bound_at") if existing_binding else timestamp,
        "updated_at": timestamp,
    }

    if existing_binding is None:
        bindings.append(binding)
    else:
        bindings = [binding if row.get("binding_id") == binding_id else row for row in bindings]

    if surface not in case.setdefault("channel_origins", []):
        case["channel_origins"].append(surface)
    if conversation_id and conversation_id not in case.setdefault("conversation_ids", []):
        case["conversation_ids"].append(conversation_id)
    identities = case.setdefault("customer_identity", {}).setdefault("external_user_ids", [])
    if external_user_id not in identities:
        identities.append(external_user_id)

    case["surface_bindings"] = bindings
    if preferred_return or not case.get("preferred_return_binding_id"):
        case["preferred_return_binding_id"] = binding_id
    case["updated_at"] = timestamp
    case["last_customer_message_at"] = timestamp
    case["authority_created"] = False
    case.setdefault("journey_core", {})["surface_neutral"] = True
    case["journey_core"]["available_actions"] = available_actions(case)

    write_json(_case_path(state_root, str(case_id)), case)
    surface_index[key] = str(case_id)
    if conversation_id:
        index.setdefault("conversations", {})[conversation_id] = str(case_id)
    _write_index(state_root, index)
    return binding


def find_case_for_surface(
    state_root: Path,
    *,
    surface: str,
    external_user_id: str,
    conversation_id: str | None = None,
) -> dict[str, Any] | None:
    index = _load_index(Path(state_root))
    key = _surface_key(surface, external_user_id, conversation_id)
    case_id = (index.get("surface_bindings") or {}).get(key)
    if not case_id:
        return None
    return load_case(Path(state_root), str(case_id))


def available_actions(case: dict[str, Any]) -> list[str]:
    if case.get("schema") != CASE_SCHEMA:
        raise ValueError("unsupported customer case schema")
    stage = str(case.get("stage") or "NEW_LEAD")
    if stage not in _AVAILABLE_ACTIONS:
        raise ValueError(f"unknown customer case stage: {stage}")
    return list(_AVAILABLE_ACTIONS[stage])


def transition_case(
    state_root: Path,
    case_id: str,
    stage: str,
    *,
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    current = str(case.get("stage") or "NEW_LEAD")
    target = str(stage or "").strip()
    if target == current:
        refreshed = deepcopy(case)
        refreshed.setdefault("journey_core", {})["available_actions"] = available_actions(refreshed)
        return refreshed
    if target not in _ALLOWED_TRANSITIONS.get(current, ()):
        raise ValueError(f"invalid customer journey transition: {current} -> {target}")

    updated = update_case(
        state_root,
        case,
        stage=target,
        evidence_ref=evidence_ref,
    )
    updated.setdefault("journey_core", {})["surface_neutral"] = True
    updated["journey_core"]["available_actions"] = available_actions(updated)
    write_json(_case_path(state_root, str(case_id)), updated)
    return updated


def _return_route(case: dict[str, Any]) -> dict[str, Any] | None:
    bindings = list(case.get("surface_bindings") or [])
    if not bindings:
        return None
    preferred = str(case.get("preferred_return_binding_id") or "")
    binding = next((row for row in bindings if str(row.get("binding_id")) == preferred), None)
    binding = binding or bindings[-1]
    return {
        "binding_id": binding.get("binding_id"),
        "surface": binding.get("surface"),
        "external_user_id": binding.get("external_user_id"),
        "conversation_id": binding.get("conversation_id"),
    }


def record_journey_event(
    state_root: Path,
    case_id: str,
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    event_type = str(event_type or "").strip().upper()
    if not event_type:
        raise ValueError("event_type is required")
    payload = deepcopy(payload or {})
    sequence = len(case.get("journey_events") or []) + 1
    event_material = json.dumps(
        {
            "case_id": str(case_id),
            "event_type": event_type,
            "payload": payload,
            "sequence": sequence,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(event_material.encode("utf-8")).hexdigest()[:20].upper()
    event = {
        "schema": JOURNEY_EVENT_SCHEMA,
        "event_id": f"JEVT-{digest}",
        "case_id": str(case_id),
        "event_type": event_type,
        "sequence": sequence,
        "recorded_at": _now(),
        "payload": payload,
        "return_route": _return_route(case),
        "authority_created": False,
    }

    events = list(case.get("journey_events") or [])
    events.append(event)
    case["journey_events"] = events
    case["updated_at"] = event["recorded_at"]
    case["authority_created"] = False
    case.setdefault("journey_core", {})["surface_neutral"] = True
    case["journey_core"]["available_actions"] = available_actions(case)
    write_json(_case_path(state_root, str(case_id)), case)
    return event
