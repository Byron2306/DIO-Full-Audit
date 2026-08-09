from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA = "dio.commercial_semantic_object.v1"
EPISTEMIC_STATES = frozenset({"verified", "inferred", "unknown"})
MARKET_SIGNAL_STATES = frozenset({"observed", "derived", "unknown"})


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _source_refs(values: Iterable[Any] | None) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in (values or []) if str(value).strip()))


def stable_semantic_object_id(*parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper()
    return f"CSO-{digest}"


def semantic_value(
    value: Any = None,
    *,
    status: str,
    source_refs: Iterable[Any] | None = None,
    authority: str | None = None,
    confidence: float | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    """Build one epistemically labelled semantic value.

    `verified` means DIO has evidence for the value itself, not merely evidence that
    somebody asserted it. `inferred` means the value remains a hypothesis and must
    retain its basis. `unknown` is an explicit first-class state, never a placeholder
    score or fabricated default.
    """
    item: dict[str, Any] = {
        "value": value,
        "status": status,
        "source_refs": _source_refs(source_refs),
    }
    if authority:
        item["authority"] = str(authority)
    if confidence is not None:
        item["confidence"] = float(confidence)
    if method:
        item["method"] = str(method)
    return item


def market_signal(
    value: float | None = None,
    *,
    state: str,
    source_refs: Iterable[Any] | None = None,
    provenance: str | None = None,
    method: str | None = None,
    measurement: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build a market signal without laundering a score into an observation.

    `observed` is reserved for measured values carrying measurement identity,
    observation time and source references. `derived` covers heuristics, model scores,
    operator/provider priors and other transformations. `unknown` carries no number.
    """
    item: dict[str, Any] = {
        "value": None if state == "unknown" else (float(value) if value is not None else None),
        "state": state,
        "source_refs": _source_refs(source_refs),
    }
    if provenance:
        item["provenance"] = str(provenance)
    if method:
        item["method"] = str(method)
    if measurement:
        item["measurement"] = str(measurement)
    if observed_at:
        item["observed_at"] = str(observed_at)
    return item


def semantic_claim(
    statement: str,
    *,
    status: str,
    source_refs: Iterable[Any] | None = None,
    authority: str | None = None,
    confidence: float | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    claim: dict[str, Any] = {
        "statement": str(statement).strip(),
        "status": status,
        "source_refs": _source_refs(source_refs),
    }
    if authority:
        claim["authority"] = str(authority)
    if confidence is not None:
        claim["confidence"] = float(confidence)
    if method:
        claim["method"] = str(method)
    return claim


def unknown(field: str, reason: str, *, source_refs: Iterable[Any] | None = None) -> dict[str, Any]:
    return {
        "field": str(field),
        "reason": str(reason),
        "status": "unknown",
        "source_refs": _source_refs(source_refs),
    }


def _validate_semantic_value(path: str, item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object")
        return
    status = item.get("status")
    if status not in EPISTEMIC_STATES:
        errors.append(f"{path}.status must be one of {sorted(EPISTEMIC_STATES)}")
        return
    refs = item.get("source_refs")
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        errors.append(f"{path}.source_refs must be a list of non-empty strings")
        refs = []
    value = item.get("value")
    if status == "unknown":
        if value is not None:
            errors.append(f"{path}.value must be null when status=unknown")
        if item.get("confidence") is not None:
            errors.append(f"{path}.confidence is not permitted when status=unknown")
    else:
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{path}.value is required when status={status}")
        if not refs:
            errors.append(f"{path}.source_refs must preserve evidence/basis when status={status}")
    confidence = item.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0.0 <= float(confidence) <= 1.0):
        errors.append(f"{path}.confidence must be between 0 and 1")


def _validate_market_signal(path: str, item: Any, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object")
        return
    state = item.get("state")
    if state not in MARKET_SIGNAL_STATES:
        errors.append(f"{path}.state must be one of {sorted(MARKET_SIGNAL_STATES)}")
        return
    refs = item.get("source_refs")
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        errors.append(f"{path}.source_refs must be a list of non-empty strings")
        refs = []
    value = item.get("value")
    if state == "unknown":
        if value is not None:
            errors.append(f"{path}.value must be null when state=unknown")
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"{path}.value must be numeric when state={state}")
    if not refs:
        errors.append(f"{path}.source_refs must preserve evidence/basis when state={state}")
    if state == "derived":
        if not str(item.get("provenance") or "").strip():
            errors.append(f"{path}.provenance is required when state=derived")
        if not str(item.get("method") or "").strip():
            errors.append(f"{path}.method is required when state=derived")
    if state == "observed":
        if not str(item.get("measurement") or "").strip():
            errors.append(f"{path}.measurement is required when state=observed")
        if not str(item.get("observed_at") or "").strip():
            errors.append(f"{path}.observed_at is required when state=observed")


def _validate_claim(path: str, item: Any, expected_status: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object")
        return
    if item.get("status") != expected_status:
        errors.append(f"{path}.status must be {expected_status}")
    if not str(item.get("statement") or "").strip():
        errors.append(f"{path}.statement is required")
    refs = item.get("source_refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        errors.append(f"{path}.source_refs must preserve at least one evidence/basis reference")
    confidence = item.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0.0 <= float(confidence) <= 1.0):
        errors.append(f"{path}.confidence must be between 0 and 1")


def _validate_market_context(context: Any, errors: list[str]) -> None:
    if not isinstance(context, dict):
        errors.append("market_context must be an object")
        return
    if not str(context.get("source_system") or "").strip():
        errors.append("market_context.source_system is required")
    for section, fields in {
        "opportunity": ("title", "topic", "angle", "content_role", "series_hint"),
        "audience": ("public_segment", "primary_persona", "viewer_job", "content_pillar", "desired_reward", "likely_next_action"),
    }.items():
        body = context.get(section)
        if not isinstance(body, dict):
            errors.append(f"market_context.{section} must be an object")
            continue
        for field in fields:
            if field not in body:
                errors.append(f"market_context.{section}.{field} is required")
            else:
                _validate_semantic_value(f"market_context.{section}.{field}", body[field], errors)
    signals = context.get("signals")
    if not isinstance(signals, dict):
        errors.append("market_context.signals must be an object")
    else:
        for name, item in signals.items():
            _validate_market_signal(f"market_context.signals.{name}", item, errors)
    scoring = context.get("scoring")
    if not isinstance(scoring, dict):
        errors.append("market_context.scoring must be an object")
    else:
        for field in ("opportunity_score", "score_confidence", "benefit_index", "risk_index"):
            if field not in scoring:
                errors.append(f"market_context.scoring.{field} is required")
            else:
                _validate_market_signal(f"market_context.scoring.{field}", scoring[field], errors)
        if "decision" not in scoring:
            errors.append("market_context.scoring.decision is required")
        else:
            _validate_semantic_value("market_context.scoring.decision", scoring["decision"], errors)
    refs = context.get("source_refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        errors.append("market_context.source_refs must preserve at least one source reference")


def validate_commercial_semantic_object(payload: Any) -> list[str]:
    """Return semantic-contract violations without mutating the payload."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["commercial semantic object must be a mapping"]
    if payload.get("schema") != SCHEMA:
        errors.append(f"schema must equal {SCHEMA}")
    if not str(payload.get("object_id") or "").startswith("CSO-"):
        errors.append("object_id must use the CSO- prefix")

    lineage = payload.get("lineage")
    lineage_keys = (
        "lead_id", "conversation_id", "transaction_id", "prospect_id",
        "campaign_id", "hypothesis_id", "opportunity_id",
    )
    if not isinstance(lineage, dict) or not any(lineage.get(key) for key in lineage_keys):
        errors.append("lineage must preserve at least one lead/conversation/transaction/prospect/campaign/hypothesis/opportunity identifier")

    semantic_paths = {
        "subject": ("organisation", "buyer_role", "organisation_type", "relationship_state", "consent_state"),
        "need": ("job_to_be_done", "workflow_pain", "trigger", "why_now"),
        "commercial": ("product", "offer", "scope"),
        "strategy": ("desired_next_action", "channel", "communicative_act", "tone", "length", "rhetorical_strategy"),
    }
    for section, fields in semantic_paths.items():
        body = payload.get(section)
        if not isinstance(body, dict):
            errors.append(f"{section} must be an object")
            continue
        for field in fields:
            if field not in body:
                errors.append(f"{section}.{field} is required")
            else:
                _validate_semantic_value(f"{section}.{field}", body[field], errors)

    truth = payload.get("truth")
    if not isinstance(truth, dict):
        errors.append("truth must be an object")
    else:
        verified = truth.get("verified_facts")
        inferred = truth.get("inferred_hypotheses")
        unknowns = truth.get("unknowns")
        if not isinstance(verified, list):
            errors.append("truth.verified_facts must be a list")
        else:
            for index, claim in enumerate(verified):
                _validate_claim(f"truth.verified_facts[{index}]", claim, "verified", errors)
        if not isinstance(inferred, list):
            errors.append("truth.inferred_hypotheses must be a list")
        else:
            for index, claim in enumerate(inferred):
                _validate_claim(f"truth.inferred_hypotheses[{index}]", claim, "inferred", errors)
        if not isinstance(unknowns, list):
            errors.append("truth.unknowns must be a list")
        else:
            for index, row in enumerate(unknowns):
                if not isinstance(row, dict) or row.get("status") != "unknown" or not str(row.get("field") or "").strip():
                    errors.append(f"truth.unknowns[{index}] must be an explicit unknown field record")

    proof = payload.get("proof")
    if not isinstance(proof, dict):
        errors.append("proof must be an object")
    else:
        for field in ("relevant_proof", "permitted_claims", "prohibited_claims"):
            if not isinstance(proof.get(field), list):
                errors.append(f"proof.{field} must be a list")

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority must be an object")
    else:
        if not str(authority.get("authority_state") or "").strip():
            errors.append("authority.authority_state is required")
        refs = authority.get("evidence_refs")
        if not isinstance(refs, list):
            errors.append("authority.evidence_refs must be a list")

    if isinstance(proof, dict):
        permitted = {str(item).strip() for item in proof.get("permitted_claims") or [] if str(item).strip()}
        prohibited = {str(item).strip() for item in proof.get("prohibited_claims") or [] if str(item).strip()}
        overlap = sorted(permitted & prohibited)
        if overlap:
            errors.append(f"claims cannot be both permitted and prohibited: {', '.join(overlap)}")

    market_context = payload.get("market_context")
    if market_context is not None:
        _validate_market_context(market_context, errors)

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("adapter") or "").strip():
        errors.append("provenance.adapter is required")
    return errors


def assert_valid_commercial_semantic_object(payload: Any) -> None:
    errors = validate_commercial_semantic_object(payload)
    if errors:
        raise ValueError("invalid commercial semantic object: " + "; ".join(errors))


def commercial_semantic_object_from_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Conservatively adapt a canonical/thin DIO lead into CSO v1.

    The adapter verifies only what the lead record itself can establish. In particular,
    free text in a request may prove that text was captured, but does not automatically
    prove the customer's underlying pain, urgency, budget, scope, or processing authority.
    """
    lead_id = str(lead.get("lead_id") or "").strip()
    conversation_id = str(lead.get("conversation_id") or "").strip() or None
    prospect_id = str(lead.get("prospect_id") or "").strip() or None
    if not (lead_id or conversation_id or prospect_id):
        raise ValueError("lead requires lead_id, conversation_id, or prospect_id")

    contact = lead.get("contact") or {}
    request = lead.get("request") or {}
    consents = lead.get("consents") or {}
    attribution = lead.get("attribution") or {}
    qualification = lead.get("qualification") or {}
    source_ref = f"lead:{lead_id}" if lead_id else f"conversation:{conversation_id}" if conversation_id else f"prospect:{prospect_id}"
    source_refs = [source_ref]
    now = timestamp()

    organisation = contact.get("organisation")
    product = lead.get("product")
    offer = lead.get("offer")
    medium = attribution.get("medium") or attribution.get("source")
    qualification_state = qualification.get("state") or lead.get("state")
    processing_confirmed = consents.get("processing_authority_confirmed") is True

    verified_facts: list[dict[str, Any]] = []
    for label, value in (
        ("lead_id", lead_id),
        ("contact email", contact.get("email")),
        ("contact name", contact.get("name")),
        ("organisation supplied in lead record", organisation),
        ("selected product", product),
        ("selected offer", offer),
        ("captured request subject", request.get("subject")),
    ):
        if value:
            verified_facts.append(semantic_claim(
                f"{label}: {value}",
                status="verified",
                source_refs=source_refs,
                authority="lead_record",
            ))

    explicit_unknowns = [
        unknown("subject.buyer_role", "Thin lead record does not establish the buyer's role.", source_refs=source_refs),
        unknown("subject.organisation_type", "Thin lead record does not establish organisation type.", source_refs=source_refs),
        unknown("need.job_to_be_done", "Request text has not yet been semantically resolved.", source_refs=source_refs),
        unknown("need.workflow_pain", "No evidence-backed workflow pain has been resolved yet.", source_refs=source_refs),
        unknown("need.trigger", "No verified commercial trigger has been resolved yet.", source_refs=source_refs),
        unknown("need.why_now", "No verified urgency or timing reason has been resolved yet.", source_refs=source_refs),
        unknown("commercial.scope", "Scope must be explicitly qualified rather than inferred from thin intake.", source_refs=source_refs),
        unknown("strategy.desired_next_action", "Next action belongs to later commercial reasoning/governance.", source_refs=source_refs),
        unknown("strategy.communicative_act", "Communicative act is assigned downstream, not by the compatibility adapter.", source_refs=source_refs),
    ]

    object_id = stable_semantic_object_id(lead_id, conversation_id, prospect_id, product, contact.get("email"))
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "object_id": object_id,
        "created_at": now,
        "updated_at": now,
        "lineage": {
            "lead_id": lead_id or None,
            "conversation_id": conversation_id,
            "transaction_id": lead.get("transaction_id"),
            "prospect_id": prospect_id,
        },
        "subject": {
            "organisation": semantic_value(organisation, status="verified", source_refs=source_refs, authority="lead_record") if organisation else semantic_value(status="unknown"),
            "buyer_role": semantic_value(status="unknown"),
            "organisation_type": semantic_value(status="unknown"),
            "relationship_state": semantic_value(qualification_state, status="verified", source_refs=source_refs, authority="lead_record") if qualification_state else semantic_value(status="unknown"),
            "consent_state": semantic_value(
                "processing_authority_confirmed" if processing_confirmed else "processing_authority_not_confirmed",
                status="verified",
                source_refs=source_refs,
                authority="lead_record",
            ),
        },
        "truth": {
            "verified_facts": verified_facts,
            "inferred_hypotheses": [],
            "unknowns": explicit_unknowns,
        },
        "need": {
            "job_to_be_done": semantic_value(status="unknown"),
            "workflow_pain": semantic_value(status="unknown"),
            "trigger": semantic_value(status="unknown"),
            "why_now": semantic_value(status="unknown"),
        },
        "commercial": {
            "product": semantic_value(product, status="verified", source_refs=source_refs, authority="lead_record") if product else semantic_value(status="unknown"),
            "offer": semantic_value(offer, status="verified", source_refs=source_refs, authority="lead_record") if offer else semantic_value(status="unknown"),
            "scope": semantic_value(status="unknown"),
        },
        "proof": {
            "relevant_proof": [],
            "permitted_claims": [
                "captured_lead_identity",
                "selected_product",
                "captured_consent_state",
            ],
            "prohibited_claims": [
                "customer_budget",
                "customer_urgency",
                "customer_workflow_pain",
                "agreed_scope",
                "processing_authority" if not processing_confirmed else "unverified_scope_authority",
            ],
        },
        "strategy": {
            "desired_next_action": semantic_value(status="unknown"),
            "channel": semantic_value(medium, status="verified", source_refs=source_refs, authority="lead_record") if medium else semantic_value(status="unknown"),
            "communicative_act": semantic_value(status="unknown"),
            "tone": semantic_value(status="unknown"),
            "length": semantic_value(status="unknown"),
            "rhetorical_strategy": semantic_value(status="unknown"),
        },
        "authority": {
            "authority_state": "lead_record_only",
            "evidence_refs": source_refs,
            "attribution": dict(attribution),
        },
        "provenance": {
            "adapter": "commerce.semantic.commercial_semantic_object_from_lead",
            "adapter_version": 1,
            "source_schema": lead.get("schema") or "unknown",
            "source_ref": source_ref,
        },
    }
    assert_valid_commercial_semantic_object(result)
    return result
