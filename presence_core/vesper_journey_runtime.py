from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from .customer_cases import load_case
from .journey_core import (
    available_actions,
    bind_surface_to_case,
    create_journey_case,
    find_case_for_surface,
    record_journey_event,
)


VESPER_JOURNEY_VIEW_SCHEMA = "dio.vesper_journey_view.v1"
VESPER_JOURNEY_RESOLUTION_SCHEMA = "dio.vesper_journey_resolution.v1"
VESPER_ACTION_DECISION_SCHEMA = "dio.vesper_journey_action_decision.v1"
VESPER_ACTION_EXECUTION_SCHEMA = "dio.vesper_journey_action_execution.v1"
VESPER_REENTRY_SCHEMA = "dio.vesper_journey_reentry.v1"

Handler = Callable[..., Any]

# This is actor policy, not product routing. The same map applies to every product.
# Vesper is the conversational mediator and therefore never appears as an authority
# class. It presents customer choices and system/operator state; canonical actors
# remain customer, operator, or system.
_ACTION_ACTORS: dict[str, tuple[str, ...]] = {
    "QUALIFY": ("system", "operator"),
    "OPEN_INTAKE": ("customer", "operator"),
    "RECEIVE_FILES": ("customer", "system", "operator"),
    "ASSESS_SCOPE": ("customer", "system", "operator"),
    "RECOMMEND_PRICE": ("system", "operator"),
    "PREPARE_QUOTE": ("customer", "system", "operator"),
    "REQUEST_OPERATOR": ("customer", "system"),
    "DRAFT_INVOICE": ("system", "operator"),
    "AWAIT_SETTLEMENT": ("customer", "system", "operator"),
    "RESUME_AUTHORISED_PATH": ("operator", "system"),
    "REQUEST_INVOICE_SEND_APPROVAL": ("operator", "system"),
    "SEND_INVOICE": ("system",),
    "VERIFY_SETTLEMENT": ("system", "operator"),
    "QUEUE_WORK": ("system", "operator"),
    "START_PROCESSING": ("system",),
    "RECORD_FULFILMENT_RESULT": ("system",),
    "REQUEST_RELEASE_APPROVAL": ("operator", "system"),
    "DELIVER": ("system",),
    "CLOSE": ("customer", "operator", "system"),
}


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _required(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _action_ref(case_id: str, stage: str, action_id: str) -> str:
    basis = {
        "case_id": case_id,
        "stage": stage,
        "action_id": action_id,
        "schema": "dio.vesper_journey_action_ref.v1",
    }
    return "JACT-" + _canonical_hash(basis)[:24].upper()


def _bounded_facts(case: dict[str, Any]) -> dict[str, Any]:
    intake = deepcopy((case.get("intake") or {}).get("requirement") or {})
    scope = deepcopy(case.get("scope_receipt") or {})
    commercial = deepcopy(case.get("commercial") or {})
    quote_result = deepcopy(commercial.get("quote_result") or {})
    quote = deepcopy(quote_result.get("quote") or {})
    settlement = deepcopy(case.get("settlement") or {})
    fulfilment = deepcopy(case.get("fulfilment") or {})
    manifest = deepcopy(fulfilment.get("deliverable_manifest") or {})
    receipt = deepcopy(fulfilment.get("delivery_receipt") or {})

    return {
        "intake": {
            "missing_input_ids": list(intake.get("missing_input_ids") or []),
            "invalid_input_ids": list(intake.get("invalid_input_ids") or []),
            "scope_sufficient": bool(intake.get("scope_sufficient")),
        },
        "scope": {
            "state": scope.get("state"),
            "scope_receipt_sha256": scope.get("scope_receipt_sha256"),
        },
        "quote": {
            "quote_id": quote.get("quote_id") or commercial.get("quote_id"),
            "amount": quote.get("amount") or commercial.get("amount"),
            "currency": quote.get("currency") or commercial.get("currency"),
            "presentation_authority": bool(quote.get("presentation_authority")),
            "quote_state": commercial.get("quote_state"),
        },
        "settlement": {
            "settlement_class": settlement.get("settlement_class"),
            "fulfilment_eligible": bool(settlement.get("fulfilment_eligible")),
            "settlement_receipt_sha256": settlement.get("settlement_receipt_sha256"),
        },
        "fulfilment": {
            "state": fulfilment.get("state"),
            "fulfilment_result_sha256": (fulfilment.get("result") or {}).get(
                "fulfilment_result_sha256"
            ),
        },
        "deliverables": {
            "manifest_id": manifest.get("manifest_id"),
            "manifest_sha256": manifest.get("manifest_sha256"),
            "artifact_count": manifest.get("artifact_count"),
            "release_state": manifest.get("release_state"),
        },
        "delivery": {
            "delivery_receipt_id": receipt.get("delivery_receipt_id"),
            "delivery_receipt_sha256": receipt.get("delivery_receipt_sha256"),
            "channel": receipt.get("channel"),
            "sent": bool(receipt.get("sent")),
        },
    }


def build_vesper_journey_view(case: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise ValueError("canonical customer case is required")
    case_id = _required(case.get("case_id"), "case_id")
    stage = _required(case.get("stage") or "NEW_LEAD", "stage")
    canonical_actions = available_actions(case)

    actions = []
    for action_id in canonical_actions:
        actors = list(_ACTION_ACTORS.get(action_id) or ())
        if not actors:
            raise ValueError(f"Vesper actor policy missing for journey action: {action_id}")
        actions.append(
            {
                "action_id": action_id,
                "action_ref": _action_ref(case_id, stage, action_id),
                "actor_classes": actors,
                "state_mutation_authority": False,
                "financial_authority": False,
                "release_authority": False,
            }
        )

    view = {
        "schema": VESPER_JOURNEY_VIEW_SCHEMA,
        "case_id": case_id,
        "product_id": case.get("product_id"),
        "stage": stage,
        "actions": actions,
        "facts": _bounded_facts(case),
        "raw_text_is_action": False,
        "product_specific_runtime_branch": False,
        "authority_created": False,
        "external_send_authority": False,
        "financial_commitment_authority": False,
        "fulfilment_release_authority": False,
    }
    view["view_sha256"] = _canonical_hash(view)
    return view


def resolve_vesper_journey(
    state_root: Path,
    *,
    surface: str,
    external_user_id: str,
    conversation_id: str | None = None,
    case_id: str | None = None,
    product_id: str | None = None,
    preferred_return: bool = False,
) -> dict[str, Any]:
    state_root = Path(state_root)
    surface = _required(surface, "surface").lower()
    external_user_id = _required(external_user_id, "external_user_id")
    conversation_id = str(conversation_id or "").strip() or None
    requested_case_id = str(case_id or "").strip() or None

    bound = find_case_for_surface(
        state_root,
        surface=surface,
        external_user_id=external_user_id,
        conversation_id=conversation_id,
    )
    created = False

    if bound is not None:
        if requested_case_id and str(bound.get("case_id")) != requested_case_id:
            raise ValueError("surface is already bound to a different customer case")
        case = bound
        binding = next(
            (
                deepcopy(row)
                for row in case.get("surface_bindings") or []
                if row.get("surface") == surface
                and row.get("external_user_id") == external_user_id
                and (row.get("conversation_id") or None) == conversation_id
            ),
            None,
        )
    elif requested_case_id:
        case = load_case(state_root, requested_case_id)
        if case is None:
            raise ValueError(f"customer case not found: {requested_case_id}")
        binding = bind_surface_to_case(
            state_root,
            requested_case_id,
            surface=surface,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            preferred_return=preferred_return,
        )
        case = load_case(state_root, requested_case_id)
    else:
        case = create_journey_case(state_root, product_id=product_id)
        created = True
        binding = bind_surface_to_case(
            state_root,
            str(case["case_id"]),
            surface=surface,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            preferred_return=preferred_return,
        )
        case = load_case(state_root, str(case["case_id"]))

    if case is None:
        raise ValueError("canonical customer case could not be resolved")

    return {
        "schema": VESPER_JOURNEY_RESOLUTION_SCHEMA,
        "case_id": str(case["case_id"]),
        "created": created,
        "binding": deepcopy(binding),
        "view": build_vesper_journey_view(case),
        "identity_inferred": False,
        "authority_created": False,
    }


def validate_vesper_action(
    state_root: Path,
    case_id: str,
    *,
    action: str,
    action_ref: str,
    actor_class: str,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    action = str(action or "").strip().upper()
    actor_class = str(actor_class or "").strip().lower()
    action_ref = str(action_ref or "").strip()
    view = build_vesper_journey_view(case)
    row = next((item for item in view["actions"] if item["action_id"] == action), None)

    if row is None:
        decision, reason = "REFUSE", "action_not_currently_available"
    elif action_ref != row["action_ref"]:
        decision, reason = "REFUSE", "stale_or_invalid_action_ref"
    elif actor_class not in set(row["actor_classes"]):
        decision, reason = "REFUSE", "actor_not_permitted"
    else:
        decision, reason = "ALLOW", "canonical_action_current_and_actor_permitted"

    return {
        "schema": VESPER_ACTION_DECISION_SCHEMA,
        "decision": decision,
        "reason": reason,
        "case_id": str(case["case_id"]),
        "stage": str(case.get("stage") or ""),
        "action": action,
        "action_ref": action_ref,
        "actor_class": actor_class,
        "available_actions": [item["action_id"] for item in view["actions"]],
        "authority_created": False,
        "external_effects": False,
    }


def execute_vesper_action(
    state_root: Path,
    case_id: str,
    *,
    action: str,
    action_ref: str,
    actor_class: str,
    handlers: Mapping[str, Handler],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    action = str(action or "").strip().upper()
    decision = validate_vesper_action(
        state_root,
        str(case_id),
        action=action,
        action_ref=action_ref,
        actor_class=actor_class,
    )
    if decision["decision"] != "ALLOW":
        raise ValueError(str(decision["reason"]))

    handler = handlers.get(action) if isinstance(handlers, Mapping) else None
    if not callable(handler):
        raise ValueError(f"journey action handler not registered: {action}")

    before_case = load_case(state_root, str(case_id))
    if before_case is None:
        raise ValueError(f"customer case not found: {case_id}")
    before_view = build_vesper_journey_view(before_case)

    # The handler may call the typed Phase 2-5 contracts, but its return object is
    # never considered journey truth. Only the canonical case store is authoritative.
    handler(
        state_root=state_root,
        case=deepcopy(before_case),
        payload=deepcopy(payload or {}),
    )

    after_case = load_case(state_root, str(case_id))
    if after_case is None:
        raise ValueError("journey action handler removed the canonical customer case")

    event = record_journey_event(
        state_root,
        str(case_id),
        event_type="VESPER_ACTION_EXECUTED",
        payload={
            "action": action,
            "actor_class": str(actor_class or "").strip().lower(),
            "before_stage": before_view["stage"],
            "after_stage": str(after_case.get("stage") or ""),
            "action_ref": action_ref,
        },
    )
    canonical_after = load_case(state_root, str(case_id))
    if canonical_after is None:
        raise ValueError("canonical customer case missing after journey event")

    return {
        "schema": VESPER_ACTION_EXECUTION_SCHEMA,
        "case_id": str(case_id),
        "action": action,
        "actor_class": str(actor_class or "").strip().lower(),
        "decision": decision,
        "before": before_view,
        "after": build_vesper_journey_view(canonical_after),
        "journey_event_id": event["event_id"],
        "handler_result_trusted": False,
        "authority_created": False,
    }


def record_vesper_async_reentry(
    state_root: Path,
    case_id: str,
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    event = record_journey_event(
        state_root,
        str(case_id),
        event_type=event_type,
        payload=deepcopy(payload or {}),
    )
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    return {
        "schema": VESPER_REENTRY_SCHEMA,
        "case_id": str(case_id),
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "return_route": deepcopy(event.get("return_route")),
        "view": build_vesper_journey_view(case),
        "authority_created": False,
        "external_send_authority": False,
    }
