from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.dio_mail_branding import branded_email, product_profile
from scripts.manage_mail_intent import (
    create_intent_from_payload,
    emit_event,
    write_json,
)


class PublicIntakeError(RuntimeError):
    pass


def acknowledgement_message(
    lead_id: str,
    envelope: dict[str, Any],
) -> tuple[str, str]:
    product_key = str(envelope.get("product") or "dio")
    profile = product_profile(product_key)
    offer = str(envelope.get("offer") or "pilot request").replace("_", " ")
    request = envelope.get("request") or {}
    summary = "\n".join(
        f"{str(key).replace('_', ' ').title()}: {value}"
        for key, value in list(request.items())[:8]
    )
    return branded_email(
        product=product_key,
        eyebrow="REQUEST RECEIVED",
        headline=f"Your {profile['name']} request is in the DIO queue.",
        greeting="Hello,",
        intro=(
            "Thanks for reaching out. This is now a tracked DIO workflow lead, "
            "not a loose inbox note."
        ),
        body=[
            f"Offer requested: {offer}.",
            (
                "We will review the scope before asking for private files, "
                "payment or delivery authority."
            ),
            "What we received:\n" + (summary or "A controlled pilot request."),
            (
                "Reply to this email if anything needs changing. "
                "The same conversation can carry the work forward."
            ),
        ],
        reference=lead_id,
        cta_label=f"View {profile['name']}",
        cta_url=profile["url"],
        caution=(
            "No payment, private-file processing or delivery release happens "
            "from this acknowledgement alone. A human approval gate remains in place."
        ),
    )


def materialize_public_intakes(
    events: list[dict[str, Any]],
    lead_root: Path,
    intent_root: Path,
    event_log: Path,
) -> int:
    created = 0
    lead_root.mkdir(parents=True, exist_ok=True)
    for event in events:
        if (
            event.get("source") != "public_intake"
            or event.get("event_type") != "public.intake.received"
        ):
            continue
        payload = event.get("payload") or {}
        lead_id = str(payload.get("lead_id") or "")
        envelope = payload.get("envelope") or {}
        if (
            not lead_id
            or not lead_id.replace("-", "").isalnum()
            or envelope.get("schema") != "dio.public_intake.v1"
        ):
            raise PublicIntakeError(
                "Public intake event failed its local contract check."
            )

        lead_path = lead_root / f"{lead_id}.json"
        if lead_path.exists():
            continue

        contact = envelope.get("contact") or {}
        product = str(envelope.get("product") or "dio")
        body, body_html = acknowledgement_message(lead_id, envelope)
        intent = create_intent_from_payload(
            {
                "purpose": "lead_acknowledgement",
                "lead_id": lead_id,
                "recipient": contact.get("email"),
                "subject": (
                    f"{product_profile(product)['name']} request received "
                    f"[{lead_id}]"
                ),
                "body": body,
                "body_html": body_html,
                "risk": "routine",
            },
            intent_root,
            event_log,
        )
        record = {
            "schema": "dio.lead.v1",
            "lead_id": lead_id,
            "product": product,
            "offer": envelope.get("offer"),
            "contact": contact,
            "request": envelope.get("request") or {},
            "consents": envelope.get("consents") or {},
            "attribution": envelope.get("attribution") or {},
            "state": "new",
            "qualification": {
                "state": "pending",
                "decided_at": None,
                "decided_by": None,
            },
            "conversation_id": None,
            "acknowledgement": {
                "mail_intent_id": intent["mail_intent_id"],
                "state": "draft_ready",
            },
            "created_at": event.get("received_at") or envelope.get("submitted_at"),
            "updated_at": event.get("received_at") or envelope.get("submitted_at"),
            "edge_event_id": event.get("id"),
            "ingress_transport": event.get("transport") or "local_public_edge",
            "authority_created": False,
        }
        write_json(lead_path, record, exclusive=True)
        emit_event(
            event_log,
            "lead.created",
            "action",
            "lead",
            lead_id,
            {
                "product": product,
                "offer": envelope.get("offer"),
                "authority_created": False,
            },
            lead_id,
        )
        created += 1
    return created
