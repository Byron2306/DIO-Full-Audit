from __future__ import annotations
import json
import re
from pathlib import Path
from .config import state_path
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
    serialized_case_write,
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
from products.commercial_pricing_registry import build_commercial_pricing_registry, canonical_product_name
from .router import route_message
from .commercial_cognition import _document_operation_override
from .scope_capture import extract_customer_scope_observations
from .intake_scope_quote import open_intake, record_intake_inputs
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
    read_json,
    write_json,
)
from .voice import build_voice_plan
from .vesper_journey_runtime import build_vesper_journey_view
from .product_binding_registry import compile_product_journey_binding



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


@serialized_case_write
def _bind_live_customer_case(
    *,
    presence_root: Path,
    conv: dict[str, Any],
    correlation: str,
    envelope: dict[str, Any],
    attachment_record: dict[str, Any] | None,
    commercial: dict[str, Any] | None,
    quarantined_attachments: list[dict[str, Any]] | None = None,
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
    if attachment_record is None and resolved_product is None and not quarantined_attachments:
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

    incoming_records = ([attachment_record] if attachment_record is not None else []) + list(quarantined_attachments or [])
    if incoming_records:
        scope_sha = str((case.get("scope") or {}).get("scope_scan_sha256") or "").strip().lower()
        changed = [row for row in incoming_records if str(row.get("sha256") or "").lower() != scope_sha]
        incoming_sha = str((changed[0] if changed else incoming_records[0]).get("sha256") or "").strip().lower()

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

    attachment_review_state_changed = False
    for row in attachments:
        if not isinstance(row, dict):
            continue
        if str(row.get("state") or "").casefold() == "quarantined":
            if "review_state" not in row:
                row["review_state"] = "ATTACHMENT_QUARANTINED"
                attachment_review_state_changed = True

    candidate_records = []
    candidate_records.extend(quarantined_attachments or [])
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
                "review_state": "ATTACHMENT_QUARANTINED",
                "sample_review_approved": False,
                "sha256": candidate.get("sha256"),
                "size_bytes": candidate.get("size_bytes"),
                "original_file_name": candidate.get("original_file_name"),
                "mime_type": candidate.get("mime_type"),
                "safe_to_parse": False,
                "safe_to_execute": False,
            }
        )

    if attachment_review_state_changed or attachments != list(case.get("attachments") or []):
        patch["attachments"] = attachments
    quarantined_ids = [
        str(row.get("attachment_id") or "")
        for row in attachments
        if isinstance(row, dict)
        and str(row.get("state") or "").casefold() == "quarantined"
        and str(row.get("review_state") or "ATTACHMENT_QUARANTINED") != "SAMPLE_REVIEW_APPROVED"
    ]
    if quarantined_ids:
        patch["sample_review"] = {
            "state": "ATTACHMENT_QUARANTINED",
            "attachment_ids": quarantined_ids,
            "operator_review_required": True,
            "review_completed": False,
            "approved": False,
            "authority_created": False,
        }

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


def _product_scope_units(dio_root: Path, product_id: str) -> tuple[str | None, list[str]]:
    try:
        canonical = canonical_product_name(dio_root, product_id)
        registry = build_commercial_pricing_registry(dio_root)
    except (OSError, ValueError, KeyError):
        # Scope capture must remain available even when a deployment has an
        # incomplete pricing census. Pricing gaps must never erase intake facts.
        return None, []
    row = next((item for item in registry.get("products", []) if item.get("name") == canonical), None)
    if not isinstance(row, dict):
        return None, []
    primary = str(row.get("primary_scope_unit") or "").strip() or None
    secondary = [str(value).strip() for value in row.get("secondary_scope_units") or [] if str(value).strip()]
    return primary, secondary


