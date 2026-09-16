from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .commercial_cognition import resolve_commercial_cognition


GROUNDABLE_INTENTS = {
    "unknown",
    "product_info",
    "pricing_info",
    "intake_request",
}


def should_ground_commercial(
    *,
    role: str,
    intent: str,
    text: str,
    attachment_present: bool = False,
) -> bool:
    if str(role or "").strip().lower() != "public":
        return False
    if attachment_present:
        return False
    if not str(text or "").strip():
        return False
    return str(intent or "").strip() in GROUNDABLE_INTENTS


def build_commercial_grounding(
    root: Path,
    message: str,
    *,
    incarnation_hint: str | None = None,
    context_tier_hint: str | None = None,
) -> dict[str, Any]:
    result = resolve_commercial_cognition(
        Path(root),
        message,
        incarnation_hint=incarnation_hint,
        context_tier_hint=context_tier_hint,
    )

    route = result.get("route") or {}
    candidates = [
        str(row.get("incarnation"))
        for row in route.get("candidates") or []
        if row.get("incarnation")
    ]

    packet: dict[str, Any] = {
        "schema": "dio.vesper.commercial_grounding.v1",
        "source_schema": result.get("schema"),
        "state": result.get("state"),
        "clarification_required": (
            result.get("state") == "NEEDS_CLARIFICATION"
        ),
        "candidates": candidates[:3],
        "product": None,
        "pricing": None,
        "authority_created": False,
        "external_effects": False,
    }

    if result.get("state") != "RESOLVED":
        return packet

    product = result.get("product") or {}
    pricing = result.get("pricing") or {}
    selected = pricing.get("selected_tier")

    packet["product"] = {
        "product_id": product.get("product_id"),
        "name": product.get("name"),
        "suite": product.get("suite"),
        "primary_family": product.get("primary_family"),
        "primary_scope_unit": product.get(
            "primary_scope_unit"
        ),
    }

    packet["pricing"] = {
        "currency": pricing.get("currency"),
        "reference_band_zar": dict(
            pricing.get("reference_band_zar") or {}
        ),
        "pricing_model": pricing.get("pricing_model"),
        "pricing_state": pricing.get("pricing_state"),
        "commercial_validation": pricing.get(
            "commercial_validation"
        ),
        "tier_state": pricing.get("tier_state"),
        "requested_tier": pricing.get("requested_tier"),
        "tier_basis": pricing.get("tier_basis"),
        "selected_tier": (
            {
                "tier_id": selected.get("tier_id"),
                "label": selected.get("label"),
                "reference_amount_zar": selected.get(
                    "reference_amount_zar"
                ),
                "quote_issue_authority": selected.get(
                    "quote_issue_authority"
                ),
                "invoice_issue_authority": selected.get(
                    "invoice_issue_authority"
                ),
            }
            if isinstance(selected, dict)
            else None
        ),
        "quote_authority": dict(
            pricing.get("quote_authority") or {}
        ),
        "truth_boundary": pricing.get("truth_boundary"),
    }

    return packet


def commercial_facts(packet: dict[str, Any]) -> str:
    return (
        "COMMERCIAL_TRUTH="
        + json.dumps(
            packet,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


def commercial_fallback(
    packet: dict[str, Any],
    *,
    intent: str,
) -> str | None:
    state = packet.get("state")

    if state == "NEEDS_CLARIFICATION":
        candidates = [
            str(x)
            for x in packet.get("candidates") or []
            if str(x).strip()
        ]

        if len(candidates) >= 2:
            return (
                "I can see more than one plausible DIO route here: "
                + ", ".join(candidates[:3])
                + ". I don't have enough evidence to choose between "
                "them without guessing. Tell me which outcome matters "
                "most and I'll narrow the route."
            )

        return (
            "I can see the shape of the request, but not enough "
            "evidence to bind it to one DIO product safely yet. "
            "Tell me the concrete outcome you want."
        )

    if state != "RESOLVED":
        return None

    product = packet.get("product") or {}
    pricing = packet.get("pricing") or {}

    name = str(product.get("name") or "that DIO workflow")
    scope = str(
        product.get("primary_scope_unit") or "bounded work item"
    ).replace("_", " ")

    if intent == "pricing_info":
        band = pricing.get("reference_band_zar") or {}
        low = band.get("min")
        high = band.get("max")

        if isinstance(low, int) and isinstance(high, int):
            text = (
                f"That maps most closely to {name}. "
                f"The current governed reference band is "
                f"R{low:,} to R{high:,}. "
            )
        else:
            text = (
                f"That maps most closely to {name}. "
                "I have the governed pricing structure, but not a "
                "safe numeric band for this turn. "
            )

        selected = pricing.get("selected_tier")
        if isinstance(selected, dict):
            amount = selected.get("reference_amount_zar")
            label = selected.get("label")
            if isinstance(amount, int):
                text += (
                    f"Your wording supports the {label} tier, whose "
                    f"governed reference point is R{amount:,}. "
                )
        else:
            text += (
                "I don't have enough context to select a commercial "
                "tier yet. "
            )

        return (
            text
            + "Those are governed reference points, not an issued "
            "quote, invoice, or proof of willingness to pay."
        )

    return (
        f"That maps most closely to {name}, scoped around a "
        f"{scope}. I can use that governed product truth to help "
        "narrow the next step without inventing a quote, payment, "
        "or delivery commitment."
    )
