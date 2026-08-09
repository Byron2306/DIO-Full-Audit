from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any


STAGE_ORDER = {
    "observed": 0,
    "acknowledgement_ready": 1,
    "acknowledged": 2,
    "qualification_pending": 3,
    "qualified": 4,
    "intake_collecting": 5,
    "intake_ready": 6,
    "quote_ready": 7,
    "payment_pending": 8,
    "paid": 9,
    "processing": 10,
    "review_required": 11,
    "delivery_ready": 12,
    "delivered": 13,
    "closeout_ready": 14,
    "closed": 15,
    "blocked": -1,
}


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def harmonic_assessment(transaction: dict[str, Any]) -> dict[str, Any]:
    timestamps = sorted(
        parsed
        for parsed in (_parse_time(item) for item in transaction.get("event_times") or [])
        if parsed is not None
    )
    intervals = [
        (right - left).total_seconds()
        for left, right in zip(timestamps, timestamps[1:])
        if right >= left
    ]
    median_seconds = statistics.median(intervals) if intervals else None
    jitter_seconds = statistics.pstdev(intervals) if len(intervals) > 1 else 0.0
    short_threshold = max(30.0, (median_seconds or 300.0) * 0.2)
    burstiness = (
        sum(1 for interval in intervals if interval <= short_threshold) / len(intervals)
        if intervals
        else 0.0
    )
    latest = timestamps[-1] if timestamps else _parse_time(transaction.get("updated_at"))
    age_hours = max(0.0, (datetime.now(timezone.utc) - latest).total_seconds() / 3600.0) if latest else None
    stage = transaction.get("stage") or "observed"
    stale_after = 48.0 if STAGE_ORDER.get(stage, 0) < STAGE_ORDER["processing"] else 24.0
    stale = bool(age_hours is not None and age_hours >= stale_after and stage not in {"closed", "delivered"})
    duplicate_count = int((transaction.get("signals") or {}).get("duplicate_messages") or 0)

    discord = min(
        1.0,
        (0.45 if burstiness >= 0.65 and len(intervals) >= 3 else 0.0)
        + (0.45 if stale else 0.0)
        + min(0.3, duplicate_count * 0.1),
    )
    sample_confidence = min(1.0, len(intervals) / 8.0)
    resonance = max(0.0, min(1.0, (1.0 - discord) * (0.55 + 0.45 * sample_confidence)))
    if stale:
        recommendation = "follow_up_or_close"
    elif discord >= 0.7:
        recommendation = "slow_and_gate"
    elif discord >= 0.4:
        recommendation = "inspect_transition"
    else:
        recommendation = "normal_flow"
    return {
        "sample_size": len(timestamps),
        "median_interval_seconds": round(median_seconds, 2) if median_seconds is not None else None,
        "jitter_seconds": round(jitter_seconds, 2),
        "burstiness": round(burstiness, 4),
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "stale": stale,
        "resonance_score": round(resonance, 4),
        "discord_score": round(discord, 4),
        "confidence": round(sample_confidence, 4),
        "mode_recommendation": recommendation,
    }


def metatron_assess(transaction: dict[str, Any]) -> dict[str, Any]:
    lineage = transaction.get("lineage") or {}
    required_lineage = ["lead_id", "conversation_id", "job_id", "order_id"]
    available = [key for key in required_lineage if lineage.get(key)]
    lineage_completeness = len(available) / len(required_lineage)
    intake = transaction.get("intake") or {}
    consents = transaction.get("consents") or {}
    nonempty_consents = [value for value in consents.values() if value is True or str(value).strip()]
    consent_confidence = min(1.0, len(nonempty_consents) / max(1, len(consents))) if consents else 0.0
    stage = str(transaction.get("stage") or "observed")
    stage_confidence = float((transaction.get("signals") or {}).get("stage_confidence") or 0.5)
    readiness = min(
        1.0,
        0.35 * stage_confidence
        + 0.25 * lineage_completeness
        + 0.2 * float(bool(transaction.get("product")))
        + 0.2 * float(bool(intake.get("meaningful_input"))),
    )
    risk = 0.0
    if not transaction.get("product"):
        risk += 0.3
    if STAGE_ORDER.get(stage, 0) >= STAGE_ORDER["paid"] and not lineage.get("order_id"):
        risk += 0.45
    if STAGE_ORDER.get(stage, 0) >= STAGE_ORDER["delivery_ready"] and not transaction.get("review_approved"):
        risk += 0.5
    return {
        "status": "ok",
        "commercial_belief": {
            "stage": stage,
            "stage_confidence": round(stage_confidence, 4),
            "lineage_completeness": round(lineage_completeness, 4),
            "lineage_present": available,
            "intake_meaningful": bool(intake.get("meaningful_input")),
            "attachment_count": len(intake.get("attachments") or []),
            "consent_confidence": round(consent_confidence, 4),
            "readiness_score": round(readiness, 4),
            "risk_score": round(min(1.0, risk), 4),
        },
        "policy_tier_suggestion": "high" if risk >= 0.6 else "medium" if risk >= 0.3 else "routine",
    }


