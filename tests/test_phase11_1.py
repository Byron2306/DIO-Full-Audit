from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from products.attachment_intake import AttachmentIntakeError, quarantine_attachments
from products.phase11_1_gauntlet import run_phase11_1_gauntlet


ROOT = Path(__file__).resolve().parents[1]


def _item(filename: str, body: bytes, role: str = "evidence") -> dict:
    return {"filename": filename, "mime_type": "text/plain", "role": role, "content_base64": base64.b64encode(body).decode()}


def test_phase11_1_binds_attachments_and_stops_at_draft(tmp_path: Path) -> None:
    receipt = run_phase11_1_gauntlet(output_dir=tmp_path, root=ROOT)
    assert receipt["deterministic_execution"] == "PASS"
    assert receipt["attachment_count"] == 3 and receipt["evidence_attachment_count"] == 2
    assert receipt["evidence_fanout_guard"] == "PASS" and receipt["unresolved_attachment_count"] == 0
    assert receipt["external_delivery"] == "REFUSE" and receipt["human_release"] == "NEEDS_YOU" and receipt["sent"] is False
    draft = json.loads((tmp_path / "first" / receipt["outlook_draft_ref"]).read_text())
    assert draft["state"] == "DRAFT_ONLY" and draft["send_authorized"] is False and draft["message_id"] is None
    assert {row["filename"] for row in draft["attachments"]} >= {"EVIDENCE_PACK.pdf", "EVIDENCE_PACK.docx"}
    manifest = next((tmp_path / "first" / "state" / "vesper" / "quarantine").glob("*/ATTACHMENT_INTAKE.json"))
    attachment_manifest = json.loads(manifest.read_text())
    assert attachment_manifest["policy"] == "quarantine_only"
    assert all(row["trust_state"] == "captured_untrusted" for row in attachment_manifest["attachments"])


def test_signature_spoof_and_unsafe_filename_are_refused(tmp_path: Path) -> None:
    with pytest.raises(AttachmentIntakeError, match="signature"):
        quarantine_attachments([_item("fake.pdf", b"not a pdf")], output_dir=tmp_path, intake_id="VIN-X")
    with pytest.raises(AttachmentIntakeError, match="unsafe"):
        quarantine_attachments([_item("../escape.txt", b"safe text")], output_dir=tmp_path, intake_id="VIN-Y")


def test_attachment_bytes_are_hash_bound(tmp_path: Path) -> None:
    one = quarantine_attachments([_item("evidence.txt", b"alpha")], output_dir=tmp_path / "a", intake_id="VIN-A")
    two = quarantine_attachments([_item("evidence.txt", b"beta")], output_dir=tmp_path / "b", intake_id="VIN-B")
    assert one["attachments"][0]["sha256"] != two["attachments"][0]["sha256"]
