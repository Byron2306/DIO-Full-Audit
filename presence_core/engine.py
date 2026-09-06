from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from adapters.lingua.communicator import register_communication, requested_language
from adapters.lingua.conversation import apply_resolution_to_state, resolve_conversation
from adapters.lingua.conversation_knowledge import load_public_product_knowledge
from adapters.lingua.interaction_regulator import observe_interaction
from adapters.lingua.persona_lab import assign_persona

from .attachments import AttachmentError, validate_and_store_attachment
from .config import operator_ids
from .events import emit_event
from .identity import bound_order_status, load_status_binding
from .llm import draft_with_ollama, resolve_conversation_with_ollama
from .policy import authorize
from .router import decision_from_conversation_action, route_message
from .state import (
    append_conversation_turn,
    create_intake,
    create_needs_you,
    list_needs_you,
    load_conversation_state,
    load_or_create_conversation,
    load_recent_conversation_turns,
    operator_summary,
    save_conversation_state,
    update_conversation,
)
from .voice import build_voice_plan

PRODUCT_COPY = {
    "homs": "HOMS turns curriculum intent into governed educator-ready work: assessments, marking support, lesson plans, slides, worksheets and lesson media. Educator approval remains the authority gate.",
    "evidex": "Evidex turns scattered evidence into a review trail with claims, source mapping, provenance and gaps kept visible for human review.",
    "sophia": "Sophia supports research review and guided learning while preserving authorship and human scholarship.",
    "vamp": "VAMP maps performance evidence to tasks, objectives and review structures while leaving performance judgment with the authorised human.",
    "nichefoundry": "NicheFoundry is DIO's media and campaign-production organ, used to turn validated ideas into audience-ready creative assets.",
    "document_studio": "Document Studio translates, edits and formats governed source meaning into client-ready DOCX, PDF, slide, web and caption outputs, with reviewable terminology and layout checks.",
}


def _role(envelope: dict[str, Any]) -> str:
    trusted_edge_role = str(envelope.get("_trusted_edge_role") or "public")
    return (
        "operator"
        if trusted_edge_role == "operator"
        and envelope.get("channel") == "telegram"
        and str(envelope.get("external_user_id")) in operator_ids()
        else "public"
    )


def _conversational_guide_enabled(role: str) -> bool:
    return role == "public" and os.getenv(
        "DIO_PRESENCE_CONVERSATIONAL_GUIDE", "0"
    ).strip().lower() in {"1", "true", "yes"}


def _status_text(statuses: list[dict[str, Any]]) -> tuple[str, str]:
    parts = []
    for status in statuses:
        if status.get("state") != "found":
            parts.append(
                f"{status.get('order_id')}: not currently present in DIO's local commerce state"
            )
        else:
            fulfil = "released" if status.get("fulfilment_released") else "not released"
            parts.append(
                f"{status.get('order_id')}: payment {status.get('payment_state', 'unknown')}; fulfilment {fulfil}"
            )
    return (
        "I found the order status bound to this verified conversation: "
        + "; ".join(parts)
        + ".",
        json.dumps(statuses, sort_keys=True),
    )


