from __future__ import annotations

from pathlib import Path
from typing import Any

from presence_core.customer_cases import create_or_attach_case, update_case

REAL_ENGAGEMENT_STATES = {
    "OUTREACH_SENT",
    "RESPONSE_OBSERVED",
    "APPLICATION_SUBMITTED",
    "TERM_SHEET_OR_AWARD_EVIDENCE",
    "SETTLED_FUNDS_EVIDENCE",
}


def attach_real_engagement_to_case(
    state_root: Path,
    opportunity: dict[str, Any],
    engagement: dict[str, Any],
) -> dict[str, Any] | None:
    state = str(engagement.get("state") or "").strip().upper()
    if state not in REAL_ENGAGEMENT_STATES:
        return None

    opportunity_id = str(opportunity.get("opportunity_id") or "").strip()
    if not opportunity_id:
        raise ValueError("opportunity_id is required for real engagement")
    conversation_id = str(engagement.get("conversation_id") or f"capital-{opportunity_id}").strip()
    channel = str(engagement.get("channel") or "capital_support").strip()
    external_user_id = str(
        engagement.get("external_user_id")
        or engagement.get("contact_email")
        or opportunity.get("organisation_id")
        or opportunity_id
    ).strip()
    evidence_ref = str(engagement.get("evidence_ref") or "").strip()
    if state != "OUTREACH_SENT" and not evidence_ref:
        raise ValueError(f"{state} requires an evidence_ref")

    case = create_or_attach_case(
        Path(state_root),
        conversation_id=conversation_id,
        channel=channel,
        external_user_id=external_user_id,
        product_id=str(opportunity.get("product_id") or "").strip() or None,
        contact_email=str(engagement.get("contact_email") or "").strip() or None,
    )

    existing_capital = dict(case.get("capital_support") or {})
    refs = [str(x) for x in existing_capital.get("engagement_evidence_refs") or [] if str(x).strip()]
    if evidence_ref and evidence_ref not in refs:
        refs.append(evidence_ref)
    patch = {
        "capital_support": {
            **existing_capital,
            "opportunity_id": opportunity_id,
            "opportunity_type": opportunity.get("opportunity_type"),
            "organisation_id": opportunity.get("organisation_id"),
            "engagement_state": state,
            "engagement_evidence_refs": refs,
            "truth_class": state,
            "authority_created": False,
        }
    }
    target_stage = "QUALIFIED" if state in {
        "RESPONSE_OBSERVED",
        "APPLICATION_SUBMITTED",
        "TERM_SHEET_OR_AWARD_EVIDENCE",
        "SETTLED_FUNDS_EVIDENCE",
    } else None
    updated = update_case(
        Path(state_root),
        case,
        stage=target_stage,
        patch=patch,
        evidence_ref=evidence_ref or f"capital:{opportunity_id}:{state}",
    )
    updated["authority_created"] = False
    return updated