def _merge_case_scope_observations(
    dio_root: Path,
    presence_root: Path,
    case: dict[str, Any] | None,
    *,
    text: str,
    recent_turns: list[dict[str, Any]],
    source_message_id: str | None,
) -> dict[str, Any] | None:
    """Persist literal customer scope statements for any catalog product."""
    if not isinstance(case, dict) or not str(case.get("product_id") or "").strip():
        return case
    primary_unit, secondary_units = _product_scope_units(dio_root, str(case["product_id"]))
    recognized_units = [value for value in [primary_unit, *secondary_units] if value]
    prior_user_messages = [
        row for row in recent_turns
        if isinstance(row, dict) and str(row.get("role") or "").casefold() == "user"
    ]
    message_rows = prior_user_messages + [{"role": "user", "text": text, "source_message_id": source_message_id}]
    observations = []
    seen_messages: set[str] = set()
    for index, row in enumerate(message_rows):
        message = str(row.get("text") or "").strip()
        if not message:
            continue
        observation = extract_customer_scope_observations(
            message,
            source_message_id=(
                str(row.get("source_message_id") or "").strip()
                or (str(source_message_id) if index == len(message_rows) - 1 and source_message_id else None)
                or f"history:{row.get('observed_at') or observation_digest(message)[:16]}"
            ),
            product_id=str(case["product_id"]),
            recognized_units=recognized_units,
        )
        if observation.get("message_sha256") in seen_messages:
            continue
        seen_messages.add(str(observation.get("message_sha256") or ""))
        if any(observation.get(key) for key in (
            "quantities", "requested_formats", "requirements", "exclusions",
            "deadline_statements", "data_classification_statements", "requested_outcome_statements",
        )):
            observations.append(observation)
    if not observations:
        return case

    scope = dict(case.get("scope") or {})
    customer_scope = dict(scope.get("customer_stated") or {})
    prior = list(customer_scope.get("observations") or [])
    for stored in prior:
        if not isinstance(stored, dict):
            continue
        stored["quantities"] = [
            item for item in stored.get("quantities") or []
            if not re.search(r"\b\d+[A-Za-z0-9]{5,}\b", str(item.get("source_text") or ""))
            and str(item.get("unit") or "").casefold() not in {"formatted", "edited", "processed", "reviewed", "checked", "approved", "requested", "required"}
        ]
        stored["exclusions"] = [
            item for item in stored.get("exclusions") or []
            if not (str(item.get("item") or "").strip().casefold() == "approval"
                    or re.search(r"\bwithout\s+(?:my|your|their)?\s*approval\b", str(item.get("source_text") or ""), re.I))
        ]
        stored["deadline_statements"] = [
            item for item in stored.get("deadline_statements") or []
            if not (re.search(r"\b(?:turnaround|delivery schedule)\b", str(item.get("source_text") or ""), re.I)
                    and not re.search(r"\b(?:deadline|due date|fixed date)\b", str(item.get("source_text") or ""), re.I))
        ]
    known_hashes = {str(item.get("message_sha256") or "") for item in prior if isinstance(item, dict)}
    for observation in observations:
        if observation.get("message_sha256") not in known_hashes:
            prior.append(observation)
            known_hashes.add(str(observation.get("message_sha256") or ""))
    customer_scope.update({
        "schema": "dio.customer_stated_scope.v1",
        "state": "CUSTOMER_STATED_UNVERIFIED",
        "observations": prior[-40:],
        "primary_scope_unit": primary_unit,
        "authority_created": False,
    })
    case = update_case(
        presence_root,
        case,
        patch={"scope": {"customer_stated": customer_scope}},
        evidence_ref="customer_scope_observation:" + ",".join(
            str(item.get("message_sha256") or "")[:16] for item in observations
        ),
    )

    # Populate only typed fields explicitly present in the customer statements.
    # Buyer class, eligibility, or other categorical judgments are never inferred.
    outcome = next((
        statement
        for observation in reversed(observations)
        for statement in reversed(observation.get("requested_outcome_statements") or [])
        if str(statement).strip()
    ), None)
    quantity = None
    if primary_unit:
        for observation in reversed(prior):
            for item in reversed(observation.get("quantities") or []):
                if str(item.get("unit") or "").casefold() != primary_unit.casefold():
                    continue
                if item.get("qualifier") not in {"maximum", "customer_stated"}:
                    continue
                value = item.get("value")
                if isinstance(value, int):
                    quantity = value
                    break
            if quantity is not None:
                break
    typed_inputs: dict[str, Any] = {}
    if outcome:
        typed_inputs["requested_outcome"] = str(outcome).strip()
    if quantity is not None:
        typed_inputs["scope_quantity"] = quantity
    try:
        if str(case.get("stage") or "") in {"NEW_LEAD", "QUALIFIED", "INTAKE_OPEN", "FILES_RECEIVED_QUARANTINED"}:
            open_intake(dio_root, presence_root, str(case["case_id"]))
            case = load_case(presence_root, str(case["case_id"])) or case
            if typed_inputs:
                case = record_intake_inputs(
                    dio_root,
                    presence_root,
                    str(case["case_id"]),
                    typed_inputs,
                    evidence_ref="customer_scope_observation:" + ",".join(
                        str(item.get("message_sha256") or "")[:16] for item in observations
                    ),
                )
    except (ValueError, OSError):
        # Observation capture remains available even when a downstream intake
        # stage is no longer writable; never roll back customer evidence.
        pass
    return load_case(presence_root, str(case["case_id"])) or case


