from __future__ import annotations

from typing import Any

from .semantic import (
    SCHEMA,
    assert_valid_commercial_semantic_object,
    semantic_claim,
    semantic_value,
    stable_semantic_object_id,
    timestamp,
    unknown,
)


PRODUCT_NAMES = {
    "homs": "HOMS Assessment Desk",
    "evidex": "Evidex Evidence Packs",
}


def commercial_semantic_object_from_product_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    job_id = str(workflow.get("job_id") or "").strip()
    product_key = str(workflow.get("product") or "").strip().lower()
    if not job_id or product_key not in PRODUCT_NAMES:
        raise ValueError("product workflow bridge requires a supported product and job_id")

    product = PRODUCT_NAMES[product_key]
    job_ref = f"product_job:{job_id}"
    source_path = str(workflow.get("source_job_path") or "").strip()
    source_refs = [job_ref] + ([f"source_job:{source_path}"] if source_path else [])
    processing = workflow.get("processing") or {}
    output_review = workflow.get("output_review") or {}
    recipient = str((workflow.get("customer") or {}).get("recipient") or "").strip()
    if product_key == "homs":
        act = "intake_request"
        ready = processing.get("state") == "request_ready"
        authority_state = "workflow_intake_notification_ready" if ready and recipient else "research_only"
    else:
        act = "delivery"
        ready = output_review.get("state") == "approved"
        authority_state = "reviewed_delivery_ready" if ready and recipient else "research_only"

    now = timestamp()
    result = {
        "schema": SCHEMA,
        "object_id": stable_semantic_object_id(job_id, product_key, recipient, act),
        "created_at": now,
        "updated_at": now,
        "lineage": {
            "lead_id": None,
            "conversation_id": None,
            "transaction_id": job_id,
            "prospect_id": None,
            "campaign_id": None,
            "hypothesis_id": None,
            "opportunity_id": None,
        },
        "subject": {
            "organisation": semantic_value(status="unknown"),
            "buyer_role": semantic_value(status="unknown"),
            "organisation_type": semantic_value(status="unknown"),
            "relationship_state": semantic_value("active_product_workflow", status="verified", source_refs=[job_ref], authority="workflow_state"),
            "consent_state": semantic_value(
                "workflow_notification_authorized" if ready and recipient else "workflow_notification_held",
                status="verified",
                source_refs=[job_ref],
                authority="workflow_state",
            ),
        },
        "truth": {
            "verified_facts": [
                semantic_claim(f"product workflow: {job_id}", status="verified", source_refs=[job_ref], authority="workflow_state"),
                semantic_claim(f"product: {product}", status="verified", source_refs=[job_ref], authority="workflow_state"),
                semantic_claim(f"processing state: {processing.get('state')}", status="verified", source_refs=[job_ref], authority="workflow_state"),
                semantic_claim(f"output review state: {output_review.get('state')}", status="verified", source_refs=[job_ref], authority="workflow_state"),
            ],
            "inferred_hypotheses": [],
            "unknowns": [
                unknown("need.workflow_pain", "Notification rendering does not require or infer customer pain.", source_refs=[job_ref]),
                unknown("customer.budget", "Product notification does not establish budget information.", source_refs=[job_ref]),
            ],
        },
        "need": {
            "job_to_be_done": semantic_value(status="unknown"),
            "workflow_pain": semantic_value(status="unknown"),
            "trigger": semantic_value(status="unknown"),
            "why_now": semantic_value(status="unknown"),
        },
        "commercial": {
            "product": semantic_value(product, status="verified", source_refs=[job_ref], authority="workflow_state"),
            "offer": semantic_value(status="unknown"),
            "scope": semantic_value(status="unknown"),
        },
        "proof": {
            "relevant_proof": [value for value in [processing.get("receipt_path"), processing.get("output_dir")] if value],
            "permitted_claims": ["workflow_reference", "product_identity", "recorded_processing_state", "recorded_review_state"],
            "prohibited_claims": ["new_customer_need", "guaranteed_outcome", "new_scope", "new_price", "unreviewed_delivery"],
        },
        "strategy": {
            "desired_next_action": semantic_value(
                "supply required source material" if act == "intake_request" else "inspect delivery and request revision if needed",
                status="inferred",
                source_refs=[job_ref],
                authority="strategy_only",
                method="workflow_notification_state",
            ),
            "channel": semantic_value("email", status="verified", source_refs=[job_ref], authority="workflow_state"),
            "communicative_act": semantic_value(act, status="inferred", source_refs=[job_ref], authority="strategy_only", method="workflow_notification_state"),
            "tone": semantic_value(status="unknown"),
            "length": semantic_value(status="unknown"),
            "rhetorical_strategy": semantic_value(
                "request only required material" if act == "intake_request" else "announce only the approved delivery state",
                status="inferred",
                source_refs=[job_ref],
                authority="strategy_only",
                method="workflow_notification_state",
            ),
        },
        "authority": {
            "authority_state": authority_state,
            "evidence_refs": source_refs,
            "attribution": {
                "job_id": job_id,
                "product": product_key,
                "recipient_present": bool(recipient),
                "processing_state": processing.get("state"),
                "output_review_state": output_review.get("state"),
            },
        },
        "provenance": {
            "adapter": "commerce.workflow_bridge.commercial_semantic_object_from_product_workflow",
            "adapter_version": 1,
            "source_schema": workflow.get("schema") or "dio.product_workflow.v1",
            "source_ref": job_ref,
        },
    }
    assert_valid_commercial_semantic_object(result)
    return result