def _action(
    name: str,
    authority: str,
    *,
    readiness: float,
    customer_value: float,
    reversibility: float,
    urgency: float = 0.5,
    reason: str,
) -> dict[str, Any]:
    score = 0.4 * readiness + 0.25 * customer_value + 0.2 * reversibility + 0.15 * urgency
    return {
        "action": name,
        "authority": authority,
        "score": round(max(0.0, min(1.0, score)), 4),
        "reason": reason,
        "components": {
            "readiness": readiness,
            "customer_value": customer_value,
            "reversibility": reversibility,
            "urgency": urgency,
        },
    }


def michael_plan(transaction: dict[str, Any], metatron: dict[str, Any]) -> dict[str, Any]:
    stage = str(transaction.get("stage") or "observed")
    readiness = float((metatron.get("commercial_belief") or {}).get("readiness_score") or 0.0)
    actions: list[dict[str, Any]] = []
    if stage == "observed":
        actions.append(_action("triage_intake", "automatic_internal", readiness=max(readiness, 0.7), customer_value=0.6, reversibility=1.0, reason="Classify and bind the observation without contacting the customer."))
    if stage in {"acknowledgement_ready", "qualification_pending"}:
        actions.append(_action("review_qualification", "operator_required", readiness=readiness, customer_value=0.8, reversibility=0.9, reason="A human confirms fit, authority and commercial scope."))
    if stage == "qualified":
        actions.append(_action("collect_or_validate_intake", "automatic_internal", readiness=readiness, customer_value=0.85, reversibility=0.95, reason="Correlate supplied messages and quarantined files into an intake packet."))
        actions.append(_action("prepare_quote", "operator_required", readiness=readiness, customer_value=0.9, reversibility=0.8, reason="Price and scope require commercial authority."))
    if stage in {"intake_collecting", "intake_ready"}:
        actions.append(_action("stage_product_job", "automatic_internal", readiness=readiness, customer_value=0.9, reversibility=0.9, reason="Create a review-gated product job from the accepted intake."))
        actions.append(_action("issue_invoice_and_payment_link", "operator_required", readiness=readiness, customer_value=0.95, reversibility=0.65, reason="Order amount and payment request are external commercial acts."))
    if stage in {"quote_ready", "payment_pending"}:
        actions.append(_action("reconcile_verified_payment", "automatic_internal", readiness=readiness, customer_value=0.8, reversibility=1.0, reason="Consume only signed provider payment evidence."))
    if stage == "paid":
        actions.append(_action("release_processing", "policy_gated_internal", readiness=max(readiness, 0.8), customer_value=1.0, reversibility=0.75, reason="Verified payment may release the approved fulfilment policy."))
    if stage == "processing":
        actions.append(_action("monitor_product_job", "automatic_internal", readiness=readiness, customer_value=0.7, reversibility=1.0, reason="Observe processing receipts and failures."))
    if stage == "review_required":
        actions.append(_action("human_output_review", "operator_required", readiness=readiness, customer_value=1.0, reversibility=0.9, reason="Product authority remains with the qualified human reviewer."))
    if stage == "delivery_ready":
        actions.append(_action("prepare_outbound_package", "automatic_internal", readiness=readiness, customer_value=0.9, reversibility=0.95, reason="Hash and stage the approved package and exact mail draft."))
        actions.append(_action("approve_and_send_delivery", "operator_required", readiness=readiness, customer_value=1.0, reversibility=0.25, reason="External delivery consumes a one-time send authority."))
    if stage == "delivered":
        actions.append(_action("prepare_closeout_receipt", "automatic_internal", readiness=readiness, customer_value=0.75, reversibility=0.95, reason="Build campaign-to-payment-to-delivery ancestry."))
    if stage == "closeout_ready":
        actions.append(_action("close_transaction", "operator_required", readiness=readiness, customer_value=0.6, reversibility=0.7, reason="Confirm acknowledgement, revisions and final commercial state."))
    actions.sort(key=lambda row: (-float(row["score"]), row["action"]))
    return {"ranked_actions": actions, "selected_action": actions[0] if actions else None}