def _operator_brief_text(summary: dict[str, Any], focus: str = "full") -> str:
    jobs = summary.get("jobs", {})
    mail = summary.get("mail", {})
    commerce = summary.get("commerce", {})
    market = summary.get("market", {})
    needs = summary.get("needs_you", {})
    actions = summary.get("top_actions", [])
    first_actions = "; ".join(
        f"{item.get('kind')}: {item.get('summary')}" for item in actions[:4]
    ) or "none waiting"
    if focus == "market":
        metrics = market.get("metrics", {})
        return (
            f"Market Command: {market.get('campaigns', 0)} campaigns, {market.get('active', 0)} active or approved, "
            f"{market.get('released', 0)} released, {market.get('awaiting_approval', 0)} campaign approvals waiting and "
            f"{market.get('content_awaiting_approval', 0)} content approvals waiting. Metrics currently show "
            f"{metrics.get('impressions', 0)} impressions, {metrics.get('clicks', 0)} clicks, {metrics.get('enquiries', 0)} enquiries and "
            f"{metrics.get('paid_orders', 0)} paid orders. I have not published or spent anything."
        )
    if focus == "commerce":
        return (
            f"Commerce: {commerce.get('orders', 0)} orders recorded, {commerce.get('paid', 0)} paid, "
            f"{commerce.get('live_paid', 0)} live paid and {commerce.get('paid_unreleased', 0)} paid but unreleased. "
            "I have not released fulfilment or touched refunds."
        )
    if focus == "mail":
        return (
            f"Mail: {mail.get('total', 0)} intents, {mail.get('pending', 0)} pending and "
            f"{mail.get('approval_required', 0)} still requiring approval. Top actions: {first_actions}. "
            "I have not sent anything."
        )
    if focus == "jobs":
        return (
            f"Jobs: {jobs.get('total', 0)} total, by product {jobs.get('by_product', {})}, by state {jobs.get('by_state', {})}. "
            f"{len(jobs.get('awaiting_review', []))} awaiting review and {len(jobs.get('delivery_ready', []))} delivery drafts ready. "
            "I have not approved or delivered work."
        )
    return (
        f"Morning, Professor. DIO is awake: {jobs.get('total', 0)} jobs, {mail.get('pending', 0)} pending mail, "
        f"{commerce.get('paid_unreleased', 0)} paid-unreleased order(s), {market.get('active', 0)} active/approved campaigns, "
        f"{needs.get('open', 0)} Needs You item(s), {summary.get('leads', {}).get('total', 0)} lead(s), "
        f"{summary.get('incidents', {}).get('open_or_recorded', 0)} recorded incident(s). Top actions: {first_actions}. "
        "I have not sent, approved, released, published, spent, or processed attachments."
    )


def _reply(
    decision: dict[str, Any],
    role: str,
    summary=None,
    needs=None,
    intake=None,
    statuses=None,
    attachment=None,
) -> tuple[str, str]:
    intent = decision["intent"]
    product = decision.get("product")
    if intent == "help":
        if role == "operator":
            return (
                "Operator commands: /status, /market, /commerce, /mail, /jobs, /needs, /help. "
                "Plain-language equivalents also work: market command, paid orders, pending mail, delivery drafts, attention queue. "
                "I am read-only here: I can brief and route, but I cannot send mail, publish, spend, approve, release fulfilment, or process attachments.",
                "operator_help",
            )
        return (
            "I can explain DIO, HOMS, Evidex, Sophia, VAMP and Document Studio; capture a request; receive bounded uploads into quarantine; "
            "and explain translation or formatting. I cannot take payment, release work, or disclose private order status from an unverified chat.",
            "public_help",
        )
    if intent == "operator_summary" and summary:
        return _operator_brief_text(summary), json.dumps(summary, sort_keys=True)
    if intent in {"campaign_summary", "revenue_summary", "mail_summary", "job_summary"} and summary:
        focus = {
            "campaign_summary": "market",
            "revenue_summary": "commerce",
            "mail_summary": "mail",
            "job_summary": "jobs",
        }[intent]
        return _operator_brief_text(summary, focus), json.dumps(summary, sort_keys=True)
    if intent == "needs_you":
        needs = needs or []
        if not needs:
            return "Your Needs You queue is clear right now. Suspiciously civilised.", "needs_you=0"
        top = "; ".join(
            f"{item['needs_you_id']}: {item['summary'][:110]}" for item in needs[:5]
        )
        return f"You have {len(needs)} open Needs You item(s). Top items: {top}", f"needs_you={len(needs)}"
    if intent == "intake_request" and intake:
        suffix = (
            f" I also quarantined attachment {attachment['attachment_id']} for human review; it has not been opened or parsed."
            if attachment
            else ""
        )
        return (
            f"I’ve captured this as a {product.upper()} intake ({intake['intake_id']}) and placed it in human review. I haven’t charged you, started fulfilment, or promised a delivery time yet.{suffix}",
            f"intake={intake['intake_id']}; state=pending_operator_review",
        )
    if intent == "attachment_received" and attachment:
        return (
            f"I received {attachment['original_file_name']} and quarantined it as {attachment['attachment_id']}. DIO has not opened, parsed, executed, or trusted the file. A human can review and attach it to the right workflow.",
            f"attachment={attachment['attachment_id']}; state=quarantined",
        )
    if intent == "pricing_info":
        return (
            "Pricing is product- and scope-specific. I can capture what you need and prepare it for a human-approved quote rather than inventing a number at you.",
            "pricing_not_resolved",
        )
    if intent == "status_request" and statuses is not None:
        return _status_text(statuses)
    if intent == "status_request":
        return (
            "I can help with status, but this conversation has not yet been identity-bound to an order by DIO. I’ve put the request in the human queue rather than exposing customer information to an unverified chat.",
            "public_status_lookup=identity_binding_required",
        )
    if intent == "translation_info":
        return (
            "Yes. DIO’s localisation path is designed to translate structured meaning before final rendering, so terminology, grade level and layout can be checked rather than blindly translating a finished document. Human language review remains available as a gate.",
            "translation=structured_meaning_first",
        )
    if intent == "formatting_info":
        return (
            "Yes. DIO Format treats presentation as a governed render step: templates, document geometry, headings, tables, references, PowerPoint masters and delivery profiles can be applied without rewriting the underlying content.",
            "formatting=render_layer",
        )
    if intent == "product_info" and product:
        return PRODUCT_COPY.get(product, "I can explain that DIO workflow or capture an intake for it."), f"product={product}"
    if intent == "general_info":
        return (
            "I’m Vesper, DIO’s Presence Core. I’m an AI system. I can explain HOMS, Evidex, Sophia, VAMP and Document Studio, capture a request, receive bounded document uploads, explain translation/formatting, and route sensitive work to a human authority gate. I don’t silently spend money, release work, or make professional judgments for you.",
            "public_capabilities=bounded",
        )
    return (
        "I’m not confident enough to route that safely yet. Tell me whether this is about HOMS, Evidex, Sophia, VAMP, translation/formatting, an uploaded file, or an existing DIO job and I’ll put it on the right rail.",
        "classification=unresolved",
    )