def observation_digest(text: str) -> str:
    import hashlib
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _upsert_presence_intake(
    presence_root: Path,
    conv: dict[str, Any],
    *,
    product: str,
    summary: str,
    source_message_id: str | None,
    attachment_ids: list[str],
    case: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep one stable intake reference per conversation/product and link updates."""
    case_ref = str((case or {}).get("presence_intake_id") or "").strip()
    rows = []
    for path in (presence_root / "intakes").glob("PRES-*.json"):
        try:
            row = read_json(path)
        except Exception:
            continue
        if row.get("conversation_id") == conv.get("conversation_id") and row.get("product") == product:
            rows.append((path, row))
    rows.sort(key=lambda pair: str(pair[1].get("created_at") or ""))
    selected = next((pair for pair in rows if pair[1].get("intake_id") == case_ref), None)
    if selected is None:
        selected = next((pair for pair in rows if pair[1].get("state") not in {"superseded_duplicate", "closed"}), None)
    if selected is None:
        intake = create_intake(presence_root, conv, product, summary, source_message_id, attachment_ids=attachment_ids)
    else:
        path, intake = selected
        merged_ids = list(dict.fromkeys(list(intake.get("attachment_ids") or []) + list(attachment_ids or [])))
        updates = list(intake.get("updates") or [])
        update_ref = str(source_message_id or "").strip()
        if update_ref and update_ref not in {str(item.get("source_message_id") or "") for item in updates}:
            updates.append({"source_message_id": update_ref, "attachment_ids": list(attachment_ids or [])})
        intake.update({"attachment_ids": merged_ids, "updates": updates, "last_updated_at": _utc_now(), "state": "pending_operator_review"})
        write_json(path, intake)
    if case and str(case.get("presence_intake_id") or "") != str(intake.get("intake_id") or ""):
        case = update_case(presence_root, case, patch={"presence_intake_id": intake.get("intake_id")}, evidence_ref=f"presence_intake:{intake.get('intake_id')}")
    # Preserve the earliest valid intake ID and retire accidental duplicates
    # without deleting their audit history.
    for path, duplicate in rows:
        if duplicate.get("intake_id") == intake.get("intake_id") or duplicate.get("state") == "superseded_duplicate":
            continue
        duplicate["state"] = "superseded_duplicate"
        duplicate["superseded_by"] = intake.get("intake_id")
        duplicate["supersession_reason"] = "same_conversation_product_intake_reused"
        write_json(path, duplicate)
    return intake


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_quarantine_review_task(
    presence_root: Path,
    case: dict[str, Any] | None,
    *,
    conversation_id: str,
) -> dict[str, Any] | None:
    if not isinstance(case, dict):
        return None
    pending = [
        row for row in case.get("attachments") or []
        if isinstance(row, dict)
        and str(row.get("state") or "").casefold() == "quarantined"
        and str(row.get("review_state") or "ATTACHMENT_QUARANTINED") != "SAMPLE_REVIEW_APPROVED"
    ]
    if not pending:
        return None
    attachment_ids = [str(row.get("attachment_id") or "") for row in pending if row.get("attachment_id")]
    existing = None
    for path in (presence_root / "needs_you").glob("*.json"):
        try:
            item = read_json(path)
        except Exception:
            continue
        if (item.get("state") == "open" and item.get("reason") == "public_attachment_review"
                and item.get("conversation_id") == conversation_id
                and item.get("case_id") in {None, case.get("case_id")}):
            existing = item
            break
    if existing is None:
        existing = create_needs_you(
            presence_root,
            reason="public_attachment_review",
            conversation_id=conversation_id,
            product=str(case.get("product_id") or "") or None,
            summary=(f"Review quarantine and access authorization for attachment(s) {', '.join(attachment_ids)} "
                     f"on case {case.get('case_id')}. Do not parse or process before the review gate."),
        )
        existing["case_id"] = case.get("case_id")
        existing["attachment_ids"] = attachment_ids
        existing["review_action"] = "VERIFY_CUSTODY_AND_AUTHORIZE_SAMPLE_LAYOUT_REVIEW"
        write_json(presence_root / "needs_you" / f"{existing['needs_you_id']}.json", existing)
    else:
        existing["case_id"] = case.get("case_id")
        existing["product"] = case.get("product_id")
        existing["attachment_ids"] = list(dict.fromkeys(list(existing.get("attachment_ids") or []) + attachment_ids))
        existing["review_action"] = "VERIFY_CUSTODY_AND_AUTHORIZE_PRODUCT_REVIEW"
        existing["summary"] = (
            f"Review quarantine custody/access for attachment(s) {', '.join(existing['attachment_ids'])} "
            f"on case {case.get('case_id')}; do not parse or process before review authorization."
        )
        write_json(presence_root / "needs_you" / f"{existing['needs_you_id']}.json", existing)
    ids = list(dict.fromkeys(list(case.get("needs_you_ids") or []) + [str(existing.get("needs_you_id"))]))
    sample_review = dict(case.get("sample_review") or {})
    sample_review.update({
        "state": "ATTACHMENT_QUARANTINED",
        "attachment_ids": attachment_ids,
        "needs_you_id": existing.get("needs_you_id"),
        "operator_review_required": True,
        "review_completed": False,
        "approved": False,
        "authority_created": False,
    })
    return update_case(
        presence_root,
        case,
        patch={"needs_you_ids": ids, "sample_review": sample_review},
        evidence_ref=f"needs_you:{existing.get('needs_you_id')}",
    )


def _ensure_intake_review_task(
    presence_root: Path,
    case: dict[str, Any] | None,
    *,
    conversation_id: str,
    intake_id: str,
) -> dict[str, Any] | None:
    if not isinstance(case, dict) or not intake_id:
        return case
    item = None
    for path in (presence_root / "needs_you").glob("*.json"):
        try:
            candidate = read_json(path)
        except Exception:
            continue
        if (candidate.get("state") == "open"
                and candidate.get("reason") == "public_intake_review"
                and candidate.get("conversation_id") == conversation_id
                and intake_id in str(candidate.get("summary") or "")):
            item = candidate
            break
    if item is None:
        item = create_needs_you(
            presence_root,
            reason="public_intake_review",
            conversation_id=conversation_id,
            product=str(case.get("product_id") or "") or None,
            summary=f"Review {case.get('product_id')} intake {intake_id} for case {case.get('case_id')}; do not issue a quote or start fulfilment.",
        )
    item["case_id"] = case.get("case_id")
    item["intake_id"] = intake_id
    item["review_action"] = "REVIEW_CUSTOMER_STATED_SCOPE_AND_PRODUCT_REQUIREMENTS"
    write_json(presence_root / "needs_you" / f"{item['needs_you_id']}.json", item)
    ids = list(dict.fromkeys(list(case.get("needs_you_ids") or []) + [str(item.get("needs_you_id"))]))
    return update_case(
        presence_root,
        case,
        patch={"needs_you_ids": ids},
        evidence_ref=f"needs_you:{item.get('needs_you_id')}",
    )


def _case_scope_progress_reply(
    case: dict[str, Any],
    *,
    intake_reference: str | None,
) -> str:
    case_id = str(case.get("case_id") or "")
    scope = case.get("scope") or {}
    customer_stated = scope.get("customer_stated") or {}
    observations = [row for row in customer_stated.get("observations") or [] if isinstance(row, dict)]
    quantities: dict[str, dict[str, Any]] = {}
    formats = {}
    exclusions = []
    requirement_statements = []
    deadline_statements = []
    data_statements = []
    for row in observations:
        for quantity in row.get("quantities") or []:
            value = quantity.get("value")
            unit = str(quantity.get("unit") or "units")
            qualifier = str(quantity.get("qualifier") or "customer_stated")
            quantity_value = (value.get("maximum") if isinstance(value, dict) else value)
            display_unit = unit if quantity_value == 1 else (unit if unit.endswith("s") else unit + "s")
            if isinstance(value, dict):
                display = f"{value.get('minimum')}–{value.get('maximum')} {display_unit}"
            else:
                display = f"{value} {display_unit}"
            if qualifier == "maximum":
                display = "maximum " + display
            elif qualifier == "approximate":
                display = "approximately " + display
            rank = {"maximum": 3, "customer_stated": 2, "approximate": 1, "minimum": 0}.get(qualifier, 0)
            current = quantities.get(unit.casefold())
            if current is None or rank >= current["rank"]:
                quantities[unit.casefold()] = {"rank": rank, "display": display}
        for item in row.get("requested_formats") or []:
            formats[(item.get("format"), item.get("preference"))] = item
        exclusions.extend(item.get("item") for item in row.get("exclusions") or [] if item.get("item"))
        requirement_statements.extend(item.get("statement") for item in row.get("requirements") or [] if item.get("statement"))
        deadline_statements.extend(item.get("statement") for item in row.get("deadline_statements") or [] if item.get("statement"))
        data_statements.extend(item.get("statement") for item in row.get("data_classification_statements") or [] if item.get("statement"))
    details = []
    if quantities:
        details.append("scope quantities already recorded: " + ", ".join(row["display"] for row in quantities.values()))
    if formats:
        details.append("requested output formats: " + ", ".join(
            f"{name} ({'optional' if preference == 'optional' else 'requested'})"
            for name, preference in formats
        ))
    if exclusions:
        details.append("stated exclusions: " + ", ".join(dict.fromkeys(exclusions)))
    if deadline_statements:
        details.append("deadline/schedule instruction recorded: " + deadline_statements[-1])
    if data_statements:
        details.append("data classification recorded as customer-stated: " + data_statements[-1])
    if requirement_statements:
        details.append("requirements recorded from your messages; see the case scope record for the exact statements")
    scope_note = " I have retained " + "; ".join(details) + "." if details else " I have retained the scope details you supplied on the case."
    refs = []
    if intake_reference:
        refs.append(f"intake {intake_reference}")
    if case_id:
        refs.append(f"case {case_id}")
    reference_note = " This remains linked to " + " and ".join(refs) + "." if refs else ""
    sample_review = case.get("sample_review") or {}
    attachments = [row for row in case.get("attachments") or [] if isinstance(row, dict)]
    if attachments and str(sample_review.get("state") or "") == "ATTACHMENT_QUARANTINED":
        pending = [row for row in attachments if str(row.get("state") or "").casefold() == "quarantined"]
        hashes: dict[str, list[str]] = {}
        for row in pending:
            key = str(row.get("sha256") or row.get("attachment_id") or "unknown")
            hashes.setdefault(key, []).append(str(row.get("attachment_id") or ""))
        duplicate_note = (
            f" DIO has {len(pending)} attachment records with the same content hash, consistent with repeated uploads."
            if len(pending) > 1 and len(hashes) == 1 else ""
        )
        ids = ", ".join(str(row.get("attachment_id")) for row in pending if row.get("attachment_id"))
        review = (
            f" The uploaded attachment(s) {ids} are associated with this case and remain in quarantine. "
            + duplicate_note + " They have not been opened or inspected. An operator review is queued to verify custody/access and determine what review is authorized for this product. "
        )
    elif sample_review.get("state") == "SAMPLE_REVIEW_APPROVED":
        review = " The sample has a recorded operator approval for the stated review scope; this does not approve production or factual changes. "
    else:
        review = " No sample review approval is recorded. "
    intake = case.get("intake") or {}
    requirement = intake.get("requirement") or {}
    provided = intake.get("provided_inputs") or {}
    missing = list(requirement.get("missing_input_ids") or [])
    missing = [field for field in missing if field not in provided]
    if missing:
        labels = {"buyer_class": "the applicable buyer/pricing class", "scope_quantity": "a primary scope quantity", "requested_outcome": "the requested outcome"}
        missing_labels = [labels.get(field, field.replace("_", " ")) for field in missing]
        outstanding = " The intake still lacks " + ", ".join(missing_labels) + "; I will not infer those fields."
    else:
        outstanding = " The recorded customer-stated intake fields are complete; the operator must review them before a quotation is prepared."
    commercial = case.get("commercial") or {}
    quote_request = commercial.get("quote_request") or {}
    quote_request_id = str(quote_request.get("quote_request_id") or "").strip()
    if quote_request_id and commercial.get("quote_state") == "needs_operator_review":
        next_step = (
            f"A scoped quote request ({quote_request_id}) is queued for operator pricing review; it is not an issued quotation. "
            "No customer quote reference, price, validity period, or delivery schedule exists yet. The operator must review the quarantined sample and confirm the pricing basis and schedule before a written quote can be issued."
        )
    else:
        next_step = (
            "No quotation has been issued, so there is no quote reference, price, validity period, or delivery schedule yet. "
            "After the operator completes the required review and confirms the pricing basis, a written quotation will state the scope, inclusions, exclusions, assumptions, ZAR price, validity, and agreed schedule for your review."
        )
    upload_note = ""
    if attachments:
        upload_note = " Use the + Attach Files control to submit a file; this web intake accepts one attachment per message. Your sample is already recorded, so do not upload it again. Upload the remaining batch after you review and accept the written quotation."
    return (
        f"I confirm the attachment is recorded against case {case_id} in quarantine; I have not inspected its contents."
        + reference_note + scope_note + review + outstanding + " " + next_step + upload_note
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


def _case_intake_reply(name: str, profile: dict[str, Any], case: dict[str, Any], *, buyer_context_refined=False) -> str:
    """Describe existing intake requirements without accepting them or changing a case."""
    missing = (case.get('intake') or {}).get('requirement', {}).get('missing_input_ids')
    fields = [row for row in profile.get('required_inputs') or []
              if (missing is None or row.get('field_id') in missing)
              and not (buyer_context_refined and row.get('field_id') == 'buyer_class')]
    labels = {'requested_outcome': 'the outcome you want',
              'buyer_class': 'who the work is for',
              'scope_quantity': 'roughly how many {unit}s are involved'}
    parts = []
    for row in fields:
        field = str(row.get('field_id') or '')
        label = labels.get(field, field.replace('_', ' '))
        if field == 'scope_quantity':
            label = label.format(unit=str(row.get('semantic_unit') or 'work item').replace('_', ' '))
        parts.append(label)
    if not parts:
        return f'We have the initial details for {name}. I can explain the next step for your current case.'
    prefix = f'For {name}, that clarifies who the work is for. I still need ' if buyer_context_refined else f'For {name}, tell me '
    return prefix + ', '.join(parts[:-1]) + (', and ' if len(parts) > 1 else '') + parts[-1] + '.'


def _document_edit_discovery_reply() -> str:
    return (
        "For reports that already contain approved factual content and need consistent client-facing presentation, "
        "Document Studio Edit is the best starting service. It can standardise supplied branding, heading hierarchy, "
        "typography, tables, headers/footers and page layouts while preserving factual wording. Document Studio Publish "
        "is better after content and edits are approved, when you need the approved material prepared for a publication "
        "format; Localize is for language adaptation, which you have not requested. A typical process is: share one "
        "representative DOCX and any brand/style guide; an operator reviews the sample and confirms scope, exclusions, "
        "price and schedule; you review and accept a written quote; the team formats the agreed batch, flags any proposed "
        "wording changes separately, and returns reviewable files for your approval before delivery. Nothing is charged, "
        "edited or released by this recommendation."
    )


def _document_quote_scope_reply(
    product: str,
    case: dict[str, Any],
    message: str,
    *,
    presence_root: Path | None = None,
    conversation_id: str | None = None,
    intake_reference_hint: str | None = None,
) -> str | None:
    """Answer a document quote request with the actual scope and next steps."""
    if not re.search(r"\b(?:quote|quotation|estimate)\b", str(message or ""), re.I):
        return None
    if str(product or "") not in {
        "Document Studio Edit",
        "Document Studio Localize",
        "Document Studio Publish",
    }:
        return None

    stage = str(case.get("stage") or "")
    if stage in {"PRICE_RECOMMENDED", "QUOTE_READY", "INVOICE_DRAFTED", "INVOICE_SENT"}:
        return None

    details = {
        "Document Studio Edit": (
            "Document Studio Edit is the best fit: it can professionally edit and standardise "
            "headings, typography, tables, page layout and supplied branding while preserving "
            "the factual wording. Document Studio Publish is for preparing already-approved "
            "content for publication, so it is not the right first step for this editing job."
        ),
        "Document Studio Localize": (
            "Document Studio Localize is the right fit for adapting approved material into "
            "another language, with terminology and language review kept visible."
        ),
        "Document Studio Publish": (
            "Document Studio Publish is the right fit for preparing approved content into "
            "controlled publication formats while preserving its supplied wording."
        ),
    }[product]

    attachments = [
        row for row in case.get("attachments") or []
        if isinstance(row, dict)
    ]
    intake_reference = None
    if re.fullmatch(r"PRES-[A-Z0-9]{8,32}", str(intake_reference_hint or "")):
        intake_reference = str(intake_reference_hint)
    if presence_root is not None and conversation_id:
        candidates = re.findall(r"\bPRES-[A-Z0-9]{8,32}\b", str(message or "").upper())
        if intake_reference is None:
            candidates = [str(intake_reference_hint or "").upper(), *candidates]
        for candidate in candidates:
            path = Path(presence_root) / "intakes" / f"{candidate}.json"
            try:
                recorded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if str(recorded.get("conversation_id") or "") == str(conversation_id):
                intake_reference = candidate
                break
        if intake_reference is None:
            for path in sorted((Path(presence_root) / "intakes").glob("PRES-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
                try:
                    recorded = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if str(recorded.get("conversation_id") or "") == str(conversation_id):
                    intake_reference = str(recorded.get("intake_id") or path.stem)
                    break
    case_id = str(case.get("case_id") or "").strip()
    if intake_reference and case_id:
        reference_note = (
            f" I’ll retain your existing intake reference {intake_reference} and keep this "
            f"work linked to case {case_id}."
        )
    elif intake_reference:
        reference_note = f" I’ll retain your existing intake reference {intake_reference}."
    elif case_id:
        reference_note = f" This remains linked to case {case_id}."
    else:
        reference_note = ""
    if attachments:
        sample_step = (
            f"I can see {len(attachments)} uploaded file(s) recorded on this case. They remain in intake quarantine; "
            "an operator must clear and review the sample before scope assessment or production. I cannot verify "
            "encryption, retention duration or malware-scanning status from this chat."
        )
    else:
        sample_step = (
            "Please attach one representative English DOCX with typical headings, tables, and "
            "page layouts. It will be recorded in intake quarantine; an operator must clear and review it before "
            "scope assessment or production. I cannot verify encryption, retention duration or malware-scanning "
            "status from this chat."
        )

    return (
        details + reference_note + " To prepare a bounded quote, the next step is a human feasibility and scope "
        "review of one sample. No quotation has been issued: there is no quote reference, price, validity period or "
        "turnaround estimate to review yet. The proposed scope is visual formatting and consistency across the agreed "
        "batch; factual changes, substantive rewriting, translation, source research and publication are excluded unless "
        "separately scoped and approved. After sample review, an operator can prepare a written quote with included work, "
        "exclusions, ZAR price, assumptions, schedule, reference, validity and approval steps for your review. " + sample_step + " "
        "One sample cannot establish the total pages across all 12 reports, so please confirm "
        "the exact total or a maximum page cap; your current estimate is 96–180 pages. Also "
        "confirm final output format(s), deadline, whether grammar or house-style editing is "
        "allowed beyond visual formatting, and attach a style guide or logo if available. "
        "If the reports use several materially different layouts, tell me how many layout types "
        "the sample represents. This request has not authorised "
        "document processing, paid work or payment, and no quote has been issued."
    )

def _lingua_reply(*,dio_root:Path,envelope:dict[str,Any],decision:dict[str,Any],role:str,correlation:str,reply:str,interaction:dict[str,Any]|None=None,persona:dict[str,Any]|None=None,lingua_state_root:Path|None=None)->tuple[str,dict[str,Any]]:
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
        state_root=lingua_state_root or state_path('lingua', dio_root=dio_root),
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

def process_envelope(envelope:dict[str,Any],dio_root:Path,cfg:dict[str,Any], *, quarantined_attachments:list[dict[str,Any]]|None=None)->dict[str,Any]:
    presence_root=dio_root/str(cfg.get('state_root','state/presence')); event_log=dio_root/str(cfg.get('event_log','telemetry/dio_events.jsonl')); routes_path=dio_root/str(cfg.get('routes_path','config/routes.json'))
    lingua_root=Path(cfg.get('lingua_state_root') or state_path('lingua', dio_root=dio_root))
    role=_role(envelope); conv=load_or_create_conversation(presence_root,envelope,role); text=str(envelope.get('text') or '').strip(); correlation=conv['conversation_id']
    conversation_state=load_conversation_state(presence_root,correlation)
    recent_turns=load_recent_conversation_turns(presence_root,correlation)
    metadata=envelope.get('metadata') or {}
    interaction=observe_interaction(
        state_root=lingua_root,
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
    # Resolve explicit document work before broad greeting/formatting intents.
    # Quotation requests create governed intake only; they never issue a quote.
    document_operation = _document_operation_override(text) if role == 'public' else None
    if document_operation:
        is_quote_request = bool(re.search(r"\b(?:quote|quotation|estimate)\b", text, re.I))
        decision = {
            'intent': 'intake_request' if is_quote_request else 'product_info',
            'product': document_operation,
            'confidence': 0.99,
            'source': 'document_operation_morphology',
            'reason': 'document operation resolved before generic intent',
        }
    elif role == 'public' and re.search(r"\b(?:quote|quotation|estimate)\b", text, re.I):
        active_case = find_case_for_conversation(presence_root, correlation)
        retained_product = (
            (active_case or {}).get('product_id')
            or conversation_state.get('selected_product')
        )
        if retained_product:
            decision.update({
                'intent': 'pricing_info',
                'product': str(retained_product),
                'source': 'active_customer_case' if active_case else 'conversation_product_context',
                'reason': 'quotation follow-up retains active product context',
            })
    if (attachment_record or quarantined_attachments) and decision['intent'] in {'unknown','general_info'}:
        decision={'intent':'attachment_received','product':decision.get('product'),'confidence':1.0,'source':'attachment_policy','reason':'quarantined attachment requires human routing'}
    ok,reason=authorize(role,decision['intent'])
    if not ok: decision={'intent':'unknown','product':None,'confidence':1.0,'source':'policy','reason':reason}

    current_customer_case = find_case_for_conversation(
        presence_root,
        correlation,
    )

    buyer_scope_followup = bool(
        role == 'public'
        and current_customer_case
        and current_customer_case.get('product_id')
        and semantic_continuity.get('relation') == 'CONTINUATION'
        and semantic_continuity.get('retain_active_referent') is True
        and semantic_continuity.get('speech_act') == 'BUYER_SCOPE_REFINEMENT'
        and decision['intent'] in {'general_info', 'product_info', 'unknown', 'intake_request', 'pricing_info'}
        and attachment_record is None
        and not quarantined_attachments
    )
    buyer_scope_pricing = bool(buyer_scope_followup
                               and (semantic_continuity.get('evidence') or {}).get('price_signal'))

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

    # Canonical site context is routing context, never attachment-processing
    # authority. Advisory intent labels must not erase an exact product hint.
    explicit_site_context = str(metadata.get('incarnation_hint') or envelope.get('incarnation_hint') or '').strip()
    held_case_context = bool(quarantined_attachments and current_customer_case
                             and current_customer_case.get('product_id'))
    contextual_product_turn = bool(role == 'public' and text.strip()
                                   and (explicit_site_context or held_case_context))
    commercial=None
    if should_ground_commercial(
        role=role,
        intent=decision['intent'],
        text=text,
        attachment_present=bool(attachment_record),
    ) or buyer_scope_followup or contextual_product_turn:
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

            commercial_probe=build_commercial_grounding(dio_root, text)
            if commercial_probe.get('resolution_basis') == 'multiple_explicit_products':
                commercial=commercial_probe
            elif commercial_probe.get('resolution_basis') == 'single_explicit_product':
                commercial=commercial_probe
            elif explicit_incarnation_hint:
                commercial=build_commercial_grounding(
                    dio_root,
                    text,
                    incarnation_hint=explicit_incarnation_hint,
                    context_tier_hint=persisted_tier_hint,
                )
            elif buyer_scope_followup or held_case_context:
                commercial=build_commercial_grounding(
                    dio_root, text,
                    incarnation_hint=str(current_customer_case['product_id']),
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
    summary=None; needs=None; intake=None; statuses=None; capital=None; pricing=None
    customer_case=_bind_live_customer_case(
        presence_root=presence_root,
        conv=conv,
        correlation=correlation,
        envelope=envelope,
        attachment_record=attachment_record,
        commercial=commercial,
        quarantined_attachments=quarantined_attachments,
    )
    scope_observation_written = False
    if role == "public" and customer_case is not None:
        before_hashes = {
            str(row.get("message_sha256") or "")
            for row in (((customer_case.get("scope") or {}).get("customer_stated") or {}).get("observations") or [])
            if isinstance(row, dict)
        }
        customer_case = _merge_case_scope_observations(
            dio_root,
            presence_root,
            customer_case,
            text=text,
            recent_turns=recent_turns,
            source_message_id=str(envelope.get("source_message_id") or metadata.get("source_message_id") or "") or None,
        )
        after_hashes = {
            str(row.get("message_sha256") or "")
            for row in (((customer_case.get("scope") or {}).get("customer_stated") or {}).get("observations") or [])
            if isinstance(row, dict)
        }
        scope_observation_written = bool(after_hashes - before_hashes)

        # Preserve one canonical intake across follow-up messages and uploads.
        # This path is shared by the full catalog; it does not depend on a
        # product-specific script or a classifier's attachment intent.
        has_upload = bool(attachment_record or quarantined_attachments)
        intake_requested = decision.get("intent") == "intake_request"
        if (has_upload or intake_requested) and customer_case.get("product_id"):
            attachment_ids = [
                str(row.get("attachment_id"))
                for row in ([attachment_record] if attachment_record else list(quarantined_attachments or []))
                if isinstance(row, dict) and row.get("attachment_id")
            ]
            intake = _upsert_presence_intake(
                presence_root,
                conv,
                product=str(customer_case["product_id"]),
                summary=text,
                source_message_id=str(envelope.get("source_message_id") or metadata.get("source_message_id") or "") or None,
                attachment_ids=attachment_ids,
                case=customer_case,
            )
            conversation_state["active_intake_id"] = intake.get("intake_id")
            customer_case = load_case(presence_root, str(customer_case.get("case_id"))) or customer_case
            customer_case = _ensure_intake_review_task(
                presence_root,
                customer_case,
                conversation_id=correlation,
                intake_id=str(intake.get("intake_id") or ""),
            ) or customer_case

        # Quarantine review is created from custody state, independently of
        # the intent classifier, and remains explicitly unapproved.
        has_pending_quarantine = any(
            isinstance(row, dict)
            and str(row.get("state") or "").casefold() == "quarantined"
            and str(row.get("review_state") or "ATTACHMENT_QUARANTINED") != "SAMPLE_REVIEW_APPROVED"
            for row in customer_case.get("attachments") or []
        )
        if has_pending_quarantine:
            customer_case = _ensure_quarantine_review_task(
                presence_root,
                customer_case,
                conversation_id=correlation,
            ) or customer_case
        canonical_intake_id = str(customer_case.get("presence_intake_id") or "").strip()
        if canonical_intake_id:
            customer_case = _ensure_intake_review_task(
                presence_root,
                customer_case,
                conversation_id=correlation,
                intake_id=canonical_intake_id,
            ) or customer_case

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
        state_root=lingua_root,
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
    voice_plan=build_voice_plan(root=dio_root,language=target_language,interaction=interaction,public_default_only=True)
    voice_profile_id=voice_plan.get('profile_id')
    emit_event(event_log,'presence.persona_assigned','info','vesper_persona',persona['assignment_id'],{'experimental_assignment':persona.get('experimental_assignment'),'cell_id':((persona.get('package') or {}).get('cell_id')),'persona_id':((persona.get('package') or {}).get('persona_id')),'avatar_id':((persona.get('package') or {}).get('avatar_id')),'voice_profile_id':voice_profile_id,'stable_for_conversation':True},correlation)
    if decision['intent'] in CAPITAL_INTENTS:
        capital=capital_query(dio_root,decision['intent'],text)
    elif decision['intent']=='pricing_info' and role=='operator':
        pricing=pricing_operator_query(dio_root,state_root=presence_root,text=text,product_hint=decision.get('product'))
    elif decision['intent'] in {'operator_summary','campaign_summary','revenue_summary','mail_summary','job_summary'}: summary=operator_summary(dio_root,presence_root)
    elif decision['intent']=='needs_you': needs=list_needs_you(presence_root,20)
    elif decision['intent']=='intake_request' and decision.get('product') and not buyer_scope_followup:
        if intake is None:
            intake = _upsert_presence_intake(
                presence_root, conv, product=str(decision['product']), summary=text,
                source_message_id=str(envelope.get('source_message_id') or metadata.get('source_message_id') or '') or None,
                attachment_ids=[attachment_record['attachment_id']] if attachment_record else [],
                case=customer_case,
            )
        conversation_state['active_intake_id'] = intake['intake_id']
        customer_case = _ensure_intake_review_task(
            presence_root, customer_case, conversation_id=correlation,
            intake_id=str(intake.get('intake_id') or ''),
        ) or customer_case
        item = None
        for path in (presence_root / 'needs_you').glob('*.json'):
            try:
                candidate = read_json(path)
            except Exception:
                continue
            if candidate.get('reason') == 'public_intake_review' and candidate.get('conversation_id') == correlation and intake['intake_id'] in str(candidate.get('summary') or ''):
                item = candidate
                break
        if item is None:
            item=create_needs_you(presence_root,reason='public_intake_review',conversation_id=correlation,product=decision['product'],summary=f"Review {decision['product']} intake {intake['intake_id']}: {text[:300]}")
        emit_event(event_log,'presence.intake_received','action','presence_intake',intake['intake_id'],{'product':decision['product'],'needs_you_id':item['needs_you_id'],'automatic_fulfilment':False,'attachment_ids':intake.get('attachment_ids',[])},correlation)
    elif decision['intent']=='attachment_received' and quarantined_attachments and not attachment_record:
        held_ids=[row['attachment_id'] for row in quarantined_attachments]
        item=None
        if customer_case is None:
            item=create_needs_you(presence_root,reason='public_attachment_review',conversation_id=correlation,product=decision.get('product'),summary='Review quarantined web attachments: '+', '.join(held_ids))
        if item:
            emit_event(event_log,'presence.attachment_review_required','action','presence_conversation',correlation,{'needs_you_id':item['needs_you_id'],'attachment_ids':held_ids},correlation)
    elif decision['intent']=='attachment_received' and attachment_record:
        item=None
        if customer_case is None:
            item=create_needs_you(presence_root,reason='public_attachment_review',conversation_id=correlation,product=decision.get('product'),summary=f"Review quarantined attachment {attachment_record['attachment_id']}: {attachment_record['original_file_name']}")
        if item:
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
    facts += '\nintake_created=' + str(intake is not None).lower()
    opened = bool(customer_case and (customer_case.get('stage') == 'INTAKE_OPEN'
                  or any(row.get('stage') == 'INTAKE_OPEN' for row in customer_case.get('stage_history') or [])))
    facts += '\njourney_intake_open=' + str(opened).lower()

    journey_view = None
    intake_profile = None
    journey_intake_reply_applied = False
    if role == 'public' and customer_case is not None:
        journey_view = build_vesper_journey_view(customer_case)
        canonical_name = str(customer_case.get('product_id') or '')
        if canonical_name:
            intake_profile = compile_product_journey_binding(dio_root, canonical_name)['intake_profile']
        if not buyer_scope_pricing and (decision['intent'] == 'intake_request' or buyer_scope_followup) and intake is None and intake_profile:
            # A model advisory is not intake acceptance. A resolved canonical
            # case must not fall through to the legacy "unknown product" reply.
            fallback = _case_intake_reply(canonical_name, intake_profile, customer_case,
                                          buyer_context_refined=semantic_continuity.get('speech_act') == 'BUYER_SCOPE_REFINEMENT')
            journey_intake_reply_applied = True
            facts += '\nCANONICAL_JOURNEY=' + json.dumps(journey_view, sort_keys=True)
            facts += '\nINTAKE_REQUIREMENTS=' + json.dumps(intake_profile, sort_keys=True)

    grounded_facts=facts
    if commercial is not None:
        grounded_facts=(
            facts
            + '\n'
            + commercial_facts(commercial)
        )
        if not journey_intake_reply_applied and (decision['intent'] in {
            'unknown',
            'product_info',
            'pricing_info',
        } or buyer_scope_followup or (decision['intent'] == 'intake_request' and intake is None and not intake_profile)):
            grounded_fallback=commercial_fallback(
                commercial,
                intent='pricing_info' if buyer_scope_pricing else decision['intent'],
            )
            if grounded_fallback:
                fallback=grounded_fallback

    knowledge=retrieve_conversation_knowledge(
        dio_root,
        text,
        conversation_state,
    )

    governed_context=dict(knowledge)
    if journey_view is not None:
        governed_context['journey_view'] = journey_view
        governed_context['intake_profile'] = intake_profile

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

    semantic_utterance=text or ('[Attachment-only transport event; no customer utterance.]' if attachment_record or quarantined_attachments else '')
    semantic_evidence['customer_utterance_present']=bool(text)
    current_semantic_context=(
        build_current_semantic_context(
            role=role,
            text=semantic_utterance,
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
    if role == 'public' and document_operation == 'Document Studio Edit' and not re.search(r"\b(?:quote|quotation|estimate)\b", text, re.I):
        reply = _document_edit_discovery_reply()
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

    document_quote_reply = None
    quote_case = customer_case
    if (
        quote_case is None
        and role == "public"
        and re.search(r"\b(?:quote|quotation|estimate)\b", text, re.I)
        and str(decision.get("product") or "") in {
            "Document Studio Edit", "Document Studio Localize", "Document Studio Publish"
        }
    ):
        # A missing commercial census must not erase the product already
        # selected in this conversation or trigger unrelated sibling guesses.
        quote_case = {"product_id": decision["product"], "stage": "NEW_LEAD", "attachments": []}
    if (
        role == "public"
        and quote_ready_reply is None
        and case_price_reply is None
        and isinstance(quote_case, dict)
    ):
        document_quote_reply = _document_quote_scope_reply(
            str(quote_case.get("product_id") or ""),
            quote_case,
            text,
            presence_root=presence_root,
            conversation_id=correlation,
            intake_reference_hint=str(
                (intake or {}).get("intake_id")
                or conversation_state.get("active_intake_id")
                or ""
            ) or None,
        )

    if document_quote_reply is not None:
        reply = document_quote_reply

    # Canonical case state outranks product-specific canned copy. The same
    # response builder applies to every product, and reports only the current
    # custody/review state plus customer-stated scope.
    case_scope = ((customer_case or {}).get("scope") or {}).get("customer_stated") or {}
    case_has_scope = bool(case_scope.get("observations"))
    quote_followup = bool(re.search(r"\b(?:quote|quotation|estimate|price|pricing)\b", text, re.I))
    if (
        role == "public"
        and isinstance(customer_case, dict)
        and (scope_observation_written or attachment_record or quarantined_attachments or (case_has_scope and quote_followup))
    ):
        intake_reference = str(
            (intake or {}).get("intake_id")
            or customer_case.get("presence_intake_id")
            or conversation_state.get("active_intake_id")
            or ""
        ) or None
        reply = _case_scope_progress_reply(customer_case, intake_reference=intake_reference)

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
        reply,lingua=_lingua_reply(dio_root=dio_root,envelope=envelope,decision=decision,role=role,correlation=correlation,reply=reply,interaction=interaction,persona=persona,lingua_state_root=lingua_root)
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
    return {'schema':'dio.presence_response.v2','conversation_id':correlation,'role':role,'decision':decision,'reply':{'text':reply,'mode':'text','voice_eligible':bool(envelope.get('message_type') in {'voice','audio'}),'voice_policy':policy.get('voice'),'voice_plan':voice_plan,'avatar_id':((persona.get('package') or {}).get('avatar_id'))},'authority':{'executed_external_action':False,'spend_authorized':False,'fulfilment_released':False,'attachment_processed':False,'send_authorized':False,'submission_authorized':False,'financial_commitment_authorized':False},'customer_case':({key:customer_case.get(key) for key in ('case_id','stage','product_id')} if customer_case else None),'attachment':attachment_record,'intake':intake,'status':statuses,'capital':capital,'pricing':pricing,'commercial':commercial,'commercial_action':commercial_action,'interaction':interaction,'persona':persona,'lingua':lingua}
