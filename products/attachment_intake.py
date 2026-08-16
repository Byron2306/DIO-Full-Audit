from __future__ import annotations

import base64
import hashlib
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SCHEMA = "dio.vesper.attachment_intake.v1"
MAX_ATTACHMENTS = 12
MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {".txt", ".md", ".json", ".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".zip"}
TEXT_TYPES = {".txt", ".md", ".json"}
MAGIC = {".pdf": b"%PDF", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}


class AttachmentIntakeError(RuntimeError):
    pass


def _safe_name(value: Any) -> str:
    raw = str(value or "")
    if "/" in raw or "\\" in raw:
        raise AttachmentIntakeError("attachment filename is unsafe")
    name = Path(raw).name
    if not name or name in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,179}", name):
        raise AttachmentIntakeError("attachment filename is unsafe")
    return name


def _decode(value: Any) -> bytes:
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except Exception as exc:
        raise AttachmentIntakeError("attachment content_base64 is invalid") from exc


def _docx_text(body: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(body)) as archive:
            xml = archive.read("word/document.xml")
    except Exception as exc:
        raise AttachmentIntakeError("DOCX container is invalid") from exc
    root = ElementTree.fromstring(xml)
    lines = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _xlsx_text(body: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(body)) as archive:
            names = set(archive.namelist())
            shared = []
            if "xl/sharedStrings.xml" in names:
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")) for item in root]
            rows = []
            for name in sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
                root = ElementTree.fromstring(archive.read(name))
                values = []
                for cell in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    value = next(cell.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"), None)
                    if value is not None and value.text is not None:
                        text = shared[int(value.text)] if cell.get("t") == "s" and int(value.text) < len(shared) else value.text
                        values.append(text)
                if values:
                    rows.append(f"{name}: " + " | ".join(values))
            return "\n".join(rows)
    except Exception as exc:
        raise AttachmentIntakeError("XLSX container is invalid") from exc


def _zip_inventory(body: bytes) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(BytesIO(body)) as archive:
            rows = []
            for info in archive.infolist():
                path = Path(info.filename)
                unsafe = path.is_absolute() or ".." in path.parts or info.file_size > MAX_BYTES
                rows.append({"name": info.filename, "bytes": info.file_size, "safe": not unsafe})
            return rows
    except Exception as exc:
        raise AttachmentIntakeError("ZIP container is invalid") from exc


def quarantine_attachments(attachments: list[dict[str, Any]], *, output_dir: Path, intake_id: str) -> dict[str, Any]:
    if not attachments or len(attachments) > MAX_ATTACHMENTS:
        raise AttachmentIntakeError(f"between 1 and {MAX_ATTACHMENTS} attachments are required")
    output_dir = output_dir.resolve()
    quarantine = output_dir / "state" / "vesper" / "quarantine" / intake_id
    quarantine.mkdir(parents=True, exist_ok=True)
    receipts = []
    for index, item in enumerate(attachments, 1):
        name = _safe_name(item.get("filename"))
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED:
            raise AttachmentIntakeError(f"unsupported attachment type: {suffix or '<none>'}")
        body = _decode(item.get("content_base64"))
        if not body or len(body) > MAX_BYTES:
            raise AttachmentIntakeError(f"attachment {name} is empty or exceeds {MAX_BYTES} bytes")
        expected = MAGIC.get(suffix)
        if expected and not body.startswith(expected):
            raise AttachmentIntakeError(f"attachment {name} failed file-signature verification")
        digest = hashlib.sha256(body).hexdigest()
        stored_name = f"{index:02d}-{digest[:12]}-{name}"
        stored = quarantine / stored_name
        stored.write_bytes(body)
        extracted, state, inventory = "", "METADATA_ONLY", []
        if suffix in TEXT_TYPES:
            extracted, state = body.decode("utf-8", errors="strict"), "EXTRACTED"
            if suffix == ".json":
                json.loads(extracted)
        elif suffix == ".docx":
            extracted, state = _docx_text(body), "EXTRACTED"
        elif suffix == ".xlsx":
            extracted, state = _xlsx_text(body), "EXTRACTED"
        elif suffix == ".zip":
            inventory, state = _zip_inventory(body), "INVENTORIED_QUARANTINED"
            if any(not row["safe"] for row in inventory):
                raise AttachmentIntakeError(f"attachment {name} contains an unsafe ZIP member")
        receipt = {
            "attachment_id": f"ATT-{digest[:16].upper()}", "filename": name, "role": str(item.get("role") or "evidence"),
            "declared_mime_type": str(item.get("mime_type") or "application/octet-stream"), "bytes": len(body), "sha256": digest,
            "source_ref": f"quarantine://{intake_id}/{stored_name}", "quarantine_path": str(stored),
            "extraction_state": state, "extracted_text": extracted, "archive_inventory": inventory,
            "trust_state": "captured_untrusted", "freshness_state": "unknown", "external_effects": False,
        }
        receipts.append(receipt)
    manifest = {"schema": SCHEMA, "intake_id": intake_id, "policy": "quarantine_only", "attachments": receipts, "human_gate": "NEEDS_YOU", "external_effects": False}
    (quarantine / "ATTACHMENT_INTAKE.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
