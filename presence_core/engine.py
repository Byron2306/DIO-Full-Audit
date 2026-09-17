from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any
from adapters.lingua.communicator import register_communication, requested_language
from adapters.lingua.conversation_crystals import resolve_conversation_crystal
from adapters.lingua.conversation_knowledge import retrieve_conversation_knowledge
from adapters.lingua.semantic_context import build_current_semantic_context
from adapters.lingua.conversation_semantics import resolve_conversation_semantics
from adapters.lingua.interaction_regulator import observe_interaction
from adapters.lingua.persona_lab import assign_persona
from .attachments import AttachmentError, validate_and_store_attachment
from .capital_queries import CAPITAL_INTENTS, capital_query
from .commercial_grounding import build_commercial_grounding, commercial_facts, commercial_fallback, should_ground_commercial
from .commerce import commercial_surface_state
from .config import operator_ids
from .customer_cases import (
    CASE_STAGES,
    create_or_attach_case,
    create_successor_case,
    find_case_for_conversation,
    load_case,
    update_case,
)
from .customer_quotes import (
    evaluate_bounded_quote_authority,
    issue_bounded_quote,
)
from .events import emit_event
from .identity import load_status_binding, bound_order_status
from .llm import draft_with_cortex
from .policy import authorize
from .pricing_governance import pricing_operator_query
from products.commercial_pricing_registry import canonical_product_name
from .router import route_message
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



def _is_affirmative_continuation(text: str) -> bool:
    """
    True only for short confirmation language.

    This may retain an already-selected canonical product.
    It does not itself select a product or create authority.
    """
    return bool(
        re.fullmatch(
            r"\s*(?:"
            r"yes(?:\s+please)?|"
            r"please\s+do|"
            r"go\s+ahead|"
            r"proceed|"
            r"continue|"
            r"sure|"
            r"ok(?:ay)?"
            r")\s*[.!]?\s*",
            str(text or ""),
            re.IGNORECASE,
        )
    )


def _is_price_acceptance(text: str) -> bool:
    """
    Detect explicit customer acceptance of an already-governed
    PRICE_RECOMMENDED case.

    This signal never creates authority by itself. It only permits the
    bounded quote-authority policy to be evaluated.
    """
    value = str(text or "").strip().lower()

    if not value:
        return False

    if _is_affirmative_continuation(value):
        return True

    acceptance_terms = (
        "i accept",
        "accept the price",
        "accept this price",
        "happy with the price",
        "happy with that price",
        "happy with the r",
        "please proceed",
        "go ahead",
        "let's proceed",
        "lets proceed",
    )

    return any(term in value for term in acceptance_terms)


