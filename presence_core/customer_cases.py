from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state import read_json, safe, write_json


CASE_SCHEMA = "dio.customer_case.v1"

CASE_STAGES = (
    "NEW_LEAD",
    "QUALIFIED",
    "INTAKE_OPEN",
    "FILES_RECEIVED_QUARANTINED",
    "SCOPE_ASSESSED",
    "PRICE_RECOMMENDED",
    "QUOTE_READY",
    "NEEDS_YOU",
    "INVOICE_DRAFTED",
    "INVOICE_SEND_APPROVAL",
    "INVOICE_SENT",
    "PAYMENT_PENDING",
    "PAYMENT_VERIFIED",
    "WORK_QUEUED",
    "PROCESSING",
    "REVIEW_READY",
    "RELEASE_APPROVAL",
    "DELIVERED",
    "CLOSED",
)
_STAGE_INDEX = {stage: index for index, stage in enumerate(CASE_STAGES)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _case_root(state_root: Path) -> Path:
    return Path(state_root) / "customer_cases"


def _case_path(state_root: Path, case_id: str) -> Path:
    return _case_root(state_root) / "cases" / f"{safe(case_id)}.json"


def _index_path(state_root: Path) -> Path:
    return _case_root(state_root) / "index.json"


def _load_index(state_root: Path) -> dict[str, Any]:
    path = _index_path(state_root)
    if not path.exists():
        return {"schema": "dio.customer_case_index.v1", "conversations": {}}
    try:
        value = read_json(path)
    except Exception:
        return {"schema": "dio.customer_case_index.v1", "conversations": {}}
    if not isinstance(value.get("conversations"), dict):
        value["conversations"] = {}
    return value


def _write_index(state_root: Path, index: dict[str, Any]) -> None:
    write_json(_index_path(state_root), index)


def _stable_case_id(conversation_id: str) -> str:
    digest = hashlib.sha256(str(conversation_id).encode("utf-8")).hexdigest()[:20].upper()
    return f"CASE-{digest}"


def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(target)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _new_case(
    *,
    conversation_id: str,
    channel: str,
    external_user_id: str,
    product_id: str | None,
    contact_email: str | None,
) -> dict[str, Any]:
    timestamp = _now()
    return {
        "schema": CASE_SCHEMA,
        "case_id": _stable_case_id(conversation_id),
        "created_at": timestamp,
        "updated_at": timestamp,
        "channel_origins": [channel],
        "conversation_ids": [conversation_id],
        "customer_identity": {
            "external_user_ids": [str(external_user_id)],
            "state": "unverified",
        },
        "contact_email": contact_email,
        "product_id": product_id,
        "requested_outcome": None,
        "scope": {},
        "attachments": [],
        "commercial": {
            "pricing_mode": None,
            "reference_offer": None,
            "reference_band": None,
            "quote_recommendation": None,
            "quote_reasoning": [],
            "quote_state": "not_prepared",
            "invoice_id": None,
            "invoice_state": "not_created",
            "payment_state": "unverified",
            "payment_evidence_ref": None,
            "currency": None,
            "amount": None,
        },
        "outlook": {
            "message_ids": [],
            "thread_ids": [],
            "draft_ids": [],
            "send_receipt_ids": [],
        },
        "job_links": [],
        "needs_you_ids": [],
        "stage": "NEW_LEAD",
        "stage_history": [
            {
                "stage": "NEW_LEAD",
                "at": timestamp,
                "evidence_ref": f"conversation:{conversation_id}",
            }
        ],
        "last_customer_message_at": timestamp,
        "last_operator_action_at": None,
        "authority_created": False,
    }


def load_case(state_root: Path, case_id: str) -> dict[str, Any] | None:
    path = _case_path(state_root, case_id)
    if not path.exists():
        return None
    try:
        value = read_json(path)
    except Exception:
        return None
    return value if value.get("schema") == CASE_SCHEMA else None


def find_case_for_conversation(state_root: Path, conversation_id: str) -> dict[str, Any] | None:
    index = _load_index(state_root)
    case_id = (index.get("conversations") or {}).get(str(conversation_id))
    if not case_id:
        return None
    return load_case(state_root, str(case_id))


def create_or_attach_case(
    state_root: Path,
    *,
    conversation_id: str,
    channel: str,
    external_user_id: str,
    product_id: str | None = None,
    contact_email: str | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    existing = find_case_for_conversation(state_root, conversation_id)
    if existing is None:
        case = _new_case(
            conversation_id=conversation_id,
            channel=channel,
            external_user_id=external_user_id,
            product_id=product_id,
            contact_email=contact_email,
        )
    else:
        case = deepcopy(existing)
        if channel not in case.setdefault("channel_origins", []):
            case["channel_origins"].append(channel)
        if conversation_id not in case.setdefault("conversation_ids", []):
            case["conversation_ids"].append(conversation_id)
        identities = case.setdefault("customer_identity", {}).setdefault("external_user_ids", [])
        if str(external_user_id) not in identities:
            identities.append(str(external_user_id))
        if contact_email:
            case["contact_email"] = contact_email
        if product_id and not case.get("product_id"):
            case["product_id"] = product_id
        case["updated_at"] = _now()
        case["last_customer_message_at"] = case["updated_at"]

    write_json(_case_path(state_root, case["case_id"]), case)
    index = _load_index(state_root)
    index.setdefault("conversations", {})[conversation_id] = case["case_id"]
    _write_index(state_root, index)
    return case


def update_case(
    state_root: Path,
    case: dict[str, Any],
    *,
    stage: str | None = None,
    patch: dict[str, Any] | None = None,
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    if case.get("schema") != CASE_SCHEMA:
        raise ValueError("unsupported customer case schema")

    updated = _deep_merge(case, patch or {})
    current_stage = str(case.get("stage") or "NEW_LEAD")

    if stage is not None:
        if stage not in _STAGE_INDEX:
            raise ValueError(f"unknown customer case stage: {stage}")
        if current_stage not in _STAGE_INDEX:
            raise ValueError(f"unknown current customer case stage: {current_stage}")
        if _STAGE_INDEX[stage] < _STAGE_INDEX[current_stage]:
            raise ValueError(f"backwards customer case stage transition: {current_stage} -> {stage}")
        if stage != current_stage:
            updated["stage"] = stage
            updated.setdefault("stage_history", []).append(
                {
                    "stage": stage,
                    "at": _now(),
                    "evidence_ref": evidence_ref,
                }
            )

    updated["updated_at"] = _now()
    updated["authority_created"] = False
    write_json(_case_path(Path(state_root), str(updated["case_id"])), updated)
    return updated


def list_cases(state_root: Path, limit: int = 100) -> list[dict[str, Any]]:
    root = _case_root(Path(state_root)) / "cases"
    rows: list[dict[str, Any]] = []
    if root.exists():
        for path in root.glob("*.json"):
            try:
                row = read_json(path)
            except Exception:
                continue
            if row.get("schema") == CASE_SCHEMA:
                rows.append(row)
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("case_id") or "")), reverse=True)
    return rows[: max(0, int(limit))]
