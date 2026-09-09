from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from statistics import median
from typing import Any


_PRICE_RE = re.compile(r"\bR\s*([0-9][0-9,]*(?:\.\d+)?)\s*(?:[-–—]\s*R?\s*([0-9][0-9,]*(?:\.\d+)?))?", re.IGNORECASE)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _amount(value: str) -> int | None:
    try:
        return int(round(float(value.replace(",", ""))))
    except (TypeError, ValueError):
        return None


def _parse_zar_range(label: str) -> tuple[int, int] | None:
    match = _PRICE_RE.search(str(label or ""))
    if not match:
        return None
    low = _amount(match.group(1))
    high = _amount(match.group(2) or match.group(1))
    if low is None or high is None:
        return None
    if high < low:
        low, high = high, low
    return low, high


def reference_offers(root: Path, product_id: str) -> list[dict[str, Any]]:
    """Return only governed public numeric offer bands for one product."""
    config_path = Path(root) / "config" / "commercial_campaigns.json"
    campaigns = _read_json(config_path)
    products = campaigns.get("products") or {}
    raw_product = products.get(product_id) if isinstance(products, Mapping) else None
    if not isinstance(raw_product, Mapping):
        return []

    result: list[dict[str, Any]] = []
    for raw in raw_product.get("offers") or []:
        if not isinstance(raw, Mapping):
            continue
        price_label = str(raw.get("price") or "").strip()
        parsed = _parse_zar_range(price_label)
        if parsed is None:
            continue
        low, high = parsed
        result.append(
            {
                "schema": "dio.commercial_reference_offer.v1",
                "product_id": product_id,
                "offer_id": str(raw.get("id") or "").strip(),
                "name": str(raw.get("name") or "").strip(),
                "promise": str(raw.get("promise") or "").strip(),
                "price_label": price_label,
                "currency": "ZAR",
                "min_amount": low,
                "max_amount": high,
                "source": "config/commercial_campaigns.json",
                "authority_created": False,
            }
        )
    return result


def _portfolio_product(root: Path, product_id: str) -> dict[str, Any] | None:
    portfolio = _read_json(Path(root) / "config" / "dio_product_portfolio.json")
    for row in portfolio.get("products") or []:
        if isinstance(row, Mapping) and str(row.get("id") or "").strip() == product_id:
            return dict(row)
    return None


def _scope_exceeds_portfolio_offer(root: Path, product_id: str, scope: Mapping[str, Any]) -> dict[str, Any] | None:
    row = _portfolio_product(root, product_id)
    if not row:
        return None
    offer = str(row.get("offer") or "").strip()
    cta = str(row.get("cta") or "").strip()
    bounded_text = f"{offer} {cta}".lower()
    one_section = "one-section" in bounded_text or "one section" in bounded_text or "one bounded manuscript section" in bounded_text
    requested_depth = str(scope.get("requested_depth") or "").strip().lower()
    try:
        section_count = int(scope.get("section_count") or 0)
    except (TypeError, ValueError):
        section_count = 0
    if one_section and (requested_depth in {"full_document", "whole_document", "full_article", "whole_article"} or section_count > 1):
        return {
            "mode": "needs_operator",
            "reason": "scope_exceeds_governed_offer",
            "product_id": product_id,
            "governed_offer": offer or cta,
            "scope": dict(scope),
            "evidence": "config/dio_product_portfolio.json",
            "authority_created": False,
        }
    return None


def _evidex_offer(offers: list[dict[str, Any]], scope: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    by_id = {row.get("offer_id"): row for row in offers}
    try:
        file_count = int(scope.get("file_count") or 0)
    except (TypeError, ValueError):
        file_count = 0
    complexity = str(scope.get("complexity") or "normal").strip().lower()
    urgency = str(scope.get("urgency") or "normal").strip().lower()

    if file_count and file_count <= 5 and complexity in {"low", "normal"} and urgency not in {"urgent", "rush"}:
        return by_id.get("starter"), "file_count<=5; complexity=low_or_normal; urgency=normal"
    if file_count and file_count <= 20 and complexity in {"low", "normal", "medium"} and urgency not in {"urgent", "rush"}:
        return by_id.get("standard"), "file_count=6_to_20; complexity=low_to_medium; urgency=normal"
    if file_count > 20 or complexity in {"high", "complex", "messy"} or urgency in {"urgent", "rush"}:
        return by_id.get("complex"), "file_count>20_or_complexity_high_or_urgency_urgent"
    return None, "scope_does_not_match_governed_evidex_rule"


def _select_offer(product_id: str, offers: list[dict[str, Any]], scope: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, str]:
    if product_id == "evidex":
        offer, reasoning = _evidex_offer(offers, scope)
        if offer is None:
            return None, reasoning, "needs_operator"
        if offer.get("offer_id") == "starter":
            return offer, reasoning, "known_band"
        return offer, reasoning, "scope_sensitive"
    if len(offers) == 1:
        return offers[0], "single_governed_numeric_offer", "known_band"
    return None, "multiple_offers_require_product_specific_scope_rule", "needs_operator"


def _structured_comparables(
    historical_rows: list[dict[str, Any]] | None,
    *,
    product_id: str,
    offer_id: str,
    low: int,
    high: int,
) -> list[int]:
    values: list[int] = []
    for row in historical_rows or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("product_id") or "") != product_id or str(row.get("offer_id") or "") != offer_id:
            continue
        outcome = str(row.get("payment_outcome") or "").lower()
        if outcome and outcome not in {"paid", "succeeded", "verified"}:
            continue
        raw = row.get("final_invoice_amount")
        if not isinstance(raw, (int, float)):
            continue
        amount = int(round(float(raw)))
        if low <= amount <= high:
            values.append(amount)
    return values


def recommend_quote(
    root: Path,
    *,
    product_id: str,
    scope: dict[str, Any],
    historical_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recommend only from governed public bands and structured comparable evidence."""
    root = Path(root)
    scope_guard = _scope_exceeds_portfolio_offer(root, product_id, scope)
    if scope_guard is not None:
        return scope_guard

    offers = reference_offers(root, product_id)
    if not offers:
        return {
            "mode": "needs_operator",
            "reason": "no_governed_price",
            "product_id": product_id,
            "scope": dict(scope),
            "authority_created": False,
        }

    offer, reasoning, mode = _select_offer(product_id, offers, scope)
    if offer is None:
        return {
            "mode": "needs_operator",
            "reason": "scope_requires_product_rule",
            "product_id": product_id,
            "scope": dict(scope),
            "reasoning": reasoning,
            "governed_offers": [row["offer_id"] for row in offers],
            "authority_created": False,
        }

    low = int(offer["min_amount"])
    high = int(offer["max_amount"])
    result: dict[str, Any] = {
        "mode": mode,
        "product_id": product_id,
        "offer_id": offer["offer_id"],
        "offer_name": offer["name"],
        "price_label": offer["price_label"],
        "currency": "ZAR",
        "min_amount": low,
        "max_amount": high,
        "scope": dict(scope),
        "reasoning": reasoning,
        "evidence": [offer["source"]],
        "comparables_used": 0,
        "authority_created": False,
    }

    comparables = _structured_comparables(
        historical_rows,
        product_id=product_id,
        offer_id=str(offer["offer_id"]),
        low=low,
        high=high,
    )
    if comparables:
        recommended = int(round(float(median(comparables))))
        result["recommended_amount"] = max(low, min(high, recommended))
        result["comparables_used"] = len(comparables)
        result["mode"] = "scope_sensitive"
        result["reasoning"] += "; structured_paid_comparables_within_governed_band"
    return result
