from __future__ import annotations

from typing import Any

from .semantic import (
    SCHEMA,
    assert_valid_commercial_semantic_object,
    market_signal,
    semantic_claim,
    semantic_value,
    stable_semantic_object_id,
    timestamp,
    unknown,
)


SIGNAL_NAMES = (
    "audience_demand",
    "content_gap",
    "series_potential",
    "visual_potential",
    "monetization_alignment",
    "evidence_availability",
    "production_burden",
    "policy_risk",
    "freshness_risk",
    "studio_authority_fit",
)


def _score_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if payload.get("schema") == "dio.nichefoundry.score_receipt.v1":
        scored = payload.get("scored_opportunity") or {}
        audience_fit = payload.get("audience_fit") or {}
        return scored, audience_fit
    return payload, payload.get("audience_fit") or {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _signal_from_nichefoundry(
    name: str,
    scored: dict[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    """Project a NicheFoundry score without confusing a score with a measurement.

    NicheFoundry currently distinguishes proxy heuristics, studio-engine values and a
    combined `operator_or_provider_signal` category. DIO intentionally treats all three
    as derived unless an explicit measurement record supplies measurement identity,
    observation time and source references. This prevents operator priors from silently
    becoming observed market facts.
    """
    normalized = scored.get("normalized_signals") or {}
    provenance = scored.get("signal_provenance") or {}
    evidence = (scored.get("signal_evidence") or {}).get(name) or {}
    value = normalized.get(name)
    if value is None:
        return market_signal(state="unknown")

    evidence_refs = [str(ref).strip() for ref in evidence.get("source_refs") or [] if str(ref).strip()]
    evidence_state = str(evidence.get("state") or evidence.get("kind") or "").lower()
    measurement = _text(evidence.get("measurement"))
    observed_at = _text(evidence.get("observed_at"))
    evidence_value = evidence.get("value")
    if (
        evidence_state in {"observed", "measurement"}
        and evidence_refs
        and measurement
        and observed_at
        and evidence_value is not None
    ):
        return market_signal(
            float(evidence_value),
            state="observed",
            source_refs=evidence_refs,
            provenance=_text(evidence.get("provenance")) or "explicit_measurement_record",
            measurement=measurement,
            observed_at=observed_at,
        )

    provenance_name = _text(provenance.get(name)) or "nichefoundry_unlabelled_derived_signal"
    method_by_provenance = {
        "documented_proxy_heuristic": "nichefoundry_documented_proxy_heuristic",
        "studio_pack_fit_engine": "nichefoundry_studio_pack_fit_engine",
        "operator_or_provider_signal": "nichefoundry_operator_or_provider_signal_unresolved",
    }
    return market_signal(
        float(value),
        state="derived",
        source_refs=[source_ref],
        provenance=provenance_name,
        method=method_by_provenance.get(provenance_name, "nichefoundry_derived_signal"),
    )


def _derived_score(value: Any, name: str, source_ref: str) -> dict[str, Any]:
    if value is None:
        return market_signal(state="unknown")
    return market_signal(
        float(value),
        state="derived",
        source_refs=[source_ref],
        provenance="nichefoundry_scoring_engine",
        method=f"nichefoundry_{name}",
    )


def commercial_semantic_object_from_nichefoundry(
    score_payload: dict[str, Any],
    *,
    campaign_record: dict[str, Any] | None = None,
    market_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a pre-lead CSO from NicheFoundry opportunity and audience semantics.

    The bridge preserves NicheFoundry strategy and scoring while refusing to promote
    target personas, heuristics, operator priors or model scores into customer facts.
    A campaign can therefore carry rich meaning before a lead exists without acquiring
    customer identity, consent, scope or demand authority it has not earned.
    """
    campaign_record = campaign_record or {}
    market_observation = market_observation or {}
    scored, audience_fit = _score_payload(score_payload)
    opportunity_id = _text(scored.get("opportunity_id"))
    campaign_id = _text(campaign_record.get("campaign_id"))
    hypothesis_id = _text(campaign_record.get("hypothesis_id"))
    if not (opportunity_id or campaign_id or hypothesis_id):
        raise ValueError("NicheFoundry semantic bridge requires opportunity_id, campaign_id, or hypothesis_id")

    nf_ref = f"nichefoundry:{opportunity_id or 'unidentified'}"
    campaign_ref = f"campaign:{campaign_id}" if campaign_id else None
    hypothesis_ref = f"hypothesis:{hypothesis_id}" if hypothesis_id else None
    observation_id = _text(market_observation.get("observation_id"))
    observation_ref = f"market_observation:{observation_id}" if observation_id else None
    source_refs = [ref for ref in (nf_ref, campaign_ref, hypothesis_ref, observation_ref) if ref]

    product_record = campaign_record.get("product") or {}
    audience_record = campaign_record.get("audience") or {}
    experiment = campaign_record.get("experiment") or {}
    gates = campaign_record.get("gates") or {}
    product = _text(product_record.get("public_name") or product_record.get("product_layer"))
    offer = _text(product_record.get("offer_id"))
    public_segment = _text(audience_record.get("public_segment"))
    channel = _text(experiment.get("channel"))
    public_outreach_allowed = str(gates.get("electronic_sales_outreach") or "").lower() == "allowed"

    persona = audience_fit.get("persona") or None
    viewer_job_fit = audience_fit.get("viewer_job") or None
    content_pillar = audience_fit.get("content_pillar") or None
    desired_reward = _text(audience_fit.get("desired_reward"))
    likely_next_action = _text(audience_fit.get("likely_next_action"))
    viewer_job = _text(scored.get("viewer_job"))
    angle = _text(scored.get("angle"))
    campaign_hypothesis = _text(campaign_record.get("hypothesis"))

    observation_signals = market_observation.get("signals") or {}
    trigger = _text(observation_signals.get("seasonal_trigger"))
    why_now = _text(observation_signals.get("seasonal_urgency"))

    now = timestamp()
    object_id = stable_semantic_object_id(campaign_id, hypothesis_id, opportunity_id, product, offer)

    verified_facts: list[dict[str, Any]] = []
    for label, value, refs in (
        ("campaign_id", campaign_id, [campaign_ref] if campaign_ref else []),
        ("hypothesis_id", hypothesis_id, [hypothesis_ref] if hypothesis_ref else []),
        ("configured product", product, [campaign_ref] if campaign_ref else [nf_ref]),
        ("configured offer", offer, [campaign_ref] if campaign_ref else [nf_ref]),
        ("configured public segment", public_segment, [campaign_ref] if campaign_ref else [nf_ref]),
        ("publication gate", gates.get("publication"), [campaign_ref] if campaign_ref else []),
        ("electronic outreach gate", gates.get("electronic_sales_outreach"), [campaign_ref] if campaign_ref else []),
    ):
        if value and refs:
            verified_facts.append(
                semantic_claim(
                    f"{label}: {value}",
                    status="verified",
                    source_refs=refs,
                    authority="campaign_record",
                )
            )

    inferred_hypotheses: list[dict[str, Any]] = []
    for statement, method in (
        (campaign_hypothesis, "hivenance_marketing_hypothesis"),
        (angle, "nichefoundry_opportunity_angle"),
        (viewer_job, "nichefoundry_viewer_job"),
        (_text(audience_fit.get("value_proposition")), "nichefoundry_audience_fit"),
    ):
        if statement:
            inferred_hypotheses.append(
                semantic_claim(
                    statement,
                    status="inferred",
                    source_refs=[nf_ref] if method.startswith("nichefoundry") else ([hypothesis_ref] if hypothesis_ref else [nf_ref]),
                    authority="strategy_only",
                    method=method,
                )
            )

    explicit_unknowns = [
        unknown("subject.organisation", "Pre-lead campaign strategy does not identify an actual customer organisation.", source_refs=source_refs),
        unknown("subject.buyer_role", "A NicheFoundry persona is a target model, not a verified buyer role.", source_refs=[nf_ref]),
        unknown("subject.organisation_type", "Public segment strategy does not establish an actual customer organisation type.", source_refs=source_refs),
        unknown("need.workflow_pain", "Campaign pain remains a market hypothesis until a customer or authoritative observation confirms it.", source_refs=source_refs),
        unknown("commercial.scope", "No customer scope exists before qualification.", source_refs=source_refs),
        unknown("market.measured_customer_demand", "NicheFoundry opportunity scoring is not customer-demand measurement.", source_refs=[nf_ref]),
        unknown("market.product_market_fit", "No product-market-fit authority is granted by a NicheFoundry score.", source_refs=[nf_ref]),
        unknown("customer.budget", "No customer budget is established by market strategy.", source_refs=source_refs),
    ]

    signals = {
        name: _signal_from_nichefoundry(name, scored, nf_ref)
        for name in SIGNAL_NAMES
    }
    scoring = {
        "opportunity_score": _derived_score(scored.get("opportunity_score"), "opportunity_score", nf_ref),
        "score_confidence": _derived_score(scored.get("score_confidence"), "score_confidence", nf_ref),
        "benefit_index": _derived_score(scored.get("benefit_index"), "benefit_index", nf_ref),
        "risk_index": _derived_score(scored.get("risk_index"), "risk_index", nf_ref),
        "decision": semantic_value(
            scored.get("decision"),
            status="inferred",
            source_refs=[nf_ref],
            authority="strategy_only",
            method="nichefoundry_opportunity_decision",
        ) if scored.get("decision") else semantic_value(status="unknown"),
    }

    relevant_proof = list(dict.fromkeys(
        str(value).strip()
        for value in [*(scored.get("source_hints") or []), experiment.get("proof_asset")]
        if str(value or "").strip()
    ))

    consent_state = (
        "registry_permission_basis_recorded_operator_gate_still_required"
        if public_outreach_allowed
        else "public_content_only_no_direct_outreach_authority"
    )
    authority_state = (
        "market_strategy_with_permission_basis_operator_gate_required"
        if public_outreach_allowed
        else "market_strategy_public_content_only"
    )

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "object_id": object_id,
        "created_at": now,
        "updated_at": now,
        "lineage": {
            "lead_id": None,
            "conversation_id": None,
            "transaction_id": None,
            "prospect_id": None,
            "campaign_id": campaign_id,
            "hypothesis_id": hypothesis_id,
            "opportunity_id": opportunity_id,
        },
        "subject": {
            "organisation": semantic_value(status="unknown"),
            "buyer_role": semantic_value(status="unknown"),
            "organisation_type": semantic_value(status="unknown"),
            "relationship_state": semantic_value(
                "pre_lead_market_hypothesis",
                status="verified",
                source_refs=[campaign_ref] if campaign_ref else [nf_ref],
                authority="system_state",
            ),
            "consent_state": semantic_value(
                consent_state,
                status="verified",
                source_refs=[campaign_ref] if campaign_ref else [nf_ref],
                authority="campaign_gate",
            ),
        },
        "truth": {
            "verified_facts": verified_facts,
            "inferred_hypotheses": inferred_hypotheses,
            "unknowns": explicit_unknowns,
        },
        "need": {
            "job_to_be_done": semantic_value(
                viewer_job,
                status="inferred",
                source_refs=[nf_ref],
                authority="strategy_only",
                method="nichefoundry_viewer_job",
            ) if viewer_job else semantic_value(status="unknown"),
            "workflow_pain": semantic_value(status="unknown"),
            "trigger": semantic_value(
                trigger,
                status="inferred",
                source_refs=[observation_ref] if observation_ref else [nf_ref],
                authority="market_observation",
                method="registry_market_signal",
            ) if trigger else semantic_value(status="unknown"),
            "why_now": semantic_value(
                why_now,
                status="inferred",
                source_refs=[observation_ref] if observation_ref else [nf_ref],
                authority="market_observation",
                method="registry_market_signal",
            ) if why_now else semantic_value(status="unknown"),
        },
        "commercial": {
            "product": semantic_value(
                product,
                status="verified",
                source_refs=[campaign_ref] if campaign_ref else [nf_ref],
                authority="campaign_record",
            ) if product else semantic_value(status="unknown"),
            "offer": semantic_value(
                offer,
                status="verified",
                source_refs=[campaign_ref] if campaign_ref else [nf_ref],
                authority="campaign_record",
            ) if offer else semantic_value(status="unknown"),
            "scope": semantic_value(status="unknown"),
        },
        "proof": {
            "relevant_proof": relevant_proof,
            "permitted_claims": [
                "configured_campaign_target_segment",
                "nichefoundry_strategy_is_derived",
                "proof_asset_may_be_referenced_subject_to_review",
            ],
            "prohibited_claims": [
                "measured_customer_demand",
                "verified_customer_workflow_pain",
                "product_market_fit",
                "paid_conversion",
                "customer_budget",
                "agreed_customer_scope",
                "personalised_outreach_authority" if not public_outreach_allowed else "unreviewed_personalised_outreach",
            ],
        },
        "strategy": {
            "desired_next_action": semantic_value(
                likely_next_action,
                status="inferred",
                source_refs=[nf_ref],
                authority="strategy_only",
                method="nichefoundry_audience_fit",
            ) if likely_next_action else semantic_value(status="unknown"),
            "channel": semantic_value(
                channel,
                status="verified",
                source_refs=[campaign_ref] if campaign_ref else [nf_ref],
                authority="campaign_record",
            ) if channel else semantic_value(status="unknown"),
            "communicative_act": semantic_value(
                "proof_led_campaign_content",
                status="inferred",
                source_refs=[nf_ref],
                authority="strategy_only",
                method="nichefoundry_content_role",
            ),
            "tone": semantic_value(status="unknown"),
            "length": semantic_value(status="unknown"),
            "rhetorical_strategy": semantic_value(
                angle,
                status="inferred",
                source_refs=[nf_ref],
                authority="strategy_only",
                method="nichefoundry_opportunity_angle",
            ) if angle else semantic_value(status="unknown"),
        },
        "market_context": {
            "source_system": "nichefoundry",
            "opportunity": {
                "title": semantic_value(scored.get("title"), status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_opportunity") if scored.get("title") else semantic_value(status="unknown"),
                "topic": semantic_value(scored.get("topic"), status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_opportunity") if scored.get("topic") else semantic_value(status="unknown"),
                "angle": semantic_value(angle, status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_opportunity") if angle else semantic_value(status="unknown"),
                "content_role": semantic_value(scored.get("content_role"), status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_role_classifier") if scored.get("content_role") else semantic_value(status="unknown"),
                "series_hint": semantic_value(scored.get("series_hint"), status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_opportunity") if scored.get("series_hint") else semantic_value(status="unknown"),
            },
            "audience": {
                "public_segment": semantic_value(public_segment, status="verified", source_refs=[campaign_ref] if campaign_ref else [nf_ref], authority="campaign_record") if public_segment else semantic_value(status="unknown"),
                "primary_persona": semantic_value(persona, status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_audience_fit") if persona else semantic_value(status="unknown"),
                "viewer_job": semantic_value(viewer_job_fit or viewer_job, status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_audience_fit") if (viewer_job_fit or viewer_job) else semantic_value(status="unknown"),
                "content_pillar": semantic_value(content_pillar, status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_audience_fit") if content_pillar else semantic_value(status="unknown"),
                "desired_reward": semantic_value(desired_reward, status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_audience_fit") if desired_reward else semantic_value(status="unknown"),
                "likely_next_action": semantic_value(likely_next_action, status="inferred", source_refs=[nf_ref], authority="strategy_only", method="nichefoundry_audience_fit") if likely_next_action else semantic_value(status="unknown"),
            },
            "signals": signals,
            "scoring": scoring,
            "source_refs": source_refs,
        },
        "authority": {
            "authority_state": authority_state,
            "evidence_refs": source_refs,
            "attribution": {
                "campaign_id": campaign_id,
                "hypothesis_id": hypothesis_id,
                "opportunity_id": opportunity_id,
                "publication_gate": gates.get("publication"),
                "electronic_sales_outreach": gates.get("electronic_sales_outreach"),
            },
        },
        "provenance": {
            "adapter": "commerce.nichefoundry_bridge.commercial_semantic_object_from_nichefoundry",
            "adapter_version": 1,
            "source_schema": score_payload.get("schema") or scored.get("schema") or "unknown",
            "source_ref": nf_ref,
        },
    }
    assert_valid_commercial_semantic_object(result)
    return result