def _bind_live_customer_case(
    *,
    presence_root: Path,
    conv: dict[str, Any],
    correlation: str,
    envelope: dict[str, Any],
    attachment_record: dict[str, Any] | None,
    commercial: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Bind live Presence custody/routing truth into the canonical customer-case spine.

    This creates no quote, payment, fulfilment, parsing, execution or release authority.
    """
    metadata = envelope.get("metadata") or {}

    external_user_id = str(
        conv.get("external_user_id")
        or envelope.get("external_user_id")
        or metadata.get("external_user_id")
        or envelope.get("sender_id")
        or metadata.get("sender_id")
        or f"conversation:{correlation}"
    )

    resolved_product = str(
        ((commercial or {}).get("product") or {}).get("name")
        or ""
    ).strip() or None

    # Do not create empty commercial cases for every casual public turn.
    # Attachment custody or a deterministic product resolution is sufficient.
    if attachment_record is None and resolved_product is None:
        return None

    case = create_or_attach_case(
        presence_root,
        conversation_id=correlation,
        channel=str(envelope.get("channel") or conv.get("channel") or "conversation"),
        external_user_id=external_user_id,
        product_id=resolved_product,
        contact_email=(
            str(metadata.get("email") or "").strip()
            or None
        ),
        customer_id=(
            str(conv.get("customer_id") or metadata.get("customer_id") or "").strip()
            or None
        ),
    )

    if attachment_record is not None:
        incoming_sha = str(
            attachment_record.get("sha256") or ""
        ).strip().lower()

        scope = case.get("scope") or {}
        scoped_sha = str(
            scope.get("scope_scan_sha256") or ""
        ).strip().lower()

        commercial_state = case.get("commercial") or {}

        has_derived_truth = bool(scope) or (
            str(
                commercial_state.get("quote_state")
                or "not_prepared"
            )
            != "not_prepared"
        )

        if (
            incoming_sha
            and scoped_sha
            and incoming_sha != scoped_sha
            and has_derived_truth
        ):
            case = create_successor_case(
                presence_root,
                case,
                conversation_id=correlation,
                source_sha256=incoming_sha,
            )

    patch: dict[str, Any] = {}

    # Product routing may remain defeasible during early intake.
    # Once governed scope/commercial truth exists, the case product
    # identity is immutable. A later conversational product change
    # must not rewrite an already-derived customer case.
    product_rebind_stages = {
        "NEW_LEAD",
        "QUALIFIED",
        "INTAKE_OPEN",
        "FILES_RECEIVED_QUARANTINED",
    }

    case_stage = str(
        case.get("stage") or "NEW_LEAD"
    ).strip()

    if (
        resolved_product
        and resolved_product != case.get("product_id")
        and case_stage in product_rebind_stages
    ):
        history = list(case.get("product_history") or [])
        prior = str(case.get("product_id") or "").strip()

        if prior and prior not in history:
            history.append(prior)

        if resolved_product not in history:
            history.append(resolved_product)

        patch["product_id"] = resolved_product
        patch["product_history"] = history

    attachments = list(case.get("attachments") or [])

    candidate_records = []
    if attachment_record is not None:
        candidate_records.append(attachment_record)

    # Deployment/backfill continuity:
    # recover prior quarantined attachments already bound to this conversation.
    #
    # Successor cases must not resurrect attachments already owned by
    # predecessor lineage.
    predecessor_attachment_ids: set[str] = set()
    predecessor_id = str(
        case.get("predecessor_case_id") or ""
    ).strip()
    visited_predecessors: set[str] = set()

    while (
        predecessor_id
        and predecessor_id not in visited_predecessors
    ):
        visited_predecessors.add(predecessor_id)

        predecessor_case = load_case(
            presence_root,
            predecessor_id,
        )
        if predecessor_case is None:
            break

        for predecessor_attachment in (
            predecessor_case.get("attachments") or []
        ):
            if not isinstance(
                predecessor_attachment,
                dict,
            ):
                continue

            predecessor_attachment_id = str(
                predecessor_attachment.get(
                    "attachment_id"
                )
                or ""
            ).strip()

            if predecessor_attachment_id:
                predecessor_attachment_ids.add(
                    predecessor_attachment_id
                )

        predecessor_id = str(
            predecessor_case.get(
                "predecessor_case_id"
            )
            or ""
        ).strip()

    quarantine_root = presence_root / "quarantine"
    if quarantine_root.exists():
        for metadata_path in sorted(quarantine_root.glob("*/ATTACHMENT.json")):
            try:
                row = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if str(row.get("conversation_id") or "") != correlation:
                continue

            if (
                str(row.get("attachment_id") or "")
                in predecessor_attachment_ids
            ):
                continue

            if not any(
                str(existing.get("attachment_id") or "") == str(row.get("attachment_id") or "")
                for existing in candidate_records
                if isinstance(existing, dict)
            ):
                candidate_records.append(row)

    for candidate in candidate_records:
        aid = str(candidate.get("attachment_id") or "")
        if not aid or any(
            isinstance(row, dict) and str(row.get("attachment_id") or "") == aid
            for row in attachments
        ):
            continue

        attachments.append(
            {
                "attachment_id": aid,
                "conversation_id": correlation,
                "state": "quarantined",
                "sha256": candidate.get("sha256"),
                "size_bytes": candidate.get("size_bytes"),
                "original_file_name": candidate.get("original_file_name"),
                "mime_type": candidate.get("mime_type"),
                "safe_to_parse": False,
                "safe_to_execute": False,
            }
        )

    if attachments != list(case.get("attachments") or []):
        patch["attachments"] = attachments

    current_stage = str(case.get("stage") or "NEW_LEAD")
    stage = None

    if attachments:
        try:
            current_index = CASE_STAGES.index(current_stage)
            quarantine_index = CASE_STAGES.index("FILES_RECEIVED_QUARANTINED")
        except ValueError:
            current_index = quarantine_index = 0

        if current_index < quarantine_index:
            stage = "FILES_RECEIVED_QUARANTINED"

    if not patch and stage is None:
        return case

    evidence_bits = []
    if attachment_record is not None:
        evidence_bits.append(f"attachment:{attachment_record['attachment_id']}")
    if resolved_product:
        evidence_bits.append(f"product:{resolved_product}")

    return update_case(
        presence_root,
        case,
        stage=stage,
        patch=patch,
        evidence_ref=";".join(evidence_bits) or f"conversation:{correlation}",
    )


PRODUCT_COPY={
'homs':'HOMS turns curriculum intent into governed educator-ready work: assessments, marking support, lesson plans, slides, worksheets and lesson media. Educator approval remains the authority gate.',
'evidex':'Evidex turns scattered evidence into a review trail with claims, source mapping, provenance and gaps kept visible for human review.',
'sophia':'Sophia supports research review and guided learning while preserving authorship and human scholarship.',
'vamp':'VAMP maps performance evidence to tasks, objectives and review structures while leaving performance judgment with the authorised human.',
'nichefoundry':"NicheFoundry is DIO's media and campaign-production organ, used to turn validated ideas into audience-ready creative assets.",
'document_studio':'Document Studio translates, edits and formats governed source meaning into client-ready DOCX, PDF, slide, web and caption outputs, with reviewable terminology and layout checks.'
}

def _role(envelope:dict[str,Any])->str:
    trusted_edge_role=str(envelope.get('_trusted_edge_role') or 'public')
    return 'operator' if trusted_edge_role=='operator' and envelope.get('channel')=='telegram' and str(envelope.get('external_user_id')) in operator_ids() else 'public'

def _status_text(statuses:list[dict[str,Any]])->tuple[str,str]:
    parts=[]
    for s in statuses:
        if s.get('state')!='found': parts.append(f"{s.get('order_id')}: not currently present in DIO's local commerce state")
        else:
            fulfil='released' if s.get('fulfilment_released') else 'not released'
            parts.append(f"{s.get('order_id')}: payment {s.get('payment_state','unknown')}; fulfilment {fulfil}")
    return 'I found the order status bound to this verified conversation: '+ '; '.join(parts)+'.',json.dumps(statuses,sort_keys=True)

def _operator_brief_text(summary:dict[str,Any], focus:str='full')->str:
    jobs=summary.get('jobs',{}); mail=summary.get('mail',{}); commerce=summary.get('commerce',{}); market=summary.get('market',{}); needs=summary.get('needs_you',{})
    actions=summary.get('top_actions',[])
    first_actions='; '.join(f"{x.get('kind')}: {x.get('summary')}" for x in actions[:4]) or 'none waiting'
    if focus=='market':
        metrics=market.get('metrics',{})
        return (f"Market Command: {market.get('campaigns',0)} campaigns, {market.get('active',0)} active or approved, "
                f"{market.get('released',0)} released, {market.get('awaiting_approval',0)} campaign approvals waiting and "
                f"{market.get('content_awaiting_approval',0)} content approvals waiting. Metrics currently show "
                f"{metrics.get('impressions',0)} impressions, {metrics.get('clicks',0)} clicks, {metrics.get('enquiries',0)} enquiries and "
                f"{metrics.get('paid_orders',0)} paid orders. I have not published or spent anything.")
    if focus=='commerce':
        return (f"Commerce: {commerce.get('orders',0)} orders recorded, {commerce.get('paid',0)} paid, "
                f"{commerce.get('live_paid',0)} live paid and {commerce.get('paid_unreleased',0)} paid but unreleased. "
                "I have not released fulfilment or touched refunds.")
    if focus=='mail':
        return (f"Mail: {mail.get('total',0)} intents, {mail.get('pending',0)} pending and "
                f"{mail.get('approval_required',0)} still requiring approval. Top actions: {first_actions}. "
                "I have not sent anything.")
    if focus=='jobs':
        return (f"Jobs: {jobs.get('total',0)} total, by product {jobs.get('by_product',{})}, by state {jobs.get('by_state',{})}. "
                f"{len(jobs.get('awaiting_review',[]))} awaiting review and {len(jobs.get('delivery_ready',[]))} delivery drafts ready. "
                "I have not approved or delivered work.")
    return (f"Morning, Professor. DIO is awake: {jobs.get('total',0)} jobs, {mail.get('pending',0)} pending mail, "
            f"{commerce.get('paid_unreleased',0)} paid-unreleased order(s), {market.get('active',0)} active/approved campaigns, "
            f"{needs.get('open',0)} Needs You item(s), {summary.get('leads',{}).get('total',0)} lead(s), "
            f"{summary.get('incidents',{}).get('open_or_recorded',0)} recorded incident(s). Top actions: {first_actions}. "
            "I have not sent, approved, released, published, spent, or processed attachments.")

def _reply(decision:dict[str,Any],role:str,summary=None,needs=None,intake=None,statuses=None,attachment=None,capital=None,pricing=None)->tuple[str,str]:
    intent=decision['intent']; product=decision.get('product')
    if intent=='help':
        if role=='operator':
            return ("Operator commands: /status, /market, /commerce, /mail, /jobs, /needs, /help. "
                    "Plain-language equivalents also work: market command, paid orders, pending mail, delivery drafts, attention queue, capital priorities, grants, patronage and governed draft review. "
                    "I am read-only here: I can brief and route, but I cannot send mail, publish, spend, approve, release fulfilment, submit applications, accept funds, or process attachments."), 'operator_help'
        return ("I can explain DIO, HOMS, Evidex, Sophia, VAMP and Document Studio; capture a request; receive bounded uploads into quarantine; "
                "and explain translation or formatting. I cannot take payment, release work, or disclose private order status from an unverified chat."), 'public_help'
    if intent in CAPITAL_INTENTS and capital:
        return str(capital.get('text') or 'Capital & Support query completed.'),json.dumps(capital,sort_keys=True)
    if intent=='operator_summary' and summary:
        return _operator_brief_text(summary),json.dumps(summary,sort_keys=True)
    if intent in {'campaign_summary','revenue_summary','mail_summary','job_summary'} and summary:
        focus={'campaign_summary':'market','revenue_summary':'commerce','mail_summary':'mail','job_summary':'jobs'}[intent]
        return _operator_brief_text(summary,focus),json.dumps(summary,sort_keys=True)
    if intent=='needs_you':
        needs=needs or []
        if not needs: return 'Your Needs You queue is clear right now. Suspiciously civilised.','needs_you=0'
        top='; '.join(f"{x['needs_you_id']}: {x['summary'][:110]}" for x in needs[:5]); return f'You have {len(needs)} open Needs You item(s). Top items: {top}',f'needs_you={len(needs)}'
    if intent=='intake_request' and intake:
        suffix=f" I also quarantined attachment {attachment['attachment_id']} for human review; it has not been opened or parsed." if attachment else ''
        if role=='operator':
            return (f"Operator intake captured for {product.upper()} as {intake['intake_id']}; it is in human review. No charge, fulfilment start, or delivery commitment exists yet.{suffix}"),f"intake={intake['intake_id']}; state=pending_operator_review; role=operator"
        return f"I’ve captured this as a {product.upper()} intake ({intake['intake_id']}) and placed it in human review. I haven’t charged you, started fulfilment, or promised a delivery time yet.{suffix}",f"intake={intake['intake_id']}; state=pending_operator_review"
    if intent=='attachment_received' and attachment:
        if role=='operator':
            return (f"Operator rail: received {attachment['original_file_name']} and quarantined it as {attachment['attachment_id']}. Nothing has been opened, parsed, processed, or trusted yet."),f"attachment={attachment['attachment_id']}; state=quarantined; attachment_processed=false; role=operator"
        return f"I received {attachment['original_file_name']} and quarantined it as {attachment['attachment_id']}. DIO has not opened, parsed, executed, or trusted the file. A human can review and attach it to the right workflow.",f"attachment={attachment['attachment_id']}; state=quarantined; attachment_processed=false"
    if intent=='pricing_info' and pricing:
        return str(pricing.get('text') or 'Pricing intelligence resolved.'),json.dumps(pricing,sort_keys=True)
    if intent=='pricing_info':
        if role=='operator': return 'Operator pricing view: no deterministic price is bound to this turn yet. I can surface governed offer bands and scope evidence, but I will not invent a number.','pricing_not_resolved; role=operator'
        return 'Pricing is product- and scope-specific. I can capture what you need and prepare it for a human-approved quote rather than inventing a number at you.','pricing_not_resolved'
    if intent=='status_request' and statuses is not None: return _status_text(statuses)
    if intent=='status_request': return 'I can help with status, but this conversation has not yet been identity-bound to an order by DIO. I’ve put the request in the human queue rather than exposing customer information to an unverified chat.','public_status_lookup=identity_binding_required'
    if intent=='translation_info': return 'Yes. DIO’s localisation path is designed to translate structured meaning before final rendering, so terminology, grade level and layout can be checked rather than blindly translating a finished document. Human language review remains available as a gate.','translation=structured_meaning_first'
    if intent=='formatting_info': return 'Yes. DIO Format treats presentation as a governed render step: templates, document geometry, headings, tables, references, PowerPoint masters and delivery profiles can be applied without rewriting the underlying content.','formatting=render_layer'
    if intent=='product_info' and product:
        copy=PRODUCT_COPY.get(product,'I can explain that DIO workflow or capture an intake for it.')
        if role=='operator': return f"Operator view: {copy}",f'product={product}'
        return copy,f'product={product}'
    if intent=='general_info':
        if role=='operator':
            return ("You’re on Vesper’s operator rail. DIO is the governed operating system behind the product, evidence, commercial, market, and execution rails I brief you on. I can surface jobs, customer work, mail, payments, Needs You decisions, campaigns, and current system truth without selling DIO back to you."),'role=operator; operator_capabilities=bounded'
        return 'I’m Vesper, DIO’s Presence Core. I’m an AI system. I can explain HOMS, Evidex, Sophia, VAMP and Document Studio, capture a request, receive bounded document uploads, explain translation/formatting, and route sensitive work to a human authority gate. I don’t silently spend money, release work, or make professional judgments for you.','public_capabilities=bounded'
    return 'I’m not confident enough to route that safely yet. Tell me whether this is about HOMS, Evidex, Sophia, VAMP, translation/formatting, an uploaded file, or an existing DIO job and I’ll put it on the right rail.','classification=unresolved'

def _lingua_reply(*,dio_root:Path,envelope:dict[str,Any],decision:dict[str,Any],role:str,correlation:str,reply:str,interaction:dict[str,Any]|None=None,persona:dict[str,Any]|None=None)->tuple[str,dict[str,Any]]:
    metadata=envelope.get('metadata') or {}
    explicit_language=metadata.get('language') or metadata.get('locale') or envelope.get('language')
    target=requested_language(str(envelope.get('text') or ''),str(explicit_language) if explicit_language else None)
    artifact='operator_brief' if role=='operator' else 'conversation_response'
    interaction_context=None
    if interaction:
        policy=interaction.get('delivery_policy') or {}
        interaction_context={
            'observation_id':interaction.get('observation_id'),
            'delivery_mode':policy.get('mode'),
            'sales_pressure_allowed':policy.get('sales_pressure_allowed'),
            'humour_allowed':policy.get('humour_allowed'),
            'proof_priority':policy.get('proof_priority'),
            'voice':policy.get('voice'),
            'emotion_diagnosed':False,
            'personality_diagnosed':False,
        }
    persona_context=None
    if persona:
        package=persona.get('package') or {}
        persona_context={
            'assignment_id':persona.get('assignment_id'),
            'experiment_id':persona.get('experiment_id'),
            'experimental_assignment':persona.get('experimental_assignment'),
            'cell_id':package.get('cell_id'),
            'persona_id':package.get('persona_id'),
            'avatar_id':package.get('avatar_id'),
            'voice_candidate_id':package.get('voice_candidate_id'),
            'voice_profile_id':package.get('voice_profile_id'),
            'stable_for_conversation':True,
            'ai_disclosure_locked':True,
        }
    receipt=register_communication(
        dio_root=dio_root,
        owner='vesper',
        artifact_type=artifact,
        channel=str(envelope.get('channel') or 'conversation'),
        body=reply,
        audience='operator' if role=='operator' else 'public',
        privacy_domain='operator_private' if role=='operator' else 'public_communication',
        correlation_id=correlation,
        source_message_id=str(envelope.get('source_message_id') or metadata.get('source_message_id') or '' ) or None,
        source_language='English',
        target_language=target,
        purpose=str(decision.get('intent') or 'response'),
        authority_boundary='LINGUA may preserve and render Vesper meaning but cannot create send, spend, fulfilment, professional, identity, or release authority.',
        product_context=str(decision.get('product') or '') or None,
        interaction_context=interaction_context,
        persona_context=persona_context,
    )
    if receipt.get('translation_state')=='approved_translation':
        return str(receipt.get('selected_text') or reply),receipt
    return reply,receipt

def process_envelope(envelope:dict[str,Any],dio_root:Path,cfg:dict[str,Any])->dict[str,Any]:
    presence_root=dio_root/str(cfg.get('state_root','state/presence')); event_log=dio_root/str(cfg.get('event_log','telemetry/dio_events.jsonl')); routes_path=dio_root/str(cfg.get('routes_path','config/routes.json'))
    role=_role(envelope); conv=load_or_create_conversation(presence_root,envelope,role); text=str(envelope.get('text') or '').strip(); correlation=conv['conversation_id']
    conversation_state=load_conversation_state(presence_root,correlation)
    recent_turns=load_recent_conversation_turns(presence_root,correlation)
    metadata=envelope.get('metadata') or {}
    interaction=observe_interaction(
        state_root=dio_root/'state'/'lingua',
        conversation_id=correlation,
        text=text,
        channel=str(envelope.get('channel') or 'conversation'),
        role=role,
        source_message_id=str(envelope.get('source_message_id') or metadata.get('source_message_id') or '') or None,
    )
    policy=interaction.get('delivery_policy') or {}

    semantic_continuity=resolve_conversation_semantics(
        text=text,
        conversation_state=conversation_state,
        recent_turns=recent_turns,
        interaction=interaction,
    )
    emit_event(event_log,'presence.message_received','info','presence_conversation',correlation,{'channel':envelope.get('channel'),'role':role,'message_type':envelope.get('message_type','text'),'campaign_hint':(conv.get('attribution') or {}).get('campaign_hint')},correlation)
    emit_event(event_log,'presence.interaction_observed','info','lingua_interaction',interaction['observation_id'],{'delivery_mode':policy.get('mode'),'sales_pressure_allowed':policy.get('sales_pressure_allowed'),'humour_allowed':policy.get('humour_allowed'),'proof_priority':policy.get('proof_priority'),'emotion_diagnosed':False,'personality_diagnosed':False},correlation)
    attachment_record=None
    if envelope.get('attachment'):
        try:
            attachment_record=validate_and_store_attachment(presence_root,correlation,envelope['attachment'],cfg)
            emit_event(event_log,'presence.attachment_quarantined','action','presence_attachment',attachment_record['attachment_id'],{'channel':envelope.get('channel'),'sha256':attachment_record['sha256'],'size_bytes':attachment_record['size_bytes'],'automatic_processing':False},correlation)
        except AttachmentError as exc:
            emit_event(event_log,'presence.attachment_rejected','warning','presence_conversation',correlation,{'reason':str(exc)},correlation)
            return {'schema':'dio.presence_response.v2','conversation_id':correlation,'role':role,'decision':{'intent':'attachment_rejected','product':None,'confidence':1.0,'source':'policy','reason':str(exc)},'reply':{'text':f"I refused that upload safely: {exc}",'mode':'text','voice_eligible':False},'authority':{'executed_external_action':False,'spend_authorized':False,'fulfilment_released':False,'attachment_processed':False},'attachment':None,'intake':None,'interaction':interaction,'persona':None,'lingua':{'state':'not_registered','reason':'attachment_rejected_before_response_registration'}}
    decision=route_message(text,role,routes_path).as_dict()
    if attachment_record and decision['intent'] in {'unknown','general_info'}:
        decision={'intent':'attachment_received','product':decision.get('product'),'confidence':1.0,'source':'attachment_policy','reason':'quarantined attachment requires human routing'}
    ok,reason=authorize(role,decision['intent'])
    if not ok: decision={'intent':'unknown','product':None,'confidence':1.0,'source':'policy','reason':reason}

    current_customer_case = find_case_for_conversation(
        presence_root,
        correlation,
    )

    active_case_product = None
    if current_customer_case is not None:
        active_case_stage = str(
            current_customer_case.get("stage") or ""
        ).strip()

        active_commercial_stages = {
            "PRICE_RECOMMENDED",
            "QUOTE_READY",
            "NEEDS_YOU",
            "INVOICE_DRAFTED",
            "INVOICE_SEND_APPROVAL",
            "INVOICE_SENT",
            "PAYMENT_PENDING",
            "PAYMENT_VERIFIED",
            "WORK_QUEUED",
            "PROCESSING",
            "REVIEW_READY",
            "RELEASE_APPROVAL",
        }

        if active_case_stage in active_commercial_stages:
            active_case_product = str(
                current_customer_case.get(
                    "product_id"
                )
                or ""
            ).strip() or None

    commercial=None
    if should_ground_commercial(
        role=role,
        intent=decision['intent'],
        text=text,
        attachment_present=bool(attachment_record),
    ):
        try:
            # Explicit product context remains authoritative.
            # Lingua owns defeasible conversational continuity.
            explicit_incarnation_hint=(
                str(
                    metadata.get('incarnation_hint')
                    or envelope.get('incarnation_hint')
                    or ''
                ).strip()
                or None
            )

            semantic_referent=(
                str(
                    (
                        semantic_continuity.get('active_referent')
                        or {}
                    ).get('value')
                    or ''
                ).strip()
                or None
            )

            # Persisted buyer scope is defeasible context only.
            # Explicit evidence in the current message still wins.
            persisted_tier_hint=None

            for constraint in reversed(
                list(
                    conversation_state.get(
                        'known_constraints'
                    )
                    or []
                )
            ):
                if isinstance(constraint,str):
                    prefix='buyer_scope:'
                    if constraint.startswith(prefix):
                        persisted_tier_hint=(
                            constraint[len(prefix):].strip()
                            or None
                        )
                        break

                elif isinstance(constraint,dict):
                    if constraint.get('kind') == 'buyer_scope':
                        persisted_tier_hint=(
                            str(
                                constraint.get('value')
                                or ''
                            ).strip()
                            or None
                        )
                        break

            if explicit_incarnation_hint:
                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=explicit_incarnation_hint,
                    context_tier_hint=persisted_tier_hint,
                )
            elif (
                decision.get("product")
                and str(decision.get("product")).strip()
            ):
                explicit_product_name = canonical_product_name(
                    dio_root,
                    str(decision.get("product")).strip(),
                )

                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=explicit_product_name,
                    context_tier_hint=persisted_tier_hint,
                )
            elif active_case_product:
                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=active_case_product,
                    context_tier_hint=persisted_tier_hint,
                )
            elif (
                semantic_continuity.get('relation')
                == 'CONTINUATION'
                and semantic_continuity.get(
                    'retain_active_referent'
                ) is True
                and semantic_referent
            ):
                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=semantic_referent,
                    context_tier_hint=persisted_tier_hint,
                )
            elif (
                _is_affirmative_continuation(text)
                and str(
                    conversation_state.get('selected_product') or ''
                ).strip()
            ):
                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=str(
                        conversation_state.get('selected_product')
                    ).strip(),
                    context_tier_hint=persisted_tier_hint,
                )
            else:
                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=None,
                    context_tier_hint=persisted_tier_hint,
                )

            emit_event(
                event_log,
                'presence.commercial_grounding_resolved',
                'info',
                'presence_conversation',
                correlation,
                {
                    'state':commercial.get('state'),
                    'product':(
                        (commercial.get('product') or {}).get('name')
                    ),
                    'clarification_required':commercial.get(
                        'clarification_required'
                    ),
                    'authority_created':False,
                },
                correlation,
            )
        except Exception as exc:
            commercial={
                'schema':'dio.vesper.commercial_grounding.v1',
                'state':'UNAVAILABLE',
                'reason':str(exc)[:300],
                'product':None,
                'pricing':None,
                'authority_created':False,
                'external_effects':False,
            }
            emit_event(
                event_log,
                'presence.commercial_grounding_failed',
                'warning',
                'presence_conversation',
                correlation,
                {'error':str(exc)[:180]},
                correlation,
            )
    customer_case=_bind_live_customer_case(
        presence_root=presence_root,
        conv=conv,
        correlation=correlation,
        envelope=envelope,
        attachment_record=attachment_record,
        commercial=commercial,
    )
    if customer_case is not None:
        emit_event(
            event_log,
            'presence.customer_case_bound',
            'info',
            'customer_case',
            customer_case['case_id'],
            {
                'conversation_id':correlation,
                'product_id':customer_case.get('product_id'),
                'attachment_ids':[
                    row.get('attachment_id')
                    for row in (customer_case.get('attachments') or [])
                    if isinstance(row,dict)
                ],
                'stage':customer_case.get('stage'),
                'customer_id':customer_case.get('customer_id'),
                'authority_created':False,
            },
            correlation,
        )

    # Customer acceptance is evidence of willingness to proceed, not
    # authority by itself. For an already governed PRICE_RECOMMENDED
    # case, evaluate the separately defined bounded quote policy.
    if (
        role == "public"
        and isinstance(customer_case, dict)
        and str(customer_case.get("stage") or "")
        == "PRICE_RECOMMENDED"
        and _is_price_acceptance(text)
    ):
        bounded_quote_authority = (
            evaluate_bounded_quote_authority(
                dio_root,
                customer_case,
            )
        )

        emit_event(
            event_log,
            "presence.bounded_quote_authority_evaluated",
            "info",
            "customer_case",
            customer_case["case_id"],
            {
                "decision": bounded_quote_authority.get(
                    "decision"
                ),
                "reason": bounded_quote_authority.get(
                    "reason"
                ),
                "buyer_class": bounded_quote_authority.get(
                    "buyer_class"
                ),
                "amount_zar": bounded_quote_authority.get(
                    "amount_zar"
                ),
                "autonomous_ceiling_zar":
                    bounded_quote_authority.get(
                        "autonomous_ceiling_zar"
                    ),
                "authority_created": False,
            },
            correlation,
        )

        if (
            bounded_quote_authority.get("decision")
            == "ALLOW"
        ):
            stable_quote_id = (
                "DIO-Q-"
                + str(customer_case["case_id"])
                .removeprefix("CASE-")
            )

            issued_quote = issue_bounded_quote(
                dio_root,
                presence_root,
                case_id=customer_case["case_id"],
                quote_id=stable_quote_id,
            )

            customer_case = load_case(
                presence_root,
                customer_case["case_id"],
            )

            emit_event(
                event_log,
                "presence.bounded_quote_issued",
                "action",
                "customer_quote",
                issued_quote["quote_id"],
                {
                    "case_id": issued_quote["case_id"],
                    "amount": issued_quote["amount"],
                    "currency": issued_quote["currency"],
                    "approval_mode": (
                        issued_quote.get("approval")
                        or {}
                    ).get("mode"),
                    "payment_authority_created": False,
                    "fulfilment_authority_created": False,
                    "release_authority_created": False,
                },
                correlation,
            )

    explicit_language=metadata.get('language') or metadata.get('locale') or envelope.get('language')
    target_language=requested_language(text,str(explicit_language) if explicit_language else None)
    persona=assign_persona(
        root=dio_root,
        conversation_id=correlation,
        role=role,
        channel=str(envelope.get('channel') or 'conversation'),
        audience=str(metadata.get('audience') or ('operator' if role=='operator' else 'public')),
        product=str(
            ((commercial or {}).get('product') or {}).get('name')
            or decision.get('product')
            or ''
        ) or None,
        language=target_language,
    )
    voice_profile_id=((persona.get('package') or {}).get('voice_profile_id'))
    voice_plan=build_voice_plan(root=dio_root,language=target_language,interaction=interaction,requested_profile=voice_profile_id)
    emit_event(event_log,'presence.persona_assigned','info','vesper_persona',persona['assignment_id'],{'experimental_assignment':persona.get('experimental_assignment'),'cell_id':((persona.get('package') or {}).get('cell_id')),'persona_id':((persona.get('package') or {}).get('persona_id')),'avatar_id':((persona.get('package') or {}).get('avatar_id')),'voice_profile_id':voice_profile_id,'stable_for_conversation':True},correlation)
    summary=None; needs=None; intake=None; statuses=None; capital=None; pricing=None
    if decision['intent'] in CAPITAL_INTENTS:
        capital=capital_query(dio_root,decision['intent'],text)
    elif decision['intent']=='pricing_info' and role=='operator':
        pricing=pricing_operator_query(dio_root,state_root=presence_root,text=text,product_hint=decision.get('product'))
    elif decision['intent'] in {'operator_summary','campaign_summary','revenue_summary','mail_summary','job_summary'}: summary=operator_summary(dio_root,presence_root)
    elif decision['intent']=='needs_you': needs=list_needs_you(presence_root,20)
    elif decision['intent']=='intake_request' and decision.get('product'):
        intake=create_intake(presence_root,conv,str(decision['product']),text,envelope.get('source_message_id'),attachment_ids=[attachment_record['attachment_id']] if attachment_record else None)
        item=create_needs_you(presence_root,reason='public_intake_review',conversation_id=correlation,product=decision['product'],summary=f"Review {decision['product']} intake {intake['intake_id']}: {text[:300]}")
        emit_event(event_log,'presence.intake_received','action','presence_intake',intake['intake_id'],{'product':decision['product'],'needs_you_id':item['needs_you_id'],'automatic_fulfilment':False,'attachment_ids':intake.get('attachment_ids',[])},correlation)
    elif decision['intent']=='attachment_received' and attachment_record:
        item=create_needs_you(presence_root,reason='public_attachment_review',conversation_id=correlation,product=decision.get('product'),summary=f"Review quarantined attachment {attachment_record['attachment_id']}: {attachment_record['original_file_name']}")
        emit_event(event_log,'presence.attachment_review_required','action','presence_attachment',attachment_record['attachment_id'],{'needs_you_id':item['needs_you_id']},correlation)
    elif decision['intent']=='status_request':
        binding=load_status_binding(presence_root,correlation)
        if binding:
            statuses=bound_order_status(dio_root,binding)
            emit_event(event_log,'presence.status_disclosed','info','presence_conversation',correlation,{'binding_id':binding['binding_id'],'order_count':len(statuses),'disclosure':'minimal_status_only'},correlation)
        else:
            item=create_needs_you(presence_root,reason='public_status_identity_required',conversation_id=correlation,product=decision.get('product'),summary=f'Public user requested status lookup: {text[:300]}')
            emit_event(event_log,'presence.status_escalated','action','presence_conversation',correlation,{'needs_you_id':item['needs_you_id']},correlation)
    fallback,facts=_reply(decision,role,summary,needs,intake,statuses,attachment_record,capital,pricing=pricing)

    grounded_facts=facts
    if commercial is not None:
        grounded_facts=(
            facts
            + '\n'
            + commercial_facts(commercial)
        )
        if decision['intent'] in {
            'unknown',
            'product_info',
            'pricing_info',
        }:
            grounded_fallback=commercial_fallback(
                commercial,
                intent=decision['intent'],
            )
            if grounded_fallback:
                fallback=grounded_fallback

    knowledge=retrieve_conversation_knowledge(
        dio_root,
        text,
        conversation_state,
    )

    governed_context=dict(knowledge)

    semantic_world_state={
        'role':role,
        'audience':str(
            metadata.get('audience')
            or (
                'operator'
                if role=='operator'
                else 'public'
            )
        ),
        'commercial_state':str(
            (commercial or {}).get('state')
            or 'NONE'
        ),
    }

    semantic_capabilities={
        'semantic_continuity':bool(
            semantic_continuity
        ),
        'commercial_grounding':bool(
            commercial is not None
        ),
        'pricing_registry_read':bool(
            commercial is not None
            and str(
                (commercial or {}).get('state')
                or ''
            )=='RESOLVED'
        ),
        'operator_rail':bool(
            role=='operator'
        ),
    }

    commercial_semantic_state=str(
        (commercial or {}).get('state')
        or 'NONE'
    )

    if (
        commercial_semantic_state
        == 'NEEDS_CLARIFICATION'
    ):
        commercial_semantic_state='AMBIGUOUS'

    commercial_product_resolved=bool(
        (
            (commercial or {})
            .get('product')
            or {}
        ).get('name')
    )

    semantic_evidence={
        'relation':str(
            semantic_continuity.get(
                'relation'
            )
            or 'UNRESOLVED'
        ),
        'speech_act':str(
            semantic_continuity.get(
                'speech_act'
            )
            or 'UNRESOLVED'
        ),
        'commercial_resolution':
            commercial_semantic_state,
        'product_resolved':
            commercial_product_resolved,
    }

    semantic_policy={
        'semantic_policy_version':
            'vesper.semantic-policy.v1',
        'authority_created':False,
        'quote_issue_authority':False,
        'external_send_authority':False,
        'spend_authority':False,
        'fulfilment_release_authority':False,
    }

    semantic_temporal_scope={
        'scope':'current_request',
        'semantic_context_version':
            'dio.vesper.semantic_context.v1',
    }

    current_semantic_context=(
        build_current_semantic_context(
            role=role,
            text=text,
            semantic_continuity=
                semantic_continuity,
            conversation_state=
                conversation_state,
            commercial=commercial or {},
            decision=decision,
            world_state=
                semantic_world_state,
            capabilities=
                semantic_capabilities,
            evidence=
                semantic_evidence,
            policy=
                semantic_policy,
            temporal_scope=
                semantic_temporal_scope,
        )
    )

    crystal=resolve_conversation_crystal(
        root=dio_root,
        text=text,
        role=role,
        semantic_context=
            current_semantic_context,
    )

    if (
        crystal
        and crystal.get('provider_called') is False
        and crystal.get('authority_created') is False
        and crystal.get('external_effects') is False
    ):
        governed_context[
            'verified_semantic_crystal'
        ]=crystal

    governed_context[
        'current_semantic_context'
    ]={
        'schema':
            current_semantic_context.get(
                'schema'
            ),
        'semantic_domain':
            current_semantic_context.get(
                'semantic_domain'
            ),
        'semantic_match_digest':
            current_semantic_context.get(
                'semantic_match_digest'
            ),
        'authority_created':False,
        'external_effects':False,
    }

    governed_context.update({
        'role':role,
        'audience':str(
            metadata.get('audience')
            or ('operator' if role=='operator' else 'public')
        ),
        'customer_message':text[:2500],
        'semantic_continuity':semantic_continuity,
        'commercial_truth':commercial,
        'authority_created':False,
    })

    resolved_product=str(
        ((commercial or {}).get('product') or {}).get('name')
        or decision.get('product')
        or ''
    ) or None

    draft_turns=[
        *recent_turns,
        {
            'role':'user',
            'text':text,
            'act':decision.get('intent'),
            'product':resolved_product,
        },
    ]

    reply=draft_with_cortex(
        decision,
        grounded_facts,
        fallback,
        interaction,
        persona,
        conversation_state=conversation_state,
        recent_turns=draft_turns,
        governed_context=governed_context,
    )
    commercial_action=commercial_surface_state(customer_case)

    # Once an immutable quote exists, issued case truth outranks generic
    # product-tier pricing representation.
    quote_ready_reply = None

    if (
        role == "public"
        and isinstance(customer_case, dict)
        and str(customer_case.get("stage") or "")
        == "QUOTE_READY"
    ):
        case_commercial = (
            customer_case.get("commercial") or {}
        )

        case_product = str(
            customer_case.get("product_id") or ""
        ).strip()

        quoted_amount = case_commercial.get("amount")
        quote_id = str(
            case_commercial.get("quote_id") or ""
        ).strip()

        scope = customer_case.get("scope") or {}
        scope_quantity = (
            scope.get("quantity")
            or case_commercial.get("scope_quantity")
        )

        scope_unit = str(
            scope.get("primary_scope_unit")
            or case_commercial.get("scope_unit")
            or ""
        ).strip()

        if (
            case_product
            and isinstance(quoted_amount, int)
            and quoted_amount > 0
            and quote_id
        ):
            scope_text = ""

            if scope_quantity and scope_unit:
                scope_text = (
                    f" and bound to the governed "
                    f"{scope_quantity} {scope_unit} scope"
                )

            quote_ready_reply = (
                f"Your {case_product} quote is now issued at "
                f"R{quoted_amount:,}{scope_text}. "
                "No payment has been received yet. "
                "Fulfilment and release remain locked until "
                "their separate governed authority steps."
            )

    if quote_ready_reply is not None:
        reply = quote_ready_reply

    # A governed case-specific recommendation outranks generic product
    # reference pricing for a continuation of that same priced case.
    #
    # This is representation of existing case truth only. It creates
    # no quote, payment, spend, fulfilment, send, or release authority.
    case_price_reply = None

    if (
        role == "public"
        and decision.get("intent") == "pricing_info"
        and isinstance(customer_case, dict)
        and str(customer_case.get("stage") or "") == "PRICE_RECOMMENDED"
    ):
        case_product = str(
            customer_case.get("product_id") or ""
        ).strip()

        grounded_product = str(
            ((commercial or {}).get("product") or {}).get("name")
            or ""
        ).strip()

        case_commercial = customer_case.get("commercial") or {}
        recommended_amount = case_commercial.get(
            "recommended_amount_zar"
        )

        if (
            case_product
            and grounded_product == case_product
            and isinstance(recommended_amount, int)
            and recommended_amount > 0
        ):
            case_price_reply = (
                f"The current recommendation for this {case_product} "
                f"case is R{recommended_amount:,}. "
                "I've kept that recommendation bound to this case. "
                "It is not yet an issued quote or invoice, and your "
                "message does not create payment, fulfilment, or release "
                "authority. A separate authorised quote step is still "
                "required before payment can proceed."
            )

    if case_price_reply is not None:
        reply = case_price_reply

    if (
        role == 'public'
        and isinstance(commercial_action, dict)
        and commercial_action.get('state') == 'PAYMENT_PENDING'
    ):
        quoted=(
            (commercial_action.get('quoted') or {}).get('display')
            or ''
        )
        settlement=(
            (commercial_action.get('settlement') or {}).get('display')
            or ''
        )
        checkout_url=(
            ((commercial_action.get('checkout') or {}).get('approval_url'))
            or ''
        )

        if quoted and settlement and checkout_url:
            reply=(
                reply.rstrip()
                + '\n\n'
                + f'Your approved quote is {quoted}. '
                + f'PayPal will process the settlement as {settlement}.'
                + '\n'
                + f'Pay securely with PayPal: {checkout_url}'
            )

    try:
        reply,lingua=_lingua_reply(dio_root=dio_root,envelope=envelope,decision=decision,role=role,correlation=correlation,reply=reply,interaction=interaction,persona=persona)
    except Exception as exc:
        lingua={'schema':'dio.lingua.communication_receipt.v1','state':'registration_failed','error':str(exc)[:300],'external_action_executed':False,'send_authorized':False,'authority_created':False}
        emit_event(event_log,'presence.lingua_registration_failed','warning','presence_conversation',correlation,{'error':str(exc)[:180]},correlation)
    append_conversation_turn(
        presence_root,
        correlation,
        role='user',
        text=text,
        act=decision.get('intent'),
        product=resolved_product,
    )
    append_conversation_turn(
        presence_root,
        correlation,
        role='vesper',
        text=reply,
        act=decision.get('intent'),
        product=resolved_product,
    )

    conversation_state['turn_count']=int(
        conversation_state.get('turn_count',0)
    )+1
    conversation_state['last_route_intent']=decision.get('intent')

    commercial_pricing=(
        (commercial or {}).get('pricing')
        or {}
    )

    commercial_selected_tier=(
        commercial_pricing.get('selected_tier')
        or {}
    )

    if (
        commercial_pricing.get('tier_basis')
        == 'EXPLICIT_MESSAGE'
        and commercial_selected_tier.get('tier_id')
    ):
        buyer_scope_value=str(
            commercial_selected_tier.get('tier_id')
        ).strip()

        constraints=[
            constraint
            for constraint in (
                conversation_state.get(
                    'known_constraints'
                )
                or []
            )
            if not (
                isinstance(constraint,str)
                and constraint.startswith(
                    'buyer_scope:'
                )
            )
            and not (
                isinstance(constraint,dict)
                and constraint.get('kind')
                    == 'buyer_scope'
            )
        ]

        constraints.append(
            'buyer_scope:' + buyer_scope_value
        )

        conversation_state[
            'known_constraints'
        ]=constraints

    if resolved_product:
        conversation_state['candidate_products']=[resolved_product]
        conversation_state['selected_product']=resolved_product

    save_conversation_state(
        presence_root,
        conversation_state,
    )

    update_conversation(
        presence_root,
        conv,
        decision['intent'],
        resolved_product,
    )
    emit_event(event_log,'presence.reply_prepared','info','presence_conversation',correlation,{'intent':decision['intent'],'product':decision.get('product'),'role':role,'llm_advisory':decision.get('source')=='ollama_advisory','lingua_object_id':lingua.get('object_id'),'lingua_translation_state':lingua.get('translation_state'),'interaction_observation_id':interaction.get('observation_id'),'delivery_mode':policy.get('mode'),'persona_assignment_id':persona.get('assignment_id'),'persona_cell_id':((persona.get('package') or {}).get('cell_id'))},correlation)
    return {'schema':'dio.presence_response.v2','conversation_id':correlation,'role':role,'decision':decision,'reply':{'text':reply,'mode':'text','voice_eligible':bool(envelope.get('message_type') in {'voice','audio'}),'voice_policy':policy.get('voice'),'voice_plan':voice_plan,'avatar_id':((persona.get('package') or {}).get('avatar_id'))},'authority':{'executed_external_action':False,'spend_authorized':False,'fulfilment_released':False,'attachment_processed':False,'send_authorized':False,'submission_authorized':False,'financial_commitment_authorized':False},'attachment':attachment_record,'intake':intake,'status':statuses,'capital':capital,'pricing':pricing,'commercial':commercial,'commercial_action':commercial_action,'interaction':interaction,'persona':persona,'lingua':lingua}
