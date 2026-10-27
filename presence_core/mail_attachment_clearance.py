"""Fail-closed scanner and identified-clearance boundary for Outlook attachments."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


class AttachmentClearanceError(ValueError):
    pass


class ClamAvScanner(Protocol):
    engine_version: str | None
    signature_version: str | None

    def scan(self, path: Path) -> Mapping[str, Any]: ...


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_mail_attachments(attachments: Sequence[Mapping[str, Any]], *, scanner: ClamAvScanner) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for attachment in attachments:
        row = dict(attachment)
        path = Path(str(row.get("path") or ""))
        expected = str(row.get("sha256") or "")
        if not path.is_file() or not expected or _digest(path) != expected:
            state = "held_capture_mismatch"
            result: Mapping[str, Any] = {}
        else:
            result = scanner.scan(path)
            raw_state = str(result.get("state") or "unavailable")
            state = "clean" if raw_state == "clean" else ("held_scanner_unavailable" if raw_state == "unavailable" else "held_malware_or_error")
        row.update({
            "inspection_state": state,
            "scanned_at": _now(),
            "scanner_engine_version": getattr(scanner, "engine_version", None),
            "scanner_signature_version": getattr(scanner, "signature_version", None),
        })
        rows.append(row)
    return {"schema": "dio.outlook_attachment_inspection.v1", "attachments": rows, "inspected_at": _now(), "external_action_executed": False}


def clear_mail_attachments(inspection: Mapping[str, Any], *, actor_id: str) -> dict[str, Any]:
    if not actor_id:
        raise AttachmentClearanceError("Attachment clearance requires an identified actor.")
    rows: list[dict[str, Any]] = []
    for attachment in inspection.get("attachments") or []:
        row = dict(attachment)
        if row.get("inspection_state") != "clean":
            raise AttachmentClearanceError("Attachment is not clean and remains held.")
        row.update({"clearance_state": "cleared", "cleared_by": actor_id, "cleared_at": _now()})
        rows.append(row)
    return {"schema": "dio.outlook_attachment_clearance.v1", "attachments": rows, "cleared_at": _now(), "actor_id": actor_id}


def promote_mail_attachments(clearance: Mapping[str, Any]) -> list[dict[str, Any]]:
    promoted: list[dict[str, Any]] = []
    for attachment in clearance.get("attachments") or []:
        if attachment.get("clearance_state") != "cleared":
            raise AttachmentClearanceError("Attachment lacks an identified clearance.")
        path = Path(str(attachment.get("path") or ""))
        if not path.is_file() or _digest(path) != str(attachment.get("sha256") or ""):
            raise AttachmentClearanceError("Attachment bytes changed after clearance.")
        promoted.append({
            "attachment_id": str(attachment.get("provider_attachment_id") or attachment.get("sha256")),
            "original_file_name": attachment.get("name"),
            "sha256": attachment.get("sha256"),
            "size_bytes": attachment.get("size"),
            "state": "cleared_for_presence",
            "source": "outlook_mail_capture",
            "clearance_actor_id": attachment.get("cleared_by"),
        })
    return promoted
