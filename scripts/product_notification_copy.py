from __future__ import annotations

from typing import Any

from commerce.expression_guarded import CommunicativeAct, render_expression
from commerce.workflow_bridge import commercial_semantic_object_from_product_workflow
from scripts.dio_mail_branding import branded_email


PRODUCT_LINKS = {
    "homs": "https://byron2306.github.io/DIO-Workflows/sites/homs/",
    "evidex": "https://byron2306.github.io/DIO-Workflows/sites/evidex/",
}


def notification_bundle(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return product notification copy plus the C3 semantic objects that produced it."""
    cso = commercial_semantic_object_from_product_workflow(workflow)
    product = str(workflow["product"])
    job_id = str(workflow["job_id"])
    job_ref = f"product_job:{job_id}"

    if product == "homs":
        act = CommunicativeAct.INTAKE_REQUEST
        purpose = "intake"
        expression = render_expression(
            cso,
            act,
            context={
                "verified_context": {
                    "job_reference": {"value": job_id, "source_refs": [job_ref], "authority": "workflow_record"},
                    "requested_material": {
                        "value": "Please send the electronic submission batch, rubric or memo, task instructions, and the gradebook or mark list when mark collation is required.",
                        "source_refs": ["product_contract:homs_assessment_intake_v1"],
                        "authority": "product_contract",
                    },
                }
            },
        )
        eyebrow = "ASSESSMENT WORKFLOW OPENED"
        headline = "Your HOMS assessment job is ready for source files."
        cta_label = "View HOMS Assessment Desk"
    else:
        act = CommunicativeAct.DELIVERY
        purpose = "delivery"
        expression = render_expression(
            cso,
            act,
            context={
                "verified_context": {
                    "job_reference": {"value": job_id, "source_refs": [job_ref], "authority": "workflow_record"}
                }
            },
        )
        eyebrow = "REVIEWED DELIVERY READY"
        headline = "Your Evidex evidence pack is ready for inspection."
        cta_label = "View Evidex Evidence Packs"

    body, body_html = branded_email(
        product=product,
        eyebrow=eyebrow,
        headline=headline,
        greeting=expression["greeting"] or "Hello,",
        intro=expression["intro"],
        body=list(expression["paragraphs"]) + [expression["cta"]],
        reference=job_id,
        cta_label=cta_label,
        cta_url=PRODUCT_LINKS[product],
        caution=expression.get("caution"),
    )
    return {
        "cso": cso,
        "expression": expression,
        "purpose": purpose,
        "communicative_act": act.value,
        "subject": str(expression["subject"]),
        "body": body,
        "body_html": body_html,
    }


def notification_copy(workflow: dict[str, Any]) -> tuple[str, str, str, str]:
    """Compatibility wrapper returning purpose, subject, plain body and branded HTML."""
    bundle = notification_bundle(workflow)
    return bundle["purpose"], bundle["subject"], bundle["body"], bundle["body_html"]
