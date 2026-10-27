from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from presence_core.mail_attachment_clearance import AttachmentClearanceError, clear_mail_attachments, inspect_mail_attachments, promote_mail_attachments


class CleanScanner:
    engine_version = "clamav-test-1"
    signature_version = "daily-test-1"

    def scan(self, path: Path) -> dict[str, object]:
        return {"state": "clean"}


class MissingScanner:
    engine_version = None
    signature_version = None

    def scan(self, path: Path) -> dict[str, object]:
        return {"state": "unavailable"}


def _capture(tmp_path: Path, data: bytes = b"%PDF-1.7\nproof") -> dict[str, object]:
    path = tmp_path / "brief.pdf"
    path.write_bytes(data)
    return {"provider_attachment_id": "graph-a1", "name": "brief.pdf", "content_type": "application/pdf", "path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "capture_state": "captured_quarantined"}


def test_clean_attachment_requires_identified_clearance_then_promotes(tmp_path: Path) -> None:
    inspection = inspect_mail_attachments([_capture(tmp_path)], scanner=CleanScanner())
    clearance = clear_mail_attachments(inspection, actor_id="operator:byron")
    promoted = promote_mail_attachments(clearance)

    assert inspection["attachments"][0]["inspection_state"] == "clean"
    assert clearance["attachments"][0]["clearance_state"] == "cleared"
    assert promoted[0]["state"] == "cleared_for_presence"


def test_missing_scanner_holds_attachment(tmp_path: Path) -> None:
    inspection = inspect_mail_attachments([_capture(tmp_path)], scanner=MissingScanner())
    assert inspection["attachments"][0]["inspection_state"] == "held_scanner_unavailable"
    with pytest.raises(AttachmentClearanceError, match="not clean"):
        clear_mail_attachments(inspection, actor_id="operator:byron")


def test_mutated_attachment_cannot_be_promoted(tmp_path: Path) -> None:
    capture = _capture(tmp_path)
    inspection = inspect_mail_attachments([capture], scanner=CleanScanner())
    clearance = clear_mail_attachments(inspection, actor_id="operator:byron")
    Path(str(capture["path"])).write_bytes(b"%PDF-mutated")
    with pytest.raises(AttachmentClearanceError, match="changed"):
        promote_mail_attachments(clearance)
