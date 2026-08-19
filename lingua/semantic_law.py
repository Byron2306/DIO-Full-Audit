from __future__ import annotations

import hashlib
import json
from typing import Any

SEMANTIC_LAW_SCHEMA = "dio.lingua.semantic_law.v1"

DEFAULT_PROHIBITIONS = [
    "invented_customer_result",
    "invented_certification_or_approval",
    "market_demand_claim_without_observed_evidence",
    "guaranteed_outcome",
    "authority_transfer",
    "automatic_publication_or_spend",
    "claim_stronger_than_source_bound_product_promise",
]

PROJECTION_MUTABLE_FIELDS = [
    "story_arc",
    "scene_count",
    "hook_style",
    "tone",
    "pacing",
    "visual_grammar",
    "narrator_profile",
    "music_family",
    "motion_grammar",
    "cta_expression",
]

PROJECTION_INVARIANTS = [
    "product_identity",
    "source_bound_promise",
    "source_bound_proof",
    "human_authority",
    "publication_held",
    "spend_disabled",
    "market_validation_not_claimed",
]


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_semantic_law(product: dict[str, Any], audience: dict[str, Any]) -> dict[str, Any]:
    """Bind M1 denotation/affordance/prohibition/projection law to one campaign family."""
    source = {
        "product_id": str(product.get("id") or ""),
        "product_name": str(product.get("name") or ""),
        "offer": str(product.get("offer") or ""),
        "promise": str(product.get("promise") or ""),
        "proof": str(product.get("proof") or ""),
        "cta": str(product.get("cta") or ""),
        "audience_id": str(audience.get("id") or ""),
        "audience_name": str(audience.get("name") or ""),
        "audience_pain": str(audience.get("pain") or ""),
        "audience_outcome": str(audience.get("outcome") or ""),
    }
    source_hash = _canonical_hash(source)
    core = {
        "schema": SEMANTIC_LAW_SCHEMA,
        "source_hash": source_hash,
        "denotation": {
            "product_id": source["product_id"],
            "product_name": source["product_name"],
            "offer": source["offer"],
            "audience_id": source["audience_id"],
            "audience_name": source["audience_name"],
        },
        "affordance": {
            "source_bound_promise": source["promise"],
            "source_bound_proof": source["proof"],
            "bounded_outcome": source["audience_outcome"],
            "cta_intent": source["cta"],
        },
        "prohibition": {
            "rules": list(DEFAULT_PROHIBITIONS),
            "publication_authorized": False,
            "spend_authorized": False,
            "market_validation_claimed": False,
            "authority_created": False,
        },
        "projection": {
            "mutable_fields": list(PROJECTION_MUTABLE_FIELDS),
            "must_preserve": list(PROJECTION_INVARIANTS),
            "law": "same meaning, different lawful skin",
        },
        "source": source,
    }
    return {**core, "semantic_law_hash": _canonical_hash(core)}


def validate_projection(law: dict[str, Any], projection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if law.get("schema") != SEMANTIC_LAW_SCHEMA:
        errors.append("LINGUA semantic law schema is not recognised")
    if projection.get("semantic_law_hash") != law.get("semantic_law_hash"):
        errors.append("Projection is not bound to the current semantic law hash")
    if projection.get("source_hash") != law.get("source_hash"):
        errors.append("Projection source hash does not match the semantic law source")
    governance = projection.get("governance") or {}
    if governance.get("publication") != "held":
        errors.append("Projection must keep publication held")
    if governance.get("spend") != "disabled":
        errors.append("Projection must keep spend disabled")
    if governance.get("market_validation_claimed") is not False:
        errors.append("Projection must not claim market validation")
    if governance.get("authority_created") is not False:
        errors.append("Projection must not create authority")
    preserved = set(projection.get("preserves") or [])
    missing = [item for item in PROJECTION_INVARIANTS if item not in preserved]
    if missing:
        errors.append("Projection omitted semantic invariants: " + ", ".join(missing))
    return errors
