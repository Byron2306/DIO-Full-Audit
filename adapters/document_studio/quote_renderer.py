from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from adapters.format_core.renderer import render_semantic_asset


class QuoteRenderError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_quote_semantic_content(
    quote: dict[str, Any],
    *,
    official: bool,
) -> dict[str, Any]:
    case_id = _text(quote.get("case_id"))
    product = _text(quote.get("product_id"))
    filename = _text(quote.get("original_file_name"))
    scope_unit = _text(quote.get("scope_unit"))
    currency = _text(quote.get("currency") or "ZAR")

    try:
        quantity = int(quote["scope_quantity"])
        amount = int(quote["amount"])
    except Exception as exc:
        raise QuoteRenderError(
            "quote requires integer scope_quantity and amount"
        ) from exc

    if not case_id:
        raise QuoteRenderError("case_id is required")
    if not product:
        raise QuoteRenderError("product_id is required")
    if not filename:
        raise QuoteRenderError("original_file_name is required")
    if quantity < 1:
        raise QuoteRenderError("scope_quantity must be >= 1")
    if amount < 1:
        raise QuoteRenderError("amount must be >= 1")

    quote_state = _text(quote.get("quote_state"))

    if official:
        if quote_state != "approved":
            raise QuoteRenderError(
                "official quote rendering requires quote_state=approved"
            )

        approval = quote.get("approval") or {}

        if not _text(approval.get("approved_by")):
            raise QuoteRenderError(
                "official quote rendering requires operator approval"
            )

        if not _text(approval.get("approved_at")):
            raise QuoteRenderError(
                "official quote rendering requires approval timestamp"
            )

    document_label = (
        "OFFICIAL QUOTE / PAYMENT REQUEST"
        if official
        else "PRICING RECOMMENDATION / DRAFT QUOTE"
    )

    status_text = (
        "Approved for quotation"
        if official
        else "Awaiting operator quote approval"
    )

    payment_url = _text(
        quote.get("payment_url")
        or quote.get("paypal_url")
    )

    logo_path = _text(
        quote.get("logo_path")
        or "sites/product-classes/assets/dio-logo.png"
    )

    amount_label = (
        f"R {amount:,.2f}"
        if currency == "ZAR"
        else f"{currency} {amount:,.2f}"
    )

    blocks: list[dict[str, Any]] = [
        {
            "block_id": "DIO_LOGO",
            "type": "figure",
            "media_path": logo_path,
            "alt_text": "DIO Workflows logo",
            "caption": "DIO Workflows",
            "width_inches": 1.25,
        },
        {
            "block_id": "TITLE",
            "type": "title",
            "text": "DIO WORKFLOWS",
        },
        {
            "block_id": "DOCUMENT_CLASS",
            "type": "heading",
            "level": 1,
            "text": document_label,
        },
        {
            "block_id": "PRODUCT",
            "type": "heading",
            "level": 2,
            "text": product,
        },
        {
            "block_id": "SERVICE_NOTE",
            "type": "paragraph",
            "text": (
                "Controlled evidence review prepared through "
                "Deterministic Intelligence Orchestration."
            ),
        },
        {
            "block_id": "COMMERCIAL_SUMMARY",
            "type": "table",
            "headers": ["Commercial item", "Verified value"],
            "rows": [
                ["Case", case_id],
                ["Document", filename],
                [
                    "Verified scope",
                    f"{quantity} {scope_unit.replace('_', ' ')}"
                    + ("" if quantity == 1 else "s"),
                ],
                ["Amount", amount_label],
                ["Status", status_text],
            ],
        },
        {
            "block_id": "AMOUNT",
            "type": "heading",
            "level": 1,
            "text": f"Amount: {amount_label}",
        },
    ]

    if official and payment_url:
        blocks.extend(
            [
                {
                    "block_id": "PAYMENT_HEADING",
                    "type": "heading",
                    "level": 2,
                    "text": "Payment",
                },
                {
                    "block_id": "PAYMENT",
                    "type": "paragraph",
                    "text": (
                        "Pay securely using the approved PayPal "
                        f"payment link: {payment_url}"
                    ),
                },
            ]
        )

    if not official:
        blocks.extend(
            [
                {
                    "block_id": "PAYMENT_PENDING_APPROVAL",
                    "type": "paragraph",
                    "text": (
                        "Payment instructions will be provided once "
                        "this pricing recommendation has received "
                        "operator quote approval."
                    ),
                },
            ]
        )
        blocks.append(
            {
                "block_id": "DRAFT_BOUNDARY",
                "type": "paragraph",
                "text": (
                    "This document records a governed pricing "
                    "recommendation. It is not yet an issued quote, "
                    "invoice, payment demand or fulfilment authority."
                ),
            }
        )

    blocks.extend(
        [
            {
                "block_id": "SERVICE_BOUNDARY",
                "type": "heading",
                "level": 2,
                "text": "Service boundary",
            },
            {
                "block_id": "BOUNDARY_TEXT",
                "type": "paragraph",
                "text": (
                    "Sophia Integrity prepares evidence-review material "
                    "for authorised human consideration. It does not "
                    "determine plagiarism or research misconduct, decide "
                    "authorship, impose disciplinary action, decide "
                    "publication, or create an institutional integrity "
                    "finding."
                ),
            },
            {
                "block_id": "AUTHORITY",
                "type": "paragraph",
                "text": (
                    "Document Studio rendered this artifact from supplied "
                    "commercial truth. Rendering created no commercial, "
                    "payment, fulfilment or release authority."
                ),
            },
        ]
    )

    return {
        "schema": "dio.semantic_content.v1",
        "object_id": _text(
            quote.get("quote_id")
            or f"DIO-QUOTE-{case_id}"
        ),
        "version": "1.0.0",
        "title": document_label,
        "source_language": "English",
        "context": {
            "product": "Document Studio",
            "artifact_type": (
                "official_quote"
                if official
                else "pricing_recommendation"
            ),
            "audience": "customer",
        },
        "blocks": blocks,
    }


