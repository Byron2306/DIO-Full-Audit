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


def commercial_semantic_object_for_vendor_rfq(
    campaign: dict[str, Any],
    partner: dict[str, Any],
) -> dict[str, Any]:
    campaign_id = str(campaign.get("campaign_id") or campaign.get("id") or "").strip()
    partner_id = str(partner.get("id") or "").strip()
    if not campaign_id or not partner_id:
        raise ValueError("vendor RFQ bridge requires campaign and partner identifiers")

    campaign_ref = f"campaign:{campaign_id}"
    vendor_ref = f"vendor:{partner_id}"
    source_refs = [campaign_ref, vendor_ref]
    product = str(campaign.get("name") or campaign.get("product_name") or campaign.get("product_line_id") or "").strip()
    vendor = str(partner.get("name") or partner_id).strip()
    inquiry = partner.get("inquiry") or {}
    permission = str(inquiry.get("permission") or "").strip()
    route_mode = str(inquiry.get("mode") or "").strip()
    route_verified = partner.get("status") == "public_route_verified" and permission == "single_rfq_only"
    now = timestamp()

    result = {
        "schema": SCHEMA,
        "object_id": stable_semantic_object_id(campaign_id, partner_id, product, route_mode),
        "created_at": now,
        "updated_at": now,
        "lineage": {
            "lead_id": None,
            "conversation_id": None,
            "transaction_id": None,
            "prospect_id": partner_id,
            "campaign_id": campaign_id,
            "hypothesis_id": None,
            "opportunity_id": None,
        },
        "subject": {
            "organisation": semantic_value(vendor, status="verified", source_refs=[vendor_ref], authority="vendor_catalog"),
            "buyer_role": semantic_value(status="unknown"),
            "organisation_type": semantic_value("media_or_marketing_vendor", status="verified", source_refs=[vendor_ref], authority="vendor_catalog"),
            "relationship_state": semantic_value("vendor", status="verified", source_refs=[vendor_ref], authority="vendor_catalog"),
            "consent_state": semantic_value(
                "single_rfq_public_route" if route_verified else "rfq_route_not_authorised",
                status="verified",
                source_refs=[vendor_ref],
                authority="vendor_route_gate",
            ),
        },
        "truth": {
            "verified_facts": [
                semantic_claim(f"campaign: {campaign_id}", status="verified", source_refs=[campaign_ref], authority="campaign_record"),
                semantic_claim(f"vendor: {vendor}", status="verified", source_refs=[vendor_ref], authority="vendor_catalog"),
                semantic_claim(f"RFQ permission state: {permission or 'not recorded'}", status="verified", source_refs=[vendor_ref], authority="vendor_route_gate"),
            ],
            "inferred_hypotheses": [],
            "unknowns": [
                unknown("commercial.scope", "Vendor scope remains open until a placement is selected for the RFQ.", source_refs=source_refs),
                unknown("commercial.price", "The purpose of the RFQ is to obtain vendor pricing.", source_refs=source_refs),
            ],
        },
        "need": {
            "job_to_be_done": semantic_value(status="unknown"),
            "workflow_pain": semantic_value(status="unknown"),
            "trigger": semantic_value(status="unknown"),
            "why_now": semantic_value(status="unknown"),
        },
        "commercial": {
            "product": semantic_value(product, status="verified", source_refs=[campaign_ref], authority="campaign_record") if product else semantic_value(status="unknown"),
            "offer": semantic_value("bounded measurable media pilot", status="inferred", source_refs=[campaign_ref], authority="strategy_only", method="rfq_strategy"),
            "scope": semantic_value(status="unknown"),
        },
        "proof": {
            "relevant_proof": [],
            "permitted_claims": ["campaign_identity", "vendor_identity", "request_for_quotation_only"],
            "prohibited_claims": ["spend_authorised", "booking_confirmed", "vendor_selected", "price_agreed"],
        },
        "strategy": {
            "desired_next_action": semantic_value("return an itemised quotation", status="inferred", source_refs=source_refs, authority="strategy_only", method="rfq_strategy"),
            "channel": semantic_value(route_mode or "email", status="verified", source_refs=[vendor_ref], authority="vendor_route_gate"),
            "communicative_act": semantic_value("request_for_quotation", status="inferred", source_refs=source_refs, authority="strategy_only", method="rfq_strategy"),
            "tone": semantic_value(status="unknown"),
            "length": semantic_value(status="unknown"),
            "rhetorical_strategy": semantic_value("bounded quotation request without spend authority", status="inferred", source_refs=source_refs, authority="strategy_only", method="rfq_strategy"),
        },
        "authority": {
            "authority_state": "vendor_public_rfq_route" if route_verified else "research_only",
            "evidence_refs": source_refs,
            "attribution": {
                "campaign_id": campaign_id,
                "vendor_id": partner_id,
                "route_mode": route_mode,
                "permission": permission,
            },
        },
        "provenance": {
            "adapter": "commerce.vendor_bridge.commercial_semantic_object_for_vendor_rfq",
            "adapter_version": 1,
            "source_schema": "dio.market_command.vendor_rfq_context.v1",
            "source_ref": vendor_ref,
        },
    }
    assert_valid_commercial_semantic_object(result)
    return result
