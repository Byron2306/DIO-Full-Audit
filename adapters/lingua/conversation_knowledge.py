from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PUBLIC_PORTFOLIO_FIELDS = {
    "id",
    "name",
    "category",
    "status",
    "runtime_mode",
    "customer_facing",
    "intake_enabled",
    "one_liner",
    "pain",
    "promise",
    "offer",
    "cta",
    "risk_boundary",
    "keywords",
    "route_keywords",
    "expected_outputs",
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalized(value: Any) -> str:
    return _clean_text(value).lower()


def _dedupe_strings(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    result: list[str] = []
    for raw in values:
        value = _clean_text(raw)
        if value and value not in result:
            result.append(value)
    return result


def _campaign_product(product_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    offers = row.get("offers") or []
    promises: list[str] = []
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, Mapping):
                promise = _clean_text(offer.get("promise"))
                if promise and promise not in promises:
                    promises.append(promise)

    boundaries = _dedupe_strings(row.get("claim_boundaries"))
    projected: dict[str, Any] = {
        "id": product_id,
        "name": _clean_text(row.get("name")) or product_id.replace("_", " ").title(),
        "customer_facing": True,
        "one_liner": _clean_text(row.get("campaign_line")),
        "promise": " ".join(promises),
        "risk_boundary": " ".join(boundaries),
        "proof": _dedupe_strings(row.get("proof")),
        "audiences": _dedupe_strings(row.get("audiences")),
    }
    return {key: value for key, value in projected.items() if value not in (None, "", [])}


def _portfolio_product(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not bool(row.get("customer_facing")):
        return None
    product_id = _clean_text(row.get("id"))
    if not product_id:
        return None
    projected = {key: row[key] for key in PUBLIC_PORTFOLIO_FIELDS if key in row}
    projected["id"] = product_id
    return projected


def load_public_product_knowledge(root: Path) -> dict[str, dict[str, Any]]:
    root = Path(root)
    knowledge: dict[str, dict[str, Any]] = {}

    portfolio = _read_json(root / "config" / "dio_product_portfolio.json", {})
    if isinstance(portfolio, Mapping):
        for raw in portfolio.get("products") or []:
            if not isinstance(raw, Mapping):
                continue
            projected = _portfolio_product(raw)
            if projected is not None:
                knowledge[projected["id"]] = projected

    campaigns = _read_json(root / "config" / "commercial_campaigns.json", {})
    if isinstance(campaigns, Mapping):
        products = campaigns.get("products") or {}
        if isinstance(products, Mapping):
            for raw_id, raw in products.items():
                if not isinstance(raw, Mapping):
                    continue
                product_id = _clean_text(raw_id)
                if not product_id:
                    continue
                base = knowledge.get(product_id, {})
                campaign = _campaign_product(product_id, raw)
                knowledge[product_id] = {**campaign, **base}

    lingua_routes = _read_json(root / "config" / "lingua_product_routes.json", {})
    if isinstance(lingua_routes, Mapping):
        products = lingua_routes.get("products") or {}
        if isinstance(products, Mapping):
            for raw_id, raw in products.items():
                if not isinstance(raw, Mapping):
                    continue
                product_id = _clean_text(raw_id)
                if not product_id:
                    continue
                current = dict(knowledge.get(product_id, {"id": product_id}))
                for field in ("artifact_types", "required_context", "channels"):
                    values = _dedupe_strings(raw.get(field))
                    if values:
                        current[field] = values
                knowledge[product_id] = current

    routes = _read_json(root / "config" / "routes.json", {})
    if isinstance(routes, Mapping):
        products = routes.get("products") or {}
        if isinstance(products, Mapping):
            for raw_id, raw in products.items():
                if not isinstance(raw, Mapping):
                    continue
                product_id = _clean_text(raw_id)
                if not product_id:
                    continue
                current = dict(knowledge.get(product_id, {"id": product_id}))
                route_keywords = _dedupe_strings(raw.get("keywords"))
                if route_keywords:
                    current["route_keywords"] = _dedupe_strings(
                        list(current.get("route_keywords") or []) + route_keywords
                    )
                if "priority" in raw:
                    try:
                        current["route_priority"] = int(raw["priority"])
                    except (TypeError, ValueError):
                        pass
                knowledge[product_id] = current

    class_routes = _read_json(root / "config" / "product_class_routes.json", {})
    if isinstance(class_routes, Mapping):
        direct = class_routes.get("direct_products") or {}
        if isinstance(direct, Mapping):
            for raw_id, route in direct.items():
                product_id = _clean_text(raw_id)
                if not product_id or not isinstance(route, Mapping):
                    continue
                current = dict(knowledge.get(product_id, {"id": product_id}))
                current["route_kind"] = _clean_text(route.get("route_kind"))
                current["route_engine"] = _clean_text(route.get("engine"))
                current["route_auto_promotable"] = bool(route.get("auto_promotable", False))
                knowledge[product_id] = current
        aliases = class_routes.get("aliases") or {}
        if isinstance(aliases, Mapping):
            by_product: dict[str, list[str]] = {}
            for alias, target in aliases.items():
                target_id = _clean_text(target)
                alias_id = _clean_text(alias)
                if target_id and alias_id:
                    by_product.setdefault(target_id, []).append(alias_id)
            for product_id, alias_rows in by_product.items():
                current = dict(knowledge.get(product_id, {"id": product_id}))
                current["aliases"] = _dedupe_strings(alias_rows)
                knowledge[product_id] = current

    # A product with only an internal route and no public semantic description is
    # not useful provider context. Keep routed public families that Lingua knows,
    # and rich governed portfolio/campaign products.
    result: dict[str, dict[str, Any]] = {}
    for product_id, row in knowledge.items():
        if not isinstance(row, Mapping):
            continue
        if not any(row.get(field) for field in ("name", "one_liner", "promise", "artifact_types")):
            continue
        clean = dict(row)
        clean["id"] = product_id
        result[product_id] = clean
    return result


def _terms(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("id", "name", "one_liner", "pain", "promise", "offer", "cta", "risk_boundary"):
        value = _normalized(row.get(field))
        if value:
            values.append(value)
    for field in ("keywords", "route_keywords", "aliases", "artifact_types", "expected_outputs"):
        for item in row.get(field) or []:
            value = _normalized(item)
            if value:
                values.append(value)
    return values


def _score_product(text: str, row: Mapping[str, Any], state: Mapping[str, Any]) -> float:
    query = _normalized(text)
    if not query:
        return 0.0
    tokens = set(re.findall(r"[a-z0-9]+", query))
    score = 0.0

    product_id = _normalized(row.get("id"))
    name = _normalized(row.get("name"))
    identifiers = [product_id, product_id.replace("_", " "), name]
    identifiers.extend(_normalized(value) for value in row.get("aliases") or [])
    for identifier in identifiers:
        if identifier and identifier in query:
            score += 12.0

    for keyword in row.get("route_keywords") or []:
        normalized_keyword = _normalized(keyword)
        if not normalized_keyword:
            continue
        if normalized_keyword in query:
            score += 4.0 + min(3.0, float(len(normalized_keyword.split())))
        else:
            keyword_tokens = set(re.findall(r"[a-z0-9]+", normalized_keyword))
            score += 0.75 * len(tokens & keyword_tokens)

    semantic_tokens: set[str] = set()
    for term in _terms(row):
        semantic_tokens.update(re.findall(r"[a-z0-9]+", term))
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
        "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "to", "what",
        "with", "you", "your",
    }
    score += 0.35 * len((tokens - stop) & (semantic_tokens - stop))

    selected = _normalized(state.get("selected_product")) if isinstance(state, Mapping) else ""
    candidates = {
        _normalized(item)
        for item in (state.get("candidate_products") or [])
        if isinstance(state, Mapping)
    }
    if selected and selected == product_id:
        score += 2.5
    if product_id in candidates:
        score += 1.0
    return score


def retrieve_conversation_knowledge(
    root: Path,
    text: str,
    state: Mapping[str, Any],
    *,
    limit: int = 4,
) -> dict[str, Any]:
    catalog = load_public_product_knowledge(Path(root))
    ranked = [
        (product_id, _score_product(text, row, state), row)
        for product_id, row in catalog.items()
    ]
    ranked.sort(key=lambda item: (-item[1], int(item[2].get("route_priority", 9999)), item[0]))

    positive = [dict(row, retrieval_score=round(score, 4)) for _, score, row in ranked if score > 0]
    products = positive[: max(1, int(limit))]

    portfolio = _read_json(Path(root) / "config" / "dio_product_portfolio.json", {})
    truth_boundary = "Public product knowledge is descriptive context only and creates no execution authority."
    if isinstance(portfolio, Mapping) and _clean_text(portfolio.get("truth_boundary")):
        truth_boundary = _clean_text(portfolio.get("truth_boundary"))

    return {
        "schema": "dio.vesper.conversation_knowledge.v1",
        "products": products,
        "truth_boundary": truth_boundary,
        "authority_created": False,
    }


def _mentions_product(text: str, row: Mapping[str, Any]) -> bool:
    query = _normalized(text)
    if not query:
        return False
    identifiers = [
        _normalized(row.get("id")),
        _normalized(row.get("id")).replace("_", " "),
        _normalized(row.get("name")),
    ]
    identifiers.extend(_normalized(value) for value in row.get("aliases") or [])
    return any(identifier and identifier in query for identifier in identifiers)


def resolve_knowledge_answer(
    text: str,
    knowledge: Mapping[str, Any],
) -> dict[str, Any] | None:
    rows = knowledge.get("products") or []
    if not isinstance(rows, list):
        return None
    mentioned = [row for row in rows if isinstance(row, Mapping) and _mentions_product(text, row)]
    if len(mentioned) != 1:
        return None

    row = mentioned[0]
    product_id = _clean_text(row.get("id"))
    name = _clean_text(row.get("name")) or product_id.replace("_", " ").title()
    parts: list[str] = []
    one_liner = _clean_text(row.get("one_liner"))
    promise = _clean_text(row.get("promise"))
    artifacts = _dedupe_strings(row.get("artifact_types"))
    boundary = _clean_text(row.get("risk_boundary"))

    if one_liner:
        parts.append(f"{name}: {one_liner}")
    elif promise:
        parts.append(f"{name}: {promise}")
    else:
        return None
    if artifacts:
        readable = ", ".join(item.replace("_", " ") for item in artifacts[:5])
        parts.append(f"Its governed Lingua route covers {readable}.")
    if boundary:
        parts.append(boundary)

    return {
        "schema": "dio.vesper.conversation_resolution.v1",
        "reply": " ".join(parts),
        "conversation_act": "explain",
        "interpreted_need": None,
        "candidate_products": [product_id],
        "confidence": 0.95,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": None,
        "source": "knowledge",
        "authority_created": False,
    }
