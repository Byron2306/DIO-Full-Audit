from __future__ import annotations

from typing import Any

from commerce.expression_guarded import CommunicativeAct, render_expression
from commerce.vendor_bridge import commercial_semantic_object_for_vendor_rfq
from scripts.dio_mail_branding import MAIN_SITE, branded_email


def mail_copy(campaign: dict[str, Any], partner: dict[str, Any], placement: str) -> tuple[str, str, str]:
    cso = commercial_semantic_object_for_vendor_rfq(campaign, partner)
    campaign_id = str(campaign.get("campaign_id") or campaign.get("id") or "")
    campaign_ref = f"campaign:{campaign_id}"
    vendor_ref = f"vendor:{partner.get('id')}"
    expression = render_expression(
        cso,
        CommunicativeAct.REQUEST_FOR_QUOTATION,
        context={
            "verified_context": {
                "audience": {
                    "value": campaign.get("audience") or "audience defined in attached brief",
                    "source_refs": [campaign_ref],
                },
                "objective": {
                    "value": campaign.get("objective") or "a measurable bounded pilot",
                    "source_refs": [campaign_ref],
                },
                "placement": {
                    "value": placement or "the most suitable measurable placement for this audience",
                    "source_refs": [campaign_ref, vendor_ref],
                },
            }
        },
    )
    body, body_html = branded_email(
        product="dio",
        eyebrow="MEDIA PILOT RFQ",
        headline="Request for a measurable South African campaign pilot.",
        greeting=f"Hello {partner['name']} team,",
        intro=expression["intro"],
        body=list(expression["paragraphs"]),
        reference=campaign_id,
        cta_label="View DIO Workflows",
        cta_url=MAIN_SITE,
        bullets=["Measured pilots", "Human spend approval", "Attribution before scale"],
        caution="This is a request for quotation only. It is not a booking, insertion order or spend authorisation.",
    )
    return str(expression["subject"]), body, body_html
