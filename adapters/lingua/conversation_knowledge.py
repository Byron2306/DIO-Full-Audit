from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


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
            "one_liner": one_liner,
            "risk_boundary": risk_boundary,
            "authority_created": False,
            "source": "atlas_crosswalk+routes",
        }

    return knowledge


def _mentioned_product(text: str, knowledge: dict[str, dict[str, Any]]) -> str | None:
    value = str(text or "").lower()
    compact = _norm(value)
    for product, record in knowledge.items():
        labels = [product, record.get("label", "")]
        if any(_norm(label) and _norm(label) in compact for label in labels):
            return product
    return None


def answer_from_governed_knowledge(
    text: str,
    knowledge: dict[str, dict[str, Any]],
    *,
    provider: Callable[..., Any] | None = None,
) -> dict[str, Any] | None:
    product = _mentioned_product(text, knowledge)
    if product is None:
        return None

    value = str(text or "").lower()
    explanation_markers = ("what is", "what does", "explain", "tell me", "about", "can you describe", "who is")
    if not any(marker in value for marker in explanation_markers):
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
        "candidate_products": [product],
        "confidence": 1.0,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": None,
        "source": "knowledge",
        "authority_created": False,
    }
