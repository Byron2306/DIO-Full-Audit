from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader


SCOPE_SCAN_SCHEMA = "dio.presence.scope_scan.v1"


class ScopeScanError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scan_pdf_scope(
    presence_root: Path,
    *,
    case_id: str,
    attachment_id: str,
    product_id: str,
) -> dict[str, Any]:
    """
    Perform bounded structural inspection for commercial scoping only.

    This operation may count PDF pages and inspect structural metadata.
    It does not perform semantic product analysis, execute embedded content,
    or create fulfilment authority.
    """
    presence_root = Path(presence_root)

    attachment_dir = (
        presence_root
        / "quarantine"
        / attachment_id
    )
    metadata_path = attachment_dir / "ATTACHMENT.json"

    if not metadata_path.exists():
        raise ScopeScanError("ATTACHMENT_METADATA_NOT_FOUND")

    attachment = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    if str(attachment.get("attachment_id")) != attachment_id:
        raise ScopeScanError("ATTACHMENT_ID_MISMATCH")

    blob_path = Path(
        attachment.get("blob_path")
        or attachment_dir / "content.blob"
    )

    if not blob_path.is_absolute():
        blob_path = presence_root / blob_path

    if not blob_path.exists():
        raise ScopeScanError("ATTACHMENT_BLOB_NOT_FOUND")

    raw = blob_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    expected_sha256 = str(attachment.get("sha256") or "")

    if actual_sha256 != expected_sha256:
        raise ScopeScanError("ATTACHMENT_SHA256_DRIFT")

    filename = str(
        attachment.get("original_file_name")
        or attachment_id
    )

    if not filename.lower().endswith(".pdf"):
        raise ScopeScanError("UNSUPPORTED_SCOPE_SCAN_TYPE")

    reader = PdfReader(str(blob_path))

    if reader.is_encrypted:
        raise ScopeScanError("ENCRYPTED_PDF_SCOPE_SCAN_REFUSED")

    page_count = len(reader.pages)

    if page_count < 1:
        raise ScopeScanError("PDF_HAS_NO_PAGES")

    receipt = {
        "schema": SCOPE_SCAN_SCHEMA,
        "case_id": case_id,
        "attachment_id": attachment_id,
        "product_id": product_id,
        "original_file_name": filename,
        "source_sha256": actual_sha256,
        "document_type": "pdf",
        "primary_scope_unit": "manuscript_page",
        "scope_quantity": page_count,
        "page_count": page_count,
        "scan_class": "BOUNDED_PRICING_SCOPE",
        "semantic_analysis_performed": False,
        "embedded_content_executed": False,
        "safe_to_execute": False,
        "fulfilment_authority_created": False,
        "authority_created": False,
        "scanned_at": _now(),
    }

    receipt_path = attachment_dir / "SCOPE_SCAN.json"

    # Idempotent for the same exact bytes and measured scope.
    if receipt_path.exists():
        existing = json.loads(
            receipt_path.read_text(encoding="utf-8")
        )

        if (
            existing.get("source_sha256") == actual_sha256
            and existing.get("page_count") == page_count
            and existing.get("case_id") == case_id
            and existing.get("product_id") == product_id
        ):
            return existing

        raise ScopeScanError("SCOPE_SCAN_RECEIPT_CONFLICT")

    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return receipt
