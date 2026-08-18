from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_html_pack(
    *,
    studio_id: str,
    title: str,
    body: str,
    audience: str,
    out_dir: Path,
    source_root: Path,
    object_prefix: str,
    artifact_type: str,
    receipt_schema: str,
    capability_executed: str,
) -> dict[str, Any]:
    paragraphs = [part.strip() for part in str(body or "").split("\n") if part.strip()]
    rows = [{"paragraph_id": "P1", "text": str(title).strip()}]
    rows.extend({"paragraph_id": f"P{index}", "text": value} for index, value in enumerate(paragraphs, 2))
    content = build_paragraph_semantic_content(
        object_id=f"{object_prefix}-{studio_id.upper()}",
        version="1.0.0",
        title=str(title).strip(),
        source_language="English",
        source_rows=rows,
        context={
            "product": studio_id,
            "artifact_type": artifact_type,
            "audience": audience,
        },
    )
    receipt = render_semantic_asset(
        content,
        out_dir,
        style_profile="dio_professional",
        delivery_profile="editable_review",
        language="English",
        channels=["html"],
        release_mode=False,
        source_root=source_root,
    )
    output = next((row for row in receipt.get("outputs") or [] if row.get("channel") == "html"), None)
    if not output:
        raise RuntimeError("Document Studio controlled pack renderer produced no HTML output")
    path = out_dir / str(output["path"])
    qa = receipt.get("qa") or {}
    if receipt.get("status") != "rendered_review_candidate" or not qa.get("passed"):
        raise RuntimeError("Document Studio controlled pack failed render QA")
    normalized = {
        "schema": receipt_schema,
        "studio_id": studio_id,
        "artifact_type": artifact_type,
        "channel": "html",
        "sha256": _sha(path),
        "bytes": path.stat().st_size,
        "semantic_source_hash": receipt.get("semantic_source_hash"),
        "style_profile_hash": receipt.get("style_profile_hash"),
        "delivery_profile_hash": receipt.get("delivery_profile_hash"),
        "qa_passed": True,
        "release_mode": False,
        "external_delivery": "REFUSE",
        "publication": "REFUSE",
        "authority_created": False,
        "source_engine": "document_studio",
        "capability_executed": capability_executed,
        "output_path": str(path),
    }
    # Format Core's canonical receipt includes an observation timestamp. The
    # Studio closure keeps the deterministic normalized receipt and rendered
    # asset, so the double-run proof is not polluted by clock metadata.
    (out_dir / "FORMAT_CORE_RECEIPT.json").unlink(missing_ok=True)
    return normalized


def render_studio_sales_asset(*, studio_id: str, title: str, body: str, audience: str, out_dir: Path, source_root: Path) -> dict[str, Any]:
    """Render a controlled deterministic HTML sales asset through Format Core."""
    return _render_html_pack(
        studio_id=studio_id,
        title=title,
        body=body,
        audience=audience,
        out_dir=out_dir,
        source_root=source_root,
        object_prefix="STUDIO-SALES",
        artifact_type="controlled_sales_asset",
        receipt_schema="dio.document_studio_sales_asset_receipt.v1",
        capability_executed="document.sales_assets",
    )


def render_finance_readiness_pack(*, studio_id: str, title: str, body: str, audience: str, out_dir: Path, source_root: Path) -> dict[str, Any]:
    """Render a controlled finance-readiness dossier without financial authority."""
    return _render_html_pack(
        studio_id=studio_id,
        title=title,
        body=body,
        audience=audience,
        out_dir=out_dir,
        source_root=source_root,
        object_prefix="STUDIO-FINANCE",
        artifact_type="finance_readiness_review_pack",
        receipt_schema="dio.document_studio_finance_readiness_pack_receipt.v1",
        capability_executed="document.finance_readiness_pack",
    )


def render_publication_pack(*, studio_id: str, title: str, body: str, audience: str, out_dir: Path, source_root: Path) -> dict[str, Any]:
    """Render a controlled editorial publication-review pack without publishing it."""
    return _render_html_pack(
        studio_id=studio_id,
        title=title,
        body=body,
        audience=audience,
        out_dir=out_dir,
        source_root=source_root,
        object_prefix="STUDIO-PUBLICATION",
        artifact_type="publication_review_pack",
        receipt_schema="dio.document_studio_publication_pack_receipt.v1",
        capability_executed="document.publication_pack",
    )
