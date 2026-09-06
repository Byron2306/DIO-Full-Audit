from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _topic_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _split_patterns(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _family_tokens(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split("+") if part.strip()]


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        value = str(value).strip()
        if value and value not in out:
            out.append(value)
    return out


def _route_label(product: str) -> str:
    special = {
        "homs": "HOMS",
        "evidex": "Evidex",
        "sophia": "Sophia",
        "vamp": "VAMP",
        "document_studio": "Document Studio",
        "nichefoundry": "NicheFoundry",
    }
    return special.get(product, product.replace("_", " ").title())


def _load_class_routes(root: Path) -> dict[str, Any]:
    path = root / "config" / "product_class_routes.json"
    if not path.is_file():
        return {"direct_products": {}, "product_classes": {}, "aliases": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "direct_products": dict(payload.get("direct_products") or {}),
        "product_classes": dict(payload.get("product_classes") or {}),
        "aliases": dict(payload.get("aliases") or {}),
    }


def _topic_route(topic_id: str, family: str, class_routes: dict[str, Any]) -> tuple[str | None, bool, str | None]:
    aliases = class_routes["aliases"]
    direct = class_routes["direct_products"]
    classes = class_routes["product_classes"]

    if topic_id in aliases:
        target = str(aliases[topic_id])
        spec = direct.get(target) or classes.get(target) or {}
        route = str(spec.get("engine") or spec.get("suggested_engine") or target).strip() or None
        return route, bool(spec.get("auto_promotable", False)), str(spec.get("route_kind") or "alias")

    if topic_id in classes:
        spec = classes[topic_id]
        route = str(spec.get("suggested_engine") or "").strip() or None
        return route, bool(spec.get("auto_promotable", False)), str(spec.get("route_kind") or "product_class")

    if topic_id in direct:
        spec = direct[topic_id]
        route = str(spec.get("engine") or topic_id).strip() or None
        return route, bool(spec.get("auto_promotable", False)), str(spec.get("route_kind") or "direct")

    family_norm = _norm(family)
    for product, spec in direct.items():
        if _norm(product) == family_norm:
            route = str(spec.get("engine") or product).strip() or None
            return route, bool(spec.get("auto_promotable", False)), str(spec.get("route_kind") or "family")
    return None, False, None


def load_public_product_knowledge(root: Path) -> dict[str, dict[str, Any]]:
    atlas_path = root / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
    routes_path = root / "config" / "routes.json"
    if not atlas_path.is_file():
        raise FileNotFoundError(atlas_path)
    if not routes_path.is_file():
        raise FileNotFoundError(routes_path)

    with atlas_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    routes = json.loads(routes_path.read_text(encoding="utf-8")).get("routes") or []
    class_routes = _load_class_routes(root)

    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for family in _family_tokens(row.get("primary_family", "")):
            by_family[_norm(family)].append(row)

    knowledge: dict[str, dict[str, Any]] = {}
    for route in routes:
        product = str(route.get("product") or "").strip()
        if not product:
            continue
        route_norm = _norm(product)
        candidates = list(by_family.get(route_norm, []))

        if not candidates:
            stripped = route_norm[3:] if route_norm.startswith("dio") else route_norm
            for row in rows:
                incarnation_norm = _norm(row.get("incarnation", ""))
                if stripped and (incarnation_norm == stripped or incarnation_norm.endswith(stripped)):
                    candidates.append(row)

        if not candidates:
            continue

        incarnations = _unique([row.get("incarnation", "") for row in candidates])
        suites = _unique([row.get("suite", "") for row in candidates])
        maturity = _unique([row.get("source_maturity", "") for row in candidates])
        truth_classes = _unique([row.get("execution_truth_class", "") for row in candidates])
        patterns: list[str] = []
        for row in candidates:
            patterns.extend(_split_patterns(row.get("source_work_patterns", "")))
        patterns = _unique(patterns)

        label = _route_label(product)
        suite = suites[0] if len(suites) == 1 else ", ".join(suites)
        one_liner = (
            f"{label} is a DIO {suite} path covering "
            + (", ".join(patterns) if patterns else "the governed work represented in ATLAS")
            + "."
        )
        risk_boundary = (
            "ATLAS maturity: "
            + ", ".join(maturity)
            + ". This public description creates no send, spend, payment, fulfilment, "
              "publication, professional, or external-action authority and does not imply market validation."
        )
        knowledge[product] = {
            "product": product,
            "label": label,
            "suite": suite,
            "incarnations": incarnations,
            "work_patterns": patterns,
            "maturity_states": maturity,
            "execution_truth_classes": truth_classes,
            "route_keywords": _unique(list(route.get("keywords") or [])),
            "approval_required": bool(route.get("approval_required", True)),
            "route_auto_promotable": bool((class_routes["direct_products"].get(product) or {}).get("auto_promotable", False)),
            "one_liner": one_liner,
            "risk_boundary": risk_boundary,
            "authority_created": False,
            "source": "atlas_crosswalk+routes",
        }

    topics: dict[str, dict[str, Any]] = {}
    for row in rows:
        topic = _topic_id(row.get("incarnation", ""))
        if not topic:
            continue
        route_product, auto_promotable, route_kind = _topic_route(
            topic,
            row.get("primary_family", ""),
            class_routes,
        )
        topics[topic] = {
            "id": topic,
            "name": str(row.get("incarnation") or ""),
            "suite": str(row.get("suite") or ""),
            "primary_family": str(row.get("primary_family") or ""),
            "work_patterns": _split_patterns(row.get("source_work_patterns", "")),
            "source_maturity": str(row.get("source_maturity") or ""),
            "execution_truth_class": str(row.get("execution_truth_class") or ""),
            "route_product": route_product,
            "route_auto_promotable": auto_promotable,
            "route_kind": route_kind,
            "notes": str(row.get("notes") or ""),
            "authority_created": False,
        }
    knowledge["_topics"] = topics
    return knowledge


def _mentioned_topic(text: str, knowledge: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    value = str(text or "").lower()
    matches = []
    for topic in (knowledge.get("_topics") or {}).values():
        name = str(topic.get("name") or "").strip()
        if name and name.lower() in value:
            matches.append(topic)
    if not matches:
        return None
    return max(matches, key=lambda item: len(str(item.get("name") or "")))


def _mentioned_product(text: str, knowledge: dict[str, dict[str, Any]]) -> str | None:
    compact = _norm(text)
    for product, record in knowledge.items():
        if product.startswith("_"):
            continue
        labels = [product, record.get("label", "")]
        if any(_norm(label) and _norm(label) in compact for label in labels):
            return product
    return None


def _is_explanation_question(text: str) -> bool:
    value = str(text or "").lower()
    markers = ("what is", "what does", "explain", "tell me", "about", "can you describe", "who is")
    return any(marker in value for marker in markers)


def answer_from_governed_knowledge(
    text: str,
    knowledge: dict[str, dict[str, Any]],
    *,
    provider: Callable[..., Any] | None = None,
) -> dict[str, Any] | None:
    if not _is_explanation_question(text):
        return None

    topic = _mentioned_topic(text, knowledge)
    if topic is not None:
        patterns = ", ".join(topic["work_patterns"]) or "governed DIO work"
        route_product = topic.get("route_product")
        route_note = (
            f"It maps to the {route_product} route for discussion."
            if route_product
            else "It does not currently map to an automatic public route."
        )
        if route_product and not topic.get("route_auto_promotable"):
            route_note += " That mapping is explanatory only and is not auto-promotable into execution."
        reply = (
            f"{topic['name']} is a {topic['suite']} incarnation covering {patterns}. "
            f"ATLAS currently records its maturity as {topic['source_maturity']}. {route_note} "
            "This explanation creates no external-action authority."
        )
        return {
            "schema": "dio.vesper.conversation_resolution.v1",
            "reply": reply,
            "conversation_act": "explain",
            "interpreted_need": None,
            "current_topic": topic["id"],
            "candidate_products": [route_product] if route_product else [],
            "confidence": 1.0,
            "clarification_needed": False,
            "clarification_question": None,
            "action_intent": "none",
            "action_product": None,
            "route_auto_promotable": bool(topic.get("route_auto_promotable")),
            "source": "knowledge",
            "authority_created": False,
        }

    product = _mentioned_product(text, knowledge)
    if product is None:
        return None
    item = knowledge[product]
    incarnations = item["incarnations"]
    if len(incarnations) <= 5:
        incarnation_text = ", ".join(incarnations)
    else:
        incarnation_text = ", ".join(incarnations[:5]) + f", and {len(incarnations) - 5} more"
    maturity_text = ", ".join(item["maturity_states"])
    reply = (
        f"{item['one_liner']} Canonical incarnations include {incarnation_text}. "
        f"Current ATLAS maturity states: {maturity_text}. "
        "I can explain one of those incarnations, compare options, or help you describe the problem you need solved. "
        "Nothing in this explanation authorizes an external action."
    )
    return {
        "schema": "dio.vesper.conversation_resolution.v1",
        "reply": reply,
        "conversation_act": "explain",
        "interpreted_need": None,
        "current_topic": product,
        "candidate_products": [product],
        "confidence": 1.0,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": None,
        "route_auto_promotable": bool(item.get("route_auto_promotable", False)),
        "source": "knowledge",
        "authority_created": False,
    }
