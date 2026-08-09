from __future__ import annotations

import re
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


EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
ELIGIBLE_PERMISSION_ROUTES = {
    "PARTNERSHIP_ROUTE_AVAILABLE",
    "INSTITUTIONAL_ROUTE_AVAILABLE",
    "PUBLIC_ROUTE_PRESENT_REVERIFY_ROLE",
}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _public_email(target: dict[str, Any]) -> str | None:
    for part in str(target.get("public_contact_route") or "").split(";"):
        candidate = part.strip().lower()
        if EMAIL_PATTERN.fullmatch(candidate):
            return candidate
    return None


def commercial_semantic_object_from_prospect_target(target: dict[str, Any]) -> dict[str, Any]:
    """Adapt one Wave 4 prospect target into a conservative target-level CSO.

    The prospect registry may establish a public organisation route and an internal
    targeting hypothesis. It does not establish customer need, consent to marketing,
    budget, agreed scope or a personal buyer identity.
    """
    target_id = _text(target.get("target_id"))
    if not target_id:
        raise ValueError("prospect target requires target_id")

    organisation = _text(target.get("organisation"))
    product_line_id = _text(target.get("product_line_id"))
    product_name = _text(target.get("product_name")) or product_line_id
    primary_offer = _text(target.get("primary_offer"))
    buyer_unit = _text(target.get("buyer_unit"))
    segment = _text(target.get("segment"))
    route_state = _text(target.get("route_state")) or "RESEARCH_ONLY"
    public_email = _public_email(target)
    do_not_contact = str(target.get("do_not_contact") or "").strip().lower() == "yes"
    route_eligible = route_state in ELIGIBLE_PERMISSION_ROUTES and bool(public_email) and not do_not_contact

    target_ref = f"prospect_target:{target_id}"
    route_ref = _text(target.get("contact_source"))
    source_refs = [target_ref] + ([route_ref] if route_ref else [])
    now = timestamp()

    consent_value = (
        "do_not_contact"
        if do_not_contact
        else "permission_not_yet_granted_once_off_request_only"
        if route_eligible
        else "research_only_no_direct_contact_authority"
    )
    authority_state = (
        "prospect_registry_once_off_permission_request"
        if route_eligible
        else "research_only"
    )

    verified_facts = [
        semantic_claim(
            f"prospect target id: {target_id}",
            status="verified",
            source_refs=[target_ref],
            authority="prospect_registry",
        )
    ]
    for label, value in (
        ("organisation in prospect registry", organisation),
        ("product line in prospect registry", product_line_id),
        ("public route state", route_state),
        ("public contact route", public_email),
    ):
        if value:
            verified_facts.append(
                semantic_claim(
                    f"{label}: {value}",
                    status="verified",
                    source_refs=source_refs,
                    authority="prospect_registry",
                )
            )

    inferred_hypotheses = []
    for statement, method in (
        (f"Suggested buyer unit: {buyer_unit}" if buyer_unit else None, "prospect_registry_targeting"),
        (f"Target segment: {segment}" if segment else None, "prospect_registry_segmentation"),
        (f"Candidate offer: {primary_offer}" if primary_offer else None, "prospect_registry_offer_mapping"),
    ):
        if statement:
            inferred_hypotheses.append(
                semantic_claim(
                    statement,
                    status="inferred",
                    source_refs=[target_ref],
                    authority="targeting_hypothesis_only",
                    method=method,
                )
            )

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "object_id": stable_semantic_object_id(target_id, organisation, product_line_id, public_email),
        "created_at": now,
        "updated_at": now,
        "lineage": {
            "lead_id": None,
            "conversation_id": None,
            "transaction_id": None,
            "prospect_id": target_id,
            "campaign_id": None,
            "hypothesis_id": None,
            "opportunity_id": None,
        },
        "subject": {
            "organisation": semantic_value(
                organisation,
                status="verified",
                source_refs=[target_ref],
                authority="prospect_registry",
            ) if organisation else semantic_value(status="unknown"),
            "buyer_role": semantic_value(
                buyer_unit,
                status="inferred",
                source_refs=[target_ref],
                authority="targeting_hypothesis_only",
                method="prospect_registry_targeting",
            ) if buyer_unit else semantic_value(status="unknown"),
            "organisation_type": semantic_value(
                segment,
                status="inferred",
                source_refs=[target_ref],
                authority="targeting_hypothesis_only",
                method="prospect_registry_segmentation",
            ) if segment else semantic_value(status="unknown"),
            "relationship_state": semantic_value(
                "cold",
                status="verified",
                source_refs=[target_ref],
                authority="prospect_registry",
            ),
            "consent_state": semantic_value(
                consent_value,
                status="verified",
                source_refs=source_refs,
                authority="prospect_route_gate",
            ),
        },
        "truth": {
            "verified_facts": verified_facts,
            "inferred_hypotheses": inferred_hypotheses,
            "unknowns": [
                unknown("need.job_to_be_done", "Targeting does not establish an actual customer job.", source_refs=[target_ref]),
                unknown("need.workflow_pain", "Targeting does not establish verified customer pain.", source_refs=[target_ref]),
                unknown("need.trigger", "No customer trigger is established by the prospect registry.", source_refs=[target_ref]),
                unknown("need.why_now", "No customer urgency is established by the prospect registry.", source_refs=[target_ref]),
                unknown("commercial.scope", "No scope exists before qualification.", source_refs=[target_ref]),
                unknown("customer.budget", "No budget is established by targeting data.", source_refs=[target_ref]),
            ],
        },
        "need": {
            "job_to_be_done": semantic_value(status="unknown"),
            "workflow_pain": semantic_value(status="unknown"),
            "trigger": semantic_value(status="unknown"),
            "why_now": semantic_value(status="unknown"),
        },
        "commercial": {
            "product": semantic_value(
                product_name,
                status="verified",
                source_refs=[target_ref],
                authority="prospect_registry",
            ) if product_name else semantic_value(status="unknown"),
            "offer": semantic_value(
                primary_offer,
                status="inferred",
                source_refs=[target_ref],
                authority="targeting_hypothesis_only",
                method="prospect_registry_offer_mapping",
            ) if primary_offer else semantic_value(status="unknown"),
            "scope": semantic_value(status="unknown"),
        },
        "proof": {
            "relevant_proof": [],
            "permitted_claims": [
                "public_organisation_identity",
                "public_route_identity",
                "configured_product_name",
                "once_off_permission_request" if route_eligible else "research_only",
            ],
            "prohibited_claims": [
                "verified_customer_need",
                "verified_customer_workflow_pain",
                "customer_urgency",
                "customer_budget",
                "agreed_scope",
                "customer_consent_to_marketing",
                "personal_buyer_identity",
            ],
        },
        "strategy": {
            "desired_next_action": semantic_value(
                "request permission to send one proof example",
                status="inferred",
                source_refs=[target_ref],
                authority="strategy_only",
                method="cold_permission_contract",
            ),
            "channel": semantic_value(
                "email",
                status="verified",
                source_refs=source_refs,
                authority="public_route",
            ) if public_email else semantic_value(status="unknown"),
            "communicative_act": semantic_value(
                "cold_permission_request",
                status="inferred",
                source_refs=[target_ref],
                authority="strategy_only",
                method="cold_permission_contract",
            ),
            "tone": semantic_value(status="unknown"),
            "length": semantic_value(status="unknown"),
            "rhetorical_strategy": semantic_value(
                "low-assumption permission request",
                status="inferred",
                source_refs=[target_ref],
                authority="strategy_only",
                method="cold_permission_contract",
            ),
        },
        "authority": {
            "authority_state": authority_state,
            "evidence_refs": source_refs,
            "attribution": {
                "target_id": target_id,
                "route_state": route_state,
                "public_email": public_email,
                "contact_source": route_ref,
                "do_not_contact": do_not_contact,
            },
        },
        "provenance": {
            "adapter": "commerce.prospect_bridge.commercial_semantic_object_from_prospect_target",
            "adapter_version": 1,
            "source_schema": target.get("schema") or "dio.prospect_intelligence.wave4.target",
            "source_ref": target_ref,
        },
    }
    assert_valid_commercial_semantic_object(result)
    return result
