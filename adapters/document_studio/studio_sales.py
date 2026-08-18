from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_studio_sales_asset(*, studio_id: str, title: str, body: str, audience: str, out_dir: Path, source_root: Path) -> dict[str, Any]:
    """Render a controlled deterministic HTML sales asset through Format Core.

    This is distinct from the preview render used by the native activation
    harness. It fulfils the Document Studio ``document.sales_assets`` seam
    without requiring publication or external delivery.
    """
    paragraphs = [part.strip() for part in str(body or "").split("\n") if part.strip()]
    rows = [{"paragraph_id": "P1", "text": str(title).strip()}]
    rows.extend({"paragraph_id": f"P{index}", "text": value} for index, value in enumerate(paragraphs, 2))
    content = build_paragraph_semantic_content(
        object_id=f"STUDIO-SALES-{studio_id.upper()}",
        version="1.0.0",
        title=str(title).strip(),
        source_language="English",
        source_rows=rows,
        context={
            "product": studio_id,
            "artifact_type": "controlled_sales_asset",
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
        raise RuntimeError("Document Studio sales asset renderer produced no HTML output")
    path = out_dir / str(output["path"])
    qa = receipt.get("qa") or {}
    if receipt.get("status") != "rendered_review_candidate" or not qa.get("passed"):
        raise RuntimeError("Document Studio sales asset failed controlled render QA")
    return {
        "schema": "dio.document_studio_sales_asset_receipt.v1",
        "studio_id": studio_id,
        "artifact_type": "controlled_sales_asset",
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
        "capability_executed": "document.sales_assets",
        "output_path": str(path),
    }
