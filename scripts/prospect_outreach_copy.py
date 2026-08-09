from __future__ import annotations

from typing import Any

from commerce.expression import CommunicativeAct, render_expression
from commerce.prospect_bridge import commercial_semantic_object_from_prospect_target
from scripts.dio_mail_branding import MAIN_SITE, branded_email, product_profile, reply_link


PRODUCT_KEY_BY_LINE = {
    "HOMS_ASSESS": "homs",
    "HOMS_LEARN": "homs_learning",
    "SOPHIA_LEARN": "sophia",
    "SOPHIA_REVIEW": "sophia",
    "EVIDEX": "evidex",
    "EVIDEX_PACK": "evidex",
    "VAMP": "vamp",
    "VAMP_ACADEMIC": "vamp",
    "DOCUMENT_STUDIO": "document_studio",
}


def product_key_for_target(target: dict[str, Any]) -> str:
    return PRODUCT_KEY_BY_LINE.get(str(target.get("product_line_id") or ""), "dio")


def message_for(target: dict[str, Any]) -> tuple[str, str, str]:
    """Compose cold prospect outreach through the C3 communicative-act contract.

    Product branding remains a presentation concern. All rhetorical choices and the
    cold-contact assumption boundary come from the Commercial Semantic Object and the
    `cold_permission_request` act contract.
    """
    cso = commercial_semantic_object_from_prospect_target(target)
    expression = render_expression(cso, CommunicativeAct.COLD_PERMISSION_REQUEST)

    organisation = str(target.get("organisation") or "the organisation")
    product_key = product_key_for_target(target)
    profile = product_profile(product_key)
    product = profile["name"]

    yes_url = reply_link(
        f"YES - {product} proof example",
        f"YES, {organisation} consents to receive one {product} proof example by email.\n\nPreferred contact method: Email",
    )
    no_url = reply_link(
        f"NO - {product} outreach",
        f"NO, {organisation} does not consent to receive marketing about {product}. Please record this preference.",
    )

    body_parts = [
        expression["greeting"],
        expression["intro"],
        *expression["paragraphs"],
        expression["cta"],
        expression.get("secondary_cta"),
        f"DIO Workflows: {MAIN_SITE}",
        f"{product}: {profile['url']}",
        expression.get("caution"),
        "Regards,\nByron Bunt\nDIO Workflows\ndio_workflows@outlook.com",
    ]
    body = "\n\n".join(str(value).strip() for value in body_parts if str(value or "").strip()) + "\n"

    _, body_html = branded_email(
        product=product_key,
        eyebrow="ONCE-OFF PROOF PERMISSION",
        headline=f"May I send one {product} proof example?",
        greeting=expression["greeting"] or "Hello,",
        intro=expression["intro"],
        body=list(expression["paragraphs"]),
        bullets=list(expression.get("bullets") or []),
        cta_label="YES, send the proof",
        cta_url=yes_url,
        secondary_label="NO, thank you",
        secondary_url=no_url,
        caution=expression.get("caution"),
    )
    return str(expression["subject"]), body, body_html