def _lingua_reply(
    *,
    dio_root: Path,
    envelope: dict[str, Any],
    decision: dict[str, Any],
    role: str,
    correlation: str,
    reply: str,
    interaction: dict[str, Any] | None = None,
    persona: dict[str, Any] | None = None,
    conversation_context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    metadata = envelope.get("metadata") or {}
    explicit_language = metadata.get("language") or metadata.get("locale") or envelope.get("language")
    target = requested_language(
        str(envelope.get("text") or ""),
        str(explicit_language) if explicit_language else None,
    )
    artifact = "operator_brief" if role == "operator" else "conversation_response"
    interaction_context = None
    if interaction:
        policy = interaction.get("delivery_policy") or {}
        interaction_context = {
            "observation_id": interaction.get("observation_id"),
            "delivery_mode": policy.get("mode"),
            "sales_pressure_allowed": policy.get("sales_pressure_allowed"),
            "humour_allowed": policy.get("humour_allowed"),
            "proof_priority": policy.get("proof_priority"),
            "voice": policy.get("voice"),
            "emotion_diagnosed": False,
            "personality_diagnosed": False,
        }
    persona_context = None
    if persona:
        package = persona.get("package") or {}
        persona_context = {
            "assignment_id": persona.get("assignment_id"),
            "experiment_id": persona.get("experiment_id"),
            "experimental_assignment": persona.get("experimental_assignment"),
            "cell_id": package.get("cell_id"),
            "persona_id": package.get("persona_id"),
            "avatar_id": package.get("avatar_id"),
            "voice_candidate_id": package.get("voice_candidate_id"),
            "voice_profile_id": package.get("voice_profile_id"),
            "stable_for_conversation": True,
            "ai_disclosure_locked": True,
        }
    receipt = register_communication(
        dio_root=dio_root,
        owner="vesper",
        artifact_type=artifact,
        channel=str(envelope.get("channel") or "conversation"),
        body=reply,
        audience="operator" if role == "operator" else "public",
        privacy_domain="operator_private" if role == "operator" else "public_communication",
        correlation_id=correlation,
        source_message_id=str(
            envelope.get("source_message_id") or metadata.get("source_message_id") or ""
        )
        or None,
        source_language="English",
        target_language=target,
        purpose=str(decision.get("intent") or "response"),
        authority_boundary="LINGUA may preserve and render Vesper meaning but cannot create send, spend, fulfilment, professional, identity, or release authority.",
        product_context=str(decision.get("product") or "") or None,
        interaction_context=interaction_context,
        persona_context=persona_context,
        conversation_context=conversation_context,
    )
    if receipt.get("translation_state") == "approved_translation":
        return str(receipt.get("selected_text") or reply), receipt
    return reply, receipt


def _conversation_event_data(resolution: dict[str, Any]) -> dict[str, Any]:
    return {
        "conversation_act": resolution.get("conversation_act"),
        "source": resolution.get("source"),
        "confidence": resolution.get("confidence"),
        "current_topic": resolution.get("current_topic"),
        "candidate_products": list(resolution.get("candidate_products") or [])[:8],
        "action_intent": resolution.get("action_intent"),
        "action_product": resolution.get("action_product"),
        "provider_called": bool(resolution.get("provider_called", False)),
        "authority_created": False,
    }


def _process_conversational_public(
    *,
    envelope: dict[str, Any],
    dio_root: Path,
    presence_root: Path,
    event_log: Path,
    routes_path: Path,
    conv: dict[str, Any],
    text: str,
    correlation: str,
    metadata: dict[str, Any],
    interaction: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    role = "public"
    state = load_conversation_state(presence_root, correlation)
    recent_turns = load_recent_conversation_turns(presence_root, correlation)
    explicit_language = metadata.get("language") or metadata.get("locale") or envelope.get("language")
    target_language = requested_language(text, str(explicit_language) if explicit_language else None)
    persona = assign_persona(
        root=dio_root,
        conversation_id=correlation,
        role=role,
        channel=str(envelope.get("channel") or "conversation"),
        audience=str(metadata.get("audience") or "public"),
        product=str(state.get("selected_product") or "") or None,
        language=target_language,
    )
    voice_profile_id = (persona.get("package") or {}).get("voice_profile_id")
    voice_plan = build_voice_plan(
        root=dio_root,
        language=target_language,
        interaction=interaction,
        requested_profile=voice_profile_id,
    )
    emit_event(
        event_log,
        "presence.persona_assigned",
        "info",
        "vesper_persona",
        persona["assignment_id"],
        {
            "experimental_assignment": persona.get("experimental_assignment"),
            "cell_id": (persona.get("package") or {}).get("cell_id"),
            "persona_id": (persona.get("package") or {}).get("persona_id"),
            "avatar_id": (persona.get("package") or {}).get("avatar_id"),
            "voice_profile_id": voice_profile_id,
            "stable_for_conversation": True,
        },
        correlation,
    )

    append_conversation_turn(
        presence_root,
        correlation,
        role="user",
        text=text,
        max_turns=6,
    )
    knowledge = load_public_product_knowledge(dio_root)
    resolution = resolve_conversation(
        root=dio_root,
        text=text,
        state=state,
        recent_turns=recent_turns,
        knowledge=knowledge,
        interaction=interaction,
        persona=persona,
        provider_resolver=resolve_conversation_with_ollama,
    )
    emit_event(
        event_log,
        "presence.conversation_resolved",
        "info",
        "presence_conversation",
        correlation,
        _conversation_event_data(resolution),
        correlation,
    )
    if resolution.get("source") == "provider":
        emit_event(
            event_log,
            "presence.conversation_provider_called",
            "info",
            "presence_conversation",
            correlation,
            {"provider_called": True, "authority_created": False},
            correlation,
        )
    if resolution.get("source") == "lingua_crystal":
        emit_event(
            event_log,
            "presence.conversation_crystal_reused",
            "info",
            "presence_conversation",
            correlation,
            {
                "crystal_id": resolution.get("crystal_id"),
                "reuse_receipt_digest": resolution.get("reuse_receipt_digest"),
                "authority_created": False,
            },
            correlation,
        )
    if resolution.get("clarification_needed"):
        emit_event(
            event_log,
            "presence.conversation_clarification_requested",
            "info",
            "presence_conversation",
            correlation,
            {
                "current_topic": resolution.get("current_topic"),
                "candidate_products": list(resolution.get("candidate_products") or [])[:8],
                "authority_created": False,
            },
            correlation,
        )

    action_decision = decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text=text,
        role=role,
        routes_path=routes_path,
    )
    updated_state = apply_resolution_to_state(state, resolution)
    updated_state["turn_count"] = int(state.get("turn_count", 0)) + 1

    old_proposal = state.get("action_proposal")
    new_proposal = updated_state.get("action_proposal")
    if new_proposal and new_proposal != old_proposal:
        emit_event(
            event_log,
            "presence.conversation_action_proposed",
            "info",
            "presence_conversation",
            correlation,
            {
                "action_intent": new_proposal.get("intent"),
                "action_product": new_proposal.get("product"),
                "authority_created": False,
            },
            correlation,
        )

    decision = {
        "intent": "conversation",
        "product": updated_state.get("selected_product"),
        "confidence": float(resolution.get("confidence") or 0.0),
        "source": f"conversation:{resolution.get('source') or 'fallback'}",
        "reason": "conversational response; no consequential action authorized",
    }
    action_accepted = False
    if action_decision is not None:
        ok, reason = authorize(role, action_decision.intent)
        if ok:
            decision = action_decision.as_dict()
            action_accepted = True
            emit_event(
                event_log,
                "presence.conversation_action_accepted",
                "action",
                "presence_conversation",
                correlation,
                {
                    "intent": decision.get("intent"),
                    "product": decision.get("product"),
                    "authority_created": False,
                },
                correlation,
            )
        else:
            emit_event(
                event_log,
                "presence.conversation_action_refused",
                "warning",
                "presence_conversation",
                correlation,
                {
                    "action_intent": resolution.get("action_intent"),
                    "action_product": resolution.get("action_product"),
                    "reason": reason,
                    "authority_created": False,
                },
                correlation,
            )
    elif str(resolution.get("action_intent") or "none") != "none":
        emit_event(
            event_log,
            "presence.conversation_action_refused",
            "warning",
            "presence_conversation",
            correlation,
            {
                "action_intent": resolution.get("action_intent"),
                "action_product": resolution.get("action_product"),
                "reason": "deterministic_action_bridge_refused",
                "authority_created": False,
            },
            correlation,
        )

    intake = None
    statuses = None
    if action_accepted and decision["intent"] == "intake_request" and decision.get("product"):
        intake = create_intake(
            presence_root,
            conv,
            str(decision["product"]),
            text,
            envelope.get("source_message_id"),
        )
        item = create_needs_you(
            presence_root,
            reason="public_intake_review",
            conversation_id=correlation,
            product=decision["product"],
            summary=f"Review {decision['product']} intake {intake['intake_id']}: {text[:300]}",
        )
        emit_event(
            event_log,
            "presence.intake_received",
            "action",
            "presence_intake",
            intake["intake_id"],
            {
                "product": decision["product"],
                "needs_you_id": item["needs_you_id"],
                "automatic_fulfilment": False,
                "attachment_ids": [],
            },
            correlation,
        )
    elif action_accepted and decision["intent"] == "status_request":
        binding = load_status_binding(presence_root, correlation)
        if binding:
            statuses = bound_order_status(dio_root, binding)
            emit_event(
                event_log,
                "presence.status_disclosed",
                "info",
                "presence_conversation",
                correlation,
                {
                    "binding_id": binding["binding_id"],
                    "order_count": len(statuses),
                    "disclosure": "minimal_status_only",
                },
                correlation,
            )
        else:
            item = create_needs_you(
                presence_root,
                reason="public_status_identity_required",
                conversation_id=correlation,
                product=decision.get("product"),
                summary="Public user requested status lookup; identity binding required.",
            )
            emit_event(
                event_log,
                "presence.status_escalated",
                "action",
                "presence_conversation",
                correlation,
                {"needs_you_id": item["needs_you_id"]},
                correlation,
            )

    if intake is not None or (action_accepted and decision["intent"] == "status_request"):
        reply, _facts = _reply(
            decision,
            role,
            intake=intake,
            statuses=statuses,
        )
    else:
        reply = str(resolution.get("reply") or "").strip()

    try:
        reply, lingua = _lingua_reply(
            dio_root=dio_root,
            envelope=envelope,
            decision=decision,
            role=role,
            correlation=correlation,
            reply=reply,
            interaction=interaction,
            persona=persona,
            conversation_context=resolution,
        )
    except Exception as exc:
        lingua = {
            "schema": "dio.lingua.communication_receipt.v1",
            "state": "registration_failed",
            "error": str(exc)[:300],
            "conversation_context": None,
            "external_action_executed": False,
            "send_authorized": False,
            "authority_created": False,
        }
        emit_event(
            event_log,
            "presence.lingua_registration_failed",
            "warning",
            "presence_conversation",
            correlation,
            {"error": str(exc)[:180]},
            correlation,
        )

    append_conversation_turn(
        presence_root,
        correlation,
        role="vesper",
        text=reply,
        act=str(resolution.get("conversation_act") or "unknown"),
        product=str(updated_state.get("selected_product") or "") or None,
        max_turns=6,
    )
    updated_state["last_route_intent"] = decision.get("intent")
    save_conversation_state(presence_root, updated_state)
    update_conversation(
        presence_root,
        conv,
        str(decision.get("intent") or "conversation"),
        str(decision.get("product") or "") or None,
    )
    emit_event(
        event_log,
        "presence.conversation_state_updated",
        "info",
        "presence_conversation",
        correlation,
        {
            "turn_count": updated_state.get("turn_count"),
            "current_topic": updated_state.get("current_topic"),
            "candidate_products": list(updated_state.get("candidate_products") or [])[:8],
            "selected_product": updated_state.get("selected_product"),
            "has_action_proposal": bool(updated_state.get("action_proposal")),
            "authority_created": False,
        },
        correlation,
    )
    emit_event(
        event_log,
        "presence.reply_prepared",
        "info",
        "presence_conversation",
        correlation,
        {
            "intent": decision.get("intent"),
            "product": decision.get("product"),
            "role": role,
            "llm_advisory": resolution.get("source") == "provider",
            "lingua_object_id": lingua.get("object_id"),
            "lingua_translation_state": lingua.get("translation_state"),
            "interaction_observation_id": interaction.get("observation_id"),
            "delivery_mode": policy.get("mode"),
            "persona_assignment_id": persona.get("assignment_id"),
            "persona_cell_id": (persona.get("package") or {}).get("cell_id"),
        },
        correlation,
    )
    return {
        "schema": "dio.presence_response.v2",
        "conversation_id": correlation,
        "role": role,
        "decision": decision,
        "conversation": resolution,
        "reply": {
            "text": reply,
            "mode": "text",
            "voice_eligible": bool(envelope.get("message_type") in {"voice", "audio"}),
            "voice_policy": policy.get("voice"),
            "voice_plan": voice_plan,
            "avatar_id": (persona.get("package") or {}).get("avatar_id"),
        },
        "authority": {
            "executed_external_action": False,
            "spend_authorized": False,
            "fulfilment_released": False,
            "attachment_processed": False,
        },
        "attachment": None,
        "intake": intake,
        "status": statuses,
        "interaction": interaction,
        "persona": persona,
        "lingua": lingua,
    }


def process_envelope(
    envelope: dict[str, Any], dio_root: Path, cfg: dict[str, Any]
) -> dict[str, Any]:
    presence_root = dio_root / str(cfg.get("state_root", "state/presence"))
    event_log = dio_root / str(cfg.get("event_log", "telemetry/dio_events.jsonl"))
    routes_path = dio_root / str(cfg.get("routes_path", "config/routes.json"))
    role = _role(envelope)
    conv = load_or_create_conversation(presence_root, envelope, role)
    text = str(envelope.get("text") or "").strip()
    correlation = conv["conversation_id"]
    metadata = envelope.get("metadata") or {}
    interaction = observe_interaction(
        state_root=dio_root / "state" / "lingua",
        conversation_id=correlation,
        text=text,
        channel=str(envelope.get("channel") or "conversation"),
        role=role,
        source_message_id=str(
            envelope.get("source_message_id") or metadata.get("source_message_id") or ""
        )
        or None,
    )
    policy = interaction.get("delivery_policy") or {}
    emit_event(
        event_log,
        "presence.message_received",
        "info",
        "presence_conversation",
        correlation,
        {
            "channel": envelope.get("channel"),
            "role": role,
            "message_type": envelope.get("message_type", "text"),
            "campaign_hint": (conv.get("attribution") or {}).get("campaign_hint"),
        },
        correlation,
    )
    emit_event(
        event_log,
        "presence.interaction_observed",
        "info",
        "lingua_interaction",
        interaction["observation_id"],
        {
            "delivery_mode": policy.get("mode"),
            "sales_pressure_allowed": policy.get("sales_pressure_allowed"),
            "humour_allowed": policy.get("humour_allowed"),
            "proof_priority": policy.get("proof_priority"),
            "emotion_diagnosed": False,
            "personality_diagnosed": False,
        },
        correlation,
    )
    attachment_record = None
    if envelope.get("attachment"):
        try:
            attachment_record = validate_and_store_attachment(
                presence_root, correlation, envelope["attachment"], cfg
            )
            emit_event(
                event_log,
                "presence.attachment_quarantined",
                "action",
                "presence_attachment",
                attachment_record["attachment_id"],
                {
                    "channel": envelope.get("channel"),
                    "sha256": attachment_record["sha256"],
                    "size_bytes": attachment_record["size_bytes"],
                    "automatic_processing": False,
                },
                correlation,
            )
        except AttachmentError as exc:
            emit_event(
                event_log,
                "presence.attachment_rejected",
                "warning",
                "presence_conversation",
                correlation,
                {"reason": str(exc)},
                correlation,
            )
            return {
                "schema": "dio.presence_response.v2",
                "conversation_id": correlation,
                "role": role,
                "decision": {
                    "intent": "attachment_rejected",
                    "product": None,
                    "confidence": 1.0,
                    "source": "policy",
                    "reason": str(exc),
                },
                "reply": {
                    "text": f"I refused that upload safely: {exc}",
                    "mode": "text",
                    "voice_eligible": False,
                },
                "authority": {
                    "executed_external_action": False,
                    "spend_authorized": False,
                    "fulfilment_released": False,
                    "attachment_processed": False,
                },
                "attachment": None,
                "intake": None,
                "interaction": interaction,
                "persona": None,
                "lingua": {
                    "state": "not_registered",
                    "reason": "attachment_rejected_before_response_registration",
                },
            }

    # Keep quarantined-attachment handling on the already-proven deterministic rail.
    # The conversational guide never receives attachment bytes or parsed attachment content.
    if _conversational_guide_enabled(role) and attachment_record is None:
        return _process_conversational_public(
            envelope=envelope,
            dio_root=dio_root,
            presence_root=presence_root,
            event_log=event_log,
            routes_path=routes_path,
            conv=conv,
            text=text,
            correlation=correlation,
            metadata=metadata,
            interaction=interaction,
            policy=policy,
        )

    decision = route_message(text, role, routes_path).as_dict()
    if attachment_record and decision["intent"] in {"unknown", "general_info"}:
        decision = {
            "intent": "attachment_received",
            "product": decision.get("product"),
            "confidence": 1.0,
            "source": "attachment_policy",
            "reason": "quarantined attachment requires human routing",
        }
    ok, reason = authorize(role, decision["intent"])
    if not ok:
        decision = {
            "intent": "unknown",
            "product": None,
            "confidence": 1.0,
            "source": "policy",
            "reason": reason,
        }
    explicit_language = metadata.get("language") or metadata.get("locale") or envelope.get("language")
    target_language = requested_language(
        text, str(explicit_language) if explicit_language else None
    )
    persona = assign_persona(
        root=dio_root,
        conversation_id=correlation,
        role=role,
        channel=str(envelope.get("channel") or "conversation"),
        audience=str(metadata.get("audience") or ("operator" if role == "operator" else "public")),
        product=str(decision.get("product") or "") or None,
        language=target_language,
    )
    voice_profile_id = (persona.get("package") or {}).get("voice_profile_id")
    voice_plan = build_voice_plan(
        root=dio_root,
        language=target_language,
        interaction=interaction,
        requested_profile=voice_profile_id,
    )
    emit_event(
        event_log,
        "presence.persona_assigned",
        "info",
        "vesper_persona",
        persona["assignment_id"],
        {
            "experimental_assignment": persona.get("experimental_assignment"),
            "cell_id": (persona.get("package") or {}).get("cell_id"),
            "persona_id": (persona.get("package") or {}).get("persona_id"),
            "avatar_id": (persona.get("package") or {}).get("avatar_id"),
            "voice_profile_id": voice_profile_id,
            "stable_for_conversation": True,
        },
        correlation,
    )
    summary = None
    needs = None
    intake = None
    statuses = None
    if decision["intent"] in {
        "operator_summary",
        "campaign_summary",
        "revenue_summary",
        "mail_summary",
        "job_summary",
    }:
        summary = operator_summary(dio_root, presence_root)
    elif decision["intent"] == "needs_you":
        needs = list_needs_you(presence_root, 20)
    elif decision["intent"] == "intake_request" and decision.get("product"):
        intake = create_intake(
            presence_root,
            conv,
            str(decision["product"]),
            text,
            envelope.get("source_message_id"),
            attachment_ids=[attachment_record["attachment_id"]]
            if attachment_record
            else None,
        )
        item = create_needs_you(
            presence_root,
            reason="public_intake_review",
            conversation_id=correlation,
            product=decision["product"],
            summary=f"Review {decision['product']} intake {intake['intake_id']}: {text[:300]}",
        )
        emit_event(
            event_log,
            "presence.intake_received",
            "action",
            "presence_intake",
            intake["intake_id"],
            {
                "product": decision["product"],
                "needs_you_id": item["needs_you_id"],
                "automatic_fulfilment": False,
                "attachment_ids": intake.get("attachment_ids", []),
            },
            correlation,
        )
    elif decision["intent"] == "attachment_received" and attachment_record:
        item = create_needs_you(
            presence_root,
            reason="public_attachment_review",
            conversation_id=correlation,
            product=decision.get("product"),
            summary=f"Review quarantined attachment {attachment_record['attachment_id']}: {attachment_record['original_file_name']}",
        )
        emit_event(
            event_log,
            "presence.attachment_review_required",
            "action",
            "presence_attachment",
            attachment_record["attachment_id"],
            {"needs_you_id": item["needs_you_id"]},
            correlation,
        )
    elif decision["intent"] == "status_request":
        binding = load_status_binding(presence_root, correlation)
        if binding:
            statuses = bound_order_status(dio_root, binding)
            emit_event(
                event_log,
                "presence.status_disclosed",
                "info",
                "presence_conversation",
                correlation,
                {
                    "binding_id": binding["binding_id"],
                    "order_count": len(statuses),
                    "disclosure": "minimal_status_only",
                },
                correlation,
            )
        else:
            item = create_needs_you(
                presence_root,
                reason="public_status_identity_required",
                conversation_id=correlation,
                product=decision.get("product"),
                summary=f"Public user requested status lookup: {text[:300]}",
            )
            emit_event(
                event_log,
                "presence.status_escalated",
                "action",
                "presence_conversation",
                correlation,
                {"needs_you_id": item["needs_you_id"]},
                correlation,
            )
    fallback, facts = _reply(
        decision, role, summary, needs, intake, statuses, attachment_record
    )
    reply = draft_with_ollama(decision, facts, fallback, interaction, persona)
    try:
        reply, lingua = _lingua_reply(
            dio_root=dio_root,
            envelope=envelope,
            decision=decision,
            role=role,
            correlation=correlation,
            reply=reply,
            interaction=interaction,
            persona=persona,
        )
    except Exception as exc:
        lingua = {
            "schema": "dio.lingua.communication_receipt.v1",
            "state": "registration_failed",
            "error": str(exc)[:300],
            "external_action_executed": False,
            "send_authorized": False,
            "authority_created": False,
        }
        emit_event(
            event_log,
            "presence.lingua_registration_failed",
            "warning",
            "presence_conversation",
            correlation,
            {"error": str(exc)[:180]},
            correlation,
        )
    update_conversation(
        presence_root, conv, decision["intent"], decision.get("product")
    )
    emit_event(
        event_log,
        "presence.reply_prepared",
        "info",
        "presence_conversation",
        correlation,
        {
            "intent": decision["intent"],
            "product": decision.get("product"),
            "role": role,
            "llm_advisory": decision.get("source") == "ollama_advisory",
            "lingua_object_id": lingua.get("object_id"),
            "lingua_translation_state": lingua.get("translation_state"),
            "interaction_observation_id": interaction.get("observation_id"),
            "delivery_mode": policy.get("mode"),
            "persona_assignment_id": persona.get("assignment_id"),
            "persona_cell_id": (persona.get("package") or {}).get("cell_id"),
        },
        correlation,
    )
    return {
        "schema": "dio.presence_response.v2",
        "conversation_id": correlation,
        "role": role,
        "decision": decision,
        "reply": {
            "text": reply,
            "mode": "text",
            "voice_eligible": bool(envelope.get("message_type") in {"voice", "audio"}),
            "voice_policy": policy.get("voice"),
            "voice_plan": voice_plan,
            "avatar_id": (persona.get("package") or {}).get("avatar_id"),
        },
        "authority": {
            "executed_external_action": False,
            "spend_authorized": False,
            "fulfilment_released": False,
            "attachment_processed": False,
        },
        "attachment": attachment_record,
        "intake": intake,
        "status": statuses,
        "interaction": interaction,
        "persona": persona,
        "lingua": lingua,
    }