def render_quote(
    quote: dict[str, Any],
    *,
    out_dir: Path,
    source_root: Path,
    official: bool = False,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    content = build_quote_semantic_content(
        quote,
        official=official,
    )

    receipt = render_semantic_asset(
        content,
        out_dir,
        style_profile="dio_commercial_quote",
        delivery_profile="print_pack",
        language="English",
        channels=["pdf", "html"],
        release_mode=False,
        source_root=Path(source_root),
    )

    qa = receipt.get("qa") or {}

    if not qa.get("passed"):
        raise QuoteRenderError(
            f"Document Studio render QA failed: {qa}"
        )

    outputs = []

    for row in receipt.get("outputs") or []:
        path = out_dir / str(row["path"])

        outputs.append(
            {
                "channel": row.get("channel"),
                "path": str(path),
                "sha256": _sha(path),
                "bytes": path.stat().st_size,
            }
        )

    normalized = {
        "schema": "dio.document_studio.quote_render_receipt.v1",
        "quote_id": content["object_id"],
        "case_id": quote["case_id"],
        "product_id": quote["product_id"],
        "artifact_class": (
            "OFFICIAL_QUOTE"
            if official
            else "PRICING_RECOMMENDATION"
        ),
        "quote_state": quote.get("quote_state"),
        "amount": quote["amount"],
        "currency": quote.get("currency") or "ZAR",
        "scope_quantity": quote["scope_quantity"],
        "scope_unit": quote["scope_unit"],
        "outputs": outputs,
        "semantic_source_hash": receipt.get(
            "semantic_source_hash"
        ),
        "style_profile_hash": receipt.get(
            "style_profile_hash"
        ),
        "delivery_profile_hash": receipt.get(
            "delivery_profile_hash"
        ),
        "qa_passed": True,
        "external_delivery": "REFUSE",
        "payment_authority_created": False,
        "fulfilment_authority_created": False,
        "release_authority_created": False,
        "authority_created": False,
        "source_engine": "document_studio",
    }

    (out_dir / "QUOTE_RENDER_RECEIPT.json").write_text(
        json.dumps(
            normalized,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return normalized
