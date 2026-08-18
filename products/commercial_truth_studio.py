from __future__ import annotations

from typing import Any

from products.commercial_truth import evaluate_product, load_config


DEFAULT_EVENTS = [
    "studio_job_routed",
    "controlled_artifact_generated",
    "human_review_requested",
]


def evaluate_studio_truth(*, studio_id: str, root, events: list[str] | None = None) -> dict[str, Any]:
    config = load_config(root)
    evaluation = evaluate_product(studio_id, [], config)
    claims = evaluation.get("claims") or {}
    if any(value != "UNKNOWN" for value in claims.values()):
        raise RuntimeError("Commercial Truth inflated an unobserved Studio into market truth")
    if evaluation.get("authority_created") or evaluation.get("external_release_authorized"):
        raise RuntimeError("Commercial Truth created forbidden Studio authority")
    chosen = list(events or DEFAULT_EVENTS)
    if not chosen or any(not str(event).strip() for event in chosen):
        raise ValueError("Studio measurement contract requires named events")
    contract = {
        "schema": "dio.commercial_measurement_contract.v1",
        "product_id": studio_id,
        "events": [{"event": str(event), "claim_ceiling": "OBSERVED"} for event in chosen],
        "unsupported_inferences": [
            "qualified demand",
            "verified payment",
            "attributed revenue",
            "customer value",
            "repeatability",
            "economic proof",
            "market validation",
        ],
        "payment_enabled": False,
        "revenue_claimed": False,
        "market_validation_claimed": False,
        "maturity_changed": False,
        "authority_created": False,
        "external_release_authorized": False,
        "source_engine": "commercial_truth",
        "capability_executed": "commercial.measurement.contract",
    }
    return {
        "schema": "dio.commercial_truth_studio_receipt.v1",
        "studio_id": studio_id,
        "evaluation": evaluation,
        "measurement_contract": contract,
        "capabilities_executed": ["commercial.claim.boundary", "commercial.measurement.contract"],
        "authority_created": False,
        "external_release_authorized": False,
    }
