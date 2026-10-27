"""Immutable, content-addressed custody for Microsoft Graph mailbox changes."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_message(message: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "id", "@odata.etag", "conversationId", "internetMessageId", "subject",
        "receivedDateTime", "from", "toRecipients", "body", "bodyPreview",
        "hasAttachments", "isRead", "@removed",
    )
    return {key: message.get(key) for key in fields if key in message}


def _safe_attachments(attachments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    fields = ("id", "name", "contentType", "size", "sha256", "isInline", "capture_state")
    return [{key: attachment.get(key) for key in fields if key in attachment} for attachment in attachments]


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical(value) + b"\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def capture_message_version(
    state_root: Path,
    message: Mapping[str, Any],
    attachments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Persist a Graph change once; retain each changed version and every tombstone."""
    provider_message_id = str(message.get("id") or "")
    if not provider_message_id:
        raise ValueError("Outlook capture requires Graph message id.")
    root = Path(state_root).expanduser().resolve() / "outlook_captures"
    index_path = root / "provider_index.json"
    index = _read_json(index_path, {"schema": "dio.outlook_capture_index.v1", "providers": {}})
    if not isinstance(index, dict) or not isinstance(index.get("providers"), dict):
        raise ValueError("Outlook capture index is invalid.")
    semantic = {"message": _safe_message(message), "attachments": _safe_attachments(attachments)}
    content_sha256 = _digest(semantic)
    capture_id = "MAILCAP-" + content_sha256[:20].upper()
    capture_path = root / f"{capture_id}.json"
    prior_id = index["providers"].get(provider_message_id)
    if capture_path.exists():
        receipt = _read_json(capture_path, {})
        return {**receipt, "capture_state": "replayed"}
    receipt = {
        "schema": "dio.outlook_mail_capture.v1",
        "capture_id": capture_id,
        "provider": "microsoft_graph",
        "provider_message_id": provider_message_id,
        "content_sha256": content_sha256,
        "previous_capture_id": prior_id,
        "captured_at": _now(),
        "message": semantic["message"],
        "attachments": semantic["attachments"],
        "capture_state": "tombstoned" if "@removed" in message else "captured",
    }
    _write_json(capture_path, receipt)
    index["providers"][provider_message_id] = capture_id
    index["updated_at"] = _now()
    _write_json(index_path, index)
    return receipt


def recover_delta_cursor(state: Mapping[str, Any], *, error_code: str | None) -> dict[str, Any]:
    """Classify a Graph delta cursor failure without creating customer ingress."""
    expired = error_code in {"SyncStateNotFound", "InvalidDeltaToken", "resyncRequired"}
    return {
        "schema": "dio.graph_delta_recovery_receipt.v1",
        "recovery_state": "baseline_required" if expired else "retry_existing_cursor",
        "previous_delta_link_present": bool(state.get("delta_link")),
        "provider_error_code": error_code,
        "ingress_created": 0,
    }