def loki_challenge(transaction: dict[str, Any], michael: dict[str, Any]) -> dict[str, Any]:
    stage = str(transaction.get("stage") or "observed")
    lineage = transaction.get("lineage") or {}
    intake = transaction.get("intake") or {}
    payment = transaction.get("payment") or {}
    flags: list[dict[str, Any]] = []

    def flag(code: str, severity: str, message: str) -> None:
        flags.append({"code": code, "severity": severity, "message": message})

    if not transaction.get("product"):
        flag("AMBIGUOUS_PRODUCT", "challenge", "No authoritative product route is bound to this transaction.")
    if not lineage.get("lead_id") and not lineage.get("conversation_id"):
        flag("UNBOUND_CUSTOMER_CONTEXT", "challenge", "The observation is not bound to a lead or Outlook conversation.")
    if intake.get("sender_mismatch"):
        flag("SENDER_IDENTITY_MISMATCH", "veto", "The message sender does not match the bound lead without an approved delegation.")
    if intake.get("attachments_untrusted"):
        flag("UNTRUSTED_ATTACHMENTS", "challenge", "Mailbox attachments remain quarantined and must not execute or enter product processing yet.")
    if int((transaction.get("signals") or {}).get("duplicate_messages") or 0) > 0:
        flag("DUPLICATE_OBSERVATION", "challenge", "Duplicate message evidence could create repeated jobs or customer contact.")
    if STAGE_ORDER.get(stage, 0) >= STAGE_ORDER["paid"] and payment.get("state") not in {"paid", "waived"}:
        flag("PAYMENT_NOT_VERIFIED", "veto", "The inferred stage exceeds the verified payment state.")
    if payment.get("state") in {"amount_mismatch", "held", "unmatched"}:
        flag("PAYMENT_INTEGRITY_FAILURE", "veto", "Provider payment evidence does not match the registered order.")
    if STAGE_ORDER.get(stage, 0) >= STAGE_ORDER["delivery_ready"] and not transaction.get("review_approved"):
        flag("OUTPUT_AUTHORITY_MISSING", "veto", "Final delivery has no recorded human output approval.")
    if stage == "qualified" and not transaction.get("consents"):
        flag("CONSENT_EVIDENCE_THIN", "challenge", "Qualification exists without structured consent or processing authority evidence.")

    selected = michael.get("selected_action") or {}
    if any(item["severity"] == "veto" for item in flags):
        status = "vetoed"
    elif flags:
        status = "challenged"
    else:
        status = "clear"
    return {
        "status": status,
        "selected_action": selected.get("action"),
        "challenges": flags,
        "alternative_hypotheses": [
            "This may be a support conversation rather than a new order.",
            "The customer may be supplying missing material for an existing job.",
            "A platform notification may be mistaken for customer payment authority.",
        ],
    }


def assess_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    harmonic = harmonic_assessment(transaction)
    metatron = metatron_assess(transaction)
    michael = michael_plan(transaction, metatron)
    loki = loki_challenge(transaction, michael)
    if loki["status"] == "vetoed":
        verdict = "BLOCK"
    elif loki["status"] == "challenged" or harmonic["mode_recommendation"] in {"slow_and_gate", "inspect_transition"}:
        verdict = "ALLOW_WITH_OBLIGATIONS"
    else:
        verdict = "ALLOW"
    return {
        "schema": "dio.commercial_triune_decision.v1",
        "verdict": verdict,
        "metatron": metatron,
        "michael": michael,
        "loki": loki,
        "harmonic": harmonic,
    }
